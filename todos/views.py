from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import date as format_date
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
    require_safe,
)

from . import undo
from .forms import ShareForm, SubtaskForm, TodoForm, TodoListForm, TodoQueryForm
from .models import Subtask, Todo, TodoList
from .ordering import parse_ids, save_order
from .queries import (
    DEFAULT_SORT,
    SORT_OPTIONS,
    apply_list_query,
    can_reorder,
    chosen_sort,
    list_query,
)

STEP_MAX_LENGTH = Subtask._meta.get_field("title").max_length

# A view that reads or changes a list or its to-dos finds the list with
#   get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)
# or the to-do with get_visible_todo(request.user, pk), or a step with
# get_visible_subtask(request.user, pk). That is the person's own
# lists plus the lists shared with them.
# Only rename, delete, share and remove-member are for the owner alone. They use
#   get_object_or_404(TodoList, pk=pk, owner=request.user)
# so a member gets the same 404 as a stranger.
# list_leave is for members alone: it uses
#   get_object_or_404(TodoList, pk=pk, members=request.user)
# so the owner and strangers get 404.


def get_visible_todo(user, pk):
    """A to-do in a list this user owns or is a member of, or 404."""
    return get_object_or_404(
        Todo, pk=pk, todo_list__in=TodoList.objects.visible_to(user)
    )


def get_visible_subtask(user, pk):
    """A step of a to-do in a list this user owns or is a member of, or 404.

    select_related loads the to-do in the same query: back_to_steps needs it.
    """
    return get_object_or_404(
        Subtask.objects.select_related("todo"),
        pk=pk,
        todo__todo_list__in=TodoList.objects.visible_to(user),
    )


def back_to_steps(todo, *, to_new_step=False):
    """Back to the to-do's list, with this to-do's steps open.

    Built only from numbers in the database, never from the request, so it can
    never send the browser to another website.

    to_new_step (after "Add step"): no #todo-<pk>, because a browser skips
    autofocus when the address names an element. Then the "New step" field of
    this to-do gets the cursor, and the browser scrolls to it. Step Done and
    Delete keep the # (the page opens at the row, the cursor does not move).
    """
    url = reverse("list_detail", args=[todo.todo_list_id])
    if to_new_step:
        return redirect(f"{url}?open={todo.pk}")
    return redirect(f"{url}?open={todo.pk}#todo-{todo.pk}")


def anchors_after_removal(pks):
    """For each row: the anchor to open after it leaves the page.

    The next row, else the row before, else the list itself ("todos").
    Only numbers from the database go in, so a fragment never holds request text.
    """
    anchors = {}
    for i, pk in enumerate(pks):
        if i + 1 < len(pks):
            anchors[pk] = f"todo-{pks[i + 1]}"
        elif i > 0:
            anchors[pk] = f"todo-{pks[i - 1]}"
        else:
            anchors[pk] = "todos"
    return anchors


def wanted_done(request):
    """The state the Done/Undo button asks for: "1" is True, "0" is False.

    Anything else, also no value, is None: the caller answers 400.
    """
    return {"1": True, "0": False}.get(request.POST.get("done"))


def redirect_back(request, default):
    """Go back to the safe address in POST "next", or else to `default`.

    Only a path on this site: it must start with "/" (a bare word like "foo"
    would make redirect() look for a URL name and crash), and Django's check
    refuses other sites, "//evil.example", backslashes and "javascript:".
    """
    next_url = request.POST.get("next", "")
    # The "/" rule already refuses every absolute URL (http://...), even one to
    # this site; require_https is only a second guard for that case.
    if next_url.startswith("/") and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return HttpResponseRedirect(next_url)
    return redirect(default)


def render_list_page(request, the_list, form):
    """The list page: this list's to-dos, the add form, and the person's lists.

    The one place that builds the list page. The form is empty, or has the
    errors of a bad add.
    """
    is_owner = the_list.owner_id == request.user.id
    # A delete that can no longer be undone: do not keep its to-do text around.
    undo.drop_expired(request.session, timezone.now())
    # Search, filter and sort from the address. Only GET is read,
    # so an invalid add (a POST) shows the whole list.
    query_form = TodoQueryForm(request.GET)
    # All tags and all steps in one query each, not one query per row.
    todos = apply_list_query(
        the_list.todos.prefetch_related("tags", "subtasks"), query_form
    )
    data = query_form.cleaned_data  # Filled by apply_list_query.
    q = data.get("q", "")
    status = data.get("status", "")
    list_url = the_list.get_absolute_url()
    # Where Done, Undo and Delete go back to: this list, with the same query.
    # Not request.get_full_path(): after a bad add that is .../add/ (POST only).
    back_url = f"{list_url}?{request.GET.urlencode()}" if request.GET else list_url
    # Where each row goes after it leaves the page (Delete, or Done in a filter).
    # list() fills the queryset's cache: todos stays a QuerySet, the template reads
    # the cache, and the number of queries does not change.
    rows = list(todos)
    anchors = anchors_after_removal([todo.pk for todo in rows])
    for todo in rows:
        todo.anchor_after_removal = anchors[todo.pk]
    # Each link keeps the other values (the search) and changes only status.
    filter_links = [
        {
            "label": label,
            "query": list_query(data, status=value),
            "current": status == value,
        }
        for value, label in [("", "All"), *TodoQueryForm.STATUS_CHOICES]
    ]
    # The hidden inputs that keep the other choices when a form is sent. Only
    # cleaned values: status is "open" or "done", the sort a key of SORT_OPTIONS.
    current_sort = chosen_sort(query_form)
    search_hidden = [("status", status)] if status else []
    if current_sort != DEFAULT_SORT:
        search_hidden.append(("sort", current_sort))  # A new search keeps the order.
    sort_hidden = [
        (name, value) for name, value in [("q", q), ("status", status)] if value
    ]
    return render(
        request,
        "todos/todo_list.html",
        {
            "the_list": the_list,
            "todos": todos,
            "query_form": query_form,
            "q": q,
            "status": status,
            "list_url": list_url,
            "back_url": back_url,
            "filter_links": filter_links,
            # The order shown, always a key of SORT_OPTIONS (#15 uses "manual").
            "current_sort": current_sort,
            "search_hidden": search_hidden,
            "sort_hidden": sort_hidden,
            # The longest title of a to-do and of a step, for maxlength.
            "title_max_length": Todo._meta.get_field("title").max_length,
            "step_max_length": STEP_MAX_LENGTH,
            # Drag handles and Move buttons: manual order, no search, no filter.
            "can_reorder": can_reorder(query_form),
            # "Show all" clears the search and the filter, but keeps the order.
            "show_all_query": list_query(data, q="", status=""),
            # A search or a filter is set: "No to-dos match" and "Show all".
            "filtering": bool(q or status),
            # Always the whole list: "Clear completed" deletes all of these.
            "done_count": the_list.todos.filter(done=True).count(),
            "my_lists": request.user.todo_lists.all(),
            "form": form,
            # Only the owner sees the members and the share form.
            "is_owner": is_owner,
            "members": the_list.members.all() if is_owner else None,
            "share_form": ShareForm(todo_list=the_list) if is_owner else None,
            # Leaves out the person's own lists, in case the admin made the
            # owner a member too.
            "shared_lists": request.user.shared_lists.exclude(
                owner=request.user
            ).select_related("owner"),
        },
    )


@login_not_required  # A visitor must see the landing page. It shows no user data.
@require_safe  # GET and HEAD only.
def todo_list(request):
    """`/`. A visitor who is not logged in sees the landing page.

    A logged-in person is only sent on: to the oldest own list, else to the
    oldest list shared with them, else to "New list".
    """
    if not request.user.is_authenticated:
        # Nothing from the database goes into this page, so it cannot show
        # anyone's lists or to-dos.
        return render(request, "todos/landing.html")
    the_list = (
        request.user.todo_lists.first()
        or TodoList.objects.visible_to(request.user).first()
    )
    if the_list is None:
        return redirect("list_create")
    return redirect(the_list)


@require_GET
def list_detail(request, pk):
    the_list = get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)
    return render_list_page(request, the_list, TodoForm())


@require_http_methods(["GET", "POST"])
def list_create(request):
    new_list = TodoList(owner=request.user)  # Never from the form.
    if request.method == "POST":
        form = TodoListForm(request.POST, instance=new_list)
        if form.is_valid():
            return redirect(form.save())
    else:
        form = TodoListForm(instance=new_list)
    return render(
        request,
        "todos/list_form.html",
        {"form": form, "has_lists": TodoList.objects.visible_to(request.user).exists()},
    )


@require_http_methods(["GET", "POST"])
def list_rename(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)
    if request.method == "POST":
        form = TodoListForm(request.POST, instance=the_list)
        if form.is_valid():
            return redirect(form.save())
    else:
        form = TodoListForm(instance=the_list)
    return render(request, "todos/list_form.html", {"form": form, "the_list": the_list})


@require_http_methods(["GET", "POST"])
def list_delete(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)
    if request.method == "POST":
        the_list.delete()  # Its to-dos are deleted too.
        return redirect("todo_list")
    return render(
        request,
        "todos/list_confirm_delete.html",
        {"the_list": the_list, "todo_count": the_list.todos.count()},
    )


@require_POST
def list_clear_completed(request, pk):
    """Delete every done to-do of this one list. Never reads to-do ids from the form."""
    # The owner and the members may clear; a stranger gets 404.
    the_list = get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)
    # delete() also counts rows deleted with each to-do, so use the Todo number only.
    _, per_model = the_list.todos.filter(done=True).delete()
    deleted = per_model.get("todos.Todo", 0)
    if deleted:
        messages.success(
            request, f"Deleted {deleted} completed to-do{pluralize(deleted)}."
        )
    else:
        messages.info(request, "No completed to-dos to delete.")
    return redirect(the_list)


@require_POST
def todo_add(request, pk):
    the_list = get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)
    form = TodoForm(request.POST)
    if form.is_valid():
        todo = form.save(commit=False)
        todo.todo_list = the_list  # Only from the address, never from the form.
        todo.save()
        return redirect(the_list)
    return render_list_page(request, the_list, form)


@require_POST
def todo_toggle(request, pk):
    """Done (POST done=1) or Undo (done=0); any other value is 400.

    The form says which state it wants, so a double click or an old tab does
    nothing when the to-do already has it: no flip, no copy, no message.
    Done on a repeating to-do makes its next copy; Undo removes that copy
    again, unless it is already done, in another list, or has a done step.
    """
    done = wanted_done(request)
    # Read the to-do inside the transaction, so a second click at the same time
    # waits and then sees the new value (see transaction_mode in settings.py).
    with transaction.atomic():
        todo = get_visible_todo(request.user, pk)  # 404 before 400: reveals nothing.
        if done is None:
            return HttpResponseBadRequest("Done must be 0 or 1.")
        if todo.done == done:
            # Already so: nothing to do.
            return redirect_back(request, todo.todo_list.get_absolute_url())
        todo.done = done
        todo.save()
        if todo.done:
            todo.make_next_copy(timezone.localdate())
        else:
            copy = todo.get_next_copy()
            if copy and not copy.done and copy.todo_list_id == todo.todo_list_id:
                due = format_date(copy.due_date, "j M Y")
                if copy.subtasks.filter(done=True).exists():
                    # A done step is work: never delete it on one click.
                    messages.info(
                        request,
                        f"The next copy, due {due}, was kept, "
                        "because a step in it is already done.",
                    )
                else:
                    copy.delete()  # Its steps go with it (on_delete=CASCADE).
                    messages.info(request, f"The next copy, due {due}, was removed.")
    return redirect_back(request, todo.todo_list.get_absolute_url())


@require_POST
def todo_delete(request, pk):
    """Delete at once, and keep a snapshot in the session for the Undo button."""
    todo = get_visible_todo(request.user, pk)
    the_list = todo.todo_list  # Read before the delete.
    with transaction.atomic():
        snapshot = undo.take_snapshot(todo, request.user, timezone.now())
        todo.delete()
    request.session[undo.SESSION_KEY] = snapshot  # Only the last delete.
    # The id in the tag ties this message to this delete (see base.html).
    messages.success(
        request, f"Deleted “{todo.title}”.", extra_tags=f"undo-delete-{snapshot['id']}"
    )
    return redirect_back(request, the_list.get_absolute_url())


@require_POST
def todo_undo_delete(request, pk):
    """Make the last deleted to-do again, for the person who deleted it.

    The session is saved after the view, outside the database transaction, so
    two posts close together can both read the snapshot. The real guard is the
    "id exists" check inside the transaction, before anything is made.
    """
    now = timezone.now()
    snapshot = request.session.get(undo.SESSION_KEY)
    if not snapshot or snapshot["id"] != pk or snapshot["user"] != request.user.id:
        # Already restored (a double click, a second tab): nothing to say.
        # Anything else (a stranger, an older delete, after logout): 404.
        todo = get_visible_todo(request.user, pk)
        return redirect_back(
            request, f"{todo.todo_list.get_absolute_url()}#todo-{todo.pk}"
        )
    del request.session[undo.SESSION_KEY]
    visible_lists = TodoList.objects.visible_to(request.user)
    the_list = visible_lists.filter(pk=snapshot["todo_list_id"]).first()
    list_url = the_list.get_absolute_url() if the_list else reverse("todo_list")
    with transaction.atomic():
        existing = Todo.objects.filter(pk=pk).first()
        if existing is not None:
            if (
                existing.todo_list_id == snapshot["todo_list_id"]
                and existing.title == snapshot["title"]
                and existing.created_at == undo.created_at(snapshot)
            ):
                # The same to-do, restored a moment ago by the other post.
                return redirect_back(request, f"{list_url}#todo-{pk}")
            # Another to-do got this id (after a table rebuild): never touch it.
            messages.error(request, "Could not undo.")
            return redirect(list_url)
        if undo.is_expired(snapshot, now):
            messages.info(request, "Too late to undo: the to-do stays deleted.")
            return redirect(list_url)
        if the_list is None:
            messages.error(
                request, "Could not undo: you can no longer see the list it was in."
            )
            return redirect("todo_list")
        todo = undo.restore(snapshot, the_list)
    messages.success(request, f"Restored “{todo.title}”.")
    return redirect_back(request, f"{list_url}#todo-{todo.pk}")


@require_http_methods(["GET", "POST"])
def todo_edit(request, pk):
    todo = get_visible_todo(request.user, pk)
    # Read before the form: a ModelForm copies a valid typed title into `todo`,
    # even when another field fails and nothing is saved.
    saved_title = todo.title
    if request.method == "POST":
        form = TodoForm(request.POST, instance=todo)
        if form.is_valid():
            form.save()
            return redirect(todo.todo_list)
    else:
        form = TodoForm(instance=todo)
    return render(
        request,
        "todos/todo_edit.html",
        {"form": form, "todo": todo, "saved_title": saved_title},
    )


@require_POST
def todo_reorder(request, pk):
    """Save a new manual order from drag and drop: id=7&id=3&id=5.

    The ids must be exactly the to-dos of this list, or nothing is saved (400).
    The JavaScript then reloads the page. The owner and the members may do it.
    """
    the_list = get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)
    try:
        save_order(the_list, parse_ids(request.POST.getlist("id")))
    except ValueError:
        return HttpResponseBadRequest("The order does not match this list.")
    return HttpResponse(status=204)  # It worked, nothing to send back.


@require_POST
def todo_move(request, pk):
    """Move up or Move down: swap the to-do with its neighbour in the manual order.

    A move that is not possible (the first to-do up) changes nothing.
    """
    direction = request.POST.get("direction")
    # Read and save in one transaction, so the order cannot change in between.
    with transaction.atomic():
        todo = get_visible_todo(request.user, pk)  # 404 before 400: reveals nothing.
        if direction not in ("up", "down"):
            return HttpResponseBadRequest("Direction must be up or down.")
        the_list = todo.todo_list
        ids = list(
            the_list.todos.order_by(*SORT_OPTIONS["manual"][1]).values_list(
                "pk", flat=True
            )
        )
        here = ids.index(todo.pk)
        there = here - 1 if direction == "up" else here + 1
        if 0 <= there < len(ids):
            ids[here], ids[there] = ids[there], ids[here]
            save_order(the_list, ids)
    # Back to the moved row, so a keyboard user does not start at the top.
    return redirect(f"{the_list.get_absolute_url()}?sort=manual#todo-{todo.pk}")


@require_POST
def list_share(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)  # Owner only.
    form = ShareForm(request.POST, todo_list=the_list)
    if form.is_valid():
        user = form.cleaned_data["username"]  # clean_username gives the User.
        the_list.members.add(user)
        messages.success(request, f"Shared with {user.username}.")
    else:
        messages.error(request, form.errors["username"][0])
    return redirect(the_list)


@require_POST
def list_member_remove(request, pk, user_id):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)  # Owner only.
    # Only a member of THIS list. Never get_object_or_404(User, ...): the answer
    # must not tell whether a user with that number exists.
    member = get_object_or_404(the_list.members, pk=user_id)
    the_list.members.remove(member)
    messages.success(request, f"{member.username} was removed.")
    return redirect(the_list)


@require_POST
def list_leave(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, members=request.user)  # Members only.
    the_list.members.remove(request.user)  # The to-dos they added stay.
    messages.success(request, "You left the list.")
    return redirect("todo_list")


@require_POST
def subtask_add(request, todo_pk):
    todo = get_visible_todo(request.user, todo_pk)
    form = SubtaskForm(request.POST)
    if form.is_valid():
        subtask = form.save(commit=False)
        subtask.todo = todo  # Only from the address, never from the form.
        subtask.save()
    else:
        messages.error(
            request, f"A step needs a title of 1 to {STEP_MAX_LENGTH} characters."
        )
    return back_to_steps(todo, to_new_step=True)


@require_POST
def subtask_toggle(request, pk):
    """Done (POST done=1) or Undo (done=0) for a step; any other value is 400.

    Setting a value twice is safe, so this needs no transaction.
    """
    subtask = get_visible_subtask(request.user, pk)  # 404 before 400.
    done = wanted_done(request)
    if done is None:
        return HttpResponseBadRequest("Done must be 0 or 1.")
    if subtask.done != done:
        subtask.done = done
        subtask.save(update_fields=["done"])  # The to-do itself does not change.
    return back_to_steps(subtask.todo)


@require_POST
def subtask_delete(request, pk):
    subtask = get_visible_subtask(request.user, pk)
    subtask.delete()
    return back_to_steps(subtask.todo)
