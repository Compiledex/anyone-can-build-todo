# BUG-002: A failed daily backup said "Today's copy is already there", and make run gave no warning

| | |
|---|---|
| Type | Bug report |
| Phase | Production |
| Written by | QA engineer (in this project: found by the adversarial code reviewer agent; written up by Claude) |
| Status | Done (fixed in PR #48 before merge) |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A bug report tells everyone exactly how to see a bug, how bad it is,
> and, once fixed, why it happened and which test now stops it from coming back. A developer,
> tester or reviewer writes it when the bug is found. Without a clear report, a bug cannot be
> reproduced, and the same mistake is made again later.

- **Severity:** S2. No data is lost at that moment, but the person believes a backup exists when
  it does not. The day they need it, it is missing. A silent failure of a safety feature is worse
  than a loud one.
- **Found:** 2026-10-11, by the adversarial code review of backup-on-run, before merge.
- **Status:** Fixed in commit 449a3e9, merged in PR #48 (2026-10-11). No user ever met it.

## Steps to reproduce (on the code before the fix)

Do this only in a scratch folder, never with your real `backups/`. The tests use `--source` and
`--folder` for that (they exist for the tests only).

1. Make a scratch database file, for example `/tmp/scratch/db.sqlite3`.
2. Make a plain **file** where the backup folder should be: `touch /tmp/scratch/backups`.
3. Run `uv run python manage.py backup_db --daily --source /tmp/scratch/db.sqlite3 --folder /tmp/scratch/backups`.

A second way: make a **folder** (or a symbolic link) with today's daily name inside the backup
folder, for example `backups/db-20261011-081500-daily.sqlite3/`, in the same second.

## Expected

`CommandError: Could not copy the database: ...`, a non-zero exit, and in `make run` the line
"Warning: the daily backup did not work (see the message above). The app starts anyway. Run make
backup to try again."

## Actual

The command said "Today's copy is already in backups/." and exited 0. `make run` showed no warning.
No copy was made.

## Environment

Branch `feature/backup-on-run` at commit b494f09 (before the review fix), macOS, Python's standard
`pathlib` and `sqlite3`.

## Root cause

In `todos/backup.py`, `daily_backup` calls `backup_database`, which can raise `FileExistsError`
(Python's error for "a file with this name already exists") in more than one place:

| Where | Why it raises | What it really means |
|---|---|---|
| `open(target, "xb")` | Another run made today's copy in the same second | Today's copy is safe: OK |
| `folder.mkdir(exist_ok=True)` | `backups` is a plain file, not a folder | The copy failed |
| `open(target, "xb")` | A folder or link has today's name | The copy failed |

The old code caught **every** `FileExistsError` as the first case (`except FileExistsError:
created = None`). So two kinds of failure looked like success.

## Fix

Commit 449a3e9: after `except FileExistsError`, check what has today's name. Only a **regular
file** that is **not a symbolic link** means "today's copy is there". Anything else re-raises the
error, so the command fails and `make run` prints its warning:

```python
protect = folder / f"db-{now:%Y%m%d-%H%M%S}{DAILY_SUFFIX}.sqlite3"
if protect.is_symlink() or not protect.is_file():
    raise
```

## Guard tests

In `todos/tests/integration/test_backup.py`, class `DailyBackupTests`:

- `test_folder_that_is_a_file_is_a_failed_copy`: a file where the folder should be gives
  `CommandError("Could not copy the database ...")`.
- `test_something_else_with_todays_name_is_a_failed_copy`: a folder, then a symbolic link, with
  today's name both give the same error, and the link's target is not changed.
- `test_failed_daily_copy_is_a_command_error`: a failing SQLite copy is a `CommandError`, and no old
  copy is deleted.

`MakeRunTests.test_failed_backup_still_starts_with_a_warning` in the same file checks that
`make run` prints the warning and still starts when the copy fails. Each new guard test was shown failing first (PR #48, "Review" section).

## Lessons

- One exception type can mean different things. Catch it, then check the real state.
- A safety feature must fail loudly.

## Related documents

- [Bug triage process](README.md), [BUG-003](BUG-003-daily-name-matches-non-ascii-digits.md) (same review)
- [On-call and incident runbook](../runbooks/on-call-and-incidents.md) (the daily backup warning)
- Plan: [`docs/plans/backup-on-run.md`](../plans/backup-on-run.md); PR #48
