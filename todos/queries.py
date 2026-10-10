"""The to-dos a list page shows, from the query in the address.

Every function here gets a starting set of to-dos (`todos`) that the person
may see, and only makes it smaller. Never start from `Todo.objects` here:
that would be every user's to-dos.
"""

from urllib.parse import urlencode

from django.db.models import F, Q
from django.db.models.functions import Lower

DEFAULT_SORT = "created"

# The only orders a list page can have. key: (label in the menu, the order).
# The key from the address is only used to look up an entry here; the text
# from a request never goes to order_by itself. Every order ends with
# "created_at", "pk", so to-dos with equal values always keep the same order.
SORT_OPTIONS = {
    "created": ("Created", ("created_at", "pk")),
    # No date is the least urgent, so last (SQLite would put NULL first).
    "due": ("Due date", (F("due_date").asc(nulls_last=True), "created_at", "pk")),
    # Priority is 1 Low, 2 Medium, 3 High, never empty: biggest first.
    "priority": ("Priority", (F("priority").desc(), "created_at", "pk")),
    # Lower ignores case, but only for A-Z on SQLite.
    "title": ("Title", (Lower("title"), "created_at", "pk")),
    # The order the people of the list chose by drag and drop or Move (#15).
    "manual": ("Manual", ("position", "created_at", "pk")),
}


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


def chosen_sort(form):
    """The sort key from a checked TodoQueryForm, or the default.

    It is always a key of SORT_OPTIONS: the ChoiceField accepts nothing else.
    """
    return form.cleaned_data.get("sort") or DEFAULT_SORT


def can_reorder(form):
    """True when the page may show drag handles and Move buttons.

    Only in the manual order, with no search and no filter: then every to-do
    of the list is shown, so a new order never has to guess where hidden rows
    go. A form that is not valid never allows it.
    """
    if not form.is_valid():
        return False
    data = form.cleaned_data
    return chosen_sort(form) == "manual" and not data["q"] and not data["status"]


def apply_list_query(todos, form):
    """Apply every valid field of a TodoQueryForm to `todos`, then sort them.

    A field that is not valid is left out of cleaned_data, so it is ignored;
    the other fields still work. It always sorts, also for the default, so the
    page never depends on the model's Meta.ordering.
    """
    form.is_valid()
    data = form.cleaned_data
    todos = search(todos, data.get("q", ""))
    todos = filter_by_status(todos, data.get("status", ""))
    return todos.order_by(*SORT_OPTIONS[chosen_sort(form)][1])


def list_query(data, **changes):
    """The part after "?" for the list page: the cleaned values, with some changed.

    Only values that are set are kept. Returns "" when nothing is set.
    `data` is a form's cleaned_data, so junk like `?foo=bar` is never copied.
    """
    params = {key: value for key, value in {**data, **changes}.items() if value}
    return "?" + urlencode(params) if params else ""
