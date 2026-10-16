# To-do list: short commands for this project. Type `make help` to see them.

.PHONY: help setup run test unit integration cuj lint format check backup reset worktree landing-shots

# How many processes run the tests. 1 is fastest while there are few tests:
# each extra process has to start Python and Django again. Try PARALLEL=auto
# (one per CPU core) when the tests get slower, for example: make test PARALLEL=auto
PARALLEL ?= 1
TEST = uv run python manage.py test --parallel $(PARALLEL)

# The test folders for one layer, for example `layer_dirs,unit` gives
# config/tests/unit todos/tests/unit. Stops with an error if there are none,
# because `manage.py test` with no folders would run every test.
layer_dirs = $(or $(wildcard */tests/$(1)),$(error No */tests/$(1) folders))

help:
	@echo "make setup            install Python and the packages, create the database, turn on the commit checks"
	@echo "make run              copy db.sqlite3 to backups/ (once a day, keeps 14), remove expired sessions, then start the server at http://127.0.0.1:8000"
	@echo "make test             run every test, then show how many passed in each layer"
	@echo "make unit             run only the unit tests (tests/unit/ folders)"
	@echo "make integration      run only the integration tests (tests/integration/ folders)"
	@echo "make cuj              run only the CUJ tests, in a real browser (tests/cuj/ folders)"
	@echo "make lint             look for mistakes and style problems (ruff check)"
	@echo "make format           rewrite the code in the standard style (ruff format)"
	@echo "make check            the commit checks on every file, the migration check, the tests"
	@echo "make backup           copy db.sqlite3 to backups/ (safe while the server runs; kept until you delete it)"
	@echo "make reset            ask, copy db.sqlite3 to backups/, then start again with an empty database"
	@echo "make landing-shots    take the landing page's screenshots of the app again (scratch data)"
	@echo "make worktree BRANCH=name"
	@echo "                      give a branch its own folder, .claude/worktrees/name"

setup:
	uv sync
	uv run playwright install chromium
	uv run python manage.py migrate
	uv run pre-commit install

# A daily copy of db.sqlite3 first (at most one a day, the newest 14 are kept;
# see todos/backup.py). Then expired sessions are deleted (Django's own
# clearsessions). If either fails, say so and start the app anyway.
run:
	@uv run python manage.py backup_db --daily || echo "Warning: the daily backup did not work (see the message above). The app starts anyway. Run make backup to try again."
	@uv run python manage.py clearsessions || echo "Warning: could not remove expired sessions (see the message above). The app starts anyway."
	uv run python manage.py runserver

test:
	$(TEST)

unit:
	$(TEST) $(call layer_dirs,unit)

integration:
	$(TEST) $(call layer_dirs,integration)

cuj:
	$(TEST) $(call layer_dirs,cuj)

lint:
	uv run ruff check

format:
	uv run ruff format

check:
	uv run pre-commit run --all-files
	uv run python manage.py makemigrations --check --dry-run
	$(TEST)

# A safe copy of db.sqlite3 in backups/db-YYYYMMDD-HHMMSS.sqlite3 (see todos/backup.py).
# It is never deleted automatically (only make run's -daily copies are).
backup:
	uv run python manage.py backup_db

# Asks first (only "yes" goes on), then copies, then deletes. CONFIRM=yes skips
# the question, never the copy. If the copy fails, nothing is deleted.
reset:
	@if [ -f db.sqlite3 ]; then \
		if [ "$(CONFIRM)" != "yes" ]; then \
			printf 'This deletes every account, list and to-do in db.sqlite3.\nA copy goes to backups/ first. Type yes to go on: '; \
			read answer; \
			if [ "$$answer" != "yes" ]; then echo "Nothing was deleted."; exit 1; fi; \
		fi; \
		uv run python manage.py backup_db || exit 1; \
	fi
	rm -f db.sqlite3
	uv run python manage.py migrate

# The landing page's pictures of the app, light and dark. Invented data in a
# scratch database in a temporary folder (never db.sqlite3), on a free port.
landing-shots:
	uv run python scripts/landing_shots.py

# Every branch gets its own worktree: its own folder and its own files, so
# several people or agents can work at the same time.
worktree:
	@test -n "$(BRANCH)" || { echo "Say which branch: make worktree BRANCH=name"; exit 1; }
	@if git show-ref --quiet --verify refs/heads/$(BRANCH); then \
		git worktree add .claude/worktrees/$(BRANCH) $(BRANCH); \
	else \
		git worktree add -b $(BRANCH) .claude/worktrees/$(BRANCH) main; \
	fi
	@echo "Now work in .claude/worktrees/$(BRANCH)"
