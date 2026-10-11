"""Tests for the list page and for adding, marking done and deleting a to-do.

Edit, priority, tags, repeating to-dos and access rules have their own files.
"""

import re
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo, TodoList
from todos.tests.helpers import add_todo, button_form

# What an overdue row shows next to its date.
OVERDUE_LABEL = '<span class="overdue-label">Overdue</span>'


def button_next(response, action):
    """The `next` the button that posts to `action` sends, as the browser reads it."""
    button, _ = button_form(response, action)
    if button.get("name") != "next":
        raise AssertionError(f"The button that posts to {action} sends no next")
    return button["value"]


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

    def test_todos_with_the_same_time_come_back_by_pk(self):
        # Meta.ordering ends with pk, so to-dos made at the same moment keep
        # a fixed order (the admin and the_list.todos.all() use it).
        todos = [add_todo(self.todo_list, title) for title in ["C", "B", "A"]]
        self.todo_list.todos.update(created_at=timezone.now())
        # SQLite often gives rowid order anyway, so check the SQL asks for it.
        self.assertTrue(
            str(self.todo_list.todos.all().query).endswith('"todos_todo"."id" ASC')
        )
        self.assertEqual(
            [todo.pk for todo in self.todo_list.todos.all()],
            sorted(todo.pk for todo in todos),
        )

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
        for todo, value in [(open_todo, "1"), (done_todo, "0")]:
            with self.subTest(todo=todo.title):
                action = reverse("todo_toggle", args=[todo.pk])
                _, hidden = button_form(response, action)
                self.assertEqual(hidden["done"], value)

    def test_done_goes_back_to_its_row(self):
        first, second, _ = self.make_three()
        url = self.todo_list.get_absolute_url()
        response = self.client.get(url)
        next_url = button_next(response, reverse("todo_toggle", args=[second.pk]))
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
        self.assertTrue(button_next(response, action).endswith(f"#todo-{third.pk}"))
        # A bad status shows every row, so it is no filter: the row stays.
        response = self.client.get(f"{url}?status=bogus")
        self.assertTrue(button_next(response, action).endswith(f"#todo-{second.pk}"))

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

    def test_delete_ignores_done(self):
        # The row's Delete shares its form with Done/Undo, so it also sends done.
        for value in ["0", "1"]:
            with self.subTest(done=value):
                todo = Todo.objects.create(title="Call home", todo_list=self.todo_list)
                self.client.post(
                    reverse("todo_delete", args=[todo.pk]), {"done": value}
                )
                self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

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
            next_url = button_next(self.client.get(url), action)
            response = self.client.post(action, {"next": next_url})
            self.assertRedirects(response, next_url, fetch_redirect_response=False)
            return next_url

        self.assertEqual(delete(first), f"{url}#todo-{second.pk}")
        self.assertEqual(delete(third), f"{url}#todo-{second.pk}")
        self.assertEqual(delete(second), f"{url}#todos")
        # The anchor after the only row names an element that exists.
        self.assertContains(self.client.get(url), 'id="todos"', count=1)
