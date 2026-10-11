"""Tests for the priority of a to-do (Low, Medium, High)."""

from django.urls import reverse

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo


class PriorityTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.add_url = reverse("todo_add", args=[self.todo_list.pk])

    def make_todo(self, priority):
        todo = Todo.objects.create(
            title="Pay rent", todo_list=self.todo_list, priority=priority
        )
        return todo, reverse("todo_edit", args=[todo.pk])

    def test_add_a_todo_with_high_priority(self):
        self.client.post(self.add_url, {"title": "Pay rent", "priority": "3"})
        todo = Todo.objects.get(title="Pay rent")
        self.assertEqual(todo.priority, Todo.Priority.HIGH)

    def test_add_without_priority_is_medium(self):
        for data in [{"title": "Only a title"}, {"title": "Empty", "priority": ""}]:
            with self.subTest(data=data):
                self.client.post(self.add_url, data)
                todo = Todo.objects.get(title=data["title"])
                self.assertEqual(todo.priority, Todo.Priority.MEDIUM)

    def test_add_form_selects_medium(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertInHTML('<option value="2" selected>Medium</option>', response.text)

    def test_invalid_priority_is_not_added(self):
        response = self.client.post(
            self.add_url, {"title": "Pay rent", "priority": "7"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Todo.objects.exists())
        self.assertContains(response, "Select a valid choice.")
        self.assertContains(response, 'value="Pay rent"')
        # Screen readers hear that the drop-down is wrong, and which error it has.
        self.assertInHTML(
            '<select name="priority" aria-label="Priority" aria-invalid="true"'
            ' aria-describedby="id_priority_error" id="id_priority">'
            '<option value="1">Low</option><option value="2">Medium</option>'
            '<option value="3">High</option></select>',
            response.text,
        )
        self.assertContains(response, 'id="id_priority_error"')

    def test_invalid_priority_on_edit_changes_nothing(self):
        todo, url = self.make_todo(Todo.Priority.LOW)
        response = self.client.post(url, {"title": "New", "priority": "7"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice.")
        todo.refresh_from_db()
        self.assertEqual(todo.title, "Pay rent")
        self.assertEqual(todo.priority, Todo.Priority.LOW)

    def test_list_shows_priority_label(self):
        self.make_todo(Todo.Priority.HIGH)
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertInHTML(
            '<span class="priority priority-3">'
            '<span class="visually-hidden">Priority: </span>High</span>',
            response.text,
        )

    def test_edit_shows_current_priority(self):
        _, url = self.make_todo(Todo.Priority.LOW)
        response = self.client.get(url)
        self.assertInHTML('<option value="1" selected>Low</option>', response.text)

    def test_edit_changes_priority(self):
        todo, url = self.make_todo(Todo.Priority.MEDIUM)
        self.client.post(url, {"title": "Pay rent", "priority": "3"})
        todo.refresh_from_db()
        self.assertEqual(todo.priority, Todo.Priority.HIGH)

    def test_edit_without_priority_keeps_it(self):
        todo, url = self.make_todo(Todo.Priority.HIGH)
        self.client.post(url, {"title": "Pay the rent"})
        todo.refresh_from_db()
        self.assertEqual(todo.title, "Pay the rent")
        self.assertEqual(todo.priority, Todo.Priority.HIGH)

    def test_other_user_cannot_change_priority(self):
        todo, url = self.make_todo(Todo.Priority.LOW)
        self.assertOtherUserGets404(url, data={"title": "Pay rent", "priority": "3"})
        todo.refresh_from_db()
        self.assertEqual(todo.priority, Todo.Priority.LOW)
