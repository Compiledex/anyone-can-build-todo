# Design of the to-do list

This document explains the big picture of the app and **why** it is built the way it is. It is
for a new developer or AI agent, and for the owner of the project.

- For the job and the rules of each file, read [`AGENTS.md`](../AGENTS.md). When this document
  and `AGENTS.md` disagree about a file rule, `AGENTS.md` wins (and this document should be
  fixed).
- For what was decided for each feature, and why, read the plans in [`docs/plans/`](plans/).
  They are history: they say what was decided then, not how the code is now.
- For how to install and run the app, read [`README.md`](../README.md).

Technical words are explained the first time they appear, and again in the
[Glossary](#14-glossary) at the end.

## 1. Summary

The app is a small to-do list, built with **Django** (a Python framework for websites). A person
makes an account, keeps several lists, and adds to-dos to them. A to-do can have a due date, a
priority, tags, notes, steps, and a repeat rule. The owner of a list can share it with other
users.

| Question | Answer |
|---|---|
| Who uses it? | The owner of the project, and a few people they share lists with. |
| Where does it run? | Only on the owner's Mac, at <http://127.0.0.1:8000>. It is not deployed to a server. |
| Where is the data? | In one SQLite file, `db.sqlite3`, next to the code. It is not in git. |
| How big is it? | 16 Python files in `todos/`, 22 migrations, 731 tests. |
| Status | All planned features are built and merged (33 plans, PR #1 to #52). |
| Date of this document | 2026-10-16 (Tokyo time), written against `main` at `c0401bc`. |

The README also explains how to put the app on a host. The settings are ready for it (see
[Operations](#10-operations)), but the owner chose to run it locally. Before going public, some
work is still needed (see [Known limits](#13-known-limits-and-possible-future-work)).

## 2. Goals and non-goals

### Goals

- **Simple and correct.** Every feature is small, and every rule has a test.
- **Private by default.** Every page needs a login. A person sees only their own lists and the
  lists shared with them.
- **Safe with data.** A delete can be undone for 15 minutes, a list delete asks first, and
  `make run` makes a daily backup.
- **Easy to read.** Plain server-rendered HTML, almost no JavaScript, short functions with
  docstrings in plain English.
- **Works for Norwegian text.** Sort and search handle æ, ø and å correctly.
- **Accessible.** Good contrast in light and dark mode, big touch targets, buttons with clear
  names for screen readers.

### Non-goals

Each line below was decided on purpose. The plan that decided it is in brackets.

| Not a goal | Why |
|---|---|
| Deployment to a server | The site runs locally on the owner's Mac (reminders, decided 2026-10-10). |
| Real-time updates between people | Each page is loaded fresh. A member sees a change after a reload. Simple, and enough for a few people. |
| A warning when two people edit the same to-do | The last Save wins. The owner decided against a warning (safe-toggles "Left for the person"; product choices of 2026-10-11). |
| Accent-insensitive search ("e" finds "é") | For a Norwegian, "o" and "ø" are different letters, so it would give wrong matches (nordic-letters). |
| Full dictionary sort order (CLDR) | A simple rule is enough: a to z, then æ, ø, å (nordic-letters). |
| A light/dark toggle button | The app follows the system setting only (dark-mode). |
| Email (password reset, reminders) | No email at all. Reminders are Mac notifications (reminders). |
| Reminders switched on | The code is there, but the owner chose not to turn it on. It needs a manual launchd setup (reminders). |
| A limit on wrong passwords, closed sign-up | Not needed on a local Mac. Must be done before the site is public (accounts). |
| Soft delete (a hidden "deleted" flag) | A snapshot in the session was chosen for Undo instead: no migration, no query changes (delete-undo). |

## 3. Users and main journeys

| Who | What they can do |
|---|---|
| **Visitor** (not logged in) | Sees the landing page at `/`, with screenshots of the app. Can create an account or log in. Sees no user data. |
| **Owner** of a list | Everything: add, edit, mark done, delete to-dos; clear the done ones; rename, delete and share the list; see and remove members. |
| **Member** of a list | Sees the list and changes its to-dos: add, edit, done, delete, clear done, reorder. Can leave the list. Cannot rename, delete or share it, and cannot see the other members. |

The main journeys (each one has a CUJ test in a real browser):

1. Sign up. The first list, "Inbox", is already there.
2. Add a to-do, mark it done, undo that, delete it, undo the delete.
3. Make a to-do repeat weekly; mark it done; the next copy appears with a new date.
4. Search, filter (All, Not done, Done) and sort a list.
5. Put to-dos in your own order by drag and drop, or with the Move buttons.
6. Share a list with another username; that person finds it under "Shared with me".

## 4. Architecture

### The big parts

The app is a **monolith**: one Django project, one process, one database. There is no separate
frontend and no API.

| Part | What it is | Why |
|---|---|---|
| Django 5.2 | The web framework: addresses, views, forms, templates, admin, accounts. | It already has login, forms, the admin and a test client, so we write less code. |
| Server-rendered templates | Each page is HTML made on the server. Forms post to the server, which answers with a redirect. | Simple, works without JavaScript, easy to test with Django's test client. |
| One small script, `reorder.js` | Drag and drop for the manual order. | The only thing HTML cannot do alone. The Move buttons do the same without JavaScript. |
| SQLite | The database, one file. | No server to install. Enough for one Mac and a few people. |
| WhiteNoise | Serves the CSS, JavaScript and pictures. | Needed only on a host; harmless on the laptop. |
| uv | Installs Python and the packages from `uv.lock`. | The same versions everywhere. |

There are two Django **apps** (folders with their own models, views and templates):

- `accounts/`: sign up, log in, log out. It uses Django's own `User`. No models of its own.
- `todos/`: everything else: lists, to-dos, tags, steps, the landing page, backups, reminders.

`config/` holds the settings, the main addresses, and the test runner.

### How a request flows

A **request** is what the browser sends; a **response** is what the server sends back.
**Middleware** is code that runs before and after every view.

```
 Browser
   |  GET /lists/3/          or   POST /7/toggle/  (done=1, next=/lists/3/#todo-7)
   v
 Middleware (config/settings.py MIDDLEWARE)
   - sessions, CSRF check (POST only), authentication
   - LoginRequiredMiddleware: no login -> redirect to /accounts/login/
   v
 config/urls.py -> todos/urls.py -> one view in todos/views.py
   |  1. find the object through visible_to / get_visible_todo (else 404)
   |  2. GET: read and render a template
   |     POST: check the form, change the database inside transaction.atomic()
   v
 Models (todos/models.py) --SQL--> SQLite (db.sqlite3)
   |      + Python functions in SQLite: casefold(), "norwegian" collation
   v
 GET:  HTML from todos/templates/ (base.html + the page)
 POST: 302 redirect back to the list (to "next" when it is safe), plus a message
```

Every change uses **POST**, and every POST ends with a **redirect** to a normal page
("Post/Redirect/Get"). So a reload never sends a form twice. The only exception is the
drag-and-drop save, which answers `204 No Content` to the script.

### Why SQLite with `IMMEDIATE` transactions

A **transaction** is a group of database changes that happen all together or not at all.
SQLite allows only one writer at a time. In its normal mode, a transaction takes the write lock
late, and a second request can fail with "database is locked". With
`"transaction_mode": "IMMEDIATE"` (in `config/settings.py`), a transaction takes the lock at the
start, so a second request **waits** instead of failing. Django recommends this for SQLite
websites.

This is what makes the "read, then write" views safe: Toggle, Delete, Undo-delete, Edit and Move
read the row **inside** `transaction.atomic()`. A second click at the same time waits, then sees
the new value.

### Python functions inside SQLite

SQLite's own `LOWER()` and `LIKE` only know A to Z. So `todos/sqlite_functions.py` adds two
Python functions to every SQLite connection (through a Django signal in `TodosConfig.ready()`):

- `casefold(text)`: the text in one case, for every letter. Used by search.
- the `norwegian` **collation** (a rule for sorting text): a to z, then æ, ø, å. Used only for
  "Sort by Title".

Why not a stored column? It needs no migration and nothing to keep up to date (nordic-letters).
The cost: any tool that opens `db.sqlite3` without these functions cannot run those queries. That
is why the collation is **only** used for `ORDER BY`, never in a database rule (see
[why `name_key` exists](#why-each-important-field-exists)).

## 5. Data model

### Tables

| Table | Key fields | Rules and notes |
|---|---|---|
| `User` | Django's own. | Accounts. No custom user model. |
| `TodoList` | `owner`, `name`, `name_key`, `created_at`, `members` | `name_key` is `casefold(name)`, set by `save()`. Unique per owner: `unique_list_name_key_per_owner`. Ordered by `created_at`, `pk`. |
| `TodoList.members` | many-to-many to `User` | The people the list is shared with. The owner is never a member. |
| `Todo` | `todo_list`, `title`, `done`, `created_at`, `due_date`, `description`, `priority`, `repeat`, `position` | Belongs to exactly one list. Its owner is `todo.todo_list.owner`. |
| `Todo.repeated_from` | one-to-one to `Todo` | On a recurring copy: the to-do it was copied from. `SET_NULL` when that one is deleted. |
| `Todo.copy_fingerprint` | 64 hex characters | On a copy: a hash of what the copy looked like when it was made. Not editable. |
| `Todo.reminded_on` | date | The day this to-do was last in a Mac notification. Not editable. |
| `Tag` | `owner`, `name` | Unique per owner (`unique_tag_name_per_owner`). Lower case, no `#`. |
| `Todo.tags` | many-to-many to `Tag` | Always the **list owner's** tags, also when a member edits. |
| `Subtask` ("step") | `todo`, `title`, `done`, `created_at` | No owner and no list of its own. Deleted with its to-do. |

```
   User 1 ──────< owns >────── * TodoList * ──< members >── * User
     |                              |
     | 1                            | 1
     |                              |
     * Tag * ──────< tags >─────── * Todo 1 ────────────── * Subtask
                                    |  ^
                                    |  | repeated_from (one-to-one,
                                    +--+  at most one next copy)
```

(`1` and `*` mean "one" and "many". `──<` reads "has".)

### Why each important field exists

- **`name_key` and its unique rule.** Two lists of one owner may not have the same name,
  ignoring case for every letter ("Ærend" and "ærend"). The key is made in Python by `save()`,
  so the database rule is a plain `=` that works with every SQLite tool, also without the custom
  functions (list-name-casefold). This is why a name must never change without `save()`.
- **`position`.** The manual order. It belongs to the list, so everyone sees the same order.
  A new to-do goes last (`Todo.save()` does it, so the add view, recurring copies and the admin
  all get it). Numbers do not have to be unique or without gaps; ties are broken by
  `created_at`, then `pk`.
- **`repeated_from` as one-to-one.** The database itself allows at most one next copy per
  to-do. A double click can never make two copies.
- **`copy_fingerprint`.** Lets Undo see whether someone changed the copy (see
  [Recurring copies](#recurring-to-dos)).
- **`reminded_on`.** So a to-do is shown in a notification at most once a day.
- **Tags per owner.** A member who types `#work` on a shared list adds the owner's `work` tag,
  never their own, so tags never leak between users.
- **`priority` as numbers** (1 Low, 2 Medium, 3 High). Sorting by `-priority` gives High first.
- **`repeat` "" for Never**, not `NULL`, so the form's select needs no empty line.

### Migration history

A **migration** is a file that changes the database tables step by step. Django makes most of
them from `models.py`. A **data migration** changes rows instead of tables, and is written by
hand. There are 22 migrations in `todos/migrations/`:

| Migrations | What they did |
|---|---|
| 0001 | The first `Todo` table. |
| 0002-0004 | Accounts: a to-do got an owner. **0003 is a data migration**: old to-dos go to the oldest admin. |
| 0005-0007 | Lists. **0006 is a data migration**: every user gets an "Inbox" list with their to-dos. 0007 makes the list required and removes the old owner field. |
| 0008, 0010, 0011 | Due date, notes (`description`), priority. |
| 0009 | Sharing (`members`). |
| 0012, 0013 | Tags, steps. |
| 0014 | Recurring (`repeat`, `repeated_from`). |
| 0015-0016 | Manual order. **0016 is a data migration**: numbers each list's to-dos in the order they were made. |
| 0017 | `reminded_on`. |
| 0018 | Ordering tie-break (`created_at`, then `pk`). |
| 0019-0021 | List names unique ignoring case. **0020 is a data migration**: fills `name_key`, and renames a clashing name to "<name> (2)", "(3)", and so on. 0021 swaps the old A-to-Z rule for the new one. |
| 0022 | `copy_fingerprint`. |

Some migrations are a **set** that must stay together (0005-0007, 0015-0016, 0019-0021). Never
edit a migration by hand, except a data migration.

## 6. Access control

**Access control** decides who may see and change what. The rules are in `AGENTS.md` ("Only my
data, plus what is shared with me"). Here is why they look the way they do.

### Login on every page

Django's `LoginRequiredMiddleware` sends every visitor who is not logged in to the login page.
A view must opt **out** with `@login_not_required`. So a new page is private by default, and a
forgotten decorator fails safe.

Only four views are open: `login`, `logout`, `signup` and `home` (`/`). A test
(`test_only_landing_login_and_signup_are_open`) lists them, so a new open view must be added there
on purpose. `home` shows the landing page to a visitor and renders it with **no** database data;
a logged-in person is sent on to their first list.

### Four ways to find a thing

| Helper | Gives | Used by |
|---|---|---|
| `TodoList.objects.visible_to(user)` | The lists the user owns plus the lists shared with them. | Every list view for owner and members. |
| `get_visible_todo(user, pk)` / `get_visible_subtask(user, pk)` | A to-do or step in such a list, or 404. | Every to-do and step view. |
| `get_object_or_404(TodoList, pk=pk, owner=request.user)` | Only the owner's own list. | Rename, delete, share, remove member. |
| `get_object_or_404(TodoList, pk=pk, members=request.user)` | Only a list the user is a member of. | Leave. |

Why one helper and not a filter in each view? One place to get right, and one place to test.
`visible_to` uses `distinct()`, because the join with the members table would give the owner one
row per member, and `get_object_or_404` would then fail.

### 404, not 403

Someone else's list gives **404 Not Found**, exactly like a list that does not exist. A **403
Forbidden** would tell a stranger that the list exists. A member who tries an owner-only action
gets the same 404 as a stranger. Even "remove member" looks the member up only among the list's
members, so the answer never tells whether a user number exists.

Every view has a test that another user gets 404 and that nothing changed
(`assertOtherUserGets404`).

### What the views never trust

- The list of a new to-do comes from the address, never from the form
  (`todo.todo_list = the_list`).
- The owner of a new list is set in the view.
- A posted `next` address is followed only when it is a path on this site (see
  [Safe redirects](#safe-redirects-and-anchors)).
- A sort order from the address is only a key in an allow-list (see [List page](#the-list-page-query)).

### The reminders exception

`todos/reminders.py` filters to-dos by `todo_list__owner`, not by `visible_to`. This is on
purpose: `reminded_on` is one date per to-do, so only one person (the list owner) can be reminded
of it. It is not a view, and views never do this.

## 7. Key behaviours and their design

### Recurring to-dos

A to-do can repeat daily, weekly or monthly. It needs a due date (`Todo.clean()`, checked only in
forms).

**Done makes the next copy.** `Todo.make_next_copy(today)` is the one place that makes a copy:

- The new due date comes from `next_due_date` (`todos/recurrence.py`): the first date in the
  series that is **strictly after today**. A late daily to-do done today gets a copy due
  tomorrow, not today (decided by the owner, recurring). It uses arithmetic, not a loop, so a
  very old date is as fast as a new one.
- Monthly on the 31st gives the last day of a shorter month, and then stays there
  (31 Jan, 28 Feb, 28 Mar). The owner accepted this.
- The copy keeps the fields in `COPIED_FIELDS` (title, notes, priority, repeat), the same tags,
  and the same steps (not done). It never copies `reminded_on`.
- It makes nothing when a copy already exists (the one-to-one rule), or when there is no next
  date (after the year 9999).

**Undo removes the copy, unless it holds work.** Undo on the original removes the copy, except
when:

| The copy... | Result |
|---|---|
| is already done, or is in another list | Kept, no message. |
| has a done step | Kept: "The next copy, due ..., was kept, because a step in it is already done." |
| was changed after it was made | Kept: "... because it was changed after it was made." |
| none of the above | Removed: "The next copy, due ..., was removed." |

**How "changed" is detected: a fingerprint.** When the copy is made, a SHA-256 hash of its
title, notes, priority, repeat, due date, tag names and step titles is stored in
`copy_fingerprint`. Undo computes the hash again and compares. Why a hash and not an "edited"
flag? A flag must be set by every view that edits (and the admin, and future views), and it
counts a change that was changed back. A hash sees every change, from anywhere
(recurring-copy-rules). Copies made before this field existed have no hash, and count as
unchanged.

If the shape of the hash changes, `FINGERPRINT_VERSION` changes too. Then every old copy counts
as changed, so Undo keeps it: no data is lost.

**Turning on Repeat for a done to-do** (in Edit) makes the next copy at once, with the message
"Made the next copy, due ...".

### Delete with Undo

Delete removes the to-do from the database at once. An "Undo" button in the message can bring it
back for 15 minutes.

**Why a session snapshot, not a soft delete?** A soft delete (a "deleted" flag) would need a
migration and a new filter in every query that reads to-dos. Forgetting one filter would show
deleted to-dos. A **snapshot** in the **session** (data the server keeps for one logged-in
browser) needs neither (delete-undo).

How it works (`todos/undo.py`):

1. Before the delete, `take_snapshot` copies every field (`SNAPSHOT_FIELDS`), the tag names, the
   steps with their done state, and the id of its next copy into plain JSON data.
2. The snapshot goes in `request.session["undo_delete"]`. Only the last delete is kept.
3. The "Deleted" message carries the id (`undo-delete-<id>`). Only the message whose id matches
   the snapshot shows an Undo button, so a button always undoes what its message says.
4. `restore` makes the to-do again **with its old id**, its old `created_at` and `position`, the
   list owner's tags, its steps, and its recurring links where they are still free.

The rules:

| Situation | Result |
|---|---|
| Another user, an older delete, after logout | 404 (only the last delete of this user). |
| Undo clicked twice | The second click finds the row back already and does nothing. |
| More than 15 minutes | "Too late to undo: the to-do stays deleted." |
| The list is gone, or the person lost access | "Could not undo: you can no longer see the list it was in." |
| The id now belongs to another to-do | "Could not undo." The other to-do is not touched. |

**Race handling.** The session is saved after the view, outside the database transaction, so two
quick Undo posts can both read the snapshot. The real guard is the "does a row with this id
exist?" check **inside** the transaction. Delete also reads the to-do inside its transaction, so
a second Delete at the same time gets 404 instead of overwriting the good snapshot with a broken
one.

`SNAPSHOT_FIELDS` must list every `Todo` field. A unit test checks it, so a new field cannot be
forgotten.

### The list page query

The list page reads `q` (search), `status` (filter) and `sort` from the address, through
`TodoQueryForm`. A bad value is simply ignored (the default is used), with no error page.

| Feature | Design | Why |
|---|---|---|
| Search | Title, notes and tag names contain `q`, compared with `casefold()` on both sides. `#work` also finds the tag `work`. | Works for every letter, also æ, ø, å. `Contains` escapes `%` and `_`. |
| Filter | All, Not done (`open`), Done (`done`). Default: All. | The owner chose All as the default. |
| Sort | Only the keys of `SORT_OPTIONS`: created, due, priority, title, manual. Default: created. | An **allow-list**: text from a request never reaches `order_by`. |
| Tie-break | Every order ends with `created_at`, `pk`. | Equal values always come back in the same order. |
| No due date | Last in "Due date" order. | It is the least urgent (SQLite would put it first). |
| Title order | The `norwegian` collation. | a to z, then æ, ø, å; upper and lower case are the same. |

Every function in `todos/queries.py` starts from the to-dos it is given (the list's to-dos) and
only makes the set smaller. It never starts from `Todo.objects`, so it can never read other
people's rows. The tag search uses a sub-query, so a to-do with two matching tags is shown once.

The page loads all tags and steps with `prefetch_related`, so the number of queries does not grow
with the number of rows.

### Manual order

- **When:** only in "Sort by: Manual", with no search and no filter (`can_reorder`). Then every
  to-do of the list is on the page, so a new order never has to guess where hidden rows go.
- **Two ways in:** drag and drop (`reorder.js`) and the Move up / Move down buttons (work with a
  keyboard and without JavaScript).
- **One way to write:** both use `save_order(todo_list, ids)` in `todos/ordering.py`. The ids
  must be exactly the list's to-dos, each once; otherwise nothing is saved (400). The check and
  the save are in one transaction, so a to-do added in between cannot be missed.
- **Not the default:** the owner kept "created" as the default sort.
- If saving fails, the script reloads the page, so the screen shows the real order.

### Safe toggles (Done and Undo)

The Done/Undo button sends the state it **wants**: `done=1` or `done=0`. Before, it flipped the
state. With a flip, a double click (or an old tab) would mark done and then undo, and on a
repeating to-do it would delete the copy just made. Now:

- The to-do already has the wanted state: nothing happens (no change, no copy, no message).
- Any other value of `done`: `400 Bad Request`. But first the 404 check, so a stranger learns
  nothing.
- Steps work the same way.

### Safe redirects and anchors

After Done, Undo or Delete, the browser goes back to the same page (with the same search, filter
and sort), at the right row. The button posts a `next` address, built from `back_url` plus an
**anchor** (the `#todo-7` part, which scrolls to the row with that id).

- Done/Undo goes back to its own row. With a filter, the row leaves the page, so it goes to the
  next row (or the one before, or the top).
- Delete always goes to the next row.
- Only database numbers go after the `#`, never text from the request.
- `redirect_back` follows `next` only if it starts with `/` and Django's
  `url_has_allowed_host_and_scheme` accepts it. So `//evil.example`, backslashes and
  `javascript:` are refused. This stops an **open redirect** (a link on this site that sends a
  person to another site).

### Steps

A step (`Subtask`) is a small part of a to-do, one level only. It has no owner: whoever may see
the to-do may change its steps. Marking all steps done does not mark the to-do done, and the
other way round. After "Add step", the page opens with the steps of that to-do open
(`?open=<id>`) and the cursor in the "New step" field. A step's address holds only the step's
number, never a to-do number, so the two cannot be mixed up.

### Lists and sharing

- Sign-up makes the first list, "Inbox".
- List names are unique per owner ignoring case for every letter. Names of lists shared **with**
  you do not count. The form names the list you already have ("You already have a list called
  “Ærend”.").
- Delete list asks first, and deletes its to-dos too.
- Share by exact username. Members do not see each other; only the owner sees the member list.
- Leave asks once more first (only the owner can share the list again). The to-dos a member added
  stay.
- "Clear completed" deletes all done to-dos of the whole list, also the ones other people added,
  after asking once more ("This cannot be undone"). It never reads to-do ids from the form.

## 8. Frontend and design system

### Three CSS files, one source of tokens

A **design token** is a named value in CSS, like `--accent: #1f4f8f`. Pages use the name, never
the raw value, so one change updates every page.

| File | Role | Used by |
|---|---|---|
| `todos/tokens.css` | The **only** place that sets tokens: colors, sizes, the font. Only `:root`, and `:root` in dark mode. | Every page. |
| `todos/site.css` | Shared look of the visitor pages (buttons, fields). | Landing, login, sign-up (`site_base.html`). |
| `todos/app.css` | Look of the app pages, including the to-do row. | The logged-in pages (`base.html`). |
| `landing.css`, `auth.css` | Only place the sections of one page. | That page only. |

Why split it this way? The visitor pages and the app look like one product (the same tokens and
the same button classes), but neither loads CSS it does not need. A unit test
(`test_tokens_css.py`) checks that no other file sets a token, so the colors cannot drift.

### Light and dark

The app follows the system setting (`prefers-color-scheme`). There is no toggle (the owner
decided). Dark mode only redefines the tokens; no other CSS changes.

### Accessibility rules

| Rule | How |
|---|---|
| Contrast | Every text color at least 4.5 : 1 against its background, field edges and the focus ring at least 3 : 1 (WCAG AA), in both modes. |
| Touch | Under a finger (`pointer: coarse`), every small control is at least 44px tall, 8px apart. |
| Screen readers | Each button's `aria-label` starts with its visible word and names the to-do: "Done: Buy milk", "Delete: Buy milk". The visible word first, so voice control works. |
| Errors | After a failed Save: `Error: ` before the page title, and a focused "Not saved." line. |
| Motion | Only color changes and a 1px press; none with `prefers-reduced-motion`. |
| Stable layout | A missing Move button leaves an empty slot, so the other buttons do not jump. |
| Labels | Visible labels, without a colon. |

### Page-size budget

A list with many to-dos sends a lot of HTML. The row template uses `{% spaceless %}`, and Done,
Undo and Delete share one form (one CSRF token instead of two). The test
`test_list_page_size.py` keeps a plain row under 1,429 bytes plus 5 %, and a row with one step
under 2,011 bytes plus 5 %. A feature that must make every row bigger raises the budget on
purpose, and says so in its pull request.

### The landing page

The landing page at `/` explains the app to a visitor. Its pictures are **real screenshots** of
the app with invented data, in a light and a dark version. They are taken by `make landing-shots`
(a scratch database in a temporary folder and a free port, never `db.sqlite3` or port 8000). A
drawn mockup could drift from the real app; a real screenshot cannot lie. The page has no
JavaScript, nothing from other sites, and no data from the database.

## 9. Time and dates

- `TIME_ZONE = "Asia/Tokyo"`: the owner's time zone. `USE_TZ = True`: times are stored in UTC.
- **"Today" is always `timezone.localdate()`**, the date in Tokyo. Never `date.today()` or
  `datetime.now()`: they use the computer's own time zone, which can differ (on a host, for
  example).
- Code that needs "today" takes it as an argument (`make_next_copy(today)`,
  `send_reminders(user, today)`, `is_overdue(today=None)`). The view or command passes the real
  date; a test passes a fixed date. So tests do not depend on the day they run.
- "Overdue" means the due date is before today and the to-do is not done. Due today is not
  overdue.
- Backup names and the "one daily backup a day" rule also use the Tokyo date.

## 10. Operations

### Everyday commands

| Command | What it does |
|---|---|
| `make setup` | Install Python and the packages, download Chromium for tests, migrate, turn on the commit checks. |
| `make run` | First a daily backup (see below), then the server at <http://127.0.0.1:8000>. |
| `make backup` | A copy of `db.sqlite3` in `backups/`, kept until you delete it. |
| `make reset` | Asks (only `yes` goes on), makes a copy, then starts with an empty database. |
| `make check` | Every commit check, the migration check, then all tests. |

### Backup design

All data is in one file, so a backup is a copy of that file (`todos/backup.py`).

| Choice | Why |
|---|---|
| SQLite's **online backup**, not a plain file copy | The copy is whole even while the server writes. |
| The source is opened read-only | A missing database is never created as an empty file. |
| The final name is reserved first (`open(..., "xb")`) | An older backup is never overwritten. |
| Write to a temporary name, `fsync`, then rename | A crash never leaves a half-written file with the final name. |
| Mode 600 | Only the owner can read the copy. It holds every account and to-do. |
| Daily copy on `make run`: at most one a day, keep the newest 14 | Automatic safety with no launchd setup (the owner chose this). |
| Only `-daily` files are ever deleted | Copies from `make backup` and `make reset` are never deleted automatically. |
| A failed backup gives a warning, the server starts anyway | A full disk should not stop the app. |
| Old copies are pruned only after today's copy is safe | Never fewer copies on a day without a new one. |

`backups/` is not in git. A copy on the same Mac does not help if the Mac breaks: the README asks
the owner to copy `backups/` to another disk now and then.

### Settings and environment

On the laptop no environment variable is needed. On a host, three are needed
(`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`). `config/env.py` reads them with
pure functions:

- `read_debug`: only `True` or `False` (any case). Anything else, also empty, stops the app. A
  typo like `Flase` must never silently mean "debug on".
- `read_secret_key`: with debug off, a missing or weak key stops the app (the same limits as
  Django's deploy check: 50 characters, 5 different characters, not `django-insecure-`).
- No error message ever shows a value, because messages end up in build logs.

With debug off, the settings turn on HTTPS only, secure cookies and HSTS.

### Reminders on the Mac (off)

`python manage.py send_reminders --user <name>` shows one macOS notification with the to-dos due
today in the user's **own** lists. Mac's scheduler, **launchd**, can run it at 08:00 using the
template in `deploy/macos/`. It is **off**: the owner chose not to set it up. The AI never
installs it, never runs `launchctl`, and never writes to `~/Library`, because that changes the
Mac's own settings.

Safety design:

- `osascript` gets a **fixed** AppleScript. The title and text go in as arguments after `--`,
  never inside the script and never through a shell. A to-do title like `-e ...` cannot run code.
- An error message never includes `osascript`'s error output, which could repeat to-do titles
  into a log file.
- `reminded_on` is set only after the notification worked.
- Tests never start the real `osascript` (`FakeOsascriptMixin`).

## 11. Testing and quality

### Three layers

| Layer | Folder | Tool | Count (2026-10-16) |
|---|---|---|---|
| CUJ | `*/tests/cuj/` | A real Chromium browser, driven by Playwright | 30 |
| Integration | `*/tests/integration/` | Django's test client: address to database | 577 |
| Unit | `*/tests/unit/` | One function, no requests, no database | 124 |
| **Total** | | | **731** |

These numbers come from a full run of `uv run python manage.py test` on `main` (`c0401bc`).

**Why is the middle layer the biggest?** Most of the app's logic is the view, the form, the page
and the database working together, and the test client tests that fast. The rule is: **test each
rule once, in the lowest layer where a person would notice it** (test-pyramid). Pure logic (dates,
tags, the fingerprint, the order parser) is unit-tested; CUJ tests only check that the parts work
together in a browser.

### Layer rules enforced by the runner

`config/test_runner.py` finds each test's layer from its folder, and **stops before running** if
a test breaks a rule:

- A test outside a `unit/`, `integration/` or `cuj/` folder.
- A unit test that is not a `SimpleTestCase` (Django's test class with no database).
- A CUJ test that is not a `StaticLiveServerTestCase` (in practice: `BrowserTestCase` from
  `todos/tests/cuj/browser.py`, which starts Chromium).

At the end it prints one line per layer.

### The quality gates

| Gate | When | What |
|---|---|---|
| pre-commit | Every `git commit` | Ruff lint and format, `manage.py check`, whitespace, YAML/TOML, merge markers, large files, private keys. |
| `make check` | Before every commit (a rule) | All of pre-commit on every file, `makemigrations --check`, all tests. |
| GitHub CI | Every push and pull request | Job `lint` (pre-commit, migration check) and job `test` (all three layers). |
| Ruleset on `main` | Merging | `lint` and `test` must be green. No force-push, no deleting `main`. |

### How tests are checked

A test that cannot fail is worse than no test. So:

- A change in behaviour comes with a test, shown **failing before** the fix and **passing after**.
- Code reviewers **break the code on purpose** (a small wrong change, also called mutation
  testing) and check that a test fails. Several tests were found this way to pass for the wrong
  reason, and were fixed (see the "Review" and "Built" sections of the plans).

## 12. How work is done

Each feature follows the same path:

1. **Plan.** A plan in `docs/plans/<feature>.md`: goal, decisions, the tests to write, open
   choices with a recommendation.
2. **Plan review.** An independent reviewer checks the plan against the real code, often with
   small prototypes ("APPROVE WITH CHANGES").
3. **Approval.** The owner answers the open choices ("Decided by the person"). When the owner was
   away, the orchestrator (the AI session that runs the work) chose the recommended option and
   wrote it under "Decided by the orchestrator for the person"; risky items were left for the
   owner.
4. **Tests first.** The implementer writes the tests, shows them failing, then writes the code.
5. **Code review.** A separate reviewer, with mutation testing ("PASS WITH FIXES").
6. **Pull request.** One PR per feature, with `make check` green and CI green.
7. **Merge queue.** The orchestrator merges one PR at a time, rebases the next one on `main`,
   and renumbers migrations when two branches made the same number.
8. **Status line.** The last commit sets the plan's line to `Status: **done** (<date>)`.

Each branch works in its own **worktree** (a second folder with its own checkout), so several
agents can work at once without touching each other's files or the owner's `db.sqlite3`.

## 13. Known limits and possible future work

| Limit | Notes |
|---|---|
| Backups only on the same Mac | The owner must copy `backups/` to another disk or cloud folder by hand. |
| Undo on a filtered page | If the restored to-do does not match the filter (it was done, the page shows "Not done"), its row is not on the page, and the page opens at the top (delete-undo, accepted). |
| Only the last delete can be undone | An Undo button from an older delete, still open in another tab, gives a 404. |
| Restored steps get new ids | Nothing links to a step id except its own buttons on the page. |
| Last Save wins | No warning when two people edit the same to-do (decided). |
| A tab opened before safe-toggles | Sends no `done`, gets a bare 400 page; a reload fixes it. |
| Search ignores case, not accents | "e" does not find "é" (decided). |
| `db.sqlite3` needs the custom functions for search and title sort | Another SQLite tool can read the data, but not run those two queries. |
| No threaded test for two requests at once | `IMMEDIATE` and the idempotent toggles cover the known cases. |
| Sign-up is open, no limit on wrong passwords | Fine on a local Mac. Must change before the site is public. |
| Hosting | On many hosts the SQLite file is lost on every deploy. A persistent disk or PostgreSQL would be needed; neither is built. |
| Reminders off | The code works; it needs the owner's own launchd setup, and the project moved out of `Documents`. |

Possible future work, only if the owner asks: login rate limiting, a hosted database, switching
on reminders, automatic copies off the Mac.

## 14. Glossary

| Word | Meaning |
|---|---|
| Allow-list | A fixed list of accepted values; anything else is refused or ignored. |
| Anchor (fragment) | The `#todo-7` part of an address. The browser scrolls to the element with that id. |
| App (Django) | A folder with its own models, views and templates, like `todos/`. |
| CI | Continuous integration: GitHub runs the checks and tests on every push. |
| Collation | A rule a database uses to sort text. |
| CSRF | Cross-site request forgery: another site posting a form in your name. Django blocks it with a token in each form. |
| CUJ | Critical user journey: an important task done from start to finish, tested in a real browser. |
| Data migration | A migration that changes rows, not tables. Written by hand. |
| Design token | A named CSS value, like `--accent`, used by every page. |
| Fingerprint (hash) | A short code computed from some data. The same data always gives the same code. |
| Idempotent | Doing it twice has the same effect as doing it once. |
| Integration test | A test of one address from the request to the database. |
| launchd | The Mac's own scheduler for background jobs. |
| Middleware | Code that runs before and after every view. |
| Migration | A file that changes the database tables step by step. |
| Monolith | One program that does everything, not several services. |
| Mutation testing | Breaking the code on purpose to check that a test notices. |
| Open redirect | A link on a site that sends people to another, possibly harmful, site. |
| Orchestrator | The AI session that plans the work, starts other agents and merges their PRs. |
| Playwright | A tool that drives a real browser from test code. |
| Prefetch | Loading related rows (tags, steps) in one extra query instead of one per row. |
| Request / response | What the browser sends / what the server sends back. |
| Session | Data the server keeps for one logged-in browser. |
| Snapshot | A copy of a to-do's data, kept so it can be made again. |
| SQLite | A database that lives in one file, with no server. |
| Transaction | A group of database changes that happen all together or not at all. |
| Unit test | A test of one function on its own, with no database. |
| View | A Python function that answers one address. |
| Worktree | A second folder with its own checkout of the same git repository. |
| 404 / 403 / 400 | "Not found" / "Forbidden" / "Bad request". The app uses 404 for other people's things. |
