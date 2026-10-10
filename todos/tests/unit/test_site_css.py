"""One design source: the colors and shared parts live only in site.css.

So the landing page and the login and sign-up pages cannot drift apart.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

SITE_CSS = Path(settings.BASE_DIR, "todos/static/todos/site.css")
PAGE_CSS = [
    Path(settings.BASE_DIR, "todos/static/todos/landing.css"),
]
# A custom property being set, like `--accent: #1f4f8f;`.
SETS_A_TOKEN = re.compile(r"--[\w-]+\s*:")
# Rules that belong to every page of the site, not to one page.
SHARED_SELECTORS = [
    ":root",
    ".site-nav",
    ".site-footer",
    ".button-primary",
    ".wordmark",
]


class SiteCssTests(SimpleTestCase):
    def test_site_css_has_the_tokens_for_light_and_dark(self):
        css = SITE_CSS.read_text()
        for token in ["--bg", "--text", "--muted", "--accent", "--radius", "--error"]:
            with self.subTest(token=token):
                self.assertEqual(
                    len(re.findall(rf"{token}\s*:", css)),
                    2 if token != "--radius" else 1,
                )
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_page_css_sets_no_tokens_and_no_shared_rules(self):
        for path in PAGE_CSS:
            with self.subTest(path=path.name):
                css = path.read_text()
                self.assertIsNone(
                    SETS_A_TOKEN.search(css), "set colors in site.css only"
                )
                for selector in SHARED_SELECTORS:
                    self.assertNotIn(selector, css)
