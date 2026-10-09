from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.tests.helpers import TEST_PASSWORD, make_user

LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"
LOGOUT_URL = "/accounts/logout/"


def is_logged_in(client):
    return client.get(reverse("todo_list")).status_code == 200


class SignupTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            SIGNUP_URL,
            {
                "username": "carol",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )
        self.assertTrue(get_user_model().objects.filter(username="carol").exists())
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(is_logged_in(self.client))

    def test_signup_with_different_passwords_shows_error(self):
        response = self.client.post(
            SIGNUP_URL,
            {
                "username": "carol",
                "password1": TEST_PASSWORD,
                "password2": "another-long-password-9",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="carol").exists())
        self.assertContains(response, "The two password fields didn")
        self.assertContains(response, 'value="carol"')

    def test_signup_with_taken_username_shows_error(self):
        make_user("alice")
        response = self.client.post(
            SIGNUP_URL,
            {
                "username": "Alice",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A user with that username already exists.")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_signup_ignores_next(self):
        response = self.client.post(
            SIGNUP_URL + "?next=https://evil.example/",
            {
                "username": "carol",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
                "next": "https://evil.example/",
            },
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("alice")

    def test_login_with_right_password_goes_to_next(self):
        response = self.client.post(
            LOGIN_URL, {"username": "alice", "password": TEST_PASSWORD, "next": "/"}
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(is_logged_in(self.client))

    def test_login_ignores_next_to_another_site(self):
        for next_url in [
            "https://evil.example/",
            "//evil.example/",
            "/\\evil.example/",
        ]:
            with self.subTest(next=next_url):
                client = Client()
                response = client.post(
                    LOGIN_URL,
                    {"username": "alice", "password": TEST_PASSWORD, "next": next_url},
                )
                self.assertRedirects(response, "/", fetch_redirect_response=False)
                self.assertNotIn("evil.example", response["Location"])

    def test_login_with_wrong_password_shows_error(self):
        response = self.client.post(
            LOGIN_URL, {"username": "alice", "password": "wrong-password-1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password.")
        self.assertFalse(is_logged_in(self.client))

    def test_logged_in_user_on_login_or_signup_goes_to_list(self):
        self.client.force_login(self.user)
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_login_page_keeps_next(self):
        response = self.client.get(LOGIN_URL + "?next=/add/")
        self.assertContains(response, 'name="next" value="/add/"')

    def test_anonymous_pages_have_no_header(self):
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Logged in as")

    def test_login_page_has_csrf_token(self):
        for url in [LOGIN_URL, SIGNUP_URL]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="csrfmiddlewaretoken"')


class LogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user("alice")

    def setUp(self):
        self.client.force_login(self.user)

    def test_logout_logs_out(self):
        response = self.client.post(LOGOUT_URL, {"next": "https://evil.example/"})
        self.assertRedirects(response, LOGIN_URL, fetch_redirect_response=False)
        response = self.client.get(reverse("todo_list"))
        self.assertRedirects(
            response, LOGIN_URL + "?next=/", fetch_redirect_response=False
        )

    def test_logout_when_already_logged_out_goes_to_login(self):
        response = Client().post(LOGOUT_URL)
        self.assertRedirects(response, LOGIN_URL, fetch_redirect_response=False)

    def test_logout_with_get_is_405(self):
        response = self.client.get(LOGOUT_URL)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(is_logged_in(self.client))

    def test_header_shows_username_and_logout_button(self):
        response = self.client.get(reverse("todo_list"))
        self.assertContains(response, "Logged in as alice")
        self.assertContains(response, f'<form method="post" action="{LOGOUT_URL}"')
