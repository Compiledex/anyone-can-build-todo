"""The lists and people journeys in a real browser: several lists, two accounts, sharing."""

from playwright.sync_api import expect

from accounts.tests.helpers import TEST_PASSWORD, make_user
from todos.models import TodoList
from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.helpers import LOGIN_PAGE, PASSWORD, make_user_with_inbox


class SeparateListsTests(BrowserTestCase):
    def test_separate_lists(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)
        lists = page.get_by_role("navigation", name="Your lists")

        lists.get_by_role("link", name="New list").click()
        expect(page.get_by_role("heading", name="New list")).to_be_visible()
        page.get_by_label("Name").fill("Shopping")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_role("heading", name="Shopping")).to_be_visible()
        page.get_by_label("New to-do").fill("Buy milk")
        page.get_by_role("button", name="Add").click()
        expect(page.get_by_role("listitem").filter(has_text="Buy milk")).to_be_visible()

        lists.get_by_role("link", name="Inbox").click()
        expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
        expect(page.get_by_text("Buy milk")).to_have_count(0)

        lists.get_by_role("link", name="Shopping").click()
        expect(page.get_by_role("heading", name="Shopping")).to_be_visible()
        page.get_by_role("link", name="Delete list").click()
        expect(page.get_by_role("heading", name="Delete")).to_contain_text("1 to-do?")
        page.get_by_role("button", name="Delete list").click()

        expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
        expect(lists.get_by_role("link", name="Shopping")).to_have_count(0)


class TwoPeopleTests(BrowserTestCase):
    def sign_up(self, username):
        page = self.page
        page.get_by_role("link", name="Create an account").click()
        expect(page.get_by_role("heading", name="Create an account")).to_be_visible()
        page.get_by_label("Username").fill(username)
        page.get_by_label(PASSWORD).fill(TEST_PASSWORD)
        page.get_by_label("Password confirmation").fill(TEST_PASSWORD)
        page.get_by_role("button", name="Create an account").click()
        expect(page.get_by_text(f"Logged in as {username}")).to_be_visible()

    def log_out(self):
        self.page.get_by_role("button", name="Log out").click()
        expect(self.page.get_by_role("button", name="Log in")).to_be_visible()

    def test_two_people_have_their_own_lists(self):
        page = self.page
        # The login page, not `/`: `/` is the landing page, tested in LandingTests.
        page.goto(f"{self.live_server_url}{LOGIN_PAGE}")
        expect(page.get_by_role("button", name="Log in")).to_be_visible()

        self.sign_up("alice")
        page.get_by_label("New to-do").fill("Buy milk")
        page.get_by_role("button", name="Add").click()
        expect(page.get_by_role("listitem").filter(has_text="Buy milk")).to_be_visible()
        self.log_out()

        self.sign_up("bob")
        expect(page.get_by_text("Nothing to do yet")).to_be_visible()
        expect(page.get_by_text("Buy milk")).to_have_count(0)
        self.log_out()

        page.get_by_label("Username").fill("alice")
        page.get_by_label(PASSWORD).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Log in").click()
        expect(page.get_by_text("Logged in as alice")).to_be_visible()
        expect(page.get_by_role("listitem").filter(has_text="Buy milk")).to_be_visible()


class ShareAListTests(BrowserTestCase):
    def test_share_a_list(self):
        alice_page = self.page
        self.log_in_as(make_user_with_inbox())  # alice
        bob = make_user("bob")
        make_user("carol")
        TodoList.objects.create(owner=bob, name="Bob's stuff")

        alice_page.goto(self.live_server_url)
        alice_lists = alice_page.get_by_role("navigation", name="Your lists")
        alice_lists.get_by_role("link", name="New list").click()
        expect(alice_page.get_by_role("heading", name="New list")).to_be_visible()
        alice_page.get_by_label("Name").fill("Groceries")
        alice_page.get_by_role("button", name="Save").click()
        expect(alice_page.get_by_role("heading", name="Groceries")).to_be_visible()
        alice_page.get_by_label("Username to share with").fill("bob")
        alice_page.get_by_role("button", name="Share").click()
        expect(alice_page.get_by_text("Shared with bob.")).to_be_visible()
        sharing = alice_page.get_by_role("region", name="Sharing")
        expect(sharing.get_by_role("listitem").filter(has_text="bob")).to_be_visible()

        # alice shares with carol by mistake, and removes her again.
        alice_page.get_by_label("Username to share with").fill("carol")
        alice_page.get_by_role("button", name="Share").click()
        expect(alice_page.get_by_text("Shared with carol.")).to_be_visible()
        sharing.get_by_role("button", name="Remove carol").click()
        expect(alice_page.get_by_text("carol was removed.")).to_be_visible()
        expect(sharing.get_by_role("listitem").filter(has_text="carol")).to_have_count(
            0
        )
        expect(sharing.get_by_role("listitem").filter(has_text="bob")).to_be_visible()

        # bob, in a second browser with his own cookies.
        bob_context = self.new_context()
        self.log_in_as(bob, context=bob_context)
        bob_page = bob_context.new_page()
        bob_page.goto(self.live_server_url)
        expect(bob_page.get_by_role("heading", name="Bob's stuff")).to_be_visible()
        bob_lists = bob_page.get_by_role("navigation", name="Your lists")
        shared = bob_lists.locator("#shared-lists")
        expect(shared).to_contain_text("Shared with me")
        shared.get_by_role("link", name="Groceries (alice)").click()
        expect(bob_page.get_by_text("Shared by alice")).to_be_visible()
        bob_page.get_by_label("New to-do").fill("Eggs")
        bob_page.get_by_role("button", name="Add").click()
        expect(bob_page.get_by_role("listitem").filter(has_text="Eggs")).to_be_visible()

        alice_page.reload()
        expect(
            alice_page.get_by_role("listitem").filter(has_text="Eggs")
        ).to_be_visible()

        # Leaving asks first: the button is hidden until the question opens.
        yes_leave = bob_page.get_by_role("button", name="Yes, leave the list")
        expect(yes_leave).to_be_hidden()
        bob_page.get_by_text("Leave this list").click()
        expect(
            bob_page.get_by_text("Only alice can share it with you again.")
        ).to_be_visible()
        expect(bob_page.get_by_role("heading", name="Groceries")).to_be_visible()
        yes_leave.click()
        expect(bob_page.get_by_text("You left the list.")).to_be_visible()
        expect(bob_page.get_by_role("heading", name="Bob's stuff")).to_be_visible()
        expect(bob_lists.get_by_role("link", name="Groceries (alice)")).to_have_count(0)
