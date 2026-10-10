"""The manual order of a list: read a posted order, and save it.

Drag and drop and the Move buttons both save with save_order, so there is one
way to write an order.
"""

from django.db import transaction


def parse_ids(values):
    """The posted strings as whole numbers, in the same order.

    Raises ValueError for anything that is not a whole number (also "", "-1"
    and " 2"), and for a number that is there twice. An empty list is allowed
    here; save_order checks it against the real list.
    """
    ids = []
    for value in values:
        # isascii(): isdigit() alone also accepts digits like "²" or "٣".
        if not (value.isascii() and value.isdigit()):
            raise ValueError(f"Not a to-do id: {value!r}")
        ids.append(int(value))
    if len(set(ids)) != len(ids):
        raise ValueError("A to-do id is there twice.")
    return ids


def save_order(todo_list, ids):
    """Give the to-dos of this list positions 1, 2, 3, ... in the order of `ids`.

    `ids` must be exactly the ids of the list's to-dos: every one, once, and
    nothing else. Otherwise it raises ValueError and saves nothing. An id from
    another list can never be written, because only this list's rows are read.
    The check and the save are in one transaction, so a to-do added between
    them cannot be missed.
    """
    with transaction.atomic():
        todos = {todo.pk: todo for todo in todo_list.todos.all()}
        if len(ids) != len(todos) or set(ids) != set(todos):
            raise ValueError("The order does not match the to-dos of the list.")
        for number, pk in enumerate(ids, start=1):
            todos[pk].position = number
        # One query for all rows. It skips Todo.save(), which is fine here.
        todo_list.todos.bulk_update(todos.values(), ["position"])
