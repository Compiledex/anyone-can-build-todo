"""Start `manage.py check` in a new process, with chosen environment variables.

Settings are loaded once per process, so the only way to test that
config/settings.py really uses config/env.py is a new process. These tests
use subprocesses, not Django's test client. `check` does not open the database.
"""

import os
import secrets
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


def run_manage(*args, **variables):
    """Run manage.py in a new process with no DJANGO_* variable but `variables`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    env.update(variables)
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def output_of(result):
    return f"exit code {result.returncode}\n{result.stdout}\n{result.stderr}"


class SettingsStartupTests(SimpleTestCase):
    def test_debug_off_without_key_stops(self):
        result = run_manage("check", DJANGO_DEBUG="False")
        self.assertNotEqual(result.returncode, 0, output_of(result))
        self.assertIn("DJANGO_SECRET_KEY is not set", result.stderr, output_of(result))

    def test_debug_off_with_strong_key_passes_deploy_check(self):
        result = run_manage(
            "check",
            "--deploy",
            "--fail-level",
            "WARNING",
            DJANGO_DEBUG="False",
            DJANGO_SECRET_KEY=secrets.token_urlsafe(50),
            DJANGO_ALLOWED_HOSTS="example.com",
        )
        self.assertEqual(result.returncode, 0, output_of(result))

    def test_no_variables_still_starts(self):
        result = run_manage("check")
        self.assertEqual(result.returncode, 0, output_of(result))
