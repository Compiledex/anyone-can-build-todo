# Plan: user accounts and login (#17)

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (the test pyramid, `TodoForm` in `todos/forms.py`, the partial
`todos/templates/todos/_todo_item.html`, colors as CSS variables on `:root`, and the shared layout
`todos/templates/base.html` with its `{% block content %}`). This plan does **not** make its own
`base.html`. It adds a small header to wave 0's `base.html`, and its new pages extend it.

## Goal

A person can **sign up**, **log in** and **log out**. After logging in, they see **only their own
to-dos**, and they can change only their own to-dos.

This is the first feature of wave 1. Every later feature builds on it, so this plan also sets
**the pattern for "only my data"** (see below), and **the test helpers** that later tests reuse.

Words used in this plan:

- **Authentication**: checking who a person is (here: a username and a password).
- **Session**: Django remembers that you are logged in with a cookie (a small piece of data the
  browser keeps and sends back with every request).
- **CSRF** (cross-site request forgery): another website tricks your browser into sending a form
  to our site. Django blocks this with a secret token in every form (`{% csrf_token %}`).
- **Foreign key**: a field that points to a row in another table. Here, each to-do points to the
  user who owns it.
- **Open redirect**: a link to our login page with `?next=https://evil.example`, so that after
  logging in the person lands on a stranger's site. Django's `LoginView` refuses such a `next`.

## Decisions

- **Use Django's built-in accounts** (`django.contrib.auth`). It is already in
  `INSTALLED_APPS`, and its tables already exist. We use its `User` model, `LoginView`,
  `LogoutView` and `UserCreationForm`. No new package.
- **A user has a username and a password. No email.** Without email there is no "forgot my
  password" page. An admin can set a new password in `/admin/`.
- **Login is required everywhere, by default.** We turn on Django's
  `LoginRequiredMiddleware` (new in Django 5.1; `uv.lock` has Django 5.2.17, checked). A
  **middleware** is code that runs for every request, before the view. With it, every view needs a
  logged-in user, unless the view is marked with `@login_not_required`. Why this and not
  `@login_required` on each view: a later feature that forgets the decorator would show data to
  everyone. With the middleware, forgetting is safe: the new page simply needs a login.
- **What stays open to everyone** (checked in Django 5.2's code and by a quick try):
  - Our login page (`LoginView` is marked `login_not_required` by Django), our sign-up page
    (we mark it), and our logout address (we mark it, see "Logout" below).
  - The admin's own login page, `/admin/login/`. **Other admin pages are not open**: an anonymous
    visitor to `/admin/` goes to `/admin/login/`, and to a deeper page such as
    `/admin/todos/todo/` goes to our `/accounts/login/`. Both are fine: either login works for
    the admin, and the admin still checks "is staff" after that.
  - Static files (CSS). WhiteNoise and the test server serve them before the middleware runs.
  - An address that does not exist gives 404 before the middleware runs. It shows no data.
- **What an anonymous visitor sees**: any page sends them to `/accounts/login/?next=<the page>`.
  The login page has a link "Create an account". After logging in, they go back to `next`, or to
  the list. `next` must point to our own site; `LoginView` checks this (no open redirect).
- **After sign-up**, the new user is logged in at once and goes to the list. A logged-in user who
  opens the login or sign-up page is sent to the list. The sign-up page ignores `next`.
- **Session fixation is handled by Django.** (Session fixation: an attacker gives you a session
  cookie before you log in, then uses it after.) Django's `login()` always makes a new session
  key, and `logout()` deletes the session. We call `login()` in sign-up too, so this holds
  there. We do not test Django's own code for this.
- **Logout is a `POST`** (a button in a form), as Django 5 requires. A `GET` to the logout
  address gives 405 ("method not allowed"). After logout, the browser goes to the login page.
  Logout ignores a `next` that points to another site (Django checks it, like login).
- **Logout is open to everyone** (`login_not_required(LogoutView.as_view())`). Django does not
  mark `LogoutView` open by itself. Without this, a person who already logged out in another tab
  (or whose session ended) and then presses "Log out" is sent to
  `/accounts/login/?next=/accounts/logout/`; after logging in, the browser does a `GET` there and
  gets a 405 page. Open, an anonymous `POST` just goes to the login page (checked). It shows no
  data, and it still needs the CSRF token.
- **The sign-up page tells whether a username is taken** ("A user with that username already
  exists."). Every sign-up page does this; it cannot be hidden. The login page does not: a wrong
  password and an unknown username give the same error (checked).
- **Each to-do has an owner**: `owner = models.ForeignKey(settings.AUTH_USER_MODEL,
  on_delete=models.CASCADE, related_name="todos")`. It is **required** (not null). When a user is
  deleted, their to-dos are deleted too (`CASCADE`). (#10 lists later moves the owner to the
  list and removes `Todo.owner`. That is fine; this plan does not depend on it staying.)
- **The owner is never taken from the form.** The view sets it from `request.user`. `TodoForm`
  keeps `fields = ["title"]` (plus any field later waves add), never `owner`.
- **Someone else's to-do gives 404, not 403.** 404 means "not found". 403 would say "it exists, but
  it is not yours", which tells an attacker which numbers exist.
- **Existing to-dos (the migration)**: to-dos made before this change have no owner. They are
  given to **the oldest superuser** (an admin account, made with `createsuperuser`). If there are
  old to-dos but no superuser, the migration **stops with a clear message**: "Run
  `uv run python manage.py createsuperuser`, then `migrate` again." We never delete data
  without asking. An empty database (a new laptop, the test database) needs no superuser: the
  migration sees no old to-dos and does nothing.
- **The admin** (`/admin/`) shows every to-do, with its owner. Admins are trusted. This does not
  break "only my data", because the admin is not the app.
- **One shared layout, from wave 0**: `todos/templates/base.html`. This plan adds a small header
  to it ("Logged in as alice" and a "Log out" button). The login and sign-up pages extend it, so
  they get the same CSS and dark mode with no copying.
- **A session that ended while a person pressed a to-do button** (for example "Done"): the middleware
  sends them to login with `next=/5/toggle/`. After logging in, the browser does a `GET` there,
  which gives 405. This is rare (sessions last two weeks) and harmless (no data changes). We
  leave it.
- **Anyone can sign up, and there is no limit on wrong passwords.** Fine on a laptop and for the
  class. See open question 1 before the site is public.

## The pattern for "only my data" — copy this in every later feature

This is the most important part of the plan. `AGENTS.md` gets a short copy of it.

1. **Read a list**: always start from the user.

   ```python
   todos = Todo.objects.filter(owner=request.user)
   ```

   Never `Todo.objects.all()` in a view.

2. **Read or change one thing by its number (`pk`)**: put the owner in the lookup.

   ```python
   todo = get_object_or_404(Todo, pk=pk, owner=request.user)
   ```

   Someone else's to-do then gives 404, exactly like a to-do that does not exist.

3. **Create**: set the owner in the view, never from the form.

   ```python
   todo = form.save(commit=False)
   todo.owner = request.user
   todo.save()
   ```

4. **A new model** that belongs to a to-do (for example subtasks, tags) is reached **through** a
   to-do the user owns (`get_object_or_404(Todo, pk=pk, owner=request.user)` first), or gets its
   own `owner` field and follows rules 1–3.

5. **Every new view gets one test**: user B gets 404 (or does not see the thing) for user A's
   thing. Use `assertOtherUserGets404` from the helpers below, **and** check that A's thing did
   not change.

After #10 lists, "owner" is reached through the list (`todo_list__owner=request.user`), and after
#18 sharing through `TodoList.objects.visible_to(request.user)`. Those plans change the lookups;
the rules above stay the same.

## Not part of this task

- Password reset by email, email addresses, email confirmation.
- A "change my password" page. An admin can do it in `/admin/`.
- Limits on wrong passwords (blocking a user after many tries). This matters on a public
  server; it can be its own task, and may need a package.
- A custom user model. Django's `User` is enough. The code still points at the user with
  `settings.AUTH_USER_MODEL` / `get_user_model()`, the Django way.
- Sharing to-dos with other users (#18, wave 3).
- Several lists per user (#10, wave 2).
- Deleting your own account.

## Changes to files

| File | Change |
|---|---|
| `config/settings.py` | Add `"accounts"` to `INSTALLED_APPS`; add `"django.contrib.auth.middleware.LoginRequiredMiddleware"` right after `AuthenticationMiddleware`; add `LOGIN_URL = "login"`, `LOGIN_REDIRECT_URL = "todo_list"`, `LOGOUT_REDIRECT_URL = "login"`. `TEMPLATES` does not change: `APP_DIRS` already finds templates in each app. |
| `config/urls.py` | Add `path("accounts/", include("accounts.urls"))`, before the `todos` line. |
| `accounts/` (new app) | Made with `uv run python manage.py startapp accounts`. Keep `__init__.py`, `apps.py`, `views.py`, and add `urls.py`. Delete the `models.py`, `admin.py`, `tests.py` and the `migrations/` folder that `startapp` makes (this app has no models). |
| `accounts/urls.py` (new) | Three addresses: `login/` → `LoginView.as_view(redirect_authenticated_user=True)`, name `login`; `logout/` → `login_not_required(LogoutView.as_view())`, name `logout`; `signup/` → `views.signup`, name `signup`. We do **not** include all of `django.contrib.auth.urls`, because the password reset pages need email. |
| `accounts/views.py` (new) | One view, `signup`, marked `@login_not_required`. See step 5. |
| `todos/templates/base.html` (made by wave 0) | Add a header. When `user.is_authenticated`: "Logged in as {{ user.username }}" and a `<form method="post" action="{% url 'logout' %}">` with `{% csrf_token %}` and a "Log out" button. Nothing else in it changes. |
| `accounts/templates/registration/login.html` (new) | `{% extends "base.html" %}`. Shows the login form (`{{ form.as_div }}`), `{% csrf_token %}`, a hidden `next` field (`<input type="hidden" name="next" value="{{ next }}">`), a "Log in" button, and a link "Create an account" to `signup`. The `registration/` folder is where `LoginView` looks by default. |
| `accounts/templates/registration/signup.html` (new) | `{% extends "base.html" %}`. The `UserCreationForm` (`{{ form.as_div }}`), `{% csrf_token %}`, a "Sign up" button, and a link "Already have an account? Log in". |
| `todos/models.py` | Add the `owner` foreign key (see Decisions). |
| `todos/migrations/0002_todo_owner.py`, `0003_give_old_todos_an_owner.py`, `0004_alter_todo_owner.py` (new) | See step 3. |
| `todos/views.py` | Follow the pattern above in all four views. `render_list_page` (from wave 0, used by `todo_list` and by `todo_add` on an invalid form): `filter(owner=request.user)`, so both pages show only my to-dos. `todo_add`: set the owner. `todo_toggle`, `todo_delete`: `get_object_or_404(Todo, pk=pk, owner=request.user)`. No decorators needed, because the middleware does it. |
| `todos/admin.py` | `@admin.register(Todo)` with `list_display = ["title", "owner", "done", "created_at"]` and `list_filter = ["owner", "done"]`, so an admin can see whose to-do it is. |
| `accounts/tests/__init__.py`, `accounts/tests/integration/__init__.py` (new, empty) | So the test runner finds the tests. |
| `accounts/tests/helpers.py` (new) | The test helpers (see below). |
| `accounts/tests/integration/test_accounts.py` (new) | Sign up, log in, log out. |
| `todos/tests/integration/test_views.py` | Existing tests use the helpers; new "only my data" tests. |
| `todos/tests/integration/test_migrations.py` (new) | The data migration test. |
| `todos/tests/cuj/browser.py` | Add `log_in_as(user)`. |
| `todos/tests/cuj/test_journeys.py` | Log in first; add the sign-up journey. |
| `AGENTS.md`, `README.md` | See step 9. |

## The test helpers — for every later feature

New file `accounts/tests/helpers.py`. Its name does not start with `test`, so the test runner
does not load it as a test file, and the layer check in `config/test_runner.py` does not look at
it. Other features import from it. (A test file that imports `LoggedInTestCase` makes the runner
see that class too, but it has no `test_` methods, so it adds no tests.)

```python
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

# Only for tests. It is not a real password for anything. It passes Django's
# password rules (checked: it is not in the common-password list).
TEST_PASSWORD = "correct-horse-battery-staple"


def make_user(username="alice"):
    return get_user_model().objects.create_user(username=username, password=TEST_PASSWORD)


class LoggedInTestCase(TestCase):
    """A TestCase where self.client is logged in as self.user (alice).

    self.other_user (bob) exists too, to check that bob cannot see or
    change alice's things.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("alice")
        cls.other_user = make_user("bob")

    def setUp(self):
        self.client.force_login(self.user)

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def assertOtherUserGets404(self, url, method="post", data=None):
        """bob asks for alice's thing, and gets 404."""
        response = getattr(self.client_for(self.other_user), method)(url, data or {})
        self.assertEqual(response.status_code, 404)
```

- `force_login` logs a user in without a password check. It is fast, and it is the Django way to
  log in inside tests. The real login form is tested once, in `test_accounts.py`, and once in a
  real browser (the CUJ).
- `setUpTestData` makes the two users once per class, not once per test. That keeps the tests
  fast, because making a password hash is slow on purpose.
- A test still checks the data did not change after a 404 (for example `todo.refresh_from_db()`
  and `assertFalse(todo.done)`). A 404 alone is not enough: a view could change the data and
  then fail.

For CUJ tests, `BrowserTestCase` in `todos/tests/cuj/browser.py` gets one method (it needs
`from django.conf import settings` and `from django.test import Client`):

```python
def log_in_as(self, user):
    """Give the browser this user's session cookie, so the test starts logged in.

    Call it before the first page.goto().
    """
    client = Client()
    client.force_login(user)
    cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    self.context.add_cookies(
        [{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}]
    )
```

Why this works: `force_login` saves the session in the test database, and the live server reads
the same database (Django shares the in-memory SQLite database with the server thread). The
cookie is not "secure-only" in tests, because `DJANGO_DEBUG` is not set in the tests or in CI.

This skips the login form in journeys that are about something else. The one sign-up journey
uses the real forms.

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

### 1. The helpers and the tests first

Write `accounts/tests/helpers.py` (step above) and the tests in step 8. Run `make test` and show
them failing. Most fail with a clear reason: `/accounts/login/` is 404, the list shows bob
alice's to-dos, and bob's toggle of alice's to-do gives 302 instead of 404.

`Todo.objects.create(...)` in tests needs `owner=self.user` once the field exists. Before that, the
tests fail with "unexpected keyword argument 'owner'". That is fine for step 1, but say so in the
pull request.

### 2. The model — `todos/models.py`

```python
from django.conf import settings
from django.db import models


class Todo(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todos"
    )
    title = models.CharField(max_length=200)
    ...
```

`settings.AUTH_USER_MODEL` is the Django way to point at the user table. It is `auth.User` here.

### 3. Migrations — `todos/migrations/`

A required field cannot be added to a table that already has rows, because the old rows have no
value for it. So we do it in three migrations, each with a **fixed name**:

1. **`0002_todo_owner`**: first write the field with `null=True`, and run
   `uv run python manage.py makemigrations todos --name todo_owner`. Django makes this file. It
   already depends on the user table (`migrations.swappable_dependency(settings.AUTH_USER_MODEL)`).
2. **`0003_give_old_todos_an_owner`**: a **data migration** (a migration that changes rows, not
   the table). Make the empty file with
   `uv run python manage.py makemigrations todos --empty --name give_old_todos_an_owner`, then
   write its function at the top of the file (module level). `AGENTS.md`'s "never edit migrations
   by hand" means the files Django writes by itself; this one is meant to be written.

   ```python
   from django.conf import settings
   from django.db import migrations


   def give_old_todos_an_owner(apps, schema_editor):
       Todo = apps.get_model("todos", "Todo")
       User = apps.get_model(settings.AUTH_USER_MODEL)
       old_todos = Todo.objects.filter(owner__isnull=True)
       if not old_todos.exists():
           return
       admin = User.objects.filter(is_superuser=True).order_by("pk").first()
       if admin is None:
           raise RuntimeError(
               "There are to-dos with no owner, and no admin account to give them to. "
               "Run `uv run python manage.py createsuperuser`, then `migrate` again."
           )
       old_todos.update(owner=admin)
   ```

   Use `migrations.RunPython(give_old_todos_an_owner, migrations.RunPython.noop)`. `noop` means
   going back does nothing (going back past `0002` removes the `owner` column anyway).
   `dependencies` is only `[("todos", "0002_todo_owner")]`: `0002` already brings in the user
   table. Do **not** write `apps.get_model("auth", "User")` or a fixed `auth` migration number;
   use `settings.AUTH_USER_MODEL`, as above.
   Why the stop is safe: each migration is saved on its own. If `0003` stops, `0002` is already
   done, and after `createsuperuser` a new `migrate` starts again at `0003`.
3. **`0004_alter_todo_owner`**: remove `null=True` from the field, and run
   `uv run python manage.py makemigrations todos --name alter_todo_owner --noinput`. Django
   makes this file. Without `--noinput`, Django asks a question ("It is impossible to change a
   nullable field ... Please select a fix"); an agent has no keyboard, so the command crashes
   with `EOFError` (checked). With `--noinput` Django takes the answer "ignore for now", which is
   right here: `0003` has already filled every row. (A person typing it by hand picks option 2.)

**For the merge queue** (say this in the pull request report): treat **all three** files as
hand-managed. Do **not** delete and regenerate `0002` and `0004`: a new `makemigrations` would
make one file that adds a required field to a table with rows, and ask for a default. Only fix
the numbers and `dependencies`. The orchestrator's "migrate backwards, then forward again" check
needs a **superuser in the sample database** if it has to-dos; without one, `0003` stops with the
message above, which is the intended behavior.

Then run `uv run python manage.py migrate`. On a laptop with old to-dos: run `createsuperuser`
first, if you have not.

### 4. Settings and addresses — `config/settings.py`, `config/urls.py`, `accounts/`

As in the table. The middleware must come **after** `AuthenticationMiddleware`, because it needs
`request.user`. `LOGIN_URL = "login"` is a URL name, so the address is only written once, in
`accounts/urls.py`.

### 5. The sign-up view — `accounts/views.py`

```python
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


@login_not_required
def signup(request):
    if request.user.is_authenticated:
        return redirect("todo_list")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("todo_list")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})
```

`UserCreationForm` checks that the username is free (ignoring upper and lower case), that both
passwords match, and the password rules already in `AUTH_PASSWORD_VALIDATORS` (at least 8
characters, not too common, not only numbers, not too close to the username). In Django 5.2 it
has no "usable password" choice (that is only in the admin's form), checked.

### 6. The to-do views — `todos/views.py`

Change the four views as in "the pattern". The owner filter for the list goes **inside**
`render_list_page` (from wave 0), not in `todo_list`: `todo_add` also calls it when the form is
not valid, so a filter only in `todo_list` would show bob's to-dos on that error page. Nothing
else changes: add, toggle and delete still accept `POST` only.

### 7. The templates

As in the table. Give the header in `base.html` a little style
(`display: flex; justify-content: space-between`), using the existing CSS variables for colors,
so dark mode works with no new colors. Form fields on the login and sign-up pages: one per
line, full width, the same font size as the add field.

### 8. The full list of tests

**Unit**: none. This feature has no logic that runs without a request or the database. The rules
are about what a person sees, so they are integration tests.

**Integration**, `accounts/tests/integration/test_accounts.py` (class `TestCase`, users from
`make_user`). A test that expects a redirect to the list uses
`assertRedirects(response, "/", fetch_redirect_response=False)`: after #10 lists, `/` is itself a
redirect, and the default would then fail.

| Test | What it checks |
|---|---|
| `test_signup_creates_user_and_logs_in` | `POST` to sign-up with a good username and `TEST_PASSWORD` twice: the user exists, the response goes to the list, and a `GET` of the list is 200 (logged in). |
| `test_signup_with_different_passwords_shows_error` | No user is made; the page is shown again (200) with an error; the typed username is still in the field. |
| `test_signup_with_taken_username_shows_error` | `alice` exists; signing up as `Alice` (other case) makes no second user. |
| `test_login_with_right_password_goes_to_next` | `POST` to login with `next=/` → redirect to `/`, and the user is logged in. |
| `test_login_ignores_next_to_another_site` | `POST` to login with `next` set to `https://evil.example/`, `//evil.example/` and `/\evil.example/` (`subTest` each, a fresh `Client` each) → redirect to the list, not to `evil.example`. This guards against an open redirect if someone later writes their own login view. |
| `test_login_with_wrong_password_shows_error` | 200, an error on the page, and not logged in. |
| `test_logged_in_user_on_login_or_signup_goes_to_list` | Both pages redirect to the list (`subTest` for each). |
| `test_logout_logs_out` | `POST` to logout with `next=https://evil.example/` → redirect to the login page (not to `evil.example`); then the list redirects to login. |
| `test_logout_when_already_logged_out_goes_to_login` | Anonymous `POST` to logout → redirect to `/accounts/login/` with no `next` (not a 405 after the next login). |
| `test_logout_with_get_is_405` | `GET` to logout is 405, and the user is still logged in. |
| `test_header_shows_username_and_logout_button` | The list page has "Logged in as alice" and a form that posts to the logout address. |
| `test_login_page_has_csrf_token` | The login and sign-up pages contain a `csrfmiddlewaretoken` field (`subTest` for each). The test client skips the CSRF check, so without this a page with no `{% csrf_token %}` would pass every other test here. |

**Integration**, `todos/tests/integration/test_views.py`:

- All existing test classes extend `LoggedInTestCase`, and make to-dos with `owner=self.user`.
- New class `LoginRequiredTests` (plain `TestCase`, nobody logged in):

| Test | What it checks |
|---|---|
| `test_anonymous_list_goes_to_login` | `GET /` → redirect to `/accounts/login/?next=/`. |
| `test_anonymous_cannot_add_toggle_or_delete` | `POST` to each → redirect to login, and the to-do (owned by alice) did not change (`subTest` per address). |
| `test_only_login_and_signup_are_open` | Walks **every** URL pattern of the whole site (`get_resolver().url_patterns`; for a `URLResolver`, go into its `url_patterns`, but skip the one with `namespace == "admin"`), and collects the views marked open (`getattr(pattern.callback, "login_required", True) is False`). The set of their names must be exactly `{"login", "logout", "signup"}` (checked: this is what the walk finds). Logout counts as part of "login" here; the name stays, because lists.md and sharing.md use it. This guards every later feature in every app: a new page marked `@login_not_required` makes this test fail, and the author must add it here on purpose. |
| `test_admin_is_not_open` | Anonymous `GET /admin/login/` is 200 (the admin's own login works). Anonymous `GET /admin/` and `GET /admin/todos/todo/` are redirects to a login page, never 200 (`subTest` each). |

- New class `OnlyMyDataTests(LoggedInTestCase)`:

| Test | What it checks |
|---|---|
| `test_list_shows_only_my_todos` | alice has "Buy milk", bob has "Call home". alice's list shows the first and not the second: check `response.context["todos"]` **and** `assertNotContains(response, "Call home")`. |
| `test_invalid_add_shows_only_my_todos` | Same data. alice posts an empty title: status 200, and the page shown again has "Buy milk" and not "Call home" (context **and** HTML). Without this, a filter only in `todo_list` would leak bob's to-dos on the error page. |
| `test_add_sets_me_as_owner` | A new to-do's owner is alice. |
| `test_add_ignores_owner_in_the_form` | `POST` with `owner=<bob's pk>`: the to-do's owner is still alice. |
| `test_other_user_cannot_toggle_my_todo` | `assertOtherUserGets404`, and alice's to-do is still not done. |
| `test_other_user_cannot_delete_my_todo` | `assertOtherUserGets404`, and alice's to-do still exists. |
| `test_post_without_csrf_token_is_403` | With `Client(enforce_csrf_checks=True)` logged in as alice, a `POST` to add without a token is 403 and adds nothing. (Django's test client skips the CSRF check by default, so this test turns it on.) |

**Integration**, `todos/tests/integration/test_migrations.py` (a `TransactionTestCase`, because it
moves the database between migrations with Django's `MigrationExecutor`):

| Test | What it checks |
|---|---|
| `test_old_todos_go_to_the_oldest_superuser` | Migrate back to `todos 0002_todo_owner`. Make two superusers and an ownerless to-do. Migrate to `0004`: the to-do's owner is the first superuser. |
| `test_old_todos_without_a_superuser_stop_the_migration` | Migrate back to `0002`: an ownerless to-do and no superuser. Migrating to `0003` raises `RuntimeError` with the `createsuperuser` hint. |

Rules for this file, so it keeps working after later features change the models:

- Make rows only with the **historical models** of that moment:
  `executor.loader.project_state(target).apps.get_model("todos", "Todo")` (and the user model the
  same way). Never import `todos.models` here: after #10 removes `Todo.owner`, it would break.
- At the end of each test (in `tearDown`, so it also runs after a failure), migrate forward to
  `executor.loader.graph.leaf_nodes()`, so the other tests get the newest tables. Use a **new**
  `MigrationExecutor(connection)` for each migrate, so it reads which migrations are applied now.
- `test_old_todos_without_a_superuser_stop_the_migration` must **delete its ownerless to-do**
  (with the historical `Todo`) after the `assertRaises`. Otherwise `tearDown` runs `0003` again,
  raises the same `RuntimeError`, and the test errors (checked: it does).
- Make users here with `User.objects.create(username=..., is_superuser=True)` on the historical
  model; they need no password.
- If the orchestrator renumbers the migrations, update the names in this file.

**CUJ**, `todos/tests/cuj/test_journeys.py`:

- `test_plan_and_finish`: call `self.log_in_as(make_user())` before `page.goto(...)`. Nothing
  else changes.
- New `test_two_people_have_their_own_lists`: open the site → it shows the login page → click
  "Create an account" → sign up as alice (password `TEST_PASSWORD`) → add "Buy milk" → "Log
  out" → sign up as bob → bob's list says "Nothing to do yet" and does not show "Buy milk" → log
  out → log in as alice → "Buy milk" is there. This is the one test that uses the real sign-up,
  login and logout forms in a browser, including their CSRF tokens.

### 9. Docs

- `AGENTS.md`:
  - The file table: add `accounts/`, `accounts/templates/registration/`,
    `accounts/tests/helpers.py`; `models.py` gets `owner`; `base.html` gets the header.
  - "What this is": replace "There are no accounts: everyone sees the same list" with "Each person
    has an account and sees only their own to-dos."
  - A new rule under "Rules": **Only my data.** The five points of the pattern above, short, with
    the two code lines, and "every new view gets a test that another user gets 404, and the data
    did not change".
  - A new rule: **Every page needs a login, by default.** Only mark a view `@login_not_required`
    when a stranger must see it, add its name to `test_only_login_and_signup_are_open`, and say
    why in the pull request.
- `README.md`: after `make setup`, say "open the site and click *Create an account*". Say that
  `createsuperuser` is needed before `migrate` if the database already has to-dos. Update the file
  table.

### 10. Before the commit

- Run `make check`. It runs the commit checks, the migration check, and the tests.
- On a copy of a `db.sqlite3` with old to-dos: `migrate` stops with the message; after
  `createsuperuser` it works; `migrate todos 0001` and `migrate` again also work (all checked).
- With `make run`: sign up two users in two browser windows (one normal, one private), and check
  each sees only their own list. Try logging out and opening `/` again.
- Look at the login and sign-up pages on a narrow window, in light and dark mode.

## Open questions

1. **Before the site is public**: anyone on the internet can make an account, and nobody is
   blocked after many wrong passwords. Fine for a laptop and the class. Before a public deploy,
   decide: close sign-up (only an admin makes accounts), or add a limit on wrong passwords (its
   own task, likely a package such as `django-axes`).

## Review

What the review changed, and why:

- Removed the plan's own `templates/base.html` and the `TEMPLATES["DIRS"]` change: wave 0 makes
  `todos/templates/base.html`; this plan only adds the header to it.
- Moved the login and sign-up templates to `accounts/templates/registration/`, found by
  `APP_DIRS` (the admin has no `registration/login.html` that could hide ours; checked).
- Fixed the claim "the admin is `login_not_required`": in Django 5.2 only `/admin/login/` is
  open; deeper admin pages go to our login. Replaced `test_admin_still_has_its_own_login`
  (it would pass for `/admin/` only) with `test_admin_is_not_open`.
- Replaced the "every pattern in `todos.urls`" guard with a walk over the whole site that checks
  the set of open views is exactly `{login, signup}`. The old test missed pages in other apps.
- Migrations: the merge queue regenerates auto-made files, which would turn `0002`+`0004` into
  one file that cannot run on a table with rows. All three are now hand-managed, with fixed names.
- Data migration: `apps.get_model(settings.AUTH_USER_MODEL)` and no fixed `auth 0012`
  dependency, so it follows the swappable user model the Django way.
- Noted that the orchestrator's backwards-forwards check needs a superuser in the sample database.
- Migration test: use historical models only, and migrate to the leaf in `tearDown`, so it still
  works after #10 removes `Todo.owner`.
- Added `test_login_ignores_next_to_another_site` (open redirect) and
  `test_login_page_has_csrf_token` (the test client skips CSRF, so a missing token was untested).
- `test_list_shows_only_my_todos` now also checks the HTML, not only the context.
- Wrote down why session fixation is safe (`login()` makes a new session key) and why the CUJ
  cookie trick works (shared in-memory test database, cookie not secure-only in tests).
- Decided open questions: old to-dos go to the oldest superuser (no data loss); the "session
  ended, then pressed a button" 405 is left as it is; dark-mode order is solved by wave 0's
  `base.html`.
- Helpers use `get_user_model()`; checked that `TEST_PASSWORD` passes Django's password rules.
- `startapp` also makes a `migrations/` folder: delete it; add the `tests/__init__.py` files.

## Second review

What the second review changed, and why (each claim below was run against Django 5.2.17 in a copy
of the repo: the migrations, all the tests, and the CUJ with the session cookie):

- Migration test: the "no superuser" test now deletes its ownerless to-do; without that its
  `tearDown` re-ran `0003` and failed. A new `MigrationExecutor` per migrate; users made on the
  historical model.
- `0004`: `makemigrations ... --noinput`. Without it the command asks a question and crashes with
  `EOFError` when no person types an answer.
- Logout is marked `login_not_required`. Django does not mark it; before, "Log out" in a tab whose
  session had ended led to a 405 page after the next login. The URL-walk test keeps its name
  (`test_only_login_and_signup_are_open`, used by lists.md and sharing.md) and now expects
  `{"login", "logout", "signup"}`.
- Open redirect: the login test now tries `//evil.example/` and `/\evil.example/` too; logout
  with a foreign `next` is tested; sign-up ignores `next` (checked).
- Wrote down that sign-up shows when a username is taken (unavoidable), and login does not.
- Tests that redirect to `/` use `fetch_redirect_response=False`, so they survive #10 lists.
- Checked and kept: the admin behavior (`/admin/` → `/admin/login/`, `/admin/todos/todo/` →
  our login; a logged-in non-staff user is refused), the URL walk, a 404 for unknown addresses,
  CSRF on login, sign-up and logout (403 without the token), a new session key after sign-up,
  `TEST_PASSWORD` passing the password rules, and `log_in_as` in a real browser. The full suite
  also passes with `--parallel 4`.
- For #10 lists and #18 sharing: their assumptions (test name, helpers,
  `LOGIN_REDIRECT_URL = "todo_list"`, admin `owner`, `0004_alter_todo_owner`, leaf in `tearDown`)
  match this plan. Where they say the walk finds exactly `{login, signup}`, it is now
  `{login, logout, signup}`; nothing else changes for them.

## Decided by the person (2026-10-09)

The plan is **approved**.

- Sign-up stays open and there is no limit on wrong passwords for now. Before the site is public, close sign-up or add a limit, as its own task.

## Post-review check

- The orchestrator's `render_list_page` note was listed under "Decided by the person", but it was
  not the person's decision. Moved it here: the owner filter goes in wave 0's `render_list_page`,
  so the page after an invalid add is filtered too; test `test_invalid_add_shows_only_my_todos`.
- Step 6 still said only "change the four views". It now says the filter goes inside
  `render_list_page`, matching the file table.
