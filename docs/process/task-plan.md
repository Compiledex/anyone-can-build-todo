# Task plan: Undo after deleting a to-do

| | |
|---|---|
| Type | Task plan (also called an implementation plan or technical spec) |
| Phase | Build |
| Written by | The engineer who builds the feature, reviewed by another engineer (in this project: a planner agent wrote it, an independent reviewer agent reviewed it, the owner approved it) |
| Status | Done (the plan's Status line: done 2026-10-11) |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A task plan says *how* a ticket will be built, before any code is
> written: what changes, which choices were made and why, which tests prove it, and what could go
> wrong. The engineer writes it; a reviewer and the decision maker approve it. Without one,
> design mistakes are found in code review, when they are expensive to fix.

## Task plans in this project

In this project, every feature has a task plan in `docs/plans/<feature>.md` (33 plans today).
They follow one shape, and one rule from `AGENTS.md`: a plan is **history**. It says what was
decided and why. When the plan and the code disagree later, the code wins; only the plan's
Status line is changed after it is built.

The life of a plan:

1. A planner writes it on `main`, and checks every fact against the code (with the commit, here
   `d66b978`).
2. An independent reviewer tries to break it (an *adversarial* review), sometimes with small
   prototypes. Its verdict is APPROVE, APPROVE WITH CHANGES, or REJECT.
3. The owner reads a short summary (the "plan card") and answers the open choices marked PERSON.
4. The plans are merged as docs (here PR #47, five plans A to E together).
5. The implementer builds it on a branch; the last commit sets `Status: **done** (<date>)`, and
   a "Built" section lists what turned out different.

## How `docs/plans/delete-undo.md` is structured

| Section | What it holds in this plan |
|---|---|
| Status, Builds on | Done 2026-10-11. Builds on edit, steps, tags, recurring, drag and drop, sharing, safe toggles, and plan A (`copy_fingerprint`). |
| Words used in this plan | Session, snapshot, soft delete, AUTOINCREMENT. Defined before they are used. |
| What is wrong today | Facts checked on `main`: Delete deletes at once; steps go with it (`CASCADE`). |
| Goal | One paragraph: what the person sees after Delete and after Undo. |
| Decisions 1 to 7 | 1: a snapshot in the session, not a soft delete (with the reasons against the other options). 2: what the snapshot holds. 3: Delete. 4: the Undo button. 5: the Undo view, step by step. 6: how `restore` makes the rows. 7: what the person sees. |
| Security | One line per rule: own data plus shared, POST and CSRF, open redirect, no injection, only once, never overwrite another to-do. |
| Data and migrations | None. How to go back: revert the commit. |
| Working next to | The other plans in the wave and the merge order. |
| Not part of this task | Undo for Clear completed, for a list, a step, an edit. |
| Changes to files | A table: each file and its change. |
| Steps | Tests first, then the code, then the browser test, then docs. |
| Tests | Three tables (unit, integration, CUJ): each test, what it checks, and "the break that fails it". |
| Decided by the person | The owner's rules, dated 2026-10-11. |
| Open choices | Four choices, each with a recommendation. Two marked PERSON. |
| Known limits | An old Undo button in a second tab gives 404; steps get new ids. |
| Review | What the planner verified, and what the plan review changed. |
| Built | What turned out different when it was built. |

The column "the break that fails it" is worth copying. For each test it names the bug the test
is there to catch. A test with no such bug is not needed.

## How the plan review changed the plan

The plan review (2026-10-11) said APPROVE WITH CHANGES. Five changes, all real:

| Found by the review | Change to the plan |
|---|---|
| Django saves the session *after* the view, outside the database transaction, so two posts close together can both read the snapshot. | The "id already exists" check now runs first inside the transaction. It is the real guard. New test: put the old session back and Undo twice. |
| The plan said SQLite never reuses ids. Wrong: a table rebuild by a migration resets the counter (`sqlite_sequence`). | If the id belongs to another to-do: "Could not undo." and nothing is touched (an owner choice). |
| Messages were `<p>` elements; a `<form>` cannot be inside a `<p>`. | Messages become `<div>`. The form shows only when a snapshot exists (no `{% url %}` with an empty id, which would be a 500 page). |
| One button for two "Deleted" messages would be confusing. | The message tag carries the deleted id; only the matching message gets a button, through a small context processor. |
| An expired snapshot stayed in the session with the to-do's text. | The list page drops an expired snapshot. |

## The tasks, as they were done

Breaking work into tasks makes each step small enough to check. Here are the real commits of
PR #51 (`gh pr view 51 --json commits`), in order, on 2026-10-11 (Tokyo time).

| # | Commit | Task | Files |
|---|---|---|---|
| 1 | `75b49b0` Add Undo after deleting a to-do | Tests first (the plan expected them to fail: no module, no URL, no message), then `todos/undo.py`, the views, the URL, the context processor, `base.html`, `app.css`, the CUJ journey, `AGENTS.md`. | 11 files, +700 |
| 2 | `c6cacf9` Mark the delete-undo plan done | Status line and the "Built" section. | 1 |
| 3 | `57dec28` Apply the delete-undo code review | Delete reads the to-do inside its transaction; Undo finds the list inside its transaction; the button's label is "Undo delete: <title>"; two new guard tests. | 7 files, +94 |
| 4 | `e02ffda` Merge origin/main into feature/delete-undo | Brings in C, A and D. `SNAPSHOT_FIELDS` gets `copy_fingerprint` (the unit test failed until it did). | merge |
| 5 | `b1745b0` Check that Undo keeps a recurring copy's fingerprint | A restored copy that was not changed still counts as unchanged. | 1 test file |

Note on task 1: the plan's steps were "tests first, then code", but tests and code are in one
commit. The commit message says why: the tests import `todos.undo` and use the new URL, so they
cannot pass on their own. PR #51 says the tests "were shown failing before the code": the
failing run was shown, not saved as a commit.

## Estimate against reality

The plan has no time estimate; this project does not estimate. The ticket's "3 points" in
[ticket.md](ticket.md) is simulated. What is real: the PR's commits span 17:21 to 17:43 on
2026-10-11, and it merged at 17:46 (Tokyo), the same day as the plan.

## Related documents

- [ticket.md](ticket.md): the ticket this plan builds
- [pull-request-description.md](pull-request-description.md): the PR made from these commits
- [pr-review-by-risk.md](pr-review-by-risk.md): the review the PR got
- [test-plan.md](test-plan.md): the tests from the plan's tables, as they were built
- [../design/design-doc.md](../design/design-doc.md) and [../adr/README.md](../adr/README.md): the bigger design choices
- [../plans/delete-undo.md](../plans/delete-undo.md): the plan itself; PR #47 (the plans), PR #51 (the code)
