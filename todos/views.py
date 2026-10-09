from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import TodoForm, TodoListForm
from .models import Todo, TodoList

# Every view finds a list or a to-do in one of two ways, and nothing else:
#   get_object_or_404(TodoList, pk=pk, owner=request.user)
#   get_object_or_404(Todo, pk=pk, todo_list__owner=request.user)
# So another person's list or to-do is always 404.


def render_list_page(request, the_list, form):
    """The list page: this list's to-dos, the add form, and the person's lists.

    The one place that builds the list page. The form is empty, or has the
    errors of a bad add.
    """
    return render(
        request,
        "todos/todo_list.html",
        {
            "the_list": the_list,
            "todos": the_list.todos.all(),
            "my_lists": request.user.todo_lists.all(),
            "form": form,
        },
    )


@require_GET
def todo_list(request):
    """Only sends the browser on: to the oldest list, or to "New list"."""
    the_list = request.user.todo_lists.first()
    if the_list is None:
        return redirect("list_create")
    return redirect(the_list)


@require_GET
def list_detail(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)
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
        {"form": form, "has_lists": request.user.todo_lists.exists()},
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
def todo_add(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)
    form = TodoForm(request.POST)
    if form.is_valid():
        todo = form.save(commit=False)
        todo.todo_list = the_list  # Only from the address, never from the form.
        todo.save()
        return redirect(the_list)
    return render_list_page(request, the_list, form)


@require_POST
def todo_toggle(request, pk):
    todo = get_object_or_404(Todo, pk=pk, todo_list__owner=request.user)
    todo.done = not todo.done
    todo.save()
    return redirect(todo.todo_list)


@require_POST
def todo_delete(request, pk):
    todo = get_object_or_404(Todo, pk=pk, todo_list__owner=request.user)
    the_list = todo.todo_list
    todo.delete()
    return redirect(the_list)
