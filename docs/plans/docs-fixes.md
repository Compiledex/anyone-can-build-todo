# Plan: make the docs match the code

Status: **done** (2026-10-11).

Builds on: every merged feature (PRs #1 to #33). Changes only Markdown files: no code, no
migration.

## Goal

A new reader (a person or an AI agent) can trust the docs. Every plan in `docs/plans/` says
whether it was built and in which pull request (PR). `AGENTS.md` describes the code as it is on
`main` today, says what CI runs, says what "today" means, and says that the plans are history.

## What is wrong today

Checked on `main` (commit `0e9379c`) on 2026-10-11:

1. **Every built plan still says "not started".** `grep -n "Status:" docs/plans/*.md` shows 19
   plans with "approved ... not started" (or "approved again ... not started", or "Not started."),
   although all of them were merged. Only `test-pyramid.md` says "done".
2. **The `todos/views.py` row in `AGENTS.md` says two opposite things.** First: "The step views
   (`subtask_add`, `subtask_toggle`, `subtask_delete`) go back with `back_to_steps(todo)`: the list
   page with `?open=<to-do id>#todo-<to-do id>`". Later: "Add, edit, clear completed and the step
   views still go to the plain list." The code (`todos/views.py`: `back_to_steps`, and the three
   step views that return it) does the first. The second sentence is wrong for the step views.
3. **`AGENTS.md` does not mention CI.** `.github/workflows/check.yml` runs on every push and pull
   request, with two jobs at the same time: `lint` (`uv sync --locked`, `pre-commit run
   --all-files`, `makemigrations --check --dry-run`) and `test` (`playwright install --with-deps
   chromium`, then `manage.py test`). It sets no `DJANGO_*` variable.
4. **`AGENTS.md` does not say what "today" is.** The code uses `timezone.localdate()` (in
   `todos/models.py` `is_overdue`, the toggle view, and `send_reminders`), which is the date in
   `TIME_ZONE = "Asia/Tokyo"` (`config/settings.py`). The person chose Tokyo in the due-date plan
   ("Decided by the person": keep `Asia/Tokyo`, the same as the person's computer).
5. **Nothing says the plans are history.** A reader may follow an old plan (for example a file
   name or a class name that changed later) instead of the code.
6. **Smaller gaps found while checking every file of `git ls-files` against `AGENTS.md`:**
   `todos/admin.py` and the folder `scripts/` (the tool behind `make landing-shots`) have no row of
   their own (`scripts/` is only named inside the landing pictures row).

Checked and **already right**, so not changed: the `base.html` row (it already says `base.html`
holds no CSS and loads `tokens.css`, then `app.css`, since PR #32); the `app.css`, `tokens.css`,
`site.css` and `_field.html` rows; the names `NoColon`, `get_visible_todo`,
`get_visible_subtask`, `redirect_back`, `BrowserTestCase`, `assertOtherUserGets404` and
`test_only_landing_login_and_signup_are_open` all exist; the README test counts (CUJ 24,
Integration 400, Unit 93) match the number of `def test_` methods per layer.

## Decisions

### 1. The new Status line of each plan

The form is: `Status: **done** (<date>, PR #<n>).`, then the rest of the old first sentence that
still helps, for example `The decisions are in "Decided by the person" at the end.` The words
"approved" and "not started" go away. The **body** of each plan does not change: it is history.

- **Date:** the day the PR was merged, **in Tokyo time** (`Asia/Tokyo`, the person's time zone
  and the app's `TIME_ZONE`). GitHub gives the time in UTC; Tokyo is 9 hours later, so a PR
  merged after 15:00 UTC counts for the next day. Example: PR #20 was merged at
  2026-10-09 15:18 UTC, which is 2026-10-10 in Tokyo.
- **PR:** the PR that really merged. When a first PR was closed and a "rebased" one merged
  (#17 search and #18 recurring were closed), use the merged one.

| Plan | PR that merged | Merged (UTC) | Date in Tokyo |
|---|---|---|---|
| `test-pyramid.md` | #1 | 2026-10-09 08:40 | 2026-10-09 |
| `foundation.md` | #5 | 2026-10-09 09:06 | 2026-10-09 |
| `dark-mode.md` | #6 | 2026-10-09 09:11 | 2026-10-09 |
| `accounts.md` | #7 | 2026-10-09 09:49 | 2026-10-09 |
| `lists.md` | #8 | 2026-10-09 10:07 | 2026-10-09 |
| `edit-todo.md` | #9 | 2026-10-09 10:12 | 2026-10-09 |
| `due-date.md` | #10 | 2026-10-09 10:18 | 2026-10-09 |
| `sharing.md` | #11 | 2026-10-09 12:36 | 2026-10-09 |
| `clear-completed.md` | #12 | 2026-10-09 12:44 | 2026-10-09 |
| `description.md` | #13 (`feature/description-rebased`) | 2026-10-09 14:47 | 2026-10-09 |
| `priority.md` | #14 (`feature/priority-rebased`) | 2026-10-09 14:55 | 2026-10-09 |
| `tags.md` | #15 (`feature/tags-rebased`) | 2026-10-09 14:55 | 2026-10-09 |
| `subtasks.md` | #16 | 2026-10-09 14:55 | 2026-10-09 |
| `recurring.md` | #20 (`feature/recurring-rebased`; #18 was closed) | 2026-10-09 15:18 | 2026-10-10 |
| `search.md` | #21 (`feature/search-rebased`; #17 was closed) | 2026-10-09 15:29 | 2026-10-10 |
| `filter.md` | #23 | 2026-10-10 13:36 | 2026-10-10 |
| `sort.md` | #24 | 2026-10-10 13:48 | 2026-10-10 |
| `drag-and-drop.md` | #25 | 2026-10-10 14:05 | 2026-10-10 |
| `reminders.md` | #27 (#26 was only the plan) | 2026-10-10 14:32 | 2026-10-10 |
| `app-redesign.md` | #32 (#30 was only the plan) | 2026-10-11 03:07 | 2026-10-11 |

The implementer checks this table again with
`gh pr list -R Compiledex/anyone-can-build-todo --state merged --limit 100 --json number,title,mergedAt,headRefName`
before editing, in case a number is wrong.

Special cases:

- `test-pyramid.md` already says `**done**`. It gets the same form for the sake of one style:
  `Status: **done** (2026-10-09, PR #1). See "Result" at the end.`
- `reminders.md` has a two-line Status. The new one keeps the useful part:
  `Status: **done** (2026-10-10, PR #27). The plan was approved again on 2026-10-10 after the
  person changed how reminders are shown (see the next section). The person's answers are in
  "Decided by the person" at the end.`
- `app-redesign.md`: `Status: **done** (2026-10-11, PR #32). Approved by the person on 2026-10-11
  (see "Decided by the person").`
- `app-redesign-mockup.html` is not a plan and has no Status. Not changed.
- `safe-settings.md` and this plan stay `draft` until they are approved and built.
- The reminders code is merged, but the person has not switched the launchd job on. "done" is
  still right: the plan's task was the code and the template, and the README says the person
  turns it on.

### 1b. The rule for future plans

From now on, the **implementer's last commit** on a feature branch sets the plan's Status line to
`Status: **done** (<date in Tokyo>)`. The PR number is optional there (the PR may not exist yet);
it can be added later if the repo keeps it. The orchestrator checks the line before merging. This
rule goes into `AGENTS.md` (decision 3). The existing plans get the date **and** the PR number, as
in the table above.

### 2. Fix the `todos/views.py` row in `AGENTS.md`

Replace the sentence "Add, edit, clear completed and the step views still go to the plain list."
with: "Add, edit and clear completed go to the plain list address, without the search, filter or
order." Nothing else in the row changes. (The sentence about `back_to_steps` earlier in the row
is right and stays.)

### 3. New `AGENTS.md` lines

| Where in `AGENTS.md` | New text (short version) |
|---|---|
| Table, new row after `Makefile` | `.github/workflows/check.yml`: CI (checks GitHub runs by itself). On every push and every pull request, two jobs at the same time: `lint` (`uv sync --locked`, every commit check on every file, the migration check) and `test` (installs Chromium, then `manage.py test`, all three layers). It sets no `DJANGO_*` variable, so the settings use the laptop defaults. The team merges a PR only when both jobs are green (GitHub does not enforce it; branch protection is off). |
| Table, new row after `todos/models.py` | `todos/admin.py`: the admin pages at `/admin/` for `TodoList` (members chosen with a two-box picker) and `Todo` (with its steps on the same page). |
| Table, new row near the landing pictures row | `scripts/landing_shots.py`, `scripts/landing_seed.py`: the tool behind `make landing-shots` (see the `todos/static/todos/landing/` row). |
| Table, new row at the end | `docs/plans/`: one plan per feature, written and approved before the code. **History**: they say what was decided and why, not how the code is now. Their Status line says which PR built them. |
| `config/settings.py` row, one sentence added | `TIME_ZONE` is `"Asia/Tokyo"` (the person's choice): "today" in the app is the date in Tokyo. |
| Rules, new rule after "Run `make check`" | **"Today" is `timezone.localdate()`**, the date in `TIME_ZONE` (`Asia/Tokyo`). Never `date.today()` or `datetime.now()`, which use the computer's own time zone. Code takes "today" as an argument where a test needs to choose the day (like `make_next_copy(today)`, `send_reminders(user, today)`, and `is_overdue(today=None)`, which falls back to `timezone.localdate()`); the view or command that calls it passes `timezone.localdate()`. |
| Rules, new rule at the end | **`AGENTS.md` describes the code on `main`; the plans in `docs/plans/` are history.** When a plan and the code disagree, the code (and this file) win. When you change the code, update this file in the same PR; do not edit the body of an old plan, only its Status line. |
| Rules, new rule after the plans rule | **A plan's Status line says when it was built.** The implementer's last commit on a feature branch sets the plan's line to `Status: **done** (<date in Tokyo>)`; the PR number is optional and may be added later. The orchestrator checks this line before merging. |
| `## Commands`, one line after `make check` | "GitHub runs the same checks and all the tests on every push (see `.github/workflows/check.yml`)." |

### 4. `README.md` lines

`README.md` already says "GitHub runs the same checks and the tests on every push." Only two rows
are added to "How it is put together":

- `.github/workflows/check.yml`: "The checks and tests GitHub runs on every push and pull request".
- `docs/plans/`: "The plan for each feature, written before the code; history, not a description
  of the code today".

### 5. No test

A test that "no plan says not started" would be **wrong**: the team merges a plan as soon as the
person approves it, **before** the code is built (see `docs/plans/reminders.md` and PR #26 and
#30). So "approved, not started" is a correct state on `main` for a while. A test of the Status
format alone would only check spelling. Prose has no behavior, so the rule "a test with every
change in behavior" does not apply.

How it is checked instead:

- `grep -n "Status:" docs/plans/*.md`: every built plan says `**done** (<date>, PR #<n>)`, and
  only drafts say anything else.
- `grep -n "step views still go" AGENTS.md` finds nothing.
- `make check` passes (the commit checks look at trailing spaces and the end of every file).
- A reviewer opens each changed `AGENTS.md` sentence next to the code it describes.

## Security

Docs only. No code, no setting, no data changes. The new text names no secret and no user data.
The "Today" rule protects against a real bug class (an off-by-one day between the Mac's clock and
`TIME_ZONE`), and the "plans are history" rule stops an agent from rebuilding old, replaced
behavior from a plan.

## Data and migrations

None.

## Working next to

`docs/plans/safe-settings.md` also changes `AGENTS.md` (the `config/settings.py` row, new rows for
`config/env.py` and `config/tests/`) and `README.md` ("Put it on the internet", "How it is put
together"). **Merge order: this plan first** (it is docs only). Then safe-settings rebases on it,
keeps the `TIME_ZONE` sentence in the `config/settings.py` row and the CI row, and sets its own
Status line to done in its last commit (decision 1b).

## Not part of this task

- Turning on branch protection on GitHub (open question c).

- Rewriting the body of any plan.
- Adding a plan for the landing page (#29) or the login pages (#31), which were built without a
  file in `docs/plans/`.
- Any code change, even a small one found while checking.

## Changes to files

| File | Change |
|---|---|
| `docs/plans/*.md` (20 files: every plan in the table in decision 1) | Only the Status line (one or two lines at the top). |
| `AGENTS.md` | The `todos/views.py` sentence (decision 2); the new rows and rules (decision 3). |
| `README.md` | Two rows in "How it is put together" (decision 4). |

## Steps

1. Run the `gh pr list` command and compare it with the table in decision 1. Fix the table first
   if a number or a date is wrong.
2. Change the Status line of each plan. Run `grep -n "Status:" docs/plans/*.md` and show the
   person the result.
3. Fix the `todos/views.py` row in `AGENTS.md`. Read `todos/views.py` again first and check that
   `subtask_add`, `subtask_toggle` and `subtask_delete` still return `back_to_steps(...)`, and that
   add, edit and clear completed still redirect to the plain list.
4. Add the new `AGENTS.md` rows and rules. For each, open the file it describes and check every
   name in the new text.
5. Add the two `README.md` rows.
6. Check that no new text has an em dash (the long dash, Unicode U+2014; search the changed lines only, old text may
   keep its dashes).
7. `make check`, then commit.

## Tests

No new tests (see decision 5). `make check` must pass, with the same test counts as before.

## Open questions

1. **(c) Turn on GitHub branch protection for `main`?** Today it is off (checked with
   `gh api repos/Compiledex/anyone-can-build-todo/branches/main`: `protected` is `false`), so "merge
   only when CI is green" is a team habit, not a rule GitHub enforces. Branch protection would make
   GitHub refuse a merge while a job is red. **Recommendation: yes, require the `lint` and `test`
   checks before a merge**, but the person turns it on in the GitHub settings (it is an account
   setting, so not the AI). It is not part of this plan.
2. **(d) Status lines: date in Tokyo plus PR number, or only the PR number?** **Recommendation:
   both**, with the date in Tokyo: it is the person's time zone, the app's `TIME_ZONE`, and the
   dates the person already wrote in the plans ("approved on 2026-10-11"). The PR number links to
   the code and the review.

## Review

The plan review (2026-10-11) said APPROVE WITH CHANGES. What changed:

- New decision 1b and an `AGENTS.md` rule: the implementer's last commit sets the plan's Status to
  done with the Tokyo date (PR number optional); the orchestrator checks it before merging.
- The CI row says the team merges only on green, and that GitHub does not enforce it (branch
  protection is off). Branch protection is now open question (c).
- The "today" rule: code takes `today` as an argument where a test needs to choose the day, and
  the caller passes `timezone.localdate()` (`is_overdue(today=None)` falls back to it).
- New section "Working next to": this plan merges before safe-settings.
- Open questions are now (c) branch protection and (d) Tokyo date plus PR number. The
  `test-pyramid.md` question was dropped: it simply gets the same form (decision 1).

## Decided by the person (2026-10-11)

The plan is **approved**.

- Status lines use the Tokyo date and the PR number, as in the table.
- GitHub branch protection: the person turns it on for `main` themselves (require the `lint` and
  `test` checks), outside this plan. Until it is on, the CI row in AGENTS.md says it is a team rule
  that GitHub does not enforce; when it is on, that half-sentence is removed in a later change.
