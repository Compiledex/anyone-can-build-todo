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
# WCAG AA for things that are not text: the edge of a field, a focus ring, a line
# that marks the current choice.
UI_CONTRAST = 3.0


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


LOGIN_PAGE = "/accounts/login/"
SIGNUP_PAGE = "/accounts/signup/"

# The first password field only, not "Password confirmation".
PASSWORD = re.compile(r"^Password:?$")

# A click on a link or a form button only *starts* loading the next page. Before
# the next step, wait with expect() for something that is only on the new page.
# Otherwise the next step can act on the old page, or page.reload() can fail with
# "Not attached to an active page" while the browser swaps the pages.


class PlanAndFinishTests(BrowserTestCase):
    def test_plan_and_finish(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)

        page.get_by_label("New to-do").fill("Buy milk")
        page.get_by_label("Due date").fill("2030-01-15")
        page.get_by_role("button", name="Add").click()
        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
        expect(milk).to_contain_text("Due 15 Jan 2030")
        page.get_by_label("New to-do").fill("Call home")
        page.get_by_role("button", name="Add").click()
        call = page.get_by_role("listitem").filter(has_text="Call home")
        expect(call).to_be_visible()

        milk.get_by_role("button", name="Done").click()
        expect(milk).to_have_class(DONE)
        milk.get_by_role("button", name="Undo").click()
        expect(milk).not_to_have_class(DONE)

        call.get_by_role("button", name="Delete").click()
        expect(call).to_have_count(0)

        # Load the page again: the change is really saved.
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


class ColorSchemeTests(BrowserTestCase):
    def test_readable_in_light_and_dark(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)  # Opens the list page.

        for title in ["Buy milk", "Call home"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()
            expect(page.get_by_role("listitem").filter(has_text=title)).to_be_visible()
        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
        milk.get_by_role("button", name="Done").click()
        expect(milk).to_have_class(DONE)

        # One overdue to-do, so its red date is checked too.
        late = timezone.localdate() - timedelta(days=30)
        page.get_by_label("New to-do").fill("Pay rent")
        page.get_by_label("Due date").fill(late.isoformat())
        page.get_by_role("button", name="Add").click()
        expect(page.locator("li.overdue time")).to_be_visible()

        # One High to-do, so its colored priority label is checked too.
        page.get_by_label("New to-do").fill("Fix the roof")
        page.get_by_label("Priority").select_option(label="High")
        page.get_by_role("button", name="Add").click()
        roof = page.get_by_role("listitem").filter(has_text="Fix the roof")
        expect(roof.locator(".priority-3")).to_have_text("Priority: High")
        # "Priority: " is for screen readers: in the page, but not seen. With
        # display: none it would have no box at all, and screen readers skip it.
        hidden = roof.locator(".visually-hidden")
        expect(hidden).to_be_attached()
        box = hidden.bounding_box()
        self.assertIsNotNone(box)
        self.assertLessEqual(box["width"], 1)

        # One done High to-do: its label must be grey like the rest of the row.
        page.get_by_label("New to-do").fill("Paint the fence")
        page.get_by_label("Priority").select_option(label="High")
        page.get_by_role("button", name="Add").click()
        fence = page.get_by_role("listitem").filter(has_text="Paint the fence")
        expect(fence).to_be_visible()
        fence.get_by_role("button", name="Done").click()
        expect(fence).to_have_class(DONE)

        # One tag, so its colors are checked too.
        call = page.get_by_role("listitem").filter(has_text="Call home")
        call.get_by_role("link", name="Edit").click()
        page.get_by_label("Tags").fill("home")
        page.get_by_role("button", name="Save").click()
        expect(page.locator("li .tag")).to_have_text("#home")

        # An error under a field: a date the browser would never send.
        page.evaluate(
            """() => {
                const due = document.querySelector("form.add input[name=due_date]");
                due.type = "text";
                due.value = "31-02-2026";
            }"""
        )
        page.get_by_label("New to-do").fill("Bad date")
        page.get_by_role("button", name="Add", exact=True).click()
        expect(page.get_by_text("Enter a valid date.")).to_be_visible()

        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                colors = page.evaluate(
                    r"""() => {
                        const color = (selector, property) =>
                            getComputedStyle(document.querySelector(selector))[property];
                        return {
                            background: color("body", "backgroundColor"),
                            text: color("li:not(.done) .title", "color"),
                            done: color("li.done .title", "color"),
                            header: color("header.site .who", "color"),
                            overdue: color("li.overdue time", "color"),
                            high: color("li:not(.done) .priority-3", "color"),
                            doneHigh: color("li.done .priority-3", "color"),
                            tag: color("li .tag", "color"),
                            tag_background: color("li .tag", "backgroundColor"),
                            meta: color("li:not(.done) .meta", "color"),
                            link: color("nav.lists a[aria-current]", "color"),
                            button: color("form.add button[type=submit]", "color"),
                            buttonBackground: color(
                                "form.add button[type=submit]", "backgroundColor"
                            ),
                            error: color(".errorlist", "color"),
                            fieldEdge: color(
                                "form.add input[name=title]", "borderTopColor"
                            ),
                            filterGroup: color("nav.filter", "backgroundColor"),
                            filterLine: color(
                                "nav.filter a[aria-current]", "boxShadow"
                            ).match(/rgb\([^)]*\)/)?.[0] ?? "none",
                        };
                    }"""
                )
                # The focus ring, on a field the keyboard is on.
                field = page.locator("form.add input[name=title]")
                field.focus()
                ring = field.evaluate(
                    """el => ({
                        color: getComputedStyle(el).outlineColor,
                        style: getComputedStyle(el).outlineStyle,
                    })"""
                )
                field.blur()
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
                self.assertGreaterEqual(
                    contrast(colors["high"], colors["background"]), AA_CONTRAST
                )
                # High must not look like overdue.
                self.assertNotEqual(colors["high"], colors["overdue"], colors)
                # A done row is grey, also its priority label.
                self.assertEqual(colors["doneHigh"], colors["done"], colors)
                self.assertGreaterEqual(
                    contrast(colors["tag"], colors["tag_background"]), AA_CONTRAST
                )
                if scheme == "dark":
                    self.assertLess(luminance(colors["tag_background"]), 0.1, colors)
                for name in ["meta", "link", "error"]:
                    self.assertGreaterEqual(
                        contrast(colors[name], colors["background"]), AA_CONTRAST, name
                    )
                # An error is red, not the normal text color.
                self.assertNotEqual(colors["error"], colors["text"], colors)
                self.assertGreaterEqual(
                    contrast(colors["button"], colors["buttonBackground"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["fieldEdge"], colors["background"]), UI_CONTRAST
                )
                self.assertEqual(ring["style"], "solid")
                self.assertGreaterEqual(
                    contrast(ring["color"], colors["background"]), UI_CONTRAST
                )
                # The current filter: its line, not only its fill, stands out.
                self.assertGreaterEqual(
                    contrast(colors["filterLine"], colors["filterGroup"]), UI_CONTRAST
                )


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


# One word, wider than a phone screen, with no place to break it.
LONG_WORD = "x" * 120

# True when the element, or anything around it, has a line through its text.
# A line-through on a parent also goes through the text of everything inside it.
LINE_THROUGH_ON_SELF_OR_ANCESTOR = """element => {
    for (let e = element; e; e = e.parentElement) {
        if (getComputedStyle(e).textDecorationLine.includes("line-through")) return true;
    }
    return false;
}"""


class FixATypoTests(BrowserTestCase):
    def test_fix_a_typo(self):
        page = self.page
        # Phone width, so the check below sees a long word that does not wrap.
        page.set_viewport_size({"width": 375, "height": 800})
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)
        page.get_by_label("New to-do").fill("Buy mlik")
        page.get_by_role("button", name="Add").click()

        row = page.get_by_role("listitem").filter(has_text="Buy mlik")
        expect(row).to_be_visible()
        row.get_by_role("link", name="Edit").click()
        page.get_by_label("Title").fill("Buy milk")
        page.get_by_label("Notes").fill(
            "The lactose-free one.\nAlso ask about oat milk.\n" + LONG_WORD
        )
        page.get_by_label("Tags").fill("Work, #urgent")
        page.get_by_role("button", name="Save").click()

        row = page.get_by_role("listitem").filter(has_text="Buy milk")
        expect(row).to_be_visible()
        expect(row.locator(".tag")).to_have_text(["#urgent", "#work"])
        expect(page.get_by_text("Buy mlik")).to_have_count(0)

        # The note is closed until the person opens it.
        note = row.get_by_text("Also ask about oat milk.")
        expect(note).to_be_hidden()
        row.get_by_text("Notes").click()
        expect(row.get_by_text("The lactose-free one.")).to_be_visible()
        expect(note).to_be_visible()

        # One long word in the note wraps, so the page is not wider than the phone.
        self.assertLessEqual(
            page.evaluate("document.documentElement.scrollWidth"),
            page.evaluate("document.documentElement.clientWidth"),
        )

        # When the to-do is done, its title is crossed out, but its note is not.
        row.get_by_role("button", name="Done").click()
        expect(row).to_have_class(DONE)
        crossed_out = row.locator("details.notes").evaluate(
            LINE_THROUGH_ON_SELF_OR_ANCESTOR
        )
        self.assertFalse(crossed_out)


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
            expect(page.get_by_role("listitem").filter(has_text=title)).to_be_visible()
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


class BreakATodoIntoStepsTests(BrowserTestCase):
    def test_break_a_todo_into_steps(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)  # Opens the list page.

        page.get_by_label("New to-do").fill("Move house")
        page.get_by_role("button", name="Add").click()
        expect(
            page.get_by_role("listitem").filter(has_text="Move house")
        ).to_be_visible()
        page.get_by_text("Add steps").click()
        for title in ["Pack books", "Book a van"]:
            page.get_by_label("New step for Move house").fill(title)
            page.get_by_role("button", name="Add step").click()
            # The old page has the same "New step" field: wait for the new page.
            expect(page.locator("li.step").filter(has_text=title)).to_be_visible()

        # Full button names: the "Move house" row also contains the steps.
        page.get_by_role("button", name="Done: Pack books").click()
        expect(page.get_by_text("Steps: 1 of 2 done")).to_be_visible()

        # The steps are still open after the click, and only the step is done.
        expect(page.get_by_role("button", name="Undo: Pack books")).to_be_visible()
        van = page.locator("li.step").filter(has_text="Book a van")
        expect(van).to_be_visible()
        expect(van).not_to_have_class(DONE)
        expect(van.locator(".step-title")).not_to_have_css(
            "text-decoration-line", "line-through"
        )
        house = page.locator("ul.todos > li").filter(has_text="Move house")
        expect(house).not_to_have_class(DONE)

        # Finish the to-do. Its steps keep their own look: a not-done step is
        # not crossed out, a done step still is.
        house.get_by_role("button", name="Done", exact=True).click()
        expect(house).to_have_class(DONE)
        page.get_by_text("Steps: 1 of 2 done").click()
        expect(van.locator(".step-title")).not_to_have_css(
            "text-decoration-line", "line-through"
        )
        books = page.locator("li.step").filter(has_text="Pack books")
        expect(books.locator(".step-title")).to_have_css(
            "text-decoration-line", "line-through"
        )


class SearchJourneyTests(BrowserTestCase):
    def test_search_and_show_all(self):
        page = self.page
        self.log_in_as(make_user_with_inbox())
        page.goto(self.live_server_url)  # Opens the list page.

        for title in ["Buy milk", "Call home"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()
            expect(page.get_by_role("listitem").filter(has_text=title)).to_be_visible()
        rows = page.locator("ul.todos > li")
        expect(rows).to_have_count(2)

        box = page.get_by_label("Search to-dos")
        box.fill("milk")
        box.press("Enter")
        expect(page).to_have_url(re.compile(r"\?q=milk$"))
        expect(rows).to_have_count(1)
        expect(rows).to_contain_text("Buy milk")
        expect(page.get_by_label("Search to-dos")).to_have_value("milk")

        page.get_by_role("link", name="Show all").click()
        expect(rows).to_have_count(2)
        expect(
            page.get_by_role("listitem").filter(has_text="Call home")
        ).to_be_visible()
        expect(page.get_by_label("Search to-dos")).to_have_value("")


class ReorderJourneyTests(BrowserTestCase):
    def test_reorder_by_drag(self):
        page = self.page
        user = make_user_with_inbox()
        self.log_in_as(user)
        page.goto(self.live_server_url)  # Opens the list page.

        for title in ["First", "Second", "Third"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()
            expect(page.get_by_role("listitem").filter(has_text=title)).to_be_visible()

        list_url = user.todo_lists.get().get_absolute_url()
        page.goto(f"{self.live_server_url}{list_url}?sort=manual")
        titles = page.locator("ul.todos > li .title")
        expect(titles).to_have_text(["First", "Second", "Third"])

        def row(title):
            return page.locator("ul.todos > li").filter(has_text=title)

        # Drop on the top edge of "First", not the middle: there, before or
        # after would be a coin toss. Wait for the answer before the reload.
        with page.expect_response(lambda r: r.url.endswith("/reorder/")) as answer:
            row("Third").locator(".handle").drag_to(
                row("First"), target_position={"x": 5, "y": 2}
            )
        self.assertEqual(answer.value.status, 204)
        expect(titles).to_have_text(["Third", "First", "Second"])

        page.reload()  # Saved on the server, not only moved in the page.
        expect(titles).to_have_text(["Third", "First", "Second"])

        page.get_by_role("button", name="Move down: Third").click()
        expect(titles).to_have_text(["First", "Third", "Second"])

    def test_escape_cancels_a_drag(self):
        page = self.page
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        for title in ["First", "Second", "Third"]:
            the_list.todos.create(title=title)
        sent = []
        page.on(
            "request", lambda r: sent.append(r.url) if "/reorder/" in r.url else None
        )
        self.log_in_as(user)
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}?sort=manual")
        titles = page.locator("ul.todos > li .title")
        expect(titles).to_have_text(["First", "Second", "Third"])

        handle = (
            page.locator("ul.todos > li").filter(has_text="Third").locator(".handle")
        )
        start = handle.bounding_box()
        target = page.locator("ul.todos > li").filter(has_text="First").bounding_box()
        page.mouse.move(start["x"] + 2, start["y"] + 2)
        page.mouse.down()
        page.mouse.move(target["x"] + 5, target["y"] + 10, steps=5)
        page.mouse.move(target["x"] + 5, target["y"] + 2, steps=5)
        page.keyboard.press("Escape")
        page.mouse.up()

        expect(titles).to_have_text(["First", "Second", "Third"])
        expect(page.locator("li.dragging")).to_have_count(0)
        page.wait_for_timeout(300)  # A request would be sent at once.
        self.assertEqual(sent, [])


def overlaps(a, b):
    """True when two boxes from bounding_box() cover some of the same pixels."""
    return (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )


class RowLayoutTests(BrowserTestCase):
    def test_a_full_row_stays_readable(self):
        """A to-do with a long title and every label: nothing on top of each other."""
        page = self.page
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        rent = the_list.todos.create(
            title="Pay the electricity bill and the rent",
            priority=3,  # High
            due_date=timezone.localdate() + timedelta(days=3),
            repeat="weekly",
        )
        rent.set_tags(["home", "money"])
        self.log_in_as(user)

        # 1280 is a laptop, 390 a phone. The manual order adds the handle and Move.
        for width in [1280, 390]:
            for sort in ["", "?sort=manual"]:
                for scheme in ["light", "dark"]:
                    with self.subTest(width=width, sort=sort, scheme=scheme):
                        page.set_viewport_size({"width": width, "height": 800})
                        page.emulate_media(color_scheme=scheme)
                        page.goto(
                            f"{self.live_server_url}{the_list.get_absolute_url()}{sort}"
                        )
                        row = page.locator(f"#todo-{rent.pk}")
                        expect(row.locator(".repeat")).to_contain_text("Repeats every")

                        title = row.locator(".title").bounding_box()
                        priority = row.locator(".priority").bounding_box()
                        self.assertFalse(overlaps(title, priority), (title, priority))
                        # The title's words fit inside its own box.
                        self.assertTrue(
                            row.locator(".title").evaluate(
                                "el => el.scrollWidth <= el.clientWidth"
                            )
                        )

                        done = row.get_by_role("button", name="Done").bounding_box()
                        delete = row.get_by_role("button", name="Delete").bounding_box()
                        self.assertEqual(done["y"], delete["y"], (done, delete))


# The size of a laptop screen and of a phone (iPhone 14), in CSS pixels.
DESKTOP = {"width": 1280, "height": 800}
PHONE = {"width": 390, "height": 844}

# The first screen of the landing page, in the order a visitor reads it.
HEADLINE = "Simple to-do lists you can share"


class LandingTests(BrowserTestCase):
    def test_visitor_opens_landing_and_creates_an_account(self):
        page = self.page
        page.goto(self.live_server_url)
        expect(page.get_by_role("heading", level=1)).to_have_text(HEADLINE)

        page.get_by_role("link", name="Create an account").first.click()
        expect(page.get_by_role("heading", name="Create an account")).to_be_visible()
        self.assertEqual(page.url, f"{self.live_server_url}{SIGNUP_PAGE}")

    def test_hero_fits_the_first_screen(self):
        page = self.page
        for size in [DESKTOP, PHONE]:
            with self.subTest(size=size):
                page.set_viewport_size(size)
                page.goto(self.live_server_url)
                hero = page.locator(".hero")
                for name in ["Create an account", "Log in"]:
                    link = hero.get_by_role("link", name=name)
                    expect(link).to_be_in_viewport(ratio=1)
                # The headline is at most 2 lines.
                lines = page.evaluate(
                    """() => {
                        const h1 = document.querySelector("h1");
                        const lineHeight = parseFloat(getComputedStyle(h1).lineHeight);
                        return Math.round(h1.getBoundingClientRect().height / lineHeight);
                    }"""
                )
                self.assertLessEqual(lines, 2)
                # Nothing is wider than the screen, so there is no sideways scroll.
                width = page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(width, size["width"])

    def test_landing_is_readable_in_light_and_dark(self):
        page = self.page
        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                page.goto(self.live_server_url)
                colors = page.evaluate(
                    """() => {
                        const color = (selector, property = "color") =>
                            getComputedStyle(document.querySelector(selector))[property];
                        return {
                            background: color("body", "backgroundColor"),
                            text: color("h1"),
                            body: color(".hero p"),
                            muted: color(".muted"),
                            button: color(".button-primary"),
                            buttonBackground: color(".button-primary", "backgroundColor"),
                            link: color(".button-secondary"),
                            band: color(".band", "backgroundColor"),
                            bandText: color(".band p"),
                        };
                    }"""
                )
                for name in ["text", "body", "muted", "link"]:
                    self.assertGreaterEqual(
                        contrast(colors[name], colors["background"]), AA_CONTRAST, name
                    )
                self.assertGreaterEqual(
                    contrast(colors["button"], colors["buttonBackground"]), AA_CONTRAST
                )
                self.assertGreaterEqual(
                    contrast(colors["bandText"], colors["band"]), AA_CONTRAST
                )
                if scheme == "dark":
                    self.assertLess(luminance(colors["background"]), 0.05, colors)
                else:
                    self.assertGreater(luminance(colors["background"]), 0.8, colors)
