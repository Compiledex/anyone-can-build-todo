# Plan: Delete my account

Status: draft (2026-10-16)

Builds on: **accounts** (Django's `User`, login, sign-up, `LoggedInTestCase`), **lists** and
**sharing** (`TodoList.owner`, `members`, `visible_to`, "Leave this list"), **tags** (`Tag.owner`),
**subtasks**, **delete-undo** (the snapshot in the session), **backup-on-run** and **local-safety**
(`make backup`, `backups/`), and, from this round, **split-browser-tests** (the new CUJ file layout)
and **privacy-small-fixes** (`MESSAGE_STORAGE` = session storage).

## Words used in this plan

- **Cascade**: when a row is deleted, the database rows that point to it with
  `on_delete=CASCADE` are deleted too, and the rows that point to *those*, and so on.
- **Session**: the small store Django keeps on the server for one logged-in browser (here in the
  table `django_session`; `config/settings.py` sets no other `SESSION_ENGINE`). The browser only
  holds a random key in a cookie. One person who is logged in on two browsers has two sessions.
- **Flush**: empty a session and give it a new key. `logout()` does this.
- **Membership**: one row in the hidden table behind `TodoList.members`: "this user may see this
  list".

## What is wrong today

Facts, checked on `main` (commit `2c75b89`): there is no page to delete your own account. Only the
admin can delete a user at `/admin/` (`docs/design/data-inventory-and-privacy.md`, section 6 and
gap 1; `docs/product/prd.md`, open question 1; `docs/design/design-doc.md`, known limits).

## Goal

A logged-in person can delete their own account. A page first shows what will go: how many lists
and to-dos, which of their lists are shared (members will lose them), and how many lists shared
with them they will leave. It says this cannot be undone, and that copies in `backups/` still hold
the data. The person types their password and presses **Delete my account**. Then everything they
own is deleted, they are logged out, and they land on `/` with the message
"Your account was deleted."

## Decisions

### 1. What is deleted: Django's cascade, in one transaction

The view calls `user.delete()`. Every foreign key to `User` already says what happens (checked in
`todos/models.py` and Django 5.2's `django/contrib/admin/models.py`):

| Row | Points to | `on_delete` | After alice deletes her account |
|---|---|---|---|
| `TodoList` | `owner` → alice | CASCADE | Every list alice **owns** is deleted. |
| `Todo` | `todo_list` → her list | CASCADE | Every to-do in her lists is deleted (also to-dos that members added). |
| `Subtask` | `todo` → her to-do | CASCADE | Their steps are deleted. |
| `Todo.repeated_from` | another to-do | SET_NULL | A copy is always in the same list as its original (`make_next_copy`; a to-do never moves to another list: `todo_list` is not in any form), so both go. Through the app nothing outside her lists changes. Through `/admin/` a staff user could link a to-do in bob's list to one in hers; then bob's to-do only loses that link (SET_NULL). Nothing of bob's is deleted. |
| `Tag` | `owner` → alice | CASCADE | Her tags are deleted, and the tag links of her to-dos. `set_tags` always uses the **list owner's** tags, so through the app no to-do in someone else's list has one of alice's tags. If a staff user put one there in `/admin/`, bob's to-do only loses that tag link; the to-do stays. |
| `TodoList.members` rows where alice is a **member** | alice | (M2M, deleted) | Alice leaves every list shared with her. Those lists, their to-dos and their other members stay with their owners. |
| `TodoList.members` rows of alice's **own** lists | her list | (M2M, deleted) | Her members lose those lists (the lists are gone). Their own lists are not touched. |
| To-dos alice added to **bob's** list | bob's list | — | They stay: they belong to bob's list (as with "Leave this list" today). Their steps and (bob's) tags stay too. |
| `admin.LogEntry` (`django_admin_log`) made **by** alice | `user` → alice | CASCADE | Deleted by Django. Only a staff user has these. Log rows made by *another* admin about alice's things stay (the plan **admin-log-without-names** blanks their names). |
| `auth` group and permission links | alice | (M2M, deleted) | Deleted by Django. |

All of this runs inside one `transaction.atomic()` (with `transaction_mode: "IMMEDIATE"`, another
writing request waits). If anything fails, nothing is deleted.

No new code walks the tables by hand: `user.delete()` is Django's own cascade (rule "Use what
Django already has"). A test checks the exact rows that remain, so a later model with the wrong
`on_delete` is caught.

### 2. Every session of that user is deleted too

**Chosen: delete every session row whose `_auth_user_id` is alice's id, inside the same
transaction.** Reasons:

- A session of alice on another browser would stop working anyway (Django finds no user with that
  id and treats the browser as logged out). But the row stays in `django_session` until it expires
  and `clearsessions` runs, and it may hold an **undo snapshot** with the text of one of her
  to-dos (`todos/undo.py`). Her data should go with her account.
- `make run` runs `clearsessions` after privacy-small-fixes, but that only removes **expired**
  sessions; a two-week session of alice would stay.

How: a small function `delete_sessions_of(user)` in the new module `accounts/deletion.py`. It goes
through `Session.objects.iterator()`, reads each with `get_decoded()`, and **collects** the keys of
the rows where `get(SESSION_KEY) == str(user.pk)` (`SESSION_KEY` from `django.contrib.auth`). Only
after the loop it deletes them with one `Session.objects.filter(session_key__in=keys).delete()`,
inside the same `transaction.atomic()` as `user.delete()`. It never deletes while it iterates: on
SQLite, reads and writes on one connection are not isolated from each other, so a delete during
the loop could change what the loop still reads. This reads every session row; on one Mac that
is a handful of rows. A broken row decodes to `{}` and is skipped.

This only works with the database session engine. The module docstring says so. A test first
checks that `SESSION_ENGINE` is `django.contrib.sessions.backends.db` and that a second browser's
session row exists and decodes to alice, then that it is gone after the delete. If
`SESSION_ENGINE` ever changes, that test fails.

Not deleted: a snapshot in **another person's** session. If carol (a member of alice's list)
deleted a to-do there a minute ago, her Undo now says "Could not undo: you can no longer see the
list it was in." (the branch that exists in `todo_undo_delete`). Her snapshot leaves her session as
today (the next list page after 15 minutes, a new delete, logout, or `clearsessions` once it
expires). A test checks carol's Undo restores nothing.

### 3. The confirm page (GET) shows counts, list names of her own shared lists, no member names

`GET /accounts/delete/` shows (built by `account_summary(user)` in `accounts/deletion.py`, only from
`user.todo_lists` and `user.shared_lists`, never from `Todo.objects`):

- **Your lists**: "3 lists and their 12 to-dos (with their steps), and your 5 tags will be deleted."
  The to-do count comes from `user.todo_lists.annotate(todo_count=Count("todos", distinct=True),
  member_count=Count("members", distinct=True))`, summed in Python. The page needs about three queries in all (the own lists with their counts, the tags, the lists shared with her), whatever the number of lists. A person with no
  lists sees "You have no lists."
- **Your shared lists**: for each own list with members, its name and the number of members:
  "“Family” (2 members) — they will lose this list." In the list menu's order
  (`TodoList.Meta.ordering`: `created_at`, `pk`). **No member names.** The owner may already see their members on the
  list page, but this page does not need them, and a count is enough to decide. Less data on the
  page is the safer default. If none: the section is not shown.
- **Lists shared with you**: only a number: "You will leave 1 list that someone else shared with
  you. It stays with its owner, and the to-dos you added there stay in it." No list names and no
  owner names (not needed to decide).
- "This cannot be undone." and: "Copies in the `backups/` folder still hold your data. A daily copy
  is removed by itself after 14 newer ones; delete other copies by hand. If you may want your
  to-dos back, run `make backup` first." (The app only runs on the owner's Mac, so whoever reads
  this can run it.)
- The form: one field **Password** (`autocomplete="current-password"`), the danger button
  **Delete my account**, and **Cancel** (a link to `home`).

Template: `accounts/templates/registration/account_delete.html`, extends `base.html` (a
logged-in page), the field through `todos/_field.html`, styled with the classes that exist
(`page-form`, `form-actions`, `button button-danger`, `muted lead`). No new CSS.

### 4. POST checks the password; a wrong one changes nothing

`accounts.forms.DeleteAccountForm(NoColon, forms.Form)`:

```python
def __init__(self, user, *args, **kwargs): ...   # the view passes request.user
password = forms.CharField(
    label="Password",
    strip=False,
    widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
)
def clean_password(self):  # user.check_password(value), else:
    raise forms.ValidationError("Wrong password. Nothing was deleted.", code="wrong_password")
```

- Wrong or empty password: the page again with status 200, `Error: ` before the title and the
  focused `form-error-summary` line "Not deleted. Fix what is marked below." (the pattern of
  `list_form.html` and `todo_edit.html`). Nothing is deleted; the person stays logged in.
  `PasswordInput` never prints the typed value back.
- The form takes **only** `password`. The user always comes from `request.user`; any `username` or
  `user_id` in the POST is ignored. There is no id in the address, so there is nothing to guess.
- **Rate limiting is out of scope**: a person who is already logged in could try passwords here,
  as on the login page, which has no limit either. Data inventory gap 7 already lists "a
  password-attempt limit" for a server. The app runs only on the owner's Mac.

### 5. After the delete: log out, then add the message

Order inside the view, after the form is valid:

```python
user = request.user
with transaction.atomic():
    delete_sessions_of(user)   # also this browser's own session row
    user.delete()
logout(request)                # flushes this session, request.user = AnonymousUser
messages.success(request, "Your account was deleted.")
return redirect("home")
```

**Why the message survives**: `messages.success()` only puts the message in a queue in memory
(`request._messages`). It is written only when the response leaves the view, after `logout()`:
`MessageMiddleware.process_response` runs before `SessionMiddleware.process_response` (middleware
answer in the reverse order of `MIDDLEWARE`, and messages come after sessions there). So the flush
in `logout()` never touches it.

- With **session storage** (after privacy-small-fixes): the message goes into the new, empty
  session; the session is then not empty, so `SessionMiddleware` saves it with a new key and sets
  the cookie. The landing page reads and removes it. That session holds no user.
- With today's **fallback storage** (cookie first): the message goes into the messages cookie.

The message would survive also if it were added before `logout()`, for the same reason (the
queue is in memory, not in the session). The order above is only the plain reading order: first
the account goes, then the person is logged out, then they are told. It is not a safety rule. The
integration test runs with both storages (two `override_settings` test classes), so it passes
before and after privacy-small-fixes is merged.

`logout()` sends the `user_logged_out` signal with the deleted user object; nothing in this repo
listens to it. The session sweep already deleted this browser's own session row; `flush()` then
deletes a row that is gone, which Django allows.

Redirect to `home` (`/`): logged out, it renders `todos/landing.html` through `site_base.html`,
which shows Django's messages in `role="status"`. The landing page still gets no database data.

### 6. Methods, login and CSRF

- `@require_http_methods(["GET", "HEAD", "POST"])` (HEAD like the sign-up page). GET and HEAD
  only show the page; a `?password=...` in the address is ignored. PUT, PATCH, DELETE: 405.
- **Not** `@login_not_required`: `LoginRequiredMiddleware` sends a visitor to
  `/accounts/login/?next=/accounts/delete/`. The open views stay `login`, `logout`, `signup` and
  `home`; `test_only_landing_login_and_signup_are_open` is **not** changed.
- CSRF: the form has `{% csrf_token %}`; Django's `CsrfViewMiddleware` refuses a POST without it
  (403), so another site cannot make a logged-in browser delete its account.
- The `GET` page sends no "next" and the view follows none: after the delete it always goes to
  `/` (no open redirect).

### 7. Staff and superusers may delete themselves

**Recommended: allow it, with no special case.** On this Mac the owner can make a new admin at
any time with `uv run python manage.py createsuperuser` (README, step 4). Blocking "the last superuser"
would add a rule and a test for a case the owner can fix in one command. The page adds one line
for a staff user only: "You are an admin. After this, make a new admin with
`uv run python manage.py createsuperuser` if you need `/admin/`." (Open question 1.)

### 8. The link in the header

In `base.html`, inside `.user`, between "Logged in as …" and the **Log out** form: a link
`<a class="button button-secondary button-compact" href="{% url 'account_delete' %}">Delete account</a>`.

- Its accessible name is its visible text, "Delete account" (no `aria-label` needed; it names no
  to-do).
- The same classes as Log out, so under a finger (`pointer: coarse`) it gets the 44px height and
  8px gap from `app.css`. No new CSS.
- It is only a link to the confirm page, so a mis-tap deletes nothing.
- On a 375px phone the header has the word mark, the name, and two small buttons; `.who` already
  wraps (`overflow-wrap: anywhere`). The CUJ test checks the link is visible at phone width.
- "Delete account" rather than "Account": the page does only one thing, and the person should know
  that before opening it. (Open question 2.)

### 9. Reminders

If the person had set up the launchd job (`deploy/macos/...plist`) for this username,
`send_reminders --user <name>` now stops with `No active user named "<name>".` and shows nothing.
The page does not mention it (reminders are off by default); the README line for reminders gets
one sentence: "If you delete that account, remove the launchd job too." The AI never touches
launchd.

## Security

- **Only my data**: the view acts only on `request.user`; there is no id in the address and the
  form has no user field. Rule 5 ("another user gets 404") has nothing to point at; instead a test
  checks that bob's POST (with bob's password) deletes bob and leaves every row of alice.
- **Other users' data**: lists alice is a member of stay with their owners (only the membership
  row goes); a test checks bob's list, its to-dos (also the one alice added), steps and tags stay.
- **Members do not learn each other**: the page shows the owner no member names, and shows nothing
  to members. A member of a deleted list simply no longer sees it (404, as for any list that does
  not exist).
- **GET never deletes**, CSRF on POST, login required, no redirect target from the request.
- **Password**: checked with `user.check_password` (Django's own, constant-time compare), never
  logged, never printed back, never in an address. Rate limiting: out of scope (decision 4).
- **Leftover data**: sessions of the user deleted (decision 2). Backups keep the data, and the page
  says so. Another person's undo snapshot of a to-do from her list stays in *their* session for at
  most its normal life (decision 2).

## Data and migrations

No model change, no migration. Existing rows are untouched until a person deletes their account.
There is no way back except a copy in `backups/` (the page says so and suggests `make backup`).
Going back on the code: remove the view, URL, form, template, link and module; no data to undo.

## Working next to

This round's build order: wave A (split-browser-tests, readme-to-runbooks, privacy-small-fixes,
admin-log-without-names) builds in parallel with this plan; merge order split-browser-tests →
readme-to-runbooks → privacy-small-fixes → admin-log-without-names → **delete-account (last)**.

- **split-browser-tests**: this plan's CUJ test is a **new file**
  `todos/tests/cuj/test_account_journeys.py` in that layout (coordinator's decision: a new file,
  not `test_auth_pages.py`). It imports only from `todos/tests/cuj/helpers.py` (made by
  split-browser-tests) or `todos/tests/cuj/browser.py`, never from another journey file. Expected
  CUJ count after the merge: 31.
- **privacy-small-fixes**: sets `MESSAGE_STORAGE` to session storage and runs `clearsessions` from
  `make run`. Decision 5 is designed for session storage, and the test runs with both storages.
  After the rebase, run the message test again with the real setting.
- **admin-log-without-names**: no shared code. Its data inventory gap 6 and this plan's gap 1 are
  different lines in the same file; on conflict keep both. Its LogEntry rows *by* the deleted user
  go by cascade either way.
- **readme-to-runbooks**: moves the README's reminders section into `docs/runbooks/reminders.md`.
  The one sentence of decision 9 goes wherever that section is on main at rebase time.
- Shared files: `AGENTS.md` (rows), `CHANGELOG.md`, `docs/design/data-inventory-and-privacy.md`,
  `docs/design/design-doc.md` (known limits table), `docs/product/prd.md`, `README.md`. Rebase on
  main right before the PR and keep every other plan's lines.

## Not part of this task

- A password-attempt limit (data inventory gap 7).
- An "export my data" page.
- Deleting the user's data from `backups/` (the page explains it instead).
- A way to give an own shared list to a member before deleting (the owner chose: it is deleted).
- Deleting another user (the admin can, as today).
- An email or notice to members who lose a list.
- A grace period or "undo" for the account delete.

## Changes to files

| File | Change |
|---|---|
| `accounts/deletion.py` (new) | `account_summary(user)` (the counts and own shared lists for the page) and `delete_sessions_of(user)`. Docstring: database sessions only. |
| `accounts/forms.py` | `DeleteAccountForm(NoColon, forms.Form)`: `password`, checked in `clean_password` with `check_password`. |
| `accounts/views.py` | `account_delete`: GET/HEAD show the page, POST checks, deletes in one transaction, logs out, then adds the message, redirects to `home`. |
| `accounts/urls.py` | `path("delete/", views.account_delete, name="account_delete")`. |
| `accounts/templates/registration/account_delete.html` (new) | The confirm page (decision 3), extends `base.html`. |
| `todos/templates/base.html` | The "Delete account" link in `.user`, before Log out. Its comment names the new page. |
| `accounts/tests/unit/__init__.py`, `accounts/tests/unit/test_delete_account_form.py` (new) | The form on its own (no database). |
| `accounts/tests/integration/test_delete_account.py` (new) | The integration tests below. |
| `todos/tests/cuj/test_account_journeys.py` (new) | The one browser journey. |
| `AGENTS.md` | "What this is": a person can delete their own account (what goes, what stays). Rows: `accounts/` (no models; plus delete account), `accounts/forms.py` (`DeleteAccountForm`), `accounts/urls.py`/`views.py` (`account_delete`: GET, HEAD, POST; a delete in one transaction with the user's sessions, then logout, then the message), new row `accounts/deletion.py`, `accounts/templates/registration/` (the delete page extends `base.html`, not `site_base.html`), `base.html` (the header link), `todos/tests/cuj/` (the new file). The open-views list in Rules stays `login`, `logout`, `signup`, `home`. |
| `docs/design/data-inventory-and-privacy.md` | Section 6 row "Delete an account": the page, what goes (also sessions), what stays. Section 7 gap 1: marked closed, with a link to this plan. Retention row for accounts. Retention row for sessions: after the delete, the new session that only carried the message is empty once the landing page has read it; that empty row stays in `django_session` until `clearsessions` runs. |
| `docs/design/design-doc.md` | Remove the known-limit row "No "delete my account" page"; one line in 7.7 (lists, sharing) on what happens to shared lists. |
| `docs/product/prd.md` | Open question 1: answered (yes, with this plan). |
| `CHANGELOG.md` | A new version: Added "Delete your own account", Security "its sessions go too". |
| `README.md` | "Private by default": one sentence, "You can delete your account (Delete account at the top); your lists and to-dos go with it." Reminders section: decision 9's sentence. |
| `docs/plans/README.md` | The row for this plan, when it is done. |
| `docs/plans/delete-account.md` | Status line on the implementer's last commit. |

## Steps

1. Rebase check: note which of wave A is already on main (the CUJ layout, `MESSAGE_STORAGE`).
2. Write the tests first (all files in "Tests"); run them and show them failing (no URL
   `account_delete`).
3. `accounts/forms.py`: `DeleteAccountForm`. Run the unit tests: green.
4. `accounts/deletion.py`: `account_summary`, `delete_sessions_of`.
5. `accounts/views.py` and `accounts/urls.py`: `account_delete` exactly as decision 5, with the
   comment "The message is written after the view, so logout() does not remove it."
6. The template and the header link.
7. Docs (the table above), `AGENTS.md` rows.
8. `make check` (all three layers green; the CUJ count goes from 30 to 31, the unit and integration
   counts by the new tests). Then the Status line commit.

## Tests

The world for the integration tests (`DeleteAccountTests(LoggedInTestCase)`, in
`setUpTestData`): alice (logged in) owns "Inbox" (helper) with "Buy milk" (one step, alice's tag
"home") and "Family", shared with **carol**, with "Plan trip". **bob** owns "Bob's list" (helper),
shared with alice; in it "Alice's idea" (added by alice, one step, bob's tag "work") and "Bob's
own". carol owns "Carol's list". Every test counts rows per table before and after.

### Integration — `accounts/tests/integration/test_delete_account.py`

| Test | Checks |
|---|---|
| `test_page_shows_what_will_be_deleted` | GET: 200, "2 lists", "2 to-dos", "1 tag"; "“Family” (1 member)"; "You will leave 1 list"; "cannot be undone"; `make backup`; the `backups/` sentence; a password field with `autocomplete="current-password"`; a CSRF token. |
| `test_page_names_no_member_and_no_other_list` | In this test the member and the other owner have names that cannot appear in a CSRF token or in markup (for example "Zoë-member" and "Øystein-owner", and the list "Øystein's list"). The page's **visible text** (`parse_page`, all text nodes joined) contains neither name nor the list name; a raw check uses `django.utils.html.escape(...)` of each, so an escaped apostrophe cannot make it pass by accident. The "something shows" side: the same text does contain "Family". |
| `test_page_for_a_person_with_no_lists` | A new user with no lists: "You have no lists.", no shared-lists section; the form is there. |
| `test_get_and_head_delete_nothing` | GET (also `?password=<right>`) and HEAD: every row count unchanged, alice still logged in. |
| `test_other_methods_are_405` | PUT, PATCH, DELETE: 405, nothing deleted. |
| `test_anonymous_goes_to_login` | Logged out, GET and POST: redirect to `/accounts/login/?next=/accounts/delete/`; no user deleted. |
| `test_post_without_csrf_token_is_403` | `Client(enforce_csrf_checks=True)`, logged in, right password, no token: 403, alice exists. |
| `test_wrong_password_deletes_nothing` | 200, "Wrong password. Nothing was deleted.", `Error: ` in the title, the summary line; every row count unchanged; still logged in. |
| `test_empty_password_deletes_nothing` | Every row count unchanged, still logged in. (The error text is checked in the unit test.) |
| `test_right_password_deletes_exactly_alices_rows` | (The "something happens" case of the two above.) alice is gone; "Inbox" and "Family", their to-dos, steps and alice's tags are gone; bob, carol, "Bob's list" with "Alice's idea" (its step and its tag "work") and "Bob's own", bob's tags, "Carol's list" all remain; exact row counts per table. |
| `test_lists_shared_with_her_lose_only_her` | `bob_list.members` no longer has alice; its other data unchanged. |
| `test_member_loses_her_shared_list` | carol: GET the old "Family" address is 404; carol's `visible_to` is only "Carol's list"; `/` sends carol to her own list. |
| `test_logged_out_with_message_on_landing` | Redirect to `/`; following it renders `todos/landing.html` with "Your account was deleted." inside `role="status"`, no "Logged in as"; `_auth_user_id` not in `client.session`. Written in a mixin `MessageAfterDeleteChecks`, run by two classes: `MessageAfterDeleteFallbackTests` with `override_settings(MESSAGE_STORAGE="django.contrib.messages.storage.fallback.FallbackStorage")` and `MessageAfterDeleteSessionTests` with `...session.SessionStorage` (not `subTest`: the database is only rolled back per test method, and the first delete would leave nothing to delete). |
| `test_message_is_shown_once` | A second GET of `/` has no "Your account was deleted." |
| `test_her_other_sessions_are_deleted` | `settings.SESSION_ENGINE` is the db backend. A second client logged in as alice (another browser), and bob logged in; **before** the delete, the second client's session row exists and decodes to alice's id. After the delete, no `Session` row decodes to alice's id; the second client's `/` is the landing page; bob's session row still exists and bob is still logged in. |
| `test_failed_delete_changes_nothing` | `User.delete` patched to raise: the POST raises (or 500); every row count is unchanged, and alice's second session row still exists and decodes to her (the session sweep was rolled back with the transaction). |
| `test_her_admin_log_rows_go` | One `LogEntry` by alice and one by bob: after the delete only bob's remains. |
| `test_bob_deletes_only_bob` | bob's client posts bob's password (and an extra `username=alice`): bob, "Bob's list" (with "Alice's idea") and bob's tags are gone; alice, "Inbox", "Family", their to-dos, steps and alice's tag stay; carol is untouched. |
| `test_staff_user_can_delete_themselves` | A superuser with lists: right password deletes them (decision 7); the admin line is on their GET page and not on alice's. |
| `test_members_undo_after_the_list_is_gone` | carol deletes "Plan trip" (snapshot in her session), alice deletes her account, carol posts Undo: "Could not undo: you can no longer see the list it was in.", no to-do made. |
| `test_header_has_delete_account_link` | On a list page: a link to `/accounts/delete/` with text "Delete account", placed before the Log out form. |

### Unit — `accounts/tests/unit/test_delete_account_form.py` (`SimpleTestCase`)

An unsaved `User(username="alice")` with `set_password(TEST_PASSWORD)` (no database).

| Test | Checks |
|---|---|
| `test_right_password_is_valid` | `is_valid()` is True. |
| `test_wrong_password_is_invalid` | False, the error text, code `wrong_password`. |
| `test_empty_password_is_invalid` | False, "This field is required.". |
| `test_password_is_not_stripped_or_rendered` | `" " + password` is wrong (no strip); the bound form's HTML does not contain the typed value (the one place this is checked); the label is "Password" without a colon. |

### CUJ — `todos/tests/cuj/test_account_journeys.py` (`DeleteAccountJourney(BrowserTestCase)`)

| Test | Checks |
|---|---|
| `test_delete_my_account` | alice logs in (a list shared with bob, who has his own list); at 375px width "Delete account" is visible in the header; she opens it, sees the counts and the shared list, types a wrong password and sees the error, then the right one, presses **Delete my account**, lands on `/` with "Your account was deleted.", and logging in as alice again fails. bob, in a second browser context, reloads and no longer sees alice's list, but still has his own. |

## Open questions

1. **May a staff user or the last superuser delete themselves?** Recommended: yes, no special
   case, with the one admin line on the page (decision 7). The other choice: refuse while they are
   the only active superuser.
2. **The header link's text: "Delete account" or "Account"?** Recommended: "Delete account"
   (decision 8). "Account" would fit better if a later page adds more (change password, export).
3. **Show member names on the page?** Recommended: no, only the number of members per own shared
   list (decision 3). The owner may already see them on the list page, so showing them would be
   allowed, but it is not needed to decide.

## Review

Plan review (2026-10-16): APPROVE WITH CHANGES. All findings applied:

1. Decision 5 said a message added before `logout()` would be lost. That was wrong: messages wait
   in memory and are written after the view. The order stays (it reads naturally), but it is no
   longer called a rule; the reason, the step 5 comment and the `AGENTS.md` row text are fixed.
2. The message test used `subTest` per storage, which cannot work (the database is rolled back
   per test method, not per sub-test). Now a mixin run by two `override_settings` classes.
3. `delete_sessions_of` deleted while iterating; on SQLite one connection sees its own writes
   during a read. Now it collects the keys, then deletes them in one query, in the same
   transaction.
4. The other-sessions test could pass without checking anything. It now first checks the engine
   and that the second session row exists and belongs to alice.
5. The "no names" test was a tautology ("Bob's list" is escaped in HTML) and "bob" could appear
   in a CSRF token. Now it checks the visible text, with names that cannot be in a token.
6. Decision 1 said nothing outside her lists changes. True through the app; through `/admin/` a
   staff user could link across lists. Now it says so, and that bob's row only loses the link.
7. New test: a failed `user.delete()` changes no row and keeps her other session.
8. Each rule tested once: "This field is required." and "not rendered" only in the unit test.
9. Decision 3 said "one query"; it is about three.
10. The CUJ journey is a new file `todos/tests/cuj/test_account_journeys.py`, imports only from
    `helpers.py` or `browser.py`; the CUJ count becomes 31.
11. The data inventory retention row now says the empty session row left after the message stays
    until `clearsessions` runs.

## Decided by the person

(Filled in after the plan card.)
