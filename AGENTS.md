# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language.
Explain in short, plain sentences, and define a technical word the first time you use it. When you
change code, say which file changed and why.

## What this is

The most basic to-do list, in Django. A person can add a to-do, edit it, mark it done (or undo
that), delete it, and clear all the done to-dos of a list at once. A to-do can repeat (daily, weekly
or monthly): marking it done makes its next copy, and "Undo" removes that copy again. In the
"Manual" order, the to-dos of a list can be put in any order by drag and drop or the Move buttons;
that order belongs to the list, so everyone who sees it sees the same order. Each person
has an account. A person can have several lists (make, rename and delete a list); each to-do is in
exactly one list. The owner of a list can share it with other users by username. Those users are its
*members*: they can see the list and add, edit, mark done and delete its to-dos, clear its done
to-dos, and they can leave it. Only the owner can rename, delete or share the list, see its members,
or remove a member. Members do not see each other. A person sees their own lists plus the lists
shared with them, and nothing else. Once a day, on the person's Mac, launchd (the Mac's scheduler)
can run `send_reminders`, which shows one macOS notification with the person's to-dos due today.
The data is kept in a SQLite database, the file `db.sqlite3`,
which is not in git.

## What each file does

| File | Its one job |
|---|---|
| `config/settings.py` | Settings for the whole project. The secret key, debug and allowed hosts come from environment variables on a live server, with defaults for a laptop. SQLite uses `transaction_mode: "IMMEDIATE"`, so two requests that write at the same time wait for each other instead of failing. |
| `config/urls.py` | Sends `/admin/` to Django's admin, `/accounts/` to `accounts/urls.py`, and everything else to `todos/urls.py`. |
| `accounts/` | The accounts app: sign up, log in, log out. It uses Django's own `User`, `LoginView`, `LogoutView` and `UserCreationForm`. It has no models. |
| `accounts/urls.py`, `accounts/views.py` | The three addresses (`login`, `logout`, `signup`), and the `signup` view. Sign-up also makes the person's first list, "Inbox". |
| `accounts/templates/registration/` | The login and sign-up pages. They extend `base.html`. |
| `accounts/tests/helpers.py` | Test helpers for every feature: `TEST_PASSWORD`, `make_user()`, and `LoggedInTestCase` (logged in as alice, with bob as the other user, alice's list `todo_list` ("Inbox"), bob's list `other_list`, and `assertOtherUserGets404`). `make_user()` makes no list. |
| `todos/models.py` | The `TodoList` table: `owner` (the user it belongs to), `name` (unique per person, ignoring case), `created_at`, `members` (the users it is shared with; `user.shared_lists` is the other side). `TodoList.objects.visible_to(user)` gives the lists the user owns plus the lists shared with them. The `Todo` table: `todo_list` (the list it is in), `title`, `done`, `created_at`, `due_date` (optional), `description` (optional notes, up to 2000 characters, `""` when empty), `priority` (Low, Medium or High, stored as 1, 2, 3; default Medium), `tags` (many-to-many to `Tag`), `repeat` (`Todo.Repeat`: Never `""`, `daily`, `weekly`, `monthly`), `position` (the place in the list's manual order, smaller first; not unique, ties go by `created_at` then `pk`; `save()` gives a **new** to-do the biggest `position` in its list plus 1, so a new to-do and a recurring copy go last; gaps after a delete do not matter), `reminded_on` (the day the to-do was last shown in a Mac notification, or empty; `editable=False`, so no form or admin form sets it; not copied by `make_next_copy`, so a copy starts never reminded), `repeated_from` (on a copy: the to-do it was copied from; one-to-one, so at most one copy each; the other side is `next_copy`, read it with `get_next_copy()`), `is_overdue()`, `set_tags(names)`, `subtask_progress()` (number of done steps, number of steps; it counts the prefetched steps in Python, so it makes no new query), `clean()` (a repeating to-do needs a due date; only a form runs it, never `save()`), and `make_next_copy(today)` (the one place that makes a copy: same list, title, notes, priority, repeat and tags, the steps (none done), the next due date; `None` when there is nothing to copy or a copy exists). A to-do's owner is `todo.todo_list.owner`. The `Tag` table: `owner`, `name` (lower case, no `#`, unique per owner). `set_tags` always uses the list owner's tags, never `request.user`'s, so a member of a shared list adds tags to the owner's tags. The `Subtask` table (a step inside a to-do): `todo` (`todo.subtasks`; deleted with its to-do), `title`, `done`, `created_at`, oldest first. A step has no owner and no list: whoever may see its to-do may change its steps. Marking all steps done does not mark the to-do done, and the other way round. |
| `todos/tags.py` | `parse_tags(text)`: turns the typed "work, #Home" into clean tag names (lower case, no `#`, no repeats), and checks the limits (30 characters, 10 tags). No database. |
| `todos/recurrence.py` | `next_due_date(due_date, repeat, today)`: the first date after the due date, in steps of a day, a week or a month, that is after today (`None` after 31 Dec 9999). `add_months` keeps the day of the month, or the last day of a shorter month. No loop and no Django, so a very old date is fast. |
| `todos/urls.py` | The addresses: `/` (only sends the browser to the oldest own list, else the oldest list shared with the person, else "New list"), `/lists/new/`, `/lists/<pk>/` (a list page), `/lists/<pk>/add/`, `/lists/<pk>/rename/`, `/lists/<pk>/delete/`, `/lists/<pk>/share/`, `/lists/<pk>/members/<user_id>/remove/`, `/lists/<pk>/leave/`, `/lists/<pk>/clear-completed/` (deletes the done to-dos of that list), and `/<pk>/toggle/`, `/<pk>/delete/` and `/<pk>/edit/` for a to-do, `/lists/<pk>/reorder/` (`todo_reorder`: the new order from drag and drop), `/<pk>/move/` (`todo_move`: Move up or Move down), `/<todo_pk>/subtasks/add/` (add a step to that to-do), and `/subtasks/<pk>/toggle/` and `/subtasks/<pk>/delete/` for a step (only the step's number, never a to-do number). |
| `todos/forms.py` | `TodoForm`, the Django form for a to-do (it checks the title, the optional due date, YYYY-MM-DD only, the optional notes, shown as "Notes" on the edit page, the priority; a missing or empty priority keeps the to-do's own priority, Medium for a new to-do; the `repeat` select (when the typed due date is not valid, only the date error shows, not also "A repeating to-do needs a due date"); and a `tag_names` text field that `save()` turns into tags), `NoteField`, a text field that counts a line break as one character, as the browser does, `TodoListForm`, for a list's name (it refuses a name the person already has), `SubtaskForm`, a step's title (the view sets the to-do, never the form), `ShareForm`, the username to share a list with (it gives the `User`, and refuses an unknown or switched-off user, the owner, and a member), and `TodoQueryForm`, which reads the list page's address (`request.GET`): `q`, the search text (spaces at the ends removed, at most 200 characters), `status` (`open` or `done`; empty or any other value means all, with no error), and `sort` (a key of `SORT_OPTIONS`: `created`, `due`, `priority`, `title` or `manual`; empty or any other value means the default, with no error). |
| `todos/queries.py` | Builds the to-dos shown on a list page from the address: search, filter and sort. `SORT_OPTIONS` is the one allow-list of orders (key: label in the menu, and the order): `created` (oldest first, the default, `DEFAULT_SORT`), `due` (soonest first, no date last), `priority` (High first) `title` (A to Z, ignoring case for A-Z only on SQLite) and `manual` (`position`); every order ends with `created_at`, `pk`, so equal values keep a fixed order. `chosen_sort(form)` gives the chosen key, or the default. `can_reorder(form)` is `True` only when the form is valid, the sort is `manual`, and there is no `q` and no `status` (then every to-do is shown, so drag and Move are allowed). `apply_list_query` always ends with `order_by`, so the page never depends on `Meta.ordering`. `apply_list_query(todos, form)` applies each valid field of `TodoQueryForm` and ignores a bad one. `search(todos, q)` keeps the to-dos whose title, notes or a tag name contain `q`, ignoring case (A-Z only on SQLite); tags are matched with a sub-query, so a to-do is shown once. `filter_by_status(todos, status)` keeps the not done (`open`) or done (`done`) to-dos; anything else shows all. `list_query(data, **changes)` builds the part after `?` for a list link from the form's cleaned values, with some changed (empty values left out, so "All" has no `status`). Every function starts from the `todos` it is given and only makes it smaller; never `Todo.objects` here. |
| `todos/ordering.py` | The manual order. `parse_ids(values)` turns the posted strings into whole numbers, and raises `ValueError` for text, `""`, `-1` or a repeat. `save_order(todo_list, ids)` gives the list's to-dos `position` 1, 2, 3, ... in the order of `ids` with one `bulk_update`, in one transaction; `ids` must be exactly the list's to-dos (every one, once, nothing else), or it raises `ValueError` and saves nothing. Drag and Move both use it. |
| `todos/views.py` | One function per address. `render_list_page` is the one place that builds the list page (it loads all tags and all steps with `prefetch_related`, one query each, then applies the search from `?q=` and the filter from `?status=` and the order from `?sort=` with `TodoQueryForm` and `apply_list_query`; all are `GET` only and change nothing; it also gives the filter links, `current_sort`, `show_all_query` and `back_url`, the list address with the same query). A view that reads or changes a list or its to-dos finds the list with `TodoList.objects.visible_to(request.user)`, or the to-do with `get_visible_todo(request.user, pk)`, or a step with `get_visible_subtask(request.user, pk)` (through its to-do); only rename, delete, share and remove-member use `owner=request.user`, so a member or a stranger gets 404 there. Share, remove-member and leave are `POST` only and show their result as a message. Changes are `POST` only; then the browser goes back to the list. An invalid add shows the list page again with the error. Clear completed (`list_clear_completed`, owner and members) deletes only `done=True` to-dos of the one list in the address, and its message counts only the `todos.Todo` rows from `QuerySet.delete()`. The step views (`subtask_add`, `subtask_toggle`, `subtask_delete`; owner and members) go back with `back_to_steps(todo)`: the list page with `?open=<to-do id>#todo-<to-do id>`, built only from database numbers. A bad step title saves nothing and shows the message "A step needs a title of 1 to 200 characters.". Edit shows its form on `GET` and saves on `POST`, then goes back to the to-do's list; an invalid edit shows the edit page again. Toggle and delete go back with `redirect_back(request, default)`: to the `POST` value `next` only when it starts with `/` and `url_has_allowed_host_and_scheme` accepts it (so never another site, `//...`, a backslash or a bare word), else to the list. Add, edit, clear completed and the step views still go to the plain list. Toggle runs in one `transaction.atomic()` and reads the to-do inside it: Done calls `make_next_copy(timezone.localdate())`; Undo deletes the copy if it is not done and still in the same list, with a message. `todo_reorder` (drag and drop; owner and members) reads `id=7&id=3&id=5` with `parse_ids` and saves it with `save_order`: `204` when it worked, `400` when the ids are not exactly this list's to-dos. `todo_move` (owner and members) swaps the to-do with its neighbour in the manual order (`direction` `up` or `down`, else `400`; no neighbour: nothing changes) and goes back to `?sort=manual#todo-<pk>`. `render_list_page` gives the template `can_reorder`. |
| `todos/templates/base.html` | The shared page frame: the `<head>`, all the CSS (the colors are CSS variables, with dark values that follow the system's light or dark mode), the header ("Logged in as ..." and "Log out"), and the messages. The drag handle, the row being dragged (`--drag-bg`) and the Move buttons are styled here too. |
| `todos/templates/todos/todo_list.html` | The list page, which extends `base.html`: the menu ("My lists", and "Shared with me" with each owner's name), the list's name with "Rename" and "Delete list" (owner) or "Shared by ..." (member), the member list with Remove buttons and the share form (owner only), "Leave this list" (member only), the errors, the add form, the search form (`GET`; hidden `status` and `sort` keep the filter and the order; "Show all" while searching or filtering, which keeps the order), the "Sort by" form (`GET`, its own "Sort" button; hidden `q` and `status` keep the search and the filter), the filter links "All", "Not done" and "Done" (the chosen one has `aria-current="page"`; each keeps the search), "No to-dos match “...”" (or "No to-dos match." with only a filter) when nothing matches, the to-dos, and below them "Clear completed (N)" (N and the delete are always the whole list, whatever the search or filter shows; a `<details>` box that asks once more; hidden when nothing is done; owner and members see it). When `can_reorder`: the `<ul>` has `data-reorder-url`, a hidden form `reorder-csrf` with the CSRF token, and `todos/reorder.js` is loaded; in `?sort=manual` with a search or a filter, the line "Clear the filter to change the order." instead. |
| `todos/templates/todos/list_form.html` | The "New list" and "Rename list" page: the name field and its errors. |
| `todos/templates/todos/list_confirm_delete.html` | "Delete this list and its N to-dos?", with the button that really deletes. |
| `todos/templates/todos/_todo_item.html` | One row of the list (one `<li id="todo-<pk>">`), with a `<details class="steps">` under it: "Steps: N of M done" (or "Add steps"), the steps with Done/Undo and Delete (their `aria-label`s name the step), and the "Add step" form. The Done/Undo and Delete forms of the to-do have a hidden `next` with `back_url`, so the person comes back to the same search and filter. Next to the due date of a repeating to-do: "Repeats daily", "Repeats every Monday" or "Repeats monthly". The details is open when `?open=` is this to-do's id; the value is only compared, never printed. When `can_reorder`: `data-id` on the `<li>`, the drag handle `⠿` (only it is draggable, so the text and the "add step" box still work), and one Move form with "↑" (not on the first row) and "↓" (not on the last row); their `aria-label` and `title` are "Move up: <title>" and "Move down: <title>". |
| `todos/static/todos/reorder.js` | Drag and drop, plain JavaScript with the browser's own (HTML5) drag and drop, no library. Runs only when the list has `data-reorder-url`; only the direct rows move, never the steps; Escape or a drop outside the list puts the row back; on `dragend` it sends the new order once with `fetch`, and reloads the page when the answer is not `204` or the network fails. |
| `todos/templates/todos/todo_edit.html` | The edit page, which extends `base.html`: every field of `TodoForm`, Save and Cancel. |
| `todos/reminders.py` | Mac notifications for to-dos due today. `due_today(user, today)`: the not-done to-dos in the user's **own** lists (not the lists shared with them) due that day, whose `reminded_on` is not that day, in list order. `notification_text(todos)`: `(title, text)`; the title holds only the number ("To-do list: 3 to-dos due today"), the text at most 3 titles, one line each (spaces made one space, then invisible characters removed, cut at 60 characters with `…`), then "and N more". `show_notification(title, text)` runs `/usr/bin/osascript` with a fixed AppleScript, `--`, then the title and the text as `argv`; a list (no shell), `check=True`, `timeout=30`; any failure becomes `NotificationError`, whose text is only the error's name and exit code, never `stderr`. `send_reminders(user, today)` shows one notification, then sets `reminded_on` with one `update()` (only after `osascript` worked; no transaction), and returns how many. |
| `todos/management/commands/send_reminders.py` | `python manage.py send_reminders --user <username>` (`--user` is required): an unknown or switched-off user gives `No active user named "...".`; a failed `osascript` (or no `osascript`, as on Linux) gives `Could not show the notification: ...`. It prints one line, never a to-do title. |
| `deploy/macos/com.anyone-can-build-todo.reminders.plist` | The launchd template (a LaunchAgent) that runs `send_reminders` at 08:00, with the blanks `__REPO_PATH__`, `__HOME__` and `__USERNAME__`. The person fills it in and installs it (see `README.md`); the AI never installs it, never runs `launchctl`, and never writes to `~/Library`. |
| `todos/tests/helpers.py` | `FakeOsascriptMixin`: replaces `todos.reminders.subprocess.run` with a fake (`self.run`) in `setUp`, so a test never shows a real notification. Every reminders test uses it. |
| `todos/tests/unit/` | Unit tests: one method on its own, no requests, no database. |
| `todos/tests/integration/` | Integration tests: Django's test client, from the address to the database. |
| `todos/tests/cuj/` | CUJ tests (critical user journeys): a real Chromium browser, driven by Playwright. |
| `config/test_runner.py` | Finds each test's layer from its folder, checks the layer rules, and prints one line per layer after a run. |
| `config/tests/unit/` | The tests for the test runner. |
| `todos/migrations/` | Made by Django from `models.py`. Never edit these by hand. One exception: a data migration (one that changes rows, like `0003_give_old_todos_an_owner.py` and `0006_default_lists.py`) is meant to be written. |
| `pyproject.toml`, `uv.lock` | The packages this project uses, and their exact versions. |
| `.pre-commit-config.yaml` | The checks that run on every `git commit`. |
| `Makefile` | Short commands. `make help` lists them. |

## Commands

This project uses **uv** to install Python and the packages. Run every Python command through
`uv run`, so it uses this project's packages:

- `make setup` — install everything, create the database, turn on the commit checks
- `make run` — start the server at <http://127.0.0.1:8000>
- `make test` — run every test, then show how many passed in each layer
- `make unit` / `make integration` / `make cuj` — run only one layer
- `make lint` / `make format` — Ruff: find mistakes, and rewrite code in the standard style
- `make check` — every commit check on every file, the migration check, then the tests

Add a package with `uv add <name>`, never with `pip install`. After changing `models.py`, run
`uv run python manage.py makemigrations` and then `uv run python manage.py migrate`.

## Rules

- **Run `make check` before every commit.** The commit checks also run by themselves. If one fails
  after fixing a file, look at the change, `git add` the file, and commit again.
- **Never put a secret in the code.** Passwords, keys and tokens go in environment variables.
- **Use what Django already has** — forms, the admin, `get_object_or_404`, the test client — before
  writing your own.
- **Change data only with `POST`.** A `GET` request only reads.
- **Add or change a test with every change in behavior**, and show the person the test failing
  before the fix and passing after.
- **Put each test in the folder for its layer**: `tests/unit/`, `tests/integration/` or
  `tests/cuj/`. The folder is the layer. Test each rule once, in the lowest layer where a person
  would notice it. A unit test must be a `SimpleTestCase` (no database). A CUJ test must extend
  `BrowserTestCase` from `todos/tests/cuj/browser.py`. The test runner stops if a test breaks
  these rules.
- **Never pass text from a request to `order_by`.** Add an entry to `SORT_OPTIONS` in
  `todos/queries.py` instead; the `sort` field of `TodoQueryForm` only accepts its keys.
- **Never build AppleScript from user text.** The script is fixed in `todos/reminders.py`; pass
  the text as `argv`, and always put `--` before those arguments. Never `shell=True`. A test never
  starts the real `osascript`: use `FakeOsascriptMixin` from `todos/tests/helpers.py`.
- **Every page needs a login, by default.** Django's `LoginRequiredMiddleware` (code that runs
  before every view) sends a visitor who is not logged in to the login page. Only mark a view
  `@login_not_required` when a stranger must see it, add its name to
  `test_only_login_and_signup_are_open`, and say why in the pull request.
- **Only my data, plus what is shared with me.** A person sees and changes only their own lists
  and the lists shared with them:
  1. A view that reads or changes a list or its to-dos finds the list with
     `get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)`, or the to-do with
     `get_visible_todo(request.user, pk)`. The to-dos of a list are `the_list.todos.all()`. Never
     `Todo.objects.all()` in a view, and never filter to-dos by owner or by
     `Q(todo_list__owner=...) | Q(todo_list__members=...)` (that gives double rows).
  2. Only rename, delete, share and remove-member use
     `get_object_or_404(TodoList, pk=pk, owner=request.user)`: they are for the owner alone.
     Someone else's thing gives 404, like a thing that does not exist (not 403, which would tell
     that it exists). A member gets the same 404 as a stranger.
  3. Create: set the owner or the list in the view (`form.save(commit=False)`, then
     `todo.todo_list = the_list`), never from the form.
  4. A new model that belongs to a to-do is reached through a to-do the user can see
     (`get_visible_todo`), or gets its own `owner` field and follows rules 1 to 3.
  5. Every new view gets a test that another user gets 404 (`assertOtherUserGets404` from
     `accounts/tests/helpers.py`), and that the data did not change.

  One exception: `todos/reminders.py` filters to-dos by `todo_list__owner` on purpose:
  `reminded_on` is one date per to-do, so only the owner is reminded. It is not a view. Views
  never do this.
