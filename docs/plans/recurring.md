# Plan: recurring to-dos

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: test pyramid and foundation (wave 0: `TodoForm`, `_todo_item.html`, `base.html`),
17 accounts (wave 1), 10 lists, 4 edit, 6 due date (wave 2), 5 description, 9 priority, 11 tags,
18 sharing, 19 clear completed (wave 3).

## Goal

A person can make a to-do **repeat**: every day, every week or every month. "Every Monday" is a
weekly to-do whose due date is a Monday.

When a repeating to-do is marked **Done**, the app makes a **copy** of it, with the next due date.
The done one stays in the list as done, as today. The copy is the next time the task must be done.

There is no background job (a program that runs by itself on a timer). The copy is made in the
same request as the click on "Done". This is the simplest way that works.

## Decisions

### The rules

- **Four choices: Never, Daily, Weekly, Monthly.** "Never" is the default. A to-do that does not
  repeat works exactly as it does today.
- **No "every 2 weeks", no "weekdays only", no yearly.** Each one is easy to add later as a new
  choice, but none is needed now.
- **Weekly keeps the weekday of the due date.** A weekly to-do due on Monday 12 Oct 2026 is next
  due on Monday 19 Oct 2026. So "every Monday" means: choose Weekly, and a due date on a Monday.
  The list shows "Repeats every Monday", so the person sees it.

### The field

```python
class Repeat(models.TextChoices):
    NEVER = "", "Never"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"

repeat = models.CharField(max_length=10, choices=Repeat.choices, default=Repeat.NEVER, blank=True)
```

- `blank=True` is **needed**: without it, Django's validation refuses the empty string, so
  "Never" could not be saved through a form. Because one choice already has the value `""`, the
  `<select>` does not get the extra "---------" line.

### A repeating to-do needs a due date

- **The form refuses "repeat" without a due date.** The error says: "A repeating to-do needs a due
  date." Without a date, there is nothing to count from.
- The check goes in `Todo.clean()` on the model. Raise it on the field:
  `ValidationError({"repeat": "A repeating to-do needs a due date."})`, so the error shows next to
  the select.
- **Where `clean()` runs, and where it does not.** A `ModelForm` runs `clean()` when the view calls
  `form.is_valid()`. So the add form, the edit page (#4) and the Django admin get the rule. But
  `save()` and `Todo.objects.create()` do **not** run it. So:
  - Every view that saves `repeat` must go through `TodoForm` and `is_valid()`. Never set
    `repeat` from `request.POST` by hand.
  - `make_next_copy` uses `create()`. That is fine: a copy always gets a due date.
  - `"repeat"` and `"due_date"` must **both** be in `TodoForm.Meta.fields`. If `clean()` raises an
    error for a field that is not in the form, Django raises `ValueError` (a crash, not a form
    error).
- **Safety net:** if a repeating to-do somehow has no due date (for example, a row changed by hand
  in the database), marking it done makes **no** copy. It never crashes.

### The next due date

All date math is in one **pure function** (a function that only uses its inputs and returns a
result; it does not read the database, the clock or the request). It lives in a new file,
`todos/recurrence.py`:

```python
def next_due_date(due_date, repeat, today):
    """The first date after due_date, in steps of `repeat`, that is today or later.

    Returns None if that date would be after 31 Dec 9999 (the last date Python can store).
    """
```

- **It counts from the due date, not from the day the person clicked Done.** A weekly Monday task
  stays on Mondays, even if it is done on a Wednesday.
- **It always moves at least one step.** Done early (due tomorrow, done today): the copy is due one
  step after tomorrow.
- **It skips dates that are already past.** A daily to-do due 10 days ago, done today, gets a copy
  due **today**, not 9 days ago. Without this rule, the copy would be overdue the moment it
  appears, and the person would have to click Done 10 times to catch up. "Due today" is not
  overdue (see the due date plan), so a copy due today is fine.
- **No loop. It computes the number of steps directly.** A date field accepts any year from 1 to
  9999. A loop of "one more step" from a due date in the year 1 would run about 740,000 times for
  daily, in one request. Instead:
  - Daily and weekly: `days = (today - due_date).days`, step = 1 or 7,
    `steps = max(1, -(-days // step))` (whole numbers only, rounded up), result `due_date + timedelta(days=steps * step)`.
  - Monthly: `months = (today.year - due_date.year) * 12 + (today.month - due_date.month)`,
    `months = max(1, months)`. If `add_months(due_date, months)` is still before `today`, add one
    more month. (One extra month is always enough: the first guess is at most one month short.)
- **The end of the calendar.** A to-do due 31 Dec 9999 has no next date: `due_date + 1 day` is an
  `OverflowError` in Python (and a month after Dec 9999 is a `ValueError`). `next_due_date`
  catches both and returns `None`, and then no copy is made. This is silly data, but without the check a person could crash the page with one click.
- `today` is a parameter, like `Todo.is_overdue(today=...)`, so the tests can use a fixed date. The
  view passes `timezone.localdate()`: today in `TIME_ZONE` (`Asia/Tokyo`), the same "today" that
  `is_overdue` uses. So "today" on the page and "today" for the copy always agree.

### Month-end dates

- **Monthly keeps the day of the month. If that day does not exist, it uses the last day of the
  month.** 31 Jan → 28 Feb (or 29 Feb in a leap year). 31 Mar → 30 Apr. 31 Dec → 31 Jan of the
  next year. 29 Feb 2028 → 29 Mar 2028.
- Python's `calendar.monthrange(year, month)` gives the number of days in a month. **No new
  package** (like `python-dateutil`) is needed for this.
- When more than one step is needed (the "skip past dates" rule), the months are added to the
  **original** due date in one go: 31 Jan + 2 months is 31 Mar, not 28 Mar.
- **Known limit, on purpose:** the copy only stores its own due date. A to-do due 31 Jan gets a
  copy due 28 Feb. When that copy is done, its copy is due 28 Mar, not 31 Mar. The day "drifts" to
  the 28th. To fix this we would need one more field (the "wanted day of the month"). That is
  more than this task needs. It is listed under "Open questions".

### What is copied

The copy is a new `Todo` row, made with `Todo.objects.create(...)` (never with the
`pk = None; save()` trick, which would also copy `done` and `repeated_from`):

| Copied | Not copied |
|---|---|
| `title` | `done` — the copy starts as not done |
| `description` (#5) | `created_at` — the copy gets the time it was made |
| `priority` (#9) | `id` — the copy is a new row |
| `todo_list` (#10) — the same list | `repeated_from` of the original — the copy points to the original instead |
| `repeat` — so the copy repeats too | |
| `due_date` — set to `next_due_date(...)` | |
| `tags` (#11) — the same `Tag` rows, with `copy.tags.set(original.tags.all())` **after** the copy is saved | |

- **There is no owner to copy.** After #10, the owner of a to-do is `todo.todo_list.owner`. The
  copy is in the same list, so it has the same owner, even when a shared member (#18) clicks Done.
  It is never `request.user`. If the merged #10 code kept a `Todo.owner` field, copy it from the
  original too.
- **Tags:** a many-to-many link (a link table between to-dos and tags) can only be set after the
  row exists. So the tags are set after `create()`, and **only when a new copy was really made**.
  The same `Tag` rows are reused; they already belong to the list owner (see the tags plan), so no
  new tags are made and `set_tags` is not needed.
- **Sharing is per list** (#18: `TodoList.members`). The copy is in the same list, so the same
  people see it. Nothing else to copy.
- The copy goes to the end of the list, because the list is ordered by `created_at`.
- All the copy logic is in **one** model method, `Todo.make_next_copy(today)`. It returns the new
  copy, or `None` when no copy was made (no repeat, no due date, no next date, or a copy already
  exists). The view only calls it. A field added later (for example subtasks or reminders) only
  needs a change in this one place.

### "Undo", and clicking twice — no duplicates

This is the tricky part. The rules:

1. **The copy remembers where it came from.** A new field on the copy:
   `repeated_from = models.OneToOneField("self", null=True, blank=True,
   on_delete=models.SET_NULL, related_name="next_copy")`.
   A `OneToOneField` puts a `UNIQUE` rule in the database: one original can have **at most one**
   copy. Empty values (`NULL`) do not count, so many to-dos can have no `repeated_from`.
2. **Done:** inside `make_next_copy`: if the original already has a copy, do nothing. If not, make
   one. `get_or_create` is not used, because the tags must be set only on a new copy; a plain
   "does `next_copy` exist? if not, create" is clearer, and the `UNIQUE` rule is the safety net.
3. **Undo:** "Undo" means "I did not do it yet", so the next one should not exist yet either.
   - If the copy is **not done** and is **still in the same list**, delete it. The page shows a
     message (Django's `messages`): "The next copy, due 19 Oct 2026, was removed."
   - If the copy is **already done**, keep it. The person has already moved on to the next one.
     Only the original goes back to "not done". Because the link still exists, clicking Done
     on the original again does **not** make another copy.
   - If the copy was **moved to another list** (if #4 allows that), keep it. A member of the first
     list must not delete a to-do in a list that is not shared with them.
4. **If the person deleted the copy themselves**, the link is gone (the link is stored on the
   copy's row, so it is deleted with that row). Then Done on the original makes a new copy. That
   is correct: there is no next one any more.
5. **If the original is deleted** (by Delete, or by "Clear completed" #19), the copy stays, and
   its `repeated_from` becomes empty (`SET_NULL`). Django does this for a bulk delete
   (`QuerySet.delete()`) too.

**Two requests at the same time.** The whole toggle runs inside `transaction.atomic()` (all the
database changes happen together, or none of them do), and the to-do is **read inside** that
block, not before it. Otherwise a second request decides "Done or Undo?" from an old value.

On SQLite there is one more problem. We checked it: when two transactions have both read, and both
then try to write, SQLite refuses the second one at once with "database is locked". The person
would see an error page. The fix is one line in `config/settings.py`, available since Django 5.1
(we have 5.2): `"OPTIONS": {"transaction_mode": "IMMEDIATE"}` in `DATABASES["default"]`. Then a
transaction takes the write lock when it starts, and the second request **waits** for the first,
instead of failing. This is the setting Django's documentation recommends for SQLite web sites.

Walk through "toggle twice", and more:

| Clicks on the original | Result |
|---|---|
| Done | original done, 1 copy |
| Done, Undo | original not done, 0 copies |
| Done, Undo, Done | original done, 1 copy (a new one) |
| Done, Undo, Done, Undo | original not done, 0 copies |
| A double-click on Done, so two requests are sent | the requests run one after the other; the second sees "done" and is an Undo, because toggle flips: original not done, 0 copies. Same as today for any to-do. |
| "Done" in two tabs that both still show "Done" | the same: the second one is an Undo. Toggle flips; this is today's behavior and not changed here. |
| Done, copy marked done, Undo on the original | original not done, the done copy stays, and the copy has its own copy |

- **Known limit:** Undo deletes a copy that is not done, even if the person edited it (#4) in
  between. The message tells them it was removed. This is rare: a person who already works on
  the next copy usually does not undo the old one.

### The page

- The add form gets the `repeat` select from `TodoForm`, labelled "Repeat", with "Never" first.
- The edit page (#4) gets the same field, through `TodoForm`, with no template change.
- Each repeating to-do shows a short text next to its due date, in `_todo_item.html`:
  - Daily: "Repeats daily"
  - Weekly: "Repeats every Monday" (the weekday of the due date, with `date:'l'`)
  - Monthly: "Repeats monthly"
- Messages from Django's `messages` are shown in `base.html`. #19 clear completed adds that block;
  if it is not there yet, add it there once (not in `todo_list.html`).

## Not part of this task

- More rules: every 2 weeks, weekdays only, yearly, "the last Friday of the month".
- Fixing the month-end drift (see "Open questions").
- Copying **subtasks** (#16) and **reminders** (#7). They are in the same wave (4), so this plan
  cannot assume they exist. Whichever is built last adds them to `Todo.make_next_copy`. (The
  subtasks plan suggests: copy the steps, with `done` set back to false.)
- "Skip this one" or "stop repeating" buttons. To stop, the person edits the to-do (#4) and
  chooses "Never".
- Changing toggle into two separate actions ("mark done" and "mark not done"), which would make
  the two-tabs case exact. Toggle stays a flip.
- A background job that makes copies before the old one is done.
- Showing the future dates of a repeating to-do in a calendar.
- A browser (CUJ) test. The integration tests check every rule; one manual check in a real
  browser is enough (step 8).
- The admin: no change. `repeat` already shows on the admin's edit page, because the admin builds
  its form from the model.

## Changes to files

| File | Change |
|---|---|
| `todos/recurrence.py` | **New.** Only the date math: `add_months(day, months)` and `next_due_date(due_date, repeat, today)`. `repeat` is a plain string (`"daily"`, `"weekly"`, `"monthly"`), the same values as `Todo.Repeat`. No Django imports, so the unit tests need nothing else. |
| `todos/models.py` | The `Repeat` class and the `repeat` field (see "The field"). New field `repeated_from`. `clean()` with the due date rule. `make_next_copy(today)`. |
| `todos/migrations/` | One new migration, made by `makemigrations`. Existing rows get `repeat = ""` (Never) and no `repeated_from`. |
| `todos/forms.py` | Add `"repeat"` to `TodoForm.Meta.fields`. |
| `todos/views.py` | `todo_toggle`: inside `transaction.atomic()`, find the to-do (with `get_visible_todo`, from #18), flip `done`, save; on Done call `make_next_copy(timezone.localdate())`; on Undo delete the copy if it is not done and in the same list, and add a message. The 404 check for other users does not change. |
| `config/settings.py` | `"OPTIONS": {"transaction_mode": "IMMEDIATE"}` for the SQLite database. |
| `todos/templates/todos/todo_list.html` | The `repeat` select in the add form. |
| `todos/templates/todos/_todo_item.html` | The "Repeats ..." text. |
| `todos/templates/base.html` | The messages block, only if no earlier feature added it. |
| `AGENTS.md`, `README.md` | `recurrence.py` in the file table; new fields in the `models.py` row; new test numbers. |

`next_due_date` with `repeat = ""` (Never) raises `ValueError`. The model never calls it for a
to-do that does not repeat, so this only catches a programming mistake.

## Tests

Rule from the test pyramid: test each rule once, in the lowest layer where a person would notice
it.

**Dates in tests.** Unit tests pass a fixed `today` (for example `date(2026, 10, 9)`). Integration
tests cannot: the view uses the real `timezone.localdate()`. So integration tests that check a
copy's date use a due date **in the future**, counted from today:
`due = timezone.localdate() + timedelta(days=30)`, and expect `due + 7 days` (weekly). A fixed date
like 12 Oct 2026 would make the test fail after that day. (Only the display test may use a fixed
Monday, because the text does not depend on today.)

### Unit — `todos/tests/unit/test_recurrence.py` (`SimpleTestCase`, no database)

| Test | What it checks |
|---|---|
| `test_daily_next_day` | Due 9 Oct, today 9 Oct → 10 Oct. |
| `test_weekly_same_weekday` | Due Mon 12 Oct, today 9 Oct → Mon 19 Oct. |
| `test_monthly_same_day` | Due 15 Oct → 15 Nov. |
| `test_monthly_jan_31_to_feb_28` | Due 31 Jan 2027 → 28 Feb 2027. |
| `test_monthly_jan_31_to_feb_29_in_leap_year` | Due 31 Jan 2028 → 29 Feb 2028. |
| `test_monthly_feb_29_to_mar_29` | Due 29 Feb 2028 → 29 Mar 2028. |
| `test_monthly_mar_31_to_apr_30` | Due 31 Mar → 30 Apr. |
| `test_monthly_dec_to_jan_next_year` | Due 31 Dec 2026 → 31 Jan 2027. |
| `test_done_early_moves_one_step` | Due 20 Oct (future), today 9 Oct, daily → 21 Oct. |
| `test_overdue_daily_catches_up_to_today` | Due 30 Sep, today 9 Oct, daily → 9 Oct. |
| `test_overdue_weekly_catches_up_to_next_weekday` | Due Mon 14 Sep, today Fri 9 Oct → Mon 12 Oct. |
| `test_overdue_weekly_lands_on_today` | Due Fri 2 Oct, today Fri 9 Oct → 9 Oct (exactly on today, not 16 Oct). |
| `test_overdue_monthly_counts_from_original_day` | Due 31 Jan 2026, today 9 Mar 2026 → 31 Mar 2026 (not 28 Mar). |
| `test_overdue_monthly_needs_one_more_month` | Due 15 Jan 2026, today 20 Mar 2026 → 15 Apr 2026 (the first guess, 15 Mar, is before today). |
| `test_very_old_due_date_is_fast` | Due 1 Jan 0001, daily, today 9 Oct 2026 → 9 Oct 2026 (this would be ~740,000 loop steps). |
| `test_last_possible_date_returns_none` | Due 31 Dec 9999, daily → `None`; monthly → `None`. No crash. |
| `test_never_raises` | `repeat = ""` raises `ValueError`. |

### Unit — `todos/tests/unit/test_models.py`

| Test | What it checks |
|---|---|
| `test_repeat_without_due_date_is_invalid` | `Todo(repeat="weekly").clean()` raises `ValidationError`, with the error on `repeat`. |
| `test_repeat_with_due_date_is_valid` | With a due date, `clean()` does not raise. |

### Integration — `todos/tests/integration/test_views.py`, new class `RecurringTests`

| Test | What it checks |
|---|---|
| `test_add_a_repeating_todo` | Posting `repeat=weekly` with a due date saves it. |
| `test_add_repeat_without_due_date_shows_error` | Nothing saved; the page shows "A repeating to-do needs a due date". |
| `test_edit_cannot_remove_due_date_of_repeating_todo` | *If #4 is merged.* Edit page, repeat weekly, empty due date: not saved, same error. |
| `test_done_makes_a_copy_with_next_date` | The copy has the next due date (future date, see above), is not done, and `repeated_from` is the original. The original is done. |
| `test_copy_keeps_fields` | Title, description, priority, `todo_list`, repeat, and the same tags. The original has **at least one** tag, so an empty tag copy fails the test. The original still has its tags after the copy. |
| `test_copy_stays_in_owners_list_when_member_clicks_done` | User B, a member of A's shared list, clicks Done; the copy is in A's list (so `copy.todo_list.owner` is A). |
| `test_done_on_todo_that_does_not_repeat_makes_no_copy` | Count stays 1. |
| `test_done_without_due_date_makes_no_copy` | A repeating row with no due date (made directly, skipping `clean`) → no copy, no error. |
| `test_undo_removes_copy_that_is_not_done` | After Done, Undo: one to-do left, and the message is shown. |
| `test_done_undo_done_makes_one_new_copy` | Check the row count **after each click**: 2, then 1, then 2. At the end, exactly one row has `repeated_from` = the original. |
| `test_undo_keeps_copy_that_is_done` | The copy is done; Undo on the original keeps it; Done again on the original makes **no** new copy (count stays the same). This is the test for "no duplicates". |
| `test_deleted_copy_is_made_again` | Delete the copy, Undo and Done on the original → a new copy. |
| `test_deleting_original_keeps_copy` | Delete the done original: the copy is still there, with `repeated_from` empty. |
| `test_other_user_cannot_toggle_repeating_todo` | User C (not owner, not member) gets 404, the to-do is still not done, and no copy is made. |
| `test_list_shows_repeat_text` | The page contains "Repeats every Monday" for a weekly to-do due on a Monday. |

No test for two requests at the same moment: the Django test client sends one request at a time,
so such a test would not really test anything. The `UNIQUE` rule and the `IMMEDIATE` setting are
the protection.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

1. **Unit tests for the date math.** Write `test_recurrence.py`. Run `make test`; they fail,
   because `todos/recurrence.py` does not exist.
2. **Write `todos/recurrence.py`.** `add_months` with `calendar.monthrange`; `next_due_date`
   computes the number of steps directly (no loop; see "The next due date"). Run `make test`; the
   unit tests pass.
3. **Model tests**, then the model: `Repeat`, `repeat`, `repeated_from`, `clean()`,
   `make_next_copy(today)`.
4. **Migration:** `uv run python manage.py makemigrations`, then
   `uv run python manage.py migrate`. Do not edit the file by hand.
5. **Integration tests** (the table above). Show them failing.
6. **Form, view and setting:** add `repeat` to `TodoForm`; change `todo_toggle` as described (read
   the to-do inside `transaction.atomic()`); add `transaction_mode` to `config/settings.py`. Keep
   `POST` only, and keep the 404 check for other users.
7. **Templates:** the select in the add form, the "Repeats ..." text, the messages block if
   missing.
8. **Check it in a real browser** with `make run`: add a weekly to-do, click Done, see the copy,
   click Undo, see the message. Also on a narrow window (the add form now has one more field; it
   must still wrap well on a phone).
9. **Docs:** `AGENTS.md` and `README.md`.
10. **`make check`**, then commit.

In the pull request, say honestly which tests could not be "shown failing" in a meaningful way:
`test_done_on_todo_that_does_not_repeat_makes_no_copy` and
`test_other_user_cannot_toggle_repeating_todo` already pass before the change.

## Open questions

1. **Month-end drift.** Is it OK that 31 Jan → 28 Feb → 28 Mar? The fix is one more field, for
   example `repeat_day` (the wanted day of the month), copied to every copy. Suggestion: accept
   the drift now, and fix it only if someone asks.
2. **Overdue daily to-do, done today: copy due today, or tomorrow?** This plan says "today or
   later", so a daily to-do due yesterday and done today gets a copy due **today** — the person
   may feel they already did today's. The other choice is "after today" (copy due tomorrow).
   Suggestion: keep "today or later", because for weekly and monthly it is clearly right, and one
   rule for all three is simpler.

## Review

Changes made in review:

- `owner` removed from "What is copied": after #10 the owner is `todo.todo_list.owner`; copying
  `todo_list` is enough. Field name fixed from `list` to `todo_list`.
- Sharing question removed: #18 shares per list (`TodoList.members`), so nothing more to copy.
- Date math: no loop. A due date in the year 1 would loop ~740,000 times in one request.
- Date math: 31 Dec 9999 + 1 day is an `OverflowError` (checked); now returns `None`, no copy.
- `repeat` field written out, with `blank=True`; without it "Never" (`""`) fails validation.
- `clean()`: said clearly that `save()`/`create()` do not run it, that both fields must be in
  `TodoForm`, and that the error goes on `repeat`.
- Race: the to-do is now read inside `transaction.atomic()`. Before, the flip used an old value.
- Race on SQLite: checked that a second writer gets "database is locked" at once (an error page),
  and the `OneToOneField` + `get_or_create` "retry" never runs. Added
  `transaction_mode: "IMMEDIATE"` (Django 5.1+) so the second request waits.
- The two-tabs row in the walk-through was wrong: with a flip, the second "Done" is an Undo, not
  a second copy. Fixed.
- `get_or_create` dropped: it cannot set tags only on a new copy, and the plan had it in the view
  while also saying all copy logic is in `make_next_copy`. Now `make_next_copy` does it all.
- Undo now deletes the copy only if it is still in the same list (a member must not delete a to-do
  in a list not shared with them).
- Integration tests: dates counted from `timezone.localdate()`; fixed dates would fail after
  12 Oct 2026.
- `test_done_undo_done_...` passed even if Undo deleted nothing; now checks the count after each
  click. `test_copy_keeps_fields` passed with no tags at all; now needs at least one tag.
- Added unit tests: Feb 29, landing exactly on today, the "one more month" case, the year 1, the
  year 9999. Added integration tests: edit cannot clear the due date, deleting the original.
- Cut: the CUJ browser test (integration tests cover every rule; a manual check is enough), and
  the admin change (the admin already shows the field).
- Messages block goes in `base.html` (as #19 says), not in `todo_list.html`.

## Decided by the person (2026-10-09)

The plan is **approved**.

- Month-end drift is accepted (31 Jan → 28 Feb → 28 Mar).
- CHANGE to the plan: the copy is always due strictly AFTER today, for all three rules. A daily to-do that is late and done today gets its copy due tomorrow, not today. The rule becomes: at least one step from the due date, and the first date in the series that is after today. Update `next_due_date` and its unit tests to match (a date that lands exactly on today must move one more step).
