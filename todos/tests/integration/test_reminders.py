import io
import subprocess
from datetime import UTC, date, datetime
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.tests.helpers import make_user
from todos.models import Todo, TodoList
from todos.reminders import NotificationError, send_reminders
from todos.tests.helpers import FakeOsascriptMixin

# A fixed "today", so the tests give the same answer on any day.
TODAY = date(2026, 10, 10)
YESTERDAY = date(2026, 10, 9)
TOMORROW = date(2026, 10, 11)
# 2026-10-10 08:00 in Tokyo (UTC+9), for the command tests.
TOKYO_MORNING = datetime(2026, 10, 9, 23, 0, tzinfo=UTC)


class RemindersTestCase(FakeOsascriptMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user("alice")
        cls.bob = make_user("bob")
        cls.alice_list = TodoList.objects.create(owner=cls.alice, name="Inbox")
        cls.bob_list = TodoList.objects.create(owner=cls.bob, name="Bob's list")

    def add(self, title, due_date=TODAY, todo_list=None, **fields):
        return Todo.objects.create(
            todo_list=todo_list or self.alice_list,
            title=title,
            due_date=due_date,
            **fields,
        )

    def reminded_on(self, todo):
        todo.refresh_from_db()
        return todo.reminded_on


class SendRemindersTests(RemindersTestCase):
    def test_shows_todos_due_today(self):
        self.add("Buy milk")
        self.add("Pay rent")
        self.assertEqual(send_reminders(self.alice, TODAY), 2)
        self.run.assert_called_once()
        self.assertIn("Buy milk", self.shown_text())
        self.assertIn("Pay rent", self.shown_text())

    def test_only_due_today(self):
        self.add("Yesterday thing", due_date=YESTERDAY)
        self.add("Tomorrow thing", due_date=TOMORROW)
        self.add("Someday thing", due_date=None)
        self.add("Today thing")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Today thing")

    def test_done_todo_is_not_shown(self):
        self.add("Finished", done=True)
        self.add("Still open")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Still open")

    def test_other_users_todos_not_shown(self):
        self.add("Bob's secret", todo_list=self.bob_list)
        self.add("Alice's own")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Alice's own")

    def test_list_shared_with_user_not_shown(self):
        self.bob_list.members.add(self.alice)
        shared = self.add("In Bob's shared list", todo_list=self.bob_list)
        self.add("Alice's own")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Alice's own")
        self.assertIsNone(self.reminded_on(shared))

    def test_member_added_todo_in_own_list_is_shown(self):
        # Bob is a member of Alice's list and adds a to-do to it.
        self.alice_list.members.add(self.bob)
        self.add("Added by Bob")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Added by Bob")

    def test_nothing_due_shows_nothing(self):
        later = self.add("Tomorrow thing", due_date=TOMORROW)
        self.assertEqual(send_reminders(self.alice, TODAY), 0)
        self.run.assert_not_called()
        self.assertIsNone(self.reminded_on(later))

    def test_never_reminded_todo_is_shown(self):
        todo = self.add("Never reminded")
        self.assertIsNone(todo.reminded_on)
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Never reminded")

    def test_sets_reminded_on(self):
        todo = self.add("Buy milk")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.reminded_on(todo), TODAY)

    def test_second_run_same_day_shows_nothing(self):
        self.add("Buy milk")
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.run.call_count, 1)
        self.assertEqual(send_reminders(self.alice, TODAY), 0)
        self.assertEqual(self.run.call_count, 1)

    def test_moved_due_date_is_reminded_again(self):
        self.add("Moved", reminded_on=YESTERDAY)
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- Moved")

    def test_failed_osascript_marks_nothing(self):
        todo = self.add("Buy milk")
        self.run.side_effect = subprocess.CalledProcessError(1, "osascript")
        with self.assertRaises(NotificationError):
            send_reminders(self.alice, TODAY)
        self.assertIsNone(self.reminded_on(todo))

    def test_timeout_marks_nothing(self):
        todo = self.add("Buy milk")
        self.run.side_effect = subprocess.TimeoutExpired("osascript", 30)
        with self.assertRaises(NotificationError):
            send_reminders(self.alice, TODAY)
        self.assertIsNone(self.reminded_on(todo))

    def test_failed_run_is_tried_again(self):
        todo = self.add("Buy milk")
        self.run.side_effect = subprocess.CalledProcessError(1, "osascript")
        with self.assertRaises(NotificationError):
            send_reminders(self.alice, TODAY)
        self.run.side_effect = None
        self.assertEqual(send_reminders(self.alice, TODAY), 1)
        self.assertEqual(self.shown_text(), "- Buy milk")
        self.assertEqual(self.reminded_on(todo), TODAY)

    def test_cut_todos_are_also_marked(self):
        # Only 3 titles fit in the text, but all 5 counted in the title are marked.
        made = [self.add(title) for title in "ABCDE"]
        self.assertEqual(send_reminders(self.alice, TODAY), 5)
        for todo in made:
            self.assertEqual(self.reminded_on(todo), TODAY)
        self.assertEqual(send_reminders(self.alice, TODAY), 0)
        self.assertEqual(self.run.call_count, 1)

    def test_shown_in_list_order_then_position(self):
        # Inbox is Alice's older list. Its to-dos are made in a different order
        # than their positions, and the newer list's to-do is made last.
        second = self.add("Second")
        first = self.add("First")
        work = TodoList.objects.create(owner=self.alice, name="Work")
        self.add("Work thing", todo_list=work)
        Todo.objects.filter(pk=first.pk).update(position=1)
        Todo.objects.filter(pk=second.pk).update(position=2)
        send_reminders(self.alice, TODAY)
        self.assertEqual(self.shown_text(), "- First\n- Second\n- Work thing")

    def test_recurring_copy_starts_unreminded(self):
        todo = self.add("Water plants", repeat=Todo.Repeat.DAILY, reminded_on=TODAY)
        todo.done = True
        todo.save()
        copy = todo.make_next_copy(TODAY)
        self.assertIsNotNone(copy)
        self.assertIsNone(self.reminded_on(copy))


@patch("django.utils.timezone.now", return_value=TOKYO_MORNING)
class SendRemindersCommandTests(RemindersTestCase):
    def call(self, *args):
        out = io.StringIO()
        call_command("send_reminders", *args, stdout=out)
        return out.getvalue()

    def test_command_needs_user_option(self, _now):
        with self.assertRaises(CommandError):
            self.call()
        self.run.assert_not_called()

    def test_command_unknown_user(self, _now):
        with self.assertRaisesMessage(CommandError, 'No active user named "nobody".'):
            self.call("--user", "nobody")
        self.run.assert_not_called()

    def test_command_inactive_user(self, _now):
        self.alice.is_active = False
        self.alice.save()
        todo = self.add("Buy milk")
        with self.assertRaisesMessage(CommandError, 'No active user named "alice".'):
            self.call("--user", "alice")
        self.run.assert_not_called()
        self.assertIsNone(self.reminded_on(todo))

    def test_command_prints_count(self, _now):
        self.add("Buy milk")
        output = self.call("--user", "alice")
        self.assertEqual(output, "Showed 1 notification (1 to-do) for alice.\n")
        self.assertNotIn("Buy milk", output)

    def test_command_prints_nothing_due(self, _now):
        output = self.call("--user", "alice")
        self.assertEqual(output, "No to-dos due today for alice.\n")

    def test_command_fails_when_osascript_fails(self, _now):
        todo = self.add("Buy milk")
        self.run.side_effect = subprocess.CalledProcessError(1, "osascript")
        with self.assertRaises(CommandError) as caught:
            self.call("--user", "alice")
        self.assertTrue(
            str(caught.exception).startswith("Could not show the notification")
        )
        self.assertIsNone(self.reminded_on(todo))

    def test_command_fails_without_osascript(self, _now):
        todo = self.add("Buy milk")
        self.run.side_effect = FileNotFoundError("/usr/bin/osascript")
        with self.assertRaises(CommandError):
            self.call("--user", "alice")
        self.assertIsNone(self.reminded_on(todo))

    def test_command_uses_tokyo_date(self, now):
        # 23:30 UTC on 9 October is 08:30 on 10 October in Tokyo.
        now.return_value = datetime(2026, 10, 9, 23, 30, tzinfo=UTC)
        self.add("Due on the 10th", due_date=date(2026, 10, 10))
        self.add("Due on the 9th", due_date=date(2026, 10, 9))
        self.call("--user", "alice")
        self.assertEqual(self.shown_text(), "- Due on the 10th")
