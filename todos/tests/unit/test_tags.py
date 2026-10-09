from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from todos.tags import parse_tags


class ParseTagsTests(SimpleTestCase):
    def test_parse_tags_splits_and_strips(self):
        self.assertEqual(parse_tags(" work , home "), ["work", "home"])

    def test_parse_tags_lower_case_and_hash(self):
        self.assertEqual(
            parse_tags("#Important, ##WORK, # trip"), ["important", "work", "trip"]
        )

    def test_parse_tags_drops_empty_pieces(self):
        self.assertEqual(parse_tags("a,, ,b,"), ["a", "b"])
        self.assertEqual(parse_tags(""), [])
        self.assertEqual(parse_tags("#"), [])

    def test_parse_tags_drops_repeats(self):
        self.assertEqual(parse_tags("work, Work, #WORK"), ["work"])

    def test_parse_tags_joins_inner_spaces(self):
        self.assertEqual(parse_tags("work   trip"), ["work trip"])

    def test_parse_tags_too_long_name(self):
        self.assertEqual(parse_tags("a" * 30), ["a" * 30])
        with self.assertRaises(ValidationError):
            parse_tags("a" * 31)

    def test_parse_tags_too_many(self):
        ten = [f"tag{n}" for n in range(10)]
        self.assertEqual(parse_tags(", ".join(ten)), ten)
        with self.assertRaises(ValidationError):
            parse_tags(", ".join(ten + ["tag10"]))
        # 11 pieces, but one is a repeat: 10 tags.
        self.assertEqual(parse_tags(", ".join(ten + ["TAG0"])), ten)
