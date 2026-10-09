import re
from datetime import timedelta

from django.utils import timezone
from playwright.sync_api import expect

from accounts.tests.helpers import TEST_PASSWORD, make_user
from todos.models import TodoList
from todos.tests.cuj.browser import BrowserTestCase

DONE = re.compile(r"\bdone\b")
RGB = re.compile(r"rgb\((\d+), (\d+), (\d+)\)")

# WCAG AA: normal text needs at least this contrast ratio with its background.
AA_CONTRAST = 4.5


def luminance(css_color):
    """The WCAG relative luminance of a solid `rgb(r, g, b)`: 0 is black, 1 is white.

    Anything else (for example the see-through `rgba(0, 0, 0, 0)` of a body with no
    background) fails the test, so it can never be read as black by mistake.
    """
    match = RGB.fullmatch(css_color)
    if match is None:
        raise AssertionError(f"Expected a solid rgb(r, g, b) color, got {css_color!r}")
    channels = []
    for value in match.groups():
        c = int(value) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(color_a, color_b):
    """The WCAG contrast ratio of two colors, from 1 (the same) to 21 (black on white)."""
    lighter, darker = sorted([luminance(color_a), luminance(color_b)], reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def make_user_with_inbox():
    """A user with an "Inbox" list, like a person who just signed up."""
    user = make_user()
    TodoList.objects.create(owner=user, name="Inbox")
    return user


# The first password field only, not "Password confirmation".
PASSWORD = re.compile(r"^Password:?$")


class PlanAndFinishTests(BrowserTestCase):
    def test_plan_and_finish(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)

        page.get_by_label("New to-do").fill("Buy milk")
        page.get_by_label("Due date").fill("2030-01-15")
        page.get_by_role("button", name="Add").click()
        page.get_by_label("New to-do").fill("Call home")
        page.get_by_role("button", name="Add").click()

        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
        expect(milk).to_contain_text("Due 15 Jan 2030")
        milk.get_by_role("button", name="Done").click()
        expect(milk).to_have_class(DONE)
        milk.get_by_role("button", name="Undo").click()
        expect(milk).not_to_have_class(DONE)

        call = page.get_by_role("listitem").filter(has_text="Call home")
        call.get_by_role("button", name="Delete").click()

        page.reload()
        expect(page.get_by_role("listitem")).to_have_count(1)
        expect(milk).to_be_visible()
        expect(call).to_have_count(0)


class SeparateListsTests(BrowserTestCase):
    def test_separate_lists(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)
        lists = page.get_by_role("navigation", name="Your lists")

        lists.get_by_role("link", name="New list").click()
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
        page.get_by_role("link", name="Delete list").click()
        expect(page.get_by_role("heading", name="Delete")).to_contain_text("1 to-do?")
        page.get_by_role("button", name="Delete list").click()

        expect(page.get_by_role("heading", name="Inbox")).to_be_visible()
        expect(lists.get_by_role("link", name="Shopping")).to_have_count(0)


class ColorSchemeTests(BrowserTestCase):
    def test_readable_in_light_and_dark(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)  # Opens the list page.

        for title in ["Buy milk", "Call home"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()
        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
        milk.get_by_role("button", name="Done").click()
        expect(milk).to_have_class(DONE)

        # One overdue to-do, so its red date is checked too.
        late = timezone.localdate() - timedelta(days=30)
        page.get_by_label("New to-do").fill("Pay rent")
        page.get_by_label("Due date").fill(late.isoformat())
        page.get_by_role("button", name="Add").click()
        expect(page.locator("li.overdue time")).to_be_visible()

        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                colors = page.evaluate(
                    """() => {
                        const color = (selector, property) =>
                            getComputedStyle(document.querySelector(selector))[property];
                        return {
                            background: color("body", "backgroundColor"),
                            text: color("li:not(.done) .title", "color"),
                            done: color("li.done .title", "color"),
                            header: color("header.site", "color"),
                            overdue: color("li.overdue time", "color"),
                        };
                    }"""
                )
                background = luminance(colors["background"])
                if scheme == "dark":
                    self.assertLess(background, 0.1, colors)
                else:
                    self.assertGreater(background, 0.9, colors)
                self.assertGreaterEqual(
                    contrast(colors["text"], colors["background"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["done"], colors["background"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["header"], colors["background"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["overdue"], colors["background"]), AA_CONTRAST
                )
                self.assertNotEqual(colors["overdue"], colors["text"], colors)


class TwoPeopleTests(BrowserTestCase):
    def sign_up(self, username):
        page = self.page
        page.get_by_role("link", name="Create an account").click()
        page.get_by_label("Username").fill(username)
        page.get_by_label(PASSWORD).fill(TEST_PASSWORD)
        page.get_by_label("Password confirmation").fill(TEST_PASSWORD)
        page.get_by_role("button", name="Sign up").click()
        expect(page.get_by_text(f"Logged in as {username}")).to_be_visible()

    def log_out(self):
        self.page.get_by_role("button", name="Log out").click()
        expect(self.page.get_by_role("button", name="Log in")).to_be_visible()

    def test_two_people_have_their_own_lists(self):
        page = self.page
        page.goto(self.live_server_url)
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


class FixATypoTests(BrowserTestCase):
    def test_fix_a_typo(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)
        page.get_by_label("New to-do").fill("Buy mlik")
        page.get_by_role("button", name="Add").click()

        row = page.get_by_role("listitem").filter(has_text="Buy mlik")
        row.get_by_role("link", name="Edit").click()
        page.get_by_label("Title").fill("Buy milk")
        page.get_by_role("button", name="Save").click()

        expect(page.get_by_role("listitem").filter(has_text="Buy milk")).to_be_visible()
        expect(page.get_by_text("Buy mlik")).to_have_count(0)


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

        bob_page.get_by_role("button", name="Leave this list").click()
        expect(bob_page.get_by_text("You left the list.")).to_be_visible()
        expect(bob_page.get_by_role("heading", name="Bob's stuff")).to_be_visible()
        expect(bob_lists.get_by_role("link", name="Groceries (alice)")).to_have_count(0)


class ClearCompletedJourneyTests(BrowserTestCase):
    def test_clear_completed(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)  # Opens the list page.

        for title in ["Buy milk", "Call home", "Pay rent"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()
        for title in ["Buy milk", "Call home"]:
            row = page.get_by_role("listitem").filter(has_text=title)
            row.get_by_role("button", name="Done").click()
            expect(row).to_have_class(DONE)

        # The question is hidden until the first click.
        yes = page.get_by_role("button", name="Yes, delete them")
        expect(yes).to_be_hidden()
        page.get_by_text("Clear completed (2)").click()
        expect(
            page.get_by_text("Delete 2 done to-dos? This cannot be undone.")
        ).to_be_visible()
        yes.click()

        expect(page.get_by_text("Deleted 2 completed to-dos.")).to_be_visible()
        expect(page.locator("ul.todos > li")).to_have_count(1)
        expect(page.get_by_role("listitem").filter(has_text="Pay rent")).to_be_visible()
        expect(page.get_by_text("Clear completed")).to_have_count(0)
