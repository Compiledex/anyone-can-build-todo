# Plan: backups before a reset, "#work" finds the tag, and the repeat error on the date

Status: **approved** (2026-10-11, by the orchestrator for the person), not started.

Builds on: **foundation** (the `Makefile`, `make reset`), **tags** (`parse_tags`), **search**
and **nordic-letters** (merged first: `search()` uses `casefold` and `Contains(CaseFold(...))`),
**recurring** (`Todo.clean`, `TodoForm.full_clean`), **safe-toggles** and **accessibility-pass**
(merged before this one), and **recurring-undo-steps**.

The app runs only on the person's Mac, with SQLite (`db.sqlite3`). There is no server and no
deploy work here.

## Words used in this plan

- **Backup**: a copy of `db.sqlite3` in another file, to get the data back after a mistake.
- **SQLite online backup**: SQLite's own way to copy a database file safely, even while the app
  writes to it. Python has it built in (`sqlite3.Connection.backup`).
- **Management command**: a Python file that runs with `uv run python manage.py <name>`, like
  `send_reminders`.

## What is wrong today

Facts, checked on `main` (commit `6c7169b`) and on `feature/nordic-letters`:

1. `make reset` is `rm -f db.sqlite3` then `migrate`. One command deletes every list, to-do and
   account, with no question and no copy. `make help` says so, but a person can type it by
   mistake, or an AI agent can run it. There is no `make backup`, and the README never says how
   to back up the data.
2. The list page shows tags as `#work`. A person who searches `#work` finds nothing: the tag is
   stored as `work` (`parse_tags` strips a leading `#`), and `search()` looks for the text `#work`
   in the tag names.
3. When a person sets Repeat but no due date, "A repeating to-do needs a due date." shows under
   **Repeat** and marks Repeat as wrong. The field to fix is **Due date**, which is not marked.

## Goal

`make reset` asks first and keeps a copy; `make backup` makes a copy any time; the README says how
to back up and restore. Searching `#work` finds the to-dos tagged `work`. The repeat error sits
under Due date, the field to fix.

## Decisions

### 1. `backup_db`: one management command makes a safe copy

- New `todos/backup.py`:

  ```python
  def backup_database(source, folder, now):
      """Copy the SQLite file `source` into `folder` as db-YYYYMMDD-HHMMSS.sqlite3.

      Uses SQLite's online backup, so the copy is whole even while the app runs.
      Returns the new file's path, or None when `source` does not exist.
      Never overwrites a file, and never changes `source`.
      """
  ```

  It opens `source` **read-only** (`sqlite3.connect(f"file:{source}?mode=ro", uri=True)`), so a
  missing file is never created as an empty database. It makes `folder` if needed. Then:
  1. It **reserves the final name** with `open(target, "xb")` (create, fail if it exists). Two
     backups in the same second: the second gets `FileExistsError` and writes nothing. No "check,
     then create" gap.
  2. It writes the copy to a **temporary name in the same folder** (`.db-...sqlite3.tmp`).
  3. It **renames** the temporary file over the reserved (empty) final name (`os.replace`, one
     step on the same disk). So `backups/` never holds a half-written file with the final name.
  If the copy fails, it removes both the temporary file and the reserved empty file.
  Plain Python and the standard library only.
- New `todos/management/commands/backup_db.py`: `uv run python manage.py backup_db`. The source
  is `settings.DATABASES["default"]["NAME"]`, the folder `settings.BASE_DIR / "backups"`, the time
  `timezone.localtime()` (the app's time zone, the same "today" as everywhere else). Two options,
  `--source` and `--folder`, exist for the tests; the `Makefile` never uses them. It prints one
  line: `Saved a copy in backups/db-20261011-081500.sqlite3.`, or `No database yet: nothing to
  back up.` (exit 0), or a `CommandError` with a plain message.
- Why a command and not `cp` in the `Makefile`: `cp` of a SQLite file while `make run` writes can
  give a broken copy, and a command can be tested.

### 2. `make backup`, and `make reset` asks first

```make
backup:
	uv run python manage.py backup_db

reset:
	@if [ -f db.sqlite3 ]; then \
		if [ "$(CONFIRM)" != "yes" ]; then \
			printf 'This deletes every account, list and to-do in db.sqlite3.\nA copy goes to backups/ first. Type yes to go on: '; \
			read answer; \
			if [ "$$answer" != "yes" ]; then echo "Nothing was deleted."; exit 1; fi; \
		fi; \
		uv run python manage.py backup_db || exit 1; \
	fi
	rm -f db.sqlite3
	uv run python manage.py migrate
```

- It **asks first, then copies**: a "no" leaves nothing behind. (The request said "copies, then
  asks"; the order does not change the safety, and this way a "no" makes no file.)
- Only the word `yes` goes on. Enter, `y`, or no terminal at all (`read` gets nothing) stops with
  "Nothing was deleted." and exit code 1.
- `make reset CONFIRM=yes` skips the question (for a person who knows), but **still** makes the
  copy.
- If the copy fails, nothing is deleted (`|| exit 1`).
- No `db.sqlite3`: no question, no copy, just `migrate`.
- `make help` gets both lines: `make backup  copy db.sqlite3 to backups/ (safe while the server
  runs)` and `make reset  ask, copy db.sqlite3 to backups/, then start again with an empty
  database`.

### 3. `backups/` is not in git

`.gitignore` gets `/backups/` (only the folder at the top of the project), with a comment: "Copies of db.sqlite3 from make backup and make
reset. Your data: never commit it." Old copies are kept; the person deletes them by hand (the
README says so).

### 4. README: "Back up your data"

A short new section after "Run it on your laptop": what `make backup` does and where the file
goes; that `make reset` asks and makes a copy; how to **restore**: stop the server (`Ctrl+C`),
copy the backup over `db.sqlite3` (`cp backups/db-<time>.sqlite3 db.sqlite3`), run `make setup`
(or `uv run python manage.py migrate`) so an older copy gets the newest tables, start again; and
that copying the `backups/` folder to another disk or cloud is what really protects the data.
The contents line at the top gets the new link.

### 5. Search: `#work` also finds the tag `work`

In `search()` (after nordic-letters):

```python
folded = casefold(q)
tag_text = folded.lstrip("#").strip()  # Tags are stored without "#" (parse_tags).
...
| Q(pk__in=with_matching_tag)   # only when tag_text is not empty
```

- The title and the notes are still searched for the whole text (`#work`), so a to-do titled
  "Fix #work bug" is still found.
- The tag part uses the text without leading `#` and without spaces at the ends (`# work` finds
  `work`), like `parse_tags`.
- `#` alone, `###` or `# `: the tag part is empty, so the tag sub-query is **left out** (an empty
  `Contains` would match every tag). Title and notes are still searched for `#`.
- Still one sub-query, still from `todos`, so a to-do with two matching tags is shown once, and no
  other person's rows are read.

### 6. "A repeating to-do needs a due date." goes under Due date

- `Todo.clean()` puts the error on `due_date` instead of `repeat` (same text, same code
  `needs_due_date`).
- `TodoForm.full_clean` keeps the rule "a typed date that is not valid shows only its own error":
  now both errors would be on `due_date`, so it removes the `needs_due_date` error from
  `due_date` when `due_date` also has another error.
- Nothing else changes: on the list page, `{{ form.due_date.errors }}` already shows under the
  date field and already sets `aria-invalid` and `aria-describedby` on the date input; on the edit
  page `_field.html` does the same. Repeat is no longer marked red.
- The `Meta.fields` comment in `forms.py` ("Todo.clean() puts its error on repeat") changes.
- Why this is the smallest clear choice: one place shows the message, and it is the field the
  person must change. Marking both fields would show two red fields for one problem; a message
  under Repeat pointing elsewhere is what we have today.

## Security

- **Backups hold all the data** (accounts with password hashes, lists, to-dos). They stay on the
  Mac, in the project folder, and are ignored by git. The README says not to share them.
- The command takes no user input from a web request; `--source` and `--folder` are for the
  command line only. The source is opened read-only. The target is never overwritten.
- No new view. `make reset` cannot be run from the web.
- Search: the text goes into SQL only as a parameter (Django's `Contains`). `order_by` is not
  touched. The sub-query starts from the list's to-dos, so data isolation does not change.
- The repeat error: no change to who may save what.

## Data and migrations

No model field change and no migration (`clean()` is Python only; `makemigrations --check` sees
nothing). No existing row changes. The tests never open the person's `db.sqlite3`: the backup
tests use a temporary folder with their own small SQLite file. Going back: revert the commit; old
backup files stay and are harmless.

## Working next to

Merge order: **safe-toggles → accessibility-pass → local-safety (this) → maintenance-pass**.
local-safety has **no dependency** on the first two (no shared code file, only different
`AGENTS.md` rows and different classes in `test_views.py`), so it may be built in parallel with
them; whichever merges later rebases.

- nordic-letters (merged first) wrote today's `search()`; this plan adds only the `#` rule.
- safe-toggles and accessibility-pass change templates and `views.py`; this plan does not touch
  them. The list page template already shows due date errors.
- maintenance-pass splits `test_views.py`: the `RecurringTests` changed here move to
  `test_recurring.py` there. It merges last.
- `AGENTS.md`: different rows (`models.py`, `forms.py`, `queries.py`, the new rows, the
  Commands list).

## Not part of this task

- Automatic backups (for example every day with launchd). Left for the person.
- A `make restore` command: the README explains the one `cp`.
- Deleting old backups automatically.
- Searching for several tags at once (`#work #home`).

## Changes to files

| File | Change |
|---|---|
| `todos/backup.py` (new) | `backup_database(source, folder, now)`. |
| `todos/management/commands/backup_db.py` (new) | The command. |
| `Makefile` | `backup`; `reset` asks and copies; `.PHONY`; `help`. |
| `.gitignore` | `backups/` with the comment. |
| `README.md` | "Back up your data"; the contents line; `make backup` in the short command list if there is one. |
| `todos/queries.py` | `search()`: the `#` rule (decision 5). |
| `todos/models.py` | `Todo.clean()`: the error on `due_date`. |
| `todos/forms.py` | `TodoForm.full_clean` and the `Meta.fields` comment. |
| `todos/tests/integration/test_backup.py` (new) | The backup tests. |
| `todos/tests/integration/test_search.py` | The `#` tests. |
| `todos/tests/unit/test_models.py` line 53 | `{"due_date": [...]}` instead of `{"repeat": [...]}` (decision 6). |
| `todos/tests/integration/test_views.py` (`RecurringTests`) | Where the error shows. |
| `AGENTS.md` | New rows `todos/backup.py` and `backup_db`; the Commands list (`make backup`, `make reset` asks); `queries.py` row (`#`); `models.py` and `forms.py` rows (the error on `due_date`). |

## Steps

1. **Tests first** (below). `make integration unit`: the new ones fail. Show the person.
2. `todos/backup.py`, the command, then the `Makefile` and `.gitignore`.
3. By hand, **in the worktree only** (its own `db.sqlite3`, made with `migrate`; never the main
   checkout's file, never port 8000): `make backup` makes a file in `backups/`; `make reset` then
   Enter says "Nothing was deleted." and the file is unchanged; `make reset` then `yes` makes a
   second copy and an empty database; `make reset CONFIRM=yes` copies without asking. Say what
   you saw in the PR. **Never run `make reset` with `CONFIRM=yes`, or answer `yes`, outside the
   worktree**: in the main checkout it would replace the person's real data.
4. `search()`.
5. `Todo.clean()` and `TodoForm.full_clean`.
6. README and `AGENTS.md`. `make check`. Commit. Last commit: Status `**done** (<date>)`.

## Tests

### Integration: `todos/tests/integration/test_backup.py`

`SimpleTestCase` (no Django database): each test makes a temporary folder and a small SQLite file
with the standard `sqlite3` module (one table, two rows), so the person's data is never near it.
Every call of the function and of the command **always** passes the temporary source and folder
(`--source`, `--folder`), so no test ever writes to the real `backups/`.

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_backup_copies_the_rows` | `backup_database` returns `folder / "db-20261011-081500.sqlite3"` for a fixed `now`; the copy has the two rows and passes `PRAGMA integrity_check`. | A wrong name, or a copy that is not a database. |
| `test_backup_makes_the_folder` | A folder that does not exist yet is made. | Failing on the first backup. |
| `test_missing_source_makes_nothing` | No source file: returns `None`, no file in the folder, and **no source file is created**. | Opening the source read-write (SQLite would create an empty file). |
| `test_never_overwrites` | A file with the target name exists: `FileExistsError`, that file is unchanged, and no temporary file is left. | Overwriting an older backup, or a check-then-create instead of `open(target, "xb")`. |
| `test_failed_copy_leaves_no_file` | The copy step raises (patched): no final file and no `.tmp` file in the folder. | Leaving a half-written or empty backup. |
| `test_source_is_not_changed` | The source's bytes are the same before and after. | Writing to the source. |
| `test_command_prints_where_the_copy_is` | `call_command("backup_db", source=..., folder=...)` prints "Saved a copy in" and the file exists; with a missing source it prints "No database yet". | A command that does not call the function. |
| `test_make_reset_copies_before_deleting` | Runs `make -n reset CONFIRM=yes` (a dry run: it only prints the commands) in a subprocess (skipped if `make` is not installed); the output contains `backup_db` before `rm -f db.sqlite3`, and the `read answer` question. | Someone removing the copy or the question from the `Makefile`. |

### Integration: `todos/tests/integration/test_search.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_hash_finds_the_tag` | A to-do tagged `work`: `?q=%23work` shows it; `?q=%23WORK` too. | Today's code (finds nothing). |
| `test_hash_still_searches_titles` | A to-do titled "Fix #work bug" with no tags is found by `#work`. | Searching titles without the `#`. |
| `test_hash_alone_does_not_match_every_tag` | Two to-dos, one tagged `home`, neither has `#` in title or notes: `?q=%23` and `?q=%23%20` show none. | An empty tag search that matches every tag. |
| `test_hash_search_shows_a_todo_once` | A to-do with tags `work` and `workshop`: `#work` shows it once. | A join instead of the sub-query. |
| `test_hash_search_stays_in_the_list` | bob's to-do tagged `work` is not shown on alice's list for `#work`. | Starting from `Todo.objects`. |

### Unit and integration: the repeat error

| File, test | What it checks | The break that fails it |
|---|---|---|
| `unit/test_models.py` (changed, line 53) | `Todo(repeat="weekly").clean()` raises `{"due_date": ["A repeating to-do needs a due date."]}`. | Leaving it on `repeat`. |
| `test_views.py` `RecurringTests.test_add_repeat_without_due_date_marks_the_date` | Add with repeat and no date: the date input has `aria-invalid="true"` and `aria-describedby="id_due_date_error"`; the error `<ul>` with id `id_due_date_error` holds the text; the repeat select has no `aria-invalid`. | The error under Repeat. |
| `test_views.py` `RecurringTests.test_edit_repeat_without_due_date_marks_the_date` | The same on the edit page (`_field.html`). | The same. |
| `test_views.py` `test_add_repeat_with_bad_date_shows_only_the_date_error` (kept) | A bad date: only "Enter a valid date." under the date. | `full_clean` not removing the second error from `due_date`. |

## Decided by the orchestrator for the person (2026-10-11, person away)

- `make reset` **asks, then copies, then deletes**; only `yes` goes on; `CONFIRM=yes` skips the
  question but not the copy.
- A `backup_db` command with SQLite's online backup, not `cp`. Backups in `backups/`, kept until
  the person deletes them.
- The backup name uses the app's time zone (the same as "today" in the app).
- `#work` finds tags without `#`; titles and notes are still searched with the `#`.
- The repeat error moves to Due date (one message, under the field to fix).

## Left for the person

- **Automatic daily backups** (launchd, like the reminders). Recommended: yes, later, if you use
  the app every day; it needs you to install a LaunchAgent yourself.
- **Copy backups off the Mac** (an external disk or a cloud folder). Only you can choose where.
- **Making a done to-do repeat via Edit, so it makes a copy.** Today a done to-do that gets a
  repeat rule makes no copy until it is undone and done again. Recommended: not now.

## Review

Verification by the planner (2026-10-11), against `main` (`6c7169b`) and `feature/nordic-letters`:

- Confirmed: `make reset` is `rm -f db.sqlite3` then `migrate`, with no question; no `backup`
  target; `.gitignore` has no `backups/`; README has no backup section.
- Confirmed by reading: `parse_tags` stores tags with `lstrip("#")`; `search()` (both on `main`
  and on `feature/nordic-letters`) compares the whole `q` with the tag names, so `#work` cannot
  match `work`.
- Confirmed: `Todo.clean()` puts `needs_due_date` on `repeat`; `TodoForm.full_clean` removes it
  when the date has its own error; `test_models.py` line 53 checks the `repeat` key.
- Found while checking: plain `sqlite3.connect(path)` makes an empty file when the path is
  missing, so the backup opens the source read-only. A test pins it.
- Found while checking: in tests `settings.DATABASES["default"]["NAME"]` is the in-memory test
  database, so the command takes `--source` and `--folder` for the tests instead of patching
  settings.
- Changed from the request: ask first, then copy (a "no" leaves no file). Same safety.

The plan review (2026-10-11) said APPROVE WITH CHANGES. What changed:

- The backup reserves the final name with `open(target, "xb")`, writes to a temporary name in the
  same folder, then renames; a failed copy leaves nothing. New test.
- Tests always pass `--source` and `--folder`, so nothing goes to the real `backups/`.
- The manual step warns: never `CONFIRM=yes` or `yes` outside the worktree.
- `.gitignore` uses `/backups/`; the README restore runs `make setup` (migrate) after an older
  copy.
- `#` search: `folded.lstrip("#").strip()`, and the tag sub-query is left out when empty.
- "Working next to": this plan may be built in parallel with the first two.
