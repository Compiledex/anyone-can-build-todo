# Test plan: Undo after deleting a to-do

| | |
|---|---|
| Type | Test plan (with the project's test strategy) |
| Phase | Build |
| Written by | QA engineer or the developer who builds the feature (in this project: the planner wrote the test tables in `docs/plans/delete-undo.md`; the implementer built them; the code reviewer added guard tests) |
| Status | Done |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A test plan says how we will know a feature works: which cases are
> tested, at which level, and by which test. A QA engineer or the developer writes it before the
> code, and the reviewer checks it. Without one, tests cover what was easy to test, not what
> could break.

## Part 1: Test strategy (for every feature)

### Three layers

A *test pyramid*: many fast, small tests at the bottom, a few slow, real ones at the top.

| Layer | Folder | What it is | Base class | Count today |
|---|---|---|---|---|
| CUJ | `*/tests/cuj/` | A critical user journey: a real Chromium browser (Playwright) clicks through the app on a real server | `BrowserTestCase` (`todos/tests/cuj/browser.py`) | 30 |
| Integration | `*/tests/integration/` | Django's test client: a request goes from the address to the database and back | Django `TestCase`, often `LoggedInTestCase` | 577 |
| Unit | `*/tests/unit/` | One function on its own, no requests, no database | `SimpleTestCase` | 124 |

The counts are from `make check` on this branch (from `main` at `59b7de2`): 731 in all.

### The layer rules are checked by code

`config/test_runner.py` finds each test's layer from its folder. Before any test runs,
`check_layers` stops the run when:

- a test is in no `unit/`, `integration/` or `cuj/` folder;
- a unit test is not a `SimpleTestCase` (or is a `TransactionTestCase`), so it cannot use the
  database;
- a CUJ test is not a `StaticLiveServerTestCase` (`BrowserTestCase` is one, and is the class to
  extend, because it starts the browser).

At the end it prints one line per layer, for example `Integration  577 passed`.

### Rules for writing tests (from `AGENTS.md`)

1. **Test each rule once, in the lowest layer where a person would notice it.** "Undo needs a
   POST" is an integration test, not a browser test. A browser test is only for a journey that
   needs JavaScript, focus, or the real page.
2. **Tests first, shown failing.** The new tests are written and run before the code, and the
   failure is shown to the owner. Then the code makes them pass.
3. **Every new view gets a 404 test for another user**, with `assertOtherUserGets404` from
   `accounts/tests/helpers.py` (bob asks for alice's thing), and a check that the data did not
   change.
4. **Every test names its break.** The plan's test tables have a column "the break that fails
   it". In review, mutation testing checks that the break really fails it (see
   [pr-review-by-risk.md](pr-review-by-risk.md)).
5. **No real side effects.** Tests never use `db.sqlite3` (Django makes a test database), never
   port 8000, and never show a real Mac notification (`FakeOsascriptMixin`).

### Commands

`make unit`, `make integration`, `make cuj` run one layer; `make test` runs all; `make check`
runs the commit checks, the migration check and all tests. CI runs the same on every push.

## Part 2: The test plan for delete-undo

Files: `todos/tests/unit/test_undo.py` (1 test), `todos/tests/integration/test_delete_undo.py`
(30 tests in the classes `DeleteTests`, `UndoTests`, `SharedUndoTests`, `RecurringUndoTests`),
and `DeleteAndUndoTests.test_delete_and_undo` in `todos/tests/cuj/test_todo_basics.py`.

### Delete

| Case | Layer | Test |
|---|---|---|
| Delete shows "Deleted “…”." and a POST Undo form with CSRF and `next` ending in `#todo-<id>` | Integration | `test_delete_shows_message_with_undo` |
| The row and its steps are really gone (no soft delete) | Integration | `test_delete_still_deletes_at_once` |
| Two Deletes at once: the second gets 404 and does not replace the good snapshot | Integration | `test_double_delete_does_not_replace_the_snapshot` |
| A message is a `<div>` and the form is inside it | Integration | `test_message_is_a_div` |
| A title like `<b>x</b>` is escaped in the messages | Integration | `test_message_escapes_the_title` |

### Undo

| Case | Layer | Test |
|---|---|---|
| The snapshot holds every concrete `Todo` field | Unit | `test_snapshot_fields_are_every_todo_field` |
| Every field, tags, steps (and done states), place and `created_at` come back, same id | Integration | `test_undo_restores_everything` |
| Goes back to the row (`next` + `#todo-<id>`); a bad `next` goes to the list | Integration | `test_undo_goes_back_to_the_row` |
| Undo twice: one to-do, one message | Integration | `test_undo_works_only_once` |
| Double submit with the old session put back: restores once, no 500 | Integration | `test_double_submit_with_the_old_session_restores_once` |
| The id is taken by another to-do: "Could not undo.", the other one untouched | Integration | `test_id_taken_by_another_todo` |
| Two deletes: only the last message has the button | Integration | `test_two_deletes_only_the_last_message_has_undo` |
| No snapshot: no button and no 500 | Integration | `test_no_undo_button_without_snapshot`, `test_no_undo_button_for_a_message_without_its_snapshot_after_login` |
| The list page drops a snapshot older than 15 minutes | Integration | `test_expired_snapshot_is_dropped_by_the_list_page` |
| Only the last delete can be undone | Integration | `test_only_the_last_delete_can_be_undone` |
| After 15 minutes: "Too late to undo"; at 14 minutes it works | Integration | `test_undo_after_the_time_limit` |
| The button's accessible name is "Undo delete: <title>" | Integration | `test_undo_button_names_the_deleted_todo` |
| No extra queries on the list page with a snapshot | Integration | `test_list_query_count_does_not_change` |

### Access and safety

| Case | Layer | Test |
|---|---|---|
| Another user gets 404 (`assertOtherUserGets404`); nothing restored | Integration | `test_stranger_gets_404` |
| A stranger posting Undo for a to-do that exists gets 404 | Integration | `test_stranger_gets_404_for_an_existing_todo` |
| A snapshot of another user is not offered and not used | Integration | `test_snapshot_of_another_user_is_not_offered_or_used` |
| `GET` gives 405 | Integration | `test_get_is_405` |
| Log out and in again: 404 | Integration | `test_logout_ends_the_undo` |

### Shared lists

| Case | Layer | Test |
|---|---|---|
| A removed member cannot undo: "you can no longer see the list" | Integration | `test_member_undo_after_being_removed` |
| A member who still is a member can undo | Integration | `test_member_can_undo` |
| The list was deleted: the same message, no 500 | Integration | `test_undo_after_the_list_was_deleted` |
| The tags go to the list owner, not the member | Integration | `test_tags_go_to_the_list_owner` |

### Repeating to-dos

| Case | Layer | Test |
|---|---|---|
| The links between a to-do and its copy come back, both ways | Integration | `test_recurring_links_come_back` |
| A restored copy that was not changed still counts as unchanged | Integration | `test_restored_copy_still_counts_as_unchanged` |
| A link already taken is not stolen | Integration | `test_recurring_link_not_stolen` |

### The journey

| Case | Layer | Test |
|---|---|---|
| Delete the middle of three to-dos, see "Deleted", click "Undo delete: …": the row is back in the middle, in view, with its step, and the button is gone | CUJ | `test_delete_and_undo` |

Only this one case is a browser test: it needs the real page (the place in the list, the scroll
to the row). Everything else is checked faster in the integration layer.

## Differences from the plan's test tables

- The plan listed 23 integration tests. 7 more were added: `test_member_can_undo` and
  `test_no_undo_button_for_a_message_without_its_snapshot_after_login` while building; four guard
  tests from the code review (commit `57dec28`); and `test_restored_copy_still_counts_as_unchanged`
  after merging plan A (commit `b1745b0`).
- Not tested on purpose: an Undo button from an older delete in a second tab gives a plain 404
  (a known limit), and a restored to-do hidden by the current filter (accepted).

## Related documents

- [ticket.md](ticket.md): the acceptance criteria these tests cover
- [task-plan.md](task-plan.md): where the test tables were first written
- [pr-review-by-risk.md](pr-review-by-risk.md): mutation testing against these tests
- [qa-run-and-bug-bash.md](qa-run-and-bug-bash.md): testing by hand after merge
- [../plans/delete-undo.md](../plans/delete-undo.md), [../plans/test-pyramid.md](../plans/test-pyramid.md), PR #1 (the test pyramid), PR #51
