"""Labels on the list page: every field has a visible label tied to it.

A label is tied to its field by `for` (the field's id), or by wrapping it. Then a
screen reader reads the label, and a click on the label puts the cursor in the
field. Each error comes after its field, so it is read after the field.
"""

from html.parser import HTMLParser

from django.urls import reverse

from accounts.tests.helpers import LoggedInTestCase

FIELDS = {"input", "select", "textarea"}


class Labels(HTMLParser):
    """Collects each <label> (its `for`, its text, whether it wraps a field) and every id."""

    def __init__(self):
        super().__init__()
        self.labels = []
        self.ids = set()
        self._label = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "label":
            self._label = {"for": attrs.get("for"), "text": "", "wraps": False}
            self.labels.append(self._label)
        elif self._label is not None and tag in FIELDS:
            if attrs.get("type") != "hidden":
                self._label["wraps"] = True

    def handle_data(self, data):
        if self._label is not None:
            self._label["text"] += data

    def handle_endtag(self, tag):
        if tag == "label" and self._label is not None:
            self._label["text"] = " ".join(self._label["text"].split())
            self._label = None


def labels_of(response):
    parser = Labels()
    parser.feed(response.content.decode())
    return parser


class ListPageLabelTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        # A to-do, so the page has its "New step" field; alice owns the list, so
        # the page has the share form too.
        self.todo = self.todo_list.todos.create(title="Water the plants")
        self.url = self.todo_list.get_absolute_url()

    def test_every_label_is_tied_to_its_field(self):
        parts = labels_of(self.client.get(self.url))
        self.assertTrue(parts.labels)
        for label in parts.labels:
            with self.subTest(label=label["text"]):
                if label["for"]:
                    self.assertIn(label["for"], parts.ids)
                else:
                    self.assertTrue(label["wraps"], label)

    def test_every_field_has_its_visible_label(self):
        texts = {label["text"] for label in labels_of(self.client.get(self.url)).labels}
        for text in [
            "New to-do",
            "Due date",
            "Repeat",
            "Priority",
            "Search to-dos",
            "Sort by",
            "Username",
            "New step",
        ]:
            with self.subTest(text=text):
                self.assertIn(text, texts)

    def test_sort_label_has_no_colon(self):
        response = self.client.get(self.url)
        self.assertContains(response, ">Sort by</label>")

    def test_title_error_comes_after_its_field(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": ""}
        )
        content = response.content.decode()
        add_form = content[content.index('<form class="add"') :]
        self.assertIn('id="id_title_error"', add_form)
        self.assertLess(
            add_form.index('name="title"'), add_form.index('id="id_title_error"')
        )

    def test_share_field_has_a_label_not_a_placeholder(self):
        # The visible "Username" label says what to type; a placeholder with the
        # same word would only repeat it, and it disappears while typing.
        response = self.client.get(self.url)
        self.assertContains(response, 'name="username"')
        self.assertNotContains(response, 'placeholder="Username"')
