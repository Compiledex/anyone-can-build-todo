from django.contrib import admin

from .models import Subtask, Todo, TodoList


@admin.register(TodoList)
class TodoListAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    filter_horizontal = ["members"]


class SubtaskInline(admin.TabularInline):
    """The steps of a to-do, on the to-do's admin page."""

    model = Subtask
    extra = 0


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ["title", "todo_list", "done", "created_at"]
    list_filter = ["todo_list", "done"]
    inlines = [SubtaskInline]
