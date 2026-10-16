"""The steps and repeat journeys in a real browser: steps inside a to-do, and a repeating to-do."""

from datetime import timedelta

from django.utils import timezone
from playwright.sync_api import expect

from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.helpers import DONE, make_user_with_inbox


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
        house.get_by_role("button", name="Done: Move house").click()
        expect(house).to_have_class(DONE)
        page.get_by_text("Steps: 1 of 2 done").click()
        expect(van.locator(".step-title")).not_to_have_css(
            "text-decoration-line", "line-through"
        )
        books = page.locator("li.step").filter(has_text="Pack books")
        expect(books.locator(".step-title")).to_have_css(
            "text-decoration-line", "line-through"
        )


class KeyboardStepsTests(BrowserTestCase):
    def test_add_steps_with_the_keyboard(self):
        """After "Add step", the cursor is in "New step" again: type, Enter, type."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        the_list.todos.create(title="Move house")
        self.log_in_as(user)
        page = self.page
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}")
        page.get_by_text("Add steps").click()
        field = page.get_by_label("New step for Move house")
        field.fill("Pack books")
        field.press("Enter")
        expect(page.locator("li.step").filter(has_text="Pack books")).to_be_visible()
        expect(field).to_be_focused()
        expect(page.get_by_label("New to-do")).not_to_be_focused()

        page.keyboard.type("Book a van")  # No click: the field has the cursor.
        page.keyboard.press("Enter")
        expect(page.locator("li.step").filter(has_text="Book a van")).to_be_visible()
        expect(page.locator("li.step")).to_have_count(2)
        expect(page.get_by_text("Steps: 0 of 2 done")).to_be_visible()


class KeepAChangedCopyTests(BrowserTestCase):
    def test_undo_keeps_a_changed_copy(self):
        """Done on a weekly to-do, change the copy, Undo: the changed copy stays."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        the_list.todos.create(
            title="Water the plants",
            due_date=timezone.localdate() + timedelta(days=3),
            repeat="weekly",
        )
        self.log_in_as(user)
        page = self.page
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}")

        page.get_by_role("button", name="Done: Water the plants").click()
        copy = page.locator("ul.todos > li:not(.done)")
        expect(copy).to_have_count(1)
        copy.get_by_role("link", name="Edit Water the plants").click()
        page.get_by_label("Title").fill("Water the plants and the herbs")
        page.get_by_role("button", name="Save").click()

        changed = page.locator("ul.todos > li").filter(
            has=page.locator(".title", has_text="Water the plants and the herbs")
        )
        expect(changed).to_have_count(1)
        page.get_by_role("button", name="Undo: Water the plants").click()
        expect(
            page.get_by_text("was kept, because it was changed after it was made.")
        ).to_be_visible()
        expect(page.locator("ul.todos > li")).to_have_count(2)
        expect(changed).to_have_count(1)
        expect(changed).not_to_have_class(DONE)
