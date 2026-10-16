"""Delete my account in a real browser: the link in the header, the confirm page, the end."""

import re

from playwright.sync_api import expect

from accounts.tests.helpers import TEST_PASSWORD, make_user
from todos.models import TodoList
from todos.tests.cuj.browser import BrowserTestCase

# A small phone. The header must stay one short bar there.
PHONE = {"width": 375, "height": 812}

HEADER_SIZES = """() => ({
    header: document.querySelector("header.site").getBoundingClientRect().height,
    who: document.querySelector(".who").getBoundingClientRect().width,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
})"""


class DeleteAccountJourney(BrowserTestCase):
    def test_delete_my_account(self):
        alice = make_user("alice")
        bob = make_user("bob")
        TodoList.objects.create(owner=alice, name="Inbox")
        TodoList.objects.create(owner=alice, name="Family").members.add(bob)
        TodoList.objects.create(owner=bob, name="Bob's list")

        # bob, in a second browser, sees alice's shared list.
        bob_context = self.new_context()
        self.log_in_as(bob, context=bob_context)
        bob_page = bob_context.new_page()
        bob_page.goto(self.live_server_url)
        bob_lists = bob_page.get_by_role("navigation", name="Your lists")
        expect(bob_lists.get_by_role("link", name="Family (alice)")).to_be_visible()

        page = self.page
        page.set_viewport_size(PHONE)
        self.log_in_as(alice)
        page.goto(self.live_server_url)
        expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
        sizes = page.evaluate(HEADER_SIZES)
        self.assertLessEqual(sizes["header"], 64)
        self.assertGreaterEqual(sizes["who"], 100)
        self.assertLessEqual(sizes["scrollWidth"], sizes["innerWidth"])

        page.get_by_role("link", name="Logged in as alice").click()
        expect(page.get_by_role("heading", name="Delete your account")).to_be_visible()
        expect(page.get_by_text("2 lists and their 0 to-dos")).to_be_visible()
        expect(page.get_by_text("“Family” (1 member)")).to_be_visible()

        password = page.get_by_label("Password", exact=True)
        delete = page.get_by_role("button", name="Delete my account")
        password.fill("not-the-password")
        delete.click()
        expect(page.get_by_text("Wrong password. Nothing was deleted.")).to_be_visible()

        password.fill(TEST_PASSWORD)
        delete.click()
        expect(page.get_by_role("status")).to_contain_text("Your account was deleted.")
        expect(page).to_have_url(f"{self.live_server_url}/")

        # Her password no longer logs in.
        page.goto(f"{self.live_server_url}/accounts/login/")
        page.get_by_label("Username").fill("alice")
        page.get_by_label(re.compile(r"^Password$")).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_text("Please enter a correct username")).to_be_visible()

        # bob reloads: alice's list is gone, his own stays.
        bob_page.reload()
        expect(bob_page.get_by_role("heading", name="Bob's list")).to_be_visible()
        expect(bob_lists.get_by_role("link", name="Family (alice)")).to_have_count(0)
