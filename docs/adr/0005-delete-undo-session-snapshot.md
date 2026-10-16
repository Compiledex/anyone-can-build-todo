# 0005. Delete undo with a session snapshot, not a soft delete

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-11) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about how a deleted to-do can be brought back with an Undo button.

## Context

- The owner asked for an Undo button after Delete, that restores the to-do with its notes,
  priority, tags, steps, position and recurring links (delete-undo, "Decided by the person").
- A **soft delete** keeps the row and marks it with a "deleted" field. Then every query that reads
  to-dos must leave those rows out: the list page, search, "Clear completed", reorder, recurring
  copies, reminders, the admin. One forgotten filter shows a deleted to-do, or makes Move fail.
- A **session** is data the server keeps for one logged-in browser. The browser cannot change it.

## Decision

Delete really deletes the row. Just before, `take_snapshot` (`todos/undo.py`) copies the to-do
into plain JSON data: every field in `SNAPSHOT_FIELDS`, the tag names, the steps with their done
state, and the id of its next copy. The snapshot goes in `request.session["undo_delete"]`.
`restore` makes the to-do again **with its old id**.

- Only the last delete, only for 15 minutes (`UNDO_SECONDS`), only for the user who deleted it.
- Only the message whose id matches the snapshot shows the Undo button.
- The list page drops a snapshot that is too old (`drop_expired`), so old to-do text does not stay.

## Consequences

- Easy: no migration, and no query had to change.
- Safe: logout empties the session, so another person on the same browser cannot undo.
- Rule: `SNAPSHOT_FIELDS` must list every `Todo` field. A unit test checks it.
- Rule: Delete reads the to-do inside its transaction. Code review found that a double click
  could otherwise snapshot a stale object after the cascade, and Undo would restore it without
  its steps and tags (fixed before merge, PR #51).
- Limit: only the last delete can be undone, and not after logout.
- Limit: if the restored to-do does not match the page's filter, its row is not shown, and the
  page opens at the top (accepted).
- Privacy: the snapshot (title, notes, tags, steps) sits in the session table until it is replaced,
  dropped, or the person logs out. If the session just expires, its row (with the snapshot) stays
  in the database, because nothing runs `clearsessions` (a known gap). See
  [Data inventory](../design/data-inventory-and-privacy.md), section 7.

## Alternatives considered

| Option | Why not |
|---|---|
| Soft delete (`deleted_at` field) | A filter in every query that reads to-dos, plus a job that really deletes old rows. Too much risk. Its one benefit, Undo after logout, was not needed. |
| The snapshot in a hidden form field in the page | The browser could change it or send it twice, and another person's data would be in the HTML. |
| A confirm step before Delete | Listed as "Confirm or undo a single Delete" in safe-toggles; the owner chose Undo. A confirm slows every delete. |

## Source

- [`docs/plans/delete-undo.md`](../plans/delete-undo.md), decision 1 and open choice 2 (PR #51).
- `todos/undo.py`, `todos/views.py` (`todo_delete`, `todo_undo_delete`), `todos/context_processors.py`.

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
