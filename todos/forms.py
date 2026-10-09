from django import forms

from .models import Todo, TodoList


class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["title"]


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
