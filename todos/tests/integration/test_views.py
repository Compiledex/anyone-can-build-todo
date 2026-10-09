from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import URLResolver, get_resolver, reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.forms import TodoForm
from todos.models import Todo, TodoList

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
        self.assertContains(response, "Due 12 Oct 2026")

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
