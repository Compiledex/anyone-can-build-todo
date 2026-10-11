# Plan: a priority on a to-do (#9)

Status: **done** (2026-10-09, PR #14). The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (`TodoForm` in `todos/forms.py`, the partial template
`todos/templates/todos/_todo_item.html`, colors as CSS variables on `:root`, the shared
`todos/templates/base.html` that holds all the CSS), #17 accounts, #20 dark mode, #10 lists,
#4 edit, #6 due date.

Same wave (3), built at the same time: #5 description, #11 tags, #19 clear completed, #18 sharing.
This plan does not assume any of them.

## Goal

Each to-do has a priority: **Low**, **Medium** or **High**. A person chooses it when they add a
to-do, and can change it on the edit page. The list shows the priority of each to-do as a word,
not only as a color.

## Decisions

- **Django `IntegerChoices`.** `IntegerChoices` is a Django class for a field that may hold only a
  few fixed values. Each value is a number with a label. The class lives inside the model, as
  `Todo.Priority`:

  | Name | Number in the database | Label on the page |
  |---|---|---|
  | `LOW` | 1 | Low |
  | `MEDIUM` | 2 | Medium |
  | `HIGH` | 3 | High |

  **A bigger number means more important.** So #14 (sort) can sort by the number: `-priority`
  gives High first. We store a number, not a word, because words sort by the alphabet
  ("High" < "Low" < "Medium"), which is wrong.
- **The default is Medium**, for new to-dos and for to-dos that already exist. Medium is the
  neutral middle: it says "nothing special". A person changes it only when a to-do is more or
  less important than usual.
- **There is no "no priority".** Every to-do has one of the three. A fourth "empty" state would
  make the form, the page and #14 sort more complex, for little gain. The field is not nullable.
- **Where it is chosen:** a drop-down list (`<select>`) in the add form, with Medium already
  selected; and on the edit page from #4, showing the current priority. The edit page draws every
  field of `TodoForm` by itself (`form.as_div`), so the edit template does not change.
- **A request with no priority does not change the priority.** The page always sends a priority.
  But the tests of other features (and older tests) post only a title, to add or to edit. They
  must keep working, and they must not change data by accident. So:
  - adding with a missing or empty priority gives **Medium** (the model default);
  - editing with a missing or empty priority **keeps** the priority the to-do already has.

  We checked this: Django's usual way (`required=False` with `empty_value=MEDIUM`) gets adding
  right, but on the edit page it silently resets a Low or High to-do to Medium. Step 4 avoids that.
- **A priority that is not 1, 2 or 3** (for example `7` or `urgent`) is an error: nothing is saved,
  and the page shows the error and keeps what was typed, as for a bad due date in #6.
- **How it is shown: a word on every row.** Each to-do shows a small label "Low", "Medium" or
  "High". Before the word there is the text "Priority:" that only screen readers read (a
  "visually hidden" text, see step 6). So a screen reader says "Priority: High". This is the
  accessibility rule: never show information **only** with color.
- **Every row shows the label, also Medium.** If Medium showed nothing, the meaning of "no label"
  would be hidden. Showing all three is simpler and clear. (See "Open questions".)
- **Only one new color.** High gets a new color variable, `--priority-high`. Medium uses the normal
  text color (`--text`) and Low the grey color (`--muted`), which exist already. Fewer new colors
  means fewer dark-mode values to check. The High color must not be the same red as `--overdue`
  from #6, so "High" and "overdue" do not look like one thing.
- **The CSS class uses the number, not the label**: `priority-3`, not `priority-high`. The label
  is text for people, and may be translated one day; the number never changes.
- **Done to-dos keep their priority.** The label stays, grey like the rest of a done row.
- **Accounts and lists:** the priority is saved and changed only through the add and edit views.
  After #10 they find the list and the to-do through the owner of the list
  (`todo.todo_list.owner`). Nothing new is needed for safety. One test checks that user B cannot
  change the priority of user A's to-do (404, not 403), as every feature must.

## Not part of this task

- **Sorting by priority.** That is #14. The list keeps the order it has today.
- **Filtering by priority** ("show only High"). That is #13.
- A database index on `priority`. #14 can add one if it is needed.
- Changing the priority straight from the list with one click. The edit page is enough.
- More than three levels, or levels a user can name.
- Translating the labels into other languages.
- #5 description, #11 tags and #18 sharing are in the same wave. This plan does not assume them.
  #5 and #11 also add fields to `TodoForm` and a migration, so the one merged later must update
  from `main` (see step 3). If #18 lets shared people edit, it changes the lookup in `todo_edit`;
  the priority follows with no extra work.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | `Todo.Priority` (`IntegerChoices`) and the field `priority`. |
| `todos/migrations/000N_todo_priority.py` | Made by Django. Existing rows get Medium. |
| `todos/forms.py` | The field `priority` in `TodoForm`, and a small `clean_priority` method. |
| `todos/templates/todos/todo_list.html` | The `<select>` in the add form, and its errors. |
| `todos/templates/todos/_todo_item.html` | The priority label in each row. |
| `todos/templates/base.html` | The CSS: `.visually-hidden`, `.priority`, `--priority-high` (light and dark). |
| `todos/tests/unit/test_models.py` | One unit test. |
| `todos/tests/integration/test_views.py` | The integration tests. |
| `AGENTS.md`, `README.md` | The file table and the test numbers. |

`todos/views.py` does **not** change: the add view (`todo_add`, at `/lists/<int:pk>/add/` since #10) and the edit view
already use `TodoForm`. If a view lists the form fields by hand, add `priority` there.

The edit template from #4 does **not** change: it draws the form with `form.as_div`, which shows
the new field with a label and its errors by itself.

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first — `todos/tests/`

Write the tests in step 8. Run `make test` and show that they fail. Start with
`test_add_a_todo_with_high_priority`: it fails because `Todo` has no `priority` yet.

### 2. The model — `todos/models.py`

```python
class Todo(models.Model):
    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    # ... the fields that exist ...
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.MEDIUM
    )
```

- `PositiveSmallIntegerField` stores a small whole number that is 0 or more. 1 to 3 fits.
- `choices` tells Django (the form, the admin) which values are allowed, and gives
  `todo.get_priority_display()`, which returns the label, for example `"High"`.
- `default` is used for a new to-do when no priority is given.

### 3. Migration — `todos/migrations/`

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

Django makes `000N_todo_priority.py` (the number depends on the waves before). Never edit it by
hand. Because the field has a default, Django gives every existing to-do the value 2 (Medium).
Check this by opening the migration file: it has `default=2`.

If #5 or #11 merges first with its own migration, do not keep two migrations with the same number:
update this branch from `main`, delete **our own** new migration file (not yet merged), and run
`makemigrations` again. The migration check in `make check` finds a missing migration.

### 4. The form — `todos/forms.py`

Add `"priority"` to `Meta.fields` (this is needed: a field that is only declared, and not in
`Meta.fields`, is checked but **not saved**). Then declare the field, and add `clean_priority`:

```python
class TodoForm(forms.ModelForm):
    priority = forms.TypedChoiceField(
        choices=Todo.Priority.choices,
        coerce=int,
        required=False,
        empty_value=None,
        initial=Todo.Priority.MEDIUM,
        widget=forms.Select(attrs={"aria-label": "Priority"}),
    )

    # ... Meta, with "priority" in fields ...

    def clean_priority(self):
        priority = self.cleaned_data["priority"]
        if priority is None:
            # No priority was sent: keep the one the to-do has.
            # A new to-do has the default, Medium.
            return self.instance.priority
        return priority
```

- `TypedChoiceField` accepts only the listed choices, and turns the text `"3"` from the browser
  into the number `3` (`coerce=int`).
- `required=False` and `empty_value=None`: a missing or empty priority is not an error, and
  becomes `None`. Then `clean_priority` replaces `None` with the priority the to-do already has.
  On the add form, `self.instance` is a new, unsaved `Todo`, so that is Medium. On the edit page,
  `self.instance` is the to-do being edited, so its priority stays.
- `7` or `urgent` is still an error: "Select a valid choice."
- `initial` makes Medium selected in an empty add form. It is needed: a form made with no
  `instance` does not read the model default for the drop-down. On the edit page the form is made
  with `instance=todo`, and then the to-do's own priority is selected.
- `aria-label` gives the drop-down a name for screen readers on the add form, like the title
  field has. On the edit page `form.as_div` also writes a visible label "Priority".

We tried this code with Django 5.2 before writing it down: add with no priority gives 2; edit of a
Low to-do with no priority keeps 1; `priority=7` is an error.

### 5. The views — `todos/views.py`

No change expected (see "Changes to files").

### 6. The pages

**Add form** (`todo_list.html`, the list page since #10): add `{{ form.priority }}` next to the
title, and show `form.priority.errors` with the other errors. Django renders the `<select>` and
marks the right `<option>` as `selected`, also after an error.

**Each row** (`_todo_item.html`), after the title:

```html
<span class="priority priority-{{ todo.priority }}">
  <span class="visually-hidden">Priority: </span>{{ todo.get_priority_display }}
</span>
```

**CSS** (in `base.html`, where all the CSS is since wave 0):

- `.visually-hidden`: the standard rule that hides text on the screen but keeps it for screen
  readers: `position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; border: 0;
  overflow: hidden; clip-path: inset(50%); white-space: nowrap;`. Not `display: none`, because
  screen readers skip that. Other features can use this class too.
- `.priority`: a small label with a border in the same color as its text (`currentColor`),
  smaller text, and `white-space: nowrap`. Its color is `var(--text)` (Medium).
- `.priority-3 { color: var(--priority-high); font-weight: bold; }` (3 is High) and
  `.priority-1 { color: var(--muted); }` (1 is Low). Write these comments in the CSS.
- `li.done .priority { color: var(--muted); }`, so a done row is grey also for its label.
- One new CSS variable on `:root`: `--priority-high`, with a dark-mode value in the dark-mode
  block from #20. It must have a contrast of at least 4.5 to 1 against `--bg`, in light and in
  dark mode, because it colors text. Suggested: a dark orange such as `#a14a00` in light mode, a
  light orange such as `#ffb366` in dark mode. Against the `--bg` values from #20 (`#ffffff` and
  `#121212`) these give about 6.0 : 1 and 10.6 : 1. If #20 merged other `--bg` values, check
  again with a contrast checker.
- On a phone the row must not get wider than the screen. Check it on a narrow window.

### 7. Checks — already done

The migration check (`makemigrations --check --dry-run`) is already in `make check` and in
`check.yml`. Nothing to do.

### 8. The tests — `todos/tests/`

Rule: test each rule once, in the lowest layer where a person would notice it.

**Unit** — `todos/tests/unit/test_models.py` (`SimpleTestCase`, no database):

| Test | What it checks |
|---|---|
| `test_priority_numbers_go_up_with_importance` | `LOW < MEDIUM < HIGH`. #14 sort depends on this. |

**Integration** — `todos/tests/integration/test_views.py` (Django test client), in a class
`PriorityTests`. Log in with `self.client.force_login(user)`, and post new to-dos to
`reverse("todo_add", args=[the_list.pk])` (the add address since #10).

| Test | What it checks |
|---|---|
| `test_add_a_todo_with_high_priority` | Posting `priority=3` saves a High to-do. |
| `test_add_without_priority_is_medium` | Two cases (`subTest`): only a title, and a title with `priority=""`. Both save a Medium to-do. |
| `test_add_form_selects_medium` | The empty add form has `<option value="2" selected>Medium</option>` (checked with `assertInHTML`). |
| `test_invalid_priority_is_not_added` | `priority=7` saves nothing, shows an error, keeps the typed title. |
| `test_list_shows_priority_label` | A High to-do's row contains the label span with "Priority: " and "High" (`assertInHTML`). |
| `test_edit_shows_current_priority` | The edit page of a Low to-do has `<option value="1" selected>Low</option>`. |
| `test_edit_changes_priority` | Posting `priority=3` (with a title) on the edit page changes a Medium to-do to High. |
| `test_edit_without_priority_keeps_it` | Posting only a new title on the edit page of a High to-do: the title changes, the priority is still High. This test fails with `empty_value=MEDIUM`; show that. |
| `test_other_user_cannot_change_priority` | User B posts `priority=3` to the edit page of user A's Low to-do: 404, and the priority is still Low. |

The existing tests that post only a title must still pass without a change. That shows the
Medium default works for them.

**No CUJ step.** A `<select>` is a plain HTML form field. The integration tests already send what
the browser sends, so a browser test would test the same rule a second time. (The date picker in
#6 is different: the browser draws it.)

Count the tests with `make test` at the end, and write the new numbers in the pull request.

### 9. Docs

- `AGENTS.md`: in the table, `models.py` gets `priority` (Low, Medium, High; default Medium).
- `README.md`: update the example layer summary under "Run the tests" to the real numbers from the
  runner.

### 10. Before the commit

- Run `make check`.
- `make run`: add to-dos with each priority, edit one, look at the list in light and dark mode,
  and on a narrow window. Try the page with a screen reader (VoiceOver on a Mac: Cmd+F5) and
  hear "Priority: High".

## Open questions

1. **Show "Medium" on every row, or only "High" and "Low"?** This plan shows all three, for
   clarity. If most to-dos are Medium, the label may feel like noise. Hiding Medium would be a
   small change to `_todo_item.html` later.

## Review

What the adversarial review changed, and why:

- Edit with no priority kept the old `empty_value=MEDIUM`, which we tested: it reset a Low or High to-do to Medium on edit. Now `empty_value=None` plus `clean_priority` keeps the current value; new test `test_edit_without_priority_keeps_it`.
- Moved all CSS from `todo_list.html` to `base.html`, because wave 0 put all CSS there.
- The edit template does not change: #4 draws it with `form.as_div`. Removed the step that added `{{ form.priority }}` by hand.
- Add tests post to `todo_add` with the list's `pk` (the add address since #10), and the accounts note uses `todo.todo_list.owner`.
- Only one new color (`--priority-high`), not the same red as `--overdue`; Medium and Low reuse `--text` and `--muted`. Fewer dark-mode values to check.
- CSS class uses the number (`priority-3`), not the label, so a translation cannot break it. Removed open questions 2 and 3 (decided: no bold title beyond the High label; translation is out of scope).
- Added a CSS rule so the label is grey in a done row; the plan said so, but no rule did it.
- Fixed the `.visually-hidden` rule to the full standard one (margin, padding, border, `clip-path`).
- `test_add_without_priority_is_medium` now also checks `priority=""`: missing and empty go through two different paths in Django.
- Removed the CUJ step: a `<select>` needs no real browser; the integration tests cover it.
- Said that `priority` must be in `Meta.fields`, or the declared field is not saved.
- Noted #18 sharing (same wave) in "Not part of this task".
- Note for #4 and #14 (not changed here): #4's `test_edit_page_shows_every_form_field` must look for `name="priority"`, not only `<input`, because priority is a `<select>`. `docs/plans/sort.md` calls the middle level "normal"; it is "Medium".
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- Every row shows its priority, also "Medium".
