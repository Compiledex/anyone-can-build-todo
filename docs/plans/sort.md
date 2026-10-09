# Plan: sort the list

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: #17 accounts, #10 lists, #6 due date, #9 priority, #18 sharing, #16 subtasks,
#12 search (`TodoQueryForm`, `apply_list_query`), #13 filter (`status`, `next`,
`redirect_back`, the link helper), and the wave 0 foundation (`_todo_item.html`, `base.html`,
CSS variables).

## Goal

A person can choose the order of the to-dos on a list:

| Choice in the menu | Value of `?sort=` | Order |
|---|---|---|
| Created (default) | `created` | Oldest first, as today. |
| Due date | `due` | Soonest due date first. To-dos with no due date go **last**. |
| Priority | `priority` | High, then Medium, then Low. |
| Title | `title` | A to Z, ignoring upper and lower case (for the letters A–Z). |

The choice is a **GET parameter** in the address, for example
`/lists/3/?q=milk&status=open&sort=due`. A GET parameter is the part of the address after `?`.
It only changes what the page *shows*, never the data, so GET is correct here (the rule in
`AGENTS.md`: change data only with POST).

Sort works together with search (#12) and filter (#13): first we pick the to-dos (the open list,
the search, the filter), then we put them in order.

## Decisions

- **One form, one function, no new file.** Sort follows the shared design from #12: it adds one
  field, `sort`, to `TodoQueryForm` in `todos/forms.py`, and one line to `apply_list_query` in
  `todos/queries.py`. There is no `sorting.py` and no second form.
- **An allow-list, never user input in `order_by`.** `todos/queries.py` has one fixed dictionary,
  `SORT_OPTIONS`, from the four allowed words to a label and the real order. The `sort` field is
  a Django `ChoiceField` whose choices come from that dictionary. A `ChoiceField` only accepts
  values from its list, so the text from the address can only ever be used as a *key* into our
  own dictionary. It is never given to `order_by()` itself. `?sort=-created_at` or
  `?sort=todo_list__owner__password` are just invalid values.
  Why it matters: `order_by("todo_list__owner__password")` would sort by a field the person must
  not see, and the order alone can leak information about it. Another value could make the page
  crash (error 500).
- **An unknown or empty value shows the default order** (`created`), with status 200. We do not
  show an error. A wrong sort is harmless, and an old bookmark should still open. This is the
  rule #12 already set: a bad value is ignored, one field at a time, and the others still work.
- **No date goes last.** In `due` order, to-dos without a due date go after all dated ones:
  `F("due_date").asc(nulls_last=True)`. A to-do with no date is the least urgent. Without
  `nulls_last`, SQLite would put them *first*, because it sorts "empty" (`NULL`) before every
  value. (Django 5.2, which this project uses, supports `nulls_last=True` on SQLite.)
- **Priority: `F("priority").desc()`.** #9 stores priority as a whole number, 1 = Low,
  2 = Medium, 3 = High ("a bigger number means more important"), and it can never be empty. So
  "biggest first" is the right order, and no `nulls_last` is needed. If the merged #9 code is
  different, follow the merged code and say so in the pull request.
- **The order is always stable.** "Stable" means: the same data always gives the same order,
  also when two to-dos have the same due date, priority or title. Every option ends with the same
  tie-breakers: `created_at`, then `pk` (the to-do's id number, which is unique). Two to-dos made
  in the same moment still have a fixed order.
- **`Meta.ordering` stays as it is.** `order_by()` replaces the model's default order, so the
  model does not change. `apply_list_query` *always* calls `order_by`, also for the default, so
  the order on the page never depends on `Meta.ordering`.
- **Only one direction per option.** There is no "Z to A" or "newest first". Four choices are
  enough for now, and fewer choices mean fewer tests.
- **Done to-dos are sorted like the others.** They are not moved to the bottom. The filter (#13)
  already lets a person hide them.
- **The choice is kept only in the address**, not in the database or the session. It is the
  smallest change (no new field, no migration), and it works the same way as search and filter.
  What this means after each action:
  - **Done, Undo, Delete:** the order is kept. #13 puts the whole current address in a hidden
    `next` field (`request.get_full_path`), so `sort=` is already in it. Nothing to add.
  - **Add, Edit (#4), and the others that #13 did not change:** they go back to the plain list
    page, so the order goes back to the default. #13 decided the same for the filter. This is a
    known limit, not a bug.
  - Opening the list fresh (from the menu of lists, or a new tab) shows the default order.
- **The menu is its own small form, with a "Sort" button.** It is a GET form with the
  `<select>`, and hidden inputs for the current `q` and `status`, so sorting keeps the search
  and the filter. In the other direction, the search form gets a hidden `sort` input, and the
  filter links (and the "Show all" link) keep `sort`. This is the same pattern #13 uses to keep
  `status` in the search form. We do not put the menu inside the search form: then a person who
  only wants to sort would press a button called "Search", which is confusing.
- **Sorting by title ignores case** with Django's `Lower("title")`. Known limit: on SQLite,
  `Lower` only changes the letters A–Z. Letters like `Æ Ø Å` keep their case, and they sort by
  their code number, so `å` comes before `æ` and `ø` (Norwegian order is `æ ø å`), and all of
  them come after `z`. Fixing this needs a database collation (a rule for comparing letters),
  which SQLite does not have built in. We accept this for now (search #12 has the same limit).
- **Subtasks (#16) keep their own order.** Sort changes the order of the top-level to-dos only.
  Subtasks stay under their parent, in their own `Meta.ordering`, because they are loaded with
  `prefetch_related("subtasks")`, which `order_by` on the top-level to-dos does not change.
- **Sharing (#18) is not affected.** The sort is in each person's own address, so two people
  looking at a shared list can each use a different order. Sort can only reorder the to-dos that
  the list page already picked; it can never add one.

### How "manual" order (#15, drag and drop) will fit

We do **not** build it now. But the design leaves one clear place for it:

- #15 adds one field, `position`, to `Todo`, and one more entry to `SORT_OPTIONS`:
  `"manual": ("Manual", ("position", "created_at", "pk"))`. Use `"pk"`, not `"id"`, so the
  unit test for tie-breakers (step 6) keeps passing.
- The form's choices are built from `SORT_OPTIONS`, so the fifth choice appears in the menu by
  itself.
- The default stays in **one** constant, `DEFAULT_SORT`. If #15 decides that "manual" should be
  the new default, it changes that one line (and the default-order test).
- The view passes `current_sort` to the template, so #15 can show the drag handles only when
  `current_sort == "manual"`.

## Not part of this task

- Drag and drop and the `position` field (#15, comes next).
- Reverse order ("Z to A", "newest first").
- Remembering the choice after leaving the page (in the session or the database).
- Keeping the order after Add or Edit (see Decisions).
- Sorting with more than one option at once (for example "priority, then due date").
- A correct Norwegian (or other language) letter order for titles.
- Sorting by tags (#11) or by list (#10). A tag can have many to-dos and a to-do many tags, so
  "sort by tag" has no single clear meaning.
- A database index for sorting. The lists are small; add one only if a page becomes slow.
- JavaScript to sort without reloading the page.

## Changes to files

| File | Change |
|---|---|
| `todos/queries.py` | `DEFAULT_SORT`, `SORT_OPTIONS`, `chosen_sort(form)`, and one sort line at the end of `apply_list_query`. |
| `todos/forms.py` | `TodoQueryForm` gets the field `sort` (a `ChoiceField` built from `SORT_OPTIONS`). |
| `todos/views.py` | The list view passes `current_sort` to the template (one line). |
| The link helper from #13 | The filter links and "Show all" keep `sort`. |
| `todos/templates/todos/todo_list.html` | The "Sort by" form; a hidden `sort` input in the search form. |
| `todos/tests/unit/test_sort.py` (new) | Unit tests for the `sort` field and `SORT_OPTIONS`. |
| `todos/tests/integration/test_sort.py` (new) | Integration tests for the order on the page. |
| `AGENTS.md`, `README.md` | A rule about `order_by`; new test numbers. |

No model change, so **no migration**. Existing to-dos are not touched.

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Read what is there now

#12 and #13 are merged before this. Read `todos/forms.py`, `todos/queries.py`, the list view, and
the list template. Find the real name of the helper that builds the filter links (the #13 plan
calls it `list_query(data, **changes)`). Use the real names below where this plan guesses them.

### 2. Tests first

Write the tests in step 7. Run `make test` and show that they fail. Start with
`test_sort_by_due_date_puts_no_date_last`: it fails on its assertion (the page ignores `sort` and
shows the oldest first), not only because a name is missing.

### 3. The allow-list — `todos/queries.py`

```python
from django.db.models import F
from django.db.models.functions import Lower

DEFAULT_SORT = "created"

# key: (label in the menu, the order). Every order ends with "created_at", "pk",
# so to-dos with equal values always keep the same order.
SORT_OPTIONS = {
    "created": ("Created", ("created_at", "pk")),
    "due": ("Due date", (F("due_date").asc(nulls_last=True), "created_at", "pk")),
    "priority": ("Priority", (F("priority").desc(), "created_at", "pk")),
    "title": ("Title", (Lower("title"), "created_at", "pk")),
}


def chosen_sort(form):
    """The sort key from a checked TodoQueryForm, or the default."""
    return form.cleaned_data.get("sort") or DEFAULT_SORT
```

At the end of `apply_list_query`, after search and filter:

```python
    return todos.order_by(*SORT_OPTIONS[chosen_sort(form)][1])
```

- `form.is_valid()` has already run at the start of `apply_list_query` (from #12). An invalid
  `sort` is missing from `cleaned_data`, and an empty one is `""`. Both give the default.
- `chosen_sort` can only return a key of `SORT_OPTIONS`, because the `ChoiceField` accepts
  nothing else. So `order_by` only ever gets our own code, never the person's text.

### 4. The form field — `todos/forms.py`

```python
from .queries import SORT_OPTIONS

class TodoQueryForm(forms.Form):
    q = ...       # from #12
    status = ...  # from #13
    sort = forms.ChoiceField(
        label="Sort by",
        required=False,
        choices=[(key, label) for key, (label, _order) in SORT_OPTIONS.items()],
    )
```

- `required=False` lets "no sort" mean the default.
- A `ChoiceField` compares exactly, so `TITLE` is not `title`: it is invalid, and the default is
  used.
- `forms.py` imports from `queries.py`. `queries.py` must **not** import from `forms.py`, or
  Python would get stuck in a circle of imports. (`apply_list_query` only receives the form; it
  does not need to import it.)

### 5. The view — `todos/views.py`

In the list view, after `apply_list_query(...)` (from #12), pass one more value to the template:
`current_sort = chosen_sort(query_form)`. Nothing else in the view changes. Who may see which
list is still checked first, so a list that is not the person's is still a 404, with or without
`sort`.

### 6. The page — `todos/templates/todos/todo_list.html` and the link helper

**The sort form**, next to the search form:

```html
<form method="get">
  {{ query_form.sort.label_tag }} {{ query_form.sort }}
  {% if query_form.cleaned_data.q %}<input type="hidden" name="q" value="{{ query_form.cleaned_data.q }}">{% endif %}
  {% if status %}<input type="hidden" name="status" value="{{ status }}">{% endif %}
  <button type="submit">Sort</button>
</form>
```

- `{{ query_form.sort }}` lets Django draw the `<select>` and mark the current choice as
  `selected`. With no or a bad `sort`, nothing is marked, so the browser shows the first option,
  "Created", which is also the order on the page.
- `label_tag` gives a `<label>` linked to the `<select>`, so a screen reader says "Sort by".
- The hidden inputs use the **cleaned** values, like #13 does. Django escapes them, so text like
  `"><b>` stays text. Use the real name of the status value from #13.
- No JavaScript is needed.

**The search form** (from #12) gets a hidden input, so a new search keeps the order:
`{% if current_sort != "created" %}<input type="hidden" name="sort" value="{{ current_sort }}">{% endif %}`.
Write `DEFAULT_SORT` into the template context instead of `"created"` if you prefer one source.

**The filter links and "Show all"** (from #13): #13's helper `list_query(data, **changes)` already
copies every cleaned `TodoQueryForm` field, so it keeps `sort` with no change to the helper. Do not
add a `sort` argument. Only check that it really does (the test below), and that a missing or
invalid `sort` is cleaned to `""` and left out of the address, so links stay short.

Colors come from the CSS variables on `:root` (wave 0), so dark mode (#20) works. No new color is
needed.

### 7. The full list of tests

Each rule is tested once, in the lowest layer where a person would notice it.

**Unit** — `todos/tests/unit/test_sort.py`, `SimpleTestCase` (no database). A form can be
checked without a database.

| Test | What it checks |
|---|---|
| `test_allowed_sort_keys_are_kept` | `TodoQueryForm({"sort": key})`, then `form.is_valid()` (it fills `cleaned_data`), for each of `created`, `due`, `priority`, `title`: `chosen_sort` gives the same key. |
| `test_bad_sort_key_gives_default` | `"bogus"`, `"-created_at"`, `"todo_list__owner__password"`, `"TITLE"`, `""` and no `sort` at all each give `"created"`. |
| `test_every_option_ends_with_tie_breakers` | The order of every entry in `SORT_OPTIONS` ends with `"created_at", "pk"`. This also guards the future `manual` option. |
| `test_link_helper_keeps_sort` | #13's `list_query` with cleaned data that has `sort="title"` keeps `sort=title` in the link it builds, with no change to the helper. |

**Integration** — `todos/tests/integration/test_sort.py`, Django test client, class `SortTests`.
Each test logs in as user A and opens A's list. Order is checked with
`list(response.context["todos"])`, like the existing `test_list_is_oldest_first`. Each test makes
the to-dos in an order that is **different** from the expected result, so the test fails if the
sort does nothing.

| Test | What it checks |
|---|---|
| `test_sort_by_due_date_puts_no_date_last` | Made in this order: due in 10 days, no date, due in 2 days (dates far from today). `?sort=due` shows: 2 days, 10 days, no date. |
| `test_sort_by_due_date_ties_use_created_at` | Two to-dos with the same due date. With `.update(created_at=...)`, the one made **second** (bigger `pk`) gets the **older** `created_at`. It must come first. (If both had creation order, the test would pass even without the tie-breaker.) |
| `test_sort_by_priority_most_important_first` | Made in this order: Low, High, Medium. `?sort=priority` shows High, Medium, Low. |
| `test_sort_by_title_ignores_case` | Made in this order: `"cherry"`, `"Banana"`, `"apple"`. `?sort=title` shows apple, Banana, cherry. (A plain sort by bytes would give Banana, apple, cherry, because capital letters come first. So this test fails without `Lower`.) |
| `test_bad_sort_shows_default_order` | `?sort=-created_at` gives status 200 and the oldest-first order (if the text reached `order_by`, it would be newest first). |
| `test_sort_menu_shows_current_choice` | With `?sort=due`, the "Due date" `<option>` has `selected` (checked with `assertContains(..., html=True)`). |
| `test_sort_combines_with_search_and_filter` | `?q=milk&status=open&sort=title` shows only the open to-dos that match "milk", in title order. |
| `test_forms_keep_each_other` | With `?q=milk&status=open&sort=title`: the sort form has hidden `q=milk` and `status=open`, and the search form has hidden `sort=title`. |
| `test_other_users_list_with_sort_is_404` | User B opens user A's list with `?sort=due`: 404. |

The existing default-order test (`test_list_is_oldest_first`, or its #10 version) already checks
the default order with no `sort`. It stays as it is, so the default is not tested twice.

Not tested again here: that Done/Undo/Delete come back to the same address. #13 tests `next`
already, and `sort` is just part of that address.

**CUJ** — none. The hidden inputs are checked in `test_forms_keep_each_other`, and a browser
sending a normal GET form is not something our code can break. A new journey would be slow and
add little.

### 8. Docs

- `AGENTS.md`: in the `todos/queries.py` row, mention the sort options. In "Rules", add:
  *Never pass text from a request to `order_by`; add an entry to `SORT_OPTIONS` instead.*
- `README.md`: update the test numbers under "Run the tests".

### 9. Before the commit

- Run `make check`.
- Run `make run`. Try each order, with and without a search and a filter. Click a filter link
  and check that the order stays. Mark a to-do done and check that the order stays. Try
  `?sort=nonsense` in the address.

## Open questions

1. **Norwegian letters in title order.** This plan accepts that `å` sorts before `æ` and `ø`,
   and after `z`, on SQLite. A correct order would need a custom collation, or a move to
   PostgreSQL. Is that good enough for you?

## Review

What the review changed, and why:

- Removed the new file `todos/sorting.py`: the shared names say sort is a field in `TodoQueryForm` plus one line in `apply_list_query`.
- The allow-list is now a Django `ChoiceField` built from `SORT_OPTIONS` (use what Django has); `resolve_sort` became `chosen_sort(form)`.
- Decided the priority order (`F("priority").desc()`, not nullable) from the #9 plan, instead of leaving it open.
- Fixed a wrong claim: after Add and Edit the order is **not** kept (#13 only keeps the address for Done/Undo/Delete).
- Fixed a real bug: #13's filter links and "Show all" kept only `q` and `status`, so clicking a filter would drop the sort. The link helper now keeps `sort`.
- Moved the menu to its own small form with a "Sort" button, plus hidden inputs both ways; #13's filter is links, not a form with a button, so "the same GET form" did not exist.
- Fixed `test_sort_by_title_ignores_case`: with "banana", "Apple", "cherry" it passed even without `Lower`. New data fails without it.
- Fixed `test_sort_by_due_date_ties_use_created_at`: it passed even without the tie-breaker. Now `created_at` goes against `pk` order.
- Every integration test now makes to-dos in an order different from the expected one, so "no sort at all" fails.
- Replaced `test_sort_shows_only_own_todos` (could not fail: `order_by` never adds rows) with a 404 test for another user's list with `?sort=`.
- Removed `test_sort_is_kept_after_toggle` (already tested by #13's `next` tests) and the CUJ (an integration test checks the hidden inputs).
- Said that `Meta.ordering` stays, and that `apply_list_query` always sorts, so the page never depends on it.
- Told #15 to use `"pk"`, not `"id"`, in the manual order, so the tie-breaker test still passes.
- Moved "remember the choice" and "manual as default" out of Open questions: both are already decided (address only; #15 decides).
- Names aligned with lists.md and accounts.md (orchestrator pass).
- Orchestrator decision: #13's `list_query(data, **changes)` already keeps `sort`; #14 does not change the helper.

## Decided by the person (2026-10-09)

The plan is **approved**.

- Title order for æ, ø, å on SQLite is accepted for now; fixing it is a small task later.
