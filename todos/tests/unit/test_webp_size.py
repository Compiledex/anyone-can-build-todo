"""webp_size() in todos/tests/helpers.py: the size of a WebP file from its header.

The landing pictures are VP8X today, but a WebP file can start with any of the
three chunks, so each one is checked with a small made-up header.
"""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from todos.tests.helpers import webp_size


def riff(chunk, body):
    """A WebP header: RIFF, a size (not read), WEBP, then the first chunk."""
    data = b"RIFF" + b"\0\0\0\0" + b"WEBP" + chunk + b"\0\0\0\0" + body
    return data.ljust(30, b"\0")


class WebpSizeTests(SimpleTestCase):
    def size_of(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "picture.webp"
            path.write_bytes(data)
            return webp_size(path)

    def test_vp8x(self):
        body = b"\0" * 4 + (1087).to_bytes(3, "little") + (657).to_bytes(3, "little")
        self.assertEqual(self.size_of(riff(b"VP8X", body)), (1088, 658))

    def test_vp8_lossy(self):
        # 3 bytes of frame tag, the start code, then width and height.
        body = b"\0" * 3 + b"\x9d\x01\x2a" + (1088).to_bytes(2, "little")
        body += (658).to_bytes(2, "little")
        self.assertEqual(self.size_of(riff(b"VP8 ", body)), (1088, 658))

    def test_vp8l_lossless(self):
        bits = (1088 - 1) | ((658 - 1) << 14)
        body = b"\x2f" + bits.to_bytes(4, "little")
        self.assertEqual(self.size_of(riff(b"VP8L", body)), (1088, 658))

    def test_not_a_webp_file(self):
        with self.assertRaises(ValueError):
            self.size_of(b"\x89PNG" + b"\0" * 26)
