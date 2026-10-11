from django.test import SimpleTestCase

from todos.models import Todo
from todos.undo import SNAPSHOT_FIELDS


class SnapshotFieldsTests(SimpleTestCase):
    def test_snapshot_fields_are_every_todo_field(self):
        # A new Todo field must be added to SNAPSHOT_FIELDS, or Undo would lose it.
        self.assertEqual(
            set(SNAPSHOT_FIELDS),
            {field.attname for field in Todo._meta.concrete_fields},
        )
        self.assertEqual(len(SNAPSHOT_FIELDS), len(set(SNAPSHOT_FIELDS)))
