"""The visitor's landing page in a real browser: what it shows, colors, sizes."""

from playwright.sync_api import expect

from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.helpers import (
    AA_CONTRAST,
    DESKTOP,
    PHONE,
    SIGNUP_PAGE,
    UI_CONTRAST,
    contrast,
    luminance,
)

# The first screen of the landing page, in the order a visitor reads it.
HEADLINE = "Simple to-do lists you can share"


class LandingTests(BrowserTestCase):
    def test_visitor_opens_landing_and_creates_an_account(self):
        page = self.page
        page.goto(self.live_server_url)
        expect(page.get_by_role("heading", level=1)).to_have_text(HEADLINE)

        page.get_by_role("link", name="Create an account").first.click()
        expect(page.get_by_role("heading", name="Create an account")).to_be_visible()
        self.assertEqual(page.url, f"{self.live_server_url}{SIGNUP_PAGE}")

    def test_hero_fits_the_first_screen(self):
        page = self.page
        for size in [DESKTOP, PHONE]:
            with self.subTest(size=size):
                page.set_viewport_size(size)
                page.goto(self.live_server_url)
                hero = page.locator(".hero")
                for name in ["Create an account", "Log in"]:
                    link = hero.get_by_role("link", name=name)
                    expect(link).to_be_in_viewport(ratio=1)
                # The headline is at most 2 lines.
                lines = page.evaluate(
                    """() => {
                        const h1 = document.querySelector("h1");
                        const lineHeight = parseFloat(getComputedStyle(h1).lineHeight);
                        return Math.round(h1.getBoundingClientRect().height / lineHeight);
                    }"""
                )
                self.assertLessEqual(lines, 2)
                # Nothing is wider than the screen, so there is no sideways scroll.
                width = page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(width, size["width"])

    def test_landing_is_readable_in_light_and_dark(self):
        page = self.page
        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                page.goto(self.live_server_url)
                colors = page.evaluate(
                    """() => {
                        const color = (selector, property = "color") =>
                            getComputedStyle(document.querySelector(selector))[property];
                        return {
                            background: color("body", "backgroundColor"),
                            text: color("h1"),
                            body: color(".hero p"),
                            muted: color(".muted"),
                            button: color(".button-primary"),
                            buttonBackground: color(".button-primary", "backgroundColor"),
                            secondary: color(".button-secondary"),
                            secondaryEdge: color(
                                ".button-secondary", "borderTopColor"
                            ),
                            accent: color(".button-primary", "backgroundColor"),
                            band: color(".band", "backgroundColor"),
                            bandText: color(".band p"),
                        };
                    }"""
                )
                for name in ["text", "body", "muted", "secondary"]:
                    self.assertGreaterEqual(
                        contrast(colors[name], colors["background"]), AA_CONTRAST, name
                    )
                self.assertGreaterEqual(
                    contrast(colors["button"], colors["buttonBackground"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["bandText"], colors["band"]), AA_CONTRAST
                )
                # The secondary button: a gray edge you can see, a label that is
                # not the accent color (the one look of the whole product).
                self.assertGreaterEqual(
                    contrast(colors["secondaryEdge"], colors["background"]),
                    UI_CONTRAST,
                )
                self.assertNotEqual(colors["secondary"], colors["accent"], colors)
                if scheme == "dark":
                    self.assertLess(luminance(colors["background"]), 0.05, colors)
                else:
                    self.assertGreater(luminance(colors["background"]), 0.8, colors)
