# To-do list

A small to-do list app, built with Django. Make a few lists, add to-dos with a due date, a priority
and tags, break a big to-do into steps, and share a list with the people you plan with. It runs on
your own computer, and your data stays in one file, `db.sqlite3`.

The pictures below are real screenshots of the app, with invented sample data. They follow your
light or dark GitHub theme. To take them again after the app changes, run `make landing-shots`.

**Contents:** [What it does](#what-it-does) · [Run it on your laptop](#run-it-on-your-laptop) ·
[Back up your data](#back-up-your-data) · [Reminders on your Mac](#reminders-on-your-mac) ·
[Tests](#tests) · [Checks](#checks) · [How it is put together](#how-it-is-put-together) ·
[Put it on the internet](#put-it-on-the-internet)

## What it does

### Your lists and to-dos

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="todos/static/todos/landing/list-dark.webp">
  <img src="todos/static/todos/landing/list-light.webp" width="720" alt="The Home list: the menu of lists, the form to add a to-do, search and sort, and two to-dos with a priority, a due date and a tag. One is overdue, the other shows Steps: 2 of 5 done.">
</picture>

- Keep your to-dos in **several lists**, like "Home" and "Work". When you sign up, your first
  list, "Inbox", is already there. You can make, rename and delete lists.
- Give a to-do a **due date**. When the day has passed, it says **Overdue** in red.
- Give it a **priority** (Low, Medium or High), **tags** (like `#home`) and **notes**.
- A to-do can **repeat** every day, week or month: mark it **Done**, and the next one appears
  with its new date.
- **Edit**, **Done** (and **Undo**) and **Delete** sit on every row. **Clear completed** deletes
  all the done to-dos of a list at once, after asking once more.

### Steps inside a to-do

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="todos/static/todos/landing/steps-dark.webp">
  <img src="todos/static/todos/landing/steps-light.webp" width="720" alt="The to-do Paint the hallway with its steps open: 2 of 5 done, the done steps crossed out, and a field to add one more step.">
</picture>

Break a big to-do into small steps and tick them off one by one. The row shows how far you are,
like "Steps: 2 of 5 done".

### Share a list

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="todos/static/todos/landing/share-owner-dark.webp">
  <img src="todos/static/todos/landing/share-owner-light.webp" width="720" alt="The Sharing part of a list: two members, theo and ines, each with a Remove button, and a field to share the list with one more username.">
</picture>

The owner of a list shares it by typing another person's username. Those people are its
**members**: they can add, edit, finish and delete its to-dos. Only the owner can rename, delete
or share the list, and remove a member. Members do not see each other.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="todos/static/todos/landing/share-member-dark.webp">
  <img src="todos/static/todos/landing/share-member-light.webp" width="720" alt="The same list seen by theo, a member: it is under Shared with me, and the page says Shared by mara.">
</picture>

A member finds the list under **Shared with me**, and can leave it at any time. "Leave this list" asks once more first, because only the owner can share the list again.

### Find a to-do, and sort them

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="todos/static/todos/landing/find-dark.webp">
  <img src="todos/static/todos/landing/find-light.webp" width="720" alt="A list showing only the to-dos that are not done, sorted by due date, with the overdue one first.">
</picture>

- **Search** the titles, notes and tags of a list (upper and lower case do not matter, also for æ, ø and å).
- **Filter**: show All, Not done or Done.
- **Sort by** date added, due date, priority, title (a to z, then æ, ø, å), or your own order.

### Put them in your own order

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="todos/static/todos/landing/order-dark.webp">
  <img src="todos/static/todos/landing/order-light.webp" width="720" alt="A list in the Manual order: each to-do has a drag handle and arrow buttons to move it up or down.">
</picture>

With **Sort by: Manual**, drag a to-do by its handle, or use the arrow buttons (they also work
with a keyboard). The order belongs to the list, so everyone who shares it sees the same order.

### Light or dark, like your system

<p>
  <img src="todos/static/todos/landing/compare-light.webp" width="49%" alt="The Garden list in light mode.">
  <img src="todos/static/todos/landing/compare-dark.webp" width="49%" alt="The same Garden list in dark mode.">
</p>

The app follows the light or dark setting of your computer or phone. It works on a phone too.

### Private by default

Every page needs a login. A person sees only their own lists and the lists shared with them;
someone else's list gives "not found", as if it did not exist. A visitor who is not logged in only
sees a front page that explains the app, with **Create an account** and **Log in**.

Optional: your Mac can show you **one notification each morning** with the to-dos due that day.
It is off until you set it up; see [Reminders on your Mac](#reminders-on-your-mac).

## Run it on your laptop

**The short version, on a Mac:** install uv (step 1), get the code (step 2), then run
`make setup` and `make run`, and open <http://127.0.0.1:8000/>. The steps below explain each part.

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
git clone https://github.com/Compiledex/anyone-can-build-todo.git
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

Open <http://127.0.0.1:8000/>. You see the landing page, which says what the app does. Click
*Create an account*. Each account sees only its own
lists and to-dos, plus the lists other people share with it. Press `Ctrl+C` in the terminal to
stop the server.

**8. Run the tests.**

```bash
uv run python manage.py test
```

You should see `OK`, and then one line for each layer of tests, something like this (the
numbers grow with the app):

```
Test layers
  CUJ          30 passed
  Integration  577 passed
  Unit         124 passed
```

On a Mac, `make` does the same in fewer words: `make setup` is steps 3 to 6, `make run` is step 7,
`make test` is step 8. `make help` lists the rest.

## Back up your data

All your accounts, lists and to-dos are in one file, `db.sqlite3`. A **backup** is a copy of that
file, so you can get your data back after a mistake.

**Make a copy.** Run:

```bash
make backup
```

It saves a copy in the folder `backups/`, with the date and time in the name, for example
`backups/db-20261011-081500.sqlite3`. It is safe while the server runs: it uses SQLite's own copy,
not a plain file copy. Without `make`: `uv run python manage.py backup_db`.

**`make run` also makes a copy, once a day.** Before it starts the server, `make run` saves a
*daily copy*, for example `backups/db-20261011-081500-daily.sqlite3`, at most one a day. It keeps the
newest 14 daily copies and deletes older **daily** copies. It never deletes the copies from
`make backup` or `make reset`, or any other file. If the copy does not work (for example the disk is
full), it prints a warning, and the app starts anyway; run `make backup` to try again.

**`make reset` asks first.** It deletes `db.sqlite3` and starts again with an empty database. So it
first asks you to type `yes` (anything else stops, and nothing is deleted), then it makes a copy in
`backups/`, and only then deletes the database.

**Get your data back (restore).**

1. Stop the server: press `Ctrl+C` in its terminal.
2. Copy the backup you want over `db.sqlite3`:

   ```bash
   cp backups/db-20261011-081500.sqlite3 db.sqlite3
   ```

3. Run `make setup` (or `uv run python manage.py migrate`), so an older copy gets the newest
   tables.
4. Start the server again with `make run`.

**Good to know.**

- `backups/` is not in git. The copies from `make backup` and `make reset` stay until you delete them
  by hand; of the daily copies from `make run`, only the newest 14 stay.
- A copy holds all your data, also the accounts (with their password hashes). Do not share it.
- A copy on the same Mac does not help if the Mac breaks. Copy the `backups/` folder to an
  external disk or a cloud folder now and then: that is what really keeps your data safe.

## Reminders on your Mac

Once a day, at 08:00, your Mac can show **one notification** with the to-dos in **your own
lists** that are **due today**. It is off until you set it up once, yourself, in the Terminal:
the steps are in the [reminders runbook](docs/runbooks/reminders.md).

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

| Folder or file | What it holds |
|---|---|
| `config/` | The settings for the whole project, the main addresses, and the test runner |
| `accounts/` | Sign up, log in and log out, with Django's own accounts |
| `todos/` | The to-do app itself |
| `todos/models.py` | The tables in the database: lists, to-dos, tags and steps |
| `todos/views.py` | What happens when each address is visited |
| `todos/queries.py` | The search, the filter and the order of a list page |
| `todos/forms.py` | The forms that check what a person types |
| `todos/templates/` | The HTML of each page |
| `todos/static/` | The CSS, the JavaScript and the landing page's pictures |
| `todos/tests/` | The tests, one folder per layer (unit, integration, CUJ) |
| `deploy/macos/` | The launchd template for the morning reminders on a Mac (set up with the [reminders runbook](docs/runbooks/reminders.md)) |
| `scripts/` | The tool behind `make landing-shots` |
| `docs/` | The documentation: one example of each document a team writes, from the idea to the retrospective ([index](docs/README.md)) |
| `docs/plans/` | The plan for each feature, written before the code; history, not a description of the code today |
| `CHANGELOG.md` | What is new in each version |

Each file's job is in `AGENTS.md`.

## Put it on the internet

> [!WARNING]
> On many hosts the SQLite database file, `db.sqlite3`, is deleted at every deploy or restart,
> and all accounts and to-dos are gone; read the runbook before you put real data online.

The app runs on your own computer. Before you put it on a server, read
[If it ever runs on a server](docs/runbooks/deployment.md#if-it-ever-runs-on-a-server) in the
deployment runbook: it says how to keep the database, and which three environment variables a
live server needs.
