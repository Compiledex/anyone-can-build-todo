# BUG-003: The daily-backup name pattern also matched digits from other scripts

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

- **Severity:** S3. The pattern decides which files `make run` may **delete** when it keeps only
  the newest 14 daily copies. A wrong match could count, or delete, a file that is not one of its
  own copies. It needs a file with a very unusual name in `backups/`, so it is unlikely; but the
  rule "only delete our own daily copies" must hold exactly.
- **Found:** 2026-10-11, by the adversarial code review of backup-on-run, before merge.
- **Status:** Fixed in commit 449a3e9, merged in PR #48 (2026-10-11).

## Steps to reproduce (on the code before the fix)

In a scratch folder (never your real `backups/`):

1. Make an empty file whose name uses Arabic-Indic digits for the date, for example
   `db-٢٠٢٠٠١٠١-000000-daily.sqlite3`.
2. In Python: `from todos.backup import daily_copies; daily_copies("<scratch folder>")`.

## Expected

The file is **not** in the list. Only names with the digits 0-9 are daily copies.

## Actual

The file is in the list, so `prune_daily` could delete it.

## Environment

Branch `feature/backup-on-run` at commit b494f09 (before the review fix), Python 3 `re` module.

## Root cause

The pattern `DAILY_NAME` in `todos/backup.py` used `\d`:

```python
DAILY_NAME = re.compile(r"db-(\d{8})-\d{6}-daily\.sqlite3")
```

In Python, for normal text (`str`), `\d` means *any* Unicode decimal digit, not only 0-9. It also
matches for example `٢` (Arabic-Indic two) or `५` (Devanagari five). A *regular expression* (a
pattern for matching text) that guards a delete must match only what it means.

## Fix

Commit 449a3e9:

```python
# [0-9], not \d: \d also matches other scripts' digits, like "٢".
DAILY_NAME = re.compile(r"db-([0-9]{8})-[0-9]{6}-daily\.sqlite3")
```

`daily_copies` still uses `fullmatch` (the whole name must match), and still skips symbolic links
and anything that is not a regular file.

## Guard test

`todos/tests/integration/test_backup.py`, class `DailyBackupTests`,
`test_daily_name_must_match_whole`. It makes several near-miss names (an extra letter at the end
or start, a `.tmp` name, seven digits, and the Arabic-Indic digits) plus one real daily name, and
checks that `daily_copies` returns only the real one.

## Lessons

- In Python, `\d` is not `[0-9]`. Use `[0-9]` (or the `re.ASCII` flag) when the digits must be
  ASCII.
- Every pattern that decides what to delete deserves a test with "almost matching" names.

## Related documents

- [Bug triage process](README.md), [BUG-002](BUG-002-failed-backup-reported-as-success.md) (same review)
- [Deployment runbook](../runbooks/deployment.md) (daily backups)
- Plan: [`docs/plans/backup-on-run.md`](../plans/backup-on-run.md); PR #48
