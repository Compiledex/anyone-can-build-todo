"""Test helpers for the to-do tests.

The name does not start with `test`, so the test runner does not load this
file as tests. Other test files import from it.
"""

from unittest.mock import patch


class FakeOsascriptMixin:
    """Replaces subprocess.run in todos/reminders.py with a fake, for every test.

    So a test never starts the real osascript: it never shows a notification on
    the Mac, and it does not fail on Linux. The fake is self.run. A test that
    wants a failure sets self.run.side_effect, for example
    FileNotFoundError(...) for "not a Mac".
    """

    def setUp(self):
        super().setUp()
        patcher = patch("todos.reminders.subprocess.run")
        self.run = patcher.start()
        self.addCleanup(patcher.stop)

    def shown_text(self):
        """The text of the last notification: the last argv item of the fake run."""
        return self.run.call_args.args[0][-1]
