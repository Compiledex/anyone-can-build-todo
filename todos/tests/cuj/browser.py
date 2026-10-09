import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright

# The server runs on this computer, so 5 seconds is plenty. Playwright's
# default of 30 seconds makes a broken test slow to fail.
TIMEOUT_MS = 5_000


class BrowserTestCase(StaticLiveServerTestCase):
    """A real server and a real Chromium browser, for CUJ tests.

    Each test gets a fresh page, so tests cannot see each other's cookies.
    """

    @classmethod
    def setUpClass(cls):
        # Playwright runs an event loop in this thread, and Django then refuses
        # to use the database. That check is not needed in tests, so turn it off
        # here. It is never turned off for the real server.
        cls._async_unsafe = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        expect.set_options(timeout=TIMEOUT_MS)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()
        if cls._async_unsafe is None:
            os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        else:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = cls._async_unsafe

    def setUp(self):
        self.context = self.browser.new_context()
        self.context.set_default_timeout(TIMEOUT_MS)
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
