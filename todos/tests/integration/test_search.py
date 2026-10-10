"""Tests for searching the to-dos of the open list (`?q=` on the list page).

alice is logged in and owns "Inbox" (self.todo_list). bob owns "Bob's list".
Every "does not contain" has a "does contain" next to it, so an empty or
broken page cannot pass.
"""

from urllib.parse import quote

from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Subtask, Todo, TodoList

NO_MATCH = "No to-dos match"
EMPTY_LIST = "Nothing to do yet"
SHOW_ALL = ">Show all</a>"


class SearchTests(LoggedInTestCase):
    def add(self, title, todo_list=None, **fields):
        return Todo.objects.create(
            todo_list=todo_list or self.todo_list, title=title, **fields
        )

    def search(self, q, todo_list=None, client=None):
        the_list = todo_list or self.todo_list
        url = f"{the_list.get_absolute_url()}?q={quote(q)}"
        return (client or self.client).get(url)

    def shown(self, response):
        return [todo.title for todo in response.context["todos"]]

    def test_search_finds_word_in_title(self):
        self.add("Buy milk")
        self.add("Call home")
        response = self.search("milk")
        self.assertEqual(self.shown(response), ["Buy milk"])
        self.assertContains(response, "Buy milk")
        self.assertNotContains(response, "Call home")

    def test_search_ignores_case(self):
        self.add("Buy milk")
        self.add("Call home")
        response = self.search("MILK")
        self.assertEqual(self.shown(response), ["Buy milk"])

    def test_search_finds_word_in_description(self):
        self.add("Shopping", description="Remember the milk")
        self.add("Call home")
        response = self.search("milk")
        self.assertEqual(self.shown(response), ["Shopping"])

    def test_search_finds_tag_name(self):
        todo = self.add("Buy bread")
        todo.set_tags(["shopping"])
        self.add("Call home")
        response = self.search("shop")
        self.assertEqual(self.shown(response), ["Buy bread"])

    def test_todo_with_two_matching_tags_is_shown_once(self):
        todo = self.add("Buy bread")
        todo.set_tags(["shop", "shopping"])
        self.add("Call home")
        response = self.search("shop")
        self.assertEqual(self.shown(response), ["Buy bread"])

    def test_empty_search_shows_whole_list(self):
        self.add("Buy milk")
        self.add("Call home")
        response = self.search("  ")
        self.assertEqual(self.shown(response), ["Buy milk", "Call home"])
        self.assertNotContains(response, SHOW_ALL)
        self.assertNotContains(response, NO_MATCH)

    def test_search_trims_spaces(self):
        self.add("Buy milk")
        self.add("Call home")
        response = self.search(" milk ")
        self.assertEqual(self.shown(response), ["Buy milk"])

        response = self.search(" xyz ")
        self.assertContains(response, f"{NO_MATCH} “xyz”.")
        self.assertNotContains(response, "“ xyz ”")

    def test_percent_sign_is_not_a_wildcard(self):
        self.add("50% off")
        self.add("Call home")
        response = self.search("%")
        self.assertEqual(self.shown(response), ["50% off"])

        # `_` is a normal letter too, not "any one letter".
        self.add("a_b")
        self.add("axb")
        response = self.search("_")
        self.assertEqual(self.shown(response), ["a_b"])

    def test_no_match_shows_message(self):
        self.add("Buy milk")
        response = self.search("xyz")
        self.assertEqual(self.shown(response), [])
        self.assertContains(response, f"{NO_MATCH} “xyz”.")
        self.assertContains(response, SHOW_ALL)
        self.assertNotContains(response, EMPTY_LIST)

    def test_show_all_goes_back_to_the_open_list(self):
        # A newer list, so `/` would send the browser to Inbox, not here.
        work = TodoList.objects.create(owner=self.user, name="Work")
        self.add("Buy milk", todo_list=work)
        response = self.search("xyz", todo_list=work)
        self.assertContains(
            response, f'<a href="{work.get_absolute_url()}">Show all</a>', html=True
        )

    def test_clear_completed_counts_the_whole_list_while_searching(self):
        # The button deletes every done to-do of the list, so the count must
        # not shrink to the search results.
        self.add("Buy milk")
        self.add("Call home", done=True)
        response = self.search("milk")
        self.assertEqual(self.shown(response), ["Buy milk"])
        self.assertContains(response, "Clear completed (1)")

    def test_search_box_keeps_typed_text(self):
        self.add("Buy milk")
        response = self.search("milk")
        self.assertContains(
            response,
            '<input type="search" name="q" aria-label="Search to-dos" '
            'placeholder="Search" maxlength="200" value="milk">',
            html=True,
        )

    def test_search_text_is_escaped(self):
        self.add("Buy milk")
        response = self.search('"><script>x</script>')
        self.assertNotContains(response, "<script>x</script>")
        # In the search box, the sort form's hidden q, and the "no match" message.
        self.assertContains(response, "&quot;&gt;&lt;script&gt;", count=3)
        self.assertContains(response, NO_MATCH)

    def test_too_long_search_shows_error_and_whole_list(self):
        self.add("Buy milk")
        self.add("Call home")
        response = self.search("m" * 201)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "at most 200 characters")
        self.assertEqual(self.shown(response), ["Buy milk", "Call home"])
        self.assertNotContains(response, NO_MATCH)

        response = self.search("m" * 200)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "at most 200 characters")
        self.assertContains(response, NO_MATCH)

    def test_search_stays_in_open_list(self):
        work = TodoList.objects.create(owner=self.user, name="Work")
        self.add("Buy milk", todo_list=work)
        self.add("Milk the cow")
        response = self.search("milk")
        self.assertEqual(self.shown(response), ["Milk the cow"])
        self.assertNotContains(response, "Buy milk")

    def test_other_users_todos_never_match(self):
        theirs = self.add("Buy milk")  # alice's to-do, with a matching tag.
        theirs.set_tags(["milk"])
        Todo.objects.create(todo_list=self.other_list, title="Milk shake")
        bob = self.client_for(self.other_user)
        response = self.search("milk", todo_list=self.other_list, client=bob)
        self.assertEqual(self.shown(response), ["Milk shake"])
        self.assertNotContains(response, "Buy milk")

    def test_other_users_list_with_search_is_404(self):
        self.add("Buy milk")
        bob = self.client_for(self.other_user)
        response = self.search("milk", client=bob)
        self.assertEqual(response.status_code, 404)

    def test_shared_list_can_be_searched(self):
        self.todo_list.members.add(self.other_user)
        self.add("Buy milk").set_tags(["dairy"])
        self.add("Call home")
        bob = self.client_for(self.other_user)

        response = self.search("milk", client=bob)
        self.assertEqual(self.shown(response), ["Buy milk"])

        response = self.search("dairy", client=bob)
        self.assertEqual(self.shown(response), ["Buy milk"])

    def test_search_keeps_steps_open(self):
        # ?open= (from a step action) and ?q= work together.
        milk = self.add("Buy milk")
        Subtask.objects.create(todo=milk, title="Find a bag")
        self.add("Call home")
        url = f"{self.todo_list.get_absolute_url()}?q=milk&open={milk.pk}"
        response = self.client.get(url)
        self.assertEqual(self.shown(response), ["Buy milk"])
        self.assertContains(response, '<details class="steps" open>', count=1)
        self.assertContains(response, "Find a bag")

    def test_search_query_count_does_not_grow_with_rows(self):
        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(self.search("milk").status_code, 200)
            return len(queries)

        def add_match(n):
            todo = self.add(f"Milk {n}")
            todo.set_tags(["milk", f"tag{n}"])
            Subtask.objects.create(todo=todo, title=f"Step {n}")

        add_match(0)
        with_one = count_queries()
        for n in range(1, 5):
            add_match(n)
        self.assertEqual(count_queries(), with_one)
