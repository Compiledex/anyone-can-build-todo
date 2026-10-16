"""Shared helpers for the CUJ tests.

Not a test file: the name does not start with `test`, so the runner never runs it.
"""

import re

from accounts.tests.helpers import make_user
from todos.models import TodoList

# A click on a link or a form button only *starts* loading the next page. Before
# the next step, wait with expect() for something that is only on the new page.
# Otherwise the next step can act on the old page, or page.reload() can fail with
# "Not attached to an active page" while the browser swaps the pages.

DONE = re.compile(r"\bdone\b")
RGB = re.compile(r"rgb\((\d+), (\d+), (\d+)\)")

# WCAG AA: normal text needs at least this contrast ratio with its background.
AA_CONTRAST = 4.5
# WCAG AA for things that are not text: the edge of a field, a focus ring, a line
# that marks the current choice.
UI_CONTRAST = 3.0


def luminance(css_color):
    """The WCAG relative luminance of a solid `rgb(r, g, b)`: 0 is black, 1 is white.

    Anything else (for example the see-through `rgba(0, 0, 0, 0)` of a body with no
    background) fails the test, so it can never be read as black by mistake.
    """
    match = RGB.fullmatch(css_color)
    if match is None:
        raise AssertionError(f"Expected a solid rgb(r, g, b) color, got {css_color!r}")
    channels = []
    for value in match.groups():
        c = int(value) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(color_a, color_b):
    """The WCAG contrast ratio of two colors, from 1 (the same) to 21 (black on white)."""
    lighter, darker = sorted([luminance(color_a), luminance(color_b)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def make_user_with_inbox():
    """A user with an "Inbox" list, like a person who just signed up."""
    user = make_user()
    TodoList.objects.create(owner=user, name="Inbox")
    return user


LOGIN_PAGE = "/accounts/login/"
SIGNUP_PAGE = "/accounts/signup/"

# The first password field only, not "Password confirmation".
PASSWORD = re.compile(r"^Password:?$")


# The size of a laptop screen and of a phone (iPhone 14), in CSS pixels.
DESKTOP = {"width": 1280, "height": 800}
PHONE = {"width": 390, "height": 844}
