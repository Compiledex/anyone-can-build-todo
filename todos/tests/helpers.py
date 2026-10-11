"""Test helpers for the to-do tests.

The name does not start with `test`, so the test runner does not load this
file as tests. Other test files import from it.
"""

from unittest.mock import patch

from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext

from todos.models import Todo


def add_todo(todo_list, title, **fields):
    """A new to-do in this list."""
    return Todo.objects.create(todo_list=todo_list, title=title, **fields)


def shown_titles(response):
    """The titles of the to-dos the list page shows, in their order."""
    return [todo.title for todo in response.context["todos"]]


def messages_of(response):
    """The texts of the messages this response added."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def count_queries(func):
    """Runs func() and returns how many database queries it made.

    Fails when there are none: then func() did not load the page, and two
    counts of 0 would prove nothing.
    """
    with CaptureQueriesContext(connection) as queries:
        func()
    if not queries:
        raise AssertionError("func() made no database queries.")
    return len(queries)


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


def webp_size(path):
    """The width and height of a WebP file, read from its header (no image package).

    A WebP file is RIFF, then "WEBP", then its first chunk: VP8X (extended), VP8
    (lossy) or VP8L (lossless). Each keeps the size in its own place.
    """
    with open(path, "rb") as file:
        data = file.read(30)
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError(f"{path} is not a WebP file")
    chunk = data[12:16]
    if chunk == b"VP8X":  # 24-bit numbers, each 1 less than the size.
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
    elif chunk == b"VP8 ":  # 14-bit numbers after the frame start code.
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
    elif chunk == b"VP8L":  # Two 14-bit numbers, each 1 less than the size.
        bits = int.from_bytes(data[21:25], "little")
        width = 1 + (bits & 0x3FFF)
        height = 1 + ((bits >> 14) & 0x3FFF)
    else:
        raise ValueError(f"{path}: unknown WebP chunk {chunk!r}")
    return width, height
