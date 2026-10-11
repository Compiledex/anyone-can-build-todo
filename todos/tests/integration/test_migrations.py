"""Tests for the data migrations: old to-dos get an owner, then a list.

These tests move the database back to an old migration and forward again.
They only use the models as they were at that migration ("historical models"),
never `todos.models`, so they keep working when later features change the models.
If the migrations are renumbered, change the names below.

One exception: FillPositionMigrationTests does not migrate the database. It calls
the function of 0016_fill_todo_position directly on today's tables.
"""

import datetime
import importlib

import django.apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo

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
        call = Todo.objects.create(title="Call home", owner=ben)

        apps = migrate(LISTS_AFTER)
        TodoList = apps.get_model("todos", "TodoList")
        Todo = apps.get_model("todos", "Todo")
        for user in [ana, ben]:
            names = list(
                TodoList.objects.filter(owner_id=user.pk).values_list("name", flat=True)
            )
            self.assertEqual(names, ["Inbox"])
        for todo, user in [(milk, ana), (call, ben)]:
            inbox = TodoList.objects.get(owner_id=user.pk)
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


class FillPositionMigrationTests(LoggedInTestCase):
    def test_fill_migration_numbers_each_list(self):
        # The file name starts with a number, so a normal import cannot load it.
        migration = importlib.import_module("todos.migrations.0016_fill_todo_position")
        now = timezone.now()
        lists = {"alice": self.todo_list, "bob": self.other_list}
        for the_list in lists.values():
            # Made in the order C, B, A, but A is the oldest (created_at).
            for minutes_ago, title in [(1, "C"), (2, "B"), (3, "A")]:
                todo = Todo.objects.create(todo_list=the_list, title=title)
                Todo.objects.filter(pk=todo.pk).update(
                    created_at=now - datetime.timedelta(minutes=minutes_ago),
                    position=0,
                )

        migration.fill_position(django.apps.apps, None)

        for owner, the_list in lists.items():
            with self.subTest(owner=owner):
                numbered = list(
                    the_list.todos.order_by("position").values_list("title", "position")
                )
                self.assertEqual(numbered, [("A", 1), ("B", 2), ("C", 3)])
