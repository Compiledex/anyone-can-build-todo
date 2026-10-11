# Plan: a description (notes) on a to-do

Status: **done** (2026-10-09, PR #13). The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (`TodoForm` in `todos/forms.py`, the partial `_todo_item.html`, CSS variables,
the shared `base.html`), 17 accounts, 20 dark mode, 10 lists, 4 edit (its page uses `TodoForm`
and draws it with `{{ form.as_div }}`).

Same wave (3), built at the same time: #9 priority, #11 tags, #18 sharing, #19 clear completed.
#9 and #11 also add a model field, a migration, a line in `TodoForm` and a line in
`_todo_item.html`. See "Merging with the rest of wave 3".

## Goal

A person can write a longer note under the title of a to-do, for example "Buy milk" with the note
"The lactose-free one. Also ask about oat milk." The note is **optional**. A to-do without one
looks and works exactly as it does today.

## Decisions

- **The field is called `description`.** On the page we call it "Notes", because that word is
  simpler. It is a `TextField` (a database column for long text) with `blank=True, default=""`.
  "No note" is an empty string, not `NULL`, the Django way for text fields. Then there is only one
  way to say "empty".
- **The maximum length is 2000 characters.** That is about one page of text: much more than a
  note needs, and small enough that one to-do cannot fill the page. We set `max_length=2000` on
  the `TextField`. For a `TextField`, Django does not check this in the database, but the form
  checks it, and the `<textarea>` gets `maxlength="2000"` by itself. (Checked with Django 5.2: the
  form field gets `max_length=2000` and the widget gets `maxlength="2000"`.)
- **A line break counts as one character, on the server too.** A browser sends a line break as
  two characters (`\r\n`), but its own `maxlength` counts it as one. Django counts two (checked:
  700 lines of `"a"` = 1400 characters in the browser, but Django says "it has 2098"). Then a note
  the browser allowed would get a "too long" error with a number the person cannot see. So the
  form turns every `\r\n` into `\n` **before** it checks the length. This is a tiny field class,
  `NoteField`, in `todos/forms.py`:

  ```python
  class NoteField(forms.CharField):
      """A text field that counts a line break as one character, as the browser does."""

      def to_python(self, value):
          return super().to_python(value).replace("\r\n", "\n")
  ```

  `TodoForm` uses it through `Meta.field_classes = {"description": NoteField}`. That way the field
  still gets `max_length`, `required=False` and the `Textarea` from the model by itself. It also
  means notes are saved with `\n` only, one way to write a line break.
- **The note is set only on the edit page (#4), not when adding.** The add form on the list page is
  hand-written and stays one short line, so adding a to-do stays quick. It does not send
  `description`. That is fine: the field is optional, and Django keeps the default `""` for a
  field that is missing from the request. To add a note, a person adds the to-do, then clicks
  "Edit".
- **The edit page needs no template change.** #4 draws the form with `{{ form.as_div }}`, so a new
  field in `TodoForm` shows up there with its label and its errors by itself. We only set the
  label: `Meta.labels = {"description": "Notes"}`, and a smaller box:
  `Meta.widgets = {"description": forms.Textarea(attrs={"rows": 4})}`. No `aria-label`: the
  visible `<label>` already names the box for screen readers.
- **Spaces at the start and end are removed.** The Django form field does this by default
  (`strip=True`). A note of only spaces and line breaks is saved as empty.
- **In the list, the note is hidden behind a `<details>` element.** `<details>` and `<summary>`
  are plain HTML: the browser shows a small "Notes" line, and the note opens when a person clicks
  it. It needs no JavaScript and works with the keyboard and screen readers. It is closed by
  default, so long notes do not make the list long. When a to-do has no note, there is no
  `<details>` at all.
- **The note sits next to the title, but not inside `.title`.** Two reasons. (1) A done to-do's
  `.title` is crossed out (`text-decoration: line-through`), and in CSS a line-through also goes
  onto everything inside, so the note would be crossed out too and hard to read. (2) `.title` is
  a `<span>`, and a `<span>` may not hold block elements like `<details>` or `<p>`. So the title
  and the note go together in one `<div class="main">`, which takes the free space in the row.
- **Line breaks show.** We use the Django filter `linebreaksbr`. It turns each line break into
  `<br>`.
- **Long words wrap.** A long link or word with no spaces would push the row wider than a phone
  screen. `overflow-wrap: anywhere` on the note, and `min-width: 0` on `.main`, stop that.
- **The note is always escaped.** "Escaped" means characters like `<` and `>` are shown as text,
  not read by the browser as HTML. Django escapes every `{{ }}` by default, and `linebreaksbr`
  escapes the text **first**, then adds the `<br>` tags (checked: `"a\r\nb<b>"` becomes
  `a<br>b&lt;b&gt;`). So `<script>` in a note shows as the text `<script>`. We never use `|safe` or
  `{% autoescape off %}` on the note.
- **A note that is too long shows an error and keeps what was typed**, like every other form
  error on the edit page (#4).
- **Who sees a note:** exactly the people who see the to-do. Today (after #10) that is the owner.
  After #18 sharing, members of a shared list see it too. That is wanted: the note is part of the
  to-do. This plan adds no new view and no new query, so it adds no new way to see a to-do.

## Not part of this task

- A note field on the add form.
- Formatting (bold, links, Markdown). The note is plain text. Making links clickable could be a
  later task, with `urlize`, but it needs its own review for safety.
- Searching in notes. That belongs to search (#12, wave 4), which can then decide to include it.
- Showing a short preview of the note in the list. `<details>` is simpler and shows the whole
  note when open.
- Remembering which notes are open after the page reloads.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | New field `description = models.TextField(max_length=2000, blank=True, default="")`. |
| `todos/migrations/000X_todo_description.py` | Made by `makemigrations`. Existing to-dos get `""`. Never edit it by hand. |
| `todos/forms.py` | New class `NoteField` (above). In `TodoForm.Meta`: add `"description"` to `fields`, and add `field_classes`, `labels` and `widgets` for it. |
| `todos/templates/todos/_todo_item.html` | Wrap the title in `<div class="main">`, and add the `<details>` block after the title, inside `.main`, only `{% if todo.description %}`. |
| `todos/templates/base.html` | Small CSS for `.main` and `.notes` (this is where the page CSS lives since wave 0). |
| `todos/templates/todos/todo_edit.html` | **No change.** `form.as_div` shows the new field. |
| `todos/views.py` | **No change.** The edit view (#4) already saves the form and already finds only to-dos the person may see. |
| `todos/admin.py` | No change. The admin shows the new field by itself. |

The row in `_todo_item.html` (only the title part; the buttons stay as they are):

```django
<div class="main">
  <span class="title">{{ todo.title }}</span>
  {% if todo.description %}
    <details class="notes">
      <summary>Notes</summary>
      <p>{{ todo.description|linebreaksbr }}</p>
    </details>
  {% endif %}
</div>
```

The CSS in `base.html`:

```css
li .main { flex: 1; min-width: 0; }
.notes { font-size: 0.9rem; color: var(--muted); }
.notes p { margin: 0.25rem 0 0; overflow-wrap: anywhere; }
```

Move `flex: 1` from `li .title` to `li .main`. `--muted` stands for the muted text color that
wave 0 already made (the one for done to-dos); use its real name. Do **not** add a new color. If a
new one is really needed, it needs a dark-mode value with 4.5:1 contrast.

## Tests

Each test goes in the lowest layer where a person would notice the rule (see
`docs/plans/test-pyramid.md`). Every test logs in as a user, as the tests from #17 do.

**Integration** — `todos/tests/integration/test_views.py`, in `EditTests` (from #4) and
`ListTests`. The edit form needs every required field (title, and anything #6 or #10 made
required). Build the POST data with one small helper in the test class, for example
`edit_data(todo, **changes)`, that starts from the to-do's current values. Then a field added
later only needs a change in one place.

| Test | What it checks |
|---|---|
| `test_edit_page_shows_notes_field` | `GET` the edit page of a to-do with a note: the page has the label "Notes", a `<textarea name="description"`, `maxlength="2000"`, and the current note inside the box. |
| `test_edit_saves_description` | Posting the edit form with a note saves it. |
| `test_edit_saves_line_breaks_as_one_character` | Post a note `"Line one\r\nLine two"`: it is saved as `"Line one\nLine two"`. |
| `test_edit_can_clear_description` | Posting an empty note makes `description` `""`. |
| `test_description_only_spaces_is_empty` | A note of `"  \r\n  "` is saved as `""`. |
| `test_description_of_2000_characters_is_saved` | Exactly 2000 characters: saved. |
| `test_long_description_is_not_saved` | 2001 characters, plus a new title: status 200, an error shows, the typed text is still in the box, and neither the title nor the note changed in the database. |
| `test_many_lines_near_the_limit_are_saved` | A note of many short lines that the browser counts as under 2000 but that is over 2000 as sent: it is saved, with `\n` line breaks. See the note below the table. |
| `test_add_still_works_without_description` | Adding a to-do with the add form (title only) still works, and its `description` is `""`. |
| `test_list_shows_description_with_line_breaks` | A to-do with `"Line one\nLine two"`: the page has `<details class="notes">` and `Line one<br>Line two`. |
| `test_list_escapes_description` | A note `<script>alert(1)</script>`: the page has `&lt;script&gt;alert(1)&lt;/script&gt;`, and does not have `<script>alert(1)`. Both checks are needed: the first one proves the note is on the page at all, so the second one cannot pass just because the note is missing. |
| `test_details_only_for_todos_with_a_note` | Two to-dos, one with a note and one without: the page has `<details` exactly once (`assertContains(..., count=1)`). |
| `test_other_user_cannot_see_description` | User A's note is not on the list page of user B (B is not a member of A's list). The test also checks that A's own page **does** show it, so the test cannot pass by accident. |
| `test_other_user_cannot_edit_description` | User B posts a note to A's edit address: 404, and A's note does not change. |

Note for `test_many_lines_near_the_limit_are_saved`: make a note of 1000 lines `"a\r\n"` minus the
last line break. As the browser counts it, that is 1999 characters (1000 `a` + 999 line breaks).
As sent it is 2998 characters. It must be saved, with `\n` line breaks. Before `NoteField`
exists, this test fails with "too long". This is the test that shows the line-break rule works.
In Python: `"\r\n".join(["a"] * 1000)`.

**Unit** — `todos/tests/unit/test_forms.py`:

| Test | What it checks |
|---|---|
| `test_note_field_turns_crlf_into_lf` | `NoteField().clean("a\r\nb")` is `"a\nb"`. No database and no request needed. |

**CUJ**: no new journey. Add three steps to #4's `test_fix_a_typo` in
`todos/tests/cuj/test_journeys.py`: write a two-line note on the edit page, save, click "Notes" in
the list, and see both lines. This is the only test that checks the `<details>` really opens in a
real browser. Notes are not important enough for a journey of their own.

All tests that exist before this task must still pass. Check #4's
`test_edit_page_shows_every_form_field` in particular: the note is a `<textarea>`, not an
`<input>`. If that test looks for `<input ... name="...">`, change it to look for `name="..."`
only, so it works for every kind of field.

## Steps

The order follows `AGENTS.md`: test first, see it fail, then the code.

1. **Tests first.** Write the tests in the tables. Run `make test` and show them failing. Start
   with `test_list_escapes_description`, `test_edit_saves_description` and
   `test_many_lines_near_the_limit_are_saved`. Say in the pull request that
   `test_other_user_cannot_edit_description` would pass before the change too (#4's lookup
   already gives 404), so it is a guard, not "shown failing".
2. **Model.** Add the field to `todos/models.py`.
3. **Migration.** Run `uv run python manage.py makemigrations`, then
   `uv run python manage.py migrate`. Open the new file and check it adds `description` with
   `default=""`. Existing to-dos get an empty note.
4. **Form.** Add `NoteField` and the `description` lines to `TodoForm` in `todos/forms.py`.
5. **List.** Change `_todo_item.html` (the `.main` wrapper and the `<details>` block), and add the
   CSS to `base.html`.
6. Run `make test`. All tests pass. Show this.
7. **Docs.** `AGENTS.md`: in the file table, `models.py` gets `description`, and `forms.py`
   gets `NoteField`. `README.md`: update the test numbers if it lists them.
8. **Look at it.** `make run`, add a note with a few lines and with `<b>hi</b>` in it, and look
   at the list in light mode, dark mode, and on a narrow window (phone width). Also try a done
   to-do with a note (the note must not be crossed out) and a note that is one very long word.
9. **Check.** Run `make check` before the commit.

## Merging with the rest of wave 3

- **Migrations.** #9 priority and #11 tags also add a migration. Two new migrations with the same
  parent make Django stop with "Conflicting migrations detected". Whoever merges second: rebase
  on `main`, delete **your own** new migration file (it is not on `main` yet), and run
  `makemigrations` again. Never edit a migration by hand.
- **`todos/forms.py`.** #9 and #11 also add to `TodoForm.Meta`. Keep every field from both sides.
- **`_todo_item.html`.** #9 and #11 add their label or tags after the title. Put them inside or
  next to `.main` as their plans say; keep the `<details>` as the last thing inside `.main`, so
  the note opens under everything else.
- **#18 sharing.** If #18 merges first, make sure user B in `test_other_user_cannot_see_description`
  is not a member of A's list.
- Whoever merges last runs `make check` again after the merge.

## Open questions

- **Should the note open by default** when it is short (for example one line)? This plan says no:
  always closed, one simple rule.

## Review

What the review changed, and why:

- Edit page: removed the template change. #4's `form.as_div` already shows the new field and its errors.
- Removed the "which form does edit use?" question: #4 uses `TodoForm` (decided in the build order).
- `aria-label="Notes"` replaced by `Meta.labels`: the visible label already names the box; the label text was otherwise "Description".
- Line breaks: verified that Django counts `\r\n` as 2 and the browser as 1, so real notes could be refused. Decided to fix it with a small `NoteField` instead of accepting it; added a unit test and an integration test that fails before the fix.
- Moved the note out of `.title`: a done to-do's line-through would cross out the note, and `<details>` inside a `<span>` is not valid HTML.
- Added `overflow-wrap: anywhere` and `min-width: 0`, so one long word cannot make the page wider than a phone.
- CSS goes in `base.html`, where wave 0 put the page CSS, not in `todo_list.html`; uses the existing muted color, no new color.
- Added tests: edit page shows the field, label, `maxlength` and current value; exactly 2000 characters is saved; the too-long test also checks the title did not change.
- Made weak tests stronger: the escape test and the "other user" test each also check a positive, so they cannot pass when the note is simply missing; the "no details" test now counts `<details` with two to-dos.
- Tests build POST data with one helper, because #6 and #10 may add required fields to `TodoForm`.
- Warned that #4's "every form field" test must not look only for `<input>`: the note is a `<textarea>`.
- Added a merge section: #9 and #11 add migrations in the same wave, so the second must regenerate its migration.
- Added "Builds on" #10 and #20, and a line on who sees a note after #18 sharing.

## Decided by the person (2026-10-09)

The plan is **approved**.

- A note is always closed by default, also a short one.
