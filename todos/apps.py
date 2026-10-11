from django.apps import AppConfig


class TodosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "todos"

    def ready(self):
        from django.db import connections
        from django.db.backends.signals import connection_created

        from .sqlite_functions import add_functions

        # Every new SQLite connection gets the Norwegian collation and casefold().
        connection_created.connect(add_functions, dispatch_uid="todos_sqlite_functions")
        # A connection opened before ready() (rare) gets them too. add_functions
        # skips a wrapper that is set up but not open yet (connection is None).
        for connection in connections.all(initialized_only=True):
            add_functions(sender=connection.__class__, connection=connection)
