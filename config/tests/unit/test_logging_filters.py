"""Tests for config/logging_filters.py: no query string in a log line."""

import logging

from django.test import SimpleTestCase

from config.logging_filters import DropQueryString

# The format of the development server's request lines (django.server).
REQUEST_FORMAT = '"%s" %s %s'


def make_record(msg, args, **extra):
    record = logging.LogRecord(
        "django.server", logging.INFO, __file__, 1, msg, args, None
    )
    record.__dict__.update(extra)
    return record


def cleaned(requestline, status="200", size="512"):
    record = make_record(REQUEST_FORMAT, (requestline, status, size))
    DropQueryString().filter(record)
    return record.getMessage()


class DropQueryStringTests(SimpleTestCase):
    def test_search_words_are_removed(self):
        self.assertEqual(
            cleaned("GET /lists/3/?q=secret+words&sort=title HTTP/1.1"),
            '"GET /lists/3/ HTTP/1.1" 200 512',
        )

    def test_line_without_query_is_unchanged(self):
        for line in ["GET /lists/3/ HTTP/1.1", "GET /static/a%20b.css HTTP/1.1"]:
            with self.subTest(line=line):
                self.assertEqual(cleaned(line), f'"{line}" 200 512')

    def test_login_next_is_removed(self):
        self.assertEqual(
            cleaned("GET /accounts/login/?next=/lists/3/%3Fq%3Dsecret HTTP/1.1"),
            '"GET /accounts/login/ HTTP/1.1" 200 512',
        )

    def test_status_and_size_stay(self):
        record = make_record(
            REQUEST_FORMAT, ("GET /nope/?q=x HTTP/1.1", "404", "10"), status_code=404
        )
        DropQueryString().filter(record)
        self.assertEqual(record.args[1:], ("404", "10"))
        self.assertEqual(record.status_code, 404)

    def test_quotes_in_the_query_are_removed_too(self):
        for line in ["GET /?q=don't+tell HTTP/1.1", 'GET /?q=say+"hi" HTTP/1.1']:
            with self.subTest(line=line):
                message = cleaned(line)
                self.assertEqual(message, '"GET / HTTP/1.1" 200 512')
                self.assertNotIn("tell", message)
                self.assertNotIn("hi", message)

    def test_error_line_in_a_later_argument(self):
        record = make_record(
            "code %d, message %s",
            (400, "Bad request syntax ('GET /?q=secret HTTP/1.1')"),
        )
        DropQueryString().filter(record)
        self.assertEqual(
            record.getMessage(),
            "code 400, message Bad request syntax ('GET / HTTP/1.1')",
        )
        self.assertIsInstance(record.args[0], int)

    def test_never_drops_a_line(self):
        records = [
            make_record(REQUEST_FORMAT, ("GET /?q=x HTTP/1.1", "200", "1")),
            make_record(REQUEST_FORMAT, ("GET / HTTP/1.1", "200", "1")),
            make_record("code %d, message %s", (400, "Bad request ('GET /?q=x')")),
            make_record("no args here", ()),
            make_record("plain", None),
        ]
        for record in records:
            with self.subTest(msg=record.msg):
                self.assertIs(DropQueryString().filter(record), True)
        # A dict as args is left as it is.
        record = make_record("%(path)s", ({"path": "/?q=x"},))
        self.assertEqual(record.args, {"path": "/?q=x"})
        self.assertIs(DropQueryString().filter(record), True)
        self.assertEqual(record.args, {"path": "/?q=x"})
