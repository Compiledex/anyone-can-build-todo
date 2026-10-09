# Plan: edit a to-do

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (`TodoForm` in `todos/forms.py`, the row partial
`todos/templates/todos/_todo_item.html`, CSS variables on `:root`, the shared
`todos/templates/base.html`), wave 1 #17 accounts (each to-do has an owner; Django's
`LoginRequiredMiddleware` sends every visitor who is not logged in to the login page; the test
helpers in `accounts/tests/helpers.py`) and wave 1 #20 dark mode.

Same wave (2), built at the same time: #6 due date and #10 lists. Both also touch `TodoForm`, the
views and the templates. #10 changes a lot: it **removes `Todo.owner`** (the owner becomes
`todo.todo_list.owner`), and the URL name `todo_list` (`/`) now only redirects to the person's
oldest list, not to the list a to-do is in. `docs/plans/lists.md` asks to be merged first. So
this plan has two versions of three lines: one for "#10 is not merged yet" and one
for "#10 is merged" (see "Merging with #6 and #10"). This plan does **not** change
`todos/forms.py`, and adds only one line to `_todo_item.html`.

## Goal

A person can change the text of a to-do after it is saved. Every field in `TodoForm` shows up on
the edit page by itself. So when #6 adds a due date, or later #5 a description and #9 a priority,
the edit page shows that field too, with no extra work.

## Decisions

- **A separate edit page, not inline editing.** Each to-do in the list gets an "Edit" link. It
  opens the page `/<pk>/edit/` (`pk` is the to-do's number in the database). The other to-do
  addresses (`/<pk>/toggle/`, `/<pk>/delete/`) look the same, and #10 keeps them.
  - `GET` shows a form with the current values filled in.
  - `POST` saves the changes.
  - Why not inline editing (typing straight into the list)? It needs JavaScript, or a hidden form
    in every row. And a list row has no room for later fields like a description. A separate page
    is the standard Django pattern, works with no JavaScript, and shows every field of the form.
- **The page draws the form with `{{ form.as_div }}`.** Django writes a label, an input and the
  errors for every field in the form. This is what makes new fields appear with no work. The add
  form on the list page stays as wave 0 wrote it.
- **The page extends `base.html`** from wave 0. So it gets the same CSS, dark mode and the
  "Logged in as … / Log out" header with no copying.
- **Invalid input: show the edit page again.** If the form is not valid (for example an empty
  title, or a title longer than 200 characters), nothing is saved. The edit page is shown again
  (status 200) with the error message, and the fields still hold what the person typed.
- **After saving, go back to the list the to-do is in.** Before #10: `redirect("todo_list")`.
  After #10: `redirect(todo.todo_list)` (Django calls the list's `get_absolute_url`), the same as
  toggle and delete do after #10. A refresh of the list then does not send the form again.
- **No `?next=` address.** The view never takes "where to go after saving" from the request. That
  would let another site make a link that sends a person somewhere bad after saving (an "open
  redirect"). The place to go back to always comes from the to-do itself.
- **A "Cancel" link** on the edit page goes back to the same list and saves nothing. It is a link
  (`<a>`), not a button, because it only reads.
- **Only the owner can edit.** The view finds the to-do with exactly the same line that
  `todo_toggle` and `todo_delete` use at merge time (see "The view"). For any other person, both
  `GET` and `POST` give **404 Not Found**, not 403 Forbidden. 404 does not tell them that the to-do
  exists. Using the same line matters: #18 sharing will search for these lines and change them all.
- **Login: no decorator.** #17 turns on `LoginRequiredMiddleware`, so every view needs a login by
  default. Do not add `@login_required` (the other views do not have it either).
- **Editing changes only the fields in `TodoForm`.** The form does not contain `done`, `owner` or
  (after #10) `todo_list`, so editing cannot change them, even if someone sends them in the request.
  The view must use `TodoForm(request.POST, instance=todo)`; `instance` means "change this to-do",
  not "make a new one".
- **A done to-do can be edited too.** There is no reason to forbid it.
- **No new model field, so no migration.**

## Not part of this task

- Inline editing in the list, or saving without leaving the list page.
- **Moving a to-do to another list.** `docs/plans/lists.md` keeps `todo_list` out of `TodoForm`,
  and lists this as later work. Warning for whoever adds it later: the list choice must offer
  only the person's own lists (and, after #18, lists shared with them). If it offers every list,
  a person could move their to-do into a stranger's list. `docs/plans/sharing.md` says the task
  that adds a list choice must limit it to `visible_to(user)` and test it.
- Editing a to-do that is shared with you (#18 sharing comes in wave 3). #18 changes the lookup line
  in `todo_edit` together with the others.
- Edit history, or "undo" for an edit.
- Two edits at the same time (two tabs, or after #18 two people). The last save wins. That is
  normal for a small app, and we accept it.
- A "Saved" message after saving. Seeing the new text in the list is enough.

## Changes to files

| File | Change |
|---|---|
| `todos/urls.py` | Add one line: `path("<int:pk>/edit/", views.todo_edit, name="todo_edit")`. |
| `todos/views.py` | Add one new function, `todo_edit`, at the end of the file. No other view changes. |
| `todos/templates/todos/todo_edit.html` | New file: the edit page. Extends `base.html`. |
| `todos/templates/todos/_todo_item.html` | Add one line: the "Edit" link. |
| `todos/templates/base.html` | Add a few CSS rules for the edit form (see "The page"). No new colors. |
| `todos/forms.py` | **No change.** |
| `todos/tests/integration/test_views.py` | Add a new class `EditTests` at the end of the file. |
| `todos/tests/cuj/test_journeys.py` | Add one new test class at the end of the file. |
| `AGENTS.md`, `README.md` | Add `todo_edit.html` to the file tables, and the edit address to the list of addresses in `todos/urls.py` (`AGENTS.md` says "the four addresses" today; use whatever the text says after #10). |

### The view — `todos/views.py`

```python
def todo_edit(request, pk):
    # Before #10:
    todo = get_object_or_404(Todo, pk=pk, owner=request.user)
    # After #10, the same line as todo_toggle and todo_delete:
    # todo = get_object_or_404(Todo, pk=pk, todo_list__owner=request.user)
    if request.method == "POST":
        form = TodoForm(request.POST, instance=todo)
        if form.is_valid():
            form.save()
            return redirect("todo_list")  # after #10: redirect(todo.todo_list)
    else:
        form = TodoForm(instance=todo)
    return render(request, "todos/todo_edit.html", {"form": form, "todo": todo})
```

- `get_object_or_404` runs **before** anything else, so another person gets 404 for both `GET`
  and `POST`.
- `GET` only reads. `POST` is the only way to change data (the rule in `AGENTS.md`). Other methods
  (for example `PUT`) are treated like `GET` and change nothing. That is fine.
- Only one of the two lookup lines is in the code. Copy the line from `todo_toggle` exactly as it
  is at merge time; do not invent a third way.
- If `TodoForm` needs extra arguments by the time this is built (for example the user), pass the
  same arguments here as the add view does.

### The page — `todos/templates/todos/todo_edit.html`

- `{% extends "base.html" %}`, and put the content in `{% block content %}`. If `base.html` has a
  block for the page title, set it to "Edit to-do".
- Heading: "Edit to-do". Do not put the to-do's title in the heading: after an invalid `POST`, Django
  has already copied some of the typed values onto `todo`, so it may not show what is saved.
- The form:

  ```html
  <form class="edit" method="post" action="{% url 'todo_edit' todo.pk %}">
    {% csrf_token %}
    {{ form.as_div }}
    <button type="submit">Save</button>
    <a href="{% url 'todo_list' %}">Cancel</a>
  </form>
  ```

  After #10, the Cancel link is `<a href="{{ todo.todo_list.get_absolute_url }}">Cancel</a>`.
- `{% csrf_token %}` is Django's protection against other websites sending this form (CSRF means
  "cross-site request forgery").
- `form.as_div` also shows `form.non_field_errors` and each field's errors. Django escapes the
  saved title when it puts it in the input, so a title like `<script>` is shown as text, not run.
- Style: a few rules in the `<style>` of `base.html`, under a comment `/* edit page */`, so that
  each label is on its own line and the inputs are full width (`form.edit input { width: 100%; }`
  with `box-sizing: border-box`, so it does not stick out on a phone). Use only the CSS variables
  from wave 0. No new colors, so dark mode (#20) keeps working and needs no new contrast check.

### The link — `todos/templates/todos/_todo_item.html`

Add one line, next to the Done and Delete buttons:

```html
<a href="{% url 'todo_edit' todo.pk %}" aria-label="Edit {{ todo.title }}">Edit</a>
```

It is a link because opening the edit page only reads. The `aria-label` tells a screen reader
which to-do the link edits; it starts with the visible word "Edit", so voice control ("click
Edit") still works. Django escapes the title inside the attribute, so quotes in a title cannot
break it. Put this line just before the Done form, so it does not collide with lines #6 adds to
the same file.

## Tests

The rule: test each rule once, in the lowest layer where a person would notice it. The title rules
(empty, too long) are already tested for adding, and edit uses the same form. So edit needs only
**one** invalid-input test, to check the invalid path of the view.

There are no new **unit** tests: there is no new logic outside the view.

**Integration** — `todos/tests/integration/test_views.py`, new class
`EditTests(LoggedInTestCase)` (from `accounts/tests/helpers.py`: `self.client` is alice,
`self.other_user` is bob). Make alice's to-do the same way the other tests in the file do at merge
time (after #10: `todo_list=self.todo_list`, alice's list, which #10 adds to `LoggedInTestCase`;
bob's list is `self.other_list`).

**Post the whole form, not only the title.** Later features add fields to `TodoForm`. #9 adds a
priority that is required, so a test that posts only `{"title": ...}` would suddenly fail when #9
merges, even though edit still works. Add one small helper at the top of the class:

```python
def edit_data(self, todo, **changes):
    """What the edit form sends, with the current values, plus the changes."""
    form = TodoForm(instance=todo)
    data = {name: form[name].value() for name in form.fields}
    data = {name: "" if value is None else value for name, value in data.items()}
    data.update(changes)
    return data
```

| Test | What it checks |
|---|---|
| `test_edit_page_shows_current_title` | `GET` as alice: status 200, the title input holds the current title. |
| `test_edit_page_shows_every_form_field` | `GET` as alice: for each name in `response.context["form"].fields`, the page contains `name="<that name>"` (an `<input>`, `<select>` or `<textarea>`). Use the form from the response, not `TodoForm.base_fields`, so fields a form adds in `__init__` count too. This test keeps checking when #6, #5 or #9 add fields. |
| `test_edit_saves_new_title` | `POST` `edit_data(todo, title="Buy milk")`: redirects to the list (`assertRedirects`), and the title in the database is the new one. |
| `test_invalid_edit_is_not_saved` | `POST` `edit_data(todo, title="   ")`: status 200, the page shows the form error, the title in the database is unchanged. |
| `test_edit_does_not_change_done_or_owner` | A done to-do. `POST` `edit_data(todo, title="New", done="", owner=self.other_user.pk)` (after #10 also `todo_list=self.other_list.pk`): the title changes, `done` is still `True`, it still belongs to alice. |
| `test_other_user_gets_404` | `assertOtherUserGets404(url, method="get")` and `assertOtherUserGets404(url, data=edit_data(todo, title="Hacked"))`; then the title is unchanged. |
| `test_logged_out_user_is_sent_to_login` | A new `Client()` with no login: `GET` and `POST` both redirect to the login page; the title is unchanged. |
| `test_list_has_edit_link` | The list page has a link to `reverse("todo_edit", args=[todo.pk])`. |

**CUJ** — `todos/tests/cuj/test_journeys.py`, one short new test, `test_fix_a_typo`. Fixing a
typo is a main journey. It is also the only test that uses the page's own form: the integration
tests post straight to the address, so they would still pass if the form's `action`, the Save
button or the Cancel link were broken.

1. Make alice, `self.log_in_as(alice)` (the helper from #17), open the site, and add "Buy mlik".
2. Click the "Edit" link in its row. Fill the "Title" field with "Buy milk". Click "Save".
3. The list shows "Buy milk", and not "Buy mlik".

## Steps

The order follows `AGENTS.md`: write the test, see it fail, then write the code.

1. **Check what is merged.** Is #10 merged? Then use the "after #10" lines everywhere in this plan.
   Look at how `todo_toggle` finds a to-do, and how the integration tests make one.
2. **Tests first.** Add `EditTests` and the CUJ test. Run `make test`. They fail, because the URL
   `todo_edit` does not exist yet. Show this.
3. **URL** — add the line to `todos/urls.py`.
4. **View** — add `todo_edit` to `todos/views.py`.
5. **Page** — make `todos/templates/todos/todo_edit.html`, and the few CSS rules in `base.html`.
6. **Link** — add the Edit link to `_todo_item.html`.
7. Run `make test`. All tests pass. Show this.
8. **Docs** — `AGENTS.md` and `README.md` (see the file table).
9. **Look at it.** `make run`, log in, edit a to-do, try Cancel. (An empty title is stopped by the
   browser's `required` check; the server side is covered by the integration test.) Look at the edit
   page in a narrow window (phone width) and in dark mode.
10. Run `make check` before the commit.

## Merging with #6 due date and #10 lists

- **If #10 merges first** (what `docs/plans/lists.md` asks for): change the three lines marked
  "after #10" (the lookup, the redirect, the Cancel link), and make the test to-dos inside a list.
  Without this, the code fails: `Todo.owner` no longer exists. (The URL name `todo_list` still
  exists, but `/` now only redirects to the oldest list, so Save and Cancel would not go back to
  the to-do's own list.)
- **If this plan merges before #10**: #10 must change the same three lines in `todo_edit` and its
  template when it rebases. `lists.md` ("Working next to other wave 2 features") already lists
  these three changes: the lookup, the redirect and the Cancel link.
- `todos/forms.py`: this plan does not touch it. No conflict.
- `todos/views.py`, `todos/urls.py`: this plan only adds at the end. A conflict there is only "both
  added at the end": keep both.
- `_todo_item.html`: one new line. If #6 merges first, its due date also shows on the edit page by
  itself (`form.as_div`), and `test_edit_page_shows_every_form_field` checks that. Whichever of #4
  and #6 merges second adds `test_edit_clears_due_date` (see `docs/plans/due-date.md`); it should
  use `edit_data`.
- Whichever of the three merges last runs the full `make check` again after the merge.

## Open questions

None that block the work. Decided in the review: go back to the to-do's own list after saving
(the same as toggle and delete after #10); no list choice on the edit page; use the shared
`base.html` from wave 0.

## Review

What the review changed, and why:

- `@login_required` removed: #17 uses `LoginRequiredMiddleware`, and no other view has a decorator.
- The lookup, the redirect and the Cancel link now have an "after #10" version: #10 removes
  `Todo.owner` (the old lookup would crash) and makes `/` only a redirect to the oldest list.
- "Use the same lookup line as toggle and delete": so #18 sharing can find and change all of them.
- Tests post the whole form (`edit_data`): otherwise they break when #9 adds a required field.
- Field test uses `response.context["form"].fields`, not `base_fields`: fields added in `__init__`
  were missed.
- Tests use the #17 helpers (`LoggedInTestCase`, `assertOtherUserGets404`, `log_in_as`); the
  404 test covers `GET` and `POST`; the logged-out test covers `GET` too.
- The "done/owner" test also sends `todo_list` after #10, so a to-do cannot be moved by a forged
  request.
- The page extends `base.html` (now made in wave 0); the old open question about copying the
  `<head>` is gone. Where the edit-page CSS goes is now stated (`base.html`, no new colors).
- Added "No `?next=`" to rule out an open redirect, and notes on escaping (XSS) and CSRF.
- The CUJ test now has a real reason (it is the only test of the page's own form) and uses
  `log_in_as`.
- "Two people editing at the same time cannot happen" was wrong (two tabs, and #18): now "last
  save wins".
- Moving a to-do to another list: stays out, with a warning that the choice must be limited to the
  person's own lists.
- Open questions 1–3 decided (see above).
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- No open questions.
