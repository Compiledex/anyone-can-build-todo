import re

from playwright.sync_api import expect

from todos.tests.cuj.browser import BrowserTestCase

DONE = re.compile(r"\bdone\b")
RGB = re.compile(r"rgb\((\d+), (\d+), (\d+)\)")

# WCAG AA: normal text needs at least this contrast ratio with its background.
AA_CONTRAST = 4.5


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


class PlanAndFinishTests(BrowserTestCase):
    def test_plan_and_finish(self):
        page = self.page
        page.goto(self.live_server_url)

        for title in ["Buy milk", "Call home"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()

        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
        milk.get_by_role("button", name="Done").click()
        expect(milk).to_have_class(DONE)
        milk.get_by_role("button", name="Undo").click()
        expect(milk).not_to_have_class(DONE)

        call = page.get_by_role("listitem").filter(has_text="Call home")
        call.get_by_role("button", name="Delete").click()

        page.reload()
        expect(page.get_by_role("listitem")).to_have_count(1)
        expect(milk).to_be_visible()
        expect(call).to_have_count(0)


class ColorSchemeTests(BrowserTestCase):
    def test_readable_in_light_and_dark(self):
        page = self.page
        page.goto(self.live_server_url)  # Opens the list page.

        for title in ["Buy milk", "Call home"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()
        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
        milk.get_by_role("button", name="Done").click()
        expect(milk).to_have_class(DONE)

        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                colors = page.evaluate(
                    """() => {
                        const color = (selector, property) =>
                            getComputedStyle(document.querySelector(selector))[property];
                        return {
                            background: color("body", "backgroundColor"),
                            text: color("li:not(.done) .title", "color"),
                            done: color("li.done .title", "color"),
                        };
                    }"""
                )
                background = luminance(colors["background"])
                if scheme == "dark":
                    self.assertLess(background, 0.1, colors)
                else:
                    self.assertGreater(background, 0.9, colors)
                self.assertGreaterEqual(
                    contrast(colors["text"], colors["background"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["done"], colors["background"]), AA_CONTRAST
                )
