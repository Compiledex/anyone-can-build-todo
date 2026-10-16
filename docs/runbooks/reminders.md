# Reminders runbook

| | |
|---|---|
| Type | Runbook (set up a scheduled job) |
| Phase | Production |
| Written by | Site reliability engineer (in this project: the owner and Claude) |
| Status | Approved; not in use (the owner has not switched reminders on) |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** The steps to switch on the morning notification on the owner's Mac,
> and to change or stop it. They change the Mac's settings, so the person does them, not the AI
> (`AGENTS.md`: the AI never installs the job, never runs `launchctl`, never writes to
> `~/Library`). Run every command in the project folder. Moved here from `README.md` on
> 2026-10-16 (this PR); the text is the same.

## Set it up

Once a day, at 08:00, your Mac can show **one notification** with the to-dos in **your own lists**
that are **due today** and not done (not the lists others shared with you). If nothing is due,
there is no notification. A to-do is shown only once a day.

You can run it by hand at any time (replace `alice` with your username on the site):

```bash
uv run python manage.py send_reminders --user alice
```

It prints `Showed 1 notification (2 to-dos) for alice.` or `No to-dos due today for alice.`

To run it every morning, the Mac's own scheduler, **launchd**, starts it. You set this up once, in
the Terminal. These steps change your Mac's settings, so you do them yourself (not the AI).

1. **Move the project out of `Documents` (recommended).** macOS protects `Documents` from programs
   that start in the background, so launchd cannot go into the project folder, and the job fails
   with an empty log. Move it, for example to `~/code/anyone-can-build-todo`, and run `make setup`
   again there. Do not give Python "Full Disk Access" instead: that gives every Python script on
   the Mac access to all your files. (iCloud "Desktop & Documents" can also touch `db.sqlite3`
   while the app writes to it.)
2. **Get the database ready**, after you pull this feature:

   ```bash
   uv run python manage.py migrate
   ```

3. **Allow notifications first.** Show one test notification:

   ```bash
   osascript -e 'display notification "Test" with title "To-do list"'
   ```

   Open **System Settings → Notifications → Script Editor** and turn on **Allow notifications**.
   Run the line again and check that you see "Test", and that a Focus mode (like Do Not Disturb)
   is off. Do this before step 4: `osascript` says "it worked" even when notifications are not
   allowed, and then the to-dos are marked as reminded although you saw nothing.
4. **Try the command by hand.** Make a to-do due today in one of your own lists, then run
   `uv run python manage.py send_reminders --user <your username>`. To try again the same day,
   make a **new** to-do due today: the shown ones are now marked.
5. **Fill in the template** `deploy/macos/com.anyone-can-build-todo.reminders.plist`. In the
   project folder (replace `alice` with your username):

   ```bash
   mkdir -p ~/Library/LaunchAgents
   sed -e "s|__REPO_PATH__|$(pwd)|g" -e "s|__HOME__|$HOME|g" -e "s|__USERNAME__|alice|g" \
     deploy/macos/com.anyone-can-build-todo.reminders.plist \
     > ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   plutil -lint ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   ```

   `plutil -lint` must say `OK`. The project folder's path must not contain `&` or `|`: `sed`
   reads them as special characters, and the paths in the file would be wrong.
6. **Turn it on.** An error from `bootout` the first time is normal.

   ```bash
   launchctl bootout gui/$(id -u)/com.anyone-can-build-todo.reminders
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.anyone-can-build-todo.reminders.plist
   ```

   If "Background Items Added" comes up, check **System Settings → General → Login Items →
   Allow in the Background**. If it is off, the job never runs.
7. **Test it now** (make a new to-do due today first):

   ```bash
   launchctl kickstart -k gui/$(id -u)/com.anyone-can-build-todo.reminders
   cat ~/Library/Logs/anyone-can-build-todo-reminders.log
   launchctl print gui/$(id -u)/com.anyone-can-build-todo.reminders | grep "last exit code"
   ```

   `last exit code = 0` means it worked. Another number with an empty log usually means launchd
   could not go into the project folder (see step 1).
8. **To change or stop it:** run the `bootout` line, change the file (or fill it in again with
   step 5), and run `bootstrap` again. To stop it for good, run `bootout` and delete the file from
   `~/Library/LaunchAgents/`.

If the Mac is asleep at 08:00, the job runs when it wakes up. If the Mac is shut down, it does not
run that day: run the command by hand. The job runs the code that is in the project folder now, so
after you pull new code, run `uv run python manage.py migrate` once.

## Related documents

- [ADR 0008: Mac notifications via osascript](../adr/0008-mac-notifications-via-osascript.md)
- [`docs/plans/reminders.md`](../plans/reminders.md) (why it works this way; history)
- The template: [`deploy/macos/com.anyone-can-build-todo.reminders.plist`](../../deploy/macos/com.anyone-can-build-todo.reminders.plist)
- [Deployment runbook](deployment.md): start, update and roll back the app itself
