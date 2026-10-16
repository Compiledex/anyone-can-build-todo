"""Deleting your own account: what the confirm page shows, and the sessions that go too.

Only for the database session engine (django.contrib.sessions.backends.db, the
default, which config/settings.py does not change): delete_sessions_of reads the
rows of django_session. A test checks the engine, so a change is noticed.
"""

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.db.models import Count


def account_summary(user):
    """What deleting this user's account deletes, and what it leaves, for the page.

    Reads only user.todo_lists, user.tags and user.shared_lists (never
    Todo.objects), in three queries, whatever the number of lists.
    """
    own_lists = list(
        user.todo_lists.annotate(
            # distinct=True: the two joins (to-dos and members) multiply the rows.
            todo_count=Count("todos", distinct=True),
            member_count=Count("members", distinct=True),
        )
    )
    return {
        "list_count": len(own_lists),
        "todo_count": sum(the_list.todo_count for the_list in own_lists),
        "tag_count": user.tags.count(),
        # Her own lists that members will lose, in the list menu's order. Only
        # the number of members: the page names nobody.
        "shared_lists": [the_list for the_list in own_lists if the_list.member_count],
        "joined_count": user.shared_lists.count(),
    }


def delete_sessions_of(user):
    """Delete every session row of this user: every browser where they are logged in.

    Call it inside the same transaction.atomic() as user.delete(). It collects
    the keys first and deletes them after the loop: on SQLite a delete during
    the loop could change what the loop still reads. A broken row decodes to {}
    and is skipped.
    """
    keys = [
        row.session_key
        for row in Session.objects.iterator()
        if row.get_decoded().get(SESSION_KEY) == str(user.pk)
    ]
    Session.objects.filter(session_key__in=keys).delete()
