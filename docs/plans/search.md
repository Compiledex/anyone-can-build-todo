# Plan: search the to-dos (#12)

Status: **done** (2026-10-10, PR #21). The decisions are in "Decided by the person" at the end.

Builds on: the foundation refactor (`TodoForm`, `_todo_item.html`, CSS variables), #17 accounts,
#10 lists, #5 description, #11 tags, #18 sharing.

## Goal

A person types a word in a search box and presses Enter. The list then shows only the to-dos that
contain that word. The box still shows the word, so the person can see what they searched for and
change it. A "Show all" link brings the whole list back.

Search only **reads** data, so it uses a `GET` form. The word goes in the address, as `?q=milk`. A
**query parameter** is a `name=value` pair after the `?` in an address. This also means a search
can be saved as a bookmark, and the browser's Back button works.

## Decisions

- **Search looks in three places: the title, the description (#5) and the tag names (#11).** A
  person remembers a word, not where they wrote it. All three exist after wave 3, so this costs
  almost nothing.
- **Case does not matter.** We use Django's `icontains` lookup ("contains, ignoring case").
  `milk`, `Milk` and `MILK` all find "Buy milk". A **lookup** is the part after `__` in a Django
  filter, like `title__icontains`.
- **The search text is one phrase.** `buy milk` finds "Buy milk today", but not "Milk, buy it".
  Splitting into separate words is a later idea.
- **Spaces at the start and end are removed.** A search of only spaces is the same as no search:
  the whole list is shown.
- **Search works inside the list that is open now, not across all lists.** The reasons:
  - #13 filter and #14 sort also work on the open list, as more query parameters on the same
    page. Search belongs with them.
  - The page already knows how to show one list. A search across lists would need a new page that
    also shows which list each to-do is in.
  - Who may see what is already checked when the list is opened (see the next point).
- **Only to-dos the person may see can match.** The list page opens the list with the helper from
  #10/#18 (it gives the list only if the person owns it or it is shared with them, and a `404`
  otherwise). Search only filters the to-dos **inside** that list. So it can never reach anyone
  else's to-dos. Tag names are matched only on tags attached to those same to-dos.
- **A to-do is shown once,** even if two of its tags match. We match tags with a sub-query
  (`pk__in=...`), not with a join plus `.distinct()`. A **join** reads two tables together, and it
  can return the same to-do twice. A **sub-query** is a small query inside the big one: "the
  numbers of the to-dos that have a matching tag". It avoids the duplicates, and it does not get
  in the way when #14 adds sorting. The sub-query also starts from the to-dos of the open list,
  not from every to-do in the database, so it never even reads other people's rows.
- **`%` and `_` are normal letters in a search.** In SQL, `%` and `_` are wildcards ("any text",
  "any one letter"). Django's `icontains` escapes them for us, so `?q=50%` finds "50% off" and
  does not match everything. A test checks this.
- **When nothing matches**, the page says `No to-dos match “milk”.` and shows a "Show all" link.
  This is a different message from the empty list ("Nothing to do yet"), so the person knows the
  list is not empty. The word in the message is the **cleaned** search text (no spaces at the
  ends). If the list is really empty and someone opens it with `?q=milk`, the page also says "No
  to-dos match": that is true. #13 filter keeps this one message and widens its rule to "a search
  or a filter is set".
- **The search box keeps the typed text,** with `value="{{ query_form.q.value|default_if_none:'' }}"`.
  Django **escapes** it: it changes `<`, `>`, `"`, `'` and `&` into safe codes like `&lt;`. So
  text like `<b>` or `"><script>` is shown as text and never runs as HTML. The value is always
  inside double quotes in the template; without the quotes, escaping would not be enough.
  Never use `|safe` on the search text.
- **The search text may be at most 200 characters,** like a title. A longer one shows an error
  under the box, and the whole list is shown.
- **One form object reads all the query parameters.** A new Django form, `TodoQueryForm`, reads
  `request.GET`. Today it has one field, `q`. #13 and #14 each add one field to it, and one step
  to `apply_list_query`. The view keeps the same three lines for the query; #13 and #14 only add
  what they pass to the template (for example the filter links).
- **A bad value is ignored, one field at a time.** If one parameter is wrong, only that one is
  ignored; the others still work. Nobody gets an error page from a strange address.

## Not part of this task

- **Search across all lists.** It could come later as its own page. It can reuse the same
  `search()` function with a different starting set of to-dos (all to-dos in
  `TodoList.objects.visible_to(user)`), and show the list name on each result.
- **Keeping the search after Done, Undo, Delete or Add.** These buttons `POST` and then go back to
  the list without `?q=`, so the search is cleared. This is decided and accepted for now: #13
  filter adds the safe "go back to this address" field (`next`, checked with Django's
  `url_has_allowed_host_and_scheme`) and the `redirect_back` helper, for search and filter
  together.
- **Search in subtasks (#16), and anything about recurring (#8) or reminders (#7).** They are in
  the same wave as this task, so this plan cannot assume them.
- **Filter (#13) and sort (#14).** This plan only makes room for them.
- **Highlighting the matching word** in the results.
- **Search as you type** (JavaScript). The page works with a normal form and Enter.
- **Letters outside A–Z.** See "Open questions": with SQLite, `icontains` ignores case only for
  the letters A–Z. `æ`, `ø`, `å`, `é` are matched, but only in the same case.

## Changes to files

| File | Change |
|---|---|
| `todos/forms.py` | New form `TodoQueryForm`, with one field `q`. |
| `todos/queries.py` | New file. `search(todos, q)` and `apply_list_query(todos, form)`. |
| list view in `todos/views.py` | Read `request.GET` through `TodoQueryForm`, and pass the result on. |
| `todos/templates/todos/todo_list.html` (the list page, from #10) | The search form, the "no match" message, the "Show all" link. |
| `todos/tests/integration/test_search.py` | New file with the search tests. |
| `todos/tests/cuj/test_journeys.py` | One new journey: search, then show all. |
| `todos/admin.py` | Nothing. (Django's admin has its own search; not needed here.) |
| `AGENTS.md`, `README.md` | The new file `todos/queries.py`, and the new test numbers. |

No model change, so **no migration**. Existing data does not change.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in step 6. Run `make test` and show that they fail. Start with
`test_search_finds_word_in_title`: today the page ignores `?q=`, so it shows both to-dos and the
test fails on its assertion. Some tests already pass today, because the page ignores `q`:
`test_empty_search_shows_whole_list`, `test_search_stays_in_open_list`,
`test_other_users_todos_never_match` and `test_other_users_list_with_search_is_404`. They guard
against a broken search later. We say so in the pull request instead of pretending they failed.

### 2. The form — `todos/forms.py`

```python
class TodoQueryForm(forms.Form):
    q = forms.CharField(required=False, max_length=200)
```

`CharField` removes spaces at the start and end by itself (`strip=True` is the default). It is
not a `ModelForm`, because it does not save anything; it only reads the address.

### 3. The query function — new file `todos/queries.py`

```python
from django.db.models import Q


def search(todos, q):
    if not q:
        return todos
    with_matching_tag = todos.filter(tags__name__icontains=q).values("pk")
    return todos.filter(
        Q(title__icontains=q) | Q(description__icontains=q) | Q(pk__in=with_matching_tag)
    )


def apply_list_query(todos, form):
    form.is_valid()
    data = form.cleaned_data
    return search(todos, data.get("q", ""))
```

- `todos` is the starting set: the to-dos of the open list. `search` can only make it smaller, so
  it can never add a to-do the person may not see. **Both** parts start from `todos`: the main
  filter and the tag sub-query. Never write `Todo.objects` in this file; that would start from
  every user's to-dos. (`queries.py` therefore does not import `Todo` at all.)
- `.values("pk")` makes the sub-query return only the numbers of the to-dos. Django puts it
  inside the main query as `pk IN (SELECT ...)`, so there is still only one trip to the database.
- `Q(...) | Q(...)` means "this **or** that".
- `form.is_valid()` fills `form.cleaned_data` with the fields that are valid. A field that is not
  valid is missing from it, so `.get("q", "")` gives "no search". We call `is_valid()` but do not
  stop when it is `False`: that is how "ignore a bad value, one field at a time" works.
- A form made from `request.GET` is always **bound** (it has data), even when the address has no
  `?`. So with no `q` at all, the form is valid and `q` is `""`.
- **How #13 and #14 fit in:** each adds one field to `TodoQueryForm` and one line to
  `apply_list_query`, for example `todos = filter_by_status(todos, data.get("status", ""))` and
  `todos = sort(todos, data.get("sort", ""))`. The three query lines in the view stay the same;
  they only pass new things to the template.

The names of the fields (`description`, and the `tags` relation with `name`) are the ones planned
in #5 and #11. If they end up different, use the real names.

### 4. The view — the list view in `todos/views.py`

After #10, one view shows one list (here called `list_detail`). Change only how it gets the
to-dos:

```python
todo_list = <the #10/#18 helper that returns the list or a 404>
query_form = TodoQueryForm(request.GET)
todos = apply_list_query(<the to-dos the page shows now>, query_form)
q = query_form.cleaned_data.get("q", "")  # filled by is_valid() inside apply_list_query
```

- `<the to-dos the page shows now>` is the queryset the view already uses before this task
  (probably `todo_list.todos.all()`, maybe with `select_related` or `prefetch_related("tags")`).
  Keep it exactly; search only goes **after** it.
- The list must be found **first**, with the helper. A wrong list number is a `404` before any
  search runs.
- Pass `todos`, `query_form`, `q` and `searching = bool(q)` to the template. Everything else in
  the view stays the same.
- If another view also shows the list page (for example the add view, when the add form is not
  valid, renders the list again with the error), it must pass the same things. That helper
  exists: #10's `render_list_page(request, the_list, form)` builds the page for `list_detail` and
  for an invalid add (#18 adds its keys there too). Put these lines **inside it**, once, with
  `the_list` as the list and `the_list.todos.all()` as the start. On the invalid-add page
  `request.GET` is empty, so it simply shows the whole list. #13, #14 and #15 add their lines there
  too. Do not copy them.

### 5. The page — the list template

- A search form, above the list and below the add form:

  ```html
  <form class="search" method="get" role="search">
    <input type="search" name="q" aria-label="Search to-dos" placeholder="Search"
           maxlength="200" value="{{ query_form.q.value|default_if_none:'' }}">
    <button type="submit">Search</button>
    {% if searching %}<a href="{{ request.path }}">Show all</a>{% endif %}
  </form>
  {{ query_form.q.errors }}
  ```

  With no `action`, the form sends to the page it is on, so it stays in the open list.
  `role="search"` tells screen readers what this form is. #13 and #14 keep their values when a
  person searches: each adds a hidden input (`status`, `sort`) to this same form.
- In the `{% empty %}` part of the list: if `searching`, show `No to-dos match “{{ q }}”.`;
  otherwise keep the old "Nothing to do yet" text. The "Show all" link is already in the search
  form just above, so we do not add a second one. Use `{{ q }}` (the cleaned text), not `query_form.q.value` (the raw text, with spaces).
- The input is written by hand, so it has no `id` and the error is not linked to it. That is
  fine for one short error; do not add more.
- Style: give `form.search` the same flex layout as `form.add`, with colors from the CSS variables.

### 6. Tests

**Unit:** none. The search has no logic without the database, and the form rules (spaces, 200
characters) are tested through the page (see `docs/plans/test-pyramid.md`: test each rule once, in the lowest layer where
a person would notice it).

**Integration**, in the new file `todos/tests/integration/test_search.py`, class `SearchTests`.
Each test logs in a user with `self.client.force_login(...)` and uses that user's list.

| Test | What it checks |
|---|---|
| `test_search_finds_word_in_title` | `?q=milk` shows "Buy milk" and not "Call home". |
| `test_search_ignores_case` | `?q=MILK` finds "Buy milk". |
| `test_search_finds_word_in_description` | A to-do whose description has the word is shown; its title does not have it. |
| `test_search_finds_tag_name` | A to-do with tag "shopping" is found with `?q=shop`. |
| `test_todo_with_two_matching_tags_is_shown_once` | Tags "shop" and "shopping", `?q=shop`: the to-do is in `response.context["todos"]` once. |
| `test_empty_search_shows_whole_list` | `?q=%20%20` shows every to-do, and no "Show all" link and no "No to-dos match". |
| `test_search_trims_spaces` | `?q=%20milk%20` finds "Buy milk", and the message for a miss says `“milk”`, not `“ milk ”`. |
| `test_percent_sign_is_not_a_wildcard` | To-dos "50% off" and "Call home": `?q=%25` (a `%`) shows only "50% off". |
| `test_no_match_shows_message` | `?q=xyz` shows `No to-dos match` and a "Show all" link, not "Nothing to do yet". |
| `test_search_box_keeps_typed_text` | `?q=milk`: the page has the **whole** search `<input>` element, with every attribute and `value="milk"`, checked with `assertContains(..., html=True)`. (With `html=True`, Django compares whole elements: a needle with only some of the attributes does not match.) |
| `test_search_text_is_escaped` | `?q="><script>x</script>`: `assertNotContains` the raw `<script>x</script>`, and `assertContains` the escaped `&quot;&gt;&lt;script&gt;`. This checks both the box and the "no match" message. |
| `test_too_long_search_shows_error_and_whole_list` | 201 characters: status 200, the "at most 200 characters" error, every to-do shown, no "No to-dos match". Also check 200 characters is accepted (no error). |
| `test_search_stays_in_open_list` | The same user has "milk" in another list; it is not shown. |
| `test_other_users_todos_never_match` | User A has "Buy milk" with tag "milk" in A's list. User B searches their own list for "milk": A's to-do is not shown. This test fails if the main filter in `search` ever starts from `Todo.objects` instead of `todos`. |
| `test_other_users_list_with_search_is_404` | User B opens user A's list with `?q=milk`: `404`. |
| `test_shared_list_can_be_searched` | A list shared with B: B's search there finds the matching to-do. |

**CUJ**, in `todos/tests/cuj/test_journeys.py`: `test_search_and_show_all`. Add "Buy milk" and
"Call home", type `milk` in "Search to-dos" and press Enter. Only "Buy milk" is shown, and the box
still says `milk`. Click "Show all": both are shown and the box is empty. This checks the real
browser part: Enter sends the `GET` form, and the address keeps `?q=`.

### 7. Docs

- `AGENTS.md`: add `todos/queries.py` to the table ("builds the to-dos shown on a list page from
  the address: search now, filter and sort later"), and mention `TodoQueryForm` for `forms.py`.
- `README.md`: add `todos/queries.py` to the file table, and update the layer numbers under "Run
  the tests".

### 8. Before the commit

- Run `make check`.
- Open the page with `make run`. Search for a word in a title, a description and a tag. Search in
  capitals. Search for something that is not there. Look at it in a narrow window and in dark
  mode (#20): the search box and the "Show all" link must be readable in both.

## Open questions

1. **Letters outside A–Z (æ, ø, å, é).** With SQLite, `icontains` ignores case only for A–Z. So
   `øl` does not find "Øl", and `ÅSE` does not find "Åse". For a Norwegian user this matters.
   Fixes, from small to big: (a) accept it for now; (b) a SQLite function that lowercases with
   Python, registered when the database connects (about 10 lines, no new package); (c) move to
   PostgreSQL on the live server. This plan does (a), and a later small task can do (b). Is that
   acceptable, or should (b) be part of this task?

## Review

What the review changed, and why:

- The tag sub-query now starts from `todos`, not `Todo.objects`. The old version did not leak (the outer filter still limited it), but it scanned every user's to-dos, and it made `Todo.objects` look normal in this file.
- The "no match" message uses the cleaned `q`, not the raw box value: the raw value keeps the spaces at the ends.
- The view passes `q`, and the plan says where the query must go if another view (an invalid add) also renders the list page.
- The view keeps its existing starting queryset instead of assuming `todo_list.todos.all()`.
- The softer claim about #13/#14: they add a field and a step, but they do pass new things to the template.
- New tests: spaces at the ends are removed, `%` is not a wildcard, 200 characters is still accepted.
- The escape test now uses `"><script>`, so it also checks that the text cannot break out of `value="..."`.
- The `html=True` test now says to use the whole `<input>` element: a partial element never matches.
- The tag-leak test now gives user A's to-do a matching tag. It fails if the main filter in `search` starts from `Todo.objects`. It cannot fail if only the tag sub-query starts from `Todo.objects`: the main filter still keeps only the open list's to-dos, so that mistake only makes the search slower, not wrong.
- Removed `test_search_does_not_change_data`: a `GET` view that never writes makes it pass even if search were broken.
- Listed every test that already passes before the change, as `AGENTS.md` asks for honesty about "see it fail".
- Removed the open questions about keeping the search after Done/Delete and about search across lists: the build order already decides the first (#13 does it), and the second is under "Not part of this task".
- Only one "Show all" link (in the search form), not a second one in the empty message.
- Added a dark-mode check to the manual test.
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- Upper/lower case for æ, ø, å is NOT part of this task. Accept the SQLite limit; it is a small task later.

## Post-review check

- The orchestrator pass made `render_list_page` (#10, extended by #18) the one place that builds
  the list page. Named it here as the place for the search lines, so #13–#15 follow.
