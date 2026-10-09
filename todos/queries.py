"""The to-dos a list page shows, from the query in the address.

Every function here gets a starting set of to-dos (`todos`) that the person
may see, and only makes it smaller. Never start from `Todo.objects` here:
that would be every user's to-dos.
"""

from django.db.models import Q


def search(todos, q):
    """The to-dos whose title, notes or a tag name contain `q`, ignoring case.

    `icontains` escapes `%` and `_`, so they are normal letters here.
    """
    if not q:
        return todos
    # A sub-query, not a join: a to-do with two matching tags is shown once.
    # It starts from `todos` too, so it never reads other people's rows.
    with_matching_tag = todos.filter(tags__name__icontains=q).values("pk")
    return todos.filter(
        Q(title__icontains=q)
        | Q(description__icontains=q)
        | Q(pk__in=with_matching_tag)
    )


def apply_list_query(todos, form):
    """Apply every valid field of a TodoQueryForm to `todos`.

    A field that is not valid is left out of cleaned_data, so it is ignored;
    the other fields still work.
    """
    form.is_valid()
    data = form.cleaned_data
    return search(todos, data.get("q", ""))
