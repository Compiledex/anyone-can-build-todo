# Plan: email reminders for to-dos that are due

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: **accounts** (wave 1: Django `User`, login everywhere), **lists** (wave 2: each to-do
is in a `TodoList`, and the owner of a to-do is `todo.todo_list.owner`), **due date** (wave 2:
`Todo.due_date`) and **sharing** (wave 3: other people can add to-dos to a list).

## Goal

Once a day, the app sends each user **one email** that lists their to-dos that are **due today**
and **not done**. A user with nothing due today gets no email.

The app cannot wake itself up. A **scheduler** on the server starts the sending once a day. A
scheduler is a program that runs a command at a fixed time; on Linux it is called **cron**. The
app only gives cron one command to run: `python manage.py send_reminders`.

## Decisions

- **A management command.** A management command is a command you run with
  `python manage.py <name>`, like `migrate`. Django has this built in. We add one called
  `send_reminders`. No Celery, no new package.
- **"Due today", not "due tomorrow".** The email comes in the morning and says what to do today.
  This matches the due date plan, where "due today" is not yet overdue. Overdue to-dos are not in
  the email: the list page already shows them in red.
- **"Today" is the date in `TIME_ZONE`** (`Asia/Tokyo` in `config/settings.py`). The command uses
  `timezone.localdate()`, the same as `Todo.is_overdue`. Users have no time zone of their own, so
  everyone gets "today" in Tokyo. The server clock is usually in UTC; that does not matter for the
  code, but it matters for the cron time (see "What you must set up on the server").
- **The owner is the list's owner.** The lists plan removed `Todo.owner`; the owner of a to-do is
  `todo.todo_list.owner`. So every query goes through the list: `todo_list__owner`. (If the merged
  lists code kept a `Todo.owner` field, still use `todo_list__owner`, because sharing says no code
  may filter to-dos by `Todo.owner` any more.)
- **Where the email address comes from: only an admin sets it.** The accounts plan has **no email
  address** on sign-up, and no page to change one. Django's `User` already has an `email` field;
  an admin can fill it in `/admin/`. Only users with an email address get reminders. This also
  means nobody can type a stranger's address and make the app send them emails, because admins are
  trusted. A page where a person types (and confirms) their own address is a separate task. See
  "Open questions".
- **A new field `reminded_on` stops double emails.** It is the date the last reminder for this
  to-do was sent. The command skips a to-do when `reminded_on` is already today. So if cron runs
  twice in one day, or a person runs the command by hand, nobody gets the same email twice.
  - If the due date is later changed to another day (with the edit feature), `reminded_on` is
    older than the new date, so the to-do is reminded again on its new day. No extra code needed.
  - `reminded_on` is set **only after the email was sent**, one user at a time. If sending fails,
    the to-do is not marked, and the next run tries again (the same day only, because only "due
    today" is sent).
  - **Known limit, on purpose:** if the program stops in the tiny moment after the email was sent
    but before `reminded_on` was saved (the server restarts, for example), the next run sends that
    one user's email again. A second email is better than a lost one. Two runs at the **same**
    moment could also both send; cron runs it once a day, so we accept this.
- **Only the owner gets the email.** People a list is shared with (sharing, wave 3) do not get a
  reminder, even for to-dos they added. That keeps one clear rule: one email per owner, with the
  to-dos in their own lists.
- **Users without an email address are skipped.** No error. Their to-dos are not marked, and the
  command's output counts them ("skipped 1 user with no email address"). Inactive users
  (`is_active=False`) are skipped too.
- **One failed email does not stop the others.** If sending to one user raises any error
  (`except Exception`: the mail server says no, the network is down, ...), the command writes the
  error, goes on with the next user, and at the end exits with an error (a `CommandError`), so
  cron's log shows that something went wrong.
- **Sending can never hang forever.** Django waits for the mail server with no time limit by
  default (`EMAIL_TIMEOUT = None`). We set `EMAIL_TIMEOUT = 30` (seconds), so a broken mail server
  gives an error instead of a cron job that never ends.
- **No "sent" when nothing was sent.** On a live server (`DEBUG` is `False`) with no mail server
  set, the console backend would only print the emails, and the command would still mark the
  to-dos as reminded: the reminders would be lost without a sign. So the command **refuses to
  run** in that case, with a `CommandError` ("Email is not set up: set DJANGO_EMAIL_HOST"), before
  it sends or marks anything.
- **Plain text email, built in Python.** No HTML email, and no template. A Django template escapes
  `&` to `&amp;` even in a `.txt` file, which would look wrong in a plain text email.
  - The **subject** holds only a number ("To-do list: 2 to-dos due today"), never a to-do title,
    so a title can never break the email's header lines. (Django also refuses a header with a line
    break in it, with `BadHeaderError`.)
  - In the **body**, each title is put on **one line**: line breaks and tabs in a title become
    single spaces (`" ".join(todo.title.split())`). A form's text box cannot send a line break,
    but a hand-made `POST` can. Without this, a person a list is shared with could add a "to-do"
    whose title is many lines of fake text, and the app would email it to the owner.
- **Email settings come from environment variables**, like the secret key. With no
  `DJANGO_EMAIL_HOST` set (on a laptop), Django's **console backend** is used: the email is printed
  in the terminal, not sent. A **backend** is the part of Django that actually delivers email.
- **Tests need no email setting.** Django's test runner always switches to the **locmem
  backend**, which keeps sent emails in a Python list, `django.core.mail.outbox`. Nothing is sent
  for real. (Checked: `setup_test_environment` does this, our `LayeredTestRunner` calls it through
  `super()`, and with `--parallel` each worker process calls it too.)

## Not part of this task

- A page where a person types their own email address, and a confirmation email that proves the
  address is theirs. Until that exists, only an admin sets addresses (see Decisions).
- A setting where a user turns reminders on or off, or picks a time. Everyone with an email
  address and a to-do due today gets one. To stop them, an admin clears the address.
- A time zone per user.
- Reminders for overdue to-dos, or "due tomorrow".
- A link to the site in the email. It needs a new setting for the site's address; it can be added
  later.
- Reminders for members of a shared list.
- Reminders for subtasks (wave 4, same wave). Recurring to-dos (wave 4, same wave) work without
  extra code: the copy gets a new due date, and the recurring plan copies only the fields in its
  table, so the copy starts with `reminded_on = None`. If recurring is merged first, add
  `reminded_on` to its "not copied" column.
- HTML email, more than one email per user per day, push notifications.
- Starting cron from the app. The person who runs the server must set it up (see below).

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | New field `reminded_on = models.DateField(null=True, blank=True, editable=False)` |
| `todos/migrations/00xx_todo_reminded_on.py` | Made by `makemigrations`. Existing to-dos get `reminded_on = NULL` (never reminded). |
| `todos/reminders.py` (new) | `reminder_message(todos)` and `send_reminders(today)`: the logic |
| `todos/management/__init__.py`, `todos/management/commands/__init__.py` (new, empty) | Django finds commands only in this folder layout |
| `todos/management/commands/send_reminders.py` (new) | The command. It checks that email is set up, calls `send_reminders(timezone.localdate())` and prints the result |
| `config/settings.py` | Email settings from environment variables |
| `todos/tests/unit/test_reminders.py` (new) | Unit tests for `reminder_message` |
| `todos/tests/integration/test_reminders.py` (new) | Integration tests for `send_reminders` and the command |
| `README.md`, `AGENTS.md` | New files, new environment variables, how an admin sets an email address, the cron setup |

`editable=False` hides `reminded_on` from forms and the admin form. Nobody should set it by hand.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in the tables in step 8. Run `make test` and show that they fail.

### 2. The model — `todos/models.py`

Add the field `reminded_on` (see the table above). Then:

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

### 3. The logic — new file `todos/reminders.py`

Two functions, so the tests can pass a fixed date, like `is_overdue(today=...)`:

```python
from itertools import groupby

from django.core.mail import send_mail

from .models import Todo


def reminder_message(todos):
    """The subject and body of one reminder email."""
    count = len(todos)
    noun = "to-do" if count == 1 else "to-dos"
    subject = f"To-do list: {count} {noun} due today"
    # " ".join(title.split()) puts each title on one line, whatever it contains.
    titles = [f"- {' '.join(todo.title.split())}" for todo in todos]
    lines = [f"Due today ({count}):", ""] + titles
    return subject, "\n".join(lines) + "\n"


def send_reminders(today):
    """Email each user their to-dos due on `today`. Returns counts for the output."""
    todos = (
        Todo.objects.filter(
            due_date=today, done=False, todo_list__owner__is_active=True
        )
        .exclude(reminded_on=today)
        .select_related("todo_list__owner")
        .order_by("todo_list__owner_id", "created_at")
    )
    ...
```

`.exclude(reminded_on=today)` keeps to-dos where `reminded_on` is empty (`NULL`): Django writes
the SQL so that `NULL` is not excluded. The test `test_never_reminded_todo_is_sent` checks it.

`send_reminders` then, for each owner (with `groupby` on `todo.todo_list.owner_id`; turn each
group into a `list` first, because a `groupby` group can be read only once):

- no email address: count the user as skipped, go on;
- otherwise `send_mail(subject, body, None, [owner.email])`. `None` means "use
  `DEFAULT_FROM_EMAIL`";
- if `send_mail` raises an error (`except Exception`): remember the user and the error, go on;
- if it worked: `Todo.objects.filter(pk__in=[...]).update(reminded_on=today)`, right away, before
  the next user.

It returns the numbers: emails sent, to-dos in them, users skipped, and the list of errors.

### 4. The command — `todos/management/commands/send_reminders.py`

A `BaseCommand` with a `help` text. The command has no options. `handle()`:

1. If `settings.DEBUG` is `False` and `settings.EMAIL_BACKEND` is the console backend, raise
   `CommandError("Email is not set up: set DJANGO_EMAIL_HOST")`. Nothing is sent or marked.
2. Call `send_reminders(timezone.localdate())`.
3. Write one line with `self.stdout.write(...)`, for example
   `Sent 2 reminders (5 to-dos). Skipped 1 user with no email address.`
4. If there were errors, write one line per error (the username and the error, never the
   password or other settings) and raise `CommandError`.

### 5. Settings — `config/settings.py`

```python
# Email. On a laptop, emails are printed in the terminal. On a live server, set
# DJANGO_EMAIL_HOST and the other variables, so they are sent for real.
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True  # Port 587 with STARTTLS: the usual setting for mail services.
EMAIL_TIMEOUT = 30  # Seconds. Without it, a broken mail server can make the command hang.
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "todo@localhost")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
```

**SMTP** is the standard way to send email to a mail server. **TLS** keeps the password secret
on the way to the mail server. The password is never in the code.

### 6. Checks

The migration check in `make check` and `check.yml` already catches a missing migration. Nothing
to change.

### 7. Docs

- `AGENTS.md`: add `todos/reminders.py` and the command to the table, and add the new field to the
  `models.py` row.
- `README.md`: add the email variables to the "Put it on the internet" table; a short note "To get
  reminders, an admin opens the user in `/admin/` and fills in Email address"; and a new section
  "Reminders" with the cron setup below. Update the test numbers.

### 8. Tests

No CUJ test: there is no browser in this feature.

**Unit** — `todos/tests/unit/test_reminders.py`, `SimpleTestCase`, with `Todo(...)` made in memory
and never saved:

| Test | What it checks |
|---|---|
| `test_subject_says_one_todo` | One to-do: subject is exactly `To-do list: 1 to-do due today`. |
| `test_subject_says_many_todos` | Two to-dos: subject is exactly `To-do list: 2 to-dos due today`. |
| `test_body_lists_titles_in_order` | Each title on its own line, in the order given. |
| `test_body_does_not_escape_title` | A title `Tom & Jerry` stays `Tom & Jerry`, not `&amp;`. |
| `test_title_with_line_breaks_stays_on_one_line` | A title `Buy\nmilk\r\nnow` is the line `- Buy milk now`, and the body has exactly one line per to-do after the header. |

**Integration** — `todos/tests/integration/test_reminders.py`, `TestCase` (a database, and
`mail.outbox`). These do not use the test client, because a command has no address; they test
the logic with the database, which is the lowest layer where the rules show. Each user gets a
list (`TodoList`) and the to-dos go in it.

Most tests call `send_reminders(date(2026, 10, 9))`. The command tests call
`call_command("send_reminders", stdout=out)` with `out = io.StringIO()`, and **replace
`django.utils.timezone.now`** (with `unittest.mock.patch`) by a fixed time, so they never depend
on the real date. (`timezone.localdate()` asks `timezone.now()` for the time, so this works.)

**Each "nothing is sent" test also has one to-do that _is_ sent**, and checks that only that
title is in the email. Without it, a `send_reminders` that sends nothing at all would pass.

| Test | What it checks |
|---|---|
| `test_one_email_per_user` | A has two to-dos due today, B has one: exactly two emails, one to each address, A's email holds both of A's titles. |
| `test_email_has_only_that_users_todos` | A's email does not contain B's title, and B's does not contain A's. |
| `test_done_todo_is_not_reminded` | A has one done and one not-done to-do due today: one email, with only the not-done title. |
| `test_only_todos_due_today` | To-dos due yesterday, tomorrow, with no due date, and one due today: one email, with only today's title. |
| `test_no_email_when_nothing_is_due` | Nothing due: `mail.outbox` is empty, and the result says 0 sent. |
| `test_never_reminded_todo_is_sent` | A to-do with `reminded_on = None`, due today: it is sent (checks the `NULL` case of `exclude`). |
| `test_sets_reminded_on` | After sending, the to-do's `reminded_on` is today (read again from the database). |
| `test_second_run_same_day_sends_nothing` | Run once: one email (check it). Run again: still one email in `mail.outbox`. |
| `test_moved_due_date_is_reminded_again` | `reminded_on` is an earlier day and `due_date` is today: an email is sent. |
| `test_user_without_email_is_skipped` | A has no email address, B has one: one email, to B. A's to-do keeps `reminded_on = None`, and the result counts 1 skipped. |
| `test_inactive_user_is_skipped` | An inactive user with an email address gets no email; an active user does. |
| `test_shared_todo_reminds_only_owner` | A shares a list with B (both have email addresses). B adds a to-do due today to A's list: one email, to A, with that title. B gets none. |
| `test_failed_send_is_not_marked_and_others_still_sent` | `todos.reminders.send_mail` is replaced so it raises `SMTPException` for A's address only: B still gets the email (B's to-do marked), A's to-do keeps `reminded_on = None`, and the result has one error. |
| `test_failed_user_is_tried_again` | After the failure above, a second run with a working `send_mail` sends A's email. |
| `test_command_prints_counts` | One to-do due on the fixed date: the output contains `Sent 1 reminder (1 to-do).` |
| `test_command_fails_when_a_send_fails` | With a failing `send_mail`, the command raises `CommandError`. |
| `test_command_refuses_console_backend_on_live_server` | With `@override_settings(DEBUG=False, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend")`: `CommandError`, and the to-do's `reminded_on` stays `None`. |
| `test_command_uses_tokyo_date` | `timezone.now` is replaced with 2026-10-09 23:30 UTC, which is 2026-10-10 08:30 in Tokyo. A to-do due 2026-10-10 is reminded; one due 2026-10-09 is not. |

The test dates are fixed, so the tests give the same answer on any computer, at any time of day.

**Show each important test failing first** (rule in `AGENTS.md`). For example: remove
`.exclude(reminded_on=today)` and see `test_second_run_same_day_sends_nothing` fail; remove the
title clean-up and see `test_title_with_line_breaks_stays_on_one_line` fail; remove the console
check and see `test_command_refuses_console_backend_on_live_server` fail.

### 9. Before the commit

- Run `make check`.
- On a laptop: in `/admin/`, give your user an email address. Make a to-do due today, run
  `uv run python manage.py send_reminders`, and see the email printed in the terminal. Run it
  again and see `Sent 0 reminders`.

## What you must set up on the server

The app cannot do these things by itself. The person who runs the server must do them.

1. **An email account that can send by SMTP.** For example a mail service like Postmark,
   Mailgun, or SendGrid, or your email provider's SMTP. Set these environment variables:
   `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT` (usually `587`), `DJANGO_EMAIL_HOST_USER`,
   `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_DEFAULT_FROM_EMAIL` (an address the mail service lets you
   send from). Without `DJANGO_EMAIL_HOST` on a live server, the command stops with an error.
   Note: the mail service sees the to-do titles in the emails.
2. **Email addresses for the users.** In `/admin/`, open each user who wants reminders and fill in
   "Email address".
3. **A daily job that runs the command.** The job must run on the **same machine and database**
   as the website, with the **same environment variables** (cron does not read the website's
   variables by itself), including `DJANGO_DEBUG=False`.
   - On a Linux server with cron, run `crontab -e` and add one line. Cron uses the server's clock.
     Check it with `date`; it is usually UTC. 23:00 UTC is 08:00 the next morning in Tokyo (Japan
     has no summer time, so this never moves):

     ```
     0 23 * * * cd /path/to/anyone-can-build-todo && /full/path/to/uv run --no-dev python manage.py send_reminders >> reminders.log 2>&1
     ```

     Use the full path to `uv` (find it with `which uv`), because cron has a very short `PATH`.
   - On a hosting service, use its "scheduled task" or "cron job" feature with the same command.
     **Warning:** the database is a SQLite file. Some services (for example Render) run a cron job
     on a separate machine that cannot see the website's disk. There, the job would not find the
     to-dos. Such a service needs a shared database (like PostgreSQL), which is its own task.
     Services where the job runs next to the website's files (for example PythonAnywhere's
     "Tasks") work as they are.
4. **Check it once.** Run the command by hand on the server, and look in `reminders.log` the next
   day.

## Open questions

1. **Is "only an admin sets email addresses" enough for now?** It is safe and small, but people
   cannot turn reminders on by themselves. The other choice is a "My email" page with a
   confirmation email, as its own task before this one.
2. **Where will the site run?** The cron setup depends on the hosting service (see the warning
   about SQLite above).
3. **Is 08:00 in Tokyo the right time?** It is only the cron line; the code does not change.

## Review

What changed in this review, and why:

- Owner path changed from `Todo.owner` to `todo_list__owner`: the shared names say the owner is
  `todo.todo_list.owner` after lists; the old query would crash.
- Email addresses now come only from the admin: the accounts plan has no email at all, so the old
  plan would have sent to almost nobody, and "confirmation belongs to accounts" was wrong.
- The command refuses to run on a live server with the console backend: otherwise to-dos were
  marked "reminded" while nothing was sent (silent lost reminders).
- Added `EMAIL_TIMEOUT = 30`: Django's default is no time limit, so a broken mail server could
  hang the cron job.
- Titles are put on one line in the body: a shared-list member could otherwise make the app email
  the owner many lines of fake text.
- Wrote down the known double-send case (crash between send and save, two runs at once) and chose
  "a second email is better than a lost one".
- Tests: every "nothing sent" test now has a to-do that is sent (so an empty `send_reminders`
  cannot pass); command tests now fix the time (they used the real date); added tests for `NULL`
  `reminded_on`, line breaks in titles, a retry after failure, and the console-backend check.
- Recurring: noted that `reminded_on` is not copied to the next copy.
- Removed the open question "where does the owner live" (the shared names decide it).

## Decided by the person (2026-10-09)

The plan is **approved**.

- Only an admin sets email addresses, in /admin/, for now.
- Hosting is decided later, before wave 4. The cron job must run on the same machine as the SQLite file.
