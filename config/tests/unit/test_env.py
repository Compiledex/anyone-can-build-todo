import secrets

from django.core.checks.security import base as django_security
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.env import (
    INSECURE_PREFIX,
    LAPTOP_SECRET_KEY,
    MIN_LENGTH,
    MIN_UNIQUE_CHARACTERS,
    read_debug,
    read_secret_key,
)

MAKE_A_KEY = "secrets.token_urlsafe(50)"


class ReadDebugTests(SimpleTestCase):
    def test_debug_not_set_is_true(self):
        self.assertIs(read_debug({}), True)

    def test_debug_true_any_case(self):
        for value in ["True", "true", "TRUE", " true "]:
            with self.subTest(value=value):
                self.assertIs(read_debug({"DJANGO_DEBUG": value}), True)

    def test_debug_false_any_case(self):
        for value in ["False", "false", "FALSE", " False", "false\n"]:
            with self.subTest(value=value):
                self.assertIs(read_debug({"DJANGO_DEBUG": value}), False)

    def test_debug_unknown_value_stops(self):
        for value in ["", "0", "1", "yes", "no", "Flase"]:
            with self.subTest(value=value):
                with self.assertRaisesMessage(ImproperlyConfigured, "True or False"):
                    read_debug({"DJANGO_DEBUG": value})

    def test_debug_message_has_no_part_of_the_value(self):
        # A fixed key-like value, so the test can never fail by chance.
        value = "q7Zx" + "Kw9vLm3RtY8pNb2HjC5sFd6GaE4uXo1VnB0iTe7MzQ" + "Ws9R"
        with self.assertRaises(ImproperlyConfigured) as caught:
            read_debug({"DJANGO_DEBUG": value})
        message = str(caught.exception)
        for start in range(len(value) - 3):
            piece = value[start : start + 4]
            self.assertNotIn(piece, message)
        self.assertIn(f"(length {len(value)})", message)

    def test_debug_message_length_of_one_character(self):
        with self.assertRaises(ImproperlyConfigured) as caught:
            read_debug({"DJANGO_DEBUG": "0"})
        self.assertIn("(length 1)", str(caught.exception))


class ReadSecretKeyTests(SimpleTestCase):
    def test_debug_on_uses_laptop_key(self):
        self.assertEqual(read_secret_key({}, debug=True), LAPTOP_SECRET_KEY)

    def test_debug_on_uses_given_key(self):
        env = {"DJANGO_SECRET_KEY": "short"}
        self.assertEqual(read_secret_key(env, debug=True), "short")

    def test_debug_off_missing_key_stops(self):
        for env in [{}, {"DJANGO_SECRET_KEY": ""}]:
            with self.subTest(env=env):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    read_secret_key(env, debug=False)
                message = str(caught.exception)
                self.assertIn("DJANGO_SECRET_KEY is not set", message)
                self.assertIn(MAKE_A_KEY, message)

    def test_debug_off_laptop_key_stops(self):
        env = {"DJANGO_SECRET_KEY": LAPTOP_SECRET_KEY}
        with self.assertRaisesMessage(ImproperlyConfigured, "too weak"):
            read_secret_key(env, debug=False)

    def test_debug_off_weak_keys_stop(self):
        weak_keys = {
            "49 characters": secrets.token_urlsafe(50)[:49],
            "4 different characters": "abcd" * 15,
            "insecure prefix": "django-insecure-" + secrets.token_urlsafe(50)[:44],
            "only spaces": " " * 60,
        }
        for name, key in weak_keys.items():
            with self.subTest(name):
                with self.assertRaises(ImproperlyConfigured) as caught:
                    read_secret_key({"DJANGO_SECRET_KEY": key}, debug=False)
                self.assertIn("too weak", str(caught.exception))
                self.assertIn(MAKE_A_KEY, str(caught.exception))

    def test_debug_off_strong_key_is_used(self):
        strong = secrets.token_urlsafe(50)
        edge = "abcde" * 10  # exactly 50 characters, exactly 5 different ones
        for key in [strong, edge]:
            with self.subTest(key_length=len(key)):
                env = {"DJANGO_SECRET_KEY": key}
                self.assertEqual(read_secret_key(env, debug=False), key)

    def test_limits_match_django(self):
        self.assertEqual(MIN_LENGTH, django_security.SECRET_KEY_MIN_LENGTH)
        self.assertEqual(
            MIN_UNIQUE_CHARACTERS, django_security.SECRET_KEY_MIN_UNIQUE_CHARACTERS
        )
        self.assertEqual(INSECURE_PREFIX, django_security.SECRET_KEY_INSECURE_PREFIX)

    def test_weak_key_message_does_not_show_the_key(self):
        env = {"DJANGO_SECRET_KEY": "x" * 10 + "SECRETPART"}
        with self.assertRaises(ImproperlyConfigured) as caught:
            read_secret_key(env, debug=False)
        self.assertNotIn("SECRETPART", str(caught.exception))
