"""Tests for the shared test helpers that need the database (todos/tests/helpers.py).

A helper that counts wrong would let a "the number of queries does not grow"
test pass whatever the page does.
"""

from django.test import TestCase

from todos.models import TodoList
from todos.tests.helpers import count_queries


class CountQueriesTests(TestCase):
    def test_counts_each_query(self):
        self.assertEqual(count_queries(lambda: list(TodoList.objects.all())), 1)
        self.assertEqual(
            count_queries(
                lambda: (list(TodoList.objects.all()), TodoList.objects.count())
            ),
            2,
        )

    def test_no_query_is_an_error(self):
        with self.assertRaisesMessage(AssertionError, "made no database queries"):
            count_queries(lambda: None)
