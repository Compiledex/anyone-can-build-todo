# Plan: split the browser tests into files by journey (no new behaviour)

Status: draft (2026-10-16)

Builds on: **test-pyramid** (the `cuj/` folder is the CUJ layer, `config/test_runner.py`),
**maintenance-pass** (the same kind of split for `test_views.py`), and everything on `main`
(`2c75b89`).

## Words used in this plan

- **CUJ test** (critical user journey): a test that drives a real Chromium browser through a whole
  task, with Playwright. All of them extend `BrowserTestCase` (`todos/tests/cuj/browser.py`).
- **Test id**: the full name of one test, `<module>.<Class>.<method>`, for example
  `todos.tests.cuj.test_journeys.PlanAndFinishTests.test_plan_and_finish`.
- **Discovery**: how the test runner finds tests: every file whose name starts with `test` in a
  package (a folder with `__init__.py`).
- **Behaviour-preserving**: every test checks exactly what it checked before. Only the file it
  lives in, and its imports, change.

## What is wrong today

Facts, checked on `main` (`2c75b89`):

1. `todos/tests/cuj/test_journeys.py` is 1203 lines. It holds **21** test classes with **25**
   tests, plus 27 module-level helpers and constants (functions and assignments). (The CUJ folder has **22** classes and
   **30** tests in all: the 22nd class is `AuthPagesTests` in `test_auth_pages.py`, 5 tests.)
2. `todos/tests/cuj/test_auth_pages.py` imports eight names **from a test module**:
   `from todos.tests.cuj.test_journeys import AA_CONTRAST, DESKTOP, LOGIN_PAGE, PASSWORD, PHONE,
   SIGNUP_PAGE, contrast, make_user_with_inbox`. A test file that other test files import from is
   easy to break by accident (rename a constant, and a different file fails).
3. A person who wants "the sharing journey" has to search one long file.

## Goal

The same 30 browser tests, in six smaller files named by journey, plus one helper module that
holds what more than one file uses. Nothing a test checks changes. The proof is that the sorted
list of `<Class>.<method>` names is the same before and after, every class's source is
byte-for-byte the same, and `make check` passes.

## Decisions

### 1. Six new test files, by journey

| New file | Classes (tests) | Journey |
|---|---|---|
| `todos/tests/cuj/test_todo_basics.py` | `PlanAndFinishTests` (1), `KeepThePlaceTests` (1), `FixATypoTests` (1), `ClearCompletedJourneyTests` (1), `DeleteAndUndoTests` (1) | Add, edit, done, undo, delete, undo-delete, clear completed |
| `todos/tests/cuj/test_steps_and_repeat.py` | `BreakATodoIntoStepsTests` (1), `KeyboardStepsTests` (1), `KeepAChangedCopyTests` (1) | Steps inside a to-do, and a repeating to-do |
| `todos/tests/cuj/test_lists_and_people.py` | `SeparateListsTests` (1), `TwoPeopleTests` (1), `ShareAListTests` (1) | Several lists, two accounts, sharing |
| `todos/tests/cuj/test_find_and_order.py` | `SearchJourneyTests` (1), `ReorderJourneyTests` (2), `MoveSlotTests` (1) | Search, drag and drop, Move buttons |
| `todos/tests/cuj/test_landing_page.py` | `LandingTests` (3) | The visitor's landing page |
| `todos/tests/cuj/test_look_and_feel.py` | `ColorSchemeTests` (1), `RowLayoutTests` (1), `OneProductTests` (1), `TouchTests` (2), `QuietDeleteTests` (1), `ReducedMotionTests` (1) | Colors, layout, touch sizes, focus, reduced motion |
| `todos/tests/cuj/test_auth_pages.py` (stays) | `AuthPagesTests` (5) | Login and sign-up pages |

Total: 5 + 3 + 3 + 4 + 3 + 7 + 5 = **30** tests in **22** classes. `test_journeys.py` is deleted.

Why these names: each says the journey, so a person finds a test from what they did in the app.
`test_landing_page.py` says what the journey is about, like the other names (an integration file
`todos/tests/integration/test_landing.py` exists too; same names in different folders work, so
this is only for easier search).

Inside each new file the classes keep the order they had in `test_journeys.py`.

### 2. Shared helpers go in a new module `todos/tests/cuj/helpers.py`

The name does not start with `test`, so discovery never runs it as tests, and it holds no test
class. It is next to `browser.py` (which stays only `BrowserTestCase` and `TIMEOUT_MS`), and
matches the other helper modules (`todos/tests/helpers.py`, `accounts/tests/helpers.py`).

A name goes to `helpers.py` only when **two or more files** use it. Each name, where it is used
today, and where it goes:

| Name (line in `test_journeys.py`) | Used by | Goes to |
|---|---|---|
| `DONE` (11) | PlanAndFinish, KeepThePlace, FixATypo, ClearCompleted, BreakATodo, KeepAChangedCopy, ColorScheme | `helpers.py` |
| `RGB` (12), `luminance` (21), `contrast` (38) | ColorScheme, Landing, `test_auth_pages.py` (`contrast`) | `helpers.py` |
| `AA_CONTRAST` (15), `UI_CONTRAST` (18), with their comments | ColorScheme, Landing, `test_auth_pages.py` (`AA_CONTRAST`) | `helpers.py` |
| `make_user_with_inbox` (44) | 19 classes and `test_auth_pages.py` | `helpers.py` |
| `LOGIN_PAGE` (51), `SIGNUP_PAGE` (52) | TwoPeople, Landing, ReducedMotion, `test_auth_pages.py` | `helpers.py` |
| `PASSWORD` (55), with its comment | TwoPeople, `test_auth_pages.py` | `helpers.py` |
| The comment at lines 57-60 ("A click on a link or a form button only *starts* loading ...") | A rule for every CUJ test (postmortem 2026-10-09, PR #19) | Top of `helpers.py`, word for word |
| `DESKTOP` (782), `PHONE` (783) | Landing, `test_auth_pages.py` | `helpers.py` |
| `HEADLINE` (786) | Landing | `test_landing_page.py` |
| `LONG_WORD` (356), `LINE_THROUGH_ON_SELF_OR_ANCESTOR` (360), with comments | FixATypo | `test_todo_basics.py` |
| `overlaps` (669), `inside` (679), `LONG_TITLE` (687), `LONG_URL` (691) | RowLayout | `test_look_and_feel.py` |
| `TOUCH_HEIGHT` (917) | RowLayout, Touch (same file) | `test_look_and_feel.py`, see below |
| `TOUCH_GAP` (920), `DISPLAY` (922), `gaps` (925) | Touch | `test_look_and_feel.py` |
| `BUTTON_LOOK` (873), `SECONDARY_LOOK` (882) | OneProduct | `test_look_and_feel.py` |
| `hex_to_rgb` (1012) | QuietDelete | `test_look_and_feel.py` |
| `MOVING` (1046) | ReducedMotion | `test_look_and_feel.py` |

Every helper and constant moves with its code, its docstring and the comment above it unchanged.
In a test file, each constant or helper keeps the place it has today relative to the classes,
that is just above the class it stood above in `test_journeys.py`. In particular lines 915-922
(the WCAG comment, `TOUCH_HEIGHT`, `TOUCH_GAP`, the `DISPLAY` comment and `DISPLAY`) stay **one
block** above `TouchTests`, as today, although `RowLayoutTests` (earlier in the file) also uses
`TOUCH_HEIGHT`; that works because the name is read when the test runs, not when the class is
defined.

`helpers.py` gets a short module docstring: "Shared helpers for the CUJ tests. Not a test file:
the name does not start with `test`, so the runner never runs it." Then the comment block of
lines 57-60.

### 3. Imports

Each new file imports only what it uses; Ruff (`F401` unused import, `F821` undefined name, in
`make lint` and the commit checks) catches a missing or extra one. The imports each file needs,
from the table above and from the code:

| File | Imports |
|---|---|
| `helpers.py` | `re`; `make_user` from `accounts.tests.helpers`; `TodoList` from `todos.models` |
| `test_todo_basics.py` | `expect`; `BrowserTestCase`; `DONE`, `make_user_with_inbox` |
| `test_steps_and_repeat.py` | `timedelta`; `timezone`; `expect`; `BrowserTestCase`; `DONE`, `make_user_with_inbox` |
| `test_lists_and_people.py` | `expect`; `TEST_PASSWORD`, `make_user`; `TodoList`; `BrowserTestCase`; `LOGIN_PAGE`, `PASSWORD`, `make_user_with_inbox` |
| `test_find_and_order.py` | `re`; `expect`; `BrowserTestCase`; `make_user_with_inbox` |
| `test_landing_page.py` | `expect`; `BrowserTestCase`; `AA_CONTRAST`, `DESKTOP`, `PHONE`, `SIGNUP_PAGE`, `UI_CONTRAST`, `contrast`, `luminance` |
| `test_look_and_feel.py` | `timedelta`; `timezone`; `expect`; `make_user`; `TodoList`; `BrowserTestCase`; `AA_CONTRAST`, `DONE`, `LOGIN_PAGE`, `SIGNUP_PAGE`, `UI_CONTRAST`, `contrast`, `luminance`, `make_user_with_inbox` |
| `test_auth_pages.py` | The same names as today, now `from todos.tests.cuj.helpers import ...` |

(The table is the planner's reading; the implementer trusts Ruff over it.)

`test_auth_pages.py` keeps its own `UI_CONTRAST = 3.0` and its comment: removing it would be a
change to that file beyond the import line. See open question 2.

### 4. The rest stays

- `browser.py` does not change.
- `config/test_runner.py` and its tests do not change, except one docstring example (decision 5).
- No class is renamed; no test method is renamed, reordered inside its class, or edited.

### 5. Names of `test_journeys.py` elsewhere

`git grep -n test_journeys -- ':!docs/plans'` on `main` finds:

| Place | What it says | Change |
|---|---|---|
| `todos/tests/cuj/test_auth_pages.py:9` | The import | Decision 3. |
| `config/test_runner.py:34` (docstring of `layer_of`) | `"setUpClass (todos.tests.cuj.test_journeys.SomeTests)"`, an example id | `test_todo_basics` instead of `test_journeys`, so the example names a real file. |
| `config/tests/unit/test_test_runner.py:34,38` | `layer_of("todos.tests.cuj.test_journeys.A.test_a")` | **No change.** The test reads a string; the file does not have to exist. Changing it would change a test for no reason. |
| `docs/process/test-plan.md:69` | "`DeleteAndUndoTests.test_delete_and_undo` in `todos/tests/cuj/test_journeys.py`" | Becomes `todos/tests/cuj/test_todo_basics.py`. This page describes how the tests are laid out. |
| `docs/bug-reports/BUG-001-...md:92` | "The browser journey `test_delete_and_undo` in `todos/tests/cuj/test_journeys.py`" | **No change**: a bug report is a record of that day (see open question 3). |
| `docs/postmortems/2026-10-09-merged-with-red-ci.md:75` | "a comment at the top of `todos/tests/cuj/test_journeys.py`" | **No change**: same reason. The comment now lives at the top of `helpers.py`. |
| `docs/plans/*.md` (19 plans) | Old plans name the file | **No change**: plans are history (`AGENTS.md`). |

`AGENTS.md` never names `test_journeys.py`. Its row for `todos/tests/cuj/` becomes:

> | `todos/tests/cuj/` | CUJ tests (critical user journeys): a real Chromium browser, driven by Playwright. One file per journey (`test_todo_basics.py`, `test_steps_and_repeat.py`, `test_lists_and_people.py`, `test_find_and_order.py`, `test_landing_page.py`, `test_look_and_feel.py`, `test_auth_pages.py`); `browser.py` holds `BrowserTestCase`, `helpers.py` what several files share (`make_user_with_inbox`, `contrast`, `DONE`, the page addresses). A helper module's name never starts with `test`. |

`README.md` (section "Tests") and `docs/design/design-doc.md` name only the folder and the count
(30), which stay the same: no change.

## Security

Nothing changes in the app. No test of who may see what is touched; `TwoPeopleTests` and
`ShareAListTests` move whole. The tests still run against `StaticLiveServerTestCase`'s own test
database, never `db.sqlite3`, and on a free port, never 8000.

## Data and migrations

None. Going back: revert the commit.

## Working next to

Wave A, built in parallel with **readme-to-runbooks**, **privacy-small-fixes** and
**admin-log-without-names**. Merge order: **split-browser-tests (this) → readme-to-runbooks →
privacy-small-fixes → admin-log-without-names → delete-account**.

- **delete-account** merges after this plan, so its new CUJ test goes into the new layout, in a
  new file `todos/tests/cuj/test_account.py` (decided by the orchestrator, 2026-10-16). It imports shared helpers from
  `todos.tests.cuj.helpers`, never from a test file. If delete-account is built before this merges,
  it rebases and moves its class; it must not add to `test_journeys.py` after this merges.
- **privacy-small-fixes** changes how messages are stored (session instead of cookie). The CUJ
  tests that read a message (`ShareAListTests` "Shared with bob.", `DeleteAndUndoTests` "Deleted")
  must still pass after both merge; since this plan only moves them, a failure there belongs to
  that plan.
- Shared files: `AGENTS.md` (only the `todos/tests/cuj/` row here; readme-to-runbooks changes the
  plist row), `CHANGELOG.md` (one line each; the second PR to merge resolves the conflict by
  keeping both lines), `docs/process/test-plan.md` (only this plan).
- No other plan of this round touches `todos/tests/cuj/` files, except delete-account.

## Not part of this task

- Any change to what a test checks, a test's name, or `browser.py`.
- Merging `test_auth_pages.py`'s own `UI_CONTRAST` and `AUTH_COLORS` into the helpers (open
  question 2).
- Making the CUJ tests faster (for example `--parallel`). Each class still starts its own live
  server, as today, so the run time stays about the same.
- Editing old plans, the bug report or the postmortem.

## Changes to files

| File | Change |
|---|---|
| `todos/tests/cuj/helpers.py` (new) | The shared names of decision 2, word for word, with a module docstring. |
| `todos/tests/cuj/test_todo_basics.py`, `test_steps_and_repeat.py`, `test_lists_and_people.py`, `test_find_and_order.py`, `test_landing_page.py`, `test_look_and_feel.py` (new) | The classes of decision 1 and their own helpers, word for word; a one-line module docstring each (like `test_auth_pages.py`: "The ... journeys in a real browser: ..."). |
| `todos/tests/cuj/test_journeys.py` | Deleted (`git rm`). |
| `todos/tests/cuj/test_auth_pages.py` | Only the import line: `from todos.tests.cuj.helpers import ...`. |
| `config/test_runner.py` | The docstring example (decision 5). |
| `AGENTS.md` | The `todos/tests/cuj/` row (decision 5). |
| `docs/process/test-plan.md` | Line 69: the new file name. |
| `CHANGELOG.md` | Under `## [Unreleased]` (create it above `## [0.5.1]` if it is not there yet), `### Under the hood`: "The browser tests are split into one file per journey; the same 30 tests (PR #N)." |
| `docs/plans/README.md` | One row for this plan when it is built (plan, what it built, PR, date). |
| `docs/plans/split-browser-tests.md` | Status line on the last commit. |

## Steps

Each step is a commit; `make check` passes after each one.

1. **Baseline.** In the worktree, before any change, save the test ids (this runs no test and
   opens no browser):

   ```bash
   DJANGO_SETTINGS_MODULE=config.settings uv run python -c "
   import django; django.setup()
   from django.test.runner import DiscoverRunner
   from django.test.utils import iter_test_cases
   suite = DiscoverRunner(verbosity=0).build_suite(['todos/tests/cuj'])
   print('\n'.join(sorted(t.id() for t in iter_test_cases(suite))))" > "$SCRATCH/cuj-before.txt"
   wc -l "$SCRATCH/cuj-before.txt"   # 30
   ```

   (`$SCRATCH` is the session's scratchpad folder; the files are not committed.) Also save the
   source of every class and module-level name, with the AST script of step 4, to
   `$SCRATCH/cuj-before.json`. Run `make cuj` once and note `CUJ 30 passed`.
2. **Add `helpers.py`** with the shared names, and in the **same commit** delete those names from
   `test_journeys.py` and import them there from `helpers.py` (two definitions of one name would
   be Ruff's `F811`, and the AST check would see a duplicate). Switch `test_auth_pages.py`'s
   import to `helpers.py`. `make check`.
3. **Move the classes**, one new file at a time, in the order of decision 1. After each file,
   delete the moved classes and helpers from `test_journeys.py` and import from `helpers.py` in
   `test_journeys.py` what the remaining classes still need. When the last class is moved,
   `git rm todos/tests/cuj/test_journeys.py`. Move code by cut and paste only; no reformatting
   (`ruff format` must leave the moved lines as they were; if it changes one, look at why).
   Before the PR, run `uv run ruff check todos/tests/cuj` **without** `--fix` (the commit hook
   runs with fixes, and would quietly remove an unused import instead of showing it), and put
   its output in the PR.
4. **Prove nothing was lost** (after the last move):

   a. Same ids, ignoring the module:

   ```bash
   # the same command as step 1, into cuj-after.txt, then:
   wc -l "$SCRATCH/cuj-after.txt"   # 30
   diff <(sed -E 's/^todos\.tests\.cuj\.[a-z_]+\.//' "$SCRATCH/cuj-before.txt" | sort) \
        <(sed -E 's/^todos\.tests\.cuj\.[a-z_]+\.//' "$SCRATCH/cuj-after.txt" | sort)
   # no output
   ```

   b. Each class is in the file decision 1 says: `grep -c` the module names in `cuj-after.txt`
   gives 5, 3, 3, 4, 3, 7 and 5.

   c. Same code: a short script (in the scratchpad, not committed) uses the **same file set**
   before and after. Before: `test_journeys.py`, `test_auth_pages.py` and `browser.py` from
   `main` (`git show origin/main:<path>`). After: every `.py` file in `todos/tests/cuj/`. For
   each file it parses the module with `ast` and collects one `(name, source)` pair per
   top-level class, function and assignment (`ast.get_source_segment(...)`), skipping imports
   and the module docstring. The two collections are compared as **multisets** (a
   `collections.Counter`), so a name defined twice counts twice. They must be equal. The one
   duplicate name allowed is the known one: `UI_CONTRAST = 3.0` in both the shared module and
   `test_auth_pages.py`, as on `main` (open question 2); any other name found in two files fails
   the check.

   e. Same comments: `ast` source segments miss comments that stand between top-level
   definitions (for example the comment above `LONG_WORD`, or the block at lines 57-60). The
   script also reads the same before and after file sets with the `tokenize` module and keeps
   every `COMMENT` token's text. The two sorted lists must be equal.

   d. `git grep -n test_journeys -- ':!docs/plans' ':!docs/bug-reports' ':!docs/postmortems'
   ':!config/tests'` finds nothing.
5. **Run everything**: `make cuj` (`CUJ 30 passed`), then once more in a shuffled order to show
   that no test depended on the order of the old file:
   `uv run python manage.py test todos/tests/cuj --shuffle`, then `make check`
   (CUJ 30, Integration and Unit the same as on `main`).
6. **Docs**: `AGENTS.md` row, `config/test_runner.py` docstring, `docs/process/test-plan.md`,
   `CHANGELOG.md`, `docs/plans/README.md`. Last commit: Status `**done** (<date in Tokyo>)`.

## Tests

No new test and no changed test: this plan only moves tests. What proves it:

| Check | What it proves | The break that fails it |
|---|---|---|
| Step 4a, the id diff | The same 30 `<Class>.<method>` names exist after the split. | A class left out, a method lost in a paste, a class that is not a `BrowserTestCase` any more (the runner refuses it). |
| Step 4b, per-file counts | Each class is in the file this plan names. | A class in the wrong file. |
| Step 4c, the AST compare | Every class, helper and constant has the same source as before; none is defined twice (except the known `UI_CONTRAST`). | An edited assertion, a changed constant, a helper copied into two files. |
| Step 4e, the comment compare | Every comment is still there, word for word. | A comment lost between two definitions while moving. |
| Ruff in `make check` | No missing and no unused import. | A file that forgot `DONE`, or imports one it does not use. |
| `make cuj`, and once with `--shuffle` | All 30 still pass, in any order. | A test that only passed because another test in the old file ran before it. |
| `make check` | The other layers are untouched (`config/tests/unit/test_test_runner.py` still passes). | |

## Risks

- **Discovery pattern.** Django's runner finds files matching `test*.py`. `helpers.py` does not
  match, so it never runs as tests; a helper module named `test_helpers.py` **would** be
  collected (and would be empty, but confusing). The six new names all start with `test_`; check
  with step 4b that each is found.
- **Module-level setup.** `test_journeys.py` has no `setUpModule`, no module-level fixture and no
  code that runs at import except constants and `re.compile`. `BrowserTestCase.setUpClass` starts
  a browser per class, as before. The number of classes is the same (22), so the number of
  browser starts is the same.
- **Importing a test module.** After the split, no file imports from a `test_*.py` file. Importing
  test classes into another test module would make the runner find them twice; the AST check (4c)
  and the id count (30, not more) catch that.
- **Order.** unittest runs modules in name order, so the order of the tests changes. Each test has
  its own browser context and a fresh database (`StaticLiveServerTestCase` is a
  `TransactionTestCase`, which empties the tables after each test), so order should not matter;
  step 5's `--shuffle` run checks it.
- **`test_list_page_size.py`, `test_landing.py`, and the other integration tests** are in another
  layer and are not touched.
- **Formatting.** If `ruff format` reflows a moved line (for example an import line that is now
  longer), only the import lines may change; class bodies must stay byte-identical (4c).

## Open questions

1. **The file names and the grouping** (decision 1). Recommended: as written; six files of
   roughly 100 to 480 lines, named by what the person does. `test_look_and_feel.py` is the
   largest (about 480 lines, mostly `ColorSchemeTests` and `TouchTests`).
2. **`test_auth_pages.py` has its own `UI_CONTRAST = 3.0`**, the same value as the shared one.
   Recommended: leave it in this PR (a pure move), and remove it in a later tidy-up.
3. **Old records that name `test_journeys.py`** (BUG-001, the 2026-10-09 postmortem). Recommended:
   leave them; they describe that day, like the plans. Only `docs/process/test-plan.md`, which
   describes the layout, changes.

## Review

The plan review (2026-10-16) said APPROVE WITH CHANGES. What changed:

- Step 4c compares the **same file set** before and after (`test_journeys.py`,
  `test_auth_pages.py` and `browser.py` on `main`; every `.py` in `cuj/` after), as multisets of
  `(name, source)`, skipping imports and module docstrings, with exactly one allowed duplicate
  (`UI_CONTRAST` in `test_auth_pages.py`). Before, the "after" side had more files than the
  "before" side, so `test_auth_pages.py`'s own names would have looked new.
- New step 4e: the comments are compared with `tokenize`, because `ast` source segments do not
  hold comments between definitions.
- `TOUCH_HEIGHT` stays in its block above `TouchTests` (lines 915-922), as today; the wording
  "just above the first class that uses it" was wrong for it.
- Counts corrected: 27 module-level helpers and constants; `test_auth_pages.py` imports eight
  names.
- Step 2 deletes the shared copies from `test_journeys.py` in the same commit (no `F811`); the PR
  shows `uv run ruff check` without `--fix`.
- delete-account's CUJ file is named: `todos/tests/cuj/test_account.py`.
- The reason for `test_landing_page.py` is softer: same file names in different folders work.

## Decided by the person

(Filled in after the person answers.)
