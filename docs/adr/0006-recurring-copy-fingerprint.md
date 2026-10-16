# 0006. A fingerprint, not an "edited" flag, to see a changed copy

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-11) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about how Undo on a repeating to-do knows whether someone changed the next copy, so it does
> not throw away their work.

## Context

- A repeating to-do (daily, weekly, monthly) makes its **next copy** when it is marked done
  (`make_next_copy`, PR #20). Undo removes that copy again.
- If someone already worked on the copy (renamed it, added a step, changed the date), removing it
  loses that work. The owner decided: Undo keeps a copy that was changed after it was made, with
  a clear message (recurring-copy-rules, "Decided by the person").
- A copy can be changed in many places: the edit page, Add step, Delete step, the admin, and
  future features.

## Decision

When `make_next_copy` makes a copy, it stores a **fingerprint** in `Todo.copy_fingerprint`: a
SHA-256 hash (a short code computed from data; the same data always gives the same code) of the
copied fields (`COPIED_FIELDS`: title, notes, priority, repeat), the due date, the tag names and
the step titles. Undo computes the hash again (`changed_since_copy`). If it differs, the copy is
kept: "... was kept, because it was changed after it was made."

The hash starts with `FINGERPRINT_VERSION`. If the shape of the hash ever changes, the version
changes too.

## Consequences

- Every way to change a copy is caught, also the admin and later features, without touching their
  views.
- A change that is changed back (add a step, then delete it) is not a change. "Save" with nothing
  changed is not a change.
- Cost: two small queries (tags and steps of one copy) inside the Undo transaction. The list page
  does not change.
- Rule: `make_next_copy` and the fingerprint both read `COPIED_FIELDS`, so they cannot drift. A
  test changes each copied field once and checks the fingerprint changes.
- Safe default: after a version change, every old fingerprint differs, so every old copy is kept.
  Copies made before the field existed have no hash and count as unchanged.
- One new migration (0022) and a field that is `editable=False`.

## Alternatives considered

| Option | Why not |
|---|---|
| An `edited_since_copy` flag set by the edit and step views | Works only where someone remembered to set it (not the admin). Counts a change that was changed back. Would need `form.has_changed()`, which sees "a,b" and "a, b" as different. |
| Always keep the copy on Undo (open choice in the plan, for old copies) | A double click or a wrong Done would leave extra copies. |
| Always remove the copy (the rule before, PR #20) | Loses work that was done on the copy. |

## Source

- [`docs/plans/recurring-copy-rules.md`](../plans/recurring-copy-rules.md), "Why a fingerprint" and open choice 2 (PR #50).
- [`docs/plans/recurring-undo-steps.md`](../plans/recurring-undo-steps.md) (PR #40): keep a copy with a done step.
- `todos/models.py` (`fingerprint`, `COPIED_FIELDS`, `FINGERPRINT_VERSION`, `changed_since_copy`).

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
