# Plan: move the reminders and server instructions from the README into runbooks

Status: approved (2026-10-16) — not started

Builds on: **reminders** (PR #27: `send_reminders` and the launchd template), **safe-settings**
(PR #36: the three `DJANGO_*` variables), the README host warning (PR #37), and the documentation
set (PR #54: `docs/runbooks/deployment.md`, `docs/README.md`). Checked on `main` (`2c75b89`).

## Words used in this plan

- **Runbook**: a page of exact steps for a job you do now and then (install, update, set up a
  scheduled job). The repo has two: `docs/runbooks/deployment.md` and
  `docs/runbooks/on-call-and-incidents.md`.
- **Anchor**: the part of a link after `#`. GitHub makes one from each heading, for example
  `## Reminders on your Mac` gets `#reminders-on-your-mac`.
- **Behaviour-free**: only documentation moves. No code, no setting, no test changes.

## What is wrong today

1. `README.md` is 410 lines. Two long sections are for jobs the owner does rarely or never:
   - **"Reminders on your Mac"** (lines 233-313, 81 lines): an 8-step launchd setup. The owner
     has not switched reminders on (`docs/design/design-doc.md`, "Reminders").
   - **"Put it on the internet"** (lines 364-410, 47 lines): the host warning, the three
     environment variables, the build and start commands. The app is not deployed (a decision,
     `docs/runbooks/deployment.md`).
2. The server part is written **twice**: `docs/runbooks/deployment.md`, section "If it ever runs on
   a server" (lines 114-138), is a summary of the README section. The two are not the same: each
   has facts the other lacks (see decision 3). Two copies drift apart.
3. `AGENTS.md`'s plist row says "(see `README.md`)" for how to install the job.

## Goal

The README stays the front door: what the app does, how to run it, back it up and test it. The
rare jobs live in runbooks, each written **once**: the reminders setup in a new
`docs/runbooks/reminders.md`, the server notes in the existing deployment runbook section. The
README keeps both headings, each with one or two sentences and a link, so old links still work.
No instruction, command or warning is lost; a diff of the moved text proves it.

## Decisions

### 1. Keep both README headings, shorten their bodies

The headings `## Reminders on your Mac` and `## Put it on the internet` stay, so the anchors
`#reminders-on-your-mac` and `#put-it-on-the-internet` keep working: the README's own contents
line (lines 10-13), the link in "Private by default" (line 98), and any link from outside the repo.

New body of **"Reminders on your Mac"** (replaces lines 235-313):

> Once a day, at 08:00, your Mac can show **one notification** with the to-dos in **your own
> lists** that are **due today**. It is off until you set it up once, yourself, in the Terminal:
> the steps are in the [reminders runbook](docs/runbooks/reminders.md).

New body of **"Put it on the internet"** (replaces lines 366-410):

> [!WARNING]
> On many hosts the SQLite database file, `db.sqlite3`, is deleted at every deploy or restart,
> and all accounts and to-dos are gone; read the runbook before you put real data online.

The app runs on your own computer. Before you put it on a server, read
[If it ever runs on a server](docs/runbooks/deployment.md#if-it-ever-runs-on-a-server) in the
deployment runbook: it says how to keep the database, and which three environment variables a
live server needs.

(The one-sentence warning stays in the README because the owner asked for it there, PR #37.)

The README's "How it is put together" row for `deploy/macos/` becomes: "The launchd template for
the morning reminders on a Mac (set up with the [reminders runbook](docs/runbooks/reminders.md))".

### 2. The reminders setup moves word for word to `docs/runbooks/reminders.md`

The new file has the same frame as the two runbooks (a header table, the "What this document is"
box), then README lines 235-313 **unchanged**, then "Related documents". Exact content:

```markdown
# Reminders runbook

| | |
|---|---|
| Type | Runbook (set up a scheduled job) |
| Phase | Production |
| Written by | Site reliability engineer (in this project: the owner and Claude) |
| Status | Approved; not in use (the owner has not switched reminders on) |
| Date | <build date> |
| Data | REAL |

> **What this document is.** The steps to switch on the morning notification on the owner's Mac,
> and to change or stop it. They change the Mac's settings, so the person does them, not the AI
> (`AGENTS.md`: the AI never installs the job, never runs `launchctl`, never writes to
> `~/Library`). Run every command in the project folder. Moved here from `README.md` on
> <build date> (this PR); the text is the same.

## Set it up

<README.md lines 235-313, byte for byte>

## Related documents

- [ADR 0008: Mac notifications via osascript](../adr/0008-mac-notifications-via-osascript.md)
- [`docs/plans/reminders.md`](../plans/reminders.md) (why it works this way; history)
- The template: [`deploy/macos/com.anyone-can-build-todo.reminders.plist`](../../deploy/macos/com.anyone-can-build-todo.reminders.plist)
- [Deployment runbook](deployment.md): start, update and roll back the app itself
```

Why word for word: the steps were tested on a real Mac when reminders was built (PR #27), and
each step has a reason (for example step 3 before step 4: `osascript` says "it worked" even when
notifications are blocked). Rewording risks losing one. Lines 235-313 contain no Markdown link and
no `#anchor`, so nothing inside them breaks when the file moves; paths in them
(`deploy/macos/...`, `~/Library/...`) are relative to the project folder, which the box says.

### 3. The server part: one full version, in the deployment runbook

`docs/runbooks/deployment.md` section "If it ever runs on a server" (lines 114-138) is rewritten
to hold **everything** from both places, once. Then README lines 366-410 are removed.

What each place has today, and where it ends up:

| Fact | README (line) | deployment.md (line) | In the new section |
|---|---|---|---|
| Not in use; the app runs only locally | - | 116-117 | Intro (kept) |
| Hosts throw files away at deploy or restart; the database starts empty, no error | 366-370 (warning box, Render example) | 134-135 (bullet) | The README warning box, word for word |
| Choose a persistent disk; `db.sqlite3` must be on it; no setting for the path yet | 374-376 | 135-137 | Warning box |
| Or PostgreSQL: a code change in `config/settings.py`, not built | 377-378 | 136-137 | Warning box |
| Make backups, `make backup`, link to "Back up your data" | 379 | 137 ("Back up regularly") | Warning box; the link becomes `../../README.md#back-up-your-data` |
| On your laptop this does not happen | 381 | - | Warning box |
| "A live server needs three environment variables. Never put their real values in the code." | 383 | 119 ("never in the code") | Sentence above the table, from the README |
| The three variables and their values, how to make a key | 385-389 | 121-125 | The deployment.md table (it has the extra "If wrong" column), with the README's example `my-todo.onrender.com` added to `DJANGO_ALLOWED_HOSTS` |
| Debug off: HTTPS only; a missing or weak key stops the app, and what "weak" means | 391-393 | 123, 127-128 | HTTPS: one sentence with "(`SECURE_SSL_REDIRECT` in `config/settings.py`)" from deployment.md. The weak-key rule is written **once**, in the table's "If wrong" cell; the sentence points to it |
| Set the variables for the build too; on Render the settings page is used for both | 395-396 | 129 ("must be set for the build too") | README sentences, word for word |
| Build command | 400-402 (code block) | 130 (inline) | The README code block, byte for byte |
| `check --deploy` is Django's production checks; `--fail-level WARNING` stops on any warning | - | 131-132 | Kept from deployment.md |
| "If the build stops, read the last line of the error: it says which variable to set." | 404 | - | Kept, after the build command |
| Start command | 406-410 (code block) | 133 (inline) | The README code block, byte for byte |
| The reminders only work on a Mac, not on a server | - | 138 | Kept, last |

The new section, exactly (the implementer copies the README parts from the file, not from here):

````markdown
## If it ever runs on a server

This section is **not in use**: the app runs only locally. It holds what was the "Put it on the
internet" part of `README.md` until <build date> (this PR), with the facts of the safe-settings plan
(PR #36), so nobody starts from zero.

### Data loss on a host

<README.md lines 366-381 (the `> [!WARNING]` box), word for word, except the link
`(#back-up-your-data)` becomes `(../../README.md#back-up-your-data)`>

### Environment variables

A live server needs three environment variables. Never put their real values in the code.

| Variable | Value | If wrong |
|---|---|---|
| `DJANGO_SECRET_KEY` | A long random string: `uv run python -c "import secrets; print(secrets.token_urlsafe(50))"` | With debug off, missing or weak (under 50 characters, under 5 different characters, or starting with `django-insecure-`) stops the app with `ImproperlyConfigured` (`config/env.py`) |
| `DJANGO_DEBUG` | `False` | Only `True` or `False` (any case). Any other value, also empty, stops the app |
| `DJANGO_ALLOWED_HOSTS` | The site's address without `https://`, for example `my-todo.onrender.com`; commas between several | Requests to other names get 400 |

With `DJANGO_DEBUG` set to `False`, the site only works over HTTPS (`SECURE_SSL_REDIRECT` in
`config/settings.py`), and a missing or weak `DJANGO_SECRET_KEY` stops the app at once (see the
table).

### Build and start

The build uses the settings too, so set the three variables for the build as well as for the start.
(On most hosts, for example Render, the variables on the settings page are used for both.)

Build command:

<README.md lines 400-402, the code block, byte for byte>

`check --deploy` is Django's list of production safety checks; with `--fail-level WARNING` any
warning stops the build. If the build stops, read the last line of the error: it says which
variable to set.

Start command:

<README.md lines 408-410, the code block, byte for byte>

### Logs

On a server, check what the web server (for example gunicorn and the host's proxy) and Django
write to their logs. A request line holds the whole address, and a search address holds the
search words (`?q=...`), so the log can hold what people searched for. Keep such logs short, or
leave the query string out.

### Not on a server

- The reminders (`send_reminders`) only work on a Mac and are not part of a server.
````

The "Logs" note is new (not from the README); privacy-small-fixes relies on it for the server
case, since its log filter covers only the development server.

The intro of the runbook (line 19), "Every command below exists in the `Makefile` or
`README.md`.", becomes "Every command below exists in the `Makefile` or `README.md`, except the
server commands in the last section, which live only here."

### 4. Every link and reference that names the moved text

From `git grep -n -i "reminders-on-your-mac\|put-it-on-the-internet\|Reminders on your Mac\|Put
it on the internet\|README"` on `main`, outside `docs/plans/`:

| Place | Today | Change |
|---|---|---|
| `README.md:10-13` (contents line) | Links to both headings | **None**: the headings stay. |
| `README.md:98` ("Private by default") | `see [Reminders on your Mac](#reminders-on-your-mac)` | **None**: the heading stays, and links on. |
| `AGENTS.md:74` (plist row) | "The person fills it in and installs it (see `README.md`)" | "(see `docs/runbooks/reminders.md`)". |
| `docs/runbooks/deployment.md:19` | "exists in the `Makefile` or `README.md`" | Decision 3. |
| `docs/runbooks/deployment.md:116` | "It summarises the "Put it on the internet" part of `README.md`" | Decision 3 (new intro). |
| `docs/runbooks/deployment.md`, "Related documents" | | Add "[Reminders runbook](reminders.md)". |
| `docs/README.md:58-59` (phase 4 table) | Two runbook rows | Add a row after the deployment runbook: "\| [Reminders runbook](runbooks/reminders.md) \| How to switch on the morning Mac notification, and stop it \| Real \|". |
| `docs/README.md:81` (folder tree) | "runbooks/ deployment, on-call and incidents" | "deployment, reminders, on-call and incidents". |
| `docs/product/prd.md:112` | "(`README.md`, "Reminders on your Mac")" | "([reminders runbook](../runbooks/reminders.md))". |
| `docs/adr/0008-mac-notifications-via-osascript.md:68`, `docs/adr/0002-sqlite-immediate-transactions.md:43` and `:53` (PostgreSQL, "the README names it") | Name the README sections | **None** (decided by the orchestrator): an ADR is a record of that day. The README headings stay and link on, so the pointers still lead to the text. ADR 0002 line 53 says "the README names it" (PostgreSQL); after the move the README no longer names PostgreSQL, only the runbook does. Left so knowingly. |
| `CHANGELOG.md` | | Under `## [Unreleased]` (create it above `## [0.5.1]` if no PR of this round made it yet), `### Changed`: "The steps to switch on the Mac reminders, and the notes for a server, moved from the README to the runbooks; the README links to them (this PR)." |
| `docs/plans/README.md` | | One row for this plan when it is built. |
| `docs/plans/reminders.md`, `safe-settings.md`, `docs-fixes.md` and other plans | Name the README sections | **None**: plans are history. |
| `deploy/macos/*.plist`, `todos/reminders.py`, `send_reminders.py` | Name no README section (checked) | None. |
| `pyproject.toml:5` (`readme = "README.md"`) | The package's readme | None. |

### 5. Only text moves

No instruction is changed, reworded or dropped. Two small wording facts stay as they are, on
purpose: step 2 of the reminders says "after you pull this feature" (written when reminders was
new), and the deployment runbook's header `Date` stays `2026-10-16`. Fixing them is a separate
docs change (open question 3).

## Security

No code or setting changes. The moved text keeps every safety instruction: "you do them yourself
(not the AI)", "Do not give Python Full Disk Access", "Never put their real values in the code",
the weak-key rule, and the data-loss warning. The new runbook's box repeats the `AGENTS.md` rule
that the AI never installs the job. No secret, username or path of the owner's Mac is written
into the docs (the examples stay `alice` and `$(pwd)`).

## Data and migrations

None. Going back: revert the commit.

## Working next to

Wave A, built in parallel with **split-browser-tests**, **privacy-small-fixes** and
**admin-log-without-names**. Merge order: **split-browser-tests → readme-to-runbooks (this) →
privacy-small-fixes → admin-log-without-names → delete-account**.

- **privacy-small-fixes** changes the `make run` paragraph in `README.md`'s "Back up your data"
  section (line 202, "`make run` also makes a copy, once a day"; not a moved section), relies on
  the new "Logs" note in the server section (decision 3), and probably `docs/runbooks/deployment.md`
  section 2 "Start and stop" (`make run` also clears old sessions). This plan changes only the
  intro line 19 and the last section of that file, so the hunks do not touch; it merges first,
  and privacy-small-fixes rebases.
- **delete-account** adds "If you delete that account, remove the launchd job too." to the
  reminders steps. After this plan merges, those steps are in `docs/runbooks/reminders.md`, so
  delete-account puts the sentence there, in step 8 ("To change or stop it"), when it rebases.
  It may also add a sentence elsewhere in `README.md`, not in the moved sections.
- **split-browser-tests** changes the `todos/tests/cuj/` row of `AGENTS.md`; this plan the plist
  row. Both add a `CHANGELOG.md` line under `## [Unreleased]`: the second to merge keeps both.
- The privacy plans close gaps in `docs/design/data-inventory-and-privacy.md`; this plan does not
  touch that file (its line 107 names "The README" for the backup advice, which stays in the
  README).

## Not part of this task

- Rewording the moved text, or fixing "after you pull this feature" (open question 3).
- Moving other README sections ("Back up your data", "Tests", "Checks").
- Switching reminders on, or any change to the plist, `send_reminders` or the settings.
- Editing the body of any plan.

## Changes to files

| File | Change |
|---|---|
| `docs/runbooks/reminders.md` (new) | Decision 2. |
| `docs/runbooks/deployment.md` | Line 19, the section "If it ever runs on a server" (decision 3), "Related documents". |
| `README.md` | The two short bodies (decision 1); the `deploy/macos/` row. |
| `AGENTS.md` | The plist row. |
| `docs/README.md` | The runbook row and the folder tree. |
| `docs/product/prd.md` | The pointer (decision 4). |
| `CHANGELOG.md` | One line. |
| `docs/plans/README.md` | One row when built. |
| `docs/plans/readme-to-runbooks.md` | Status line on the last commit. |

## Steps

1. **Save the old text** (scratchpad, not committed):
   `git show origin/main:README.md > "$SCRATCH/README-before.md"`,
   `sed -n '235,313p' "$SCRATCH/README-before.md" > "$SCRATCH/reminders-before.md"`,
   `sed -n '366,410p' "$SCRATCH/README-before.md" > "$SCRATCH/server-before.md"`,
   and `git show origin/main:docs/runbooks/deployment.md > "$SCRATCH/deployment-before.md"`.
   Check the line numbers first: line 233 is `## Reminders on your Mac`, 315 is `## Tests`, 364
   is `## Put it on the internet`, 410 is the last line. If they moved, use the headings.
2. Write `docs/runbooks/reminders.md` with `reminders-before.md` pasted in (by file, not retyped).
3. Rewrite the deployment runbook section (decision 3), pasting the README parts from
   `server-before.md`.
4. Shorten the README sections; update every reference in decision 4.
5. **Prove nothing was lost** (decision "Tests" below), then `make check`.
6. Last commit: Status `**done** (<date in Tokyo>)` and the `docs/plans/README.md` row.

## Tests

No code changes, so no new test. The checks, run by the implementer and shown in the PR:

| Check | How | Must give |
|---|---|---|
| The reminders steps moved byte for byte | `diff "$SCRATCH/reminders-before.md" <(awk '/^## Related documents$/{f=0} f; /^## Set it up$/{f=1; getline}' docs/runbooks/reminders.md \| sed '$d')` (the lines between the two headings, without the blank line after each heading) | No output |
| Every command of the reminders steps is in the runbook | `grep -o '`[^`]*`' "$SCRATCH/reminders-before.md"` and each fenced line; every one found with `grep -F` in `docs/runbooks/reminders.md` | 0 missing |
| Every command and value of the server section is in the deployment runbook | The same for `server-before.md`: every backticked part and every line of its two code blocks found with `grep -F` in `docs/runbooks/deployment.md` | 0 missing |
| The warning box moved word for word | `diff <(sed -n '1,16p' "$SCRATCH/server-before.md")` (README lines 366-381) against the box in the new section | Only that one link differs |
| No fact of the old deployment section was lost | Every row of the table in decision 3 that comes from deployment.md: its text (`ImproperlyConfigured`, `SECURE_SSL_REDIRECT`, "commas between several", "Requests to other names get 400", `check --deploy`, "not part of a server") found with `grep -F` | 0 missing |
| Nothing written twice | `grep -c "gunicorn config.wsgi"` in `README.md` 0, in `deployment.md` 1; `grep -c "launchctl bootstrap"` in `README.md` 0, in `reminders.md` 1 | As said |
| Links resolve | A small script (scratchpad) lists every relative Markdown link in the changed files and checks that the file exists and, for `#anchor`, that a heading with that anchor exists (GitHub's rule: lower case, spaces to `-`, drop punctuation) | 0 broken; includes `#if-it-ever-runs-on-a-server`, `#back-up-your-data`, `#reminders-on-your-mac` |
| The commit checks pass | `make check` (trailing whitespace and end-of-file hooks run on Markdown; the tests are unchanged) | Green, same counts as `main` |

The PR shows the outputs of these checks.

## Open questions

1. **A new file `docs/runbooks/reminders.md`, or a section in `deployment.md`?** Recommended: a new
   file. It is a different job (a Mac scheduler, not the app), and `deployment.md` is already 146
   lines.
2. **Fix "after you pull this feature" in reminders step 2?** It reads oddly now. Recommended:
   not in this PR (word for word makes the diff check simple); a one-line follow-up later.

## Review

The plan review (2026-10-16) said APPROVE WITH CHANGES. What changed:

- ADRs are not edited at all (orchestrator's decision): they are records of that day, and the
  README headings still link on. ADR 0002 line 53 ("the README names it", PostgreSQL) is left
  knowingly. The old open question about it is gone.
- "Working next to": delete-account's sentence about the launchd job goes into
  `docs/runbooks/reminders.md` step 8 when it rebases; privacy-small-fixes changes the `make run`
  paragraph in "Back up your data" (there is no "Commands" section).
- The server section gets a short "Logs" note (request lines can hold search words), which
  privacy-small-fixes relies on.
- The weak-key rule is written once, in the table; the heading is "Data loss on a host".
- "(this PR)" instead of "(PR #N)".
- The README keeps a one-sentence `> [!WARNING]` in "Put it on the internet" that the SQLite
  database can be deleted on many hosts, with the link (orchestrator's decision; the owner asked
  for this warning in PR #37).

## Decided by the person

(Filled in after the person answers.)

## Decided by the person (2026-10-16)

- Approved: "Ja, bygg dem" (build all five plans, in the merge order of the build order).
- The open questions follow the plan's recommendations (decided by the orchestrator): a new `docs/runbooks/reminders.md`; the move is word for word (no wording fixes in this PR); ADRs are not edited; README keeps a one-sentence warning about the database on a host (the person asked for that warning in PR #37).
