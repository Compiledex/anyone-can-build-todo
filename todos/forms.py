from django import forms

from .models import Todo, TodoList


class TodoForm(forms.ModelForm):
    # Only YYYY-MM-DD, the format the browser's date picker sends. Other formats,
    # like 10/12/2026, can mean two different dates.
    due_date = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = Todo
        fields = ["title", "due_date"]


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
