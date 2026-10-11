"""`python manage.py backup_db`: copy db.sqlite3 into backups/.

`make backup` runs it, and `make reset` runs it before it deletes the database.
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from todos.backup import backup_database


class Command(BaseCommand):
    help = (
        "Copy the SQLite database into backups/ as db-YYYYMMDD-HHMMSS.sqlite3. "
        "Safe while the server runs."
    )

    def add_arguments(self, parser):
        # For the tests only: the Makefile never passes these.
        parser.add_argument("--source", help="The database file to copy.")
        parser.add_argument("--folder", help="The folder to put the copy in.")

    def handle(self, *args, **options):
        source = Path(options["source"] or settings.DATABASES["default"]["NAME"])
        folder = Path(options["folder"] or settings.BASE_DIR / "backups")
        try:
            target = backup_database(source, folder, timezone.localtime())
        except FileExistsError as error:
            raise CommandError(
                "A backup with this time already exists. Wait a second and try again."
            ) from error
        except (OSError, sqlite3.Error) as error:
            raise CommandError(f"Could not copy the database: {error}") from error
        if target is None:
            self.stdout.write("No database yet: nothing to back up.")
            return
        try:
            shown = target.relative_to(settings.BASE_DIR)
        except ValueError:
            shown = target
        self.stdout.write(f"Saved a copy in {shown}.")
