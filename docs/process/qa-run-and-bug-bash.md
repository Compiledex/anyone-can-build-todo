# QA run and bug bash: release v0.5.0

| | |
|---|---|
| Type | QA checklist and bug bash report |
| Phase | Production |
| Written by | QA lead (in this project: the checklist by the owner and Claude; the bug bash is simulated) |
| Status | Done |
| Date | 2026-10-16 |
| Data | MIXED (see below) |

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

> **What this document is.** Before a release, a QA (quality assurance) lead walks through the
> app's most important journeys by hand, with a checklist, so nothing big is broken on the day
> people get it. A *bug bash* is a short meeting where several people try to break the app at the
> same time. Without this step, a team learns about broken journeys from its users.

The **checklist** (part 1) is real: every step uses a real feature and real words from the app.
The **bug bash** (part 2) is simulated, except the rows marked **REAL**.

## Part 1. The release checklist (real)

Run it on the owner's Mac, against a **scratch copy** of the data, never the only copy:

1. `make backup` first (see [deployment runbook](../runbooks/deployment.md)).
2. `make check` must pass (731 tests: CUJ 30, Integration 577, Unit 124, as in PR #53).
3. Start with `make run` and open <http://127.0.0.1:8000/>.
4. Use two test accounts made for this run, for example `qa-anna` and `qa-ben`. Never your real account.

Tick each line. "Expected" is what must happen. Any other result is a bug: file it with the
[bug template](../bug-reports/README.md).

### Accounts and lists

| # | Step | Expected | Source |
|---|---|---|---|
| 1 | Log out. Open `/`. | The landing page with "Create an account" and "Log in". No user data. | PR #29 |
| 2 | Create an account `qa-anna`. | You are logged in. A list "Inbox" is already there. | PR #7, PR #8 |
| 3 | Make a list "Home". Then try a list "HOME". | "HOME" is refused: the name is already used (case does not matter, also for æ, ø, å). | PR #49 |
| 4 | Rename "Home" to "Hjem". Delete it. | Delete asks "Delete this list and its N to-dos?" first. | PR #8 |

### To-dos, steps and repeat

| # | Step | Expected | Source |
|---|---|---|---|
| 5 | Add "Buy milk" with a due date yesterday, priority High, tags `shop, home`. | The row shows High, the date, **Overdue** in red, and `#home` `#shop`. | PR #10, #14, #15 |
| 6 | Edit the title to an empty text. Save. | The page title starts with "Error: ", a "Not saved." line has focus, nothing changed. | PR #45 |
| 7 | Add two steps. Tick one. | The row says "Steps: 1 of 2 done". | PR #16 |
| 8 | Click Done, then Undo. | The row is crossed out, then normal again. The page stays at that row. | PR #44 |
| 9 | Set Repeat "Weekly" on a to-do with a due date. Click Done. | A new copy appears, due on the next date after today (in Tokyo). | PR #20 |
| 10 | Click Undo on the done to-do. | The copy is removed again. | PR #20 |
| 11 | Repeat step 9, then edit the copy's title. Undo the first one. | The copy stays: "... was kept, because it was changed after it was made." | PR #50 |
| 12 | Set Repeat with no due date. | "A repeating to-do needs a due date." under Due date. | PR #43 |

### Find, sort, order

| # | Step | Expected | Source |
|---|---|---|---|
| 13 | Search `#shop`, then `MILK`. | Both find "Buy milk". "Show all" brings back the whole list. | PR #21, #43 |
| 14 | Filter Not done, then Done. | Only those rows show. Reload: the same view. | PR #23 |
| 15 | Sort by Title with "Ål", "Øl", "Banan". | Banan, Øl, Ål (a to z, then æ, ø, å). | PR #41 |
| 16 | Sort Manual. Drag a row. Then use the Move buttons. | The new order stays after a reload. | PR #25 |
| 17 | In Manual, type a search. | The drag handles and Move buttons are gone (no reorder while searching). | `todos/queries.py` `can_reorder` |

### Delete, undo, clear

| # | Step | Expected | Source |
|---|---|---|---|
| 18 | Delete a to-do with tags and steps. Click Undo in the message. | "Restored “…”." with its tags and steps back, in the same place. | PR #51 |
| 19 | Double-click Delete fast, then Undo. | The to-do comes back with its tags and steps. | PR #51, [BUG-001](../bug-reports/BUG-001-double-delete-loses-steps-and-tags.md) |
| 20 | Mark two to-dos done. Clear completed. Yes, delete them. | Only the done ones are gone. A message says how many. | PR #12 |

### Sharing (needs both test accounts)

| # | Step | Expected | Source |
|---|---|---|---|
| 21 | As `qa-anna`, share "Inbox" with `qa-ben`. | `qa-ben` is listed under the list's members. | PR #11 |
| 22 | As `qa-ben`: open "Shared with me", add and finish a to-do. | It works. There is no Rename, Delete or Share control. | PR #11 |
| 23 | As `qa-ben`, open the address of one of anna's lists that is **not** shared. | "Not found" (404), as if it did not exist. | AGENTS.md rules |
| 24 | As `qa-ben`, "Leave this list". | It asks once more first. Then the list is gone for ben. | PR #45 |

### Look, phone, keyboard

| # | Step | Expected | Source |
|---|---|---|---|
| 25 | Switch macOS to dark mode. | Every page turns dark, and all text is readable. | PR #6, `todos/static/todos/tokens.css` |
| 26 | Make the window 375px wide (phone width). | No sideways scroll. Buttons at least 44px tall under a finger. | PR #32, #45 |
| 27 | Use only the keyboard: Tab to a row, Done, Delete, Move. | A focus ring is always visible. Each button reads e.g. "Done: Buy milk". | PR #45 |
| 28 | Add steps with the keyboard only. | After "Add step", focus stays in that row's step field. | PR #45 |

Stop here and fix first if any line in "Accounts", "Sharing" or "Delete" fails: those are S1/S2
(see [severity levels](../bug-reports/README.md#severity-levels)).

## Part 2. Bug bash (simulated)

**When:** 45 minutes, on the build of v0.5.0 (`main` after PR #52, see the
[changelog](../../CHANGELOG.md)). **Who:** five invented team members. (They are not the invented
users of the [user research](../product/user-research-notes.md) and the
[UX test](../design/ux-test-plan-and-findings.md).)

| Person | Role in the bash | Focus |
|---|---|---|
| Hanna | Facilitator, keeps time | Sharing between two accounts |
| Jonas | Developer | Delete, Undo, repeat |
| Leila | Designer | Dark mode, phone width |
| Mateo | Support | First-time sign-up, wrong input |
| Priya | Accessibility tester | Keyboard and screen reader only |

**Plan of the 45 minutes:** 5 min intro and test accounts, 30 min free testing (each person their
focus, then swap), 10 min to read out the findings and give each a severity.

### Results (simulated, except rows marked REAL)

Rows 1 to 3 are **real** bugs from this project, found before the bash. They are listed so the
team can check them again by hand. Rows 4 to 8 are the (simulated) bash itself.

| # | Found by | What happened | Severity | Outcome |
|---|---|---|---|---|
| 1 | **REAL:** code review of PR #51 | Two fast clicks on Delete, then Undo: the to-do came back **without its steps and tags**. In the bash (simulated), Jonas re-checked it by hand (checklist step 19): fixed. | S2 | Fixed before merge in PR #51. See [BUG-001](../bug-reports/BUG-001-double-delete-loses-steps-and-tags.md). |
| 2 | **REAL:** code review of PR #48 | A failed daily backup said "Today's copy is already there", and `make run` showed no warning. | S2 | Fixed before merge in PR #48. See [BUG-002](../bug-reports/BUG-002-failed-backup-reported-as-success.md). |
| 3 | **REAL:** seen on the list page (PR #28) | A two-line title ran under the priority label, and Delete jumped to a new line (1280px wide). | S4 | Fixed in PR #28. |
| 4 | Leila | (simulated) In dark mode, the tag chips felt "too bright" next to the title. | S4 | Contrast measured: passes 4.5 : 1. Kept as a design note, no change. |
| 5 | Priya | (simulated) With a screen reader, "Undo" in a row and "Undo" in the delete message sounded the same. | S3 | Real in history: PR #51 named the message button "Undo delete: <title>". Re-checked: passes. |
| 6 | Hanna | (simulated) `qa-ben` could not see who else is a member of the shared list. | none | Works as designed: members do not see each other (AGENTS.md). Closed as "not a bug". |
| 7 | Mateo | (simulated) The Undo button was gone after a coffee break. | none | Works as designed: Undo lasts 15 minutes (`UNDO_SECONDS` in `todos/undo.py`). Closed. |
| 8 | Jonas | (simulated) Searching only `#` showed the whole list. | S4 | Invented for practice. Not checked against the code; would need a ticket and a test first. |

**Summary (simulated):** 5 new findings in 45 minutes, plus the 3 real bugs re-checked (all
already fixed before release). 2 findings were "works as designed", which tells us the README
could explain sharing and Undo better.
No S1. Release decision: **go**.

## Related documents

- [Bug triage process](../bug-reports/README.md) and the real bug reports
  [BUG-001](../bug-reports/BUG-001-double-delete-loses-steps-and-tags.md),
  [BUG-002](../bug-reports/BUG-002-failed-backup-reported-as-success.md),
  [BUG-003](../bug-reports/BUG-003-daily-name-matches-non-ascii-digits.md)
- [Deployment runbook](../runbooks/deployment.md), [Release notes](../../CHANGELOG.md)
- [Test plan](test-plan.md), [UX test plan and findings](../design/ux-test-plan-and-findings.md)
- Plans: [`delete-undo.md`](../plans/delete-undo.md), [`accessibility-pass.md`](../plans/accessibility-pass.md)
