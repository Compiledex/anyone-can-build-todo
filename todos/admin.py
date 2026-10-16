from django.contrib import admin

from .admin_log import NoNamesInLog
from .models import Subtask, Todo, TodoList


@admin.register(TodoList)
class TodoListAdmin(NoNamesInLog, admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    filter_horizontal = ["members"]


class SubtaskInline(admin.TabularInline):
    """The steps of a to-do, on the to-do's admin page.

    It writes no log row of its own: the to-do's row names the steps, and
    NoNamesInLog hides their titles there.
    """

    model = Subtask
    extra = 0


@admin.register(Todo)
class TodoAdmin(NoNamesInLog, admin.ModelAdmin):
    list_display = ["title", "todo_list", "done", "created_at"]
    list_filter = ["todo_list", "done"]
    inlines = [SubtaskInline]
