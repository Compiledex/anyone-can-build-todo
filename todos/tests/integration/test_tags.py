"""Tests for the tags of a to-do: setting them on the edit page and showing them."""

from unittest import mock

from django.db import IntegrityError
from django.urls import reverse

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Tag, Todo
from todos.tests.helpers import count_queries


class TagTests(LoggedInTestCase):
    """Tags on a to-do. alice is A, bob is B; each has their own list."""

    def setUp(self):
        super().setUp()
        self.todo = Todo.objects.create(title="Buy milk", todo_list=self.todo_list)
        self.other_todo = Todo.objects.create(
            title="Bob's thing", todo_list=self.other_list
        )

    def edit(self, todo, tag_names, title=None, client=None):
        """Post the edit form for this to-do. The edit form always needs the title."""
        return (client or self.client).post(
            reverse("todo_edit", args=[todo.pk]),
            {"title": title or todo.title, "tag_names": tag_names},
        )

    def tag_names(self, todo):
        return [tag.name for tag in todo.tags.all()]

    def list_page(self):
        return self.client.get(reverse("list_detail", args=[self.todo_list.pk]))

    def test_edit_sets_tags(self):
        self.edit(self.todo, "Work, #home")
        self.assertEqual(self.tag_names(self.todo), ["home", "work"])
        for tag in self.todo.tags.all():
            self.assertEqual(tag.owner, self.user)

    def test_edit_page_shows_current_tags(self):
        self.edit(self.todo, "work, home")
        response = self.client.get(reverse("todo_edit", args=[self.todo.pk]))
        self.assertEqual(response.context["form"]["tag_names"].value(), "home, work")
        self.assertContains(response, 'value="home, work"')

    def test_edit_with_empty_tags_removes_them(self):
        self.edit(self.todo, "work, home")
        self.edit(self.todo, "")
        self.assertEqual(self.tag_names(self.todo), [])

    def test_same_tag_name_is_reused(self):
        second = Todo.objects.create(title="Call home", todo_list=self.todo_list)
        self.edit(self.todo, "work")
        self.edit(second, "Work")
        self.assertEqual(Tag.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(self.todo.tags.get(), second.tags.get())

    def test_bad_tags_show_error_and_change_nothing(self):
        self.edit(self.todo, "work")
        too_many = ", ".join(f"t{n}" for n in range(11))
        response = self.edit(self.todo, too_many, title="A new title")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A to-do can have at most 10 tags.")
        self.assertContains(response, f'value="{too_many}"')
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")
        self.assertEqual(self.tag_names(self.todo), ["work"])

    def test_list_shows_tags_sorted(self):
        self.edit(self.todo, "work, home")
        page = self.list_page().content.decode()
        self.assertIn('<span class="tag">#home</span>', page)
        self.assertLess(page.index("#home"), page.index("#work"))

    def test_list_query_count_does_not_grow_with_tags(self):
        def load():
            self.assertEqual(self.list_page().status_code, 200)

        self.edit(self.todo, "work, home")
        with_one = count_queries(load)
        for n in range(4):
            todo = Todo.objects.create(title=f"Todo {n}", todo_list=self.todo_list)
            self.edit(todo, f"work, tag{n}")
        self.assertEqual(count_queries(load), with_one)

    def test_same_name_for_two_users_is_two_tags(self):
        self.edit(self.todo, "work")
        self.edit(self.other_todo, "work", client=self.client_for(self.other_user))
        self.assertEqual(Tag.objects.filter(name="work").count(), 2)
        self.assertEqual(self.todo.tags.get().owner, self.user)
        self.assertEqual(self.other_todo.tags.get().owner, self.other_user)

    def test_other_users_tags_are_not_shown(self):
        self.edit(self.todo, "secret")
        bob = self.client_for(self.other_user)
        list_page = bob.get(reverse("list_detail", args=[self.other_list.pk]))
        edit_page = bob.get(reverse("todo_edit", args=[self.other_todo.pk]))
        self.assertNotContains(list_page, "secret")
        self.assertNotContains(edit_page, "secret")

    def test_cannot_tag_other_users_todo(self):
        self.edit(self.todo, "work")
        response = self.edit(
            self.todo,
            "hacked",
            title="Hacked",
            client=self.client_for(self.other_user),
        )
        self.assertEqual(response.status_code, 404)
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")
        self.assertEqual(self.tag_names(self.todo), ["work"])
        self.assertFalse(Tag.objects.filter(owner=self.other_user).exists())

    def test_tag_names_are_escaped(self):
        self.edit(self.todo, "<b>x</b>")
        response = self.list_page()
        self.assertContains(response, "#&lt;b&gt;x&lt;/b&gt;")
        self.assertNotContains(response, "<b>x</b>")

    def test_tag_error_rolls_back_title(self):
        # If saving the tags fails, the new title must not be saved either.
        with mock.patch.object(Todo, "set_tags", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.edit(self.todo, "work", title="A new title")
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.title, "Buy milk")

    def test_unused_tag_is_kept(self):
        self.edit(self.todo, "work")
        self.edit(self.todo, "")
        self.assertTrue(Tag.objects.filter(owner=self.user, name="work").exists())

    def test_add_still_works(self):
        response = self.client.post(
            reverse("todo_add", args=[self.todo_list.pk]), {"title": "Call home"}
        )
        self.assertRedirects(response, self.todo_list.get_absolute_url())
        todo = Todo.objects.get(title="Call home")
        self.assertEqual(self.tag_names(todo), [])
