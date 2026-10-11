"""Python functions that SQLite uses for Norwegian sorting and for search.

SQLite's own LOWER() and LIKE only know the letters A to Z. These functions
know every letter. They are added to every new SQLite connection (see
TodosConfig.ready in apps.py), also in the tests and in manage.py commands.

The "norwegian" collation is only for ORDER BY. Never use it for =, UNIQUE,
DISTINCT or GROUP BY: it says "Ål" equals "ål", and a database rule built on
a Python function breaks when the function is missing.
"""

import functools
import unicodedata

COLLATION = "norwegian"  # the name SQL uses: ORDER BY title COLLATE "norwegian"
CASEFOLD = "casefold"  # the name SQL uses: casefold(title)

# The Norwegian letters after z. ä counts as æ and ö as ø (the simple rule).
NORDIC = {"æ": (1, 26), "ä": (1, 26), "ø": (1, 27), "ö": (1, 27), "å": (1, 28)}


def casefold(text):
    """The text in one case, for comparing: NFC, then str.casefold(). None stays None.

    NFC first: on a Mac "å" can arrive as "a" plus a small ring; NFC joins them.
    SQL passes NULL as None (a to-do without tags, in the tag sub-query).
    """
    if text is None:
        return None
    return unicodedata.normalize("NFC", text).casefold()


def _letter_pair(ch):
    """The pair for one character with no combining mark."""
    if ch in NORDIC:
        return NORDIC[ch]
    if "a" <= ch <= "z":
        return (1, ord(ch) - ord("a"))
    if ch.isalpha():
        return (2, ord(ch))
    return (0, ord(ch))


@functools.lru_cache(maxsize=4096)
def norwegian_key(text):
    """A sort key: a to z, then æ, ø, å. Upper and lower case are the same.

    A tuple of (group, number) pairs: 0 for spaces, digits and signs (before
    a), 1 for a to z, æ, ø, å, 2 for other letters (after å). Another letter
    with an accent counts as its base letter. A tuple, because the answer is
    cached and must not be changeable. `text` must be a str: SQLite never
    passes NULL to a collation, and the title column is NOT NULL.
    """
    pairs = []
    for ch in casefold(text):
        if ch in NORDIC:
            pairs.append(NORDIC[ch])
            continue
        for part in unicodedata.normalize("NFKD", ch):
            if not unicodedata.combining(part):
                pairs.append(_letter_pair(part))
    return tuple(pairs)


def compare_norwegian(a, b):
    """-1, 0 or 1, the way SQLite wants a collation to answer."""
    key_a, key_b = norwegian_key(a), norwegian_key(b)
    return (key_a > key_b) - (key_a < key_b)


def add_functions(sender, connection, **kwargs):
    """The connection_created signal handler. Only for SQLite.

    It does nothing for another database, or for a connection wrapper that
    has not opened the database yet (it gets them from the signal later).
    """
    if connection.vendor != "sqlite" or connection.connection is None:
        return
    connection.connection.create_collation(COLLATION, compare_norwegian)
    connection.connection.create_function(CASEFOLD, 1, casefold, deterministic=True)
