"""Delete my account: the confirm page, the password check, what goes and what stays."""

from unittest import mock

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.test import Client, override_settings
from django.urls import reverse
from django.utils.html import escape

from accounts.tests.helpers import (
    TEST_PASSWORD,
    LoggedInTestCase,
    PageParts,
    make_user,
    parse_page,
)
from todos.models import Subtask, Tag, Todo, TodoList
from todos.tests.helpers import add_todo, messages_of

URL = "/accounts/delete/"
LOGIN_REDIRECT = "/accounts/login/?next=/accounts/delete/"
DELETED_MESSAGE = "Your account was deleted."

User = get_user_model()

# Every table this feature may touch, counted before and after.
TABLES = {
    "users": User,
    "lists": TodoList,
    "todos": Todo,
    "steps": Subtask,
    "tags": Tag,
    "members": TodoList.members.through,
    "todo tags": Todo.tags.through,
    "sessions": Session,
    "admin log": LogEntry,
}


def row_counts():
    return {name: model.objects.count() for name, model in TABLES.items()}


def sessions_of(user):
    """The session rows that belong to this user (one per browser)."""
    return [
        row
        for row in Session.objects.all()
        if row.get_decoded().get(SESSION_KEY) == str(user.pk)
    ]


class PageText(PageParts):
    """Also the visible text of the page, and the text inside role="status"."""

    def __init__(self):
        super().__init__()
        self.texts = []
        self.status_texts = []
        self._roles = []  # (tag, is a role="status" element), of the open elements

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag not in {"input", "img", "source", "link", "meta", "br"}:
            self._roles.append((tag, dict(attrs).get("role") == "status"))

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        for index in range(len(self._roles) - 1, -1, -1):
            if self._roles[index][0] == tag:
                self._roles.pop(index)
                break

    def handle_data(self, data):
        super().handle_data(data)
        self.texts.append(data)
        if any(is_status for _tag, is_status in self._roles):
            self.status_texts.append(data)

    @property
    def text(self):
        return " ".join(" ".join(self.texts).split())

    @property
    def status_text(self):
        return " ".join(" ".join(self.status_texts).split())


def page_text(response):
    return parse_page(response, PageText)


class DeleteAccountWorld(LoggedInTestCase):
    """alice (logged in) owns "Inbox" and "Family" (shared with carol and dave);
    bob and carol each own a list shared with alice.

    alice owns 2 lists with 3 to-dos and 1 tag. "Family" has 2 members and
    2 to-dos, so a count without distinct=True would say 4 there.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        alice = cls.user
        cls.carol = make_user("carol")
        cls.dave = make_user("dave")

        cls.milk = add_todo(cls.todo_list, "Buy milk")
        Subtask.objects.create(todo=cls.milk, title="Find the bag")
        cls.milk.set_tags(["home"])
        cls.family = TodoList.objects.create(owner=alice, name="Family")
        cls.family.members.add(cls.carol, cls.dave)
        cls.plan_trip = add_todo(cls.family, "Plan trip")
        cls.carols_packing = add_todo(cls.family, "Carol's packing")  # Added by carol.

        cls.other_list.members.add(alice)
        cls.alices_idea = add_todo(cls.other_list, "Alice's idea")  # Added by alice.
        cls.idea_step = Subtask.objects.create(todo=cls.alices_idea, title="Sketch it")
        cls.alices_idea.set_tags(["work"])  # bob's tag: he owns the list.
        cls.bobs_own = add_todo(cls.other_list, "Bob's own")

        cls.carol_list = TodoList.objects.create(owner=cls.carol, name="Carol's list")
        cls.carol_list.members.add(alice)
        cls.carols_own = add_todo(cls.carol_list, "Carol's own")

    def delete_account(self, client=None, password=TEST_PASSWORD, **extra):
        return (client or self.client).post(URL, {"password": password, **extra})

    def assertStillLoggedIn(self, client=None, user=None):
        session = (client or self.client).session
        self.assertEqual(session.get(SESSION_KEY), str((user or self.user).pk))
        self.assertTrue(User.objects.filter(pk=(user or self.user).pk).exists())


class DeleteAccountPageTests(DeleteAccountWorld):
    def test_page_shows_what_will_be_deleted(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        text = page_text(response).text
        self.assertIn(
            "2 lists and their 3 to-dos (with their steps), and your 1 tag"
            " will be deleted.",
            text,
        )
        self.assertIn("“Family” (2 members) — they will lose this list.", text)
        # The to-dos of "Bob's list" and "Carol's list" ("Alice's idea" too) are not counted.
        self.assertIn("You will leave 2 lists that someone else shared with you.", text)
        self.assertIn("This cannot be undone.", text)
        self.assertIn("Copies in the backups/ folder still hold your data.", text)
        self.assertIn("make backup", text)
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_page_names_no_member_and_no_other_list(self):
        member = make_user("Zoë-member")
        owner = make_user("Øystein-owner")
        self.family.members.add(member)
        theirs = TodoList.objects.create(owner=owner, name="Øystein's list")
        theirs.members.add(self.user)
        response = self.client.get(URL)
        text = page_text(response).text
        self.assertIn("Family", text)  # The page does show her own shared list.
        for name in ["Zoë-member", "Øystein-owner", "Øystein's list"]:
            with self.subTest(name=name):
                self.assertNotIn(name, text)
                self.assertNotContains(response, escape(name))

    def test_page_for_a_person_with_no_lists(self):
        erin = make_user("erin")
        response = self.client_for(erin).get(URL)
        text = page_text(response).text
        self.assertIn("You have no lists.", text)
        self.assertNotIn("they will lose", text)
        self.assertNotIn("You will leave", text)
        self.assertEqual(len(parse_page(response).all("input", name="password")), 1)

    def test_header_links_to_the_account_page(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        page = parse_page(response)
        (link,) = page.all("a", **{"class": "who"})
        self.assertEqual(link["href"], URL)
        self.assertEqual(link["aria-label"], "Logged in as alice: your account")
        self.assertNotIn("aria-current", link)
        self.assertIn((URL, "Logged in as alice"), page.links)

        (link,) = parse_page(self.client.get(URL)).all("a", **{"class": "who"})
        self.assertEqual(link["aria-current"], "page")

    def test_form_helps_password_managers(self):
        page = parse_page(self.client.get(URL))
        (password,) = page.all("input", name="password")
        self.assertEqual(password["type"], "password")
        self.assertEqual(password["autocomplete"], "current-password")
        (username,) = page.all("input", name="username")
        self.assertEqual(username["autocomplete"], "username")
        self.assertEqual(username["value"], "alice")
        self.assertIn("readonly", username)
        self.assertIn("hidden", username)

    def test_staff_user_can_delete_themselves(self):
        root = User.objects.create_superuser(username="root", password=TEST_PASSWORD)
        TodoList.objects.create(owner=root, name="Admin things")
        client = self.client_for(root)
        admin_line = "You are an admin."
        self.assertIn(admin_line, page_text(client.get(URL)).text)
        self.assertNotIn(admin_line, page_text(self.client.get(URL)).text)

        self.delete_account(client)
        self.assertFalse(User.objects.filter(pk=root.pk).exists())
        self.assertFalse(TodoList.objects.filter(name="Admin things").exists())


class NothingIsDeletedTests(DeleteAccountWorld):
    def test_get_and_head_delete_nothing(self):
        before = row_counts()
        self.assertEqual(
            self.client.get(URL, {"password": TEST_PASSWORD}).status_code, 200
        )
        self.assertEqual(self.client.head(URL).status_code, 200)
        self.assertEqual(row_counts(), before)
        self.assertStillLoggedIn()

    def test_other_methods_are_405(self):
        before = row_counts()
        for method in ["put", "patch", "delete"]:
            with self.subTest(method=method):
                response = getattr(self.client, method)(URL)
                self.assertEqual(response.status_code, 405)
        self.assertEqual(row_counts(), before)

    def test_anonymous_goes_to_login(self):
        visitor = Client()
        before = row_counts()
        for response in [
            visitor.get(URL),
            visitor.post(URL, {"password": TEST_PASSWORD}),
        ]:
            self.assertRedirects(
                response, LOGIN_REDIRECT, fetch_redirect_response=False
            )
        self.assertEqual(row_counts(), before)

    def test_post_without_csrf_token_is_403(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = self.delete_account(client)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password_deletes_nothing(self):
        before = row_counts()
        response = self.delete_account(password="not-the-password")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wrong password. Nothing was deleted.")
        self.assertContains(response, "<title>Error: ")
        self.assertContains(response, "Not deleted. Fix what is marked below.")
        # A fresh summary, the same as on the GET page.
        text = page_text(response).text
        self.assertIn("3 to-dos", text)
        self.assertIn("“Family” (2 members)", text)
        self.assertEqual(row_counts(), before)
        self.assertStillLoggedIn()

    def test_empty_password_deletes_nothing(self):
        before = row_counts()
        self.assertEqual(self.delete_account(password="").status_code, 200)
        self.assertEqual(row_counts(), before)
        self.assertStillLoggedIn()

    def test_failed_delete_changes_nothing(self):
        second = self.client_for(self.user)  # Another browser of alice.
        before = row_counts()
        with mock.patch.object(User, "delete", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                self.delete_account()
        self.assertEqual(row_counts(), before)
        # The session sweep was rolled back with the transaction.
        row = Session.objects.get(pk=second.session.session_key)
        self.assertEqual(row.get_decoded()[SESSION_KEY], str(self.user.pk))


class WhatGoesAndWhatStaysTests(DeleteAccountWorld):
    def test_right_password_deletes_exactly_alices_rows(self):
        before = row_counts()
        response = self.delete_account()
        self.assertRedirects(response, "/", fetch_redirect_response=False)

        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(
            TodoList.objects.filter(pk__in=[self.todo_list.pk, self.family.pk]).exists()
        )
        gone = [self.milk, self.plan_trip, self.carols_packing]
        self.assertFalse(Todo.objects.filter(pk__in=[t.pk for t in gone]).exists())
        self.assertFalse(Subtask.objects.filter(title="Find the bag").exists())
        self.assertFalse(Tag.objects.filter(name="home").exists())

        self.assertEqual(
            set(User.objects.values_list("username", flat=True)),
            {"bob", "carol", "dave"},
        )
        self.assertEqual(
            {t.title for t in self.other_list.todos.all()},
            {"Alice's idea", "Bob's own"},
        )
        self.assertEqual(list(self.alices_idea.subtasks.all()), [self.idea_step])
        self.assertEqual([t.name for t in self.alices_idea.tags.all()], ["work"])
        self.assertEqual([t.name for t in self.other_user.tags.all()], ["work"])
        self.assertEqual(
            [t.title for t in self.carol_list.todos.all()], ["Carol's own"]
        )
        self.assertEqual(list(self.other_list.members.all()), [])
        self.assertEqual(list(self.carol_list.members.all()), [])

        after = row_counts()
        expected = {
            "users": before["users"] - 1,
            "lists": before["lists"] - 2,
            "todos": before["todos"] - 3,
            "steps": before["steps"] - 1,
            "tags": before["tags"] - 1,
            "members": before["members"] - 4,  # carol, dave in Family; alice in two.
            "todo tags": before["todo tags"] - 1,
            "admin log": before["admin log"],
        }
        after.pop("sessions")  # Checked in SessionsTests.
        self.assertEqual(after, expected)

    def test_lists_shared_with_her_lose_only_her(self):
        self.other_list.members.add(self.dave)
        self.delete_account()
        self.other_list.refresh_from_db()
        self.assertEqual(list(self.other_list.members.all()), [self.dave])
        self.assertEqual(self.other_list.name, "Bob's list")
        self.assertEqual(self.other_list.owner, self.other_user)
        self.assertEqual(self.other_list.todos.count(), 2)

    def test_member_loses_her_shared_list(self):
        carol = self.client_for(self.carol)
        self.delete_account()
        self.assertEqual(carol.get(self.family.get_absolute_url()).status_code, 404)
        self.assertEqual(
            list(TodoList.objects.visible_to(self.carol)), [self.carol_list]
        )
        self.assertRedirects(
            carol.get("/"),
            self.carol_list.get_absolute_url(),
            fetch_redirect_response=False,
        )

    def test_her_admin_log_rows_go(self):
        list_type = ContentType.objects.get_for_model(TodoList)
        for user in [self.user, self.other_user]:
            LogEntry.objects.create(
                user=user,
                content_type=list_type,
                object_id=str(self.other_list.pk),
                object_repr="",
                action_flag=ADDITION,
            )
        self.delete_account()
        self.assertEqual(
            list(LogEntry.objects.values_list("user", flat=True)), [self.other_user.pk]
        )

    def test_bob_deletes_only_bob(self):
        bob = self.client_for(self.other_user)
        response = self.delete_account(bob, username="alice", user_id=self.user.pk)
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=self.other_user.pk).exists())
        self.assertFalse(TodoList.objects.filter(pk=self.other_list.pk).exists())
        self.assertFalse(Todo.objects.filter(pk=self.alices_idea.pk).exists())
        self.assertFalse(Tag.objects.filter(name="work").exists())

        self.assertStillLoggedIn()
        self.assertEqual(
            {lst.name for lst in self.user.todo_lists.all()}, {"Inbox", "Family"}
        )
        self.assertEqual(
            set(
                Todo.objects.filter(todo_list__owner=self.user).values_list(
                    "title", flat=True
                )
            ),
            {"Buy milk", "Plan trip", "Carol's packing"},
        )
        self.assertTrue(Subtask.objects.filter(title="Find the bag").exists())
        self.assertEqual([t.name for t in self.user.tags.all()], ["home"])
        self.assertEqual(list(self.carol_list.members.all()), [self.user])
        self.assertEqual(
            [t.title for t in self.carol_list.todos.all()], ["Carol's own"]
        )

    def test_members_undo_after_the_list_is_gone(self):
        carol = self.client_for(self.carol)
        carol.post(reverse("todo_delete", args=[self.plan_trip.pk]))
        self.delete_account()
        response = carol.post(reverse("todo_undo_delete", args=[self.plan_trip.pk]))
        # Her "Deleted ..." message was never shown, so it is still in the queue.
        self.assertEqual(
            messages_of(response)[-1],
            "Could not undo: you can no longer see the list it was in.",
        )
        self.assertFalse(Todo.objects.filter(pk=self.plan_trip.pk).exists())


class SessionsTests(DeleteAccountWorld):
    def test_her_other_sessions_are_deleted(self):
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")
        second = self.client_for(self.user)  # Another browser of alice.
        bob = self.client_for(self.other_user)
        row = Session.objects.get(pk=second.session.session_key)
        self.assertEqual(row.get_decoded()[SESSION_KEY], str(self.user.pk))
        self.assertEqual(len(sessions_of(self.user)), 2)  # This browser and the second.

        self.delete_account()

        self.assertEqual(sessions_of(self.user), [])
        self.assertTemplateUsed(second.get("/"), "todos/landing.html")
        self.assertTrue(Session.objects.filter(pk=bob.session.session_key).exists())
        self.assertRedirects(
            bob.get("/"),
            self.other_list.get_absolute_url(),
            fetch_redirect_response=False,
        )


class MessageAfterDeleteChecks:
    """Run by one class per message storage (each test method gets a fresh database)."""

    def test_logged_out_with_message_on_landing(self):
        response = self.delete_account(follow=True)
        self.assertRedirects(response, "/")
        self.assertTemplateUsed(response, "todos/landing.html")
        page = page_text(response)
        self.assertIn(DELETED_MESSAGE, page.status_text)
        self.assertNotIn("Logged in as", page.text)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_message_is_shown_once(self):
        self.delete_account(follow=True)
        self.assertNotContains(self.client.get("/"), DELETED_MESSAGE)

    def delete_account(self, follow=False):
        return self.client.post(URL, {"password": TEST_PASSWORD}, follow=follow)


@override_settings(
    MESSAGE_STORAGE="django.contrib.messages.storage.fallback.FallbackStorage"
)
class MessageAfterDeleteFallbackTests(MessageAfterDeleteChecks, LoggedInTestCase):
    pass


@override_settings(
    MESSAGE_STORAGE="django.contrib.messages.storage.session.SessionStorage"
)
class MessageAfterDeleteSessionTests(MessageAfterDeleteChecks, LoggedInTestCase):
    pass
