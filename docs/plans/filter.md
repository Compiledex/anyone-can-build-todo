# Plan: filter the list (#13)

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: the test pyramid and the foundation refactor (wave 0: `TodoForm`, the partial
`_todo_item.html`, `base.html`), accounts (#17), lists (#10), sharing (#18), and search (#12,
built just before this; it made `TodoQueryForm` and `apply_list_query`). It must also work next to
tags (#11), priority (#9) and due date (#6), but it does not filter by them yet (see "Not part of
this task").

## Goal

A person can choose to see **all** their to-dos, only the ones **not done**, or only the ones
**done**. The choice is in the address of the page, so it works with the back button, a bookmark,
and a page reload. It works together with search: "not done, with *milk* in the title" is one
address, `?q=milk&status=open`.

When the person presses **Done**, **Undo** or **Delete** on a filtered or searched page, they come
back to the **same** page, not to the full list.

## Words used in this plan

- **Query parameter**: the part of an address after `?`, like `q=milk` in `/lists/1/?q=milk`. A
  `GET` request uses it to say *what to show*. It never changes data.
- **Open redirect**: a bug where a site sends the browser to *any* address that someone put in a
  link. An attacker can use it to send a person from our site to a fake one. We prevent it in
  step 5.
- **Queryset**: Django's description of a database question, like "all to-dos of this list". We
  can add more conditions to it before it runs.

## Decisions

- **The first set is only the status: all / not done / done.** Why this set:
  - Every to-do has a `done` value, so the filter is useful for every person, on every list.
  - It is the smallest step that builds the whole pattern: reading a query parameter safely,
    combining it with `?q=`, the links, and the "come back to the same view" redirect. Tag,
    priority and overdue filters can then each be a small task that adds one field to the same
    form (see "Not part of this task").
  - Tag, priority and overdue each have their own questions (several tags? "high and up" or only
    "high"? overdue in which time zone?). Mixing them in would make this task three tasks.
- **No new form and no new file for the query.** Search (#12) made **one** form, `TodoQueryForm`
  in `todos/forms.py`, and **one** function, `apply_list_query(todos, form)` in
  `todos/queries.py`. This task adds **one field** (`status`) to that form and **one line** to that
  function. Sort (#14) will do the same with `sort`. There is no `TodoFilterForm` and no
  `filters.py`.
- **One parameter: `status`.** Its values are `open` (not done) and `done`. No `status`, or any
  other value, means **all**. The links never write `status=all`; "All" is the address without
  `status`. So there is only one address for each view.
- **Bad values are ignored, never an error.** `?status=banana`, `?status=DONE`, `?status=` and a
  very long value all show the full list, with status code 200. A filter is only a view; a bad
  link should not break the page. A bad `status` does not turn off a good `q`, and the other way
  round: `TodoQueryForm` already drops only the field that is not valid (see #12). If `status`
  appears twice, Django's form reads the last one; that is fine.
- **The filter only makes the list smaller.** It starts from the same queryset the page already
  uses: the to-dos of the list that the view found with
  `get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)` (from #10 and #18). Then
  search adds its condition, then the filter adds its condition. So a filter can never show a
  to-do the person could not already see, and another user's list is still a 404.
- **The filter is a row of links, not a form with a button.** Three links: *All*, *Not done*,
  *Done*. The current one is marked with `aria-current="page"` so a screen reader says which one
  is chosen. Links need no JavaScript and no extra click.
- **Every link keeps the other parameters, by one helper.** A helper `list_query(data, **changes)`
  builds the part after `?` from the form's *cleaned* values, with some values changed. It keeps
  every field of `TodoQueryForm` that has a value. So when #14 adds `sort` to the form, the filter
  links keep `sort` with no change here. Unknown junk in the address (`?foo=bar`) is not a form
  field, so it is dropped from the links.
- **The search form keeps the filter.** It gets a hidden `<input name="status">` when a status is
  chosen. So a new search does not lose the filter.
- **Done, Undo and Delete come back to the same view.** Each of these forms gets a hidden
  `<input name="next">` with the current address, for example `/lists/1/?q=milk&status=open`.
  A helper `redirect_back(request, default)` in `todos/views.py` redirects there **only if** the
  value starts with `/` **and** Django's `url_has_allowed_host_and_scheme` says it is our own
  site. Otherwise it redirects to `default`, the normal list page. This is how Django's own login
  view handles `next`, plus the `/` rule (see step 5 for why).
- **Pressing Done on the "Not done" view makes the to-do disappear from that view.** This is
  correct: it is not "not done" any more. We do not add a message for it.
- **Adding a to-do still goes to the plain list page**, as today, without the search or filter.
  Then the new to-do is always visible, even if the person was looking at "Done" or a search.
  (An invalid add form shows the page again as today.)
- **The "no match" message from search is reused.** Search (#12) shows "No to-dos match" and a
  "Show all" link when `q` is set and nothing is found. This task widens that rule from "a search
  is set" to "a search **or** a filter is set". No extra database query and no second message.

## Not part of this task

- Filter by **tag** (#11), **priority** (#9) or **overdue** (#6). Each is a later small task: one
  more field in `TodoQueryForm`, one more line in `apply_list_query`, one more row of links.
- **Sort** (#14). It comes right after this, and adds `sort` to the same form. `list_query` and
  the hidden `next` already carry it, with no change.
- Remembering the last filter between visits (in the session or a cookie). The address is enough.
- Counts next to the links ("Not done (3)").
- Returning to the filtered view after **other** actions (edit #4, clear completed #19, subtasks
  #16, add). They can use `redirect_back` later; this task changes only toggle and delete.
- A filter in the Django admin. The admin already has `list_filter` if someone wants it.

## Changes to files

| File | Change |
|---|---|
| `todos/forms.py` | `TodoQueryForm` gets one new field, `status`. |
| `todos/queries.py` | New `filter_by_status(todos, status)` and `list_query(data, **changes)`; one new line in `apply_list_query`. |
| `todos/views.py` | The list view passes `status` and the filter links; a new `redirect_back` helper; toggle and delete use it. |
| `todos/templates/todos/todo_list.html` (the list page, from #10) | The filter links, the hidden `status` in the search form, the wider "no match" rule. |
| `todos/templates/todos/_todo_item.html` | A hidden `next` input in the Done/Undo and Delete forms. |
| `todos/tests/unit/test_list_query.py` | New: unit tests for the `status` field and `list_query`. |
| `todos/tests/integration/test_filter.py` | New: integration tests for the page and the redirects. |
| `AGENTS.md`, `README.md` | Say what `queries.py` and `next` do now; update the test numbers. |

No model change, so **no migration**. Existing to-dos are not touched.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Read what is there now

Search (#12) and the other wave 1 to 4 features change `views.py` and the template. Before
writing code, read:

- the list view, `TodoQueryForm` and `apply_list_query` as #12 merged them,
- the name of the list page template and of the "Show all" / "No to-dos match" part,
- the exact URL of the list page (`list_detail`, `/lists/<int:pk>/`).

Use the real names below where this plan guesses them.

### 2. Tests first

Write the tests in the table in step 8. Run `make test` and show that they fail.

### 3. The form — `todos/forms.py`

Add one field to the existing form:

```python
class TodoQueryForm(forms.Form):
    STATUS_CHOICES = [("open", "Not done"), ("done", "Done")]

    q = forms.CharField(required=False, max_length=200)   # already there, from #12
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False)
```

- `required=False` lets "no status" mean "all": the cleaned value is then `""`.
- A value that is not in `STATUS_CHOICES` makes only this field not valid. Django leaves it out of
  `cleaned_data`, so `cleaned_data.get("status", "")` gives `""`, and the page shows all to-dos.
  This is the "ignore bad values" rule. The `q` field still works.
- The page shows errors only for `q` (`{{ query_form.q.errors }}` from #12), so a bad `status`
  shows no error text. That is what we want: it is silently ignored.

### 4. The query helpers — `todos/queries.py`

```python
from urllib.parse import urlencode


def filter_by_status(todos, status):
    if status == "open":
        return todos.filter(done=False)
    if status == "done":
        return todos.filter(done=True)
    return todos


def apply_list_query(todos, form):
    form.is_valid()
    data = form.cleaned_data
    todos = search(todos, data.get("q", ""))
    todos = filter_by_status(todos, data.get("status", ""))   # the new line
    return todos


def list_query(data, **changes):
    """The part after "?" for the list page: the cleaned values, with some changed.

    Only values that are set are kept. Returns "" when nothing is set.
    """
    params = {key: value for key, value in {**data, **changes}.items() if value}
    return "?" + urlencode(params) if params else ""
```

- `filter_by_status` only adds a condition. It never starts a new queryset, so the owner and
  sharing rules from before stay in place.
- `list_query(form.cleaned_data, status="done")` gives the address of the "Done" link, with the
  current `q` (and later `sort`) kept. `list_query({})` is `""`: the "Show all" link.
- `urlencode` makes text like `milk & eggs` safe in an address.
- `cleaned_data` holds only the form's own fields, so junk like `?foo=bar` is never copied.

### 5. The views — `todos/views.py`

The list view does not change how it gets the to-dos (`apply_list_query` already does the work).
It passes three more things to the template:

```python
data = query_form.cleaned_data          # after apply_list_query, so is_valid() has run
status = data.get("status", "")
filter_links = [
    {"label": label, "query": list_query(data, status=value), "current": status == value}
    for value, label in [("", "All"), ("open", "Not done"), ("done", "Done")]
]
filtering = bool(data.get("q") or status)
```

Pass `status`, `filter_links` and `filtering` to the template. (`filtering` replaces the
`searching` flag from #12 for the "no match" message. Keep `searching` if #12 uses it elsewhere.)

A helper for "go back to where the person was":

```python
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme


def redirect_back(request, default):
    """Go back to the safe address in POST "next", or else to `default`."""
    next_url = request.POST.get("next", "")
    if next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return HttpResponseRedirect(next_url)
    return redirect(default)
```

- `url_has_allowed_host_and_scheme` returns `False` for other sites (`https://evil.example/`),
  for "scheme-relative" addresses (`//evil.example/`, which a browser opens on *another* site),
  for addresses with a backslash that browsers read as `//` (`/\evil.example`, `\\evil.example`),
  for `javascript:` addresses, and for an empty value. Then we use `default`.
- **Why also `startswith("/")`:** the check above says `True` for a bare word like `foo`. And
  Django's `redirect("foo")` does not treat a bare word as an address: it tries to find a URL
  *named* `foo`, fails, and the page crashes with error 500. With the `/` rule, only real paths on
  our site are used. (Checked with Django 5.2.)
- **Why `HttpResponseRedirect` and not `redirect`:** for the same reason. `HttpResponseRedirect`
  always treats the value as an address. Django's login view does the same.
- **A line break in `next` is safe.** Django writes it in the `Location` header as `%0D%0A`, so
  nobody can add a header of their own. (Checked with Django 5.2.)
- **`next` can only lead to a page on our own site, opened with `GET`.** That page checks again
  who may see it. So `next=/lists/<another user's list>/` only gives that user a 404.
- `require_https=request.is_secure()`: on the live server (HTTPS), an `http://` address to our
  own host is not accepted either.
- `todo_toggle` and `todo_delete` end with
  `return redirect_back(request, todo.todo_list.get_absolute_url())` instead of #10's
  `redirect(todo.todo_list)`. For delete, read the list before
  `todo.delete()`.
- **Order matters**: they still find the to-do first with `get_object_or_404` limited to what this
  user may change. A `next` value can never skip that check. Another user's to-do is still a 404.

### 6. The page — the list template

- Above the list, after the search form:

  ```html
  <nav class="filter" aria-label="Filter">
    {% for link in filter_links %}
      <a href="{{ request.path }}{{ link.query }}"{% if link.current %} aria-current="page"{% endif %}>{{ link.label }}</a>
    {% endfor %}
  </nav>
  ```

  `link.query` comes from `urlencode`, and Django escapes it again in the HTML (`&` becomes
  `&amp;`). That is correct: the browser reads `&amp;` in an `href` as `&`.
- Inside the search form from #12:
  `{% if status %}<input type="hidden" name="status" value="{{ status }}">{% endif %}`.
  `status` is the *cleaned* value, so it is only ever `open` or `done`.
- The "no match" part from #12: use `filtering` instead of `searching`. Show the quoted search
  text only when `q` is set, so "Done" with no search says just "No to-dos match." The "Show all"
  link stays `{{ request.path }}`. "Nothing to do yet. Add something above." stays for an empty
  list with no search and no filter.
- Style: `.filter a[aria-current] { font-weight: bold; }` and the CSS variables from wave 0 for
  colors, so dark mode (#20) works. No new color.

### 7. One row — `todos/templates/todos/_todo_item.html`

In **both** the Done/Undo form and the Delete form:

```html
<input type="hidden" name="next" value="{{ request.get_full_path }}">
```

- `request.get_full_path` is the current address with its query parameters. The template has
  `request` because `django.template.context_processors.request` is already on in
  `config/settings.py`.
- Django escapes the value in the HTML, so a `"` in the address cannot break the page.

### 8. The full list of tests

Each test goes in the folder for its layer. A test for user B always uses a to-do or list that
belongs to user A, and checks for 404 (not 403).

**Unit** — `todos/tests/unit/test_list_query.py` (`SimpleTestCase`, no database; a form that is
only validated needs no database):

| Test | What it checks |
|---|---|
| `test_no_status_means_all` | `TodoQueryForm({})` gives `status` `""`. |
| `test_open_and_done_are_read` | `open` and `done` come back as they are. |
| `test_unknown_status_means_all` | `banana`, `DONE` and a 1000-character value: `cleaned_data.get("status", "")` is `""`. |
| `test_bad_status_keeps_search` | `{"q": "milk", "status": "banana"}`: `q` is still `milk`. |
| `test_list_query_is_empty_without_values` | `list_query({})` and `list_query({"q": "", "status": ""})` are `""`. |
| `test_list_query_keeps_search_and_changes_status` | `list_query({"q": "milk & eggs", "status": "done"}, status="open")` is `?q=milk+%26+eggs&status=open`. |
| `test_list_query_keeps_unknown_future_fields` | `list_query({"q": "", "sort": "title"}, status="done")` keeps `sort=title`. This is what #14 relies on. |

**Integration** — `todos/tests/integration/test_filter.py` (Django test client, logged in with
`force_login`). Use two to-dos whose titles do not contain each other or the link labels, like
"Buy milk" (open) and "Call home" (done). Check the shown to-dos with
`response.context["todos"]`, not with `assertNotContains("Done")`: the word "Done" is also on the
buttons and the links.

| Test | What it checks |
|---|---|
| `test_open_shows_only_not_done` | `?status=open` shows the open to-do, not the done one. |
| `test_done_shows_only_done` | `?status=done` shows the done to-do, not the open one. |
| `test_no_status_shows_all` | No parameter: both are shown. |
| `test_bad_status_shows_all` | `?status=banana`: status 200, both are shown. |
| `test_filter_combines_with_search` | Three to-dos ("Buy milk" open, "Milk done" done, "Call home" open). `?q=milk&status=open` shows only "Buy milk". |
| `test_filter_links_keep_search` | On `?q=milk`, the "Done" link has `href` `<list url>?q=milk&amp;status=done` (check with `assertContains(..., html=True)`). |
| `test_current_filter_is_marked` | On `?status=done`, only the "Done" link has `aria-current="page"`. On no parameter, only "All" has it. |
| `test_search_form_keeps_status` | On `?status=open`, the search form has a hidden `status` with `open`. On `?status=banana`, there is no hidden `status`. |
| `test_no_match_message` | `?status=done` on a list with only open to-dos: "No to-dos match." and a "Show all" link, not "Nothing to do yet". |
| `test_other_users_list_with_filter_is_404` | User B opens user A's list with `?status=done`: 404. |
| `test_filter_shows_shared_todos` | On a list shared with B, B's `?status=done` shows the done to-do. |
| `test_toggle_returns_to_filtered_view` | Toggle with `next=<list url>?status=open` redirects to exactly that address. |
| `test_delete_returns_to_filtered_view` | Same for delete, with `next=<list url>?q=milk`. |
| `test_toggle_without_next_goes_to_list` | No `next`: redirect to the list page, as before. |
| `test_unsafe_next_is_ignored` | Each of `https://evil.example/`, `//evil.example/`, `/\evil.example/`, `\\evil.example/`, `javascript:alert(1)`, `http://testserver/` with `secure=True`, and `foo`: status 302 to the plain list page (never 500). Use `subTest` for each value. |
| `test_next_does_not_skip_owner_check` | User B toggles user A's to-do with a valid `next`: 404, and the to-do does not change. |

Use the real list URL from #10 where the table says `<list url>`.

**CUJ** — no new journey. Filtering is a way to look at the list, and every rule above is
noticed in the HTML or in the redirect address, so the integration layer is the lowest layer that
sees it. The existing journeys must still pass, because the Done and Delete buttons changed.

Some tests only guard an edge and pass before the change too: `test_no_status_shows_all`,
`test_bad_status_shows_all`, `test_toggle_without_next_goes_to_list`,
`test_other_users_list_with_filter_is_404`, `test_next_does_not_skip_owner_check`, and
`test_unsafe_next_is_ignored` (before the change, every redirect goes to the list page). We say
this in the pull request instead of pretending they were shown failing. The `foo` case of
`test_unsafe_next_is_ignored` **does** fail if someone writes `redirect(next_url)` without the
`/` rule: show that once.

### 9. Docs

- `AGENTS.md`: in the table, say that `todos/queries.py` now also filters by status and builds
  the list links; say that toggle and delete go back to `next` when it is safe.
- `README.md`: update the test numbers.

### 10. Before the commit

- Run `make check`.
- `make run`, then by hand: choose "Not done", search for a word, press Done on a row, and check
  that the address still has both `q` and `status`. Try `?status=banana` in the address bar.

## Open questions

1. Should the default view be **Not done** instead of **All**? Many to-do apps hide done items by
   default. This plan keeps **All**, because that is how the app works today, and a change in the
   default would surprise people. It is a one-line change later.

## Review

Changes made by the review:

- Removed `TodoFilterForm`, `read_status` and `todos/filters.py`: the shared names say one
  `TodoQueryForm` and one `apply_list_query` in `todos/queries.py`; `status` is now a field there.
- `list_query` now takes the form's cleaned values, not just `q` and `status`, so the filter links
  keep `sort` when #14 adds it (before, they would have dropped it).
- `redirect_back`: added the `startswith("/")` rule and `HttpResponseRedirect`. Checked: Django's
  check accepts `next=foo`, and `redirect("foo")` then crashes with `NoReverseMatch` (error 500).
- Checked backslash, scheme-relative and CRLF values against Django 5.2; added the backslash, `foo`
  and `http://` + `secure=True` cases to the test.
- Dropped `has_any_todos` and the second "No to-dos match." message: search (#12) already has
  one; this plan widens its rule (`filtering`) instead. One query less.
- Replaced `test_filter_does_not_show_other_users_todos` (it could not fail: B's list never holds
  A's to-dos) with a 404 test for A's list with `?status=done`.
- Integration tests now say to check `response.context["todos"]`, because "Done" is also a button
  and link label, so `assertNotContains("Done")` would be wrong.
- `test_filter_combines_with_search` now has a done to-do that also matches "milk"; before, it
  would pass even if the filter did nothing.
- Added unit tests: a bad `status` keeps a good `q`; `list_query` keeps future fields.
- Moved the open question "should Add keep the view?" into Decisions (no, as before), and the
  labels question too (All / Not done / Done, to match the buttons).
- Note for #14: `sort.md` says #12 and #13 keep the view after **Add** and **Edit**. They do not.
  #14 should only rely on `next` for toggle and delete.
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- The default view stays "All".
