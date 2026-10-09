"""Turn the text a person types in the Tags field into clean tag names.

Plain Python: no database, no request.
"""

import re

from django.core.exceptions import ValidationError

MAX_TAG_LENGTH = 30
MAX_TAGS = 10


def parse_tags(text):
    """`"#Work, home,, work"` gives `["work", "home"]`.

    Split on commas, strip spaces and a leading `#`, join inner spaces, make
    lower case, drop empty pieces and repeats. Raises ValidationError when a
    name is too long or there are too many tags.
    """
    names = []
    for piece in text.split(","):
        name = re.sub(r"\s+", " ", piece.strip().lstrip("#").strip()).lower()
        if name and name not in names:
            names.append(name)
    for name in names:
        if len(name) > MAX_TAG_LENGTH:
            raise ValidationError(
                f"A tag can have at most {MAX_TAG_LENGTH} characters: “{name}”."
            )
    if len(names) > MAX_TAGS:
        raise ValidationError(f"A to-do can have at most {MAX_TAGS} tags.")
    return names
