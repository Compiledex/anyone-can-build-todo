# Retrospective: the first week (2026-10-09 to 2026-10-16)

| | |
|---|---|
| Type | Project retrospective |
| Phase | Analysis |
| Written by | Engineering manager or team lead, with the whole team (in this project: the owner and Claude) |
| Status | Done |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A team writes a retrospective (a "retro") at the end of a project
> or a period of work. Everyone looks back together: what went well, what did not, and what to
> change next time. It is blameless: it talks about the process, not about who made a mistake.
> Without it, the same problems come back in the next project.

All numbers here are real. Each one names its source: a PR number, a plan in `docs/plans/`, or a
file in the code. Nothing is estimated.

## 1. What we built

| Part | PRs | Dates |
|---|---|---|
| Test pyramid (unit, integration, CUJ layers) | #1, #2 | 2026-10-09 |
| Plans for the 17 features and the foundation | #3, #4 | 2026-10-09 |
| The 17 features, in waves: foundation, dark mode, accounts, lists, edit, due date, sharing, clear completed, notes, priority, tags, steps, recurring, search, filter, sort, drag and drop, Mac reminders | #5 to #27 | 2026-10-09 to 2026-10-10 |
| Design: row layout fix, landing page, login and sign-up, app redesign, README screenshots | #28 to #33 | 2026-10-10 to 2026-10-11 |
| Audit improvements: safe settings, docs fixes, Norwegian letters, Undo keeps a copy with a done step, local safety, safe toggles, accessibility, maintenance | #34 to #46 | 2026-10-11 |
| The owner's product choices A to E: recurring copy rules, Undo after Delete, list names ignore case, daily backup on `make run`, cleanups | #47 to #52 | 2026-10-11 |
| Docs fixes | #53 | 2026-10-16 |

Numbers (from `gh pr list --state all`):

- 53 pull requests: **51 merged**, 2 closed (#17 and #18 were replaced by #21 and #20).
- 33 plans in `docs/plans/` (plus one HTML mockup), each with Status **done**.
- Tests: 32 after the foundation (PR #5), 188 after PR #12, 517 after the redesign (PR #32), 634
  after the maintenance pass (PR #46), **731** now (PR #52 and #53: CUJ 30, Integration 577,
  Unit 124).
- During the product choices A to E the count went from 634 (PR #46) to 656 (PR #48), 672
  (PR #49), 695 (PR #50), 727 (PR #51) and 731 (PR #52).
- PR #52 made the list page with 300 to-dos 25 % smaller (594,081 to 445,581 bytes; 905 to 605
  forms) and `AGENTS.md` shorter (50,093 to 23,163 bytes; `docs/plans/cleanups.md`).

## 2. How we worked

1. **A plan per feature**, written before the code, in `docs/plans/`.
2. **Adversarial plan review**: a separate agent tried to break the plan, often with small
   prototypes (example: PR #47, "all APPROVE WITH CHANGES; 18 findings applied").
3. **A plan card**: the owner approved each plan and answered its open choices. The answers are
   in each plan's "Decided by the person" section.
4. **Tests first**: each new test was shown failing before the code.
5. **Code review with mutation testing**: a reviewer agent broke the code on purpose (a
   "mutation") and checked that some test failed. Example: PR #46 ran 38 mutations.
6. **A merge queue**: the orchestrator merged one PR at a time, rebased the next, and remade
   migrations when two branches clashed (for example `0012_tags` in PR #15).
7. **Strict green CI**: GitHub runs `lint` and `test` (`.github/workflows/check.yml`); a ruleset
   on `main` requires both.

## 3. Went well

| What | Evidence |
|---|---|
| Code review found real bugs before merge | PR #51: a double click on Delete could save an empty snapshot, so Undo brought the to-do back without its steps and tags. Fixed by reading the to-do inside the transaction. |
| | PR #48: `except FileExistsError` also caught "backups is a file", so a failed backup said "Today's copy is already there" and gave no warning. Also `\d` matched non-ASCII digits; now `[0-9]`. |
| | PR #32: row buttons were only 4 px apart on a phone (a CSS specificity mistake). |
| Plan review found bugs before any code | PR #4: two plans used `todo_list.pk` where the page key is `the_list` (a `NoReverseMatch` error); "Show all" lost the sort order; the recurring rules disagreed with their own tests. |
| | `docs/plans/delete-undo.md`: the claim "ids are never reused" was wrong (a table rebuild resets `sqlite_sequence`); the plan now handles a taken id. |
| Mutation testing made tests stronger | Most PRs report how many mutations were caught. PR #48: 33 run, 28 caught; PR #51: 28 run, 24 caught; PR #52: 20 run, 19 caught. Each missed one got a guard test. |
| The owner made the product choices; agents did the rest | Every plan has "Decided by the person". The owner let the orchestrator merge after review and green CI. |
| A refactor changed nothing visible | PR #52: 16 screenshot pairs pixel-identical to `main`, same accessibility tree. |
| Fast | 17 features in about two days (PR #5 to #27), everything in three working days. |

## 4. To improve

| What happened | Effect | What we changed |
|---|---|---|
| PR #12 (Clear completed) was merged while one CI run was red, from a flaky browser test. The rerun was green. | The rule "only merge on green" was broken once. | PR #19 and PR #22 fixed the two flaky CUJ tests (Playwright's `click()` does not wait for the new page; now `expect()` waits). The merge command refuses unless every check is SUCCESS; later the ruleset on `main` enforces it. |
| Deleting the base branch of a stacked PR made GitHub close the child PR (tags, stacked on priority, PR #15). | The branch had to be restored, the PR reopened and retargeted to `main`. | Rule: retarget children before deleting a base branch. |
| A safety hook refused force-pushes. | Work moved to new `-v2` branches (PR #41, PR #44); old branches stayed on GitHub for a while. | Never retry a refused command; use a new branch. The old branches were later deleted. |
| A wrong assumption: "SQLite never reuses row ids". | Undo after Delete could have restored over another to-do. | Found in plan review; `docs/plans/delete-undo.md` says "Could not undo." and touches nothing. |
| Two sessions "resumed" the rollout at once (2026-10-10) and both rebased the same PRs. | Duplicate work. | The owner decided one orchestrator session finishes the rollout; check `gh pr list` and `git worktree list` first. |
| After a merge with a migration, the owner's database was not migrated once. | The owner saw an `OperationalError`. | After every merge with a migration: test it on a copy of `db.sqlite3`, then migrate. |
| Docs drifted from the code. | Fixes were needed in PR #4, #35 and #53. | `AGENTS.md` must change in the same PR as the code; plans are history. |
| `AGENTS.md` grew to 50 KB. | Hard to read, for people and agents. | PR #52 cut it to 23 KB; details went into docstrings. |
| Many agents per feature (planner, plan reviewer, implementer, code reviewer, merge queue). | Good quality, but much time and cost per small change. We did not measure the cost. | Open (action 6). |
| Old open tabs get a plain 400 after PR #44 changed the Done/Undo form. | A small surprise; reloading fixes it. | Accepted as a known limit. |

## 5. What we learned

- An adversarial reviewer finds more than the author, both for plans and code.
- "Shown failing first" proves a test can fail. Mutation testing proves the other tests can too.
- Flaky tests are bugs. One red run must stop the merge, even if a rerun is green.
- Write down a decision when it is made (the plan's "Decided by" section), or it gets lost.
- On a local app, the real "production" risk is the owner's own data: backups (PR #43, #48)
  and migrations matter more than servers.

## 6. Actions

| # | Action | Owner (role) | Status |
|---|---|---|---|
| 1 | Fix the flaky CUJ tests | Test engineer | Done (PR #19, PR #22) |
| 2 | Merge only when every check is SUCCESS; ruleset on `main` requires `lint` and `test` | Orchestrator / repo admin | Done (ruleset on `main`) |
| 3 | Retarget stacked PRs before deleting their base branch | Orchestrator | Done (rule in the process notes) |
| 4 | Back up the database automatically | Tech lead | Done (PR #43 `make backup`, PR #48 daily copy on `make run`) |
| 5 | Shorten `AGENTS.md` and keep it in step with the code | Tech lead | Done (PR #52, PR #53) |
| 6 | Measure the time and cost of one feature through the whole agent process, and try a lighter process for docs-only changes | Engineering manager | Open |
| 7 | Add a check that warns when `db.sqlite3` has unapplied migrations before `make run` | Tech lead | Open (idea, not planned) |
| 8 | Write the fuller documentation set the owner asked for | Owner and Claude | In progress (the folders under `docs/`) |

## Related documents

- [Tracking plan](../product/tracking-plan.md)
- [Experiment doc](../product/experiment-doc.md)
- [Postmortems](../postmortems/)
- [Changelog (release notes)](../../CHANGELOG.md)
- [Test plan](../process/test-plan.md)
- [PR review by risk](../process/pr-review-by-risk.md)
- Plans: [`docs/plans/`](../plans/), especially [`delete-undo.md`](../plans/delete-undo.md),
  [`backup-on-run.md`](../plans/backup-on-run.md), [`cleanups.md`](../plans/cleanups.md)
- PRs: #12, #19, #22, #32, #47, #48, #51, #52, #53 on GitHub (Compiledex/anyone-can-build-todo)
