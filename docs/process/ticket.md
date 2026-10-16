# Ticket TODO-51: Undo after deleting a to-do

| | |
|---|---|
| Type | Ticket (a work item in an issue tracker) |
| Phase | Build |
| Written by | Product manager or tech lead (in this project: written now by Claude from the owner's decision B, the plan and PR #51; the project had no tracker) |
| Status | Done |
| Date | 2026-10-16 |
| Data | MIXED (see below) |

> **What this document is.** A ticket is one small piece of work in an issue tracker (a tool such
> as a shared board where each piece of work is a card). A product manager or tech lead files it
> before the work starts, so everyone agrees on *what* "done" means. Without tickets, work is
> lost, done twice, or finished without anyone knowing what was promised.

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

This project never used an issue tracker: the owner made product decisions in chat, and each
feature got a plan in `docs/plans/`. This page shows how the same work would look as a ticket.
The ID, priority, estimate, labels and dates of the board are simulated. The user story and the
acceptance criteria are real: they come from the "Decided by the person" section of
`docs/plans/delete-undo.md` and from PR #51.

## The ticket

| Field | Value |
|---|---|
| ID | TODO-51 (simulated; the number matches PR #51 to make it easy to follow) |
| Title | Undo after deleting a to-do |
| Type | Feature |
| Reporter | The owner (real: product decision B in PR #47, "the person's product choices") |
| Assignee | Implementer agent (real: Claude built it on the branch `feature/delete-undo`) |
| Priority | P2, medium (simulated) |
| Estimate | 3 story points, about one working day (simulated) |
| Labels | `feature`, `data-loss`, `risk:high`, `no-migration` (simulated) |
| Sprint | Wave "product choices", item B of A to E (real: PR #47 planned A, B, C, D, then E; they merged as D #48, C #49, A #50, B #51, E #52, so A still merged before B, as B needed) |
| Status | Done, merged 2026-10-11 (real: PR #51) |

A **story point** is a rough size, not hours. Teams use it to plan how much fits in a sprint (a
short, fixed period of work, often two weeks).

### User story

> As a person who manages my to-dos, I want an **Undo** button right after I delete a to-do,
> so that a wrong click does not cost me its notes, tags and steps.

### Background

Before this work, Delete removed a to-do at once, with its steps, and there was no way back
(real: `docs/plans/delete-undo.md`, "What is wrong today"). The safe-toggles plan had listed
"Confirm or undo a single Delete" under "Left for the person". The owner then chose an Undo
button (real: decision B in PR #47).

### Acceptance criteria

Acceptance criteria are the checks that must all be true before the ticket can close. These come
from the plan's rules and the owner's decisions (real).

- [x] Delete removes the to-do at once and shows "Deleted “<title>”." with an Undo button.
- [x] The Undo button sends a `POST` with a CSRF token. A `GET` gives 405.
- [x] Undo brings back the title, notes, priority, due date, repeat, done state, tags, steps (and
      which steps were done), the place in the list, and the recurring links where they are still
      free. It keeps the same id, so the page opens at the restored row (`#todo-<id>`).
- [x] Only the person who deleted it can undo it, only once, and only for 15 minutes.
- [x] Only the last delete can be undone. When two "Deleted" messages show, only the last one has
      a button.
- [x] A stranger gets 404, the same as for a thing that does not exist.
- [x] If the list was deleted, or the person can no longer see it, nothing is made, and the
      message says "Could not undo: you can no longer see the list it was in."
- [x] If another to-do now has the same id: "Could not undo." The other to-do is not touched.
- [x] Titles in the messages are escaped (a title like `<b>x</b>` shows as text).
- [x] Tags of a restored to-do belong to the list owner, also when a member undoes.
- [x] No migration. Tests in all three layers, shown failing before the code.

### Out of scope

Undo for "Clear completed", for deleting a list or a step, for an edit; more than one delete;
keeping Undo after logout (real: the plan's "Not part of this task").

### Links

| Link | Where |
|---|---|
| Task plan | `docs/plans/delete-undo.md` (see [task-plan.md](task-plan.md)) |
| Pull request | PR #51, branch `feature/delete-undo` |
| Test plan | [test-plan.md](test-plan.md) |
| Depends on | TODO-50 (recurring copy rules, PR #50): it adds `copy_fingerprint`, which the snapshot must keep |
| Blocks | TODO-52 (cleanups, PR #52): it changes the row template and must keep the Undo form |

### Comments (simulated)

> **Sofie (QA):** Does Undo work when the to-do was a repeating copy? Please add a test.
>
> **Tomas (tech lead):** Yes, `test_recurring_links_come_back` covers both directions. Marking as
> risk:high, because it writes data back and touches access control.

## Other tickets in this project (simulated IDs, real PRs)

Each ID is invented, but the feature and the PR are real (`gh pr list --state merged`).

| Ticket | Title | PR | Merged |
|---|---|---|---|
| TODO-7 | Accounts: sign up, log in, see only your own to-dos | #7 | 2026-10-09 |
| TODO-11 | Share a list with other users by username | #11 | 2026-10-09 |
| TODO-12 | Clear completed: delete all done to-dos of a list | #12 | 2026-10-09 |
| TODO-20 | Repeat a to-do every day, week or month | #20 | 2026-10-09 |
| TODO-25 | Drag and drop for a manual order | #25 | 2026-10-10 |
| TODO-48 | Make a daily backup when `make run` starts | #48 | 2026-10-11 |
| TODO-49 | List names ignore case for every letter, also æ, ø, å | #49 | 2026-10-11 |
| TODO-50 | Recurring: Undo keeps a changed copy | #50 | 2026-10-11 |
| TODO-52 | Cleanups: rename `/` view to `home`, lighter list HTML | #52 | 2026-10-11 |
| BUG-19 | Flaky CUJ test `test_plan_and_finish` | #19 | 2026-10-09 |

## Related documents

- [task-plan.md](task-plan.md): how this ticket became a reviewed plan and five commits
- [pull-request-description.md](pull-request-description.md): the PR that closed it
- [pr-review-by-risk.md](pr-review-by-risk.md): why it was reviewed as high risk
- [test-plan.md](test-plan.md): the tests for each acceptance criterion
- [../product/prd.md](../product/prd.md): the product requirements behind the features
- [../bug-reports/README.md](../bug-reports/README.md): how bug tickets are triaged
- [../../.github/ISSUE_TEMPLATE/feature_request.md](../../.github/ISSUE_TEMPLATE/feature_request.md): the template for a new ticket
- [../plans/delete-undo.md](../plans/delete-undo.md): the real plan
