import re

from playwright.sync_api import expect

from todos.tests.cuj.browser import BrowserTestCase

DONE = re.compile(r"\bdone\b")


class PlanAndFinishTests(BrowserTestCase):
    def test_plan_and_finish(self):
        page = self.page
        page.goto(self.live_server_url)

        for title in ["Buy milk", "Call home"]:
            page.get_by_label("New to-do").fill(title)
            page.get_by_role("button", name="Add").click()

        milk = page.get_by_role("listitem").filter(has_text="Buy milk")
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
