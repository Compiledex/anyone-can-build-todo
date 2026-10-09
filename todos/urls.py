from django.urls import path

from . import views

urlpatterns = [
    path("", views.todo_list, name="todo_list"),
    path("lists/new/", views.list_create, name="list_create"),
    path("lists/<int:pk>/", views.list_detail, name="list_detail"),
    path("lists/<int:pk>/add/", views.todo_add, name="todo_add"),
    path("lists/<int:pk>/rename/", views.list_rename, name="list_rename"),
    path("lists/<int:pk>/delete/", views.list_delete, name="list_delete"),
    path("lists/<int:pk>/share/", views.list_share, name="list_share"),
    path(
        "lists/<int:pk>/members/<int:user_id>/remove/",
        views.list_member_remove,
        name="list_member_remove",
    ),
    path("lists/<int:pk>/leave/", views.list_leave, name="list_leave"),
    path("<int:pk>/toggle/", views.todo_toggle, name="todo_toggle"),
    path("<int:pk>/delete/", views.todo_delete, name="todo_delete"),
    path("<int:pk>/edit/", views.todo_edit, name="todo_edit"),
]
