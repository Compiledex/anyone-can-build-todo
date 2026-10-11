# Plan: an accessibility pass on the app pages

Status: **approved** (2026-10-11, by the orchestrator for the person), not started.

Builds on: **app-redesign** (#32: `base.html`, `app.css`, `_field.html`, the row grid, the 44px
touch rule, and its "Decided by the person"), **accounts** (`accounts/forms.py`), **subtasks**,
**sharing**, **clear-completed** (the `<details>` confirm), **drag-and-drop** (the Move buttons),
and **safe-toggles** (`docs/plans/safe-toggles.md`, merged first: hidden `done`, `next` with an
anchor, `id="todos"`). Also assumes **nordic-letters** and **recurring-undo-steps** are merged.

## Words used in this plan

- **Accessible name**: the name a screen reader says for a button or link. It is the
  `aria-label` if there is one, else the visible text.
- **Label in name** (WCAG 2.5.3): the accessible name must contain the visible text, best at the
  start. A person using voice control says what they see ("click Done"), and it must match.
- **Visually hidden**: text that a screen reader reads but the screen does not show (the
  existing `.visually-hidden` class in `app.css`).
- **`role="alert"`**: tells a screen reader to read this text at once when the page opens.
- **Coarse pointer**: a finger, not a mouse (`@media (pointer: coarse)`).

## What is wrong today

Facts, checked on `main` (commit `6c7169b`):

1. The row buttons Done, Undo and Delete have no `aria-label`. A screen reader that lists the
   buttons hears "Done, Done, Done, Delete, Delete, ..." with no to-do name. Edit (`Edit <title>`),
   Move (`Move up: <title>`) and the step buttons (`Done: <step>`) already name their thing.
2. The steps summary says "Add steps" or "Steps: 1 of 2 done" with no to-do name. (The notes
   summary already has `aria-label="Notes for <title>"`.)
3. A done to-do is only shown by a line through the title and the "Undo" button. A screen reader
   reading the row hears the title as if it were open.
4. The 44px touch rule in `app.css` covers the row buttons, the step buttons and the add-step
   form only. The `<summary>` of notes, steps and Clear completed, the filter links (2px apart),
   the list menu links, and Rename and Delete list stay small under a finger.
5. After a failed Save on the edit, new list or rename page, the `<title>` does not change and
   nothing is announced. A screen reader user does not know it failed until they find the error.
6. After "Add step", the page opens at the row (`?open=<pk>#todo-<pk>`), but the cursor is not in
   the "New step" field, so adding three steps needs three clicks in the field. (Checked in
   Chromium: an address with a fragment that names an element **skips** `autofocus`. So an
   `autofocus` on the step field only works if the add-step redirect has no fragment.)
7. In the manual order, the first row has no "Move up" and the last row has no "Move down". The
   Move form is `display: contents`, so on those rows Edit, Done and Delete shift one button to
   the left. The buttons are not in the same place from row to row.
8. Page titles: the list page is just `<list name>`, the edit page is "Edit to-do" (for every
   to-do). With several tabs, the person cannot tell them apart.
9. The sign-up page shows Django's own help text: "Required. 150 characters or fewer. Letters,
   digits and @/./+/-/_ only.", a list of four password rules, and "Enter the same password as
   before, for verification." Long and technical for a new person.
10. The list menu says "My lists:" and "Shared with me:". The person decided "no colon" for
    labels (app-redesign).
11. "Leave this list" leaves at once on one click. Coming back needs the owner to share again.
    "Clear completed" already asks first with a `<details>`.

## Goal

A screen reader user hears which to-do each button belongs to, whether a to-do is done, and when
a form failed. A finger can hit every small control on the list page. The buttons of a row stay in
the same place. Tabs have useful titles. Sign-up help is short and plain. Leaving a list asks
first.

## Decisions

### 1. Row buttons and the steps summary name their to-do

| Control | Visible text | Accessible name |
|---|---|---|
| Row Done | Done | `aria-label="Done: <title>"` |
| Row Undo | Undo | `aria-label="Undo: <title>"` |
| Row Delete | Delete | `aria-label="Delete: <title>"` |
| Steps summary, no steps | Add steps | `Add steps<span class="visually-hidden"> to <title></span>` |
| Steps summary, with steps | Steps: 1 of 2 done | `Steps: 1 of 2 done<span class="visually-hidden"> in <title></span>` |

- The same "Verb: thing" pattern as the step buttons and Move. The visible word is first, so
  label in name holds and voice control still works.
- Edit keeps `Edit <title>` (CUJ tests use it; it is already label-in-name).
- The summary uses hidden text at the end, not an `aria-label`: a `<summary>`'s name comes from
  its text, and the visible "Steps: 1 of 2 done" stays one piece of text (tests use it).
- Titles are escaped by Django's template engine, as in the existing `aria-label`s.

### 2. "Done: " before a done to-do's title, for screen readers

In `_todo_item.html`, before `<span class="title">`: `{% if todo.done %}<span
class="visually-hidden">Done: </span>{% endif %}`. **Outside** the title span, because:
`test_note_of_a_done_todo_is_not_inside_the_title` checks that the title span closes right after
the title, and CUJ tests read `ul.todos > li .title` text.

### 3. 44px under a finger, also for summaries, filter links, menu links, Rename and Delete list

Add to the `@media (pointer: coarse)` block in `app.css`:

- `ul.todos details summary`, `details.clear-completed summary`, `details.leave summary` (new,
  decision 9): `display: flex; align-items: center; min-height: var(--control-height-touch)`.
- `nav.filter a`: `min-height: var(--control-height-touch)`; `nav.filter` gap `var(--space-2)`.
- `nav.lists a` and `.list-actions a`: `display: inline-flex; align-items: center; min-height:
  var(--control-height-touch)`. `nav.lists .menu` gets only `row-gap: var(--space-2)` (its 16px
  column gap stays); `.list-actions` gap `var(--space-2)`.

CSS only, only under a finger; the laptop look does not change.

### 4. Form errors: "Error: " in the title, and one line that is announced

On the edit, new list and rename pages (`todo_edit.html`, `list_form.html`), when `form.errors`:

- `<title>` starts with `Error: ` (the GOV.UK pattern).
- Above the fields, one line: `<p class="form-error-summary" role="alert" tabindex="-1"
  autofocus>Not saved. Fix what is marked below.</p>`. `tabindex="-1"` lets it take focus
  without joining the Tab order, and `autofocus` puts the focus there when the page opens, so a
  screen reader reads it first (no JavaScript; these pages have no other autofocus). Screen
  readers do not reliably announce a `role="alert"` that is already in the page when it loads, so
  the reliable parts are the `Error: ` title and the focus; `role="alert"` is only extra. The errors stay under their fields, as today. No list of links: these forms
  have one to six fields.
- `.form-error-summary` in `app.css`: `--danger` text, the existing message box look. No new
  token.

The list page's add form is not part of this: its error is already under the field, and the add
form is small. The login and sign-up pages already have `role="alert"` for form errors.

### 5. After "Add step", the cursor is in that row's "New step" field

- `back_to_steps(todo, *, to_new_step=False)` in `todos/views.py`. `subtask_add` calls it with
  `to_new_step=True`: the address is `?open=<pk>` with **no** fragment. Step Done/Undo and Delete
  keep `?open=<pk>#todo-<pk>` (they should not move the cursor).
- `_todo_item.html`: the "New step" input gets `autofocus` when `request.GET.open` equals this
  to-do's id (the same string compare as the `open` attribute of the `<details>`; the value is
  never printed).
- `todo_list.html`: the "New to-do" input has `autofocus` only when there is no `open` in the
  address. Two `autofocus` fields on one page: the browser uses the first, which would be
  "New to-do".
- Why it works: with no fragment, the browser focuses the step field and scrolls it into view.
  With a fragment (step Done/Delete, and Done/Undo/Delete of safe-toggles), the browser skips
  autofocus and only scrolls.
- `?open=` with a number that is not on the page: no step field gets autofocus and "New to-do"
  does not either. Harmless.

### 6. Move up and Move down keep their slot

In the manual order, when a row has only one Move button, the missing one is replaced by `<span
class="move-slot" aria-hidden="true"></span>`. In `app.css`, Move buttons and `.move-slot` get
the same fixed width (`--control-height-compact`, and `--control-height-touch` under a finger).
The slot is not a button: nothing to tab to, nothing read out. A list with one to-do still shows
no Move form at all (nothing to line up with). The labels and `title`s of the Move buttons do
not change.

### 7. Page titles and the edit heading

| Page | `<title>` | `<h1>` |
|---|---|---|
| List | `<list name> – To-do list` | `<list name>` (as today) |
| Edit | `Edit “<title>” – To-do list` | `Edit “<title>”` |
| New list | `New list – To-do list` | as today |
| Rename list | `Rename list – To-do list` | as today (`Rename “<name>”`) |
| Delete list | `Delete list – To-do list` | as today |

With `Error: ` before it when decision 4 applies. The separator is an en dash with spaces, as
asked. The edit page uses the **saved** title: `todo_edit` passes `saved_title = todo.title`,
read before the form is bound, because a ModelForm copies a valid typed title into the instance
even when another field fails. `base.html`'s default title stays "To-do list".

### 8. Sign-up help in plain English

`accounts/forms.py`, `SignupForm.__init__` sets the help texts (the checks stay Django's own):

- Username: "Up to 150 characters: letters, numbers and @ . + - _ (no spaces)."
- Password: "Use at least 8 characters. Not only numbers, not a common password, and not too
  close to your username." (It starts with "Use", so the existing check in
  `accounts/tests/integration/test_auth_pages.py`
  `test_signup_help_text_is_shown_and_linked_to_its_input`, which looks for the lower-case
  "at least 8 characters", still passes; only its comment, if it names Django's text, changes.)
- Password confirmation: "Type the same password again."

The "8" comes from the `MinimumLengthValidator` in `AUTH_PASSWORD_VALIDATORS` (its default). A
test checks that the help text names the validator's real `min_length`, so the text cannot lie
after a settings change.

### 9. "My lists" and "Shared with me" without a colon; "Leave this list" asks first

- `todo_list.html`: `<span class="menu-label">My lists</span>` and `Shared with me`.
- Leave becomes a `<details class="leave">` like Clear completed: `<summary>Leave this
  list</summary>`, then a form with `<p>Leave “<list>”? Only <owner> can share it with you
  again.</p>` and `<button class="button button-secondary" type="submit">Yes, leave the
  list</button>`. Secondary, not danger: nothing is deleted.
- The view `list_leave` does not change (POST only, members only).

### Respecting the app redesign

- No icons (decided by the person): only text and the existing ↑ ↓ ⠿ characters.
- The row Delete stays quiet gray, red on hover and focus (decided by the person).
- Exact-HTML tests from `docs/plans/app-redesign.md` that this plan keeps: the filter links
  (`html=True`, no new attribute), the search input, the sort form start, the priority select,
  `<summary aria-label="Notes for …">Notes</summary>`, `<details class="steps" open>`,
  `<span class="overdue-label">Overdue</span>`, Cancel links, `aria-current="page">` twice.
  `<details class="steps" open>` keeps its attributes (only the summary text gets a hidden span).

Tests that **must** change, and why:

| Test | Change | Why |
|---|---|---|
| `todos/tests/integration/test_lists.py` line 176 | `<title>&lt;b&gt;x&lt;/b&gt; – To-do list</title>` | Decision 7. |
| `todos/tests/integration/test_views.py` `test_heading_is_fixed_and_title_is_escaped` (line 499) | Renamed `test_heading_names_the_todo_and_escapes_it`; checks `<h1>Edit “&quot;&gt;&lt;script&gt;x&lt;/script&gt;”</h1>` and no `<script>x`. | Decision 7: the heading now names the to-do. Escaping is still checked. |
| `todos/tests/integration/test_views.py` `test_add_input_keeps_its_browser_checks` | Still finds `autofocus` (no `open`); a new test checks it is gone with `?open=`. | Decision 5. |
| `todos/tests/integration/test_subtasks.py` `test_add_a_step`, `test_list_member_can_change_steps` and `test_after_action_details_is_open` (all three add a step; the helper `back_url()` gets a `fragment=True` argument) | The add redirect is `?open=<pk>` with no fragment. | Decision 5. |
| `todos/tests/cuj/test_journeys.py` lines 515, 698-699, 901-902, 935-936 | `name="Done", exact=True` and `name="Delete", exact=True` become the full names (`f"Done: {title}"`, `f"Delete: {title}"`). | Decision 1: the accessible name is now longer. Lines 79, 81, 84, 135, 165, 384 and 462 match a part of the name and still pass. |
| `todos/tests/cuj/test_journeys.py` line 444 | Click the "Leave this list" summary, then the "Yes, leave the list" button. | Decision 9. |

## Security

- No new view, URL or form field that saves data. `list_leave` is unchanged.
- Every new text that holds user data (titles, list names, owner names in `aria-label`s, hidden
  spans, `<title>`, `<h1>`) goes through Django's autoescape. Tests use `<b>"x` titles.
- `?open=` is only compared with the to-do's id, never printed (as today). `back_to_steps` still
  builds its address only from database numbers.
- No JavaScript is added.

## Data and migrations

No model change, no migration. Going back: revert the commit.

## Working next to

Merge order: **safe-toggles → accessibility-pass (this) → local-safety → maintenance-pass**.

- After safe-toggles: the row forms already have the hidden `done` and `next` with the anchor;
  this plan only adds `aria-label`s to the buttons. "New to-do" autofocus: safe-toggles keeps it;
  this plan adds the `open` condition.
- local-safety changes `todos/models.py` (the repeat error goes on `due_date`), `queries.py`,
  `forms.py` comments and the `Makefile`. It does not touch these templates. Both touch
  `AGENTS.md` (different rows) and `todos/tests/integration/test_views.py` (different classes).
- maintenance-pass moves tests from `test_views.py` and uses `TodoQueryForm.STATUS_CHOICES` in
  the filter links; it merges last and moves what this plan adds.

## Not part of this task

- A skip link, landmarks or heading changes beyond the edit `<h1>`.
- An error summary on the list page's add form.
- Making the done state visible in another way than the line and Undo.
- Lighter or `spaceless` list HTML (Left for the person).

## Changes to files

| File | Change |
|---|---|
| `todos/templates/todos/_todo_item.html` | Decisions 1, 2, 5 (step autofocus), 6 (move slot). |
| `todos/templates/todos/todo_list.html` | `<title>` (7), "New to-do" autofocus only without `open` (5), captions without colon and the Leave `<details>` (9). |
| `todos/templates/todos/todo_edit.html` | `<title>`, `<h1>` with `saved_title`, `Error: `, the alert line (4, 7). |
| `todos/templates/todos/list_form.html`, `list_confirm_delete.html` | `<title>` (7); `list_form.html` also `Error: ` and the alert line (4). |
| `todos/views.py` | `back_to_steps(todo, *, to_new_step=False)`; `subtask_add` passes `True`; `todo_edit` passes `saved_title`. |
| `todos/static/todos/app.css` | The coarse-pointer rules (3), `.move-slot` and the fixed Move width (6), `.form-error-summary` (4), `details.leave` like `details.clear-completed`, taking over `form.leave`'s `margin-top`, `padding-top` and `border-top` (the form is now inside it). |
| `accounts/forms.py` | `SignupForm` help texts (8). |
| Tests | See "Tests" and the table of tests that must change. |
| `AGENTS.md` | Rows for `_todo_item.html`, `todo_list.html`, `todo_edit.html`, `list_form.html`, `views.py` (`back_to_steps`), `app.css` (touch rule list), `accounts/forms.py` (help texts). |
| `README.md` | "Share a list": leaving asks first. |

## Steps

1. **Tests first**: the new integration tests, then the changed ones. `make integration`: the new
   ones fail. Show the person.
2. Decisions 1, 2 and 9 (templates), 7 and 4 (titles, alert), 8 (sign-up).
3. Decision 5 (`back_to_steps`, the two autofocus rules).
4. Decisions 3 and 6 (CSS) with the CUJ tests; `make cuj`.
5. `make test`; update the docs; `make check`; commit.
6. The landing page shows real screenshots of the app. Run `make landing-shots` (scratch data, a
   free port, never `db.sqlite3`) and, if pictures changed, commit them after
   `todos/tests/unit/test_webp_size.py` and the landing width and height tests pass. Last commit:
   Status `**done** (<date>)`.

## Tests

### Integration

| File, test | What it checks | The break that fails it |
|---|---|---|
| `test_views.py` `ListTests.test_row_buttons_name_their_todo` | For a to-do `<b>"x`: `aria-label="Done: &lt;b&gt;&quot;x"` and `aria-label="Delete: &lt;b&gt;&quot;x"`; for a done one `aria-label="Undo: …"`; the visible text is still `Done`/`Undo`/`Delete`. | A missing or unescaped label. |
| `test_views.py` `ListTests.test_done_todo_says_done_to_screen_readers` | A done to-do's row has `<span class="visually-hidden">Done: </span>` right before `<span class="title">`; an open one does not. | Leaving it out, or putting it inside the title span. |
| `test_subtasks.py` `test_steps_summary_names_the_todo` | "Add steps" plus hidden " to <title>"; "Steps: 1 of 2 done" plus hidden " in <title>"; "Steps: 1 of 2 done" is still one piece of text. | Breaking the visible text, or no name. |
| `test_subtasks.py` `test_after_add_step_the_step_field_has_autofocus` | `subtask_add` redirects to `?open=<pk>` (no `#`); that page's "New step for <title>" input has `autofocus`, other rows' do not, and "New to-do" has none. | A fragment on the add redirect (the browser would skip autofocus), or two autofocus fields. |
| `test_subtasks.py` `test_step_done_keeps_the_fragment` | Step Done and Delete still go to `?open=<pk>#todo-<pk>`. | Moving the cursor on every step click. |
| `test_views.py` `EditTests.test_bad_edit_says_error_in_title_and_alert` | An empty title: `<title>` starts with `Error: Edit “`, the page has the summary with `role="alert"`, `tabindex="-1"`, `autofocus` and "Not saved."; a valid GET has neither. | No title prefix or no alert. |
| `test_views.py` `EditTests.test_title_and_heading_use_the_saved_title` | A valid new title with bad tags: `<h1>` and `<title>` show the **old** title. | Using the half-validated instance. |
| `test_lists.py` `test_bad_new_list_and_rename_say_error` | Duplicate names on New list and Rename: `Error: ` in `<title>` and the alert line. | Leaving out one page. |
| `test_lists.py` `test_page_titles` | List, New list, Rename, Delete list titles end with ` – To-do list`. | A missing suffix. |
| `accounts/tests/integration/test_accounts.py` `test_signup_help_is_plain` | The sign-up page shows the three new help texts and not "Required." or "for verification". | Django's default text. |
| `accounts/tests/integration/test_accounts.py` `test_password_help_names_the_real_minimum` | The password help contains `str(min_length)` of the `MinimumLengthValidator` from `get_default_password_validators()`. | A settings change that makes the text wrong. |
| `test_sharing.py` `test_leave_asks_first` | A member's page has `<details class="leave">` with the summary "Leave this list" and a "Yes, leave the list" button inside its form; no "My lists:" or "Shared with me:" with a colon. | One-click leave, or the old caption. |

### CUJ: `todos/tests/cuj/test_journeys.py`

| Test | What it checks | The break that fails it |
|---|---|---|
| `TouchTests.test_row_and_step_buttons_fit_a_finger` (extended) | Also: the steps and notes summaries, Clear completed summary, the three filter links, the list menu links, Rename and Delete list: each at least 44px tall, and 8px apart where they are side by side. | A rule left out of the coarse block. |
| `test_move_buttons_keep_their_slot` | Manual order, three to-dos, at 1280 and 390: the x of Edit, Done and Delete is the same on all three rows. | No slot on the first or last row. |
| `test_add_steps_with_the_keyboard` | Open the steps of a to-do, type a step, press Enter; after the page loads, type the second step at once (the field is focused) and press Enter: both steps are there. | No autofocus, or the autofocus on "New to-do". |
| `test_leave_asks_first` (or the changed line 444 journey) | Clicking "Leave this list" opens the question; the list is only left after "Yes, leave the list". | One-click leave. |

## Decided by the orchestrator for the person (2026-10-11, person away)

- Names: "Done: <title>", "Undo: <title>", "Delete: <title>"; steps summary with hidden " to
  <title>" / " in <title>".
- Error line text: "Not saved. Fix what is marked below."; `Error: ` before the page title.
- Page titles with " – To-do list"; the edit heading names the to-do (saved title).
- The step field gets the cursor only after "Add step"; step Done/Delete keep the fragment.
- Move slot: an empty, hidden-from-readers span of the same width.
- Sign-up help texts as in decision 8.
- Leave asks first with a gray (secondary) button, not a red one.
- The landing screenshots are taken again after this plan (`make landing-shots`).

## Left for the person

- **"Leave this list" now asks first.** This is a change in behaviour (one more click). Review it
  when you are back; it is easy to undo.
- **Lighter list HTML** (`{% spaceless %}` or fewer wrappers). Recommended: not now; it changes
  many exact-HTML tests for a small gain on a local app.
- **Renaming the `todo_list` URL and view to `home`.** Recommended: not now; many tests and
  templates use the name.

## Review

Verification by the planner (2026-10-11), against `main` (`6c7169b`):

- Confirmed every "What is wrong" item by reading `_todo_item.html`, `todo_list.html`,
  `todo_edit.html`, `list_form.html`, `app.css` (the coarse block lists only row, step and
  add-step controls; `nav.filter` gap is 2px), `accounts/forms.py` (no help text override) and
  `list_leave`.
- Found while checking: in Chromium, `autofocus` is skipped when the address has a fragment that
  names an element (tested with a small Playwright script). So "autofocus when `?open=` matches"
  alone would never work, because `back_to_steps` adds `#todo-<pk>`. Decision 5 drops the
  fragment for "Add step" only. Two `autofocus` fields would also pick "New to-do" first, so it
  gets the `open` condition.
- Found while checking: CUJ tests use `name="Done", exact=True` and `name="Delete", exact=True`
  in five places; they must use the full names. Listed above.
- Found while checking: a ModelForm copies a valid typed title into `todo` even when the form
  fails, so the heading would show an unsaved title. Decision 7 passes `saved_title`.
- Changed from the request: the "Done: " text is put before the title span, not inside it, to
  keep an existing exact test and the CUJ title reads.

The plan review (2026-10-11) said APPROVE WITH CHANGES. What changed:

- The password help starts with "Use at least 8 characters", so
  `test_signup_help_text_is_shown_and_linked_to_its_input` (lower-case "at least 8 characters")
  keeps passing.
- Under a finger, `nav.lists .menu` gets only a bigger row gap (the 16px column gap stays);
  `details.leave` takes over `form.leave`'s top margin, padding and line.
- No claim that `role="alert"` is announced on load; the error summary gets `tabindex="-1"` and
  `autofocus`, and the `Error: ` title is the reliable part.
- New last step: `make landing-shots`, and commit changed pictures (orchestrator's choice).
- Left for the person: "Leave asks first" is a behaviour change to review.
