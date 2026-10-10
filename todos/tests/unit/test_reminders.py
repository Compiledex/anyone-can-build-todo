import subprocess

from django.test import SimpleTestCase

from todos.models import Todo
from todos.reminders import NotificationError, notification_text, show_notification
from todos.tests.helpers import FakeOsascriptMixin

SCRIPT_ARGS = [
    "/usr/bin/osascript",
    "-e",
    "on run argv",
    "-e",
    "display notification (item 2 of argv) with title (item 1 of argv)",
    "-e",
    "end run",
]


def todos(*titles):
    """To-dos made in memory, never saved."""
    return [Todo(title=title) for title in titles]


class NotificationTextTests(FakeOsascriptMixin, SimpleTestCase):
    def test_title_says_one_todo(self):
        title, _ = notification_text(todos("A"))
        self.assertEqual(title, "To-do list: 1 to-do due today")

    def test_title_says_many_todos(self):
        title, _ = notification_text(todos("A", "B"))
        self.assertEqual(title, "To-do list: 2 to-dos due today")

    def test_title_never_contains_a_todo_title(self):
        title, _ = notification_text(todos("Secret plan"))
        self.assertNotIn("Secret plan", title)

    def test_text_lists_titles_in_order(self):
        _, text = notification_text(todos("A", "B"))
        self.assertEqual(text, "- A\n- B")

    def test_title_with_line_breaks_stays_on_one_line(self):
        _, text = notification_text(todos("Buy\nmilk\r\n\tnow"))
        self.assertEqual(text, "- Buy milk now")

    def test_japanese_wide_space_becomes_one_space(self):
        _, text = notification_text(todos("牛乳　を買う"))
        self.assertEqual(text, "- 牛乳 を買う")

    def test_control_characters_are_removed(self):
        _, text = notification_text(todos("Ring\x07bell"))
        self.assertEqual(text, "- Ringbell")

    def test_long_title_is_cut(self):
        _, text = notification_text(todos("x" * 80))
        self.assertEqual(text, "- " + "x" * 59 + "…")
        self.assertEqual(len(text), 2 + 60)
        _, text = notification_text(todos("y" * 60))
        self.assertEqual(text, "- " + "y" * 60)

    def test_more_than_three_says_how_many_more(self):
        title, text = notification_text(todos("A", "B", "C", "D", "E"))
        self.assertEqual(text, "- A\n- B\n- C\nand 2 more")
        self.assertEqual(title, "To-do list: 5 to-dos due today")

    def test_text_does_not_escape(self):
        _, text = notification_text(todos('Tom & "Jerry" <3'))
        self.assertEqual(text, '- Tom & "Jerry" <3')


class ShowNotificationTests(FakeOsascriptMixin, SimpleTestCase):
    def argv(self):
        return self.run.call_args.args[0]

    def test_runs_osascript_with_fixed_script_and_argv(self):
        show_notification("T", "X")
        self.assertEqual(self.argv(), [*SCRIPT_ARGS, "--", "T", "X"])

    def test_title_cannot_inject_applescript(self):
        show_notification(*notification_text(todos('" & do shell script "x')))
        argv = self.argv()
        self.assertEqual(argv[-1], '- " & do shell script "x')
        self.assertEqual(argv[:7], SCRIPT_ARGS)
        self.assertEqual([item for item in argv[:-1] if "do shell script" in item], [])

    def test_dash_arguments_are_not_options(self):
        show_notification("-e x", '-e do shell script "y"')
        self.assertEqual(
            self.argv(), [*SCRIPT_ARGS, "--", "-e x", '-e do shell script "y"']
        )

    def test_error_reason_has_no_stderr(self):
        self.run.side_effect = subprocess.CalledProcessError(
            1, "osascript", stderr=b"Buy milk"
        )
        with self.assertRaises(NotificationError) as caught:
            show_notification("T", "X")
        self.assertIn("CalledProcessError", str(caught.exception))
        self.assertIn("1", str(caught.exception))
        self.assertNotIn("Buy milk", str(caught.exception))

    def test_no_shell_with_check_and_timeout(self):
        show_notification("T", "X")
        kwargs = self.run.call_args.kwargs
        self.assertIs(kwargs["check"], True)
        self.assertEqual(kwargs["timeout"], 30)
        self.assertFalse(kwargs.get("shell", False))

    def test_timeout_raises_notification_error(self):
        self.run.side_effect = subprocess.TimeoutExpired("osascript", 30)
        with self.assertRaises(NotificationError):
            show_notification("T", "X")

    def test_failed_osascript_raises_notification_error(self):
        self.run.side_effect = subprocess.CalledProcessError(1, "osascript")
        with self.assertRaises(NotificationError):
            show_notification("T", "X")

    def test_missing_osascript_raises_notification_error(self):
        self.run.side_effect = FileNotFoundError("/usr/bin/osascript")
        with self.assertRaises(NotificationError):
            show_notification("T", "X")
