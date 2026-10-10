"""One design source: every token is set only in tokens.css.

tokens.css has only `:root` (light) and `:root` inside the dark media query.
site.css, landing.css and auth.css only use the tokens, so the landing page,
the login and sign-up pages (and later the app) cannot drift apart.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STATIC = Path(settings.BASE_DIR)
TOKENS_CSS = STATIC / "todos/static/todos/tokens.css"
SITE_CSS = STATIC / "todos/static/todos/site.css"
# Every CSS file of every app, except tokens.css. A new file is checked too.
OTHER_CSS = sorted(
    path for path in STATIC.glob("*/static/**/*.css") if path != TOKENS_CSS
)
# A page's own CSS: every other file except the shared site.css.
PAGE_CSS = [path for path in OTHER_CSS if path != SITE_CSS]
# A custom property being declared, like `--accent: #1f4f8f;`: at the start of a
# line, or after `{` or `;`. Not `var(--accent)`, and not a selector.
SETS_A_TOKEN = re.compile(r"(?:^|[{;])\s*--[\w-]+\s*:", re.M)
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
DARK_QUERY = "@media (prefers-color-scheme: dark)"
COLORS = [
    "--bg",
    "--band",
    "--text",
    "--muted",
    "--border",
    "--surface",
    "--control",
    "--accent",
    "--accent-hover",
    "--on-accent",
    "--danger",
]
NOT_COLORS = ["--radius", "--font", "--control-height", "--control-height-small"]


def tokens_in(css):
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css))


class TokensCssTests(SimpleTestCase):
    def setUp(self):
        css = COMMENT.sub("", TOKENS_CSS.read_text())
        light, _, dark = css.partition(DARK_QUERY)
        self.light = tokens_in(light)
        self.dark = tokens_in(dark)
        self.css = css

    def test_every_color_has_a_light_and_a_dark_value(self):
        for token in COLORS:
            with self.subTest(token=token):
                self.assertIn(token, self.light)
                self.assertIn(token, self.dark)

    def test_sizes_and_font_are_tokens_too(self):
        for token in NOT_COLORS:
            with self.subTest(token=token):
                self.assertIn(token, self.light)

    def test_tokens_css_has_only_root_blocks(self):
        selectors = re.findall(r"([^{}]+)\{", self.css)
        self.assertEqual([s.strip() for s in selectors], [":root", DARK_QUERY, ":root"])

    def test_every_css_file_is_checked(self):
        names = {path.name for path in OTHER_CSS}
        self.assertLessEqual({"site.css", "landing.css", "auth.css"}, names)

    def test_other_css_sets_no_tokens_and_has_no_root(self):
        for path in OTHER_CSS:
            with self.subTest(path=path.name):
                css = COMMENT.sub("", path.read_text())
                self.assertIsNone(SETS_A_TOKEN.search(css), "set tokens in tokens.css")
                self.assertNotIn(":root", css)

    def test_page_css_has_no_shared_rules(self):
        shared = [".site-nav", ".site-footer", ".button-primary", ".wordmark", ".field"]
        for path in PAGE_CSS:
            css = path.read_text()
            for selector in shared:
                with self.subTest(path=path.name, selector=selector):
                    self.assertNotIn(selector, css)

    def test_no_generic_actions_class(self):
        # The app's to-do row uses `.actions`; the shared CSS must not style it.
        for path in OTHER_CSS:
            with self.subTest(path=path.name):
                self.assertIsNone(re.search(r"\.actions\b", path.read_text()))
