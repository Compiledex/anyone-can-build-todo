# Tracking plan: local, opt-in usage counts

| | |
|---|---|
| Type | Tracking plan (analytics event specification) |
| Phase | Analysis |
| Written by | Product analyst with the tech lead (in this project: simulated, written by Claude) |
| Status | Proposed (not built) |
| Date | 2026-10-16 |
| Data | MIXED (see below) |

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

> **What this document is.** A product analyst writes a tracking plan before anyone adds
> analytics to a product. It lists the questions the team wants answered, and the exact events
> (things the app records, like "a to-do was deleted") that answer them, with their properties.
> Without it, teams collect too much, collect personal data by accident, or collect data that
> answers nothing.

## 1. The real situation today

This part is real.

- The app collects **no analytics**. It records no usage events and sends **nothing** to any
  other computer. This is on purpose: privacy is a feature of the app. (The only records of
  activity are Django's admin log (without names) and the development server's request lines in the terminal;
  see the [data inventory](../design/data-inventory-and-privacy.md), section 7.)
- The app runs only on the owner's Mac (decided on 2026-10-10, `docs/plans/reminders.md`; there
  is no deploy). The data is in one SQLite file, `db.sqlite3`, which is not in git (`AGENTS.md`).
- The pages load no scripts from other sites. The landing page has "No JavaScript and nothing
  from other sites" (`AGENTS.md`, `todos/templates/todos/landing.html`). The only app script is
  `todos/static/todos/reorder.js` (drag and drop).
- The only thing that leaves the web app is a local macOS notification (`todos/reminders.py`),
  and it is not switched on.

**Nothing in the rest of this document exists in the code.** It is a proposal, written to show
how a real team would plan tracking that keeps these promises.

## 2. Questions we want answered (simulated)

| # | Question | Why it matters |
|---|---|---|
| Q1 | Do people use steps (`Subtask`)? How many to-dos have at least one step? | Steps add HTML to every row (`test_list_page_size.py`). If nobody uses them, we could hide them. |
| Q2 | Does Undo after Delete get used? How soon after the delete? | Decides the 15-minute window (`UNDO_SECONDS` in `todos/undo.py`). See the [experiment](experiment-doc.md). |
| Q3 | Do shared lists stay active? Do members add or change to-dos, or only look? | Sharing is the most complex access rule (`visible_to`). Is it worth it? |
| Q4 | Which sort and filter do people use on the list page? | `SORT_OPTIONS` has several orders. Maybe the default should change. |
| Q5 | How often is "Clear completed" used compared with one-by-one Delete? | Clear completed cannot be undone. If it is common, people may need Undo there too. |

## 3. Events (simulated)

An **event** is one row that says "this happened, now". A **property** is a small fact stored
with it.

**The hard rule:** no event ever stores a to-do title, notes, a tag name, a step title, a list
name or a username. Only counts, database ids, booleans (true/false) and fixed words from the
code (like a sort key).

| Event name | When it fires | Properties |
|---|---|---|
| `todo_created` | A to-do is saved from the add form | `list_id`, `list_is_shared` (bool), `has_due_date` (bool) |
| `todo_toggled` | Done or Undo changed the state (not when nothing changed) | `todo_id`, `new_done` (bool), `made_copy` (bool, a recurring copy was made) |
| `todo_deleted` | One to-do is deleted | `todo_id`, `step_count`, `tag_count`, `list_is_shared` (bool) |
| `todo_undo_delete` | Undo after Delete is pressed | `todo_id`, `seconds_since_delete`, `result` (`restored` / `id_taken` / `no_access`) |
| `step_added` | A step is added to a to-do | `todo_id`, `step_count_after` |
| `step_toggled` | A step is marked done or not done | `todo_id`, `new_done` (bool) |
| `list_shared` | The owner adds a member | `list_id`, `member_count_after` |
| `list_left` | A member leaves a list | `list_id`, `member_count_after` |
| `completed_cleared` | "Clear completed" deletes done to-dos | `list_id`, `deleted_count` |
| `list_viewed` | The list page is shown | `list_id`, `sort` (a key of `SORT_OPTIONS`), `status` (empty for All, `open` or `done`), `has_search` (bool, never the words) |

Every event also has `id`, `created_at` (`timezone.now()`: stored in UTC, shown in Tokyo time), and `actor_is_owner`
(bool: the list owner or a member). It does **not** store who the actor is.

For Q3, "active" means: a shared list has at least one `todo_created`, `todo_toggled` or
`step_toggled` event from a member in the last 14 days.

## 4. Where the data would be stored (simulated)

- In a **separate local SQLite file**, `usage.sqlite3`, next to `db.sqlite3`, with one table
  `usage_event`. A separate file, because `make backup` and the daily backup copy `db.sqlite3`
  (`todos/backup.py`); usage data should not spread into every backup.
- **Opt-in:** off by default. The owner turns it on with one setting on a settings page. When it
  is off, nothing is written, not even a counter.
- **Deletable:** one button, "Delete all usage data", empties the table. Deleting the file has
  the same effect.
- **Nothing is sent.** No network call, no third-party script, no cookie for tracking. The owner
  reads the numbers on a local page or with a `manage.py` command.

## 5. Retention (simulated)

| Data | Kept for | How it is removed |
|---|---|---|
| Single events | 90 days | A daily cleanup, run by `make run` like the daily backup |
| Monthly counts (for example "deletes in September: 41") | 2 years | Replaced when the month is counted again |
| Everything | Until the owner presses "Delete all usage data" | That button, or deleting `usage.sqlite3` |

## 6. Privacy review checklist (simulated)

Each line must be "yes" before any code is written.

- [ ] No event stores free text that a person typed (titles, notes, tags, steps, list names,
      search words).
- [ ] No event stores a username, email, IP address or browser details.
- [ ] Ids are only database numbers, and they never leave the Mac.
- [ ] Tracking is off until the owner turns it on, and the setting says plainly what is kept.
- [ ] A member of a shared list is told, on the list page, that the owner counts usage (members
      are other people).
- [ ] There is one button that deletes all usage data.
- [ ] The usage file is not in git (`.gitignore`) and not in the backups.
- [ ] No network request is added. A test checks that the event code imports no HTTP library.
- [ ] Retention (90 days) is enforced by code, with a test, not only by this document.
- [ ] `AGENTS.md` gets a row for the new file and a rule "never log user text".

## 7. Risks (simulated)

- **Ids can still point to people.** `todo_id` plus the real `db.sqlite3` tells which to-do it
  was. That is acceptable only because both files stay on the same Mac with the same owner.
- **Members did not agree.** A member's actions are counted on the owner's machine. This needs
  the notice in the checklist, or member actions should not be counted at all.
- **Small numbers mislead.** With one or a few people, most numbers are noise (see the
  [experiment doc](experiment-doc.md), section 5).

## 8. Decision

**Not built.** Status: Proposed. The value is small for an app with one real user, and the cost
is real: a new file, a settings page, a cleanup job and a privacy promise to keep. If the app ever
has more users, start from this plan, and run the privacy review again.

## Related documents

- [Experiment doc](experiment-doc.md): the Undo-window experiment that would use these events
- [Retrospective](../retrospectives/2026-10-16-project-retrospective.md)
- [Data inventory and privacy](../design/data-inventory-and-privacy.md)
- [PRD](./prd.md)
- [Design doc](../design/design-doc.md)
- Plan: [`docs/plans/delete-undo.md`](../plans/delete-undo.md) (Undo after Delete, PR #51)
- Plan: [`docs/plans/subtasks.md`](../plans/subtasks.md) (steps, PR #16)
- Plan: [`docs/plans/sharing.md`](../plans/sharing.md) (shared lists, PR #11)
