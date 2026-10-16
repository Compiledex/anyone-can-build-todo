# Plan: the admin log keeps no names

Status: draft (2026-10-16)

Builds on: **foundation** and **accounts** (`/admin/`, `todos/admin.py`, Django's own `User`
admin), **subtasks** (the steps inline on a to-do's admin page), **list-name-casefold** (the
style of a hand-written data migration with a frozen copy of its rule, and its migration tests),
and the docs set (PR #54: `docs/design/data-inventory-and-privacy.md` section 7, gap 6).

## Words used in this plan

- **Admin log**: Django's table `django_admin_log` (the model `LogEntry`). The admin at
  `/admin/` writes one row for each object it adds, changes or deletes.
- **`object_repr`**: the column that holds the object's name, `str(obj)`: a to-do's title, a
  list's name, a step's title, a username.
- **`change_message`**: the column that says what changed, as JSON (a list of small dicts).
- **Label**: what this plan stores instead of a name: the model's name and the row number, for
  example `todo 42`.
- **Mixin**: a small class with a few methods that other classes add to their parents, so they
  all get those methods.
- **Data migration**: a migration that changes rows, not the table. AGENTS.md allows writing one
  by hand.

## What is wrong today

Facts, checked on `main` (commit `2c75b89`) and in Django 5.2.17's own code in `.venv`:

1. `ModelAdmin.log_addition`, `log_change` and `log_deletions` (`django/contrib/admin/options.py`)
   all call `LogEntry.objects.log_actions(...)` (`django/contrib/admin/models.py`). It sets
   `object_repr=str(obj)[:200]`. So the log keeps "Buy milk", "Errands", "carol", also after the
   object is deleted (gap 6). In 5.1 and later, deletes go through `log_deletions` (plural): one
   row is `save()`d, **two or more are `bulk_create`d** ("Delete selected" in the change list).
2. `change_message` is made by `construct_change_message` (`django/contrib/admin/utils.py`):
   - for the object itself: `{"added": {}}` or `{"changed": {"fields": [<field labels>]}}`. Only
     field **labels** (like "Title"), never a value.
   - but for each inline object (a to-do's **steps**): `{"added": {"name": "subtask", "object":
     str(step)}}`, the same for `"changed"` and `"deleted"`. `str(step)` is the **step's title**
     (`Subtask.__str__`). So `change_message` can hold user text too.
   - Django's `UserAdmin.user_change_password` calls `self.log_change` with
     `[{"changed": {"fields": ["password"]}}]` (a label, no value).
3. The admin's "Recent actions" box (`admin/index.html`) shows `{{ entry.object_repr }}` as the
   link text (or plain text for a deletion), with the content type's name under it. An empty
   `object_repr` would make an empty, invisible link.
4. Only staff can open `/admin/` (in this app: the owner's superuser). The box shows only the
   viewer's own actions (`get_admin_log ... for_user user`). `LogEntry` itself has no admin page.
5. Registered admins: `TodoList` and `Todo` (`todos/admin.py`), and Django's own `User` and
   `Group` (`django/contrib/auth/admin.py`). `accounts/` has no `admin.py`.

## Goal

The admin log keeps when something was added, changed or deleted, by whom, and which fields
changed, but **no names**: no to-do title, list name, step title or username. New rows store a
label like `todo 42`; a data migration replaces the names in the rows that are already there. The
admin's "Recent actions" box shows the label.

## Decisions

### 1. How: a mixin on every registered admin, not a signal

Ways to stop `object_repr` being written, checked against Django 5.2:

| Way | Problem |
|---|---|
| A `pre_save` signal on `LogEntry` that blanks the name | **Misses "Delete selected"** with two or more objects: `log_actions` uses `bulk_create`, which sends no signal. (Prototype: deleting two to-dos with the admin action gave 2 rows with both titles and 0 signal calls.) |
| Replace `LogEntry.objects.log_actions` (monkeypatch Django's manager) | Changes Django's code at run time, for every caller; hard to see and to explain; breaks quietly when Django changes the method. |
| Call `super()`, then `update()` the row | The name is written first, then overwritten: for a moment it is in the database, and its old bytes can stay in the file (free pages). |
| **A mixin with its own `log_addition`, `log_change` and `log_deletions`** (**chosen**) | These three are the only places the admin writes a log row (`UserAdmin.user_change_password` also goes through `log_change`). The name is never written. A test checks that every registered admin has the mixin. |

`todos/admin_log.py` (new):

```python
"""The admin log without names: no to-do title, list name, step or username.

Every ModelAdmin in this project has NoNamesInLog first (a test checks it).
Django's own log_actions() stores str(obj); these methods store a label like
"todo 42" instead, and hide the names of inline objects (steps) in the change
message. Only field labels (like "Title") stay.
"""

HIDDEN_NAME = "name not kept"


def log_label(obj):
    """ "<model name> <id>", for example "todo 42": a number, never user text."""


def hide_names(change_message):
    """The change message as JSON text, with every "object" value replaced by HIDDEN_NAME.

    A list (from construct_change_message) or JSON text. Anything that is not a
    JSON list of dicts (old plain text) becomes "": it could hold any text.
    "" stays "". Field labels ("fields") and model names ("name") stay.
    """


class NoNamesInLog:
    """Put first in the parents of every ModelAdmin: log rows keep no names."""

    def log_addition(self, request, obj, message):
        return self._log(request, [obj], ADDITION, message)[0]

    def log_change(self, request, obj, message):
        return self._log(request, [obj], CHANGE, message)[0]

    def log_deletions(self, request, queryset):
        return self._log(request, queryset, DELETION, "")

    def _log(self, request, objects, action_flag, message):
        """Like Django 5.2's LogEntry.objects.log_actions, with a label as object_repr.

        One row: save(); more: bulk_create (as Django does). Returns the rows.
        """
        message = hide_names(message)
        entries = [
            LogEntry(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(
                    obj, for_concrete_model=False
                ).pk,
                object_id=obj.pk,
                object_repr=log_label(obj)[:200],
                action_flag=action_flag,
                change_message=message,
            )
            for obj in objects
        ]
        ...
```

- **Return values** match Django's: `log_addition` and `log_change` return the row,
  `log_deletions` a list. (Django's admin does not use them, but a subclass might.)
- **Django's deprecated `log_deletion`** (singular, removed in Django 6.0) is not overridden:
  Django 5.2 only calls it when a class overrides it, and none does.
- **A test compares** the row the mixin makes with the row Django's own `log_actions` makes for
  the same object: every field is the same except `id`, `action_time`, `object_repr` and
  `change_message`. A Django upgrade that adds a field to the log fails this test, so the copy
  is updated.
- **Where the mixin is used**:
  - `todos/admin.py`: `class TodoListAdmin(NoNamesInLog, admin.ModelAdmin)`, `class
    TodoAdmin(NoNamesInLog, admin.ModelAdmin)`. The inline (`SubtaskInline`) writes no log row of
    its own; its steps are in the to-do's `change_message`, which `hide_names` cleans.
  - `accounts/admin.py` (new): `admin.site.unregister(User)` and `unregister(Group)`, then
    register `class UserAdmin(NoNamesInLog, django.contrib.auth.admin.UserAdmin)` and `class
    GroupAdmin(NoNamesInLog, django.contrib.auth.admin.GroupAdmin)`. `accounts` comes after
    `django.contrib.auth` in `INSTALLED_APPS`, so Django's admin is registered first and can be
    replaced. The pages look and work exactly as before.

### 2. The label: `<model name> <id>`

- `log_label(obj)` is `f"{obj._meta.model_name} {obj.pk}"`: `todo 42`, `todolist 3`,
  `user 2`, `group 1`. `model_name` is the same text as `content_type.model` (both from the
  model's class name), so the data migration can make **exactly the same label** from a row's
  content type and `object_id`. With no id: only the model name. The `object <id>` branch (a row
  whose content type was deleted, `content_type` is `NULL`) exists **only in the migration's
  `frozen_label`**: a new row always has an object, so `log_label` never needs it.
- **Why not empty**: "Recent actions" uses `object_repr` as the link text. An empty one is an
  invisible link, and a deletion shows nothing at all. With the label, the box shows
  "todo 42" (a link to the to-do's admin page while it exists) with "Todo" under it.
- **Why not the verbose name** ("to-do list 3"): a data migration's historical models do not
  always know it (a deleted model), and two rules for one label would drift.
- The label holds no user text: a model name from the code, and a database number. The number
  is already in `object_id`.

### 3. The change message keeps field labels, hides inline names

- `{"changed": {"fields": ["Title", "Due date"]}}` stays: labels from the code, never values.
- `{"added": {"name": "subtask", "object": "Call the bank"}}` becomes `{"added": {"name":
  "subtask", "object": "name not kept"}}`. The admin's history page then says: Added subtask
  “name not kept”.
- `HIDDEN_NAME = "name not kept"`: plain words, so the owner sees that the name was left out on
  purpose (open question 1). The inline step's id is not used: a deleted step has no id any more
  when the message is made.
- Plain-text change messages (not a JSON list): Django's admin has written JSON since Django
  1.10, so none should exist; if one does, it becomes "" (it could hold any text).

### 4. The data migration `todos/migrations/0023_blank_admin_log_names.py`

Written by hand (AGENTS.md allows data migrations).

- `dependencies`: `("todos", "0022_todo_copy_fingerprint")`, `("admin",
  "0003_logentry_add_action_flag_choices")` (the newest admin migration in Django 5.2), and
  `("contenttypes", "0002_remove_content_type_name")` (the content type model as it is now).
- Forward, `blank_names(apps, schema_editor)`: for every `LogEntry` row (historical model,
  `select_related("content_type")`, in order of `pk`): `object_repr = frozen_label(row)[:200]`,
  `change_message = frozen_hide_names(row.change_message)`. The rows are read and written in
  chunks of 500 (`iterator(chunk_size=500)`, and `bulk_update(chunk, ["object_repr",
  "change_message"])` after each chunk), so a big log never sits in memory at once. Nothing else
  in the row changes.
- `frozen_label` and `frozen_hide_names` are **copies** in the migration file (as
  `0020_fill_list_name_key.py` copies `casefold`), so the migration never changes when
  `todos/admin_log.py` changes later. `frozen_label` uses `row.content_type.model` and
  `row.object_id`, which gives the same label as `log_label` for a new row.
- Backward: `migrations.RunPython.noop`. The names cannot be known again; the labels stay, and
  they are valid rows. Going back with `migrate todos 0022` works.
- It prints nothing. The person's database: probably a few rows from making the first superuser
  and lists in `/admin/`.

## Security

- **Who can see the log**: only staff, at `/admin/` (Django's `AdminSite.has_permission`); in
  this app only the owner. A logged-in person who is not staff gets the admin's login page, and a
  visitor too. No new view, URL or form. A test checks that a normal user (alice) cannot open
  `/admin/` and does not see the log.
- **What the log keeps after this**: the admin user, the time, the action, the content type, the
  object's id, field labels. No text a person typed.
- The label is built from the model's code name and the database id, never from `str(obj)`.
- **Old bytes in the file**: the migration overwrites the names, but SQLite may keep the old bytes
  in free pages of `db.sqlite3` until it reuses them, and every backup made before the migration
  still has the names. The docs say so (gap 6 text); erasing free pages is open question 3.

## Data and migrations

- No schema change: `django_admin_log` keeps its columns. One data migration, `0023` (above).
- **Before migrating**, the person runs `make backup` (the deployment runbook, section 3, says
  so; the PR body repeats it).
  After that copy, the names are only in backups (manual ones forever, daily ones for 14 days).
- **Going back**: `migrate todos 0022` (a no-op backwards) and revert the commit. New rows then
  get names again; the replaced names do not come back.
- delete-account (merges later) adds no migration. If another plan adds a `todos` migration
  first, this one is renumbered (see "Working next to").

## Working next to

Wave A: **split-browser-tests**, **readme-to-runbooks**, **privacy-small-fixes** and
**admin-log-without-names (this)** are built at the same time; **delete-account** is built in
parallel too. **Merge order: split-browser-tests → readme-to-runbooks → privacy-small-fixes →
admin-log-without-names (this) → delete-account.**

- **Migration number**: no other plan in this round adds a migration, so `0023` stays. If one
  merges first anyway, delete this file's number and make it the next one, with `dependencies`
  on that migration (never two `0023` files on `main`).
- **privacy-small-fixes** merges just before this. Both close gaps in
  `docs/design/data-inventory-and-privacy.md` section 7, remove rows in the design doc's known
  limits, change the PRD's open question 6 and add to `CHANGELOG.md`'s `[Unreleased]` section.
  After privacy-small-fixes, open question 6 asks only about the admin log; this plan removes it.
  Rebase and merge these lines by hand. With privacy-small-fixes, the admin's own messages ("The
  to-do “…” was deleted successfully.") are in the session, not a cookie.
- **delete-account** merges last. Deleting a user deletes the log rows **that user made** as
  staff (`LogEntry.user` is `CASCADE`); rows *about* the deleted person's objects stay, and after
  this plan they hold only labels, so no name of a deleted account stays in the log. The person
  can still delete a user in `/admin/`: the row is "user 3".
- `AGENTS.md`: this plan writes the `todos/admin.py` row, a new `todos/admin_log.py` row, the
  `accounts/` row (`accounts/admin.py`), and the `todos/migrations/` row (one more data
  migration). privacy-small-fixes writes other rows.
- split-browser-tests and readme-to-runbooks touch none of these files.

## Not part of this task

- Erasing old bytes from the SQLite file (`VACUUM`, `PRAGMA secure_delete`): open question 3.
- Removing names from backups that already exist.
- Deleting old log rows, or a time limit for them.
- A page that lists all log rows (Django has none for `LogEntry`, and none is added).
- Changing what the admin's change lists show (they show the real titles and names: that is the
  admin's job).

## Changes to files

| File | Change |
|---|---|
| `todos/admin_log.py` (new) | `HIDDEN_NAME`, `log_label`, `hide_names`, `NoNamesInLog`. |
| `todos/admin.py` | `TodoListAdmin` and `TodoAdmin` get `NoNamesInLog` first. |
| `accounts/admin.py` (new) | Unregister and register again `User` and `Group` with `NoNamesInLog`. |
| `todos/migrations/0023_blank_admin_log_names.py` (new, written) | The data migration, with `frozen_label` and `frozen_hide_names`. |
| `todos/tests/unit/test_admin_log.py` (new) | `HideNamesTests`, `LogLabelTests`. |
| `todos/tests/integration/test_admin_log.py` (new) | `AdminLogTests`. |
| `todos/tests/integration/test_migrations.py` | `BlankAdminLogNamesMigrationTests`; names of the migrations at the top. |
| `docs/design/data-inventory-and-privacy.md` | Section 2: the `django_admin_log` row (labels, no names). Section 3: a staff user's session holds the admin's success message (with a title, for example "The to-do “…” was deleted successfully.") until the next admin page shows it; accepted. Section 7: gap 6 says **Closed** (keep the number), with the note about backups and free pages. |
| `docs/design/design-doc.md` | Section 12: remove the "Admin log keeps object names" row. |
| `docs/product/prd.md` | Remove open question 6 (all its gaps are closed). |
| `docs/product/tracking-plan.md` | The sentence "the only records of activity are Django's admin log and ..." gets "(without names)". |
| `CHANGELOG.md` | `## [Unreleased]`, **Security**: the admin log keeps no names; old names are replaced. |
| `AGENTS.md` | Rows: `todos/admin.py`, new `todos/admin_log.py` ("every ModelAdmin has `NoNamesInLog` first; a test checks it"), `accounts/` (`admin.py`), `todos/migrations/` (0023). |
| `docs/plans/README.md` | A row for this plan when it is built. |
| `docs/plans/admin-log-without-names.md` | Status line when built. |

## Steps

1. **Tests first** (below). `make unit` and `make integration`: the new ones fail (the log has
   the title; the module does not exist). Show the person.
2. `todos/admin_log.py`, then `todos/admin.py`, then `accounts/admin.py`.
3. The data migration. `uv run python manage.py makemigrations --check --dry-run` must say "No
   changes detected" (the migration has no schema change).
4. **In the worktree only** (its own `db.sqlite3`, never the person's file, never port 8000):
   `migrate`, make a superuser with `createsuperuser --noinput` and `DJANGO_SUPERUSER_PASSWORD`
   set to a throw-away value in that shell, then `migrate todos 0022` and `migrate` again, to
   check both ways.
5. The docs and `AGENTS.md`. `make check`. Commit. Last commit: Status `**done** (<date in
   Tokyo>)` and the `docs/plans/README.md` row. The PR says: run `make backup` before
   `migrate`.

## Tests

### Unit: `todos/tests/unit/test_admin_log.py` (`SimpleTestCase`, no database)

| Test | What it checks | The break that fails it |
|---|---|---|
| `HideNamesTests.test_inline_names_are_hidden` | `[{"added": {"name": "subtask", "object": "Call the bank"}}, {"changed": {"name": "subtask", "object": "Pay", "fields": ["Title"]}}, {"deleted": {"name": "subtask", "object": "Old"}}]`: every `object` is `HIDDEN_NAME`; `name` and `fields` stay. Also as JSON text. | No hiding, or hiding the field labels. |
| `HideNamesTests.test_field_labels_stay` | `[{"added": {}}]` and `[{"changed": {"fields": ["Title", "Due date"]}}]` come out the same (the "nothing to hide" case). | Removing everything. |
| `HideNamesTests.test_plain_text_becomes_empty` | `"Changed title to Secret."`, `"[not json"`, `'{"a": 1}'` give `""`; `""` stays `""`. | Keeping plain text. |
| `HideNamesTests.test_input_is_not_changed` | The list given to `hide_names` is the same after the call (a copy is changed). | Changing the caller's list. |
| `LogLabelTests.test_label_is_model_and_id` | `Todo(pk=42)` gives `todo 42`, `TodoList(pk=3)` gives `todolist 3`, a `User(pk=2, username="carol")` gives `user 2`, never "carol". | `str(obj)`. |
| `LogLabelTests.test_migration_label_is_the_same` | The migration's `frozen_label` (imported with `importlib`) gives the same text as `log_label` for the same model and id, and `object 9` without a content type; its `frozen_hide_names` gives the same as `hide_names` for the cases above. | The migration and the mixin drifting apart. |

### Integration: `todos/tests/integration/test_admin_log.py`

`AdminLogTests` (`TestCase`): a superuser "staffer" is logged in with `force_login`; carol owns
"Secret errands" with the to-do "Buy secret milk". Every test checks that no row's
`object_repr` or `change_message` contains "secret" (any case) or "carol". The form fields of the
admin pages are read from a `GET` of the page first (the steps inline uses the prefix
`subtasks`).

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_add_keeps_a_label` | Add a to-do with one step "Call the bank" in `/admin/todos/todo/add/`: one row, `object_repr == f"todo {pk}"`, `change_message` has `{"added": {}}` and the step as `HIDDEN_NAME`. Fails on `main`. | Django's default `log_addition`. |
| `test_change_keeps_field_labels_only` | Change the title: the row has `{"changed": {"fields": ["Title"]}}` and neither the old nor the new title. | A message with values. |
| `test_delete_keeps_a_label` | Delete the to-do on its delete page: the row is `todo <pk>`, `action_flag == DELETION`. | Default `log_deletions`. |
| `test_delete_selected_keeps_labels` | "Delete selected" with two to-dos (`action=delete_selected`, `post=yes`): two rows, both labels, no title. | A `pre_save` signal, which `bulk_create` skips. |
| `test_list_change_keeps_no_name` | Rename "Secret errands" in `/admin/todos/todolist/<pk>/change/`: `todolist <pk>`, fields `["Name"]`. | `TodoListAdmin` without the mixin. |
| `test_deleting_a_user_keeps_no_username` | Delete carol at `/admin/auth/user/<pk>/delete/`: the row is `user <pk>`, no "carol". | Django's own `UserAdmin` still registered. |
| `test_recent_actions_show_the_label` | After an add, `GET /admin/` shows `todo <pk>` in the "Recent actions" box, as a link to the change page, and not the title. | An empty `object_repr` (invisible link). |
| `test_every_admin_hides_names` | For every model admin in `admin.site._registry` (today: `TodoList`, `Todo`, `User`, `Group`): `type(ma).log_addition is NoNamesInLog.log_addition`, the same for `log_change` and `log_deletions` (so a parent later in the MRO cannot win), and `type(ma).log_deletion is ModelAdmin.log_deletion` (no class brings back Django's deprecated path, which stores `str(obj)`). | A new admin without the mixin, the mixin after `ModelAdmin` in the parents, or an override of `log_deletion`. |
| `test_rows_match_djangos_own_except_names` | For one to-do, `LogEntry.objects.log_actions(..., single_object=True)` and the mixin's `log_change`: all fields equal except `id`, `action_time`, `object_repr`, `change_message`. | A Django upgrade that adds a log field the copy misses. |
| `test_normal_user_cannot_open_the_admin` | alice (not staff) and a visitor get a redirect to the admin's login page for `/admin/`, and the page has no log rows. | An admin open to non-staff. |

### Integration: `todos/tests/integration/test_migrations.py`

`BlankAdminLogNamesMigrationTests` (`TransactionTestCase`, like `FillListNameKeyMigrationTests`;
`tearDown` migrates to the newest). Before the migration:
`migrate([("todos", "0022_todo_copy_fingerprint"), ("admin",
"0003_logentry_add_action_flag_choices"), ("contenttypes", "0002_remove_content_type_name")])`
(all three targets, so the historical apps have `LogEntry` and `ContentType`). Rows are made with
the historical `LogEntry`, with content types from the historical `ContentType`.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_names_are_replaced` | Rows: an addition of a to-do "Buy secret milk"; a change with a step "Call the bank" in `change_message` and `fields: ["Title"]`; a deletion of user "carol"; a row with no content type; a row with plain-text "Changed title to Secret.". After `migrate_to_newest()`: `todo <id>`, `user <id>`, `object <id>`; the step is `HIDDEN_NAME`, `["Title"]` stays; the plain text is `""`. No row has "secret" or "carol". | A migration that only blanks `object_repr`, or misses inline names. |
| `test_other_columns_do_not_change` | `action_time`, `user_id`, `action_flag`, `object_id`, `content_type_id` and the number of rows are the same before and after. | A migration that deletes or rewrites rows. |
| `test_migration_goes_back` | Migrate back to `todos 0022`: no error; the labels stay. Then forward again: no error (running it twice is safe). | A broken or non-idempotent path. |

No CUJ test: the owner sees the change only in `/admin/`, and the integration tests cover it.

## Open questions

1. **The text for a hidden inline name.** Decided in the plan review: "name not kept".
2. **The label.** Decided in the plan review: `todo 42` style (model code name and id).
3. **Erase old bytes from the file?** Not in this plan, **recommended**: overwritten names can
   stay in SQLite's free pages until they are reused, and in older backups. `PRAGMA
   secure_delete` (or a `VACUUM` after the migration) would also help for deleted to-dos, so it
   is its own small plan if the owner wants it. The docs name the limit.

## Review

Verification by the planner (2026-10-16), against `main` (`2c75b89`) and Django 5.2.17 in
`.venv`:

- Confirmed: `log_actions` stores `str(obj)[:200]`; one row with `save()`, more with
  `bulk_create`; `delete_selected` calls `log_deletions(request, queryset)`; `delete_view` calls
  `log_deletions(request, [obj])`; `changeform_view` and `changelist_view` call `log_addition` and
  `log_change`; `UserAdmin.user_change_password` calls `log_change`.
- Confirmed: `construct_change_message` puts `str(added_object)` (and changed and deleted inline
  objects) in `change_message`; `Subtask.__str__` is the title. The main object's part has only
  field labels.
- Confirmed with a throw-away prototype test (deleted again): "Delete selected" on two to-dos
  wrote two log rows with both titles and sent no `pre_save` signal.
- Confirmed: `admin/index.html` uses `object_repr` as the link text; `object_id` and
  `content_type` can be empty (`null=True`); admin's newest migration is
  `0003_logentry_add_action_flag_choices`; the newest `todos` migration is
  `0022_todo_copy_fingerprint`.

The plan review (2026-10-16, an independent reviewer) said APPROVE WITH CHANGES. What changed:

- The registry test checks the methods themselves (`type(ma).log_addition is
  NoNamesInLog.log_addition`, and so on, and `log_deletion is ModelAdmin.log_deletion`), not
  only `isinstance`, so the order of the parents cannot hide a wrong method.
- The `object <id>` branch (no content type) is only in the migration's `frozen_label`.
- The migration reads and writes in chunks of 500 (no `.iterator()` feeding one big
  `bulk_update`).
- Data inventory: a staff user's session holds the admin's success message with a title until
  the next page; accepted.
- Decided by the coordinator: "name not kept" for hidden inline names; `todo 42` style labels.

## Decided by the person

- (2026-10-16, from the round's brief) Keep the admin log, but without names. New rows store no
  title; a data migration removes the names from existing rows.
