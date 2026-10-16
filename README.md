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
sees a front page that explains the app, with **Create an account** and **Log in**. You can
delete your account (click your name at the top); your lists and to-dos go with it.

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
  CUJ          31 passed
  Integration  601 passed
  Unit         129 passed
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

Once a day, at 08:00, your Mac can show **one notification** with the to-dos in **your own lists**
that are **due today** and not done (not the lists others shared with you). If nothing is due,
there is no notification. A to-do is shown only once a day.

You can run it by hand at any time (replace `alice` with your username on the site):

```bash
uv run python manage.py send_reminders --user alice
```

It prints `Showed 1 notification (2 to-dos) for alice.` or `No to-dos due today for alice.`

To run it every morning, the Mac's own scheduler, **launchd**, starts it. You set this up once, in
the Terminal. These steps change your Mac's settings, so you do them yourself (not the AI).

1. **Move the project out of `Documents` (recommended).** macOS protects `Documents` from programs
   that start in the background, so launchd cannot go into the project folder, and the job fails
   with an empty log. Move it, for example to `~/code/anyone-can-build-todo`, and run `make setup`
   again there. Do not give Python "Full Disk Access" instead: that gives every Python script on
   the Mac access to all your files. (iCloud "Desktop & Documents" can also touch `db.sqlite3`
   while the app writes to it.)
2. **Get the database ready**, after you pull this feature:

   ```bash
   uv run python manage.py migrate
   ```

3. **Allow notifications first.** Show one test notification:

   ```bash
   osascript -e 'display notification "Test" with title "To-do list"'
   ```

   Open **System Settings → Notifications → Script Editor** and turn on **Allow notifications**.
   Run the line again and check that you see "Test", and that a Focus mode (like Do Not Disturb)
   is off. Do this before step 4: `osascript` says "it worked" even when notifications are not
   allowed, and then the to-dos are marked as reminded although you saw nothing.
4. **Try the command by hand.** Make a to-do due today in one of your own lists, then run
   `uv run python manage.py send_reminders --user <your username>`. To try again the same day,
   make a **new** to-do due today: the shown ones are now marked.
5. **Fill in the template** `deploy/macos/com.anyone-can-build-todo.reminders.plist`. In the
   project folder (replace `alice` with your username):

   ```bash
   mkdir -p ~/Library/LaunchAgents
   sed -e "s|__REPO_PATH__|$(pwd)|g" -e "s|__HOME__|$HOME|g" -e "s|__USERNAME__|alice|g" \
     deploy/macos/com.anyone-can-build-todo.reminders.plist \
     > ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   plutil -lint ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   ```

   `plutil -lint` must say `OK`. The project folder's path must not contain `&` or `|`: `sed`
   reads them as special characters, and the paths in the file would be wrong.
6. **Turn it on.** An error from `bootout` the first time is normal.

   ```bash
   launchctl bootout gui/$(id -u)/com.anyone-can-build-todo.reminders
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   ```

   If "Background Items Added" comes up, check **System Settings → General → Login Items →
   Allow in the Background**. If it is off, the job never runs.
7. **Test it now** (make a new to-do due today first):

   ```bash
   launchctl kickstart -k gui/$(id -u)/com.anyone-can-build-todo.reminders
   cat ~/Library/Logs/anyone-can-build-todo-reminders.log
   launchctl print gui/$(id -u)/com.anyone-can-build-todo.reminders | grep "last exit code"
   ```

   `last exit code = 0` means it worked. Another number with an empty log usually means launchd
   could not go into the project folder (see step 1).
8. **To change or stop it:** run the `bootout` line, change the file (or fill it in again with
   step 5), and run `bootstrap` again. To stop it for good, run `bootout` and delete the file from
   `~/Library/LaunchAgents/`. If you delete that account, remove the launchd job too, or a new
   account with the same name gets its reminders.

If the Mac is asleep at 08:00, the job runs when it wakes up. If the Mac is shut down, it does not
run that day: run the command by hand. The job runs the code that is in the project folder now, so
after you pull new code, run `uv run python manage.py migrate` once.

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
| `deploy/macos/` | The launchd template for the morning reminders on a Mac |
| `scripts/` | The tool behind `make landing-shots` |
| `docs/` | The documentation: one example of each document a team writes, from the idea to the retrospective ([index](docs/README.md)) |
| `docs/plans/` | The plan for each feature, written before the code; history, not a description of the code today |
| `CHANGELOG.md` | What is new in each version |

Each file's job is in `AGENTS.md`.

## Put it on the internet

> [!WARNING]
> **Your data can disappear on a host.** All accounts, lists and to-dos are in one file,
> `db.sqlite3`, in the project folder. Many hosts (for example Render's web services) throw away
> every file the app wrote each time you deploy or the server restarts. Then the database starts
> empty again, and everything is gone, without an error.
>
> Before you put real data online, check how your host keeps files:
>
> - Choose a host or plan with a **persistent disk** (storage that survives a deploy and a
>   restart), and make sure `db.sqlite3` is on that disk. Today the app always keeps the file in
>   the project folder; a setting to put it somewhere else is not built yet.
> - Or use a hosted database such as PostgreSQL. That needs a small code change in
>   `config/settings.py`, which is not built yet either.
> - Either way, **make backups**: run `make backup` regularly (see [Back up your data](#back-up-your-data)).
>
> On your own laptop this does not happen: `db.sqlite3` stays until you delete it.

A live server needs three environment variables. Never put their real values in the code.

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string. Make one with `uv run python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False`. Only `True` or `False` are allowed (upper or lower case); any other value, also an empty one, stops the app |
| `DJANGO_ALLOWED_HOSTS` | The site's address without `https://`, for example `my-todo.onrender.com` |

With `DJANGO_DEBUG` set to `False`, the site only works over HTTPS, and the app stops at once if
`DJANGO_SECRET_KEY` is missing or weak (fewer than 50 characters, fewer than 5 different
characters, or starting with `django-insecure-`).

The build uses the settings too, so set the three variables for the build as well as for the start.
(On most hosts, for example Render, the variables on the settings page are used for both.)

Build command:

```bash
pip install uv && uv sync --locked --no-dev && uv run --no-dev python manage.py check --deploy --fail-level WARNING && uv run --no-dev python manage.py collectstatic --no-input && uv run --no-dev python manage.py migrate
```

If the build stops, read the last line of the error: it says which variable to set.

Start command:

```bash
uv run --no-dev gunicorn config.wsgi
```
