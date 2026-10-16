from datetime import timedelta

from django.utils import timezone
from playwright.sync_api import expect

from accounts.tests.helpers import make_user
from todos.models import TodoList
from todos.tests.cuj.browser import BrowserTestCase
from todos.tests.cuj.helpers import (
    AA_CONTRAST,
    DONE,
    LOGIN_PAGE,
    SIGNUP_PAGE,
    UI_CONTRAST,
    contrast,
    luminance,
    make_user_with_inbox,
)


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
        hidden = roof.locator(".priority-3 .visually-hidden")
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
                # Colors change with a short transition: read them after it.
                page.wait_for_function("document.getAnimations().length === 0")
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
                            invalidEdge: color(
                                "form.add input[aria-invalid=true]", "borderTopColor"
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
                # The field with the error has a red edge, in the error's color.
                self.assertEqual(colors["invalidEdge"], colors["error"], colors)
                self.assertGreaterEqual(
                    contrast(colors["invalidEdge"], colors["background"]), UI_CONTRAST
                )
                self.assertEqual(ring["style"], "solid")
                self.assertGreaterEqual(
                    contrast(ring["color"], colors["background"]), UI_CONTRAST
                )
                # The current filter: its line, not only its fill, stands out.
                self.assertGreaterEqual(
                    contrast(colors["filterLine"], colors["filterGroup"]), UI_CONTRAST
                )


def overlaps(a, b):
    """True when two boxes from bounding_box() cover some of the same pixels."""
    return (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )


def inside(inner, outer):
    """True if the box `inner` is inside the box `outer` (left and right)."""
    return inner["x"] >= outer["x"] - 0.5 and (
        inner["x"] + inner["width"] <= outer["x"] + outer["width"] + 0.5
    )


# 140 characters, and a link of 80 characters with no space to break at.
LONG_TITLE = (
    "Pay the electricity bill and the rent, then call the landlords about the "
    "broken window in the kitchen and ask when the painters can come by."
)
LONG_URL = "https://example.org/" + "a" * 60


class RowLayoutTests(BrowserTestCase):
    def test_a_full_row_stays_readable(self):
        """A to-do with a long title and every label: nothing on top of each other."""
        self.assertEqual(len(LONG_TITLE), 140)
        self.assertEqual(len(LONG_URL), 80)
        page = self.page
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        rent = the_list.todos.create(
            title=LONG_TITLE,
            priority=3,  # High
            due_date=timezone.localdate() + timedelta(days=3),
            repeat="weekly",
            description=f"The form is at {LONG_URL} for the meter reading.",
        )
        rent.set_tags(["home", "money"])
        for step in ["Read the meter", "Find the contract"]:
            rent.subtasks.create(title=step)
        self.log_in_as(user)

        # 1280 is a laptop, 390 and 320 phones. The manual order adds the handle
        # and Move. ?open= opens the steps.
        for width in [1280, 390, 320]:
            for sort in ["?", "?sort=manual&"]:
                for scheme in ["light", "dark"]:
                    with self.subTest(width=width, sort=sort, scheme=scheme):
                        page.set_viewport_size({"width": width, "height": 800})
                        page.emulate_media(color_scheme=scheme)
                        page.goto(
                            f"{self.live_server_url}{the_list.get_absolute_url()}"
                            f"{sort}open={rent.pk}"
                        )
                        row = page.locator(f"#todo-{rent.pk}")
                        expect(row.locator(".repeat")).to_contain_text("Repeats every")
                        row.locator("details.notes summary").click()
                        expect(row.locator("details.notes p")).to_be_visible()
                        expect(row.locator("details.steps ul")).to_be_visible()

                        title = row.locator(".title").bounding_box()
                        priority = row.locator(".priority").bounding_box()
                        self.assertFalse(overlaps(title, priority), (title, priority))
                        # The title's words fit inside its own box.
                        self.assertTrue(
                            row.locator(".title").evaluate(
                                "el => el.scrollWidth <= el.clientWidth"
                            )
                        )

                        # The full names: not the steps' "Done: Read the meter".
                        done = row.get_by_role("button", name=f"Done: {LONG_TITLE}")
                        delete = row.get_by_role("button", name=f"Delete: {LONG_TITLE}")
                        done, delete = done.bounding_box(), delete.bounding_box()
                        self.assertEqual(done["y"], delete["y"], (done, delete))

                        # On a laptop, the buttons are to the right of the title,
                        # at the top of the row. On a phone, on their own line.
                        actions = row.locator(".actions").bounding_box()
                        main = row.locator(".main").bounding_box()
                        if width == 1280:
                            self.assertGreaterEqual(
                                actions["x"], title["x"] + title["width"]
                            )
                            self.assertLessEqual(abs(actions["y"] - title["y"]), 8)
                            # A mouse: the summaries keep their small laptop size
                            # (the 44px is only for a finger).
                            for part in ["details.notes", "details.steps"]:
                                summary = row.locator(f"{part} > summary")
                                height = summary.bounding_box()["height"]
                                self.assertLess(height, TOUCH_HEIGHT, part)
                        else:
                            self.assertGreaterEqual(
                                actions["y"], main["y"] + main["height"]
                            )
                        # The open notes and steps stay inside the row.
                        box = row.bounding_box()
                        for part in ["details.notes", "details.steps"]:
                            part_box = row.locator(part).bounding_box()
                            self.assertTrue(inside(part_box, box), (part, part_box))
                        # Nothing is wider than the screen.
                        self.assertTrue(
                            page.evaluate(
                                "document.documentElement.scrollWidth"
                                " <= document.documentElement.clientWidth"
                            )
                        )


# What makes two buttons look the same, read with getComputedStyle.
BUTTON_LOOK = """el => {
    const style = getComputedStyle(el);
    return {
        background: style.backgroundColor,
        radius: style.borderRadius,
        weight: style.fontWeight,
    };
}"""
# A secondary button: also its edge and its label.
SECONDARY_LOOK = """el => {
    const style = getComputedStyle(el);
    return {
        background: style.backgroundColor,
        edge: style.borderTopColor,
        color: style.color,
        radius: style.borderRadius,
        weight: style.fontWeight,
    };
}"""


class OneProductTests(BrowserTestCase):
    def test_primary_button_is_the_same_everywhere(self):
        """The landing page and the app use the same primary and secondary buttons."""
        page = self.page
        user = make_user_with_inbox()
        for scheme in ["light", "dark"]:
            with self.subTest(scheme=scheme):
                page.emulate_media(color_scheme=scheme)
                self.context.clear_cookies()
                page.goto(self.live_server_url)  # The landing page.
                landing = page.locator(".hero .button-primary").evaluate(BUTTON_LOOK)
                log_in = page.locator(".hero .button-secondary").evaluate(
                    SECONDARY_LOOK
                )

                self.log_in_as(user)
                page.goto(self.live_server_url)  # The list page.
                add = page.get_by_role("button", name="Add", exact=True)
                self.assertEqual(add.evaluate(BUTTON_LOOK), landing)
                search = page.get_by_role("button", name="Search", exact=True)
                self.assertEqual(search.evaluate(SECONDARY_LOOK), log_in)


# Under a finger (WCAG 2.5.8 and the person's decision): a button at least 44px
# tall, and at least 8px between two buttons, so a finger hits the right one.
TOUCH_HEIGHT = 44
TOUCH_GAP = 8
# The computed display of an element; a <summary> with its triangle is "list-item".
DISPLAY = "el => getComputedStyle(el).display"


def gaps(boxes):
    """The space between each box and the next one on the same line, in pixels."""
    return [
        b["x"] - (a["x"] + a["width"]) for a, b in zip(boxes, boxes[1:], strict=False)
    ]


class TouchTests(BrowserTestCase):
    def test_row_and_step_buttons_fit_a_finger(self):
        """On a phone, every small control of the list page is 44px tall and 8px
        apart: row and step buttons, summaries, filter links, menu links, and
        Rename and Delete list."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        todo = the_list.todos.create(
            title="Water the plants", description="The big one first."
        )
        todo.subtasks.create(title="Fill the can")
        the_list.todos.create(title="Old task", done=True)  # For Clear completed.
        user.todo_lists.create(name="Work")  # Two lists in the menu.
        phone = self.browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
        )
        self.addCleanup(phone.close)
        self.log_in_as(user, phone)
        page = phone.new_page()
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}?open={todo.pk}")
        row = page.locator(f"#todo-{todo.pk}")
        expect(row.locator("details.steps ul")).to_be_visible()

        step = row.locator("ul.steps li").first
        add_step = row.locator("form.add-step")
        groups = {
            "row": [
                row.get_by_role("link", name="Edit Water the plants"),
                row.get_by_role("button", name="Done: Water the plants"),
                row.get_by_role("button", name="Delete: Water the plants"),
            ],
            "step": [step.locator(".button").nth(0), step.locator(".button").nth(1)],
            "add step": [
                add_step.locator("input[name=title]"),
                add_step.locator("button"),
            ],
            "steps summary": [row.locator("details.steps > summary")],
            "notes summary": [row.locator("details.notes > summary")],
            "clear completed": [page.locator("details.clear-completed > summary")],
            "filter": [page.locator("nav.filter a").nth(n) for n in range(3)],
            "list menu": [
                page.locator("#my-lists a").nth(n)
                for n in range(3)  # + New list
            ],
            "list actions": [
                page.get_by_role("link", name="Rename"),
                page.get_by_role("link", name="Delete list"),
            ],
        }
        for name, controls in groups.items():
            with self.subTest(name):
                boxes = [control.bounding_box() for control in controls]
                for box in boxes:
                    self.assertGreaterEqual(box["height"], TOUCH_HEIGHT, boxes)
                for gap in gaps(boxes):
                    self.assertGreaterEqual(gap, TOUCH_GAP, boxes)
        # Taller, but still a <summary> with its open/closed triangle.
        for name in ["steps summary", "notes summary", "clear completed"]:
            with self.subTest(name, check="triangle"):
                self.assertEqual(groups[name][0].evaluate(DISPLAY), "list-item")

    def test_leave_summary_fits_a_finger(self):
        """A member's "Leave this list" is 44px tall under a finger, triangle kept."""
        owner = make_user("bob")
        groceries = TodoList.objects.create(owner=owner, name="Groceries")
        member = make_user_with_inbox()
        groceries.members.add(member)
        phone = self.browser.new_context(
            viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
        )
        self.addCleanup(phone.close)
        self.log_in_as(member, phone)
        page = phone.new_page()
        page.goto(f"{self.live_server_url}{groceries.get_absolute_url()}")
        leave = page.locator("details.leave > summary")
        expect(leave).to_have_text("Leave this list")
        self.assertGreaterEqual(leave.bounding_box()["height"], TOUCH_HEIGHT)
        self.assertEqual(leave.evaluate(DISPLAY), "list-item")


def hex_to_rgb(value):
    """`#b42318` as the browser writes a computed color: `rgb(180, 35, 24)`."""
    value = value.strip().lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgb({red}, {green}, {blue})"


class QuietDeleteTests(BrowserTestCase):
    def test_row_delete_turns_red_on_keyboard_focus(self):
        """The row Delete is gray at rest, and the error red when Tab reaches it."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        the_list.todos.create(title="Water the plants")
        self.log_in_as(user)
        page = self.page
        page.goto(f"{self.live_server_url}{the_list.get_absolute_url()}")
        done = page.get_by_role("button", name="Done: Water the plants")
        delete = page.get_by_role("button", name="Delete: Water the plants")
        color = "el => getComputedStyle(el).color"
        resting = delete.evaluate(color)
        danger = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--danger')"
        )

        done.focus()
        page.keyboard.press("Tab")  # The keyboard, so :focus-visible applies.
        expect(delete).to_be_focused()
        page.wait_for_function("document.getAnimations().length === 0")
        focused = delete.evaluate(color)
        self.assertEqual(focused, hex_to_rgb(danger))
        self.assertNotEqual(focused, resting)


# Every element with a transition that takes time, with its selector-like name.
MOVING = """() => [...document.querySelectorAll("*")]
    .filter(el => getComputedStyle(el).transitionDuration
        .split(",").some(part => parseFloat(part) > 0))
    .map(el => el.tagName.toLowerCase() + (el.className ? "." + el.className : ""))"""


class ReducedMotionTests(BrowserTestCase):
    def test_nothing_moves_when_the_person_asks_for_less_motion(self):
        """With "reduce motion" on, no app or visitor page has a transition."""
        user = make_user_with_inbox()
        the_list = user.todo_lists.get()
        the_list.todos.create(title="Water the plants", done=True)
        the_list.todos.create(title="Feed the cat")
        self.page.emulate_media(reduced_motion="reduce")
        page = self.page
        for address in ["/", LOGIN_PAGE, SIGNUP_PAGE]:
            with self.subTest(address=address):
                page.goto(self.live_server_url + address)
                self.assertEqual(page.evaluate(MOVING), [])
        self.log_in_as(user)
        list_url = the_list.get_absolute_url()
        for address in [list_url, f"{list_url}?status=open", "/lists/new/"]:
            with self.subTest(address=address):
                page.goto(self.live_server_url + address)
                self.assertEqual(page.evaluate(MOVING), [])
