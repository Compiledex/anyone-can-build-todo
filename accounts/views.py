from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from todos.models import TodoList

from .deletion import account_summary, delete_sessions_of
from .forms import DeleteAccountForm, SignupForm


@login_not_required
@require_http_methods(["GET", "HEAD", "POST"])  # HEAD: like the login page.
def signup(request):
    """Make a new account with an "Inbox" list, log in with it, and go to the list."""
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            TodoList.objects.create(owner=user, name="Inbox")
            login(request, user)
            return redirect("home")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


@require_http_methods(["GET", "HEAD", "POST"])  # HEAD: like the sign-up page.
def account_delete(request):
    """Delete the account of the person who is logged in, after their password.

    It acts only on request.user: there is no id in the address, and the form
    has no user field. user.delete() is Django's cascade: the lists they own
    (with their to-dos, steps and members), their tags, their memberships of
    other people's lists, and their admin log rows. Their sessions go too, in
    the same transaction. GET and HEAD only show what will go.
    """
    user = request.user
    if request.method == "POST":
        with transaction.atomic():
            form = DeleteAccountForm(user, request.POST)
            # check_password may save a rehashed password: the same transaction.
            deleted = form.is_valid()
            if deleted:
                delete_sessions_of(user)  # Also this browser's own session row.
                user.delete()
        if deleted:
            logout(request)  # Flushes this session; request.user is now anonymous.
            # The message is written after the view, so logout() does not remove it.
            messages.success(request, "Your account was deleted.")
            return redirect("home")
    else:
        form = DeleteAccountForm(user)
    return render(
        request,
        "registration/account_delete.html",
        {"form": form, "summary": account_summary(user)},
    )
