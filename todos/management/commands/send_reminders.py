"""`python manage.py send_reminders --user alice`: one Mac notification.

launchd runs this every morning (see deploy/macos/). It never prints a to-do
title, so the log file stays free of the person's to-dos.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from todos.reminders import NotificationError, send_reminders


class Command(BaseCommand):
    help = (
        "Show one Mac notification with the to-dos in the user's own lists "
        "that are due today and not done."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            required=True,
            help="The username on the site whose to-dos are shown. Required.",
        )

    def handle(self, *args, **options):
        username = options["user"]
        # The same message for an unknown and a switched-off user, so the
        # command does not tell which usernames exist.
        user = (
            get_user_model().objects.filter(username=username, is_active=True).first()
        )
        if user is None:
            raise CommandError(f'No active user named "{username}".')
        try:
            count = send_reminders(user, timezone.localdate())
        except NotificationError as error:
            raise CommandError(f"Could not show the notification: {error}") from error
        if count == 0:
            self.stdout.write(f"No to-dos due today for {username}.")
        else:
            todos = "1 to-do" if count == 1 else f"{count} to-dos"
            self.stdout.write(f"Showed 1 notification ({todos}) for {username}.")
