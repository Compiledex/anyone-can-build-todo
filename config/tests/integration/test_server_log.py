"""The development server's request lines, printed through LOGGING.

Django's own WSGIRequestHandler.log_request writes the line to the
django.server logger; LOGGING (config/settings.py) puts DropQueryString on it.
No socket, no server and no port: the handler is made without __init__.
"""

import io
import logging

from django.core.servers.basehttp import WSGIRequestHandler
from django.test import SimpleTestCase
from django.utils.log import AdminEmailHandler


class ServerLogTests(SimpleTestCase):
    def setUp(self):
        logger = logging.getLogger("django.server")
        self.assertEqual(len(logger.handlers), 1)
        handler = logger.handlers[0]
        self.output = io.StringIO()
        old_stream = handler.setStream(self.output)
        self.addCleanup(handler.setStream, old_stream)

    def log_request(self, requestline, code, size=512):
        handler = WSGIRequestHandler.__new__(WSGIRequestHandler)
        handler.requestline = requestline
        handler.request = None
        handler.log_request(code, size)
        return self.output.getvalue()

    def test_request_line_has_no_query_string(self):
        line = self.log_request("GET /lists/3/?q=secret HTTP/1.1", 200)
        self.assertTrue(
            line.rstrip("\n").endswith('"GET /lists/3/ HTTP/1.1" 200 512'), line
        )
        self.assertNotIn("secret", line)

    def test_error_status_still_shows(self):
        line = self.log_request("GET /nope/?q=x HTTP/1.1", 404)
        self.assertIn("/nope/", line)
        self.assertIn("404", line)
        self.assertNotIn("q=x", line)

    def test_django_logger_is_unchanged(self):
        handlers = logging.getLogger("django").handlers
        self.assertTrue(
            any(type(h) is logging.StreamHandler for h in handlers), handlers
        )
        self.assertTrue(
            any(isinstance(h, AdminEmailHandler) for h in handlers), handlers
        )
