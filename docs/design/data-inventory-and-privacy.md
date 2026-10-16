# Data inventory and privacy

| | |
|---|---|
| Type | Data inventory and privacy review |
| Phase | Design |
| Written by | Privacy / security engineer (in this project: the owner and Claude) |
| Status | Approved (describes the code as built) |
| Date | 2026-10-16, checked against `main` at `59b7de2` |
| Data | REAL |

> **What this document is.** A data inventory lists every place where the app keeps personal data:
> what it is, why we keep it, who can see it, how long it stays, and how to delete it. Privacy or
> security engineers write it during design and update it with each feature. Without it, nobody
> knows where personal data hides (a session, a log, a backup), and a request like "delete my
> data" cannot be answered.

**Personal data** is any data about a person who can be identified: a username, a password hash,
and also the text of their to-dos, which can say a lot about their life.

## 1. Where the data lives

Everything is on **the owner's Mac only**. The app is not deployed.

| Place | What is there | In git? |
|---|---|---|
| `db.sqlite3` (project folder) | Every table below. | No (`.gitignore`) |
| `backups/*.sqlite3` | Whole copies of `db.sqlite3`, mode 600 (only the Mac user can read them). | No (`.gitignore`) |
| The browser's cookies | The session id and the CSRF token. Messages are in the session, not in a cookie. | No |
| The terminal running `make run` | Django's development server prints each request line: the method, the address **without** its query string, the status code (`config/logging_filters.py`). | No |
| `~/Library/Logs/anyone-can-build-todo-reminders.log` | Only if the owner installs the reminders job (not done today). | No |

## 2. Tables and fields

| Table / field | Personal data | Purpose | Who can see it |
|---|---|---|---|
| `auth_user.username` | Yes | Log in; share a list by username. | The person; the owner of a list sees its members' usernames; the admin. |
| `auth_user.password` | A **hash** (a one-way code; the password itself is not stored) | Check the password. | Nobody in the app; anyone who has the file can try to crack weak passwords. |
| `auth_user.email`, `first_name`, `last_name` | Empty | Django's own fields. Sign-up does not ask for them. | The admin. |
| `auth_user.last_login`, `date_joined`, `is_staff`, `is_superuser` | Yes (times) | Django's own bookkeeping. | The admin. |
| `TodoList.name`, `name_key`, `created_at` | Yes | The person's lists. `name_key` is the name in one case, for the unique rule. | Owner and members (`visible_to`). |
| `TodoList.members` | Yes (who shares with whom) | Sharing. | The list owner only. Members do not see each other. |
| `Todo.title`, `description` (notes), `due_date`, `priority`, `repeat`, `done`, `created_at`, `position` | Yes, can be sensitive | The to-do itself. | Owner and members of its list. |
| `Todo.repeated_from`, `copy_fingerprint` | No (links and a hash) | Recurring copies ([ADR 0006](../adr/0006-recurring-copy-fingerprint.md)). | Not shown. |
| `Todo.reminded_on` | Low | A reminder at most once a day. | Not shown. |
| `Tag.name`, `Tag.owner` | Yes | Tags. Always the **list owner's** tags, also when a member types one, so tags never leak between users. | Owner and members of a list with that tag. |
| `Subtask.title`, `done`, `created_at` | Yes | Steps of a to-do. | Whoever can see the to-do. |
| `django_session.session_data` | Yes | Login, and the **undo snapshot** (below). | The server only. |
| `django_admin_log` | Yes, but **no names**: a label like `todo 42`, the time, the admin user, the action and the labels of the changed fields (like "Title"). A step's title becomes "name not kept". | Django records changes made in `/admin/` (`todos/admin_log.py`). | The admin. |

Access rules: every view finds data through `visible_to`, `get_visible_todo` or
`get_visible_subtask`; someone else's data gives 404 ([ADR 0003](../adr/0003-404-for-other-peoples-data.md)).
The landing page at `/` is rendered with **no** database data.

## 3. Sessions, cookies and messages

| Item | What it holds | How long |
|---|---|---|
| Session (database table, Django's default) | The user id, and for 15 minutes the last delete's snapshot. | 2 weeks (Django's default `SESSION_COOKIE_AGE`; not changed in `config/settings.py`). Logout empties it. |
| Undo snapshot, `session["undo_delete"]` | A deleted to-do's fields, notes, tag names and steps (`todos/undo.py`). | Usable 15 minutes. Removed by the next list page after that (`drop_expired`), by a new delete, by Undo, or by logout. If none of these happens, it stays in the session row until `make run` deletes the expired session (`clearsessions`). |
| Messages, `session["_messages"]` (`MESSAGE_STORAGE` is the session storage, never a cookie) | Short notes for the next page, like "Deleted “<title>”." or "Restored “<title>”." | Read on the next page, then removed from the session. Logout empties it. A message shown to a visitor who is not logged in leaves an empty session row (`{}`, no text), which `clearsessions` removes after it expires. |
| The admin's success messages | For a staff user in `/admin/`: a note with a name, like "The to-do “…” was deleted successfully." It is kept in the session too, like the app's messages (the row above), never in a cookie. | Until the next admin page shows it, then removed. Accepted: only the owner uses `/admin/`. |
| CSRF cookie | A random token. | Django's default (one year). |

With `DJANGO_DEBUG=False` (only on a server), the session and CSRF cookies are sent over HTTPS
only.

## 4. Retention: how long data stays

| Data | Retention |
|---|---|
| Accounts, lists, to-dos, tags, steps | Until the person (or the admin) deletes them. A person deletes their own account, and everything they own, on "Delete your account" (section 6). |
| A deleted to-do | Gone from `db.sqlite3` at once (no soft delete, [ADR 0005](../adr/0005-delete-undo-session-snapshot.md)). It can still be in the session for a short time, and in backups. |
| Daily backups (`make run`) | The newest 14 daily copies (`DAILY_KEEP = 14` in `todos/backup.py`). Older daily copies are deleted. |
| Manual backups (`make backup`, `make reset`) | **Forever**, until the owner deletes them by hand. |
| Expired session rows | Deleted by `make run` (Django's `clearsessions`, after the daily copy, before the server starts). The daily copy of that day can still hold them, for 14 days. |
| Sessions after an account delete | Every session row of the deleted user goes in the same transaction. Messages are kept in the session, so one new session row then holds only the message "Your account was deleted." (no user id) until the landing page shows it; then it is saved as `{}` (no user id, no text) and the `sessionid` cookie is set again for two weeks. That `{}` row stays in `django_session` until `clearsessions` (run by `make run`) deletes it after it expires. |

## 5. What is never collected

- **No analytics**, no tracking pixels, no ads, no error-reporting service.
- **Nothing is sent to a third party.** The pages load only this site's own CSS, pictures and one
  script (`reorder.js`). No CDN, no web fonts from other sites; the landing page makes no request
  to another site.
- **No email**: sign-up asks only for a username and a password, and there is no password reset
  by email ([ADR 0008](../adr/0008-mac-notifications-via-osascript.md)).
- **No logs of to-do text** from the app itself: `send_reminders` prints one line with a count and
  the username, never a title, and never `osascript`'s error output.
- **No search words in the terminal**: a search is a `GET` address (`?q=...`), but the
  development server prints its request lines without the query string (`DropQueryString` in
  `config/logging_filters.py`). Known limits, both only with hand-made requests (tools like
  `curl` or `nc`, never from the app's own pages): a raw space in the query gives a "Bad request
  syntax" line in which the words after the space are still printed; and a `?` written as `%3F`
  in the path (`/lists/3/%3Fq=secret`) is part of the path, not a query string, so it is printed
  as it is.

## 6. How to delete data

| Want | How | Notes |
|---|---|---|
| Delete one to-do | Delete button (Undo for 15 minutes). | |
| Delete the done to-dos of a list | "Clear completed". | Cannot be undone. |
| Delete a list | "Delete list" (owner only). | Its to-dos and member rows go too. |
| Stop seeing a shared list | "Leave this list" (member). | The to-dos the member added stay in the list. |
| Delete an account | "Delete your account" (`/accounts/delete/`; click "Logged in as <name>" at the top), with the password. The admin can also delete a user at `/admin/`. | Cascade: the user's own lists (with all their to-dos, also those members added, and their steps), their tags, their memberships, the admin log rows they made (by CASCADE; rows another admin made about their things stay, with no names), and every session of the user go. Members of the user's shared lists lose those lists. Lists shared *with* the user stay with their owners, with the to-dos the user added there. Copies in `backups/` still hold the data (the page says so). |
| Delete everything | `make reset` (asks `yes` first). | It makes a backup first. |
| Remove data from backups | Delete the files in `backups/` by hand. | A daily copy leaves by itself after 14 newer ones. |

## 7. Known gaps and recommendations

1. **Closed.** There was no self-service account delete: now a person can delete their own
   account (POST, password check, its sessions go too); see the plan
   [delete-account](../plans/delete-account.md).
2. **Closed.** Expired sessions were not cleaned: now `make run` runs `clearsessions` after the
   daily copy.
3. **Manual backups never expire** and hold every account and to-do. The README says: do not share
   them; copy them only to a safe place.
4. **Closed.** The messages cookie showed to-do titles in clear text: now messages are kept in
   the session on the server (`MESSAGE_STORAGE`).
5. **Closed.** Search words were printed in the terminal: now the development server's request
   lines have no query string (section 5 names the one known limit).
6. **Closed: the admin log keeps no names.** `django_admin_log` stores a label like `todo 42`
   (the model's name and the row number) instead of a to-do's title, a list's name or a
   username, and a step's title becomes "name not kept" (`todos/admin_log.py`). The data
   migration `0023_blank_admin_log_names` replaced the names in the rows that were already
   there. Two limits: backups made before that migration still hold the old names, and SQLite
   can keep the old bytes in free pages of `db.sqlite3` until it reuses them.
7. **If it ever runs on a server:** add HTTPS (already forced with debug off), a password-attempt
   limit, closed or invited sign-up, a privacy notice, and backups off the machine.

## Related documents

- [Design doc](design-doc.md), sections 6 and 10
- [ADRs](../adr/README.md): 0003, 0005, 0008
- [Product requirements](../product/prd.md)
- [Deployment runbook](../runbooks/deployment.md)
- Plans: [`accounts.md`](../plans/accounts.md), [`sharing.md`](../plans/sharing.md),
  [`delete-undo.md`](../plans/delete-undo.md), [`backup-on-run.md`](../plans/backup-on-run.md),
  [`local-safety.md`](../plans/local-safety.md), [`reminders.md`](../plans/reminders.md)
