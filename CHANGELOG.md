# Changelog

| | |
|---|---|
| Type | Release notes (changelog) |
| Phase | Production |
| Written by | Product manager with the release engineer (in this project: the owner and Claude, from the merged PR list) |
| Status | Done |
| Date | 2026-10-16 |
| Data | REAL (the version numbers are labels, see below) |

> **What this document is.** Release notes tell the people who use an app what changed, in their
> words: what they can do now, and what was fixed. A product manager or release engineer writes
> them for every release. Without them, people miss new features, or are surprised by a change.

**About the version numbers.** The repo has no git tags or releases, and `pyproject.toml` still
says `version = "0.1.0"`. The numbers below are labels given afterwards, one per day or stage of
work, so the history is easy to read. Dates are Tokyo dates (the app's `TIME_ZONE`). Each line
names its pull request (PR). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
Added, Changed, Fixed, Security, plus "Under the hood" for changes you cannot see.

## [0.5.1] - 2026-10-16

### Fixed

- The README's example test counts, and two sentences in `AGENTS.md`, now match the code (PR #53).

## [0.5.0] - 2026-10-11

### Added

- **Undo after Delete.** Deleting a to-do shows "Deleted “…”." with an **Undo** button for 15
  minutes. The to-do comes back exactly as it was: list, place, notes, tags and steps (PR #51).
- **A daily backup.** `make run` first saves a copy of your data in `backups/`, at most once a
  day, and keeps the newest 14 daily copies (PR #48).
- Turning on **Repeat** for a to-do that is already done makes its next copy at once (PR #50).

### Changed

- Undo on a repeating to-do **keeps the next copy if you changed it** (title, notes, priority,
  tags, date, repeat or steps), and says so (PR #50).
- List names ignore upper and lower case for every letter, also æ, ø and å: you cannot have both
  "Ærend" and "ærend" (PR #49).

### Fixed

- Before release, code review found and fixed: Undo after a fast double Delete lost the steps and
  tags ([BUG-001](docs/bug-reports/BUG-001-double-delete-loses-steps-and-tags.md), PR #51); a failed
  daily backup said it worked ([BUG-002](docs/bug-reports/BUG-002-failed-backup-reported-as-success.md),
  PR #48); the backup name check accepted non-ASCII digits
  ([BUG-003](docs/bug-reports/BUG-003-daily-name-matches-non-ascii-digits.md), PR #48).

### Under the hood

- The list page is 25 % lighter with 300 to-dos (one form per row), and `AGENTS.md` is shorter (PR #52).

## [0.4.0] - 2026-10-11

### Added

- **`make backup`**: a safe copy of your data, also while the app runs. **`make reset`** now asks
  you to type `yes` and always makes a copy first (PR #43).
- Search for `#work` finds the tag `work` (PR #43).
- Sort by title puts æ, ø, å after z, and search finds æ, ø, å in any case (PR #41).

### Changed

- Done and Undo say which state they want, so two tabs or a double click can no longer undo your
  work. After Done, Undo or Delete, the page stays where you were (PR #44).
- Accessibility: each button names its to-do for screen readers ("Done: Paint the hallway"),
  bigger buttons under a finger, clear "Error:" titles, and "Leave this list" asks first (PR #45).
- Undo on a repeating to-do keeps the next copy when a step in it is already done (PR #40).
- "A repeating to-do needs a due date." now shows under the Due date field (PR #43).

### Security

- On a server, the app refuses to start with a missing or weak secret key, or a bad
  `DJANGO_DEBUG` value (PR #36). The README warns that some hosts delete the database file (PR #37).

### Under the hood

- Shared test helpers and smaller test files (PR #46); docs and plans brought in line with the
  code (PR #35); plans for these changes (PR #34, #39, #42).

## [0.3.0] - 2026-10-11

### Added

- A **landing page** at `/` for visitors, with real screenshots and no user data (PR #29).
- The README shows what the app does, with screenshots (PR #33).

### Changed

- **A new look**: the app, the login and the sign-up pages share one calm design, in light and dark,
  and work on a phone (PR #31, PR #32).

### Fixed

- A long title no longer runs under its priority label, and the row's buttons stay together (PR #28).

## [0.2.0] - 2026-10-10

### Added

- **Repeat** a to-do every day, week or month: mark it done, and the next one appears (PR #20).
- **Search** the titles, notes and tags of a list (PR #21).
- **Filter**: All, Not done or Done (PR #23).
- **Sort by** date added, due date, priority or title (PR #24).
- **Your own order**: sort Manual, then drag a to-do or use the Move buttons (PR #25).
- **Mac reminders** (optional, off until you set them up): one notification at 08:00 with the
  to-dos due today in your own lists (PR #26, PR #27).

### Fixed

- Two browser tests that sometimes failed on GitHub for no real reason (PR #19, PR #22). See the
  [postmortem](docs/postmortems/2026-10-09-merged-with-red-ci.md).

## [0.1.0] - 2026-10-09

### Added

- **Accounts**: sign up, log in, and see only your own to-dos (PR #7).
- **Lists**: several lists per person, with an "Inbox" for everyone (PR #8).
- **Edit** a to-do on its own page (PR #9).
- **Due date**, with **Overdue** in red (PR #10).
- **Share a list** with other people by username (PR #11).
- **Clear completed**: delete all done to-dos of a list at once (PR #12).
- **Notes** (PR #13), **priority** Low / Medium / High (PR #14), **tags** (PR #15) and **steps**
  inside a to-do (PR #16).
- **Dark mode**: follows your system's light or dark setting (PR #6).

### Changed

- An empty title, or one over 200 characters, now shows an error and keeps what you typed (PR #5).

### Under the hood

- Tests sorted into three layers: unit, integration and browser journeys (PR #1, PR #2); the
  reviewed plans for every feature (PR #3, PR #4).

## Related documents

- [Deployment runbook](docs/runbooks/deployment.md) (how to update to a new version)
- [QA run and bug bash](docs/process/qa-run-and-bug-bash.md)
- [Bug reports](docs/bug-reports/README.md)
- [Product requirements](docs/product/prd.md), [Retrospective](docs/retrospectives/2026-10-16-project-retrospective.md)
- The plans for each feature: [`docs/plans/`](docs/plans/)
