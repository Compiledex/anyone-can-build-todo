"""A safe copy of the SQLite database, for `make backup`, `make reset` and `make run`.

`make run` makes a *daily copy* (`daily_backup`): at most one a day, named
db-YYYYMMDD-HHMMSS-daily.sqlite3, and only the newest DAILY_KEEP of them stay.
Copies from `make backup` and `make reset` have no "-daily" and are never
deleted by this file.

Plain Python and the standard library only, so it can be tested without Django.
"""

import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

DAILY_SUFFIX = "-daily"
# The whole name of a daily copy; group 1 is its day. Always use fullmatch.
# [0-9], not \d: \d also matches other scripts' digits, like "٢".
DAILY_NAME = re.compile(r"db-([0-9]{8})-[0-9]{6}-daily\.sqlite3")
# How many daily copies stay, today's included.
DAILY_KEEP = 14


class PruneError(OSError):
    """An old daily copy could not be deleted, after today's copy was safe.

    `path` is the copy that stayed, `removed` the copies deleted before it,
    and `created` today's new copy (or None when it was already there).
    """

    def __init__(self, path, removed, error):
        super().__init__(f"{path.name}: {error}")
        self.path = path
        self.removed = removed
        self.created = None


def copy_sqlite(source, target):
    """Copy the SQLite file `source` into the new file `target`.

    SQLite's online backup: the copy is whole even while the app writes to
    `source`. `source` is opened read-only, so it is never changed, and a
    missing file is never made as an empty database.
    """
    # quote(): a "?" or "#" in the folder name must not end the path in the URI.
    uri = f"file:{quote(Path(source).resolve().as_posix())}?mode=ro"
    reader = sqlite3.connect(uri, uri=True)
    try:
        writer = sqlite3.connect(target)
        try:
            reader.backup(writer)
        finally:
            writer.close()
    finally:
        reader.close()


def backup_database(source, folder, now, suffix=""):
    """Copy the SQLite file `source` into `folder` as db-YYYYMMDD-HHMMSS.sqlite3.

    `suffix` goes before ".sqlite3" (DAILY_SUFFIX for a daily copy).
    Uses SQLite's online backup, so the copy is whole even while the app runs.
    Returns the new file's path, or None when `source` does not exist.
    Never overwrites a file, and never changes `source`. Only the owner can
    read the copy (mode 600).
    """
    source = Path(source)
    if not source.is_file():
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"db-{now:%Y%m%d-%H%M%S}{suffix}.sqlite3"
    target = folder / name
    temporary = folder / f".{name}.tmp"
    # Reserve the final name: "x" fails with FileExistsError when the file
    # exists, so an older backup is never overwritten (no check-then-create gap).
    with open(target, "xb"):
        pass
    try:
        temporary.unlink(missing_ok=True)
        copy_sqlite(source, temporary)
        # Only the person can read the copy: it holds every account and to-do.
        os.chmod(temporary, 0o600)
        # On the disk before the rename, so a crash never leaves an empty
        # file with the final name.
        with open(temporary, "rb") as copy:
            os.fsync(copy.fileno())
        # One step on the same disk: backups/ never holds a half-written file
        # with the final name.
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    return target


def daily_copies(folder):
    """The daily copies in `folder`, oldest first (by name, which is by time).

    Only regular files (not links, not folders) whose whole name matches
    DAILY_NAME. Never a .tmp file, never another backup, never anything else.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.iterdir()
        if DAILY_NAME.fullmatch(path.name) and not path.is_symlink() and path.is_file()
    )


def prune_daily(folder, keep, protect):
    """Delete all but the newest `keep` daily copies. Returns the deleted paths.

    `protect` (today's copy) is never deleted and counts as one of the `keep`;
    of the others, the newest keep - 1 by name stay. A failed delete stops
    here with PruneError, which holds the copies deleted before it.
    """
    others = [path for path in daily_copies(folder) if path != protect]
    keep_others = max(keep - 1, 0)
    removed = []
    for path in others[: max(len(others) - keep_others, 0)]:
        try:
            path.unlink()
        except OSError as error:
            raise PruneError(path, removed, error) from error
        removed.append(path)
    return removed


def daily_backup(source, folder, now, keep=DAILY_KEEP):
    """Make today's daily copy unless one exists, then prune.

    Today is `now.date()`. Returns (new path or None, deleted paths). No
    source: (None, []) and nothing is pruned. If the copy fails, the error
    goes up and nothing is pruned, so old copies are never deleted on a day
    without a new one. A failed delete raises PruneError, with `created` set.
    """
    if not Path(source).is_file():
        return None, []
    folder = Path(folder)
    today = f"{now:%Y%m%d}"
    todays = [
        path
        for path in daily_copies(folder)
        if DAILY_NAME.fullmatch(path.name).group(1) == today
    ]
    created = None
    if todays:
        protect = todays[-1]
    else:
        try:
            created = backup_database(source, folder, now, suffix=DAILY_SUFFIX)
        except FileExistsError:
            # Another run made a copy in this same second: today's copy exists.
            # Anything else (`folder` is a file, or a folder or a link has
            # today's name) is a failed copy.
            protect = folder / f"db-{now:%Y%m%d-%H%M%S}{DAILY_SUFFIX}.sqlite3"
            if protect.is_symlink() or not protect.is_file():
                raise
        else:
            if created is None:  # The source went away just now.
                return None, []
            protect = created
    try:
        removed = prune_daily(folder, keep, protect)
    except PruneError as error:
        error.created = created
        raise
    return created, removed
