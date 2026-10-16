# 0004. "Today" is the date in Asia/Tokyo

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-09) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about which day "today" is, which decides when a to-do is overdue, when a repeating copy is
> due, and which to-dos a reminder shows.

## Context

- Due dates (PR #10), recurring copies (PR #20) and reminders (PR #27) all need "today".
- Python's `date.today()` and `datetime.now()` use the computer's own time zone. On a server, that
  is often UTC, not the owner's day. Near midnight, two parts of the app could then disagree about
  the date.
- The owner and their Mac are in the `Asia/Tokyo` time zone.
- Tests must not depend on the day they run.

## Decision

- `TIME_ZONE = "Asia/Tokyo"` and `USE_TZ = True` in `config/settings.py`. Times are stored in UTC
  and shown in Tokyo time.
- "Today" is always `timezone.localdate()`. Never `date.today()` or `datetime.now()`.
- Code that needs "today" takes it as an argument (`make_next_copy(today)`,
  `send_reminders(user, today)`, `is_overdue(today=None)`). The view or command passes
  `timezone.localdate()`; a test passes a fixed date.

## Consequences

- One "today" for every person and every part of the app. A to-do turns overdue at midnight in
  Tokyo.
- Backup names and "one daily backup a day" also use the Tokyo date (`todos/backup.py`).
- Cost: a person in another time zone sees "overdue" at Tokyo's midnight, not their own. Accepted:
  the users are the owner and a few people they share with.
- Rule (in `AGENTS.md`): reviewers reject `date.today()` and `datetime.now()`.

## Alternatives considered

| Option | Why not |
|---|---|
| `TIME_ZONE = "UTC"` (Django's usual default) *(added here)* | "Today" would change at 09:00 in Tokyo. Wrong day for the owner every morning. |
| A time zone per person (a profile field) | More code, a form, and tests for each zone. Not needed for these users; "a separate decision" (due-date plan). |
| The computer's own time zone *(added here)* | Differs between the Mac and a host, and between tests. |

## Source

- [`docs/plans/due-date.md`](../plans/due-date.md) (PR #10): "keep `TIME_ZONE = "Asia/Tokyo"`, the same as the person's computer".
- [`docs/plans/reminders.md`](../plans/reminders.md): the Mac's time zone is `Asia/Tokyo`.
- `AGENTS.md` rule "Today is `timezone.localdate()`".

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
