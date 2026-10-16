# 0008. Reminders as Mac notifications through osascript, no email

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted (the code is built; the owner has not switched the daily job on) |
| Date | 2026-10-16 (written after the fact; decided 2026-10-10) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about how the app reminds a person of the to-dos due today.

## Context

- The first reminders plan (2026-10-09) sent an **email**. It needed SMTP (a mail server
  account), email settings, secrets and email addresses.
- On 2026-10-10 the owner decided that the site runs only on their own Mac, not on a server
  (GitHub Pages was ruled out: it cannot run Django). The Mac's time zone is `Asia/Tokyo`.
- On a Mac, a program can show a notification with `osascript`, the Mac's tool that runs
  AppleScript (a small script language for the Mac).
- A to-do title is text from a person. If it were put inside a script or a shell command, a title
  like `" & do shell script "..."` could run code.

## Decision

A reminder is one macOS notification, not an email. `python manage.py send_reminders --user
<username>` shows the to-dos **due today**, not done, in the user's **own** lists.

- `todos/reminders.py` runs `/usr/bin/osascript` with a **fixed** AppleScript, then `--`, then the
  title and the text as **arguments** (`argv`). It passes a Python list, never a shell
  (`shell=True` is never used).
- `reminded_on` is set only after `osascript` worked, so a to-do is reminded at most once a day.
- The Mac's scheduler, **launchd**, can run it at 08:00 with the template in
  `deploy/macos/com.anyone-can-build-todo.reminders.plist`. launchd, not cron: cron skips a job
  while the Mac sleeps; launchd runs it on wake.
- The owner installs the template by hand. The AI never runs `launchctl` and never writes to
  `~/Library`.

## Consequences

- No email at all: no SMTP, no email secrets, no email addresses stored, no password reset by
  email (the password reset pages of Django are not included, `accounts/urls.py`).
- Safe: a to-do title can never run as code.
- Private: the command prints one line, never a to-do title. An error never includes `osascript`'s
  error output, which could repeat titles into the log file.
- Only the list **owner** is reminded: `reminded_on` is one date per to-do. This is the one place
  that filters by `todo_list__owner` instead of `visible_to` (on purpose, not a view).
- Works only on a Mac. Elsewhere `osascript` is missing, and the command stops with "Could not show the notification: ..." and marks nothing.
- Tests never start the real `osascript` (`FakeOsascriptMixin`).
- Status today: the daily job is **not** switched on (the owner's choice). The plan asks to move the
  project out of `~/Documents` first (no Full Disk Access for Python).

## Alternatives considered

| Option | Why not |
|---|---|
| Email through SMTP | Needs a mail account, secrets and addresses; dropped on 2026-10-10. |
| cron | Skips the job when the Mac is asleep at 08:00. |
| Build the AppleScript with the title inside | Lets a title run code. Forbidden by a rule in `AGENTS.md`. |
| Remind every member of a shared list | `reminded_on` is one date per to-do, so the first run would hide it from the others. Needs a small "shown to this person on this day" table; left for later (plan, "New open questions"). |

## Source

- [`docs/plans/reminders.md`](../plans/reminders.md): "Changed on 2026-10-10" and "Decided by the person" (plan PR #26, code PR #27).
- `todos/reminders.py`, `todos/management/commands/send_reminders.py`, `deploy/macos/`.
- README, "Reminders on your Mac".

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
- [Data inventory and privacy](../design/data-inventory-and-privacy.md)
