from django import forms
from django.contrib.auth import get_user_model

from .models import Todo, TodoList


class NoteField(forms.CharField):
    """A text field that counts a line break as one character, as the browser does."""

    def to_python(self, value):
        return super().to_python(value).replace("\r\n", "\n")


class TodoForm(forms.ModelForm):
    # Only YYYY-MM-DD, the format the browser's date picker sends. Other formats,
    # like 10/12/2026, can mean two different dates.
    due_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    # A missing or empty priority is not an error: clean_priority keeps the
    # to-do's own priority (Medium for a new to-do). 7 or "urgent" is an error.
    priority = forms.TypedChoiceField(
        choices=Todo.Priority.choices,
        coerce=int,
        required=False,
        empty_value=None,
        initial=Todo.Priority.MEDIUM,
        widget=forms.Select(attrs={"aria-label": "Priority"}),
    )

    class Meta:
        model = Todo
        fields = ["title", "due_date", "description", "priority"]
        field_classes = {"description": NoteField}
        labels = {"description": "Notes"}
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_priority(self):
        priority = self.cleaned_data["priority"]
        if priority is None:
            # No priority was sent: keep the one the to-do has.
            return self.instance.priority
        return priority


class TodoListForm(forms.ModelForm):
    """The name of a new list, or a new name for a list.

    The view always gives an `instance` that already has its owner.
    """

    class Meta:
        model = TodoList
        fields = ["name"]

    def clean_name(self):
        # Django's own check skips the unique constraint, because `owner` is
        # not in the form. Without this, a duplicate name is a 500 error page.
        name = self.cleaned_data["name"]
        others = TodoList.objects.filter(
            owner=self.instance.owner, name__iexact=name
        ).exclude(pk=self.instance.pk)
        if others.exists():
            raise forms.ValidationError(f"You already have a list called “{name}”.")
        return name


class ShareForm(forms.Form):
    """The username of the person the owner shares a list with.

    A valid form gives the User in cleaned_data["username"].
    """

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "aria-label": "Username to share with",
                "placeholder": "Username",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, todo_list, **kwargs):
        super().__init__(*args, **kwargs)
        self.todo_list = todo_list

    def clean_username(self):
        name = self.cleaned_data["username"]
        User = get_user_model()
        try:
            # Exact, like the login page. A switched-off user is "no user".
            user = User.objects.get(username=name, is_active=True)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username.") from None
        if user == self.todo_list.owner:
            raise forms.ValidationError("You already own this list.")
        if self.todo_list.members.filter(pk=user.pk).exists():
            raise forms.ValidationError(f"{user.username} is already a member.")
        return user
