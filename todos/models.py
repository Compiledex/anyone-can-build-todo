from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone


class TodoList(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="todo_lists",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            # One person cannot have "Work" and "work". On SQLite this ignores
            # case only for A-Z, the same as `name__iexact` in TodoListForm.
            models.UniqueConstraint(
                Lower("name"), "owner", name="unique_list_name_per_owner"
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("list_detail", args=[self.pk])


class Todo(models.Model):
    # The owner of a to-do is the owner of its list: todo.todo_list.owner.
    todo_list = models.ForeignKey(
        TodoList,
        on_delete=models.CASCADE,
        related_name="todos",
    )
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    def is_overdue(self, today=None):
        """True when the due date has passed and the to-do is not done.

        Due today is not overdue. `today` is for tests; the page uses the real date.
        """
        if self.done or self.due_date is None:
            return False
        if today is None:
            today = timezone.localdate()
        return self.due_date < today
