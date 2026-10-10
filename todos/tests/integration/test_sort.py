"""Tests for sorting a list (`?sort=` on the list page).

alice is logged in and owns "Inbox" (self.todo_list). bob owns "Bob's list".
Each test makes the to-dos in an order that is different from the expected
one, so a test fails if the sort does nothing.
"""

import datetime

from django.utils import timezone

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo


class SortTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        self.url = self.todo_list.get_absolute_url()

    def add(self, title, **fields):
        return Todo.objects.create(todo_list=self.todo_list, title=title, **fields)

    def shown(self, response):
        return [todo.title for todo in response.context["todos"]]

    def in_days(self, days):
        return timezone.localdate() + datetime.timedelta(days=days)

    def test_sort_by_due_date_puts_no_date_last(self):
        self.add("In ten days", due_date=self.in_days(10))
        self.add("No date")
        self.add("In two days", due_date=self.in_days(2))
        response = self.client.get(f"{self.url}?sort=due")
        self.assertEqual(
            self.shown(response), ["In two days", "In ten days", "No date"]
        )

    def test_sort_by_due_date_ties_use_created_at(self):
        day = self.in_days(5)
        first = self.add("Made first", due_date=day)
        second = self.add("Made second", due_date=day)
        # The one made second (bigger pk) gets the older created_at.
        Todo.objects.filter(pk=second.pk).update(
            created_at=first.created_at - datetime.timedelta(hours=1)
        )
        response = self.client.get(f"{self.url}?sort=due")
        self.assertEqual(self.shown(response), ["Made second", "Made first"])

    def test_sort_by_priority_most_important_first(self):
        self.add("Low one", priority=Todo.Priority.LOW)
        self.add("High one", priority=Todo.Priority.HIGH)
        self.add("Medium one", priority=Todo.Priority.MEDIUM)
        response = self.client.get(f"{self.url}?sort=priority")
        self.assertEqual(self.shown(response), ["High one", "Medium one", "Low one"])

    def test_sort_by_title_ignores_case(self):
        self.add("cherry")
        self.add("Banana")
        self.add("apple")
        response = self.client.get(f"{self.url}?sort=title")
        self.assertEqual(self.shown(response), ["apple", "Banana", "cherry"])

    def test_bad_sort_shows_default_order(self):
        self.add("Old")
        self.add("New")
        response = self.client.get(f"{self.url}?sort=-created_at")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.shown(response), ["Old", "New"])
        # The default order is set by apply_list_query, not by Meta.ordering.
        self.assertEqual(response.context["todos"].query.order_by, ("created_at", "pk"))

    def test_sort_menu_shows_current_choice(self):
        response = self.client.get(f"{self.url}?sort=due")
        self.assertContains(
            response, '<option value="due" selected>Due date</option>', html=True
        )

    def test_sort_combines_with_search_and_filter(self):
        self.add("milk z")
        self.add("Call home")
        self.add("milk done", done=True)
        self.add("Milk a")
        response = self.client.get(f"{self.url}?q=milk&status=open&sort=title")
        self.assertEqual(self.shown(response), ["Milk a", "milk z"])

    def test_filter_links_and_show_all_keep_sort(self):
        response = self.client.get(f"{self.url}?q=xyz&sort=title")
        # "All" is the current filter, so it has aria-current.
        for label, query, extra in [
            ("All", "?q=xyz&amp;sort=title", ' aria-current="page"'),
            ("Not done", "?q=xyz&amp;status=open&amp;sort=title", ""),
            ("Done", "?q=xyz&amp;status=done&amp;sort=title", ""),
        ]:
            with self.subTest(label=label):
                self.assertContains(
                    response,
                    f'<a href="{self.url}{query}"{extra}>{label}</a>',
                    html=True,
                )
        # "Show all" clears the search and the filter, but keeps the order.
        self.assertContains(
            response, f'<a href="{self.url}?sort=title">Show all</a>', html=True
        )

    def test_forms_keep_each_other(self):
        response = self.client.get(f"{self.url}?q=milk&status=open&sort=title")
        html = response.content.decode()
        sort_form = html[html.index('<form class="sort"') :]
        sort_form = sort_form[: sort_form.index("</form>")]
        # GET: sorting only reads, and needs no CSRF token.
        self.assertTrue(sort_form.startswith('<form class="sort" method="get">'))
        self.assertInHTML('<input type="hidden" name="q" value="milk">', sort_form)
        self.assertInHTML('<input type="hidden" name="status" value="open">', sort_form)
        search_form = html[html.index('<form class="search"') :]
        search_form = search_form[: search_form.index("</form>")]
        self.assertInHTML(
            '<input type="hidden" name="sort" value="title">', search_form
        )

    def test_other_users_list_with_sort_is_404(self):
        self.add("Buy milk")
        self.assertOtherUserGets404(f"{self.url}?sort=due", method="get")

    def test_member_can_sort_shared_list(self):
        self.todo_list.members.add(self.other_user)
        self.add("cherry")
        self.add("apple")
        bob = self.client_for(self.other_user)
        response = bob.get(f"{self.url}?sort=title")
        self.assertEqual(self.shown(response), ["apple", "cherry"])
