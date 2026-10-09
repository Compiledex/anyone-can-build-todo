# To-do list

The most basic to-do list in Django: add a to-do, edit it, mark it done, delete it, or clear all the
done ones at once. Keep your to-dos in
several lists, like "Work" and "Home".

The pages follow your computer's or phone's light or dark mode.

## Run it on your laptop

**1. Install uv, once.** uv installs Python and this project's packages for you.

Mac:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close the terminal and open a new one, then check with `uv --version`.

**2. Get the code.**

```bash
git clone https://github.com/kreativitea/anyone-can-build-todo.git
cd anyone-can-build-todo
```

**3. Install the packages.** The first time, uv also downloads the right version of Python.

```bash
uv sync
```

**4. Create the database.** This makes a file called `db.sqlite3`.

```bash
uv run python manage.py migrate
```

If your `db.sqlite3` already has to-dos from before accounts existed, `migrate` gives them to the
oldest admin account. Make one first with `uv run python manage.py createsuperuser`, then run
`uv run python manage.py migrate` again.

**5. Download the test browser.** Some tests use a real Chromium browser. This downloads it, about
150 MB, once.

```bash
uv run playwright install chromium
```

**6. Turn on the commit checks.** From now on, every `git commit` checks your code first.

```bash
uv run pre-commit install
```

**7. Start the server.**

```bash
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000/> and click *Create an account*. Each account sees only its own
lists and to-dos, plus the lists other people share with it. Press `Ctrl+C` in the terminal to
stop the server.

**8. Run the tests.**

```bash
uv run python manage.py test
```

You should see `OK`, and then one line for each layer of tests:

```
Test layers
  CUJ           8 passed
  Integration  225 passed
  Unit         29 passed
```

On a Mac, `make` does the same in fewer words: `make setup` is steps 3 to 6, `make run` is step 7,
`make test` is step 8. `make help` lists the rest.

## Tests

The tests are sorted into three layers. The folder a test is in is its layer.

| Layer | Folder | What it tests | Command |
|---|---|---|---|
| CUJ | `tests/cuj/` | A whole task, like "add a to-do, finish it, delete it", in a real browser | `make cuj` |
| Integration | `tests/integration/` | One address, from the request to the database, with Django's test client | `make integration` |
| Unit | `tests/unit/` | One method on its own, with no requests and no database | `make unit` |

CUJ means "critical user journey": an important task a person does from start to finish.

The tests run in one process. To use every CPU core instead, run `make test PARALLEL=auto`. With
as few tests as this project has, one process is faster.

## Checks

| Command | What it does |
|---|---|
| `uv run ruff check` | Finds mistakes and bad habits in the Python code |
| `uv run ruff format` | Rewrites the Python code in the standard style |
| `uv run pre-commit run --all-files` | Runs every commit check on every file |

The commit checks run Ruff, Django's own check, and a few checks on every file. If a check fails
because it fixed a file for you, look at the change, `git add` the file, and commit again. GitHub
runs the same checks and the tests on every push.

## How it is put together

| File | What it does |
|---|---|
| `config/settings.py` | Settings for the whole project |
| `config/urls.py` | Sends each address to the right app |
| `accounts/` | Sign up, log in and log out, with Django's own accounts |
| `accounts/templates/registration/` | The login and sign-up pages |
| `accounts/tests/helpers.py` | Helpers the tests share: test users, and a test that starts logged in |
| `todos/models.py` | The `TodoList` and `Todo` tables in the database; each list has an owner and can be shared with members, each to-do is in a list and has an optional due date, optional notes, a priority (Low, Medium or High) and tags; the `Tag` table holds each person's tags |
| `todos/tags.py` | Cleans the tags a person types, like "work, #Home", and checks their limits |
| `todos/urls.py` | The addresses of the list and to-do pages |
| `todos/forms.py` | The forms that check a to-do (with its tags), a list's name, the username to share a list with, and the search text |
| `todos/queries.py` | Picks the to-dos a list page shows: the search in the title, the notes and the tags |
| `todos/views.py` | What happens when each address is visited |
| `todos/templates/base.html` | The frame every page shares: the colors, the style, who is logged in, the messages |
| `todos/templates/todos/todo_list.html` | The page you see: one list |
| `todos/templates/todos/list_form.html` | The page to make or rename a list |
| `todos/templates/todos/list_confirm_delete.html` | The page that asks before a list is deleted |
| `todos/templates/todos/_todo_item.html` | One row of the list |
| `todos/templates/todos/todo_edit.html` | The page to edit one to-do |
| `todos/tests/` | The tests, one folder per layer |
| `config/test_runner.py` | Sorts the tests into layers and counts them |
| `AGENTS.md` | Instructions for the AI assistant (Codex reads it; `CLAUDE.md` points Claude to it) |

## Put it on the internet

A live server needs three environment variables. Never put their real values in the code.

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string. Make one with `uv run python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | The site's address without `https://`, for example `my-todo.onrender.com` |

With `DJANGO_DEBUG` set to `False`, the site only works over HTTPS.

Build command:

```bash
pip install uv && uv sync --locked --no-dev && uv run --no-dev python manage.py collectstatic --no-input && uv run --no-dev python manage.py migrate
```

Start command:

```bash
uv run --no-dev gunicorn config.wsgi
```
