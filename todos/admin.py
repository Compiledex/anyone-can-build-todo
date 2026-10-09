from django.contrib import admin

from .models import Todo


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "done", "created_at"]
    list_filter = ["owner", "done"]
