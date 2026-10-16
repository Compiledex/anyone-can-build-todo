# Deployment runbook

| | |
|---|---|
| Type | Deployment runbook |
| Phase | Production |
| Written by | Site reliability engineer (in this project: the owner and Claude) |
| Status | Approved |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A *runbook* is a list of exact steps for a job you do now and then:
> install, update, roll back. An operations engineer writes it, and anyone on the team can follow
> it, also at night and under stress. Without it, each person does the job a bit differently, and
> sooner or later someone loses data.

**Where the app runs:** only on the owner's Mac, at <http://127.0.0.1:8000>. It is not deployed to
a server (a decision). All data is in one file, `db.sqlite3`, which is not in git. Every command
below exists in the `Makefile` or `README.md`. Run them in the project folder.

## 1. First install

| Step | Command | What you should see |
|---|---|---|
| 1. Install uv (once) | `curl -LsSf https://astral.sh/uv/install.sh \| sh`, then open a new terminal | `uv --version` prints a version |
| 2. Get the code | `git clone https://github.com/Compiledex/anyone-can-build-todo.git` and `cd anyone-can-build-todo` | The project folder |
| 3. Set up everything | `make setup` | It runs `uv sync`, `playwright install chromium`, `migrate`, `pre-commit install` |
| 4. Check | `make check` | Every check passes; the tests end with one line per layer |
| 5. Start | `make run` | "Saved today's copy in ..." or "No database yet: nothing to back up.", then the server starts |
| 6. Open | <http://127.0.0.1:8000/> | The landing page. Click *Create an account*. |

## 2. Start and stop

- **Start:** `make run`. It first runs `backup_db --daily`: at most one copy a day
  (`backups/db-YYYYMMDD-HHMMSS-daily.sqlite3`), the newest 14 daily copies stay. If the copy fails,
  it prints "Warning: the daily backup did not work ..." and starts the app anyway (see the
  [incident runbook](on-call-and-incidents.md#playbook-c-the-daily-backup-warning)).
  Then it runs `clearsessions` (Django's own command): it deletes expired sessions and prints
  nothing. If it fails, it prints "Warning: could not remove expired sessions ..." and starts the
  app anyway.
- **Stop:** press `Ctrl+C` in the terminal where the server runs.

## 3. Update to a new version

Do this when `main` on GitHub has new commits.

1. Stop the server (`Ctrl+C`).
2. Make a safe copy: `make backup`. Note the file name it prints, e.g.
   `Saved a copy in backups/db-20261016-090000.sqlite3.` This is your **rollback point**.
3. Get the new code: `git pull`.
4. Install the new packages: `uv sync`.
5. See what will change in the database: `uv run python manage.py showmigrations todos`.
   Lines with `[ ]` are new migrations. Note the last `[X]` line (for example `0022_todo_copy_fingerprint`):
   you need it to roll back.
6. Change the database: `uv run python manage.py migrate`.
7. Check: `make check`.
8. Start: `make run`, then do the [health check](#5-health-check).

Read the PR body of each new migration first: some say "run `make backup` before `migrate`"
(for example PR #49).

## 4. Roll back

There are two ways. **A. Restore a backup** is the safe one. It gives you back the data from the
moment of the backup; changes made after it are lost.

### A. Restore a backup file (the safe way)

1. **Stop the server** (`Ctrl+C`). Never copy over `db.sqlite3` while the server runs.
2. **Keep the current state too:** `make backup`. Then even a wrong restore can be undone.
3. **Choose the copy:** `ls -l backups/`. Names hold the date and time (Tokyo time);
   `-daily` copies come from `make run`.
4. **Go back to the code that matches the copy**, if you updated the code:
   `git log --oneline` and `git checkout <commit before the update>`. (Return later with
   `git checkout main`.)
5. **Copy it over the database** (use your file name):

   ```bash
   cp backups/db-20261016-090000.sqlite3 db.sqlite3
   ```

6. **Bring the tables up to the code:** `uv run python manage.py migrate`. An older copy then gets
   the newer tables.
7. **Start:** `make run`, then do the health check. Log in and look at a few lists.

### B. Migrate back (only when no data must be lost)

Use this when the new code has a bad migration, and you have no good backup after it.

1. Stop the server, then `make backup`.
2. **While you still have the new code**, migrate back to the last migration you noted in step 5 of
   the update (here `0022`, the last one today), for example:

   ```bash
   uv run python manage.py migrate todos 0022
   ```

   The old code does not have the new migration files, so Django could not undo them after a
   checkout.
3. Then `git checkout <the old commit>` and `make run`.

A backwards migration can drop columns, and their data is gone. All data migrations in
`todos/migrations/` can run backwards (`0003`, `0016` and `0020` do nothing when undone), but this
was not tested against real data. Prefer A.

## 5. Health check

| Check | Command | Healthy |
|---|---|---|
| Settings and code | `uv run python manage.py check` | "System check identified no issues (0 silenced)." |
| Migrations | `uv run python manage.py showmigrations todos` | Every line `[X]` |
| No missing migration | `uv run python manage.py makemigrations --check --dry-run` | "No changes detected" |
| Server answers | `curl -sI http://127.0.0.1:8000/` in a second terminal | `HTTP/1.1 200 OK` (the landing page) |
| Backups | `ls -lt backups/ \| head` | A `-daily` copy from today |
| By hand | Log in, open a list, add and delete a to-do, click Undo | It works |

## If it ever runs on a server

This section is **not in use**: the app runs only locally. It summarises the "Put it on the
internet" part of `README.md` and the safe-settings plan (PR #36), so nobody starts from zero.

- **Environment variables** (never in the code):

  | Variable | Value | If wrong |
  |---|---|---|
  | `DJANGO_SECRET_KEY` | A long random string: `uv run python -c "import secrets; print(secrets.token_urlsafe(50))"` | With debug off, missing or weak (under 50 characters, under 5 different characters, or starting with `django-insecure-`) stops the app with `ImproperlyConfigured` (`config/env.py`) |
  | `DJANGO_DEBUG` | `False` | Only `True` or `False` (any case). Any other value, also empty, stops the app |
  | `DJANGO_ALLOWED_HOSTS` | The site's address without `https://`, commas between several | Requests to other names get 400 |

- With `DJANGO_DEBUG=False`, the site only works over HTTPS (`SECURE_SSL_REDIRECT` in
  `config/settings.py`).
- **Build command** (the variables must be set for the build too):
  `pip install uv && uv sync --locked --no-dev && uv run --no-dev python manage.py check --deploy --fail-level WARNING && uv run --no-dev python manage.py collectstatic --no-input && uv run --no-dev python manage.py migrate`.
  `check --deploy` is Django's list of production safety checks; with `--fail-level WARNING` any
  warning stops the build.
- **Start command:** `uv run --no-dev gunicorn config.wsgi`.
- **Data-loss risk:** many hosts throw away files the app wrote at each deploy or restart. Then
  `db.sqlite3` starts empty, with no error. Use a *persistent disk* (storage that survives a
  restart), or move to PostgreSQL (a code change, not built). Neither a setting for the database
  path nor PostgreSQL support exists today. Back up regularly either way.
- The reminders (`send_reminders`) only work on a Mac and are not part of a server.

## Related documents

- [On-call and incident runbook](on-call-and-incidents.md)
- [CHANGELOG](../../CHANGELOG.md), [QA run and bug bash](../process/qa-run-and-bug-bash.md)
- [Design document](../design/design-doc.md), [ADRs](../adr/)
- Plans: [`local-safety.md`](../plans/local-safety.md), [`backup-on-run.md`](../plans/backup-on-run.md),
  [`safe-settings.md`](../plans/safe-settings.md); PRs #36, #37, #43, #48
