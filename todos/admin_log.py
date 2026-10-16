"""The admin log without names: no to-do title, list name, step or username.

Every ModelAdmin in this project has NoNamesInLog first (a test checks it).
Django's own log_actions() stores str(obj); these methods store a label like
"todo 42" instead, and hide the names of inline objects (steps) in the change
message. Only field labels (like "Title") stay.

The data migration 0023_blank_admin_log_names has frozen copies of log_label
and hide_names, for the rows made before this file existed.
"""

import copy
import json

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType

HIDDEN_NAME = "name not kept"


def log_label(obj):
    """ "<model name> <id>", for example "todo 42": a number, never user text."""
    model_name = obj._meta.model_name
    if obj.pk is None:
        return model_name
    return f"{model_name} {obj.pk}"


def hide_names(change_message):
    """The change message as JSON text, with every "object" value replaced by HIDDEN_NAME.

    A list (from construct_change_message) or JSON text. Anything that is not a
    JSON list of dicts (old plain text) becomes "": it could hold any text.
    "" stays "". Field labels ("fields") and model names ("name") stay.
    """
    if isinstance(change_message, str):
        if not change_message:
            return ""
        try:
            parts = json.loads(change_message)
        except ValueError:
            return ""
    else:
        parts = copy.deepcopy(change_message)
    if not isinstance(parts, list) or not all(isinstance(p, dict) for p in parts):
        return ""
    for part in parts:
        for detail in part.values():
            if isinstance(detail, dict) and "object" in detail:
                detail["object"] = HIDDEN_NAME
    return json.dumps(parts)


class NoNamesInLog:
    """Put first in the parents of every ModelAdmin: log rows keep no names."""

    def log_addition(self, request, obj, message):
        return self._log(request, [obj], ADDITION, message)[0]

    def log_change(self, request, obj, message):
        return self._log(request, [obj], CHANGE, message)[0]

    def log_deletions(self, request, queryset):
        return self._log(request, queryset, DELETION, "")

    def _log(self, request, objects, action_flag, message):
        """Like Django 5.2's LogEntry.objects.log_actions, with a label as object_repr.

        One row: save(); more: bulk_create (as Django does). Returns the rows.
        """
        message = hide_names(message)
        entries = [
            LogEntry(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(
                    obj, for_concrete_model=False
                ).pk,
                object_id=obj.pk,
                object_repr=log_label(obj)[:200],
                action_flag=action_flag,
                change_message=message,
            )
            for obj in objects
        ]
        if len(entries) == 1:
            entries[0].save()
            return entries
        return LogEntry.objects.bulk_create(entries)
