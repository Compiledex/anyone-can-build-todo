# Design doc: the to-do list

| | |
|---|---|
| Type | Technical design document |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Approved (describes the code as built) |
| Date | 2026-10-16 (Tokyo), checked against `main` at `59b7de2` |
| Data | REAL |

> **What this document is.** A design doc explains how a system is built and **why**, before or
> while it is built. Engineers write it so that reviewers can find problems on paper, when they are
> cheap to fix, and so that a new person can learn the system in an hour. Without one, each
> person keeps the big picture in their head, and it is lost when they leave.

This document is a short version of an earlier, longer draft (commit `530218d`, reviewed against
the code). Important choices have their own [ADRs](../adr/README.md). For the job and rules of each
file, read [`AGENTS.md`](../../AGENTS.md): when the two disagree, `AGENTS.md` and the code win. The
plans in [`docs/plans/`](../plans/) are history.

## 1. Summary

A small to-do list, built with **Django** (a Python framework for websites). A person makes an
account, keeps several lists, and adds to-dos. A to-do can have a due date, a priority, tags,
notes, steps and a repeat rule. The owner of a list can share it with other users.

| Question | Answer |
|---|---|
| Who uses it? | The owner, and a few people they share lists with. |
| Where does it run? | Only on the owner's Mac, at <http://127.0.0.1:8000>. Not deployed. |
| Where is the data? | One SQLite file, `db.sqlite3`, next to the code. Not in git. |
| How big is it? | 16 Python files in `todos/`, 22 migrations, 731 tests. |
| Status | All planned features merged (33 plans; PR #1 to #53, of which 51 merged and 2 replaced). |

## 2. Goals and non-goals

**Goals:** simple and correct (every rule has a test); private by default; safe with data (undo,
confirm, daily backup); easy to read (server-rendered HTML, plain-English docstrings); correct for
Norwegian text (æ, ø, å); accessible (contrast, touch targets, named buttons).

**Non-goals** (each decided on purpose; the plan is in brackets):

| Not a goal | Why |
|---|---|
| Deployment to a server | The site runs on the owner's Mac (reminders, 2026-10-10). |
| Real-time updates | Each page is loaded fresh; a member sees a change after a reload. |
| A warning when two people edit the same to-do | The last Save wins (safe-toggles, "Left for the person"). |
| Accent-insensitive search ("e" finds "é") | For Norwegian, "o" and "ø" are different letters (nordic-letters). |
| A light/dark toggle | The app follows the system setting (dark-mode). |
| Email of any kind | Reminders are Mac notifications ([ADR 0008](../adr/0008-mac-notifications-via-osascript.md)). |
| Login rate limit, closed sign-up | Not needed on a local Mac; required before going public (accounts). |

## 3. Users and roles

| Who | Can do |
|---|---|
| **Visitor** (not logged in) | See the landing page at `/`, sign up, log in. Sees no user data. |
| **Owner** of a list | Everything: to-dos, clear done, rename, delete, share, see and remove members. |
| **Member** of a list | Add, edit, mark done, delete, reorder, clear done; leave the list. Cannot rename, delete or share, and does not see other members. |

Each main journey (sign up, add/done/undo/delete/undo-delete, repeat, search/filter/sort,
reorder, share) has a CUJ test in a real browser.

## 4. Architecture

The app is a **monolith**: one Django project, one process, one database. No separate frontend,
no API ([ADR 0001](../adr/0001-server-rendered-django.md)).

| Part | What it is |
|---|---|
| Django 5.2 | Addresses, views, forms, templates, admin, accounts. |
| Server-rendered templates | HTML made on the server. Forms post, the server redirects. |
| `reorder.js` | The only script: drag and drop. The Move buttons do the same without it. |
| SQLite | The database, one file ([ADR 0002](../adr/0002-sqlite-immediate-transactions.md)). |
| WhiteNoise | Serves CSS, JavaScript and pictures. |
| uv | Installs Python and the exact packages from `uv.lock`. |

Two Django **apps** (folders with their own views and templates): `accounts/` (sign up, log in,
log out; Django's own `User`, no models) and `todos/` (everything else). `config/` holds the
settings, the main addresses and the test runner.

### How a request flows

A **request** is what the browser sends; a **response** is what the server sends back.
**Middleware** is code that runs before and after every view.

```
 Browser
   |  GET /lists/3/          or   POST /7/toggle/  (done=1, next=/lists/3/#todo-7)
   v
 Middleware (config/settings.py MIDDLEWARE)
   - sessions, CSRF check (POST only), authentication
   - LoginRequiredMiddleware: no login -> redirect to /accounts/login/
   v
 config/urls.py -> todos/urls.py -> one view in todos/views.py
   |  1. find the object through visible_to / get_visible_todo (else 404)
   |  2. GET: read and render a template
   |     POST: check the form, change the database inside transaction.atomic()
   v
 Models (todos/models.py) --SQL--> SQLite (db.sqlite3)
   |      + Python functions in SQLite: casefold(), "norwegian" collation
   v
 GET:  HTML from todos/templates/ (base.html + the page)
 POST: 302 redirect back to the list (to "next" when it is safe), plus a message
```

Every change is a `POST` that ends with a redirect ("Post/Redirect/Get"), so a reload never sends
a form twice. The one exception is the drag-and-drop save, which answers `204 No Content`.

**Transactions.** SQLite runs with `"transaction_mode": "IMMEDIATE"`, so a second writer waits
instead of failing. Toggle, Delete, Undo-delete, Edit and Move read the row **inside**
`transaction.atomic()` ([ADR 0002](../adr/0002-sqlite-immediate-transactions.md)).

**Python functions inside SQLite.** SQLite's `LOWER()` and `LIKE` know only A to Z. So
`todos/sqlite_functions.py` adds `casefold()` (for search) and the `norwegian` **collation** (a
sort rule: a to z, then æ, ø, å; for "Sort by Title") to every connection. Another tool that
opens `db.sqlite3` lacks them, so the collation is used only for `ORDER BY`, never for a
database rule ([ADR 0007](../adr/0007-list-name-key.md)).

## 5. Data model

| Table | Key fields | Notes |
|---|---|---|
| `User` | Django's own | No custom user model. |
| `TodoList` | `owner`, `name`, `name_key`, `created_at`, `members` | `name_key = casefold(name)`, unique per owner. `members`: users it is shared with. |
| `Todo` | `todo_list`, `title`, `done`, `created_at`, `due_date`, `description`, `priority`, `repeat`, `position` | In exactly one list. Its owner is `todo.todo_list.owner`. |
| `Todo.repeated_from` | one-to-one to `Todo` | On a recurring copy: its original. At most one next copy per to-do. |
| `Todo.copy_fingerprint` | 64 hex characters | Hash of the copy when it was made ([ADR 0006](../adr/0006-recurring-copy-fingerprint.md)). |
| `Todo.reminded_on` | date | Last day in a Mac notification. |
| `Tag` | `owner`, `name` | Unique per owner, lower case. A to-do always uses the **list owner's** tags. |
| `Subtask` ("step") | `todo`, `title`, `done`, `created_at` | No owner of its own. Deleted with its to-do. |

```
   User 1 ──────< owns >────── * TodoList * ──< members >── * User
     |                              |
     | 1                            | 1
     |                              |
     * Tag * ──────< tags >─────── * Todo 1 ────────────── * Subtask
                                    |  ^
                                    |  | repeated_from (one-to-one,
                                    +--+  at most one next copy)
```

(`1` and `*` mean "one" and "many".)

- **`position`** is the manual order. It belongs to the list, so everyone sees the same order.
  `Todo.save()` puts a new to-do last. Ties are broken by `created_at`, then `pk`.
- **`priority`** is a number (1 Low, 2 Medium, 3 High), so `-priority` sorts High first.
- **Migrations** (files that change the tables step by step): 22 in `todos/migrations/`. Data
  migrations (written by hand, they change rows): 0003, 0006, 0016, 0020. Sets that stay together:
  0005-0007, 0015-0016, 0019-0021.

## 6. Access control

The rules are in `AGENTS.md`, "Only my data, plus what is shared with me". In short:

- **Login on every page.** `LoginRequiredMiddleware` sends a visitor to the login page. A view
  opts out with `@login_not_required`. Only `login`, `logout`, `signup` and `home` are open, and a
  test (`test_only_landing_login_and_signup_are_open`) lists them. `home` renders the landing page
  with no database data.
- **Four helpers find every object**: `visible_to`, `get_visible_todo` / `get_visible_subtask`,
  `owner=request.user` (rename, delete, share, remove member) and `members=request.user` (leave).
- **404, not 403**, for anything that is not yours ([ADR 0003](../adr/0003-404-for-other-peoples-data.md)).
  Every view has a test that another user gets 404 and nothing changed.
- **Never trusted from the request:** the list or owner of a new object (set in the view), a
  `next` address (followed only when it is a path on this site, see 7.6), a sort order (only keys
  of `SORT_OPTIONS`).
- **One exception:** `todos/reminders.py` filters by `todo_list__owner`, on purpose (one
  `reminded_on` per to-do). It is not a view.

## 7. Key behaviours

### 7.1 Recurring to-dos

A repeating to-do needs a due date (`Todo.clean()`, in forms only). Done calls
`make_next_copy(today)`, the one place that makes a copy:

- The new date (`todos/recurrence.py`) is the first date in the series **strictly after today**.
  Monthly on the 31st gives the last day of a shorter month, then stays there (accepted).
- The copy keeps `COPIED_FIELDS` (title, notes, priority, repeat), the tags and the steps (not
  done). Never `reminded_on`.
- The one-to-one `repeated_from` means a double click can never make two copies.

Undo on the original removes the copy, **unless** the copy is done, is in another list, has a done
step, or was changed after it was made (the fingerprint differs). Each "kept" case gives a clear
message. Turning on Repeat for a done to-do makes the next copy at once (PR #50).

### 7.2 Delete with Undo

Delete really deletes. A snapshot in the session lets the "Undo" button restore it, with its old
id, for 15 minutes; only the last delete, only for the user who deleted it
([ADR 0005](../adr/0005-delete-undo-session-snapshot.md)).

| Situation | Result |
|---|---|
| Another user, an older delete, after logout | 404 |
| Undo clicked twice | The second finds the row back and does nothing. |
| More than 15 minutes | "Too late to undo: the to-do stays deleted." |
| List gone, or access lost | "Could not undo: you can no longer see the list it was in." |
| The id now belongs to another to-do | "Could not undo." The other to-do is not touched. |

### 7.3 The list page query

`TodoQueryForm` reads `q`, `status` and `sort` from the address. A bad value means the default.

| Feature | Design |
|---|---|
| Search | Title, notes and tag names, `casefold()` on both sides. `#work` finds the tag `work`. |
| Filter | All (default), Not done, Done. |
| Sort | Only `SORT_OPTIONS` keys: created (default), due, priority, title, manual. Every order ends with `created_at`, `pk`. No due date sorts last. |

Every function in `todos/queries.py` starts from the list's to-dos and only makes the set smaller,
never from `Todo.objects`. Tags and steps are loaded with `prefetch_related`, so the number of
queries does not grow with the rows.

### 7.4 Manual order

Only in "Sort by: Manual" with no search and no filter (`can_reorder`), so every to-do is on the
page. Drag and drop and the Move buttons both call `save_order(todo_list, ids)`
(`todos/ordering.py`): the ids must be exactly the list's to-dos, or nothing is saved (400).

### 7.5 Safe toggles

Done/Undo sends the state it **wants** (`done=1` or `done=0`), not "flip". If the to-do already
has that state, nothing happens. Any other value gives 400, after the 404 check. Steps work the
same way (PR #44).

### 7.6 Safe redirects and anchors

After Done, Undo or Delete the browser returns to the same page (same search, filter, sort) at the
right row. The button posts `next` = `back_url` plus an **anchor** (`#todo-7`, which scrolls to
that row). Only database numbers go after `#`. `redirect_back` follows `next` only if it starts
with `/` and Django's `url_has_allowed_host_and_scheme` accepts it. This stops an **open redirect**
(a link on this site that sends a person to another site).

### 7.7 Lists, sharing and steps

- Sign-up makes the first list, "Inbox". Names are unique per owner, ignoring case for every
  letter; names of lists shared with you do not count.
- Delete list and "Clear completed" ask first. Leave asks first. Share by exact username.
- A step (`Subtask`) is one level only and has no owner: whoever can see the to-do may change its
  steps. A step's address holds only the step's number.

## 8. Frontend

- **Design tokens** (named CSS values like `--accent`) are set in **one** file,
  `todos/static/todos/tokens.css`, for light and dark. `site.css` styles the visitor pages,
  `app.css` the app pages. A unit test (`test_tokens_css.py`) checks no other file sets a token.
- **Light and dark** follow `prefers-color-scheme`. Dark mode only redefines tokens.
- **Accessibility:** text contrast at least 4.5 : 1, controls and focus ring 3 : 1; 44px touch
  targets 8px apart under a finger; every button's `aria-label` starts with its visible word and
  names the to-do; after a failed Save, `Error: ` in the title and a focused "Not saved." line;
  motion only for color and a 1px press, off with `prefers-reduced-motion` (PR #45).
- **Page size:** `test_list_page_size.py` keeps a plain row under 1,429 bytes plus 5 %
  (`{% spaceless %}`, one shared form per row; PR #52).
- **Landing page:** real screenshots with invented data (`make landing-shots`), no JavaScript,
  nothing from other sites, no database data. See the [prototype](prototype.md).

## 9. Time and dates

`TIME_ZONE = "Asia/Tokyo"`, `USE_TZ = True`. "Today" is always `timezone.localdate()`; code that
needs it takes it as an argument, so tests choose the day. "Overdue" means before today and not
done ([ADR 0004](../adr/0004-today-in-asia-tokyo.md)).

## 10. Operations

| Command | What it does |
|---|---|
| `make run` | A daily backup (at most one a day, newest 14 kept), then the server at 127.0.0.1:8000. |
| `make backup` | A copy of `db.sqlite3` in `backups/`, kept until deleted by hand. |
| `make reset` | Asks (`yes` only), copies, then makes an empty database. |
| `make check` | Every commit check, the migration check, all tests. |

**Backups** (`todos/backup.py`): SQLite's online backup (whole even while the server writes);
source opened read-only; the final name reserved first, so nothing is overwritten; a temporary
name, `fsync`, then rename; mode 600; only `-daily` files are ever pruned; a failed daily backup
warns and the server starts anyway. `backups/` is not in git.

**Settings** (`config/env.py`): on the laptop no environment variable is needed. With
`DJANGO_DEBUG=False`, a missing or weak `DJANGO_SECRET_KEY` stops the app, and HTTPS-only,
secure cookies and HSTS turn on. No message shows a secret value (PR #36).

**Reminders:** `send_reminders` and a launchd template exist; the owner has not switched them on
([ADR 0008](../adr/0008-mac-notifications-via-osascript.md)).

## 11. Testing and quality

| Layer | Folder | Tool | Count |
|---|---|---|---|
| CUJ | `*/tests/cuj/` | Chromium driven by Playwright | 30 |
| Integration | `*/tests/integration/` | Django's test client | 577 |
| Unit | `*/tests/unit/` | One function, no database | 124 |

Rule: test each rule once, in the lowest layer where a person would notice it (test-pyramid,
PR #1). `config/test_runner.py` stops before running if a test is in the wrong folder or class.
Gates: pre-commit on every commit; `make check` before every commit; GitHub CI (`lint`, `test`)
on every push; a ruleset on `main` requires both green. Reviewers break the code on purpose
(mutation testing) to check that a test fails.

## 12. Known limits

"Gap N" is item N in section 7 of the [data inventory](data-inventory-and-privacy.md).

| Limit | Notes |
|---|---|
| Backups only on the same Mac | The owner copies `backups/` elsewhere by hand. |
| Undo: only the last delete | And on a filtered page, a restored row that does not match the filter is not shown. |
| Last Save wins | No warning on two edits (decided). |
| Search ignores case, not accents | Decided. |
| Custom SQL functions | Other SQLite tools cannot run search or title sort. |
| No threaded test for two requests at once | `IMMEDIATE` and idempotent toggles cover the known cases. |
| Open sign-up, no password-attempt limit | Must change before going public. |
| No "delete my account" page | Only the admin can delete a user ([data inventory](data-inventory-and-privacy.md), gap 1). |
| Expired sessions are never cleared | Their rows (with any undo snapshot) stay in `django_session`; nothing runs `clearsessions` (gap 2). |
| Messages cookie is signed, not encrypted | A to-do title in "Deleted “…”." can be read in the browser's cookies (gap 4). |
| Search words in the server log | A search is a `GET` address, so the development server prints `?q=...` in the terminal (gap 5). |
| Admin log keeps object names | `django_admin_log` keeps the name of each object changed in `/admin/` (for example a to-do's title), also after the object is deleted (gap 6). |
| Hosting | Many hosts lose the SQLite file on deploy; not built for it. |

## 13. Glossary

| Word | Meaning |
|---|---|
| Anchor | The `#todo-7` part of an address; the browser scrolls to that element. |
| Collation | A rule a database uses to sort text. |
| CSRF | Another site posting a form in your name; Django blocks it with a token in each form. |
| CUJ | Critical user journey: an important task tested start to finish in a real browser. |
| Idempotent | Doing it twice has the same effect as doing it once. |
| Migration | A file that changes the database tables step by step. |
| Session | Data the server keeps for one logged-in browser. |
| Transaction | A group of database changes that happen all together or not at all. |

## Related documents

- [ADRs](../adr/README.md): the eight main decisions.
- [Data inventory and privacy](data-inventory-and-privacy.md)
- [Prototype](prototype.md) and [UX test plan and findings](ux-test-plan-and-findings.md)
- [Product requirements](../product/prd.md)
- [Test plan](../process/test-plan.md), [Deployment runbook](../runbooks/deployment.md)
- [`AGENTS.md`](../../AGENTS.md), [`README.md`](../../README.md), [feature plans](../plans/)
