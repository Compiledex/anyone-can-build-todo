# Plan: `make run` makes a daily backup first

Status: approved by the person (2026-10-11, plan card answered), not started

Builds on: **local-safety** (`todos/backup.py`, `backup_database`, `copy_sqlite`, the `backup_db`
command, `make backup`, `make reset`, `/backups/` in `.gitignore`, `MakeResetTests` with a fake
`uv`), and **foundation** (the `Makefile`, `make run`).

## Words used in this plan

- **Daily copy**: the backup that `make run` makes, at most one per day.
- **Local day**: the date in the app's time zone, `TIME_ZONE = "Asia/Tokyo"` in
  `config/settings.py`, the same "today" as everywhere in the app (`timezone.localtime()`).
- **Prune**: delete old files so only the newest ones stay.

## What is wrong today

Facts, checked on `main` (commit `d66b978`):

- `make run` is only `uv run python manage.py runserver`. A backup happens only when the person
  types `make backup`, or before `make reset`.
- `backup_database(source, folder, now)` names a copy `db-YYYYMMDD-HHMMSS.sqlite3`, never
  overwrites, and never deletes anything. Nothing removes old copies, so `backups/` only grows.

## Goal

Every `make run` first makes a copy of `db.sqlite3`, but at most one per local day. It keeps only
the newest 14 daily copies and deletes older **daily** copies. Then the server starts, also when
the copy failed (with a clear warning). `make backup` and `make reset` work as today, and their
copies are never deleted by this.

## Decisions

### 1. Daily copies have their own name: `db-YYYYMMDD-HHMMSS-daily.sqlite3`

- Only files whose **whole name** matches `^db-\d{8}-\d{6}-daily\.sqlite3$` are daily copies.
  Only they count for "one per day", and only they are ever pruned.
- Copies from `make backup` and `make reset` keep today's name `db-YYYYMMDD-HHMMSS.sqlite3` and
  are **never** deleted automatically. Why: the copy `make reset` makes is the only copy of the
  data before the reset. Fourteen days of `make run` must not delete it.
- The name still starts with `db-` and the time, so the README's restore line (`cp
  backups/db-<time>.sqlite3 db.sqlite3`) works for both.
- `backup_database` gets one keyword argument, `suffix=""`, put before `.sqlite3`. Everything else
  in it (read-only source, reserve the name with `open(target, "xb")`, temporary file, `fsync`,
  `os.replace`, mode 600) stays and is used by the daily copy too.

### 2. New functions in `todos/backup.py`

```python
DAILY_SUFFIX = "-daily"
DAILY_NAME = re.compile(r"db-(\d{8})-\d{6}-daily\.sqlite3")
DAILY_KEEP = 14

def daily_copies(folder):
    """The daily copies in `folder`, oldest first (by name, which is by time).

    Only regular files (not links, not folders) whose whole name matches
    DAILY_NAME (DAILY_NAME.fullmatch(name), never .match or .search). Never a
    .tmp file, never another backup, never anything else.
    """

def prune_daily(folder, keep, protect):
    """Delete all but the newest `keep` daily copies. Returns the deleted paths.

    `protect` (today's copy: the one just made, or the one already there) is
    never deleted and counts as one of the `keep`. Of the others, the newest
    keep - 1 by name stay.
    """

def daily_backup(source, folder, now, keep=DAILY_KEEP):
    """Make today's daily copy unless one exists, then prune.

    Returns (new path or None, deleted paths). No source: (None, []) and
    nothing is pruned. If the copy fails, the error goes up and nothing is
    pruned, so old copies are never deleted on a day without a new one.
    """
```

- **"Today"** is `now.date()`, where `now` is `timezone.localtime()` (Tokyo). A daily copy exists
  for today when a daily name has today's `YYYYMMDD`.
- **Two `make run` in the same second**: `backup_database` raises `FileExistsError`; `daily_backup`
  treats it as "today's copy exists" (no error).
- **Prune only after success**: when the copy fails, the function raises before pruning. When
  today's copy already exists, it prunes (that is safe: today's copy is there).
- `prune_daily` uses `Path.unlink()` on each path from `daily_copies`; it never deletes folders,
  never follows a link (`not path.is_symlink() and path.is_file()`; not
  `is_file(follow_symlinks=False)`, which needs Python 3.13, and `pyproject.toml` allows 3.12),
  and never leaves the folder it was given.
- The 14 includes today's copy, and **today's copy is never pruned**, even when other daily
  names sort after it (for example files with a future date, after the Mac's clock was wrong).
  Without `protect`, 14 future-dated files would make the copy just made the oldest, and it
  would be deleted at once.

### 3. The command: `backup_db --daily`

`todos/management/commands/backup_db.py` gets a flag, `--daily`. Without it, the command is
unchanged (`make backup`, `make reset`). With it, it calls `daily_backup` and prints one or two
lines:

- `Saved today's copy in backups/db-20261011-081500-daily.sqlite3.`
- or `Today's copy is already in backups/.`
- or `No database yet: nothing to back up.`
- and, when something was pruned: `Removed 2 old daily copies.`

A failed copy is a `CommandError` with the same plain message as today ("Could not copy the
database: ..."), exit code 1, and `make run` prints its warning.

A failed delete during pruning comes **after** today's copy is safely saved, so it is not a
failed backup: the command prints the "Saved" line, then `Warning: could not remove an old daily
copy: <name>: <error>.` on stderr, and exits 0. `prune_daily` stops at the first failed delete
and returns what it removed so far; the error goes up to the command as an `OSError` it catches.
The person sees a different warning from "the daily backup did not work", which would be wrong
here.

### 4. `make run`: copy, then start, also when the copy failed

```make
# A daily copy of db.sqlite3 first (at most one a day, the newest 14 are kept;
# see todos/backup.py). If it fails, say so and start the app anyway.
run:
	@uv run python manage.py backup_db --daily || echo "Warning: the daily backup did not work (see the message above). The app starts anyway. Run make backup to try again."
	uv run python manage.py runserver
```

**Why start the app after a failed copy** (the person wants the app to start):

- Starting the server does not change or delete any data, so the older copies in `backups/` are
  still as good as before.
- The usual reasons for a failure (a full disk, a locked or unreadable folder) are not fixed by
  refusing to start; the person would only lose the app for the day.
- The warning is printed in the terminal right before the server's own lines, and it says what to
  do.
- Nothing is pruned on a failed day (decision 2), so a broken backup can never shrink the set of
  good copies.

`make help` changes the `run` line: `make run  copy db.sqlite3 to backups/ (once a day, keeps
14), then start the server at http://127.0.0.1:8000`. The `backup` line adds "(kept until you
delete it)".

### 5. README

The "Back up your data" section gets: `make run` makes a daily copy (named `...-daily.sqlite3`),
keeps the newest 14, and never deletes copies from `make backup` or `make reset`; a failed copy
prints a warning and the app starts anyway.

## Security

- **Never touches other files**: only names that match the daily pattern exactly, only regular
  files, only in `backups/` (or the `--folder` a test passes). A `.tmp` file, a copy from `make
  backup` or `make reset`, a file the person put there, a folder or a link are never deleted.
  Tests prove each case.
- The backups hold all the data; they stay in `backups/`, mode 600, ignored by git, as today.
- No web view, no new URL: the web app cannot start a backup or a prune.
- The command takes no user text except the test options `--source` and `--folder`, which the
  `Makefile` never passes.

## Data and migrations

No model, no migration. The person's `db.sqlite3` is only read (read-only, as today). Going back:
revert the commit; daily copies stay as normal files (the person can delete them).

## Working next to

Wave: A, B, C and D are built at the same time; **merge order A → B → C → D (this), then E**.

- A, B and C do not touch `todos/backup.py`, the command, the `Makefile` or `README.md`.
- C adds migrations; the person should run `make backup` before migrating (C says so). After D,
  `make run` also makes a daily copy.
- **E, cleanups**: merges last; it may shorten the `AGENTS.md` rows this plan writes.
- `AGENTS.md`: the `todos/backup.py` and `backup_db.py` rows, the Commands list (`make run`).

## Not part of this task

- A launchd job that makes a copy when the app is not started.
- Copying backups off the Mac.
- Pruning copies from `make backup` or `make reset`.
- A setting for the number 14 (a constant in `todos/backup.py`).
- A `make restore` command.

## Changes to files

| File | Change |
|---|---|
| `todos/backup.py` | `suffix` for `backup_database`; `DAILY_SUFFIX`, `DAILY_NAME`, `DAILY_KEEP`; `daily_copies`, `prune_daily`, `daily_backup`. |
| `todos/management/commands/backup_db.py` | `--daily`. |
| `Makefile` | `run` makes the daily copy first; `help` lines. |
| `README.md` | "Back up your data": the daily copy. |
| `todos/tests/integration/test_backup.py` | `DailyBackupTests`, `MakeRunTests`. |
| `AGENTS.md` | `todos/backup.py` and `backup_db.py` rows; Commands (`make run`). |

## Steps

1. **Tests first** (below). `make integration`: the new ones fail. Show the person.
2. `todos/backup.py`, then the command, then the `Makefile`.
3. By hand, **in the worktree only**: `uv run python manage.py migrate` (the worktree's own
   `db.sqlite3`), then `uv run python manage.py backup_db --daily` twice (one copy, then "already
   in"). **Never run `make run` in the main checkout and never use port 8000**: the person's
   server runs there. `MakeRunTests` covers the `Makefile` with a fake `uv`, so no server is
   started by hand.
4. README and `AGENTS.md`. `make check`. Commit. Last commit: Status `**done** (<date in Tokyo>)`.

## Tests

All in `todos/tests/integration/test_backup.py`, `SimpleTestCase`, each with its own temporary
folder and its own small SQLite file (as `BackupTests` does). Every call passes `--source` and
`--folder`, so the real `backups/` and `db.sqlite3` are never near a test.

### `DailyBackupTests`

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_first_run_makes_a_daily_copy` | `daily_backup(source, folder, now)` makes `db-20261011-081500-daily.sqlite3`, with the rows. | No suffix, or no copy. |
| `test_second_run_the_same_day_makes_nothing` | A second call at 23:59 the same day returns `(None, [])`; one file. | A copy on every run. |
| `test_next_day_makes_a_new_copy` | A call the next day (00:00:01) makes a second daily copy. | Comparing the wrong date part. |
| `test_the_day_is_the_tokyo_day` | `call_command("backup_db", "--daily", ...)` with `timezone.now` patched to 2026-10-11 15:30 UTC (00:30 on the 12th in Tokyo): the file name has `20261012`. | Using UTC or the computer's own time zone. |
| `test_manual_copy_does_not_count_as_daily` | A `db-20261011-070000.sqlite3` exists; `daily_backup` the same day still makes a daily copy. | Counting `make backup` copies. |
| `test_keeps_the_newest_fourteen` | Twenty daily files (empty, named for 20 days), then a run: the 14 newest stay (today's new one included), the 7 oldest are deleted, the return value lists them. | Keeping the wrong ones, or by file time instead of name. |
| `test_never_deletes_other_files` | In the folder, besides 20 daily copies: `db-20200101-000000.sqlite3` (manual), `.db-20200101-000000-daily.sqlite3.tmp`, `db-20200101-000000-daily.sqlite3.bak`, `notes.txt`, a folder named `db-20200101-000000-daily.sqlite3`, and a symlink with a daily name that points to a file outside the folder. After the run: all of these are still there (and the link's target too). | A loose pattern (`startswith("db-")`, `glob("*daily*")`), or following a link. |
| `test_failed_copy_prunes_nothing` | Twenty daily files; `copy_sqlite` patched to raise: the error goes up, all twenty are still there, no new file. | Pruning before the copy, or on a failed day. |
| `test_no_database_makes_and_prunes_nothing` | No source: `(None, [])`, the twenty files stay. | Pruning with no new copy and no today's copy. |
| `test_same_second_counts_as_done` | A daily file with exactly `now`'s name exists: no error, nothing new. | `FileExistsError` stopping `make run` with a warning. |
| `test_todays_copy_is_never_pruned` | Twenty daily files dated in 2027 (the future); a run today: today's new copy is still there, with the 13 newest 2027 files; 7 are deleted. | Pruning by name only, without `protect`. |
| `test_prune_failure_after_a_good_copy_is_a_warning` | Twenty daily files; `Path.unlink` patched to raise `PermissionError` for one old file: the command exits normally (no `CommandError`), today's copy is there, stderr has "Warning: could not remove an old daily copy", stdout has "Saved today's copy". | Treating a prune failure as a failed backup, or hiding it. |
| `test_daily_name_must_match_whole` | `daily_copies` ignores `db-20200101-000000-daily.sqlite3x` and `xdb-20200101-000000-daily.sqlite3`. | `DAILY_NAME.match` or `.search` instead of `fullmatch`. |
| `test_daily_command_prints_one_line` | The command with `--daily` prints "Saved today's copy in"; the second time "Today's copy is already in"; with 14 old ones (15 after the new one) also "Removed 1 old daily copy." (or "copies" with `pluralize`). | Wrong output. |
| `test_plain_command_never_prunes` | Twenty daily files; `call_command("backup_db", ...)` without `--daily`: a normal copy is made and all twenty stay. | `make backup` pruning. |

### `MakeRunTests` (the real `make run`, with a fake `uv`, like `MakeResetTests`)

The fake `uv` from `MakeResetTests` (it logs its arguments; `FAKE_BACKUP_EXIT=1` makes
`backup_db` fail; everything else, also `runserver`, exits 0 at once). The `Makefile` is copied
into a temporary folder. No server starts, no port is used.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_run_backs_up_then_starts` | The log has a line with `backup_db --daily` and a later line with `runserver` (the test compares the two lines' positions, not the exact list of lines); exit code 0. | No backup, or the backup after the server. |
| `test_failed_backup_still_starts_with_a_warning` | With `FAKE_BACKUP_EXIT=1`: a `runserver` line comes after the `backup_db` line in the log, the output has "Warning: the daily backup did not work", exit code 0. | Stopping the app on a failed backup, or no warning. |
| `test_backup_target_has_no_daily_flag` | `make backup` logs `backup_db` **without** `--daily`. | `make backup` limited or pruned. |

## Decided by the person (2026-10-11)

- `make run` first makes a backup with the existing `backup_db` code, at most once per local day
  (Asia/Tokyo), then keeps only the newest 14 backup files made by this daily step (older ones
  deleted, only by name pattern), then starts the server.
- A failed backup prints a warning but the app still starts.
- Never touch files that are not backups. `make backup` stays unlimited.
- Tests only in temporary folders (a fake `uv` on `PATH` for the `Makefile`).

## Open choices

1. **Which copies the 14 counts and prunes.** Only the daily copies (their own `-daily` name),
   **recommended**: the copy before a `make reset` and the person's own `make backup` copies are
   never deleted automatically. (The other reading, "the newest 14 of all copies", could delete
   the only copy from before a reset after two weeks.)
2. **Does a `make backup` copy count as today's daily copy?** No, **recommended**: one simple
   rule ("one daily copy a day"), and the manual copy is never pruned anyway. (Yes would save one
   copy on days when the person also types `make backup`.)
3. **Where the logic lives.** In `todos/backup.py` and a `--daily` flag on the existing command,
   **recommended**: tested Python, and the `Makefile` stays one line. (A shell `find ... -delete`
   in the `Makefile` is harder to test and easy to get dangerously wrong.)

## Review

Verification by the planner (2026-10-11), against `main` (`d66b978`):

- Confirmed: `make run` is `uv run python manage.py runserver` only; `make backup` is
  `uv run python manage.py backup_db`; `make reset` calls `backup_db` before `rm -f db.sqlite3`.
- Confirmed: `backup_database` makes `db-{now:%Y%m%d-%H%M%S}.sqlite3`, reserves the name with
  `open(target, "xb")`, writes `.<name>.tmp` first, and the command passes
  `timezone.localtime()` (`TIME_ZONE = "Asia/Tokyo"`).
- Confirmed: `MakeResetTests` copies the `Makefile` to a temporary folder and puts a fake `uv`
  first on `PATH`; its `case` matches `*backup_db*`, so the same fake works for `backup_db
  --daily` and logs `runserver` without running it.
- Confirmed: `/backups/` is in `.gitignore`.

The plan review (2026-10-11, an independent reviewer who also ran small prototypes) said APPROVE
WITH CHANGES. What changed:

- `DAILY_NAME.fullmatch` everywhere (a test with a longer name).
- A prune failure after a good copy is a warning on stderr with exit code 0, with its own text,
  not "the daily backup did not work". `MakeRunTests` compares the order of lines, not exact
  lists.
- Today's copy is never pruned (`protect`), even when future-dated names sort after it.
