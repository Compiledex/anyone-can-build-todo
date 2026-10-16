from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from todos.forms import NoColon


class LoginForm(NoColon, AuthenticationForm):
    """Django's login form, with labels like "Username" instead of "Username:"."""


class SignupForm(NoColon, UserCreationForm):
    """Django's sign-up form, with labels like "Username" instead of "Username:",
    and short, plain help texts. The checks stay Django's own."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "username"
        ].help_text = (
            "Up to 150 characters: letters, numbers and @ . + - _ (no spaces)."
        )
        # The 8 is the default of MinimumLengthValidator in AUTH_PASSWORD_VALIDATORS;
        # a test checks that this text names its real min_length.
        self.fields["password1"].help_text = (
            "Use at least 8 characters. Not only numbers, not a common password,"
            " and not too close to your username."
        )
        self.fields["password2"].help_text = "Type the same password again."


class DeleteAccountForm(NoColon, forms.Form):
    """The password of the person who wants to delete their account.

    The view gives the user (always request.user); the form has no user field,
    so a posted username or user id is never read.
    """

    password = forms.CharField(
        label="Password",
        strip=False,  # A space is part of a password.
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        # Django's own check (a constant-time compare). It may save a new hash.
        if not self.user.check_password(password):
            raise forms.ValidationError(
                "Wrong password. Nothing was deleted.", code="wrong_password"
            )
        return password
