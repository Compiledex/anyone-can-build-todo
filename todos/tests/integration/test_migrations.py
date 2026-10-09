"""Tests for the data migration that gives old to-dos an owner.

These tests move the database back to an old migration and forward again.
They only use the models as they were at that migration ("historical models"),
never `todos.models`, so they keep working when later features change the models.
If the migrations are renumbered, change the names below.
"""

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("todos", "0002_todo_owner")]
DATA_MIGRATION = [("todos", "0003_give_old_todos_an_owner")]
AFTER = [("todos", "0004_alter_todo_owner")]


def migrate(targets):
    """Move the database to these migrations, and return the models of that moment."""
    # A new executor each time: it reads which migrations are applied now.
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class GiveOldTodosAnOwnerTests(TransactionTestCase):
    def tearDown(self):
        # Back to the newest migrations, so the other tests get the newest tables.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_old_todos_go_to_the_oldest_superuser(self):
        apps = migrate(BEFORE)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        Todo = apps.get_model("todos", "Todo")
        first = User.objects.create(username="first", is_superuser=True)
        User.objects.create(username="second", is_superuser=True)
        todo = Todo.objects.create(title="Old to-do")

        apps = migrate(AFTER)
        Todo = apps.get_model("todos", "Todo")
        self.assertEqual(Todo.objects.get(pk=todo.pk).owner_id, first.pk)

    def test_old_todos_without_a_superuser_stop_the_migration(self):
        apps = migrate(BEFORE)
        Todo = apps.get_model("todos", "Todo")
        todo = Todo.objects.create(title="Old to-do")

        with self.assertRaisesMessage(RuntimeError, "createsuperuser"):
            migrate(DATA_MIGRATION)

        # Otherwise tearDown runs 0003 again, and it stops again.
        Todo.objects.filter(pk=todo.pk).delete()
