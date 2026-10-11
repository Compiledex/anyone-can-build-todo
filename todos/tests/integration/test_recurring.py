"""Tests for repeating to-dos: the copy on Done, and removing it on Undo."""

from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from unittest import mock

from django.urls import reverse
from django.utils import dateformat, timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.models import Subtask, Tag, Todo, TodoList
from todos.tests.helpers import count_queries, messages_of


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
