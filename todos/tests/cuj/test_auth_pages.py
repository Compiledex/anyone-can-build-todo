"""The login and sign-up pages in a real browser: the way in, errors, colors, sizes."""

import re

from playwright.sync_api import expect

from accounts.tests.helpers import TEST_PASSWORD
from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.test_journeys import (
    AA_CONTRAST,
    DESKTOP,
    LOGIN_PAGE,
    PASSWORD,
    PHONE,
    SIGNUP_PAGE,
    contrast,
    make_user_with_inbox,
)

# WCAG AA for the edge of an input and for the focus ring (non-text contrast).
UI_CONTRAST = 3.0

# Reads the colors of the auth page that a person must be able to see.
AUTH_COLORS = """() => {
    const style = selector => getComputedStyle(document.querySelector(selector));
    const input = document.querySelector("#id_username");
    input.focus();
    const focused = getComputedStyle(input);
    const colors = {
        background: style("body").backgroundColor,
        heading: style("h1").color,
        intro: style(".auth-intro").color,
        label: style("label").color,
        inputText: focused.color,
        inputBackground: focused.backgroundColor,
        inputBorder: style("#id_password1").borderTopColor,
        focusRing: focused.outlineColor,
        focusStyle: focused.outlineStyle,
        help: style(".helptext").color,
        error: style(".errorlist").color,
        errorBorder: style("[aria-invalid=true]").borderTopColor,
        button: style("button[type=submit]").color,
        buttonBackground: style("button[type=submit]").backgroundColor,
        headerLink: style(".site-nav a:not(.wordmark)").color,
        headerLinkEdge: style(".site-nav a:not(.wordmark)").borderTopColor,
    };
    input.blur();
    return colors;
}"""


def submit_bad_password(page, live_server_url):
    page.goto(f"{live_server_url}{SIGNUP_PAGE}")
    page.get_by_label("Username").fill("carol")
    page.get_by_label(PASSWORD).fill("123")
    page.get_by_label("Password confirmation").fill("123")
    page.get_by_role("button", name="Create an account").click()
    expect(page.get_by_text("This password is too short.")).to_be_visible()


class AuthPagesTests(BrowserTestCase):
    def test_visitor_goes_from_landing_to_login_to_their_list(self):
        make_user_with_inbox()  # The user from make_user(): alice.
        page = self.page
        page.goto(self.live_server_url)
        page.get_by_role("link", name="Log in").first.click()
        expect(page.get_by_role("heading", name="Log in")).to_be_visible()

        page.get_by_label("Username").fill("alice")
        page.get_by_label(PASSWORD).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
        expect(page.get_by_text("Logged in as alice")).to_be_visible()

    def test_bad_password_shows_the_error_below_the_field(self):
        page = self.page
        submit_bad_password(page, self.live_server_url)
        field = page.get_by_label("Password confirmation")
        expect(field).to_have_attribute("aria-invalid", "true")
        # The error is under the field, and it is part of the field's description.
        error = page.locator("#id_password2_error")
        field_box = field.bounding_box()
        error_box = error.bounding_box()
        self.assertGreaterEqual(error_box["y"], field_box["y"] + field_box["height"])
        expect(field).to_have_accessible_description(
            re.compile(r"Enter the same password as before.*This password is too short")
        )

    def test_auth_pages_are_readable_in_light_and_dark(self):
        page = self.page
        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                submit_bad_password(page, self.live_server_url)
                colors = page.evaluate(AUTH_COLORS)
                for name in [
                    "heading",
                    "intro",
                    "label",
                    "help",
                    "error",
                    "headerLink",
                ]:
                    self.assertGreaterEqual(
                        contrast(colors[name], colors["background"]), AA_CONTRAST, name
                    )
                self.assertGreaterEqual(
                    contrast(colors["inputText"], colors["inputBackground"]),
                    AA_CONTRAST,
                )
                self.assertGreaterEqual(
                    contrast(colors["button"], colors["buttonBackground"]), AA_CONTRAST
                )
                self.assertEqual(colors["focusStyle"], "solid")
                # The header button (secondary): its gray edge can be seen.
                self.assertGreaterEqual(
                    contrast(colors["headerLinkEdge"], colors["background"]),
                    UI_CONTRAST,
                )
                for name in ["inputBorder", "errorBorder", "focusRing"]:
                    for against in ["background", "inputBackground"]:
                        self.assertGreaterEqual(
                            contrast(colors[name], colors[against]),
                            UI_CONTRAST,
                            f"{name} on {against}",
                        )

    def test_submit_is_on_the_first_screen_and_nothing_scrolls_sideways(self):
        page = self.page
        for size in [DESKTOP, PHONE]:
            for path, button in [
                (LOGIN_PAGE, "Log in"),
                (SIGNUP_PAGE, "Create an account"),
            ]:
                with self.subTest(size=size, path=path):
                    page.set_viewport_size(size)
                    page.goto(f"{self.live_server_url}{path}")
                    # With every help text shown, the button is still on screen.
                    expect(page.get_by_role("button", name=button)).to_be_in_viewport(
                        ratio=1
                    )
                    width = page.evaluate("document.documentElement.scrollWidth")
                    self.assertLessEqual(width, size["width"])
                    # The screenshot is only on a wide screen; a phone shows the form.
                    screenshot = page.locator(".auth-shot img")
                    if size is DESKTOP:
                        expect(screenshot).to_be_visible()
                    else:
                        expect(screenshot).to_be_hidden()
            with self.subTest(size=size, errors=True):
                submit_bad_password(page, self.live_server_url)
                width = page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(width, size["width"])

    def test_inputs_are_big_enough_for_a_phone(self):
        page = self.page
        page.set_viewport_size(PHONE)
        page.goto(f"{self.live_server_url}{SIGNUP_PAGE}")
        sizes = page.evaluate(
            """() => [...document.querySelectorAll("input:not([type=hidden])")].map(i => ({
                font: parseFloat(getComputedStyle(i).fontSize),
                width: i.getBoundingClientRect().width,
                form: i.form.getBoundingClientRect().width,
            }))"""
        )
        self.assertEqual(len(sizes), 3)
        for size in sizes:
            # 16px or more, so iPhone Safari does not zoom in; as wide as the form.
            self.assertGreaterEqual(size["font"], 16)
            self.assertAlmostEqual(size["width"], size["form"], delta=1)
