"""The list page stays light: a budget in bytes for each plain to-do row.

Per row, not a fixed total, so a change to the page frame (the header, the menu,
a message) does not touch it; only a heavier row does. When a feature has to add
to every row, raise ROW_BUDGET on purpose and say so in the pull request.
"""

from accounts.tests.helpers import LoggedInTestCase
from todos.models import Todo

ROWS = 300

# Measured on 2026-10-11 with this test (cleanups plan): 1,429 bytes per plain to-do
# (no notes, tags or steps), after {% spaceless %} and one form for Done/Undo and
# Delete. Before: 1,924 bytes, and 1,611 with only {% spaceless %}. The budget is the
# measured number plus 5 %.
MEASURED_BYTES_PER_ROW = 1429
ROW_BUDGET = round(MEASURED_BYTES_PER_ROW * 1.05)


class ListPageSizeTests(LoggedInTestCase):
    def page_size(self):
        response = self.client.get(self.todo_list.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        return len(response.content)

    def test_bytes_per_row_stay_light(self):
        empty = self.page_size()
        Todo.objects.bulk_create(
            Todo(todo_list=self.todo_list, title=f"To-do {i:03d}", position=i)
            for i in range(ROWS)
        )
        per_row = (self.page_size() - empty) / ROWS
        self.assertLessEqual(per_row, ROW_BUDGET)
