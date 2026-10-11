# Plan: æ, ø and å sort and search correctly

Status: **approved** (2026-10-11, by the orchestrator for the person), not started.

Builds on: **search** (#12, `search()` in `todos/queries.py`), **sort** (`SORT_OPTIONS["title"]`),
**tags** (`todos/tags.py`, tag names are stored in lower case), and the **test pyramid**
(`config/test_runner.py`: the folder of a test is its layer).

## Words used in this plan

- **SQLite**: the database the app uses. It is one file, `db.sqlite3`, on the person's Mac.
- **Collation**: a rule that says which of two texts comes first. The database uses it in
  `ORDER BY`. SQLite lets a program add its own collation, written in Python.
- **SQL function**: a small function the database can call while it runs a query, like `LOWER()`.
  SQLite lets a program add its own, written in Python.
- **Case folding** (`str.casefold()` in Python): turning a text into one form where upper and
  lower case are the same. `"ÆREND".casefold()` is `"ærend"`. It is a stronger `lower()`: it also
  turns `ß` into `ss`.
- **Signal** (`connection_created`): Django calls our function each time it opens a new
  connection to the database. That is where we add the collation and the function.

## What is wrong today

Facts, checked on `main` (commit `2dc6747`):

- `SORT_OPTIONS["title"]` in `todos/queries.py` sorts by `Lower("title")`. SQLite's `LOWER()` only
  changes the letters A to Z. `Æ`, `Ø` and `Å` stay upper case, and SQLite then compares the
  Unicode numbers of the letters: `Å` (U+00C5) < `Æ` (U+00C6) < `å` (U+00E5) < `æ` (U+00E6) <
  `ø` (U+00F8). So "apple, Banana, Zebra, Ærend, øl, Ål" comes out as
  "apple, Banana, Zebra, Ål, Ærend, øl". A reviewer saw "a, z, Æ, å, ø". The Norwegian order is
  a to z, then æ, ø, å.
- `search()` uses `icontains`. On SQLite that is `LIKE`, which ignores case only for A to Z. So
  "ærend" does not find "Ærend", and "ØL" does not find "øl". This is true for the title, the
  notes and the tag names.
- Tag names: `parse_tags` uses Python's `.lower()`, which works for all letters
  (`"ÆRE".lower()` is `"ære"`). So the stored tag names are already right. Only the search
  (`tags__name__icontains`) is wrong, because the typed text is not made lower case before `LIKE`.

The person is Norwegian, so these are words they use every day.

## Goal

On a list page, "Sort by Title" gives the Norwegian alphabet: a to z, then æ, ø, å, and upper and
lower case count as the same letter. A search finds a to-do whatever the case of any letter, also
æ, ø, å and other letters like é or ß, in the title, the notes and the tag names. No migration, no
new package, nothing for the person to install.

## Decisions

### 1. One small new file: `todos/sqlite_functions.py`

It holds three plain Python functions, and one function that adds them to a database connection:

```python
"""Python functions that SQLite uses for Norwegian sorting and for search.

SQLite's own LOWER() and LIKE only know the letters A to Z. These functions
know every letter. They are added to every new SQLite connection (see
TodosConfig.ready in apps.py), also in the tests and in manage.py commands.
"""

COLLATION = "norwegian"     # the name SQL uses: ORDER BY title COLLATE "norwegian"
CASEFOLD = "casefold"       # the name SQL uses: casefold(title)


def casefold(text):
    """The text in one case, for comparing: NFC, then str.casefold(). None stays None."""


def norwegian_key(text):
    """A sort key: a to z, then æ, ø, å. Upper and lower case are the same."""


def compare_norwegian(a, b):
    """-1, 0 or 1, the way SQLite wants a collation to answer."""


def add_functions(sender, connection, **kwargs):
    """The connection_created signal handler. Only for SQLite."""
```

Reasons:

- **One place.** Both the collation and the search function live here, and only here.
- **Plain functions first.** `casefold`, `norwegian_key` and `compare_norwegian` need no
  database, so unit tests (`SimpleTestCase`) can check every letter fast.
- The names `norwegian` and `casefold` are not SQLite built-ins (checked: SQLite has `BINARY`,
  `NOCASE`, `RTRIM`, and no `casefold()`), so they never clash.

### 2. `casefold(text)`: NFC, then `str.casefold()`

- `unicodedata.normalize("NFC", text).casefold()`.
- **NFC first.** On a Mac, "å" can arrive as two characters: "a" and a small ring (this is called
  NFD). NFC joins them into one "å". Then a typed "å" and a pasted "å" are the same.
- `None` gives `None`, because SQL can pass `NULL`. (Today no searched column can be `NULL`, but a
  crash here would break the whole page.)
- **Only case, not accents.** "e" does not find "é". The person asked for case. Ignoring accents
  is a separate choice (see "Not part of this task").

### 3. `norwegian_key(text)`: the Norwegian alphabet

The key is a list of pairs `(group, number)`, one or more per character of `casefold(text)`.
Python compares lists pair by pair, and a shorter list that is the start of a longer one comes
first ("al" before "ale").

| Character (after `casefold`) | Pair | So it sorts |
|---|---|---|
| `a` to `z` | `(1, 0)` to `(1, 25)` | in the normal order |
| `æ`, and `ä` | `(1, 26)` | after z (`ä` is the Swedish and German way to write æ, and Norwegian dictionaries sort it as æ) |
| `ø`, and `ö` | `(1, 27)` | after æ (the same reason) |
| `å` | `(1, 28)` | last |
| another letter with an accent, like `é`, `ü`, `ñ` | its base letter, `e`, `u`, `n` | with its base letter |
| another letter, like Greek or Cyrillic | `(2, its Unicode number)` | after å |
| anything else: a space, a digit, a sign | `(0, its Unicode number)` | before a (as today: SQLite's order also puts spaces, digits and most signs before letters) |

"Its base letter" means: `unicodedata.normalize("NFKD", ch)`, then drop the combining marks
(`unicodedata.combining`). A character that becomes two letters, like `ß` (casefold gives `ss`)
or `ﬁ`, gives two pairs.

### 4. `compare_norwegian(a, b)`: equal keys give 0

It returns `-1`, `0` or `1` from the two keys. "Ål" and "ål" have the same key, so the answer is
`0`, and `ORDER BY` then uses the next columns: `created_at`, then `pk`. That is the "stable
tiebreak", and it is the same as today: today "Apple" and "apple" also tie and keep the order
they were made in. We do not add a tiebreak inside the collation (for example "upper case
first"), because the page already has one, and two tiebreaks would be harder to explain.

### 5. Add them to every connection with the `connection_created` signal

`todos/apps.py`, in `TodosConfig.ready()`:

```python
def ready(self):
    from django.db import connections
    from django.db.backends.signals import connection_created

    from .sqlite_functions import add_functions

    connection_created.connect(add_functions, dispatch_uid="todos_sqlite_functions")
    # A connection opened before ready() (rare) gets them too.
    for connection in connections.all(initialized_only=True):
        add_functions(sender=connection.__class__, connection=connection)
```

`add_functions` does nothing unless `connection.vendor == "sqlite"`. For SQLite it calls, on the
real `sqlite3` connection (`connection.connection`):

- `create_collation(COLLATION, compare_norwegian)`
- `create_function(CASEFOLD, 1, casefold, deterministic=True)` (deterministic means: the same
  input always gives the same output, so SQLite may reuse an answer).

Why this works everywhere:

- `ready()` runs in every program that starts Django: `runserver`, `manage.py send_reminders`,
  `manage.py shell`, and the test runner. With `--parallel`, each worker process runs
  `django.setup()` too, so `ready()` runs there, and the signal fires for each worker's copy of
  the test database.
- `dispatch_uid` makes sure the handler is connected only once, even if `ready()` runs twice.
- Django's own `django.contrib.postgres` does the same thing (signal plus the loop over open
  connections), so this is a known pattern.

Tried on 2026-10-11 with Django 5.2.17 and an in-memory database: the order came out as
"apple, Banana, Zebra, Ærend, øl, Ål, ål", "ÆREND" found "Ærend", "ØL" found the tag "øl", `%`
was still a normal character, and a brand-new connection (`connections.create_connection`)
answered `SELECT casefold('ÆØÅ')` with `æøå`.

### 6. Sort: `Collate("title", COLLATION)`

`SORT_OPTIONS["title"]` becomes:

```python
# Norwegian order: a to z, then æ, ø, å; upper and lower case are the same
# (see todos/sqlite_functions.py).
"title": ("Title", (Collate("title", COLLATION), "created_at", "pk")),
```

`Collate` is Django's own (`django.db.models.functions.Collate`). It makes
`ORDER BY "todos_todo"."title" COLLATE "norwegian" ASC, ...`. The collation name is our constant,
never text from a request, so the rule "never pass text from a request to `order_by`" still holds.
`Lower` is no longer imported in `queries.py`.

### 7. Search: `casefold()` on both sides, with Django's `Contains`

```python
class CaseFold(Func):
    """casefold(column) in SQL: the column in one case (see sqlite_functions)."""
    function = CASEFOLD
    output_field = TextField()


def search(todos, q):
    if not q:
        return todos
    folded = casefold(q)
    with_matching_tag = todos.filter(Contains(CaseFold("tags__name"), folded)).values("pk")
    return todos.filter(
        Q(Contains(CaseFold("title"), folded))
        | Q(Contains(CaseFold("description"), folded))
        | Q(pk__in=with_matching_tag)
    )
```

- `CaseFold` lives in `todos/queries.py`, next to the one place that uses it.
- `Contains` is Django's own lookup (`django.db.models.lookups.Contains`), used as an expression
  in `filter()` (allowed since Django 4.0). It still escapes `%`, `_` and `\`, so
  `test_percent_sign_is_not_a_wildcard` keeps passing.
- Both sides are folded the same way, so the match ignores case for every letter. On SQLite
  `contains` is `LIKE`, which also ignores case for A to Z; that does not matter, both sides are
  already folded.
- The sub-query for tags stays a sub-query, so a to-do with two matching tags is still shown once.
- `casefold(q)` is computed once in Python; the column is folded by SQLite for each row.

### 8. Performance

SQLite calls our Python function once per row and column during a search, and the collation once
per comparison during a title sort. The person's lists have tens or hundreds of to-dos, on their
own Mac, so this costs well under a millisecond. No index can be used, but `LIKE '%...%'` can not
use an index today either. The number of queries does not change (no new query).

## Security

- **No text from a request reaches SQL as code.** The collation name and the function name are
  constants. The search text goes in as a parameter (`%s`), as today, through Django's `Contains`.
- **`order_by` still only gets entries of `SORT_OPTIONS`.** `TodoQueryForm` is not changed.
- **Data isolation is not changed.** `search()` still starts from the `todos` it is given (the
  open list's to-dos), and the tag sub-query starts from them too. Never `Todo.objects` here.
- **No crash from odd text.** `casefold` and `norwegian_key` accept any string, also empty, emoji,
  or control characters; `casefold(None)` is `None`. A Python error inside a SQLite function
  would make the page fail, so the unit tests feed them odd strings.
- **No data in GET that was not there before.** The address is the same: `?q=` and `?sort=title`.

## Data and migrations

No model change, no migration, no data change. `Collate` and `CaseFold` are only used in queries,
so `makemigrations --check` (in `make check`) sees nothing new. The model constraint
`unique_list_name_per_owner` (`Lower("name")`) is not touched (see "Not part of this task").
The tests never open `db.sqlite3`. Going back: revert the commit; nothing is stored.

## Working next to

`docs/plans/recurring-undo-steps.md` is planned at the same time. It changes `todos/views.py`,
`todos/tests/integration/test_views.py`, `todos/tests/integration/test_sharing.py` and one cell
of the `todos/views.py` row in `AGENTS.md`. This plan changes `todos/queries.py`, `todos/apps.py`,
a new `todos/sqlite_functions.py`, the search and sort tests, `README.md`, and the
`todos/queries.py` row plus one new row in `AGENTS.md`. **No shared code file.** Both touch
`AGENTS.md`, but different rows. **Merge order: this plan first, then recurring-undo-steps** (or
either; the second one rebases, and a conflict, if any, is only in `AGENTS.md`).

The app redesign (`feature/app-redesign`, paused) changes templates and CSS only, not
`queries.py`, so it does not conflict.

## Not part of this task

- **Ignoring accents in search** ("e" finds "é"). A separate choice; today it does not either.
- **"aa" sorted as "å"** (old Norwegian spelling in names like "Aasen"). Dictionaries do it,
  most apps do not. It would surprise more often than help.
- **List names**: the constraint `unique_list_name_per_owner` and `name__iexact` in
  `TodoListForm` still ignore case only for A to Z, so "Ærend" and "ærend" can both be list names.
  Fixing that needs a migration (the constraint is in the database). See "Left for the person".
- **The order of tags on a row** (`Tag.Meta.ordering = ["name"]`): `å` still comes before `æ`
  there. It is a model option; changing it touches every place that shows tags.
- Changing `parse_tags` from `.lower()` to `.casefold()`. `.lower()` is already right for æ, ø, å.
  (`ß` stays `ß` in a tag; the search still finds it, because both sides are case folded.)
- Another database (PostgreSQL). `add_functions` does nothing there, and `Collate("title",
  "norwegian")` would then need a real collation. The person runs only SQLite.

## Changes to files

| File | Change |
|---|---|
| `todos/sqlite_functions.py` (new) | `COLLATION`, `CASEFOLD`, `casefold`, `norwegian_key`, `compare_norwegian`, `add_functions` (decisions 1 to 5). Imports only `unicodedata`. |
| `todos/apps.py` | `TodosConfig.ready()`: connect `add_functions` to `connection_created` with `dispatch_uid`, and call it for every open connection (decision 5). |
| `todos/queries.py` | `SORT_OPTIONS["title"]` uses `Collate("title", COLLATION)`, with the new comment; drop the `Lower` import. Imports: `F, Func, Q, TextField` from `django.db.models`, `Collate` from `django.db.models.functions`, `Contains` from `django.db.models.lookups`, and `CASEFOLD, COLLATION, casefold` from `.sqlite_functions`. New `CaseFold(Func)`. `search()` folds `q` with `casefold` and uses `Contains(CaseFold(...), folded)` for title, notes and tag names. The docstring of `search()` says "ignoring case for every letter (also æ, ø, å)" and that `Contains` escapes `%` and `_`. |
| `todos/tests/unit/test_sqlite_functions.py` (new) | Unit tests (see "Tests"). |
| `todos/tests/integration/test_sort.py` | Two new tests (see "Tests"). |
| `todos/tests/integration/test_search.py` | Four new tests (see "Tests"). |
| `todos/tests/integration/test_sqlite_functions.py` (new) | One test that a new connection has the function and the collation. |
| `AGENTS.md` | `todos/queries.py` row: `title` is "Norwegian order: a to z, then æ, ø, å, ignoring case (the `norwegian` collation)"; `search` ignores case "for every letter, also æ, ø, å (`CaseFold` on both sides)"; remove both "(A-Z only on SQLite)" notes. New row `todos/sqlite_functions.py`: what the three functions do, that `TodosConfig.ready()` adds them to every SQLite connection with the `connection_created` signal, and "a query that uses `COLLATE \"norwegian\"` or `casefold()` fails on a connection that missed them, so never open a raw `sqlite3` connection for app queries". `todos/models.py` row: unchanged. |
| `README.md` | "Find a to-do, and sort them": "Search the titles, notes and tags of a list (upper and lower case do not matter, also for æ, ø and å)." and "Sort by date added, due date, priority, title (a to z, then æ, ø, å), or your own order." "How it is put together": add the `todos/sqlite_functions.py` row, and in the `todos/queries.py` row nothing else changes. |

## Steps

1. **Tests first.** Write `todos/tests/unit/test_sqlite_functions.py`, the new tests in
   `test_sort.py` and `test_search.py`, and `todos/tests/integration/test_sqlite_functions.py`.
   Run `make unit` and `make integration`: the unit tests fail (no module yet), and the new sort
   and search tests fail with today's order and today's search. Show the person the failures.
2. Write `todos/sqlite_functions.py`.
3. Change `todos/apps.py`.
4. Change `todos/queries.py`.
5. `make test`: all pass, also the old ones (`test_sort_by_title_ignores_case`,
   `test_percent_sign_is_not_a_wildcard`, `test_search_query_count_does_not_grow_with_rows`,
   `test_todo_with_two_matching_tags_is_shown_once`). Also run `make test PARALLEL=2` once
   (`make test` uses one process by default), so the worker processes are covered: each worker
   must get the collation and the function from the signal.
6. `uv run python manage.py makemigrations --check --dry-run`: "No changes detected". No manual
   check in the browser: the tests use the real view, and `db.sqlite3` is never opened.
7. Update `AGENTS.md` and `README.md`.
8. `make check`, then commit. In the last commit, set the Status line of this plan to
   `**done** (<date>)`.

## Tests

### Unit: `todos/tests/unit/test_sqlite_functions.py` (`SimpleTestCase`, no database)

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_casefold_makes_nordic_letters_one_case` | `casefold("ÆØÅ")` is `"æøå"`; `casefold("Straße")` is `"strasse"`. | Using SQLite's `LOWER()`-like ASCII rule, or `.lower()` (keeps `ß`). |
| `test_casefold_joins_a_split_letter` | `casefold("å")` (a plus ring) equals `casefold("å")`. | Leaving out the NFC step. |
| `test_casefold_keeps_none` | `casefold(None)` is `None`. | Calling `.casefold()` on `None` (a crash on a `NULL` column). |
| `test_norwegian_order` | `sorted(["Ål", "Zebra", "øl", "Ærend", "apple", "Banana"], key=norwegian_key)` is `["apple", "Banana", "Zebra", "Ærend", "øl", "Ål"]`. | Sorting by Unicode number (gives `Ål` before `Ærend`). |
| `test_swedish_letters_sort_as_norwegian` | `ä` sorts with `æ` and `ö` with `ø`: `sorted(["øre", "Ärlig", "örn", "ære"], key=norwegian_key)` is `["ære", "Ärlig", "øre", "örn"]` ("ære" is before "Ärlig" because e comes before l). | Leaving `ä`/`ö` to the accent rule (they would sort as a and o). |
| `test_accented_letter_sorts_with_its_base_letter` | `"élan"` sorts between `"dag"` and `"fisk"`; `"über"` between `"tak"` and `"vann"`. | Putting every non-ASCII letter after z. |
| `test_case_does_not_change_the_key` | `norwegian_key("ÅL") == norwegian_key("ål")`, and `compare_norwegian("ÅL", "ål") == 0`. | A key that keeps case. |
| `test_compare_answers_minus_one_zero_one` | `compare_norwegian("z", "æ") == -1`, `("å", "ø") == 1`, `("a", "a") == 0`, `("al", "ale") == -1`. | Returning a bool, or the wrong sign. |
| `test_signs_and_digits_before_letters_other_letters_after` | `sorted(["b", "2", " x", "ж", "å"], key=norwegian_key)` is `[" x", "2", "b", "å", "ж"]`. | A key that crashes or mixes groups. |
| `test_odd_text_does_not_crash` | `""`, `"🙂"`, `"\x00"`, `"ﬁ"`, 200 × `"Å"` give a key and a casefold without an error. | A Python error inside a SQLite function, which breaks the page. |
| `test_add_functions_skips_other_databases` | `add_functions(sender=None, connection=<a stub with vendor "postgresql">)` does nothing (the stub's `connection` attribute is never touched). | Calling `create_collation` on a database that has no such method. |

### Integration: `todos/tests/integration/test_sort.py` (`LoggedInTestCase`)

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_sort_by_title_uses_norwegian_order` | Make "Ål", "Zebra", "øl", "Ærend", "apple", "Banana" (in that order); `?sort=title` shows `["apple", "Banana", "Zebra", "Ærend", "øl", "Ål"]`. | Today's `Lower("title")` (gives "Ål, Ærend, øl" after Zebra), or the collation not being used. |
| `test_sort_by_title_nordic_case_ties_keep_created_order` | Make "ål" then "Ål"; the shown order is `["ål", "Ål"]`. Then set "Ål"'s `created_at` one hour earlier (as `test_sort_by_due_date_ties_use_created_at` does); the order is `["Ål", "ål"]`. | A collation that puts upper case first, or a missing `created_at` tiebreak. |

The old `test_sort_by_title_ignores_case` (apple, Banana, cherry) stays and must still pass.
`test_every_option_ends_with_tie_breakers` (unit) still checks the title option ends with
`created_at`, `pk`.

### Integration: `todos/tests/integration/test_search.py` (`SearchTests`)

Each "finds" test also makes one to-do that must **not** be found, so an empty filter cannot
pass.

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_search_ignores_case_of_nordic_letters_in_title` | "Ærend på posten" and "Kjøp melk"; `?q=ærend` shows only "Ærend på posten", and `?q=ÆREND` does too. | Today's `icontains` (SQLite `LIKE` ignores case for A to Z only). |
| `test_search_ignores_case_of_nordic_letters_in_notes` | Notes "Kjøp ØL og brus" on "Fest", and "Vask bilen" with no notes; `?q=øl` shows only "Fest". | Folding only the title. |
| `test_search_ignores_case_of_nordic_letters_in_tags` | "Handle" with the tag `åker` (typed "Åker", stored `åker`), and "Ring" with the tag `jobb`; `?q=ÅKER` shows only "Handle". | Folding only the column, not the typed text (the tag is already lower case). |
| `test_nordic_search_keeps_other_users_out` | alice has "Ærend i byen" with the tag `ærend`; bob's list has "Ærend for bob". bob searches **his** list for `ÆREND`: he sees only `["Ærend for bob"]` (the "does happen" case), and not alice's to-do. Same shape as `test_other_users_todos_never_match`. | A tag sub-query that starts from `Todo.objects` instead of `todos` (alice's to-do would then match through her tag). |

`test_search_query_count_does_not_grow_with_rows`, `test_todo_with_two_matching_tags_is_shown_once`
and `test_percent_sign_is_not_a_wildcard` stay and must still pass.

### Integration: `todos/tests/integration/test_sqlite_functions.py` (`SimpleTestCase` with `databases = {"default"}`)

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_a_new_connection_has_the_functions` | Open a new connection with `connections.create_connection("default")`, run `SELECT casefold('ÆØÅ')` (gives `æøå`), `SELECT 'å' < 'ø' COLLATE "norwegian"` (gives `0`) and `SELECT 'ø' < 'å' COLLATE "norwegian"` (gives `1`), then close it (in a `try`/`finally`). | Adding the functions only to the current connection, or only in a test's `setUp`, instead of with the signal. |

No CUJ test: the browser sees the same page, only the rows are in another order, and the
integration tests already check that through the real view.

## Decided by the orchestrator for the person (2026-10-11, person away)

- **Fix it in Python inside SQLite (a collation and a function), not with a new column.** No
  migration, nothing stored, easy to revert. A stored "sort key" column would need a migration and
  must be kept up to date on every save.
- **Norwegian order: a to z, then æ, ø, å.** `ä` counts as `æ`, `ö` as `ø`. Other accented letters
  sort with their base letter.
- **Upper and lower case are the same letter**, and equal titles keep the order they were made in
  (`created_at`, then `pk`), as today.
- **Search ignores case for every letter, but not accents.**
- **Both are registered for every connection with `connection_created` in `TodosConfig.ready()`.**

## Left for the person

- **List names "Ærend" and "ærend" can both exist** (the constraint ignores case only for A to Z).
  Fixing it needs a migration that changes a database constraint, and a check for existing lists
  that would then clash. Not done here. Do you want a separate small plan for it?
- **Should search also ignore accents** ("e" finds "é", "o" finds "ø")? Not done: for a Norwegian
  "o" and "ø" are different letters, so it could give wrong matches.

## Review

Self-review by the planner (2026-10-11), reading the plan as a stranger would, against the real
code on `main` (`2dc6747`):

- Checked every name: `SORT_OPTIONS`, `search()`, `Lower`, `parse_tags`, `TodosConfig`,
  `LoggedInTestCase` (`client_for`, `other_user`, `other_list`), `SearchTests.search/shown/add`,
  `SortTests.add/shown`, and the old tests the plan says must still pass. All exist.
- Tried the approach on 2026-10-11 (Django 5.2.17, Python 3.13, in-memory SQLite, not
  `db.sqlite3`): the collation, `Collate`, `Contains(CaseFold(...))` in `filter()` and with `Q`,
  the tag sub-query, `%` escaping, and a new connection. All worked as written.
- Fixed: `test_swedish_letters_sort_as_norwegian` had a wrong expected order ("ære" comes before
  "Ärlig", because e is before l).
- Fixed: `test_nordic_search_keeps_other_users_out` could not fail (the old version had no way for
  another user's row to match). It now copies `test_other_users_todos_never_match`: alice's to-do
  has a matching tag, so a sub-query from `Todo.objects` would leak it.
- Fixed: the new-connection test also checks the "does happen" direction (`'ø' < 'å'` is `1`).
- Fixed: `make test` uses one process by default (`PARALLEL ?= 1` in the `Makefile`), so a step
  now runs `make test PARALLEL=2` once to cover the worker processes.
- Removed a manual browser step that would have needed a database; `makemigrations --check`
  instead.
- Checked: `parse_tags` uses `.lower()`, which is right for æ, ø, å, so stored tags need no change.
- Found, and left out on purpose: list-name uniqueness and tag display order have the same A to Z
  limit (see "Not part of this task" and "Left for the person").
