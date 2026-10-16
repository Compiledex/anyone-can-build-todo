"""The admin log keeps no names: replace them in the rows already there.

Written by hand (a data migration). Every row's object_repr becomes a label
like "todo 42", and the names of inline objects (steps) in change_message
become "name not kept". Field labels ("Title") stay. Nothing else changes.

frozen_label and frozen_hide_names are copies of todos/admin_log.py as it was
when this was written, so this migration never changes when that file does.
Going back does nothing: the names cannot be known again.
"""

import json

from django.db import migrations

HIDDEN_NAME = "name not kept"
CHUNK = 500


def frozen_label(row):
    """ "<model name> <id>", or "object <id>" when the content type is gone."""
    model_name = row.content_type.model if row.content_type else "object"
    if row.object_id is None:
        return model_name
    return f"{model_name} {row.object_id}"


def frozen_hide_names(change_message):
    """The JSON change message with every "object" value hidden; other text is ""."""
    if not change_message:
        return ""
    try:
        parts = json.loads(change_message)
    except ValueError:
        return ""
    if not isinstance(parts, list) or not all(isinstance(p, dict) for p in parts):
        return ""
    for part in parts:
        for detail in part.values():
            if isinstance(detail, dict) and "object" in detail:
                detail["object"] = HIDDEN_NAME
    return json.dumps(parts)


def save_chunk(LogEntry, chunk):
    LogEntry.objects.bulk_update(chunk, ["object_repr", "change_message"])


def blank_names(apps, schema_editor):
    LogEntry = apps.get_model("admin", "LogEntry")
    rows = LogEntry.objects.select_related("content_type").order_by("pk")
    chunk = []
    for row in rows.iterator(chunk_size=CHUNK):
        row.object_repr = frozen_label(row)[:200]
        row.change_message = frozen_hide_names(row.change_message)
        chunk.append(row)
        if len(chunk) == CHUNK:
            save_chunk(LogEntry, chunk)
            chunk = []
    if chunk:
        save_chunk(LogEntry, chunk)


class Migration(migrations.Migration):
    dependencies = [
        ("todos", "0022_todo_copy_fingerprint"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(blank_names, migrations.RunPython.noop),
    ]
