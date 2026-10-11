# Plan: list names are unique ignoring case for every letter, also æ, ø and å

Status: approved by the person (2026-10-11), not started

Builds on: **lists** (`TodoList`, `TodoListForm`, new list and rename), **accounts** (sign-up
makes "Inbox"), **sharing** (lists shared with you), **nordic-letters** (`casefold()` in
`todos/sqlite_functions.py`), and **recurring-copy-rules** (A in this wave: its migration
`0019` merges first).

## Words used in this plan

- **Case**: upper case (A, Æ) and lower case (a, æ).
- **Casefold**: Python's `str.casefold()`, a stronger "lower case" for comparing text: it knows
  every letter, not only A to Z ("Ærend" and "ærend" become the same; "Straße" becomes
  "strasse"). `todos/sqlite_functions.casefold` also joins a letter that a Mac sends in two parts
  (an "a" plus a ring) into one ("å") first (NFC).
- **Key**: here, the list name after `casefold`. Two names with the same key count as the same
  name.
- **Unique constraint**: a rule inside the database that refuses a second row with the same
  values.

## What is wrong today

Facts, checked on `main` (commit `d66b978`):

1. `TodoList.Meta.constraints` has `UniqueConstraint(Lower("name"), "owner",
   name="unique_list_name_per_owner")`. SQLite's `LOWER()` only changes A to Z (the comment in
   `models.py` says so).
2. `TodoListForm.clean_name` checks `name__iexact`. On SQLite that is `LIKE`, which also ignores
   case only for A to Z.
3. So a person can have both "Ærend" and "ærend", or "Øl" and "øl". "Work" and "work" are already
   refused, by both the form and the database.
4. A database rule cannot use the `casefold()` SQL function: it exists only on connections where
   `todos/apps.py` added it. `sqlite_functions.py` itself says a database rule built on a Python
   function breaks when the function is missing (the `sqlite3` command line tool, a backup tool,
   a migration run in another way).

## Goal

One person cannot have two lists whose names differ only in case, for every letter (also æ, ø, å,
and "å" typed as two parts on a Mac). Names of lists shared with you do not count. The rule holds
in the form (a clear message) and in the database (no second row, ever).

## Decisions

### 1. A stored key column, `name_key`, with a normal unique constraint

```python
# casefold(name): the name in one case, for the unique rule. Set by save(), never by a form.
name_key = models.CharField(max_length=300, editable=False, default="")
```

- `TodoList.save()` sets `self.name_key = casefold(self.name)` every time (from
  `todos/sqlite_functions.py`, plain Python). When `save()` gets `update_fields` with `"name"`,
  it adds `"name_key"`.
- `Meta.constraints`: `UniqueConstraint(fields=["owner", "name_key"],
  name="unique_list_name_key_per_owner")` **replaces** `unique_list_name_per_owner`. The old rule
  is not needed: two names with the same `LOWER()` always have the same casefold.
- `max_length=300`: casefold can make a name longer ("ß" becomes "ss"; a few letters become
  three). A 100-letter name gives at most 300. SQLite does not check the length anyway; the field
  is never in a form.
- **Why this way**: the database compares two plain texts with `=`, so the rule works with every
  SQLite connection and every tool, with or without the app's SQL functions. The key is computed
  in Python, in one place.

Other ways, and why not:

| Way | Problem |
|---|---|
| Form check only (`casefold` in `clean_name`), keep today's constraint | The database still allows "Ærend" next to "ærend": the admin, a script, or two requests at the same moment can make both. |
| A database rule on `casefold(name)` (the SQL function) | Breaks wherever the function is not added (see "What is wrong today", 4). |
| `GeneratedField` with `casefold(name)` | The same problem: SQLite computes it with the SQL function. |
| A `COLLATE NOCASE` column | SQLite's NOCASE also knows only A to Z. |

### 2. The form

`TodoListForm.clean_name`:

```python
key = casefold(name)
clash = (
    TodoList.objects.filter(owner=self.instance.owner, name_key=key)
    .exclude(pk=self.instance.pk)
    .first()
)
if clash:
    raise forms.ValidationError(f"You already have a list called “{clash.name}”.")
```

- **The message names the list the person already has** (for example typed "ærend", has
  "Ærend"), so they see which one clashes. Same sentence as today (open choice 2).
- **Rename**: `exclude(pk=self.instance.pk)` as today, so renaming "inbox" to "Inbox" (the same
  list) is allowed and changes the name; `save()` keeps the same key.
- **Sharing**: the filter is `owner=self.instance.owner`. Lists shared **with** you have another
  owner, so their names never count. A member can have a list "Ærend" while a shared list is also
  called "Ærend".
- The form escapes the name in the message (Django's `{{ form.name.errors }}`), as today.

### 3. Every way a list is made goes through `save()`

- New list and rename: `form.save()`.
- Sign-up: `TodoList.objects.create(owner=user, name="Inbox")` calls `save()`.
- The admin: `TodoListAdmin` saves with `save()`. **Today the admin shows a friendly error** for
  "Work" next to "work": its form has both `owner` and `name`, so Django checks the old
  constraint before saving. With the new constraint on `name_key` (not a form field), Django
  would skip the check and the database would answer with a 500 page. To keep the friendly
  error:
  - `TodoList.clean()` sets `self.name_key = casefold(self.name)` (a model form runs `clean()`
    before it checks constraints);
  - `TodoList.validate_constraints(exclude=None)` removes `"name_key"` from `exclude` when
    `"name"` is not in `exclude`, then calls `super()`. So when a form has the name (and the
    owner), the unique rule on `owner` and `name_key` is checked, and a clash is a form error.
  For `TodoListForm` nothing changes: `owner` is not in that form, so Django still skips the
  constraint there, and `clean_name` gives the message.
- `QuerySet.update(name=...)` and `bulk_create` skip `save()`. No code does that today. The
  `AGENTS.md` row says: never change a list's name without `save()`.
- A data migration that makes lists (like `0006_default_lists.py`) uses historical models without
  this `save()`. It must set `name_key` itself; `AGENTS.md` says so.

## Security

- No new view or URL; the owner-only rule of rename (`get_object_or_404(TodoList, pk=pk,
  owner=request.user)`) and the `visible_to` rule do not change.
- `name_key` has `editable=False`: no form can set it. It is never shown.
- The clash check reads only the person's **own** lists (`owner=self.instance.owner`), so the
  message can never reveal another person's list name.
- The name goes into SQL only as a parameter.

## Data and migrations

Three migrations, in this order (the same pattern as `0015_todo_position` and
`0016_fill_todo_position`). Numbers assume A's `0019` is on `main` first; C makes them again
after A merges.

1. `0020_todolist_name_key` (made by Django: `makemigrations todos --name todolist_name_key`):
   `AddField name_key` with `default=""`. The model at this step has the field but still the old
   constraint.
2. `0021_fill_list_name_key` (a data migration, written by hand, as AGENTS.md allows): for every
   list, `name_key = casefold(name)`. The function is **copied into the migration** (NFC, then
   `str.casefold()`, three lines), so the migration does not change when app code changes later.
   **Duplicates**: per owner, lists with the same key are sorted by `created_at`, then `pk`. The
   first keeps its name. Each other one is renamed to "<name> (2)", "<name> (3)", ...: the
   smallest number whose new key is free for that owner. "Free" is checked against **all** of
   that owner's keys from the start (also lists that are not duplicates, like an existing
   "ærend (2)") **plus** every key the migration has already given out, so two renamed lists
   can never get the same name. When the name must be cut so the whole fits in 100 characters,
   trailing spaces are removed after the cut (no "ærend  (2)"). The key of a new name uses the
   same frozen function as every other row, which is exactly what `TodoList.save()` uses (NFC,
   then casefold). The review suggested an optional second NFC after casefold; it is **not**
   added, because the migration and `save()` must give the same key for the same name, and
   `sqlite_functions.casefold` (also used by search) has no second NFC. Their to-dos, members and ids do not change. The migration prints one line per
   renamed list ("Renamed list 7 to “ærend (2)”."), and nothing when there is none. Backwards:
   does nothing (the old names cannot be known; the renamed lists keep their new names, which are
   still valid).
3. `0022_list_name_key_unique` (made by Django: `--name list_name_key_unique`):
   `RemoveConstraint unique_list_name_per_owner`, `AddConstraint unique_list_name_key_per_owner`.

**The person's data**: one list, "Inbox", so nothing is renamed; the rule is still written and
tested. Run `make backup` before `migrate` (the README says so already; the PR repeats it).

**Going back**: `migrate todos 0019` removes the new constraint, the key and puts back the old
constraint. Renamed lists keep their new names. Revert the commit.

## Working next to

Wave: A, B, C and D are built at the same time; **merge order A → B → C (this) → D, then E**.

- **A, recurring-copy-rules**: adds `0019_todo_copy_fingerprint`. C is built on `main` (its
  migrations then start at `0019`); after A merges, C rebases, **deletes its own migration files
  and makes them again** with the same `--name` values, so they become `0020`, `0021`, `0022`
  and depend on A's. The hand-written data migration is moved, not rewritten (only its number
  and `dependencies` change). Never two `0019` files on `main`.
- **B, delete-undo**: no shared code (it does not touch `TodoList`).
- **D, backup-on-run**: no shared code.
- **E, cleanups**: merges last; it may shorten the `AGENTS.md` rows this plan writes.
- `AGENTS.md`: the `todos/models.py` and `todos/forms.py` rows; the `sqlite_functions.py` row
  (casefold is also used for `name_key`).

## Not part of this task

- Turning a duplicate that two requests make at the same moment into a form error (the database
  refuses the second with a 500 page, as today).
- Unique names for tags (they are already lower case) or to-do titles.
- Treating names with different spaces ("My  list" and "My list") or accents ("é" and "e") as
  the same.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | `name_key`; `TodoList.save()`, `clean()` and `validate_constraints()`; the new constraint instead of the old one; comments. |
| `todos/forms.py` | `TodoListForm.clean_name` uses `name_key` and names the clashing list. |
| `todos/migrations/0020_todolist_name_key.py` (new, made by Django) | The field. |
| `todos/migrations/0021_fill_list_name_key.py` (new, written) | The fill and the duplicate rule. |
| `todos/migrations/0022_list_name_key_unique.py` (new, made by Django) | The constraints. |
| `todos/tests/integration/test_lists.py` | New tests in `NewListTests` and `RenameListTests`. |
| `todos/tests/integration/test_sharing.py` | One test. |
| `todos/tests/integration/test_migrations.py` | `FillListNameKeyMigrationTests`. |
| `todos/tests/integration/test_access.py` | `AdminTests.test_admin_duplicate_is_a_form_error`. |
| `AGENTS.md` | `todos/models.py` row (`name_key`, the constraint, "never change a name without `save()`"; a data migration that makes lists sets `name_key`); `todos/forms.py` row; `sqlite_functions.py` row. |

## Steps

1. **Tests first** (below). `make integration`: the new ones fail ("Ærend" and "ærend" are both
   saved). Show the person.
2. Add `name_key` and `save()` (keep the old constraint); `makemigrations todos --name
   todolist_name_key`.
3. Write `0021_fill_list_name_key`.
4. Swap the constraint in `Meta`; `makemigrations todos --name list_name_key_unique`.
5. `migrate` **in the worktree only** (its own `db.sqlite3`; never the person's file, never port
   8000). Then `migrate todos 0019` and `migrate` again, to check both ways.
6. `clean_name`.
7. After A merges: rebase, make the migrations again (see "Working next to"), `make check`.
8. `AGENTS.md`. `make check`. Commit. Last commit: Status `**done** (<date in Tokyo>)`.

## Tests

### Integration: `todos/tests/integration/test_lists.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `NewListTests.test_nordic_name_in_other_case_is_refused` | alice has "Ærend"; a new list "ærend": 200 with "You already have a list called “Ærend”.", still one list. Subtests: "øl"/"ØL", "Åker"/"åKER", "STRASSE"/"straße". | Today's `iexact` (A to Z only). |
| `NewListTests.test_split_a_ring_counts_as_the_same` | alice has "Åker" (one letter); new list with "A" + U+030A + "ker": refused. | No NFC before casefold. |
| `NewListTests.test_different_nordic_name_is_allowed` | alice has "Ærend"; "Ærender" and "Erend" are saved (the "something happens" case). | A rule that refuses too much. |
| `NewListTests.test_database_refuses_a_duplicate_key` | `TodoList.objects.create(owner=alice, name="Ærend")` twice with different case: `IntegrityError` (inside `transaction.atomic()`). | Only a form check, or no `save()` that sets the key. |
| `NewListTests.test_save_sets_the_key` | `TodoList.objects.create(owner=alice, name="ÆRend")`: `name_key == "ærend"`; after a rename with `form.save()` the key follows. | A stale key after rename. |
| `RenameListTests.test_rename_to_other_case_of_own_name_works` | "ærend" renamed to "Ærend" (the same list): saved, the new name shows. | `exclude(pk=...)` lost. |
| `RenameListTests.test_rename_to_another_lists_nordic_name_is_refused` | alice has "Ærend" and "Hjem"; rename "Hjem" to "ærend": refused with the message, "Hjem" unchanged. | Rename skipping the rule. |
| `NewListTests.test_same_nordic_name_as_another_person_is_allowed` | bob has "Ærend"; alice makes "ærend": saved. | A rule across owners. |
| `AdminTests.test_admin_duplicate_is_a_form_error` (in `test_access.py`, next to the other admin tests) | A superuser posts the admin "add list" form for alice with "ærend" while she has "Ærend": 200 with an error on the form, no 500, still one list. The same with "Hjem" (no clash): saved. | The new constraint skipped by the admin form (a 500 page). |
| `NewListTests.test_message_escapes_the_name` | alice has a list `<b>Æ</b>`; typing `<b>æ</b>` shows the escaped name in the error. | `|safe` on the error. |

### Integration: `todos/tests/integration/test_sharing.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `ShareTests.test_shared_list_name_does_not_count` | alice shares "Ærend" with bob; bob makes his own "ærend": saved. | Checking `visible_to` instead of `owner`. |

### Integration: `todos/tests/integration/test_migrations.py`

`FillListNameKeyMigrationTests` (`TransactionTestCase`, like `DefaultListsTests`):

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_fill_sets_every_key` | Migrate to `0020`; make lists with the historical model; migrate to the newest: every `name_key` is `casefold(name)`. | An empty key left (then the constraint fails on a second empty key). |
| `test_duplicates_are_renamed` | At `0020`, one owner has, made in this order, "Ærø", "ærø (2)", "ærø" and "ÆrØ" (the old A-to-Z constraint allows all four); another owner has "ærø". After: the oldest keeps "Ærø"; the others become "ærø (3)" and "ÆrØ (4)" (the free numbers); "ærø (2)" and the other owner's list are unchanged; the to-dos stay in their lists. | Renaming the wrong one, a clash with an existing "(2)" (a list outside the duplicate group), two renamed lists given the same number, or renaming across owners. |
| `test_long_duplicate_name_is_cut` | A 100-letter duplicate gets a name of at most 100 characters that ends in " (2)"; a duplicate whose cut falls after a space has no double space before "(2)". | A name too long for the column, or trailing spaces kept. |
| `test_migration_goes_back` | Migrate back to `0019`: the old constraint is back, no error. | A broken backwards path. |

## Decided by the person (2026-10-11)

- List names are unique per owner ignoring case for **all** letters, also æ, ø and å ("Ærend" and
  "ærend").
- A robust way that does not depend on the custom SQLite function being added.
- Existing duplicates are handled in the data migration (the person has one list, "Inbox"; the
  rule is still written).
- Names of lists shared **with** you do not count.

## Open choices

1. **Stored key or form check only.** Stored `name_key` with a unique constraint,
   **recommended** (decision 1): the database itself refuses a duplicate, with every tool. Form
   only is fewer lines, but the admin, a script, or two requests at once can still make "Ærend"
   and "ærend".
2. **The message.** Name the list the person already has ("You already have a list called
   “Ærend”."), **recommended**, or the name they typed (today's code). Same sentence either way.
3. **A duplicate typed in the admin** (PERSON). Default written into the plan: keep today's
   friendly form error (`clean()` and `validate_constraints()`, decision 3), **recommended**.
   Other option: let the database refuse it with a 500 page (the admin is only for the person).
4. **What the migration does with duplicates.** Rename the newer ones to "<name> (2)" and on,
   **recommended**: nothing is lost and the person sees both lists. (Other options: stop the
   migration with an error and ask the person to rename by hand; or merge the lists, which mixes
   members and to-dos and cannot be undone.)

## Review

Verification by the planner (2026-10-11), against `main` (`d66b978`):

- Confirmed: the constraint is `UniqueConstraint(Lower("name"), "owner",
  name="unique_list_name_per_owner")` and the form uses `name__iexact`; both are A to Z only on
  SQLite.
- Confirmed: `todos/sqlite_functions.casefold` is plain Python (NFC, then `casefold`), and its
  docstring warns against database rules built on a Python function.
- Confirmed: sign-up (`accounts/views.py`) makes "Inbox" with `TodoList.objects.create`, which
  calls `save()`; `TodoListAdmin` edits the name through the model's `save()`.
- Confirmed: no code calls `TodoList.objects.update(name=...)` or `bulk_create` on lists.
- Confirmed: `test_migrations.py` already tests data migrations with `MigrationExecutor`
  (`DefaultListsTests`, `FillPositionMigrationTests`); the new class follows them.

The plan review (2026-10-11, an independent reviewer who also ran small prototypes) said APPROVE
WITH CHANGES. What changed:

- Admin regression found: today the admin form checks the old constraint and shows a friendly
  error; a constraint on `name_key` would be skipped and give a 500 page. Now `TodoList.clean()`
  sets `name_key`, and `validate_constraints()` keeps `name_key` in the check when `name` is
  checked. New admin test. Keeping the friendly error is the PERSON default.
- Migration `0021`: a new name is checked against all of the owner's keys from the start plus
  every key given out so far; trailing spaces are removed after a cut. The optional second NFC
  after casefold was not taken, so the migration and `save()` always make the same key.
