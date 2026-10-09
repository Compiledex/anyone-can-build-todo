# Plan: drag and drop to reorder the to-dos

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: accounts (#17), lists (#10), sharing (#18), subtasks (#16), recurring (#8), search
(#12), filter (#13), sort (#14), and the wave 0 foundation (`TodoForm`, the partial
`_todo_item.html`, CSS variables, `todos/templates/base.html`).

## Goal

A person can put the to-dos in a list in **their own order**. They drag a to-do up or down with
the mouse, and the new order is saved. People who cannot drag (keyboard users, screen reader
users, most phones, or a browser with JavaScript turned off) use **Move up** and **Move down**
buttons instead. Both ways save the same order.

This order is one more value of the `sort` field in `TodoQueryForm`: **`manual`**, shown in the
menu as "Manual". The address is `?sort=manual`.

## Decisions

- **A new field, `position`, on `Todo`.** It is a whole number. Smaller numbers come first. The
  order belongs to the **list**, not to the person: everyone who can see a shared list sees the
  same order. One field is enough for that, because a to-do is in exactly one list.
- **No "unique" rule on `position`.** Two to-dos with the same number are allowed in the
  database. A unique rule would make saving a new order fail halfway (two rows have the same
  number for a moment). When two rows have the same number, `created_at` and then `pk` decide, so
  the order is always the same.
- **The migration numbers the to-dos that already exist.** In each list, the to-dos get 1, 2, 3, …
  in the order they were made (`created_at`, then `pk`). So the manual view starts out looking
  exactly like "oldest first".
- **A new to-do goes last, and this is done in `Todo.save()`.** When a **new** to-do is saved (it
  has no `pk` yet), `save()` gives it the biggest `position` in its list, plus 1. Why in the model and not in the add view: there is more than one way to make a
  to-do. The add view (`todo_add`), the copy that recurring (#8) makes when a to-do is marked done,
  and the admin. If only the add view set it, a recurring copy would get `position` 0 and jump to
  the **top** of the manual order. `save()` always sets the number for a new row, even if a value
  was copied from another to-do.
  - Two people adding at the same second may get the same number. That is fine: `created_at`
    breaks the tie, and both are still at the end.
- **Deleting a to-do leaves a gap** (1, 2, 4). Gaps do not matter: only the order of the numbers
  matters. We do not renumber on delete.
- **Marking a to-do done does not move it.** It keeps its place in the manual order.
- **Only to-dos are reordered, not subtasks.** Subtasks (#16) are a separate model, `Subtask`, with
  a link to their `Todo`. They have no `position` field; they stay under their to-do, in the order
  they were made. Moving a to-do moves its subtasks with it, because they are shown inside its
  row.
- **Drag and the Move buttons are shown only in the manual view, and only when no filter or
  search is active.** A **filter** (#13) or a **search** (#12) hides some to-dos. Reordering a
  list where you cannot see every row is confusing, and the server would have to guess where the
  hidden rows go. So in `?sort=manual&status=open` (for example) the list is shown in manual
  order, but with no drag handles and no Move buttons, and a short line says "Clear the filter to
  change the order." Exactly: reordering is allowed when the form is valid, `sort` is `manual`,
  `q` is empty and `status` is empty ("all").
- **One function saves an order:** `save_order(todo_list, ids)` in `todos/ordering.py`. It gives
  the to-dos positions 1, 2, 3, … in the order of `ids`, with `bulk_update`, inside one
  **transaction** (all changes are saved together, or none). Both drag and the Move buttons use
  it, so there is one way to write an order, not two.
- **The server endpoint for drag** (an *endpoint* is one address the server answers) is
  `POST /lists/<int:pk>/reorder/`, named `todo_reorder`. It gets the full new order of the list as
  a repeated form field: `id=7&id=3&id=5`. It saves it, and answers `204 No Content` (it worked,
  nothing to send back).
  - It accepts `POST` only, with the normal Django **CSRF token** (a secret number in each form
    that proves the request came from our own page).
  - The list must be one the person owns or that is shared with them
    (`get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)`). Otherwise: **404**,
    so we do not reveal that the list exists. A member of a shared list may reorder it, because a
    member may already add, edit and delete its to-dos (#18).
  - The ids must be **exactly** the to-dos in that list: every one, once, and nothing
    else. A missing id, an extra id, an id from another list (also another user's list), a
    repeated id, or text that is not a number: **400 Bad Request**, and nothing is saved. Because
    the check compares with the ids **in this list**, an id from someone else's list can never be
    written. Every posted number is read as a **to-do** id, never as a `Subtask` id. A subtask's
    number is just a number: if it is not the id of a to-do in this list, the same check refuses
    it; if it happens to be one, it only names that to-do. This also covers the case where someone else added or deleted a to-do in a shared
    list a second ago: the page is out of date, so we refuse, and the page reloads.
  - The check and the save happen **inside the same transaction**, so a to-do added between the
    check and the save cannot be missed.
  - **Two members reordering at the same time:** the last one to save wins. Both see the order of
    the last save when they reload. We accept this: it is a to-do list, not a shared editor. (On
    SQLite, two saves at the exact same moment may also make one of them fail with "database is
    locked". That person gets an error answer, the page reloads, and they can drag again.)
- **Move up / Move down are normal forms**, not JavaScript: `POST /<int:pk>/move/`, named
  `todo_move`, with `direction=up` or `direction=down`. The server takes the current manual order
  of the list, swaps the to-do with its neighbour, and calls `save_order`. Then it sends the
  browser back to the list at `?sort=manual#todo-<pk>`. The `#todo-<pk>` part (the `<li>` already
  has `id="todo-<pk>"` from subtasks, #16) scrolls back to the moved row, so a keyboard user can
  press Tab and land near it, instead of starting again at the top of the page.
  - The first to-do has no "Move up" button, and the last has no "Move down" button. A move that
    is not possible (for example a crafted request to move the first to-do up) changes nothing and
    still sends the browser back.
  - `direction` that is not `up` or `down`: **400**. Another person's to-do: **404**. (The address
    is the same shape as the other to-do addresses, `/<int:pk>/toggle/`, from lists, #10.)
  - Because `save_order` renumbers the whole list, two to-dos with the **same** `position` still
    swap. No special case is needed.
- **Plain JavaScript with the browser's own drag and drop (the HTML5 drag-and-drop API), in one
  small file**: `todos/static/todos/reorder.js`. No library from a CDN, no build step, no new
  package. A library like SortableJS handles touch screens better, but the Move buttons already
  cover phones, and a CDN adds a third party that can break or change the page. If touch drag is
  wanted later, that is its own task.
- **Only the handle `⠿` is draggable, not the whole row.** If the whole `<li>` had
  `draggable="true"`, the text box for adding a step (#16) inside it would be hard to click and
  select in, and the title text could not be selected. The handle is a `<span draggable="true">`.
  When the drag starts, the code moves the handle's row (`closest("li")`).
- **How the JavaScript works**, in short:
  1. It runs only if the list has the attribute `data-reorder-url` (the template adds it only when
     reordering is allowed).
  2. It looks only at the **direct** rows of that `<ul>` (`:scope > li[data-id]`). Subtasks are
     shown in their own `<ul>` inside a row; they are never moved, and a row is never dropped
     inside them.
  3. While dragging, the row moves in the page as the mouse passes other rows.
  4. When the drag ends, it reads the ids from the rows (`data-id`), in their new order, and sends
     them with `fetch` (the browser's way to send a request without leaving the page). It sends a
     `FormData` made from a small hidden form that has `{% csrf_token %}`, so the token is read
     from the page, not from a cookie.
  5. If the answer is not `204`, or the request fails (no network), it reloads the page, so the
     person sees the order the server really has.
  6. If the person cancels the drag (presses Escape, or drops outside the list), the row goes back
     to where it was, and nothing is sent.
- **The Move buttons stay visible even when JavaScript works.** They are the keyboard way to
  reorder. A drag handle that only works with a mouse is not enough. They are small arrows
  (`↑` `↓`) with an `aria-label` ("Move up: Buy milk"), so a screen reader hears words, and the
  same words as a `title`, so a mouse user sees a tooltip.
- **Manual is not the default sort.** The default stays `created`, as sort (#14) decided. Nothing
  changes for people who never reorder. See Open questions.
- **Static files need no settings change.** Checked in the code: `whitenoise.middleware.
  WhiteNoiseMiddleware` is in `MIDDLEWARE`, `STATIC_ROOT` is set, and the deploy command in
  `README.md` runs `collectstatic`. The browser tests use `StaticLiveServerTestCase`
  (`todos/tests/cuj/browser.py`), which serves files from `static/` folders by itself.
- **No `@login_required`.** Accounts (#17) turned on `LoginRequiredMiddleware`, so every view
  already needs a logged-in user. The new views follow the same rule as the others.

## Not part of this task

- Dragging on touch screens. The HTML5 drag-and-drop API does not work on most phones. Phones use
  the Move buttons.
- Dragging a to-do **into another list**, or into another to-do to make it a subtask. (Lists, #10,
  has no "move to another list", so a to-do never changes list.)
- Reordering subtasks.
- Reordering while a filter or search is active.
- A different order for each person who shares a list.
- Moving with the keyboard **inside** the drag (for example: Space to pick up, arrows to move).
  The Move buttons do this job.
- Live updates: if another person reorders a shared list, you see it when you reload.
- Making "manual" the default sort.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | `position = models.PositiveIntegerField(default=0)` on `Todo`. `save()` sets `position` for a new to-do (see step 4). |
| `todos/migrations/00NN_todo_position.py` | Made by `makemigrations` (adds the field). |
| `todos/migrations/00NN_fill_todo_position.py` | Made with `makemigrations --empty`, then the one `RunPython` function written in it (see step 3). This is the one migration we write code into; Django makes the file, we fill in the function. |
| `todos/ordering.py` (new) | `parse_ids(values)`: turns the posted strings into a list of whole numbers, or raises `ValueError` for text or repeats. Pure Python, so it can be unit tested. `save_order(todo_list, ids)`: checks and saves an order (see step 5). |
| `todos/queries.py` | One entry in `SORT_OPTIONS`: `"manual": ("Manual", ("position", "created_at", "pk"))`. Use `"pk"`, not `"id"`, so #14's tie-breaker unit test keeps passing. The `sort` choices of `TodoQueryForm` are built from `SORT_OPTIONS`, so `forms.py` does not change. A small function `can_reorder(form)`: `True` only when `chosen_sort(form)` is `manual` and there is no `q` and no `status`. |
| `todos/views.py` | New views `todo_reorder` and `todo_move`. `render_list_page` passes `can_reorder` to the template. |
| `todos/urls.py` | `lists/<int:pk>/reorder/` (name `todo_reorder`) and `<int:pk>/move/` (name `todo_move`), the same prefix as the other to-do addresses. |
| `todos/templates/todos/todo_list.html` | `{% load static %}`. The `<ul>` gets `data-reorder-url` when `can_reorder`. The hidden form with `{% csrf_token %}`. `<script src="{% static 'todos/reorder.js' %}" defer>`. The "Clear the filter to change the order." line. |
| `todos/templates/todos/_todo_item.html` | When `can_reorder`: `data-id` on the `<li>`, the handle `<span class="handle" draggable="true" aria-hidden="true">⠿</span>`, and the two Move forms. |
| `todos/static/todos/reorder.js` (new) | The drag and drop code. About 60 lines. |
| Page CSS (in `todos/templates/base.html`) | `.handle { cursor: grab; }`, and a style for the row being dragged (`.dragging`), using the CSS variables, with a dark-mode value. |
| `todos/tests/...` | See Tests. |
| `AGENTS.md`, `README.md` | `position` in the model row; the new files and addresses. |

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in the table under Tests. Run `make test` and show that they fail.

### 2. The model — `todos/models.py`

```python
position = models.PositiveIntegerField(default=0)
```

Do **not** change `Meta.ordering`. The sort choice (#14) decides the order on the page.

### 3. The migrations

```bash
uv run python manage.py makemigrations
uv run python manage.py makemigrations todos --empty --name fill_todo_position
```

In the empty one, write one function and a `RunPython` that calls it. It uses
`apps.get_model("todos", "Todo")`, never `from todos.models import Todo`, because the migration
must use the model **as it was at that point**:

```python
def fill_position(apps, schema_editor):
    Todo = apps.get_model("todos", "Todo")
    current_list = None
    for todo in Todo.objects.order_by("todo_list_id", "created_at", "pk"):
        if todo.todo_list_id != current_list:
            current_list, number = todo.todo_list_id, 0
        number += 1
        todo.position = number
        todo.save(update_fields=["position"])
```

Subtasks are in their own table (`Subtask`) and have no `position`, so they are not touched. The
reverse step is `migrations.RunPython.noop`: going back just drops the field.
(Inside a migration, `save()` is Django's plain one, not our version from step 4, because
`apps.get_model` gives a model without our own methods. That is what we want here.)

Then `uv run python manage.py migrate`.

### 4. A new to-do goes last — `Todo.save()`

```python
def save(self, *args, **kwargs):
    if self.pk is None:
        biggest = Todo.objects.filter(todo_list=self.todo_list).aggregate(
            biggest=Max("position")
        )["biggest"]
        self.position = (biggest or 0) + 1
    super().save(*args, **kwargs)
```

`Max` is Django's aggregate. `self.pk is None` means "not in the database yet". Check how the
recurring copy (#8) is made: if it uses `pk = None` and then `save()`, this works too.

### 5. `todos/ordering.py`

- `parse_ids(values)`: takes the list of strings from `request.POST.getlist("id")`. Returns a list
  of `int`. Raises `ValueError` if a value is not a whole number, or if an id appears twice. An
  empty list is allowed here; `save_order` checks it against the real list.
- `save_order(todo_list, ids)`: inside `transaction.atomic()`, read the list's to-dos.
  If `set(ids)` is not exactly the set of their ids, or `len(ids)` is different, raise
  `ValueError` and save nothing. Otherwise give position 1, 2, 3, … in the order of `ids` and
  `bulk_update(todos, ["position"])`.

### 6. The views — `todos/views.py`

- `todo_reorder(request, pk)`: `@require_POST`. Get the list with
  `get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)`. Call `parse_ids` and
  then `save_order`; on `ValueError` → `HttpResponseBadRequest()` (400). Answer
  `HttpResponse(status=204)`.
- `todo_move(request, pk)`: `@require_POST`. Get the to-do with
  `get_object_or_404(Todo, pk=pk, todo_list__in=TodoList.objects.visible_to(request.user))`.
  Read `direction`; not `up` or `down` → 400. Get the ids of the list's to-dos in manual
  order (`position`, `created_at`, `pk`). If the to-do has a neighbour in that direction, swap the
  two ids and call `save_order`. Redirect to the list page with `?sort=manual#todo-<pk>`.
- The list page (#10's `render_list_page`, where #12 put the query form): pass
  `can_reorder = can_reorder(query_form)` to the template.

### 7. The page

- "Manual" appears in the sort menu by itself, because the choices of `TodoQueryForm` are built
  from `SORT_OPTIONS` (#14). The menu is #14's own small GET form with hidden `q` and `status`
  inputs, so choosing "Manual" keeps the search and the filter (and then the "Clear the filter"
  line shows). Nothing to change in that form.
- When `can_reorder`, the `<ul>` gets `data-reorder-url="{% url 'todo_reorder' the_list.pk %}"`
  (`the_list` is the name #10's `render_list_page` gives the list in the template), and each row (in
  `_todo_item.html`) gets `data-id`, the handle, and two small forms:
  `<button name="direction" value="up" aria-label="Move up: {{ todo.title }}" title="Move up: {{ todo.title }}">↑</button>`
  and the same for down. The `aria-label` says which to-do moves, because a screen reader would
  otherwise hear many buttons all called "Move up". Use `forloop.first` and `forloop.last` to
  leave out the button that cannot work (an `{% include %}` inside a `{% for %}` can read
  `forloop`).
- The hidden form: `<form id="reorder-csrf" hidden>{% csrf_token %}</form>`.
- `{% load static %}` at the top of the template, then
  `<script src="{% static 'todos/reorder.js' %}" defer></script>`. `defer` means the script runs
  after the page is read, so it can find the list.

### 8. `todos/static/todos/reorder.js`

Plain JavaScript, no library. Listen on the `<ul>` for `dragstart`, `dragover`, `drop` and
`dragend`:

- `dragstart` (only from a `.handle`): remember the row and the row after it (to put it back on
  cancel), add the class `dragging`, and call `event.dataTransfer.setData("text/plain", id)`.
  **Firefox does not start a drag at all without `setData`.** Also
  `event.dataTransfer.setDragImage(row, 0, 0)`, so the person sees the whole row move, not only
  the handle.
- `dragover`: find the row under the mouse with `closest("li")`, and use it only if its parent is
  **this** `<ul>` (not a subtask list). Call `event.preventDefault()` (needed, or the browser does
  not allow a drop) and set `event.dataTransfer.dropEffect = "move"`. Then put the dragged row
  before or after that row, depending on which half of it the mouse is in.
- `drop`: `event.preventDefault()` only (so the browser does not open the text as a link).
- `dragend`: remove `dragging`. If `event.dataTransfer.dropEffect` is `"none"` (the drag was
  cancelled), put the row back and stop. If the order changed, send it **once, here** (not also
  in `drop`, or it is sent twice): `fetch(url, {method: "POST", body: formData})`, where
  `formData` is `new FormData(document.getElementById("reorder-csrf"))` with one `id` appended per
  direct row. If the answer is not `204`, or `fetch` fails, call `location.reload()`.

### 9. Docs

- `AGENTS.md`: `position` in the `models.py` row; `ordering.py`, `static/todos/reorder.js` and the
  two new addresses in the table.
- `README.md`: the new files and the new test numbers.

### 10. Before the commit

- Run `make check`.
- `make run`: drag a to-do in Chrome and in Firefox; reload and see the order stays. Press Escape
  during a drag and see the row go back. Click in a to-do's "add step" box and see that it does
  not start a drag. Use the Move buttons with only the keyboard (Tab, Enter). Turn JavaScript off
  and use the Move buttons again. Look at it on a narrow window, and in dark mode.

## Tests

Each test goes in the folder for its layer. Test each rule once, in the lowest layer where a
person would notice it. In every integration test, user A owns the list, unless the test says
otherwise.

**Unit** — `todos/tests/unit/test_ordering.py` (`SimpleTestCase`, no database):

| Test | What it checks |
|---|---|
| `test_parse_ids_keeps_order` | `["3", "1", "2"]` gives `[3, 1, 2]`. |
| `test_parse_ids_rejects_text` | `["3", "abc"]`, `["3", ""]` and `["-1"]` raise `ValueError`. |
| `test_parse_ids_rejects_repeats` | `["3", "3"]` raises `ValueError`. |
| `test_can_reorder_only_manual_without_search_or_filter` | `can_reorder` on a `TodoQueryForm`: `sort=manual` → `True`; `sort=manual&q=milk`, `sort=manual&status=open`, `sort=title`, and no `sort` → `False`. |

**Integration** — `todos/tests/integration/test_reorder.py` (Django test client):

| Test | What it checks |
|---|---|
| `test_reorder_saves_new_order` | Three to-dos, POST them as 3rd, 1st, 2nd: 204, and `?sort=manual` shows them in that order (checked with `list(response.context["todos"])`). |
| `test_new_todo_goes_last` | Reorder so the oldest to-do is last, then add a to-do with the add form: it is the last row in the manual view, after the oldest. |
| `test_recurring_copy_goes_last` | Reorder so a repeating to-do is first, mark it done: its copy is the last row in the manual view, not the first. |
| `test_reorder_needs_post` | GET on the reorder address: 405. |
| `test_reorder_needs_csrf_token` | With `Client(enforce_csrf_checks=True)`, logged in, no token: 403, nothing saved. |
| `test_reorder_other_users_list_is_404` | User B posts to user A's list (with A's ids): 404, A's order unchanged. |
| `test_reorder_with_other_users_id_is_400` | A posts the ids of A's list, but with one id **replaced** by the id of a to-do in user B's list (same number of ids): 400, nothing saved in either list. |
| `test_reorder_with_missing_id_is_400` | Only two of three ids: 400, nothing saved. (A subtask's pk is read as a to-do id like any other number, so it needs no test of its own: the missing-id and other-user tests cover it.) |
| `test_reorder_with_bad_id_is_400` | One id is `abc`: 400 (checks the view uses `parse_ids`). |
| `test_shared_member_can_reorder` | A user the list is shared with can reorder it: 204, and the owner sees the new order. |
| `test_move_up_swaps_with_neighbour` | Move the second to-do up: it becomes first. Redirects to `?sort=manual#todo-<pk>`. |
| `test_move_down_on_last_changes_nothing` | Move the last to-do down: order unchanged, still redirects. |
| `test_move_with_bad_direction_is_400` | `direction=sideways`: 400, order unchanged. |
| `test_move_other_users_todo_is_404` | User B moves user A's to-do: 404, A's order unchanged. |
| `test_move_with_equal_positions_still_moves` | Set two to-dos to the same `position` by hand: Move up on the second still makes it first. |
| `test_handles_only_when_reordering_is_allowed` | `?sort=manual`: the `<ul>` has `data-reorder-url`, rows have a `draggable="true"` handle and Move buttons. `?sort=manual&status=open`: none of these, and the "Clear the filter" line is shown. (The unit test already checks every combination of `can_reorder`; this checks the template uses it.) |
| `test_first_row_has_no_move_up_and_last_has_no_move_down` | In `?sort=manual`, checked with `assertContains`/`assertNotContains` on the `aria-label`s. |
| `test_fill_migration_numbers_each_list` | Import the fill function from the migration file with `importlib` (its name starts with a number), make to-dos in two lists with `position` 0, call `fill_position(django.apps.apps, None)`, and check each list is numbered 1, 2, 3 in `created_at` order. Simpler and faster than migrating the test database back and forward. |

The login rule is not tested again here: accounts (#17) tests `LoginRequiredMiddleware` for every
address.

**CUJ** — `todos/tests/cuj/test_journeys.py`, one new journey `test_reorder_by_drag`:

1. Log in (the helper from accounts, #17), add "First", "Second", "Third".
2. Open the list with `?sort=manual`.
3. Drag the handle of "Third" to the **top edge** of "First", with Playwright's
   `locator.drag_to(target, target_position={"x": 5, "y": 2})`. Playwright sends real HTML5 drag
   events in Chromium. The position matters: by default `drag_to` drops on the **middle** of the
   target, where "before or after" is a coin toss.
4. Wrap the drag in `page.expect_response(...)` for the reorder address and check the answer is
   `204`. Without this wait, the reload in step 6 can happen **before** the order is saved, and
   the test would fail only sometimes.
5. Check the rows read Third, First, Second.
6. Reload. Check the order is the same (it was saved on the server, not only moved in the page).
7. Press the "Move down: Third" button, and check the order is First, Third, Second. This checks
   the button path works in a real browser next to the JavaScript.

## Open questions

- Should **manual** become the default sort? Many to-do apps do this. This plan
  keeps `created` as the default, so nothing changes for people who never reorder. If you want
  it, it is a one-line change to `DEFAULT_SORT` in #14's code (and its default-order test).

## Review

What the review changed, and why:

- Used the shared names and the reviewed sort plan: `manual` is one entry in `SORT_OPTIONS` in
  `todos/queries.py`, labelled "Manual", with `"pk"` (not `"id"`) as the last tie-breaker; the
  sort menu is #14's own GET form, so the page needs no menu change.
- Used the names from lists (#10): the add view is `todo_add`, the list page is `list_detail`, URL
  parameters are called `pk`.
- Moved "new to-do goes last" from the add view into `Todo.save()`: the recurring copy (#8) and
  the admin also make to-dos, and they would have jumped to the top.
- Made the Move buttons call the same `save_order` as drag: one way to save an order, and the
  "equal positions" special case is gone.
- Put the check and the save of a reorder in one transaction, and wrote down "last save wins" for
  two members reordering at once.
- Added `setData` in `dragstart`: without it, drag does not start in Firefox at all.
- Made only the handle draggable, and made the JavaScript look only at direct rows: the subtask
  list (#16) and its "add step" box are inside each row.
- Send the order only on `dragend` (it was "drop / dragend", which could send twice), put the row
  back on Escape, and reload when `fetch` fails.
- CUJ test: drop on the top edge, not the middle, and wait for the 204 before reloading; both
  made the test flaky.
- Removed `@login_required`: accounts (#17) uses `LoginRequiredMiddleware`; removed the login test
  that only repeated #17's test.
- Changed the "other list" test to replace an id with **another user's** id (same count), which
  is the attack that matters; added tests for a bad `direction` and the first/last buttons.
- Replaced the `MigrationExecutor` test with a direct call of the fill function: simpler, faster.
- Added `can_reorder(form)` with a unit test, so "no filter and no search" has one exact meaning.
- Moved the keyboard user back to the moved row with `#todo-<pk>` after a Move.
- Checked the static files claim in the code (WhiteNoise, `STATIC_ROOT`, `collectstatic` in the
  deploy command, `StaticLiveServerTestCase`): correct; added the missing `{% load static %}`.
- Decided the open questions on "move to another list" (lists has no such feature) and arrows vs
  words (arrows with `aria-label` and `title`).
- Names aligned with lists.md and accounts.md (orchestrator pass).
- Orchestrator pass: uses the separate Subtask model from subtasks.md (no Todo.parent); todo_move at /<pk>/move/.

## Decided by the person (2026-10-09)

The plan is **approved**.

- "Manual" is NOT the default sort. The default stays "created".

## Post-review check

- The orchestrator pass said a subtask's id "is refused by the same check". Not always: `Subtask`
  and `Todo` number their rows separately, so a subtask's number can equal a to-do id in this list.
  Reworded: every posted number is read as a to-do id, so nothing about subtasks can be written.
- The template used `todo_list.pk`; the list page has the list as `the_list` (#10's
  `render_list_page`). Now `the_list.pk`.
- `can_reorder` was passed in `list_detail`; the list page context is built in #10's
  `render_list_page`, where #12 put `query_form`, so it goes there.
