"""The find and order journeys in a real browser: search, drag and drop, Move buttons."""

import re

from playwright.sync_api import expect

from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.helpers import make_user_with_inbox


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
        # Record every fetch() of the page, so the test can read them, with no wait.
        page.add_init_script(
            "window.__fetchCalls = [];"
            "const realFetch = window.fetch;"
            "window.fetch = (...args) => {"
            " window.__fetchCalls.push(String(args[0]));"
            " return realFetch(...args); };"
        )
        self.log_in_as(user)
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}?sort=manual")
        titles = page.locator("ul.todos > li .title")
        expect(titles).to_have_text(["First", "Second", "Third"])

        handle = (
            page.locator("ul.todos > li").filter(has_text="Third").locator(".handle")
        )
        # The mouse only reaches what is on the screen: in a 720px-high window
        # the last row starts near the bottom edge, and no drag would start.
        page.locator("ul.todos").scroll_into_view_if_needed()
        start = handle.bounding_box()
        target = page.locator("ul.todos > li").filter(has_text="First").bounding_box()
        page.mouse.move(start["x"] + 2, start["y"] + 2)
        page.mouse.down()
        page.mouse.move(target["x"] + 5, target["y"] + 10, steps=5)
        page.mouse.move(target["x"] + 5, target["y"] + 2, steps=5)
        # The drag really started (or the test would prove nothing).
        expect(page.locator("li.dragging")).to_have_count(1)
        page.keyboard.press("Escape")
        page.mouse.up()

        expect(titles).to_have_text(["First", "Second", "Third"])
        # reorder.js removes "dragging" in its dragend handler, and in that same
        # handler it would call fetch(). So once no row is "dragging", any
        # request is already recorded.
        expect(page.locator("li.dragging")).to_have_count(0)
        self.assertEqual(page.evaluate("window.__fetchCalls"), [])
        # The recorder works: a fetch the test makes itself is recorded.
        page.evaluate("fetch('/')")
        self.assertEqual(page.evaluate("window.__fetchCalls"), ["/"])


class MoveSlotTests(BrowserTestCase):
    def test_move_buttons_keep_their_slot(self):
        """In the manual order, Edit, Done and Delete are in the same place on the
        first row (no Move up), a middle row and the last row (no Move down)."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        titles = ["First", "Second", "Third"]
        for title in titles:
            the_list.todos.create(title=title)
        self.log_in_as(user)
        page = self.page
        for width in [1280, 390]:
            with self.subTest(width=width):
                page.set_viewport_size({"width": width, "height": 800})
                page.goto(
                    f"{self.live_server_url}{the_list.get_absolute_url()}?sort=manual"
                )
                expect(page.locator("ul.todos > li .title")).to_have_text(titles)
                places = []
                for title in titles:
                    row = page.locator("ul.todos > li").filter(has_text=title)
                    places.append(
                        [
                            row.get_by_role(
                                "link", name=f"Edit {title}"
                            ).bounding_box()["x"],
                            row.get_by_role(
                                "button", name=f"Done: {title}"
                            ).bounding_box()["x"],
                            row.get_by_role(
                                "button", name=f"Delete: {title}"
                            ).bounding_box()["x"],
                        ]
                    )
                self.assertEqual(places[0], places[1], places)
                self.assertEqual(places[1], places[2], places)
                # The empty slot is not a button and is not read out.
                expect(page.get_by_role("button", name="Move up: First")).to_have_count(
                    0
                )
                expect(page.locator(".move-slot[aria-hidden=true]")).to_have_count(2)
