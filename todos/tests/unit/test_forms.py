from datetime import date

from django.test import SimpleTestCase

from todos.forms import NoteField, TodoForm
from todos.models import Todo


class TodoFormTests(SimpleTestCase):
    def test_due_date_input_is_a_date_picker_with_the_saved_date(self):
        todo = Todo(title="x", due_date=date(2030, 1, 15))
        html = str(TodoForm(instance=todo)["due_date"])
        self.assertIn('type="date"', html)
        self.assertIn('value="2030-01-15"', html)

    def test_note_field_turns_crlf_into_lf(self):
        self.assertEqual(NoteField().clean("a\r\nb"), "a\nb")
