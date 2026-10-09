from datetime import UTC, date, datetime
from unittest import mock

from django.test import SimpleTestCase

from todos.models import Todo

# A fixed "today", so the tests give the same answer on any day.
TODAY = date(2026, 10, 9)


class IsOverdueTests(SimpleTestCase):
    def test_past_due_date_is_overdue(self):
        todo = Todo(title="Pay rent", due_date=date(2026, 10, 8))
        self.assertTrue(todo.is_overdue(today=TODAY))

    def test_due_today_is_not_overdue(self):
        todo = Todo(title="Pay rent", due_date=TODAY)
        self.assertFalse(todo.is_overdue(today=TODAY))

    def test_done_todo_is_not_overdue(self):
        todo = Todo(title="Pay rent", due_date=date(2026, 10, 8), done=True)
        self.assertFalse(todo.is_overdue(today=TODAY))

    def test_no_due_date_is_not_overdue(self):
        todo = Todo(title="Pay rent")
        self.assertFalse(todo.is_overdue(today=TODAY))

    def test_today_is_the_date_in_tokyo(self):
        # 16:00 on 9 October in UTC is already 01:00 on 10 October in Tokyo
        # (TIME_ZONE in config/settings.py), so a to-do due on 9 October is late.
        now = datetime(2026, 10, 9, 16, 0, tzinfo=UTC)
        todo = Todo(title="Pay rent", due_date=date(2026, 10, 9))
        with mock.patch("django.utils.timezone.now", return_value=now):
            self.assertTrue(todo.is_overdue())
