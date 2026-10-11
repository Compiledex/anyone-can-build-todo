import html
import re
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import URLResolver, get_resolver, reverse
from django.utils import dateformat, timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.forms import TodoForm
from todos.models import Subtask, Tag, Todo, TodoList
from todos.tests.helpers import count_queries, messages_of, shown_titles

# What an overdue row shows next to its date.
OVERDUE_LABEL = '<span class="overdue-label">Overdue</span>'


def hidden_next(response, action):
    """The hidden `next` of the form that posts to `action`, as the browser reads it."""
    pattern = re.compile(
        rf'<form method="post" action="{re.escape(action)}">.*?'
        r'name="next" value="([^"]*)"',
        re.S,
    )
    match = pattern.search(response.content.decode())
    if match is None:
        raise AssertionError(f"No form with a hidden next posts to {action}")
    return html.unescape(match.group(1))


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

    def test_add_input_has_no_autofocus_when_steps_are_open(self):
        # After "Add step" the step field gets the cursor; two autofocus fields
        # would give it to "New to-do", the first one.
        todo = Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        response = self.client.get(self.todo_list.get_absolute_url(), {"open": todo.pk})
        page = response.content.decode()
        start = page.index('<input name="title" aria-label="New to-do"')
        tag = page[start : page.index(">", start)].split()
        self.assertIn("required", tag)
        self.assertNotIn("autofocus", tag)

    def test_row_buttons_name_their_todo(self):
        Todo.objects.create(title='<b>"x', todo_list=self.todo_list)
        Todo.objects.create(title="<i>y", todo_list=self.todo_list, done=True)
        page = self.list_page().content.decode()
        for name, text in [
            ("Done: &lt;b&gt;&quot;x", "Done"),
            ("Delete: &lt;b&gt;&quot;x", "Delete"),
            ("Undo: &lt;i&gt;y", "Undo"),
            ("Delete: &lt;i&gt;y", "Delete"),
        ]:
            with self.subTest(name=name):
                # The visible word stays first and is still the button's text.
                self.assertRegex(
                    page, rf'aria-label="{re.escape(name)}">{text}</button>'
                )
        self.assertNotIn('<b>"x', page)

    def test_done_todo_says_done_to_screen_readers(self):
        Todo.objects.create(title="Buy milk", todo_list=self.todo_list, done=True)
        Todo.objects.create(title="Call home", todo_list=self.todo_list)
        page = self.list_page().content.decode()
        self.assertIn(
            '<span class="visually-hidden">Done: </span><span class="title">'
            "Buy milk</span>",
            page,
        )
        self.assertIn('<span class="title">Call home</span>', page)
        self.assertNotIn(
            '<span class="visually-hidden">Done: </span><span class="title">Call home',
            page,
        )

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
        # The title closes right after its text; the notes come later in the row.
        self.assertRegex(
            html, r'(?s)<span class="title">Buy milk</span>.*<details class="notes">'
        )

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
        self.assertContains(response, '<details class="notes"', count=1)

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
        self.client.post(reverse("todo_toggle", args=[todo.pk]), {"done": "1"})
        todo.refresh_from_db()
        self.assertTrue(todo.done)
        self.client.post(reverse("todo_toggle", args=[todo.pk]), {"done": "0"})
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
        response = self.client.post(
            reverse("todo_toggle", args=[todo.pk]), {"done": "1"}
        )
        self.assertRedirects(response, work.get_absolute_url())

    def test_toggle_unknown_todo_is_404(self):
        response = self.client.post(reverse("todo_toggle", args=[999]))
        self.assertEqual(response.status_code, 404)

    def toggle(self, todo, done, client=None):
        return (client or self.client).post(
            reverse("todo_toggle", args=[todo.pk]), {"done": "1" if done else "0"}
        )

    def make_three(self):
        return [
            Todo.objects.create(title=title, todo_list=self.todo_list)
            for title in ["First", "Second", "Third"]
        ]

    def test_done_twice_stays_done(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        self.toggle(todo, True)
        self.toggle(todo, True)
        todo.refresh_from_db()
        self.assertTrue(todo.done)

    def test_undo_twice_stays_not_done(self):
        todo = Todo.objects.create(
            title="Read chapter 3", todo_list=self.todo_list, done=True
        )
        self.toggle(todo, False)
        self.toggle(todo, False)
        todo.refresh_from_db()
        self.assertFalse(todo.done)

    def test_done_and_undo_still_work(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        self.toggle(todo, True)
        todo.refresh_from_db()
        self.assertTrue(todo.done)
        self.toggle(todo, False)
        todo.refresh_from_db()
        self.assertFalse(todo.done)

    def test_bad_done_value_is_400(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        url = reverse("todo_toggle", args=[todo.pk])
        for data in [{}, {"done": ""}, {"done": "yes"}, {"done": "2"}]:
            with self.subTest(data=data):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 400)
                todo.refresh_from_db()
                self.assertFalse(todo.done)

    def test_bad_done_value_from_stranger_is_404(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        self.assertOtherUserGets404(
            reverse("todo_toggle", args=[todo.pk]), data={"done": "x"}
        )
        todo.refresh_from_db()
        self.assertFalse(todo.done)

    def test_page_sends_the_state_it_wants(self):
        open_todo = Todo.objects.create(title="Open", todo_list=self.todo_list)
        done_todo = Todo.objects.create(
            title="Finished", todo_list=self.todo_list, done=True
        )
        response = self.client.get(self.todo_list.get_absolute_url())
        page = response.content.decode()
        for todo, value in [(open_todo, "1"), (done_todo, "0")]:
            with self.subTest(todo=todo.title):
                action = reverse("todo_toggle", args=[todo.pk])
                form = re.search(
                    rf'<form method="post" action="{action}">.*?</form>', page, re.S
                ).group(0)
                self.assertInHTML(
                    f'<input type="hidden" name="done" value="{value}">', form
                )

    def test_done_goes_back_to_its_row(self):
        first, second, _ = self.make_three()
        url = self.todo_list.get_absolute_url()
        response = self.client.get(url)
        next_url = hidden_next(response, reverse("todo_toggle", args=[second.pk]))
        self.assertEqual(next_url, f"{url}#todo-{second.pk}")
        response = self.client.post(
            reverse("todo_toggle", args=[second.pk]), {"done": "1", "next": next_url}
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_done_in_not_done_filter_goes_to_the_next_row(self):
        _, second, third = self.make_three()
        url = self.todo_list.get_absolute_url()
        action = reverse("todo_toggle", args=[second.pk])
        response = self.client.get(f"{url}?status=open")
        self.assertTrue(hidden_next(response, action).endswith(f"#todo-{third.pk}"))
        # A bad status shows every row, so it is no filter: the row stays.
        response = self.client.get(f"{url}?status=bogus")
        self.assertTrue(hidden_next(response, action).endswith(f"#todo-{second.pk}"))

    def test_next_with_a_fragment_keeps_the_same_site_rule(self):
        todo = Todo.objects.create(title="Read chapter 3", todo_list=self.todo_list)
        url = self.todo_list.get_absolute_url()
        action = reverse("todo_toggle", args=[todo.pk])
        for value in ["//evil.example/#todo-1", "/\\evil.example#todo-1", "#todo-1"]:
            with self.subTest(next=value):
                response = self.client.post(action, {"done": "1", "next": value})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], url)
        good = f"{url}?q=a#todo-{todo.pk}"
        response = self.client.post(action, {"done": "1", "next": good})
        self.assertRedirects(response, good, fetch_redirect_response=False)


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

    def test_delete_goes_to_the_next_row(self):
        first, second, third = [
            Todo.objects.create(title=title, todo_list=self.todo_list)
            for title in ["First", "Second", "Third"]
        ]
        url = self.todo_list.get_absolute_url()

        def delete(todo):
            action = reverse("todo_delete", args=[todo.pk])
            next_url = hidden_next(self.client.get(url), action)
            response = self.client.post(action, {"next": next_url})
            self.assertRedirects(response, next_url, fetch_redirect_response=False)
            return next_url

        self.assertEqual(delete(first), f"{url}#todo-{second.pk}")
        self.assertEqual(delete(third), f"{url}#todo-{second.pk}")
        self.assertEqual(delete(second), f"{url}#todos")
        # The anchor after the only row names an element that exists.
        self.assertContains(self.client.get(url), 'id="todos"', count=1)


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
        def load():
            self.assertEqual(self.list_page().status_code, 200)

        self.edit(self.todo, "work, home")
        with_one = count_queries(load)
        for n in range(4):
            todo = Todo.objects.create(title=f"Todo {n}", todo_list=self.todo_list)
            self.edit(todo, f"work, tag{n}")
        self.assertEqual(count_queries(load), with_one)

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

    def test_tag_names_are_escaped(self):
        self.edit(self.todo, "<b>x</b>")
        response = self.list_page()
        self.assertContains(response, "#&lt;b&gt;x&lt;/b&gt;")
        self.assertNotContains(response, "<b>x</b>")

    def test_tag_error_rolls_back_title(self):
        # If saving the tags fails, the new title must not be saved either.
        with mock.patch.object(Todo, "set_tags", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.edit(self.todo, "work", title="A new title")
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")

    def test_unused_tag_is_kept(self):
        self.edit(self.todo, "work")
        self.edit(self.todo, "")
        self.assertTrue(Tag.objects.filter(owner=self.user, name="work").exists())

    def test_add_still_works(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": "Call home"}
        )
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        todo = Todo.objects.get(title="Call home")
        self.assertEqual(self.tag_names(todo), [])


class TagsByName(HTMLParser):
    """The attributes of each <input>, <select> and <ul> on a page, by name or id."""

    def __init__(self, html):
        super().__init__()
        self.by_name = {}
        self.by_id = {}
        self.texts = {}
        self._open_id = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("input", "select") and "name" in attrs:
            self.by_name.setdefault(attrs["name"], attrs)
        if "id" in attrs:
            self.by_id[attrs["id"]] = attrs
            if tag == "ul":
                self._open_id = attrs["id"]
                self.texts[self._open_id] = ""

    def handle_endtag(self, tag):
        if tag == "ul":
            self._open_id = None

    def handle_data(self, data):
        if self._open_id:
            self.texts[self._open_id] += data


class RecurringTests(LoggedInTestCase):
    """Repeating to-dos. The view uses the real today, so every due date here is
    counted from timezone.localdate(), and is in the future."""

    def setUp(self):
        super().setUp()
        self.due = timezone.localdate() + timedelta(days=30)
        self.weekly = Todo.objects.create(
            title="Water the plants",
            todo_list=self.todo_list,
            repeat="weekly",
            due_date=self.due,
        )

    def toggle(self, todo, done, client=None):
        return (client or self.client).post(
            reverse("todo_toggle", args=[todo.pk]), {"done": "1" if done else "0"}
        )

    def copies_of(self, todo):
        return Todo.objects.filter(repeated_from=todo)

    def test_add_a_repeating_todo(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]),
            {"title": "Pay rent", "repeat": "monthly", "due_date": "2026-11-01"},
        )
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        todo = Todo.objects.get(title="Pay rent")
        self.assertEqual(todo.repeat, Todo.Repeat.MONTHLY)
        self.assertEqual(todo.due_date, date(2026, 11, 1))

    def test_add_form_has_repeat_select_with_never_first(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertContains(response, 'aria-label="Repeat"')
        self.assertContains(response, '<option value="" selected>Never</option>')
        self.assertNotContains(response, "---------")

    def test_add_repeat_with_bad_date_shows_only_the_date_error(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]),
            {"title": "Pay rent", "repeat": "weekly", "due_date": "2026-13-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date.")
        self.assertNotContains(response, "A repeating to-do needs a due date.")
        self.assertFalse(Todo.objects.filter(title="Pay rent").exists())

    def test_add_repeat_without_due_date_shows_error(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]),
            {"title": "Pay rent", "repeat": "monthly"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A repeating to-do needs a due date.")
        self.assertFalse(Todo.objects.filter(title="Pay rent").exists())

    def assertErrorOnDueDate(self, response):
        """The repeat error is under Due date, the field to fix; Repeat is not marked."""
        self.assertEqual(response.status_code, 200)
        page = TagsByName(response.content.decode())
        due_date = page.by_name["due_date"]
        self.assertEqual(due_date.get("aria-invalid"), "true")
        self.assertIn("id_due_date_error", due_date.get("aria-describedby", "").split())
        self.assertIn(
            "A repeating to-do needs a due date.", page.texts["id_due_date_error"]
        )
        self.assertNotIn("aria-invalid", page.by_name["repeat"])
        self.assertNotIn("id_repeat_error", page.by_id)

    def test_add_repeat_without_due_date_marks_the_date(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]),
            {"title": "Pay rent", "repeat": "monthly"},
        )
        self.assertErrorOnDueDate(response)
        self.assertFalse(Todo.objects.filter(title="Pay rent").exists())

    def test_edit_repeat_without_due_date_marks_the_date(self):
        response = self.client.post(
            reverse("todo_edit", args=[self.weekly.pk]),
            {"title": "Water the plants", "repeat": "weekly", "due_date": ""},
        )
        self.assertErrorOnDueDate(response)
        self.weekly.refresh_from_db()
        self.assertEqual(self.weekly.due_date, self.due)

    def test_edit_cannot_remove_due_date_of_repeating_todo(self):
        response = self.client.post(
            reverse("todo_edit", args=[self.weekly.pk]),
            {"title": "Water the plants", "repeat": "weekly", "due_date": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A repeating to-do needs a due date.")
        self.weekly.refresh_from_db()
        self.assertEqual(self.weekly.due_date, self.due)

    def test_edit_can_stop_repeating(self):
        self.client.post(
            reverse("todo_edit", args=[self.weekly.pk]),
            {"title": "Water the plants", "repeat": "", "due_date": ""},
        )
        self.weekly.refresh_from_db()
        self.assertEqual(self.weekly.repeat, Todo.Repeat.NEVER)
        self.assertIsNone(self.weekly.due_date)

    def test_done_makes_a_copy_with_next_date(self):
        response = self.toggle(self.weekly, True)
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        self.weekly.refresh_from_db()
        self.assertTrue(self.weekly.done)
        copy = self.copies_of(self.weekly).get()
        self.assertEqual(copy.due_date, self.due + timedelta(days=7))
        self.assertFalse(copy.done)
        self.assertEqual(copy.repeated_from, self.weekly)

    def test_copy_keeps_fields(self):
        self.weekly.description = "The ones by the window."
        self.weekly.priority = Todo.Priority.HIGH
        self.weekly.save()
        self.weekly.set_tags(["home", "plants"])
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.assertEqual(copy.title, "Water the plants")
        self.assertEqual(copy.description, "The ones by the window.")
        self.assertEqual(copy.priority, Todo.Priority.HIGH)
        self.assertEqual(copy.todo_list, self.todo_list)
        self.assertEqual(copy.repeat, Todo.Repeat.WEEKLY)
        self.assertEqual(list(copy.tags.all()), list(self.weekly.tags.all()))
        self.assertEqual([t.name for t in self.weekly.tags.all()], ["home", "plants"])
        self.assertEqual(Tag.objects.count(), 2)  # The same tags, no new ones.

    def test_copy_uses_today_in_tokyo(self):
        # 16:00 on 9 Oct in UTC is already 01:00 on 10 Oct in Tokyo. A copy
        # counted from the UTC date would be due 10 Oct (after 9 Oct).
        todo = Todo.objects.create(
            title="Stretch",
            todo_list=self.todo_list,
            repeat="daily",
            due_date=date(2026, 10, 9),
        )
        moment = datetime(2026, 10, 9, 16, 0, tzinfo=UTC)
        with mock.patch("django.utils.timezone.now", return_value=moment):
            self.toggle(todo, True)
        self.assertEqual(self.copies_of(todo).get().due_date, date(2026, 10, 11))

    def test_copy_stays_in_the_same_list_of_several(self):
        middle = TodoList.objects.create(owner=self.user, name="Middle")
        TodoList.objects.create(owner=self.user, name="Last")
        todo = Todo.objects.create(
            title="Stand-up", todo_list=middle, repeat="daily", due_date=self.due
        )
        self.toggle(todo, True)
        self.assertEqual(self.copies_of(todo).get().todo_list, middle)

    def test_copy_has_the_steps_not_done(self):
        for title, done in [("Pack", True), ("Load", False), ("Drive", True)]:
            Subtask.objects.create(todo=self.weekly, title=title, done=done)
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.assertEqual(
            [(step.title, step.done) for step in copy.subtasks.all()],
            [("Pack", False), ("Load", False), ("Drive", False)],
        )
        # The original keeps its own steps, as they were.
        self.assertEqual(
            [(step.title, step.done) for step in self.weekly.subtasks.all()],
            [("Pack", True), ("Load", False), ("Drive", True)],
        )

    def test_list_query_count_does_not_grow_with_repeating_todos(self):
        def load():
            self.assertEqual(
                self.client.get(self.todo_list.get_absolute_url()).status_code, 200
            )

        self.toggle(self.weekly, True)  # The original and its copy.
        before = count_queries(load)
        for n in range(3):
            todo = Todo.objects.create(
                title=f"Todo {n}",
                todo_list=self.todo_list,
                repeat="daily",
                due_date=self.due,
            )
            self.toggle(todo, True)
        self.assertEqual(count_queries(load), before)

    def test_copy_stays_in_owners_list_when_member_clicks_done(self):
        carol = make_user("carol")
        self.todo_list.members.add(carol)
        response = self.toggle(self.weekly, True, client=self.client_for(carol))
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        copy = self.copies_of(self.weekly).get()
        self.assertEqual(copy.todo_list, self.todo_list)
        self.assertEqual(copy.todo_list.owner, self.user)

    def test_done_on_todo_that_does_not_repeat_makes_no_copy(self):
        todo = Todo.objects.create(
            title="Once", todo_list=self.todo_list, due_date=self.due
        )
        self.toggle(todo, True)
        self.assertEqual(Todo.objects.filter(title="Once").count(), 1)

    def test_done_without_due_date_makes_no_copy(self):
        # Made directly, so clean() does not run.
        todo = Todo.objects.create(
            title="Broken", todo_list=self.todo_list, repeat="daily"
        )
        response = self.toggle(todo, True)
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        todo.refresh_from_db()
        self.assertTrue(todo.done)
        self.assertEqual(Todo.objects.filter(title="Broken").count(), 1)

    def test_done_on_last_possible_date_makes_no_copy(self):
        todo = Todo.objects.create(
            title="The end",
            todo_list=self.todo_list,
            repeat="daily",
            due_date=date(9999, 12, 31),
        )
        response = self.toggle(todo, True)
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        self.assertEqual(Todo.objects.filter(title="The end").count(), 1)

    def test_undo_removes_copy_that_is_not_done(self):
        self.toggle(self.weekly, True)
        response = self.toggle(self.weekly, False)
        self.assertEqual(Todo.objects.filter(title="Water the plants").count(), 1)
        self.weekly.refresh_from_db()
        self.assertFalse(self.weekly.done)
        next_due = self.due + timedelta(days=7)
        self.assertEqual(
            messages_of(response),
            [
                f"The next copy, due {dateformat.format(next_due, 'j M Y')}, was removed."
            ],
        )

    def test_done_undo_done_makes_one_new_copy(self):
        self.toggle(self.weekly, True)
        self.assertEqual(Todo.objects.count(), 2)
        self.toggle(self.weekly, False)
        self.assertEqual(Todo.objects.count(), 1)
        self.toggle(self.weekly, True)
        self.assertEqual(Todo.objects.count(), 2)
        self.assertEqual(self.copies_of(self.weekly).count(), 1)

    def test_undo_keeps_copy_that_is_done(self):
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.toggle(copy, True)  # The copy is done, and makes its own copy.
        count = Todo.objects.count()
        response = self.toggle(self.weekly, False)  # Undo on the original.
        self.assertEqual(messages_of(response), [])
        copy.refresh_from_db()
        self.assertTrue(copy.done)
        self.weekly.refresh_from_db()
        self.assertFalse(self.weekly.done)
        self.assertEqual(Todo.objects.count(), count)
        self.toggle(self.weekly, True)  # Done again: no second copy.
        self.assertEqual(Todo.objects.count(), count)
        self.assertEqual(self.copies_of(self.weekly).count(), 1)

    def test_undo_keeps_copy_in_another_list(self):
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        work = TodoList.objects.create(owner=self.user, name="Work")
        copy.todo_list = work
        copy.save()
        self.toggle(self.weekly, False)
        copy.refresh_from_db()
        self.assertEqual(copy.todo_list, work)

    def add_two_steps(self):
        Subtask.objects.create(todo=self.weekly, title="Fill the can")
        Subtask.objects.create(todo=self.weekly, title="Check the soil")

    def kept_message(self):
        next_due = self.due + timedelta(days=7)
        return (
            f"The next copy, due {dateformat.format(next_due, 'j M Y')}, was kept, "
            "because a step in it is already done."
        )

    def test_undo_removes_copy_and_its_steps(self):
        self.add_two_steps()
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.assertEqual(copy.subtasks.count(), 2)
        self.assertFalse(copy.subtasks.filter(done=True).exists())
        copy_pk = copy.pk
        response = self.toggle(self.weekly, False)  # Undo
        self.assertFalse(Todo.objects.filter(pk=copy_pk).exists())
        self.assertFalse(Subtask.objects.filter(todo_id=copy_pk).exists())
        self.assertEqual(self.weekly.subtasks.count(), 2)
        next_due = self.due + timedelta(days=7)
        self.assertEqual(
            messages_of(response),
            [
                f"The next copy, due {dateformat.format(next_due, 'j M Y')}, was removed."
            ],
        )

    def test_undo_keeps_copy_with_a_done_step(self):
        self.add_two_steps()
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        first = copy.subtasks.get(title="Fill the can")
        self.client.post(reverse("subtask_toggle", args=[first.pk]), {"done": "1"})
        response = self.toggle(self.weekly, False)  # Undo
        self.weekly.refresh_from_db()
        self.assertFalse(self.weekly.done)
        self.assertTrue(Todo.objects.filter(pk=copy.pk).exists())
        self.assertEqual(copy.subtasks.count(), 2)
        first.refresh_from_db()
        self.assertTrue(first.done)
        self.assertEqual(messages_of(response), [self.kept_message()])

    def test_done_after_kept_copy_makes_no_second_copy(self):
        self.add_two_steps()
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        copy_pk = copy.pk
        first = copy.subtasks.get(title="Fill the can")
        self.client.post(reverse("subtask_toggle", args=[first.pk]), {"done": "1"})
        self.toggle(self.weekly, False)  # Undo: the copy is kept.
        self.toggle(self.weekly, True)  # Done again.
        copies = list(self.copies_of(self.weekly))
        self.assertEqual([c.pk for c in copies], [copy_pk])
        first.refresh_from_db()
        self.assertTrue(first.done)

    def test_deleted_copy_is_made_again(self):
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.client.post(reverse("todo_delete", args=[copy.pk]))
        self.assertFalse(self.copies_of(self.weekly).exists())
        self.toggle(self.weekly, False)  # Undo
        self.toggle(self.weekly, True)  # Done
        self.assertEqual(self.copies_of(self.weekly).count(), 1)

    def test_deleting_original_keeps_copy(self):
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.client.post(reverse("todo_delete", args=[self.weekly.pk]))
        copy.refresh_from_db()
        self.assertIsNone(copy.repeated_from)

    def test_clearing_completed_keeps_copy(self):
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        self.client.post(reverse("list_clear_completed", args=[self.todo_list.pk]))
        self.assertFalse(Todo.objects.filter(pk=self.weekly.pk).exists())
        copy.refresh_from_db()
        self.assertIsNone(copy.repeated_from)

    def test_double_done_keeps_one_copy(self):
        self.toggle(self.weekly, True)
        self.toggle(self.weekly, True)
        self.weekly.refresh_from_db()
        self.assertTrue(self.weekly.done)
        self.assertEqual(self.copies_of(self.weekly).count(), 1)

    def test_done_on_a_done_todo_makes_no_copy(self):
        self.toggle(self.weekly, True)
        self.copies_of(self.weekly).delete()
        self.toggle(self.weekly, True)  # Already done: nothing happens.
        self.assertFalse(self.copies_of(self.weekly).exists())

    def test_double_undo_removes_the_copy_once(self):
        self.toggle(self.weekly, True)
        first = self.toggle(self.weekly, False)
        # The browser follows the redirect: the list page shows the message.
        self.client.get(self.todo_list.get_absolute_url())
        second = self.toggle(self.weekly, False)
        self.weekly.refresh_from_db()
        self.assertFalse(self.weekly.done)
        self.assertFalse(self.copies_of(self.weekly).exists())
        self.assertEqual(Todo.objects.count(), 1)
        removed = [m for m in messages_of(first) if m.endswith("was removed.")]
        self.assertEqual(len(removed), 1)
        self.assertEqual(messages_of(second), [])

    def test_undo_of_an_open_todo_keeps_a_kept_copy(self):
        self.add_two_steps()
        self.toggle(self.weekly, True)
        copy = self.copies_of(self.weekly).get()
        first = copy.subtasks.get(title="Fill the can")
        self.client.post(reverse("subtask_toggle", args=[first.pk]), {"done": "1"})
        response = self.toggle(self.weekly, False)  # Undo: the copy is kept.
        self.assertEqual(messages_of(response), [self.kept_message()])
        self.client.get(self.todo_list.get_absolute_url())  # Shows the message.
        response = self.toggle(self.weekly, False)  # Undo again: nothing happens.
        self.assertEqual(messages_of(response), [])
        self.assertTrue(Todo.objects.filter(pk=copy.pk).exists())
        first.refresh_from_db()
        self.assertTrue(first.done)

    def test_other_user_cannot_toggle_repeating_todo(self):
        self.assertOtherUserGets404(reverse("todo_toggle", args=[self.weekly.pk]))
        self.weekly.refresh_from_db()
        self.assertFalse(self.weekly.done)
        self.assertEqual(Todo.objects.count(), 1)

    def test_list_shows_repeat_text(self):
        Todo.objects.create(
            title="Bins out",
            todo_list=self.todo_list,
            repeat="weekly",
            due_date=date(2026, 10, 12),  # A Monday.
        )
        self.weekly.repeat = "daily"
        self.weekly.save()
        Todo.objects.create(
            title="Rent",
            todo_list=self.todo_list,
            repeat="monthly",
            due_date=date(2026, 10, 12),
        )
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertContains(response, "Repeats every Monday")
        self.assertContains(response, "Repeats daily")
        self.assertContains(response, "Repeats monthly")
