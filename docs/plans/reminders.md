# Plan: Mac notifications for to-dos that are due

Status: **done** (2026-10-10, PR #27). The plan was approved again on 2026-10-10 after the
person changed how reminders are shown (see the next section). The person's answers are in
"Decided by the person" at the end.

Builds on: **accounts** (wave 1: Django `User`, login everywhere), **lists** (wave 2: each to-do
is in a `TodoList`, and the owner of a to-do is `todo.todo_list.owner`), **due date** (wave 2:
`Todo.due_date`), **sharing** (wave 3: other people can add to-dos to a list) and **recurring**
(wave 4: `Todo.make_next_copy`).

## Changed on 2026-10-10

What changed, and why:

- **The site runs on the person's own Mac**, not on a server on the internet. GitHub Pages was
  ruled out: it can only show fixed files, and it cannot run Django.
- **A reminder is now a macOS notification** (the small box in the top right corner of the
  screen), **not an email**. So everything about email is gone from this plan: no SMTP, no
  `EMAIL_*` settings, no email addresses, no "an admin sets the address", no console-backend
  check.
- **The Mac's time zone is `Asia/Tokyo`**, the same as `TIME_ZONE` in `config/settings.py`.
- Because of these three changes, this plan now also decides: **whose** to-dos the notification
  shows (a new option `--user`), **how** the app shows a notification safely (`osascript`), what
  happens **when it is not a Mac**, and **how the command runs every morning** (launchd instead
  of cron).

What stays from the approved plan: a management command `send_reminders`; only to-dos **due
today** and **not done**; a field `reminded_on` so the same to-do is not reminded twice; the date
"today" is `timezone.localdate()`; the logic is in functions that take a fixed date, so tests can
use any day; tests first.

## Goal

Once a day, in the morning, the Mac shows **one notification** that lists the person's to-dos that
are **due today** and **not done**. If nothing is due today, there is no notification.

The app cannot wake itself up. A **scheduler** starts it once a day. A scheduler is a program that
runs a command at a fixed time. On a Mac, the scheduler is called **launchd**. The app only gives
launchd one command to run: `python manage.py send_reminders --user <username>`.

## Decisions

### What is reminded

- **A management command.** A management command is a command you run with
  `python manage.py <name>`, like `migrate`. Django has this built in. We add one called
  `send_reminders`. No Celery, no new package.
- **"Due today", not "due tomorrow".** The notification comes in the morning and says what to do
  today. This matches the due date plan, where "due today" is not yet overdue. Overdue to-dos are
  not in the notification: the list page already shows them in red.
- **"Today" is the date in `TIME_ZONE`** (`Asia/Tokyo`). The command uses
  `timezone.localdate()`, the same as `Todo.is_overdue`. The Mac's own time zone is also
  Tokyo, so the 08:00 in launchd (the Mac's clock) and "today" in the app (Tokyo) always agree.
  Japan has no summer time, so this never moves.

### Whose to-dos: the option `--user`

The app has several users, but a notification shows on **one Mac**, for the one person sitting at
it. So the command must know **which user** it is for.

- **The command has one option, `--user <username>`, and it is required.** Without it, the
  command stops with an error. We do not guess a user (for example "the first user"): a guess
  could show one person's to-dos on another person's screen.
- **An unknown user, or a switched-off user** (`is_active=False`), gives a `CommandError` (an
  error that stops the command and prints the reason): `No active user named "bob".` Nothing is
  shown and nothing is marked. The same message for both, so the command does not tell which
  usernames exist.
- **Only the user's own lists** (`todo_list__owner=user`), **not the lists shared with them.**
  Reasons:
  1. `reminded_on` is **one date per to-do**, not one per person. If a to-do could be reminded
     to two people (the owner and a member), the first one's run marks it, and the second person
     never sees it. With "own lists only", every to-do has exactly **one** person who can be
     reminded of it (its list's owner), so one date per to-do is always right.
  2. It keeps the rule of the approved plan: "only the owner is reminded".
  3. It is the smallest change. Shared lists can come later, with a small table "this to-do was
     shown to this person on this day". See "New open questions".
- **To-dos a member added to the owner's list are included.** They are in the owner's own list,
  so the owner is reminded of them. This is why the title clean-up below matters: another person
  can choose these titles.
- `TodoList.objects.visible_to(user)` is **not** used here, on purpose. It is for pages, where a
  member must see the shared list. The plan says this in a comment in the code, so a later change
  does not "fix" it by mistake.

### How the notification is shown: `osascript`, safely

macOS has a program `/usr/bin/osascript`. It runs a small **AppleScript** program (AppleScript is
the Mac's own script language). The AppleScript command `display notification` shows a
notification. Python starts `osascript` with `subprocess.run` (Python's way to start another
program and wait for it).

**The danger: AppleScript injection.** A to-do title is text a person typed, and on a shared list
it can be typed by **another person**. If we built the AppleScript program by gluing the title
into it, like `'display notification "' + title + '"'`, then a title like
`" & do shell script "rm -rf ~` would end our text early and add its own AppleScript command. That
command could run any program on the Mac. This is called **injection**: user text becomes code.

**The safe way:** the AppleScript program is a **fixed text in our code**, and it never changes.
The title and the text of the notification are given to it as **separate arguments** (an argument
is one item in the list of words a program is started with). AppleScript reads them with
`on run argv` (`argv` is the list of arguments). An argument is always only text, never code,
whatever it contains.

```python
# todos/reminders.py
OSASCRIPT = "/usr/bin/osascript"
# Fixed AppleScript. The title and the text come in as arguments (argv), so
# a to-do title is never read as code. Never build this text from user data.
SCRIPT_LINES = [
    "on run argv",
    "display notification (item 2 of argv) with title (item 1 of argv)",
    "end run",
]
TIMEOUT_SECONDS = 30


def show_notification(title, text):
    args = [OSASCRIPT]
    for line in SCRIPT_LINES:
        args += ["-e", line]
    # "--" ends osascript's own options. Without it, an argument that starts
    # with "-" (like "-e ...") would be read as more AppleScript code.
    args += ["--", title, text]
    try:
        subprocess.run(args, check=True, timeout=TIMEOUT_SECONDS, capture_output=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise NotificationError(reason(error)) from error
```

- **A list of arguments, never `shell=True`.** With `shell=True`, Python would give one long
  line to the **shell** (the program that reads commands in the Terminal), and the shell has its
  own injection problems. With a list, no shell is used.
- **The full path `/usr/bin/osascript`.** launchd starts programs with a very short `PATH` (the
  list of folders where the computer looks for programs). The full path always works on a Mac.
- **`check=True`**: if `osascript` ends with an error code, Python raises
  `CalledProcessError`.
- **`timeout=30`**: if `osascript` does not end within 30 seconds, Python stops it and raises
  `TimeoutExpired`. So the command can never hang forever. (Showing a notification takes less
  than a second.)
- **`--` before the title and the text.** `osascript` reads an argument that starts with `-` as
  one of its own **options** (settings for the program). It was tested: after
  `-e 'end run'`, the arguments `-e` `x` make `osascript` run `x` as AppleScript. Our text starts
  with `- ` (the first title line), and a to-do title can start with `-e`. `--` means "no more
  options after this", so everything after it is only text for `argv`.
- **`capture_output=True`** keeps `osascript`'s output away from the log (see the reason below).
- `OSError` covers "the program is not there" (`FileNotFoundError`). `SubprocessError` covers
  `CalledProcessError` and `TimeoutExpired`. All of them become one error of our own,
  `NotificationError`.
- **The reason in `NotificationError`** is only the name of the Python error and, for
  `CalledProcessError`, the exit code (the number a program gives back when it ends; 0 means it
  worked). For example `CalledProcessError (exit code 1)`, `TimeoutExpired (after 30 seconds)`,
  `FileNotFoundError`. **`osascript`'s error text (`stderr`) is never printed**: it can repeat
  parts of the notification text, so to-do titles would end up in the log file.
- **Known limit: success does not mean "seen".** `osascript` ends with exit code 0 even when
  notifications for it are turned off, not yet allowed, or hidden by a Focus mode (like Do Not
  Disturb). The app cannot know this. Then the to-dos are marked as reminded, but nothing showed.
  This is why step 1 of "What you must set up on your Mac" is to allow notifications first.

### The text of the notification

A notification has little room, and macOS cuts long text. So the text is short and built in
Python by `notification_text(todos)`, which returns `(title, text)`:

- **The title holds only a number:** `To-do list: 1 to-do due today` or
  `To-do list: 3 to-dos due today`. Never a to-do title.
- **The text:** at most **3** to-do titles, **one line each**, in the order of the list
  (`todo_list`, then `position`, the manual order). Each line starts with `- `.
- **Each title on one line, in this order:** first, every kind of space (line breaks, tabs, the
  Japanese wide space U+3000, ...) becomes one normal space (`" ".join(todo.title.split())`); then
  the other invisible control characters are removed (only characters where `str.isprintable()` is
  true are kept). The order matters: `isprintable()` is false for a line break and for U+3000, so
  doing it first would glue two words together. A form's text box cannot send a line break, but a
  hand-made `POST` can. Without this, a member of a shared list could add a "to-do" whose title is
  many lines of fake text.
- **A long title is cut:** at most 60 characters per line; a longer title becomes its first 59
  characters and `…`.
- **More than 3 to-dos:** a last line says how many are not shown: `and 2 more`.
- **A banner shows only about 2 or 3 lines.** So "and 2 more" (and sometimes the third title) may
  be visible only when the person opens the notification in **Notification Center** (click the
  date and time in the top right corner). The title with the number is always visible.
- **What is cut is still reminded.** All to-dos counted in the title are marked as reminded,
  also the ones in "and 2 more". The person sees the number and opens the site for the rest.
- `&`, `"` and `<` stay as they are. There is no HTML here, so nothing is escaped.

### When `reminded_on` is set

- **A new field `reminded_on`** is the date the to-do was last shown in a notification. The
  command skips a to-do when `reminded_on` is already today. So if launchd runs it twice in one
  day, or the person runs it by hand, the same notification does not come twice.
- **It is set only after `osascript` worked** (it ended without error and in time). If
  `osascript` fails or times out, nothing is marked, and the next run that day tries again.
- If the due date is later changed to another day, `reminded_on` is older than the new date, so
  the to-do is reminded again on its new day. No extra code.
- **No database transaction around `osascript`.** A transaction would lock the database for
  writing while we wait up to 30 seconds, and the website would have to wait too. We read the
  to-dos, show the notification, and then save `reminded_on` in one quick `update()`.
- **Known limit, on purpose:** if the program stops in the tiny moment after the notification but
  before `reminded_on` is saved, the next run shows it again. Two notifications are better than a
  lost one. Two runs at the **same** moment could also both show it; launchd runs it once a day,
  so we accept this.

### Not a Mac, or no `osascript`: an error, not a printout

When `osascript` is not there (for example on Linux, where the GitHub checks run), the command
**stops with a `CommandError`** (`Could not show the notification: ...`) and marks nothing.

Why an error and not "print the text instead": printing is not a reminder. If the command printed
the text and then marked the to-dos, the reminders would be lost without a sign. If it printed
and did not mark, a "success" would be different on a Mac and on Linux, and that is confusing.
An error is clear, and launchd's log shows it.

There is **no separate "is this a Mac?" check** in the code. "Not a Mac" shows up as
`FileNotFoundError` from `subprocess.run`, because `/usr/bin/osascript` is not there. So there is
only one thing to replace in tests: `subprocess.run`.

**The tests never start the real `osascript`.** One shared helper, `FakeOsascriptMixin` in the new
file `todos/tests/helpers.py`, replaces `todos.reminders.subprocess.run` with a fake
(`unittest.mock.patch`) in `setUp`, and keeps it as `self.run`. Both test files use it. A test
that wants "not a Mac" sets `self.run.side_effect = FileNotFoundError(...)`. So a test can never
show a real notification on the Mac or fail on Linux.

### Recurring copies start with no `reminded_on`

Checked on `main`: `Todo.make_next_copy` makes the copy with `Todo.objects.create(...)` and names
each copied field (`todo_list`, `title`, `description`, `priority`, `repeat`, `due_date`,
`repeated_from`), then the tags and steps. `reminded_on` is not in that list, so the copy gets
the default, `None`. **No code change is needed.** We add one test, so a later change to
`make_next_copy` cannot copy it by mistake. The comment in `make_next_copy` already says a new
field that a copy should keep is added there; `reminded_on` must **not** be.

### Running every morning: launchd, not cron

- **launchd** is the Mac's own scheduler. A **LaunchAgent** is a small settings file (a
  **plist**, an XML file) in `~/Library/LaunchAgents/` that tells launchd: "run this command for
  this user at this time".
- **Why not cron:** cron (the other scheduler) skips a job when the Mac is asleep at that time.
  launchd's `StartCalendarInterval` runs a missed job **when the Mac wakes up** (several missed
  days become one run). A laptop is often asleep at 08:00.
- **If the Mac is shut down** (not asleep) at 08:00, launchd does not run it later. Run the
  command by hand that day, or keep the Mac asleep instead of off.
- A LaunchAgent runs only while the person is logged in. That is fine: a notification needs a
  logged-in person anyway.
- **The repo ships a template** (a file with blanks to fill in):
  `deploy/macos/com.anyone-can-build-todo.reminders.plist`. **The person installs it**, with the
  commands in "What you must set up on your Mac". Installing it changes the Mac's settings, so the
  agent (the AI) must never do it.

### No make target

We add **no** `make` target. Reasons: launchd starts the project's Python directly, not `make`; the
command by hand is one short line (`uv run python manage.py send_reminders --user alice`); and a
make target that installs the plist would change the Mac's settings, which only the person should
do. The README shows the command.

## Not part of this task

- Email, SMTP and email addresses (dropped on 2026-10-10).
- Reminders for lists shared **with** the user (see "New open questions").
- More than one user per Mac in one run. Each person runs their own LaunchAgent with their own
  `--user`.
- A setting in the website to turn reminders on or off, or pick a time. The time is in the plist.
- A time zone per user.
- Reminders for overdue to-dos, or "due tomorrow".
- Clicking the notification to open the site. `display notification` cannot do that.
- Reminders for steps (subtasks).
- Running on Linux or Windows.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | New field `reminded_on = models.DateField(null=True, blank=True, editable=False)` on `Todo`. `make_next_copy` does not change. |
| `todos/migrations/0017_todo_reminded_on.py` | Made by `makemigrations todos --name todo_reminded_on`, after `0016_fill_todo_position`. Existing to-dos get `reminded_on = NULL` (never reminded). |
| `todos/reminders.py` (new) | `due_today(user, today)`, `notification_text(todos)`, `show_notification(title, text)`, `NotificationError`, and `send_reminders(user, today)`: the logic |
| `todos/management/__init__.py`, `todos/management/commands/__init__.py` (new, empty) | Django finds commands only in this folder layout |
| `todos/management/commands/send_reminders.py` (new) | The command: reads `--user`, finds the active user, calls `send_reminders(user, timezone.localdate())`, prints the result |
| `deploy/macos/com.anyone-can-build-todo.reminders.plist` (new) | The LaunchAgent template, with blanks to fill in |
| `todos/tests/helpers.py` (new) | `FakeOsascriptMixin`: replaces `todos.reminders.subprocess.run` in `setUp`, for both test files |
| `todos/tests/unit/test_reminders.py` (new) | Unit tests for `notification_text` and `show_notification` |
| `todos/tests/integration/test_reminders.py` (new) | Integration tests for `send_reminders` and the command |
| `README.md`, `AGENTS.md` | The new files and field, the command, and the launchd setup |

`editable=False` hides `reminded_on` from forms and the admin form. Nobody should set it by hand.
`config/settings.py` does **not** change.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in the tables in step 8. Run `make test` and show that they fail.

### 2. The model — `todos/models.py`

Add the field `reminded_on` (see the table above). Then:

```bash
uv run python manage.py makemigrations todos --name todo_reminded_on
uv run python manage.py migrate
```

Check that the new file is `0017_todo_reminded_on.py` and depends on `0016_fill_todo_position`.

### 3. The logic — new file `todos/reminders.py`

Functions that take the user and a fixed date, so the tests can choose the day:

```python
def due_today(user, today):
    """The to-dos in this user's OWN lists that are due today, not done, not yet reminded.

    Own lists only, not visible_to(user): reminded_on is one date per to-do,
    so each to-do must have only one person who can be reminded of it.
    """
    return list(
        Todo.objects.filter(todo_list__owner=user, due_date=today, done=False)
        .exclude(reminded_on=today)
        .order_by("todo_list__created_at", "todo_list_id", "position", "created_at", "pk")
    )


def send_reminders(user, today):
    """Show one notification with these to-dos. Returns how many were shown.

    Raises NotificationError, and marks nothing, when osascript fails.
    """
    todos = due_today(user, today)
    if not todos:
        return 0
    title, text = notification_text(todos)
    show_notification(title, text)  # raises NotificationError on failure
    Todo.objects.filter(pk__in=[todo.pk for todo in todos]).update(reminded_on=today)
    return len(todos)
```

Plus `notification_text`, `show_notification` and `NotificationError`, as in "Decisions".

`.exclude(reminded_on=today)` keeps to-dos where `reminded_on` is empty (`NULL`): Django writes the
SQL so that `NULL` is not excluded. The test `test_never_reminded_todo_is_shown` checks it.

### 4. The command — `todos/management/commands/send_reminders.py`

A `BaseCommand` with a `help` text. `add_arguments` adds `--user`, with `required=True` and a
help text. `handle()`:

1. Find the user: `User.objects.filter(username=..., is_active=True).first()`. If there is none,
   raise `CommandError('No active user named "<name>".')`.
2. Call `send_reminders(user, timezone.localdate())`.
3. If it raises `NotificationError`, raise `CommandError("Could not show the notification: ...")`
   with the short reason.
4. Write one line with `self.stdout.write(...)`: `Showed 1 notification (3 to-dos) for alice.`, or
   `No to-dos due today for alice.` The line never contains a to-do title, so the log file stays
   free of the person's to-dos.

### 5. The launchd template — `deploy/macos/com.anyone-can-build-todo.reminders.plist`

The blanks are written in capitals between `__`, and the person replaces them (see "What you must
set up on your Mac"):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.anyone-can-build-todo.reminders</string>
    <key>ProgramArguments</key>
    <array>
        <string>__REPO_PATH__/.venv/bin/python</string>
        <string>manage.py</string>
        <string>send_reminders</string>
        <string>--user</string>
        <string>__USERNAME__</string>
    </array>
    <key>WorkingDirectory</key>
    <string>__REPO_PATH__</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/anyone-can-build-todo-reminders.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/anyone-can-build-todo-reminders.log</string>
</dict>
</plist>
```

- **Full paths everywhere.** launchd does not understand `~` and has a short `PATH`.
- **The project's own Python, not `uv run`.** `.venv/bin/python` is the Python that `make setup`
  made, with this project's packages. In a background job, `uv run` could first change `.venv`,
  rewrite `uv.lock`, or need the internet, and then fail while nobody is watching. Starting the
  Python directly does none of this.
- **The job runs whatever code is in the project folder now** (the branch that is checked out).
  After you pull this feature, run `uv run python manage.py migrate` once, or the job fails
  because the database has no `reminded_on` column.
- **The log is outside the repo** (`~/Library/Logs/`), so it never shows in `git status`. The
  Mac's Console app can also show it.
- No environment variables are needed: on the Mac, the settings' laptop defaults are used, the
  same as for `make run`.

### 6. Checks

The migration check in `make check` and `check.yml` already catches a missing migration. The tests
run on Linux in GitHub, and they never start `osascript` (it is replaced in every test), so they
pass there. Nothing to change.

### 7. Docs

- `AGENTS.md`: add `todos/reminders.py`, the command and `deploy/macos/` to the table; add
  `reminded_on` to the `models.py` row ("not copied by `make_next_copy`"); a rule line "Never build
  AppleScript from user text; pass it as `argv`, and always put `--` before those arguments".
- `AGENTS.md`, rule "Only my data, plus what is shared with me": add an **exception** in plain
  words: "`todos/reminders.py` filters to-dos by `todo_list__owner` on purpose: `reminded_on` is
  one date per to-do, so only the owner is reminded. It is not a view. Views never do this."
- `README.md`: a new section "Reminders on your Mac" with the steps of "What you must set up on
  your Mac" below, and the new files in "How it is put together". Update the test numbers.

### 8. Tests

No CUJ test: there is no browser in this feature.

**Every test class in both files uses `FakeOsascriptMixin`** (in `todos/tests/helpers.py`). Its
`setUp` starts `patch("todos.reminders.subprocess.run")`, stops it with `self.addCleanup`, and
keeps the fake as `self.run`. A test that wants a failure sets `self.run.side_effect`. "Not a
Mac" is `self.run.side_effect = FileNotFoundError(...)`; there is nothing else to patch.

**Unit** — `todos/tests/unit/test_reminders.py`, `SimpleTestCase` (no database), with
`Todo(title=...)` made in memory and never saved:

| Test | What it checks |
|---|---|
| `test_title_says_one_todo` | One to-do: the title is exactly `To-do list: 1 to-do due today`. |
| `test_title_says_many_todos` | Two to-dos: the title is exactly `To-do list: 2 to-dos due today`. |
| `test_title_never_contains_a_todo_title` | A to-do titled `Secret plan`: the notification title does not contain `Secret plan`. |
| `test_text_lists_titles_in_order` | Titles `A`, `B`: the text is exactly `- A\n- B`. |
| `test_title_with_line_breaks_stays_on_one_line` | A title `Buy\nmilk\r\n\tnow`: the text is exactly `- Buy milk now`. |
| `test_japanese_wide_space_becomes_one_space` | A title `牛乳　を買う` (with the wide space U+3000): the text is exactly `- 牛乳 を買う`, with one normal space. |
| `test_control_characters_are_removed` | A title `Ring\x07bell`: the text is exactly `- Ringbell`. |
| `test_long_title_is_cut` | A title of 80 `x`: the line is `- ` plus 59 `x` plus `…` (60 characters after `- `). A title of exactly 60 characters is not cut. |
| `test_more_than_three_says_how_many_more` | Five to-dos `A` to `E`: the text is exactly `- A\n- B\n- C\nand 2 more`, and the title says `5 to-dos`. |
| `test_text_does_not_escape` | A title `Tom & "Jerry" <3` stays exactly the same in the text. |
| `test_runs_osascript_with_fixed_script_and_argv` | `show_notification("T", "X")`: the fake `run` got exactly `["/usr/bin/osascript", "-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run", "--", "T", "X"]`. |
| `test_title_cannot_inject_applescript` | A to-do titled `" & do shell script "x`, through `notification_text` and `show_notification`: the last argv item is exactly `- " & do shell script "x` (one item, unchanged); the three `-e` script items are exactly the fixed lines; no other argv item contains `do shell script`. |
| `test_dash_arguments_are_not_options` | `show_notification("-e x", '-e do shell script "y"')`: the argv is the fixed `-e` lines, then `"--"`, then exactly `"-e x"` and `'-e do shell script "y"'`, unchanged, as the last two items. |
| `test_error_reason_has_no_stderr` | The fake raises `CalledProcessError(1, ..., stderr=b"Buy milk")`: the `NotificationError` text contains `CalledProcessError` and `1`, and does not contain `Buy milk`. |
| `test_no_shell_with_check_and_timeout` | The fake `run` got `check=True` and `timeout=30`, and `shell` was not given or is `False`. |
| `test_timeout_raises_notification_error` | The fake raises `subprocess.TimeoutExpired`: `show_notification` raises `NotificationError`. |
| `test_failed_osascript_raises_notification_error` | The fake raises `subprocess.CalledProcessError(1, ...)`: `NotificationError`. |
| `test_missing_osascript_raises_notification_error` | The fake raises `FileNotFoundError`: `NotificationError`. |

**Integration** — `todos/tests/integration/test_reminders.py`, `TestCase` (a database). These do
not use the test client, because a command has no address; they test the logic with the database,
which is the lowest layer where the rules show. Users are made with `make_user()` from
`accounts/tests/helpers.py`, each with a `TodoList`.

Most tests call `send_reminders(alice, date(2026, 10, 10))`. The command tests call
`call_command("send_reminders", "--user", "alice", stdout=out)` with `out = io.StringIO()`, and
**replace `django.utils.timezone.now`** (with `unittest.mock.patch`) by a fixed time, so they never
depend on the real date. (`timezone.localdate()` asks `timezone.now()` for the time, so this
works.)

**Each "not shown" test also has one to-do that _is_ shown**, and checks that only that title is
in the notification text (the last argv item of the fake `run`). Without it, a `send_reminders`
that shows nothing at all would pass.

| Test | What it checks |
|---|---|
| `test_shows_todos_due_today` | Alice has two to-dos due today: `run` was called once; the text holds both titles; the result is 2. |
| `test_only_due_today` | To-dos due yesterday, tomorrow, with no due date, and one due today: the text holds only today's title. |
| `test_done_todo_is_not_shown` | One done and one not-done, both due today: the text holds only the not-done title. |
| `test_other_users_todos_not_shown` | Bob has a to-do due today in his own list: Alice's text does not hold it, and holds her own. |
| `test_list_shared_with_user_not_shown` | Bob shares his list with Alice (`members.add`); a to-do due today in it is not in Alice's text; her own to-do is; the shared to-do keeps `reminded_on = None`. |
| `test_member_added_todo_in_own_list_is_shown` | Alice shares her list with Bob; Bob's to-do in Alice's list, due today, is in Alice's text. |
| `test_nothing_due_shows_nothing` | Nothing due: `run` was not called, the result is 0, and a to-do due tomorrow keeps `reminded_on = None`. |
| `test_never_reminded_todo_is_shown` | A to-do with `reminded_on = None`, due today: it is shown (checks the `NULL` case of `exclude`). |
| `test_sets_reminded_on` | After a good run, the to-do's `reminded_on` is 2026-10-10 (read again from the database). |
| `test_second_run_same_day_shows_nothing` | Run once: `run` called once (check it). Run again: `run` is still called only once, and the result is 0. |
| `test_moved_due_date_is_reminded_again` | `reminded_on` is 2026-10-09 and `due_date` is 2026-10-10: it is shown. |
| `test_failed_osascript_marks_nothing` | The fake raises `CalledProcessError`: `send_reminders` raises `NotificationError`, and the to-do keeps `reminded_on = None`. |
| `test_timeout_marks_nothing` | The fake raises `TimeoutExpired`: `NotificationError`, and `reminded_on` stays `None`. |
| `test_failed_run_is_tried_again` | After the failure above, a second run with a working fake shows it and marks it. |
| `test_recurring_copy_starts_unreminded` | A daily to-do due 2026-10-10 with `reminded_on` 2026-10-10 is marked done and `make_next_copy(date(2026, 10, 10))` runs: the copy's `reminded_on` is `None`. |
| `test_command_needs_user_option` | `call_command("send_reminders")` without `--user` raises `CommandError`, and `run` was not called. |
| `test_command_unknown_user` | `--user nobody`: `CommandError` with `No active user named "nobody".`, and `run` was not called. |
| `test_command_inactive_user` | Alice with `is_active=False` and a to-do due today: the same `CommandError`, `run` not called, `reminded_on` stays `None`. |
| `test_command_prints_count` | One to-do due on the fixed date: the output is `Showed 1 notification (1 to-do) for alice.`, and does not contain the to-do's title. |
| `test_command_prints_nothing_due` | Nothing due: the output is `No to-dos due today for alice.` |
| `test_command_fails_when_osascript_fails` | The fake raises `CalledProcessError`: `CommandError` starting with `Could not show the notification`, and `reminded_on` stays `None`. |
| `test_command_fails_without_osascript` | The fake raises `FileNotFoundError` (as on Linux): `CommandError`, and `reminded_on` stays `None`. |
| `test_command_uses_tokyo_date` | `timezone.now` is replaced with 2026-10-09 23:30 UTC, which is 2026-10-10 08:30 in Tokyo. A to-do due 2026-10-10 is shown; one due 2026-10-09 is not. |

The test dates are fixed, so the tests give the same answer on any computer, at any time of day.

**Show each important test failing first** (rule in `AGENTS.md`). For example: remove
`.exclude(reminded_on=today)` and see `test_second_run_same_day_shows_nothing` fail; build the
script with the title glued in and see `test_title_cannot_inject_applescript` fail; mark the
to-dos before `show_notification` and see `test_failed_osascript_marks_nothing` fail; use
`visible_to(user)` and see `test_list_shared_with_user_not_shown` fail; remove the `"--"` and see
`test_dash_arguments_are_not_options` fail.

### 9. Before the commit

- Run `make check`.
- On the Mac: allow notifications first (step 3 of "What you must set up on your Mac"). Make a
  to-do due today in one of your own lists. Run
  `uv run python manage.py send_reminders --user <your username>` and see the notification. Run it
  again and see `No to-dos due today for <your username>.`

## What you must set up on your Mac

The app cannot do these things by itself, and the AI must not do them for you: they change your
Mac's settings. You do them once, in the Terminal.

1. **Move the project out of `Documents` (recommended).** macOS protects the `Documents` folder
   from programs that start in the background. Then launchd cannot even go into the project
   folder: the job fails **before** it starts, and the log file stays **empty**. So we recommend
   moving the project, for example to `~/code/anyone-can-build-todo`. Two more reasons:
   - The other way, giving Python **Full Disk Access** in System Settings, is not a good idea: it
     gives **every** Python script on the Mac access to all your files, and it stops working when
     Python is upgraded.
   - If **iCloud "Desktop & Documents"** is turned on, iCloud copies the files in `Documents`,
     and it can touch `db.sqlite3` while the app writes to it.

   After a move, run `make setup` again in the new folder (it makes `.venv` there).
2. **Get the database ready.** In the project folder, after you pull this feature:

   ```bash
   uv run python manage.py migrate
   ```

   The job runs whatever code is in the project folder. Without `migrate`, it fails, because the
   database has no `reminded_on` column.
3. **Allow notifications first.** Show one test notification:

   ```bash
   osascript -e 'display notification "Test" with title "To-do list"'
   ```

   Now **Script Editor** is in **System Settings → Notifications** (notifications from
   `osascript` show under that name). Open it and turn on **Allow notifications**. Run the line
   again and check that you see "Test". Also check that a Focus mode (like Do Not Disturb) is not
   on. **Do this before step 4:** `osascript` reports "it worked" even when the notification is
   not allowed, and then the app marks the to-dos as reminded although you saw nothing.
4. **Try the command by hand.** Make a to-do due today in one of your own lists, then:

   ```bash
   uv run python manage.py send_reminders --user <your username>
   ```

   **To try again** the same day: the shown to-dos are now marked, so a second run says
   `No to-dos due today`. Make a **new** to-do due today, and run it again.
5. **Fill in the template.** The template has three blanks: `__REPO_PATH__`, `__HOME__` and
   `__USERNAME__`. In the project folder, this one command copies the template and fills them in
   (`pwd` is the project folder; replace `alice` with your username on the site):

   ```bash
   mkdir -p ~/Library/LaunchAgents
   sed -e "s|__REPO_PATH__|$(pwd)|g" -e "s|__HOME__|$HOME|g" -e "s|__USERNAME__|alice|g" \
     deploy/macos/com.anyone-can-build-todo.reminders.plist \
     > ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   plutil -lint ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   ```

   `sed` replaces text in a file. `plutil -lint` checks that the file is a correct plist. It must
   say `OK`.
6. **Turn it on.** `bootout` first turns off an older copy, if there is one (otherwise
   `bootstrap` fails with `Bootstrap failed: 5`). An error from `bootout` the first time is
   normal.

   ```bash
   launchctl bootout gui/$(id -u)/com.anyone-can-build-todo.reminders
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   ```

   On macOS 13 or newer, a message **"Background Items Added"** may come. Open **System Settings
   → General → Login Items**, and check that the item is allowed under **Allow in the
   Background**. If it is off, the job never runs.
7. **Test it now**, without waiting for 08:00 (make a new to-do due today first):

   ```bash
   launchctl kickstart -k gui/$(id -u)/com.anyone-can-build-todo.reminders
   cat ~/Library/Logs/anyone-can-build-todo-reminders.log
   launchctl print gui/$(id -u)/com.anyone-can-build-todo.reminders | grep "last exit code"
   ```

   `last exit code = 0` means it worked. Another number with an **empty** log usually means
   launchd could not go into the project folder (see step 1).
8. **To change or stop it:** run the `bootout` line from step 6, change the file (or fill it in
   again with step 5), and run `bootstrap` again. To stop it for good, run `bootout` and delete
   the file from `~/Library/LaunchAgents/`.

## Decided by the person

### Still true from 2026-10-09

- The plan is approved: a management command `send_reminders`, to-dos due today and not done,
  `reminded_on` so nothing is reminded twice, "today" is `timezone.localdate()` in Tokyo.
- The scheduled job must run on the same machine as the SQLite file. (It now does: both are on the
  Mac.)

No longer true: "only an admin sets email addresses" (there is no email any more), and "hosting is
decided later" (it is decided: the person's Mac).

### Decided on 2026-10-10

- The site runs locally on the person's Mac (macOS), not on a server. GitHub Pages was ruled out,
  because it cannot run Django.
- A reminder is a macOS notification on that Mac, not an email. No SMTP, no email settings, no
  email addresses.
- The Mac's time zone is `Asia/Tokyo`, the same as `TIME_ZONE`.

### Answered on 2026-10-10 (the plan is approved again)

- **Shared lists:** own lists only, as this plan says. A to-do that another person added to one of
  the person's own lists is still shown.
- **Moving the project:** yes. The person moves the project out of `~/Documents/GitHub/` (for
  example to `~/code/`) before installing the launchd job. No Full Disk Access for Python.
- **Time:** 08:00 is right.

## Review

What changed in the review of 2026-10-10, and why:

- Added `--` before the title and the text: `osascript` reads an argument that starts with `-` as
  its own option, so a title like `-e ...` could run AppleScript. Removed the wrong sentence "an
  argument never starts with `-`" (the text starts with `- `). New test
  `test_dash_arguments_are_not_options`; `AGENTS.md` gets the rule "always `--`".
- Wrote down that `osascript` reports success even when notifications are off or hidden, and made
  "allow notifications first" a setup step before the first real run. Said how to try again
  after a run marked the to-dos.
- The plist starts `.venv/bin/python` directly instead of `uv run`: in a background job, `uv run`
  could change `.venv`, rewrite `uv.lock` or need the internet. Removed the wrong `--no-dev`
  sentence. Added "run `migrate` after pulling", because the job runs the checked-out code.
- `Documents`: the job can fail before it starts, with an empty log, so the setup now checks
  `last exit code` with `launchctl print`. Moving the project is the default; Full Disk Access
  for Python is advised against; iCloud sync of `db.sqlite3` is mentioned.
- Title clean-up order: spaces first, then the `isprintable` filter, so a Japanese wide space
  (U+3000) becomes one space instead of gluing words. New test.
- `AGENTS.md` gets an exception to "only my data": `todos/reminders.py` filters by
  `todo_list__owner` on purpose; views never do.
- `NotificationError` holds only the error's name and exit code, never `osascript`'s `stderr`,
  which could put to-do titles in the log. New test.
- Tests share one `FakeOsascriptMixin` in `todos/tests/helpers.py`; "not a Mac" is a
  `FileNotFoundError` from the fake, with no other check to patch.
- Setup: "Allow in the Background" (macOS 13+), `bootout` before `bootstrap`,
  `mkdir -p ~/Library/LaunchAgents`, and one `sed` command instead of a text editor.
- Noted that a banner shows only 2 or 3 lines; "and N more" may only be seen in Notification
  Center.
