from django.contrib.auth.forms import AuthenticationForm, UserCreationForm


class LoginForm(AuthenticationForm):
    """Django's login form, with labels like "Username" instead of "Username:"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""


class SignupForm(UserCreationForm):
    """Django's sign-up form, with labels like "Username" instead of "Username:"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_suffix = ""
