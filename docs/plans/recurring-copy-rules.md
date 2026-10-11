# Plan: Undo keeps a changed copy, and Repeat on a done to-do makes the copy at once

Status: **done** (2026-10-11)

Builds on: **recurring** (`make_next_copy`, `get_next_copy`, `repeated_from`), **recurring-undo-steps**
(Undo keeps the next copy when a step in it is done), **safe-toggles** (Done and Undo say which
state they want; nothing happens when the to-do already has it; the transaction in
`todo_toggle`), **subtasks** (`subtask_add`, `subtask_delete`), **edit-todo** (`todo_edit`),
**sharing** (members may edit, mark done and undo).

## Words used in this plan

- **Copy**: the next to-do that `make_next_copy` makes when a repeating to-do is marked done. It
  points back with `repeated_from`; the original reads it with `get_next_copy()`.
- **Fingerprint**: a short text (a hash) made from the parts of a to-do a person can change. Two
  to-dos with the same title, notes, priority, due date, repeat, tags and step titles have the same
  fingerprint. If one letter changes, the fingerprint changes.
- **Hash**: a fixed-length text computed from other text (here SHA-256, 64 characters). The same
  input always gives the same hash.

## What is wrong today

Facts, checked on `main` (commit `d66b978`):

1. `todo_toggle` in `todos/views.py`, on Undo, deletes the copy when it is not done, is in the same
   list and has no done step. If someone **changed** the copy (a new title, notes, a step added),
   that work is lost on one click. recurring-undo-steps listed this as a known limit ("Only steps,
   not edits"), and safe-toggles left it for the person. The person has now decided: keep it.
2. `todo_edit` saves the form and goes back to the list. If the to-do is already **done** and the
   person turns on Repeat, nothing else happens: no copy is made until the to-do is undone and
   done again. (local-safety listed this under "Left for the person".)
3. There is no "rename a step" view today (`todos/urls.py` has only `subtask_add`,
   `subtask_toggle` and `subtask_delete`). "Steps renamed" can only happen in the admin.

## Goal

Undo on a repeating to-do keeps its next copy when the copy was changed after it was made (title,
notes, priority, tags, due date, repeat, or its steps added, removed or renamed), and says so. A
copy nobody changed is removed as today. Turning on Repeat on a to-do that is already done makes
the next copy at once, with a message.

## Decisions

### 1. How the app knows "changed": a fingerprint stored on the copy

New field on `Todo`:

```python
# On a copy: the fingerprint of what make_next_copy made (content_fingerprint()).
# "" on a to-do that is not a copy, and on copies made before this field existed.
copy_fingerprint = models.CharField(max_length=64, blank=True, default="", editable=False)
```

One list of the copied fields, used by both `make_next_copy` and the fingerprint, at module
level in `todos/models.py`:

```python
# The fields make_next_copy copies as they are. due_date (a new date), the tags
# and the steps are copied too, and are always in the fingerprint.
COPIED_FIELDS = ("title", "description", "priority", "repeat")
```

`make_next_copy` builds its `Todo.objects.create(...)` arguments from this tuple
(`{name: getattr(self, name) for name in COPIED_FIELDS}`), so a field added to the copy is
added here, and then it is in the fingerprint too. This is the one guard; a test (below) checks
that a copy has every field in `COPIED_FIELDS` equal to the original, and that changing each one
changes the fingerprint.

A plain function and a method:

```python
FINGERPRINT_VERSION = "v1"

def fingerprint(values, due_date, tag_names, step_titles):
    """A SHA-256 hash (64 hex characters) of what a person can change on a to-do.

    `values`: a dict with the COPIED_FIELDS. The notes have "\r\n" made "\n"
    (as NoteField does), so the same text always gives the same hash. Tag names
    sorted, step titles in their order. Not done, not the steps' done state,
    not position, not reminded_on. Starts with FINGERPRINT_VERSION.
    """

def content_fingerprint(self):
    """fingerprint() of this to-do as it is in the database now (two queries:
    the tags and the steps)."""
```

It hashes `json.dumps([FINGERPRINT_VERSION, *values in COPIED_FIELDS order, due date as
YYYY-MM-DD or None, sorted tag names, step titles], ensure_ascii=False)`.

**At creation the fingerprint is computed from values in memory**, not read back:
`make_next_copy` already knows the copied values, the new due date, the original's tag names and
its step titles. It computes `fingerprint(...)` from them **before** `Todo.objects.create(...)`
and passes `copy_fingerprint=...` to `create()`. No second save. A test pins that a fresh copy's
stored fingerprint equals `copy.content_fingerprint()` read from the database (so the in-memory
values and the saved rows agree).

New method used by Undo:

```python
def changed_since_copy(self):
    """True when this copy no longer matches what make_next_copy made.

    False for a to-do with no stored fingerprint (not a copy, or an old copy).
    """
```

Why a fingerprint, and not a flag such as `edited_since_copy` that the edit and step views set:

- **Every way to change a copy is caught**, without touching those views: the edit page, Add
  step, Delete step, the admin (`TodoAdmin` with its step inline), and any later feature (a step
  rename view, an import). A flag works only where someone remembered to set it.
- **A change that is changed back is not a change.** Add a step, then delete it: same
  fingerprint, so Undo removes the copy as before. Nothing is lost, because the copy is again
  exactly what the app made.
- **"Save" with nothing changed is not a change**: the form saves the same values, so the
  fingerprint is the same. A flag would need `form.has_changed()`, which also compares the tag
  text as typed ("a,b" and "a, b").
- **The cost**: two small queries (tags and steps of the one copy) inside the Undo transaction.
  The list page does not change.
- **The risk**: the fingerprint must cover every field `make_next_copy` copies. Both read
  `COPIED_FIELDS`, so they cannot drift apart; a test changes each copied field once and checks
  that the fingerprint changes. If the fingerprint ever changes shape, `FINGERPRINT_VERSION`
  changes too; every stored fingerprint then differs, so every old copy counts as changed and is
  kept: the safe direction (no data is lost).

### 2. The Undo rule (in `todo_toggle`, inside the same transaction)

Today's no-op rule from safe-toggles stays first: if the to-do already has the state the button
asks for, nothing happens. When Undo really happens and the copy exists, is not done and is in the
same list:

| The copy | What happens | Message (`messages.info`) |
|---|---|---|
| a step in it is done | kept (today) | "The next copy, due 12 Oct 2026, was kept, because a step in it is already done." (today's text) |
| no done step, but `changed_since_copy()` | **kept (new)** | "The next copy, due 12 Oct 2026, was kept, because it was changed after it was made." |
| neither | deleted (today) | "The next copy, due 12 Oct 2026, was removed." (today's text) |

The done-step rule is checked first, so one Undo shows one message. A copy that is done or in
another list is left alone with no message, as today. The date uses the same `format_date(...,
"j M Y")` as today.

### 3. Turning on Repeat on a done to-do makes the copy at once (in `todo_edit`)

On `POST`, the to-do is read again **inside** the transaction, so `done` and `repeat` are the
values in the database at that moment (SQLite `IMMEDIATE`: another request that marks it done or
changes Repeat waits, or has already finished):

```python
copy = None
with transaction.atomic():
    todo = get_visible_todo(request.user, pk)  # fresh row; 404 for a stranger
    saved_title = todo.title
    was_repeating = bool(todo.repeat)
    form = TodoForm(request.POST, instance=todo)
    valid = form.is_valid()
    if valid:
        form.save()
        if todo.done and todo.repeat and not was_repeating:
            copy = todo.make_next_copy(timezone.localdate())
if valid:
    if copy:
        messages.info(request, f"Made the next copy, due {format_date(copy.due_date, 'j M Y')}.")
    return redirect(todo.todo_list)
```

`GET` stays as today (no transaction). `form.save()` keeps its own inner `atomic()` (a savepoint).

- **Only "turned on"**: Repeat was Never and now is Daily, Weekly or Monthly. Changing Weekly to
  Monthly on a done to-do does nothing new. Saving a done repeating to-do whose copy someone
  deleted does **not** bring the copy back (that would undo a delete on every Save).
- **Not done**: nothing new; the copy comes when the person clicks Done, as today.
- **A copy already exists** (Repeat was on, then off, then on again): `make_next_copy` returns
  `None`, nothing is made, no message.
- **No due date**: the form already refuses Repeat without a due date (`Todo.clean`), so this
  cannot happen.
- **The date**: `make_next_copy(timezone.localdate())`, the same rule as Done: the first date
  after the due date, in steps of the repeat, that is after today.
- **Owner and members**: `todo_edit` already uses `get_visible_todo`, so both may do it; the copy
  is in the same list (`make_next_copy` always uses `self.todo_list`).
- **Two Saves at the same moment**: the `transaction.atomic()` with SQLite's `IMMEDIATE` mode makes
  them wait for each other, and `make_next_copy` checks `get_next_copy()` first; the one-to-one
  `repeated_from` is the last guard in the database.
- The new copy gets its own fingerprint (decision 1), like every copy.

## Security

- **No new view, URL or form field.** `copy_fingerprint` has `editable=False`, so no form and no
  admin form can set it.
- Who may Undo or edit does not change: `get_visible_todo` first, so a stranger or a former member
  gets 404 before anything happens. A member's Undo and Edit follow the same rules as the owner's.
- **POST only and CSRF**, as today.
- **Messages hold no user text**: only a date from the database. Django's `{{ message }}` escapes
  it anyway.
- **The fingerprint is not a secret** and not a security check; it only decides "keep or delete"
  for a copy the person can already see and delete.
- **Data loss goes down**: Undo can now delete only a copy that is exactly as the app made it.

## Data and migrations

- One migration, made with `uv run python manage.py makemigrations todos --name todo_copy_fingerprint`:
  `0019_todo_copy_fingerprint` (an `AddField` with `default=""`).
- **Existing rows**: every to-do gets `""`. An old copy (made before this plan) has no fingerprint,
  so `changed_since_copy()` is `False` and Undo treats it as today (removed unless a step is done).
  No data migration (see "Open choices", 1).
- **Going back**: `migrate todos 0018` drops the column; revert the commit. No other data changes.

## Working next to

Wave: A, B, C and D are built at the same time; **merge order A (this) → B → C → D, then E**.

- **B, delete-undo** (`docs/plans/delete-undo.md`): changes `todo_delete` and adds a view in
  `todos/views.py` and `todos/urls.py`, and `base.html`. No shared function with this plan, but
  the same file. B rebases on this plan and **adds `copy_fingerprint` to its snapshot**, so a
  restored copy keeps its baseline.
- **C, list-name-casefold**: also adds migrations. This plan takes `0019`; C rebases after this
  merge and regenerates its migrations as `0020` and on (never two `0019` files).
- **D, backup-on-run**: no shared code.
- **E, cleanups**: merges last; it may move parts of the `AGENTS.md` rows this plan writes into
  docstrings.
- `AGENTS.md`: the `todos/models.py` and `todos/views.py` rows and the intro sentence about Undo.

## Not part of this task

- A "Remove the copy anyway" button. The kept copy has its own Delete button.
- A message when Undo leaves a copy that is done or in another list (unchanged).
- A step rename view (none exists). The fingerprint already covers step titles, so it will work
  when one is added.
- Making a copy when Repeat is turned on for a to-do that is **not** done.
- Bringing back a copy that was deleted, when a done repeating to-do is saved again.
- Filling a fingerprint for copies made before this plan (open choice 1).

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | `COPIED_FIELDS`, `FINGERPRINT_VERSION`, `fingerprint()`; `copy_fingerprint` field; `content_fingerprint()`; `changed_since_copy()`; `make_next_copy` built from `COPIED_FIELDS` and passing the fingerprint to `create()`; docstrings. |
| `todos/migrations/0019_todo_copy_fingerprint.py` (new, made by Django) | The field. |
| `todos/views.py` | `todo_toggle`: the "changed" row of the Undo rule (decision 2). `todo_edit`: on `POST`, the transaction with the fresh read, `was_repeating`, the copy and the message (decision 3). Docstrings. |
| `todos/tests/integration/test_recurring.py` | New tests (below). |
| `todos/tests/integration/test_sharing.py` | Two member tests. |
| `todos/tests/cuj/test_journeys.py` | One journey. |
| `AGENTS.md` | Intro ("Undo removes that copy again" gets "unless a step in it is done or it was changed"); `todos/models.py` row (the field and the two methods); `todos/views.py` row (Undo rule; Edit makes a copy when Repeat is turned on for a done to-do). |

## Steps

1. **Tests first.** Write the integration tests below. Run `make integration`: the new ones fail
   (no field, Undo removes a changed copy, Edit makes no copy). Show the person the failures.
2. The field and the two methods in `models.py`; `makemigrations todos --name
   todo_copy_fingerprint`; `migrate` **in the worktree only** (its own `db.sqlite3`, never the
   person's file in the main checkout).
3. `make_next_copy` stores the fingerprint.
4. `todo_toggle` (decision 2), then `todo_edit` (decision 3).
5. The CUJ test; `make cuj`.
6. `AGENTS.md`. `make check`. Commit. Last commit: Status `**done** (<date in Tokyo>)`.

## Tests

### Integration: `todos/tests/integration/test_recurring.py` (`RecurringTests`)

Each "kept" test also has its "removed" partner, so a rule that always keeps fails.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_new_copy_has_its_fingerprint` | The original has notes with a line break, two tags and two steps. After Done, the copy's `copy_fingerprint` is 64 characters and equals `copy.content_fingerprint()` read from the database; `changed_since_copy()` is `False`. The original's `copy_fingerprint` stays `""`. | In-memory values that differ from the saved rows (tags left out, steps in another order, "\r\n" in the notes). |
| `test_copy_has_every_copied_field` | Subtests over `COPIED_FIELDS`: each field of the copy equals the original's. | `make_next_copy` not built from `COPIED_FIELDS`. |
| `test_fingerprint_starts_with_the_version` | `fingerprint()` of the same values with `FINGERPRINT_VERSION` patched to `"v2"` gives a different hash. | No version in the hash. |
| `test_fingerprint_changes_for_each_field` | Subtests: change the copy's title, notes, priority, due date, repeat, tags (add one, remove one), steps (add one, delete one, change a step's title in the database). Each time `changed_since_copy()` is `True`. | A field left out of the fingerprint. |
| `test_fingerprint_ignores_done_and_order` | Marking a step done (then undone), moving the copy in the manual order (`save_order`), and `reminded_on`: `changed_since_copy()` stays `False`. | Hashing `done`, `position` or `reminded_on`. |
| `test_undo_keeps_an_edited_copy` | Done, then edit the copy's title through the edit page (`POST`), then Undo: the copy is still there with the new title; the message is "The next copy, due ..., was kept, because it was changed after it was made." | Today's code (the copy is deleted). |
| `test_undo_keeps_a_copy_with_an_added_step` | Done, add a step to the copy (`subtask_add`), Undo: kept, same message. | Checking only the to-do's own fields. |
| `test_undo_keeps_a_copy_with_a_removed_step` | The original has two steps; Done; delete one step of the copy; Undo: kept. | Counting only added steps. |
| `test_undo_removes_a_copy_changed_back` | Done; add a step to the copy, then delete it; Undo: the copy is removed with "was removed." | A flag that remembers any edit. |
| `test_undo_removes_a_copy_saved_without_changes` | Done; open the copy's edit page and post its own values back; Undo: removed. | Treating every Save as a change. |
| `test_undo_with_done_step_and_edit_says_the_step_message` | Done; edit the copy and mark one of its steps done; Undo: kept, and only the step message (one message). | Two messages, or the wrong one first. |
| `test_old_copy_without_fingerprint_is_removed` | A copy with `copy_fingerprint=""` (set with `update()`), changed title; Undo: removed, as before this plan. | Treating `""` as "changed" (every old copy would stay). |
| `test_double_undo_after_kept_copy_does_nothing` | Edited copy, Undo (kept), Undo again: no new message, the copy is still there. | Running the rule when nothing changes (safe-toggles). |
| `test_edit_turn_on_repeat_on_done_todo_makes_copy` | A done to-do with a due date and Repeat Never; Edit sets Weekly: one copy, due the next date after today (fixed with `patch("todos.views.timezone.localdate")`), message "Made the next copy, due ...". | Today's code (no copy). |
| `test_edit_turn_on_repeat_on_open_todo_makes_no_copy` | The same on a to-do that is not done: no copy, no message. | Making a copy for every repeat. |
| `test_edit_change_repeat_kind_makes_no_copy` | A done weekly to-do whose copy was deleted; Edit sets Monthly: no copy. | Treating any repeat value as "turned on". |
| `test_edit_rereads_the_todo_inside_the_transaction` | The edit page was opened while the to-do was open; then it is marked done (another request); then the Edit with Weekly is posted: one copy is made (the fresh `done` counts). | Reading `done` before the transaction. |
| `test_edit_turn_on_repeat_when_copy_exists_makes_no_second` | Done weekly with a copy; Edit sets Never, then Weekly again: still one copy, no "Made" message. | A second copy, or an `IntegrityError` (500). |
| `test_invalid_edit_makes_no_copy` | Done to-do; Edit sets Weekly and an empty title: 200 with the error, no copy. | Making the copy before `is_valid()`. |

### Integration: `todos/tests/integration/test_sharing.py` (`MemberCanTests`)

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_member_edit_is_kept_on_owners_undo` | bob (member) edits the copy's notes; alice clicks Undo on the original: the copy stays with bob's notes. | Only the owner's edits counting. |
| `test_member_turns_on_repeat_on_done_todo` | bob edits a done to-do of alice's list to Weekly: one copy, in alice's list. | Members left out, or the copy in bob's list. |

The 404 rules for `todo_toggle` and `todo_edit` already have tests (`test_other_user_gets_404`,
`test_other_user_cannot_toggle_repeating_todo`); they stay.

### CUJ: `todos/tests/cuj/test_journeys.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_undo_keeps_a_changed_copy` | A weekly to-do. Click Done; open the copy's Edit, change its title, Save; click Undo on the original. The page shows "was kept, because it was changed after it was made." and the copy's new title. | The copy is deleted, or no message. |

## Decided by the person (2026-10-11)

- Undo keeps the next copy when a step in it is done (already built, PR #40) **and** when the copy
  was changed after it was made (title, notes, priority, tags, due date, repeat, or steps added,
  removed or renamed), with a clear message. Otherwise Undo removes it as today.
- Keep safe-toggles' no-op rules and the transaction.
- Turning on Repeat (via Edit) on a to-do that is already done makes the next copy at once
  (`make_next_copy(timezone.localdate())`; nothing when a copy exists; a message), for owner and
  members.
- A migration is OK (with a fixed `--name`).

## Open choices

1. **Copies made before this plan.** They have no fingerprint. (a) Treat them as "not changed",
   so Undo removes them as today, **recommended**: we cannot know if they were changed, and that
   is exactly today's rule. (b) A data migration that stores today's fingerprint: then only later
   changes count; it needs a frozen copy of `content_fingerprint` in the migration, for very few
   rows. (c) Treat them as "changed" (always keep): safest for data, but Undo would never remove
   an old copy.
2. **Fingerprint or flag.** Fingerprint, **recommended** (decision 1). A flag
   (`edited_since_copy`, set in `todo_edit`, `subtask_add` and `subtask_delete`) is a few lines
   shorter, but misses the admin and future views, and counts a change that was changed back.
3. **The message when Repeat makes a copy.** "Made the next copy, due 12 Oct 2026."
   (**recommended**, the same date format as the Undo messages), or no message (the copy is
   visible in the list anyway).

## Review

Verification by the planner (2026-10-11), against `main` (`d66b978`):

- Confirmed: `todo_toggle` checks `copy.subtasks.filter(done=True).exists()` and else deletes the
  copy; it runs inside `transaction.atomic()` and returns early when `todo.done == done`.
- Confirmed: `todo_edit` reads `saved_title` before the form, saves with `form.save()` (which has
  its own `transaction.atomic()` for the tags) and redirects; no copy is made.
- Confirmed: `make_next_copy` sets the tags with `copy.tags.set(...)` and makes the steps with
  `bulk_create` after `Todo.objects.create(...)`, so the fingerprint must be computed after both.
- Confirmed: there is no step rename view; `TodoAdmin` has a `SubtaskInline`, so steps can be
  renamed in the admin. The fingerprint catches it; a flag would not.
- Confirmed: `Subtask.Meta.ordering = ["created_at", "id"]`, so step titles come back in a fixed
  order for the fingerprint.
- Confirmed: the latest migration is `0018_todo_ordering_tiebreak`; this plan's is `0019`.

The plan review (2026-10-11, an independent reviewer who also ran small prototypes) said APPROVE
WITH CHANGES. What changed:

- One `COPIED_FIELDS` tuple, used by `make_next_copy` and by the fingerprint, so they cannot
  drift; a test checks the copy against it.
- The fingerprint makes "\r\n" in the notes "\n" and starts with a version (`"v1"`).
- The fingerprint of a new copy is computed from the values in memory and passed to `create()`
  (no second save); a test pins that it equals the one read back from the database.
- `todo_edit` reads the to-do again with `get_visible_todo` inside `transaction.atomic()`, and
  checks `done` and `repeat` on that fresh row; a test covers a to-do marked done after the edit
  page was opened.

## Built (2026-10-11)

As planned. Small differences: the CUJ test is in its own class `KeepAChangedCopyTests`;
`make_next_copy` loads the tags and the step titles once and uses them for the fingerprint, the
tags and the steps; the tests reach `COPIED_FIELDS` and `fingerprint` through the module
(`todo_models.COPIED_FIELDS`), so a missing name fails only those tests. No data migration
(open choice 1, a), the message "Made the next copy, due ..." (open choice 3).
