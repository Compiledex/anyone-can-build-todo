"""Invented sample data for the landing page screenshots, and a server to show it.

Run by scripts/landing_shots.py (`make landing-shots`), not by hand:

    uv run python scripts/landing_seed.py <scratch database file> <port>

It uses the project's settings with ONE change: the database is the scratch file
given here, never db.sqlite3. So no real data is read or changed. It creates the
tables, adds the sample people, lists and to-dos, prints one line of JSON (the
session cookies and the ids the screenshots need), and then serves the app on
127.0.0.1:<port> until it is stopped.

The dates are counted from today, so "Overdue" and "Due in a few days" always look
the same, whatever day the screenshots are taken.
"""

import json
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def use_scratch_database(path):
    """Load the project's settings, then point the database at the scratch file."""
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from config import settings

    settings.DATABASES["default"]["NAME"] = Path(path)
    settings.DEBUG = True  # So the server also sends the CSS and the images.

    import django

    django.setup()


def seed():
    """Add the invented sample data. Returns what the screenshots need."""
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.utils import timezone

    from todos.models import Subtask, Todo, TodoList

    today = timezone.localdate()

    def day(offset):
        return today + timedelta(days=offset)

    User = get_user_model()
    mara, theo, ines = (
        User.objects.create_user(name) for name in ("mara", "theo", "ines")
    )

    home = TodoList.objects.create(owner=mara, name="Home")
    trip = TodoList.objects.create(owner=mara, name="Weekend trip")
    garden = TodoList.objects.create(owner=mara, name="Garden")
    trip.members.add(theo, ines)
    band = TodoList.objects.create(owner=theo, name="Band practice")
    band.members.add(mara)

    def todo(
        the_list,
        title,
        *,
        due=None,
        priority=2,
        tags=(),
        notes="",
        repeat="",
        done=False,
        steps=(),
    ):
        item = Todo.objects.create(
            todo_list=the_list,
            title=title,
            due_date=due,
            priority=priority,
            description=notes,
            repeat=repeat,
            done=done,
        )
        if tags:
            item.set_tags(list(tags))
        for step, step_done in steps:
            Subtask.objects.create(todo=item, title=step, done=step_done)
        return item

    todo(
        home,
        "Car insurance",
        due=day(-4),
        priority=3,
        tags=["admin"],
        notes="Compare the two quotes.",
    )
    paint = todo(
        home,
        "Paint the hallway",
        due=day(7),
        tags=["home"],
        notes="Light grey, the same as the kitchen.",
        steps=[
            ("Buy primer and rollers", True),
            ("Tape the edges", True),
            ("First coat", False),
            ("Second coat", False),
            ("Put the pictures back", False),
        ],
    )
    todo(home, "Library books", due=day(3), priority=1)
    todo(home, "Pay rent", due=day(14), tags=["admin"], repeat="monthly")
    todo(home, "Call the dentist", done=True)

    todo(trip, "Book the cabin", done=True)
    todo(trip, "Ferry times", due=day(5), priority=3)
    todo(trip, "Rain jackets", tags=["packing"])
    todo(trip, "Food for Saturday", due=day(6), tags=["shopping"])

    todo(garden, "Plant tulips", due=day(9), tags=["autumn"])
    todo(garden, "Rake leaves", repeat="weekly", due=day(0), priority=1)
    todo(
        garden, "Fix the gate", priority=3, notes="The screw on the top hinge is loose."
    )
    todo(garden, "Cover the herbs", done=True)

    todo(band, "Learn the new song")

    cookies = {}
    for user in (mara, theo):
        client = Client()
        client.force_login(user)
        cookies[user.username] = client.cookies[settings.SESSION_COOKIE_NAME].value
    return {
        "cookie_name": settings.SESSION_COOKIE_NAME,
        "cookies": cookies,
        "home": home.pk,
        "trip": trip.pk,
        "garden": garden.pk,
        "paint": paint.pk,
    }


def main():
    database, port = sys.argv[1], sys.argv[2]
    if Path(database).name == "db.sqlite3":
        sys.exit("Use a scratch database file, never db.sqlite3.")
    use_scratch_database(database)

    from django.core.management import call_command

    call_command("migrate", verbosity=0)
    print(json.dumps(seed()), flush=True)
    call_command("runserver", f"127.0.0.1:{port}", use_reloader=False, verbosity=0)


if __name__ == "__main__":
    main()
