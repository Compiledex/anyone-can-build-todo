from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import views

# Not all of django.contrib.auth.urls: its password reset pages need email.
urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    # Open to everyone, so "Log out" in a tab whose session already ended
    # goes to the login page, not to a 405 page after the next login.
    path(
        "logout/",
        login_not_required(auth_views.LogoutView.as_view()),
        name="logout",
    ),
    path("signup/", views.signup, name="signup"),
]
