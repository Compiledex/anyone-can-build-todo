# User research notes: how people keep and share to-dos

| | |
|---|---|
| Type | User research notes (interview synthesis) |
| Phase | Idea |
| Written by | UX researcher (in this project: simulated) |
| Status | Done |
| Date | 2026-10-16 |
| Data | SIMULATED (the feature links at the end are real) |

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

> **What this document is.** Research notes record what real people said and did in interviews,
> and what the team learned from it. A UX researcher or product manager writes them early, before
> the requirements are fixed. Without research, a team builds what it guesses people need, and
> often builds the wrong thing.

## 1. Goal

Learn how people keep their to-dos today, how they share them with others, and what makes them
lose things or stop using a tool.

## 2. Method

- **Six semi-structured interviews** (a list of questions, but the talk can follow the person),
  30-40 minutes each, by video call.
- Each person showed the tool or paper they use now ("show me your list").
- Notes were written during the call; quotes are written down as said. No recording.
- After the interviews, the notes were grouped by theme on a board (**affinity mapping**: putting
  similar notes together to find patterns).

Questions (short version): How do you keep track of things to do? Show me. Who else is on your
lists? Tell me about the last time something was forgotten or done twice. What made you stop using
an app?

## 3. Participants

| Id | Name | Role | Age range | Tools used now | Shares lists with |
|---|---|---|---|---|---|
| P1 | Ingrid | Nurse, shift work | 35-44 | Paper on the fridge | Partner |
| P2 | Tomas | Student | 18-24 | Phone notes app | Flatmates (3) |
| P3 | Amara | Accountant, uses a screen reader part time | 45-54 | Spreadsheet | Nobody |
| P4 | Kenji | Software tester | 25-34 | Team task board at work, nothing at home | Sister |
| P5 | Sofie | Parent of two | 35-44 | Family chat group | Partner, older child |
| P6 | Erik | Retired, volunteer | 65+ | Paper notebook | Club board (4) |

## 4. Key quotes

- "Bread is on three lists and the chat. Nobody knows which one is true." (P5)
- "I tap the wrong thing on my phone all the time, and then it's gone." (P2)
- "Every Monday I write 'water plants' again. I just want it to come back by itself." (P1)
- "My big jobs are really ten small jobs. I want to tick the small ones." (P6)
- "The work board sends everything to some cloud. For home stuff I don't want that." (P4)
- "If a button just says 'Delete', my reader says 'Delete, Delete, Delete'. Which one?" (P3)
- "I don't want my flatmates to see my own list. Only the shopping one." (P2)
- "I sort my list by hand. Most important on top. Apps always sort by date." (P6)
- "The day ends at midnight here, not in some other country." (P4)

## 5. Themes

| Theme | What we heard | Heard from |
|---|---|---|
| T1. One shared truth | Lists in many places; things bought twice or forgotten. | P1, P2, P5, P6 |
| T2. Fear of losing things | A wrong tap deletes; no way back. | P2, P5, P1 |
| T3. Repeating chores | Writing the same chore every week. | P1, P5 |
| T4. Big tasks are many small ones | Want to tick parts of a task. | P6, P4 |
| T5. Privacy | Do not want home lists in a company's cloud; want some lists private. | P4, P2, P3 |
| T6. Own order | Want to choose the order, not only by date. | P6, P1 |
| T7. Access | Screen reader names, small buttons on a phone. | P3, P2 |
| T8. Find things | Long lists; want to find by a word or a tag. | P4, P5 |

## 6. Insights and the feature each one maps to

The features are real; the link from the interviews to them is simulated (the features were
planned by the owner, not because of these interviews).

| Insight | Real feature | Source |
|---|---|---|
| T1: one list that several people see and change. | Sharing a list by username; members add, edit, mark done. | `docs/plans/sharing.md`, PR #11 |
| T1: the same order for everyone. | The manual order belongs to the list. | `docs/plans/drag-and-drop.md`, PR #25 |
| T2: a slip must be undoable. | Undo after Delete (15 minutes); safe Done/Undo. | PR #51, PR #44 |
| T2: never lose everything. | `make backup`, a daily copy on `make run`. | PR #43, PR #48 |
| T3: a chore comes back by itself. | Repeat daily, weekly or monthly. | `docs/plans/recurring.md`, PR #20 |
| T4: tick small parts. | Steps inside a to-do. | `docs/plans/subtasks.md`, PR #16 |
| T5: data stays at home; some lists private. | Runs only on the owner's Mac; you see only your own and shared lists. | `docs/plans/reminders.md`, PR #7 |
| T6: own order. | "Sort by: Manual", drag and drop and Move buttons. | PR #25 |
| T7: named buttons, bigger targets. | Accessibility pass. | `docs/plans/accessibility-pass.md`, PR #45 |
| T8: find by word or tag. | Search, filter, sort; `#tag` search. | PR #21, #23, #24, #43 |
| P4's midnight quote. | "Today" is the date in the owner's time zone. | [ADR 0004](../adr/0004-today-in-asia-tokyo.md) |

## 7. Surprises and open points

- Nobody asked for email reminders; two people said they ignore email from apps. (Matches the
  real choice of Mac notifications, [ADR 0008](../adr/0008-mac-notifications-via-osascript.md).)
- P6 wanted to print a list. Not built; not in the [PRD](prd.md).
- P5 wanted the child to see but not change the list ("read-only member"). Not built: members can
  always change to-dos.

## 8. Limits of this research

Six people, all invented, one round. A real study would recruit from the real users (the owner
and the people they share with), and test ideas with them again after the first build.

## Related documents

- [Product requirements](prd.md)
- [UX test plan and findings](../design/ux-test-plan-and-findings.md)
- [Prototype](../design/prototype.md)
- [Tracking plan](tracking-plan.md)
