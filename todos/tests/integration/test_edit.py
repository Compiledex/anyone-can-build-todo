"""Tests for the edit page of a to-do (`/<pk>/edit/`)."""

from datetime import date

from django.test import Client
from django.urls import reverse

from accounts.tests.helpers import LoggedInTestCase
from todos.forms import TodoForm
from todos.models import Todo


class EditTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.todo = Todo.objects.create(title="Buy mlik", todo_list=self.todo_list)
        self.url = reverse("todo_edit", args=[self.todo.pk])

    def edit_data(self, todo, **changes):
        """What the edit form sends, with the current values, plus the changes."""
        form = TodoForm(instance=todo)
        data = {name: form[name].value() for name in form.fields}
        data = {name: "" if value is None else value for name, value in data.items()}
        data.update(changes)
        return data

    def test_edit_page_shows_current_title(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Buy mlik"')
        self.assertContains(
            response, f'<a href="{self.todo_list.get_absolute_url()}">Cancel</a>'
        )

    def test_edit_page_shows_every_form_field(self):
        response = self.client.get(self.url)
        for name in response.context["form"].fields:
            with self.subTest(field=name):
                self.assertContains(response, f'name="{name}"')

    def test_get_does_not_change_data(self):
        self.client.get(self.url, {"title": "Hacked"})
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")

    def test_edit_other_methods_are_405(self):
        for method in ["put", "patch", "delete"]:
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url)
                self.assertEqual(response.status_code, 405)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")
        self.assertTrue(Todo.objects.filter(pk=self.todo.pk).exists())

    def test_heading_names_the_todo_and_escapes_it(self):
        self.todo.title = '"><script>x</script>'
        self.todo.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, "<script>x")
        self.assertContains(
            response, "<h1>Edit “&quot;&gt;&lt;script&gt;x&lt;/script&gt;”</h1>"
        )

    def test_bad_edit_says_error_in_title_and_alert(self):
        alert = (
            '<p class="form-error-summary" role="alert" tabindex="-1" autofocus>'
            "Not saved. Fix what is marked below.</p>"
        )
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Edit “Buy mlik” – To-do list</title>")
        self.assertNotContains(response, "Error:")
        self.assertNotContains(response, "form-error-summary")

        response = self.client.post(self.url, self.edit_data(self.todo, title="   "))
        self.assertContains(
            response, "<title>Error: Edit “Buy mlik” – To-do list</title>"
        )
        self.assertContains(response, alert, count=1)

    def test_title_and_heading_use_the_saved_title(self):
        # The title is valid, the tags are not (11 tags): nothing is saved, and
        # the page must not name the to-do by the typed title.
        tags = ", ".join(f"t{n}" for n in range(11))
        response = self.client.post(
            self.url, self.edit_data(self.todo, title="Buy milk", tag_names=tags)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>Edit “Buy mlik”</h1>")
        self.assertContains(
            response, "<title>Error: Edit “Buy mlik” – To-do list</title>"
        )
        self.assertContains(response, 'value="Buy milk"')  # The field keeps it.
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")

    def test_edit_ignores_next(self):
        response = self.client.post(
            self.url + "?next=https://evil.com",
            self.edit_data(self.todo, title="Buy milk", next="https://evil.com"),
        )
        self.assertEqual(response["Location"], self.todo_list.get_absolute_url())

    def test_edit_saves_new_title(self):
        response = self.client.post(
            self.url, self.edit_data(self.todo, title="Buy milk")
        )
        self.assertRedirects(
            response, self.todo_list.get_absolute_url(), fetch_redirect_response=False
        )
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")

    def test_edit_clears_due_date(self):
        self.todo.due_date = date(2026, 10, 12)
        self.todo.save()
        self.client.post(self.url, self.edit_data(self.todo, due_date=""))
        self.todo.refresh_from_db()
        self.assertIsNone(self.todo.due_date)

    def test_invalid_edit_is_not_saved(self):
        response = self.client.post(self.url, self.edit_data(self.todo, title="   "))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")

    def test_edit_does_not_change_done_or_owner(self):
        Todo.objects.filter(pk=self.todo.pk).update(done=True)
        self.client.post(
            self.url,
            self.edit_data(
                self.todo,
                title="New",
                done="",
                owner=self.other_user.pk,
                todo_list=self.other_list.pk,
            ),
        )
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "New")
        self.assertTrue(self.todo.done)
        self.assertEqual(self.todo.todo_list, self.todo_list)

    def test_other_user_gets_404(self):
        self.assertOtherUserGets404(self.url, method="get")
        self.assertOtherUserGets404(
            self.url, data=self.edit_data(self.todo, title="Hacked")
        )
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")

    def test_logged_out_user_is_sent_to_login(self):
        client = Client()
        for response in [
            client.get(self.url),
            client.post(self.url, self.edit_data(self.todo, title="Sneaky")),
        ]:
            self.assertRedirects(
                response,
                f"/accounts/login/?next={self.url}",
                fetch_redirect_response=False,
            )
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")

    def test_list_has_edit_link(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertContains(response, f'href="{self.url}"')

    def test_edit_page_shows_notes_field(self):
        self.todo.description = "Oat milk"
        self.todo.save()
        response = self.client.get(self.url)
        self.assertContains(response, "Notes</label>")
        self.assertContains(response, '<textarea name="description"')
        self.assertContains(response, 'maxlength="2000"')
        self.assertContains(response, ">\nOat milk</textarea>")

    def test_edit_saves_description(self):
        self.client.post(self.url, self.edit_data(self.todo, description="Oat milk"))
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "Oat milk")

    def test_edit_saves_line_breaks_as_one_character(self):
        self.client.post(
            self.url, self.edit_data(self.todo, description="Line one\r\nLine two")
        )
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "Line one\nLine two")

    def test_edit_can_clear_description(self):
        self.todo.description = "Oat milk"
        self.todo.save()
        self.client.post(self.url, self.edit_data(self.todo, description=""))
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "")

    def test_description_only_spaces_is_empty(self):
        self.client.post(self.url, self.edit_data(self.todo, description="  \r\n  "))
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "")

    def test_description_of_2000_characters_is_saved(self):
        self.client.post(self.url, self.edit_data(self.todo, description="a" * 2000))
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "a" * 2000)

    def test_long_description_is_not_saved(self):
        too_long = "b" * 2001
        response = self.client.post(
            self.url, self.edit_data(self.todo, title="Buy milk", description=too_long)
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ensure this value has at most 2000 characters")
        self.assertContains(response, too_long)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy mlik")
        self.assertEqual(self.todo.description, "")

    def test_many_lines_near_the_limit_are_saved(self):
        # The browser counts this as 1999 characters (1000 "a" + 999 line
        # breaks), but it sends 2998, because each line break is "\r\n".
        note = "\r\n".join(["a"] * 1000)
        response = self.client.post(
            self.url, self.edit_data(self.todo, description=note)
        )
        self.assertEqual(response.status_code, 302)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "\n".join(["a"] * 1000))

    def test_other_user_cannot_edit_description(self):
        self.todo.description = "Oat milk"
        self.todo.save()
        self.assertOtherUserGets404(
            self.url, data=self.edit_data(self.todo, description="Hacked")
        )
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.description, "Oat milk")

    def test_edit_without_description_keeps_note(self):
        self.todo.description = "Oat milk"
        self.todo.save()
        response = self.client.post(self.url, {"title": "Buy milk", "due_date": ""})
        self.assertEqual(response.status_code, 302)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")
        self.assertEqual(self.todo.description, "Oat milk")
