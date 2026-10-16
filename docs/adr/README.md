# Architecture decision records

| | |
|---|---|
| Type | Architecture decision record (index and template) |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** An **architecture decision record** (ADR) is a short note about one
> important technical choice: what problem we had, what we chose, what it costs, and what else we
> looked at. Engineers write one when they make a choice that is hard to change later. Without
> ADRs, a new person sees only the code, not the reasons, and may "fix" a choice that was made on
> purpose.

## How we use ADRs here

- One ADR is one decision. It is short (one page).
- An ADR is never rewritten after it is accepted. If the decision changes, write a **new** ADR
  that says "Supersedes 000N", and set the old one to "Superseded by 000M".
- The detailed reasoning is in the feature plans in [`docs/plans/`](../plans/). An ADR is the
  short summary that points there. The plans are history; the code on `main` wins.
- The ADRs below were written after the code was built (2026-10-16), from the plans and PRs. At a
  real company they are written at the time of the decision.

## Status values

| Status | Meaning |
|---|---|
| Proposed | Written, not yet agreed. |
| Accepted | Agreed, and the code follows it. |
| Superseded | Replaced by a newer ADR (named in the status). |
| Deprecated | No longer true, and nothing replaced it. |

## Template

Copy this into `NNNN-short-title.md` (the next free number):

```markdown
# NNNN. <Decision in a few words>

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | <roles of the people who decided> |
| Status | Proposed / Accepted / Superseded by NNNN |
| Date | YYYY-MM-DD |
| Data | REAL |

> **What this document is.** One or two sentences: which choice this ADR is about.

## Context
What problem do we have? What forces matter (safety, time, size, people)?

## Decision
What we chose, in one or two sentences, then the details.

## Consequences
What gets easier, what gets harder, and what we must now always do.

## Alternatives considered
| Option | Why not |
|---|---|

## Source
The plan, PRs and files where this is decided and built.
```

## Index

| ADR | Decision | Source |
|---|---|---|
| [0001](0001-server-rendered-django.md) | Server-rendered Django pages, almost no JavaScript | foundation, drag-and-drop (PR #5, #25) |
| [0002](0002-sqlite-immediate-transactions.md) | SQLite, with `IMMEDIATE` transactions | recurring (PR #20) |
| [0003](0003-404-for-other-peoples-data.md) | 404, not 403, for other people's data | accounts, sharing (PR #7, #11) |
| [0004](0004-today-in-asia-tokyo.md) | "Today" is the date in `Asia/Tokyo` | due-date (PR #10) |
| [0005](0005-delete-undo-session-snapshot.md) | Delete undo with a session snapshot, not a soft delete | delete-undo (PR #51) |
| [0006](0006-recurring-copy-fingerprint.md) | A fingerprint, not an "edited" flag, to see a changed copy | recurring-copy-rules (PR #50) |
| [0007](0007-list-name-key.md) | Unique list names through a stored `name_key` | list-name-casefold (PR #49) |
| [0008](0008-mac-notifications-via-osascript.md) | Reminders as Mac notifications through `osascript`, no email | reminders (PR #26, #27) |

## Related documents

- [Design doc](../design/design-doc.md): the whole technical design; it links to each ADR.
- [Data inventory and privacy](../design/data-inventory-and-privacy.md)
- [Product requirements](../product/prd.md)
- [Feature plans](../plans/)
