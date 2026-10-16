# 0002. SQLite, with IMMEDIATE transactions

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-09) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about the database, and how two requests that write at the same time are kept safe.

## Context

- The app runs only on the owner's Mac. There is no database server.
- **SQLite** keeps the whole database in one file, `db.sqlite3`. It allows only one writer at a
  time.
- A **transaction** is a group of changes that happen all together or not at all. In SQLite's
  normal ("deferred") mode, a transaction takes the write lock late. When two transactions have
  both read and both try to write, SQLite refuses the second one at once with "database is
  locked". The person would see an error page. This was checked while planning recurring to-dos.
- Several views read a row, decide, then write (Toggle, Delete, Undo-delete, Edit, Move). Two
  clicks at the same moment must not both decide from the old value.

## Decision

Use SQLite, and set `"OPTIONS": {"transaction_mode": "IMMEDIATE"}` in `config/settings.py`
(Django 5.1 and newer). A transaction then takes the write lock when it starts, so a second
request **waits** for the first instead of failing.

Views that read and then write do both inside one `transaction.atomic()`, and read the row
**inside** it.

## Consequences

- Easy: no database server to install, start or secure. A backup is a copy of one file
  (`todos/backup.py`, SQLite's online backup).
- Safe: a double click waits, then sees the new value. Together with the idempotent toggles
  (Done sends `done=1`, PR #44) the known races are covered.
- Cost: all writes are one after the other. Fine for a few people, not for many.
- Cost: on many hosts the file is lost on every deploy (README, "Put it on the internet"). The
  app is not deployed, so this is accepted.
- Rule: never open a raw `sqlite3` connection for app queries; it would miss the custom SQL
  functions (`todos/sqlite_functions.py`).
- Known gap: no test runs two real requests in parallel threads (maintenance-pass plan).

## Alternatives considered

| Option | Why not |
|---|---|
| PostgreSQL *(added here; the README names it for a host)* | Needs a server. Not worth it for one Mac. |
| SQLite in normal (deferred) mode | Gives "database is locked" errors on two writes at the same time. |
| `select_for_update()` row locks *(added here)* | SQLite does not support it; Django ignores it there. |

## Source

- [`docs/plans/recurring.md`](../plans/recurring.md) (PR #20), "Two requests at the same time".
- `config/settings.py`, `DATABASES`.
- Used by [`docs/plans/safe-toggles.md`](../plans/safe-toggles.md) (PR #44) and
  [`docs/plans/delete-undo.md`](../plans/delete-undo.md) (PR #51).

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
