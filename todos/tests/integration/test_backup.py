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
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from todos.backup import backup_database, copy_sqlite, daily_backup, daily_copies

NOW = datetime(2026, 10, 11, 8, 15, 0)
NAME = "db-20261011-081500.sqlite3"


class TempDatabaseTestCase(SimpleTestCase):
    """A temporary folder with a small SQLite file, `db.sqlite3`, in it."""

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


class BackupTests(TempDatabaseTestCase):
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


DAILY_NAME = "db-20261011-081500-daily.sqlite3"
# NOW in UTC: 23:15 UTC is 08:15 the next day in Tokyo (settings.TIME_ZONE).
NOW_UTC = datetime(2026, 10, 10, 23, 15, 0, tzinfo=UTC)


def daily_name(day):
    return f"db-{day:%Y%m%d}-120000-daily.sqlite3"


class DailyBackupTests(TempDatabaseTestCase):
    """`daily_backup` and `backup_db --daily`: the copy `make run` makes."""

    def setUp(self):
        super().setUp()
        self.folder.mkdir()

    def make_old_daily_copies(self, first_day, count=20):
        """`count` empty daily copies, one a day from `first_day`; their names."""
        names = [daily_name(first_day + timedelta(days=n)) for n in range(count)]
        for name in names:
            (self.folder / name).write_bytes(b"")
        return names

    def daily(self, source=None, now=NOW_UTC):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch(
            "todos.management.commands.backup_db.timezone.now", return_value=now
        ):
            call_command(
                "backup_db",
                "--daily",
                source=str(source or self.source),
                folder=str(self.folder),
                stdout=out,
                stderr=err,
            )
        return out.getvalue(), err.getvalue()

    def test_first_run_makes_a_daily_copy(self):
        created, removed = daily_backup(self.source, self.folder, NOW)
        self.assertEqual(created, self.folder / DAILY_NAME)
        self.assertEqual(removed, [])
        self.assertEqual(self.rows(created), ("ok", ["Milk", "Bread"]))
        self.assertEqual(self.files_in_folder(), [DAILY_NAME])

    def test_second_run_the_same_day_makes_nothing(self):
        daily_backup(self.source, self.folder, NOW)
        later = datetime(2026, 10, 11, 23, 59, 59)
        self.assertEqual(daily_backup(self.source, self.folder, later), (None, []))
        self.assertEqual(self.files_in_folder(), [DAILY_NAME])

    def test_next_day_makes_a_new_copy(self):
        daily_backup(self.source, self.folder, NOW)
        next_day = datetime(2026, 10, 12, 0, 0, 1)
        created, _ = daily_backup(self.source, self.folder, next_day)
        self.assertEqual(created.name, "db-20261012-000001-daily.sqlite3")
        self.assertEqual(
            self.files_in_folder(), [DAILY_NAME, "db-20261012-000001-daily.sqlite3"]
        )

    def test_the_day_is_the_tokyo_day(self):
        # 15:30 UTC on the 11th is 00:30 on the 12th in Tokyo (settings.TIME_ZONE).
        self.daily(now=datetime(2026, 10, 11, 15, 30, 0, tzinfo=UTC))
        self.assertEqual(self.files_in_folder(), ["db-20261012-003000-daily.sqlite3"])

    def test_manual_copy_does_not_count_as_daily(self):
        (self.folder / "db-20261011-070000.sqlite3").write_bytes(b"manual")
        created, _ = daily_backup(self.source, self.folder, NOW)
        self.assertEqual(created, self.folder / DAILY_NAME)
        self.assertEqual(
            self.files_in_folder(), ["db-20261011-070000.sqlite3", DAILY_NAME]
        )

    def test_keeps_the_newest_fourteen(self):
        # 21 Sep to 10 Oct: twenty days before today, the 11th.
        old = self.make_old_daily_copies(date(2026, 9, 21))
        created, removed = daily_backup(self.source, self.folder, NOW)
        self.assertEqual([path.name for path in removed], old[:7])
        self.assertEqual(self.files_in_folder(), [*old[7:], created.name])
        self.assertEqual(len(self.files_in_folder()), 14)

    def test_never_deletes_other_files(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        others = [
            "db-20200101-000000.sqlite3",
            ".db-20200101-000000-daily.sqlite3.tmp",
            "db-20200101-000000-daily.sqlite3.bak",
            "notes.txt",
        ]
        for name in others:
            (self.folder / name).write_bytes(b"keep me")
        (self.folder / "db-20200101-000001-daily.sqlite3").mkdir()
        outside = self.tmp / "outside.sqlite3"
        outside.write_bytes(b"not a backup")
        (self.folder / "db-20200101-000002-daily.sqlite3").symlink_to(outside)

        created, removed = daily_backup(self.source, self.folder, NOW)

        self.assertEqual([path.name for path in removed], old[:7])
        for name in others:
            self.assertEqual((self.folder / name).read_bytes(), b"keep me")
        self.assertTrue((self.folder / "db-20200101-000001-daily.sqlite3").is_dir())
        self.assertTrue((self.folder / "db-20200101-000002-daily.sqlite3").is_symlink())
        self.assertEqual(outside.read_bytes(), b"not a backup")
        self.assertEqual(
            [path.name for path in daily_copies(self.folder)],
            [*old[7:], created.name],
        )

    def test_failed_copy_prunes_nothing(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        with (
            mock.patch(
                "todos.backup.copy_sqlite", side_effect=sqlite3.OperationalError("full")
            ),
            self.assertRaises(sqlite3.OperationalError),
        ):
            daily_backup(self.source, self.folder, NOW)
        self.assertEqual(self.files_in_folder(), old)

    def test_no_database_makes_and_prunes_nothing(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        missing = self.tmp / "nothing.sqlite3"
        self.assertEqual(daily_backup(missing, self.folder, NOW), (None, []))
        self.assertEqual(self.files_in_folder(), old)
        out, _ = self.daily(source=missing)
        self.assertIn("No database yet: nothing to back up.", out)
        self.assertEqual(self.files_in_folder(), old)

    def test_same_second_counts_as_done(self):
        (self.folder / DAILY_NAME).write_bytes(b"made a moment ago")
        self.assertEqual(daily_backup(self.source, self.folder, NOW), (None, []))
        self.assertEqual(self.files_in_folder(), [DAILY_NAME])
        # Two runs at once: the other one made today's copy between our look
        # at the folder and our copy. The old copies are still pruned.
        (self.folder / DAILY_NAME).unlink()
        old = self.make_old_daily_copies(date(2026, 9, 21))

        def other_run_was_first(source, folder, now, suffix=""):
            (Path(folder) / DAILY_NAME).write_bytes(b"made by the other run")
            raise FileExistsError("taken")

        with mock.patch(
            "todos.backup.backup_database", side_effect=other_run_was_first
        ):
            created, removed = daily_backup(self.source, self.folder, NOW)
        self.assertIsNone(created)
        self.assertEqual([path.name for path in removed], old[:7])
        self.assertEqual(self.files_in_folder(), [*old[7:], DAILY_NAME])

    def test_prunes_when_todays_copy_is_already_there(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        todays = "db-20261011-060000-daily.sqlite3"
        future = "db-20270101-000000-daily.sqlite3"
        (self.folder / todays).write_bytes(b"made this morning")
        (self.folder / future).write_bytes(b"")
        created, removed = daily_backup(self.source, self.folder, NOW)
        self.assertIsNone(created)
        self.assertEqual([path.name for path in removed], old[:8])
        self.assertEqual(self.files_in_folder(), [*old[8:], todays, future])
        self.assertEqual((self.folder / todays).read_bytes(), b"made this morning")

    def test_folder_that_is_a_file_is_a_failed_copy(self):
        not_a_folder = self.tmp / "backups-file"
        not_a_folder.write_bytes(b"")
        with (
            mock.patch(
                "todos.management.commands.backup_db.timezone.now",
                return_value=NOW_UTC,
            ),
            self.assertRaisesMessage(CommandError, "Could not copy the database"),
        ):
            call_command(
                "backup_db",
                "--daily",
                source=str(self.source),
                folder=str(not_a_folder),
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )

    def test_something_else_with_todays_name_is_a_failed_copy(self):
        (self.folder / DAILY_NAME).mkdir()
        with self.assertRaisesMessage(CommandError, "Could not copy the database"):
            self.daily()
        outside = self.tmp / "outside.sqlite3"
        outside.write_bytes(b"not a backup")
        (self.folder / DAILY_NAME).rmdir()
        (self.folder / DAILY_NAME).symlink_to(outside)
        with self.assertRaisesMessage(CommandError, "Could not copy the database"):
            self.daily()
        self.assertEqual(outside.read_bytes(), b"not a backup")

    def test_failed_daily_copy_is_a_command_error(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        with (
            mock.patch(
                "todos.backup.copy_sqlite", side_effect=sqlite3.OperationalError("full")
            ),
            self.assertRaisesMessage(CommandError, "Could not copy the database: full"),
        ):
            self.daily()
        self.assertEqual(self.files_in_folder(), old)

    def test_todays_copy_is_never_pruned(self):
        # Names from the future (a wrong clock) sort after today's copy.
        future = self.make_old_daily_copies(date(2027, 1, 1))
        created, removed = daily_backup(self.source, self.folder, NOW)
        self.assertTrue(created.is_file())
        self.assertEqual([path.name for path in removed], future[:7])
        self.assertEqual(self.files_in_folder(), [created.name, *future[7:]])

    def test_prune_failure_after_a_good_copy_is_a_warning(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        real_unlink = Path.unlink

        def unlink(path, *args, **kwargs):
            if path.name == old[3]:
                raise PermissionError("not allowed")
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", unlink):
            out, err = self.daily()
        self.assertIn("Saved today's copy in", out)
        self.assertIn("Warning: could not remove an old daily copy", err)
        self.assertIn(old[3], err)
        self.assertIn("not allowed", err)
        # It stops at the failed one: the three before it are gone, the rest stay.
        self.assertEqual(self.files_in_folder(), [*old[3:], DAILY_NAME])

    def test_daily_name_must_match_whole(self):
        for name in [
            "db-20200101-000000-daily.sqlite3x",
            "xdb-20200101-000000-daily.sqlite3",
            "db-20200101-000000-daily.sqlite3.tmp",
            "db-2020010-000000-daily.sqlite3",
            # Arabic-Indic digits: \d would match them, [0-9] does not.
            "db-\u0662\u0660\u0662\u0660\u0660\u0661\u0660\u0661-000000-daily.sqlite3",
        ]:
            (self.folder / name).write_bytes(b"")
        (self.folder / "db-20200101-000000-daily.sqlite3").write_bytes(b"")
        self.assertEqual(
            [path.name for path in daily_copies(self.folder)],
            ["db-20200101-000000-daily.sqlite3"],
        )

    def test_daily_command_prints_one_line(self):
        out, err = self.daily()
        self.assertIn(f"Saved today's copy in {self.folder / DAILY_NAME}.", out)
        self.assertNotIn("Removed", out)
        self.assertEqual(err, "")

        out, err = self.daily()
        self.assertIn("Today's copy is already in", out)
        self.assertNotIn("Removed", out)

        for path in self.folder.iterdir():
            path.unlink()
        self.make_old_daily_copies(date(2026, 1, 1), count=14)
        out, _ = self.daily()
        self.assertIn("Saved today's copy in", out)
        self.assertIn("Removed 1 old daily copy.", out)

        for path in self.folder.iterdir():
            path.unlink()
        self.make_old_daily_copies(date(2026, 1, 1), count=15)
        out, _ = self.daily()
        self.assertIn("Removed 2 old daily copies.", out)

    def test_plain_command_never_prunes(self):
        old = self.make_old_daily_copies(date(2026, 9, 21))
        call_command(
            "backup_db",
            source=str(self.source),
            folder=str(self.folder),
            stdout=io.StringIO(),
        )
        files = self.files_in_folder()
        self.assertEqual(len(files), 21)
        self.assertTrue(set(old) <= set(files))


# A stand-in for `uv`: it writes its arguments to $UV_LOG, and for backup_db
# also whether db.sqlite3 is still there. FAKE_BACKUP_EXIT=1 makes the copy fail,
# FAKE_CLEAR_EXIT=1 makes clearsessions fail.
FAKE_UV = """#!/bin/sh
echo "$*" >> "$UV_LOG"
case "$*" in
  *backup_db*)
    if [ -f db.sqlite3 ]; then echo "db still there" >> "$UV_LOG"; fi
    exit "${FAKE_BACKUP_EXIT:-0}";;
  *clearsessions*) exit "${FAKE_CLEAR_EXIT:-0}";;
esac
exit 0
"""


class FakeUvTestCase(SimpleTestCase):
    """The real Makefile, in a temporary folder, with a fake `uv`.

    Only a copy of the Makefile and a dummy db.sqlite3 are in the folder, and
    the fake `uv` runs nothing (no server starts, no port is used), so the
    person's database is never near it.
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

    def run_make(self, *args, answer="", backup_fails=False, clear_fails=False):
        env = dict(self.env)
        if backup_fails:
            env["FAKE_BACKUP_EXIT"] = "1"
        if clear_fails:
            env["FAKE_CLEAR_EXIT"] = "1"
        return subprocess.run(
            [self.make, *args],
            cwd=self.tmp,
            env=env,
            input=answer,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def logged(self):
        return self.log.read_text().splitlines() if self.log.exists() else []


class MakeResetTests(FakeUvTestCase):
    """`make reset` for real, in a temporary folder, with a fake `uv`."""

    def reset(self, answer, *args, backup_fails=False):
        return self.run_make("reset", *args, answer=answer, backup_fails=backup_fails)

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


class MakeRunTests(FakeUvTestCase):
    """`make run` for real, with a fake `uv`: no server starts, no port is used."""

    BACKUP_WARNING = "Warning: the daily backup did not work"
    CLEAR_WARNING = "Warning: could not remove expired sessions"

    def assert_backup_then_clear_then_server(self):
        lines = self.logged()
        backup = lines.index("run python manage.py backup_db --daily")
        clear = lines.index("run python manage.py clearsessions")
        server = lines.index("run python manage.py runserver")
        self.assertLess(backup, clear)
        self.assertLess(clear, server)

    def test_run_backs_up_then_starts(self):
        result = self.run_make("run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_backup_then_clear_then_server()
        self.assertNotIn("Warning", result.stdout)

    def test_failed_backup_still_starts_with_a_warning(self):
        result = self.run_make("run", backup_fails=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_backup_then_clear_then_server()
        self.assertIn(self.BACKUP_WARNING, result.stdout)
        self.assertNotIn(self.CLEAR_WARNING, result.stdout)

    def test_failed_clearsessions_still_starts_with_a_warning(self):
        result = self.run_make("run", clear_fails=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_backup_then_clear_then_server()
        self.assertIn(self.CLEAR_WARNING, result.stdout)
        self.assertNotIn(self.BACKUP_WARNING, result.stdout)

    def test_both_fail_both_warn_and_start(self):
        result = self.run_make("run", backup_fails=True, clear_fails=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_backup_then_clear_then_server()
        self.assertIn(self.BACKUP_WARNING, result.stdout)
        self.assertIn(self.CLEAR_WARNING, result.stdout)

    def test_backup_target_has_no_daily_flag(self):
        result = self.run_make("backup")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.logged(), ["run python manage.py backup_db", "db still there"]
        )
