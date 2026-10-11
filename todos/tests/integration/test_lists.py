"""Tests for several lists: make, open, rename and delete a list.

self.todo_list is alice's "Inbox" list and self.other_list is bob's list
(from LoggedInTestCase).
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from accounts.tests.helpers import LoggedInTestCase, make_user
from todos.forms import TodoListForm
from todos.models import Tag, Todo, TodoList


class HomeTests(LoggedInTestCase):
    def test_home_opens_oldest_list(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        TodoList.objects.filter(pk=work.pk).update(
            created_at=timezone.now() + timedelta(days=1)
        )
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, self.todo_list.get_absolute_url())

    def test_home_without_lists_goes_to_new_list(self):
        carol = make_user("carol")
        response = self.client_for(carol).get(reverse("home"))
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

    def test_nordic_name_in_other_case_is_refused(self):
        # SQLite's LOWER() and LIKE only know A to Z; the rule must know every letter.
        for existing, typed in [
            ("Ærend", "ærend"),
            ("øl", "ØL"),
            ("Åker", "åKER"),
            ("STRASSE", "straße"),
        ]:
            with self.subTest(existing=existing, typed=typed):
                TodoList.objects.create(owner=self.user, name=existing)
                response = self.client.post(reverse("list_create"), {"name": typed})
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response, escape(f"You already have a list called “{existing}”.")
                )
                self.assertEqual(
                    self.user.todo_lists.exclude(pk=self.todo_list.pk).count(), 1
                )
                self.user.todo_lists.exclude(pk=self.todo_list.pk).delete()

    def test_split_a_ring_counts_as_the_same(self):
        # A Mac can send "å" as "a" plus a combining ring (U+030A).
        TodoList.objects.create(owner=self.user, name="\u00c5ker")
        response = self.client.post(reverse("list_create"), {"name": "A\u030aker"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You already have a list called")
        self.assertEqual(self.user.todo_lists.count(), 2)

    def test_different_nordic_name_is_allowed(self):
        TodoList.objects.create(owner=self.user, name="Ærend")
        for name in ["Ærender", "Erend"]:
            with self.subTest(name=name):
                self.client.post(reverse("list_create"), {"name": name})
                self.assertTrue(self.user.todo_lists.filter(name=name).exists())

    def test_database_refuses_a_duplicate_key(self):
        TodoList.objects.create(owner=self.user, name="Ærend")
        with self.assertRaises(IntegrityError), transaction.atomic():
            TodoList.objects.create(owner=self.user, name="ærend")
        self.assertEqual(self.user.todo_lists.count(), 2)

    def test_save_sets_the_key(self):
        errand = TodoList.objects.create(owner=self.user, name="ÆRend")
        self.assertEqual(errand.name_key, "ærend")
        form = TodoListForm({"name": "ØL"}, instance=errand)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        errand.refresh_from_db()
        self.assertEqual(errand.name_key, "øl")
        # casefold, not lower(): "ß" becomes "ss".
        street = TodoList.objects.create(owner=self.user, name="Straße")
        self.assertEqual(street.name_key, "strasse")
        # NFC first: "A" plus a combining ring becomes one "å".
        field = TodoList.objects.create(owner=self.user, name="A\u030aker")
        self.assertEqual(field.name_key, "\u00e5ker")

    def test_save_with_update_fields_name_sets_the_key(self):
        errand = TodoList.objects.create(owner=self.user, name="Ærend")
        errand.name = "ÅKER"
        errand.save(update_fields=["name"])
        errand.refresh_from_db()
        self.assertEqual(errand.name_key, "åker")

    def test_same_nordic_name_as_another_person_is_allowed(self):
        TodoList.objects.create(owner=self.other_user, name="Ærend")
        response = self.client.post(reverse("list_create"), {"name": "ærend"})
        errand = self.user.todo_lists.get(name="ærend")
        self.assertRedirects(response, errand.get_absolute_url())

    def test_message_escapes_the_name(self):
        TodoList.objects.create(owner=self.user, name="<b>Æ</b>")
        response = self.client.post(reverse("list_create"), {"name": "<b>æ</b>"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;b&gt;Æ&lt;/b&gt;")
        self.assertNotContains(response, "<b>Æ</b>")

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

    def test_rename_to_other_case_of_own_name_works(self):
        errand = TodoList.objects.create(owner=self.user, name="ærend")
        url = reverse("list_rename", args=[errand.pk])
        response = self.client.post(url, {"name": "Ærend"})
        self.assertRedirects(response, errand.get_absolute_url())
        errand.refresh_from_db()
        self.assertEqual(errand.name, "Ærend")
        self.assertContains(self.client.get(errand.get_absolute_url()), "Ærend")

    def test_rename_to_another_lists_nordic_name_is_refused(self):
        TodoList.objects.create(owner=self.user, name="Ærend")
        home = TodoList.objects.create(owner=self.user, name="Hjem")
        url = reverse("list_rename", args=[home.pk])
        response = self.client.post(url, {"name": "ærend"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, escape("You already have a list called “Ærend”."))
        home.refresh_from_db()
        self.assertEqual(home.name, "Hjem")


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
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(TodoList.objects.filter(pk=self.todo_list.pk).exists())
        self.assertEqual([t.title for t in Todo.objects.all()], ["Send report"])

    def test_delete_last_list_then_home_goes_to_new(self):
        self.client.post(reverse("list_delete", args=[self.todo_list.pk]))
        response = self.client.get(reverse("home"))
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
        # The second mark is "All" in the filter links.
        self.assertContains(response, 'aria-current="page">', count=2)
        self.assertContains(response, 'aria-current="page">All<')
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
        self.assertContains(
            response, "<title>&lt;b&gt;x&lt;/b&gt; – To-do list</title>"
        )


ALERT = (
    '<p class="form-error-summary" role="alert" tabindex="-1" autofocus>'
    "Not saved. Fix what is marked below.</p>"
)


class PageTitleTests(LoggedInTestCase):
    def test_page_titles(self):
        pk = self.todo_list.pk
        for url, title in [
            (self.todo_list.get_absolute_url(), "Inbox – To-do list"),
            (reverse("list_create"), "New list – To-do list"),
            (reverse("list_rename", args=[pk]), "Rename list – To-do list"),
            (reverse("list_delete", args=[pk]), "Delete list – To-do list"),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, f"<title>{title}</title>")
                self.assertNotContains(response, "form-error-summary")

    def test_bad_new_list_and_rename_say_error(self):
        TodoList.objects.create(owner=self.user, name="Work")
        for url, title in [
            (reverse("list_create"), "New list"),
            (reverse("list_rename", args=[self.todo_list.pk]), "Rename list"),
        ]:
            with self.subTest(url=url):
                response = self.client.post(url, {"name": "work"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response, f"<title>Error: {title} – To-do list</title>"
                )
                self.assertContains(response, ALERT, count=1)
        self.todo_list.refresh_from_db()
        self.assertEqual(self.todo_list.name, "Inbox")
        self.assertEqual(self.user.todo_lists.count(), 2)


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


class ClearCompletedTests(LoggedInTestCase):
    """Clear completed: delete the done to-dos of one list, in one POST.

    alice's Inbox (A1) has 2 done and 1 not done, her "Work" list (A2) has
    1 done, and bob's list (B1) has 1 done. The numbers differ on purpose:
    a view that counts or deletes in the wrong list gives a wrong number.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.work_list = TodoList.objects.create(owner=cls.user, name="Work")
        for title in ["Buy milk", "Call home"]:
            Todo.objects.create(title=title, done=True, todo_list=cls.todo_list)
        cls.open_todo = Todo.objects.create(title="Pay rent", todo_list=cls.todo_list)
        cls.work_done = Todo.objects.create(
            title="Send report", done=True, todo_list=cls.work_list
        )
        cls.bob_done = Todo.objects.create(
            title="Bob's done", done=True, todo_list=cls.other_list
        )

    def clear_url(self, the_list):
        return reverse("list_clear_completed", args=[the_list.pk])

    def test_clear_deletes_done_todos_of_this_list(self):
        response = self.client.post(self.clear_url(self.todo_list))
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        self.assertFalse(self.todo_list.todos.filter(done=True).exists())
        self.assertEqual(list(self.todo_list.todos.all()), [self.open_todo])

    def test_clear_keeps_other_lists(self):
        self.client.post(self.clear_url(self.todo_list))
        self.assertTrue(Todo.objects.filter(pk=self.work_done.pk).exists())
        self.assertTrue(Todo.objects.filter(pk=self.bob_done.pk).exists())

    def test_clear_other_users_list_is_404(self):
        response = self.client.post(self.clear_url(self.other_list))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Todo.objects.filter(pk=self.bob_done.pk).exists())

    def test_clear_unknown_list_is_404(self):
        response = self.client.post(
            reverse("list_clear_completed", args=[TodoList.objects.count() + 100])
        )
        self.assertEqual(response.status_code, 404)

    def test_get_does_not_clear(self):
        response = self.client.get(self.clear_url(self.todo_list))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.todo_list.todos.filter(done=True).count(), 2)

    def test_clear_needs_login(self):
        self.client.logout()
        url = self.clear_url(self.todo_list)
        response = self.client.post(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")
        self.assertEqual(self.todo_list.todos.filter(done=True).count(), 2)

    def test_clear_with_nothing_done(self):
        home = TodoList.objects.create(owner=self.user, name="Home")
        Todo.objects.create(title="Water plants", todo_list=home)
        response = self.client.post(self.clear_url(home), follow=True)
        self.assertRedirects(response, home.get_absolute_url())
        self.assertEqual(home.todos.count(), 1)
        self.assertEqual(Todo.objects.count(), 6)
        self.assertContains(response, "No completed to-dos to delete.")

    def test_clear_shows_message(self):
        response = self.client.post(self.clear_url(self.todo_list), follow=True)
        self.assertContains(response, "Deleted 2 completed to-dos.")

    def test_message_counts_todos_not_tags(self):
        # delete() also deletes the links between the to-dos and their tags,
        # and its first number counts those too (here 2 to-dos + 4 links = 6).
        for todo in self.todo_list.todos.filter(done=True):
            todo.set_tags(["home", "work"])
        response = self.client.post(self.clear_url(self.todo_list), follow=True)
        self.assertContains(response, "Deleted 2 completed to-dos.")
        self.assertEqual(list(self.todo_list.todos.all()), [self.open_todo])
        # Tags that are no longer used are kept (see docs/plans/tags.md).
        self.assertEqual(
            sorted(Tag.objects.filter(owner=self.user).values_list("name", flat=True)),
            ["home", "work"],
        )

    def test_list_shows_clear_button_with_count(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertContains(response, "Clear completed (2)")
        self.assertContains(response, self.clear_url(self.todo_list))

    def test_list_hides_clear_button_when_nothing_done(self):
        home = TodoList.objects.create(owner=self.user, name="Home")
        Todo.objects.create(title="Water plants", todo_list=home)
        response = self.client.get(home.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Clear completed")
        self.assertNotContains(response, self.clear_url(home))

    def test_one_done_todo_uses_singular_words(self):
        response = self.client.get(self.work_list.get_absolute_url())
        self.assertContains(response, "Clear completed (1)")
        self.assertContains(response, "Delete 1 done to-do? This cannot be undone.")
        response = self.client.post(self.clear_url(self.work_list), follow=True)
        self.assertContains(response, "Deleted 1 completed to-do.")
