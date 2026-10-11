from django.test import SimpleTestCase

from todos.views import anchors_after_removal


class AnchorsAfterRemovalTests(SimpleTestCase):
    def test_no_rows(self):
        self.assertEqual(anchors_after_removal([]), {})

    def test_one_row_goes_to_the_list(self):
        self.assertEqual(anchors_after_removal([5]), {5: "todos"})

    def test_next_row_else_previous(self):
        self.assertEqual(
            anchors_after_removal([5, 6, 7]),
            {5: "todo-6", 6: "todo-7", 7: "todo-6"},
        )
