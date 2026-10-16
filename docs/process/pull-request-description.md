# Pull request description: Undo after deleting a to-do (PR #51)

| | |
|---|---|
| Type | Pull request description |
| Phase | Build |
| Written by | The engineer who made the change (in this project: Claude, the implementer agent; merged by the orchestrator after review and green CI, with the owner's standing permission) |
| Status | Done (merged 2026-10-11) |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A pull request (PR) asks to merge one branch into `main`. Its
> description is written by the author when the code is ready, for the reviewer and for anyone who
> reads the history later. It says what changed, why, and how we know it is safe. Without it, the
> reviewer has to guess the intent from the diff, and a year later nobody knows why the code is
> the way it is.

## What a good PR description contains

| Part | The question it answers | Needed when |
|---|---|---|
| What | What does the person see that is new or different? | Always |
| Why | Which decision, ticket or bug is this for? A link to the plan. | Always |
| How | The main design choices, in a few lines. Not a copy of the diff. | Code changes |
| Safety | Access control, data loss, security. What could go wrong and why it does not. | Views, data, files |
| Migrations | Which migrations, made by Django or by hand; was a backup made; was it tested forward and back? Write "None." when there are none. | Always (even "None.") |
| Tests | Which tests were added, in which layer; were they shown failing first; the test counts. | Always |
| Review | The reviewer's verdict, its findings, and how each was fixed. | Medium and high risk |
| Screenshots | Before and after, light and dark, wide and narrow. | Visible changes |
| Known limits | What is not handled, on purpose. | When there are any |

Two habits from this project: write "None." instead of leaving a part out (so the reader knows it
was thought about), and give numbers that can be checked (test counts, mutation counts, bytes).

## The real example: PR #51

This is the real description of PR #51, quoted from `gh pr view 51` (our own text). The notes
after each part say why it is there.

### What

> Delete removes a to-do at once and shows "Deleted “…”." with an **Undo** button (decision B of
> the person's product choices). Undo brings the to-do back as it was: the same id, list, place
> in the manual order, created time, notes, priority, due date, repeat, tags, steps (with their
> done states), and the recurring links if they are still free.
>
> Plan: `docs/plans/delete-undo.md`.

**Why it is there:** it starts with what the person sees, not with the code. It names the
decision (B) and links the plan, which is the "Why": the reviewer can read the full reasons there.

### Rules (the person's decisions)

> - It works only for the person who deleted, only once, and only for 15 minutes.
> - Only the last delete's message has the Undo button.
> - If another to-do now has the id: "Could not undo." The other to-do is not touched.
> - If the list is gone or the person can no longer see it: "Could not undo: you can no longer
>   see the list it was in."
> - A stranger gets 404. `GET` gives 405. The form carries a CSRF token.

**Why it is there:** these are the acceptance criteria (see [ticket.md](ticket.md)). The reviewer
checks the code against them, one by one. The last line is the "Safety" part: access control and
CSRF (a token that stops another site from posting a form as you).

### How

> - `todos/undo.py`: `take_snapshot` and `restore`. The snapshot is JSON-safe (ISO dates) and
>   lives in the session (`request.session["undo_delete"]`, database sessions). `SNAPSHOT_FIELDS`
>   is every concrete `Todo` field, including `copy_fingerprint`, and a test checks this.
> - New view `POST /<pk>/undo-delete/` (`todo_undo_delete`). The "id exists" check runs first
>   inside the transaction, so a double submit restores once.
> - `todo_delete` reads the to-do inside its transaction, so a double click on Delete cannot
>   replace a good snapshot with an empty one.
> - `base.html` messages are now `<div>`s. A small context processor shows the Undo form only on
>   the message whose tag matches the snapshot. The button is labelled "Undo delete: <title>" for
>   screen readers. The list page drops an expired snapshot.

**Why it is there:** it points the reviewer to the risky places (the transaction, the double
submit) and to a change that touches every page (`<p>` to `<div>`), so they are not missed.

### Migrations

> None.

**Why it is there:** a migration is the riskiest part of a deploy. "None." tells the reviewer it
was checked. Compare PR #49, whose section is called "Migrations — run `make backup` before
`migrate`" and lists three migrations and a round trip on a copy of the owner's database.

### Tests

> - Unit tests (`test_undo.py`), 30 integration tests (`test_delete_undo.py`), and one CUJ journey
>   (delete, then Undo). They were shown failing before the code.
> - `make check` after merging main: 727 tests pass (CUJ 30, Integration 573, Unit 124).

**Why it is there:** it names the layers and files, says the tests failed first (so they really
test the new code), and gives the counts after merging `main` (so the merge itself was tested).

### Review

> The adversarial code review gave PASS WITH FIXES. It ran 28 mutations, 24 caught. All its
> findings are fixed, and each new guard test was shown failing against its mutant first:
> a double-delete race that emptied the snapshot; the list access check moved inside the
> transaction; a stranger posting Undo for an existing to-do; another user's snapshot in the
> session; the Undo button's accessible name; AGENTS.md.
>
> Known limit: after a delete on a filtered page, a restored to-do the filter hides goes back to
> that filtered page. The "Restored" message still shows.

(The list is shortened here into one paragraph; the PR has one bullet per finding.)

**Why it is there:** it shows the review was done, how deep it went (mutations; see
[pr-review-by-risk.md](pr-review-by-risk.md)), and that every finding is closed. The known limit
is said openly, so nobody files it later as a surprise bug.

### What PR #51 does not have

- **Screenshots.** The change is visible (a button in the message), but the PR has none. The CUJ
  test checks the flow in a real browser instead. A team that reviews the look would want a
  before and after picture. PR #52 is a better example: it says screenshots at 1280px and 375px,
  light and dark, are pixel-identical to `main`.
- **A separate "Why" heading.** The "Why" is the decision and the plan link in "What". That works
  when the plan is linked; PR #48 has its own "Why" section.

## The template for this project

The real file is `.github/pull_request_template.md`. GitHub puts its text into every new PR in
this repository. It has the sections What (with the plan link), Why, How, Safety, Migrations,
Tests and Review; Screenshots and Known limits go under Review. The hints are HTML comments, so
GitHub does not show them in the finished PR. PR #51 above is the worked example: each part of it
fills one section of the template.

| Template section | Filled in PR #51 by |
|---|---|
| What + Plan link | "What" |
| Why | the decision (B) and the plan link in "What" |
| How | "How" |
| Safety | the last line of "Rules" |
| Migrations | "None." |
| Tests | "Tests" |
| Review | "Review" (with the known limit) |

For a new ticket there are two issue templates: `.github/ISSUE_TEMPLATE/feature_request.md` (a
plan stub that links to `docs/plans/`, see [ticket.md](ticket.md)) and
`.github/ISSUE_TEMPLATE/bug_report.md` (the format of `docs/bug-reports/`).

## Related documents

- [ticket.md](ticket.md): the acceptance criteria the "Rules" part repeats
- [task-plan.md](task-plan.md): the commits behind this PR
- [pr-review-by-risk.md](pr-review-by-risk.md): what the "Review" part means
- [test-plan.md](test-plan.md): the tests the "Tests" part counts
- [../../CHANGELOG.md](../../CHANGELOG.md): where the "What" ends up for users
- [../../.github/pull_request_template.md](../../.github/pull_request_template.md): the template, as a real file
- PR #51, PR #48, PR #49, PR #52; [../plans/delete-undo.md](../plans/delete-undo.md)
