"""Tests for the Python functions that SQLite uses (todos/sqlite_functions.py).

No database: the functions are plain Python. The integration tests check
that SQLite really uses them.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from todos.sqlite_functions import (
    add_functions,
    casefold,
    compare_norwegian,
    norwegian_key,
)


class CaseFoldTests(SimpleTestCase):
    def test_casefold_makes_nordic_letters_one_case(self):
        self.assertEqual(casefold("ÆØÅ"), "æøå")
        self.assertEqual(casefold("Straße"), "strasse")

    def test_casefold_joins_a_split_letter(self):
        split = "å"  # "a" plus a small ring (NFD), as a Mac can send it.
        self.assertEqual(casefold(split), casefold("å"))

    def test_casefold_keeps_none(self):
        self.assertIsNone(casefold(None))


class NorwegianKeyTests(SimpleTestCase):
    def test_norwegian_order(self):
        titles = ["Ål", "Zebra", "øl", "Ærend", "apple", "Banana"]
        self.assertEqual(
            sorted(titles, key=norwegian_key),
            ["apple", "Banana", "Zebra", "Ærend", "øl", "Ål"],
        )

    def test_swedish_letters_sort_as_norwegian(self):
        self.assertEqual(
            sorted(["øre", "Ärlig", "örn", "ære"], key=norwegian_key),
            ["ære", "Ärlig", "øre", "örn"],
        )

    def test_accented_letter_sorts_with_its_base_letter(self):
        self.assertEqual(
            sorted(["fisk", "élan", "dag"], key=norwegian_key), ["dag", "élan", "fisk"]
        )
        self.assertEqual(
            sorted(["vann", "über", "tak"], key=norwegian_key), ["tak", "über", "vann"]
        )

    def test_case_does_not_change_the_key(self):
        self.assertEqual(norwegian_key("ÅL"), norwegian_key("ål"))
        self.assertEqual(compare_norwegian("ÅL", "ål"), 0)

    def test_compare_answers_minus_one_zero_one(self):
        self.assertEqual(compare_norwegian("z", "æ"), -1)
        self.assertEqual(compare_norwegian("å", "ø"), 1)
        self.assertEqual(compare_norwegian("a", "a"), 0)
        self.assertEqual(compare_norwegian("al", "ale"), -1)

    def test_signs_and_digits_before_letters_other_letters_after(self):
        self.assertEqual(
            sorted(["b", "2", " x", "ж", "å"], key=norwegian_key),
            [" x", "2", "b", "å", "ж"],
        )

    def test_odd_text_does_not_crash(self):
        for text in ["", "🙂", "\x00", "ﬁ", "İstanbul", "ǿ", "Å" * 200]:
            with self.subTest(text=text):
                self.assertIsInstance(norwegian_key(text), tuple)
                self.assertIsInstance(casefold(text), str)

    def test_combining_marks_are_dropped(self):
        self.assertEqual(norwegian_key("İstanbul"), norwegian_key("istanbul"))
        self.assertEqual(norwegian_key("ǿ"), norwegian_key("ø"))


class AddFunctionsTests(SimpleTestCase):
    def test_add_functions_skips_a_connection_that_is_not_open(self):
        wrapper = SimpleNamespace(vendor="sqlite", connection=None)
        add_functions(sender=None, connection=wrapper)  # Raises nothing.

    def test_add_functions_skips_other_databases(self):
        class OtherDatabase:
            vendor = "postgresql"

            @property
            def connection(self):
                raise AssertionError("the real connection must not be touched")

        add_functions(sender=None, connection=OtherDatabase())
