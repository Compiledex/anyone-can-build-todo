from django.contrib import admin

from .models import Todo, TodoList


@admin.register(TodoList)
class TodoListAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    filter_horizontal = ["members"]


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ["title", "todo_list", "done", "created_at"]
    list_filter = ["todo_list", "done"]
