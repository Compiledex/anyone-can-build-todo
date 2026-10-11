# Plan: cleanups: the "/" view is `home`, lighter list HTML, a shorter AGENTS.md

Status: approved by the person (2026-10-11), not started

Builds on: everything on `main` after **A** (recurring-copy-rules), **B** (delete-undo), **C**
(list-name-casefold) and **D** (backup-on-run) have merged. This plan starts from that `main`, not
from `d66b978`.

This plan **must not change behaviour**: every page does and shows the same things, every address
is the same, every test that checks behaviour still passes. Where a test that checks exact HTML
has to change, the PR lists it with the reason.

## Words used in this plan

- **URL name**: the name Django uses for an address in code (`reverse("todo_list")`,
  `{% url 'todo_list' %}`). The address the browser sees (`/`) does not change when the name
  changes.
- **Whitespace**: spaces, tabs and new lines. Between two HTML tags, the browser mostly ignores
  it; it still has to be sent.
- **`{% spaceless %}`**: a Django template tag that removes whitespace **between tags** (`>` and
  `<`) inside it. Text inside a tag, like `Due 12 Oct`, is not changed.
- **CSRF token**: the hidden `csrfmiddlewaretoken` input every `POST` form needs (Django refuses
  a `POST` without it). Here it is 121 bytes each time.
- **`formaction`**: an HTML attribute on a submit button: "send this form to this address instead".
  With it, two buttons in one form can go to two views.

## What is wrong today

Facts, checked on `main` (commit `d66b978`; the implementer checks them again on the `main` after
D):

1. The view and URL name for `/` are both `todo_list`, but `/` shows the landing page or sends a
   logged-in person on to a list. Every reader thinks it is the list page (`list_detail`). The
   name is used in: `todos/urls.py`, `todos/views.py` (the view, and `redirect("todo_list")` in
   `list_delete` and `list_leave`), `accounts/views.py` (two `redirect("todo_list")` in `signup`),
   `config/settings.py` (`LOGIN_REDIRECT_URL`), `todos/templates/base.html`,
   `todos/templates/todos/site_base.html`, `todos/templates/todos/list_form.html` (`{% url
   'todo_list' %}`), the tests (`reverse("todo_list")` in `accounts/tests/integration/
   test_accounts.py`, `todos/tests/integration/test_lists.py`, `test_sharing.py`; the set of open
   views in `test_access.py`, and the comment above it, `# "todo_list" is `/`...`), and
   `AGENTS.md` (the landing row, line ~56, "view `todo_list`"; and the Rules, line ~136, "Today
   the open views are ... `todo_list`"). B (delete-undo) adds a redirect to `/` after a failed
   Undo ("go to `/`"); if B wrote it as `redirect("todo_list")`, it becomes `redirect("home")`.
   The implementer runs `git grep -n "todo_list['\"]"` and `git grep -n "views.todo_list"` again
   on the new `main` and changes every hit that means the `/` view.
2. The list page is heavy. Measured on 2026-10-11 in a scratch database (never the person's file),
   one list with **300 plain to-dos** (no notes, tags or steps), logged in:

   | Page | Bytes | `<form>`s | CSRF inputs | Whitespace between tags |
   |---|---|---|---|---|
   | `/lists/<pk>/` (default order) | 594,081 | 905 | 903 | 119,298 bytes (20 %) |
   | `/lists/<pk>/?sort=manual` (Move buttons) | 804,136 | 1,206 | 1,204 | 136,730 bytes (17 %) |

   One row is about 1,943 bytes. Each row has 3 forms (Done/Undo, Delete, Add step; plus Move in
   manual order), and each step 2 more (Done/Undo, Delete). The CSRF inputs alone are
   903 × 121 = 109,263 bytes. Lines with only `{% if %}` or `{# ... #}` leave many empty lines.
3. `AGENTS.md` is 42,624 bytes. Some file rows are very long (`todos/views.py` 4,321 characters,
   `todos/models.py` 2,513, `_todo_item.html` 2,221, `todo_list.html` 1,921, `queries.py` 1,795):
   they describe behaviour line by line, and repeat what the docstrings say. An agent reads the
   whole file on every task.

## Goal

The `/` view and its URL name are called `home` everywhere; the address stays `/`. The list page
sends clearly less HTML for the same page (measured before and after). `AGENTS.md` is about half
as long: each file row says its one job, its invariants and its rules; behaviour details live in
the docstrings it points to. The Rules section keeps every rule.

## Decisions

### 1. Rename `todo_list` (the `/` view and URL name) to `home`

- `todos/urls.py`: `path("", views.home, name="home")`. `todos/views.py`: `def home(request)`,
  same decorators (`@login_not_required`, `@require_safe`), same body, same docstring.
- Every `redirect("todo_list")`, `reverse("todo_list")` and `{% url 'todo_list' %}` becomes
  `home`. `LOGIN_REDIRECT_URL = "home"`. `LOGOUT_REDIRECT_URL` stays `"login"`.
- `test_access.py`: the open views become `{"login", "logout", "signup", "home"}`;
  `AGENTS.md` Rules ("Today the open views are `login`, `logout`, `signup` and `home`").
- **Not renamed**: the model field `Todo.todo_list`, the test helper attribute
  `LoggedInTestCase.todo_list` (alice's "Inbox"), `add_todo(todo_list, ...)`, `save_order(todo_list,
  ids)`, the `todo_list.html` template, the admin's `list_display`/`list_filter`, and the
  migrations. They are a list, not the `/` view. A plain search and replace would break them; the
  implementer changes only the uses listed in "What is wrong today", 1 (and B's, if any).
- **No alias**: the old name is gone, so `reverse("todo_list")` raises `NoReverseMatch`. Nothing
  outside this repository uses it. A test pins this, so a forgotten use fails loudly.
- Old plans in `docs/plans/` are history and keep the old name (AGENTS.md: "do not edit the body
  of an old plan").

### 2. Lighter list HTML, in two steps, each measured

**Step a: `{% spaceless %}` around each row.** `_todo_item.html` is wrapped in `{% spaceless %}
... {% endspaceless %}`. It removes the whitespace between tags. It is safe here because every
container in the row where two tags sit next to each other is laid out with flexbox and `gap`, not
with the space between them (`ul.todos > li .meta`, `.tags` and `.actions` are `display: flex`
with `gap`; the `.actions` forms are `display: contents`). Text stays as it is, also the spaces
inside `<span class="visually-hidden">Done: </span>` and "Steps: 1 of 2 done". The implementer
checks every place where an inline element follows another with only whitespace between them
(today: none outside flex containers) and says so in the PR. The CUJ layout tests
(`test_a_full_row_stays_readable`, `test_move_buttons_keep_their_slot`,
`test_row_and_step_buttons_fit_a_finger`) must pass unchanged.

**Step b: one form for a row's Done/Undo and Delete; one for a step's Done/Undo and Delete.**

```django
<form method="post">
  {% csrf_token %}
  <input type="hidden" name="done" value="{% if todo.done %}0{% else %}1{% endif %}">
  <button ... formaction="{% url 'todo_toggle' todo.pk %}" name="next" value="{{ back_url }}#{% if status %}{{ todo.anchor_after_removal }}{% else %}todo-{{ todo.pk }}{% endif %}">Done</button>
  <button ... formaction="{% url 'todo_delete' todo.pk %}" name="next" value="{{ back_url }}#{{ todo.anchor_after_removal }}">Delete</button>
</form>
```

- The browser sends the clicked button's `name=value`, so each button still sends its own `next`
  (the same values as today, from safe-toggles). The Done/Undo button keeps safe-toggles' exact
  rule, `{% if status %}{{ todo.anchor_after_removal }}{% else %}todo-{{ todo.pk }}{% endif %}`
  (with a filter, the row leaves the page, so the next row); Delete keeps
  `{{ todo.anchor_after_removal }}`. The existing tests for both rules
  (`test_done_in_not_done_filter_goes_to_the_next_row`, `test_done_goes_back_to_its_row`,
  `test_delete_goes_to_the_next_row`) must pass, reading `next` from the button. `todo_delete` ignores `done`, as it ignores
  every other field today. The views do not change.
- Both buttons have a `formaction`, so the form never posts to the list page itself. The form
  has no text field, so pressing Enter cannot submit it without a button.
- The `.actions` forms are `display: contents`, so the buttons stay in the same place.
- The same for a step: one form with `done`, Done/Undo (`formaction` `subtask_toggle`) and Delete
  (`formaction` `subtask_delete`). A step's `<li>` is `display: flex` with `gap`, and today each
  of its two forms is one flex item. With one form, the two buttons would sit inside it with no
  gap (step a removes the space between them). So `app.css` gets `ul.steps li form { display:
  contents; }`, the same trick as `.actions form`: the buttons become flex items again, with the
  same gap as today. `test_row_and_step_buttons_fit_a_finger` checks the result.
- The Move form and the Add step form stay as they are (one form each, already).
- B's Undo-delete form (in `base.html`) is not touched.
- Saves one CSRF input and one `<form>` pair per row and per step: about 300 × 150 bytes for 300
  plain to-dos.

**Measure** before and after each step with the same script (300 plain to-dos, default and
manual order, in a scratch database made with `migrate` in a temporary folder; never the
person's `db.sqlite3`, never port 8000), and put the table in the PR. The expected result is
roughly 594 KB to about 430 KB for the default order. If a step saves less than 5 %, it is left
out and the PR says why.

**Exact-HTML tests that change with step b** (they read the forms; each keeps checking the same
behaviour, on the new markup):

| Test or helper | Change | Why |
|---|---|---|
| `todos/tests/integration/test_views.py` line ~24, the helper that finds a form's `next` with `<form method="post" action="...">.*?name="next" value="..."` | Find the button with `formaction="..."` and read its `value`. | The `action` moved to the button's `formaction`, and `next` to the button. |
| `test_views.py` line ~422 (`test_page_sends_the_state_it_wants`) | Find the form that holds the button with `formaction` of `todo_toggle`, then the hidden `done`. | Same. |
| `test_subtasks.py` line ~152 (the step form check) | The same for `subtask_toggle`. | Same. |
| `test_filter.py` lines ~143 and ~229-231 (`<input type="hidden" name="next" value=...>` with `count=`) | Check the buttons' `name="next" value="..."` with the same values and counts. | `next` is now on the button. |

Step a should change no test: most HTML checks use `assertInHTML` or the page parser, which
ignore whitespace between tags. A check with a raw string that holds whitespace between two tags
would fail; the implementer runs `make test` after step a and lists any such test in the PR, with
the change.

A **new test** keeps the rows light: `ListPageSizeTests.test_bytes_per_row_stay_light` measures
the default list page with 0 plain to-dos and with 300, and checks `(size with 300 - size with 0)
/ 300` against a budget per row: the measured "after" number plus 5 %, written into the test with
a comment that says how it was measured. Per row, not a fixed total, so a change to the page
frame (the header, the menu, a new message) does not break it; only heavier rows do. (Today one
row is about 1,943 bytes.)

### 3. A shorter AGENTS.md

- Each row of the file table keeps: **its one job** (one or two sentences), its **invariants**
  (what must always stay true: "the one place that ...", "never ..."), and links to the rule it
  follows. Behaviour details (which message, which redirect, which field is checked first) move
  to the file's docstrings, and the row says "See the docstrings" where useful.
- Before deleting a sentence from a row, the implementer checks that the fact is in the code: a
  docstring, a comment, or a test name. If it is not, they add a docstring line (code comments
  only; no behaviour change). The PR lists every moved fact and where it went.
- **The Rules section stays complete**: every rule, word for word unless a name changed (`home`).
  The Commands section stays complete.
- **Rules that live in file rows stay as invariants of those rows** (shortened, never dropped).
  At least:
  - `todos/queries.py`: every function starts from the `todos` it is given; never `Todo.objects`
    there; `SORT_OPTIONS` is the one allow-list of orders.
  - `deploy/macos/...reminders.plist`: the AI never installs it, never runs `launchctl`, and
    never writes to `~/Library`.
  - `todos/migrations/`: never edit these by hand, except a data migration, which is meant to
    be written.
  - `todos/reminders.py`: the fixed AppleScript, `--` before the arguments, never `stderr` in
    the error text.
  - `todos/static/todos/tokens.css`: the one place that sets the tokens.
  - `base.html`: never loads `site.css`.
  The implementer greps the current rows for "never", "only", "the one place" and "must" and
  lists each such sentence in the PR with where it stays.
- The intro ("What this is") stays, shortened only where it repeats a row.
- Target: about 22,000 bytes or less (today 42,624). The PR gives the before and after size.
- The `docs/plans/` row and the rule "AGENTS.md describes the code on `main`" stay.

## Security

- No change to who may see or change what: no view body changes, only the name of one view.
  `@login_not_required` stays on `home` only (with `login`, `logout`, `signup`), and
  `test_only_landing_login_and_signup_are_open` checks it with the new name.
- The landing page still gets no database data.
- Step b keeps CSRF on every `POST` form (one token per form, as now; there are just fewer
  forms). Every button still posts to the same view, which still checks `get_visible_todo` or
  `get_visible_subtask` first and validates `done` and `next` (`wanted_done`, `redirect_back`).
- `next` values stay built from `back_url` and database numbers, as today.

## Data and migrations

None. No model change, no migration. Going back: revert the commit.

## Working next to

Wave: **E runs last**, after A → B → C → D have merged. It starts a new branch from that `main`.

- A, B, C and D each change `AGENTS.md`; E shortens the result, so it must start after all four.
- B adds a form to `base.html` and the message with Undo; E does not change them, and its
  `_todo_item.html` changes keep Delete's `next` (B's Undo needs nothing from the row).
- A, C and D do not touch `_todo_item.html`.

## Not part of this task

- Any change in behaviour, any new feature, any new URL.
- Removing the CSRF token from forms, or a JavaScript way to send it (the app works without
  JavaScript).
- Paging the list (showing 50 to-dos at a time).
- Changing the Add step form or the Move form.
- Renaming other views or URL names (`list_detail`, `todo_toggle`, ...).
- Editing old plans in `docs/plans/`.

## Changes to files

| File | Change |
|---|---|
| `todos/urls.py`, `todos/views.py` | `home` (view and name); the two `redirect("todo_list")`. |
| `accounts/views.py` | Two `redirect("home")`. |
| `config/settings.py` | `LOGIN_REDIRECT_URL = "home"`. |
| `todos/templates/base.html`, `todos/templates/todos/site_base.html`, `todos/templates/todos/list_form.html` | `{% url 'home' %}`. |
| `todos/templates/todos/_todo_item.html` | `{% spaceless %}`; one form for Done/Undo and Delete, one per step. |
| `todos/static/todos/app.css` | `ul.steps li form { display: contents; }` (step b). |
| `accounts/tests/integration/test_accounts.py`, `todos/tests/integration/test_lists.py`, `test_sharing.py`, `test_access.py` | `reverse("home")`; the open-views set. |
| `todos/tests/integration/test_views.py`, `test_subtasks.py`, `test_filter.py` | The form checks in the table above. |
| `todos/tests/integration/test_list_page_size.py` (new) | `ListPageSizeTests.test_bytes_per_row_stay_light`. |
| `todos/tests/integration/test_landing.py` | `test_old_name_is_gone` (or in `test_access.py`). |
| Docstrings in `todos/*.py`, `accounts/*.py` | Facts moved from `AGENTS.md` that were not in the code yet. |
| `AGENTS.md` | Shorter (decision 3); `home`. |

## Steps

1. Measure the list page (the script and the table in the PR). Note `AGENTS.md`'s size.
2. **Tests first**: `test_old_name_is_gone` and the `reverse("home")` changes; `make
   integration`: they fail (`home` does not exist). Show the person.
3. Rename (decision 1). `make test`.
4. Step a (`spaceless`). Measure. `make test` (all CUJ tests too).
5. Change the form tests in the table, then step b. Measure. `make test`.
6. Write `ListPageSizeTests` with the measured bytes per row.
7. `AGENTS.md` and the docstrings (decision 3).
8. `make check`. Commit. Last commit: Status `**done** (<date in Tokyo>)`.

## Tests

### Integration

| Test | What it checks | The break that fails it |
|---|---|---|
| `test_access.py` `test_only_landing_login_and_signup_are_open` (changed) | The open views are `login`, `logout`, `signup`, `home`. | A rename that drops `@login_not_required`, or opens another view. |
| `test_landing.py` `test_old_name_is_gone` (new) | `reverse("home") == "/"`; `reverse("todo_list")` raises `NoReverseMatch`. | A forgotten alias, or the address changed. |
| `test_lists.py` `HomeTests`, `test_sharing.py` `HomeTests`, `test_accounts.py` (changed) | The same checks as today, with `reverse("home")`: `/` sends a logged-in person to the oldest list, sign-up and login go there. | Any change in where `/` goes. |
| `test_list_page_size.py` `test_bytes_per_row_stay_light` (new) | (page with 300 plain to-dos - page with 0) / 300 is at most the measured bytes per row plus 5 %. | Undoing step a or b later. |
| `test_views.py`, `test_subtasks.py`, `test_filter.py` (changed) | Each button posts to the same view with the same `done` and `next` as before. | Step b sending the wrong `next` or no `done`. |
| Every other test | Unchanged, all pass. | Any behaviour change. |

### CUJ

No new journey. All existing ones must pass unchanged; they click buttons by their role and name,
so the form change is invisible to them. In particular `test_done_keeps_the_place`,
`test_break_a_todo_into_steps`, `test_a_full_row_stays_readable` and B's `test_delete_and_undo`.

## Decided by the person (2026-10-11)

- After A to D: rename the URL name and view `todo_list` (the `/` page) to `home` everywhere,
  keeping the address `/`.
- Lighter list HTML (`{% spaceless %}` or trimmed whitespace in `_todo_item.html`, fewer repeated
  forms and CSRF inputs where it is safe), measured for 300 to-dos before and after; keep every
  exact-HTML test or justify each change.
- A shorter `AGENTS.md`: each file row keeps its one job, invariants and rules; behaviour details
  move to (or point at) docstrings; the Rules section stays complete.
- It must not change behaviour.

## Open choices

1. **Merge the Done/Undo and Delete forms (step b).** Yes, **recommended**: about 45 KB less for
   300 to-dos (more with steps), no behaviour change, and four test helpers change for a clear
   reason. (No: only step a; no test changes.)
2. **A page-size test.** Yes, **recommended**: a budget in bytes per row (the measured number
   plus 5 %) stops rows from growing back unnoticed, and a change to the page frame does not
   touch it. It must be raised on purpose when a feature adds to a row.
3. **How short AGENTS.md gets.** About half (about 22 KB), **recommended**: the Rules and Commands
   stay whole, each row keeps its job and invariants. (Shorter means more trips into the code for
   every task.)

## Review

Verification by the planner (2026-10-11), against `main` (`d66b978`):

- Confirmed every use of the URL name `todo_list` with `git grep` (listed in "What is wrong
  today", 1), and that the same word is also a model field, a test attribute, function
  arguments and a template file name, which must not change.
- Measured the list page in a scratch database (made by `migrate` in a temporary folder; the
  person's `db.sqlite3` and port 8000 were not touched): the numbers in the table.
- Confirmed in `todos/static/todos/app.css`: `ul.todos > li .meta` and `.tags` are `display:
  flex` with `gap`; `ul.todos > li > .actions` is `display: flex` and its forms are `display:
  contents`; `ul.steps li` is `display: flex` with `gap`, but its forms have no `display:
  contents` yet (found while checking; step b adds it).
- Confirmed the exact-HTML checks of the row forms: `test_views.py` (~24, ~422),
  `test_subtasks.py` (~152), `test_filter.py` (~143, ~229-231).
- Confirmed `AGENTS.md` is 42,624 bytes, and the longest rows (sizes in "What is wrong today", 3).

The plan review (2026-10-11, an independent reviewer who also ran small prototypes) said APPROVE
WITH CHANGES. What changed:

- The Done/Undo button keeps safe-toggles' exact `next` rule (`{% if status %}` the anchor after
  removal, else `todo-<pk>`); the plan writes it out.
- The rename list adds B's redirect to `/`, the comment in `test_access.py`, and the two
  `AGENTS.md` lines (~56 and ~136).
- The page-size test is a budget in bytes per row ((300 rows - 0 rows) / 300), not a fixed total.
- AGENTS.md trimming lists the rules that live in file rows and must stay as invariants (never
  `Todo.objects` in `queries.py`; never install launchd or write to `~/Library`; never edit
  migrations except data migrations; and more).
