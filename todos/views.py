from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TodoForm
from .models import Todo


def render_list_page(request, form):
    """The list page, with this add form (empty, or with the errors of a bad add)."""
    todos = Todo.objects.all()
    return render(request, "todos/todo_list.html", {"todos": todos, "form": form})


def todo_list(request):
    return render_list_page(request, TodoForm())


@require_POST
def todo_add(request):
    form = TodoForm(request.POST)
    if form.is_valid():
        form.save()
        return redirect("todo_list")
    return render_list_page(request, form)


@require_POST
def todo_toggle(request, pk):
    todo = get_object_or_404(Todo, pk=pk)
    todo.done = not todo.done
    todo.save()
    return redirect("todo_list")


@require_POST
def todo_delete(request, pk):
    todo = get_object_or_404(Todo, pk=pk)
    todo.delete()
    return redirect("todo_list")
