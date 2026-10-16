# Feature plans

One plan per feature, written, reviewed and approved by the owner **before** the code. A plan is
**history**: it says what was decided and why, at the time. The code and `AGENTS.md` describe how
things are now; when they disagree with a plan, the code wins. Never edit a plan's body, only its
Status line (see the Rules in [`AGENTS.md`](../../AGENTS.md)).

How a plan is made and used: [task plan](../process/task-plan.md). A new plan uses the file name
`<feature-slug>.md`, the same slug as its branch `feature/<slug>`.

In the order they were built:

| Plan | What it built | PR | Built |
|---|---|---|---|
| [test-pyramid](test-pyramid.md) | Sort the tests into unit, integration and CUJ | [#1](https://github.com/Compiledex/anyone-can-build-todo/pull/1) | 2026-10-09 |
| [foundation](foundation.md) | Shared form, base page and row template (wave 0) | [#5](https://github.com/Compiledex/anyone-can-build-todo/pull/5) | 2026-10-09 |
| [dark-mode](dark-mode.md) | Follow the system's light or dark mode | [#6](https://github.com/Compiledex/anyone-can-build-todo/pull/6) | 2026-10-09 |
| [accounts](accounts.md) | Sign up, log in, see only your own to-dos | [#7](https://github.com/Compiledex/anyone-can-build-todo/pull/7) | 2026-10-09 |
| [lists](lists.md) | Several lists per person, with an Inbox | [#8](https://github.com/Compiledex/anyone-can-build-todo/pull/8) | 2026-10-09 |
| [edit-todo](edit-todo.md) | Edit a to-do on its own page | [#9](https://github.com/Compiledex/anyone-can-build-todo/pull/9) | 2026-10-09 |
| [due-date](due-date.md) | An optional due date, overdue in red | [#10](https://github.com/Compiledex/anyone-can-build-todo/pull/10) | 2026-10-09 |
| [sharing](sharing.md) | Share a list with other users | [#11](https://github.com/Compiledex/anyone-can-build-todo/pull/11) | 2026-10-09 |
| [clear-completed](clear-completed.md) | Delete all done to-dos of a list at once | [#12](https://github.com/Compiledex/anyone-can-build-todo/pull/12) | 2026-10-09 |
| [description](description.md) | Notes on a to-do | [#13](https://github.com/Compiledex/anyone-can-build-todo/pull/13) | 2026-10-09 |
| [priority](priority.md) | Low, Medium or High | [#14](https://github.com/Compiledex/anyone-can-build-todo/pull/14) | 2026-10-09 |
| [tags](tags.md) | Tags on a to-do | [#15](https://github.com/Compiledex/anyone-can-build-todo/pull/15) | 2026-10-09 |
| [subtasks](subtasks.md) | Steps inside a to-do | [#16](https://github.com/Compiledex/anyone-can-build-todo/pull/16) | 2026-10-09 |
| [recurring](recurring.md) | Repeat daily, weekly or monthly | [#20](https://github.com/Compiledex/anyone-can-build-todo/pull/20) | 2026-10-10 |
| [search](search.md) | Find to-dos by a word | [#21](https://github.com/Compiledex/anyone-can-build-todo/pull/21) | 2026-10-10 |
| [filter](filter.md) | All, Not done or Done | [#23](https://github.com/Compiledex/anyone-can-build-todo/pull/23) | 2026-10-10 |
| [sort](sort.md) | Sort by date added, due date, priority or title | [#24](https://github.com/Compiledex/anyone-can-build-todo/pull/24) | 2026-10-10 |
| [drag-and-drop](drag-and-drop.md) | Your own order by drag and drop | [#25](https://github.com/Compiledex/anyone-can-build-todo/pull/25) | 2026-10-10 |
| [reminders](reminders.md) | A Mac notification for to-dos due today (off by default) | [#27](https://github.com/Compiledex/anyone-can-build-todo/pull/27) | 2026-10-10 |
| [app-redesign](app-redesign.md) | The app gets the landing page's design (with app-redesign-mockup.html) | [#32](https://github.com/Compiledex/anyone-can-build-todo/pull/32) | 2026-10-11 |
| [docs-fixes](docs-fixes.md) | Make the docs match the code | [#35](https://github.com/Compiledex/anyone-can-build-todo/pull/35) | 2026-10-11 |
| [safe-settings](safe-settings.md) | Refuse to start with unsafe production settings | [#36](https://github.com/Compiledex/anyone-can-build-todo/pull/36) | 2026-10-11 |
| [recurring-undo-steps](recurring-undo-steps.md) | Undo keeps a copy with a done step | [#40](https://github.com/Compiledex/anyone-can-build-todo/pull/40) | 2026-10-11 |
| [nordic-letters](nordic-letters.md) | Sort and search æ, ø and å correctly | [#41](https://github.com/Compiledex/anyone-can-build-todo/pull/41) | 2026-10-11 |
| [local-safety](local-safety.md) | make backup, a safe make reset, #tag search | [#43](https://github.com/Compiledex/anyone-can-build-todo/pull/43) | 2026-10-11 |
| [safe-toggles](safe-toggles.md) | Done and Undo say what they want, and keep your place | [#44](https://github.com/Compiledex/anyone-can-build-todo/pull/44) | 2026-10-11 |
| [accessibility-pass](accessibility-pass.md) | Named buttons, bigger touch targets, clear errors | [#45](https://github.com/Compiledex/anyone-can-build-todo/pull/45) | 2026-10-11 |
| [maintenance-pass](maintenance-pass.md) | Shared test helpers, tidy code, no new behaviour | [#46](https://github.com/Compiledex/anyone-can-build-todo/pull/46) | 2026-10-11 |
| [backup-on-run](backup-on-run.md) | make run makes a daily backup first | [#48](https://github.com/Compiledex/anyone-can-build-todo/pull/48) | 2026-10-11 |
| [list-name-casefold](list-name-casefold.md) | List names unique ignoring case, also æ, ø, å | [#49](https://github.com/Compiledex/anyone-can-build-todo/pull/49) | 2026-10-11 |
| [recurring-copy-rules](recurring-copy-rules.md) | Undo keeps a changed copy; Repeat on a done to-do makes the copy | [#50](https://github.com/Compiledex/anyone-can-build-todo/pull/50) | 2026-10-11 |
| [delete-undo](delete-undo.md) | Undo after deleting a to-do | [#51](https://github.com/Compiledex/anyone-can-build-todo/pull/51) | 2026-10-11 |
| [cleanups](cleanups.md) | Rename / to home, lighter list HTML, shorter AGENTS.md | [#52](https://github.com/Compiledex/anyone-can-build-todo/pull/52) | 2026-10-11 |

The plans themselves were merged in PRs #3, #4 (fixes), #26 (reminders), #30 (redesign), #34, #39, #42 and #47.
