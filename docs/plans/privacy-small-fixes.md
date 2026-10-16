# Plan: three small privacy fixes (old sessions, messages, search words in the log)

Status: draft (2026-10-16)

Builds on: **backup-on-run** (`make run` makes a daily copy first, and starts the app also when
the copy fails), **delete-undo** (the undo snapshot in the session), **accounts** (login, logout,
sign-up), **search** (`?q=` in the address), and the docs set (PR #54:
`docs/design/data-inventory-and-privacy.md` section 7, the design doc's known limits, the PRD's
open question 6, `CHANGELOG.md`).

## Words used in this plan

- **Session**: the small store Django keeps on the server for one browser. Here it is a row in the
  database table `django_session` (Django's default `SESSION_ENGINE`). The browser only holds a
  random key, the session cookie.
- **Expired session**: a session row whose `expire_date` has passed (two weeks after it last
  changed, Django's default `SESSION_COOKIE_AGE`). Nobody can use it any more, but the row stays
  until something deletes it.
- **`clearsessions`**: Django's own command, `manage.py clearsessions`. It deletes every expired
  session row, and nothing else. It prints nothing when it works.
- **Message**: Django's short note for the next page, like "Deleted “Buy milk”." (the `messages`
  framework).
- **Message storage**: where Django keeps a message between the request that makes it and the
  page that shows it.
- **Query string**: the part of an address after `?`, for example `?q=milk&sort=title`.
- **Logger, filter**: Python's `logging`. A *logger* is a named channel that code writes lines
  to; a *filter* is a small object that may change (or drop) a line before it is printed.
- **`django.server`**: the logger that Django's development server (`runserver`) uses for its
  request lines, like `[16/Oct/2026 10:00:00] "GET /lists/3/?q=milk HTTP/1.1" 200 5120`.

## What is wrong today

Facts, checked on `main` (commit `2c75b89`) and in Django 5.2.17's own code in `.venv`:

1. **Expired sessions are never deleted** (data inventory, gap 2). Nothing runs `clearsessions`.
   An expired row keeps what it held, also an undo snapshot (a deleted to-do's title, notes, tags
   and steps, `todos/undo.py`) if the person never came back to drop it.
2. **Message text is in a cookie** (gap 4). `config/settings.py` sets no `MESSAGE_STORAGE`, so
   Django uses `FallbackStorage`: the `CookieStorage` first (`storage_classes = (CookieStorage,
   SessionStorage)` in `django/contrib/messages/storage/fallback.py`). The cookie is signed, not
   encrypted: "Deleted “<title>”." can be read in the browser's cookies.
3. **Search words are printed in the terminal** (gap 5). `WSGIRequestHandler.log_message` in
   `django/core/servers/basehttp.py` logs to `django.server` with the format `'"%s" %s %s'` and
   `record.args = (requestline, status, size)`. `requestline` is the whole first line of the
   request, for example `GET /lists/3/?q=secret+words HTTP/1.1`. The login redirect has it too:
   `/accounts/login/?next=/lists/3/%3Fq%3Dsecret`.
   - `django.request` (warnings for 4xx, errors for 5xx) logs `request.path` only, never the query
     string (`log_response` in `django/utils/log.py`, and its callers in
     `django/core/handlers/exception.py`, `base.py`, `middleware/csrf.py`). So it needs no change.
   - `record.request` on a `django.server` line is the socket, not an `HttpRequest`; the
     formatter (`ServerFormatter`) does not print it.

## Goal

1. `make run` deletes expired sessions before it starts the server, so old sessions (and any old
   undo snapshot in them) do not stay in `db.sqlite3` forever.
2. Message text is kept in the session on the server, never in a cookie.
3. The development server's request lines show the method, the path and the status code, but no
   query string, so search words are not printed in the terminal.

Nothing changes in what a person sees in the app.

## Decisions

### 1. `make run` runs `clearsessions`, after the backup, before the server

```make
# A daily copy of db.sqlite3 first (at most one a day, the newest 14 are kept;
# see todos/backup.py). Then expired sessions are deleted (Django's own
# clearsessions). If either fails, say so and start the app anyway.
run:
	@uv run python manage.py backup_db --daily || echo "Warning: the daily backup did not work (see the message above). The app starts anyway. Run make backup to try again."
	@uv run python manage.py clearsessions || echo "Warning: could not remove expired sessions (see the message above). The app starts anyway."
	uv run python manage.py runserver
```

- **Django's own command** (AGENTS.md: use what Django already has). It deletes only rows with
  `expire_date` before now (`SessionStore.clear_expired()` in
  `django/contrib/sessions/backends/db.py`). A live session, so a logged-in browser, is never
  touched. No new Python code.
- **After the backup.** The same rule as `make reset`: first the copy, then a change. If a
  delete ever went wrong, the copy of the same minute still has the rows. The cost: the daily copy
  of that day still holds the sessions that expired since the last `make run` (they leave the
  copies after 14 days, like every daily copy). The next copy no longer has them. See open
  question 1.
- **It runs also when the backup failed.** The two steps are independent: an expired session has
  no use to anyone (it cannot log in, and its undo snapshot is older than 15 minutes, so it can
  never be undone). Skipping it on a day without a copy would keep useless private text longer.
  (backup-on-run's rule "nothing is pruned on a failed day" is about *backups*, which are useful
  data.) See open question 2.
- **A failed `clearsessions` prints a warning and the app starts anyway**, like the backup: a
  locked or broken database is not fixed by refusing to start. The text is different from the
  backup warning, so the person knows which step failed.
- **No database yet** (before `make setup`): today `runserver` already makes an empty
  `db.sqlite3`. `clearsessions` would fail with "no such table: django_session", print the
  warning, and the app starts as before. `make setup` runs `migrate` first, so this only happens
  when someone skips setup.
- **The tests' database**: the tests never run `make run` for real, and `clearsessions` is not in
  `make check` or `make test`. The `Makefile` test uses a fake `uv` (below). Nothing changes for
  `make check`.
- `make help`: `make run  copy db.sqlite3 to backups/ (once a day, keeps 14), remove expired
  sessions, then start the server at http://127.0.0.1:8000`.

### 2. Messages in the session: `MESSAGE_STORAGE`

```python
# Messages (like "Deleted “Buy milk”.") are kept in the session on the server,
# never in a cookie, so a to-do title is never readable in the browser.
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
```

What this changes, checked in Django's code and with a throw-away prototype test in the planner's
worktree (deleted again):

- `SessionStorage` needs `SessionMiddleware` **before** `MessageMiddleware` in `MIDDLEWARE`
  (else `ImproperlyConfigured`). It is (`config/settings.py`). Every page with a message already
  has a session (the person is logged in), except the pages below.
- **Delete, then Undo**: the delete answers 302 with only the `sessionid` cookie (no `messages`
  cookie); the session holds `_messages` next to `undo_delete`; the next page shows "Deleted
  “…”." and removes `_messages` from the session. (Prototype: confirmed.)
- **Login** calls `request.session.cycle_key()` (`django.contrib.auth.login`): a new key, the
  same data. A message waiting in the session before login is still there after it. Only when
  *another* user was logged in in that session does `login()` flush it. (Prototype: confirmed.)
- **Logout** flushes the session (`request.session.flush()`): a message that was waiting and not
  yet shown is gone. That is better for privacy than today (today an unread cookie message stays
  in the browser after logout).
- **A message added in the same request as `logout()`** (before or after the call) is still
  shown: it waits in memory (`_queued_messages`) until the response, and then `MessageMiddleware`
  writes it into the **new**, empty session, which `SessionMiddleware` saves (it comes after
  `MessageMiddleware` on the way out). (Prototype: both orders confirmed.) delete-account needs
  this.
- **Login, logout and sign-up show no message today** (`accounts/views.py`, `accounts/urls.py`:
  no `messages.*` call; Django's `LoginView` and `LogoutView` add none). So no flow loses one.
  The login page can show a message (`site_base.html`), and its test changes (Tests).
- **A message for a visitor who is not logged in** now makes a session row (today: a cookie).
  No such message exists today; delete-account will add one ("Your account was deleted."). The
  row is removed on logout or by `clearsessions` after it expires; once the message is shown, the
  session is empty and Django deletes the session cookie.
- **An old `messages` cookie** in a browser from before this change is ignored (no code reads it).
  `CookieStorage` set it without `max_age`, so the browser drops it when it closes, and it was
  already removed after its message was shown. No code to delete it.
- The admin's own messages ("The to-do “…” was added successfully.") also move to the session.

### 3. A logging filter that drops the query string: `config/logging_filters.py`

```python
"""Filters for Python logging, used by LOGGING in config/settings.py."""

import logging
import re

# "?" and everything after it up to a space or a quote: the query string of an
# address in a request line, for example "?q=milk&sort=title".
QUERY_STRING = re.compile(r"\?[^\s'\"]*")


class DropQueryString(logging.Filter):
    """Removes the query string from every text argument of a log line.

    For the development server's request lines (the `django.server` logger):
    "GET /lists/3/?q=milk HTTP/1.1" becomes "GET /lists/3/ HTTP/1.1". The
    method, the path, the status code and the size stay. It never drops a line.
    """

    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(
                QUERY_STRING.sub("", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True
```

- **It changes `record.args`, never `record.msg`**: the format `'"%s" %s %s'` stays, so a `%`
  in an address cannot break the line. The status code is `args[1]` (a string of digits, no `?`)
  and `record.status_code` (an int): both stay, so the colors and the level stay.
- **Every text argument**, not only the first: Django's other `django.server` line,
  `log_error("code %d, message %s", 400, "Bad request syntax ('GET /?q=... HTTP/1.1')")`, has the
  request line inside the second argument.
- **It stops at a space or a quote**, so ` HTTP/1.1` and the `')` of that error stay. A browser
  never sends a raw space in an address (it sends `+` or `%20`), so a real search is always
  removed whole.
- **It never returns `False`**: no line is hidden, only shortened.
- **Only `django.server`**: the filter sits on that logger, so it runs for every record logged
  there, whatever handler prints it (also a test's `assertLogs`). `django.request` needs none
  (it logs `request.path` only, see "What is wrong today").
- **It only affects `runserver`**: the tests' live server (`LiveServerTestCase`) uses
  `QuietWSGIRequestHandler`, which logs nothing; `make landing-shots` throws the server's output
  away.

`LOGGING` in `config/settings.py`:

```python
# The development server's request lines (logger django.server) are printed
# without the query string, so search words (?q=...) never show in the
# terminal. The rest is Django's own default logging (django.utils.log).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "drop_query_string": {"()": "config.logging_filters.DropQueryString"},
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
    },
    "loggers": {
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
            "filters": ["drop_query_string"],
        },
    },
}
```

- Django first applies its `DEFAULT_LOGGING`, then this. This dict repeats Django's own
  formatter, handler and logger for `django.server` (a `dictConfig` can only name handlers it
  defines itself), and adds the filter. `disable_existing_loggers: False` keeps the `django`
  logger and its handlers as they are. (Prototype with Django 5.2.17: the `django` logger still
  has its console and mail handlers, and the request lines come out as
  `[16/Oct/2026 19:45:40] "GET /lists/3/ HTTP/1.1" 200 512`.)
- The filter's module is in `config/` (the project's settings), not in `todos/`: it is about the
  server, not the app.

## Security

- No new view, URL or form. No change in who may see or change what.
- `clearsessions` deletes only expired rows; a logged-in browser keeps its session. It takes no
  user text.
- With `SessionStorage`, message text stays on the server, in the person's own session row. Only
  the session key (a random value, `HttpOnly`) is in the browser. A message can never be shown to
  another browser: each session is its own.
- The filter removes data from a log line; it adds none. The path stays, and a path holds only
  numbers chosen by the app (`/lists/3/`, `/todos/7/edit/`), never typed text.
- CSRF, `POST`-only changes and the `next` checks do not change.

## Data and migrations

No model, no migration. `clearsessions` deletes expired rows in `django_session` (on the person's
Mac, with `make run`, after the daily copy). Going back: revert the commit. Deleted expired rows
are not needed by anyone; the daily copy of that morning still has them.

## Working next to

Wave A: **split-browser-tests**, **readme-to-runbooks**, **privacy-small-fixes (this)** and
**admin-log-without-names** are built at the same time; **delete-account** is built in parallel
too. **Merge order: split-browser-tests → readme-to-runbooks → privacy-small-fixes (this) →
admin-log-without-names → delete-account.**

- **readme-to-runbooks** merges first and moves README sections into `docs/runbooks/`. This plan
  changes the "Back up your data" paragraph about `make run` in `README.md`, which stays in the
  README. Rebase after it merges; if the paragraph moved, change it where it is now.
- **admin-log-without-names** merges after this. Both close gaps in
  `docs/design/data-inventory-and-privacy.md` section 7, remove rows from the design doc's known
  limits, and change the PRD's open question 6, and both add to `CHANGELOG.md`. This plan
  rewrites open question 6 to ask only about the admin log (gap 6); admin-log-without-names then
  removes it. Both touch `AGENTS.md` (different rows: this one `config/settings.py`, the new
  `config/logging_filters.py` row and Commands; that one the admin rows).
- **delete-account** merges last. After this plan, its "account deleted" message after logout is
  kept in the new session (decision 2, confirmed with a prototype). Its tests must check that the
  message shows on `/` after the delete. Its message for a visitor makes a session row, which
  `clearsessions` removes after it expires.
- **split-browser-tests**: no shared files (this plan adds no browser test).
- `Makefile`: only this plan changes it in this wave.

## Not part of this task

- A shorter `SESSION_COOKIE_AGE`, or ending the session when the browser closes.
- Running `clearsessions` when the app is not started (a launchd job).
- Removing expired sessions from backups that already exist.
- Erasing deleted bytes inside the SQLite file (`VACUUM`, `PRAGMA secure_delete`): deleted rows
  can stay in free pages of `db.sqlite3` until SQLite reuses them. A separate idea (see
  admin-log-without-names, open question 3).
- Changing a deployed server's logging (there is no server; the deployment runbook's "if it ever
  runs on a server" part already says logs must be checked).
- Deleting an old `messages` cookie from browsers.

## Changes to files

| File | Change |
|---|---|
| `Makefile` | `run` also runs `clearsessions` (after the backup, before the server; its own warning); the `help` line; the comment above `run`. |
| `config/settings.py` | `MESSAGE_STORAGE = "...SessionStorage"`; `LOGGING` with `DropQueryString` on `django.server`; comments. |
| `config/logging_filters.py` (new) | `QUERY_STRING`, `DropQueryString`. |
| `config/tests/unit/test_logging_filters.py` (new) | `DropQueryStringTests`. |
| `config/tests/integration/test_server_log.py` (new) | `ServerLogTests`. |
| `todos/tests/integration/test_backup.py` | The fake `uv` knows `clearsessions` (`FAKE_CLEAR_EXIT`); `FakeUvTestCase.run_make(clear_fails=...)`; `MakeRunTests` checks the order and the new warning. |
| `todos/tests/integration/test_privacy.py` (new) | `ExpiredSessionsTests`, `MessagesInSessionTests`. |
| `accounts/tests/integration/test_auth_pages.py` | `MessagesTests.test_a_message_shows_on_the_login_page` puts its message in the session (not a cookie); a new test that a message survives login. |
| `README.md` | "Back up your data" (the `make run` paragraph): it also removes expired sessions. |
| `docs/runbooks/deployment.md` | Section 2 "Start": `make run` also runs `clearsessions`. |
| `docs/runbooks/on-call-and-incidents.md` | One row in the error table: "Warning: could not remove expired sessions" (cause: database locked or missing tables; fix: `make setup` / look at the message above; the app still works). |
| `docs/design/data-inventory-and-privacy.md` | Sections 1, 3, 4 and 5: the messages row (session, not cookie), the expired sessions row (`make run` removes them), the terminal row and the "small leak" (no query string). Section 7: gaps 2, 4 and 5 say **Closed** (keep the numbers, so "gap N" links stay right). |
| `docs/design/design-doc.md` | Section 12: remove the rows for gaps 2, 4 and 5; the `make run` row in the commands table. |
| `docs/product/prd.md` | Open question 6 asks only about the admin log (gap 6). |
| `CHANGELOG.md` | `## [Unreleased]`: under **Security**, the three fixes in plain words. |
| `AGENTS.md` | `config/settings.py` row (session messages, `LOGGING`); new `config/logging_filters.py` row; Commands: `make run` (also removes expired sessions). |
| `docs/plans/README.md` | A row for this plan when it is built. |
| `docs/plans/privacy-small-fixes.md` | Status line when built. |

## Steps

1. **Tests first** (below). Run `make unit` and `make integration`: the new ones fail (the
   messages test sees a `messages` cookie; the log line has `?q=`; `MakeRunTests` finds no
   `clearsessions`). Show the person.
2. `config/logging_filters.py`, then `LOGGING` and `MESSAGE_STORAGE` in `config/settings.py`.
3. The `Makefile`.
4. By hand, **in the worktree only** (its own `db.sqlite3`, never the person's file):
   `uv run python manage.py migrate`, then `uv run python manage.py clearsessions` (prints
   nothing, exits 0). **Never run `make run` or `runserver` in the main checkout, never port
   8000**: the person's server runs there. If a look at the real log line is wanted, use
   `uv run python manage.py runserver 127.0.0.1:<free port>` in the worktree, open
   `/?q=test` once, check the line, stop it.
5. The docs (README, runbooks, data inventory, design doc, PRD, CHANGELOG) and `AGENTS.md`.
6. `make check`. Commit. Last commit: Status `**done** (<date in Tokyo>)` and the
   `docs/plans/README.md` row.

## Tests

### Unit: `config/tests/unit/test_logging_filters.py` (`SimpleTestCase`)

`DropQueryStringTests`. Each test makes a `logging.LogRecord` by hand with Django's request-line
format `'"%s" %s %s'`, runs `DropQueryString().filter(record)`, and checks
`record.getMessage()`.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_search_words_are_removed` | `GET /lists/3/?q=secret+words&sort=title HTTP/1.1`, `200`, `512` gives `"GET /lists/3/ HTTP/1.1" 200 512`. | No filter, or only `q=` removed. |
| `test_line_without_query_is_unchanged` | `GET /lists/3/ HTTP/1.1` stays exactly the same (the "nothing happens" case), and so does a path with `%` like `/static/a%20b.css`. | A filter that cuts too much, or formats `msg` itself. |
| `test_login_next_is_removed` | `GET /accounts/login/?next=/lists/3/%3Fq%3Dsecret HTTP/1.1` gives `GET /accounts/login/ HTTP/1.1`. | Removing only `q=`. |
| `test_status_and_size_stay` | `args[1]` and `args[2]` (`"404"`, `"10"`) are unchanged, and `record.status_code` too. | Changing the wrong argument. |
| `test_error_line_in_a_later_argument` | `"code %d, message %s"` with `(400, "Bad request syntax ('GET /?q=secret HTTP/1.1')")` gives `... Bad request syntax ('GET / HTTP/1.1')`; the int `400` is still an int. | Only `args[0]`, or `str()` on every argument. |
| `test_never_drops_a_line` | `filter()` returns `True` for every case above, and for a record with no args and one with a dict as args (left as it is). | Returning the cleaned text, or `False`. |

### Integration: `config/tests/integration/test_server_log.py` (`SimpleTestCase`)

`ServerLogTests` uses the logging that `LOGGING` set up (the test runner applies the settings).
It replaces the stream of the `django.server` handler with an `io.StringIO`
(`handler.setStream(...)`, put back with `addCleanup`), makes a
`WSGIRequestHandler.__new__(WSGIRequestHandler)` with `requestline` and `request = None` (no
socket, no server, no port), and calls Django's own `log_request(code, size)`.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_request_line_has_no_query_string` | `GET /lists/3/?q=secret HTTP/1.1` with 200: the printed line ends with `"GET /lists/3/ HTTP/1.1" 200 512` and has no `secret`. | The filter not wired in `LOGGING`, or on the wrong logger. |
| `test_error_status_still_shows` | `GET /nope/?q=x HTTP/1.1` with 404: the line has `/nope/` and `404`, not `q=x`. | Hiding the status, or dropping 4xx lines. |
| `test_django_logger_is_unchanged` | `logging.getLogger("django")` still has a `StreamHandler` and an `AdminEmailHandler` (Django's defaults). | A `LOGGING` that replaces Django's defaults. |

### Integration: `todos/tests/integration/test_privacy.py`

`MessagesInSessionTests` (`LoggedInTestCase`):

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_delete_message_is_not_in_a_cookie` | alice deletes "Secret milk": the 302 has no `messages` cookie (`settings.MESSAGE_COOKIE_NAME not in response.cookies`), and `self.client.session["_messages"]` has the title. Fails on `main`. | The cookie storage (today). |
| `test_message_shows_once_then_leaves_the_session` | The next list page shows "Deleted “Secret milk”."; after it, `_messages` is not in the session; the page after that does not show it. | A message that stays, or is never shown. |
| `test_undo_message_still_shows` | Delete, then Undo: the page shows "Restored “Secret milk”." (the "something happens" case of a flow that already worked). | Messages lost between two redirects. |

`ExpiredSessionsTests` (`TestCase`):

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_clearsessions_removes_expired_and_keeps_live` | Two `Session` rows (made with `SessionStore`): one with an undo snapshot and `expire_date` a day ago, one live. `call_command("clearsessions")`: the expired row is gone, the live one is there. | A session engine without `clear_expired` (for example the signed-cookie engine), which would make `make run` warn every day. |

### Integration: `accounts/tests/integration/test_auth_pages.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `MessagesTests.test_a_message_shows_on_the_login_page` (changed) | The message is put in the client's session (`request.session = self.client.session`, `request._messages = SessionStorage(request)`, `messages.info(...)`, `request._messages.update(HttpResponse())`, `request.session.save()`), not in a cookie; the login page shows it in the one message box, above the title (as today). | The old way (a `CookieStorage` cookie) would no longer show. |
| `MessagesTests.test_a_message_survives_login` (new) | A message in a visitor's session; alice logs in (POST to the login page, follow): the first page after login shows it. | A flush instead of `cycle_key` (a message lost at login). |

### Integration: `todos/tests/integration/test_backup.py` (`MakeRunTests`, the real `Makefile` with a fake `uv`)

The fake `uv` gets one more case: `*clearsessions*) exit "${FAKE_CLEAR_EXIT:-0}";;`.
`FakeUvTestCase.run_make` gets `clear_fails=False` (sets `FAKE_CLEAR_EXIT=1`). No server starts,
no port is used.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_run_backs_up_then_starts` (changed) | The log has `backup_db --daily`, then `clearsessions`, then `runserver`, in this order; exit 0; no "Warning". | No `clearsessions`, or before the backup. |
| `test_failed_backup_still_starts_with_a_warning` (changed) | With a failed backup: `clearsessions` and `runserver` still run, the backup warning is printed. | Stopping after a failed backup. |
| `test_failed_clearsessions_still_starts_with_a_warning` (new) | With `clear_fails=True`: `runserver` runs, the output has "Warning: could not remove expired sessions", not the backup warning; exit 0. | Stopping the app, no warning, or the wrong warning. |
| `test_backup_target_has_no_daily_flag` | Unchanged: `make backup` runs no `clearsessions`. | `clearsessions` added to the wrong target. |

No CUJ test: a person sees no change, and each rule is tested in the lowest layer where it shows.

## Open questions

1. **`clearsessions` before or after the daily backup?** After, **recommended**: first the copy,
   then the change (like `make reset`). The cost is small: that morning's copy still holds the
   sessions that expired since the last run, for 14 days. Before would keep them out of every new
   copy, but would change the database before it is copied.
2. **Run `clearsessions` when the backup failed?** Yes, **recommended**: an expired session is of
   no use, and keeping it is the privacy problem. The alternative (skip it on a failed day, like
   pruning) keeps private text longer when the backup keeps failing.
3. **What the log line shows instead of the query string.** Nothing, **recommended**:
   `"GET /lists/3/ HTTP/1.1" 200`. The alternative, a marker like `/lists/3/?…`, tells that there
   was a search or a filter, but no one has needed that.

## Review

Verification by the planner (2026-10-16), against `main` (`2c75b89`) and Django 5.2.17 in
`.venv`:

- Confirmed: `MESSAGE_STORAGE` is not set (so `FallbackStorage`, cookie first); `SessionMiddleware`
  comes before `MessageMiddleware`; no `SESSION_ENGINE` (database sessions).
- Confirmed: the app adds no message in login, logout or sign-up; `MessagesTests` in
  `accounts/tests/integration/test_auth_pages.py` plants a `CookieStorage` cookie and must change.
- Confirmed with a throw-away prototype test (session storage switched on with
  `override_settings`, then deleted): a delete gives no `messages` cookie and puts `_messages` in
  the session; the next page removes it; a message survives `login()`; a message added before or
  after `logout()` in the same request shows on the next page.
- Confirmed with a prototype of `DropQueryString` and this `LOGGING` (Django 5.2.17): the request
  line is printed without the query string, 404 lines keep their status, and the `django` logger
  keeps Django's default handlers.
- Confirmed: `django.request` logs `request.path` only; `LiveServerTestCase` uses
  `QuietWSGIRequestHandler`; `scripts/landing_shots.py` sends the server's stderr to
  `/dev/null`.

Not reviewed yet by an independent plan reviewer.

## Decided by the person

Not yet.
