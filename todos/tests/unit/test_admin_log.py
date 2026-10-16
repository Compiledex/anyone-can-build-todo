"""The admin log without names: the label and the change message (no database)."""

import copy
import importlib
import json
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase

from todos.admin_log import HIDDEN_NAME, hide_names, log_label
from todos.models import Todo, TodoList

# The file name starts with a number, so a normal import cannot load it.
migration = importlib.import_module("todos.migrations.0023_blank_admin_log_names")

INLINE = [
    {"added": {"name": "subtask", "object": "Call the bank"}},
    {"changed": {"name": "subtask", "object": "Pay", "fields": ["Title"]}},
    {"deleted": {"name": "subtask", "object": "Old"}},
]
INLINE_HIDDEN = [
    {"added": {"name": "subtask", "object": HIDDEN_NAME}},
    {"changed": {"name": "subtask", "object": HIDDEN_NAME, "fields": ["Title"]}},
    {"deleted": {"name": "subtask", "object": HIDDEN_NAME}},
]
NOTHING_TO_HIDE = [
    [{"added": {}}],
    [{"changed": {"fields": ["Title", "Due date"]}}],
]
PLAIN_TEXT = ["Changed title to Secret.", "[not json", '{"a": 1}']


class HideNamesTests(SimpleTestCase):
    def test_inline_names_are_hidden(self):
        self.assertEqual(json.loads(hide_names(INLINE)), INLINE_HIDDEN)
        self.assertEqual(json.loads(hide_names(json.dumps(INLINE))), INLINE_HIDDEN)

    def test_field_labels_stay(self):
        for message in NOTHING_TO_HIDE:
            with self.subTest(message=message):
                self.assertEqual(json.loads(hide_names(message)), message)
                self.assertEqual(json.loads(hide_names(json.dumps(message))), message)

    def test_plain_text_becomes_empty(self):
        for message in PLAIN_TEXT:
            with self.subTest(message=message):
                self.assertEqual(hide_names(message), "")
        self.assertEqual(hide_names(""), "")

    def test_input_is_not_changed(self):
        given = copy.deepcopy(INLINE)
        hide_names(given)
        self.assertEqual(given, INLINE)


class LogLabelTests(SimpleTestCase):
    def test_label_is_model_and_id(self):
        self.assertEqual(log_label(Todo(pk=42)), "todo 42")
        self.assertEqual(log_label(TodoList(pk=3)), "todolist 3")
        carol = User(pk=2, username="carol")
        self.assertEqual(log_label(carol), "user 2")
        self.assertNotIn("carol", log_label(carol))

    def test_migration_label_is_the_same(self):
        for obj in [Todo(pk=42), TodoList(pk=3), User(pk=2, username="carol")]:
            with self.subTest(obj=type(obj).__name__):
                row = SimpleNamespace(
                    content_type=SimpleNamespace(model=obj._meta.model_name),
                    object_id=str(obj.pk),
                )
                self.assertEqual(migration.frozen_label(row), log_label(obj))
        no_type = SimpleNamespace(content_type=None, object_id="9")
        self.assertEqual(migration.frozen_label(no_type), "object 9")

        for message in [INLINE, *NOTHING_TO_HIDE, *PLAIN_TEXT, ""]:
            with self.subTest(message=message):
                text = message if isinstance(message, str) else json.dumps(message)
                self.assertEqual(migration.frozen_hide_names(text), hide_names(message))
