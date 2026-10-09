from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import URLResolver, get_resolver, reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.models import Todo, TodoList


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
