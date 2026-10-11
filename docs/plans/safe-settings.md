# Plan: the app refuses to start with unsafe production settings

Status: **done** (2026-10-11). Approved 2026-10-11. Built as planned; `config/env.py` also has a small helper `is_strong(key)` for the three limits. After code review: three more integration tests (`DJANGO_DEBUG=0` stops, `true` with no key starts, a weak key stops) and the `DJANGO_DEBUG` message says "(length N)".

Builds on: **foundation** and **accounts** (the settings in `config/settings.py` that read
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG` and `DJANGO_ALLOWED_HOSTS` from environment variables), and the
**test pyramid** (`config/test_runner.py`: the folder of a test is its layer).

## Words used in this plan

- **Environment variable**: a name and a value that the computer gives a program when it starts,
  outside the code. A hosting service lets you type them on a settings page.
- **Secret key** (`SECRET_KEY`): a long random text Django uses to sign things, for example the
  login cookie. Whoever knows it can make a cookie that logs them in as any user.
- **Debug mode** (`DEBUG`): when it is on, an error page shows the code, the settings and the
  request. Good on a laptop, dangerous on the internet.
- **`ImproperlyConfigured`**: Django's own error for "the settings are wrong". When the settings
  raise it, the program stops before it answers any request, and prints the message.

## What is wrong today

Facts, checked on `main` (commit `0e9379c`):

- In `config/settings.py`, the line `SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", ...)`: `SECRET_KEY` falls back to `"django-insecure-only-for-your-laptop"`
  when `DJANGO_SECRET_KEY` is not set. This text is in the code on GitHub, so everyone knows it.
- The line `DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"`. Not set means debug **on**.
  Any other value, also `"true"`, `"false"`, `"0"` or a typo, means debug **off**.
- With `DJANGO_DEBUG=False` and no `DJANGO_SECRET_KEY`, the app starts and serves pages with the
  public key. `manage.py check` says "no issues". Only `manage.py check --deploy` warns
  (`security.W009`), and the build command in `README.md` never runs it. (Tried on 2026-10-11:
  `check` gives exit code 0, `check --deploy --fail-level WARNING` fails with W009.)

So a person who forgets one variable on the host gets a site where anyone can log in as anyone,
and nothing stops them.

## Goal

When debug is off, the app **stops at once** if the secret key is missing or weak, with a short
message in plain English that says which variable to set and how to make a good value. On the
laptop nothing changes: `make run`, `make test` and CI work with no environment variables, as
today.

## Decisions

### 1. The rules move into a small file of pure functions: `config/env.py`

A **pure function** gets everything it needs as arguments and changes nothing outside itself. So a
unit test can call it with any made-up environment, without loading Django's settings again.

```python
# config/env.py
"""Read the settings that come from environment variables, and refuse unsafe ones.

Pure functions: they get the environment as a dict, so tests can pass any values.
"""

from django.core.exceptions import ImproperlyConfigured

LAPTOP_SECRET_KEY = "django-insecure-only-for-your-laptop"

# The same limits as Django's own deploy check (security.W009). Django has them
# as SECRET_KEY_MIN_LENGTH, SECRET_KEY_MIN_UNIQUE_CHARACTERS and
# SECRET_KEY_INSECURE_PREFIX in django.core.checks.security.base. We keep our
# own copies so this file reads on its own; a unit test checks they are equal.
MIN_LENGTH = 50
MIN_UNIQUE_CHARACTERS = 5
INSECURE_PREFIX = "django-insecure-"

MAKE_A_KEY = 'uv run python -c "import secrets; print(secrets.token_urlsafe(50))"'


def read_debug(env):
    """True or False from DJANGO_DEBUG. Not set means True (the laptop)."""


def read_secret_key(env, debug):
    """The secret key. With debug off, a missing or weak key stops the app."""
```

`config/settings.py` then only says:

```python
from config.env import read_debug, read_secret_key

DEBUG = read_debug(os.environ)
SECRET_KEY = read_secret_key(os.environ, DEBUG)
```

`DEBUG` is read first, because the key rule depends on it. The `if not DEBUG:` block (HTTPS
settings) and `ALLOWED_HOSTS` do not change.

### 2. `read_debug(env)`: only `True` or `False`, and anything else stops the app

| `DJANGO_DEBUG` | Result |
|---|---|
| not set | `True` (the laptop, as today) |
| `True`, `true`, `TRUE` | `True` |
| `False`, `false`, `FALSE` | `False` |
| anything else: `""`, `0`, `1`, `no`, `Flase`, ... | `ImproperlyConfigured`: `DJANGO_DEBUG must be True or False. It is set to something else (length N).` |

For both words, spaces and line breaks at the ends are removed first (`.strip()`), then upper and
lower case are treated the same (`.casefold()`). So ` False` and `false` followed by a line break
both mean `False`.

Reasons:

- **Upper or lower case both work**, because people type `false` and expect it to mean false.
  Today `false` already means off, so nothing gets less safe.
- **An unknown value stops the app** instead of guessing. A guess could be wrong in the dangerous
  direction (for example if a later change read `1` as on). Today an unknown value means off, which
  is safe, but silent; after this change it is safe **and** loud.
- **`0`, `1`, `yes`, `no` are refused**, not accepted. Two words are easier to explain to a new
  programmer than a table of synonyms. The message says the two allowed words.
- **The empty value `""` is refused**, not treated as "not set". On a host, an empty variable is
  almost always a mistake, and "not set" means debug **on**, so treating it as "not set" would be
  the dangerous guess.
- **The message never prints any part of the wrong value**, only its length. On a host settings
  page, two fields can be swapped by mistake, so the value of `DJANGO_DEBUG` could be the secret
  key, and the message ends up in the build log.

### 3. `read_secret_key(env, debug)`: a strong key is required when debug is off

- **Debug on:** `DJANGO_SECRET_KEY` if it is set and not empty, else `LAPTOP_SECRET_KEY`. Exactly
  as today. A weak key is allowed on the laptop.
- **Debug off:** the key must be set and pass the same test as Django's deploy check: at least 50
  characters, at least 5 different characters, and not starting with `django-insecure-` (so the
  laptop key is refused too, because it starts with that). Spaces at the ends are not removed: the
  key is used exactly as given, and a key of only spaces fails the "5 different characters" rule.
- **Two messages**, both say what to do:
  - Missing or empty: `DJANGO_SECRET_KEY is not set. DJANGO_DEBUG is False, so the site needs its
    own secret key. Make one with: <MAKE_A_KEY>, then set it as the environment variable
    DJANGO_SECRET_KEY.`
  - Weak: `DJANGO_SECRET_KEY is too weak: it needs at least 50 characters, at least 5 different
    characters, and must not start with "django-insecure-". Make one with: <MAKE_A_KEY>.`
- **The message never contains the key**, not even part of it. Error messages end up in build
  logs, which other people may see.

`secrets.token_urlsafe(50)` gives about 67 characters, so the README command always passes.

### 4. `DEBUG` still defaults to `True`

The person runs the app on the Mac with `make run` and sets no environment variables. If `DEBUG`
defaulted to `False`, `make run` would need a secret key, and `SECURE_SSL_REDIRECT` would send
every page to `https://127.0.0.1:8000`, which `runserver` cannot answer. That would break the
laptop, which is where the app really runs today.

The risk that stays: on a host, forgetting `DJANGO_DEBUG` means debug **on** (error pages show the
code and settings, and the app uses the public laptop key, since a weak key is allowed with debug
on). This plan does not close that hole by guessing. It makes the README say clearly that
`DJANGO_DEBUG=False` is required on a host, and it adds the deploy check to the build (decision
5), which fails on debug on (`security.W018`). See open question 1 for a stricter option.

### 5. The README build command also runs `check --deploy --fail-level WARNING`

Add `uv run --no-dev python manage.py check --deploy --fail-level WARNING` to the build command,
**first**, before `collectstatic` and `migrate`. Reasons:

- It catches what the start-up rule does not: debug left on (W018), a missing HTTPS setting, and
  any warning a future Django version adds. A build that fails is far better than a site that runs
  unsafely.
- It costs one second and needs no new package.
- With our settings and a good key it passes today (tried on 2026-10-11: "System check identified
  no issues (1 silenced)"; the one silenced warning is `security.W021`, HSTS preload, switched off
  on purpose in `settings.py`).
- It runs first, so a bad setting stops the build before `migrate` changes the database.

The new build command in `README.md`, exactly:

```bash
pip install uv && uv sync --locked --no-dev && uv run --no-dev python manage.py check --deploy --fail-level WARNING && uv run --no-dev python manage.py collectstatic --no-input && uv run --no-dev python manage.py migrate
```

### 6. The variables must be set at build time too

`collectstatic`, `migrate` and `check` all load `config/settings.py`. So on the host, the three
variables must be set **for the build as well as for the start**. On most hosts (for example
Render) the variables from the settings page are used for both. The README says this in one
sentence, and says what the error looks like if the key is missing at build time. It also says:
**read the last line of the error.** The error is a traceback (the long list of files Python
prints when it stops), and our plain-English message is on its last line.

### 7. Tests and CI need nothing new

- CI (`.github/workflows/check.yml`) sets no `DJANGO_*` variable, so `DEBUG` is `True` and the
  laptop key is used. Both jobs (`pre-commit` with `manage.py check`, and `manage.py test`) work as
  today.
- Django's test runner turns `DEBUG` off **while the tests run**, but only after the settings are
  loaded, so our rule (which runs while loading) sees `True` and does not ask for a key.
- A person who runs the tests with `DJANGO_DEBUG=False` set in their shell gets the clear error.
  That is correct: those are production settings.

## Security

- **What it protects:** the secret key signs the login (session) cookie, the CSRF token and
  password-reset links. With the public key, anyone can sign a session cookie for any user, so
  this is the most important setting on a live site.
- **Never print the key.** Neither message contains any part of `DJANGO_SECRET_KEY`. A test checks
  this (`test_weak_key_message_does_not_show_the_key`).
- **No new way to turn debug on.** Only `True` (any case) turns it on, or the variable being
  absent. An unknown value stops the app. A test checks that `1`, `yes` and `""` never give `True`.
- **No secret in the code.** The laptop key stays in the code on purpose (it is only used with
  debug on, on a laptop), and it is now refused when debug is off.
- **Same limits as Django.** We copy Django's three limits instead of inventing our own, so our
  rule and `check --deploy` never disagree.
- **Not changed:** the HTTPS settings, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`.

## Data and migrations

No model change, no migration. No data changes. The tests never open `db.sqlite3`: `manage.py
check` does not open the database, and the unit tests have none.

## Working next to

`docs/plans/docs-fixes.md` also changes `AGENTS.md` (the `config/settings.py` row gets a
`TIME_ZONE` sentence, a new CI row, the "today" rule) and `README.md` ("How it is put together").
**Merge order: docs-fixes first** (it is docs only). Then this branch rebases on it, keeps the
`TIME_ZONE` sentence in the `config/settings.py` row, adds its own rows next to the new ones, and
in its **last commit** sets the Status line of this plan to `**done** (<Tokyo date>)`, as the
docs-fixes plan asks of every plan.

## Not part of this task

- Requiring `DJANGO_DEBUG` to be set explicitly (open question 1).
- Checking `DJANGO_ALLOWED_HOSTS` (Django already answers `400 Bad Request` for an unknown host).
- `SECRET_KEY_FALLBACKS` (changing the key without logging everybody out).
- Moving the database off SQLite, or any other hosting change.
- A `.env` file or a package like `django-environ`: four lines of plain Python are enough.

## Changes to files

| File | Change |
|---|---|
| `config/env.py` (new) | `read_debug(env)`, `read_secret_key(env, debug)`, the constants and the two messages. Imports only `ImproperlyConfigured`, no settings. |
| `config/settings.py` | Replace the line `SECRET_KEY = os.environ.get(...)` and the line `DEBUG = os.environ.get(...)` with the two calls (in the order `DEBUG`, then `SECRET_KEY`). Keep the comments, and add one: "With DJANGO_DEBUG=False, a missing or weak DJANGO_SECRET_KEY stops the app (see config/env.py)." |
| `config/tests/unit/test_env.py` (new) | Unit tests for the two functions (see "Tests"). |
| `config/tests/integration/__init__.py`, `config/tests/integration/test_settings_startup.py` (new) | Start `manage.py check` in a new process with chosen variables (see "Tests"). |
| `README.md` | "Put it on the internet": the table says `DJANGO_DEBUG` must be exactly `True` or `False` (any case), and that with `False` the app stops without a strong key; one sentence that the variables are needed at build time too; the exact build command from decision 5; one short line "If the build stops, read the last line of the error: it says which variable to set". "How it is put together": add `config/env.py`. Update the test counts in step 8. |
| `AGENTS.md` | `config/settings.py` row: "`DEBUG` and `SECRET_KEY` come from `config/env.py`". New row `config/env.py`: what the two functions accept and refuse, and that the message never shows the key. `config/tests/unit/` row: "the tests for the test runner and for `config/env.py`". New row `config/tests/integration/`: "starts `manage.py check` in a new process (a subprocess, not Django's test client) to test the start-up rules". |

## Steps

1. **Tests first.** Write `config/tests/unit/test_env.py` and
   `config/tests/integration/test_settings_startup.py`. Run `make unit` and `make integration`:
   the unit tests fail (no `config/env.py` yet), and
   `test_debug_off_without_key_stops` fails (today `check` exits with 0). Show the person both
   failures.
2. Write `config/env.py`.
3. Change `config/settings.py` to use it.
4. Run `make test`: everything passes, including the old tests (they set no variable).
5. By hand, in the worktree (never port 8000, never `db.sqlite3`):
   `env -u DJANGO_SECRET_KEY DJANGO_DEBUG=False uv run python manage.py check` stops with the
   message; `make run`-style start with no variables still works (`uv run python manage.py check`
   gives no issues).
6. Update `README.md` and `AGENTS.md` as in "Changes to files".
7. `make check`, then commit.

## Tests

### Unit: `config/tests/unit/test_env.py` (`SimpleTestCase`, no database)

Each test passes a plain dict as `env`.

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_debug_not_set_is_true` | `read_debug({})` is `True`. | Changing the default to `False` (breaks `make run`). |
| `test_debug_true_any_case` | `True`, `true`, `TRUE`, ` true ` give `True`. | Comparing with `== "True"` only. |
| `test_debug_false_any_case` | `False`, `false`, `FALSE`, ` False`, `"false\n"` give `False`. | Comparing without `.strip()` or `.casefold()`. |
| `test_debug_unknown_value_stops` | `""`, `0`, `1`, `yes`, `no`, `Flase` each raise `ImproperlyConfigured` (subtests), and the message says `True or False`. | Treating an unknown value as off (today's behavior) or as on. |
| `test_debug_message_has_no_part_of_the_value` | A fixed key-like value of 50 characters gives a message that contains no 4-character piece of the value, but does contain its length. | Printing the value, or its first characters. |
| `test_debug_on_uses_laptop_key` | `read_secret_key({}, debug=True)` is `LAPTOP_SECRET_KEY`. | Requiring a key on the laptop (breaks `make run`, CI). |
| `test_debug_on_uses_given_key` | With debug on and a key set, that key is used, even a short one. | Ignoring the variable. |
| `test_debug_off_missing_key_stops` | With debug off, no key and an empty key both raise, and the message names `DJANGO_SECRET_KEY` and the `secrets.token_urlsafe(50)` command. | Falling back to the laptop key (today's bug). |
| `test_debug_off_laptop_key_stops` | With debug off, `DJANGO_SECRET_KEY=LAPTOP_SECRET_KEY` raises. | Only checking "is it set". |
| `test_debug_off_weak_keys_stop` | 49 characters; 60 characters with only 4 different ones; 60 characters starting with `django-insecure-`; 60 spaces. Each raises. | Leaving out one of Django's three limits. |
| `test_debug_off_strong_key_is_used` | A key from `secrets.token_urlsafe(50)` is returned unchanged; so is a 50-character key with 5 different characters (the exact edge). | An off-by-one (`>` instead of `>=`), or stripping the key. |
| `test_limits_match_django` | `MIN_LENGTH`, `MIN_UNIQUE_CHARACTERS` and `INSECURE_PREFIX` equal Django's `SECRET_KEY_MIN_LENGTH`, `SECRET_KEY_MIN_UNIQUE_CHARACTERS` and `SECRET_KEY_INSECURE_PREFIX` from `django.core.checks.security.base`. | A future Django changing its limits, so our rule and `check --deploy` disagree. |
| `test_weak_key_message_does_not_show_the_key` | For a weak key `"x" * 10 + "SECRETPART"`, the message does not contain `SECRETPART`. | Putting the key in the message. |

### Integration: `config/tests/integration/test_settings_startup.py` (`SimpleTestCase`)

Each test starts `sys.executable manage.py check` with `subprocess.run` (a list, no shell,
`timeout=60`, `cwd=settings.BASE_DIR`, `capture_output=True`, `text=True`), and puts the output in
the assert message, so a failure shows what the process printed. The environment is a copy of
`os.environ` where every `DJANGO_*` variable is removed first, then the chosen ones are set.
Removing `DJANGO_*` also removes `DJANGO_SETTINGS_MODULE` (fine: `manage.py` sets the default
`config.settings`) and `DJANGO_ALLOW_ASYNC_UNSAFE` (which the CUJ tests set; `check` does not need
it). These tests use subprocesses, not Django's test client. This is the only way to test that
`config/settings.py` really calls the functions, because settings are loaded once per process.
`check` does not open the database. The folder `config/tests/integration/` is new; the test runner
already finds the layer from the folder name.

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_debug_off_without_key_stops` | `DJANGO_DEBUG=False`, no key: exit code is not 0, and the output contains `DJANGO_SECRET_KEY is not set`. | `settings.py` not calling `read_secret_key`, or calling it before `DEBUG` is read. |
| `test_debug_off_with_strong_key_passes_deploy_check` | `DJANGO_DEBUG=False`, a fresh `secrets.token_urlsafe(50)` key, `DJANGO_ALLOWED_HOSTS=example.com`: `check --deploy --fail-level WARNING` exits with 0. This is the README build step. | A change to the HTTPS settings that makes the README build fail. |
| `test_no_variables_still_starts` | No `DJANGO_*` variable: `check` exits with 0. (The laptop and CI.) | Requiring a key when debug is on. |

Three new processes cost about 3 seconds in all. No CUJ test: a browser sees nothing new.

## Open questions

1. **(a) Should a host be forced to set `DJANGO_DEBUG` explicitly?** Today (and in this plan) "not set"
   means debug on. A stricter rule: if `DJANGO_SECRET_KEY` is set but `DJANGO_DEBUG` is not, stop
   with "Set DJANGO_DEBUG to False on a server (or True on a laptop)". It closes the "forgot
   DJANGO_DEBUG" hole without touching the laptop, but it is a guess about what "a server" is.
   **Recommendation: not now.** The deploy check in the build (decision 5) already fails on debug
   on, and the README makes `DJANGO_DEBUG=False` step one. Revisit if the app is really put on the
   internet.
2. **(b) Only `True` or `False` (any case), and an empty value stops the app?** The other choice
   is to also accept `0`/`1`/`yes`/`no`, and to treat an empty value as "not set".
   **Recommendation: yes, only the two words, and empty stops the app.** Two words are easy to
   explain, and an empty value treated as "not set" would turn debug on.

## Review

The plan review (2026-10-11) said APPROVE WITH CHANGES. What changed:

- The `DJANGO_DEBUG` error message prints no part of the wrong value, only its length: a swapped
  field could hold the secret key. The test became `test_debug_message_has_no_part_of_the_value`.
- `.strip()` and `.casefold()` apply to both words; ` False` and `"false\n"` added to the test.
- Django's three limits are public constants in `django.core.checks.security.base`, not private.
  We keep our copies, and `test_limits_match_django` checks they are equal.
- The settings lines are named by their content, not by line numbers (the numbers had changed).
- The subprocess tests: `capture_output`, `text`, output in the assert message,
  `cwd=settings.BASE_DIR`, and what removing `DJANGO_*` also removes. The `AGENTS.md` row says
  they use subprocesses, not the test client.
- The exact new build command, and "read the last line of the error".
- New section "Working next to": docs-fixes merges first.
- Open questions cut to two: (a) and (b).

## Decided by the person (2026-10-11)

The plan is **approved**.

- `DJANGO_DEBUG` accepts only `True` or `False` (any case, spaces at the ends removed). Any other
  value, including an empty one, stops the app.
- A host is **not** forced to set `DJANGO_DEBUG` explicitly for now: the `check --deploy` step in the
  build already stops a deploy with debug on.
