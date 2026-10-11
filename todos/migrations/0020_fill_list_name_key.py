# A data migration: it changes rows, not the table. Written by hand on purpose.
# todolist_name_key (the field), this file and list_name_key_unique (the rule)
# are a set: keep all three.

import unicodedata

from django.db import migrations

# The longest list name (TodoList.name max_length).
MAX_NAME_LENGTH = 100


def frozen_casefold(text):
    """A copy of todos.sqlite_functions.casefold, so this file never changes.

    NFC first (a Mac can send "å" as "a" plus a ring), then str.casefold().
    It must give the same key as TodoList.save().
    """
    return unicodedata.normalize("NFC", text).casefold()


def numbered_name(name, number):
    """ "<name> (<number>)", cut so the whole fits in MAX_NAME_LENGTH.

    Spaces at the end of the cut name are removed, so never "name  (2)".
    """
    suffix = f" ({number})"
    return name[: MAX_NAME_LENGTH - len(suffix)].rstrip() + suffix


def fill_name_key(apps, schema_editor):
    """Give every list its key; rename a list whose key its owner already has.

    Per owner, the oldest list (created_at, then pk) keeps its name. A newer
    one with the same key becomes "<name> (2)", "(3)", ...: the smallest
    number whose key that owner does not have yet (checked against all the
    owner's keys, also the ones given out by this migration). Its to-dos,
    members and id do not change. It uses the model as it was at this
    migration (apps.get_model), never todos.models.
    """
    TodoList = apps.get_model("todos", "TodoList")
    lists = list(TodoList.objects.order_by("owner_id", "created_at", "pk"))
    keys_of_owner = {}
    for the_list in lists:
        keys_of_owner.setdefault(the_list.owner_id, set()).add(
            frozen_casefold(the_list.name)
        )
    seen = set()  # (owner, key) pairs already kept
    for the_list in lists:
        key = frozen_casefold(the_list.name)
        if (the_list.owner_id, key) in seen:
            taken = keys_of_owner[the_list.owner_id]
            number = 2
            while frozen_casefold(numbered_name(the_list.name, number)) in taken:
                number += 1
            the_list.name = numbered_name(the_list.name, number)
            key = frozen_casefold(the_list.name)
            taken.add(key)
            print(f"Renamed list {the_list.pk} to “{the_list.name}”.")
        seen.add((the_list.owner_id, key))
        the_list.name_key = key
        the_list.save(update_fields=["name", "name_key"])


class Migration(migrations.Migration):
    dependencies = [
        ("todos", "0019_todolist_name_key"),
    ]

    operations = [
        # Going back does nothing: the old names cannot be known, and the new
        # names are still valid. 0019 going back drops the key.
        migrations.RunPython(fill_name_key, migrations.RunPython.noop),
    ]
