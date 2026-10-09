# Plan: several lists

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (test pyramid, `TodoForm` in `todos/forms.py`, the partial
`todos/templates/todos/_todo_item.html`, CSS variables) and wave 1, #17 accounts (log in, sign up,
each to-do has an owner, every view needs a logged-in user).

## Goal

A person can have more than one list, for example "Work", "Home" and "Shopping". They can make a
new list, rename a list, and delete a list. Each to-do belongs to exactly one list. A person sees
and changes only their own lists.

## What this plan assumes about accounts (#17)

This plan is written before the accounts code exists. It assumes that #17 gives us:

- `Todo.owner`: a `ForeignKey` to `settings.AUTH_USER_MODEL`, not null, `related_name="todos"`.
  Made by the migrations `0002`–`0004` (the last one is `0004_alter_todo_owner`).
- `LoginRequiredMiddleware` is on, so **every view needs a login by default**. No view in this
  plan needs a decorator. (A middleware is code that runs before every view.)
- A sign-up view `signup` in `accounts/views.py` that creates the user, logs them in, and does
  `redirect("todo_list")`. `config/settings.py` has `LOGIN_REDIRECT_URL = "todo_list"`.
- Views find a to-do with `get_object_or_404(Todo, pk=pk, owner=request.user)`, so another
  person's to-do gives **404** (not found), not 403 (forbidden). 404 does not reveal that the
  to-do exists.
- Test helpers in `accounts/tests/helpers.py`: `make_user`, and `LoggedInTestCase` with
  `self.user` (alice), `self.other_user` (bob) and `assertOtherUserGets404`.
- `todos/tests/integration/test_migrations.py` with a migration test.
- In `todos/tests/integration/test_views.py`: `test_only_login_and_signup_are_open`, which walks
  every address of the site and checks that only `login`, `logout` and `signup` are marked
  `@login_not_required`, and `test_anonymous_cannot_add_toggle_or_delete`.
- `todos/admin.py` shows `owner` in `list_display` and `list_filter`.

If #17 is built differently, adjust the names in this plan before starting. The decisions stay
the same.

## Decisions

### The model

A new model (a model is one database table) `TodoList` in `todos/models.py`:

```python
from django.db.models.functions import Lower


class TodoList(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todo_lists"
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "owner", name="unique_list_name_per_owner"
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("list_detail", args=[self.pk])
```

And `Todo` changes:

```python
class Todo(models.Model):
    todo_list = models.ForeignKey(TodoList, on_delete=models.CASCADE, related_name="todos")
    title = ...  # as today
    # `owner` is removed
```

- **The field is called `todo_list`, not `list`.** `list` is a built-in Python name. Using it as
  a field name works, but it is confusing to read.
- **The owner moves from the to-do to the list.** A to-do's owner is now `todo.todo_list.owner`.
  We remove `Todo.owner`, so the two can never disagree (for example, a to-do owned by Ana inside
  a list owned by Ben). This also prepares sharing (#18): sharing gives a person access to a
  *list*, and every to-do in it follows.
- **List names are unique per person, ignoring upper and lower case.** One person cannot have
  "Work" and "work". Two different people can each have a list called "Work". The form checks
  this and shows a friendly error. The database constraint (a rule the database itself enforces)
  is a safety net behind the form.
- **"Ignoring case" works only for the letters A–Z on SQLite.** SQLite's `lower()` and its
  case-insensitive compare do not change Æ, Ø, Å and other non-English letters. So "Øl" and "øl"
  can both exist. We accept this: the form and the database use the same compare (see Forms), so
  the person never sees an error page. (Checked: SQLite 3.53 blocks "work" next to "Work", and
  allows "øl" next to "ØL".)
- **Lists are shown oldest first**, like to-dos today. `"pk"` is a tie-breaker, so two lists made
  in the same moment always come in the same order. Changing the order of lists is not part of
  this task.

### The addresses (URLs)

| Address | Method | What it does |
|---|---|---|
| `/` | GET | Sends the browser to the person's oldest list. If they have no list, sends them to `/lists/new/`. |
| `/lists/new/` | GET, POST | GET shows a small form for the name. POST creates the list and goes to it. |
| `/lists/<pk>/` | GET | The list page: the list's to-dos, the add form, and links to the person's other lists. |
| `/lists/<pk>/add/` | POST | Adds a to-do to this list. (Today's `/add/` is removed.) |
| `/lists/<pk>/rename/` | GET, POST | GET shows the name form, filled in. POST saves the new name and goes back to the list. |
| `/lists/<pk>/delete/` | GET, POST | GET shows "Delete this list and its N to-dos?". POST deletes it and goes to `/`. |
| `/<pk>/toggle/` | POST | As today. Now goes back to the to-do's own list. |
| `/<pk>/delete/` | POST | As today. Now goes back to the to-do's own list. |

- **`/` is only a redirect** (it sends the browser on to another address). It never shows a page
  itself. So the address bar always tells which list is open.
- **The to-do addresses do not change.** A to-do's `pk` (its number in the database) is already
  unique, so it does not need the list's number in its address. This keeps the change small, and
  it does not break #4 (edit), which adds `/<pk>/edit/` at the same time.
- **New and rename have their own small page** (GET shows the form, POST saves). This is the
  standard Django pattern: when the name is invalid, the same page is shown again with the error
  and the typed name. Only GET pages are read-only; every change is a POST.
- **Deleting a list has a confirm page.** Deleting a list also deletes all its to-dos, so we ask
  first and say how many to-dos will go. The "Delete list" link on the list page goes to this
  page; the real delete is the POST button on it.
- **URL names: keep the old ones, add new ones.**
  - `/` keeps the name **`todo_list`** (view `todo_list`). We do **not** rename it. Today
    `LOGIN_REDIRECT_URL`, the sign-up view, #4 edit and their tests all use `"todo_list"`. A
    renamed URL would make each of them crash with `NoReverseMatch` (Django cannot find an address
    with that name). Kept, they all still work: `/` sends the browser on to a list.
  - `/lists/<pk>/add/` keeps the name **`todo_add`** (view `todo_add`), now with a `pk`. #18
    sharing already uses this name.
  - New names: `list_detail` (shared name), `list_create`, `list_rename`, `list_delete`.
    `list_create` (not `list_new`) is the name #18 sharing uses.
  - Careful: `"todo_list"` (the URL name of `/`) and `todo.todo_list` (the field) are different
    things. To go back to a to-do's own list, write `redirect(todo.todo_list)`.

### A default list for every person

- **When a person signs up, they get one list called "Inbox".** The sign-up view from #17 creates
  it, right after it creates the user. So a new person lands on a list they can use straight
  away, just like the app works today.
- **We do not create a list during a GET.** If a person has no lists (for example, they deleted
  all of them, or the user was made with `createsuperuser` or in the admin), `/` sends them to
  `/lists/new/`. A GET request only reads; it never creates data.
- **No signal.** We do not create the list automatically for every new `User` (a Django
  "signal"). It would be hidden magic, and every test user would get a list it did not ask for.
  So `make_user` in the tests makes **no** list; the test helper makes one (see Tests).

### What the migration does with existing to-dos

A migration is a file that changes the database tables to match `models.py`. Here it must also
move data, so there are three migration files, in this order:

1. **Schema, part 1** (made by `makemigrations`): create the `TodoList` table; add
   `Todo.todo_list`, allowed to be empty for now; make `Todo.owner` allowed to be empty.
2. **Data** (made by `makemigrations --empty`, then filled in by hand; see the note below):
   - For **every existing user**, create one list called "Inbox". Every user, also users with no
     to-dos, so that every person starts the same way as a new person.
   - Put each existing to-do in the "Inbox" list of its owner.
   - The way back (`reverse`): copy each to-do's list owner back into `Todo.owner`.
3. **Schema, part 2** (made by `makemigrations`): make `Todo.todo_list` required, and remove
   `Todo.owner`.

Why three files: a migration that both changes data and changes a table in one step can fail on
some databases (PostgreSQL). SQLite does not mind, but a live server may use another database
later. Why `Todo.owner` is made "allowed to be empty" before it is removed: going backwards,
Django adds the `owner` column back *before* the data step fills it. A required column cannot be
added to a table that has rows, so it must be allowed to be empty at that moment.

Checked, case by case:

- **Empty database** (a new laptop, the tests): no users, so the data step does nothing.
- **Database with users and to-dos**: every user gets a "Inbox" list; every to-do goes into its
  owner's list. Each user has one list, so there is no name clash.
- **Backwards** (`migrate todos 0004`): file 3 adds `owner` back (empty allowed) and makes
  `todo_list` optional; file 2 copies `todo.todo_list.owner` into `todo.owner`; file 1 makes
  `owner` required again (every row has one now) and drops `todo_list` and the `TodoList` table.
  The to-dos are kept; **the lists and their names are lost**. That is expected when going back.
- **Forward again** after going back: works; every user gets a new "Inbox" list.

(The second review built these three files with `makemigrations` on top of #17's `0002`–`0004`,
Django 5.2.17 and SQLite 3.53, and ran all four cases. Django numbered them `0005`–`0007`.)

**Fixed names.** Make the files with fixed names, so the orchestrator can find them:
`makemigrations todos --name todolist` (file 1), `--empty --name default_lists` (file 2),
`--name todo_list_required` (file 3).

**Note for the orchestrator (merge queue).** These three files are a set. Do **not** delete and
remake files 1 and 3 with `makemigrations`: one run would make a single file with no room for the
data step in the middle. Treat all three like a hand-written migration: only fix the numbers and
`dependencies`. Lists is merged first in wave 2, and wave 1 #20 has no migration, so they should
already be `0005`–`0007`, right after `0004_alter_todo_owner`.

**Note on "never edit migrations by hand".** `AGENTS.md` says migrations are made by Django. A
data migration is the one standard exception: Django makes the empty file, and we write the
function that moves the data. Inside it, use `apps.get_model("todos", "TodoList")`, never
`from todos.models import ...`, because the real model may change later. Step 2 is the only file
we write in; files 1 and 3 are not touched. Keep the two functions at module level (outside the
`Migration` class), as the merge queue asks:

```python
from django.conf import settings
from django.db import migrations


def give_each_user_a_list(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    TodoList = apps.get_model("todos", "TodoList")
    Todo = apps.get_model("todos", "Todo")
    for user in User.objects.all():
        todo_list = TodoList.objects.create(owner=user, name="Inbox")
        Todo.objects.filter(owner=user).update(todo_list=todo_list)


def copy_owner_back(apps, schema_editor):
    Todo = apps.get_model("todos", "Todo")
    for todo in Todo.objects.select_related("todo_list"):
        todo.owner_id = todo.todo_list.owner_id
        todo.save(update_fields=["owner"])
```

and `migrations.RunPython(give_each_user_a_list, copy_owner_back)`. Use
`settings.AUTH_USER_MODEL`, not `"auth", "User"`, the same rule as #17's data migration. No extra
`dependencies` line is needed: file 1 already depends on the user table.

### What deleting a list does to its to-dos

- **Its to-dos are deleted too** (`on_delete=models.CASCADE`). Moving them to another list would
  need a choice of list on the confirm page; that is more than this task needs.
- The confirm page says how many to-dos will be deleted, so it is not a surprise.
- **The last list can be deleted.** Then `/` goes to `/lists/new/`. This avoids a special rule.
- **After deleting a to-do,** remember its list first (`the_list = todo.todo_list`), then
  `todo.delete()`, then `redirect(the_list)`.
- When a user is deleted (for example in the admin), their lists and to-dos are deleted too.

### Who can see what

Every view finds a list or a to-do in one of two fixed ways, and nothing else:

```python
# a list (show, add, rename, delete):
the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)

# a to-do (toggle, delete):
todo = get_object_or_404(Todo, pk=pk, todo_list__owner=request.user)
```

- Another person's list or to-do always gives **404**.
- The URL parameter is always called `pk` (`/lists/<int:pk>/`), like the to-do addresses.
- **The list for a new to-do comes only from the address**, never from the form. `todo_add`
  finds the list with the line above, so Ben cannot add to Ana's list by changing the number in
  the address (he gets 404). `TodoForm` has no `todo_list` field, so a `todo_list` value sent in
  the form is ignored.
- **The menu of lists** is `request.user.todo_lists.all()`, never `TodoList.objects.all()`.

This is how we "do not make sharing hard". Sharing (#18) will add
`TodoList.objects.visible_to(user)` (lists I own, plus lists shared with me), and change the
show, add, toggle and to-do delete views to
`get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)` and
`get_object_or_404(Todo, pk=pk, todo_list__in=TodoList.objects.visible_to(request.user))`.
Rename and list delete can stay owner-only: a person who was given access to a list should not
rename or delete it (#18 decides this). Because every view uses exactly the two lines above, #18
can find and change them all with one search. We do not add `visible_to` now: with no sharing it
would only be another name for "owned by me".

### Forms

- `TodoListForm` in `todos/forms.py`: a `ModelForm` with `fields = ["name"]`. No extra
  argument: the view always gives it an `instance` that already has the owner.
  - New list: `TodoListForm(request.POST, instance=TodoList(owner=request.user))`.
  - Rename: `TodoListForm(request.POST, instance=the_list)`.
  - `clean_name` looks for another list of `self.instance.owner` with
    `name__iexact=name`, leaving out `self.instance.pk`. If one exists, it raises a
    `ValidationError` ("You already have a list called …"). When renaming, the list itself is
    left out, so saving the same name (or "work" → "Work") works.
  - Why `clean_name` is needed: Django's own constraint check skips our constraint, because
    `owner` is not a field in the form. Without `clean_name`, a duplicate name reaches the
    database, which raises `IntegrityError`, and the person sees a **500 error page**.
  - `iexact` uses the same compare as the database on SQLite (A–Z only), so the two never
    disagree.
  - Two requests in the very same moment could both pass the form; the second then gets a 500
    from the database constraint. This is very rare for one person, and the data stays correct.
    We accept it.
- A name with only spaces is rejected (Django removes spaces at the start and end, then the field
  is empty).
- `TodoForm` (from wave 0) does not change. `todo_add` sets the list before saving:
  `todo = form.save(commit=False); todo.todo_list = the_list; todo.save()`.

### One function draws the list page

Two views show the list page: `list_detail` (with an empty add form) and `todo_add` when the form
is not valid (wave 0 shows the page again with the error and the typed text; #6 due date relies on
this). Both call one small function in `todos/views.py`, so the page is built in one place:

```python
def render_list_page(request, the_list, form):
    return render(request, "todos/todo_list.html", {
        "the_list": the_list,
        "todos": the_list.todos.all(),
        "my_lists": request.user.todo_lists.all(),
        "form": form,
    })
```

- `list_detail`: `return render_list_page(request, the_list, TodoForm())`.
- `todo_add`, form not valid: `return render_list_page(request, the_list, form)` (status 200, no
  redirect). Without this function, it is easy to copy wave 0's old code and show the wrong
  to-dos, or a page with no menu.
- The to-dos always come from `the_list.todos.all()`, never from a filter on the user.
- #18 sharing adds its parts of the page (owner or member, the share form) here, once.

**Which methods each view accepts** (a method is `GET` or `POST`): `todo_list` and `list_detail`
use `@require_GET`; `list_create`, `list_rename` and `list_delete` use
`@require_http_methods(["GET", "POST"])`; `todo_add`, toggle and delete keep `@require_POST`.
Any other method gives 405. These decorators come with Django.

## Not part of this task

- **Sharing a list with another person** (#18, wave 3). This plan only prepares for it (see "Who
  can see what").
- **Moving a to-do to another list.** This could be added to the edit page (#4) later. Until
  then, it can be done in the Django admin.
- Changing the order of lists, list colors or icons, archiving a list.
- Remembering which list was open last. `/` always opens the oldest list.
- Counting open to-dos per list in the list menu.
- A page that shows all lists (an "index"). The menu on the list page is enough.
- Deleting a list without deleting its to-dos (moving them first).

## Working next to other wave 2 features

#4 (edit) and #6 (due date) are built in the same wave and touch the same files
(`views.py`, `urls.py`, `todo_list.html`, the integration tests). To keep merges simple:

- The orchestrator merges **this feature first** in wave 2, then #4 edit, then #6 due date.
- Because `todo_list` and `todo_add` keep their names, #4 edit still works after this merge. When
  #4 is rebased onto it, #4 must change:
  - `get_object_or_404(Todo, pk=pk, owner=request.user)` → `todo_list__owner=request.user`
    (`Todo.owner` no longer exists).
  - `redirect("todo_list")` → `redirect(todo.todo_list)`, and the Cancel link to
    `{{ todo.todo_list.get_absolute_url }}`, so the person goes back to the list they came from.
  - Its tests: make to-dos with `todo_list=...`, and `test_edit_does_not_change_done_or_owner`
    checks `todo_list` instead of `owner`.
- #6 due date remakes its own migration after this one (merge queue rules). No
  `makemigrations --merge`: the merge queue does not allow two leaf migrations.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | New `TodoList`. `Todo` gets `todo_list`, loses `owner`. |
| `todos/migrations/` | Three new files (see above). Only the data file is written by hand. |
| `todos/forms.py` | New `TodoListForm`. |
| `todos/views.py` | `todo_list` (at `/`) becomes only a redirect. New function `render_list_page`. New views `list_detail`, `list_create`, `list_rename`, `list_delete`. `todo_add` takes a list `pk`, and shows the list page again through `render_list_page` when the form is not valid. Toggle and delete find the to-do with `todo_list__owner=request.user` and redirect to the to-do's list. No `owner=` is left in this file except for `TodoList`. |
| `todos/urls.py` | The addresses in the table above. |
| `accounts/views.py` | `signup` creates the "Inbox" list right after the user. Its `redirect("todo_list")` stays. |
| `todos/admin.py` | Register `TodoList` (`list_display = ["name", "owner", "created_at"]`). In the `Todo` admin, **replace** `owner` with `todo_list` in `list_display` and `list_filter`. If `owner` stays there, Django's start-up check fails (`admin.E108`) and nothing runs. |
| `accounts/tests/helpers.py` | `LoggedInTestCase.setUpTestData` also makes `cls.todo_list` ("Inbox", alice's) and `cls.other_list` ("Bob's list", bob's). |
| `todos/templates/todos/todo_list.html` | The list name as the page heading. A small menu with the person's lists (the open one marked with `aria-current="page"`), a "New list" link, "Rename" and "Delete list" links. The add form posts to `todo_add` with the list's `pk`. |
| `todos/templates/todos/list_form.html` | New, extends `base.html`. One page used for both "New list" and "Rename list": the name field, errors, a save button, a "Cancel" link. When renaming, Cancel goes back to that list. When making a new list, Cancel goes to `/`, and is left out when the person has no lists (`/` would only send them back to this page). |
| `todos/templates/todos/list_confirm_delete.html` | New, extends `base.html`. "Delete 'Work' and its 5 to-dos?", a POST button, a "Cancel" link back to the list. |
| `todos/templates/todos/_todo_item.html` | No change expected. The toggle and delete addresses stay the same. |
| `todos/tests/...`, `accounts/tests/...` | See "Tests". |
| `AGENTS.md`, `README.md` | The file table: `TodoList`, the new templates, the new addresses. |

## Tests

Rule from the test pyramid: test each rule once, in the lowest layer where a person would notice
it.

**Unit** (`todos/tests/unit/`): no new tests. Every new rule here needs the database (unique
names, who owns what) or a request (redirects), so it belongs in the integration layer.

**Integration** (`todos/tests/integration/`), new file `test_lists.py`, in small classes by topic.
The classes extend `LoggedInTestCase`, which now also has `self.todo_list` (alice's "Inbox") and
`self.other_list` (bob's "Bob's list"). Give lists in tests **different names for different
people**; a "not shown" test with the same name for both would pass even when it is broken.

| Class | Test | What it checks |
|---|---|---|
| `HomeTests` | `test_home_opens_oldest_list` | Alice has "Inbox" and a newer "Work": `/` redirects to "Inbox". |
| | `test_home_without_lists_goes_to_new_list` | A person with no lists is sent to `/lists/new/`. |
| `NewListTests` | `test_create_a_list` | POST "Work" creates a list owned by alice and redirects to it. |
| | `test_empty_name_is_not_created` | A name of only spaces creates nothing and shows an error. |
| | `test_duplicate_name_is_not_created` | With "Work" already there, "work" gives 200 (not 500), creates nothing, and shows the error with the typed name. |
| | `test_same_name_as_another_person_is_allowed` | Ana has "Work"; Ben can still make "Work". |
| | `test_create_ignores_owner_in_the_form` | POST "Work" with `owner=<bob's pk>`: the new list belongs to alice, and bob has no "Work". |
| | `test_get_does_not_create` | GET `/lists/new/` shows the form and creates nothing. |
| `RenameListTests` | `test_rename_a_list` | POST "Home" renames the list and redirects to it. |
| | `test_rename_to_another_lists_name_is_refused` | Renaming "Home" to "work" when "Work" exists changes nothing and shows an error. |
| | `test_rename_keeping_the_same_name_works` | Saving "Work" as "work" works (the list is not a duplicate of itself). |
| `DeleteListTests` | `test_get_shows_confirm_and_deletes_nothing` | GET shows the name and the number of to-dos; nothing is deleted. |
| | `test_delete_removes_list_and_its_todos` | POST deletes the list and its to-dos, and redirects to `/`. To-dos in the person's other list are still there. |
| | `test_delete_last_list_then_home_goes_to_new` | Alice deletes her only list; `/` then redirects to `/lists/new/`. |
| `ListPageTests` | `test_list_shows_only_its_own_todos` | A to-do in "Home" is not on the "Work" page. |
| | `test_menu_shows_my_lists` | The page links to each of the person's lists. |
| `AddTests` (changed) | `test_add_a_todo` | POST to `/lists/<pk>/add/` puts the to-do in that list, even when the POST also sends `todo_list=<bob's list pk>`. |
| | `test_add_with_empty_title_shows_this_list_again` | Alice has "Home" (with "Water plants") and "Work" (with "Send report"). POST an empty title to "Work"'s add address: 200 (not a redirect), the form error is shown, "Send report" is on the page and "Water plants" is not, and nothing is added. |
| `ToggleTests`, `DeleteTests` (changed) | `test_toggle_returns_to_its_list`, `test_delete_returns_to_its_list` | After the POST, the browser goes back to the to-do's own list. |
| `PrivacyTests` | `test_cannot_open_someone_elses_list` | Ben gets 404 for Ana's list page. |
| | `test_cannot_add_to_someone_elses_list` | Ben's POST to Ana's add address gives 404 and adds nothing. |
| | `test_cannot_rename_someone_elses_list` | Ben's GET and POST to Ana's rename address give 404; the name does not change. |
| | `test_cannot_delete_someone_elses_list` | Ben's GET and POST to Ana's delete address give 404; the list and its to-dos are still there. |
| | `test_menu_does_not_show_someone_elses_lists` | "Bob's list" is not on alice's page. |

No new login test: with #17's middleware every view needs a login unless it is marked
`@login_not_required`, and #17's `test_only_login_and_signup_are_open` walks every address of the
site, so it also checks the new ones.

**Integration, changed tests from #17:**

- `accounts/tests/integration/test_accounts.py`: `test_signup_creates_user_and_logs_in` now also
  checks the person has exactly one list, called "Inbox". Tests that open `/` and expect a page
  (status 200, "Logged in as alice") must now follow the redirect (`follow=True`), because `/`
  is only a redirect. Tests that use `assertRedirects(response, "/")` (login with `next=/`,
  sign-up, a logged-in user on the login page) need `fetch_redirect_response=False`:
  `assertRedirects` also loads `/` and expects 200, but `/` now answers with a redirect (302).
- `todos/tests/integration/test_views.py`: `test_anonymous_cannot_add_toggle_or_delete` and
  `test_post_without_csrf_token_is_403` post to `reverse("todo_add", args=[<alice's list>.pk])`
  (the old `reverse("todo_add")` with no number now fails with `NoReverseMatch`). The first one
  is in a plain `TestCase` (`LoginRequiredTests`), so it makes alice's list itself.
- `todos/tests/integration/test_views.py`: every `Todo.objects.create(owner=...)` becomes
  `todo_list=self.todo_list` (or `self.other_list` for bob). The privacy tests (bob cannot toggle
  or delete alice's to-do: 404) stay, and now check the lookup through the list.
  `test_add_sets_me_as_owner` checks `todo.todo_list.owner`; `test_add_ignores_owner_in_the_form`
  is replaced by the `todo_list` check in `test_add_a_todo` above; `test_list_shows_only_my_todos`
  opens alice's list page, not `/`.

**Integration, migrations** — in #17's `todos/tests/integration/test_migrations.py`
(`TransactionTestCase`, Django's `MigrationExecutor`). Create rows only with the **old models**
from the migration state (`executor.loader.project_state(...).apps`), never with
`from todos.models import ...`.

| Test | What it checks |
|---|---|
| `test_migration_gives_each_user_a_list` | At `0004`: two users (one with to-dos, one without). Migrate forward: each user has one "Inbox" list, and every to-do is in its owner's list. |
| `test_migration_back_gives_todos_their_owner` | Forward with to-dos in two users' lists, then back to `0004`: every to-do's `owner` is the owner of its old list. |

Both tests end by migrating to the newest migration (the "leaf", from
`executor.loader.graph.leaf_nodes()`), not to a fixed number. Check that #17's migration tests do
the same: if they go back to a fixed `0004`, every test after them runs without the lists table.


**CUJ** (`todos/tests/cuj/test_journeys.py`), one new journey, because "my to-dos are in separate
lists" is the main thing a person would notice:

- `test_separate_lists`: log in, make a list "Shopping", add "Buy milk" to it, open the "Inbox"
  list from the menu and check "Buy milk" is not there, go back to "Shopping", delete the list on
  the confirm page, and check the browser is on "Inbox" and "Shopping" is gone from the menu.

`test_plan_and_finish`: `make_user` makes no list, so before `log_in_as(user)` also create a
"Inbox" list for the user. Without it, `/` goes to `/lists/new/` and the test fails. The journey
itself does not change.

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

1. **Tests first.** Write the integration tests above (not yet the migration tests and the CUJ),
   and the helper change. Run `make test` and show they fail, for example `test_create_a_list`
   fails because `/lists/new/` does not exist (404).
2. **Model, part 1.** Add `TodoList`; add `Todo.todo_list` with `null=True`; set `Todo.owner` to
   `null=True`. Run `uv run python manage.py makemigrations todos --name todolist`.
3. **Data migration.** Run `uv run python manage.py makemigrations todos --empty --name
   default_lists`. For now, put `migrations.RunPython(migrations.RunPython.noop,
   migrations.RunPython.noop)` in it.
4. **Model, part 2.** Remove `null=True` from `todo_list`; remove `owner`. Run
   `uv run python manage.py makemigrations todos --name todo_list_required`. Django asks how to
   fill `todo_list` in rows where it is empty. Choose **2) "Ignore for now"**: the data step
   (file 2) fills it. Do not give a one-off default: there is no list number that is right for
   every to-do.
5. **Migration tests.** Write the two migration tests. Run them and show they fail: with the
   empty data step, migrating a database with to-dos stops, because `todo_list` cannot be empty.
   Then write the two functions from "What the migration does", and show the tests pass. Run
   `uv run python manage.py migrate`.
6. **Form.** `TodoListForm` in `todos/forms.py`.
7. **Views and addresses.** The new views, the changed views, `todos/urls.py`, and the "Inbox"
   list in the sign-up view. Then run `grep -rn "owner" todos/ accounts/ config/`: every match
   must be about `TodoList.owner` or the migrations.
8. **Templates.** The list page, `list_form.html`, `list_confirm_delete.html`, all extending
   `base.html`. Use the CSS variables from wave 0 for any new color, so dark mode (#20) works.
9. **Admin.** Register `TodoList`, and replace `owner` with `todo_list` in the `Todo` admin.
10. **CUJ.** Add `test_separate_lists` and update `test_plan_and_finish`.
11. **Docs.** `AGENTS.md` and `README.md`: the file table and the addresses.
12. **Before the commit.** Run `make check` (commit checks, the migration check, all tests).
    Then `make run`, and try it by hand on a copy of a real `db.sqlite3` with to-dos in it: each
    to-do should be in a "Inbox" list after `migrate`. Then `migrate todos 0004` and `migrate`
    again on the same copy: no error. Look at the page in a narrow window too.

## Open questions

None. The default list name was decided: "Inbox".

## Review

What the review changed, and why:

- Assumed `LoginRequiredMiddleware` (what #17 plans), not `@login_required`; cut the plan's own
  login test, because #17's test already loops over every address.
- Kept the URL names `todo_list` (for `/`) and `todo_add`. Renaming `todo_list` would crash
  `LOGIN_REDIRECT_URL`, the sign-up view and #4 edit with `NoReverseMatch`.
- Renamed `list_new` to `list_create`, to match #18 sharing.
- Wrote out the data migration functions, and checked the three files on an empty database, a
  full one, and backwards. Added a test for going backwards.
- Told the orchestrator not to remake files 1 and 3 with `makemigrations` (one run would merge
  them into one file and lose the data step), and gave the files fixed names.
- Replaced the `makemigrations --merge` advice with the merge-queue order (lists, then edit,
  then due date), and listed what #4 edit must change when it is rebased.
- Added the `todos/admin.py` fix: `owner` left in `list_display` would stop Django from starting.
- `make_user` makes no list, so the test helper and `test_plan_and_finish` now make one; tests of
  #17 that open `/` must follow the redirect.
- The form gets its owner from `instance` instead of a new argument (plain Django), and the plan
  says why `clean_name` is needed (else a 500 page).
- Wrote down that "ignoring case" is A–Z only on SQLite (Æ, Ø, Å are not folded); checked by hand.
- Added `"pk"` as a tie-breaker in `ordering`, so "oldest list" is always the same list.
- "Not shown" tests use different list names per person, so they cannot pass by accident.
- Moved the migration test into #17's `test_migrations.py`, using old models, and ending at the
  newest migration, not a fixed number.
- Decided the former open questions: remove `Todo.owner` (#17 has only a few `owner` queries,
  all listed above, and #17 is merged before this starts); allow deleting the last list; oldest
  first in the menu.

## Second review

What the second review changed, and why:

- Built the three migration files on top of #17's `0002`–`0004` and ran them: empty database,
  database with users and to-dos, backwards to `0004`, forward again, and back to `0001` and
  forward. All work. Checked: `Lower("name")` makes a case-blind unique index, `clean_name` stops
  "work" next to "Work" (without it the save is an `IntegrityError`, so a 500), and `"pk"` in
  `ordering` passes Django's checks.
- Step 4: `makemigrations` asks how to fill the empty `todo_list`; the plan now says to choose
  "Ignore for now".
- The data migration uses `settings.AUTH_USER_MODEL`, like #17's, not `"auth", "User"`.
- New `render_list_page`: `todo_add` with a bad form now shows this list's page again (wave 0 and
  #6 due date expect this), not wrong to-dos or a page with no menu. Added a test for it.
- Wrote down which methods each view accepts (`require_GET`, `require_http_methods`).
- Added `test_create_ignores_owner_in_the_form` (a forged `owner` field).
- Cancel on the rename page goes back to that list; on "New list" it is hidden when the person
  has no lists (else it loops back to the same page).
- Fixed the name of #17's login guard (`test_only_login_and_signup_are_open`; there is no
  `test_every_todos_address_needs_login`), and listed more #17 tests that break: `assertRedirects`
  to `/` (now a 302) and posts to `reverse("todo_add")` with no list number.

## Decided by the person (2026-10-09)

The plan is **approved**.

- The default list is called "Inbox" (for new people and in the migration).
