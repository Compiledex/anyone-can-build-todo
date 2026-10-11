"""Who may see what: login required, only my data, and the admin.

In a LoggedInTestCase alice is logged in; in a plain TestCase nobody is.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import URLResolver, get_resolver, reverse

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.models import Todo, TodoList
from todos.tests.helpers import shown_titles


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

    def test_anonymous_page_goes_to_login(self):
        # `/` is the landing page now (test_landing.py); every other page needs a login.
        url = reverse("list_create")
        response = self.client.get(url)
        self.assertRedirects(
            response, f"/accounts/login/?next={url}", fetch_redirect_response=False
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

    def test_only_landing_login_and_signup_are_open(self):
        # A new page that needs no login must be added here on purpose.
        # "todo_list" is `/`: the landing page for a visitor (no user data).
        self.assertEqual(
            open_view_names(get_resolver().url_patterns),
            {"login", "logout", "signup", "todo_list"},
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
        self.assertEqual(shown_titles(response), ["Buy milk"])
        self.assertContains(response, "Buy milk")
        self.assertNotContains(response, "Call home")

    def test_invalid_add_shows_only_my_todos(self):
        self.make_two_todos()
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(shown_titles(response), ["Buy milk"])
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

    def test_admin_duplicate_is_a_form_error(self):
        admin = get_user_model().objects.create_user(
            username="staffer",
            password="unused-in-this-test",
            is_staff=True,
            is_superuser=True,
        )
        alice = make_user("alice")
        TodoList.objects.create(owner=alice, name="Ærend")
        self.client.force_login(admin)
        add_url = "/admin/todos/todolist/add/"
        response = self.client.post(add_url, {"owner": alice.pk, "name": "ærend"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors)
        self.assertEqual(alice.todo_lists.count(), 1)
        # The key is casefold with NFC, not lower(): "Straße" clashes with
        # "STRASSE", and "A" plus a ring with "Åker".
        TodoList.objects.create(owner=alice, name="STRASSE")
        TodoList.objects.create(owner=alice, name="\u00c5ker")
        for typed in ["Straße", "A\u030aker"]:
            with self.subTest(typed=typed):
                response = self.client.post(add_url, {"owner": alice.pk, "name": typed})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors)
                self.assertEqual(alice.todo_lists.count(), 3)
        response = self.client.post(add_url, {"owner": alice.pk, "name": "Hjem"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(alice.todo_lists.filter(name="Hjem").exists())
