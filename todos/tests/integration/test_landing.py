"""Tests for the landing page: what a visitor who is not logged in sees at `/`.

A logged-in person still goes straight to a list (see HomeTests in test_lists.py).
"""

from html.parser import HTMLParser

from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse

from accounts.tests.helpers import make_user
from todos.models import Subtask, Todo, TodoList

LANDING_TEMPLATE = "todos/landing.html"


class PageParts(HTMLParser):
    """Collects the links (address and text) and the image files of a page."""

    def __init__(self):
        super().__init__()
        self.links = []  # (href, text)
        self.images = []  # the attributes of each <img>
        self.image_files = []  # every address in src and srcset
        self.tags = set()
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.add(tag)
        if tag == "a":
            self._href = attrs.get("href")
            self._text = []
        if tag == "img":
            self.images.append(attrs)
        if tag in ("img", "source"):
            if attrs.get("src"):
                self.image_files.append(attrs["src"])
            for part in (attrs.get("srcset") or "").split(","):
                if part.strip():
                    self.image_files.append(part.split()[0])

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def parts_of(response):
    parser = PageParts()
    parser.feed(response.content.decode())
    return parser


class LandingPageTests(TestCase):
    """Nobody is logged in here."""

    def test_visitor_sees_the_landing_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, LANDING_TEMPLATE)
        self.assertNotContains(response, "Logged in as")

    def test_calls_to_action_go_to_signup_and_login(self):
        links = parts_of(self.client.get("/")).links
        signup = [href for href, text in links if text == "Create an account"]
        login = [href for href, text in links if text == "Log in"]
        self.assertTrue(signup)
        self.assertTrue(login)
        # One label per intent: every "Create an account" goes to sign-up, and
        # every "Log in" goes to the login page.
        self.assertEqual(set(signup), {reverse("signup")})
        self.assertEqual(set(login), {reverse("login")})

    def test_landing_shows_no_user_data(self):
        alice = make_user("alice")
        bob = make_user("bob")
        trip = TodoList.objects.create(owner=alice, name="Lisbon trip")
        trip.members.add(bob)
        todo = Todo.objects.create(
            title="Book the night train",
            description="Seat 42, window",
            todo_list=trip,
        )
        todo.set_tags(["holiday"])
        Subtask.objects.create(todo=todo, title="Ask about bikes")
        response = self.client.get("/")
        for text in [
            "alice",
            "bob",
            "Lisbon trip",
            "Book the night train",
            "Seat 42",
            "holiday",
            "Ask about bikes",
        ]:
            with self.subTest(text=text):
                self.assertNotContains(response, text)

    def test_every_landing_image_is_a_static_file(self):
        files = parts_of(self.client.get("/")).image_files
        self.assertTrue(files)
        for url in files:
            with self.subTest(url=url):
                self.assertTrue(url.startswith(static("")), url)
                path = url.removeprefix(static(""))
                self.assertIsNotNone(finders.find(path), f"{path} is missing")

    def test_every_image_has_a_size_and_alt_text(self):
        images = parts_of(self.client.get("/")).images
        self.assertTrue(images)
        for image in images:
            with self.subTest(src=image.get("src")):
                # A size saves the space before the image loads (no jumping).
                self.assertTrue(image.get("width", "").isdigit())
                self.assertTrue(image.get("height", "").isdigit())
                self.assertTrue(image.get("alt", "").strip())

    def test_landing_loads_nothing_from_other_sites_and_no_script(self):
        response = self.client.get("/")
        parts = parts_of(response)
        self.assertNotIn("script", parts.tags)
        for url in parts.image_files:
            self.assertFalse(url.startswith(("http:", "https:", "//")), url)
        page = response.content.decode()
        self.assertNotIn("fonts.googleapis", page)
        self.assertNotIn("@import", page)

    def test_landing_is_get_only(self):
        response = self.client.post("/")
        self.assertEqual(response.status_code, 405)


class LoggedInHomeTests(TestCase):
    def test_logged_in_person_does_not_see_the_landing_page(self):
        alice = make_user("alice")
        inbox = TodoList.objects.create(owner=alice, name="Inbox")
        self.client.force_login(alice)
        response = self.client.get("/")
        self.assertRedirects(response, inbox.get_absolute_url())
        self.assertTemplateNotUsed(response, LANDING_TEMPLATE)
