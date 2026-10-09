from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import URLResolver, get_resolver, reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.forms import TodoForm
from todos.models import Tag, Todo, TodoList

# What an overdue row shows next to its date.
OVERDUE_LABEL = '<span class="overdue-label">Overdue</span>'


class ListTests(LoggedInTestCase):
    def list_page(self):
        return self.client.get(self.todo_list.get_absolute_url())

    def test_list_page_loads(self):
        response = self.list_page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing to do yet")

    def test_list_is_oldest_first(self):
        now = timezone.now()
        newer = Todo.objects.create(title="Newer", todo_list=self.todo_list)
        older = Todo.objects.create(title="Older", todo_list=self.todo_list)
        Todo.objects.filter(pk=newer.pk).update(created_at=now)
        Todo.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=1))
        response = self.list_page()
        self.assertEqual(list(response.context["todos"]), [older, newer])

    def test_add_input_keeps_its_browser_checks(self):
        response = self.list_page()
        page = response.content.decode()
        start = page.index('<input name="title"')
        tag = page[start : page.index(">", start)].split()
        self.assertIn('maxlength="200"', tag)
        self.assertIn("required", tag)
        self.assertIn("autofocus", tag)
        self.assertIn('placeholder="What', tag)

    def test_stored_title_is_escaped(self):
        Todo.objects.create(title="<b>x</b>", todo_list=self.todo_list)
        response = self.list_page()
        self.assertContains(response, "&lt;b&gt;x&lt;/b&gt;")
        self.assertNotContains(response, "<b>x</b>")

    def test_list_shows_due_date(self):
        Todo.objects.create(
            title="Pay rent", todo_list=self.todo_list, due_date=date(2026, 10, 12)
        )
        response = self.list_page()
        self.assertContains(
            response,
            '<time datetime="2026-10-12">Due 12 Oct 2026</time>',
            html=True,
        )

    def test_list_marks_overdue_todo(self):
        Todo.objects.create(
            title="Pay rent",
            todo_list=self.todo_list,
            due_date=timezone.localdate() - timedelta(days=30),
        )
        response = self.list_page()
        self.assertContains(response, OVERDUE_LABEL, html=True)

    def test_list_does_not_mark_todo_that_is_not_late(self):
        today = timezone.localdate()
        Todo.objects.create(
            title="Pay rent",
            todo_list=self.todo_list,
            due_date=today + timedelta(days=30),
        )
        Todo.objects.create(
            title="Call home",
            todo_list=self.todo_list,
            due_date=today - timedelta(days=30),
            done=True,
        )
        response = self.list_page()
        self.assertNotContains(response, OVERDUE_LABEL, html=True)

    def test_list_shows_description_with_line_breaks(self):
        Todo.objects.create(
            title="Buy milk",
            todo_list=self.todo_list,
            description="Line one\nLine two",
        )
        response = self.list_page()
        self.assertContains(response, '<details class="notes">')
        self.assertContains(response, "Line one<br>Line two")
        self.assertContains(
            response, '<summary aria-label="Notes for Buy milk">Notes</summary>'
        )

    def test_note_of_a_done_todo_is_not_inside_the_title(self):
        # A done title is crossed out, and so is everything inside it.
        Todo.objects.create(
            title="Buy milk",
            todo_list=self.todo_list,
            description="Oat milk",
            done=True,
        )
        html = self.list_page().content.decode()
        self.assertRegex(html, r'<span class="title">Buy milk</span>\s*<details')

    def test_list_escapes_description(self):
        Todo.objects.create(
            title="Buy milk",
            todo_list=self.todo_list,
            description="<script>alert(1)</script>",
        )
        response = self.list_page()
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)")

    def test_details_only_for_todos_with_a_note(self):
        Todo.objects.create(
            title="Buy milk", todo_list=self.todo_list, description="Oat milk"
        )
        Todo.objects.create(title="Call home", todo_list=self.todo_list)
        response = self.list_page()
        self.assertContains(response, "<details", count=1)

    def test_other_user_cannot_see_description(self):
        Todo.objects.create(
            title="Buy milk", todo_list=self.todo_list, description="Secret note"
        )
        self.assertContains(self.list_page(), "Secret note")
        other = self.client_for(self.other_user)
        response = other.get(self.other_list.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secret note")


class AddTests(LoggedInTestCase):
    def add_url(self):
        return reverse("todo_add", args=[self.todo_list.pk])

    def test_add_a_todo(self):
        response = self.client.post(
            self.add_url(), {"title": "Buy milk", "todo_list": self.other_list.pk}
        )
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        todo = Todo.objects.get()
        self.assertEqual(todo.title, "Buy milk")
        self.assertEqual(todo.todo_list, self.todo_list)

    def test_add_with_empty_title_shows_this_list_again(self):
        home = TodoList.objects.create(owner=self.user, name="Home")
        work = TodoList.objects.create(owner=self.user, name="Work")
        Todo.objects.create(title="Water plants", todo_list=home)
        Todo.objects.create(title="Send report", todo_list=work)
        url = reverse("todo_add", args=[work.pk])
        response = self.client.post(url, {"title": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertContains(response, "Send report")
        self.assertNotContains(response, "Water plants")
        self.assertEqual(Todo.objects.count(), 2)

    def test_add_ignores_done(self):
        self.client.post(self.add_url(), {"title": "x", "done": "on"})
        self.assertFalse(Todo.objects.get().done)

    def test_typed_title_is_escaped_on_the_error_page(self):
        title = '"><b>x' + "a" * 200
        response = self.client.post(self.add_url(), {"title": title})
        self.assertContains(response, 'value="&quot;&gt;&lt;b&gt;x')
        self.assertNotContains(response, '"><b>x')

    def test_empty_title_is_not_added(self):
        self.client.post(self.add_url(), {"title": "   "})
        self.assertEqual(Todo.objects.count(), 0)

    def test_empty_title_shows_the_page_again(self):
        Todo.objects.create(title="Call home", todo_list=self.todo_list)
        response = self.client.post(self.add_url(), {"title": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertEqual(Todo.objects.count(), 1)
        self.assertContains(response, "Call home")
        self.assertContains(response, 'id="id_title_error"')
        self.assertContains(response, 'aria-describedby="id_title_error"')
        self.assertContains(response, 'aria-invalid="true"')

    def test_long_title_is_not_added(self):
        title = "a" * 201
        response = self.client.post(self.add_url(), {"title": title})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Todo.objects.count(), 0)
        self.assertContains(
            response, "Ensure this value has at most 200 characters (it has 201)."
        )
        self.assertContains(response, f'value="{title}"')

    def test_add_still_works_without_description(self):
        response = self.client.post(self.add_url(), {"title": "Buy milk"})
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        self.assertEqual(Todo.objects.get().description, "")

    def test_add_a_todo_with_a_due_date(self):
        self.client.post(
            self.add_url(), {"title": "Pay rent", "due_date": "2026-10-12"}
        )
        self.assertEqual(Todo.objects.get().due_date, date(2026, 10, 12))

    def test_add_a_todo_without_a_due_date(self):
        self.client.post(self.add_url(), {"title": "Pay rent", "due_date": ""})
        self.assertIsNone(Todo.objects.get().due_date)

    def test_invalid_due_date_is_not_added(self):
        response = self.client.post(
            self.add_url(), {"title": "Pay rent", "due_date": "2026-02-30"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Todo.objects.count(), 0)
        self.assertContains(response, "Enter a valid date.")
        self.assertContains(response, 'value="Pay rent"')

    def test_other_date_format_is_not_added(self):
        self.client.post(
            self.add_url(), {"title": "Pay rent", "due_date": "10/12/2026"}
        )
        self.assertEqual(Todo.objects.count(), 0)

    def test_typed_due_date_is_kept_after_an_error(self):
        response = self.client.post(
            self.add_url(), {"title": "", "due_date": "2026-10-12"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-10-12"')

    def test_typed_due_date_is_escaped_on_the_error_page(self):
        response = self.client.post(
            self.add_url(), {"title": "Pay rent", "due_date": '"><b>x</b>'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<b>x</b>")

    def test_get_does_not_add(self):
        response = self.client.get(self.add_url(), {"title": "Buy milk"})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Todo.objects.count(), 0)


class ToggleTests(LoggedInTestCase):
    def test_toggle_marks_done_and_back(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        self.client.post(reverse("todo_toggle", args=[todo.pk]))
        todo.refresh_from_db()
        self.assertTrue(todo.done)
        self.client.post(reverse("todo_toggle", args=[todo.pk]))
        todo.refresh_from_db()
        self.assertFalse(todo.done)

    def test_get_does_not_toggle(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        response = self.client.get(reverse("todo_toggle", args=[todo.pk]))
        self.assertEqual(response.status_code, 405)
        todo.refresh_from_db()
        self.assertFalse(todo.done)

    def test_toggle_returns_to_its_list(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        todo = Todo.objects.create(title="Send report", todo_list=work)
        response = self.client.post(reverse("todo_toggle", args=[todo.pk]))
        self.assertRedirects(response, work.get_absolute_url())

    def test_toggle_unknown_todo_is_404(self):
        response = self.client.post(reverse("todo_toggle", args=[999]))
        self.assertEqual(response.status_code, 404)


class DeleteTests(LoggedInTestCase):
    def test_delete_removes_it(self):
        todo = Todo.objects.create(title="Call home", todo_list=self.todo_list)
        self.client.post(reverse("todo_delete", args=[todo.pk]))
        self.assertEqual(Todo.objects.count(), 0)

    def test_get_does_not_delete(self):
        todo = Todo.objects.create(title="Call home", todo_list=self.todo_list)
        response = self.client.get(reverse("todo_delete", args=[todo.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Todo.objects.count(), 1)

    def test_delete_returns_to_its_list(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        todo = Todo.objects.create(title="Send report", todo_list=work)
        response = self.client.post(reverse("todo_delete", args=[todo.pk]))
        self.assertRedirects(response, work.get_absolute_url())

    def test_delete_unknown_todo_is_404(self):
        response = self.client.post(reverse("todo_delete", args=[999]))
        self.assertEqual(response.status_code, 404)


def open_view_names(patterns):
    """The names of every view in these URL patterns that needs no login.

    Goes into included URL files, but not into the admin (it has its own rules).
    """
    names = set()
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            if pattern.namespace != "admin":
                names |= open_view_names(pattern.url_patterns)
        elif getattr(pattern.callback, "login_required", True) is False:
            names.add(pattern.name)
    return names


class LoginRequiredTests(TestCase):
    """Nobody is logged in here."""

    def test_anonymous_list_goes_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(
            response, "/accounts/login/?next=/", fetch_redirect_response=False
        )

    def test_anonymous_cannot_add_toggle_or_delete(self):
        alice = make_user("alice")
        inbox = TodoList.objects.create(owner=alice, name="Inbox")
        todo = Todo.objects.create(title="Buy milk", todo_list=inbox)
        for url in [
            reverse("todo_add", args=[inbox.pk]),
            reverse("todo_toggle", args=[todo.pk]),
            reverse("todo_delete", args=[todo.pk]),
        ]:
            with self.subTest(url=url):
                response = self.client.post(url, {"title": "Sneaky"})
                self.assertRedirects(
                    response,
                    f"/accounts/login/?next={url}",
                    fetch_redirect_response=False,
                )
                todo.refresh_from_db()
                self.assertFalse(todo.done)
                self.assertEqual(Todo.objects.count(), 1)

    def test_only_login_and_signup_are_open(self):
        # A new page that needs no login must be added here on purpose.
        self.assertEqual(
            open_view_names(get_resolver().url_patterns),
            {"login", "logout", "signup"},
        )

    def test_admin_is_not_open(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        for url in ["/admin/", "/admin/todos/todo/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login/", response["Location"])


class OnlyMyDataTests(LoggedInTestCase):
    def make_two_todos(self):
        Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        Todo.objects.create(title="Call home", todo_list=self.other_list)

    def test_list_shows_only_my_todos(self):
        self.make_two_todos()
        response = self.client.get(self.todo_list.get_absolute_url())
        titles = [todo.title for todo in response.context["todos"]]
        self.assertEqual(titles, ["Buy milk"])
        self.assertContains(response, "Buy milk")
        self.assertNotContains(response, "Call home")

    def test_invalid_add_shows_only_my_todos(self):
        self.make_two_todos()
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": ""}
        )
        self.assertEqual(response.status_code, 200)
        titles = [todo.title for todo in response.context["todos"]]
        self.assertEqual(titles, ["Buy milk"])
        self.assertContains(response, "Buy milk")
        self.assertNotContains(response, "Call home")

    def test_other_users_due_date_is_not_shown(self):
        Todo.objects.create(
            title="Call home", todo_list=self.other_list, due_date=date(2026, 10, 12)
        )
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertNotContains(response, "Call home")
        self.assertNotContains(response, "Due 12 Oct 2026")

    def test_add_sets_me_as_owner(self):
        self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": "Buy milk"}
        )
        self.assertEqual(Todo.objects.get().todo_list.owner, self.user)

    def test_other_user_cannot_toggle_my_todo(self):
        todo = Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        self.assertOtherUserGets404(reverse("todo_toggle", args=[todo.pk]))
        todo.refresh_from_db()
        self.assertFalse(todo.done)

    def test_other_user_cannot_delete_my_todo(self):
        todo = Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        self.assertOtherUserGets404(reverse("todo_delete", args=[todo.pk]))
        self.assertTrue(Todo.objects.filter(pk=todo.pk).exists())

    def test_post_without_csrf_token_is_403(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": "Buy milk"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Todo.objects.count(), 0)


class AdminTests(TestCase):
    def test_admin_lists_show_the_list_and_the_owner(self):
        admin = get_user_model().objects.create_user(
            username="staffer",
            password="unused-in-this-test",
            is_staff=True,
            is_superuser=True,
        )
        errands = TodoList.objects.create(owner=make_user("carol"), name="Errands")
        Todo.objects.create(title="Buy milk", todo_list=errands)
        self.client.force_login(admin)
        response = self.client.get("/admin/todos/todo/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Buy milk")
        self.assertContains(response, "Errands")
        response = self.client.get("/admin/todos/todolist/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Errands")
        self.assertContains(response, "carol")


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

    def test_heading_is_fixed_and_title_is_escaped(self):
        self.todo.title = '"><script>x</script>'
        self.todo.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, "<script>x")
        self.assertContains(response, "<h1>Edit to-do</h1>")

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
        self.assertContains(response, "Notes:</label>")
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


class PriorityTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.add_url = reverse("todo_add", args=[self.todo_list.pk])

    def make_todo(self, priority):
        todo = Todo.objects.create(
            title="Pay rent", todo_list=self.todo_list, priority=priority
        )
        return todo, reverse("todo_edit", args=[todo.pk])

    def test_add_a_todo_with_high_priority(self):
        self.client.post(self.add_url, {"title": "Pay rent", "priority": "3"})
        todo = Todo.objects.get(title="Pay rent")
        self.assertEqual(todo.priority, Todo.Priority.HIGH)

    def test_add_without_priority_is_medium(self):
        for data in [{"title": "Only a title"}, {"title": "Empty", "priority": ""}]:
            with self.subTest(data=data):
                self.client.post(self.add_url, data)
                todo = Todo.objects.get(title=data["title"])
                self.assertEqual(todo.priority, Todo.Priority.MEDIUM)

    def test_add_form_selects_medium(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertInHTML('<option value="2" selected>Medium</option>', response.text)

    def test_invalid_priority_is_not_added(self):
        response = self.client.post(
            self.add_url, {"title": "Pay rent", "priority": "7"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Todo.objects.exists())
        self.assertContains(response, "Select a valid choice.")
        self.assertContains(response, 'value="Pay rent"')
        # Screen readers hear that the drop-down is wrong, and which error it has.
        self.assertInHTML(
            '<select name="priority" aria-label="Priority" aria-invalid="true"'
            ' aria-describedby="id_priority_error" id="id_priority">'
            '<option value="1">Low</option><option value="2">Medium</option>'
            '<option value="3">High</option></select>',
            response.text,
        )
        self.assertContains(response, 'id="id_priority_error"')

    def test_invalid_priority_on_edit_changes_nothing(self):
        todo, url = self.make_todo(Todo.Priority.LOW)
        response = self.client.post(url, {"title": "New", "priority": "7"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice.")
        todo.refresh_from_db()
        self.assertEqual(todo.title, "Pay rent")
        self.assertEqual(todo.priority, Todo.Priority.LOW)

    def test_list_shows_priority_label(self):
        self.make_todo(Todo.Priority.HIGH)
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertInHTML(
            '<span class="priority priority-3">'
            '<span class="visually-hidden">Priority: </span>High</span>',
            response.text,
        )

    def test_edit_shows_current_priority(self):
        _, url = self.make_todo(Todo.Priority.LOW)
        response = self.client.get(url)
        self.assertInHTML('<option value="1" selected>Low</option>', response.text)

    def test_edit_changes_priority(self):
        todo, url = self.make_todo(Todo.Priority.MEDIUM)
        self.client.post(url, {"title": "Pay rent", "priority": "3"})
        todo.refresh_from_db()
        self.assertEqual(todo.priority, Todo.Priority.HIGH)

    def test_edit_without_priority_keeps_it(self):
        todo, url = self.make_todo(Todo.Priority.HIGH)
        self.client.post(url, {"title": "Pay the rent"})
        todo.refresh_from_db()
        self.assertEqual(todo.title, "Pay the rent")
        self.assertEqual(todo.priority, Todo.Priority.HIGH)

    def test_other_user_cannot_change_priority(self):
        todo, url = self.make_todo(Todo.Priority.LOW)
        self.assertOtherUserGets404(url, data={"title": "Pay rent", "priority": "3"})
        todo.refresh_from_db()
        self.assertEqual(todo.priority, Todo.Priority.LOW)


class TagTests(LoggedInTestCase):
    """Tags on a to-do. alice is A, bob is B; each has their own list."""

    def setUp(self):
        super().setUp()
        self.todo = Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        self.other_todo = Todo.objects.create(
            title="Bob's thing", todo_list=self.other_list
        )

    def edit(self, todo, tag_names, title=None, client=None):
        """Post the edit form for this to-do. The edit form always needs the title."""
        return (client or self.client).post(
            reverse("todo_edit", args=[todo.pk]),
            {"title": title or todo.title, "tag_names": tag_names},
        )

    def tag_names(self, todo):
        return [tag.name for tag in todo.tags.all()]

    def list_page(self):
        return self.client.get(reverse("list_detail", args=[self.todo_list.pk]))

    def test_edit_sets_tags(self):
        self.edit(self.todo, "Work, #home")
        self.assertEqual(self.tag_names(self.todo), ["home", "work"])
        for tag in self.todo.tags.all():
            self.assertEqual(tag.owner, self.user)

    def test_edit_page_shows_current_tags(self):
        self.edit(self.todo, "work, home")
        response = self.client.get(reverse("todo_edit", args=[self.todo.pk]))
        self.assertEqual(response.context["form"]["tag_names"].value(), "home, work")
        self.assertContains(response, 'value="home, work"')

    def test_edit_with_empty_tags_removes_them(self):
        self.edit(self.todo, "work, home")
        self.edit(self.todo, "")
        self.assertEqual(self.tag_names(self.todo), [])

    def test_same_tag_name_is_reused(self):
        second = Todo.objects.create(title="Call home", todo_list=self.todo_list)
        self.edit(self.todo, "work")
        self.edit(second, "Work")
        self.assertEqual(Tag.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(self.todo.tags.get(), second.tags.get())

    def test_bad_tags_show_error_and_change_nothing(self):
        self.edit(self.todo, "work")
        too_many = ", ".join(f"t{n}" for n in range(11))
        response = self.edit(self.todo, too_many, title="A new title")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A to-do can have at most 10 tags.")
        self.assertContains(response, f'value="{too_many}"')
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")
        self.assertEqual(self.tag_names(self.todo), ["work"])

    def test_list_shows_tags_sorted(self):
        self.edit(self.todo, "work, home")
        page = self.list_page().content.decode()
        self.assertIn('<span class="tag">#home</span>', page)
        self.assertLess(page.index("#home"), page.index("#work"))

    def test_list_query_count_does_not_grow_with_tags(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.list_page().status_code, 200)
            return len(queries)

        self.edit(self.todo, "work, home")
        with_one = count_queries()
        for n in range(4):
            todo = Todo.objects.create(title=f"Todo {n}", todo_list=self.todo_list)
            self.edit(todo, f"work, tag{n}")
        self.assertEqual(count_queries(), with_one)

    def test_same_name_for_two_users_is_two_tags(self):
        self.edit(self.todo, "work")
        self.edit(self.other_todo, "work", client=self.client_for(self.other_user))
        self.assertEqual(Tag.objects.filter(name="work").count(), 2)
        self.assertEqual(self.todo.tags.get().owner, self.user)
        self.assertEqual(self.other_todo.tags.get().owner, self.other_user)

    def test_other_users_tags_are_not_shown(self):
        self.edit(self.todo, "secret")
        bob = self.client_for(self.other_user)
        list_page = bob.get(reverse("list_detail", args=[self.other_list.pk]))
        edit_page = bob.get(reverse("todo_edit", args=[self.other_todo.pk]))
        self.assertNotContains(list_page, "secret")
        self.assertNotContains(edit_page, "secret")

    def test_cannot_tag_other_users_todo(self):
        self.edit(self.todo, "work")
        response = self.edit(
            self.todo,
            "hacked",
            title="Hacked",
            client=self.client_for(self.other_user),
        )
        self.assertEqual(response.status_code, 404)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")
        self.assertEqual(self.tag_names(self.todo), ["work"])
        self.assertFalse(Tag.objects.filter(owner=self.other_user).exists())

    def test_add_still_works(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": "Call home"}
        )
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        todo = Todo.objects.get(title="Call home")
        self.assertEqual(self.tag_names(todo), [])
