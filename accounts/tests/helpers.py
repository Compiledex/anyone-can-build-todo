"""Test helpers for every feature: users, and a TestCase that is logged in.

The name does not start with `test`, so the test runner does not load this
file as tests. Other test files import from it.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

# Only for tests. It is not a real password for anything. It passes Django's
# password rules (it is not in the common-password list).
TEST_PASSWORD = "correct-horse-battery-staple"


def make_user(username="alice"):
    return get_user_model().objects.create_user(
        username=username, password=TEST_PASSWORD
    )


class LoggedInTestCase(TestCase):
    """A TestCase where self.client is logged in as self.user (alice).

    self.other_user (bob) exists too, to check that bob cannot see or
    change alice's things.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("alice")
        cls.other_user = make_user("bob")

    def setUp(self):
        self.client.force_login(self.user)

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def assertOtherUserGets404(self, url, method="post", data=None):
        """bob asks for alice's thing, and gets 404."""
        response = getattr(self.client_for(self.other_user), method)(url, data or {})
        self.assertEqual(response.status_code, 404)
