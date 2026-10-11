"""Values every template gets (see TEMPLATES in config/settings.py)."""

from django.utils import timezone

from . import undo


def undo_delete(request):
    """`undo_delete_tag`, `undo_delete_id` and `undo_delete_title`: the delete
    this session can undo (the title is for the button's aria-label).

    All None when there is no snapshot, it belongs to another user, or it is
    too old. base.html then shows no Undo button. Only reads the session.
    """
    snapshot = None
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        snapshot = undo.current_snapshot(request.session, user, timezone.now())
    if snapshot is None:
        return {
            "undo_delete_tag": None,
            "undo_delete_id": None,
            "undo_delete_title": None,
        }
    return {
        "undo_delete_tag": f"undo-delete-{snapshot['id']}",
        "undo_delete_id": snapshot["id"],
        "undo_delete_title": snapshot["title"],
    }
