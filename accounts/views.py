from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render

from todos.models import TodoList

from .forms import SignupForm


@login_not_required
def signup(request):
    """Make a new account with an "Inbox" list, log in with it, and go to the list."""
    if request.user.is_authenticated:
        return redirect("todo_list")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            TodoList.objects.create(owner=user, name="Inbox")
            login(request, user)
            return redirect("todo_list")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})
