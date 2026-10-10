"""The to-dos a list page shows, from the query in the address.

Every function here gets a starting set of to-dos (`todos`) that the person
may see, and only makes it smaller. Never start from `Todo.objects` here:
that would be every user's to-dos.
"""

from urllib.parse import urlencode

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


def filter_by_status(todos, status):
    """Only the not done ("open") or done ("done") to-dos; anything else: all."""
    if status == "open":
        return todos.filter(done=False)
    if status == "done":
        return todos.filter(done=True)
    return todos


def apply_list_query(todos, form):
    """Apply every valid field of a TodoQueryForm to `todos`.

    A field that is not valid is left out of cleaned_data, so it is ignored;
    the other fields still work.
    """
    form.is_valid()
    data = form.cleaned_data
    todos = search(todos, data.get("q", ""))
    return filter_by_status(todos, data.get("status", ""))


def list_query(data, **changes):
    """The part after "?" for the list page: the cleaned values, with some changed.

    Only values that are set are kept. Returns "" when nothing is set.
    `data` is a form's cleaned_data, so junk like `?foo=bar` is never copied.
    """
    params = {key: value for key, value in {**data, **changes}.items() if value}
    return "?" + urlencode(params) if params else ""
