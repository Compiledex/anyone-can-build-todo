# Plan: Undo keeps the next copy when some of its steps are done

Status: **approved** (2026-10-11, by the orchestrator for the person), not started.

Builds on: **recurring** (`Todo.make_next_copy`, `Todo.get_next_copy`, the Undo rule in
`todo_toggle`), **subtasks** (#16, `Subtask`, the step views `subtask_toggle` and friends),
**sharing** (#18, members may mark done and undo), and the **test pyramid**.

## Words used in this plan

- **Repeating to-do**: a to-do with `repeat` set (daily, weekly, monthly). Marking it done makes
  its **next copy**, a new to-do with the next due date.
- **Step** (`Subtask`): a small task inside a to-do. The copy gets the same steps, none done.
- **Cascade**: when a row is deleted, the database also deletes the rows that point to it. A
  step points to its to-do with `on_delete=models.CASCADE`, so deleting a to-do deletes its steps.

## What is wrong today

Facts, checked on `main` (commit `2dc6747`), in `todos/views.py`, `todo_toggle`:

```python
copy = todo.get_next_copy()
if copy and not copy.done and copy.todo_list_id == todo.todo_list_id:
    copy.delete()
    messages.info(request, f"The next copy, due {...}, was removed.")
```

- Undo on the original deletes the next copy when the copy is not done and is in the same list.
  It does not look at the copy's steps. So if the person (or a member) already marked some steps
  of the next copy done, one Undo click deletes that work, and the steps go with it (cascade).
  There is no way to get it back.
- No test checks that Undo removes the copy's steps together with the copy.
  (`test_undo_removes_copy_that_is_not_done` in `todos/tests/integration/test_views.py` only
  makes a to-do with no steps.)

## Goal

Undo never throws away work. When some steps of the next copy are already done, Undo keeps the
copy and says so in a message. When no step of the copy is done, Undo removes the copy and its
steps, as today, and a test now checks that the steps are gone too.

## Decisions

### 1. The rule: keep the copy when any of its steps is done

Undo on a repeating to-do now looks at its next copy like this (the first rule that matches wins):

| The next copy | What Undo does | Message |
|---|---|---|
| none | nothing more | none (as today) |
| done | keeps it | none (as today, `test_undo_keeps_copy_that_is_done`) |
| in another list | keeps it | none (as today, `test_undo_keeps_copy_in_another_list`) |
| not done, same list, **at least one step done** | **keeps it (new)** | `The next copy, due 18 Oct 2026, was kept, because some of its steps are done.` |
| not done, same list, no step done (or no steps) | deletes it and its steps | `The next copy, due 18 Oct 2026, was removed.` (as today) |

Reasons:

- **A done step is work.** Deleting it on one click, with no way back, is the bug. A copy whose
  steps are all not done holds nothing the person did; it is exactly what Done made, so removing
  it is still right.
- **Only steps, not edits.** Someone could also have edited the copy's title, notes, priority or
  tags. We do not check that: the app does not remember what the copy looked like when it was
  made, so "was it edited?" would need a new field (a migration) or a fragile compare. The
  recurring plan already lists "Undo deletes a copy that was edited" as a known limit. It stays.
- **A message, also when it keeps the copy.** The person clicked Undo and expects the copy to go.
  If it stays without a word, they will think the button is broken. The new message uses the same
  start and the same date format as the old one, so the two read as a pair.
- **No message for "done" or "other list"**, as today. Those two cases are not changed by this
  plan; see "Left for the person".

### 2. The code

Only `todo_toggle` in `todos/views.py` changes, inside the same `transaction.atomic()` block:

```python
copy = todo.get_next_copy()
if copy and not copy.done and copy.todo_list_id == todo.todo_list_id:
    due = format_date(copy.due_date, "j M Y")
    if copy.subtasks.filter(done=True).exists():
        messages.info(
            request,
            f"The next copy, due {due}, was kept, because some of its steps are done.",
        )
    else:
        copy.delete()  # Its steps go with it (on_delete=CASCADE).
        messages.info(request, f"The next copy, due {due}, was removed.")
```

- `copy.subtasks.filter(done=True).exists()` is one small query (`SELECT 1 ... LIMIT 1`), only
  on Undo of a repeating to-do with a copy. It runs inside the same transaction as the delete,
  so the check and the delete see the same rows. (Two people clicking at the very same moment,
  one on a step of the copy and one on Undo, is not new: it can already happen today with Delete
  on a to-do and a click on its step. This plan does not change it.)
- The docstring of `todo_toggle` gets the new case: "...Undo removes that copy again, unless it
  is already done, in another list, or has a done step."
- No new model method. The rule is three lines and is used in one place. (If a later feature
  needs the same rule, move it into `Todo` then.)
- Done again after a kept copy makes **no** second copy: `make_next_copy` returns `None` when a
  copy exists. That already holds; a test now checks it for this case.

## Security

- **No new view, no new URL, no new form.** The rule runs inside `todo_toggle`, after
  `get_visible_todo(request.user, pk)`, so who may click Undo does not change: the owner and the
  members; a stranger or a former member gets 404 (already tested by
  `test_stranger_cannot_undo_and_remove_copy` and `test_former_member_undo_does_not_touch_list`
  in `todos/tests/integration/test_sharing.py`).
- **The copy is reached only through the to-do**, with `get_next_copy()`, and it must be in the
  same list (unchanged). The step check reads only that copy's steps (`copy.subtasks`), never
  `Subtask.objects` without a filter.
- **`POST` only**, as today (`@require_POST` is on `todo_toggle`). CSRF as today.
- **The message holds only a date** from the database, no user text, so no escaping question.
- **Back address**: still `redirect_back(request, ...)`, unchanged.

## Data and migrations

No model change, no migration. No existing row changes. Going back: revert the commit.

## Working next to

`docs/plans/nordic-letters.md` is planned at the same time. It changes `todos/queries.py`,
`todos/apps.py`, a new `todos/sqlite_functions.py`, the sort and search tests and `README.md`.
This plan changes only `todos/views.py`, `todos/tests/integration/test_views.py`,
`todos/tests/integration/test_sharing.py` and the `todos/views.py` row of `AGENTS.md`. **No
shared code file.** Both edit `AGENTS.md`, in different rows. **Merge order: nordic-letters
first, then this one** (or either; a conflict, if any, is only in `AGENTS.md`).

## Not part of this task

- Keeping a copy whose title, notes, priority or tags were edited (decision 1).
- A message when Undo keeps a copy that is done or in another list.
- A "Remove the next copy anyway" button. The person can delete the kept copy with its own
  Delete button, which already exists.
- Changing what Done copies (steps still start not done).
- Any change to the step views (`subtask_add`, `subtask_toggle`, `subtask_delete`).

## Changes to files

| File | Change |
|---|---|
| `todos/views.py` | `todo_toggle`: the new "keep the copy when a step is done" branch and message (decision 2); the docstring. |
| `todos/tests/integration/test_views.py` | Three new tests in `RecurringTests` (see "Tests"). |
| `todos/tests/integration/test_sharing.py` | One new test in `MemberCanTests` (see "Tests"); add `Subtask` to the `from todos.models import ...` line. |
| `AGENTS.md` | `todos/views.py` row, the toggle sentence: "Undo deletes the copy (and its steps) if it is not done, still in the same list, and none of its steps is done, with a message; if a step is done, it keeps the copy and says so." Also the intro paragraph: "and "Undo" removes that copy again" gets "(unless a step of the copy is already done)". |
| `README.md` | Nothing: it does not describe what Undo does to a copy. |

## Steps

1. **Tests first.** Add the four tests. Run `make integration`:
   `test_undo_keeps_copy_with_a_done_step`, `test_done_after_kept_copy_makes_no_second_copy` and
   `test_member_undo_keeps_copy_with_a_done_step` fail (today the copy is deleted).
   `test_undo_removes_copy_and_its_steps` passes already (it adds the missing check for today's
   behavior). Show the person the failures.
2. Change `todo_toggle` in `todos/views.py`.
3. `make test`: all pass, also the old recurring and sharing tests.
4. Update `AGENTS.md`.
5. `make check`, then commit. In the last commit, set the Status line of this plan to
   `**done** (<date>)`.

## Tests

All in the integration layer: the rule needs the database and the view, and a person notices it
through the page. Each test uses the helpers that are already there: `RecurringTests` in
`test_views.py` has `self.weekly` ("Water the plants", weekly, due in 30 days), `toggle(todo,
client=None)`, `copies_of(todo)` and `messages_of(response)`; `test_sharing.py` has
`make_weekly_milk()`, `self.url(name, pk)` and `messages_of(response)`, with bob as a member of
alice's "Groceries". A step is marked done the way a person does it: `POST` to
`reverse("subtask_toggle", args=[step.pk])`.

### Integration: `todos/tests/integration/test_views.py`, class `RecurringTests`

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_undo_removes_copy_and_its_steps` | `self.weekly` gets two steps ("Fill the can", "Check the soil"). Done: the copy has two steps, none done. Undo: the copy is gone, `Subtask.objects.filter(todo_id=copy_pk)` is empty, `self.weekly` still has its two steps, and the message is "...was removed." | A keep rule that also keeps a copy whose steps are all not done (for example `copy.subtasks.exists()` instead of `filter(done=True).exists()`). |
| `test_undo_keeps_copy_with_a_done_step` | Two steps; Done; mark the copy's first step done with `subtask_toggle`; Undo. `self.weekly` is not done; the copy still exists, with both steps, the first still done; the only message is `The next copy, due <date>, was kept, because some of its steps are done.` (date as in `test_undo_removes_copy_that_is_not_done`). | Today's code (the copy and the done step are deleted), or keeping the copy without a message. |
| `test_done_after_kept_copy_makes_no_second_copy` | The same start as the test above, then Done again on `self.weekly`: `copies_of(self.weekly).count()` is 1, and `Todo.objects.count()` is 2. | A change that makes a new copy whenever Undo did not delete one (a duplicate). |

The old `test_undo_removes_copy_that_is_not_done` (no steps: removed, with the message) stays and
must still pass; it is the "something does happen" case for a copy with no steps.

### Integration: `todos/tests/integration/test_sharing.py`, class `MemberCanTests` (`self.client` is bob, a member)

| Test | What it checks | The break that makes it fail |
|---|---|---|
| `test_member_undo_keeps_copy_with_a_done_step` | `make_weekly_milk()`, add one step to milk; bob marks milk done (a copy is made); bob marks the copy's step done; bob clicks Undo on milk: it redirects to the list, milk is not done, the copy and its done step still exist, and there is one message. | The rule only applying to the owner, or a member's Undo deleting the copy. |

The stranger case needs no new test: `test_stranger_cannot_undo_and_remove_copy` already checks
that a stranger gets 404 and the copy stays, and the view still finds the to-do with
`get_visible_todo` first. No unit test (the rule is a database question) and no CUJ test (the
page only shows one more message).

## Decided by the orchestrator for the person (2026-10-11, person away)

- **Keep the copy when any of its steps is done.** Do not check for edits to the title, notes,
  priority or tags (that needs a new field or a guess).
- **Say so in a message**: `The next copy, due <date>, was kept, because some of its steps are
  done.`
- **The rule stays in `todo_toggle`**, not in a new model method.

## Left for the person

- **Should Undo also keep a copy that was edited** (title, notes, priority, tags)? Not done here;
  it would need a new field that remembers whether the copy was changed. Recommended: no, unless
  it happens to you in practice.
- **A message when Undo leaves a done copy, or a copy in another list**, in place. Today it says
  nothing in those two cases. Recommended: leave it; it is rare.

## Review

Self-review by the planner (2026-10-11), reading the plan as a stranger would, against the real
code on `main` (`2dc6747`):

- Checked every name: `todo_toggle`, `get_next_copy`, `make_next_copy`, `Subtask.done`,
  `subtask_toggle` (URL name `subtask_toggle`, `/subtasks/<pk>/toggle/`), `format_date`,
  `RecurringTests` (`self.weekly`, `toggle`, `copies_of`, `messages_of`), and in
  `test_sharing.py` `MemberCanTests` (`self.client` is bob), `make_weekly_milk`, `url`,
  `messages_of`. All exist.
- Fixed: `test_sharing.py` does not import `Subtask` today; the plan now says to add it.
- Fixed: the member test is placed in `MemberCanTests`, where `make_weekly_milk` lives.
- Fixed: a sentence about two clicks at the same moment claimed more than the code guarantees
  (`subtask_toggle` is not in a transaction). It now only says that this plan does not change
  that case.
- Checked: `test_undo_removes_copy_and_its_steps` passes on today's code. That is on purpose (it
  is the missing test), and the plan says which break makes it fail. The three other new tests
  fail on today's code, because today the copy is deleted.
- Checked: Done after a kept copy cannot make a duplicate (`make_next_copy` returns `None` when
  a copy exists), and a test now covers it.
