"""Mac notifications for the to-dos that are due today.

The command `send_reminders` (todos/management/commands/) calls send_reminders.
Every function takes the date as an argument, so tests can choose the day.
"""

import subprocess

from .models import Todo

OSASCRIPT = "/usr/bin/osascript"
# Fixed AppleScript. The title and the text come in as arguments (argv), so
# a to-do title is never read as code. Never build this text from user data.
SCRIPT_LINES = [
    "on run argv",
    "display notification (item 2 of argv) with title (item 1 of argv)",
    "end run",
]
TIMEOUT_SECONDS = 30

# How many to-do titles the text shows, and how long each line may be.
MAX_LINES = 3
MAX_LINE_LENGTH = 60


class NotificationError(Exception):
    """osascript could not show the notification. The text is a short reason."""


def due_today(user, today):
    """The to-dos in this user's OWN lists that are due today, not done, not yet reminded.

    Own lists only, not visible_to(user): reminded_on is one date per to-do,
    so each to-do must have only one person who can be reminded of it.
    """
    return list(
        Todo.objects.filter(todo_list__owner=user, due_date=today, done=False)
        .exclude(reminded_on=today)
        .order_by(
            "todo_list__created_at", "todo_list_id", "position", "created_at", "pk"
        )
    )


def one_line(title):
    """A to-do title on one short line.

    First every kind of space (line breaks, tabs, the Japanese wide space)
    becomes one normal space, then the other invisible characters go. In the
    other order, a line break would be removed and glue two words together.
    """
    line = " ".join(title.split())
    line = "".join(char for char in line if char.isprintable())
    if len(line) > MAX_LINE_LENGTH:
        line = line[: MAX_LINE_LENGTH - 1] + "…"
    return line


def notification_text(todos):
    """(title, text) of the notification for these to-dos.

    The title holds only the number, never a to-do title. Nothing is escaped:
    there is no HTML here, and osascript gets the text as an argument.
    """
    count = len(todos)
    title = f"To-do list: {count} to-do{'' if count == 1 else 's'} due today"
    lines = [f"- {one_line(todo.title)}" for todo in todos[:MAX_LINES]]
    if count > MAX_LINES:
        lines.append(f"and {count - MAX_LINES} more")
    return title, "\n".join(lines)


def reason(error):
    """A short reason for the log: the error's name, and the exit code.

    Never osascript's stderr: it can repeat the text, so to-do titles would end
    up in the log file.
    """
    name = type(error).__name__
    if isinstance(error, subprocess.CalledProcessError):
        return f"{name} (exit code {error.returncode})"
    if isinstance(error, subprocess.TimeoutExpired):
        return f"{name} (after {TIMEOUT_SECONDS} seconds)"
    return name


def show_notification(title, text):
    """Show one Mac notification. Raises NotificationError when it fails."""
    args = [OSASCRIPT]
    for line in SCRIPT_LINES:
        args += ["-e", line]
    # "--" ends osascript's own options. Without it, an argument that starts
    # with "-" (like "-e ...") would be read as more AppleScript code.
    args += ["--", title, text]
    try:
        # A list, never shell=True: no shell reads the text.
        subprocess.run(args, check=True, timeout=TIMEOUT_SECONDS, capture_output=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise NotificationError(reason(error)) from error


def send_reminders(user, today):
    """Show one notification with these to-dos. Returns how many were shown.

    Raises NotificationError, and marks nothing, when osascript fails. No
    transaction around osascript: it would lock the database for the website
    while we wait.
    """
    todos = due_today(user, today)
    if not todos:
        return 0
    title, text = notification_text(todos)
    show_notification(title, text)  # raises NotificationError on failure
    Todo.objects.filter(pk__in=[todo.pk for todo in todos]).update(reminded_on=today)
    return len(todos)
