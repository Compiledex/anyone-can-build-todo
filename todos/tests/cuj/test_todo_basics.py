"""The everyday to-do journeys in a real browser: add, edit, done, undo, delete, clear completed."""

from playwright.sync_api import expect

from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.helpers import DONE, make_user_with_inbox


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


class KeepThePlaceTests(BrowserTestCase):
    def test_done_keeps_the_place(self):
        """On a long list, Done and Delete open the page at the same place."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        todos = [the_list.todos.create(title=f"Task {n}") for n in range(1, 41)]
        phone = self.browser.new_context(viewport={"width": 390, "height": 844})
        self.addCleanup(phone.close)
        self.log_in_as(user, phone)
        page = phone.new_page()
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}")

        row_30 = page.locator(f"#todo-{todos[29].pk}")
        row_30.get_by_role("button", name="Done: Task 30").click()
        expect(row_30).to_have_class(DONE)
        expect(row_30).to_be_in_viewport()
        expect(page.get_by_label("New to-do")).not_to_be_focused()

        row_30.get_by_role("button", name="Delete: Task 30").click()
        expect(row_30).to_have_count(0)
        expect(page.locator(f"#todo-{todos[30].pk}")).to_be_in_viewport()


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


class DeleteAndUndoTests(BrowserTestCase):
    def test_delete_and_undo(self):
        """Delete by mistake, click Undo: the to-do is back in its place, with its step."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        the_list.todos.create(title="Buy milk")
        middle = the_list.todos.create(title="Call the bank")
        middle.subtasks.create(title="Find the card")
        the_list.todos.create(title="Water plants")
        self.log_in_as(user)
        page = self.page
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}")

        rows = page.locator("ul.todos > li")
        page.get_by_role("button", name="Delete: Call the bank").click()
        expect(page.get_by_text("Deleted “Call the bank”.")).to_be_visible()
        expect(rows).to_have_count(2)

        page.get_by_role("button", name="Undo delete: Call the bank").click()
        expect(page.get_by_text("Restored “Call the bank”.")).to_be_visible()
        expect(rows).to_have_count(3)
        expect(rows.nth(0)).to_contain_text("Buy milk")
        expect(rows.nth(1)).to_contain_text("Call the bank")
        expect(rows.nth(2)).to_contain_text("Water plants")
        restored = page.locator(f"#todo-{middle.pk}")
        expect(restored).to_be_in_viewport()
        expect(restored.get_by_text("Steps: 0 of 1 done")).to_be_visible()
        expect(
            page.get_by_role("button", name="Undo delete: Call the bank")
        ).to_have_count(0)
