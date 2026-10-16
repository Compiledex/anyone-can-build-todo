# Postmortem: PR #12 was merged while a CI run was red

| | |
|---|---|
| Type | Postmortem (blameless) |
| Phase | Production |
| Written by | Incident owner (in this project: the owner and Claude, from the GitHub records) |
| Status | Done (all action items closed) |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A *postmortem* is written after an incident, by the people who
> handled it, to learn from it. *Blameless* means it looks for the gap in the process or the tools,
> not for a person to blame: people make mistakes when the system lets them. Without a postmortem,
> the same incident happens again, and nobody remembers why a rule exists.

## Summary

On 2026-10-09, pull request #12 (Clear completed) was merged into `main` while one of its two CI
runs had a red `test` job. The failure was a *flaky* browser test (one that sometimes fails with
no change in the code). A rerun of the same commit was green two minutes after the merge, so the
code on `main` was fine. But the project rule is "merge only with every check green", and the
merge command did not stop. The cause was fixed in two follow-up PRs, and a GitHub ruleset now
enforces the rule.

## Impact

- **Users:** none. The app runs only on the owner's Mac, and the merged code was correct.
- **Risk:** high in principle. If the failure had been real, broken code would have been on `main`,
  and every later branch would start from it.
- **Time lost:** the flaky test failed once more on another PR the same evening (see timeline).

## Timeline

Times are Tokyo time (UTC+9), from the GitHub API (PR timeline and Actions runs). Seconds are
rounded.

| Time (2026-10-09) | Event |
|---|---|
| 21:40 | PR #12 opened. Two CI runs start for commit 57f3712: a `push` run (37931566939) and a `pull_request` run (37931575621). |
| 21:41 | The `push` run's `test` job fails (first attempt). `lint` passes. |
| 21:44 | The `pull_request` run passes (both jobs). |
| 21:44 | **PR #12 merged**, with the `push` run still red. |
| 21:45-21:46 | The `push` run is rerun: green. |
| 22:49 | The same kind of failure on PR #15 (run 37939477153). Its rerun at 23:38 is green. |
| 2026-10-10 00:10 | **PR #19** merged: fixes the flaky `test_plan_and_finish`, four more journeys and the sign-up helper with the same pattern. |
| 2026-10-10 00:29 | **PR #22** merged: fixes the same race in `test_break_a_todo_into_steps`. |
| 2026-10-11 13:14 | The GitHub ruleset on `main` is created (`lint` and `test` required). |

The exact time the merge command was made strict is not recorded in the repo; it was after this
incident and before the ruleset.

## Root cause

Two causes together:

1. **The merge step did not stop on a red check.** The merge was done by a command that did not
   check that *every* check run was `SUCCESS`. One green run was enough for it to go on. Nothing
   on GitHub blocked the merge either: `main` had no required checks yet.
2. **Flaky browser tests.** The CUJ (critical user journey) tests use Playwright, a tool that
   drives a real Chromium browser. In Playwright, `click()` waits only until the next page
   *starts* to load. Some tests did the next step (`page.reload()`, or typing into a field)
   straight away. On a slow CI machine, that step could hit the old page, which was going away.
   The error was `Page.reload: Protocol error (Page.reload): Not attached to an active page`
   (PR #19). On the laptop the test always passed, which is why it was not caught earlier.

Why did a flaky test lead to a bad merge? Because when red sometimes means "nothing is wrong",
people and tools learn to look past red. Flaky tests make the safety check worth less.

## What went well

- The code itself was correct; the rerun proved it.
- The flaky test was not hidden or skipped. PR #19 found the real reason in Playwright's
  documented behaviour and fixed the pattern in five journeys and a sign-up helper, with a comment at the top of
  `todos/tests/cuj/test_journeys.py` that explains the rule.
- PR #19 and PR #22 were tested hard: `make cuj` 20 times in a row with a busy CPU, 20 of 20 green.

## What went wrong

- A merge happened against the project's own rule.
- The first flaky failure was not treated as a bug at once; it took a second failure (PR #15) to
  start the fix.
- The old tests could not be made to fail on demand on the laptop, so the fix could not be shown
  failing first. PR #19 says so openly.

## Action items

| # | Action | Owner | Status |
|---|---|---|---|
| 1 | Fix the flaky `test_plan_and_finish` and the same pattern in other journeys: wait with `expect()` for something only on the new page | Claude | **Done**, PR #19 |
| 2 | Fix the same race in `test_break_a_todo_into_steps`, and check every CUJ test for it | Claude | **Done**, PR #22 |
| 3 | Make the merge command refuse unless every check is `SUCCESS` | Orchestrator (Claude) | **Done** (after this incident) |
| 4 | GitHub ruleset on `main`: `lint` and `test` required, no deletion, no force-push | The owner | **Done**, 2026-10-11 (`docs/plans/docs-fixes.md`) |
| 5 | Treat every flaky failure as a bug (S2 for CI), with the [triage process](../bug-reports/README.md) | Everyone | **Done** (written in the [incident runbook](../runbooks/on-call-and-incidents.md), playbook D) |

## Related near-miss: a stacked PR closed when its base branch was deleted

**What happened (real, from the GitHub timeline, 2026-10-09).** PR #14 (priority) was *stacked*
on PR #13 (notes): its base branch was #13's branch, not `main`. At 23:47 Tokyo time, #13 was
merged and its branch was deleted at once. GitHub then **closed #14** automatically, because its
base branch no longer existed. At 23:53 the branch was restored, #14 was reopened and retargeted
to `main`, and the branch was deleted again. #14 merged at 23:55. No code was lost.

**Why it matters.** A closed PR can look "done" in a list. If nobody had noticed, priority (and
the tags PR #15 stacked on it) would have been left out of `main`.

**Rule since then:** retarget every child PR to `main` **before** deleting a base branch. It was
already used minutes later: #15 was retargeted (23:55:13) before #14's branch was deleted
(23:55:16), and the search and recurring PRs (#17, #18) before #15's branch.

## Related documents

- [On-call and incident runbook](../runbooks/on-call-and-incidents.md)
- [Bug triage process](../bug-reports/README.md)
- [Retrospective](../retrospectives/2026-10-16-project-retrospective.md)
- [Test plan](../process/test-plan.md), [PR review by risk](../process/pr-review-by-risk.md)
- Plans: [`clear-completed.md`](../plans/clear-completed.md), [`test-pyramid.md`](../plans/test-pyramid.md);
  PRs #12, #13, #14, #15, #19, #22
