import hashlib
import json

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Max, Q
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone

from .recurrence import next_due_date
from .tags import MAX_TAG_LENGTH

# The fields make_next_copy copies as they are. due_date (a new date), the tags
# and the steps are copied too, and are always in the fingerprint. A field that a
# copy should keep is added here, and then it is in the fingerprint too.
COPIED_FIELDS = ("title", "description", "priority", "repeat")

# Change this when fingerprint() changes shape. Then every stored fingerprint
# differs, so every old copy counts as changed and Undo keeps it: no data is lost.
FINGERPRINT_VERSION = "v1"


def fingerprint(values, due_date, tag_names, step_titles):
    """A SHA-256 hash (64 hex characters) of what a person can change on a to-do.

    `values`: a dict with the COPIED_FIELDS. The notes have "\\r\\n" made "\\n"
    (as NoteField does), so the same text always gives the same hash. Tag names
    sorted, step titles in their order. Not done, not the steps' done state,
    not position, not reminded_on. Starts with FINGERPRINT_VERSION.
    """
    fields = [values[name] for name in COPIED_FIELDS]
    fields[COPIED_FIELDS.index("description")] = values["description"].replace(
        "\r\n", "\n"
    )
    data = [
        FINGERPRINT_VERSION,
        *fields,
        due_date.isoformat() if due_date else None,
        sorted(tag_names),
        list(step_titles),
    ]
    text = json.dumps(data, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


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
    # The place in the list's manual order: smaller comes first. Shared by
    # everyone who sees the list. Not unique: equal numbers are allowed, and
    # then created_at and pk decide. Gaps (1, 2, 4) do not matter.
    position = models.PositiveIntegerField(default=0)
    # The day this to-do was last shown in a Mac notification (todos/reminders.py),
    # so it is not shown twice on one day. Never copied by make_next_copy: a copy
    # starts never reminded. editable=False keeps it out of forms and the admin.
    reminded_on = models.DateField(null=True, blank=True, editable=False)
    # On a copy: the fingerprint of what make_next_copy made (content_fingerprint()).
    # "" on a to-do that is not a copy, and on copies made before this field existed.
    copy_fingerprint = models.CharField(
        max_length=64, blank=True, default="", editable=False
    )

    class Meta:
        ordering = ["created_at", "pk"]  # pk: a fixed order for equal times.

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """A new to-do goes last in its list's manual order.

        Here, not in a view: the add view, a recurring copy and the admin all
        make to-dos. It always sets the number for a new row, even a copied one.
        """
        if self.pk is None:
            biggest = Todo.objects.filter(todo_list_id=self.todo_list_id).aggregate(
                biggest=Max("position")
            )["biggest"]
            self.position = (biggest or 0) + 1
        super().save(*args, **kwargs)

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
        # The error is on due_date: that is the field the person must fill in.
        if self.repeat and self.due_date is None:
            raise ValidationError(
                {
                    "due_date": ValidationError(
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

    def content_fingerprint(self):
        """fingerprint() of this to-do as it is in the database now (two queries:
        the tags and the steps)."""
        values = {name: getattr(self, name) for name in COPIED_FIELDS}
        tag_names = list(self.tags.values_list("name", flat=True))
        step_titles = list(self.subtasks.values_list("title", flat=True))
        return fingerprint(values, self.due_date, tag_names, step_titles)

    def changed_since_copy(self):
        """True when this copy no longer matches what make_next_copy made.

        False for a to-do with no stored fingerprint (not a copy, or an old copy).
        """
        if not self.copy_fingerprint:
            return False
        return self.content_fingerprint() != self.copy_fingerprint

    def make_next_copy(self, today):
        """Make the next copy of a repeating to-do, and return it.

        Returns None, and makes nothing, when the to-do does not repeat, has no
        due date, has no next date (after 31 Dec 9999), or already has a copy.
        The copy is in the same list, so it has the same owner and members.
        A new field that a copy should keep is added to COPIED_FIELDS, and only
        there. The copy stores its fingerprint, so Undo can see a later change.
        """
        if not self.repeat or self.due_date is None:
            return None
        if self.get_next_copy() is not None:
            return None
        due_date = next_due_date(self.due_date, self.repeat, today)
        if due_date is None:
            return None
        values = {name: getattr(self, name) for name in COPIED_FIELDS}
        tags = list(self.tags.all())
        step_titles = [step.title for step in self.subtasks.all()]
        copy = Todo.objects.create(
            todo_list=self.todo_list,
            due_date=due_date,
            repeated_from=self,
            # From the values in memory, before the save: no second save.
            copy_fingerprint=fingerprint(
                values, due_date, [tag.name for tag in tags], step_titles
            ),
            **values,
        )
        # The same Tag rows; they already belong to the list owner.
        copy.tags.set(tags)
        # The same steps, in the same order, none of them done yet.
        Subtask.objects.bulk_create(
            Subtask(todo=copy, title=title) for title in step_titles
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
