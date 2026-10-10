"""The look and the accessibility of the login and sign-up pages.

What the forms do (log in, sign up, `next`) is tested in test_accounts.py.
Here: the pages use the same frame and CSS as the landing page, every input has
a label, and the help and error texts are linked to their input.
"""

from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse

from accounts.tests.helpers import TEST_PASSWORD, make_user

LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"
SITE_FRAME = "todos/site_base.html"


class PageParts(HTMLParser):
    """Collects the tags of a page in order, with their attributes and text."""

    def __init__(self):
        super().__init__()
        self.elements = []  # (tag, attributes), in the order of the page
        self.links = []  # (href, text)
        self.buttons = []  # the text of each <button>
        self.text_by_id = {}  # the text inside each element that has an id
        self._open = []  # (tag, id, text parts) of the elements still open
        self._href = None
        self._link_text = []
        self._button_text = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == "a":
            self._href = attrs.get("href")
            self._link_text = []
        if tag == "button":
            self._button_text = []
        if tag not in ("input", "img", "source", "link", "meta", "br"):
            self._open.append((tag, attrs.get("id"), []))

    def handle_data(self, data):
        if self._href is not None:
            self._link_text.append(data)
        if self._button_text is not None:
            self._button_text.append(data)
        for _tag, _id, parts in self._open:
            parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._link_text).split())))
            self._href = None
        if tag == "button" and self._button_text is not None:
            self.buttons.append(" ".join("".join(self._button_text).split()))
            self._button_text = None
        for index in range(len(self._open) - 1, -1, -1):
            if self._open[index][0] == tag:
                _tag, element_id, parts = self._open.pop(index)
                if element_id:
                    self.text_by_id[element_id] = " ".join("".join(parts).split())
                break

    def all(self, tag, **attrs):
        return [
            a
            for t, a in self.elements
            if t == tag and all(a.get(k) == v for k, v in attrs.items())
        ]

    def position(self, tag, **attrs):
        """The place of the first matching element in the page, for 'above' and 'below'."""
        for index, (t, a) in enumerate(self.elements):
            if t == tag and all(a.get(k) == v for k, v in attrs.items()):
                return index
        raise AssertionError(f"No <{tag}> with {attrs}")


def parts_of(response):
    parser = PageParts()
    parser.feed(response.content.decode())
    return parser


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
                    a["href"] for a in parts_of(response).all("link", rel="stylesheet")
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
                parts = parts_of(self.client.get(url))
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
                parts = parts_of(self.client.get(url))
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
                parts = parts_of(self.client.get(url))
                images = parts.all("img")
                self.assertEqual(len(images), 1)
                image = images[0]
                self.assertTrue(image.get("width", "").isdigit())
                self.assertTrue(image.get("height", "").isdigit())
                self.assertTrue(image.get("alt", "").strip())
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
                parts = parts_of(self.client.get(url))
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
                inputs = visible_inputs(parts_of(self.client.get(url)))
                self.assertEqual(
                    [(a["name"], a.get("autocomplete")) for a in inputs], fields
                )

    def test_forms_post_to_the_same_addresses(self):
        for url, action in [
            (LOGIN_URL, reverse("login")),
            (SIGNUP_URL, reverse("signup")),
        ]:
            with self.subTest(url=url):
                forms = parts_of(self.client.get(url)).all("form")
                self.assertEqual(
                    [(f.get("method"), f.get("action")) for f in forms],
                    [("post", action)],
                )

    def test_signup_help_text_is_shown_and_linked_to_its_input(self):
        parts = parts_of(self.client.get(SIGNUP_URL))
        for name in ["username", "password1", "password2"]:
            with self.subTest(name=name):
                (attrs,) = parts.all("input", name=name)
                help_id = f"id_{name}_helptext"
                self.assertIn(help_id, attrs["aria-describedby"].split())
                self.assertTrue(parts.text_by_id[help_id])
                self.assertNotIn("aria-invalid", attrs)
        # Django's own password rules, as helper text.
        self.assertIn(
            "at least 8 characters", parts.text_by_id["id_password1_helptext"]
        )

    def test_signup_error_is_below_its_input_and_linked_to_it(self):
        response = self.client.post(
            SIGNUP_URL, {"username": "carol", "password1": "123", "password2": "123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="carol").exists())
        parts = parts_of(response)
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
        parts = parts_of(response)
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
