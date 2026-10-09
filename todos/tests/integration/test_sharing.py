"""Tests for sharing a list with other users.

alice owns "Groceries" (with the to-do "Milk") and shares it with bob.
bob also owns "Bob's stuff". carol is logged in, owns "Carol's stuff", and is
not a member of Groceries.

Two rules, so that no test can pass while the feature is broken:
- "Nothing changed" is checked by reading the database again, never by the
  status code alone.
- Every "does not contain" has a "does contain" next to it, so an empty or
  broken page cannot pass.
"""

import re

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape

from accounts.tests.helpers import make_user
from todos.models import Todo, TodoList

# The two parts of the menu on the list page.
MY_LISTS = re.compile(r'<p class="menu" id="my-lists">(.*?)</p>', re.S)
SHARED_LISTS = re.compile(r'<p class="menu" id="shared-lists">(.*?)</p>', re.S)


def menu_part(response, pattern):
    """The HTML of one part of the menu, or "" if the page does not have it."""
    match = pattern.search(response.content.decode())
    return match.group(1) if match else ""


class SharingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user("alice")
        cls.bob = make_user("bob")
        cls.carol = make_user("carol")
        # Made first, so Groceries is the oldest list of all.
        cls.groceries = TodoList.objects.create(owner=cls.alice, name="Groceries")
        cls.groceries.members.add(cls.bob)
        cls.milk = Todo.objects.create(todo_list=cls.groceries, title="Milk")
        cls.bobs_list = TodoList.objects.create(owner=cls.bob, name="Bob's stuff")
        cls.carols_list = TodoList.objects.create(owner=cls.carol, name="Carol's stuff")

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def url(self, name, *args):
        return reverse(name, args=args)

    def messages_of(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def assertStillMilk(self):
        """ "Milk" exists, is not done, and has its old title."""
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.title, "Milk")
        self.assertFalse(self.milk.done)
        self.assertEqual(self.milk.todo_list, self.groceries)

    def assertBobIsMember(self):
        self.assertTrue(self.groceries.members.filter(pk=self.bob.pk).exists())


class VisibleToTests(SharingTestCase):
    def test_owner_sees_own_list(self):
        self.assertIn(self.groceries, TodoList.objects.visible_to(self.alice))

    def test_member_sees_shared_list(self):
        visible = TodoList.objects.visible_to(self.bob)
        self.assertIn(self.groceries, visible)
        self.assertIn(self.bobs_list, visible)

    def test_stranger_does_not_see_list(self):
        visible = TodoList.objects.visible_to(self.carol)
        self.assertNotIn(self.groceries, visible)
        self.assertIn(self.carols_list, visible)

    def test_list_shared_with_two_members_appears_once(self):
        # Each member row matches owner=alice, so only alice gets double rows.
        self.groceries.members.add(self.carol)
        visible = TodoList.objects.visible_to(self.alice)
        self.assertEqual(visible.filter(pk=self.groceries.pk).count(), 1)

        alice = self.client_for(self.alice)
        response = alice.get(self.groceries.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        response = alice.post(
            self.url("todo_add", self.groceries.pk), {"title": "Eggs"}
        )
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertTrue(self.groceries.todos.filter(title="Eggs").exists())

    def test_owner_added_as_member_is_in_menu_once(self):
        # The admin could do this.
        self.groceries.members.add(self.alice)
        response = self.client_for(self.alice).get(self.groceries.get_absolute_url())
        self.assertIn("Groceries", menu_part(response, MY_LISTS))
        self.assertNotContains(response, "Groceries (alice)")

    def test_former_member_does_not_see_list(self):
        self.groceries.members.remove(self.bob)
        visible = TodoList.objects.visible_to(self.bob)
        self.assertNotIn(self.groceries, visible)
        self.assertIn(self.bobs_list, visible)


class MemberCanTests(SharingTestCase):
    def setUp(self):
        self.client.force_login(self.bob)

    def test_member_sees_list_page(self):
        response = self.client.get(self.groceries.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Milk")
        self.assertContains(response, "Shared by alice")
        self.assertContains(response, "Leave this list")

    def test_member_sees_list_in_menu(self):
        response = self.client.get(self.bobs_list.get_absolute_url())
        self.assertIn("Groceries (alice)", menu_part(response, SHARED_LISTS))
        self.assertIn(escape("Bob's stuff"), menu_part(response, MY_LISTS))
        self.assertNotIn("Groceries", menu_part(response, MY_LISTS))

    def test_member_can_add(self):
        response = self.client.post(
            self.url("todo_add", self.groceries.pk), {"title": "Eggs"}
        )
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertTrue(self.groceries.todos.filter(title="Eggs").exists())

    def test_member_can_toggle(self):
        response = self.client.post(self.url("todo_toggle", self.milk.pk))
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.milk.refresh_from_db()
        self.assertTrue(self.milk.done)

    def test_member_can_edit(self):
        url = self.url("todo_edit", self.milk.pk)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"title": "Oat milk"})
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.title, "Oat milk")

    def test_member_can_edit_notes(self):
        url = self.url("todo_edit", self.milk.pk)
        response = self.client.post(
            url, {"title": "Milk", "description": "The lactose-free one."}
        )
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.description, "The lactose-free one.")
        self.assertContains(self.client.get(url), "The lactose-free one.")
        alices_page = self.client_for(self.alice).get(self.groceries.get_absolute_url())
        self.assertContains(alices_page, "The lactose-free one.")

    def test_member_can_delete_todo(self):
        response = self.client.post(self.url("todo_delete", self.milk.pk))
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertFalse(Todo.objects.filter(pk=self.milk.pk).exists())

    def test_member_can_clear_shared_list(self):
        eggs = Todo.objects.create(todo_list=self.groceries, title="Eggs", done=True)
        bread = Todo.objects.create(todo_list=self.groceries, title="Bread", done=True)
        response = self.client.post(self.url("list_clear_completed", self.groceries.pk))
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertFalse(Todo.objects.filter(pk__in=[eggs.pk, bread.pk]).exists())
        self.assertStillMilk()
        self.assertIn("Deleted 2 completed to-dos.", self.messages_of(response))

    def test_member_sees_clear_button(self):
        Todo.objects.create(todo_list=self.groceries, title="Eggs", done=True)
        response = self.client.get(self.groceries.get_absolute_url())
        self.assertContains(response, "Shared by alice")
        self.assertContains(response, "Clear completed (1)")
        self.assertContains(
            response, self.url("list_clear_completed", self.groceries.pk)
        )

    def test_member_invalid_add_shows_member_page(self):
        response = self.client.post(
            self.url("todo_add", self.groceries.pk), {"title": "x" * 201}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shared by alice")
        self.assertContains(response, "Leave this list")
        self.assertNotContains(response, self.url("list_share", self.groceries.pk))
        self.assertNotContains(response, "Remove")
        self.assertEqual(self.groceries.todos.count(), 1)


class MemberCannotTests(SharingTestCase):
    def setUp(self):
        self.client.force_login(self.bob)

    def test_member_cannot_rename_list(self):
        url = self.url("list_rename", self.groceries.pk)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"name": "Mine"}).status_code, 404)
        self.groceries.refresh_from_db()
        self.assertEqual(self.groceries.name, "Groceries")

    def test_member_cannot_delete_list(self):
        url = self.url("list_delete", self.groceries.pk)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(TodoList.objects.filter(pk=self.groceries.pk).exists())
        self.assertStillMilk()

    def test_member_cannot_share_further(self):
        response = self.client.post(
            self.url("list_share", self.groceries.pk), {"username": "carol"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.groceries.members.filter(pk=self.carol.pk).exists())
        self.assertBobIsMember()

    def test_member_cannot_remove_other_member(self):
        self.groceries.members.add(self.carol)
        response = self.client.post(
            self.url("list_member_remove", self.groceries.pk, self.carol.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.groceries.members.filter(pk=self.carol.pk).exists())

    def test_member_cannot_remove_owner(self):
        response = self.client.post(
            self.url("list_member_remove", self.groceries.pk, self.alice.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertBobIsMember()
        self.groceries.refresh_from_db()
        self.assertEqual(self.groceries.owner, self.alice)
        self.assertEqual(self.groceries.name, "Groceries")

    def test_member_does_not_see_owner_parts(self):
        self.groceries.members.add(self.carol)
        owner_parts = [
            self.url("list_share", self.groceries.pk),
            'name="username"',
            "Remove",
            self.url("list_rename", self.groceries.pk),
            self.url("list_delete", self.groceries.pk),
            "carol",
        ]
        bobs_page = self.client.get(self.groceries.get_absolute_url())
        self.assertContains(bobs_page, "Milk")
        alices_page = self.client_for(self.alice).get(self.groceries.get_absolute_url())
        for part in owner_parts:
            with self.subTest(part=part):
                self.assertNotContains(bobs_page, part)
                self.assertContains(alices_page, part)


class StrangerTests(SharingTestCase):
    def setUp(self):
        self.client.force_login(self.carol)

    def test_stranger_cannot_see_list(self):
        response = self.client.get(self.groceries.get_absolute_url())
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "Milk", status_code=404)

    def test_stranger_menu_does_not_show_list(self):
        response = self.client.get(self.carols_list.get_absolute_url())
        self.assertContains(response, escape("Carol's stuff"))
        self.assertNotContains(response, "Groceries")

    def test_stranger_cannot_add(self):
        response = self.client.post(
            self.url("todo_add", self.groceries.pk), {"title": "Eggs"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(self.groceries.todos.all()), [self.milk])

    def test_stranger_cannot_toggle(self):
        response = self.client.post(self.url("todo_toggle", self.milk.pk))
        self.assertEqual(response.status_code, 404)
        self.assertStillMilk()

    def test_stranger_cannot_edit(self):
        url = self.url("todo_edit", self.milk.pk)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"title": "Mine"}).status_code, 404)
        self.assertStillMilk()

    def test_stranger_cannot_see_or_edit_notes(self):
        self.milk.description = "Alice's note."
        self.milk.save()
        url = self.url("todo_edit", self.milk.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, "note.", status_code=404)
        response = self.client.post(url, {"title": "Milk", "description": "Mine"})
        self.assertEqual(response.status_code, 404)
        self.milk.refresh_from_db()
        self.assertEqual(self.milk.description, "Alice's note.")
        self.assertStillMilk()

    def test_stranger_cannot_delete_todo(self):
        response = self.client.post(self.url("todo_delete", self.milk.pk))
        self.assertEqual(response.status_code, 404)
        self.assertStillMilk()

    def test_stranger_cannot_share(self):
        response = self.client.post(
            self.url("list_share", self.groceries.pk), {"username": "carol"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.groceries.members.filter(pk=self.carol.pk).exists())

    def test_stranger_cannot_leave(self):
        response = self.client.post(self.url("list_leave", self.groceries.pk))
        self.assertEqual(response.status_code, 404)
        self.assertBobIsMember()

    def test_stranger_cannot_remove_member(self):
        response = self.client.post(
            self.url("list_member_remove", self.groceries.pk, self.bob.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertBobIsMember()

    def test_stranger_cannot_clear(self):
        eggs = Todo.objects.create(todo_list=self.groceries, title="Eggs", done=True)
        response = self.client.post(self.url("list_clear_completed", self.groceries.pk))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Todo.objects.filter(pk=eggs.pk).exists())
        self.assertStillMilk()


class ShareTests(SharingTestCase):
    def setUp(self):
        self.client.force_login(self.alice)

    def share(self, username):
        return self.client.post(
            self.url("list_share", self.groceries.pk), {"username": username}
        )

    def test_owner_shares_by_username(self):
        response = self.share("carol")
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertTrue(self.groceries.members.filter(pk=self.carol.pk).exists())
        self.assertEqual(self.messages_of(response), ["Shared with carol."])

    def test_unknown_username_is_refused(self):
        response = self.share("nobody")
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertEqual(list(self.groceries.members.all()), [self.bob])
        self.assertEqual(self.messages_of(response), ["No user with that username."])

    def test_inactive_user_is_refused(self):
        dave = make_user("dave")
        dave.is_active = False
        dave.save()
        response = self.share("dave")
        self.assertEqual(list(self.groceries.members.all()), [self.bob])
        self.assertEqual(self.messages_of(response), ["No user with that username."])

    def test_cannot_share_with_yourself(self):
        response = self.share("alice")
        self.assertFalse(self.groceries.members.filter(pk=self.alice.pk).exists())
        self.assertEqual(self.messages_of(response), ["You already own this list."])

    def test_sharing_twice_adds_one_member(self):
        response = self.share("bob")
        self.assertEqual(self.groceries.members.count(), 1)
        self.assertEqual(self.messages_of(response), ["bob is already a member."])

    def test_username_is_exact(self):
        self.groceries.members.remove(self.bob)
        response = self.share("BOB")
        self.assertEqual(self.groceries.members.count(), 0)
        self.assertEqual(self.messages_of(response), ["No user with that username."])

    def test_get_does_not_share(self):
        response = self.client.get(
            self.url("list_share", self.groceries.pk), {"username": "carol"}
        )
        self.assertEqual(response.status_code, 405)
        self.assertFalse(self.groceries.members.filter(pk=self.carol.pk).exists())


class LeaveRemoveTests(SharingTestCase):
    def test_member_leaves(self):
        response = self.client_for(self.bob).post(
            self.url("list_leave", self.groceries.pk)
        )
        self.assertRedirects(
            response, reverse("todo_list"), fetch_redirect_response=False
        )
        self.assertFalse(self.groceries.members.filter(pk=self.bob.pk).exists())
        self.assertStillMilk()

    def test_after_leaving_member_gets_404(self):
        bob = self.client_for(self.bob)
        bob.post(self.url("list_leave", self.groceries.pk))
        self.assertEqual(bob.get(self.groceries.get_absolute_url()).status_code, 404)
        response = bob.post(self.url("todo_toggle", self.milk.pk))
        self.assertEqual(response.status_code, 404)
        self.assertStillMilk()
        response = bob.post(self.url("list_leave", self.groceries.pk))
        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_leave_own_list(self):
        response = self.client_for(self.alice).post(
            self.url("list_leave", self.groceries.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(TodoList.objects.filter(pk=self.groceries.pk).exists())
        self.assertBobIsMember()

    def test_owner_removes_member(self):
        response = self.client_for(self.alice).post(
            self.url("list_member_remove", self.groceries.pk, self.bob.pk)
        )
        self.assertRedirects(response, self.groceries.get_absolute_url())
        self.assertFalse(self.groceries.members.filter(pk=self.bob.pk).exists())
        self.assertEqual(self.messages_of(response), ["bob was removed."])
        self.bob.refresh_from_db()
        self.assertTrue(TodoList.objects.filter(pk=self.bobs_list.pk).exists())

    def test_after_removal_member_gets_404(self):
        self.client_for(self.alice).post(
            self.url("list_member_remove", self.groceries.pk, self.bob.pk)
        )
        bob = self.client_for(self.bob)
        self.assertEqual(bob.get(self.groceries.get_absolute_url()).status_code, 404)
        response = bob.post(self.url("todo_add", self.groceries.pk), {"title": "Eggs"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(self.groceries.todos.all()), [self.milk])

    def test_remove_user_who_is_not_member_is_404(self):
        alice = self.client_for(self.alice)
        for user in [self.carol, self.alice]:
            with self.subTest(user=user.username):
                response = alice.post(
                    self.url("list_member_remove", self.groceries.pk, user.pk)
                )
                self.assertEqual(response.status_code, 404)
                self.assertBobIsMember()
                self.assertTrue(TodoList.objects.filter(pk=self.groceries.pk).exists())

    def test_remove_unknown_user_id_is_404(self):
        response = self.client_for(self.alice).post(
            self.url("list_member_remove", self.groceries.pk, 999999)
        )
        self.assertEqual(response.status_code, 404)
        self.assertBobIsMember()

    def test_deleting_list_removes_access(self):
        through = TodoList.members.through
        self.client_for(self.alice).post(self.url("list_delete", self.groceries.pk))
        response = self.client_for(self.bob).get(self.bobs_list.get_absolute_url())
        self.assertContains(response, escape("Bob's stuff"))
        self.assertNotContains(response, "Groceries")
        self.assertFalse(through.objects.filter(todolist_id=self.groceries.pk).exists())

    def test_get_does_not_leave_or_remove(self):
        bob_get = self.client_for(self.bob).get(
            self.url("list_leave", self.groceries.pk)
        )
        self.assertEqual(bob_get.status_code, 405)
        alice_get = self.client_for(self.alice).get(
            self.url("list_member_remove", self.groceries.pk, self.bob.pk)
        )
        self.assertEqual(alice_get.status_code, 405)
        self.assertBobIsMember()


class HomeTests(SharingTestCase):
    def test_home_prefers_own_list(self):
        response = self.client_for(self.bob).get(reverse("todo_list"))
        self.assertRedirects(response, self.bobs_list.get_absolute_url())

    def test_home_goes_to_shared_list_without_own_list(self):
        bob = self.client_for(self.bob)
        bob.post(self.url("list_delete", self.bobs_list.pk))
        response = bob.get(reverse("todo_list"))
        self.assertRedirects(response, self.groceries.get_absolute_url())

    def test_home_never_goes_to_a_list_you_cannot_see(self):
        carol = self.client_for(self.carol)
        carol.post(self.url("list_delete", self.carols_list.pk))
        response = carol.get(reverse("todo_list"))
        self.assertRedirects(response, reverse("list_create"))

        bob = self.client_for(self.bob)
        bob.post(self.url("list_delete", self.bobs_list.pk))
        bob.post(self.url("list_leave", self.groceries.pk))
        response = bob.get(reverse("todo_list"))
        self.assertRedirects(response, reverse("list_create"))


class LoggedOutTests(SharingTestCase):
    def test_new_addresses_need_login(self):
        requests = [
            (self.url("list_share", self.groceries.pk), {"username": "carol"}),
            (self.url("list_leave", self.groceries.pk), {}),
            (self.url("list_member_remove", self.groceries.pk, self.bob.pk), {}),
        ]
        for url, data in requests:
            with self.subTest(url=url):
                response = self.client.post(url, data)
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={url}",
                    fetch_redirect_response=False,
                )
        self.assertEqual(list(self.groceries.members.all()), [self.bob])


class EscapingTests(SharingTestCase):
    def test_usernames_are_escaped(self):
        owner = make_user("<b>ann")
        member = make_user("<b>ben")
        the_list = TodoList.objects.create(owner=owner, name="Tools")
        the_list.members.add(member)

        owners_page = self.client_for(owner).get(the_list.get_absolute_url())
        self.assertContains(owners_page, 'aria-label="Remove &lt;b&gt;ben"')
        self.assertContains(owners_page, '<span class="title">&lt;b&gt;ben</span>')
        self.assertNotContains(owners_page, "<b>")

        members_page = self.client_for(member).get(the_list.get_absolute_url())
        self.assertContains(members_page, "Shared by &lt;b&gt;ann")
        self.assertIn("Tools (&lt;b&gt;ann)", menu_part(members_page, SHARED_LISTS))
        self.assertNotContains(members_page, "<b>")


class NewListCancelTests(SharingTestCase):
    def test_member_with_only_shared_lists_sees_cancel(self):
        bob = self.client_for(self.bob)
        bob.post(self.url("list_delete", self.bobs_list.pk))
        response = bob.get(reverse("list_create"))
        self.assertContains(response, f'href="{reverse("todo_list")}">Cancel</a>')
