from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


@login_not_required
def signup(request):
    """Make a new account, log in with it, and go to the list."""
    if request.user.is_authenticated:
        return redirect("todo_list")
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("todo_list")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})
