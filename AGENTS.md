# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language.
Explain in short, plain sentences, and define a technical word the first time you use it. When you
change code, say which file changed and why.

## What this is

The most basic to-do list, in Django. A person can add a to-do, mark it done (or undo that), and
delete it. Each person has an account and sees only their own lists and to-dos. A person can have
several lists (make, rename and delete a list); each to-do is in exactly one list. The data is kept
in a SQLite database, the file `db.sqlite3`, which is not in git.

## What each file does

| File | Its one job |
|---|---|
| `config/settings.py` | Settings for the whole project. The secret key, debug and allowed hosts come from environment variables on a live server, with defaults for a laptop. |
| `config/urls.py` | Sends `/admin/` to Django's admin, `/accounts/` to `accounts/urls.py`, and everything else to `todos/urls.py`. |
| `accounts/` | The accounts app: sign up, log in, log out. It uses Django's own `User`, `LoginView`, `LogoutView` and `UserCreationForm`. It has no models. |
| `accounts/urls.py`, `accounts/views.py` | The three addresses (`login`, `logout`, `signup`), and the `signup` view. Sign-up also makes the person's first list, "Inbox". |
| `accounts/templates/registration/` | The login and sign-up pages. They extend `base.html`. |
| `accounts/tests/helpers.py` | Test helpers for every feature: `TEST_PASSWORD`, `make_user()`, and `LoggedInTestCase` (logged in as alice, with bob as the other user, alice's list `todo_list` ("Inbox"), bob's list `other_list`, and `assertOtherUserGets404`). `make_user()` makes no list. |
| `todos/models.py` | The `TodoList` table: `owner` (the user it belongs to), `name` (unique per person, ignoring case), `created_at`. The `Todo` table: `todo_list` (the list it is in), `title`, `done`, `created_at`. A to-do's owner is `todo.todo_list.owner`. |
| `todos/urls.py` | The addresses: `/` (only sends the browser to the oldest list, or to "New list"), `/lists/new/`, `/lists/<pk>/` (a list page), `/lists/<pk>/add/`, `/lists/<pk>/rename/`, `/lists/<pk>/delete/`, and `/<pk>/toggle/` and `/<pk>/delete/` for a to-do. |
| `todos/forms.py` | `TodoForm`, the Django form for a to-do (it checks the title), and `TodoListForm`, for a list's name (it refuses a name the person already has). |
| `todos/views.py` | One function per address. `render_list_page` is the one place that builds the list page. Every view finds a list with `owner=request.user`, or a to-do with `todo_list__owner=request.user`, so another person's things give 404. Changes are `POST` only; then the browser goes back to the list. An invalid add shows the list page again with the error. |
| `todos/templates/base.html` | The shared page frame: the `<head>`, all the CSS (the colors are CSS variables, with dark values that follow the system's light or dark mode), the header ("Logged in as ..." and "Log out"), and the messages. |
| `todos/templates/todos/todo_list.html` | The list page, which extends `base.html`: the menu of the person's lists, the list's name with "Rename" and "Delete list", the errors, the add form and the to-dos. |
| `todos/templates/todos/list_form.html` | The "New list" and "Rename list" page: the name field and its errors. |
| `todos/templates/todos/list_confirm_delete.html` | "Delete this list and its N to-dos?", with the button that really deletes. |
| `todos/templates/todos/_todo_item.html` | One row of the list (one `<li>`). |
| `todos/tests/unit/` | Unit tests: one method on its own, no requests, no database. |
| `todos/tests/integration/` | Integration tests: Django's test client, from the address to the database. |
| `todos/tests/cuj/` | CUJ tests (critical user journeys): a real Chromium browser, driven by Playwright. |
| `config/test_runner.py` | Finds each test's layer from its folder, checks the layer rules, and prints one line per layer after a run. |
| `config/tests/unit/` | The tests for the test runner. |
| `todos/migrations/` | Made by Django from `models.py`. Never edit these by hand. One exception: a data migration (one that changes rows, like `0003_give_old_todos_an_owner.py` and `0006_default_lists.py`) is meant to be written. |
| `pyproject.toml`, `uv.lock` | The packages this project uses, and their exact versions. |
| `.pre-commit-config.yaml` | The checks that run on every `git commit`. |
| `Makefile` | Short commands. `make help` lists them. |

## Commands

This project uses **uv** to install Python and the packages. Run every Python command through
`uv run`, so it uses this project's packages:

- `make setup` — install everything, create the database, turn on the commit checks
- `make run` — start the server at <http://127.0.0.1:8000>
- `make test` — run every test, then show how many passed in each layer
- `make unit` / `make integration` / `make cuj` — run only one layer
- `make lint` / `make format` — Ruff: find mistakes, and rewrite code in the standard style
- `make check` — every commit check on every file, the migration check, then the tests

Add a package with `uv add <name>`, never with `pip install`. After changing `models.py`, run
`uv run python manage.py makemigrations` and then `uv run python manage.py migrate`.

## Rules

- **Run `make check` before every commit.** The commit checks also run by themselves. If one fails
  after fixing a file, look at the change, `git add` the file, and commit again.
- **Never put a secret in the code.** Passwords, keys and tokens go in environment variables.
- **Use what Django already has** — forms, the admin, `get_object_or_404`, the test client — before
  writing your own.
- **Change data only with `POST`.** A `GET` request only reads.
- **Add or change a test with every change in behavior**, and show the person the test failing
  before the fix and passing after.
- **Put each test in the folder for its layer**: `tests/unit/`, `tests/integration/` or
  `tests/cuj/`. The folder is the layer. Test each rule once, in the lowest layer where a person
  would notice it. A unit test must be a `SimpleTestCase` (no database). A CUJ test must extend
  `BrowserTestCase` from `todos/tests/cuj/browser.py`. The test runner stops if a test breaks
  these rules.
- **Every page needs a login, by default.** Django's `LoginRequiredMiddleware` (code that runs
  before every view) sends a visitor who is not logged in to the login page. Only mark a view
  `@login_not_required` when a stranger must see it, add its name to
  `test_only_login_and_signup_are_open`, and say why in the pull request.
- **Only my data.** A person sees and changes only their own things:
  1. A list starts from the user: `Todo.objects.filter(owner=request.user)`. Never
     `Todo.objects.all()` in a view.
  2. One thing by its number: `get_object_or_404(Todo, pk=pk, owner=request.user)`. Someone
     else's thing then gives 404, like a thing that does not exist (not 403, which would tell
     that it exists).
  3. Create: set the owner in the view (`form.save(commit=False)`, then `todo.owner =
     request.user`), never from the form.
  4. A new model that belongs to a to-do is reached through a to-do the user owns, or gets its own
     `owner` field and follows rules 1 to 3.
  5. Every new view gets a test that another user gets 404 (`assertOtherUserGets404` from
     `accounts/tests/helpers.py`), and that the data did not change.
