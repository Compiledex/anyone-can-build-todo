# 0007. Unique list names through a stored name_key

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-11) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about how the app stops one person from having two lists with the same name in different
> case, like "Ærend" and "ærend".

## Context

- The owner decided: list names are unique per owner, ignoring case for **every** letter, also
  æ, ø and å. Names of lists shared with you do not count. The rule must not depend on the app's
  custom SQLite function (list-name-casefold, "Decided by the person").
- SQLite's own `LOWER()` and `NOCASE` know only A to Z. "Ærend" and "ærend" look different to
  them.
- The app adds a Python function `casefold()` to its own SQLite connections
  (`todos/sqlite_functions.py`). Another tool that opens `db.sqlite3` does not have it. A database
  rule that calls it would break there.

## Decision

Store the key: `TodoList.name_key = casefold(name)`, set by `TodoList.save()` (and `clean()`) in
Python. The database rule is a plain `UniqueConstraint(fields=["owner", "name_key"],
name="unique_list_name_key_per_owner")`: two plain texts compared with `=`.

The form (`TodoListForm`) checks the same key first and names the clash: "You already have a list
called “Ærend”." Only the person's **own** lists count.

## Consequences

- The rule holds in every path: the form, the admin, a script, two requests at once.
- It works with every SQLite tool, with or without the custom functions.
- Rule: never change a name without `save()` (no `QuerySet.update(name=...)`, no
  `bulk_create`), or `name_key` goes stale. A data migration that makes lists sets `name_key`
  itself.
- A data migration (0020) filled `name_key` and renamed any clash to "<name> (2)", "(3)", and so
  on. Migrations 0019 to 0021 are a set.
- Rule: the `norwegian` collation is only for sorting (`ORDER BY`), never for `=` or `UNIQUE`.

## Alternatives considered

| Option | Why not |
|---|---|
| A check in the form only | The database still allows both names (admin, script, two requests at once). |
| A database rule on `casefold(name)` (the SQL function) | Breaks wherever the function is not added. |
| A `GeneratedField` with `casefold(name)` | Same problem: SQLite computes it with the SQL function. |
| A `COLLATE NOCASE` column | SQLite's NOCASE knows only A to Z. |

## Source

- [`docs/plans/list-name-casefold.md`](../plans/list-name-casefold.md), decision 1 and "Other ways, and why not" (PR #49).
- [`docs/plans/nordic-letters.md`](../plans/nordic-letters.md) (PR #41): `casefold()` and the `norwegian` collation.
- `todos/models.py` (`TodoList`), `todos/forms.py` (`TodoListForm`), `todos/migrations/0019`-`0021`.

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
