"""Test helpers for every feature: users, a TestCase that is logged in, and a page reader.

The name does not start with `test`, so the test runner does not load this
file as tests. Other test files import from it.
"""

from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from todos.models import TodoList

# Only for tests. It is not a real password for anything. It passes Django's
# password rules (it is not in the common-password list).
TEST_PASSWORD = "correct-horse-battery-staple"


def make_user(username="alice"):
    return get_user_model().objects.create_user(
        username=username, password=TEST_PASSWORD
    )


class LoggedInTestCase(TestCase):
    """A TestCase where self.client is logged in as self.user (alice).

    self.other_user (bob) exists too, to check that bob cannot see or
    change alice's things. self.todo_list is alice's "Inbox" list, and
    self.other_list is bob's list. The two lists have different names, so a
    "not shown" test cannot pass by accident.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("alice")
        cls.other_user = make_user("bob")
        cls.todo_list = TodoList.objects.create(owner=cls.user, name="Inbox")
        cls.other_list = TodoList.objects.create(
            owner=cls.other_user, name="Bob's list"
        )

    def setUp(self):
        self.client.force_login(self.user)

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def assertOtherUserGets404(self, url, method="post", data=None):
        """bob asks for alice's thing, and gets 404."""
        response = getattr(self.client_for(self.other_user), method)(url, data or {})
        self.assertEqual(response.status_code, 404)


# The fields a <label> can wrap.
FIELD_TAGS = {"input", "select", "textarea"}
# Tags that have no end tag, so they hold no text.
VOID_TAGS = {"input", "img", "source", "link", "meta", "br"}


class PageParts(HTMLParser):
    """Reads a page: its tags in order, links, buttons, labels, ids and text by id.

    Use parse_page(response). A page test that needs more (like the landing
    page's pictures) makes a subclass that adds only that.
    """

    def __init__(self):
        super().__init__()
        self.elements = []  # (tag, attributes), in the order of the page
        self.links = []  # (href, text)
        self.buttons = []  # the text of each <button>
        self.text_by_id = {}  # the text inside each element that has an id
        self.labels = []  # each <label>: {"for": ..., "text": ..., "wraps": a field}
        self.ids = set()  # every id on the page
        self._open = []  # (tag, id, text parts) of the elements still open
        self._href = None
        self._link_text = []
        self._button_text = None
        self._label = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a":
            self._href = attrs.get("href")
            self._link_text = []
        if tag == "button":
            self._button_text = []
        if tag == "label":
            self._label = {"for": attrs.get("for"), "text": "", "wraps": False}
            self.labels.append(self._label)
        elif self._label is not None and tag in FIELD_TAGS:
            if attrs.get("type") != "hidden":
                self._label["wraps"] = True
        if tag not in VOID_TAGS:
            self._open.append((tag, attrs.get("id"), []))

    def handle_data(self, data):
        if self._href is not None:
            self._link_text.append(data)
        if self._button_text is not None:
            self._button_text.append(data)
        if self._label is not None:
            self._label["text"] += data
        for _tag, _id, parts in self._open:
            parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._link_text).split())))
            self._href = None
        if tag == "button" and self._button_text is not None:
            self.buttons.append(" ".join("".join(self._button_text).split()))
            self._button_text = None
        if tag == "label" and self._label is not None:
            self._label["text"] = " ".join(self._label["text"].split())
            self._label = None
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


def parse_page(response, parser_class=PageParts):
    """The parts of the page in this response, read by parser_class."""
    parser = parser_class()
    parser.feed(response.content.decode())
    return parser
