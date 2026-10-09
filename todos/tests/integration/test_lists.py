"""Tests for several lists: make, open, rename and delete a list.

self.todo_list is alice's "Inbox" list and self.other_list is bob's list
(from LoggedInTestCase).
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.models import Todo, TodoList


class HomeTests(LoggedInTestCase):
    def test_home_opens_oldest_list(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        TodoList.objects.filter(pk=work.pk).update(
            created_at=timezone.now() + timedelta(days=1)
        )
        response = self.client.get(reverse("todo_list"))
        self.assertRedirects(response, self.todo_list.get_absolute_url())

    def test_home_without_lists_goes_to_new_list(self):
        carol = make_user("carol")
        response = self.client_for(carol).get(reverse("todo_list"))
        self.assertRedirects(response, reverse("list_create"))


class NewListTests(LoggedInTestCase):
    def test_create_a_list(self):
        response = self.client.post(reverse("list_create"), {"name": "Work"})
        work = TodoList.objects.get(name="Work")
        self.assertEqual(work.owner, self.user)
        self.assertRedirects(response, work.get_absolute_url())

    def test_empty_name_is_not_created(self):
        response = self.client.post(reverse("list_create"), {"name": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertEqual(self.user.todo_lists.count(), 1)

    def test_duplicate_name_is_not_created(self):
        TodoList.objects.create(owner=self.user, name="Work")
        response = self.client.post(reverse("list_create"), {"name": "work"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You already have a list called")
        self.assertContains(response, 'value="work"')
        self.assertEqual(self.user.todo_lists.count(), 2)

    def test_same_name_as_another_person_is_allowed(self):
        TodoList.objects.create(owner=self.user, name="Work")
        bob = self.client_for(self.other_user)
        bob.post(reverse("list_create"), {"name": "Work"})
        self.assertTrue(self.other_user.todo_lists.filter(name="Work").exists())

    def test_create_ignores_owner_in_the_form(self):
        self.client.post(
            reverse("list_create"), {"name": "Work", "owner": self.other_user.pk}
        )
        self.assertEqual(TodoList.objects.get(name="Work").owner, self.user)
        self.assertFalse(self.other_user.todo_lists.filter(name="Work").exists())

    def test_no_cancel_link_without_lists(self):
        # `/` would only send the person back to this page.
        carol = make_user("carol")
        response = self.client_for(carol).get(reverse("list_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cancel")

    def test_get_does_not_create(self):
        response = self.client.get(reverse("list_create"), {"name": "Work"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')
        self.assertFalse(TodoList.objects.filter(name="Work").exists())


class RenameListTests(LoggedInTestCase):
    def test_rename_a_list(self):
        url = reverse("list_rename", args=[self.todo_list.pk])
        response = self.client.post(url, {"name": "Home"})
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        self.todo_list.refresh_from_db()
        self.assertEqual(self.todo_list.name, "Home")

    def test_rename_to_another_lists_name_is_refused(self):
        TodoList.objects.create(owner=self.user, name="Work")
        url = reverse("list_rename", args=[self.todo_list.pk])
        response = self.client.post(url, {"name": "work"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You already have a list called")
        self.todo_list.refresh_from_db()
        self.assertEqual(self.todo_list.name, "Inbox")

    def test_rename_keeping_the_same_name_works(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        url = reverse("list_rename", args=[work.pk])
        response = self.client.post(url, {"name": "work"})
        self.assertRedirects(response, work.get_absolute_url())
        work.refresh_from_db()
        self.assertEqual(work.name, "work")


class DeleteListTests(LoggedInTestCase):
    def test_get_shows_confirm_and_deletes_nothing(self):
        for title in ["Buy milk", "Call home"]:
            Todo.objects.create(title=title, todo_list=self.todo_list)
        work = TodoList.objects.create(owner=self.user, name="Work")
        Todo.objects.create(title="Send report", todo_list=work)
        response = self.client.get(reverse("list_delete", args=[self.todo_list.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inbox")
        self.assertContains(response, "2 to-dos")
        self.assertTrue(TodoList.objects.filter(pk=self.todo_list.pk).exists())
        self.assertEqual(Todo.objects.count(), 3)

    def test_delete_removes_list_and_its_todos(self):
        Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        work = TodoList.objects.create(owner=self.user, name="Work")
        Todo.objects.create(title="Send report", todo_list=work)
        response = self.client.post(reverse("list_delete", args=[self.todo_list.pk]))
        self.assertRedirects(
            response, reverse("todo_list"), fetch_redirect_response=False
        )
        self.assertFalse(TodoList.objects.filter(pk=self.todo_list.pk).exists())
        self.assertEqual([t.title for t in Todo.objects.all()], ["Send report"])

    def test_delete_last_list_then_home_goes_to_new(self):
        self.client.post(reverse("list_delete", args=[self.todo_list.pk]))
        response = self.client.get(reverse("todo_list"))
        self.assertRedirects(response, reverse("list_create"))


class ListPageTests(LoggedInTestCase):
    def test_post_to_list_page_is_405(self):
        response = self.client.post(self.todo_list.get_absolute_url())
        self.assertEqual(response.status_code, 405)

    def test_list_shows_only_its_own_todos(self):
        home = TodoList.objects.create(owner=self.user, name="Home")
        work = TodoList.objects.create(owner=self.user, name="Work")
        Todo.objects.create(title="Water plants", todo_list=home)
        Todo.objects.create(title="Send report", todo_list=work)
        response = self.client.get(work.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send report")
        self.assertNotContains(response, "Water plants")

    def test_menu_shows_my_lists(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        response = self.client.get(work.get_absolute_url())
        self.assertContains(
            response, f'href="{self.todo_list.get_absolute_url()}"', count=1
        )
        self.assertContains(response, ">Inbox<")
        # The open list is marked, and only that one (the `>` leaves out the CSS).
        self.assertContains(response, 'aria-current="page">', count=1)
        self.assertContains(
            response, f'href="{work.get_absolute_url()}" aria-current="page">Work<'
        )


class ListNameIsEscapedTests(LoggedInTestCase):
    def test_list_name_is_escaped_on_every_page(self):
        the_list = TodoList.objects.create(owner=self.user, name="<b>x</b>")
        for name in ["list_detail", "list_rename", "list_delete"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name, args=[the_list.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "<b>x</b>")
                self.assertContains(response, "&lt;b&gt;x&lt;/b&gt;")
        response = self.client.get(the_list.get_absolute_url())
        self.assertContains(response, "<title>&lt;b&gt;x&lt;/b&gt;</title>")


class PrivacyTests(LoggedInTestCase):
    def test_cannot_open_someone_elses_list(self):
        self.assertOtherUserGets404(self.todo_list.get_absolute_url(), method="get")

    def test_cannot_add_to_someone_elses_list(self):
        url = reverse("todo_add", args=[self.todo_list.pk])
        self.assertOtherUserGets404(url, data={"title": "Sneaky"})
        self.assertEqual(Todo.objects.count(), 0)

    def test_cannot_rename_someone_elses_list(self):
        url = reverse("list_rename", args=[self.todo_list.pk])
        self.assertOtherUserGets404(url, method="get")
        self.assertOtherUserGets404(url, data={"name": "Sneaky"})
        self.todo_list.refresh_from_db()
        self.assertEqual(self.todo_list.name, "Inbox")

    def test_cannot_delete_someone_elses_list(self):
        Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        url = reverse("list_delete", args=[self.todo_list.pk])
        self.assertOtherUserGets404(url, method="get")
        self.assertOtherUserGets404(url)
        self.assertTrue(TodoList.objects.filter(pk=self.todo_list.pk).exists())
        self.assertEqual(Todo.objects.count(), 1)

    def test_menu_does_not_show_someone_elses_lists(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Bob")
        self.assertNotContains(response, self.other_list.get_absolute_url())
