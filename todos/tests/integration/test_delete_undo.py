"""Tests for Delete with an Undo button (todos/undo.py and todo_undo_delete)."""

import html
import re
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.messages import constants
from django.contrib.messages.storage.cookie import CookieStorage
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from accounts.tests.helpers import TEST_PASSWORD, LoggedInTestCase
from todos import views
from todos.models import Subtask, Tag, Todo, TodoList
from todos.tests.helpers import add_todo, count_queries, shown_titles
from todos.undo import SESSION_KEY, SNAPSHOT_FIELDS

UNDO_FORM = re.compile(
    r'<form class="undo" method="post" action="(?P<action>[^"]+)">(?P<body>.*?)</form>',
    re.S,
)


def added_messages(response):
    """The texts of the messages this one request added (not older, unread ones)."""
    return [str(m) for m in response.wsgi_request._messages._queued_messages]


def values(todo):
    """Every snapshot field of a to-do, read fresh from the database."""
    todo = Todo.objects.get(pk=todo.pk)
    return {name: getattr(todo, name) for name in SNAPSHOT_FIELDS}


class DeleteUndoTestCase(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.list_url = self.todo_list.get_absolute_url()

    def delete(self, todo, client=None, next_url=None):
        return (client or self.client).post(
            reverse("todo_delete", args=[todo.pk]), {"next": next_url or self.list_url}
        )

    def undo(self, pk, client=None, next_url=None):
        data = {"next": next_url} if next_url is not None else {}
        return (client or self.client).post(
            reverse("todo_undo_delete", args=[pk]), data
        )

    def undo_forms(self, response):
        return list(UNDO_FORM.finditer(response.content.decode()))

    def set_snapshot_age(self, minutes, client=None):
        session = (client or self.client).session
        snapshot = session[SESSION_KEY]
        snapshot["deleted_at"] = (
            timezone.now() - timedelta(minutes=minutes)
        ).isoformat()
        session[SESSION_KEY] = snapshot
        session.save()


class DeleteTests(DeleteUndoTestCase):
    def test_delete_shows_message_with_undo(self):
        todo = add_todo(self.todo_list, "Buy milk")
        response = self.client.post(
            reverse("todo_delete", args=[todo.pk]), {"next": self.list_url}, follow=True
        )
        self.assertContains(response, "Deleted “Buy milk”.")
        forms = self.undo_forms(response)
        self.assertEqual(len(forms), 1)
        self.assertEqual(
            forms[0]["action"], reverse("todo_undo_delete", args=[todo.pk])
        )
        body = forms[0]["body"]
        self.assertIn('name="csrfmiddlewaretoken"', body)
        next_value = html.unescape(re.search(r'name="next" value="([^"]*)"', body)[1])
        self.assertTrue(next_value.endswith(f"#todo-{todo.pk}"), next_value)

    def test_double_delete_does_not_replace_the_snapshot(self):
        # Two Delete posts close together: the second read the to-do before the
        # first one committed. It must read again inside its transaction (and
        # get 404), not snapshot the stale copy with no tags and no steps.
        todo = add_todo(self.todo_list, "Buy milk")
        todo.set_tags(["shop"])
        Subtask.objects.create(todo=todo, title="Find a bag")
        stale = Todo.objects.get(pk=todo.pk)
        self.delete(todo)
        real = views.get_visible_todo
        depth = len(connection.atomic_blocks)  # The test's own transaction.

        def read_before_commit(user, pk):
            if len(connection.atomic_blocks) == depth:
                return stale  # Read before the other delete committed.
            return real(user, pk)

        with patch("todos.views.get_visible_todo", side_effect=read_before_commit):
            response = self.delete(todo)
        self.assertEqual(response.status_code, 404)
        snapshot = self.client.session[SESSION_KEY]
        self.assertEqual(snapshot["tags"], ["shop"])
        self.assertEqual(snapshot["steps"], [["Find a bag", False]])

    def test_delete_still_deletes_at_once(self):
        todo = add_todo(self.todo_list, "Buy milk")
        Subtask.objects.create(todo=todo, title="Find a bag")
        self.delete(todo)
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())
        self.assertFalse(Subtask.objects.filter(todo_id=todo.pk).exists())

    def test_message_is_a_div(self):
        todo = add_todo(self.todo_list, "Buy milk")
        response = self.client.post(
            reverse("todo_delete", args=[todo.pk]), {"next": self.list_url}, follow=True
        )
        self.assertRegex(
            response.content.decode(),
            r'(?s)<div class="message[^"]*">\s*<span>Deleted “Buy milk”.</span>\s*'
            r'<form class="undo"[^>]*>.*?</form>\s*</div>',
        )
        self.assertNotContains(response, '<p class="message')

    def test_message_escapes_the_title(self):
        todo = add_todo(self.todo_list, "<b>x</b>")
        response = self.client.post(
            reverse("todo_delete", args=[todo.pk]), {"next": self.list_url}, follow=True
        )
        self.assertContains(response, "Deleted “&lt;b&gt;x&lt;/b&gt;”.")
        self.assertNotContains(response, "<b>x</b>")
        response = self.client.post(
            reverse("todo_undo_delete", args=[todo.pk]),
            {"next": self.list_url},
            follow=True,
        )
        self.assertContains(response, "Restored “&lt;b&gt;x&lt;/b&gt;”.")
        self.assertNotContains(response, "<b>x</b>")


class UndoTests(DeleteUndoTestCase):
    def test_undo_restores_everything(self):
        old = timezone.now() - timedelta(days=3)
        first = add_todo(self.todo_list, "First")
        todo = add_todo(
            self.todo_list,
            "Buy milk",
            description="Oat milk",
            priority=Todo.Priority.HIGH,
            due_date=date(2026, 10, 20),
            repeat=Todo.Repeat.WEEKLY,
            reminded_on=date(2026, 10, 10),
        )
        last = add_todo(self.todo_list, "Last")
        Todo.objects.filter(pk=first.pk).update(created_at=old - timedelta(hours=1))
        Todo.objects.filter(pk=todo.pk).update(created_at=old)
        todo.set_tags(["work", "shop"])
        for title, done in [("Find a bag", True), ("Walk", False), ("Pay", False)]:
            Subtask.objects.create(todo=todo, title=title, done=done)
        self.assertEqual(Todo.objects.get(pk=todo.pk).position, 2)
        before = values(todo)

        self.delete(todo)
        response = self.undo(todo.pk)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(values(todo), before)
        restored = Todo.objects.get(pk=todo.pk)
        self.assertEqual(
            sorted(restored.tags.values_list("name", flat=True)), ["shop", "work"]
        )
        self.assertEqual(
            [(s.title, s.done) for s in restored.subtasks.all()],
            [("Find a bag", True), ("Walk", False), ("Pay", False)],
        )
        expected = ["First", "Buy milk", "Last"]
        self.assertEqual(shown_titles(self.client.get(self.list_url)), expected)
        manual = self.client.get(self.list_url, {"sort": "manual"})
        self.assertEqual(shown_titles(manual), expected)
        self.assertEqual(added_messages(response), ["Restored “Buy milk”."])
        self.assertEqual(last.pk, Todo.objects.get(title="Last").pk)

    def test_undo_goes_back_to_the_row(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        next_url = f"{self.list_url}?q=milk#todo-{todo.pk}"
        response = self.undo(todo.pk, next_url=next_url)
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

        self.delete(todo)
        response = self.undo(todo.pk, next_url="//evil.example/")
        self.assertRedirects(
            response, f"{self.list_url}#todo-{todo.pk}", fetch_redirect_response=False
        )

    def test_undo_works_only_once(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        first = self.undo(todo.pk, next_url=self.list_url)
        second = self.undo(todo.pk, next_url=self.list_url)
        self.assertEqual(Todo.objects.filter(title="Buy milk").count(), 1)
        self.assertEqual(added_messages(first), ["Restored “Buy milk”."])
        self.assertRedirects(second, self.list_url, fetch_redirect_response=False)
        self.assertEqual(added_messages(second), [])

    def test_double_submit_with_the_old_session_restores_once(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        saved = dict(self.client.session.items())
        first = self.undo(todo.pk, next_url=self.list_url)
        # A second post that read the session before the first one saved it.
        session = self.client.session
        for key, value in saved.items():
            session[key] = value
        session.save()
        self.assertIn(SESSION_KEY, self.client.session)
        second = self.undo(todo.pk, next_url=self.list_url)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Todo.objects.filter(pk=todo.pk).count(), 1)
        self.assertEqual(Todo.objects.filter(title="Buy milk").count(), 1)
        self.assertEqual(added_messages(first), ["Restored “Buy milk”."])
        self.assertEqual(added_messages(second), [])

    def test_id_taken_by_another_todo(self):
        todo = add_todo(self.todo_list, "Buy milk")
        pk = todo.pk
        self.delete(todo)
        # As after a table rebuild: a new to-do gets the old id.
        other = Todo.objects.create(pk=pk, todo_list=self.todo_list, title="Other")
        before = values(other)
        response = self.undo(pk, next_url=self.list_url)
        self.assertEqual(added_messages(response), ["Could not undo."])
        self.assertEqual(values(other), before)
        self.assertEqual(Todo.objects.count(), 1)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_two_deletes_only_the_last_message_has_undo(self):
        a = add_todo(self.todo_list, "A")
        b = add_todo(self.todo_list, "B")
        self.delete(a)
        self.delete(b)
        response = self.client.get(self.list_url)
        self.assertContains(response, "Deleted “A”.")
        self.assertContains(response, "Deleted “B”.")
        forms = self.undo_forms(response)
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]["action"], reverse("todo_undo_delete", args=[b.pk]))
        self.assertRegex(
            response.content.decode(),
            r"<span>Deleted “B”.</span>\s*<form class=\"undo\"",
        )

    def test_no_undo_button_without_snapshot(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        session = self.client.session
        del session[SESSION_KEY]
        session.save()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted “Buy milk”.")
        self.assertEqual(self.undo_forms(response), [])

    def test_no_undo_button_for_a_message_without_its_snapshot_after_login(self):
        # A message tagged undo-delete-7 but a new session (logged out and in).
        storage = CookieStorage(None)
        storage.add(constants.SUCCESS, "Deleted “X”.", extra_tags="undo-delete-7")
        self.client.cookies[storage.cookie_name] = storage._encode(
            list(storage._queued_messages)
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleted “X”.")
        self.assertEqual(self.undo_forms(response), [])

    def test_expired_snapshot_is_dropped_by_the_list_page(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        self.set_snapshot_age(14)
        self.client.get(self.list_url)
        self.assertIn(SESSION_KEY, self.client.session)
        self.set_snapshot_age(16)
        self.client.get(self.list_url)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_only_the_last_delete_can_be_undone(self):
        a = add_todo(self.todo_list, "A")
        b = add_todo(self.todo_list, "B")
        self.delete(a)
        self.delete(b)
        self.assertEqual(self.undo(a.pk).status_code, 404)
        self.assertFalse(Todo.objects.filter(pk=a.pk).exists())
        self.assertEqual(self.undo(b.pk).status_code, 302)
        self.assertTrue(Todo.objects.filter(pk=b.pk).exists())

    def test_stranger_gets_404(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        self.assertOtherUserGets404(reverse("todo_undo_delete", args=[todo.pk]))
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())
        self.assertEqual(self.undo(todo.pk).status_code, 302)
        self.assertTrue(Todo.objects.filter(pk=todo.pk).exists())

    def test_stranger_gets_404_for_an_existing_todo(self):
        # bob has no snapshot; alice's to-do exists but bob cannot see it.
        todo = add_todo(self.todo_list, "Buy milk")
        before = values(todo)
        self.assertOtherUserGets404(reverse("todo_undo_delete", args=[todo.pk]))
        self.assertEqual(values(todo), before)
        self.assertEqual(Todo.objects.count(), 1)

    def test_snapshot_of_another_user_is_not_offered_or_used(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        session = self.client.session
        snapshot = session[SESSION_KEY]
        snapshot["user"] = self.other_user.pk
        session[SESSION_KEY] = snapshot
        session.save()
        response = self.client.get(self.list_url)
        self.assertContains(response, "Deleted “Buy milk”.")
        self.assertEqual(self.undo_forms(response), [])
        self.assertEqual(self.undo(todo.pk).status_code, 404)
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

    def test_undo_button_names_the_deleted_todo(self):
        todo = add_todo(self.todo_list, "<b>x</b>")
        response = self.client.post(
            reverse("todo_delete", args=[todo.pk]), {"next": self.list_url}, follow=True
        )
        self.assertContains(
            response,
            '<button class="button button-secondary button-compact" type="submit" '
            'aria-label="Undo delete: &lt;b&gt;x&lt;/b&gt;">Undo</button>',
            html=True,
        )

    def test_get_is_405(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        response = self.client.get(reverse("todo_undo_delete", args=[todo.pk]))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

    def test_logout_ends_the_undo(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        self.client.logout()
        self.assertTrue(
            self.client.login(username=self.user.username, password=TEST_PASSWORD)
        )
        self.assertEqual(self.undo(todo.pk).status_code, 404)
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

    def test_undo_after_the_time_limit(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        later = timezone.now() + timedelta(minutes=16)
        with patch("django.utils.timezone.now", return_value=later):
            response = self.undo(todo.pk)
        self.assertEqual(
            added_messages(response), ["Too late to undo: the to-do stays deleted."]
        )
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

        todo = add_todo(self.todo_list, "Buy bread")
        self.delete(todo)
        later = timezone.now() + timedelta(minutes=14)
        with patch("django.utils.timezone.now", return_value=later):
            response = self.undo(todo.pk)
        self.assertEqual(added_messages(response), ["Restored “Buy bread”."])
        self.assertTrue(Todo.objects.filter(pk=todo.pk).exists())

    def test_list_query_count_does_not_change(self):
        def load():
            self.assertEqual(self.client.get(self.list_url).status_code, 200)

        add_todo(self.todo_list, "Keep")
        load()  # Reads the messages once, so both counts below start alike.
        without = count_queries(load)
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        load()  # Shows (and so ends) the "Deleted" message.
        self.assertIn(SESSION_KEY, self.client.session)
        self.assertEqual(count_queries(load), without)


class SharedUndoTests(DeleteUndoTestCase):
    def setUp(self):
        super().setUp()
        self.todo_list.members.add(self.other_user)
        self.bob = self.client_for(self.other_user)

    def test_member_undo_after_being_removed(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo, client=self.bob)
        self.client.post(
            reverse("list_member_remove", args=[self.todo_list.pk, self.other_user.pk])
        )
        response = self.undo(todo.pk, client=self.bob)
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(
            added_messages(response),
            ["Could not undo: you can no longer see the list it was in."],
        )
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

    def test_member_can_undo(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo, client=self.bob)
        response = self.undo(todo.pk, client=self.bob)
        self.assertEqual(added_messages(response), ["Restored “Buy milk”."])
        self.assertTrue(Todo.objects.filter(pk=todo.pk).exists())

    def test_undo_after_the_list_was_deleted(self):
        todo = add_todo(self.todo_list, "Buy milk")
        self.delete(todo)
        self.client.post(reverse("list_delete", args=[self.todo_list.pk]))
        self.assertFalse(TodoList.objects.filter(pk=self.todo_list.pk).exists())
        response = self.undo(todo.pk)
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(
            added_messages(response),
            ["Could not undo: you can no longer see the list it was in."],
        )
        self.assertFalse(Todo.objects.filter(pk=todo.pk).exists())

    def test_tags_go_to_the_list_owner(self):
        todo = add_todo(self.todo_list, "Buy bread")
        todo.set_tags(["shop"])
        self.delete(todo, client=self.bob)
        Tag.objects.filter(owner=self.user).delete()  # Made again by the undo.
        self.undo(todo.pk, client=self.bob)
        restored = Todo.objects.get(pk=todo.pk)
        self.assertEqual(
            [(t.owner_id, t.name) for t in restored.tags.all()],
            [(self.user.pk, "shop")],
        )
        self.assertFalse(Tag.objects.filter(owner=self.other_user).exists())


class RecurringUndoTests(DeleteUndoTestCase):
    def weekly(self):
        return add_todo(
            self.todo_list,
            "Water plants",
            repeat=Todo.Repeat.WEEKLY,
            due_date=timezone.localdate(),
        )

    def done(self, todo, value=True):
        self.client.post(
            reverse("todo_toggle", args=[todo.pk]), {"done": "1" if value else "0"}
        )

    def test_recurring_links_come_back(self):
        original = self.weekly()
        self.done(original)
        copy = Todo.objects.get(repeated_from=original)

        self.delete(original)
        copy.refresh_from_db()
        self.assertIsNone(copy.repeated_from_id)
        self.undo(original.pk)
        copy.refresh_from_db()
        self.assertEqual(copy.repeated_from_id, original.pk)
        self.assertEqual(Todo.objects.get(pk=original.pk).get_next_copy(), copy)

        self.delete(copy)
        self.undo(copy.pk)
        self.assertEqual(Todo.objects.get(pk=copy.pk).repeated_from_id, original.pk)
        self.assertEqual(Todo.objects.get(pk=original.pk).get_next_copy().pk, copy.pk)

    def test_restored_copy_still_counts_as_unchanged(self):
        original = self.weekly()
        self.done(original)
        copy = Todo.objects.get(repeated_from=original)
        made = copy.copy_fingerprint
        self.assertTrue(made)
        self.delete(copy)
        self.undo(copy.pk)
        restored = Todo.objects.get(pk=copy.pk)
        self.assertEqual(restored.copy_fingerprint, made)
        self.assertFalse(restored.changed_since_copy())
        # So Undo on the original still removes the unchanged copy.
        self.done(original, False)
        self.assertFalse(Todo.objects.filter(pk=copy.pk).exists())

    def test_recurring_link_not_stolen(self):
        original = self.weekly()
        self.done(original)
        copy = Todo.objects.get(repeated_from=original)
        self.delete(copy)
        self.done(original, False)  # No copy to remove.
        self.done(original)  # A new copy.
        new_copy = Todo.objects.get(repeated_from=original)
        response = self.undo(copy.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Todo.objects.get(pk=copy.pk).repeated_from_id)
        self.assertEqual(Todo.objects.get(pk=original.pk).get_next_copy(), new_copy)
