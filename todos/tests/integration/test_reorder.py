"""Tests for the manual order: drag and drop (reorder) and the Move buttons.

alice is logged in and owns "Inbox" (self.todo_list). bob owns "Bob's list".
"""

import datetime
import importlib

import django.apps
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.models import Todo


class ReorderTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.first = self.add("First")
        self.second = self.add("Second")
        self.third = self.add("Third")
        self.reorder_url = reverse("todo_reorder", args=[self.todo_list.pk])
        self.manual_url = f"{self.todo_list.get_absolute_url()}?sort=manual"

    def add(self, title, todo_list=None, **fields):
        return Todo.objects.create(
            todo_list=todo_list or self.todo_list, title=title, **fields
        )

    def shown(self, client=None):
        response = (client or self.client).get(self.manual_url)
        return [todo.title for todo in response.context["todos"]]

    def reorder(self, *todos, client=None):
        return (client or self.client).post(
            self.reorder_url, {"id": [todo.pk for todo in todos]}
        )

    def positions(self, todo_list=None):
        the_list = todo_list or self.todo_list
        return dict(the_list.todos.values_list("pk", "position"))

    def move(self, todo, direction, client=None):
        return (client or self.client).post(
            reverse("todo_move", args=[todo.pk]), {"direction": direction}
        )

    def test_reorder_saves_new_order(self):
        response = self.reorder(self.third, self.first, self.second)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.shown(), ["Third", "First", "Second"])

    def test_new_todo_goes_last(self):
        self.reorder(self.second, self.third, self.first)
        self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": "Fourth"}
        )
        self.assertEqual(self.shown(), ["Second", "Third", "First", "Fourth"])

    def test_recurring_copy_goes_last(self):
        repeating = self.add(
            "Water plants", repeat="daily", due_date=timezone.localdate()
        )
        self.reorder(repeating, self.first, self.second, self.third)
        self.client.post(reverse("todo_toggle", args=[repeating.pk]))
        self.assertEqual(
            self.shown(), ["Water plants", "First", "Second", "Third", "Water plants"]
        )
        self.assertTrue(Todo.objects.get(pk=repeating.pk).done)

    def test_reorder_needs_post(self):
        response = self.client.get(self.reorder_url)
        self.assertEqual(response.status_code, 405)

    def test_reorder_needs_csrf_token(self):
        before = self.positions()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.reorder(self.third, self.first, self.second, client=client)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.positions(), before)

    def test_reorder_other_users_list_is_404(self):
        before = self.positions()
        self.assertOtherUserGets404(
            self.reorder_url,
            data={"id": [self.third.pk, self.first.pk, self.second.pk]},
        )
        self.assertEqual(self.positions(), before)

    def test_reorder_with_other_users_id_is_400(self):
        bobs = self.add("Bob's to-do", todo_list=self.other_list)
        before, bobs_before = self.positions(), self.positions(self.other_list)
        response = self.reorder(self.third, bobs, self.second)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.positions(), before)
        self.assertEqual(self.positions(self.other_list), bobs_before)

    def test_reorder_with_missing_id_is_400(self):
        before = self.positions()
        response = self.reorder(self.third, self.first)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.positions(), before)

    def test_reorder_with_bad_id_is_400(self):
        before = self.positions()
        response = self.client.post(
            self.reorder_url, {"id": [self.third.pk, "abc", self.second.pk]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.positions(), before)

    def test_shared_member_can_reorder(self):
        member = make_user("carol")
        self.todo_list.members.add(member)
        response = self.reorder(
            self.third, self.second, self.first, client=self.client_for(member)
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.shown(), ["Third", "Second", "First"])

    def test_move_up_swaps_with_neighbour(self):
        response = self.move(self.second, "up")
        self.assertRedirects(
            response,
            f"{self.manual_url}#todo-{self.second.pk}",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.shown(), ["Second", "First", "Third"])

    def test_move_down_on_last_changes_nothing(self):
        before = self.positions()
        response = self.move(self.third, "down")
        self.assertRedirects(
            response,
            f"{self.manual_url}#todo-{self.third.pk}",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.positions(), before)
        self.assertEqual(self.shown(), ["First", "Second", "Third"])

    def test_move_with_bad_direction_is_400(self):
        before = self.positions()
        response = self.move(self.second, "sideways")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.positions(), before)

    def test_move_other_users_todo_is_404(self):
        before = self.positions()
        self.assertOtherUserGets404(
            reverse("todo_move", args=[self.second.pk]), data={"direction": "up"}
        )
        self.assertEqual(self.positions(), before)

    def test_move_with_equal_positions_still_moves(self):
        Todo.objects.filter(pk__in=[self.first.pk, self.second.pk]).update(position=1)
        self.move(self.second, "up")
        self.assertEqual(self.shown(), ["Second", "First", "Third"])

    def test_handles_only_when_reordering_is_allowed(self):
        response = self.client.get(self.manual_url)
        self.assertContains(response, f'data-reorder-url="{self.reorder_url}"')
        self.assertContains(response, 'draggable="true"', count=3)
        self.assertContains(response, f'data-id="{self.first.pk}"')
        self.assertContains(response, "Move down: First")
        self.assertNotContains(response, "Clear the filter to change the order.")

        response = self.client.get(f"{self.manual_url}&status=open")
        self.assertNotContains(response, "data-reorder-url")
        self.assertNotContains(response, 'draggable="true"')
        self.assertNotContains(response, "Move down: First")
        self.assertContains(response, "Clear the filter to change the order.")

    def test_first_row_has_no_move_up_and_last_has_no_move_down(self):
        response = self.client.get(self.manual_url)
        self.assertNotContains(response, "Move up: First")
        self.assertContains(response, "Move down: First")
        self.assertContains(response, "Move up: Second")
        self.assertContains(response, "Move down: Second")
        self.assertContains(response, "Move up: Third")
        self.assertNotContains(response, "Move down: Third")

    def test_move_labels_are_escaped(self):
        self.add('<b>"x')  # Last, so it has a "Move up" button.
        response = self.client.get(self.manual_url)
        self.assertContains(response, 'aria-label="Move up: &lt;b&gt;&quot;x"')
        self.assertContains(response, 'title="Move up: &lt;b&gt;&quot;x"')
        self.assertNotContains(response, '<b>"x')

    def test_new_todo_goes_last_even_with_a_position_given(self):
        todo = self.add("Fourth", position=1)  # The biggest in the list is 3.
        self.assertEqual(Todo.objects.get(pk=todo.pk).position, 4)


class FillPositionMigrationTests(LoggedInTestCase):
    def test_fill_migration_numbers_each_list(self):
        # The file name starts with a number, so a normal import cannot load it.
        migration = importlib.import_module("todos.migrations.0016_fill_todo_position")
        now = timezone.now()
        lists = {"alice": self.todo_list, "bob": self.other_list}
        for the_list in lists.values():
            # Made in the order C, B, A, but A is the oldest (created_at).
            for minutes_ago, title in [(1, "C"), (2, "B"), (3, "A")]:
                todo = Todo.objects.create(todo_list=the_list, title=title)
                Todo.objects.filter(pk=todo.pk).update(
                    created_at=now - datetime.timedelta(minutes=minutes_ago),
                    position=0,
                )

        migration.fill_position(django.apps.apps, None)

        for owner, the_list in lists.items():
            with self.subTest(owner=owner):
                numbered = list(
                    the_list.todos.order_by("position").values_list("title", "position")
                )
                self.assertEqual(numbered, [("A", 1), ("B", 2), ("C", 3)])
