# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language.
Explain in short, plain sentences, and define a technical word the first time you use it. When you
change code, say which file changed and why.

## What this is

The most basic to-do list, in Django. A person can add a to-do, mark it done (or undo that), and
delete it. There are no accounts: everyone who opens the site sees the same list. The data is kept
in a SQLite database, the file `db.sqlite3`, which is not in git.

## What each file does

| File | Its one job |
|---|---|
| `config/settings.py` | Settings for the whole project. The secret key, debug and allowed hosts come from environment variables on a live server, with defaults for a laptop. |
| `config/urls.py` | Sends `/admin/` to Django's admin, and everything else to `todos/urls.py`. |
| `todos/models.py` | The `Todo` table: `title`, `done`, `created_at`. |
| `todos/urls.py` | The four addresses: the list, add, toggle, delete. |
| `todos/forms.py` | `TodoForm`, the Django form for a to-do. It checks the title. |
| `todos/views.py` | One function per address. Add, toggle and delete accept `POST` only, then send the browser back to the list. An invalid add shows the page again with the error. |
| `todos/templates/base.html` | The shared page frame: the `<head>`, all the CSS (the colors are CSS variables, with dark values that follow the system's light or dark mode), and the messages. |
| `todos/templates/todos/todo_list.html` | The list page, which extends `base.html`: the errors, the add form and the list. |
| `todos/templates/todos/_todo_item.html` | One row of the list (one `<li>`). |
| `todos/tests/unit/` | Unit tests: one method on its own, no requests, no database. |
| `todos/tests/integration/` | Integration tests: Django's test client, from the address to the database. |
| `todos/tests/cuj/` | CUJ tests (critical user journeys): a real Chromium browser, driven by Playwright. |
| `config/test_runner.py` | Finds each test's layer from its folder, checks the layer rules, and prints one line per layer after a run. |
| `config/tests/unit/` | The tests for the test runner. |
| `todos/migrations/` | Made by Django from `models.py`. Never edit these by hand. |
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
