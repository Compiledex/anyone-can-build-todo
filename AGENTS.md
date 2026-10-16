# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language.
Explain in short, plain sentences, and define a technical word the first time you use it. When you
change code, say which file changed and why.

## What this is

The most basic to-do list, in Django. A person can add a to-do, edit it, mark it done (or undo
that), delete it (with an Undo button for 15 minutes), and clear all the done to-dos of a list at
once. A to-do can repeat (daily, weekly or monthly): marking it done makes its next copy, and
"Undo" removes that copy again (unless the copy is already done, is in another list, has a done
step, or was changed after it was made). Turning on Repeat for a to-do that is already done makes its next copy at once.
In the "Manual" order, the to-dos of a list can be put in any order by drag and drop or the Move
buttons; that order belongs to the list, so everyone who sees it sees the same order. Each person
has an account. A person can have several lists (make, rename and delete a list); each to-do is in
exactly one list. The owner of a list can share it with other users by username. Those users are
its *members*: they can see the list and add, edit, mark done and delete its to-dos, clear its done
to-dos, and they can leave it. Only the owner can rename, delete or share the list, see its
members, or remove a member. Members do not see each other. A person sees their own lists plus the
lists shared with them, and nothing else. A visitor who is not logged in sees a landing page at `/`
(what the app does, with screenshots, and the links "Create an account" and "Log in"); it shows no
user data. Once a day, on the person's Mac, launchd (the Mac's scheduler) can run
`send_reminders`, which shows one macOS notification with the person's to-dos due today. The data
is kept in a SQLite database, the file `db.sqlite3`, which is not in git.

## What each file does

Each row says the file's one job and what must stay true. The details of how it behaves are in the
file's docstrings and comments: read them before you change the file.

| File | Its one job |
|---|---|
| `config/settings.py` | Settings for the whole project. Secret key, debug and allowed hosts come from environment variables on a live server (`DEBUG` and `SECRET_KEY` through `config/env.py`), with laptop defaults. SQLite uses `transaction_mode: "IMMEDIATE"`, so two writing requests wait for each other instead of failing. `TIME_ZONE` is `"Asia/Tokyo"` (the person's choice): "today" is the date in Tokyo. |
| `config/env.py` | Pure functions that read the environment (a dict): `read_debug`, `read_secret_key`, `is_strong`. A bad `DJANGO_DEBUG`, or (with debug off) a missing or weak secret key, raises `ImproperlyConfigured` (Django's "the settings are wrong" error, which stops the app). No message ever shows the key or the value of `DJANGO_DEBUG`. |
| `config/urls.py` | `/admin/` to Django's admin, `/accounts/` to `accounts/urls.py`, everything else to `todos/urls.py`. |
| `accounts/` | Sign up, log in, log out, with Django's own `User`, `LoginView`, `LogoutView` and `UserCreationForm`. No models. |
| `accounts/forms.py` | `LoginForm` and `SignupForm`: Django's forms with `NoColon` first and plain help texts. They check and save exactly like Django's own (a test checks the "8" in the password help). |
| `accounts/urls.py`, `accounts/views.py` | The addresses `login`, `logout`, `signup`, and the `signup` view (`GET`, `HEAD`, `POST` only). Sign-up also makes the person's first list, "Inbox". |
| `accounts/templates/registration/` | The login and sign-up pages. They extend `todos/site_base.html`, not `base.html`; each field through `todos/_field.html`; one app screenshot (`_auth_shot.html`) on a wide screen. |
| `accounts/static/accounts/auth.css` | Only places the form and the screenshot. Sets no token. |
| `accounts/tests/helpers.py` | Test helpers for every feature: `TEST_PASSWORD`, `make_user()` (makes no list), `LoggedInTestCase` (alice logged in, bob as the other user, alice's list `todo_list` ("Inbox"), bob's `other_list`, `assertOtherUserGets404`), and `PageParts` / `parse_page(response, parser_class)` to read a page. A page test that needs more makes a subclass. |
| `todos/models.py` | The tables `TodoList`, `Todo`, `Tag` and `Subtask`. `TodoList.objects.visible_to(user)`: the lists the user owns plus the lists shared with them (`members`). A list name is unique per owner, ignoring case for every letter (also æ, ø, å), through `name_key` (`casefold(name)`, set by `save()` and `clean()`) and the constraint `unique_list_name_key_per_owner`: never change a name without `save()` (no `QuerySet.update(name=...)`, no `bulk_create`); a data migration that makes lists sets `name_key` itself. A to-do's owner is `todo.todo_list.owner`. `Todo.save()` puts a **new** to-do last in the manual order (`position`). `make_next_copy(today)` is the one place that makes a recurring copy; `COPIED_FIELDS` is the one list of fields a copy keeps (and so the fields in `fingerprint`); change `FINGERPRINT_VERSION` when the fingerprint changes shape. `Todo.clean()` (a repeating to-do needs a due date) runs only in a form, never in `save()`. `reminded_on` and `copy_fingerprint` are `editable=False`. `set_tags` always uses the list owner's tags, never `request.user`'s. A step (`Subtask`) has no owner and no list: whoever may see its to-do may change its steps. |
| `todos/admin.py` | The admin at `/admin/` for `TodoList` and `Todo` (with its steps). |
| `todos/tags.py` | `parse_tags(text)`: clean tag names (lower case, no `#`, no repeats) and the limits. No database. |
| `todos/recurrence.py` | `next_due_date(due_date, repeat, today)`: the next due date after today. No loop and no Django. |
| `todos/urls.py` | Every address of the app. `/` is the view `home`. A step's addresses hold only the step's number, never a to-do number. |
| `todos/forms.py` | `NoColon` (put first in every form with a label), `TodoForm`, `NoteField`, `TodoListForm` (only the person's **own** lists count for a clashing name), `SubtaskForm` and `ShareForm` (the view sets the to-do or list, never the form), and `TodoQueryForm`, which reads the list page's address (`q`, `status`, `sort`; a bad value means the default, with no error). |
| `todos/queries.py` | Search, filter and sort for the list page. `SORT_OPTIONS` is the one allow-list of orders; every order ends with `created_at`, `pk`; `apply_list_query` always ends with `order_by`. `can_reorder(form)`: manual order, no search, no filter. Every function starts from the `todos` it is given and only makes it smaller; never `Todo.objects` here. |
| `todos/sqlite_functions.py` | The `norwegian` collation (a to z, then æ, ø, å) and the SQL function `casefold()`, added to every SQLite connection by `add_functions` (connected in `TodosConfig.ready()`, `todos/apps.py`). Never open a raw `sqlite3` connection for app queries (it would miss them). The `norwegian` collation is only for `ORDER BY`; never use it for `=`, `UNIQUE`, `DISTINCT` or `GROUP BY`. |
| `todos/ordering.py` | The manual order: `parse_ids` and `save_order(todo_list, ids)`, the one way to write an order (drag and Move both use it). `ids` must be exactly the list's to-dos, or nothing is saved. |
| `todos/views.py` | One function per address. `render_list_page` is the one place that builds the list page. Every view finds what it reads or changes through `visible_to`, `get_visible_todo` or `get_visible_subtask`; only rename, delete, share and remove-member use `owner=request.user`, and `list_leave` uses `members=request.user` (see Rules). Changes are `POST` only. `redirect_back` follows a posted `next` only when it is a path on this site. Toggle, Delete and Undo-delete read and write inside one `transaction.atomic()`. Toggle takes the state it wants (`done` `1` or `0`; anything else is 400, after the 404 check) and does nothing when the to-do already has it. The rest is in the docstrings. |
| `todos/undo.py` | Undo for Delete: `take_snapshot` before the delete, kept in `request.session["undo_delete"]` (only the last delete, only `UNDO_SECONDS`, only for the user who deleted it), and `restore`, which makes the to-do again with its old id. `SNAPSHOT_FIELDS` must list every concrete `Todo` field (a unit test checks it). |
| `todos/context_processors.py` | `undo_delete(request)`: gives every template the delete this session may still undo, for the Undo button in `base.html`. Only reads the session. |
| `todos/templates/base.html` | The frame of the logged-in app pages: the `<head>` (loads `todos/tokens.css`, then `todos/app.css`; never `site.css`, a test checks it), the header, and Django's messages (`role="status"`). Each message is a `<div>` (a `<p>` cannot hold a form); only the message of the delete the session can undo gets the Undo form. It holds no CSS. |
| `todos/static/todos/app.css` | The look of the app pages, built only from the tokens (it sets none): the same button and field classes as `site.css`, plus the to-do row (a CSS grid). Under a finger (`pointer: coarse`) every small control is 44px tall and 8px apart. Forms inside a row's `.actions` and a step's `<li>` are `display: contents`. Motion only for color and a 1px press, off with `prefers-reduced-motion`. |
| `todos/templates/todos/todo_list.html` | The list page (extends `base.html`): the list menu, the owner's or member's controls, the add form, the find bar (search, sort, filter links), the rows, and "Clear completed" (always the whole list). The search and sort forms keep the other choices only through hidden inputs the view builds from cleaned values. When `can_reorder`: `data-reorder-url` and `todos/reorder.js`. |
| `todos/templates/todos/_todo_item.html` | One row (`<li id="todo-<pk>">`), inside `{% spaceless %}` (every place two tags sit side by side is a flex or grid box with gap, never a space). A row's Done/Undo and Delete share one form, and so do a step's: each button names its view with `formaction`; the row's buttons send their own `next` (`back_url` plus an anchor) as their name and value; the form sends `done` (the state Done/Undo asks for). Only database numbers go after the `#`; the `?open=` value is only compared, never printed. Every button's `aria-label` starts with its visible word and names the to-do or step. A missing Move button leaves a `.move-slot`, so the other buttons stay in place. `test_list_page_size.py` keeps a plain row under a byte budget. |
| `todos/static/todos/reorder.js` | Drag and drop, plain JavaScript (the browser's own HTML5 drag and drop), no library. Only the direct rows move, never the steps; it reloads the page when saving fails. |
| `todos/templates/todos/site_base.html` | The frame of the visitor pages (landing, login, sign-up): the `<head>` with `todos/tokens.css`, `todos/site.css`, then the page's own CSS; the header, Django's messages and the footer. The app pages never use it. |
| `todos/templates/todos/_field.html` | One form field: label, input, errors, help. Used by login, sign-up, edit, new list and rename. Give the form `label_suffix = ""` (or `NoColon`) for a label without a colon. |
| `todos/static/todos/tokens.css` | The design tokens of every page, the ONE place that sets them: only `:root` and `:root` in `@media (prefers-color-scheme: dark)`. Every text color has at least 4.5 : 1 contrast, `--control` and the focus ring at least 3 : 1, in both modes. `todos/tests/unit/test_tokens_css.py` checks that no other CSS file declares a token or has `:root`, and that only `site.css` and `app.css` hold the shared rules (only `app.css` styles `.actions`). |
| `todos/static/todos/site.css` | The shared look of the visitor pages, built only from the tokens. `.cta-row` is its row of buttons (not `.actions`, which the app's row uses). |
| `todos/templates/todos/landing.html` | The landing page at `/` for a visitor (view `home`, `@login_not_required`, `@require_safe`). Extends `todos/site_base.html`. It shows **no user data**: the view gives it nothing from the database. No JavaScript and nothing from other sites. Every picture is a `<picture>` with a dark version, `width`, `height` and alt text. |
| `todos/static/todos/landing.css` | Only places the landing page's sections; one column under 768px. |
| `todos/static/todos/landing/` | The landing page's pictures: real screenshots of the app with invented data, `<name>-light.webp` and `<name>-dark.webp`. Retake them only with `make landing-shots` (`scripts/landing_shots.py`, `scripts/landing_seed.py`: a scratch database in a temporary folder, never `db.sqlite3`, a free port, never 8000). If a height changes, update `width`/`height` in `landing.html` (and `_auth_shot.html`). Never draw a fake one. |
| `scripts/landing_shots.py`, `scripts/landing_seed.py` | The tool behind `make landing-shots`. |
| `todos/templates/todos/list_form.html`, `todo_edit.html` | The "New list" / "Rename list" page and the edit page. After a failed Save: `Error: ` before the title and a focused `form-error-summary` line ("Not saved."). The edit page shows the saved title (`saved_title`), never a typed one that was not saved. |
| `todos/templates/todos/list_confirm_delete.html` | "Delete this list and its N to-dos?", with the button that really deletes. |
| `todos/reminders.py` | Mac notifications for to-dos due today, in the user's **own** lists only. `show_notification` runs `/usr/bin/osascript` with a fixed AppleScript, then `--`, then the title and text as `argv`: a list, never a shell. Its error text is never `stderr`. `reminded_on` is set only after `osascript` worked. |
| `todos/management/commands/send_reminders.py` | `python manage.py send_reminders --user <username>`. It prints one line, never a to-do title. |
| `todos/backup.py` | `backup_database`: a whole copy of the SQLite file with SQLite's online backup, also while the app runs; it never changes or makes `source`, never overwrites a file, leaves no file when it fails, and the copy is mode 600. `daily_backup` (for `make run`): at most one `...-daily.sqlite3` a day, then `prune_daily` keeps the newest `DAILY_KEEP` (14), today's always included. `daily_copies` is the only list it deletes from (a regular file whose whole name matches `DAILY_NAME`), so copies from `make backup` and `make reset` are never deleted. Standard library only. |
| `todos/management/commands/backup_db.py` | `python manage.py backup_db` (and `--daily`, only for `make run`) into `BASE_DIR / "backups"`. `--source` and `--folder` are for the tests only; the `Makefile` never uses them. `backups/` is in `.gitignore`. |
| `deploy/macos/com.anyone-can-build-todo.reminders.plist` | The launchd template that runs `send_reminders` at 08:00. The person fills it in and installs it (see `README.md`); the AI never installs it, never runs `launchctl`, and never writes to `~/Library`. |
| `todos/tests/helpers.py` | `FakeOsascriptMixin` (every reminders test uses it, so a test never shows a real notification), `add_todo`, `shown_titles`, `messages_of`, `button_form` (a button with a `formaction` and its form's hidden fields), `count_queries` (raises when there were no queries) and `webp_size`. A test file may keep a one-line wrapper with its own defaults that calls them. |
| `todos/tests/unit/` | Unit tests: one method on its own, no requests, no database. |
| `todos/tests/integration/` | Integration tests: Django's test client, from the address to the database. One file per feature (`test_views.py`, `test_access.py`, `test_sharing.py`, `test_list_page_size.py`, and so on). |
| `todos/tests/cuj/` | CUJ tests (critical user journeys): a real Chromium browser, driven by Playwright. One file per journey (`test_todo_basics.py`, `test_steps_and_repeat.py`, `test_lists_and_people.py`, `test_find_and_order.py`, `test_landing_page.py`, `test_look_and_feel.py`, `test_auth_pages.py`); `browser.py` holds `BrowserTestCase`, `helpers.py` what several files share (`make_user_with_inbox`, `contrast`, `DONE`, the page addresses). A helper module's name never starts with `test`. |
| `config/test_runner.py` | Finds each test's layer from its folder, checks the layer rules, and prints one line per layer. |
| `config/tests/unit/`, `config/tests/integration/` | Tests for the test runner and `config/env.py`, and `manage.py check` in a new process with chosen `DJANGO_*` variables. |
| `todos/migrations/` | Made by Django from `models.py`. Never edit these by hand. One exception: a data migration (one that changes rows, like `0006_default_lists.py`) is meant to be written. |
| `pyproject.toml`, `uv.lock` | The packages and their exact versions. |
| `.pre-commit-config.yaml` | The checks that run on every `git commit`. |
| `Makefile` | Short commands. `make help` lists them. |
| `.github/workflows/check.yml` | CI: on every push and pull request, the jobs `lint` (every commit check, the migration check) and `test` (all three layers), with no `DJANGO_*` variable. A ruleset on `main` requires both to be green, and blocks deleting or force-pushing `main`. |
| `docs/README.md` and the other `docs/` folders | The documentation set: one example of each document type a team writes (PRD, design doc, ADRs, runbooks, postmortem, retrospective, ...), listed by phase in `docs/README.md`. Like the plans, they describe the app when they were written; the code and this file win. Invented content is marked SIMULATED. |
| `docs/plans/` | One plan per feature, written and approved before the code. **History**: they say what was decided and why, not how the code is now. Their Status line says when they were built. `docs/plans/README.md` lists them with their PRs. |
| `CHANGELOG.md` | The release notes, newest first. Add a line for a change a person using the app would notice. |
| `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/` | The templates GitHub puts in a new PR or issue. |

## Commands

This project uses **uv** to install Python and the packages. Run every Python command through
`uv run`, so it uses this project's packages:

- `make setup` — install everything, create the database, turn on the commit checks
- `make run` — first a daily copy of `db.sqlite3` in `backups/` (at most one a day, the newest 14
  daily copies stay; if it fails, a warning, and the server starts anyway), then start the server at
  <http://127.0.0.1:8000>
- `make test` — run every test, then show how many passed in each layer
- `make unit` / `make integration` / `make cuj` — run only one layer
- `make lint` / `make format` — Ruff: find mistakes, and rewrite code in the standard style
- `make check` — every commit check on every file, the migration check, then the tests
  (GitHub runs the same checks and all the tests on every push and pull request; see
  `.github/workflows/check.yml`)
- `make backup` — copy `db.sqlite3` to `backups/db-YYYYMMDD-HHMMSS.sqlite3` (safe while the server runs)
- `make reset` — asks (only `yes` goes on), copies `db.sqlite3` to `backups/`, then deletes it and
  makes an empty database. `CONFIRM=yes` skips the question, never the copy. An AI agent never runs
  it in the person's checkout.
- `make landing-shots` — retake the landing page's screenshots of the app (a scratch database, a free port)

Add a package with `uv add <name>`, never with `pip install`. After changing `models.py`, run
`uv run python manage.py makemigrations` and then `uv run python manage.py migrate`.

## Rules

- **Run `make check` before every commit.** The commit checks also run by themselves. If one fails
  after fixing a file, look at the change, `git add` the file, and commit again.
- **"Today" is `timezone.localdate()`**, the date in `TIME_ZONE` (`Asia/Tokyo`). Never
  `date.today()` or `datetime.now()`, which use the computer's own time zone. Code takes "today"
  as an argument where a test needs to choose the day (like `make_next_copy(today)`,
  `send_reminders(user, today)`, and `is_overdue(today=None)`, which falls back to
  `timezone.localdate()`); the view or command that calls it passes `timezone.localdate()` (a
  template calls `is_overdue` with no argument, so it uses its fallback).
- **Never put a secret in the code.** Passwords, keys and tokens go in environment variables.
- **Use what Django already has** — forms, the admin, `get_object_or_404`, the test client — before
  writing your own.
- **Change data only with `POST`.** A `GET` request only reads.
- **Add or change a test with every change in behavior**, and show the person the test failing
  before the fix and passing after.
- **Put each test in the folder for its layer**: `tests/unit/`, `tests/integration/` or
  `tests/cuj/`. The folder is the layer. Test each rule once, in the lowest layer where a person
  would notice it. A unit test must be a `SimpleTestCase` (no database). A CUJ test must extend
  `BrowserTestCase` from `todos/tests/cuj/browser.py` (it starts the browser). The test runner
  stops if a test breaks these rules; for the CUJ layer it only checks the looser rule that the
  test is a `StaticLiveServerTestCase` (which `BrowserTestCase` is).
- **Never pass text from a request to `order_by`.** Add an entry to `SORT_OPTIONS` in
  `todos/queries.py` instead; the `sort` field of `TodoQueryForm` only accepts its keys.
- **Never build AppleScript from user text.** The script is fixed in `todos/reminders.py`; pass
  the text as `argv`, and always put `--` before those arguments. Never `shell=True`. A test never
  starts the real `osascript`: use `FakeOsascriptMixin` from `todos/tests/helpers.py`.
- **Every page needs a login, by default.** Django's `LoginRequiredMiddleware` (code that runs
  before every view) sends a visitor who is not logged in to the login page. Only mark a view
  `@login_not_required` when a stranger must see it, add its name to
  `test_only_landing_login_and_signup_are_open`, and say why in the pull request. Today the open
  views are `login`, `logout`, `signup` and `home` (`/`, the landing page for a visitor). The
  landing page must never show user data: its view renders it with no database data.
- **Only my data, plus what is shared with me.** A person sees and changes only their own lists
  and the lists shared with them:
  1. A view that reads or changes a list or its to-dos finds the list with
     `get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)`, or the to-do with
     `get_visible_todo(request.user, pk)`. The to-dos of a list are `the_list.todos.all()`. Never
     `Todo.objects.all()` in a view, and never filter to-dos by owner or by
     `Q(todo_list__owner=...) | Q(todo_list__members=...)` (that gives double rows).
  2. Only rename, delete, share and remove-member use
     `get_object_or_404(TodoList, pk=pk, owner=request.user)`: they are for the owner alone.
     Someone else's thing gives 404, like a thing that does not exist (not 403, which would tell
     that it exists). A member gets the same 404 as a stranger. `list_leave` is for members
     alone: it uses `get_object_or_404(TodoList, pk=pk, members=request.user)`, so the owner and
     strangers get 404.
  3. Create: set the owner or the list in the view (`form.save(commit=False)`, then
     `todo.todo_list = the_list`), never from the form.
  4. A new model that belongs to a to-do is reached through a to-do the user can see
     (`get_visible_todo`), or gets its own `owner` field and follows rules 1 to 3.
  5. Every new view gets a test that another user gets 404 (`assertOtherUserGets404` from
     `accounts/tests/helpers.py`), and that the data did not change.

  One exception: `todos/reminders.py` filters to-dos by `todo_list__owner` on purpose:
  `reminded_on` is one date per to-do, so only the owner is reminded. It is not a view. Views
  never do this.
- **`AGENTS.md` describes the code on `main`; the plans in `docs/plans/` are history.** When a
  plan and the code disagree, the code (and this file) win. When you change the code, update
  this file in the same PR; do not edit the body of an old plan, only its Status line.
- **A plan's Status line says when it was built.** The implementer's last commit on a feature
  branch sets the plan's line to `Status: **done** (<date in Tokyo>)`; the PR number is optional
  and may be added later. The orchestrator checks this line before merging.
