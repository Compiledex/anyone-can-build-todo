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
| The browser's cookies | The session id, the CSRF token, sometimes the messages cookie. | No |
| The terminal running `make run` | Django's development server prints each request line, including the address. | No |
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
| `django_admin_log` | Yes (object names, like a to-do title) | Django records changes made in `/admin/`. | The admin. |

Access rules: every view finds data through `visible_to`, `get_visible_todo` or
`get_visible_subtask`; someone else's data gives 404 ([ADR 0003](../adr/0003-404-for-other-peoples-data.md)).
The landing page at `/` is rendered with **no** database data.

## 3. Sessions, cookies and messages

| Item | What it holds | How long |
|---|---|---|
| Session (database table, Django's default) | The user id, and for 15 minutes the last delete's snapshot. | 2 weeks (Django's default `SESSION_COOKIE_AGE`; not changed in `config/settings.py`). Logout empties it. |
| Undo snapshot, `session["undo_delete"]` | A deleted to-do's fields, notes, tag names and steps (`todos/undo.py`). | Usable 15 minutes. Removed by the next list page after that (`drop_expired`), by a new delete, by Undo, or by logout. If none of these happens, it stays in the session row, also after the session expires (gap 2). |
| Messages cookie (Django's default storage: a cookie first) | Short notes for the next page, like "Deleted “<title>”." or "Restored “<title>”." | Read on the next page, then removed. Signed (cannot be changed), but **not encrypted**: the title is readable in the browser's cookie. |
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
| Expired session rows | Stay in `django_session` until `manage.py clearsessions` runs. Nothing runs it today (known gap). |
| Sessions after an account delete | Every session row of the deleted user goes in the same transaction. With session message storage, one new session row then holds only the message "Your account was deleted." (no user id) until the landing page shows it; then it is saved as `{}` (no user id, no text) and the `sessionid` cookie is set again for two weeks. That `{}` row stays in `django_session` until `clearsessions` deletes it after it expires. |

## 5. What is never collected

- **No analytics**, no tracking pixels, no ads, no error-reporting service.
- **Nothing is sent to a third party.** The pages load only this site's own CSS, pictures and one
  script (`reorder.js`). No CDN, no web fonts from other sites; the landing page makes no request
  to another site.
- **No email**: sign-up asks only for a username and a password, and there is no password reset
  by email ([ADR 0008](../adr/0008-mac-notifications-via-osascript.md)).
- **No logs of to-do text** from the app itself: `send_reminders` prints one line with a count and
  the username, never a title, and never `osascript`'s error output.
- Small leak to know about: a search is a `GET` address (`?q=...`), so the development server
  prints the search words in the terminal. It is not saved to a file (gap 5).

## 6. How to delete data

| Want | How | Notes |
|---|---|---|
| Delete one to-do | Delete button (Undo for 15 minutes). | |
| Delete the done to-dos of a list | "Clear completed". | Cannot be undone. |
| Delete a list | "Delete list" (owner only). | Its to-dos and member rows go too. |
| Stop seeing a shared list | "Leave this list" (member). | The to-dos the member added stay in the list. |
| Delete an account | "Delete your account" (`/accounts/delete/`; click "Logged in as <name>" at the top), with the password. The admin can also delete a user at `/admin/`. | Cascade: the user's own lists (with all their to-dos, also those members added, and their steps), their tags, their memberships, their admin log rows, and every session of the user go. Members of the user's shared lists lose those lists. Lists shared *with* the user stay with their owners, with the to-dos the user added there. Copies in `backups/` still hold the data (the page says so). |
| Delete everything | `make reset` (asks `yes` first). | It makes a backup first. |
| Remove data from backups | Delete the files in `backups/` by hand. | A daily copy leaves by itself after 14 newer ones. |

## 7. Known gaps and recommendations

1. ~~**No self-service account delete.**~~ Closed: a person can delete their own account
   (POST, password check, its sessions go too); see the plan
   [delete-account](../plans/delete-account.md).
2. **Expired sessions are not cleaned.** Run `clearsessions` now and then, or from `make run`.
3. **Manual backups never expire** and hold every account and to-do. The README says: do not share
   them; copy them only to a safe place.
4. **The messages cookie shows to-do titles in clear text** in the browser. Fine on the owner's own
   Mac; on a shared computer, use the session message storage instead.
5. **Search words are printed in the terminal.** The development server shows each request line,
   also `?q=<search words>`. It is not saved to a file, but it can be seen on screen or in the
   terminal's scroll-back. Accepted on the owner's own Mac.
6. **The admin log keeps object names.** `django_admin_log` stores the name of every object
   changed in `/admin/` (for example a to-do's title), also after the object is deleted. Delete
   old rows in the admin if that matters.
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
