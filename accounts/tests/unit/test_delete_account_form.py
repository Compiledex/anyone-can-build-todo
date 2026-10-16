"""DeleteAccountForm on its own: it only checks the password of the user it is given."""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings

from accounts.forms import DeleteAccountForm
from accounts.tests.helpers import TEST_PASSWORD


# A fast hasher, only in these tests: the user is never saved.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DeleteAccountFormTests(SimpleTestCase):
    def setUp(self):
        self.user = get_user_model()(username="alice")  # Not saved: no database.
        self.user.set_password(TEST_PASSWORD)

    def form(self, password):
        return DeleteAccountForm(self.user, {"password": password})

    def test_right_password_is_valid(self):
        self.assertTrue(self.form(TEST_PASSWORD).is_valid())

    def test_wrong_password_is_invalid(self):
        form = self.form("not-the-password")
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["password"], ["Wrong password. Nothing was deleted."]
        )
        self.assertTrue(form.has_error("password", code="wrong_password"))

    def test_empty_password_is_invalid(self):
        form = self.form("")
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["password"], ["This field is required."])

    def test_password_is_not_stripped_or_rendered(self):
        form = self.form(" " + TEST_PASSWORD)
        self.assertFalse(form.is_valid())  # No strip: the space is part of it.
        self.assertNotIn(TEST_PASSWORD, str(form))
        self.assertEqual(
            form["password"].label_tag(), '<label for="id_password">Password</label>'
        )
