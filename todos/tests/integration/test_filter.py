"""Tests for filtering the open list (`?status=` on the list page), and for
Done, Undo and Delete going back to the same filtered or searched page.

alice is logged in and owns "Inbox" (self.todo_list). bob owns "Bob's list".
The shown to-dos are checked with response.context["todos"], because the word
"Done" is also on the buttons and the links.
"""

from django.urls import reverse

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo

NO_MATCH = "No to-dos match"
EMPTY_LIST = "Nothing to do yet"


class FilterTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.url = self.todo_list.get_absolute_url()

    def add(self, title, **fields):
        return Todo.objects.create(todo_list=self.todo_list, title=title, **fields)

    def shown(self, response):
        return [todo.title for todo in response.context["todos"]]

    def add_two(self):
        self.add("Buy milk")
        self.add("Call home", done=True)

    def test_open_shows_only_not_done(self):
        self.add_two()
        response = self.client.get(f"{self.url}?status=open")
        self.assertEqual(self.shown(response), ["Buy milk"])

    def test_done_shows_only_done(self):
        self.add_two()
        response = self.client.get(f"{self.url}?status=done")
        self.assertEqual(self.shown(response), ["Call home"])

    def test_no_status_shows_all(self):
        self.add_two()
        response = self.client.get(self.url)
        self.assertEqual(self.shown(response), ["Buy milk", "Call home"])

    def test_bad_status_shows_all(self):
        self.add_two()
        response = self.client.get(f"{self.url}?status=banana")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.shown(response), ["Buy milk", "Call home"])

    def test_filter_combines_with_search(self):
        self.add("Buy milk")
        self.add("Milk done", done=True)
        self.add("Call home")
        response = self.client.get(f"{self.url}?q=milk&status=open")
        self.assertEqual(self.shown(response), ["Buy milk"])

    def test_filter_links_keep_search(self):
        self.add_two()
        response = self.client.get(f"{self.url}?q=milk")
        self.assertContains(
            response, f'<a href="{self.url}?q=milk&amp;status=done">Done</a>', html=True
        )

    def test_current_filter_is_marked(self):
        # html=True compares every attribute, so `<a href=...>All</a>` does not
        # match a link that has aria-current.
        def link(query, label, current=False):
            mark = ' aria-current="page"' if current else ""
            return f'<a href="{self.url}{query}"{mark}>{label}</a>'

        response = self.client.get(f"{self.url}?status=done")
        self.assertContains(response, link("?status=done", "Done", True), html=True)
        self.assertContains(response, link("", "All"), html=True)
        self.assertContains(response, link("?status=open", "Not done"), html=True)

        response = self.client.get(self.url)
        self.assertContains(response, link("", "All", True), html=True)
        self.assertContains(response, link("?status=done", "Done"), html=True)
        self.assertContains(response, link("?status=open", "Not done"), html=True)

    def test_search_form_keeps_status(self):
        hidden = '<input type="hidden" name="status" value="open">'
        response = self.client.get(f"{self.url}?status=open")
        self.assertContains(response, hidden, html=True)
        response = self.client.get(f"{self.url}?status=banana")
        self.assertNotContains(response, 'name="status"')

    def test_no_match_message(self):
        self.add("Buy milk")
        response = self.client.get(f"{self.url}?status=done")
        self.assertEqual(self.shown(response), [])
        self.assertContains(response, f"{NO_MATCH}.")
        self.assertContains(response, f'<a href="{self.url}">Show all</a>', html=True)
        self.assertNotContains(response, EMPTY_LIST)

    def test_clear_completed_counts_the_whole_list_while_filtering(self):
        # The button deletes every done to-do of the list, whatever is shown.
        self.add_two()
        response = self.client.get(f"{self.url}?status=open")
        self.assertEqual(self.shown(response), ["Buy milk"])
        self.assertContains(response, "Clear completed (1)")

    def test_other_users_list_with_filter_is_404(self):
        self.add_two()
        self.assertOtherUserGets404(f"{self.url}?status=done", method="get")

    def test_filter_shows_shared_todos(self):
        self.todo_list.members.add(self.other_user)
        self.add_two()
        bob = self.client_for(self.other_user)
        response = bob.get(f"{self.url}?status=done")
        self.assertEqual(self.shown(response), ["Call home"])


class RedirectBackTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.url = self.todo_list.get_absolute_url()
        self.todo = Todo.objects.create(todo_list=self.todo_list, title="Buy milk")

    def toggle(self, data=None, client=None, **extra):
        url = reverse("todo_toggle", args=[self.todo.pk])
        return (client or self.client).post(url, data or {}, **extra)

    def test_row_forms_carry_current_address(self):
        response = self.client.get(f"{self.url}?q=milk&status=open")
        hidden = f'<input type="hidden" name="next" value="{self.url}?q=milk&amp;status=open">'
        self.assertContains(response, hidden, count=2, html=True)  # Done, Delete.

    def test_toggle_returns_to_filtered_view(self):
        next_url = f"{self.url}?status=open"
        response = self.toggle({"next": next_url})
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.todo.refresh_from_db()
        self.assertTrue(self.todo.done)

    def test_delete_returns_to_filtered_view(self):
        next_url = f"{self.url}?q=milk"
        response = self.client.post(
            reverse("todo_delete", args=[self.todo.pk]), {"next": next_url}
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertFalse(Todo.objects.filter(pk=self.todo.pk).exists())

    def test_toggle_keeps_open_steps(self):
        # A row on a page with ?open= (after a step action) keeps it too.
        next_url = f"{self.url}?status=open&open={self.todo.pk}"
        response = self.toggle({"next": next_url})
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_toggle_without_next_goes_to_list(self):
        response = self.toggle()
        self.assertRedirects(response, self.url, fetch_redirect_response=False)

    def test_unsafe_next_is_ignored(self):
        for value in [
            "https://evil.example/",
            "//evil.example/",
            "/\\evil.example/",
            "\\\\evil.example/",
            "javascript:alert(1)",
            "http://testserver/",
            "foo",
            "",
        ]:
            with self.subTest(next=value):
                response = self.toggle({"next": value}, secure=True)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], self.url)

    def test_unsafe_next_on_delete_is_ignored(self):
        response = self.client.post(
            reverse("todo_delete", args=[self.todo.pk]), {"next": "//evil.example/"}
        )
        self.assertRedirects(response, self.url, fetch_redirect_response=False)

    def test_next_does_not_skip_owner_check(self):
        bob = self.client_for(self.other_user)
        response = self.toggle({"next": f"{self.url}?status=open"}, client=bob)
        self.assertEqual(response.status_code, 404)
        self.todo.refresh_from_db()
        self.assertFalse(self.todo.done)
        response = bob.post(
            reverse("todo_delete", args=[self.todo.pk]), {"next": self.url}
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Todo.objects.filter(pk=self.todo.pk).exists())

    def test_bad_add_page_links_go_to_the_list(self):
        # A bad add shows the page at .../add/ (POST only). The filter links and
        # the rows' `next` must point to the list page, not to .../add/.
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, f'<a href="{self.url}?status=done">Done</a>', html=True
        )
        hidden = f'<input type="hidden" name="next" value="{self.url}">'
        self.assertContains(response, hidden, count=2, html=True)
