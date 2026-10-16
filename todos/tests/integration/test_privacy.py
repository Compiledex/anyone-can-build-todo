"""Privacy: message text stays on the server, expired sessions can be removed.

Messages (like "Deleted “Buy milk”.") are kept in the session
(MESSAGE_STORAGE in config/settings.py), never in a cookie. `make run` runs
Django's clearsessions, which deletes expired sessions (and an old undo
snapshot in them).
"""

from datetime import timedelta

from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase
from todos.tests.helpers import add_todo
from todos.undo import SESSION_KEY

DELETED = "Deleted “Secret milk”."


class MessagesInSessionTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.list_url = self.todo_list.get_absolute_url()
        self.todo = add_todo(self.todo_list, "Secret milk")

    def delete(self):
        return self.client.post(
            reverse("todo_delete", args=[self.todo.pk]), {"next": self.list_url}
        )

    def test_delete_message_is_not_in_a_cookie(self):
        response = self.delete()
        self.assertEqual(response.status_code, 302)
        # CookieStorage's cookie ("messages"), the one Django used before.
        self.assertNotIn(CookieStorage.cookie_name, response.cookies)
        self.assertIn("Secret milk", self.client.session["_messages"])

    def test_message_shows_once_then_leaves_the_session(self):
        self.delete()
        self.assertContains(self.client.get(self.list_url), DELETED)
        self.assertNotIn("_messages", self.client.session)
        self.assertNotContains(self.client.get(self.list_url), DELETED)

    def test_undo_message_still_shows(self):
        self.delete()
        response = self.client.post(
            reverse("todo_undo_delete", args=[self.todo.pk]),
            {"next": self.list_url},
            follow=True,
        )
        self.assertContains(response, "Restored “Secret milk”.")


class ExpiredSessionsTests(TestCase):
    def make_session(self, expire_date, data):
        store = SessionStore()
        store.update(data)
        store.create()
        Session.objects.filter(session_key=store.session_key).update(
            expire_date=expire_date
        )
        return store.session_key

    def test_clearsessions_removes_expired_and_keeps_live(self):
        now = timezone.now()
        expired = self.make_session(
            now - timedelta(days=1), {SESSION_KEY: {"title": "Old secret"}}
        )
        live = self.make_session(now + timedelta(days=1), {"a": 1})
        call_command("clearsessions")
        self.assertFalse(Session.objects.filter(session_key=expired).exists())
        self.assertTrue(Session.objects.filter(session_key=live).exists())
