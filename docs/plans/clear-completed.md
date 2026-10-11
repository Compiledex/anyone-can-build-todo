# Plan: clear all completed to-dos with one click (#19)

Status: **done** (2026-10-09, PR #12). The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (`TodoForm`, `_todo_item.html`, CSS variables, the shared `base.html`), #17
accounts, #10 lists (`docs/plans/lists.md`). It runs in the same wave as #18 sharing, #11 tags,
#5 description and #9 priority; see "Working next to other wave 3 features".

## Goal

On a list page, a person can delete all the to-dos in that list that are marked done, in one
action. The to-dos that are not done stay. Other lists, and lists the person may not see, are
never touched.

## Words used in this plan

- **Completed** or **done**: a to-do with `done=True`.
- **Bulk delete**: deleting many rows with one database command, `QuerySet.delete()`.
- **404**: the "page not found" answer. We give 404, not 403 ("forbidden"), for another user's
  list, so a person cannot find out which lists exist.

## What this plan uses from #10 (lists)

These names come from `docs/plans/lists.md`. If the merged #10 uses other names, use those; the
logic does not change.

- A model `TodoList` with an `owner` field, and `get_absolute_url()` (so `redirect(todo_list)`
  goes to the list page).
- `Todo.todo_list`: a `ForeignKey` to `TodoList`, with `related_name="todos"`.
- The list page is the URL `lists/<int:pk>/`, name `list_detail`. The URL parameter is always
  called `pk`. The template is still `todos/templates/todos/todo_list.html`.
- Views find a list with `get_object_or_404(TodoList, pk=pk, owner=request.user)`. Every view
  needs a login through `LoginRequiredMiddleware` (from #17), so no view has a login decorator.

## Decisions

- **The address belongs to one list:** `POST /lists/<int:pk>/clear-completed/`, URL name
  `list_clear_completed` (like `list_rename` and `list_delete`, because it acts on a list). The
  list id is in the address, so the view never has to guess "the current list".
- **POST only** (`@require_POST`). A `GET` gets `405`, and deletes nothing.
- **Safety comes from two lines.** The view first gets the list the person may change (else 404).
  Then it deletes with `todo_list.todos.filter(done=True).delete()`. This filter is the whole
  rule: only this list, only done. It never reads to-do ids from the form, so a changed form
  cannot point at other to-dos.
- **Who may clear: the same people who may delete a to-do in this list.** Before sharing (#18)
  that is the owner. After #18, it is the owner **and members**, as `docs/plans/sharing.md`
  already says ("clear completed ... is only delete to-dos"). See "Working next to other wave 3
  features" for which line to use.
- **A confirm step, without JavaScript.** Deleting many to-dos at once cannot be undone, so the
  person must click twice. We use the HTML `<details>` element. It opens and closes in the
  browser with no JavaScript:

  ```html
  {% if done_count %}
    <details class="clear-completed">
      <summary>Clear completed ({{ done_count }})</summary>
      <form method="post" action="{% url 'list_clear_completed' the_list.pk %}">
        {% csrf_token %}
        <p>Delete {{ done_count }} done to-do{{ done_count|pluralize }}? This cannot be undone.</p>
        <button type="submit">Yes, delete them</button>
      </form>
    </details>
  {% endif %}
  ```

  The first click opens the box. The second click, on "Yes, delete them", sends the `POST`. We do
  not use a separate confirm page: it would need one more view, one more URL and one more
  template, for the same result.
- **The block goes below the list**, so it is not the first thing a person clicks.
- **The button is hidden when nothing is done.** `render_list_page` (#10, which builds the list
  page for `list_detail` and for an invalid add) counts the done to-dos of this list:
  `"done_count": the_list.todos.filter(done=True).count()`. If it is 0, the `<details>` is
  not in the page at all. The number is also in the button, so the person sees what will go.
- **`done_count` always counts the whole list**, never a searched or filtered part of it. The
  button deletes all done to-dos of the list, so the number must match that. Search (#12) and
  filter (#13) come later and must keep this: they filter the to-dos they show, not `done_count`.
- **The count can change between page and click** (for example, in a second tab). The `POST`
  deletes what is done **at that moment**, not the number shown. This is simple and safe: it can
  only delete done to-dos of this list.
- **After the delete**, the browser goes back to the same list page (`redirect(todo_list)`). A
  Django message says, for example, "Deleted 3 completed to-dos." with the exact number.
- **Messages are shown in `base.html`.** `django.contrib.messages` is already installed and
  switched on in `config/settings.py` (app, middleware and context processor). Wave 0 makes one
  shared `todos/templates/base.html`. If it does not show messages yet, add the standard
  `{% for message in messages %}` block **there**, once, so every page shows them. #18 sharing
  and #8 recurring also use messages: whoever comes first adds the block, the others reuse it.
- **The number in the message counts to-dos only.** `QuerySet.delete()` returns two things: the
  number of **all** rows it deleted, and a dictionary with a number per table. The first number
  also counts rows that go with each to-do. #11 tags is in the same wave and adds a
  many-to-many field `Todo.tags`. Deleting a to-do with two tags also deletes two rows in the
  tags table, so the first number would say "Deleted 3" for one to-do. #16 subtasks will do the
  same. So we always use the number for the `Todo` table: `per_model.get("todos.Todo", 0)`.
- **Zero done to-dos** (for example, someone sends the `POST` by hand, or a second tab already
  cleared them): nothing is deleted, the browser goes back to the list, no error. The message
  says "No completed to-dos to delete."

## Working next to other wave 3 features

- **#18 sharing.** It changes who may see and change a list, from "owner" to
  `TodoList.objects.visible_to(user)`. The view must use the same rule as `todo_add` and
  `todo_delete`:
  - **If #18 is merged first**, use
    `get_object_or_404(TodoList.objects.visible_to(request.user), pk=pk)`, and add the two
    sharing tests marked "if #18 is merged" below.
  - **If this feature is merged first**, use
    `get_object_or_404(TodoList, pk=pk, owner=request.user)`. Then #18 must change this view
    too: add `list_clear_completed` to its table "Every view, and what it uses after this
    change", and add the two sharing tests. Its step 12 (`grep -rn "owner" todos/ --include="*.py"`)
    also finds this line.
- **#11 tags.** Changes the count from `delete()` (see above). This plan already uses the per-table
  number, so no change is needed, only the test marked "if #11 is merged".
- **#5 description, #9 priority.** They only add fields. No effect.

## Not part of this task

- **Subtasks (#16)** come later. Its plan already says done to-dos are deleted with their steps
  (`on_delete=CASCADE`). The per-table count above keeps the message right.
- **Search (#12) and filter (#13)** come later. Clearing always clears the whole list; see
  `done_count` above. Coming back to a filtered view after clearing is their task.
- An "undo" after clearing, or a trash bin.
- Clearing done to-dos in all lists at once.
- Any JavaScript (`confirm()` pop-ups and so on).

## Changes to files

| File | Change |
|---|---|
| `todos/urls.py` | Add `path("lists/<int:pk>/clear-completed/", views.list_clear_completed, name="list_clear_completed")`. |
| `todos/views.py` | New view `list_clear_completed` (`@require_POST`; no login decorator, the middleware from #17 does it): get the list or 404, bulk delete its done to-dos, add a message, redirect to the list. In `render_list_page` (from #10), add `done_count` to the context. |
| `todos/templates/todos/todo_list.html` | Add the `<details>` block **below** the list. |
| `todos/templates/base.html` | Show `messages`, only if no earlier feature has added this yet. |
| page CSS | A small style for `details.clear-completed`, using only the existing CSS variables, so dark mode (#20) works without extra colors. |
| `AGENTS.md`, `README.md` | Add the new address to the list of addresses. Update the test counts. |

No model change, so **no migration**.

The view, as a sketch:

```python
from django.contrib import messages
from django.template.defaultfilters import pluralize


@require_POST
def list_clear_completed(request, pk):
    todo_list = get_object_or_404(TodoList, pk=pk, owner=request.user)  # or visible_to, see above
    _, per_model = todo_list.todos.filter(done=True).delete()
    deleted = per_model.get("todos.Todo", 0)
    if deleted:
        messages.success(request, f"Deleted {deleted} completed to-do{pluralize(deleted)}.")
    else:
        messages.info(request, "No completed to-dos to delete.")
    return redirect(todo_list)
```

No `@login_required`: the `LoginRequiredMiddleware` from #17 runs before the view, so a
logged-out visitor is sent to the login page first, for any method.

## Tests

Rule from `docs/plans/test-pyramid.md`: test each rule once, in the lowest layer where a person
would notice it. There is no logic without the database here, so there are **no unit tests**.

**Integration** — `todos/tests/integration/test_lists.py` (the file from #10), new class
`ClearCompletedTests`. Set up (`setUpTestData`): user A with list A1 and list A2, user B with
list B1. A1 has **2 done and 1 not done**. A2 has **1 done**. B1 has **1 done**. The numbers are
different on purpose: a view that counts or deletes in the wrong list gives a wrong number, and
the test sees it. Log in with `self.client.force_login`, as A unless the test says otherwise.

"Still there" means: the test checks the database (`.exists()` or `.count()`), not only the
status code.

| Test | What it checks |
|---|---|
| `test_clear_deletes_done_todos_of_this_list` | `POST` on A1: A1's 2 done to-dos are gone, A1's not-done to-do is still there, the answer redirects to A1. |
| `test_clear_keeps_other_lists` | After clearing A1, the done to-do in A2 and the done to-do in B1 are still there. |
| `test_clear_other_users_list_is_404` | `POST` on B1 as user A: `404`, and B1's done to-do is still there. |
| `test_clear_unknown_list_is_404` | `POST` on a list id that does not exist: `404`. |
| `test_get_does_not_clear` | `GET` on A1: `405`, nothing deleted. |
| `test_clear_needs_login` | Logged out: redirect to the login page, nothing deleted. |
| `test_clear_with_nothing_done` | `POST` on a list with only not-done to-dos: redirect, nothing deleted, the "No completed to-dos to delete." message. |
| `test_clear_shows_message` | `POST` on A1 with `follow=True`: the page has "Deleted 2 completed to-dos." |
| `test_list_shows_clear_button_with_count` | A1's page has `Clear completed (2)` (not 3 or 4) and the address of `list_clear_completed` for A1. |
| `test_list_hides_clear_button_when_nothing_done` | A list with only not-done to-dos (while A2 still has a done one): the page has no `Clear completed` and no clear-completed address. |
| `test_message_counts_todos_not_tags` | **Only if #11 is merged.** Give one done to-do in A1 two tags. After clearing, the message still says "Deleted 2 completed to-dos." **Show it failing first** with the first number from `delete()`. |
| `test_member_can_clear_shared_list` | **Only if #18 is merged.** A1 shared with B; B clears A1: A1's done to-dos are gone, the not-done one stays. |
| `test_stranger_cannot_clear` | **Only if #18 is merged.** A1 shared with B, user C (not a member) clears A1: `404`, nothing deleted. (Without #18, `test_clear_other_users_list_is_404` covers this.) |

**CUJ** — `todos/tests/cuj/test_journeys.py`, one new test `test_clear_completed`. Only a real
browser shows that the question is hidden until the first click; the integration tests cannot
check that. Log in with `self.log_in_as(...)` from #17 and start on the default list from #10.
Add three to-dos, mark two done, check that "Yes, delete them" is **not visible**, click
"Clear completed (2)", see the question, click "Yes, delete them". Only the not-done to-do is
left, the message is shown, and the "Clear completed" button is gone.

## Steps

The order follows `AGENTS.md`: write a test, see it fail, then write the code.

1. Check the merged #10 for the real names (model, `related_name`, URL name, URL parameter). Check
   whether #18 and #11 are merged yet. Fix the names in this plan if they differ, and pick the
   right line in "Working next to other wave 3 features".
2. Write the integration tests above. Run `make test` and show them failing (the URL does not
   exist yet, so most fail with `NoReverseMatch`; the template tests fail on their assertions).
   The 404 and login tests also fail now, because the URL does not exist; that is fine.
3. Add the URL and the view. Run the view tests: they pass.
4. Add `done_count` to `render_list_page` and the `<details>` block to the template. Add the messages
   block to `base.html` if it is not there. The template tests pass.
5. Add the CSS with the existing CSS variables. Look at it with `make run` in light and dark mode,
   and on a narrow window.
6. Write the CUJ test. See it fail by removing the `<details>` block for a moment, put it back,
   see it pass.
7. Update `AGENTS.md` and `README.md`.
8. Run `make check`. Then commit.

## Open questions

- **May a member of a shared list clear it?** This plan says yes, because `docs/plans/sharing.md`
  already lets members delete each to-do, and clearing is only "delete the done ones". If you
  want bulk delete to be owner-only, change the one `get_object_or_404` line and the test
  `test_member_can_clear_shared_list` to expect `404`.

## Review

What the adversarial review changed, and why:

- Names now match `docs/plans/lists.md`: URL parameter `pk` (not `list_pk`), template
  `todo_list.html`, `todo_list.todos`, `redirect(todo_list)`. The old names would give
  `NoReverseMatch`.
- URL name `todo_clear_completed` became `list_clear_completed`, like the other list addresses.
- Sharing (#18, same wave) already says members may clear. The plan said "owner only, #18
  decides". Now it says exactly which line to use in each merge order, and adds two sharing tests.
- The message count used the first number from `delete()`. With #11 tags (same wave), that
  number also counts tag rows, so the message would be wrong. Now it always uses the `Todo`
  number, with a test.
- Test data now has a different number of done to-dos in each list, so a view that counts or
  deletes in the wrong list fails a test. Before, some tests would pass with a wrong count.
- The "hidden button" test now has a done to-do in another list, so a count over all lists fails.
- `done_count` must count the whole list, so search (#12) and filter (#13) do not change it.
- The messages block goes in the shared `base.html` from wave 0, once.
- Added the missing import of `pluralize`, and the note on decorator order.
- The CUJ now checks the part only a browser can show (the question is hidden before the first
  click), and uses the login helper from #17.
- Decided the two old open questions (button below the list; exact number in the message).
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- A member of a shared list may clear the completed to-dos of that list, also ones other people added.

## Post-review check

- The template used `todo_list.pk`, but #10's `render_list_page` passes the list as `the_list`
  (there is no `todo_list` in the page). `{% url %}` with an empty value fails with
  `NoReverseMatch`. Now `the_list.pk`.
- `done_count` now goes in `render_list_page`, not only in `list_detail`, as `sharing.md` expects
  ("keep every key ... `done_count` from #19"). So the page after an invalid add also has it.
