# On-call and incident runbook

| | |
|---|---|
| Type | On-call and incident runbook |
| Phase | Production |
| Written by | Site reliability engineer (in this project: the owner and Claude; the rota is simulated) |
| Status | Approved |
| Date | 2026-10-16 |
| Data | MIXED (see below) |

> **What this document is.** *On call* means one named person answers when something breaks. An
> *incident* is a problem that hurts users or their data now. This runbook says how bad each kind
> of incident is, who acts, and the exact steps for the common ones. Without it, people guess under
> stress, and a guess like "delete the database and start again" can turn a small problem into
> data loss.

> **SIMULATED.** The people, quotes, numbers and sessions in this document are invented for
> practice. The app has no real users besides its owner. Real facts are marked with their source.

Only the rota (who is on call in a team) is simulated. The levels and playbooks are real.

## Severity levels

The same levels as [bug triage](../bug-reports/README.md#severity-levels).

| Level | Meaning | Response |
|---|---|---|
| S1 | Data lost, or someone sees data that is not theirs | Act now. Stop the server first. Write a postmortem after. |
| S2 | The app does not start, or a main journey is broken | Act the same day. |
| S3 | One feature is wrong, with a workaround | Next working session. |
| S4 | Cosmetic | When convenient. |

## Who is on call

**Real:** the app runs only on the owner's Mac, so the owner is always on call. No pager, no
monitoring: the owner notices a problem when they use the app, or sees CI on GitHub.

**If this were a team (simulated):**

| Week | Primary | Secondary | Handover |
|---|---|---|---|
| 1 | Ingrid | Tomas | Monday 10:00 Tokyo |
| 2 | Tomas | Amara | Monday 10:00 Tokyo |
| 3 | Amara | Kenji | Monday 10:00 Tokyo |

The primary answers within 15 minutes for S1 and within 4 hours for S2. If not, the secondary
takes it.

## First three steps, for any incident

1. **Do not delete anything.** Not `db.sqlite3`, not `backups/`. Never run `make reset` to "fix" it.
2. **Stop the server** (`Ctrl+C`) if data may be changing in a wrong way.
3. **Make a copy of the current state:** `make backup`. It is safe also while the server runs.

Then follow the playbook below.

## Playbook A: the app does not start

| What you see | Cause | Fix |
|---|---|---|
| `Error: That port is already in use.` | Another server (often an old `make run`) uses port 8000 | `lsof -i :8000` shows the program. Stop it in its own terminal with `Ctrl+C`. Do not kill a process you do not recognise. |
| `ImproperlyConfigured: DJANGO_DEBUG must be True or False. It is set to something else (length N).` | `DJANGO_DEBUG` is set to something like `1`, `yes` or empty | `echo $DJANGO_DEBUG` to see it. On the laptop, remove it: `unset DJANGO_DEBUG`. Check `~/.zshrc` if it comes back. (`config/env.py`) |
| `ImproperlyConfigured: DJANGO_SECRET_KEY is not set. DJANGO_DEBUG is False ...` | `DJANGO_DEBUG=False` on the laptop | `unset DJANGO_DEBUG`. The laptop does not need a secret key. |
| `You have N unapplied migration(s)...` and pages fail with `no such column` or `no such table` | New code, old database | `make backup`, then `uv run python manage.py migrate` |
| `command not found: uv` | uv is not installed, or the terminal is old | Install uv (see the [deployment runbook](deployment.md)), open a new terminal |

After the fix: `make run`, then the health check in the [deployment runbook](deployment.md#5-health-check).

## Playbook B: data looks wrong or is lost (S1)

1. Stop the server (`Ctrl+C`).
2. `make backup`. This keeps the wrong state too, so you can study it later.
3. Write down what is wrong: which list, which to-do, what you expected, when it was last right.
4. Check that it is not a feature first:
   - A to-do you deleted can come back with **Undo** for 15 minutes (`todos/undo.py`).
   - A list you **left** is gone for you, but still exists for its owner.
   - A filter (Not done / Done) or a search hides rows. Click All and "Show all".
5. Find the newest good copy: `ls -lt backups/`. The newest `-daily` copy is from the first
   `make run` of that day.
6. Restore it with the exact steps in the [deployment runbook, section 4A](deployment.md#a-restore-a-backup-file-the-safe-way).
7. Write a postmortem (see the [postmortem example](../postmortems/2026-10-09-merged-with-red-ci.md)).

## Playbook C: the daily backup warning

`make run` printed `Warning: the daily backup did not work (see the message above). The app starts
anyway. Run make backup to try again.`

1. Read the line above it. It starts `CommandError: Could not copy the database: ...`.
2. Common causes: the disk is full (`df -h .`); `backups` is a file, not a folder
   (`ls -ld backups`); a folder or link has today's daily name ([BUG-002](../bug-reports/BUG-002-failed-backup-reported-as-success.md)).
3. Fix the cause, then run `make backup` and check it prints `Saved a copy in backups/...`.

The other warning, `Warning: could not remove an old daily copy: ...`, is milder: today's copy is
safe; only an old one stayed. Check the permissions of that file.

## Playbook D: CI is red on main

The ruleset on `main` requires `lint` and `test` to be green before a pull request merges (set on
2026-10-11). A red run on `main` can still happen, for example from a flaky test (one that
sometimes fails with no code change).

1. Look: `gh run list --branch main --limit 5`, then `gh run view <id> --log-failed`.
2. Merge nothing else until `main` is green.
3. If it is a browser (CUJ) test and the error is about timing, rerun once:
   `gh run rerun <id> --failed`. Green on rerun still means a flaky test: open a bug for it
   (see PR #19 and PR #22 for how they were fixed).
4. If it fails again, run `make check` on your Mac on the same commit. Fix it in a new branch and
   pull request, with a test.
5. Never turn off a check or skip a test to get green. See the
   [postmortem](../postmortems/2026-10-09-merged-with-red-ci.md) for why.

## Playbook E: someone sees another person's list (S1, security)

1. Stop the server.
2. Check the list is not **shared**: as the owner, open the list and look at its members. A member
   is allowed to see it. Remove the member if that was a mistake.
3. If it is not shared: write down the address (URL) and both usernames. Reproduce it with two
   test accounts, not real ones.
4. Find the view for that address in `todos/urls.py` and `todos/views.py`. Every view must find
   the list with `TodoList.objects.visible_to(request.user)` or the to-do with `get_visible_todo`
   (AGENTS.md, "Only my data, plus what is shared with me").
5. Write a failing integration test with `assertOtherUserGets404` (`accounts/tests/helpers.py`),
   then fix, then `make check`.
6. Restart only after the fix is merged. Write a postmortem.

## Related documents

- [Deployment runbook](deployment.md)
- [Bug triage process](../bug-reports/README.md)
- [Postmortem: PR #12 merged with a red CI run](../postmortems/2026-10-09-merged-with-red-ci.md)
- [Data inventory and privacy](../design/data-inventory-and-privacy.md)
- Plans: [`local-safety.md`](../plans/local-safety.md), [`backup-on-run.md`](../plans/backup-on-run.md),
  [`safe-settings.md`](../plans/safe-settings.md), [`sharing.md`](../plans/sharing.md)
