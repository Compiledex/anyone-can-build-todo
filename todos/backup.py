"""A safe copy of the SQLite database, for `make backup` and `make reset`.

Plain Python and the standard library only, so it can be tested without Django.
"""

import os
import sqlite3
from pathlib import Path
from urllib.parse import quote


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


def backup_database(source, folder, now):
    """Copy the SQLite file `source` into `folder` as db-YYYYMMDD-HHMMSS.sqlite3.

    Uses SQLite's online backup, so the copy is whole even while the app runs.
    Returns the new file's path, or None when `source` does not exist.
    Never overwrites a file, and never changes `source`.
    """
    source = Path(source)
    if not source.is_file():
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"db-{now:%Y%m%d-%H%M%S}.sqlite3"
    target = folder / name
    temporary = folder / f".{name}.tmp"
    # Reserve the final name: "x" fails with FileExistsError when the file
    # exists, so an older backup is never overwritten (no check-then-create gap).
    with open(target, "xb"):
        pass
    try:
        temporary.unlink(missing_ok=True)
        copy_sqlite(source, temporary)
        # One step on the same disk: backups/ never holds a half-written file
        # with the final name.
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    return target
