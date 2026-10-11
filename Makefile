# To-do list: short commands for this project. Type `make help` to see them.

.PHONY: help setup run test unit integration cuj lint format check reset worktree landing-shots

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
	@echo "make run              start the server, then open http://127.0.0.1:8000"
	@echo "make test             run every test, then show how many passed in each layer"
	@echo "make unit             run only the unit tests (tests/unit/ folders)"
	@echo "make integration      run only the integration tests (tests/integration/ folders)"
	@echo "make cuj              run only the CUJ tests, in a real browser (tests/cuj/ folders)"
	@echo "make lint             look for mistakes and style problems (ruff check)"
	@echo "make format           rewrite the code in the standard style (ruff format)"
	@echo "make check            the commit checks on every file, the migration check, the tests"
	@echo "make reset            delete db.sqlite3 and create it again, empty"
	@echo "make landing-shots    take the landing page's screenshots of the app again (scratch data)"
	@echo "make worktree BRANCH=name"
	@echo "                      give a branch its own folder, .claude/worktrees/name"

setup:
	uv sync
	uv run playwright install chromium
	uv run python manage.py migrate
	uv run pre-commit install

run:
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

reset:
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
