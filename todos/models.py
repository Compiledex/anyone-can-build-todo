from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone

from .recurrence import next_due_date
from .tags import MAX_TAG_LENGTH


class TodoListQuerySet(models.QuerySet):
    def visible_to(self, user):
        """The lists this user owns, plus the lists shared with them.

        `distinct()` is needed: the join with the members table gives the owner
        one row for each member, and get_object_or_404 would then fail with a
        500 error.
        """
        return self.filter(Q(owner=user) | Q(members=user)).distinct()


class TodoList(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="todo_lists",
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    # The people the owner shared this list with. The owner is never a member.
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="shared_lists", blank=True
    )

    objects = TodoListQuerySet.as_manager()

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


class Tag(models.Model):
    """A short label on to-dos, like #work. Private to its owner.

    The name is always lower case and has no `#` (see tags.parse_tags).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
    )
    name = models.CharField(max_length=MAX_TAG_LENGTH)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"], name="unique_tag_name_per_owner"
            ),
        ]

    def __str__(self):
        return f"#{self.name}"


class Todo(models.Model):
    # A bigger number is more important, so ordering by -priority gives High first.
    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    # How often a to-do comes back. "Never" is "", so a to-do that does not
    # repeat has an empty value, and the select has no "---------" line.
    class Repeat(models.TextChoices):
        NEVER = "", "Never"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

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
    # "Notes" on the page. No note is "", never NULL. The form checks max_length.
    description = models.TextField(max_length=2000, blank=True, default="")
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.MEDIUM
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="todos")
    # blank=True is needed, or a form refuses "Never" ("").
    repeat = models.CharField(
        max_length=10, choices=Repeat.choices, default=Repeat.NEVER, blank=True
    )
    # On a copy made by make_next_copy: the to-do it was copied from. One-to-one,
    # so the database allows at most one copy of each to-do. The other side is
    # `todo.next_copy`. If the original is deleted, this becomes empty.
    repeated_from = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_copy",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title

    def set_tags(self, names):
        """Make this to-do's tags exactly these clean names.

        The tags belong to the owner of the list, never to the person who is
        editing, so tags never leak between users.
        """
        owner = self.todo_list.owner
        tags = [Tag.objects.get_or_create(owner=owner, name=name)[0] for name in names]
        self.tags.set(tags)

    def subtask_progress(self):
        """(number done, number of steps). Uses the prefetched steps, so no new query.

        Never self.subtasks.filter(...).count(): that skips the prefetch and asks
        the database again for every to-do.
        """
        steps = self.subtasks.all()
        return sum(1 for step in steps if step.done), len(steps)

    def is_overdue(self, today=None):
        """True when the due date has passed and the to-do is not done.

        Due today is not overdue. `today` is for tests; the page uses the real date.
        """
        if self.done or self.due_date is None:
            return False
        if today is None:
            today = timezone.localdate()
        return self.due_date < today

    def clean(self):
        # Runs in a ModelForm's is_valid(), never in save() or create().
        if self.repeat and self.due_date is None:
            raise ValidationError(
                {
                    "repeat": ValidationError(
                        "A repeating to-do needs a due date.", code="needs_due_date"
                    )
                }
            )

    def get_next_copy(self):
        """The copy made from this to-do, or None."""
        try:
            return self.next_copy
        except ObjectDoesNotExist:
            return None

    def make_next_copy(self, today):
        """Make the next copy of a repeating to-do, and return it.

        Returns None, and makes nothing, when the to-do does not repeat, has no
        due date, has no next date (after 31 Dec 9999), or already has a copy.
        The copy is in the same list, so it has the same owner and members.
        A new field that a copy should keep is added here, and only here.
        """
        if not self.repeat or self.due_date is None:
            return None
        if self.get_next_copy() is not None:
            return None
        due_date = next_due_date(self.due_date, self.repeat, today)
        if due_date is None:
            return None
        copy = Todo.objects.create(
            todo_list=self.todo_list,
            title=self.title,
            description=self.description,
            priority=self.priority,
            repeat=self.repeat,
            due_date=due_date,
            repeated_from=self,
        )
        # The same Tag rows; they already belong to the list owner.
        copy.tags.set(self.tags.all())
        # The same steps, in the same order, none of them done yet.
        Subtask.objects.bulk_create(
            Subtask(todo=copy, title=step.title) for step in self.subtasks.all()
        )
        return copy


class Subtask(models.Model):
    """A small step inside a to-do, like "Pack books" in "Move house".

    It has no owner and no list: whoever may see or change its to-do may see or
    change its steps. A step has no steps (one level only).
    """

    todo = models.ForeignKey(Todo, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.title
