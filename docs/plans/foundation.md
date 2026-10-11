# Plan: the foundation refactor (wave 0)

Status: **done** (2026-10-09, PR #5). The decisions are in "Decided by the person" at the end.

**Builds on:** the test pyramid (wave 0, merged): tests go in `todos/tests/unit/`,
`todos/tests/integration/` or `todos/tests/cuj/`.

**Every later plan builds on this one.** Accounts (#17), dark mode (#20), edit (#4), due date (#6),
lists (#10), description (#5), priority (#9), tags (#11), clear completed (#19), sharing (#18),
recurring (#8), subtasks (#16), search (#12), filter (#13), sort (#14) and drag and drop (#15) all
name things this plan makes. "Names later plans expect" below lists each one.

## Goal

Make four small building blocks, so later features can add to them instead of copying code:

1. A Django form, `TodoForm`, for the add view.
2. One shared page frame, `base.html`, with the `<head>`, all the CSS, and the messages.
3. One small template for one row of the list, `_todo_item.html`.
4. The page colors as CSS variables (named values that CSS can reuse).

A **refactor** means: the code changes, but what the app does stays the same. A person sees the
same page, with the same colors, and the same buttons.

There is **one small, wanted change**: a bad title now shows an error. Today, a title of only
spaces is silently ignored, and a title longer than 200 characters is saved anyway (SQLite does
not check the length). After this change, both show the page again with a short error message.
The browser already stops most bad titles (`required`, `maxlength`), so most people never see it.

## Decisions

- **`TodoForm` is a `ModelForm` with `fields = ["title"]`.** A `ModelForm` is a Django form made
  from a model. It takes the rules from the model by itself: the title is required and at most
  200 characters. It also removes spaces at the start and end, as the view does today (`strip()`).
  `done`, `created_at` and (later) `owner` or `todo_list` are **not** in the form, so a person can
  never set them by sending extra values. Nothing else goes in the form now: no labels, no widgets.
  Later plans add their own fields.
- **An invalid add shows the list page again.** If the form is not valid, nothing is saved, and the
  view answers with the list page (`render`, status 200), not a redirect. The page shows the error
  above the add form, and the title field still holds what the person typed. The due-date plan
  (#6, "Check in the code before starting") and the edit plan (#4) expect exactly this.
- **A valid add still redirects to the list** (`redirect("todo_list")`), as today. Then a refresh
  of the page does not send the form again.
- **One small helper builds the list page**: `render_list_page(request, form)` in
  `todos/views.py`. Both `todo_list` (with an empty form) and `todo_add` (with the bad form) call
  it. So the query for the to-dos is written once. Its name has no `_` at the start, because later
  plans call it by this name: lists (#10) adds one argument, `render_list_page(request, the_list,
  form)`. The page gets two values: `todos` and `form`. When accounts (#17) adds
  `filter(owner=request.user)`, it changes the query **inside `render_list_page`**, not in
  `todo_list`. Then the error page also shows only the person's own to-dos.
- **The add form stays hand-written** in `todo_list.html`. We do not let Django draw it
  (`{{ form.title }}`), because the input has its own `aria-label`, `placeholder` and `autofocus`,
  and the CUJ test finds it by its label "New to-do". Description (#5) and tags (#11) say the add
  form "is hand-written and only sends `title`". The input now gets its value back from the form:
  `value="{{ form.title.value|default_if_none:'' }}"`.
- **Errors are shown above the add form**, in one `<div class="form-errors">`, with
  `{{ form.non_field_errors }}` and `{{ form.title.errors }}`. Later fields add their errors there
  too (#6 says "next to the title errors that wave 0 already shows"). Django draws each error list
  as `<ul class="errorlist" id="id_title_error">`. When there is an error, the input gets
  `aria-invalid="true"` and `aria-describedby="id_title_error"`, so a screen reader reads the
  error with the field.
- **No new color for errors.** The error text uses the normal text color. So dark mode (#20) has
  nothing extra to check. (A red for errors would need a dark value with 4.5 : 1 contrast.)
- **`base.html` lives in `todos/templates/base.html`.** Django finds it as `"base.html"`, because
  `APP_DIRS` is `True` in `config/settings.py`. No settings change. Accounts (#17) puts its login
  page in another app and still writes `{% extends "base.html" %}`; that works the same way.
- **`base.html` has two blocks**: `{% block title %}` (the text in the browser tab, default
  "To-do list") and `{% block content %}` (the page). The edit plan (#4) sets the title block to
  "Edit to-do". The `<h1>` is in `todo_list.html`, not in `base.html`, because lists (#10) changes
  the heading to the list's name.
- **All the CSS is in `base.html`.** It moves there from `todo_list.html`, unchanged except for the
  colors (next point) and the list selectors (the point after). Later plans add their CSS there.
- **The colors are CSS variables on `:root`**, with the names dark mode (#20) uses:

  | Variable | Value (as today) | Used for |
  |---|---|---|
  | `--bg` | `#ffffff` | page background (`body`) |
  | `--text` | `#000000` | normal text (`body`) |
  | `--muted` | `#666666` | the title of a done to-do |
  | `--border` | `#dddddd` | the line between to-dos |

  Today the page has no background or text color: the browser uses white and black. Setting
  `body { background: var(--bg); color: var(--text); }` with these values looks the same. Dark
  mode then only adds one `@media (prefers-color-scheme: dark)` block with new values. Only the
  light values are set here. `#666666` on white is 5.7 : 1, above the 4.5 : 1 rule.
- **The list CSS gets a class.** Today the CSS styles **every** `ul` and `li` on the page. Now the
  page also has other lists (Django's error list, and later menus from #10 and #13). So the to-do
  list gets `class="todos"`, and the rules become `ul.todos` and `ul.todos > li`. The rules
  `li .title` and `li.done .title` stay as they are. Later plans write rules like `li .main`,
  `li.done .priority` and `.overdue time`; they still work.
- **The messages block is in `base.html`, now.** Django's `messages` (short notes shown once, on
  the next page) are already switched on in `config/settings.py`. Clear completed (#19), sharing
  (#18), recurring (#8) and subtasks (#16) all say "add the block to `base.html` if it is not
  there". It is simplest to add it once here, so none of them has to. Each message is a `<p>`, not
  an `<li>`, inside `<div class="messages" role="status">`. Not a list on purpose: the CUJ test
  counts the `listitem`s on the page, and a message must not change that count. `role="status"`
  lets a screen reader know this is a status note. Messages use only `--border`, no new color.
  (Django's error list *is* a `<ul>`, so a page with a form error has one more `listitem`. No test
  counts rows on an error page; a later CUJ test that does must count inside `ul.todos`.)
- **`_todo_item.html` is one whole `<li>`**, from `<li>` to `</li>`, with the title, the Done/Undo
  form and the Delete form, exactly as today. `todo_list.html` includes it inside the loop with
  `{% include "todos/_todo_item.html" %}`. We do **not** use `only`: the row must see the whole
  page context, because filter (#13) and drag and drop (#15) use page values (`next`,
  `can_reorder`) inside the row. The other side of this: the row also sees `form`, the **add**
  form. So a later plan must not use the name `form` for something else inside the row (a form
  in the row, like #16's "Add step", is written by hand). The "Nothing to do yet" row stays in
  `todo_list.html`, in the `{% empty %}` part of the loop.

## Not part of this task

- **Dark mode** itself (#20, wave 1). This plan only makes the variables.
- **Accounts** (#17, wave 1): the header with "Logged in as … / Log out" in `base.html`, the owner.
- **The edit page** (#4, wave 2). It will use `TodoForm`; this plan does not add it.
- Any new field in `TodoForm` (due date, priority, …). Each later plan adds its own.
- Drawing the add form with Django (`{{ form.as_div }}`). The add form stays hand-written.
- A red color for error messages.
- A static CSS file (`static/…/style.css`). The CSS stays inside `<style>` in `base.html`, as it is
  today inside `todo_list.html`. Every later plan expects it there.

## Changes to files

| File | Change |
|---|---|
| `todos/forms.py` | New file. `TodoForm`. |
| `todos/views.py` | `todo_list` and `todo_add` use `TodoForm` and the new helper `render_list_page`. Toggle and delete do not change. |
| `todos/templates/base.html` | New file. The `<head>`, all the CSS with the color variables, the messages block, `{% block title %}` and `{% block content %}`. |
| `todos/templates/todos/todo_list.html` | Now only `{% extends "base.html" %}` and the content: the `<h1>`, the errors, the add form, and the list with the include. |
| `todos/templates/todos/_todo_item.html` | New file. One row (`<li>`), moved out of `todo_list.html`. |
| `todos/tests/integration/test_views.py` | Two new tests in `AddTests`. |
| `AGENTS.md` | File table: add `forms.py`, `base.html`, `_todo_item.html`; `todo_list.html` is now "the list page, which extends `base.html`". `views.py`: "an invalid add shows the page again with the error". |
| `README.md` | File table: the same three new files. The example test numbers under "Run the tests", from the real output: Integration 13, Unit 14. |

No model change, no migration, no URL change, no new package, no settings change.

## The code

### `todos/forms.py`

```python
from django import forms

from .models import Todo


class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["title"]
```

### `todos/views.py`

```python
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TodoForm
from .models import Todo


def render_list_page(request, form):
    """The list page, with this add form (empty, or with the errors of a bad add)."""
    todos = Todo.objects.all()
    return render(request, "todos/todo_list.html", {"todos": todos, "form": form})


def todo_list(request):
    return render_list_page(request, TodoForm())


@require_POST
def todo_add(request):
    form = TodoForm(request.POST)
    if form.is_valid():
        form.save()
        return redirect("todo_list")
    return render_list_page(request, form)
```

`todo_toggle` and `todo_delete` stay exactly as they are.

- `form.is_valid()` runs the rules from the model. A title of only spaces becomes empty after the
  strip, so it is "required" and fails.
- Accounts (#17) changes `form.save()` to `todo = form.save(commit=False)`, sets the owner, and
  saves. Lists (#10) does the same with the list. That is why the view keeps the form in a
  variable, not in one line.

### `todos/templates/base.html`

```django
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}To-do list{% endblock %}</title>
  <link rel="icon" href="data:,">
  <style>
    /* Colors. Dark mode (#20) gives these new values; every new color needs a dark value too. */
    :root {
      --bg: #ffffff;
      --text: #000000;
      --muted: #666666;
      --border: #dddddd;
    }
    body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto; padding: 0 1rem;
           background: var(--bg); color: var(--text); }
    .messages { margin-bottom: 1rem; }
    .message { margin: 0 0 0.5rem; padding: 0.5rem; border: 1px solid var(--border); }
    .errorlist { list-style: none; padding: 0; margin: 0 0 0.5rem; }
    form.add { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
    form.add input { flex: 1; padding: 0.5rem; font-size: 1rem; }
    ul.todos { list-style: none; padding: 0; }
    ul.todos > li { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0;
                    border-bottom: 1px solid var(--border); }
    li .title { flex: 1; }
    li.done .title { text-decoration: line-through; color: var(--muted); }
    button { padding: 0.4rem 0.8rem; font-size: 0.9rem; cursor: pointer; }
  </style>
</head>
<body>
  {% if messages %}
    <div class="messages" role="status">
      {% for message in messages %}
        <p class="message{% if message.tags %} {{ message.tags }}{% endif %}">{{ message }}</p>
      {% endfor %}
    </div>
  {% endif %}

  {% block content %}{% endblock %}
</body>
</html>
```

Accounts (#17) adds its header at the top of `<body>`, above the messages. Dark mode (#20) adds the
`color-scheme` meta tag and the dark `@media` block.

### `todos/templates/todos/todo_list.html`

```django
{% extends "base.html" %}

{% block content %}
  <h1>To-do list</h1>

  {% if form.errors %}
    <div class="form-errors">
      {{ form.non_field_errors }}
      {{ form.title.errors }}
    </div>
  {% endif %}

  <form class="add" method="post" action="{% url 'todo_add' %}">
    {% csrf_token %}
    <input name="title" aria-label="New to-do" placeholder="What needs doing?" maxlength="200"
           required autofocus value="{{ form.title.value|default_if_none:'' }}"
           {% if form.title.errors %}aria-invalid="true" aria-describedby="{{ form.title.auto_id }}_error"{% endif %}>
    <button type="submit">Add</button>
  </form>

  <ul class="todos">
    {% for todo in todos %}
      {% include "todos/_todo_item.html" %}
    {% empty %}
      <li>Nothing to do yet. Add something above.</li>
    {% endfor %}
  </ul>
{% endblock %}
```

- `form.title.auto_id` is `id_title`, so the input points at `id_title_error`, the `id` Django
  5.2 gives the title's error list.
- Django escapes the typed title when it puts it back in `value="…"`, so quotes or `<script>` in a
  title cannot break the page.

### `todos/templates/todos/_todo_item.html`

The `<li>` from today's loop, moved here unchanged:

```django
<li class="{% if todo.done %}done{% endif %}">
  <span class="title">{{ todo.title }}</span>
  <form method="post" action="{% url 'todo_toggle' todo.pk %}">
    {% csrf_token %}
    <button type="submit">{% if todo.done %}Undo{% else %}Done{% endif %}</button>
  </form>
  <form method="post" action="{% url 'todo_delete' todo.pk %}">
    {% csrf_token %}
    <button type="submit">Delete</button>
  </form>
</li>
```

## Names later plans expect from wave 0

Every name below is made by this plan.

| Name | Expected by | Where in this plan |
|---|---|---|
| `TodoForm` in `todos/forms.py`, a `ModelForm` | #17, #4, #6, #5, #9, #11, #8, #10 | `forms.py` |
| `TodoForm.Meta.fields = ["title"]`, never `owner` / `todo_list` / `done` | #17, #10, #4 | `forms.py` |
| `TodoForm` takes no extra arguments (`TodoForm(request.POST)`, `TodoForm(instance=todo)`) | #4, #10 | `forms.py` |
| `todo_add` uses `TodoForm` and `is_valid()`; valid: redirect to the list | #6, #8, #9, #17, #10 | `views.py` |
| Invalid add: the list page again, status 200, error shown, typed title kept, own to-dos shown | #6 ("Check in the code"), #9, #10 | `views.py`, `render_list_page` |
| `render_list_page(request, form)`, public name, builds the list page with `todos` and `form` | #10 (adds `the_list`: `render_list_page(request, the_list, form)`), #17 (puts `filter(owner=request.user)` here) | `views.py` |
| The view keeps the form in a variable, so `form.save(commit=False)` can be added | #17, #10 | `views.py` |
| Title errors shown on the list page, next to the add form | #6, #9 | `todo_list.html`, `.form-errors` |
| The add form is hand-written and sends only `title` | #5, #11 (and #6: "the same way wave 0 writes the title") | `todo_list.html` |
| The 200-character rule, tested once in wave 0 | #6 (it removed its own long-title test) | test `test_long_title_is_not_added` |
| `todos/templates/base.html`, extended by every page | #17, #20, #4, #6, #5, #9, #11, #10, #18, #16, #14, #15 | `base.html` |
| `{% block content %}` in `base.html` | #17, #4 | `base.html` |
| A block for the page title (optional) | #4 ("if `base.html` has a block for the page title") | `{% block title %}` |
| All the CSS in `base.html`, in a `<style>` | #20, #6, #5, #9, #11, #4, #16, #15 | `base.html` |
| CSS variables on `:root`: `--bg`, `--text`, `--muted`, `--border` | #20 (exact names and light values), #5 and #9 (`--muted`), #9 (`--text`) | `base.html` |
| Light mode looks exactly as today | #20 | values in the table above |
| The messages block (`{% for message in messages %}`) in `base.html` | #19, #18, #8, #16 | `base.html` |
| `todos/templates/todos/_todo_item.html`, one row, included in the loop | #4, #6, #5, #9, #11, #8, #16, #13, #15 | `_todo_item.html` |
| The row is the whole `<li>`, with the class `done` on a done to-do (#6 adds `overdue` next to it) | #6, #9 (`li.done .priority`) | `_todo_item.html` |
| The row sees the page context (no `only`); `form` in the row is the add form | #13 (`next`), #15 (`can_reorder`) | the include |
| The title in the row is `<span class="title">` | #5 (wraps it in `.main`), #9 | `_todo_item.html` |
| URL names `todo_list`, `todo_add`, `todo_toggle`, `todo_delete` unchanged | all | no URL change |

## Tests

The rule: **test each rule once, in the lowest layer where a person would notice it.** A refactor
needs no new tests: the tests that exist already check that the page still works. The 11
integration tests and the CUJ test must all pass without any change. The CUJ test is the one that
shows the page still looks and works the same in a real browser: it finds the input by its label
"New to-do", the buttons by their names, the rows as `listitem`s, and the class `done`.

Only the new behavior gets tests. Both go in `AddTests` in
`todos/tests/integration/test_views.py` (integration layer: the test client, the form, the page
and the database together). There are no new unit tests: there is no logic outside the view and
the form, and the test pyramid plan says form rules are tested through the test client.

| Layer | Test | What it checks |
|---|---|---|
| integration | `test_empty_title_shows_the_page_again` | Make one to-do "Call home". `POST` `{"title": "   "}`: status 200 (not a redirect); the page contains "This field is required."; still only one to-do in the database; the page still shows "Call home"; the page contains `id="id_title_error"` **and** `aria-describedby="id_title_error"` (so the input really points at the error). |
| integration | `test_long_title_is_not_added` | `POST` a title of 201 `a`: status 200; nothing saved; the page contains "Ensure this value has at most 200 characters (it has 201)."; the input still holds the typed title (`value="aaa…"`, 201 times). |

The existing `test_empty_title_is_not_added` stays. It only checks that nothing is saved, so it
passes before and after.

**Shown failing first** (the rule in `AGENTS.md`): both tests fail today.
`test_empty_title_shows_the_page_again` gets a redirect (302), not 200.
`test_long_title_is_not_added` fails because SQLite saves the 201 characters today. Both pass after
step 4 (they need the new view **and** the new template).

The messages block has no test here, because nothing in wave 0 sends a message. The first feature
that sends one tests it through the page (for example #19's `test_clear_shows_message`).

## Steps

1. **Tests first.** Add the two tests above. Run `make test` and show that both fail, and that all
   the other tests pass.
2. **Form.** Make `todos/forms.py` with `TodoForm`.
3. **View.** Change `todo_list` and `todo_add` in `todos/views.py`, and add `render_list_page`. Run
   `make test`: the status is now 200, but the two new tests still fail, because the old
   template does not show the error or the typed title yet. Every other test passes.
4. **Templates.** Make `base.html` (move the `<head>` and the CSS there, with the variables and the
   `ul.todos` selectors, and add the messages block). Make `_todo_item.html` (move the `<li>`).
   Change `todo_list.html` to extend `base.html`, with the errors and the include. Run `make test`
   again: every test passes, including the CUJ test and the two new tests.
5. **Look at it.** `make run`, open <http://127.0.0.1:8000>. Add, mark done, undo, delete. The page
   must look the same as before (compare with `main`). Type only spaces as a title and press Add:
   the error shows, and the old to-dos are still there.
6. **Docs.** Update the file tables in `AGENTS.md` and `README.md`, and the example numbers in the
   README. Copy them from the real `make test` output: Integration 13, and Unit 14 (the README says
   11 today, which is already out of date).
7. **Before the commit:** `make check`.

## Open questions

None. A refactor with one small, wanted change (the error for a bad title).

## Review

What the adversarial review changed, and why (checked in a scratch copy of the repo with Django
5.2.17: the plan's code, all 28 tests including the CUJ, and the HTML before and after):

- Renamed `_list_page` to `render_list_page` (public name), the name lists (#10) uses; #10 adds
  the `the_list` argument. Added it to "Names later plans expect".
- Said that accounts (#17) puts its owner filter inside `render_list_page`. `accounts.md` still
  says "`todo_list`: `filter(owner=request.user)`"; with this plan `todo_list` has no query.
- "Invalid add shows the list page" was listed as expected by #4; #4 only shows its own edit page
  again. Now #6, #9 and #10.
- Wrote down that the row sees `form` (the add form) because there is no `only`.
- Noted that Django's error list adds a `listitem` on an error page.
- `test_empty_title_shows_the_page_again` now also checks `id="id_title_error"` and
  `aria-describedby`; before, a wrong id would pass every test.
- README numbers: Unit is 14 today, not 11. Copy the numbers from the real output.
- The new tests pass only after step 4, not step 3: the old template shows no error.
- Checked, no change needed: the HTML differs only in the CSS, `class="todos"` on the `<ul>`,
  `value=""` on the empty input and whitespace; `autofocus`, `maxlength`, `required`,
  `aria-label` and `class="done"` are unchanged. Both new tests fail on `main` (302, not 200)
  and pass after. Django 5.2 gives the error list `id="id_title_error"`. A typed `"><script>` is
  escaped in `value`.

## Decided by the person (2026-10-09)

The plan is **approved**. No open questions.
