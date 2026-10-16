# PR review by risk

| | |
|---|---|
| Type | Code review policy (risk-based review guideline) |
| Phase | Build |
| Written by | Tech lead or engineering manager (in this project: the owner and Claude; the reviews were done by independent reviewer agents) |
| Status | In use |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A review policy says how carefully a change must be checked before
> it is merged, based on how much harm it could do. A tech lead writes it once and the team uses
> it on every PR. Without it, every PR gets the same quick look: a typo fix waits as long as a
> migration, and a risky change gets too little attention.

## Words used here

- **Adversarial review**: a reviewer who did not write the code tries to *break* it, not just
  read it. It gives a verdict: PASS, PASS WITH FIXES, or FAIL.
- **Mutation testing**: the reviewer makes a small, deliberate bug (a *mutant*) in the code, for
  example removes a check, and runs the tests. If a test fails, the mutant is *caught*. If all
  tests still pass, the tests have a gap.
- **Migration round trip**: run a migration forward, back, and forward again, on a *copy* of the
  owner's database, never on `db.sqlite3` itself.
- **Strict all-green CI**: merge only when every check is SUCCESS. CI (continuous integration)
  is GitHub running the checks on every push: here the jobs `lint` and `test`
  (`.github/workflows/check.yml`). A GitHub ruleset on `main` requires both.

## The risk levels

Pick the level of the riskiest file in the PR. When unsure, go one level up. These levels and
the table below write down what the PRs of this project really did (examples below); they were
not a written rule before this document.

| Level | What it touches | Examples of files |
|---|---|---|
| Low | Docs, comments, CSS that changes no layout rule, test-only refactors | `docs/`, `README.md`, `AGENTS.md`, `*.css` |
| Medium | Views, forms, templates, queries; behaviour a person sees, but no stored data changes shape | `todos/views.py`, `todos/forms.py`, `todos/templates/` |
| High | The data model and migrations, access control (who sees what), backups, anything that deletes or rewrites data, sessions, security settings | `todos/models.py`, `todos/migrations/`, `todos/undo.py`, `todos/backup.py`, `config/settings.py` |

## What each level requires

| Check | Low | Medium | High |
|---|---|---|---|
| A plan in `docs/plans/`, reviewed and approved by the owner | No | Yes | Yes, plan review with prototypes |
| Tests shown failing before the code | Not needed | Yes | Yes |
| `make check` passes (commit checks, migration check, all tests) | Yes | Yes | Yes |
| Adversarial code review | No | Yes | Yes |
| Mutation testing | No | Yes, a small set | Yes, a full set (PRs #48 to #51 ran 22 to 33); every survivor gets a guard test or a reason |
| Each guard test shown failing against its mutant | No | Yes | Yes |
| Rendering check (screenshots, accessibility tree) | If the look changes | If the look changes | If the look changes |
| Migration round trip on a copy of the owner's database | No | No | Yes, if there is a migration |
| "`make backup` before `migrate`" in the PR | No | No | Yes, if there is a migration |
| Strict all-green CI before merge | Yes | Yes | Yes |

Strict all-green CI is required at every level because of a real incident: PR #12 was merged
while one CI run was red (a flaky browser test). The rerun was green, but since then the merge
refuses unless every check is SUCCESS, and later the ruleset on `main` enforces it. PR #19 and
PR #22 fixed the flaky tests.

## Real examples

### Low: PR #53 (docs only)

"Docs: fix three places where AGENTS.md and README disagreed with the code". It changed only
`AGENTS.md` and `README.md`. The PR says: "Docs only ... no code and no migration. `make check`
passes (731 tests)." No plan, no adversarial review, no mutations. The check that still matters:
each docs claim was compared with the code (the test counts, `todo_toggle`, the test runner).

### Medium: PR #52 (cleanups)

It renamed a view, changed the row template to one form per row, and shortened `AGENTS.md`.
Nothing a person can see should change, so the review checked exactly that:

- PASS WITH FIXES, 19 of 20 mutations caught.
- Screenshots at 1280px and 375px, light and dark, of 4 pages (16 pairs), pixel-identical to
  `main`; the accessibility tree identical; the posted form bodies the same as on `main`, with
  JavaScript on and off.
- Safety: `@login_not_required` still only on the four open views (a test checks it).

It is medium, not low, because the forms that send Done and Delete changed.

### High: PR #49 (list names, with migrations)

It changed the data model and added three migrations, one of them a hand-written data migration
that renames duplicate lists. From the PR:

- Section heading "Migrations — run `make backup` before `migrate`".
- "Tested forward, back to 0018, and forward again on a copy of the person's database: OK, and
  the person's only list "Inbox" is unchanged."
- PASS WITH FIXES, 22 mutations; four test gaps closed, each new test shown failing against its
  mutant.

### High: PR #51 (delete and undo)

No migration, but it deletes data, writes data back, and decides who may do that. So: high.

- PASS WITH FIXES, 28 mutations, 24 caught.
- No round trip (no migration), but the plan review checked AUTOINCREMENT in a scratch database
  made by `migrate`, not the owner's file.
- One real bug found before merge: a double click on Delete could let the second request
  snapshot a stale copy of the to-do after the delete, so Undo would bring it back without its
  steps and tags. Fixed by reading the to-do inside the transaction (commit `57dec28`).

## Example: the review findings of PR #51 and their guard tests

The PR body gives the totals (28 mutants, 24 caught) and the findings, not each mutant. The
"possible mutant" column below is our description of the kind of bug each guard test catches,
based on the PR body, commit `57dec28` and the tests. It is not a copy of the reviewer's log.

| Finding (PR #51) | Possible mutant | Guard test (`test_delete_undo.py`) |
|---|---|---|
| A double-delete race that emptied the snapshot | Read the to-do *before* `transaction.atomic()` in `todo_delete` | `test_double_delete_does_not_replace_the_snapshot` |
| A stranger posting Undo for an existing to-do | Find the "already restored" to-do without the visible-to filter | `test_stranger_gets_404_for_an_existing_todo` |
| Another user's snapshot in the session | Drop the `snapshot["user"]` check | `test_snapshot_of_another_user_is_not_offered_or_used` |
| The Undo button's accessible name | Label it "Undo: <title>", like a row's Undo | `test_undo_button_names_the_deleted_todo` |
| The list access check moved inside the transaction | Find the list outside the transaction (a code change; the PR names no new test for it) | none new |
| AGENTS.md | (docs, no mutant) | none |

A good mutation table in a real review has these columns, one row per mutant: the mutant, the
file and line, caught or survived, and the test that caught it (or the new guard test).

## When the reviewer and the author disagree

The reviewer's findings are fixed, or the PR says why not (for example a "Known limit"). The
orchestrator merges only after the review verdict is PASS or PASS WITH FIXES with all fixes
pushed, and CI is all green.

## Related documents

- [pull-request-description.md](pull-request-description.md): where the "Review" part of a PR
  reports this
- [test-plan.md](test-plan.md): the tests that the mutants are run against
- [task-plan.md](task-plan.md): the plan review, the first review of a high-risk change
- [../postmortems/2026-10-09-merged-with-red-ci.md](../postmortems/2026-10-09-merged-with-red-ci.md): the incident behind the strict CI rule
- PR #12, PR #19, PR #22, PR #49, PR #51, PR #52, PR #53
