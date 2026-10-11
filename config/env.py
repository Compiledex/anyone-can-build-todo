"""Read the settings that come from environment variables, and refuse unsafe ones.

Pure functions: they get the environment as a dict, so tests can pass any values.
No error message ever shows the value of a variable: messages end up in build
logs, and a value in the wrong field could be the secret key.
"""

from django.core.exceptions import ImproperlyConfigured

LAPTOP_SECRET_KEY = "django-insecure-only-for-your-laptop"

# The same limits as Django's own deploy check (security.W009). Django has them
# as SECRET_KEY_MIN_LENGTH, SECRET_KEY_MIN_UNIQUE_CHARACTERS and
# SECRET_KEY_INSECURE_PREFIX in django.core.checks.security.base. We keep our
# own copies so this file reads on its own; a unit test checks they are equal.
MIN_LENGTH = 50
MIN_UNIQUE_CHARACTERS = 5
INSECURE_PREFIX = "django-insecure-"

MAKE_A_KEY = 'uv run python -c "import secrets; print(secrets.token_urlsafe(50))"'


def read_debug(env):
    """True or False from DJANGO_DEBUG. Not set means True (the laptop).

    Only "True" or "False" are accepted, in any case, with spaces at the ends
    removed. Any other value, also an empty one, stops the app.
    """
    if "DJANGO_DEBUG" not in env:
        return True
    value = env["DJANGO_DEBUG"]
    word = value.strip().casefold()
    if word == "true":
        return True
    if word == "false":
        return False
    raise ImproperlyConfigured(
        "DJANGO_DEBUG must be True or False. "
        f"It is set to something else ({len(value)} characters)."
    )


def is_strong(key):
    """True if Django's deploy check (security.W009) accepts this key."""
    return (
        len(key) >= MIN_LENGTH
        and len(set(key)) >= MIN_UNIQUE_CHARACTERS
        and not key.startswith(INSECURE_PREFIX)
    )


def read_secret_key(env, debug):
    """The secret key. With debug off, a missing or weak key stops the app.

    The key is used exactly as given: spaces at the ends are not removed.
    """
    key = env.get("DJANGO_SECRET_KEY", "")
    if debug:
        return key or LAPTOP_SECRET_KEY
    if not key:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set. DJANGO_DEBUG is False, so the site "
            f"needs its own secret key. Make one with: {MAKE_A_KEY}, then set it "
            "as the environment variable DJANGO_SECRET_KEY."
        )
    if not is_strong(key):
        raise ImproperlyConfigured(
            f"DJANGO_SECRET_KEY is too weak: it needs at least {MIN_LENGTH} "
            f"characters, at least {MIN_UNIQUE_CHARACTERS} different characters, "
            f'and must not start with "{INSECURE_PREFIX}". Make one with: '
            f"{MAKE_A_KEY}."
        )
    return key
