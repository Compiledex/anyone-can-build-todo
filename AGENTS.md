# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language.
Explain in short, plain sentences, and define a technical word the first time you use it. When you
change code, say which file changed and why.

## What this is

The most basic to-do list, in Django. A person can add a to-do, edit it, mark it done (or undo
that), delete it, and clear all the done to-dos of a list at once. Each person has an account. A
person can have several lists (make, rename and delete a list); each to-do is in exactly one list.
The owner of a list can share it with other users by username. Those users are its *members*: they
can see the list and add, edit, mark done and delete its to-dos, clear its done to-dos, and they can
leave it. Only the owner can rename, delete or share the list, see its members, or remove a member.
Members do not see each other. A person sees their own lists plus the lists shared with them, and
nothing else. The data is kept in a SQLite database, the file `db.sqlite3`, which is not in git.

## What each file does

| File | Its one job |
|---|---|
| `config/settings.py` | Settings for the whole project. The secret key, debug and allowed hosts come from environment variables on a live server, with defaults for a laptop. |
| `config/urls.py` | Sends `/admin/` to Django's admin, `/accounts/` to `accounts/urls.py`, and everything else to `todos/urls.py`. |
| `accounts/` | The accounts app: sign up, log in, log out. It uses Django's own `User`, `LoginView`, `LogoutView` and `UserCreationForm`. It has no models. |
| `accounts/urls.py`, `accounts/views.py` | The three addresses (`login`, `logout`, `signup`), and the `signup` view. Sign-up also makes the person's first list, "Inbox". |
| `accounts/templates/registration/` | The login and sign-up pages. They extend `base.html`. |
| `accounts/tests/helpers.py` | Test helpers for every feature: `TEST_PASSWORD`, `make_user()`, and `LoggedInTestCase` (logged in as alice, with bob as the other user, alice's list `todo_list` ("Inbox"), bob's list `other_list`, and `assertOtherUserGets404`). `make_user()` makes no list. |
| `todos/models.py` | The `TodoList` table: `owner` (the user it belongs to), `name` (unique per person, ignoring case), `created_at`, `members` (the users it is shared with; `user.shared_lists` is the other side). `TodoList.objects.visible_to(user)` gives the lists the user owns plus the lists shared with them. The `Todo` table: `todo_list` (the list it is in), `title`, `done`, `created_at`, `due_date` (optional), `description` (optional notes, up to 2000 characters, `""` when empty), `priority` (Low, Medium or High, stored as 1, 2, 3; default Medium), `tags` (many-to-many to `Tag`), `is_overdue()` and `set_tags(names)`. A to-do's owner is `todo.todo_list.owner`. The `Tag` table: `owner`, `name` (lower case, no `#`, unique per owner). `set_tags` always uses the list owner's tags, never `request.user`'s, so a member of a shared list adds tags to the owner's tags. |
| `todos/tags.py` | `parse_tags(text)`: turns the typed "work, #Home" into clean tag names (lower case, no `#`, no repeats), and checks the limits (30 characters, 10 tags). No database. |
| `todos/urls.py` | The addresses: `/` (only sends the browser to the oldest own list, else the oldest list shared with the person, else "New list"), `/lists/new/`, `/lists/<pk>/` (a list page), `/lists/<pk>/add/`, `/lists/<pk>/rename/`, `/lists/<pk>/delete/`, `/lists/<pk>/share/`, `/lists/<pk>/members/<user_id>/remove/`, `/lists/<pk>/leave/`, `/lists/<pk>/clear-completed/` (deletes the done to-dos of that list), and `/<pk>/toggle/`, `/<pk>/delete/` and `/<pk>/edit/` for a to-do. |
| `todos/forms.py` | `TodoForm`, the Django form for a to-do (it checks the title, the optional due date, YYYY-MM-DD only, the optional notes, shown as "Notes" on the edit page, the priority; a missing or empty priority keeps the to-do's own priority, Medium for a new to-do; and a `tag_names` text field that `save()` turns into tags), `NoteField`, a text field that counts a line break as one character, as the browser does, `TodoListForm`, for a list's name (it refuses a name the person already has), and `ShareForm`, the username to share a list with (it gives the `User`, and refuses an unknown or switched-off user, the owner, and a member). |
| `todos/views.py` | One function per address. `render_list_page` is the one place that builds the list page (it loads all tags in one query with `prefetch_related`). A view that reads or changes a list or its to-dos finds the list with `TodoList.objects.visible_to(request.user)`, or the to-do with `get_visible_todo(request.user, pk)`; only rename, delete, share and remove-member use `owner=request.user`, so a member or a stranger gets 404 there. Share, remove-member and leave are `POST` only and show their result as a message. Changes are `POST` only; then the browser goes back to the list. An invalid add shows the list page again with the error. Clear completed (`list_clear_completed`, owner and members) deletes only `done=True` to-dos of the one list in the address, and its message counts only the `todos.Todo` rows from `QuerySet.delete()`. Edit shows its form on `GET` and saves on `POST`, then goes back to the to-do's list; an invalid edit shows the edit page again. |
| `todos/templates/base.html` | The shared page frame: the `<head>`, all the CSS (the colors are CSS variables, with dark values that follow the system's light or dark mode), the header ("Logged in as ..." and "Log out"), and the messages. |
| `todos/templates/todos/todo_list.html` | The list page, which extends `base.html`: the menu ("My lists", and "Shared with me" with each owner's name), the list's name with "Rename" and "Delete list" (owner) or "Shared by ..." (member), the member list with Remove buttons and the share form (owner only), "Leave this list" (member only), the errors, the add form, the to-dos, and below them "Clear completed (N)" (a `<details>` box that asks once more; hidden when nothing is done; owner and members see it). |
| `todos/templates/todos/list_form.html` | The "New list" and "Rename list" page: the name field and its errors. |
| `todos/templates/todos/list_confirm_delete.html` | "Delete this list and its N to-dos?", with the button that really deletes. |
| `todos/templates/todos/_todo_item.html` | One row of the list (one `<li>`). |
| `todos/templates/todos/todo_edit.html` | The edit page, which extends `base.html`: every field of `TodoForm`, Save and Cancel. |
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
