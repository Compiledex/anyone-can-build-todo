"""Tests for subtasks (steps): small steps inside a to-do.

alice (logged in) owns "Inbox" with the to-do "Move house". bob owns
"Bob's list" with the to-do "Bob's todo". carol is made where a test needs a
member of alice's list.

Every address comes from reverse(), never typed by hand: a typed address that
does not exist also gives 404, so an "other user gets 404" test would pass
before any code exists.
"""

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.models import Subtask, Todo

OPEN_DETAILS = '<details class="steps" open>'
ERROR = "A step needs a title of 1 to 200 characters."


class SubtaskTests(LoggedInTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.todo = Todo.objects.create(title="Move house", todo_list=cls.todo_list)
        cls.bob_todo = Todo.objects.create(title="Bob's todo", todo_list=cls.other_list)

    def add_url(self, todo=None):
        return reverse("subtask_add", args=[(todo or self.todo).pk])

    def make_step(self, title="Pack books", done=False, todo=None):
        return Subtask.objects.create(todo=todo or self.todo, title=title, done=done)

    def back_url(self, todo=None):
        todo = todo or self.todo
        url = reverse("list_detail", args=[todo.todo_list_id])
        return f"{url}?open={todo.pk}#todo-{todo.pk}"

    # Add, toggle, delete

    def test_add_a_step(self):
        response = self.client.post(self.add_url(), {"title": "Pack books"})
        self.assertRedirects(response, self.back_url(), fetch_redirect_response=False)
        step = Subtask.objects.get()
        self.assertEqual(step.title, "Pack books")
        self.assertEqual(step.todo, self.todo)
        self.assertFalse(step.done)

    def test_todo_field_in_post_is_ignored(self):
        self.client.post(
            self.add_url(), {"title": "Pack books", "todo": self.bob_todo.pk}
        )
        self.assertEqual(Subtask.objects.get().todo, self.todo)
        self.assertFalse(self.bob_todo.subtasks.exists())

    def test_empty_step_title_is_not_added(self):
        response = self.client.post(self.add_url(), {"title": "   "}, follow=True)
        self.assertFalse(Subtask.objects.exists())
        self.assertContains(response, ERROR)

    def test_long_step_title_is_not_added(self):
        self.client.post(self.add_url(), {"title": "x" * 201})
        self.assertFalse(Subtask.objects.exists())
        self.client.post(self.add_url(), {"title": "x" * 200})
        self.assertEqual(Subtask.objects.get().title, "x" * 200)

    def test_toggle_step_and_back(self):
        step = self.make_step()
        url = reverse("subtask_toggle", args=[step.pk])
        response = self.client.post(url)
        self.assertRedirects(response, self.back_url(), fetch_redirect_response=False)
        step.refresh_from_db()
        self.assertTrue(step.done)
        self.client.post(url)
        step.refresh_from_db()
        self.assertFalse(step.done)

    def test_delete_step(self):
        step = self.make_step()
        response = self.client.post(reverse("subtask_delete", args=[step.pk]))
        self.assertRedirects(response, self.back_url(), fetch_redirect_response=False)
        self.assertFalse(Subtask.objects.exists())
        self.assertTrue(Todo.objects.filter(pk=self.todo.pk).exists())

    def test_get_does_not_change_steps(self):
        step = self.make_step()
        for name, args in [
            ("subtask_add", [self.todo.pk]),
            ("subtask_toggle", [step.pk]),
            ("subtask_delete", [step.pk]),
        ]:
            with self.subTest(name):
                response = self.client.get(reverse(name, args=args), {"title": "New"})
                self.assertEqual(response.status_code, 405)
        step.refresh_from_db()
        self.assertFalse(step.done)
        self.assertEqual(Subtask.objects.count(), 1)

    def test_logged_out_cannot_change_steps(self):
        step = self.make_step()
        client = Client()
        for name, args in [
            ("subtask_add", [self.todo.pk]),
            ("subtask_toggle", [step.pk]),
            ("subtask_delete", [step.pk]),
        ]:
            with self.subTest(name):
                url = reverse(name, args=args)
                response = client.post(url, {"title": "New"})
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False,
                )
        step.refresh_from_db()
        self.assertFalse(step.done)
        self.assertEqual(Subtask.objects.count(), 1)

    # Only my data: a stranger gets 404, a member may change the steps

    def test_other_user_cannot_add_step(self):
        self.assertOtherUserGets404(self.add_url(), data={"title": "Sneaky"})
        self.assertFalse(Subtask.objects.exists())

    def test_other_user_cannot_toggle_step(self):
        step = self.make_step()
        self.assertOtherUserGets404(reverse("subtask_toggle", args=[step.pk]))
        step.refresh_from_db()
        self.assertFalse(step.done)

    def test_other_user_cannot_delete_step(self):
        step = self.make_step()
        self.assertOtherUserGets404(reverse("subtask_delete", args=[step.pk]))
        self.assertTrue(Subtask.objects.filter(pk=step.pk).exists())

    def test_list_member_can_change_steps(self):
        carol = make_user("carol")
        self.todo_list.members.add(carol)
        client = self.client_for(carol)

        response = client.post(self.add_url(), {"title": "Book a van"})
        self.assertRedirects(response, self.back_url(), fetch_redirect_response=False)
        step = Subtask.objects.get(todo=self.todo)
        self.assertEqual(step.title, "Book a van")

        client.post(reverse("subtask_toggle", args=[step.pk]))
        step.refresh_from_db()
        self.assertTrue(step.done)

        client.post(reverse("subtask_delete", args=[step.pk]))
        self.assertFalse(Subtask.objects.exists())

    # The steps and their to-do

    def test_deleting_todo_deletes_its_steps(self):
        self.make_step()
        self.make_step("Book a van")
        self.client.post(reverse("todo_delete", args=[self.todo.pk]))
        self.assertEqual(Subtask.objects.count(), 0)

    def test_clear_completed_counts_only_todos(self):
        self.todo.done = True
        self.todo.save()
        for title in ["Pack books", "Book a van", "Clean the kitchen"]:
            self.make_step(title)
        response = self.client.post(
            reverse("list_clear_completed", args=[self.todo_list.pk]), follow=True
        )
        self.assertContains(response, "Deleted 1 completed to-do.")
        self.assertEqual(Subtask.objects.count(), 0)

    def test_all_steps_done_does_not_finish_todo(self):
        for title in ["Pack books", "Book a van"]:
            step = self.make_step(title)
            self.client.post(reverse("subtask_toggle", args=[step.pk]))
        self.assertEqual(self.todo.subtasks.filter(done=True).count(), 2)
        self.todo.refresh_from_db()
        self.assertFalse(self.todo.done)

    def test_finishing_todo_does_not_change_steps(self):
        self.make_step("Pack books", done=True)
        self.make_step("Book a van", done=False)
        self.client.post(reverse("todo_toggle", args=[self.todo.pk]))
        self.todo.refresh_from_db()
        self.assertTrue(self.todo.done)
        self.assertEqual(
            dict(self.todo.subtasks.values_list("title", "done")),
            {"Pack books": True, "Book a van": False},
        )

    # The list page

    def list_page(self, query=None):
        return self.client.get(reverse("list_detail", args=[self.todo_list.pk]), query)

    def test_list_shows_step_count(self):
        for i in range(5):
            self.make_step(f"Step {i}", done=i < 2)
        self.assertContains(self.list_page(), "Steps: 2 of 5 done")

    def test_todo_without_steps_shows_add_steps(self):
        response = self.list_page()
        self.assertContains(response, "Add steps")
        self.assertNotContains(response, "0 of 0")

    def test_list_has_fixed_number_of_queries(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.list_page().status_code, 200)
            return len(queries)

        for i in range(3):
            self.make_step(f"Step {i}")
        one_todo = count_queries()

        for n in range(4):
            todo = Todo.objects.create(title=f"Todo {n}", todo_list=self.todo_list)
            for i in range(3):
                self.make_step(f"Step {i}", todo=todo)
        self.assertEqual(count_queries(), one_todo)

    def test_after_action_details_is_open(self):
        second = Todo.objects.create(title="Pay rent", todo_list=self.todo_list)
        response = self.client.post(self.add_url(second), {"title": "Find the bill"})
        self.assertRedirects(
            response, self.back_url(second), fetch_redirect_response=False
        )
        page = self.list_page({"open": second.pk})
        self.assertContains(page, OPEN_DETAILS, count=1)
        self.assertContains(page, f'id="todo-{second.pk}"')
        self.assertContains(page, "Find the bill")

    def test_bad_open_value_is_ignored(self):
        for value in ["abc", "<script>"]:
            with self.subTest(value):
                response = self.list_page({"open": value})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Move house")
                self.assertNotContains(response, OPEN_DETAILS)
                self.assertNotContains(response, "<script>")
