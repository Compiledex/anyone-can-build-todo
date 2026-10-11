"""`python manage.py backup_db`: copy db.sqlite3 into backups/.

`make backup` runs it, and `make reset` runs it before it deletes the database.
`make run` runs it with --daily: at most one copy a day, the newest 14 are kept.
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import pluralize
from django.utils import timezone

from todos.backup import PruneError, backup_database, daily_backup


def shown(path):
    """`path` from the project folder (backups/...), or in full when outside it."""
    try:
        return path.relative_to(settings.BASE_DIR)
    except ValueError:
        return path


class Command(BaseCommand):
    help = (
        "Copy the SQLite database into backups/ as db-YYYYMMDD-HHMMSS.sqlite3. "
        "Safe while the server runs. With --daily: at most one copy a day, "
        "named ...-daily.sqlite3, and only the newest 14 daily copies stay."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--daily",
            action="store_true",
            help="Make today's daily copy unless one exists, then remove old ones.",
        )
        # For the tests only: the Makefile never passes these.
        parser.add_argument("--source", help="The database file to copy.")
        parser.add_argument("--folder", help="The folder to put the copy in.")

    def handle(self, *args, **options):
        source = Path(options["source"] or settings.DATABASES["default"]["NAME"])
        folder = Path(options["folder"] or settings.BASE_DIR / "backups")
        if options["daily"]:
            self.daily(source, folder)
            return
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
        self.stdout.write(f"Saved a copy in {shown(target)}.")

    def daily(self, source, folder):
        prune_error = None
        try:
            created, removed = daily_backup(source, folder, timezone.localtime())
        except PruneError as error:
            # Today's copy is safe; only an old one could not be removed.
            prune_error = error
            created, removed = error.created, error.removed
        except (OSError, sqlite3.Error) as error:
            raise CommandError(f"Could not copy the database: {error}") from error
        if created is not None:
            self.stdout.write(f"Saved today's copy in {shown(created)}.")
        elif source.is_file():
            self.stdout.write(f"Today's copy is already in {shown(folder)}/.")
        else:
            self.stdout.write("No database yet: nothing to back up.")
            return
        if removed:
            count = len(removed)
            self.stdout.write(
                f"Removed {count} old daily cop{pluralize(count, 'y,ies')}."
            )
        if prune_error is not None:
            self.stderr.write(
                f"Warning: could not remove an old daily copy: {prune_error}."
            )
