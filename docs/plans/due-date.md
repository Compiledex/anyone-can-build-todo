# Plan: a due date on a to-do (feature #6)

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.
This version includes the fixes from two adversarial reviews, and fits the build order (wave 2).

**Builds on:**

- **Wave 0, the test pyramid**: tests go in `todos/tests/unit/`, `todos/tests/integration/` or
  `todos/tests/cuj/`, and the migration check is already in `make check`.
- **Wave 0, the foundation**: the Django form `TodoForm` in `todos/forms.py` (used by `todo_add`),
  the partial template `todos/templates/todos/_todo_item.html` (one row of the list), the page
  colors as CSS variables on `:root`, and the shared page `todos/templates/base.html`. **All the
  CSS lives in `base.html`**, so the new CSS in this plan goes there, not in `todo_list.html`.
- **Wave 1, #17 accounts**: every to-do has an owner. Each person sees and changes only their own
  to-dos. Every view needs a logged-in person.
- **Wave 1, #20 dark mode**: every color has a light value and a dark value.

**Built in the same wave (wave 2), at the same time:** #4 edit and #10 lists. This plan does not
assume they exist. "Working next to #4 and #10" below says how the three fit together.

## Goal

A person can give a to-do a due date when they add it. The list shows the due date, and marks
to-dos that are past their due date and not done.

The due date is **optional**. A to-do without one works exactly as it does today.

## Decisions

- **The due date is optional.** An empty date field means "no due date".
- **Dates in the past are allowed when adding.** It is the simplest rule, and a person may want
  to note something that is already late.
- **"Due today" is not overdue.** A to-do is overdue only from the day after its due date.
- **A bad form shows an error and keeps what was typed.** If the date does not exist (for example
  `2026-02-30`), the page is shown again with an error message, and the title and date the person
  typed are still in the fields. Wave 0 already does this for the title, with `TodoForm`. The date
  uses the same pattern.
- **The list keeps its order**: by when the to-do was made, as today.
- **Dates use the format `YYYY-MM-DD` only.** The browser's date picker always sends this format.
  We do not accept other formats like `10/12/2026`, because they can mean two different dates.
- **The due date is a field of `TodoForm`.** So every page that uses `TodoForm` gets it: the add
  form now, and the edit page from #4. The form gives the field a date widget
  (`<input type="date">`), so a page that lets Django draw the field still gets a date picker.
- **The due date is shown in `_todo_item.html`**, the partial for one row. So it shows on every
  page that lists to-dos, including the list pages from #10.
- **The red "overdue" color is a CSS variable** (`--overdue`), with a light and a dark value, like
  every other color since dark mode (#20). Light: `#b00020` (about 7.3 : 1 on `#ffffff`). Dark:
  `#ff6b6b` (about 6.8 : 1 on `#121212`), the value the dark-mode plan suggests. `#b00020` must
  **not** be used on the dark background: there it is only about 2.6 : 1, too dark to read.
- **Overdue is shown with a word, not only with a color.** An overdue row shows the word
  "Overdue" next to the date. A person who cannot see red, or who uses a screen reader, still
  knows. It also gives the tests something exact to look for.
- **Accounts change nothing here.** A due date belongs to a to-do, and the to-do already belongs
  to one person. This feature adds no new address (URL) and no new way to reach a to-do.

## Not part of this task

- **Changing the due date of a to-do that already exists.** This comes from #4 (edit), built in the
  same wave. The edit page uses `TodoForm`, so once both are merged it shows and saves the due
  date, including clearing it. See "Working next to #4 and #10" for who adds the date input and
  the tests. Until #4 is merged there is no way for a person to change a due date. (The Django
  admin, `/admin/`, is now only for staff, so it is not the answer for normal users.)
- **Sorting the list by due date.** That is #14 (sort), in wave 5.
- **Showing only overdue to-dos.** That is #13 (filter), in wave 5.
- **Reminders by email, or notifications.** That is #7 (reminders), in wave 4.
- **Repeating due dates.** That is #8 (recurring), in wave 4.
- A time of day. The due date is only a date.
- **The time zone.** `config/settings.py` has `TIME_ZONE = "Asia/Tokyo"`, so "today" means the
  date in Tokyo, for every person. A time zone per person is a separate decision. The code in this
  plan works for any time zone.

## Working next to #4 and #10

All three features are built at the same time, so the one merged later must fit with the one
merged earlier. "Merge" means: put a branch's changes into `main`.

- **The migration.** A migration is a file Django writes that changes the database tables. #10
  also changes the `Todo` table, so both branches may make a migration with the same number. If
  #10 is merged first: update this branch from `main`, delete this branch's own unmerged migration
  file, and run `makemigrations` again. Django then writes a new one that comes after #10's. This
  is not editing a migration by hand: the file is made again by Django.
- **The add form and the view.** The lists plan keeps the name `todo_add`, but moves it to
  `/lists/<int:pk>/add/` (it now needs the list's `pk`), and the list page becomes `list_detail`.
  If #10 is merged first: the date input goes in the add form on the list page; step 5 checks
  `todo_add` at its new address; and the integration tests post to `todo_add` with the list's
  `pk` and read `list_detail` instead.
- **The owner.** The lists plan removes `Todo.owner`; the owner becomes `todo.todo_list.owner`.
  If #10 is merged first, this plan's tests make to-dos the way the merged tests do (inside a
  list of the user), not with `owner=...`. Nothing in this plan's model code touches the owner,
  so only the tests change.
- **The edit page (#4).** The edit plan draws the whole form with Django (`form.as_div`), so the
  date input appears on the edit page by itself, with no template change. Its test
  `test_edit_page_shows_every_form_field` already checks that the input is there. What is left
  is one test: `test_edit_clears_due_date` (in the table below). Whichever of #4 and #6 is merged
  **second** adds it. Either way, it is added exactly once.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | New field `due_date`, new method `is_overdue()`. |
| `todos/migrations/` | One new migration, made by Django. Existing to-dos get no due date. |
| `todos/forms.py` | `TodoForm` gets the field `due_date`. |
| `todos/views.py` | Nothing, if wave 0's `todo_add` already shows the page again with the form on error. |
| `todos/templates/todos/todo_list.html` | The date input in the add form (on the list page from #10, if that is merged first). |
| `todos/templates/base.html` | The `--overdue` color (light and dark value); the CSS for a narrow screen. |
| `todos/templates/todos/_todo_item.html` | The due date in each row, the class `overdue`, and the word "Overdue". |
| `todos/tests/unit/test_models.py` | Four `is_overdue` tests. |
| `todos/tests/integration/test_views.py` | Add and list tests (see "Tests"). |
| `todos/tests/cuj/test_journeys.py` | One step added to the existing journey; the readability test from #20 also checks the overdue color. |
| `AGENTS.md`, `README.md` | `due_date` in the file table; the new test numbers. |

## Tests

Each test goes in the folder for its layer. The rule is: **test each rule once, in the lowest
layer where a person would notice it.**

- **Unit** (`todos/tests/unit/test_models.py`, `SimpleTestCase`): `is_overdue`. `Todo(...)` is
  made in memory and never saved. Each test passes a fixed `today`, for example
  `date(2026, 10, 9)`, so it gives the same answer on any computer, at any time of day.
- **Integration** (`todos/tests/integration/test_views.py`, Django test client): what the add form
  and the list page do. Every test logs in a user first with `self.client.force_login(user)`,
  because every view needs a logged-in person since #17. Tests go in the existing small classes by
  topic (`AddTests`, `ListTests`). Page tests use dates far from today (30 days away), so they do
  not depend on the time of day.
- **CUJ** (`todos/tests/cuj/test_journeys.py`, a real browser): only that the date picker, the
  form and the page work together. It does not test the overdue rule again.

| Layer | Test | What it checks |
|---|---|---|
| unit | `test_past_due_date_is_overdue` | Due the day before `today`, and not done: overdue. |
| unit | `test_due_today_is_not_overdue` | Due on `today`: not overdue. |
| unit | `test_done_todo_is_not_overdue` | Done, and due before `today`: not overdue. |
| unit | `test_no_due_date_is_not_overdue` | No due date: not overdue. |
| integration | `test_add_a_todo_with_a_due_date` | A to-do added with `2026-10-12` gets that date. |
| integration | `test_add_a_todo_without_a_due_date` | With an empty date field, `due_date` is `None`. |
| integration | `test_invalid_due_date_is_not_added` | `2026-02-30` saves nothing. The answer is the page (status 200, not a redirect), with the date error, and the typed title still in the title field. |
| integration | `test_other_date_format_is_not_added` | `10/12/2026` saves nothing. |
| integration | `test_list_shows_due_date` | The page contains the exact text `Due 12 Oct 2026`. |
| integration | `test_list_marks_overdue_todo` | A to-do due 30 days ago, not done: the page contains `<span class="overdue-label">Overdue</span>` (checked with `assertContains(..., html=True)`). |
| integration | `test_list_does_not_mark_todo_that_is_not_late` | Two to-dos: one due in 30 days, and one due 30 days ago but done. The page does not contain that `<span>` (`assertNotContains(..., html=True)`). |
| integration | `test_other_users_due_date_is_not_shown` | User A's to-do has a due date. User B's list page does not show A's to-do or its date. |
| cuj | `test_plan_and_finish` (changed) | "Buy milk" is added with the due date `2030-01-15`, typed into the date input with Playwright's `fill("2030-01-15")`, and the row shows `Due 15 Jan 2030`. |
| cuj | `test_readable_in_light_and_dark` (from #20, changed) | Also add one overdue to-do (its date typed with `fill`, 30 days ago), and check that the red date has at least 4.5 : 1 contrast on the background, in both modes. |
| integration | `test_edit_clears_due_date` | *Added by whichever of #4 and #6 merges second.* A to-do with a due date; the edit page is sent an empty date field; `due_date` is now `None`. |

**Why the overdue tests look for the `<span>`, not for `<li class="overdue">`.** With
`html=True`, Django compares whole elements, including what is inside them. The text
`<li class="overdue">` is read as an *empty* `<li>`, so it would never match a real row. The
"is marked" test would always fail, and worse, the "is not marked" test would always pass, even
if the feature were broken. The `<span>` is small and has exactly known content, so it matches.

**Why the readability tests change.** Every new color must reach 4.5 : 1 in both modes (the
build-order rule). Only a real browser knows which color is really painted, so the check goes in
the CUJ test that #20 already made for this, not in a new test.

Two tests that the first draft had are gone on purpose:

- `test_long_title_is_not_added`: the 200-character rule came with `TodoForm` in wave 0, and is
  tested there. Testing it again here would test one rule twice.
- The CUJ test `test_overdue_todo`: the overdue rule is already tested in the unit layer, and the
  `overdue` class in the integration layer. A browser test would test it a third time.

All tests that exist before this change must still pass, especially the empty-title test. We do
not write the total number here, because #4 and #10 add tests at the same time. The runner prints
the real numbers per layer.

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in the table above (not the edit test yet). Run `make test` and show that they
fail.

Start with `test_past_due_date_is_overdue`, because it fails on its assertion, not only because
something is missing. Two tests — `test_due_today_is_not_overdue` and
`test_done_todo_is_not_overdue` — guard the edges. They would pass against a method that always
says "not overdue", so they are not "shown failing" in a meaningful way. We say this in the pull
request instead of pretending.

### 2. The model — `todos/models.py`

Add an import, one field and one method. Do not touch the other fields (`owner` from #17, or
`todo_list` from #10 if it is merged first):

```python
from django.utils import timezone


class Todo(models.Model):
    ...
    due_date = models.DateField(null=True, blank=True)
    ...

    def is_overdue(self, today=None):
        if self.done or self.due_date is None:
            return False
        if today is None:
            today = timezone.localdate()
        return self.due_date < today
```

- `DateField` stores only a date, with no time of day.
- `null=True` lets the database store "no due date". `blank=True` lets the form accept an empty
  field.
- `timezone.localdate()` gives today's date in the time zone set in `config/settings.py`.
- The `today` parameter lets the tests pass a fixed date. The page calls `is_overdue` with no
  argument, so it uses the real date.

### 3. Migration — `todos/migrations/`

Run:

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

Django makes the new file by itself (its number comes after the migrations from #17, and maybe
#10). It must not be edited by hand. To-dos that already exist get no due date (`NULL`), so
nothing about them changes.

### 4. The form — `todos/forms.py`

Add `due_date` to the `TodoForm` from wave 0. Keep everything else in it (for example, how it
leaves out `owner`):

```python
class TodoForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = Todo
        fields = ["title", "due_date"]  # plus any field wave 0 already has
```

- `input_formats` accepts only `YYYY-MM-DD`.
- The widget draws `<input type="date">` and writes an existing date as `YYYY-MM-DD`, the only
  format a date picker reads. This matters for #4's edit page, which shows the saved date.
- `owner` is **not** a form field. The view sets it, so a person cannot send a different owner.

### 5. The view — `todos/views.py`

Probably nothing. Check that wave 0's `todo_add` (at `/lists/<int:pk>/add/`, if #10 is merged
first) does this, and change it only if it does not:

- Valid: `form.save(commit=False)`, set the owner (#17) or the list (#10), save, and send the
  browser back to the list.
- Invalid: show the list page again with this form (`render`, not `redirect`), so the error and
  the typed values are shown. The page must still show the person's own to-dos.

`todo_add` still accepts `POST` only.

### 6. The pages

**`todos/templates/todos/todo_list.html`** (or wherever the add form is after #10):

- Add a date input to the add form, with `aria-label="Due date"` and
  `value="{{ form.due_date.value|default_if_none:'' }}"`, so a typed date comes back after an
  error. Write it the same way wave 0 writes the title input (by hand, or with `{{ form.due_date }}`).
  It is not required.
- Show `form.due_date.errors` next to the title errors that wave 0 already shows.

**`todos/templates/todos/_todo_item.html`** (one row):

- Show the due date when there is one, with the year, so a date next year is not mistaken for this
  year:
  `<time datetime="{{ todo.due_date|date:'Y-m-d' }}">Due {{ todo.due_date|date:'j M Y' }}</time>`.
  This shows, for example, "Due 12 Oct 2026". The `datetime` attribute helps screen readers.
- When `todo.is_overdue`: add the class `overdue` to the `<li>` (keep any class wave 0 already
  puts there, such as `done`), and after the `<time>` add
  `<span class="overdue-label">Overdue</span>`. A to-do can have `done` or `overdue`, but never
  both, because a done to-do is never overdue.

**The style** (in `todos/templates/base.html`, where all the CSS is since wave 0):

- A new variable `--overdue`: `#b00020` in the light `:root` block, and `#ff6b6b` in the dark
  block from #20. Both are at least 4.5 : 1 on their background (see "Decisions").
- `.overdue time, .overdue-label { color: var(--overdue); }` shows the date and the word in red.
- `form.add { flex-wrap: wrap; }` and `form.add input[type=date] { flex: 0 0 auto; }` keep the
  title field wide on a phone. Without them, the title and the date each take half the row.

### 7. Checks — already done

The test pyramid work already added the migration check to `make check` and to `check.yml`:

```bash
uv run python manage.py makemigrations --check --dry-run
```

It fails if `models.py` has a change with no migration. Nothing to do here.

### 8. Fit with #4 and #10

Before the pull request, update the branch from `main` and follow "Working next to #4 and #10":
make the migration again if needed, move the add-form changes and the tests to `todo_add` (with
the list's `pk`) and `list_detail` if #10 is already merged, and add `test_edit_clears_due_date` if #4 is already
merged. That test should pass at once (the form already allows an empty date); say so in the pull
request, as in step 1.

### 9. Docs

- `AGENTS.md`: in the table, `models.py` gets `due_date`.
- `README.md`: update the example layer summary under "Run the tests" to the real numbers from
  the runner.

### 10. Before the commit

- Run `make check`. It runs the commit checks, the migration check, and the tests.
- Open the page with `make run`, log in, add a to-do with and without a date, and look at it on a
  narrow window, in light and in dark mode.

## Check in the code before starting

These are not questions for a person. Read the merged wave 0 code and follow it:

- **Does `todo_add` already show the page again on an invalid form?** This plan assumes yes
  (step 5). If not, step 5 is real work, and it changes behavior for the title too. Then also add
  a test for the title error in the same way.
- **Are the add form's inputs written by hand, or drawn by Django (`{{ form.title }}`)?** Write
  the date input the same way. Either works with the form in step 4.

## Open questions

- **Whose "today"?** `TIME_ZONE = "Asia/Tokyo"`, so a to-do turns overdue at midnight in Tokyo,
  for every user. Now that there are accounts, a user in Europe sees a to-do turn red in their
  afternoon. This plan keeps one time zone (a time zone per person is a separate feature). Is
  Tokyo the right one for the people who use this site?

## Review

Changes made by the second adversarial review:

- The overdue tests looked for `<li class="overdue">` with `html=True`. Django reads that as an
  empty `<li>`, so the "not marked" test passed even with a broken feature. They now look for a
  small `<span class="overdue-label">Overdue</span>`.
- Overdue was shown by color only. Added the word "Overdue", for people who cannot see red and for
  screen readers.
- The dark red was `#ff6b81`, while the dark-mode plan suggests `#ff6b6b`. Now `#ff6b6b`, with the
  contrast numbers written down, and a warning that `#b00020` is about 2.6 : 1 on dark.
- No test checked the new color's contrast. The readability CUJ test from #20 now checks it.
- The CSS was placed in `todo_list.html`. Since wave 0 all CSS is in `base.html`; moved there.
- The plan said `Todo.owner` "stays" and the add view is at `/add/`. The lists plan (#10, same
  wave) removes `Todo.owner` and moves `todo_add` to `/lists/<int:pk>/add/`. Added what to do if
  #10 merges first.
- The edit page draws the form with Django (`form.as_div`), and #4 already tests that every form
  field is there. Removed the edit-page input work and the duplicate `test_edit_changes_due_date`;
  kept only `test_edit_clears_due_date`, added by whichever of #4 and #6 merges second.
- The CUJ said "through the date picker". Playwright cannot click the browser's own date picker;
  it types with `fill("YYYY-MM-DD")`. Said so.
- `test_invalid_due_date_is_not_added` now also checks status 200 (the page is shown again, not a
  redirect), and the "not marked" test also covers a done to-do with a past date.
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- Time zone: keep `TIME_ZONE = "Asia/Tokyo"`, the same as the person's computer.

## Post-review check

- The status edit left half a sentence ("fixes from two adversarial reviews, ...") on its own line. Restored it as a full sentence.
