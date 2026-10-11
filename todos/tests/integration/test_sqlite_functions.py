"""Every SQLite connection gets the Norwegian collation and casefold().

They are added by the connection_created signal (TodosConfig.ready), so a
connection opened later has them too, not only the one the tests use.
"""

from django.db import connections
from django.test import SimpleTestCase


class NewConnectionTests(SimpleTestCase):
    databases = {"default"}

    def test_a_new_connection_has_the_functions(self):
        connection = connections.create_connection("default")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT casefold('ÆØÅ')")
                self.assertEqual(cursor.fetchone()[0], "æøå")
                cursor.execute("""SELECT 'å' < 'ø' COLLATE "norwegian\"""")
                self.assertEqual(cursor.fetchone()[0], 0)
                cursor.execute("""SELECT 'ø' < 'å' COLLATE "norwegian\"""")
                self.assertEqual(cursor.fetchone()[0], 1)
        finally:
            connection.close()
