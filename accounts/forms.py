from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class LoginForm(AuthenticationForm):
    """Django's login form, with labels like "Username" instead of "Username:"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""


class SignupForm(UserCreationForm):
    """Django's sign-up form, with labels like "Username" instead of "Username:",
    and short, plain help texts. The checks stay Django's own."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""
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
