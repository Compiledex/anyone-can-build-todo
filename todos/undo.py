"""Undo for Delete on one to-do: a snapshot in the session, made again on Undo.

Delete really deletes the row. Before that, take_snapshot() copies the to-do
(every field, its tag names and its steps) into plain JSON data, and the view
keeps it in request.session[SESSION_KEY]. Only the last delete is kept, only
for UNDO_SECONDS, and only for the user who deleted it. restore() makes the
to-do again with its old id.
"""

import datetime

from django.utils.dateparse import parse_datetime

from .models import Subtask, Todo

SESSION_KEY = "undo_delete"
UNDO_SECONDS = 15 * 60

# Every concrete field of Todo, by its attname (todo_list_id, not todo_list).
# A unit test checks this is complete, so a new field cannot be forgotten.
SNAPSHOT_FIELDS = [
    "id",
    "todo_list_id",
    "title",
    "done",
    "created_at",
    "due_date",
    "description",
    "priority",
    "repeat",
    "repeated_from_id",
    "position",
    "reminded_on",
    "copy_fingerprint",
]


def _to_json(value):
    """Dates and times as ISO text: the session is stored as JSON."""
    if isinstance(value, datetime.date):  # Also a datetime.
        return value.isoformat()
    return value


def take_snapshot(todo, user, now):
    """Plain JSON data for one to-do, to make it again with restore().

    Every concrete Todo field (see SNAPSHOT_FIELDS), the tag names, and the steps
    (title and done, in their order). Dates as ISO text: the session is JSON.
    """
    snapshot = {name: _to_json(getattr(todo, name)) for name in SNAPSHOT_FIELDS}
    next_copy = todo.get_next_copy()
    snapshot["next_copy"] = next_copy.pk if next_copy else None
    snapshot["tags"] = list(todo.tags.values_list("name", flat=True))
    snapshot["steps"] = [[step.title, step.done] for step in todo.subtasks.all()]
    snapshot["user"] = user.pk
    snapshot["deleted_at"] = now.isoformat()
    return snapshot


def is_expired(snapshot, now):
    """True when the delete was more than UNDO_SECONDS ago."""
    deleted_at = parse_datetime(snapshot["deleted_at"])
    return (now - deleted_at).total_seconds() > UNDO_SECONDS


def current_snapshot(session, user, now):
    """The snapshot this user may still undo, or None."""
    snapshot = session.get(SESSION_KEY)
    if not snapshot or snapshot.get("user") != user.pk or is_expired(snapshot, now):
        return None
    return snapshot


def drop_expired(session, now):
    """Remove a snapshot that is too old, so old to-do text does not stay around."""
    snapshot = session.get(SESSION_KEY)
    if snapshot and is_expired(snapshot, now):
        del session[SESSION_KEY]


def created_at(snapshot):
    return parse_datetime(snapshot["created_at"])


def restore(snapshot, the_list):
    """Make the to-do again in `the_list`, with its old id. Returns the Todo.

    The caller has checked, inside the same transaction, that no row has this id.
    """
    fields = {}
    for name in SNAPSHOT_FIELDS:
        field = Todo._meta.get_field(name)
        fields[name] = field.to_python(snapshot[name])
    fields["todo_list_id"] = the_list.pk
    # The one-to-one link to the original, only when that is still free.
    original = fields.pop("repeated_from_id")
    fields["repeated_from_id"] = (
        original
        if original is not None
        and Todo.objects.filter(
            pk=original, todo_list=the_list, next_copy__isnull=True
        ).exists()
        else None
    )
    todo = Todo(**fields)
    todo.todo_list = the_list
    # A pk is set, so save() keeps the old position (it only sets one for a new pk).
    todo.save(force_insert=True)
    # auto_now_add wrote "now": put the old time back, so the order is the same.
    Todo.objects.filter(pk=todo.pk).update(created_at=fields["created_at"])
    todo.created_at = fields["created_at"]
    todo.set_tags(snapshot["tags"])  # The list owner's tags, never the user's.
    Subtask.objects.bulk_create(
        Subtask(todo=todo, title=title, done=done) for title, done in snapshot["steps"]
    )
    # The copy made from it lost its link at the delete (SET_NULL): give it back.
    if snapshot["next_copy"] is not None:
        Todo.objects.filter(
            pk=snapshot["next_copy"], todo_list=the_list, repeated_from__isnull=True
        ).update(repeated_from=todo)
    return todo
