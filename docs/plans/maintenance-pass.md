# Plan: a maintenance pass (tidy code and tests, no new behaviour)

Status: **approved** (2026-10-11, by the orchestrator for the person), not started.

Builds on: everything on `main`, plus the plans that merge before this one:
**nordic-letters**, **recurring-undo-steps**, **safe-toggles**, **accessibility-pass** and
**local-safety**. This plan merges **last**, so it tidies what they added too.

## Words used in this plan

- **Refactor**: changing how code is written without changing what it does.
- **Helper**: a small function that several tests share, so it is written once.
- **Behaviour-preserving**: every page, address, message and saved value is the same before and
  after. The proof is that the existing tests pass without changes to what they check, and the
  number of tests in each layer stays the same (or grows only by the new tests named here).

## What is wrong today

Facts, checked on `main` (commit `6c7169b`):

1. **Copied test helpers.** `add`/`make_todo` (a to-do in a list) is written six times
   (`test_filter.py`, `test_reorder.py`, `test_search.py`, `test_sort.py`, `test_reminders.py`,
   `test_views.py`), `shown` (the titles on the page, from `response.context["todos"]`) four
   times, `messages_of` twice (`test_views.py`, `test_sharing.py`), and the inner
   `count_queries()` with `CaptureQueriesContext` three times (`test_search.py`,
   `test_subtasks.py`, `test_views.py` twice). Three `HTMLParser` classes read pages:
   `PageParts` in `accounts/tests/integration/test_auth_pages.py`, another `PageParts` in
   `todos/tests/integration/test_landing.py`, and `Labels` in `test_list_page_labels.py`.
2. **One big test file.** `todos/tests/integration/test_views.py` is 1174 lines with 11 classes:
   list, add, toggle, delete, login, data isolation, admin, edit, priority, tags and recurring.
3. **The filter labels are written twice**: `TodoQueryForm.STATUS_CHOICES` in `forms.py` and a
   list `[("", "All"), ("open", "Not done"), ("done", "Done")]` in `render_list_page`.
4. **200 is written by hand**: `maxlength="200"` for "New to-do" (`todo_list.html`) and "New step"
   (`_todo_item.html`), and "A step needs a title of 1 to 200 characters." in `subtask_add`. The
   model already says `max_length=200` for both titles.
5. **CSS leftovers** in `app.css`: `.count` (no element has that class; it came from the mockup),
   and the overdue color written for `.overdue time, .overdue-label` and then `.overdue-label`
   again in a second block. `.button-small` in `app.css` is not used by an app page (only the
   visitor pages use it, from `site.css`), but it belongs to the shared button vocabulary.
6. **Two ways to drop the label colon**: `NoColon` in `todos/forms.py`, and `__init__` that sets
   `self.label_suffix = ""` in both forms of `accounts/forms.py`.
7. **`signup` has no method rule**: every other view has `@require_GET`, `@require_POST` or
   `@require_http_methods`. A `PUT` to `/accounts/signup/` shows the form.
8. **`Todo.Meta.ordering = ["created_at"]`** has no tiebreak; `TodoList` has `["created_at",
   "pk"]` and `Subtask` `["created_at", "id"]`. The list page never uses it (`apply_list_query`
   always sorts), but the admin and `the_list.todos.all()` do.
9. **A stale comment** in `todos/templates/todos/site_base.html`: "The logged-in app pages use
   base.html instead, which does not change." `base.html` changed in the app redesign.
10. **An undocumented rule**: `list_leave` finds the list with `members=request.user`. The header
    comment of `views.py` and rule 2 in `AGENTS.md` only name `visible_to` and
    `owner=request.user`.
11. **Hidden inputs by hand**: the search form writes `status` and `sort`, and the sort form `q`
    and `status`, each with its own `{% if %}`.
12. **A missing test**: "Move down" on the last row is tested (`test_move_down_on_last_changes_nothing`),
    "Move up" on the first row is not.
13. **A timed wait in a CUJ test**: `test_escape_cancels_a_drag` ends with
    `page.wait_for_timeout(300)` and then checks that no request was sent. On a slow machine 300ms
    can be too short (a false pass); it always costs 300ms.
14. **README**: "How it is put together" is a 40-row table that repeats `AGENTS.md`, and step 8
    shows exact test counts (`24`, `406`, `107`) that are wrong after every feature.

## Goal

The same app, easier to change: shared test helpers, smaller test files, each fact written
once, no dead CSS, one way to drop the colon, one method rule on every view, a stable default
order for to-dos, correct comments and docs, two missing tests, and no timed wait.

## Decisions

### 1. Shared test helpers, in the existing helper modules

`todos/tests/helpers.py` gets plain functions:

| Helper | What it does |
|---|---|
| `add_todo(todo_list, title, **fields)` | `Todo.objects.create(todo_list=todo_list, title=title, **fields)`. |
| `shown_titles(response)` | `[todo.title for todo in response.context["todos"]]`. |
| `messages_of(response)` | `[str(m) for m in get_messages(response.wsgi_request)]`. |
| `count_queries(func)` | Runs `func()` inside `CaptureQueriesContext(connection)` and returns the number of queries. |

`accounts/tests/helpers.py` gets **one** `PageParts(HTMLParser)` with what every page test
needs: `elements` (tag, attributes, in order), `links` (href, text), `buttons` (text),
`text_by_id`, `labels` (for, text, wraps a field) and `ids`, plus `parse_page(response)`.
`test_auth_pages.py` and `test_list_page_labels.py` use it. The landing page's parser also
collects pictures, `srcset` files and sizes; that part stays in `test_landing.py` as
`class LandingParts(PageParts)` that adds only those. (Merging the image code into the shared
class would make it big for one page.)

Each test file keeps a one-line wrapper where it has its own defaults (for example
`test_reminders.py`'s `add` with `due_date=TODAY`, `test_reorder.py`'s `shown(client)` with the
manual order), and the wrapper calls the shared helper.

### 2. `test_views.py` is split by feature

| New file | Classes from `test_views.py` |
|---|---|
| `test_edit.py` | `EditTests` |
| `test_priority.py` | `PriorityTests` |
| `test_tags.py` | `TagTests` |
| `test_recurring.py` | `RecurringTests` |
| `test_access.py` | `open_view_names`, `LoginRequiredTests`, `OnlyMyDataTests`, `AdminTests` |
| `test_views.py` (stays) | `ListTests`, `AddTests`, `ToggleTests`, `DeleteTests` |

A class moves **whole**, with its tests unchanged (only imports change). The tests added by the
earlier plans move with their class.

Correction to the request: `FillPositionMigrationTests` is not in `test_views.py`; it is in
`todos/tests/integration/test_reorder.py` (line 197). It moves to `test_migrations.py`, next to
the other migration tests, unchanged (it stays a `LoggedInTestCase`: it calls the migration's
function directly and does not migrate the database).

Check: `make test` prints the same count per layer before and after the move (plus the two new
tests of this plan).

### 3. Each fact once

- `render_list_page` builds the filter links from `[("", "All"), *TodoQueryForm.STATUS_CHOICES]`.
  The labels stay "All", "Not done" and "Done"; the exact-HTML filter tests check that.
- The title limit: `render_list_page` passes `title_max_length` (from
  `Todo._meta.get_field("title").max_length`) and `step_max_length` (from `Subtask`) to the
  template; the two `maxlength` attributes use them. `subtask_add` builds its message from the
  `Subtask` limit. The page and the message stay the same (`200`).
- `accounts/forms.py`: `LoginForm(NoColon, AuthenticationForm)` and `SignupForm(NoColon,
  UserCreationForm)`, `NoColon` imported from `todos.forms` (accounts already imports from
  `todos`: `accounts/views.py` uses `TodoList`). The `__init__` that sets `label_suffix` goes
  away. `SignupForm` keeps its `__init__` only for the help texts from accessibility-pass.
  `AuthenticationForm.__init__(request=None, *args, **kwargs)` passes `label_suffix` on to
  `Form`, so the login page is the same.
- The search form and the sort form write their hidden inputs in a loop over a list that
  `render_list_page` builds from `query_form.cleaned_data` (search form: `status`, and `sort` when
  it is not the default; sort form: `q`, `status`). Same rules as the hand-written `{% if %}`s
  today. Checked: the tests that look at these inputs (`test_sort.py` lines 113-118,
  `test_filter.py` line 97) compare them as HTML (`assertInHTML`, or `assertContains` with
  `html=True`), so the attribute order does not matter; the `assertNotContains(response,
  'name="status"')` check for a bad status still holds, because a bad value is not in
  `cleaned_data`. If one test still breaks, leave this item for later and say so in the PR.


### 4. CSS

- Delete the `.count` rule from `app.css` (the `time` part of that rule stays).
- Overdue: `.overdue time { color: var(--danger); }` and one `.overdue-label { color:
  var(--danger); font-weight: 650; }`. Same look.
- `.button-small` stays in `app.css`, with a comment: "Not used by an app page today; kept so the
  app and the visitor pages share one button vocabulary."

### 5. `signup` gets `@require_http_methods(["GET", "POST"])`

Under `@login_not_required` (that one stays on top, as on `todo_list`). `GET` and `POST` work as
today. Any other method, also `HEAD`, now gets `405` (checked with Django 5.2), the same as the
other form views (`list_create`, `todo_edit`). This is the one visible change, only for methods a
browser never sends to this page.

### 6. `Todo.Meta.ordering = ["created_at", "pk"]`

One migration made with `uv run python manage.py makemigrations todos --name
todo_ordering_tiebreak` (an `AlterModelOptions`; no SQL, no data change). Its number comes after
the last migration on `main` at build time (today `0017_todo_reminded_on`, so `0018`, unless an
earlier plan added one). It only fixes the order of to-dos made in the same microsecond.

### 7. Comments and docs

- `site_base.html`: "The logged-in app pages use base.html instead (tokens.css, then app.css; never
  site.css)."
- `views.py` header and `AGENTS.md` rule 2: "`list_leave` is for members alone: it uses
  `get_object_or_404(TodoList, pk=pk, members=request.user)`, so the owner and strangers get 404."
- README "How it is put together": a short table of the folders and the main files only
  (`config/`, `accounts/`, `todos/` with `models.py`, `views.py`, `queries.py`, `forms.py`,
  `templates/`, `static/`, `tests/`, `deploy/macos/`, `scripts/`, `docs/plans/`), then "Each
  file's job is in `AGENTS.md`."
- README step 8: "You should see something like this (the numbers grow with the app):", then the
  same three lines, so nobody has to update the numbers after each feature.

### 8. Two tests that were missing, and no timed wait

- `test_reorder.py` `test_move_up_on_first_changes_nothing` (the mirror of the "Move down" test).
- `test_escape_cancels_a_drag`: before the drag, an init script wraps `window.fetch` so every
  call is recorded in `window.__fetchCalls`, and adds a `dragend` listener on `document` in the
  **bubbling** phase that counts in `window.__dragEnds`. `reorder.js` handles `dragend` on the
  `<ul>`, which comes first while the event bubbles up, and calls `fetch` there synchronously.
  So after `page.wait_for_function("window.__dragEnds === 1")`, any request would already be in
  `window.__fetchCalls`. The test then checks it is empty. No timeout. If Chromium does not fire
  `dragend` after Escape in Playwright, the test fails clearly at the wait, and the builder keeps
  the old check and says so in the PR.

## Security

- Nothing changes in who may see or change what. The tests in `test_access.py` and every
  `assertOtherUserGets404` move unchanged.
- `signup` gets stricter (only `GET` and `POST`).
- The hidden inputs still come from `cleaned_data` (only valid values), as today.
- `order_by` is not touched (the `Meta.ordering` change is a fixed list in the model).

## Data and migrations

One migration, `AlterModelOptions` on `Todo` (`ordering`). No table or row change. Going back:
`uv run python manage.py migrate todos <the migration before>`, then revert the commit.

## Working next to

Merge order: **safe-toggles → accessibility-pass → local-safety → maintenance-pass (this)**.
This plan is last because it moves the tests the others add, and it reads the new `SignupForm`
help texts and the new hidden inputs. It rebases on `main` right before it starts, and builds the
split from the real file (class names may have grown).

## Not part of this task

- Renaming the `todo_list` URL and view to `home` (Left for the person).
- Trimming `AGENTS.md` rows down to what the docstrings say (Left for the person).
- A threaded test for the `transaction.atomic()` blocks (Left for the person).
- Any change a person can see on a page.

## Changes to files

| File | Change |
|---|---|
| `todos/tests/helpers.py` | `add_todo`, `shown_titles`, `messages_of`, `count_queries`. |
| `accounts/tests/helpers.py` | `PageParts`, `parse_page`. |
| `todos/tests/integration/test_views.py` | Keeps list, add, toggle, delete; uses the helpers. |
| `todos/tests/integration/test_edit.py`, `test_priority.py`, `test_tags.py`, `test_recurring.py`, `test_access.py` (new) | The moved classes. |
| `todos/tests/integration/test_migrations.py`, `test_reorder.py` | `FillPositionMigrationTests` moves; the new Move-up test. |
| `test_filter.py`, `test_search.py`, `test_sort.py`, `test_reminders.py`, `test_sharing.py`, `test_subtasks.py`, `test_landing.py`, `test_list_page_labels.py`, `accounts/tests/integration/test_auth_pages.py` | Use the shared helpers. |
| `todos/tests/cuj/test_journeys.py` | `test_escape_cancels_a_drag` without the timed wait. |
| `todos/views.py` | Filter links from `STATUS_CHOICES`; max lengths; the hidden-input lists; the header comment. |
| `todos/templates/todos/todo_list.html`, `_todo_item.html` | `maxlength` from the context; hidden inputs in a loop. |
| `todos/static/todos/app.css` | Decision 4. |
| `accounts/forms.py` | `NoColon`. |
| `accounts/views.py` | `@require_http_methods(["GET", "POST"])` on `signup`. |
| `todos/models.py`, `todos/migrations/00NN_todo_ordering_tiebreak.py` | Decision 6. |
| `todos/templates/todos/site_base.html` | The comment. |
| `README.md`, `AGENTS.md` | Decision 7; the test file rows; `todos/tests/helpers.py` and `accounts/tests/helpers.py` rows list the new helpers; `models.py` row (`Meta.ordering`). |

## Steps

Each step is its own commit, and `make check` passes after each one.

1. Note the per-layer test counts from `make test`.
2. Add the helpers; switch each test file to them, one file at a time.
3. Split `test_views.py`; move `FillPositionMigrationTests`. Same counts as step 1.
4. **Tests first** for the two missing tests: `test_move_up_on_first_changes_nothing` (it passes
   at once: it pins today's behaviour; show that it fails if `todo_move` stops checking
   `0 <= there`), and an `accounts` test that `PUT` to signup is `405` (it fails before decision
   5). Then decision 5.
5. Decisions 3 (each fact once) and 4 (CSS).
6. Decision 6 and its migration (`makemigrations --check` clean afterwards).
7. The CUJ change; `make cuj`.
8. Comments and docs (decision 7). Last commit: Status `**done** (<date>)`.

## Tests

| Layer, file, test | What it checks | The break that fails it |
|---|---|---|
| Integration, `test_reorder.py` `test_move_up_on_first_changes_nothing` | "Move up" on the first row: redirect to `?sort=manual#todo-<pk>`, positions and shown order unchanged. | `todo_move` wrapping around (moving the first row to the end) or crashing at index `-1`. |
| Integration, `accounts/tests/integration/test_accounts.py` `test_signup_only_get_and_post` | `PUT` and `DELETE` to `/accounts/signup/` give 405; `GET` gives 200. | No method rule on `signup`. |
| Unit, `todos/tests/unit/test_models.py` `test_todo_default_order_has_a_tiebreak` | `Todo._meta.ordering == ["created_at", "pk"]`. | Removing the tiebreak. |
| CUJ, `test_escape_cancels_a_drag` (changed) | No reorder `fetch` after Escape, checked after `dragend`, with no timed wait. | `reorder.js` sending on a cancelled drag. |

Everything else is a move or a rewrite of how a test is written; what each test checks does not
change. The per-layer counts prove that no test was lost.

## Decided by the orchestrator for the person (2026-10-11, person away)

- The helpers go in the two existing helper modules; each file may keep a one-line wrapper.
- One shared `PageParts`; the landing page keeps a small subclass for its pictures.
- The split of `test_views.py` as in decision 2; `FillPositionMigrationTests` goes to
  `test_migrations.py`.
- `.button-small` stays in `app.css` with a comment.
- `signup` allows only `GET` and `POST`.
- README: folders and main files, then "see AGENTS.md"; test counts as an example.

## Left for the person

- **Rename the `todo_list` URL and view to `home`.** It is the landing page and the redirect, not
  a list. Recommended: later; many tests and templates use the name.
- **Trim `AGENTS.md` rows to what the code's docstrings say.** The rows are long and repeat the
  code. Recommended: yes, but as its own change, because AI agents depend on that file.
- **A threaded test for the `transaction.atomic()` blocks** (two requests at once). Recommended:
  not now; SQLite's `IMMEDIATE` mode and the idempotent toggles of safe-toggles cover the known
  cases.
- **Lighter list HTML** (`spaceless`). Recommended: not now.

## Review

Verification by the planner (2026-10-11), against `main` (`6c7169b`):

- Confirmed items 1 to 14 with `git grep` and by reading the files named.
- **Corrected**: `FillPositionMigrationTests` lives in `test_reorder.py`, not `test_views.py`.
- **Corrected**: a "Move down on the last row" test already exists; only "Move up on the first
  row" is missing. One test, not two.
- **Narrowed**: the three HTML parsers do different jobs. Only the shared core (elements, links,
  buttons, text, labels) becomes one class; the landing image part stays a subclass.
- **Narrowed**: `.overdue-label` is not a duplicate rule, it is one color rule shared with
  `.overdue time` and a second rule for the weight. The tidy is one rule per selector, the same
  look.
- **Checked**: `.button-small` is used only on the visitor pages (`landing.html`, `login.html`,
  with `site.css`), so `app.css`'s copy is unused but kept on purpose.
- **Checked**: the hidden-input tests (`test_sort.py` lines 113-118, `test_filter.py` line 97)
  compare HTML, not text, so a loop is allowed.
- **Checked**: `require_http_methods(["GET", "POST"])` refuses `HEAD` too; that matches the other
  form views (`list_create`, `todo_edit`).
