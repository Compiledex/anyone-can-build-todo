# BUG-001: Undo after a double Delete brings the to-do back without its steps and tags

| | |
|---|---|
| Type | Bug report |
| Phase | Production |
| Written by | QA engineer (in this project: found by the adversarial code reviewer agent; written up by Claude) |
| Status | Done (fixed in PR #51 before merge) |
| Date | 2026-10-16 |
| Data | REAL |

> **What this document is.** A bug report tells everyone exactly how to see a bug, how bad it is,
> and, once fixed, why it happened and which test now stops it from coming back. A developer,
> tester or reviewer writes it when the bug is found. Without a clear report, a bug cannot be
> reproduced, and the same mistake is made again later.

- **Severity:** S2. A to-do the person wanted back comes back incomplete: its steps and tags are
  lost for good. It is not S1 because it needs two Delete requests at almost the same moment, and
  the title, notes and dates come back.
- **Found:** 2026-10-11, by the adversarial code review of the delete-undo feature, before merge.
- **Status:** Fixed in commit 57dec28, merged in PR #51 (2026-10-11). No user ever met it.

## Steps to reproduce (on the code before the fix)

1. Log in. Add a to-do "Buy milk". Give it the tag `shop` and one step "Find a bag".
2. On the list page, double-click **Delete** very fast (or send the same Delete form twice from
   two tabs at the same moment).
3. Click **Undo** in the message "Deleted “Buy milk”.".

## Expected

"Restored “Buy milk”." The to-do is back with its tag `shop` and its step "Find a bag".

## Actual

The to-do is back, but **with no tags and no steps**.

## Environment

Branch `feature/delete-undo` at commit 75b49b0 (before the review fix). SQLite with
`transaction_mode: "IMMEDIATE"` (`config/settings.py`). Any browser. The timing is too small to hit
by hand every time; the guard test below forces it.

## Root cause

Delete keeps a *snapshot* (a saved copy of the to-do, its tags and steps) in the session, so Undo
can make it again (`todos/undo.py`). Before the fix, `todo_delete` in `todos/views.py` read the
to-do **before** it opened the database transaction:

```python
todo = get_visible_todo(request.user, pk)      # read outside the transaction
the_list = todo.todo_list
with transaction.atomic():
    snapshot = undo.take_snapshot(todo, request.user, timezone.now())
    todo.delete()
```

With two requests close together:

1. Request A and request B both read the to-do (it still exists).
2. A takes a good snapshot and deletes the to-do. The delete also removes its steps and tag links
   (a *cascade*: rows that belong to it go too).
3. B now snapshots its **stale** object (a copy read before A's delete). Its steps and tags are
   already gone from the database, so B's snapshot has none.
4. B saves its snapshot in the session, over A's good one. Undo uses B's.

## Fix

Read the to-do **inside** the transaction (commit 57dec28):

```python
with transaction.atomic():
    todo = get_visible_todo(request.user, pk)
    the_list = todo.todo_list
    snapshot = undo.take_snapshot(todo, request.user, timezone.now())
    todo.delete()
```

SQLite's `IMMEDIATE` mode makes B wait until A has committed. Then B reads again, finds nothing,
and gets 404. The good snapshot stays. The same review also moved Undo's list check inside its
transaction.

## Guard test

`todos/tests/integration/test_delete_undo.py`, class `DeleteTests`,
`test_double_delete_does_not_replace_the_snapshot`. It replaces `get_visible_todo` with a version
that returns the stale object when it is called outside a transaction, as request B did. It then
checks that the second Delete gets 404 and that the snapshot still has `tags == ["shop"]` and
`steps == [["Find a bag", False]]`. It was shown failing against the old code first (PR #51,
"Review" section).

The browser journey `test_delete_and_undo` in `todos/tests/cuj/test_journeys.py` covers the normal
Delete and Undo path.

## Lessons

- Read a row inside the same transaction that changes it, when another request can change it too.
- A *race* (two requests in either order) is hard to see by hand; a test that forces the order is
  the only reliable check.

## Related documents

- [Bug triage process](README.md)
- [QA run and bug bash](../process/qa-run-and-bug-bash.md) (checklist step 19)
- Plan: [`docs/plans/delete-undo.md`](../plans/delete-undo.md); PR #51
