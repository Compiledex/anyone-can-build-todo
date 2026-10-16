"""Filters for Python logging, used by LOGGING in config/settings.py."""

import logging
import re

# "?" and everything after it up to a space: the query string of an address in
# a request line, for example "?q=milk&sort=title". It stops only at a space,
# not at a quote, because a quote can be part of the query (/?q=don't+tell).
QUERY_STRING = re.compile(r"\?\S*")


class DropQueryString(logging.Filter):
    """Removes the query string from every text argument of a log line.

    For the development server's request lines (the `django.server` logger):
    "GET /lists/3/?q=milk HTTP/1.1" becomes "GET /lists/3/ HTTP/1.1". The
    method, the path, the status code and the size stay. It never drops a line.
    """

    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(
                QUERY_STRING.sub("", arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True
