"""The admin log keeps no names: no to-do title, list name, step or username.

A superuser ("staffer") uses /admin/ on carol's list "Secret errands". Every
test checks that no log row holds "secret" or "carol" (any case).
"""

import json
from html.parser import HTMLParser

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.tests.helpers import make_user
from todos.admin_log import HIDDEN_NAME, NoNamesInLog
from todos.models import Todo, TodoList


class AdminFormFields(HTMLParser):
    """The fields of the admin's main form (the one that is not the logout form)."""

    def __init__(self):
        super().__init__()
        self.data = {}
        self._in_form = False
        self._select = None
        self._multiple = False
        self._textarea = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._in_form = attrs.get("id") != "logout-form"
            return
        if not self._in_form:
            return
        name = attrs.get("name")
        if tag == "input" and name:
            kind = attrs.get("type", "text")
            if kind in ("submit", "button", "file"):
                return
            if kind in ("checkbox", "radio"):
                if "checked" in attrs:
                    self.data[name] = attrs.get("value", "on")
                return
            self.data[name] = attrs.get("value") or ""
        elif tag == "select" and name:
            self._select = name
            self._multiple = "multiple" in attrs
            self.data[name] = [] if self._multiple else ""
        elif tag == "option" and self._select and "selected" in attrs:
            value = attrs.get("value") or ""
            if self._multiple:
                self.data[self._select].append(value)
            else:
                self.data[self._select] = value
        elif tag == "textarea" and name:
            self._textarea = name
            self.data[name] = ""

    def handle_endtag(self, tag):
        if tag == "form":
            self._in_form = False
        elif tag == "select":
            self._select = None
        elif tag == "textarea":
            self._textarea = None

    def handle_data(self, data):
        if self._textarea:
            # Django puts a newline after <textarea>; the browser drops it.
            self.data[self._textarea] += data.lstrip("\n")


def admin_form(client, url):
    response = client.get(url)
    assert response.status_code == 200, response.status_code
    parser = AdminFormFields()
    parser.feed(response.content.decode())
    return parser.data


class AdminLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staffer = get_user_model().objects.create_superuser(
            username="staffer", password="not-a-real-password-1"
        )
        cls.carol = make_user("carol")
        cls.the_list = TodoList.objects.create(owner=cls.carol, name="Secret errands")
        cls.todo = Todo.objects.create(todo_list=cls.the_list, title="Buy secret milk")

    def setUp(self):
        self.client.force_login(self.staffer)

    def tearDown(self):
        for entry in LogEntry.objects.all():
            for text in (entry.object_repr, entry.change_message):
                self.assertNotIn("secret", text.lower())
                self.assertNotIn("carol", text.lower())
                self.assertNotIn("call the bank", text.lower())

    def assert_saved(self, response):
        """The admin saved the form and went on (no form errors)."""
        if response.status_code != 302:
            form = response.context["adminform"].form
            inlines = [f.errors for f in response.context["inline_admin_formsets"]]
            self.fail(f"Not saved: {form.errors} {inlines}")

    def only_entry(self):
        (entry,) = LogEntry.objects.all()
        # The admin user who did it, never the owner of the object (carol).
        self.assertEqual(entry.user_id, self.staffer.pk)
        return entry

    def add_through_admin(self):
        """Add "Secret new to-do" with the step "Call the bank"; return the to-do."""
        url = reverse("admin:todos_todo_add")
        data = admin_form(self.client, url)
        data.update(
            {
                "todo_list": str(self.the_list.pk),
                "title": "Secret new to-do",
                "subtasks-TOTAL_FORMS": "1",
                "subtasks-0-title": "Call the bank",
            }
        )
        self.assert_saved(self.client.post(url, data))
        return Todo.objects.get(title="Secret new to-do")

    def test_add_keeps_a_label(self):
        new = self.add_through_admin()
        entry = self.only_entry()
        self.assertEqual(entry.action_flag, ADDITION)
        self.assertEqual(entry.object_repr, f"todo {new.pk}")
        self.assertEqual(
            json.loads(entry.change_message),
            [
                {"added": {}},
                {"added": {"name": "subtask", "object": HIDDEN_NAME}},
            ],
        )

    def test_change_keeps_field_labels_only(self):
        url = reverse("admin:todos_todo_change", args=[self.todo.pk])
        data = admin_form(self.client, url)
        data["title"] = "Buy more secret milk"
        response = self.client.post(url, data)
        self.assert_saved(response)

        entry = self.only_entry()
        self.assertEqual(entry.action_flag, CHANGE)
        self.assertEqual(entry.object_repr, f"todo {self.todo.pk}")
        self.assertEqual(
            json.loads(entry.change_message), [{"changed": {"fields": ["Title"]}}]
        )

    def test_delete_keeps_a_label(self):
        url = reverse("admin:todos_todo_delete", args=[self.todo.pk])
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)

        entry = self.only_entry()
        self.assertEqual(entry.action_flag, DELETION)
        self.assertEqual(entry.object_repr, f"todo {self.todo.pk}")
        self.assertFalse(Todo.objects.filter(pk=self.todo.pk).exists())

    def test_delete_selected_keeps_labels(self):
        second = Todo.objects.create(todo_list=self.the_list, title="Secret second")
        response = self.client.post(
            reverse("admin:todos_todo_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [self.todo.pk, second.pk],
                "post": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)

        labels = set(
            LogEntry.objects.filter(action_flag=DELETION).values_list(
                "object_repr", flat=True
            )
        )
        self.assertEqual(labels, {f"todo {self.todo.pk}", f"todo {second.pk}"})
        self.assertEqual(LogEntry.objects.count(), 2)

    def test_list_change_keeps_no_name(self):
        url = reverse("admin:todos_todolist_change", args=[self.the_list.pk])
        data = admin_form(self.client, url)
        data["name"] = "Secret errands 2"
        response = self.client.post(url, data)
        self.assert_saved(response)

        entry = self.only_entry()
        self.assertEqual(entry.object_repr, f"todolist {self.the_list.pk}")
        self.assertEqual(
            json.loads(entry.change_message), [{"changed": {"fields": ["Name"]}}]
        )

    def test_deleting_a_user_keeps_no_username(self):
        url = reverse("admin:auth_user_delete", args=[self.carol.pk])
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)

        entry = self.only_entry()
        self.assertEqual(entry.action_flag, DELETION)
        self.assertEqual(entry.object_repr, f"user {self.carol.pk}")
        self.assertFalse(get_user_model().objects.filter(username="carol").exists())

    def test_recent_actions_show_the_label(self):
        new = self.add_through_admin()
        response = self.client.get(reverse("admin:index"))

        # Only the box: the admin's own success message above it names the
        # to-do once (accepted, see the data inventory, section 3).
        box = response.content.decode().split('id="recent-actions-module"')[1]
        change_url = reverse("admin:todos_todo_change", args=[new.pk])
        self.assertIn(f'<a href="{change_url}">todo {new.pk}</a>', box)
        self.assertNotIn("Secret new to-do", box)

    def fake_request(self):
        request = RequestFactory().get("/admin/")
        request.user = self.staffer
        return request

    def test_every_admin_hides_names(self):
        registered = {model.__name__ for model in admin.site._registry}
        self.assertTrue({"TodoList", "Todo", "User", "Group"} <= registered)
        for model, model_admin in admin.site._registry.items():
            with self.subTest(model=model.__name__):
                kind = type(model_admin)
                self.assertIs(kind.log_addition, NoNamesInLog.log_addition)
                self.assertIs(kind.log_change, NoNamesInLog.log_change)
                self.assertIs(kind.log_deletions, NoNamesInLog.log_deletions)
                self.assertIs(kind.log_deletion, ModelAdmin.log_deletion)

    def test_rows_match_djangos_own_except_names(self):
        message = [{"changed": {"fields": ["Title"]}}]
        djangos = LogEntry.objects.log_actions(
            user_id=self.staffer.pk,
            queryset=[self.todo],
            action_flag=CHANGE,
            change_message=message,
            single_object=True,
        )
        ours = admin.site.get_model_admin(Todo).log_change(
            self.fake_request(), self.todo, message
        )
        skip = {"id", "action_time", "object_repr", "change_message"}
        fields = [f.attname for f in LogEntry._meta.concrete_fields]
        self.assertIn("object_repr", fields)
        for field in fields:
            if field in skip:
                continue
            with self.subTest(field=field):
                self.assertEqual(getattr(ours, field), getattr(djangos, field))
        self.assertEqual(ours.object_repr, f"todo {self.todo.pk}")
        # Django's own row holds the title; remove it so tearDown's check
        # only looks at the rows the admin made.
        djangos.delete()

    def test_normal_user_cannot_open_the_admin(self):
        admin.site.get_model_admin(Todo).log_change(self.fake_request(), self.todo, [])
        alice = make_user("alice")
        login_url = reverse("admin:login")
        signed_in = Client()
        signed_in.force_login(alice)
        for name, client in [("alice", signed_in), ("visitor", Client())]:
            with self.subTest(who=name):
                response = client.get(reverse("admin:index"))
                self.assertRedirects(
                    response, f"{login_url}?next=/admin/", fetch_redirect_response=False
                )
                page = client.get(login_url)
                self.assertNotContains(page, f"todo {self.todo.pk}")
