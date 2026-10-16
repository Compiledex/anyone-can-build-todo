# Product requirements: the to-do list

| | |
|---|---|
| Type | Product requirements document (PRD) |
| Phase | Idea |
| Written by | Product manager (in this project: the owner and Claude) |
| Status | Approved (all requirements built; PR #1 to #53, 51 merged) |
| Date | 2026-10-16 |
| Data | MIXED: problem, users, goals, non-goals and requirements are real; success measures are simulated |

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

> **What this document is.** A PRD says **what** we build and **why**, not how. A product manager
> writes it at the start, before design and code, and the whole team agrees on it. Without a PRD,
> each person builds their own idea of the product, and nobody can say when it is "done" or if it
> worked.

## 1. Problem

People who plan small things together (a household, a couple, a few friends) keep to-dos in many
places: paper, chat messages, a phone note. Things get lost, two people buy the same thing, and
nobody knows what is already done. Big apps solve this, but they are heavy, ask for an email, and
send data to a company.

We want the **most basic to-do list** that still handles real life: due dates, repeating chores,
small steps, and a list shared with a few people, while all data stays on the owner's own
computer (`AGENTS.md`, "What this is").

## 2. Target users

| User | Need |
|---|---|
| **The owner** (primary) | Keep their own lists on their Mac; trust that nothing leaves it. |
| **People the owner shares a list with** (members) | See the shared list and help: add, edit, mark done, delete. |
| **A visitor** | Understand what the app is before making an account (landing page, PR #29). |

The roles are defined in `docs/plans/sharing.md` (PR #11). See the
[user research notes](user-research-notes.md) (simulated) for the needs behind them.

## 3. Goals

1. A person can manage their to-dos in under a minute a day.
2. A shared list shows the same to-dos, in the same order, to everyone who can see it.
3. No data is lost by a slip: undo, confirm before big deletes, and daily backups.
4. Private by default: every page needs a login; you see only your lists and lists shared with
   you.
5. Works for Norwegian text (æ, ø, å) and for people who use a keyboard, a phone or a screen
   reader.

## 4. Non-goals

| Not in scope | Decided in |
|---|---|
| Deploying to a server; the app runs on the owner's Mac | `docs/plans/reminders.md` (2026-10-10) |
| Real-time sync between people (a member sees changes after a reload) | Design choice, [ADR 0001](../adr/0001-server-rendered-django.md) |
| A warning when two people edit the same to-do (last Save wins) | `docs/plans/safe-toggles.md`, "Left for the person" |
| Accent-insensitive search ("e" finds "é") | `docs/plans/nordic-letters.md` |
| Email (sign-up, password reset, reminders) | `docs/plans/reminders.md`, `accounts/urls.py` |
| A light/dark toggle button | `docs/plans/dark-mode.md` |
| A login rate limit or closed sign-up (needed before going public) | `docs/plans/accounts.md` |
| Analytics or any tracking | Privacy, [data inventory](../design/data-inventory-and-privacy.md) |

## 5. Requirements

Every requirement below is built. "Must" = needed for the first useful version; "Should" =
important, built later.

| # | Requirement | Priority | Plan | PR |
|---|---|---|---|---|
| R1 | Add, edit, mark done / undo, and delete a to-do. | Must | foundation, edit-todo | #5, #9 |
| R2 | An account per person; see only your own data. | Must | accounts | #7 |
| R3 | Several lists per person; an "Inbox" for everyone; rename and delete a list. | Must | lists | #8 |
| R4 | An optional due date; overdue shown in red. | Must | due-date | #10 |
| R5 | Share a list by username; members can work on it and leave it. | Must | sharing | #11 |
| R6 | Clear all done to-dos of a list at once. | Should | clear-completed | #12 |
| R7 | Notes, priority (Low, Medium, High), tags. | Should | description, priority, tags | #13, #14, #15 |
| R8 | Steps inside a to-do. | Should | subtasks | #16 |
| R9 | Repeat daily, weekly or monthly; Done makes the next copy; Undo removes it unless work was done on it. | Should | recurring, recurring-undo-steps, recurring-copy-rules | #20, #40, #50 |
| R10 | Search, filter (All, Not done, Done) and sort (created, due, priority, title). | Should | search, filter, sort | #21, #23, #24 |
| R11 | A manual order by drag and drop or Move buttons, shared by everyone on the list. | Should | drag-and-drop | #25 |
| R12 | A Mac notification with the to-dos due today (code built; not switched on). | Should | reminders | #27 |
| R13 | Light and dark, following the system. | Should | dark-mode | #6 |
| R14 | A landing page for visitors, with real screenshots and no user data. | Should | (no plan file) | #29 |
| R15 | Norwegian letters: title sort a-z, æ, ø, å; search in any case; list names unique ignoring case. | Should | nordic-letters, list-name-casefold | #41, #49 |
| R16 | Done and Undo are safe on a double click and keep your place. | Must | safe-toggles | #44 |
| R17 | Accessible: named buttons, 44px touch targets, clear errors, kept focus. | Must | accessibility-pass | #45 |
| R18 | Backups: `make backup`, a safe `make reset`, a daily copy on `make run`. | Must | local-safety, backup-on-run | #43, #48 |
| R19 | Undo a delete for 15 minutes. | Must | delete-undo | #51 |
| R20 | Refuse to start on a server with a missing or weak secret key. | Must | safe-settings | #36 |

## 6. Success measures (simulated)

The app has **no analytics** (on purpose), so nothing below is measured. These are the targets a
team would set, and how they could be checked **locally**, without tracking anyone. See the
[tracking plan](tracking-plan.md) for an opt-in proposal.

| Measure | Target (simulated) | How it could be checked |
|---|---|---|
| A new person adds their first to-do without help | 5 of 5 test participants | Usability test ([UX findings](../design/ux-test-plan-and-findings.md)) |
| Lost to-dos reported by the people using it | 0 per month | Asking them; Undo and backups exist |
| Time to add a to-do with a due date | under 15 seconds | Stopwatch in a usability test |
| Shared lists in use | at least 1 list with 2 or more people | The owner looks in `/admin/` |
| Automated tests | all green on every merge | CI (real: required by the ruleset on `main`) |

## 7. Open questions

1. Should a person be able to **delete their own account**? Today only the admin can
   ([data inventory](../design/data-inventory-and-privacy.md), gap 1).
2. Should the daily **reminders** be switched on? It needs the owner's own launchd setup
   ([reminders runbook](../runbooks/reminders.md)).
3. Should members of a shared list also get reminders? Needs a per-person "reminded" table
   (`docs/plans/reminders.md`).
4. Will it ever run on a **server**? Then: a persistent database, a password-attempt limit, closed
   sign-up, and backups off the machine.
5. Should the app show a hint about the manual order? (Simulated UX finding F8.)
6. Should the admin log stop keeping object names? ([data inventory](../design/data-inventory-and-privacy.md),
   gap 6; gaps 2, 4 and 5 are closed.)

## Related documents

- [User research notes](user-research-notes.md)
- [Prototype](../design/prototype.md), [UX test plan and findings](../design/ux-test-plan-and-findings.md)
- [Design doc](../design/design-doc.md), [ADRs](../adr/README.md)
- [Tracking plan](tracking-plan.md), [Experiment doc](experiment-doc.md)
- [Ticket](../process/ticket.md), [Changelog](../../CHANGELOG.md)
- [Feature plans](../plans/)
