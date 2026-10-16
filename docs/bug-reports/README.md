# Bug reports and triage

| | |
|---|---|
| Type | Bug triage process |
| Phase | Production |
| Written by | Engineering manager (in this project: the owner and Claude) |
| Status | Approved |
| Date | 2026-10-16 |
| Data | MIXED (see below) |

> **What this document is.** A team writes down how bugs are reported and sorted, so every bug
> gets the same care and the worst ones are fixed first. *Triage* means sorting by how bad
> something is, like in a hospital. Without it, bugs are lost in chat, or a cosmetic bug is fixed
> while data is being lost.

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

The process, the template and the severity levels are real rules for this project. Only the
meeting cadence is simulated (marked).

## How to file a bug

File it as a GitHub issue with the label `bug` (it exists in the repo), or as a file
`BUG-00N-short-name.md` in this folder when the bug was found and fixed in a pull request.
Copy this template:

```markdown
# BUG-00N: <what goes wrong, in one line>

- Severity: S1 / S2 / S3 / S4
- Found: <date>, <how: code review / test / by hand / bug bash>
- Status: Open / Fixed in PR #N / Won't fix

## Steps to reproduce
1. ...
2. ...

## Expected
What should happen.

## Actual
What happens instead. Copy the exact message.

## Environment
Commit (`git log --oneline -1`), browser and its version, light or dark mode, window width.

## Evidence
A screenshot, the terminal output, or a failing test. Never your real password or real data.
```

Good titles say what breaks, not what you feel: "Undo after a double Delete loses the steps", not
"Undo is broken".

## Severity levels

| Level | Meaning | Examples in this app | Response rule |
|---|---|---|---|
| S1 | Data loss, or a person sees data that is not theirs (security) | Another user's list opens; a backup is lost; `make reset` deletes without asking | Stop all other work. Follow the [incident runbook](../runbooks/on-call-and-incidents.md). Fix the same day. Nothing else is merged first. |
| S2 | A main journey is broken, or data is wrong, with no easy workaround | Undo brings back a to-do without its steps; a failed backup says it worked | Fix before the next merge to `main`. |
| S3 | A feature is wrong, but there is a workaround | A sort order is wrong for one letter; a message is unclear | Plan it for the next release. |
| S4 | Cosmetic: how it looks, not what it does | Two labels overlap at one width | Fix when convenient, or batch several. |

When unsure between two levels, pick the higher one. A bug can move up later (for example an S3
that turns out to lose data becomes S1).

## The flow

```
New -> Triaged (severity + label) -> In progress (branch + failing test) -> Fixed (PR merged) -> Verified
                                  \-> Not a bug / Duplicate / Won't fix (with a reason)
```

1. **Reproduce.** Follow the steps on a scratch account. If you cannot reproduce it, ask for
   more detail; do not close it yet.
2. **Give a severity and labels.**
3. **Write a failing test first** (a project rule in `AGENTS.md`: show the test failing before the
   fix and passing after). Put it in the lowest layer where a person would notice the bug.
4. **Fix it in its own branch and pull request.** CI must be green (the ruleset on `main` requires
   `lint` and `test`).
5. **Verify** on the real app after the merge, then close.

## Labels

| Label | Exists in the repo? | Use |
|---|---|---|
| `bug` | Yes | Something does not work as designed |
| `accessibility` | Yes | A barrier for people with disabilities |
| `duplicate`, `invalid`, `wontfix`, `question` | Yes (GitHub defaults) | Closing reasons |
| `S1` ... `S4` | No (proposed) | The severity. Until they exist, write the severity in the title: `[S2] ...` |

## Triage meeting (simulated cadence)

A real team meets 2-3 times a week for 15 minutes: the engineering manager, one developer and one
QA person go through every New bug. In this project there is **one person**, the owner, so
"triage" is: when a bug is found (usually by the code reviewer agent), the orchestrator gives it a
severity in the pull request, and the owner sees it on the next plan card or PR review. S1 skips
the meeting: it is handled at once.

## Found in review before merge, or after release

| | Found in code review, before merge | Found after release |
|---|---|---|
| Who was hit | Nobody | Possibly users and their data |
| Where it is written | In the PR body ("Review" section) and its fix commit | A GitHub issue, then a PR |
| Severity | Still given: it tells how much the review saved | Decides how fast to respond |
| Guard test | Required, shown failing against the bug first | Required, same rule |
| Postmortem | No (unless it shows a gap in the process) | Yes for S1, often for S2 |

All three real bug reports in this folder were found **before merge** by the adversarial code
review (a reviewer who tries to break the change, also with *mutation testing*: changing the code
on purpose to see if a test notices). So no user ever met them.

| Report | Severity | Found in | Fixed in |
|---|---|---|---|
| [BUG-001](BUG-001-double-delete-loses-steps-and-tags.md) Double Delete loses steps and tags | S2 | Review of PR #51 | Commit 57dec28, PR #51 |
| [BUG-002](BUG-002-failed-backup-reported-as-success.md) A failed backup said it worked | S2 | Review of PR #48 | Commit 449a3e9, PR #48 |
| [BUG-003](BUG-003-daily-name-matches-non-ascii-digits.md) Daily-name pattern matched non-ASCII digits | S3 | Review of PR #48 | Commit 449a3e9, PR #48 |

## Related documents

- [QA run and bug bash](../process/qa-run-and-bug-bash.md)
- [On-call and incident runbook](../runbooks/on-call-and-incidents.md)
- [Postmortem: merged with red CI](../postmortems/2026-10-09-merged-with-red-ci.md)
- [PR review by risk](../process/pr-review-by-risk.md), [Test plan](../process/test-plan.md)
