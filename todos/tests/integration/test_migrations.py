"""Tests for the data migrations: old to-dos get an owner, then a list.

These tests move the database back to an old migration and forward again.
They only use the models as they were at that migration ("historical models"),
never `todos.models`, so they keep working when later features change the models.
If the migrations are renumbered, change the names below.

One exception: FillPositionMigrationTests does not migrate the database. It calls
the function of 0016_fill_todo_position directly on today's tables.
"""

import contextlib
import datetime
import importlib
import io
import json
import unicodedata

import django.apps
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo

BEFORE = [("todos", "0002_todo_owner")]
DATA_MIGRATION = [("todos", "0003_give_old_todos_an_owner")]
AFTER = [("todos", "0004_alter_todo_owner")]
LISTS_AFTER = [("todos", "0007_todo_list_required")]
# The list name key (list-name-casefold): before it, the new field, the fill.
BEFORE_NAME_KEY = [("todos", "0018_todo_ordering_tiebreak")]
NAME_KEY_FIELD = [("todos", "0019_todolist_name_key")]
# The admin log without names (admin-log-without-names): the moment before it.
BEFORE_ADMIN_LOG = [
    ("todos", "0022_todo_copy_fingerprint"),
    ("admin", "0003_logentry_add_action_flag_choices"),
    ("contenttypes", "0002_remove_content_type_name"),
]


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


def frozen_casefold(text):
    """The key the migration must give: NFC, then str.casefold()."""
    return unicodedata.normalize("NFC", text).casefold()


class FillListNameKeyMigrationTests(TransactionTestCase):
    """The list name key: filled for every list, duplicates renamed."""

    def tearDown(self):
        migrate_to_newest()

    def make_lists(self, apps, owner, names):
        """Make lists in this order, each a minute after the one before."""
        TodoList = apps.get_model("todos", "TodoList")
        start = timezone.now()
        made = []
        for minutes, name in enumerate(names):
            the_list = TodoList.objects.create(owner=owner, name=name)
            TodoList.objects.filter(pk=the_list.pk).update(
                created_at=start + datetime.timedelta(minutes=minutes)
            )
            made.append(the_list)
        return made

    def migrate_to_newest_quietly(self):
        """Migrate to the newest, and return what the migration printed."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            migrate_to_newest()
        return printed.getvalue()

    def newest_lists(self):
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(executor.loader.graph.leaf_nodes()).apps
        return apps.get_model("todos", "TodoList")

    def test_fill_sets_every_key(self):
        apps = migrate(NAME_KEY_FIELD)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        ana = User.objects.create(username="ana")
        names = ["Inbox", "ÆREND", "Stra\u00dfe", "A\u030aker"]
        self.make_lists(apps, ana, names)

        self.assertEqual(self.migrate_to_newest_quietly(), "")

        TodoList = self.newest_lists()
        keys = dict(TodoList.objects.values_list("name", "name_key"))
        self.assertEqual(keys, {name: frozen_casefold(name) for name in names})
        self.assertEqual(keys["A\u030aker"], "\u00e5ker")

    def test_duplicates_are_renamed(self):
        apps = migrate(NAME_KEY_FIELD)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        Todo = apps.get_model("todos", "Todo")
        ana = User.objects.create(username="ana")
        ben = User.objects.create(username="ben")
        # The old A-to-Z rule allows all four. "ærø (2)" is the newest, so a
        # free number must be checked against all the owner's keys, not only
        # the ones seen so far.
        first, dup, dup2, two = self.make_lists(
            apps, ana, ["Ærø", "ærø", "ÆrØ", "ærø (2)"]
        )
        (bens,) = self.make_lists(apps, ben, ["ærø"])
        todo = Todo.objects.create(todo_list=dup, title="Milk")

        printed = self.migrate_to_newest_quietly()

        TodoList = self.newest_lists()
        names = dict(TodoList.objects.values_list("pk", "name"))
        self.assertEqual(
            names,
            {
                first.pk: "Ærø",
                two.pk: "ærø (2)",
                dup.pk: "ærø (3)",
                dup2.pk: "ÆrØ (4)",
                bens.pk: "ærø",
            },
        )
        Todo = apps.get_model("todos", "Todo")
        self.assertEqual(Todo.objects.get(pk=todo.pk).todo_list_id, dup.pk)
        self.assertEqual(
            printed.splitlines(),
            [
                f"Renamed list {dup.pk} to “ærø (3)”.",
                f"Renamed list {dup2.pk} to “ÆrØ (4)”.",
            ],
        )

    def test_long_duplicate_name_is_cut(self):
        apps = migrate(NAME_KEY_FIELD)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        ana = User.objects.create(username="ana")
        # Æ and æ: the old A-to-Z rule allows both.
        spaced = "æ" * 95 + " bbbb"
        _, long_dup, _, spaced_dup = self.make_lists(
            apps, ana, ["æ" * 100, "Æ" * 100, spaced, spaced.upper()]
        )

        self.migrate_to_newest_quietly()

        TodoList = self.newest_lists()
        long_name = TodoList.objects.get(pk=long_dup.pk).name
        self.assertEqual(long_name, "Æ" * 96 + " (2)")
        self.assertEqual(len(long_name), 100)
        self.assertEqual(TodoList.objects.get(pk=spaced_dup.pk).name, "Æ" * 95 + " (2)")

    def test_migration_goes_back(self):
        apps = migrate(BEFORE_NAME_KEY)
        TodoList = apps.get_model("todos", "TodoList")
        User = apps.get_model(settings.AUTH_USER_MODEL)
        ana = User.objects.create(username="ana")
        self.assertNotIn("name_key", [f.name for f in TodoList._meta.get_fields()])
        TodoList.objects.create(owner=ana, name="Work")
        # The old rule (A to Z) is back.
        with self.assertRaises(IntegrityError), transaction.atomic():
            TodoList.objects.create(owner=ana, name="work")


class BlankAdminLogNamesMigrationTests(TransactionTestCase):
    """0023: the names in the admin log become labels like "todo 42"."""

    COLUMNS = [
        "pk",
        "action_time",
        "user_id",
        "action_flag",
        "object_id",
        "content_type_id",
    ]

    def tearDown(self):
        migrate_to_newest()

    def make_rows(self):
        """Log rows as the old admin wrote them, with names. Returns them by kind."""
        apps = migrate(BEFORE_ADMIN_LOG)
        User = apps.get_model(settings.AUTH_USER_MODEL)
        ContentType = apps.get_model("contenttypes", "ContentType")
        LogEntry = apps.get_model("admin", "LogEntry")
        staffer = User.objects.create(username="staffer", is_staff=True)
        todo_type = ContentType.objects.get_or_create(app_label="todos", model="todo")[
            0
        ]
        user_type = ContentType.objects.get_or_create(app_label="auth", model="user")[0]

        def row(**fields):
            return LogEntry.objects.create(user=staffer, **fields)

        self.rows = {
            "added": row(
                content_type=todo_type,
                object_id="7",
                object_repr="Buy secret milk",
                action_flag=1,
                change_message='[{"added": {}}]',
            ),
            "changed": row(
                content_type=todo_type,
                object_id="7",
                object_repr="Buy secret milk",
                action_flag=2,
                change_message=json.dumps(
                    [
                        {"changed": {"fields": ["Title"]}},
                        {"added": {"name": "subtask", "object": "Call the bank"}},
                    ]
                ),
            ),
            "user": row(
                content_type=user_type,
                object_id="3",
                object_repr="carol",
                action_flag=3,
                change_message="",
            ),
            "no_type": row(
                content_type=None,
                object_id="9",
                object_repr="Secret thing",
                action_flag=3,
                change_message="",
            ),
            "plain": row(
                content_type=todo_type,
                object_id="8",
                object_repr="Secret plan",
                action_flag=2,
                change_message="Changed title to Secret.",
            ),
        }
        return LogEntry

    def newest_log(self):
        executor = MigrationExecutor(connection)
        apps = executor.loader.project_state(executor.loader.graph.leaf_nodes()).apps
        return apps.get_model("admin", "LogEntry")

    def assert_no_names(self, LogEntry):
        for repr_, message in LogEntry.objects.values_list(
            "object_repr", "change_message"
        ):
            for text in (repr_, message):
                for name in ("secret", "carol", "call the bank"):
                    self.assertNotIn(name, text.lower())

    def test_names_are_replaced(self):
        self.make_rows()

        migrate_to_newest()

        LogEntry = self.newest_log()
        got = {kind: LogEntry.objects.get(pk=row.pk) for kind, row in self.rows.items()}
        self.assertEqual(got["added"].object_repr, "todo 7")
        self.assertEqual(json.loads(got["added"].change_message), [{"added": {}}])
        self.assertEqual(got["changed"].object_repr, "todo 7")
        self.assertEqual(
            json.loads(got["changed"].change_message),
            [
                {"changed": {"fields": ["Title"]}},
                {"added": {"name": "subtask", "object": "name not kept"}},
            ],
        )
        self.assertEqual(got["user"].object_repr, "user 3")
        self.assertEqual(got["no_type"].object_repr, "object 9")
        self.assertEqual(got["plain"].object_repr, "todo 8")
        self.assertEqual(got["plain"].change_message, "")
        self.assert_no_names(LogEntry)

    def test_other_columns_do_not_change(self):
        LogEntry = self.make_rows()
        before = list(LogEntry.objects.order_by("pk").values_list(*self.COLUMNS))

        migrate_to_newest()

        after = list(
            self.newest_log().objects.order_by("pk").values_list(*self.COLUMNS)
        )
        self.assertEqual(after, before)

    def test_migration_goes_back(self):
        self.make_rows()
        migrate_to_newest()

        LogEntry = migrate(BEFORE_ADMIN_LOG).get_model("admin", "LogEntry")
        labels = dict(LogEntry.objects.values_list("pk", "object_repr"))
        self.assertEqual(labels[self.rows["user"].pk], "user 3")
        self.assert_no_names(LogEntry)

        # Forward again: running it on rows with labels changes nothing.
        migrate_to_newest()
        LogEntry = self.newest_log()
        self.assertEqual(
            dict(LogEntry.objects.values_list("pk", "object_repr")), labels
        )
