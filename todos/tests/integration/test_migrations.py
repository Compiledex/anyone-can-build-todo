"""Tests for the data migrations: old to-dos get an owner, then a list.

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
LISTS_AFTER = [("todos", "0007_todo_list_required")]


def migrate_to_newest():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def migrate(targets):
    """Move the database to these migrations, and return the models of that moment."""
    # A new executor each time: it reads which migrations are applied now.
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


class GiveOldTodosAnOwnerTests(TransactionTestCase):
    def tearDown(self):
        # Back to the newest migrations, so the other tests get the newest tables.
        migrate_to_newest()

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


class DefaultListsTests(TransactionTestCase):
    """0005-0007: every user gets an "Inbox" list, and their to-dos go in it."""

    def tearDown(self):
        migrate_to_newest()

    def test_migration_gives_each_user_a_list(self):
        apps = migrate(AFTER)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        Todo = apps.get_model("todos", "Todo")
        ana = User.objects.create(username="ana")
        ben = User.objects.create(username="ben")
        milk = Todo.objects.create(title="Buy milk", owner=ana)
        call = Todo.objects.create(title="Call home", owner=ana)

        apps = migrate(LISTS_AFTER)
        TodoList = apps.get_model("todos", "TodoList")
        Todo = apps.get_model("todos", "Todo")
        for user in [ana, ben]:
            names = list(
                TodoList.objects.filter(owner_id=user.pk).values_list("name", flat=True)
            )
            self.assertEqual(names, ["Inbox"])
        inbox = TodoList.objects.get(owner_id=ana.pk)
        for todo in [milk, call]:
            self.assertEqual(Todo.objects.get(pk=todo.pk).todo_list_id, inbox.pk)

    def test_migration_back_gives_todos_their_owner(self):
        apps = migrate(LISTS_AFTER)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        TodoList = apps.get_model("todos", "TodoList")
        Todo = apps.get_model("todos", "Todo")
        ana = User.objects.create(username="ana")
        ben = User.objects.create(username="ben")
        ana_list = TodoList.objects.create(owner=ana, name="Work")
        ben_list = TodoList.objects.create(owner=ben, name="Home")
        milk = Todo.objects.create(title="Buy milk", todo_list=ana_list)
        call = Todo.objects.create(title="Call home", todo_list=ben_list)

        apps = migrate(AFTER)
        Todo = apps.get_model("todos", "Todo")
        self.assertEqual(Todo.objects.get(pk=milk.pk).owner_id, ana.pk)
        self.assertEqual(Todo.objects.get(pk=call.pk).owner_id, ben.pk)
