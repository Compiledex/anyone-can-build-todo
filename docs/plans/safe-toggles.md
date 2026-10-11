# Plan: Done and Undo say what they want, and keep your place

Status: **done** (2026-10-11)

Builds on: **recurring** (`make_next_copy`, `get_next_copy`, the Undo rule in `todo_toggle`),
**subtasks** (`subtask_toggle`, `back_to_steps`), **sharing** (members may mark done and undo),
**filter** and **search** (`back_url`, `redirect_back`), and the two plans in flight that merge
first: **nordic-letters** (`todos/queries.py`, `todos/sqlite_functions.py`, `todos/apps.py`) and
**recurring-undo-steps** (Undo keeps the next copy when one of its steps is done). This plan
assumes both are on `main`.

## Words used in this plan

- **Toggle**: a button that flips a value: on becomes off, off becomes on.
- **Idempotent**: doing it twice has the same result as doing it once. "Make it done" is
  idempotent; "flip it" is not.
- **Fragment**: the part of an address after `#`, like `#todo-7`. The browser does not send it to
  the server. It scrolls the page to the element with that `id`.
- **Autofocus**: an HTML attribute that puts the cursor in a field when the page opens.

## What is wrong today

Facts, checked on `main` (commit `6c7169b`) and on `feature/recurring-undo-steps`:

- `todo_toggle` in `todos/views.py` does `todo.done = not todo.done`. The button only says "flip".
  So a double click, a second tab that still shows the old page, or two members who click at the
  same moment, flip the to-do twice: it ends up **not done**. On a repeating to-do the second flip
  is an Undo, which **deletes the next copy** that the first click made (unless a step of the
  copy is done, after recurring-undo-steps). The transaction in `todo_toggle` does not help: it
  makes the two clicks run one after the other, and each one flips.
- `subtask_toggle` does the same with a step: `subtask.done = not subtask.done`.
- After Done, Undo or Delete, the page goes back to the list (with the same search and filter,
  through `next`), but at the **top**. On a long list, the person must scroll down again to find
  where they were. `todo_move` and the step views already go back to the row with `#todo-<pk>`;
  Done, Undo and Delete do not.

## Goal

Done means "make this done" and Undo means "make this not done". If it already is, nothing
happens: no flip, no new copy, no deleted copy. The same for steps. After Done, Undo or Delete,
the page opens at the same row (after Delete: the next row), not at the top.

## Decisions

### 1. The form sends the state it wants: a hidden `done` field

Each to-do's Done/Undo form gets `<input type="hidden" name="done" value="1">` (Done) or
`value="0"` (Undo). Each step's Done/Undo form gets the same. The value comes from the state the
page showed, so a stale page asks for what the person saw on the button.

`todo_toggle` and `subtask_toggle`:

1. Find the object first, as today (`get_visible_todo` / `get_visible_subtask`), so a stranger
   gets 404 before anything else (the same "404 before 400" rule as `todo_move`).
2. Read `request.POST.get("done")`: `"1"` means True, `"0"` means False. Anything else, also a
   missing value, gives `400 Bad Request` ("Done must be 0 or 1.") and changes nothing. No old
   page can send nothing: the app runs on one Mac, and a page opened before the change only
   needs a reload. A strict rule is easier to trust than a fallback that flips.
3. If the object already has that state: do nothing (no save, no copy, no delete, no message),
   and go back as usual.
4. Otherwise set it. For a to-do this runs the recurring rules exactly as today:
   - now done: `todo.make_next_copy(timezone.localdate())`;
   - now not done: the Undo rule from recurring-undo-steps, unchanged (delete the copy if it is
     not done, in the same list and has no done step, with "was removed."; keep it with "was
     kept, because a step in it is already done." when a step is done; say nothing for a copy
     that is done or in another list).

`todo_toggle` keeps its `transaction.atomic()` and still reads the to-do inside it. With SQLite's
`IMMEDIATE` mode, two clicks at the same time run one after the other; the second one now sees
the new state and does nothing. `subtask_toggle` needs no transaction: setting a value twice is
safe. It saves with `save(update_fields=["done"])`.

The URL names stay `todo_toggle` and `subtask_toggle`. Renaming them touches many tests and
templates for no gain.

### 2. No message when nothing changes

When the state is already right, the page simply shows it (done, crossed out; or not done). A
message like "It was already done" would mostly show up after a double click, where it only
confuses. Decided by the orchestrator; see below.

### 3. Done and Undo go back to their row; Delete goes to the next row

The row forms already carry `next` = `back_url` (the list with the same search, filter and
order). This plan adds a fragment to that value, in the template:

| Button | `next` | Why |
|---|---|---|
| Done / Undo, no filter | `{{ back_url }}#todo-<pk>` | The row stays on the page. |
| Done / Undo, with a filter (the **cleaned** `status` is `open` or `done`) | `{{ back_url }}#<anchor after removal>` | With "Not done", a done row leaves the page (and with "Done", an undone row). |
| Delete | `{{ back_url }}#<anchor after removal>` | The row is gone. |

"With a filter" means the cleaned `status` that `render_list_page` already gives the template
(from `TodoQueryForm`), never `request.GET`: `?status=bogus` shows every row, so it counts as no
filter.

The **anchor after removal** is the next row of the page as shown (`todo-<pk of the next row>`),
or, for the last row, the row before it, or, for the only row, `todos` (the list itself; the
`<ul class="todos">` gets `id="todos"`).

`render_list_page` works it out once:

```python
def anchors_after_removal(pks):
    """For each row: the anchor to open after it leaves the page.

    The next row, else the row before, else the list itself ("todos").
    """
```

It is a pure function (a list of numbers in, a dict out), in `todos/views.py` next to
`back_to_steps`. `render_list_page` evaluates the to-dos once (`rows = list(todos)`; that fills the
queryset's cache, so `todos` stays a `QuerySet`, the template reads the cache, and the number of
queries does not change), then sets `todo.anchor_after_removal` on each row. The template uses
only that attribute and `todo.pk`: numbers from the database. Nothing from the request goes into
a fragment.

Search (`q`) without a filter does not change: a search does not depend on `done`, so after Done
the row is still shown.

### 4. `redirect_back` does not change

`url_has_allowed_host_and_scheme` looks at the scheme and the host, not the fragment. Checked
on 2026-10-11 with Django 5.2: `/lists/1/?q=a#todo-5` and `/lists/1/#todos` are accepted;
`//evil.example/#todo-1` and `/\evil.example#todo-1` are refused. `#todo-1` alone passes
Django's check (it has no host), but `redirect_back` refuses it with its own `startswith("/")`
rule. Either way they fall back to the list. A fragment is never run as code by the browser, so even
`/lists/1/#javascript:...` (accepted) is harmless. `back_url` cannot carry a `#` of its own:
`request.GET.urlencode()` writes `#` as `%23`. Tests pin all of this.

### 5. The "New to-do" field keeps its autofocus

Checked on 2026-10-11 with the project's Playwright Chromium: on a long page whose first field has
`autofocus`, opening it with no fragment focuses the field and stays at the top; opening it with
`#target` (an element that exists) scrolls to the target and focuses **nothing**. That is the HTML
rule ("flush autofocus candidates" skips autofocus when the document has a target element). Every
anchor this plan writes names an element that exists (the row, a neighbour, or `#todos`), so the
autofocus never pulls the page back to the top. A CUJ test pins this. If the target is gone
(someone else deleted the neighbour a moment before), the page opens at the top with the cursor
in "New to-do", as today. That is harmless.

The accessibility plan changes this autofocus for `?open=` (the steps); see "Working next to".

## Security

- **No new view, URL or form.** Who may click does not change: `get_visible_todo` and
  `get_visible_subtask` first, so a stranger or a former member gets 404, also with a bad `done`
  value (404 before 400). Existing tests cover the 404s; new ones cover the bad value.
- **POST only and CSRF** as today (`@require_POST`).
- **`done` is read strictly**: only `"0"` or `"1"`. It is never saved as text, only used to pick
  True or False.
- **Open redirect**: unchanged `redirect_back`; new tests show a fragment does not open a way
  around it.
- **Fragments come from database numbers**, written by the template; the request never writes a
  fragment.
- **The recurring copy is safer**: a double click or a stale tab can no longer delete it.

## Data and migrations

No model change, no migration, no data change. Going back: revert the commit.

## Working next to

Merge order of the four audit plans: **safe-toggles (this) → accessibility-pass →
local-safety → maintenance-pass**.

- `docs/plans/accessibility-pass.md` changes the same templates (`_todo_item.html`: the row
  buttons get `aria-label`s; `todo_list.html`) and the same autofocus. It merges after this plan
  and keeps the hidden `done` and `next` inputs.
- `docs/plans/local-safety.md` changes `todos/queries.py`, `todos/models.py`, `todos/forms.py`,
  the `Makefile` and `README.md`. No shared code with this plan; only `AGENTS.md` rows.
- `docs/plans/maintenance-pass.md` moves tests out of `todos/tests/integration/test_views.py`
  and adds shared test helpers. It merges last, so it moves the tests this plan adds.

## Not part of this task

- A confirmation or an "undo" for deleting one to-do (Left for the person).
- A warning when two members edit the same to-do (Left for the person).
- Undo keeping a copy that was edited (Left for the person).
- Keeping the place after Edit, Add, Clear completed or the list actions.
- Any change to `todo_move`, `todo_reorder` or `back_to_steps`.

## Changes to files

| File | Change |
|---|---|
| `todos/views.py` | `todo_toggle` and `subtask_toggle` read `done` (decision 1); `anchors_after_removal(pks)`; `render_list_page` evaluates the rows once and sets `anchor_after_removal`; docstrings. |
| `todos/templates/todos/_todo_item.html` | Hidden `done` in the to-do's Done/Undo form and in each step's Done/Undo form; `next` with the fragment (decision 3). |
| `todos/templates/todos/todo_list.html` | `id="todos"` on `<ul class="todos">`. |
| `todos/tests/unit/test_anchors.py` (new) | Unit tests for `anchors_after_removal`. |
| `todos/tests/integration/test_views.py` | New tests in `ToggleTests`, `DeleteTests`, `RecurringTests`; the existing toggle posts send `done` (see "Existing tests that must change"). |
| `todos/tests/integration/test_subtasks.py` | New step tests; the step toggle posts send `done`. |
| `todos/tests/integration/test_sharing.py` | Two-member tests; the toggle posts send `done`. |
| `todos/tests/integration/test_filter.py` | The hidden `next` checks and `RedirectBackTests.toggle()` (see below). |
| `todos/tests/integration/test_reorder.py` | Its one toggle post sends `done`. |
| `todos/tests/cuj/test_journeys.py` | New `test_done_keeps_the_place`. |
| `AGENTS.md` | `todos/views.py` row (toggle reads `done`, nothing happens when already in that state, 400 for a bad value; Done/Undo/Delete go back to the row or the next row); `_todo_item.html` row (hidden `done`, `next` with the anchor); `todo_list.html` row (`id="todos"`); intro ("marking it done makes its next copy" stays true). |

## Existing tests that must change

A toggle post without `done` is now 400, so every test that posts to `todo_toggle` or
`subtask_toggle` must send it. Rule: **a helper takes `done` as an explicit argument** (`True`
or `False`, sent as `"1"` or `"0"`). It never reads `todo.done` from a Python object, because
that object can be stale (the test already clicked, the database changed, the object did not).

| Test or helper | Change | Why |
|---|---|---|
| `test_filter.py` `RedirectBackTests.toggle(data=None, client=None, **extra)` (6 callers) | `toggle(done, data=None, client=None, **extra)`; it adds `done` to the posted data. Each caller says which state it wants. | 400 without `done`. |
| `test_filter.py` `test_row_forms_carry_current_address` (line ~142) | The hidden `next` value becomes `{url}?q=milk&amp;status=open#todos` (the only row, with a filter: both Done and Delete use the anchor after removal). `count=2` stays. | Decision 3. |
| `test_filter.py` `test_bad_add_page_links_go_to_the_list` (line ~222) | The one `count=2` check becomes two checks, each `count=1`: Done's `next` is `{url}#todo-<pk>`, Delete's is `{url}#todos`. | Decision 3: no filter, so Done keeps its row and Delete goes to the list. |
| `test_sharing.py`, the 14 posts to `todo_toggle` (and `make_weekly_milk` users) | Each post sends `done`; where a local helper exists, it gets the `done` argument. | 400 without `done`. |
| `test_views.py` `ToggleTests` (the existing tests) and `RecurringTests.toggle(todo, client=None)` | `toggle(todo, done, client=None)`; every caller passes `True` or `False`. | 400 without `done`. |
| `test_subtasks.py`, the step toggle posts | Send `done`. | 400 without `done`. |
| `test_reorder.py`, its one toggle post | Sends `done=1`. | 400 without `done`. |

## Steps

1. **Tests first.** Write the unit and integration tests below, and change the existing toggle
   posts to send `done` (they must still pass on today's code: today `done` is ignored). Run
   `make unit integration`: the new ones fail (today a second Done flips back; there is no
   anchor; a bad `done` is not 400). Show the person the failures.
2. `anchors_after_removal` and the change in `render_list_page`.
3. `todo_toggle` and `subtask_toggle`.
4. The templates.
5. The CUJ test; `make cuj`.
6. `make test`: all pass, also the query-count tests (`test_list_query_count_does_not_grow_*`,
   the step and search ones): evaluating the rows once adds no query.
7. Update `AGENTS.md`. `make check`, commit. In the last commit set this plan's Status to
   `**done** (<date>)`.

## Tests

### Unit: `todos/tests/unit/test_anchors.py` (`SimpleTestCase`)

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_no_rows` | `anchors_after_removal([])` is `{}`. | A crash on an empty list. |
| `test_one_row_goes_to_the_list` | `[5]` gives `{5: "todos"}`. | Pointing at the removed row itself. |
| `test_next_row_else_previous` | `[5, 6, 7]` gives `{5: "todo-6", 6: "todo-7", 7: "todo-6"}`. | Always the previous row, or the last row pointing nowhere. |

### Integration

`todos/tests/integration/test_views.py`:

| Test | What it checks | The break that fails it |
|---|---|---|
| `ToggleTests.test_done_twice_stays_done` | Two posts with `done=1`: the to-do is done. | Today's flip. |
| `ToggleTests.test_undo_twice_stays_not_done` | A done to-do, two posts with `done=0`: not done. | Today's flip. |
| `ToggleTests.test_done_and_undo_still_work` | `done=1` on an open to-do makes it done; `done=0` makes it not done again (the "something happens" case). | Ignoring `done` and never changing. |
| `ToggleTests.test_bad_done_value_is_400` | Missing, `""`, `"yes"`, `"2"` (subtests): 400 and the to-do does not change. | Treating a bad value as a flip or as "done". |
| `ToggleTests.test_bad_done_value_from_stranger_is_404` | bob posts `done=x` for alice's to-do: 404, not 400. | Checking `done` before finding the to-do (it would tell that the to-do exists). |
| `ToggleTests.test_page_sends_the_state_it_wants` | On the list page an open to-do's form has `<input type="hidden" name="done" value="1">` and a done one `value="0"` (`assertInHTML` on the form). | A template that leaves `done` out. |
| `ToggleTests.test_done_goes_back_to_its_row` | The `next` posted from the page (read from the page's hidden input) ends with `#todo-<pk>`, and the redirect keeps it (`assertRedirects`, `fetch_redirect_response=False`). | No fragment. |
| `ToggleTests.test_done_in_not_done_filter_goes_to_the_next_row` | `?status=open` with three to-dos: the middle row's Done `next` ends with `#todo-<third pk>`. With `?status=bogus` (all rows shown) it ends with `#todo-<middle pk>`. | Pointing at the row that leaves the page, or reading `request.GET` instead of the cleaned status. |
| `ToggleTests.test_next_with_a_fragment_keeps_the_same_site_rule` | `next` = `//evil.example/#todo-1`, `/\evil.example#todo-1`, `#todo-1` (subtests; the last one is refused by `redirect_back`'s own `startswith("/")` rule, not by Django): goes to the list; `next` = `/lists/<pk>/?q=a#todo-<pk>`: goes there. | A change that accepts a fragment-only or other-site address. |
| `DeleteTests.test_delete_goes_to_the_next_row` | Three to-dos: Delete on the first goes to `#todo-<second>`, on the last to `#todo-<second>`; the only to-do goes to `#todos`. | No fragment, or the deleted row's own anchor. |
| `RecurringTests.test_double_done_keeps_one_copy` | `self.weekly`: two posts with `done=1`. The original is done and there is exactly one copy. | Today: the second click is an Undo and deletes the copy. |
| `RecurringTests.test_double_undo_removes_the_copy_once` | Done, then two posts with `done=0`: not done, no copy, exactly one "was removed." message in all (the test loads the list page between the posts, as the browser does, so the first message is shown and not read again). | A second Undo doing anything. |
| `RecurringTests.test_undo_of_an_open_todo_keeps_a_kept_copy` | Done, mark a step of the copy done, Undo (kept, as in recurring-undo-steps), Undo again: the copy and its done step are still there, and the second Undo adds no message. | Running the Undo rule when nothing changes. |

`todos/tests/integration/test_sharing.py` (`MemberCanTests`; alice and bob each have a client):

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_two_members_click_done_once_each` | Repeating milk. alice posts `done=1`; bob (page from before) posts `done=1`. Milk is done; one copy. | Today: bob's click undoes milk and deletes the copy. |
| `test_stale_undo_does_not_undo_new_work` | alice Done, alice Undo (copy removed), bob's stale tab posts `done=0`: nothing changes, no message for bob. | A flip on a stale page. |

`todos/tests/integration/test_subtasks.py`:

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_step_done_twice_stays_done` | Two posts `done=1`: the step is done. | Today's flip. |
| `test_step_done_and_undo_still_work` | `done=1` then `done=0`: done, then not done. | Ignoring `done`. |
| `test_step_bad_done_value_is_400` | Missing or `"yes"`: 400, no change; bob with a bad value: 404. | A bad value flipping, or 400 before 404. |
| `test_step_form_sends_the_state_it_wants` | The step's form has the hidden `done` with `1` or `0`. | Leaving it out. |

### CUJ: `todos/tests/cuj/test_journeys.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_done_keeps_the_place` | 40 to-dos, phone size (390 x 844). Click Done on row 30 (`get_by_role("button", name="Done")` inside that row). After the page loads: row 30 is in the viewport (`to_be_in_viewport`), it has the done class, and "New to-do" is **not** focused. Then Delete on row 30: row 31 is in the viewport. | No fragment; autofocus pulling the page to the top; the wrong neighbour. |

## Decided by the orchestrator for the person (2026-10-11, person away)

- **The form sends the wanted state** (`done=1` or `0`); a missing or bad value is 400, with no
  fallback flip.
- **No message when nothing changes.**
- **Done/Undo go back to their own row; Delete, and Done/Undo with a filter, go to the next row**
  (or the one before, or the list).
- **"New to-do" keeps its autofocus**: the browser already skips it when the address has a
  fragment (checked in Chromium).
- **The URL names `todo_toggle` and `subtask_toggle` stay.**

## Left for the person

- **Confirm or undo a single Delete** of a to-do. Today one click deletes it (and its steps).
  Recommended: an "Undo" message link would need a soft delete (a migration); not now, unless
  it bites you.
- **A warning when two members edit the same to-do at the same time.** The last Save wins today.
  Recommended: not now; the app has a few people per list.
- **A tab opened before this update** sends no `done` and gets a bare "400 Bad Request" page;
  reloading the page fixes it. Recommended: accept it (one Mac, one reload).
- **Undo keeping a copy that was edited** (title, notes, priority, tags). Recommended: not now
  (see recurring-undo-steps).

## Review

Verification by the planner (2026-10-11), against `main` (`6c7169b`) and the two branches in
flight:

- Confirmed: `todo_toggle` and `subtask_toggle` flip (`not todo.done`, `not subtask.done`).
  A double Done on a repeating to-do runs Undo on the second click and deletes the copy.
- Confirmed: Done/Undo/Delete redirect to `next` without a fragment; `todo_move` and
  `back_to_steps` already use `#todo-<pk>`.
- Confirmed with Django 5.2 (a small script): `url_has_allowed_host_and_scheme` accepts same-site
  paths with a fragment and refuses `//evil.example/#...` and a backslash. `#...` alone passes
  Django's check; `redirect_back`'s own `startswith("/")` rule refuses it.
- Confirmed in Chromium (a small Playwright script): autofocus is skipped when the address has a
  fragment that names an element, and used when it has none. So the request "drop the autofocus
  or only use it without a fragment" needs **no code**: the browser already does the second.
  WebKit (Safari) follows the same HTML rule, but no test here runs WebKit, so that part is
  PLAUSIBLE.
- Found while checking: the hidden `next` is compared as exact HTML in `test_filter.py` (lines
  142 and 222). Those two lines change, on purpose.
- Found while checking: `test_sort.py` reads `response.context["todos"].query`, so the view must
  keep `todos` a `QuerySet`; `list(todos)` only fills its cache. Written into decision 3.
- Found while checking: in a "Not done" or "Done" filter the toggled row leaves the page, so its
  own anchor would point nowhere and the autofocus would win. Decision 3 uses the next row there.

The plan review (2026-10-11) said APPROVE WITH CHANGES. What changed:

- The toggle test helpers take an explicit `done` argument, never derived from a possibly stale
  object; the new table "Existing tests that must change" lists them (`RedirectBackTests.toggle`
  with 6 callers, 14 posts in `test_sharing.py`, `ToggleTests`, `RecurringTests.toggle`, steps,
  reorder).
- `test_filter.py` line ~222: Done gets `#todo-<pk>` and Delete `#todos`, so its `count=2` check
  becomes two checks; line ~142 keeps `count=2` (both `#todos`).
- Wording: Django's check accepts `#todo-1`; `redirect_back` refuses it with its own
  `startswith("/")` rule. The subtest stays.
- "With a filter" means the cleaned `status`, not `request.GET` (`?status=bogus` shows all rows);
  a test case added.
- Left for the person: a tab opened before the update gets a bare 400 until reloaded.
