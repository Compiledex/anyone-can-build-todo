# Plan: share a list with other users

Status: **approved** — not started. The decisions are in "Decided by the person" at the end.

Builds on: **#17 accounts** (log in, `LoginRequiredMiddleware`, "each user sees only their own
data"), **#10 lists** (a `TodoList` model with an `owner`, and each `Todo` belongs to one list),
and **#4 edit** (a member may edit to-dos). It uses `base.html` from wave 0.

## What this plan uses from earlier waves

These names come from `docs/plans/accounts.md`, `docs/plans/lists.md` and
`docs/plans/edit-todo.md`. **Check the merged code before you start.** If a name is different,
use the merged name; the ideas stay the same.

- `TodoList(owner=ForeignKey(User), name, created_at)`, with `related_name="todo_lists"` on
  `owner` and `get_absolute_url()` (so `redirect(the_list)` goes to the list page).
- `Todo.todo_list = ForeignKey(TodoList, on_delete=CASCADE, related_name="todos")`. #10 removes
  `Todo.owner`. The owner of a to-do is `todo.todo_list.owner`. If the merged code still has a
  `Todo.owner` field, no view may filter to-dos by it any more (a member's to-dos would then be
  hidden from the owner, or the reverse). Remove those filters in step 4.
- **Login:** #17 turns on Django's `LoginRequiredMiddleware`. A *middleware* is code that runs on
  every request. It sends a person who is not logged in to the login page, on every view, unless
  the view is marked `@login_not_required`. So the new views need **no** `@login_required`.
- One template for the list page: `todos/templates/todos/todo_list.html`. It has a small **menu**
  with links to the person's lists. There is no separate "index of lists" page.
- These views exist. Today each one finds its object with the owner:

| View | Address | Method | What it does | Lookup today |
|---|---|---|---|---|
| `todo_list` | `/` | GET | Sends the browser to the person's oldest list, or to `/lists/new/`. | `owner=user` |
| `list_create` | `/lists/new/` | GET, POST | Make a new list. | — (sets `owner=user`) |
| `list_detail` | `/lists/<pk>/` | GET | One list, its to-dos, and the menu of lists. | `owner=user` |
| `list_rename` | `/lists/<pk>/rename/` | GET, POST | Rename a list (GET shows the form). | `owner=user` |
| `list_delete` | `/lists/<pk>/delete/` | GET, POST | Delete a list (GET shows "Are you sure?"). | `owner=user` |
| `todo_add` | `/lists/<pk>/add/` | POST | Add a to-do to a list. | `owner=user` |
| `todo_toggle` | `/<pk>/toggle/` | POST | Mark done / undo. | `todo_list__owner=user` |
| `todo_edit` | `/<pk>/edit/` | GET, POST | Edit a to-do (#4). | `todo_list__owner=user` |
| `todo_delete` | `/<pk>/delete/` | POST | Delete a to-do. | `todo_list__owner=user` |
| `list_clear_completed` | `/lists/<pk>/clear-completed/` | POST | Only if #19 is merged first. | `owner=user` |

## Goal

The owner of a list can share it with another user, by typing that user's **username** (the name
they log in with). That user becomes a **member** of the list. A member can see the list, and
add, mark done, edit and delete its to-dos. The owner can remove a member, and a member can leave.

This changes the rule "I see only my data" into "I see **my lists plus the lists shared with
me**". One helper, `TodoList.objects.visible_to(user)`, holds that rule, and every view that
reads or changes to-dos uses it.

## Decisions

- **Data model: a many-to-many field.** `TodoList.members = ManyToManyField(User,
  related_name="shared_lists", blank=True)`. A *many-to-many field* means: one list can have many
  members, and one user can be a member of many lists. Django makes the extra table by itself. It
  also makes sure the same pair (list, user) is stored only once. We do not need a "role" or a
  "date shared", so we do not write our own table.
- **The owner is never a member.** The owner already sees everything. Sharing with yourself is
  refused with an error. (An admin could still add the owner in the admin. That does no harm:
  `visible_to` uses `distinct()`, and the "Shared with me" menu leaves out the person's own
  lists; see below.)
- **What a member can do:** see the list, and add, toggle, edit (`GET` and `POST`) and delete its
  to-dos, and clear completed, once #19 exists, because that is only "delete done to-dos".
- **What a member can NOT do:** rename the list, delete the list, share it with someone else,
  remove a member, or see the member list. These stay **owner only**, for `GET` and for `POST`.
  Reason: the list belongs to the owner; a member must not be able to make the list disappear, or
  give it to strangers.
- **A member who tries an owner-only action gets 404** ("not found"), the same answer as a
  stranger. It is simple (the owner-only views keep `owner=request.user`, exactly as #10 wrote
  them), and it matches the rule from #17: 404, not 403.
- **The menu on the list page has two parts:** "My lists" (`owner=user`) and "Shared with me"
  (`members=user`), each shared list with its owner's name, for example "Groceries (alice)". The
  owner's name is needed, because bob may have his own list called "Groceries" too (#10 only
  forbids the same name for the **same** owner).
- **`/` (`todo_list`) prefers your own lists.** It goes to your oldest own list. If you have no own
  list, it goes to the oldest list shared with you. If there is none, it goes to `/lists/new/`.
  Reason: without this, a person who deleted their own lists could never reach a shared list.
- **How a member leaves:** a "Leave this list" button on the list page, for members only. It sends
  `POST /lists/<pk>/leave/`. The member is removed and goes to `/` (`todo_list`). The to-dos
  they added stay in the list. The owner cannot "leave" their own list (404).
- **How the owner removes a member:** the owner sees the member list on the list page, with a
  "Remove" button next to each name. It sends `POST /lists/<pk>/members/<user_id>/remove/`. The
  address uses the user's number (`id`), not the username. A user who is not a member of **this**
  list gives 404, even if the user exists (see the code below).
- **What a member sees:** on the list page, the line "Shared by <owner's username>", and the Leave
  button. They do not see the other members, and they do not see Rename or Delete.
- **The share form is on the list page, and the share view only accepts `POST`.** After the
  `POST`, the browser always goes back to the list page, with a message: "Shared with bob." or the
  error, for example "No user with that username.". We do not show the form again with the typed
  name: the list page has many other parts, and a username is short to type again. This keeps the
  view small.
- **Does sharing reveal whether a username exists? Yes, and we accept it.** Reasons:
  - It cannot really be hidden. The owner sees the member list right after sharing, so a name
    that appears there exists.
  - The sign-up page from #17 (Django's `UserCreationForm`) already says "A user with that
    username already exists".
  - Only a logged-in owner of a list can try, only with `POST`.
  - A username is not a secret. The password is.

  What we **do** keep hidden: whether a *list* or a *to-do* exists (always 404 for strangers).
  Limiting how many tries per minute (rate limiting) is not part of this task.
- **Username match is exact**, like Django's login: `User.objects.get(username=...)`. A user with
  `is_active=False` (switched off in the admin) is treated as "no user with that username".
- **Sharing twice with the same user** adds nothing and shows "bob is already a member.".
- **Messages** use Django's `messages` framework (short notes shown once on the next page). They
  are shown by one block in `base.html`. #19 clear completed also needs that block: whoever merges
  first adds it, once, the other reuses it.
- **When the owner deletes the list**, Django deletes the member rows too. When a user account is
  deleted, their memberships are deleted too. No extra code.
- **Tags (#11) on a shared to-do belong to the list's owner.** #11 creates tags with the to-do's
  owner (`todo.todo_list.owner`), never with `request.user`. So when bob types a tag on alice's
  to-do, the tag is made in alice's tags. This is the safe answer: bob's own tags never appear on
  alice's list, and alice keeps one set of tags. Whichever of #11 and #18 merges second adds the
  test for it (see "Tests").

## The one helper

In `todos/models.py`, a *QuerySet* (a Django object that stands for a database query, and can be
filtered more) with one method:

```python
from django.db.models import Q


class TodoListQuerySet(models.QuerySet):
    def visible_to(self, user):
        """The lists this user owns, plus the lists shared with them."""
        return self.filter(Q(owner=user) | Q(members=user)).distinct()


class TodoList(models.Model):
    ...
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="shared_lists", blank=True
    )

    objects = TodoListQuerySet.as_manager()
```

**Why `.distinct()` matters.** `Q(members=user)` joins the members table: the database makes one
row for each member of each list. A list owned by Alice and shared with Bob and Carol becomes
**two rows** for Alice. Without `distinct()`, `get_object_or_404` raises
`MultipleObjectsReturned`, which is a server error (500): Alice can no longer open her own list.
(Checked by running it: two rows without `distinct()`, `MultipleObjectsReturned`; one row with
it.) The menu does not show this, because the menu does not use `visible_to` (see
`render_list_page` below). There is a test for this.

How views use it:

- A list: `get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)`
- A to-do: `get_object_or_404(Todo, pk=pk, todo_list__in=TodoList.objects.visible_to(request.user))`

To keep the second line short and the same everywhere, add one small function in
`todos/views.py`, built on the helper:

```python
def get_visible_todo(user, pk):
    return get_object_or_404(Todo, pk=pk, todo_list__in=TodoList.objects.visible_to(user))
```

**Do not write** `Todo.objects.filter(Q(todo_list__owner=user) | Q(todo_list__members=user))`.
It has the same join problem, without `distinct()`. Always go through `visible_to`.

**The to-dos of one list** are always read as `the_list.todos.all()`, after the list was found
with `visible_to`. Never `Todo.objects.filter(todo_list__owner=request.user)`: that would hide a
shared list's to-dos from its members.

Owner-only views do **not** use the helper. They keep
`get_object_or_404(TodoList, pk=pk, owner=request.user)`. This is a deliberate exception to the
shared rule "every view finds lists with `visible_to`": the rule is for views that read a list or
change its to-dos. Rename, delete, share and remove-member must stay owner only, and the stricter
filter gives a member the same 404 as a stranger.

### The three new views

```python
@require_POST
def list_share(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)  # owner only
    form = ShareForm(request.POST, todo_list=the_list)
    if form.is_valid():
        user = form.cleaned_data["username"]  # clean_username returns the User
        the_list.members.add(user)
        messages.success(request, f"Shared with {user.username}.")
    else:
        messages.error(request, form.errors["username"][0])
    return redirect(the_list)


@require_POST
def list_member_remove(request, pk, user_id):
    the_list = get_object_or_404(TodoList, pk=pk, owner=request.user)  # owner only
    member = get_object_or_404(the_list.members, pk=user_id)  # only a member of THIS list
    the_list.members.remove(member)
    messages.success(request, f"{member.username} was removed.")
    return redirect(the_list)


@require_POST
def list_leave(request, pk):
    the_list = get_object_or_404(TodoList, pk=pk, members=request.user)  # members only
    the_list.members.remove(request.user)
    messages.success(request, "You left the list.")
    return redirect("todo_list")
```

- In `list_member_remove`, the member is looked up **inside `the_list.members`**, never with
  `get_object_or_404(User, pk=user_id)`. So a user id that is not a member of this list is 404,
  and the answer does not tell the owner whether that user id exists at all.
- The list is always found **first**, with the owner. So bob, who is only a member, gets 404
  before anything else runs.
- `messages` and the f-strings: Django templates escape the username when they show it, so a
  username with `<` in it cannot break the page.

`ShareForm` in `todos/forms.py` (a plain `forms.Form`, not a `ModelForm`, because it does not save
a model):

```python
class ShareForm(forms.Form):
    username = forms.CharField(max_length=150)

    def __init__(self, *args, todo_list, **kwargs):
        super().__init__(*args, **kwargs)
        self.todo_list = todo_list

    def clean_username(self):
        name = self.cleaned_data["username"]
        try:
            user = User.objects.get(username=name, is_active=True)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username.")
        if user == self.todo_list.owner:
            raise forms.ValidationError("You already own this list.")
        if self.todo_list.members.filter(pk=user.pk).exists():
            raise forms.ValidationError(f"{user.username} is already a member.")
        return user
```

Use `get_user_model()` for `User`, as Django recommends.

### Every view, and what it uses after this change

| View | Before | After |
|---|---|---|
| `todo_list` | oldest list with `owner=user` | oldest own list; if none, oldest of `visible_to(user)`; if none, `/lists/new/` |
| `list_create` | sets `owner=user` | no change |
| `list_detail` | `owner=user` | **`visible_to(user)`**; context from `render_list_page` (`is_owner`, the member list and share form only for the owner, the menu in two parts) |
| `list_rename` | `owner=user` | no change (owner only, `GET` and `POST`) |
| `list_delete` | `owner=user` | no change (owner only, `GET` and `POST`) |
| `todo_add` | list with `owner=user` | **list from `visible_to(user)`**; an invalid form shows the page with `render_list_page` |
| `todo_toggle` | `todo_list__owner=user` | **`get_visible_todo`** |
| `todo_edit` | `todo_list__owner=user` | **`get_visible_todo`**, for `GET` and `POST` |
| `todo_delete` | `todo_list__owner=user` | **`get_visible_todo`** |
| `list_clear_completed` (#19) | list with `owner=user` | **list from `visible_to(user)`** (only if #19 is already merged) |
| `list_share` (new) | — | owner only |
| `list_member_remove` (new) | — | owner only, then member of this list |
| `list_leave` (new) | — | `members=request.user` |

**One function builds the list page.** #10 lists already has `render_list_page(request, the_list,
form)` in `todos/views.py`, used by `list_detail` and by `todo_add` on an invalid form. Sharing
does not add a second function: it adds its keys to that one.

```python
def render_list_page(request, the_list, form):
    is_owner = the_list.owner_id == request.user.id
    return render(request, "todos/todo_list.html", {
        "the_list": the_list,
        "todos": the_list.todos.all(),
        "my_lists": request.user.todo_lists.all(),
        "form": form,
        # Added by #18:
        "is_owner": is_owner,
        "members": the_list.members.all() if is_owner else None,
        "share_form": ShareForm(todo_list=the_list) if is_owner else None,
        "shared_lists": request.user.shared_lists.exclude(owner=request.user)
        .select_related("owner"),
    })
```

- Keep every key the merged code already has (for example `done_count` from #19).
- **`todo_add` already uses this function** (from #10) when it shows the page again after an
  invalid form. Never build a second context by hand: a member who sends a bad to-do must get a
  page built with the same rules. There is a test.
- The template shows the owner parts only `{% if is_owner %}`, never `{% if members %}`.
- `shared_lists` leaves out the person's own lists. Normally the owner is never a member, but an
  admin could add them in the admin; then the list would be in the menu twice.

Wave 3 runs at the same time as #5 description, #9 priority, #11 tags and #19 clear completed.
**Whichever of them merges after this plan** must use `visible_to` / `get_visible_todo` for any
view that reads or changes to-dos. #5 and #9 only add fields to existing views, so they get this
for free. #19 adds a view: `docs/plans/clear-completed.md` already says what to do in both
orders. #11 is covered by the tags decision above.

## Not part of this task

- Roles such as "can view but not edit". Every member can edit.
- Moving ownership to another user.
- Invitations that the other user must accept. Sharing takes effect at once.
- Email or other notifications when a list is shared. (#7 reminders already says only the owner
  gets the email.)
- Rate limiting the share form.
- Sharing one to-do instead of a whole list.
- Showing who added or changed a to-do.
- Members seeing each other. Easy to add later.
- Moving a to-do to another list. #10 and #4 do not offer it, so `TodoForm` has no list field. If a
  later task adds one, its choices must be `visible_to(user)`, and that task tests it.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | `TodoListQuerySet` with `visible_to`; `members` field on `TodoList`; `objects = TodoListQuerySet.as_manager()`. |
| `todos/migrations/000X_todolist_members.py` | Made by `makemigrations`. Adds one new table (list id, user id). Existing lists get no members, so nothing changes for anyone. It can be run backwards: the table is dropped. |
| `todos/forms.py` | `ShareForm` (see above). |
| `todos/views.py` | `get_visible_todo`; `render_list_page` (used by `list_detail` and by `todo_add` on an invalid form); the view changes in the table above; three new views: `list_share`, `list_member_remove`, `list_leave`. Each new view has `@require_POST`. No `@login_required`: the middleware from #17 does it. |
| `todos/urls.py` | `lists/<int:pk>/share/` (`list_share`), `lists/<int:pk>/members/<int:user_id>/remove/` (`list_member_remove`), `lists/<int:pk>/leave/` (`list_leave`). |
| `todos/templates/todos/todo_list.html` (from #10) | Menu in two parts. Owner: share form, member list with Remove buttons, Rename/Delete links. Member: "Shared by …" and the Leave button. Every new form has `{% csrf_token %}`. New colors use the CSS variables from wave 0. |
| `todos/templates/base.html` | The messages block, if #19 did not add it yet. |
| `todos/admin.py` | `filter_horizontal = ["members"]` on the `TodoList` admin, so members can be seen and changed there. |
| `AGENTS.md`, `README.md` | Describe sharing, the `visible_to` rule ("every view that reads or changes a to-do uses it"), the new addresses, and the test numbers. |

Hiding the Rename/Delete links and the share form from a member is only for a clean page. **The
security is in the views**, not in the template. The tests check the views.

## Tests

Security tests are the most important part. They go in a new file
`todos/tests/integration/test_sharing.py` (Django test client, real test database). The helper
needs the database, so it is tested there too, not in `unit/`. No new unit tests.

Set-up for most tests (`setUpTestData`): three users — **alice** (owner), **bob** (member),
**carol** (stranger, logged in, but not a member). Alice owns the list "Groceries" with the to-do
"Milk", shared with bob. Bob owns his own list "Bob's stuff". Carol owns her own list "Carol's
stuff". Each test logs in with `self.client.force_login`.

Two rules for every test here, so that a test cannot pass while the feature is broken:

- **"Nothing changed"** means: the test reloads the objects from the database
  (`refresh_from_db()` or `.exists()`) and checks them. A status code alone is not enough.
- **"Does not contain" needs a "does contain" next to it.** For example, "carol's page does not
  contain Groceries" also checks that carol's page **does** contain "Carol's stuff". Otherwise an
  empty or broken page would pass the test.

### Integration — the helper (`VisibleToTests`)

| Test | What it checks |
|---|---|
| `test_owner_sees_own_list` | Alice's `visible_to` contains Groceries. |
| `test_member_sees_shared_list` | Bob's contains Groceries and "Bob's stuff". |
| `test_stranger_does_not_see_list` | Carol's does not contain Groceries, and does contain her own list. |
| `test_list_shared_with_two_members_appears_once` | Share with bob **and** carol: Alice's `visible_to` has Groceries exactly once (`count() == 1`); alice's list page is 200, not 500; alice's add to Groceries works (the add view uses `get_object_or_404` on `visible_to` too). Only the **owner** gets the double rows (each member row matches `owner=alice`), so the test must act as alice. **Shown failing first by removing `distinct()`** (the count is 2 and the page is 500). |
| `test_owner_added_as_member_is_in_menu_once` | Add alice to Groceries' `members` by hand (what the admin could do). Alice's page has "Groceries" under "My lists", and does not have "Groceries (alice)". |
| `test_former_member_does_not_see_list` | After `members.remove(bob)`, Bob's does not contain it, and still contains "Bob's stuff". |

### Integration — what a member CAN do (`MemberCanTests`)

| Test | What it checks |
|---|---|
| `test_member_sees_list_page` | Bob gets 200 on `list_detail`, sees "Milk", "Shared by alice" and the Leave button. |
| `test_member_sees_list_in_menu` | On bob's own list page, the menu has "Groceries (alice)" under "Shared with me", and "Bob's stuff" under "My lists". |
| `test_member_can_add` | Bob adds "Eggs": it is in Groceries. |
| `test_member_can_toggle` | Bob toggles "Milk": it is done; the browser goes back to Groceries. |
| `test_member_can_edit` | Bob's `GET` on edit "Milk" is 200; his `POST` "Oat milk" is saved. |
| `test_member_can_delete_todo` | Bob deletes "Milk": it is gone. |
| `test_member_invalid_add_shows_member_page` | Only if `todo_add` shows the page again on an invalid form. Bob posts a title of 201 characters to Groceries: 200, the page has "Shared by alice" and the Leave button, and has no share form and no Remove button. Nothing was added. |
| `test_member_tags_go_to_list_owner` | Only if #11 is merged: bob sets tag "fresh" on "Milk": the tag's owner is alice, and bob has no tag. |

If #19 is already merged, also add the two sharing tests from `docs/plans/clear-completed.md`.

### Integration — what a member can NOT do (`MemberCannotTests`)

Each is 404 **and** nothing changed.

| Test | What it checks |
|---|---|
| `test_member_cannot_rename_list` | `GET` and `POST` on rename are 404. Name is still "Groceries". |
| `test_member_cannot_delete_list` | `GET` and `POST` on delete are 404. The list and "Milk" still exist. |
| `test_member_cannot_share_further` | Bob shares with carol: 404, carol is not a member. |
| `test_member_cannot_remove_other_member` | With carol also a member, bob removes carol: 404, carol is still a member. |
| `test_member_cannot_remove_owner` | Bob posts alice's id to remove: 404, bob is still a member, the list is unchanged. |
| `test_member_does_not_see_owner_parts` | Carol is also a member. Bob's page has no share form, no Remove button, no Rename/Delete links, and not the name "carol". Alice's page **does** have all of them, and "carol" (the "does contain" check). |

### Integration — a stranger (`StrangerTests`)

Carol is logged in but not a member. Each is 404 **and** nothing changed.

| Test | What it checks |
|---|---|
| `test_stranger_cannot_see_list` | `list_detail` is 404; the response does not contain "Milk". |
| `test_stranger_menu_does_not_show_list` | Carol's own page does not contain "Groceries", and does contain "Carol's stuff". |
| `test_stranger_cannot_add` | No new to-do in Groceries. |
| `test_stranger_cannot_toggle` | "Milk" is still not done. |
| `test_stranger_cannot_edit` | `GET` and `POST` are 404. Title is still "Milk". |
| `test_stranger_cannot_delete_todo` | "Milk" still exists. |
| `test_stranger_cannot_share` | Carol shares Groceries with herself: 404, she is not a member. |
| `test_stranger_cannot_leave` | 404, bob is still a member. |
| `test_stranger_cannot_remove_member` | Bob is still a member. |

### Integration — sharing (`ShareTests`)

| Test | What it checks |
|---|---|
| `test_owner_shares_by_username` | Alice shares Groceries with "carol": carol is a member; redirect to the list; message "Shared with carol.". |
| `test_unknown_username_is_refused` | "nobody": no member added; message "No user with that username.". |
| `test_inactive_user_is_refused` | A user with `is_active=False`: the same message as unknown, no member added. |
| `test_cannot_share_with_yourself` | "alice": error message; alice is not in `members`. |
| `test_sharing_twice_adds_one_member` | Share with "bob" again: `members.count()` is still 1; message "bob is already a member.". |
| `test_username_is_exact` | "BOB" does not match "bob": no member added. |
| `test_get_does_not_share` | `GET` on share is 405, no member added. |

### Integration — leave and remove (`LeaveRemoveTests`)

| Test | What it checks |
|---|---|
| `test_member_leaves` | Bob posts leave: not a member; redirected to `todo_list`; "Milk" still exists. |
| `test_after_leaving_member_gets_404` | After leaving, bob gets 404 on `list_detail`, on toggle "Milk" (still not done), and on leave again. |
| `test_owner_cannot_leave_own_list` | Alice posts leave: 404, the list still exists, bob is still a member. |
| `test_owner_removes_member` | Alice removes bob: bob is not a member; bob's account and "Bob's stuff" still exist. |
| `test_after_removal_member_gets_404` | Bob gets 404 on `list_detail` and on add. |
| `test_remove_user_who_is_not_member_is_404` | Alice removes carol (exists, not a member), and alice removes herself (her own id): each 404, bob is still a member, the list still exists. |
| `test_remove_unknown_user_id_is_404` | Alice removes user id 999999: 404, the same answer as the test above. |
| `test_deleting_list_removes_access` | Alice deletes Groceries: bob's menu no longer has it; no member rows are left for it. |
| `test_get_does_not_leave_or_remove` | `GET` on leave and on remove is 405, nothing changed. |

### Integration — home (`HomeTests`, in `test_sharing.py`)

| Test | What it checks |
|---|---|
| `test_home_prefers_own_list` | Groceries is older than "Bob's stuff". Bob's `/` still goes to "Bob's stuff". |
| `test_home_goes_to_shared_list_without_own_list` | Bob deletes "Bob's stuff": `/` goes to Groceries, not to `/lists/new/`. |
| `test_home_never_goes_to_a_list_you_cannot_see` | Carol deletes "Carol's stuff": `/` goes to `/lists/new/`, not to Groceries. Then bob deletes "Bob's stuff" and leaves Groceries: `/` goes to `/lists/new/` too. Needed because Groceries is the **oldest** list of all: a wrong fallback such as `TodoList.objects.first()` would pass the test above, and only fails here. |

### Integration — logged out (`LoggedOutTests`)

| Test | What it checks |
|---|---|
| `test_new_addresses_need_login` | `POST` to share, leave and remove without logging in: each redirects to the login page, nothing changed. One test, a loop with `subTest`. |

### CUJ — `todos/tests/cuj/test_journeys.py`

One journey, because sharing is a story between two people. It uses the login helper from #17.

| Test | What it checks |
|---|---|
| `test_share_a_list` | Alice logs in, makes "Groceries", shares it with "bob" and sees bob in the member list. In a new browser context (a separate set of cookies, like a second browser), bob logs in, sees "Groceries (alice)" under "Shared with me", opens it, adds "Eggs". Alice reloads and sees "Eggs". Bob clicks "Leave this list" and Groceries is gone from his menu. |

### The full matrix: who may do what

This table is the check that no address was forgotten. Each cell says the answer, and which test
checks it. Words used:

- **Ex-member**: bob after he left, or after alice removed him. Both leave the same data: no row
  in the members table, exactly like a stranger. So the stranger tests cover the ex-member cells.
  `test_after_leaving_member_gets_404` and `test_after_removal_member_gets_404` check that the row
  is really gone (one read and one change each).
- **#10**, **#4**, **#17**, **#19**: the test is in `lists.md`, `edit-todo.md`, `accounts.md` or
  `clear-completed.md`; it keeps passing after this change.
- A `GET` on a `POST`-only address is **405** for every logged-in person, before the list is looked
  up. It says nothing about whether the list exists, because it is the same for every number.
- **Anonymous** (not logged in) is always a redirect to the login page, for every address and
  method: #17's `test_only_login_and_signup_are_open` checks that no view except login, logout and sign-up is open, and
  `test_new_addresses_need_login` checks the three new ones change nothing.

| Address, method | Owner (alice) | Member (bob) | Ex-member | Stranger (carol) |
|---|---|---|---|---|
| `/` GET | own oldest list (#10) | own oldest list, else oldest shared (`HomeTests`) | own list or `/lists/new/`, never the old list (`test_home_never_goes_to_a_list_you_cannot_see`) | the same test |
| `/lists/new/` GET, POST | makes an own list (#10) | the same (#10) | the same (#10) | the same (#10) |
| `list_detail` GET | 200, owner parts (`test_member_does_not_see_owner_parts`) | 200, member parts (`test_member_sees_list_page`) | 404 (`test_after_leaving…`, `test_after_removal…`) | 404 (`test_stranger_cannot_see_list`) |
| `list_rename` GET, POST | works (#10) | 404 (`test_member_cannot_rename_list`) | 404 (as stranger) | 404 (#10 `test_cannot_rename_someone_elses_list`) |
| `list_delete` GET, POST | works, members lose access (`test_deleting_list_removes_access`) | 404 (`test_member_cannot_delete_list`) | 404 (as stranger) | 404 (#10 `test_cannot_delete_someone_elses_list`) |
| `todo_add` POST | works (#10) | works (`test_member_can_add`) | 404 (`test_after_removal…`) | 404 (`test_stranger_cannot_add`) |
| `todo_toggle` POST | works (#10) | works (`test_member_can_toggle`) | 404 (`test_after_leaving…`) | 404 (`test_stranger_cannot_toggle`) |
| `todo_edit` GET, POST | works (#4) | works (`test_member_can_edit`) | 404 (as stranger) | 404 (`test_stranger_cannot_edit`) |
| `todo_delete` POST | works (#10) | works (`test_member_can_delete_todo`) | 404 (as stranger) | 404 (`test_stranger_cannot_delete_todo`) |
| `list_clear_completed` POST (#19) | works (#19) | works (#19 `test_member_can_clear_shared_list`) | 404 (as stranger) | 404 (#19 `test_stranger_cannot_clear`) |
| `list_share` POST | works or a message (`ShareTests`) | 404 (`test_member_cannot_share_further`) | 404 (as stranger) | 404 (`test_stranger_cannot_share`) |
| `list_leave` POST | 404 (`test_owner_cannot_leave_own_list`) | works (`test_member_leaves`) | 404 (`test_after_leaving…`) | 404 (`test_stranger_cannot_leave`) |
| `list_member_remove` POST, a member's id | works (`test_owner_removes_member`) | 404 (`test_member_cannot_remove_other_member`) | 404 (as stranger) | 404 (`test_stranger_cannot_remove_member`) |
| `list_member_remove` POST, the owner's id | 404 (`test_remove_user_who_is_not_member_is_404`) | 404 (`test_member_cannot_remove_owner`) | 404 (as stranger) | 404 (as above) |
| `list_member_remove` POST, a non-member or unknown id | 404 (`test_remove_user_who_is_not_member_is_404`, `test_remove_unknown_user_id_is_404`) | 404 (the list lookup fails first) | 404 | 404 |

Things a stranger could try to learn, and the answer:

- **Does list 7 or to-do 7 exist?** No: every address gives the same 404 for "exists, not yours"
  and "does not exist".
- **Is user 12 a member of list 7?** No: only the owner reaches the member lookup.
- **Does the username "dave" exist?** Yes, for an owner, through the share message. Accepted; see
  "Decisions".
- **A member can still learn**: the owner's username, the list name, and every to-do in it. That
  is what sharing means. A member who leaves keeps nothing; the to-dos they added stay with the
  owner.

Races (two requests at the same moment), checked by reading Django's code:

- **Leave and remove at once:** `members.remove()` of a row that is already gone does nothing. No
  error.
- **Sharing twice at once:** `members.add()` uses "insert, ignore if it already exists" for a
  Django-made table, so the second one adds nothing. No error.
- **The owner deletes the list while a member adds a to-do:** the add can fail with a database
  error (500) at that exact moment. This is very rare, no data is wrong, and we accept it.
- **The owner removes a member who has the edit page open:** the member's Save gives 404. That is
  correct.

### Count

Integration: 47 new tests (plus 1 if `todo_add` shows the page again on an invalid form, plus 1 if
#11 is merged, plus 2 if #19 is merged). CUJ: 1 new. No new unit tests. Update the numbers in `README.md` after counting the real tests.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

1. **Check the merged code.** Read `todos/models.py`, `todos/views.py` and `todos/urls.py`. Fix
   the table "What this plan uses from earlier waves" if a name is different.
2. **Tests first.** Write `test_sharing.py`. Run `make test`. Most fail because `members` and the
   new addresses do not exist. Some "cannot" tests pass already (a stranger already gets 404). Say
   this in the pull request instead of pretending they were shown failing.
3. **Model.** Add `TodoListQuerySet`, `visible_to`, `members` and `objects` to `todos/models.py`.
4. **Migration.** `uv run python manage.py makemigrations`, then `uv run python manage.py migrate`.
   Never edit the file by hand.
5. **Switch the existing views** to the helper (the table above): `todo_list`, `list_detail`,
   `todo_add`, `todo_toggle`, `todo_edit`, `todo_delete` (and `list_clear_completed` if it
   exists). Add `get_visible_todo` and `render_list_page`, and use the latter in `list_detail`
   and in the invalid-form path of `todo_add`. Run the tests: the "member can" and helper tests
   now pass.
6. **Show `distinct()` matters.** Remove it once, run
   `test_list_shared_with_two_members_appears_once`, see it fail, put it back.
7. **Form.** Add `ShareForm` to `todos/forms.py`.
8. **New views and addresses.** `list_share`, `list_member_remove`, `list_leave` in
   `todos/views.py`; their paths in `todos/urls.py`.
9. **Templates.** Update `todo_list.html`. Add the messages block to `base.html` if it is missing.
10. **Admin.** `filter_horizontal = ["members"]`.
11. **CUJ.** Add `test_share_a_list`.
12. **Search for missed views.** Run `grep -rn "owner" todos/ --include="*.py"` (this also finds
    `todo_list__owner`). Every match in a view or form must be one of: an owner-only view from the
    table (`list_rename`, `list_delete`, `list_share`, `list_member_remove`), `list_create`, the
    first step of `todo_list`, `is_owner` and `exclude(owner=…)` in `render_list_page`,
    `ShareForm`'s "you already own this list" check, `TodoListForm.clean_name` (#10), and
    `set_tags` (#11, uses `todo_list.owner` on purpose). Anything else is a bug. Also check
    every `render(` of `todo_list.html`: each must use `render_list_page`.
13. **Docs.** `AGENTS.md`: the file table, the addresses, and a new rule: "A view that reads or
    changes a list or its to-dos finds the list with `TodoList.objects.visible_to(user)`, or the
    to-do with `get_visible_todo`. Only rename, delete, share and remove-member use
    `owner=request.user`." `README.md`: the test numbers.
14. **Before the commit.** `make check`. Then `make run`, make two users with the sign-up page,
    and try it by hand in two browser windows (one normal, one private).

## Open questions

None that block the work. One small choice can be changed later without risk:

1. **Should members see each other?** This plan says no, to keep it small.

## Review

What the review changed, and why:

- Used the real names from `lists.md` (`/<pk>/toggle/`, one template `todo_list.html` with a
  menu); the draft invented `list_index`, `list_index.html` and `list_detail.html`, which #10 does
  not make.
- `/` (`todo_list`) now falls back to a shared list; otherwise a member with no own list could not
  reach it.
- Removed `@login_required`: #17 uses `LoginRequiredMiddleware`, so the decorator is not needed.
- Wrote the three new views as code, so member removal looks the user up inside `the_list.members`
  (no IDOR, and no hint whether a user id exists); added a test for an unknown user id.
- Decided how share errors are shown (redirect plus a message); the draft did not say how a
  POST-only view shows form errors.
- Rename and delete have `GET` pages in #10, and edit has a `GET` page in #4: the tests now check
  `GET` as well as `POST` for members and strangers.
- Added a "does contain" check next to every "does not contain" check, so an empty page cannot
  make a security test pass.
- Warned against `Q(todo_list__owner=...) | Q(todo_list__members=...)` on `Todo` (duplicate rows)
  and against reading to-dos by owner instead of through the list.
- Shared lists show the owner's name in the menu, because #10 allows two people to have a list with
  the same name.
- Dropped the test for moving a to-do to a stranger's list: #10 and #4 add no list field.
- Decided the tags question (#11): tags on a shared to-do belong to the list owner, as `tags.md`
  already does; one test if #11 is merged.
- Linked #19 to `clear-completed.md`, which already says what to do in both merge orders, and the
  shared messages block in `base.html`.
- Widened the step-12 search to all `.py` files in `todos/` and listed the allowed matches.
- Removed the "default list" open question: #10 has no undeletable default list.
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Second review

What the second review changed, and why (checked by running the queries on Django 5.2 + SQLite):

- Checked: `visible_to` with `distinct()` works with `get_object_or_404` and inside
  `todo_list__in=` (a `SELECT DISTINCT` sub-query); without `distinct()` the owner gets two rows
  and `MultipleObjectsReturned`; `get_object_or_404(the_list.members, pk=user_id)` gives 404 for
  the owner's id, a non-member and an unknown id. The first review's code is correct.
- Fixed the "why `distinct()`" text: the menu cannot show a list twice (it does not use
  `visible_to`); the real harm is a 500 for the **owner**. The test now acts as alice and no
  longer checks the menu.
- Added `render_list_page`, used by `list_detail` **and** by `todo_add` when it shows the page
  again after an invalid form (wave 0, #6, #9), so a member's error page is built with the same
  rules; plus `test_member_invalid_add_shows_member_page`.
- "Shared with me" leaves out the person's own lists (an admin could add the owner as a member);
  plus `test_owner_added_as_member_is_in_menu_once`.
- Added `test_home_never_goes_to_a_list_you_cannot_see`: Groceries is the oldest list, so the old
  home test would pass with a wrong `TodoList.objects.first()` fallback.
- `test_member_does_not_see_owner_parts` now also checks that a member does not see other members.
- Removing the owner's own id, and leaving twice, are now in the tests.
- The step-12 search listed too few allowed `owner` matches (`ShareForm`, `is_owner`,
  `TodoListForm`, `set_tags`); fixed, and added "every render of `todo_list.html` uses
  `render_list_page`".
- Added the full matrix (role × address × method), what a stranger can learn, and the races.
- Count: 47 integration tests (was 45), plus the conditional ones.
- Orchestrator pass: no `list_page_context`; sharing adds its keys to #10's `render_list_page` (context key `the_list`, not `todo_list`).

## Decided by the person (2026-10-09)

The plan is **approved**.

- Members do not see each other. Only the owner sees the member list.
