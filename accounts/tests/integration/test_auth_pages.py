"""The look and the accessibility of the login and sign-up pages.

What the forms do (log in, sign up, `next`) is tested in test_accounts.py.
Here: the pages use the same frame and CSS as the landing page, every input has
a label, and the help and error texts are linked to their input.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.session import SessionStorage
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.templatetags.static import static
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.tests.helpers import (
    TEST_PASSWORD,
    LoggedInTestCase,
    make_user,
    parse_page,
)

LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"
SITE_FRAME = "todos/site_base.html"


def visible_inputs(parts):
    return [a for a in parts.all("input") if a.get("type") != "hidden"]


class SharedFrameTests(TestCase):
    def test_login_signup_and_landing_use_the_same_frame_and_css(self):
        for url in [LOGIN_URL, SIGNUP_URL, "/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertTemplateUsed(response, SITE_FRAME)
                self.assertTemplateNotUsed(response, "base.html")
                stylesheets = [
                    a["href"]
                    for a in parse_page(response).all("link", rel="stylesheet")
                ]
                # The tokens, then the shared CSS, then the page's own CSS.
                self.assertEqual(
                    stylesheets[:2],
                    [static("todos/tokens.css"), static("todos/site.css")],
                )
                self.assertEqual(len(stylesheets), 3)

    def test_every_stylesheet_is_a_static_file_and_nothing_comes_from_other_sites(self):
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                parts = parse_page(self.client.get(url))
                self.assertEqual(parts.all("script"), [])
                for attrs in parts.all("link", rel="stylesheet"):
                    path = attrs["href"].removeprefix(static(""))
                    self.assertIsNotNone(finders.find(path), f"{path} is missing")
                for tag in ("img", "source", "link"):
                    for attrs in parts.all(tag):
                        for key in ("src", "srcset", "href"):
                            value = attrs.get(key) or ""
                            self.assertFalse(
                                value.startswith(("http:", "https:", "//")), value
                            )

    def test_no_long_dashes_and_nothing_from_other_sites_in_auth_css(self):
        with open(finders.find("accounts/auth.css"), encoding="utf-8") as file:
            css = file.read()
        for text in ["@import", "url(http", "url(//"]:
            self.assertNotIn(text, css)
        pages = [
            (url, self.client.get(url).content.decode())
            for url in [LOGIN_URL, SIGNUP_URL]
        ]
        for name, text in pages + [("auth.css", css)]:
            for dash in ["\u2014", "\u2013"]:  # em dash, en dash
                self.assertNotIn(dash, text, name)

    def test_header_has_the_brand_and_only_the_other_page(self):
        # On a page, one label per intent: the login page links to sign-up in its
        # header, and has no second "Log in" link; the other way round on sign-up.
        cases = [
            (LOGIN_URL, "Create an account", reverse("signup"), "Log in"),
            (SIGNUP_URL, "Log in", reverse("login"), "Create an account"),
        ]
        for url, other, other_url, this in cases:
            with self.subTest(url=url):
                parts = parse_page(self.client.get(url))
                self.assertIn(("/", "To-do list"), parts.links)
                self.assertEqual(
                    [href for href, text in parts.links if text == other], [other_url]
                )
                self.assertEqual(
                    [href for href, text in parts.links if text == this], []
                )
                # The submit button has the same label as the landing page's link.
                self.assertEqual(parts.buttons, [this])

    def test_page_titles_stay_the_same(self):
        for url, title in [(LOGIN_URL, "Log in"), (SIGNUP_URL, "Sign up")]:
            with self.subTest(url=url):
                self.assertContains(
                    self.client.get(url), f"<title>{title}</title>", html=True
                )

    def test_one_app_screenshot_with_a_dark_version(self):
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                parts = parse_page(self.client.get(url))
                images = parts.all("img")
                self.assertEqual(len(images), 1)
                image = images[0]
                self.assertTrue(image.get("width", "").isdigit())
                self.assertTrue(image.get("height", "").isdigit())
                self.assertTrue(image.get("alt", "").strip())
                # A phone hides the picture; lazy means it then never downloads it.
                self.assertEqual(image.get("loading"), "lazy")
                sources = parts.all("source", media="(prefers-color-scheme: dark)")
                self.assertEqual(len(sources), 1)
                for file_url in [image["src"], sources[0]["srcset"]]:
                    path = file_url.removeprefix(static(""))
                    self.assertIsNotNone(finders.find(path), f"{path} is missing")


class FormFieldTests(TestCase):
    def test_fields_use_the_shared_field_include(self):
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                self.assertTemplateUsed(self.client.get(url), "todos/_field.html")

    def test_labels_have_no_colon(self):
        cases = [
            (LOGIN_URL, ["Username", "Password"]),
            (SIGNUP_URL, ["Username", "Password", "Password confirmation"]),
        ]
        for url, labels in cases:
            page = self.client.get(url).content.decode()
            for label in labels:
                with self.subTest(url=url, label=label):
                    self.assertIn(f">{label}</label>", page)
                    self.assertNotIn(f"{label}:</label>", page)

    def test_every_input_has_a_label(self):
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                parts = parse_page(self.client.get(url))
                inputs = visible_inputs(parts)
                self.assertTrue(inputs)
                label_for = {a.get("for") for a in parts.all("label")}
                for attrs in inputs:
                    self.assertIn(attrs["id"], label_for, attrs["name"])
                    # The label is above the input.
                    self.assertLess(
                        parts.position("label", **{"for": attrs["id"]}),
                        parts.position("input", id=attrs["id"]),
                    )
                    # Never a placeholder instead of a label.
                    self.assertNotIn("placeholder", attrs)

    def test_fields_keep_their_names_order_and_autocomplete(self):
        cases = [
            (LOGIN_URL, [("username", "username"), ("password", "current-password")]),
            (
                SIGNUP_URL,
                [
                    ("username", "username"),
                    ("password1", "new-password"),
                    ("password2", "new-password"),
                ],
            ),
        ]
        for url, fields in cases:
            with self.subTest(url=url):
                inputs = visible_inputs(parse_page(self.client.get(url)))
                self.assertEqual(
                    [(a["name"], a.get("autocomplete")) for a in inputs], fields
                )

    def test_forms_post_to_the_same_addresses(self):
        for url, action in [
            (LOGIN_URL, reverse("login")),
            (SIGNUP_URL, reverse("signup")),
        ]:
            with self.subTest(url=url):
                forms = parse_page(self.client.get(url)).all("form")
                self.assertEqual(
                    [(f.get("method"), f.get("action")) for f in forms],
                    [("post", action)],
                )

    def test_signup_help_text_is_shown_and_linked_to_its_input(self):
        parts = parse_page(self.client.get(SIGNUP_URL))
        for name in ["username", "password1", "password2"]:
            with self.subTest(name=name):
                (attrs,) = parts.all("input", name=name)
                help_id = f"id_{name}_helptext"
                self.assertIn(help_id, attrs["aria-describedby"].split())
                self.assertTrue(parts.text_by_id[help_id])
                self.assertNotIn("aria-invalid", attrs)
        # The password rules, in plain words, as helper text.
        self.assertIn(
            "at least 8 characters", parts.text_by_id["id_password1_helptext"]
        )

    def test_signup_error_is_below_its_input_and_linked_to_it(self):
        # Too short. Long enough that it cannot appear in the page by chance.
        bad_password = "zq7zq7x"
        response = self.client.post(
            SIGNUP_URL,
            {"username": "carol", "password1": bad_password, "password2": bad_password},
        )
        # A password is never sent back to the browser, not even a wrong one.
        self.assertNotContains(response, bad_password)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="carol").exists())
        parts = parse_page(response)
        # Django puts the password rule errors on the confirmation field.
        (attrs,) = parts.all("input", name="password2")
        self.assertEqual(attrs.get("aria-invalid"), "true")
        self.assertIn("id_password2_error", attrs["aria-describedby"].split())
        self.assertIn("too short", parts.text_by_id["id_password2_error"])
        self.assertGreater(
            parts.position("ul", id="id_password2_error"),
            parts.position("input", name="password2"),
        )
        # A field without an error is not marked invalid.
        (username,) = parts.all("input", name="username")
        self.assertNotIn("aria-invalid", username)

    def test_login_error_is_above_the_form_and_does_not_log_in(self):
        make_user("alice")
        response = self.client.post(
            LOGIN_URL,
            {"username": "alice", "password": "wrong-password-1", "next": "/"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotContains(response, "wrong-password-1")
        parts = parse_page(response)
        errors = parts.position("ul", **{"class": "errorlist nonfield"})
        self.assertLess(errors, parts.position("input", name="username"))
        self.assertContains(response, "Please enter a correct username and password.")
        # `next` is kept for the second try.
        self.assertEqual(parts.all("input", name="next")[0]["value"], "/")

    def test_login_goes_to_next(self):
        make_user("alice")
        response = self.client.post(
            LOGIN_URL,
            {
                "username": "alice",
                "password": TEST_PASSWORD,
                "next": reverse("list_create"),
            },
        )
        self.assertRedirects(
            response, reverse("list_create"), fetch_redirect_response=False
        )


class MessagesTests(TestCase):
    def add_message(self, text):
        """Make a message the way a view does, in the client's session.

        Messages are kept in the session (MESSAGE_STORAGE), never in a cookie.
        """
        request = RequestFactory().get("/")
        request.session = self.client.session
        request._messages = SessionStorage(request)
        messages.info(request, text)
        request._messages.update(HttpResponse())
        request.session.save()

    def test_a_message_shows_on_the_login_page(self):
        self.add_message("Your session ended. Please log in again.")

        response = self.client.get(LOGIN_URL)
        parts = parse_page(response)
        boxes = parts.all("div", **{"class": "container messages", "role": "status"})
        self.assertEqual(len(boxes), 1, "the message box is missing")
        self.assertContains(response, "Your session ended. Please log in again.")
        # Above the page's own content.
        self.assertLess(
            parts.position("div", **{"class": "container messages"}),
            parts.position("h1", id="auth-title"),
        )

    def test_a_message_survives_login(self):
        # Not a user flow (no page adds a message before login today): a guard
        # that login() keeps the session's data (cycle_key), not flush().
        make_user("alice")
        self.add_message("A note from before the login.")
        response = self.client.post(
            LOGIN_URL,
            {"username": "alice", "password": TEST_PASSWORD},
            follow=True,
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, "A note from before the login.")

    def test_no_message_box_without_a_message(self):
        for url in [LOGIN_URL, SIGNUP_URL, "/"]:
            with self.subTest(url=url):
                self.assertNotContains(
                    self.client.get(url), 'class="container messages"'
                )


class AppPagesTests(LoggedInTestCase):
    def test_app_pages_do_not_load_the_visitor_css(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateNotUsed(response, SITE_FRAME)
        self.assertNotContains(response, "todos/site.css")
        # The app shares the tokens with the visitor pages, then has its own CSS.
        stylesheets = [
            a["href"] for a in parse_page(response).all("link", rel="stylesheet")
        ]
        self.assertEqual(
            stylesheets, [static("todos/tokens.css"), static("todos/app.css")]
        )
