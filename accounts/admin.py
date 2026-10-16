"""Django's own User and Group admins, with an admin log that keeps no names.

The pages look and work exactly as Django's. Only the log rows change: they
store "user 3", never the username (see todos/admin_log.py). `accounts` comes
after `django.contrib.auth` in INSTALLED_APPS, so Django's admins are
registered first and can be replaced here.
"""

from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group, User

from todos.admin_log import NoNamesInLog

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(NoNamesInLog, auth_admin.UserAdmin):
    pass


@admin.register(Group)
class GroupAdmin(NoNamesInLog, auth_admin.GroupAdmin):
    pass
