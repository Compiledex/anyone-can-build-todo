"""Unit tests for the sort field of TodoQueryForm, and SORT_OPTIONS.

A form that is only validated needs no database, so these are SimpleTestCases.
"""

from django.test import SimpleTestCase

from todos.forms import TodoQueryForm
from todos.queries import SORT_OPTIONS, chosen_sort


def sort_for(data):
    form = TodoQueryForm(data)
    form.is_valid()  # Fills cleaned_data.
    return chosen_sort(form)


class SortFieldTests(SimpleTestCase):
    def test_allowed_sort_keys_are_kept(self):
        for key in ["created", "due", "priority", "title"]:
            with self.subTest(key=key):
                self.assertEqual(sort_for({"sort": key}), key)

    def test_bad_sort_key_gives_default(self):
        for value in [
            "bogus",
            "-created_at",
            "todo_list__owner__password",
            "TITLE",
            "",
        ]:
            with self.subTest(value=value):
                self.assertEqual(sort_for({"sort": value}), "created")
        self.assertEqual(sort_for({}), "created")

    def test_every_option_ends_with_tie_breakers(self):
        for key, (_label, order) in SORT_OPTIONS.items():
            with self.subTest(key=key):
                self.assertEqual(tuple(order[-2:]), ("created_at", "pk"))
