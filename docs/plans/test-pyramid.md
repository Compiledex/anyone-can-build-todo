# Plan: a test pyramid for the to-do list

Status: **done**. See "Result" at the end.

## Goal

1. Sort the tests into three layers, so each kind of check sits where it is cheapest and most
   useful.
2. The test runner finds each test's layer **by itself**, from the folder the test is in. Nobody
   has to tag a test by hand.
3. After a run, the runner prints one line per layer, top to bottom, like this:

   ```
   Test layers
     CUJ           1 passed
     Integration  10 passed
     Unit         35 passed
   ```

   If something fails, the line for that layer says so: `Integration   9 passed, 1 failed`.
4. The tests run in parallel, on every CPU core, on a laptop and on GitHub.

```
        /\        CUJ (end-to-end)   a real browser, the whole app
       /  \
      /----\      Integration        Django test client: URL -> view -> page -> database
     /      \
    /--------\    Unit               one method on its own, no requests, no database
```

A **CUJ** (critical user journey) is an important task a person does from start to finish, like
"add a to-do, finish it, delete it". A CUJ test drives a real browser and checks what the person
sees.

The numbers above are an example. The real numbers are whatever the app needs. We do not write
tests only to make a layer bigger.

## Why the middle layer is the widest

The usual pyramid has the most tests at the bottom. This app has almost no logic that stands on
its own: most of it is the view, the form, the page and the database working together. Django's
test client tests exactly that, and it is fast (a few milliseconds per test, no browser).

So we follow one rule: **test each rule once, in the lowest layer where a person would notice
it.**

- **Form rules** (title required, 200 characters at most, the date format) are tested through the
  test client, in the integration layer. The form is only used by `todo_add`, and what matters is
  what the page does with bad input. Testing the form on its own as well would test the same rule
  twice.
- **Pure logic** that needs no request and no database, like `Todo.is_overdue(today=...)`, is
  tested in the unit layer, with fixed dates.
- **CUJ tests** check only that the parts work together in a real browser. They do not test every
  rule again.

## The folders

```
todos/tests/
    __init__.py
    unit/
        __init__.py
        test_models.py
    integration/
        __init__.py
        test_views.py
    cuj/
        __init__.py
        test_journeys.py
config/tests/
    __init__.py
    unit/
        __init__.py
        test_test_runner.py
```

**The folder is the layer.** A test in `.../tests/unit/` is a unit test, and so on.

## The test runner — new file `config/test_runner.py`

Django lets a project choose its own test runner with the setting `TEST_RUNNER`. Ours is a small
subclass of Django's own `DiscoverRunner`, so everything else (finding tests, the test database,
`--parallel`) stays Django's.

In `config/settings.py`:

```python
TEST_RUNNER = "config.test_runner.LayeredTestRunner"
```

The runner does three things:

1. **It finds each test's layer** from its module name. `todos.tests.integration.test_views` is
   in the `integration` layer. A function `layer_of(test)` does this.
2. **It refuses tests that break the rules**, before any test runs, with a clear message:
   - A test that is not in `unit/`, `integration/` or `cuj/`. Every test must have a layer.
   - A unit test that is not a `SimpleTestCase`. Django's `SimpleTestCase` blocks the database,
     so a "unit test" that quietly uses the database fails at once.
   - A CUJ test that is not a `StaticLiveServerTestCase`. A CUJ test needs a real server.
3. **It counts results per layer and prints the summary** at the end. It does this with its own
   result class, which counts every pass, failure, error and skip by layer. This also works with
   `--parallel`: Django sends every result from the worker processes back to the main process,
   one by one, so the main process can still count them by layer.

The runner itself has unit tests in `config/tests/unit/test_test_runner.py`:

| Test | What it checks |
|---|---|
| `test_layer_from_folder` | A test in `.../tests/unit/` is in the `unit` layer, and the same for the other two. |
| `test_test_without_layer_is_refused` | A test outside the three folders stops the run with a clear message. |
| `test_unit_test_with_database_is_refused` | A `TestCase` in `unit/` stops the run. |
| `test_summary_counts_per_layer` | Given some results, the summary prints the right numbers on the right lines. |

## Running in parallel

### On a laptop: Django's `--parallel`

Django can already run tests in parallel: `manage.py test --parallel auto` starts one worker
process per CPU core, and gives each worker its own copy of the test database. This works for all
three layers:

- **Unit and integration**: each worker has its own copy of the database, so tests cannot get in
  each other's way.
- **CUJ**: each worker starts its own live server on a free port that the system picks, and its
  own Chromium browser.

Three things to know:

- Django splits the work **by test class**, not by test method. All tests in one class run in the
  same worker. So the tests are split into several small classes, by topic (for example
  `AddTests`, `ToggleTests`, `DeleteTests`), not one big `TodoTests`.
- When a test fails in a worker, Django needs the package **`tblib`** to send the error back to
  the main process. Without it, a failure shows a confusing error instead of the real one. We add
  it: `uv add --dev tblib`.
- Starting a worker takes time (Python and Django start again in each one). With only a few fast
  tests, parallel can be **slower** than one process. The CUJ tests are slow (a browser), so they
  gain the most. Step 6 below measures this, and we keep whichever is faster.

### On GitHub: two jobs at the same time

`.github/workflows/check.yml` gets two jobs that run at the same time instead of one after the
other:

| Job | What it runs | Needs Chromium? |
|---|---|---|
| `lint` | the commit checks, the migration check | no |
| `test` | all three layers, with `--parallel auto` | yes |

The `lint` job then does not wait for the Chromium download. The `test` job prints the layer
summary in its log.

## Commands

| Command | What it runs |
|---|---|
| `make test` | all three layers, in parallel, with the summary |
| `make unit` | only `unit/` folders |
| `make integration` | only `integration/` folders |
| `make cuj` | only `cuj/` folders |
| `make check` | the commit checks, the migration check, then `make test` |

`make unit` and `make integration` give fast feedback while working. They pass the folder paths
to `manage.py test`, so the runner does not need any extra options.

The commit checks (`.pre-commit-config.yaml`) do **not** run tests. They stay fast, as today.

## The layers

### Unit — `todos/tests/unit/test_models.py`

| Test | What it checks |
|---|---|
| `test_past_due_date_is_overdue` | Due the day before `today`, not done: overdue. |
| `test_due_today_is_not_overdue` | Due on `today`: not overdue. |
| `test_done_todo_is_not_overdue` | Done, due before `today`: not overdue. |
| `test_no_due_date_is_not_overdue` | No due date: not overdue. |

These come with the due-date feature (`docs/plans/due-date.md`). `Todo(...)` objects are made in
memory and never saved, so no database is needed. Today the model has no logic of its own worth a
unit test, so before the due-date feature, the only unit tests are the runner's own.

### Integration — `todos/tests/integration/test_views.py`

**The 5 tests that exist today** move here, split into small classes by topic.

**New tests that close gaps that exist today:**

| Test | What it checks |
|---|---|
| `test_get_does_not_add` | `GET /add/` returns 405 and saves nothing. |
| `test_get_does_not_toggle` | `GET /<pk>/toggle/` returns 405 and changes nothing. |
| `test_get_does_not_delete` | `GET /<pk>/delete/` returns 405 and deletes nothing. |
| `test_toggle_unknown_todo_is_404` | Toggling a to-do that does not exist returns 404. |
| `test_delete_unknown_todo_is_404` | Deleting a to-do that does not exist returns 404. |
| `test_list_is_oldest_first` | The list shows to-dos in the order they were made. |

`AGENTS.md` says only `POST` may change data, but no test checks it today. The first three tests
do.

**Tests that come with the due-date feature** (listed in `docs/plans/due-date.md`): add with and
without a date, an invalid date, another date format, a title that is too long, the due date on
the page, and the `overdue` class.

### CUJ — `todos/tests/cuj/test_journeys.py`

A real Chromium browser, driven by **Playwright**, against a real server started by Django's
`StaticLiveServerTestCase`. Playwright waits by itself until the page is ready, so the tests are
less fragile than with Selenium.

| Test | The journey |
|---|---|
| `test_plan_and_finish` | Open the page. Add two to-dos. Mark one done, then undo it. Delete one. Reload the page: the right to-do is still there. |
| `test_overdue_todo` | A to-do due in the past is shown in red. After marking it done, it is no longer red. |

`test_plan_and_finish` can be written now. The due-date feature adds a due date to it, and adds
`test_overdue_todo`. Each test is its own class, so the two can run in different workers.

Add Playwright as a development package with `uv add --dev playwright`, then download the browser
once with `uv run playwright install chromium` (about 150 MB).

**A known problem:** Playwright's API runs an event loop, and Django then refuses to touch the
database, with the error `SynchronousOnlyOperation`. The fix is to set the environment variable
`DJANGO_ALLOW_ASYNC_UNSAFE=true`, only inside the CUJ test classes (in `setUpClass`). It is never
set for the real server.

## Steps

Each step ends with `make test` passing.

1. **Folders.** Move `todos/tests.py` into `todos/tests/integration/test_views.py`, split into
   small classes. Still 5 tests, all passing.
2. **The runner, test first.** Write `config/tests/unit/test_test_runner.py` and show it failing.
   Then write `config/test_runner.py`, set `TEST_RUNNER`, and show it passing. The summary now
   shows the `Unit` line (the runner's own tests) and the `Integration` line.
3. **Integration gaps.** Add the 6 new integration tests. They test behavior that already exists,
   so they pass at once. To show they really test something, break the code on purpose for one of
   them (for example, remove `@require_POST`), see the test fail, and put the code back.
4. **CUJ.** Add Playwright and `test_plan_and_finish`. Show it passing, and failing when a button
   is broken on purpose. The summary now has all three lines.
5. **Parallel.** Add `tblib`, and `--parallel auto` in the `Makefile`. Break one test on purpose
   and check that the real error and the right layer line still show.
6. **Measure.** Time `make test` with and without `--parallel auto`, and write both times in the
   pull request. Keep whichever is faster.
7. **Commands, CI and docs.** Update the `Makefile` (`test`, `unit`, `integration`, `cuj`,
   `check`), `check.yml` (the two jobs), `AGENTS.md` (the file table, the commands, the layers and
   the folder rule) and `README.md` (the test count, the browser download, the summary).
8. Run `make check`.

## Order with the due-date plan

Do this plan **first**. Then the due-date tests go straight into the right folders, and
`docs/plans/due-date.md` only needs `todos/tests.py` changed to the layer folders.

## Not part of this task

- Load tests, snapshot tests, and mocking the database. They add little to an app this small.
- Testing in more than one browser. Chromium is enough here.
- Measuring test coverage.
- Splitting the GitHub `test` job into one job per layer. Each job would download and install
  everything again, so for tests this fast it would be slower, not faster.

## Result

All steps are done. `make test` now prints:

```
Test layers
  CUJ           1 passed
  Integration  11 passed
  Unit         11 passed
```

The unit tests are the test runner's own tests. The `is_overdue` unit tests come with the due-date
feature.

**Parallel was slower**, as expected for so few tests. Measured on a 10-core Mac, the whole
`manage.py test`, three runs each:

| How | Time |
|---|---|
| one process | 0.97 s |
| `--parallel 2` | 1.21 s |
| `--parallel auto` (10 processes) | 1.33 s |

So `make test` uses one process. The `Makefile` has `PARALLEL ?= 1`, and `make test PARALLEL=auto`
turns parallel on. It works: failures show the real error on the right layer line. Change the
default when the tests get slow, for example when there are more CUJ tests.

On GitHub, the two jobs (`lint` and `test`) do run at the same time.

Two small changes from the plan:

- CUJ tests extend `BrowserTestCase` (in `todos/tests/cuj/browser.py`), which starts Playwright and
  Chromium, gives each test a fresh page, and sets a 5-second timeout instead of Playwright's 30.
- `make setup` now also downloads Chromium.
