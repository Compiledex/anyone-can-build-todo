<!--
How to fill this in: docs/process/pull-request-description.md (worked example: PR #51).
Write "None." instead of deleting a section, so the reviewer knows it was thought about.
-->

## What

<!-- What the person sees that is new or different. One short paragraph. -->

Plan: `docs/plans/<feature>.md` (<the decision or ticket>).

## Why

<!-- The problem, or the decision it comes from. One or two sentences. -->

## How

<!-- The main design choices, and where the risky parts are. Not a copy of the diff. -->

-

## Safety

<!-- Who may see or change this, and what a stranger gets (404). Can anything be deleted or
overwritten, and what guards it? POST only, CSRF, redirects, escaping. Or: "None." -->

-

## Migrations

<!-- "None." Or: each migration, made by Django or by hand. Then: run `make backup` before
`migrate`; tested forward, back to <n>, and forward again on a copy of the owner's database. -->

None.

## Tests

<!-- New tests per layer (unit, integration, CUJ) and their files. They were shown failing
before the code. Then the counts from `make check`. -->

-
- `make check`: <N> tests pass (CUJ <n>, Integration <n>, Unit <n>).

## Review

<!-- Risk level (docs/process/pr-review-by-risk.md). For medium and high: the verdict, the
mutations run and caught, each finding and how it was fixed. Screenshots if the look changed.
Known limits, if any. -->
