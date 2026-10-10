from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import date as format_date
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import ShareForm, SubtaskForm, TodoForm, TodoListForm, TodoQueryForm
from .models import Subtask, Todo, TodoList
from .queries import apply_list_query, list_query

# A view that reads or changes a list or its to-dos finds the list with
#   get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)
# or the to-do with get_visible_todo(request.user, pk), or a step with
# get_visible_subtask(request.user, pk). That is the person's own
# lists plus the lists shared with them.
# Only rename, delete, share and remove-member are for the owner alone. They use
#   get_object_or_404(TodoList, pk=pk, owner=request.user)
# so a member gets the same 404 as a stranger.


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


def back_to_steps(todo):
    """Back to the to-do's list, with this to-do's steps open.

    Built only from numbers in the database, never from the request, so it can
    never send the browser to another website.
    """
    url = reverse("list_detail", args=[todo.todo_list_id])
    return redirect(f"{url}?open={todo.pk}#todo-{todo.pk}")


def redirect_back(request, default):
    """Go back to the safe address in POST "next", or else to `default`.

    Only a path on this site: it must start with "/" (a bare word like "foo"
    would make redirect() look for a URL name and crash), and Django's check
    refuses other sites, "//evil.example", backslashes and "javascript:".
    """
    next_url = request.POST.get("next", "")
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
    # Search and filter (and later sort) from the address. Only GET is read,
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
    # Each link keeps the other values (the search) and changes only status.
    filter_links = [
        {
            "label": label,
            "query": list_query(data, status=value),
            "current": status == value,
        }
        for value, label in [("", "All"), ("open", "Not done"), ("done", "Done")]
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


@require_GET
def todo_list(request):
    """Only sends the browser on: to the oldest own list, else to the oldest
    list shared with the person, else to "New list"."""
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
    """Done or Undo. Done on a repeating to-do makes its next copy; Undo removes
    that copy again, unless it is already done or in another list."""
    # Read the to-do inside the transaction, so a second click at the same time
    # waits and then sees the new value (see transaction_mode in settings.py).
    with transaction.atomic():
        todo = get_visible_todo(request.user, pk)
        todo.done = not todo.done
        todo.save()
        if todo.done:
            todo.make_next_copy(timezone.localdate())
        else:
            copy = todo.get_next_copy()
            if copy and not copy.done and copy.todo_list_id == todo.todo_list_id:
                copy.delete()
                messages.info(
                    request,
                    f"The next copy, due {format_date(copy.due_date, 'j M Y')}, "
                    "was removed.",
                )
    return redirect_back(request, todo.todo_list.get_absolute_url())


@require_POST
def todo_delete(request, pk):
    todo = get_visible_todo(request.user, pk)
    the_list = todo.todo_list  # Read before the delete.
    todo.delete()
    return redirect_back(request, the_list.get_absolute_url())


@require_http_methods(["GET", "POST"])
def todo_edit(request, pk):
    todo = get_visible_todo(request.user, pk)
    if request.method == "POST":
        form = TodoForm(request.POST, instance=todo)
        if form.is_valid():
            form.save()
            return redirect(todo.todo_list)
    else:
        form = TodoForm(instance=todo)
    return render(request, "todos/todo_edit.html", {"form": form, "todo": todo})


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
        messages.error(request, "A step needs a title of 1 to 200 characters.")
    return back_to_steps(todo)


@require_POST
def subtask_toggle(request, pk):
    subtask = get_visible_subtask(request.user, pk)
    subtask.done = not subtask.done
    subtask.save()  # The to-do itself does not change.
    return back_to_steps(subtask.todo)


@require_POST
def subtask_delete(request, pk):
    subtask = get_visible_subtask(request.user, pk)
    subtask.delete()
    return back_to_steps(subtask.todo)
