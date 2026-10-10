"""Unit tests for the status filter field of TodoQueryForm, and list_query.

A form that is only validated needs no database, so these are SimpleTestCases.
"""

from django.test import SimpleTestCase

from todos.forms import TodoQueryForm
from todos.queries import list_query


def cleaned_status(data):
    form = TodoQueryForm(data)
    form.is_valid()
    return form.cleaned_data.get("status", "")


class StatusFieldTests(SimpleTestCase):
    def test_no_status_means_all(self):
        self.assertEqual(cleaned_status({}), "")

    def test_open_and_done_are_read(self):
        self.assertEqual(cleaned_status({"status": "open"}), "open")
        self.assertEqual(cleaned_status({"status": "done"}), "done")

    def test_unknown_status_means_all(self):
        for value in ["banana", "DONE", "x" * 1000]:
            with self.subTest(value=value[:20]):
                self.assertEqual(cleaned_status({"status": value}), "")

    def test_bad_status_keeps_search(self):
        form = TodoQueryForm({"q": "milk", "status": "banana"})
        form.is_valid()
        self.assertEqual(form.cleaned_data["q"], "milk")


class ListQueryTests(SimpleTestCase):
    def test_list_query_is_empty_without_values(self):
        self.assertEqual(list_query({}), "")
        self.assertEqual(list_query({"q": "", "status": ""}), "")

    def test_list_query_keeps_search_and_changes_status(self):
        self.assertEqual(
            list_query({"q": "milk & eggs", "status": "done"}, status="open"),
            "?q=milk+%26+eggs&status=open",
        )

    def test_list_query_keeps_unknown_future_fields(self):
        # Sort (#14) adds a `sort` field; the filter links must keep it.
        self.assertEqual(
            list_query({"q": "", "sort": "title"}, status="done"),
            "?sort=title&status=done",
        )
