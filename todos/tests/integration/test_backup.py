"""Tests for the database backup: `todos/backup.py` and `manage.py backup_db`.

Every test makes its own temporary folder with a small SQLite file (one table,
two rows), and always passes that source and folder. No test ever reads the
person's db.sqlite3 or writes to the real backups/ folder.
"""

import io
import os
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from todos.backup import backup_database, copy_sqlite

NOW = datetime(2026, 10, 11, 8, 15, 0)
NAME = "db-20261011-081500.sqlite3"


class BackupTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.source = self.tmp / "db.sqlite3"
        self.folder = self.tmp / "backups"
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE todo (title TEXT)")
            db.executemany("INSERT INTO todo VALUES (?)", [("Milk",), ("Bread",)])
        db.close()

    def rows(self, path):
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            check = db.execute("PRAGMA integrity_check").fetchone()[0]
            titles = [row[0] for row in db.execute("SELECT title FROM todo")]
        finally:
            db.close()
        return check, titles

    def files_in_folder(self):
        return sorted(path.name for path in self.folder.iterdir())

    def test_backup_copies_the_rows(self):
        self.folder.mkdir()
        target = backup_database(self.source, self.folder, NOW)
        self.assertEqual(target, self.folder / NAME)
        self.assertEqual(self.rows(target), ("ok", ["Milk", "Bread"]))
        self.assertEqual(self.files_in_folder(), [NAME])

    def test_backup_makes_the_folder(self):
        folder = self.folder / "inner"
        self.assertFalse(folder.exists())
        target = backup_database(self.source, folder, NOW)
        self.assertTrue(target.is_file())

    def test_missing_source_makes_nothing(self):
        missing = self.tmp / "nothing.sqlite3"
        self.assertIsNone(backup_database(missing, self.folder, NOW))
        self.assertFalse(missing.exists())
        self.assertFalse(self.folder.exists() and any(self.folder.iterdir()))

    def test_never_overwrites(self):
        self.folder.mkdir()
        older = self.folder / NAME
        older.write_bytes(b"an older backup")
        with self.assertRaises(FileExistsError):
            backup_database(self.source, self.folder, NOW)
        self.assertEqual(older.read_bytes(), b"an older backup")
        self.assertEqual(self.files_in_folder(), [NAME])

    def test_failed_copy_leaves_no_file(self):
        self.folder.mkdir()
        with (
            mock.patch(
                "todos.backup.copy_sqlite", side_effect=sqlite3.OperationalError("full")
            ),
            self.assertRaises(sqlite3.OperationalError),
        ):
            backup_database(self.source, self.folder, NOW)
        self.assertEqual(self.files_in_folder(), [])

    def test_copy_opens_the_source_read_only(self):
        # Read-write would make an empty database file at the missing path.
        missing = self.tmp / "missing.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            copy_sqlite(missing, self.tmp / "out")
        self.assertFalse(missing.exists())

    def test_source_in_a_folder_with_special_letters(self):
        # "#" and "?" end the path in a URI unless it is quoted.
        folder = self.tmp / "a #?b æ"
        folder.mkdir()
        source = folder / "db.sqlite3"
        shutil.copy(self.source, source)
        target = backup_database(source, self.folder, NOW)
        self.assertEqual(self.rows(target), ("ok", ["Milk", "Bread"]))

    def test_copy_goes_to_a_temporary_name_first(self):
        self.folder.mkdir()
        targets = []

        def half_copy(source, target):
            targets.append(Path(target))
            Path(target).write_bytes(b"half a database")
            raise sqlite3.OperationalError("disk full")

        with (
            mock.patch("todos.backup.copy_sqlite", side_effect=half_copy),
            self.assertRaises(sqlite3.OperationalError),
        ):
            backup_database(self.source, self.folder, NOW)
        self.assertEqual(len(targets), 1)
        self.assertTrue(targets[0].name.endswith(".tmp"))
        self.assertNotEqual(targets[0].name, NAME)
        self.assertEqual(self.files_in_folder(), [])

    def test_backup_only_the_owner_can_read(self):
        target = backup_database(self.source, self.folder, NOW)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_source_is_not_changed(self):
        before = self.source.read_bytes()
        backup_database(self.source, self.folder, NOW)
        self.assertEqual(self.source.read_bytes(), before)

    def test_command_prints_where_the_copy_is(self):
        out = io.StringIO()
        call_command(
            "backup_db", source=str(self.source), folder=str(self.folder), stdout=out
        )
        self.assertIn("Saved a copy in", out.getvalue())
        self.assertEqual(len(self.files_in_folder()), 1)
        self.assertIn(self.files_in_folder()[0], out.getvalue())

        out = io.StringIO()
        call_command(
            "backup_db",
            source=str(self.tmp / "nothing.sqlite3"),
            folder=str(self.folder),
            stdout=out,
        )
        self.assertIn("No database yet", out.getvalue())
        self.assertEqual(len(self.files_in_folder()), 1)

    def test_command_names_the_copy_with_the_local_time(self):
        # 23:15 UTC is 08:15 the next day in Tokyo (settings.TIME_ZONE).
        local = datetime(2026, 10, 10, 23, 15, 0, tzinfo=UTC)
        with mock.patch(
            "todos.management.commands.backup_db.timezone.now", return_value=local
        ):
            call_command(
                "backup_db",
                source=str(self.source),
                folder=str(self.folder),
                stdout=io.StringIO(),
            )
            self.assertEqual(self.files_in_folder(), [NAME])
            with self.assertRaisesMessage(CommandError, "already exists"):
                call_command(
                    "backup_db",
                    source=str(self.source),
                    folder=str(self.folder),
                    stdout=io.StringIO(),
                )
        self.assertEqual(self.files_in_folder(), [NAME])


# A stand-in for `uv`: it writes its arguments to $UV_LOG, and for backup_db
# also whether db.sqlite3 is still there. FAKE_BACKUP_EXIT=1 makes the copy fail.
FAKE_UV = """#!/bin/sh
echo "$*" >> "$UV_LOG"
case "$*" in
  *backup_db*)
    if [ -f db.sqlite3 ]; then echo "db still there" >> "$UV_LOG"; fi
    exit "${FAKE_BACKUP_EXIT:-0}";;
esac
exit 0
"""


class MakeResetTests(SimpleTestCase):
    """`make reset` for real, in a temporary folder, with a fake `uv`.

    Only a copy of the Makefile and a dummy db.sqlite3 are in the folder, and
    the fake `uv` runs nothing, so the person's database is never near it.
    """

    def setUp(self):
        self.make = shutil.which("make")
        if self.make is None:
            self.skipTest("make is not installed")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copy(Path(settings.BASE_DIR) / "Makefile", self.tmp / "Makefile")
        self.db = self.tmp / "db.sqlite3"
        self.db.write_bytes(b"the person's data")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        uv = bin_dir / "uv"
        uv.write_text(FAKE_UV)
        uv.chmod(0o755)
        self.log = self.tmp / "uv.log"
        self.env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")
        }
        self.env["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        self.env["UV_LOG"] = str(self.log)

    def reset(self, answer, *args, backup_fails=False):
        env = dict(self.env)
        if backup_fails:
            env["FAKE_BACKUP_EXIT"] = "1"
        return subprocess.run(
            [self.make, "reset", *args],
            cwd=self.tmp,
            env=env,
            input=answer,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def logged(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_anything_but_yes_deletes_nothing(self):
        for answer in ["", "\n", "no\n", "y\n", "YES\n"]:
            with self.subTest(answer=answer):
                result = self.reset(answer)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Nothing was deleted.", result.stdout)
                self.assertEqual(self.db.read_bytes(), b"the person's data")
                self.assertEqual(self.logged(), [])

    def test_yes_copies_then_deletes(self):
        for args, answer in [((), "yes\n"), (("CONFIRM=yes",), "")]:
            with self.subTest(args=args):
                self.db.write_bytes(b"the person's data")
                self.log.unlink(missing_ok=True)
                result = self.reset(answer, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    self.logged(),
                    [
                        "run python manage.py backup_db",
                        "db still there",
                        "run python manage.py migrate",
                    ],
                )
                self.assertFalse(self.db.exists())

    def test_failed_copy_deletes_nothing(self):
        for args, answer in [((), "yes\n"), (("CONFIRM=yes",), "")]:
            with self.subTest(args=args):
                result = self.reset(answer, *args, backup_fails=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.db.read_bytes(), b"the person's data")
                self.assertNotIn("run python manage.py migrate", self.logged())

    def test_no_database_only_migrates(self):
        self.db.unlink()
        result = self.reset("")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.logged(), ["run python manage.py migrate"])


class MakeResetRecipeTests(SimpleTestCase):
    def test_make_reset_copies_before_deleting(self):
        make = shutil.which("make")
        if make is None:
            self.skipTest("make is not installed")
        # -n is a dry run: make only prints the commands, it runs none of them.
        result = subprocess.run(
            [make, "-n", "reset", "CONFIRM=yes"],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        recipe = result.stdout
        self.assertIn("read answer", recipe)
        self.assertIn("backup_db", recipe)
        self.assertIn("rm -f db.sqlite3", recipe)
        self.assertLess(recipe.index("backup_db"), recipe.index("rm -f db.sqlite3"))
