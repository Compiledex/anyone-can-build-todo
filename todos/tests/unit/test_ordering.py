"""Unit tests for reading a posted order (parse_ids) and for can_reorder.

No database: parse_ids is plain Python, and a form that is only validated
needs no database either.
"""

from django.test import SimpleTestCase

from todos.forms import TodoQueryForm
from todos.ordering import parse_ids
from todos.queries import can_reorder


class ParseIdsTests(SimpleTestCase):
    def test_parse_ids_keeps_order(self):
        self.assertEqual(parse_ids(["3", "1", "2"]), [3, 1, 2])

    def test_parse_ids_rejects_text(self):
        for values in [["3", "abc"], ["3", ""], ["-1"], ["1.5"], [" 2"]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_ids(values)

    def test_parse_ids_rejects_repeats(self):
        with self.assertRaises(ValueError):
            parse_ids(["3", "3"])


class CanReorderTests(SimpleTestCase):
    def test_can_reorder_only_manual_without_search_or_filter(self):
        self.assertTrue(can_reorder(TodoQueryForm({"sort": "manual"})))
        for data in [
            {"sort": "manual", "q": "milk"},
            {"sort": "manual", "status": "open"},
            # A form that is not valid never allows reordering.
            {"sort": "manual", "status": "bogus"},
            {"sort": "title"},
            {},
        ]:
            with self.subTest(data=data):
                self.assertFalse(can_reorder(TodoQueryForm(data)))
