# 0003. 404, not 403, for other people's data

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-09) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about what the app answers when a person asks for something that is not theirs.

## Context

- Addresses hold database numbers: `/lists/3/`, `/7/toggle/`. Anyone can type another number.
- **403 Forbidden** means "it exists, but you may not see it". **404 Not Found** means "there is
  nothing here".
- If the app answered 403 for someone else's list and 404 for a missing one, a stranger could try
  numbers and learn which lists exist and how many there are.
- Sharing (PR #11) added two roles: the owner and members. Some actions are for the owner alone.

## Decision

Someone else's list, to-do or step gives **404**, exactly like one that does not exist. A member
who tries an owner-only action (rename, delete, share, remove member) gets the same 404 as a
stranger.

Every view finds what it reads or changes through one of four helpers:

| Helper | Finds |
|---|---|
| `TodoList.objects.visible_to(user)` | Lists the user owns, plus lists shared with them. |
| `get_visible_todo(user, pk)`, `get_visible_subtask(user, pk)` | A to-do or step in such a list. |
| `get_object_or_404(TodoList, pk=pk, owner=request.user)` | Owner-only actions. |
| `get_object_or_404(TodoList, pk=pk, members=request.user)` | Leave (members only). |

## Consequences

- Safe: the answer never tells whether a thing exists.
- Easy to check: one helper per case, so there is one place to get right.
- Rule: every new view gets a test that another user gets 404 and that nothing changed
  (`assertOtherUserGets404` in `accounts/tests/helpers.py`).
- Rule: the 404 check comes **before** any other check. Toggle with a bad `done` value gives 400,
  but only after the 404 check, so a stranger learns nothing (PR #44).
- Cost: a 404 is less helpful when a person really lost access (for example after being removed
  from a list). Undo-delete gives a clear message in that case instead (PR #51).

## Alternatives considered

| Option | Why not |
|---|---|
| 403 for things that exist but are not yours | Tells a stranger which numbers exist. |
| Random ids (UUIDs) in the addresses *(added here, not in the plans)* | Harder to guess, but a migration for every table, and still needs the same checks. |
| A filter by owner in each view | Easy to forget once. With sharing, an owner-or-member filter also gives double rows; `visible_to` uses `distinct()` (sharing plan). |

## Source

- [`docs/plans/accounts.md`](../plans/accounts.md) (PR #7): "Someone else's to-do gives 404, not 403".
- [`docs/plans/sharing.md`](../plans/sharing.md) (PR #11): owner and members.
- `todos/models.py` (`visible_to`), `todos/views.py`, `AGENTS.md` rule "Only my data, plus what is shared with me".

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
- [Data inventory and privacy](../design/data-inventory-and-privacy.md)
