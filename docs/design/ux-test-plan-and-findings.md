# UX test plan and findings

| | |
|---|---|
| Type | Usability test plan and findings report |
| Phase | Design |
| Written by | UX researcher (in this project: simulated) |
| Status | Done |
| Date | 2026-10-16 |
| Data | MIXED: the tasks and the app are real; the participants, sessions and findings are simulated |

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

> **What this document is.** A usability test plan says what we want to learn, who will try the
> product, and which tasks they do. The findings report says what went wrong, how bad it is, and
> what to change. A UX researcher writes both, usually before a release and after a big redesign.
> Without a test, the team only learns about confusing screens from angry users, or never.

## 1. Test plan

### Goals

1. Can a new person do the core tasks without help?
2. Do the less common features (steps, repeat, undo, manual order, sharing) make sense?
3. Does the app work with a phone, a keyboard only, and a screen reader?

### Method

- **Moderated sessions** (a facilitator sits with the participant), 30 minutes each, on the
  owner's Mac at `http://127.0.0.1:8000`, with a scratch database (never `db.sqlite3`).
- **Think aloud**: the participant says what they think while they work.
- The facilitator does not help, unless the person is stuck for 2 minutes.
- Measures per task: done without help (yes / with help / no), time, errors, and a 1-5 ease rating.

### Participants (simulated)

| Id | Name | Device | Notes |
|---|---|---|---|
| P1 | Ingrid | Laptop, mouse | Uses paper lists. |
| P2 | Tomas | Phone (narrow browser) | Uses a phone notes app. |
| P3 | Amara | Laptop, keyboard only | Uses a screen reader part of the time. |
| P4 | Kenji | Laptop, trackpad | Uses a team task board at work. |
| P5 | Sofie | Tablet | Shares a shopping list with her family. |

### Tasks (real features)

| # | Task | Feature (source) |
|---|---|---|
| T1 | Create an account, and find your first list. | Accounts, "Inbox" (PR #7, #8) |
| T2 | Add "Pay rent", due on the 1st of next month, priority High. | Due date, priority (PR #10, #14) |
| T3 | Break "Paint the hallway" into three steps, and mark one done. | Steps (PR #16) |
| T4 | Make "Water the plants" repeat every week, then mark it done. | Recurring (PR #20) |
| T5 | Delete a to-do by mistake, then get it back. | Delete undo (PR #51) |
| T6 | Put the three most important to-dos at the top. | Manual order (PR #25) |
| T7 | Share a list with the username `ines`. (Second part, as `ines`: find the shared list.) | Sharing (PR #11) |
| T8 | Find every to-do with the tag `work` that is not done. | Search, filter (PR #21, #23) |

## 2. Results summary (simulated)

| Task | Without help | With help | Failed | Mean ease (1-5) |
|---|---|---|---|---|
| T1 | 5 | 0 | 0 | 4.8 |
| T2 | 4 | 1 | 0 | 4.2 |
| T3 | 4 | 1 | 0 | 4.0 |
| T4 | 3 | 2 | 0 | 3.6 |
| T5 | 5 | 0 | 0 | 4.6 |
| T6 | 3 | 1 | 1 | 3.2 |
| T7 | 4 | 1 | 0 | 4.0 |
| T8 | 2 | 2 | 1 | 3.0 |

## 3. Findings (simulated)

Severity: **High** (blocks the task or loses data), **Medium** (slows or confuses most people),
**Low** (small annoyance). This is a *usability* scale, for how much a finding hurts a person
doing a task. Bugs use the S1 to S4 scale in [bug triage](../bug-reports/README.md#severity-levels);
a High finding that is also a bug (like F2) would get its own S level there.

| # | Finding | Severity | Seen by | Recommendation |
|---|---|---|---|---|
| F1 | After Done on a long list, the page jumped back to the top. "Where was I?" | Medium | P1, P4, P5 | Return to the same row after Done, Undo and Delete. |
| F2 | On the phone, the row buttons were small and close; Tomas hit Delete instead of Done. | High | P2, P5 | Bigger touch targets, with space between them. |
| F3 | The screen reader said "Done, Done, Done, Delete" with no to-do name. | High | P3 | Give each button a name with the to-do's title. |
| F4 | After adding a step, the cursor was not in the "New step" field; three steps took many clicks. | Medium | P1, P3 | Put the cursor in the step field after "Add step". |
| F5 | In the manual order, the buttons moved left on the first and last rows. | Low | P4 | Keep an empty slot where a Move button is missing. |
| F6 | Typing `#work` in search found nothing; people expected the tag. | Medium | P4, P5 | Let `#work` find the tag `work`. |
| F7 | Turning on Repeat without a due date gave an error far from the date field. | Medium | P1, P2 | Show the error on the due-date field. |
| F8 | Some people did not see the drag handle and did not know about Move up / Move down until told to choose "Sort by: Manual". | Medium | P1, P2, P5 | Explain where the manual order is (help text or the landing page). |
| F9 | "Clear completed" removed to-dos a family member had added; Sofie was surprised. | Low | P5 | Keep, but say "of the whole list" in the confirm text. |
| F10 | In the second part of T7, logged in as the member `ines`, Sofie looked for "Rename" and did not find it. | Low | P5 | None: only the owner can rename (decided in the sharing plan). |

### Which findings match a real change

The test is simulated, so it did **not** cause these changes. The changes were planned and built
for their own reasons; they are listed so you can see what a real fix for each finding looks like.

| Finding | Real change |
|---|---|
| F1 | This matches a real change: PR #44 (safe toggles: Done, Undo and Delete return to the row with an anchor like `#todo-7`). |
| F2 | This matches a real change: PR #45 (accessibility pass: every small control is 44px tall and 8px apart under a finger), building on PR #32. |
| F3 | This matches a real change: PR #45 (each button's `aria-label` starts with its word and names the to-do, "Done: Buy milk"). |
| F4 | This matches a real change: PR #45 (after "Add step", the cursor is in the "New step" field). |
| F5 | This matches a real change: PR #45 (a missing Move button leaves a `.move-slot`). |
| F6 | This matches a real change: PR #43 (local safety: `#work` search finds the tag). |
| F7 | This matches a real change: PR #43 (the repeat error is shown on the due-date field). |
| F8 | No real change yet. The landing page (PR #29) shows the manual order, but the app does not. |
| F9 | No change. The confirm already says "This cannot be undone"; members may clear (clear-completed plan). |
| F10 | No change, by design (`docs/plans/sharing.md`). |

## 4. What went well (simulated)

- Everyone found "Inbox" at once after sign-up.
- Undo after Delete was found by all five; "Oh good, it's back."
- Amara could do every task except T6 drag with the keyboard; the Move buttons worked for her.
- Dark mode on Sofie's tablet matched her system without any setting.

## 5. Next steps

1. Add a short hint about the manual order (F8). Low cost, its own plan.
2. Re-test T6 and T8 with three new people after that.
3. A real test with real people before anyone besides the owner relies on the app.

## Related documents

- [Prototype](prototype.md)
- [User research notes](../product/user-research-notes.md)
- [Product requirements](../product/prd.md)
- [Design doc](design-doc.md)
- [QA run and bug bash](../process/qa-run-and-bug-bash.md)
- Plans: [`safe-toggles.md`](../plans/safe-toggles.md), [`accessibility-pass.md`](../plans/accessibility-pass.md), [`local-safety.md`](../plans/local-safety.md)
