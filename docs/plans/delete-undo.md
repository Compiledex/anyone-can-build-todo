# Plan: Undo a deleted to-do

Status: approved by the person (2026-10-11), not started

Builds on: **edit-todo**, **subtasks**, **tags**, **recurring** (`repeated_from`, `next_copy`),
**drag-and-drop** (`position`), **sharing** (members may delete), **safe-toggles** (Delete goes
back to the next row with `next` and `redirect_back`; anchors like `#todo-7`), and
**recurring-copy-rules** (A in this wave, merged first: the field `copy_fingerprint`).

## Words used in this plan

- **Session**: the small store Django keeps on the server for one logged-in browser. The browser
  only holds a random key (the session cookie). Here sessions are stored in the database
  (Django's default; `config/settings.py` sets no other `SESSION_ENGINE`). Logging out empties it.
- **Snapshot**: a copy of a to-do's values (and its tags and steps), saved as plain data before
  the to-do is deleted, so it can be made again.
- **Soft delete**: not really deleting a row, only marking it as deleted (a `deleted_at` field).
- **AUTOINCREMENT**: SQLite's rule that a row number (`id`) is not given out again after the row
  is deleted. Django creates every table here with it (checked: `todos_todo`, `todos_subtask` and
  `todos_todolist` are `integer NOT NULL PRIMARY KEY AUTOINCREMENT`). **But** when a migration
  rebuilds a table (Django does that on SQLite for many field changes), the counter in
  `sqlite_sequence` starts again from the biggest id still in the table. So after such a
  migration, the id of a deleted to-do **can** be given to a new one. This plan does not rely on
  "never".

## What is wrong today

Facts, checked on `main` (commit `d66b978`): `todo_delete` in `todos/views.py` deletes the to-do
at once (its steps go with it, `on_delete=CASCADE`; a copy made from it loses its link,
`repeated_from` is `SET_NULL`) and goes back to the next row. There is no way back. safe-toggles
listed "Confirm or undo a single Delete" under "Left for the person". The person has decided: an
Undo button.

## Goal

Delete removes the to-do at once and shows "Deleted “Buy milk”." with an **Undo** button. Undo
brings the to-do back as it was: title, notes, priority, due date, repeat, done, tags, steps (and
which steps were done), its place in the list, and its links to the to-do it was copied from and
to its own copy, where that is still possible. The page then opens at the restored row.

## Decisions

### 1. A snapshot in the session, not a soft delete

**Chosen: a snapshot in the session.** Before the delete, `todo_delete` writes one snapshot to
`request.session["undo_delete"]`. Undo reads it and makes the rows again.

- **No migration, no change to any query.** The deleted row is really gone, so the list page,
  search, filter, sort, "Clear completed" counts, reminders, reorder (`save_order` needs exactly
  the list's to-dos), `visible_to` and the admin all stay correct without a change.
- **Only the person who deleted it can undo it**: the session belongs to that browser and that
  login. Logging out empties it (`logout()` flushes the session); logging in as someone else in
  the same browser flushes it too (Django's `login()` flushes when the user changes). The snapshot
  also stores the user's id, and Undo checks it.
- **Only the last delete**: a new delete replaces the snapshot.
- **A time limit**: 15 minutes (open choice 1). After that, Undo says it is too late, and the
  next list page drops the old snapshot (decision 5).
- **Why not a soft delete**: every query that reads to-dos would have to leave out deleted rows:
  `the_list.todos`, `get_visible_todo`, `done_count`, `list_clear_completed`, `search()`'s
  sub-query, `save_order`, `todo_move`, `make_next_copy`/`get_next_copy`, `due_today` in
  reminders, the admin. One miss shows a deleted to-do, or makes Move and drag fail (400). It also
  needs a job that really deletes old rows. Too much risk for this app.
- **Why not a hidden field in the page** (the snapshot in the Undo form): the browser could change
  it or send it twice, and it would put another person's data in the page HTML. The session is on
  the server and cannot be changed by the browser.

### 2. What the snapshot holds

New module `todos/undo.py` (the one place for this feature):

```python
SESSION_KEY = "undo_delete"
UNDO_SECONDS = 15 * 60

def take_snapshot(todo, user, now):
    """Plain JSON data for one to-do, to make it again with restore().

    Every concrete Todo field (see SNAPSHOT_FIELDS), the tag names, and the steps
    (title and done, in their order). Dates as ISO text: the session is JSON.
    """

def restore(snapshot, the_list):
    """Make the to-do again in `the_list`, with its old id. Returns the Todo."""
```

`SNAPSHOT_FIELDS` names every concrete field of `Todo` by its `attname`: `id`, `todo_list_id`,
`title`, `done`, `created_at`, `due_date`, `description`, `priority`, `repeat`,
`repeated_from_id` (an id or `None`), `position`, `reminded_on`, `copy_fingerprint` (from plan
A). Plus:
`next_copy` (the id of the copy made from this to-do, or `None`), `tags` (the tag names),
`steps` (`[[title, done], ...]` in step order), `user` (the user id) and `deleted_at` (ISO time).
A unit test checks that `SNAPSHOT_FIELDS` is exactly the list of `Todo`'s concrete fields, so a
new field cannot be forgotten.

### 3. Delete

`todo_delete`, after `get_visible_todo` (so a stranger still gets 404 first):

1. In one `transaction.atomic()`: take the snapshot, delete the to-do.
2. `request.session[SESSION_KEY] = snapshot` (it replaces an older one).
3. `messages.success(request, f"Deleted “{todo.title}”.", extra_tags=f"undo-delete-{todo.pk}")`.
   The id in the tag ties this message to this delete.
4. Go back with `redirect_back` as today (the next row).

### 4. The Undo button

A small context processor, `todos.context_processors.undo_delete` (added to `TEMPLATES` in
`config/settings.py`), gives every template `undo_delete_tag` and `undo_delete_id`: from the
session's snapshot, `"undo-delete-<id>"` and the id; both `None` when there is no snapshot, it
belongs to another user, or it is too old. It only reads the session; it never writes.

In `todos/templates/base.html`, each message becomes a `<div class="message ...">` instead of a
`<p>` (a `<form>` cannot be inside a `<p>`: the browser would end the `<p>` before the form). The
text goes in a `<span>` inside it. The Undo form is shown **only** when this message's
`extra_tags` is exactly `undo_delete_tag`:

```django
<div class="message{% if message.tags %} {{ message.tags }}{% endif %}">
  <span>{{ message }}</span>
  {% if undo_delete_tag and message.extra_tags == undo_delete_tag %}
    <form class="undo" method="post" action="{% url 'todo_undo_delete' undo_delete_id %}">
      {% csrf_token %}
      <input type="hidden" name="next" value="{{ request.get_full_path }}#todo-{{ undo_delete_id }}">
      <button class="button button-secondary button-compact" type="submit">Undo</button>
    </form>
  {% endif %}
</div>
```

- **Two deletes close together**: the first message has `undo-delete-7`, but the snapshot is now
  for 8, so only the message for 8 gets a button. An Undo button always undoes the delete its
  message names.
- **No snapshot** (logged out in another tab, already undone, too old): `undo_delete_tag` is
  `None`, so no button and no `{% url %}` with an empty id (that would be a 500 page).
- The message text is escaped by `{{ message }}` (no `mark_safe`, no `|safe`), so a title like
  `<script>` shows as text. A test pins it.
- The number in the URL and the fragment is the to-do's id from the snapshot: a database number,
  never request text.
- `next` is the page the person is on (the list with the same search and filter). `redirect_back`
  checks it as today (only a path on this site).
- Messages show once (Django's message storage), so after a reload the button is gone.
- The `<p>` to `<div>` change touches every message on every page that extends `base.html`. The
  CSS keeps `.message` on the element, so the look is the same; the PR lists any test that
  looked for `<p class="message` (none found on `main` on 2026-10-11).

### 5. Undo: `todo_undo_delete` (`POST /<pk>/undo-delete/`)

```python
@require_POST
def todo_undo_delete(request, pk):
```

In one `transaction.atomic()` (SQLite `IMMEDIATE`: two clicks wait for each other in the
database). The **session is not part of that transaction**: Django's session middleware saves it
after the view has answered. So two posts that arrive close together can both read the same
snapshot. The real guard against a double restore is therefore the check in step 3, which runs
inside the transaction, before anything is made:

1. `snapshot = request.session.get(SESSION_KEY)`. If there is none, or its `id` is not `pk`, or
   its `user` is not `request.user.id`:
   - if a to-do with this `pk` exists **and** the user can see it (the same filter as
     `get_visible_todo`, without the 404): it was already restored (a double click, or a second
     tab). Go back to `next` with no message (safe-toggles: nothing changes, nothing is said).
   - else: **404**. A stranger, a person who logged out and in again, or an old button for an
     older delete all get 404. It tells nothing.
2. Remove the snapshot from the session (`pop`).
3. **A to-do with this id exists already** (checked first, inside the transaction):
   - it is in the snapshot's list and has the snapshot's title and `created_at`: this is the same
     to-do, restored a moment ago by the other post. Go back with **no message**.
   - else another to-do got this id (possible after a table rebuild, see "Words"): message
     "Could not undo." The other to-do is **not touched**. Go back to the list.
4. Too old (`deleted_at` more than `UNDO_SECONDS` ago, `timezone.now()`): message "Too late to
   undo: the to-do stays deleted." and go to the list (if visible) or `/`.
5. The list is gone, or the user can no longer see it (`TodoList.objects.visible_to(request.user)
   .filter(pk=snapshot["todo_list_id"])` is empty): message "Could not undo: you can no longer see
   the list it was in." and go to `/`. Nothing is made.
6. `restore(snapshot, the_list)`, then message "Restored “Buy milk”." and `redirect_back(request,
   list_url + "#todo-<pk>")`.

**An expired snapshot** stays in the session until the next delete, Undo or logout; nothing
offers it (the context processor hides it). To not keep old to-do text around,
`render_list_page` also drops an expired snapshot from the session when the list page is shown
(`undo.drop_expired(request.session, now)`).

### 6. How `restore` makes the rows

- The to-do is made with its **old id** (`Todo(id=..., ...)`, `save(force_insert=True)`), so
  links, anchors and an open tab still point at the right row. Step 3 of decision 5 has already
  made sure no other row has that id. `Todo.save()` only sets `position` for a row without an id, so the old
  `position` stays: the row comes back to its place in the manual order. If someone reordered the
  list in between, the old number may tie with another row; then `created_at` and `pk` decide, as
  always.
- `created_at` has `auto_now_add`, so the insert writes "now". `restore` then sets the old value
  with one `Todo.objects.filter(pk=...).update(created_at=...)`, so the default order ("oldest
  first") puts it back in its place.
- **Tags**: `todo.set_tags(names)`: the list owner's tags by name (made again if gone). Never the
  person's own tags (sharing rule).
- **Steps**: `Subtask.objects.bulk_create(...)` in the old order, with their `done` values. They
  get new ids and new `created_at` times in the same order (steps show no time).
- **Recurring links**, only inside the same list:
  - `repeated_from`: set back only if that to-do still exists in this list **and** has no other
    copy now (the link is one-to-one). Else left empty.
  - `next_copy`: if that copy still exists in this list and its `repeated_from` is empty (the
    delete set it to `NULL`), set it back to the restored to-do. Else left alone.
- `reminded_on` and `copy_fingerprint` come back as they were, so no second reminder on the same
  day, and Undo of a copy still knows whether it was changed.

### 7. What the person sees

- After Delete: the next row (as today), and at the top "Deleted “Buy milk”." with an Undo button.
- After Undo: the restored row (`#todo-<pk>`), and "Restored “Buy milk”.".
- Too late, or the list is gone or no longer shared: a clear message, nothing is made.

## Security

- **Only my data, plus what is shared with me**:
  - Delete keeps `get_visible_todo` first.
  - Undo needs the snapshot in **this** session, for **this** user and **this** id. A stranger
    has no such snapshot and gets 404 (the "already restored" check uses the visible-to filter,
    so it cannot tell a stranger that a to-do exists).
  - Undo restores only into the list in the snapshot, and only when the user can still see it
    (`visible_to`). A member who was removed, or a list that was deleted: nothing is made.
  - Tags go to the list owner (`set_tags`).
- **POST only, CSRF**: `@require_POST`, `{% csrf_token %}` in the Undo form. A `GET` gives 405.
- **Open redirect**: `next` goes through the existing `redirect_back`.
- **No injection**: the title in the messages is escaped by the template; no `|safe`. The ids in
  the URL and fragment are numbers from the snapshot (made from the database). The session data
  is JSON on the server; the browser cannot change it.
- **The snapshot holds the to-do's text** in the `django_session` table until the next delete,
  Undo or logout, or until the first list page after the time limit (which drops it). It is
  the person's own data, on their own Mac.
- **Only once**: the snapshot is removed from the session, and the "id exists" check runs inside
  the database transaction before anything is made, so two posts close together restore once.
- **Another to-do is never overwritten**: if the id belongs to a different to-do, Undo does
  nothing but say "Could not undo.".

## Data and migrations

No model change and no migration. The snapshot lives in the existing `django_session` table.
Going back: revert the commit; old snapshots in sessions are ignored (nothing reads the key).

## Working next to

Wave: A, B, C and D are built at the same time; **merge order A → B (this) → C → D, then E**.

- **A, recurring-copy-rules**: adds `copy_fingerprint` to `Todo` and changes `todo_toggle` and
  `todo_edit` in the same `views.py`. B is built on `main` and then rebased on A: it adds
  `copy_fingerprint` to `SNAPSHOT_FIELDS` (the field test fails until it does).
- **C, list-name-casefold**: no shared code.
- **D, backup-on-run**: no shared code.
- **E, cleanups**: merges last. It changes `_todo_item.html` (lighter HTML) and may merge the Done
  and Delete forms; it must keep Delete's `next` and this plan's message and Undo form.
- `todos/urls.py`: one new line. `base.html`: the Undo form in the messages box. `app.css`: a few
  lines for `.message form.undo` (inline, next to the text).

## Not part of this task

- Undo for "Clear completed", for deleting a list, or for deleting a step.
- Undo for an edit.
- More than one delete to undo (only the last one).
- Keeping the snapshot after logout.
- A friendlier page than 404 for an Undo button from an older delete (two tabs). Rare; see
  "Known limits".

## Changes to files

| File | Change |
|---|---|
| `todos/undo.py` (new) | `SESSION_KEY`, `UNDO_SECONDS`, `SNAPSHOT_FIELDS`, `take_snapshot`, `restore`, `drop_expired`. |
| `todos/views.py` | `todo_delete` takes the snapshot and adds the message; new `todo_undo_delete`; `render_list_page` drops an expired snapshot. |
| `todos/urls.py` | `path("<int:pk>/undo-delete/", views.todo_undo_delete, name="todo_undo_delete")`. |
| `todos/context_processors.py` (new) | `undo_delete(request)`: `undo_delete_tag` and `undo_delete_id`. |
| `config/settings.py` | The context processor in `TEMPLATES`. |
| `todos/templates/base.html` | Each message a `<div>` (text in a `<span>`); the Undo form inside the message whose tag matches. |
| `todos/static/todos/app.css` | `.message form.undo`: on the same line as the text. Only tokens. |
| `todos/tests/unit/test_undo.py` (new) | `SNAPSHOT_FIELDS` covers every concrete `Todo` field. |
| `todos/tests/integration/test_delete_undo.py` (new) | The tests below. |
| `todos/tests/cuj/test_journeys.py` | One journey. |
| `AGENTS.md` | Intro (delete has Undo); new row `todos/undo.py`; `todos/views.py` and `todos/urls.py` rows; `base.html` row. |

## Steps

1. **Tests first** (below). `make unit integration`: the new ones fail (no module, no URL, no
   message). Show the person.
2. `todos/undo.py`.
3. `todo_delete`, `todo_undo_delete`, the URL.
4. `base.html` and `app.css`.
5. The CUJ test; `make cuj`.
6. `AGENTS.md`. `make check`. Commit. Last commit: Status `**done** (<date in Tokyo>)`.

## Tests

### Unit: `todos/tests/unit/test_undo.py` (`SimpleTestCase`)

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_snapshot_fields_are_every_todo_field` | `set(SNAPSHOT_FIELDS)` equals `{f.attname for f in Todo._meta.concrete_fields}`. | A new `Todo` field that Undo would lose. |

### Integration: `todos/tests/integration/test_delete_undo.py` (`LoggedInTestCase`)

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_delete_shows_message_with_undo` | Delete, follow the redirect: the message "Deleted “Buy milk”." and a `POST` form to `todo_undo_delete` with the id, a CSRF input and `next` ending in `#todo-<pk>`. | No snapshot, no button. |
| `test_delete_still_deletes_at_once` | After Delete the row and its steps are gone from the database. | A soft delete. |
| `test_undo_restores_everything` | A to-do with notes, High, a due date, Weekly, two tags, three steps (one done), `position` 2 of 3, an old `created_at`: Delete, Undo. Same id, every field equal (also `created_at`, `position`, `reminded_on`), the same tag names, the steps in order with the same done values. Shown in the same place in the default and manual order. | Losing any field or the order. |
| `test_undo_goes_back_to_the_row` | The Undo response redirects to `next` (`/lists/<pk>/?q=...#todo-<pk>`); with a bad `next` (`//evil.example/`) to the list with `#todo-<pk>`. | No fragment, or skipping `redirect_back`. |
| `test_undo_works_only_once` | Undo twice: one to-do, one "Restored" message; the second post goes back with no message (already restored). | A second insert (an `IntegrityError` 500), or a second message. |
| `test_double_submit_with_the_old_session_restores_once` | Delete; keep a copy of the session data; post Undo; put the saved session data back (the snapshot is there again, as for a second post that read the session before the first one saved it); post Undo again: one to-do with that id, one "Restored" message in all, no 500. | Relying on the session `pop` alone. |
| `test_id_taken_by_another_todo` | Delete; then make another to-do with the snapshot's id (as after a table rebuild); post Undo: message "Could not undo.", the other to-do is unchanged, nothing else made. | Overwriting or crashing on the other row. |
| `test_two_deletes_only_the_last_message_has_undo` | Delete A, then delete B before loading a page (both messages show on one page): only B's message has the Undo form; its action has B's id. | One button for both messages, or a button that undoes another delete. |
| `test_no_undo_button_without_snapshot` | A message with the tag `undo-delete-7` but no snapshot in the session (logged out and in, or flushed): the page shows the text, no form, status 200. | `{% url %}` with an empty id (a 500 page). |
| `test_message_is_a_div` | The messages box holds `<div class="message ...">`, and the Undo `<form>` is inside it. | A `<form>` inside a `<p>`. |
| `test_expired_snapshot_is_dropped_by_the_list_page` | A snapshot 16 minutes old; load the list page: the session no longer has `undo_delete`. A snapshot 14 minutes old stays. | Keeping old to-do text in the session. |
| `test_only_the_last_delete_can_be_undone` | Delete A, delete B, Undo for A's id: 404, A stays deleted; Undo for B works. | Keeping several snapshots, or restoring the wrong one. |
| `test_stranger_gets_404` | alice deletes; bob posts to alice's Undo URL (`assertOtherUserGets404`): 404, nothing restored, alice's Undo still works afterwards. | Snapshots shared between sessions, or bob's post using alice's snapshot. |
| `test_get_is_405` | `GET` the Undo URL: 405, nothing restored. | Changing data on `GET`. |
| `test_logout_ends_the_undo` | alice deletes, logs out, logs in again, posts Undo: 404. | A snapshot that survives logout. |
| `test_undo_after_the_time_limit` | `deleted_at` 16 minutes ago (patch `timezone.now`): message "Too late to undo ...", nothing made; at 14 minutes it works. | No time limit, or an off-by-one the wrong way. |
| `test_member_undo_after_being_removed` | bob (member) deletes in alice's list; alice removes bob; bob posts Undo: message "Could not undo: you can no longer see the list it was in.", nothing made. A member who still is a member can undo (the "something happens" case). | Restoring into a list the user cannot see. |
| `test_undo_after_the_list_was_deleted` | Delete a to-do, delete its list, Undo: the same message, nothing made, no 500. | A crash, or a to-do without a list. |
| `test_tags_go_to_the_list_owner` | bob (member) deletes a tagged to-do in alice's list and undoes: the tags are alice's `Tag` rows, bob has none. | `set_tags` with `request.user`. |
| `test_recurring_links_come_back` | Weekly to-do: Done (copy made); delete the original; Undo: the copy's `repeated_from` is the original again, `get_next_copy()` finds it. Also: delete the copy, Undo: the original's `next_copy` is the copy again. | Leaving the links empty. |
| `test_recurring_link_not_stolen` | Delete a copy; Undo on the original (removes nothing, there is no copy) then Done (a new copy); Undo the delete: the restored to-do has no `repeated_from` (the original already has a copy), no 500. | Breaking the one-to-one link. |
| `test_message_escapes_the_title` | A to-do titled `<b>x</b>`: the page shows `&lt;b&gt;x&lt;/b&gt;` in both messages, never the raw tag. | `mark_safe` or `|safe`. |
| `test_list_query_count_does_not_change` | The list page's query count with and without a snapshot in the session is the same (`count_queries`). | Reading the snapshot with a query per row. |

### CUJ: `todos/tests/cuj/test_journeys.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_delete_and_undo` | A list with three to-dos, the middle one with a step. Click its Delete: it is gone, "Deleted “...”." shows. Click Undo: the row is back between the other two, in the viewport, with its step, and "Restored “...”." shows. | Any part of the flow. |

## Decided by the person (2026-10-11)

- Delete on one to-do removes it at once and shows "Deleted “<title>”." with an Undo button
  (`POST`, CSRF).
- Undo restores it with its notes, priority, tags, steps (and their done states), position in the
  list, repeat settings, and recurring links where possible.
- Undo only works for the person who deleted it, only into a list they can still see, and only
  once. A stranger gets 404. When the list was deleted or the person lost access, nothing happens
  and a clear message says so.
- Messages must not show titles unsafely. It works with safe-toggles' anchors (back to the
  restored row).

## Open choices

1. **The time limit.** 15 minutes, **recommended**: long enough to notice a mistake, short enough
   that an old snapshot does not linger. (Other options: 5 minutes; no limit, only "until the next
   delete or logout".)
2. **Session snapshot or soft delete.** Session snapshot, **recommended** (decision 1): no
   migration and no query has to change. Soft delete would keep the undo across logout, but every
   to-do query would need a new filter.
3. **Two deletes close together** (PERSON). Default written into the plan: the message carries
   the deleted to-do's id (`undo-delete-<id>`), and only the message whose id matches the
   session's snapshot gets an Undo button (**recommended**: a button always undoes what its
   message says). Other option: every "Deleted" message gets a button that undoes the last
   delete.
4. **When the id is taken by another to-do** (PERSON; rare, only after a table rebuild).
   Default written into the plan: the message "Could not undo." and the other to-do is not
   touched (**recommended**). Other option: restore with a new id (then links from an open tab
   point at the wrong row, and the recurring links need care).

## Known limits

- An Undo button from an **older** delete (still open in a second tab) gives a plain 404 page,
  because only the last delete can be undone.
- Steps come back with new ids (nothing links to a step id except its own forms on the page).

## Review

Verification by the planner (2026-10-11), against `main` (`d66b978`):

- Confirmed: `todo_delete` deletes at once and calls `redirect_back`; `Subtask.todo` is
  `on_delete=CASCADE`; `Todo.repeated_from` is `OneToOneField(..., on_delete=SET_NULL,
  related_name="next_copy")`.
- Confirmed in a scratch database made by `migrate` (not the person's file): the three tables use
  `PRIMARY KEY AUTOINCREMENT`. (The review found that a table rebuild resets the counter; see
  below.)
- Confirmed: `Todo.save()` sets `position` only when `self.pk is None`; `created_at` is
  `auto_now_add`, so `restore` needs the `update()` afterwards.
- Confirmed: `config/settings.py` sets no `SESSION_ENGINE` (database sessions, JSON) and no
  `MESSAGE_STORAGE`; `base.html` prints `{{ message }}`, which escapes.
- Confirmed: Django's `login()` flushes the session when a different user logs in, and `logout()`
  always flushes it.

The plan review (2026-10-11, an independent reviewer who also ran small prototypes) said APPROVE
WITH CHANGES. What changed:

- The session is saved by middleware after the view, not inside the database transaction, so the
  "id already exists" check now runs first inside the transaction and is the real double-submit
  guard. New test: put the old session back and Undo twice.
- "Ids are never reused" was wrong: a table rebuild by a migration resets `sqlite_sequence`. If
  the id belongs to another to-do, Undo says "Could not undo." and touches nothing (PERSON
  default).
- `base.html` messages were `<p>`, which cannot hold a `<form>`: they become `<div>`. The Undo
  form is shown only when a snapshot exists, so no `{% url %}` with an empty id (a 500 page).
- The message's tag carries the deleted to-do's id, and the button shows only when it matches
  the snapshot (PERSON default), via a small context processor instead of
  `request.session.undo_delete.id` in the template.
- An expired snapshot no longer "lasts until the time limit": it stays until the next delete,
  Undo or logout, so the list page now drops it.
