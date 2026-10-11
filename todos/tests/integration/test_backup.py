"""Tests for the database backup: `todos/backup.py` and `manage.py backup_db`.

Every test makes its own temporary folder with a small SQLite file (one table,
two rows), and always passes that source and folder. No test ever reads the
person's db.sqlite3 or writes to the real backups/ folder.
"""

import io
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase

from todos.backup import backup_database

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


class MakeResetTests(SimpleTestCase):
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
