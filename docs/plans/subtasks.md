# Plan: subtasks (small steps inside a to-do)

Status: **done** (2026-10-09, PR #16). The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (the test pyramid, `TodoForm` in `todos/forms.py`, the partial template
`_todo_item.html`, CSS variables, the shared `base.html`), 17 accounts, 10 lists, 18 sharing,
19 clear completed (its `messages` block in `base.html`, and its count of deleted to-dos). It does
not need any other feature.

## Goal

A person can split a to-do into small steps. A **subtask** is one step: it has a title and can
be marked done. Example: the to-do "Move house" has the steps "Pack books", "Book a van" and
"Clean the kitchen".

On the list, a to-do with steps shows how many are done, like **Steps: 2 of 5 done**. A click
opens the steps. There the person can add a step, mark one done (or undo that), and delete one.

A to-do with no steps works exactly as it does today. It only gets one small closed "Add steps"
link-like line under its title.

## Decisions

### A separate `Subtask` model, not a to-do inside a to-do

There are two ways to store steps:

1. **A new table `Subtask`** with `title`, `done`, `created_at` and a link to its `Todo`.
2. **A self-referencing `Todo`**: a `parent` field on `Todo` that points to another `Todo`.
   ("Self-referencing" means the table has a link to itself.)

We choose **1, a separate `Subtask` model**. The reasons:

- **A step is much smaller than a to-do.** A `Todo` has (by wave 4) a list, a due date, a
  description, a priority, tags, reminders and maybe a repeat rule. A step needs none of these.
  With option 2, every step would carry all those fields, and every feature would have to decide
  what they mean for a step ("Can a step have its own reminder? Its own tags?").
- **No change to the code that already works.** With option 2, every query that shows to-dos
  must add `parent=None`, or steps would appear in the main list, in search, in filters, in
  "clear completed", in the count of to-dos. Forgetting it once is a bug. With option 1, a step
  can never show up where a to-do is expected.
- **One level is built in.** A `Subtask` has no subtasks, because the table has no link to
  itself. With option 2 we would need extra checks to stop a step having steps, and to stop a
  loop (A inside B inside A).
- **Access control is simple.** A step has no owner and no list of its own. It only has its
  to-do. So "who may see or change this step" is always "who may see or change its to-do". It
  can never disagree with the parent.

The cost of option 1 is a second small set of views and URLs. That is less work than making
every existing feature aware of "parent".

### Other decisions

- **One level only.** A step cannot have steps.
- **Finishing all steps does not finish the to-do.** The person marks the to-do done by
  themselves, as today. A rule that does it by itself would surprise people ("I undid a step, why
  is my to-do open again?") and needs extra rules for the other direction.
- **Marking the to-do done does not change its steps.** The steps keep their own `done`. This
  also means the CSS must not cross out a step just because its to-do is done (see step 7).
- **Deleting the to-do deletes its steps.** A step without a to-do has no meaning. In the
  database this is `on_delete=models.CASCADE` ("cascade" means: delete the children together
  with the parent). "Clear completed" (feature 19) deletes done to-dos, so it also deletes their
  steps. **But** its message counts deleted rows, and Django counts the cascaded steps too
  ("Deleted 7 completed to-dos" when only 2 were deleted). The clear-completed plan says to count
  only `todos.Todo` once subtasks exist. Check the merged code; if it still uses the total, fix it
  in this task (step 5) and add the test `test_clear_completed_counts_only_todos`.
- **Who may change steps follows the to-do.** Sharing (#18) has no "view only" role: a member may
  do everything with a list's to-dos. So the rule is simple: whoever may see the to-do (the owner
  and the list's members) may add, toggle and delete its steps. Anyone else gets
  **404 Not Found** (not 403), so we do not reveal that the to-do or step exists.
- **No to-do number in the toggle and delete addresses of a step.** They use only the step's
  number. So a request can never have a step number and a to-do number that disagree. The view
  checks the step through its own to-do.
- **Order:** steps are shown oldest first (`created_at`, then `id`), like to-dos.
- **Title rules are the same as for a to-do:** required, not only spaces, at most 200 characters.
- **A bad step title shows a message.** If the title is empty or too long, nothing is saved, and
  the list page shows one error message: "A step needs a title of 1 to 200 characters." We use
  Django's `messages` framework (it is already turned on, and #19 shows messages in `base.html`).
  We do not show the error inside the to-do's row, because that would mean showing the whole list
  page again with one form in a special state. A message is much simpler.
- **How it looks:** each to-do gets a `<details class="steps">` element under its title. A
  `<details>` element is plain HTML that opens and closes on a click, with no JavaScript. Its
  `<summary>` (the part you click) shows `Steps: 2 of 5 done`, or `Add steps` when there are none.
  Inside are the steps and a small form "Add a step". We write the full words, not `2/5`, so a
  screen reader reads it well and we need no `aria-label`.
- **The details stays open after an action.** After adding, toggling or deleting a step, the
  browser goes back to the to-do's list page with `?open=<to-do id>#todo-<to-do id>` at the end of
  the address. The template opens the `<details>` of that one to-do, and the browser scrolls to
  it. This is a `GET` that only reads, so it follows the rule in `AGENTS.md`.
  - **It is safe.** The server builds this address only from numbers in the database (the list id
    and the to-do id), never from what the browser sent. So nobody can make it point to another
    website (an "open redirect"). On the list page, the template only *compares* `open` with each
    to-do's id. It never prints the value, so a strange value like `?open=<script>` does nothing.
  - A search (#12) on the page is cleared after a step action, like after other actions. Keeping
    it is the `next` helper from filter (#13), a later wave.
- **The count is computed from the steps already loaded.** The list page view uses
  `prefetch_related("subtasks")`. ("Prefetch" means: load all steps for all to-dos on the page in
  one extra database query, instead of one query per to-do.) We do not use `annotate(Count(...))`,
  because counting together with tags (feature 11) can count rows twice.
- **Recurring to-dos (#8, same wave):** when a repeating to-do makes its next copy, its steps are
  copied too, with `done` set to false. A checklist is the main reason to have steps on a
  repeating to-do. Whichever of #8 and #16 merges second adds this to `Todo.make_next_copy`, with
  one test.

## Not part of this task

- **Changing a step's title.** A person deletes the step and adds it again. (Staff can also
  change it in the Django admin, see step 8, but normal users cannot open the admin.)
- Steps inside steps (more than one level).
- Moving a step to another to-do, or changing the order of steps by hand. Drag and drop is
  feature 15, in a later wave.
- A due date, priority, tags or reminder on a step.
- Searching in step titles. Search (feature 12) is in the same wave, so this plan cannot assume
  it. It can be added after both are done.
- Keeping a search or filter in the address after a step action (#13's `next` helper, later wave).
- Filtering or sorting by steps (features 13 and 14 come later).
- A different look when all steps are done. Easy to add later if people ask.

## Changes to files

| File | Change |
|---|---|
| `todos/models.py` | New model `Subtask`; method `Todo.subtask_progress`. |
| `todos/migrations/` | One new migration, made by Django. |
| `todos/forms.py` | New `SubtaskForm`. |
| `todos/views.py` | Three new views and one helper; `render_list_page` prefetches steps; maybe the count in `list_clear_completed` (see Decisions). |
| `todos/urls.py` | Three new addresses. |
| `todos/templates/todos/_todo_item.html` | `id` on the `<li>`; the `<details>` with steps, count and add form. |
| `todos/templates/base.html` | A little CSS for the steps. (All CSS lives here since wave 0.) |
| `todos/admin.py` | Show steps inside a to-do in the admin. |
| `todos/tests/integration/test_subtasks.py` | New integration tests. |
| `todos/tests/cuj/test_journeys.py` | One new journey. |
| `AGENTS.md`, `README.md` | The file table and the test numbers. |

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in the table in step 9. Run `make test` and show that they fail. They fail with
`NoReverseMatch`, because the addresses do not exist yet.

**Always build addresses with `reverse("subtask_add", args=[...])`, never type them by hand.**
Why: with a typed address, the "other user gets 404" tests would pass *before* any code exists,
because a missing address is also a 404. With `reverse`, they fail until the address exists.

### 2. The model — `todos/models.py`

```python
class Subtask(models.Model):
    todo = models.ForeignKey(Todo, on_delete=models.CASCADE, related_name="subtasks")
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.title
```

- `ForeignKey` is a link to one row in another table. Here: each step belongs to one to-do.
- `related_name="subtasks"` lets the code write `todo.subtasks.all()`.
- There is **no** `owner` or `list` field. Both come from the to-do, so they can never disagree.

Add one method to `Todo`, for the template:

```python
    def subtask_progress(self):
        """(number done, number of steps). Uses the prefetched steps, so no new query."""
        steps = self.subtasks.all()
        return sum(1 for s in steps if s.done), len(steps)
```

Use `.all()` and count in Python. Do **not** write `self.subtasks.filter(done=True).count()`:
`filter` and `count` ignore the prefetched steps and ask the database again for every to-do.

### 3. Migration — `todos/migrations/`

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

Django makes a file like `000N_subtask.py`. Do not edit it by hand. It only creates a new, empty
table. Existing to-dos are not changed, and they start with no steps.

### 4. The form — `todos/forms.py`

```python
class SubtaskForm(forms.ModelForm):
    class Meta:
        model = Subtask
        fields = ["title"]
```

A `ModelForm` already rejects an empty title, a title of only spaces (Django strips spaces), and
a title over 200 characters. The `todo` field is **not** in the form: the view sets it from the
to-do it found. So sending an extra `todo=<another number>` in the `POST` does nothing.

### 5. The views — `todos/views.py`

All three have `@require_POST`, like the to-do views. No `@login_required`: the
`LoginRequiredMiddleware` from #17 already needs a login for every view. They find the to-do
with **the same helper `todo_toggle` uses**. In the sharing plan this is
`get_visible_todo(user, pk)`, which is
`get_object_or_404(Todo, pk=pk, todo_list__in=TodoList.objects.visible_to(user))`. Check the
merged code and use the real name.

```python
def back_to_steps(todo):
    """Back to the to-do's list, with this to-do's steps open."""
    url = reverse("list_detail", args=[todo.todo_list_id])
    return redirect(f"{url}?open={todo.pk}#todo-{todo.pk}")


@require_POST
def subtask_add(request, todo_pk):
    todo = get_visible_todo(request.user, todo_pk)
    form = SubtaskForm(request.POST)
    if form.is_valid():
        subtask = form.save(commit=False)
        subtask.todo = todo
        subtask.save()
    else:
        messages.error(request, "A step needs a title of 1 to 200 characters.")
    return back_to_steps(todo)


def get_visible_subtask(user, pk):
    return get_object_or_404(
        Subtask.objects.select_related("todo"),
        pk=pk,
        todo__todo_list__in=TodoList.objects.visible_to(user),
    )
```

- `subtask_toggle(request, pk)`: `get_visible_subtask`, flip `done`, save, `back_to_steps`.
- `subtask_delete(request, pk)`: `get_visible_subtask`, delete, `back_to_steps`.

The `todo__todo_list__in=...` part is what makes another user's step a 404. (`select_related`
loads the to-do in the same query, because `back_to_steps` needs it.)

`render_list_page` (#10; it builds the list page for `list_detail` and for an invalid add): add
`.prefetch_related("subtasks")` to its to-do query. If search (#12) is already
merged, add it to the queryset that `apply_list_query` returns; a prefetch survives `filter` and
`order_by`.

`list_clear_completed` (#19), only if the merged code counts all deleted rows: count only to-dos,
as its own plan says: `_, per_model = ....delete()` and `deleted = per_model.get("todos.Todo", 0)`.

### 6. The addresses — `todos/urls.py`

```python
path("<int:todo_pk>/subtasks/add/", views.subtask_add, name="subtask_add"),
path("subtasks/<int:pk>/toggle/", views.subtask_toggle, name="subtask_toggle"),
path("subtasks/<int:pk>/delete/", views.subtask_delete, name="subtask_delete"),
```

The first one has the same shape as the to-do addresses (`<int:pk>/toggle/`). If the merged code
puts to-dos under another prefix (for example `todos/`), use the same prefix here.

### 7. The page

`_todo_item.html`, inside the `<li>`:

- Give the `<li>` `id="todo-{{ todo.pk }}"`, so the `#todo-…` part of the address scrolls to it.
- Add `<details class="steps"{% if request.GET.open == todo.pk|stringformat:"d" %} open{% endif %}>`.
  (The address gives text, the id is a number, so `stringformat:"d"` turns the id into text.)
  Write the attribute exactly like this, because a test looks for `<details class="steps" open>`.
- `<summary>`: use `{% with progress=todo.subtask_progress %}`. If `progress.1` (the total) is
  0, show `Add steps`; else `Steps: {{ progress.0 }} of {{ progress.1 }} done`.
- Inside: `<ul class="steps">` with one `<li class="step">` per step (add `done` to the class when
  the step is done). Each step has `<span class="step-title">`, a `Done`/`Undo` button and a
  `Delete` button, each in its own small `POST` form, like the to-do row.
  - Give each step button an `aria-label` that starts with its visible word and names the step:
    `aria-label="Done: {{ step.title }}"`, `"Undo: …"`, `"Delete step: …"`. Reason: with the
    steps open, the to-do's row has several "Done" buttons. A screen reader user (and the browser
    tests) must be able to tell them apart.
- Under the steps: a form with `<input name="title" aria-label="New step for {{ todo.title }}"
  maxlength="200" required>` and an `Add step` button.

`base.html`, a little CSS with the existing CSS variables (so dark mode works with no new colors):

- The to-do `<li>` is a flex row. Let the `<details>` take its own line:
  `flex-wrap: wrap` on the row, `flex-basis: 100%` on `details.steps`.
- **The line-through must not leak into the steps.** Today the rule is `li.done .title`. That
  would also cross out every step of a done to-do. Use a different class for step titles
  (`.step-title`), and a rule `li.step.done .step-title` for done steps. Make sure the to-do
  rules (`li { border-bottom … }` and so on) do not make the steps look like to-dos: scope the
  step rules with `ul.steps li`.
- Indent the steps; make the step buttons a bit smaller.

### 8. The admin — `todos/admin.py`

Show steps inside a to-do with a `TabularInline` (Django's way to edit child rows on the parent's
admin page). Three lines; staff can fix a step's title there.

### 9. The full list of tests

**Unit:** none. The only logic is `subtask_progress`, and it needs steps from the database. The
person notices it as the count on the page, so it is tested there (integration), once.

**Integration**, in a new file `todos/tests/integration/test_subtasks.py`. Users A and B are made
in `setUp`; A owns a list with the to-do. Form rules are tested here, through the test client, as
the test pyramid plan says. Every address comes from `reverse` (see step 1).

| Test | What it checks |
|---|---|
| `test_add_a_step` | A posts "Pack books" to A's to-do: one step with that title, linked to that to-do, not done. |
| `test_todo_field_in_post_is_ignored` | A posts to A's to-do with an extra `todo=<B's to-do id>`: the step is on A's to-do, B's to-do has no steps. |
| `test_empty_step_title_is_not_added` | Title "   ": nothing saved; following the redirect, the page shows the error message. |
| `test_long_step_title_is_not_added` | 201 characters: nothing saved. 200 characters: saved. |
| `test_toggle_step_and_back` | Toggle twice: done, then not done. |
| `test_delete_step` | The step is gone; the to-do is still there. |
| `test_get_does_not_change_steps` | `GET` to add, toggle and delete: each is 405, nothing changes. One test, a loop with `subTest`. |
| `test_logged_out_cannot_change_steps` | `POST` to add, toggle and delete without logging in: each goes to the login page, nothing changes. One test, `subTest`. |
| `test_other_user_cannot_add_step` | B posts to A's to-do: 404, nothing saved. |
| `test_other_user_cannot_toggle_step` | B toggles A's step: 404, still not done. |
| `test_other_user_cannot_delete_step` | B deletes A's step: 404, still there. |
| `test_list_member_can_change_steps` | A shares the list with B: B can add, toggle and delete a step on A's to-do. |
| `test_deleting_todo_deletes_its_steps` | Delete the to-do: `Subtask.objects.count()` is 0. |
| `test_clear_completed_counts_only_todos` | One done to-do with 3 steps; clear completed: the message says 1 to-do, not 4. (Only if step 5 had to change the count; otherwise #19's test already covers it, so check it has a to-do with steps.) |
| `test_all_steps_done_does_not_finish_todo` | Both steps done: the to-do is still not done. |
| `test_finishing_todo_does_not_change_steps` | Toggle the to-do: its steps keep their `done`. |
| `test_list_shows_step_count` | 2 of 5 steps done: the page contains `Steps: 2 of 5 done`. |
| `test_todo_without_steps_shows_add_steps` | No steps: the page contains `Add steps`, and not `0 of 0`. |
| `test_list_has_fixed_number_of_queries` | Use `CaptureQueriesContext` to count the queries of the list page with 1 to-do with 3 steps, then with 5 to-dos with 3 steps each. The two numbers are equal. **Show it failing once by removing `prefetch_related`.** |
| `test_after_action_details_is_open` | Two to-dos. Add a step to the second: the redirect goes to `<list address>?open=<pk>#todo-<pk>`. That page contains `<details class="steps" open>` exactly once (`assertContains(..., count=1)`), and `id="todo-<pk>"`. |
| `test_bad_open_value_is_ignored` | `?open=abc` and `?open=<script>`: the page is 200, no `<details class="steps" open>`, and the text `<script>` is not in the page. |

We do not add a test "B does not see A's steps on the list page": B cannot open A's list at all,
and lists (#10) already tests that. It would pass even if steps had no access check.

**CUJ**, in `todos/tests/cuj/test_journeys.py`, one new journey `test_break_a_todo_into_steps`:
add "Move house", open "Add steps", add "Pack books" and "Book a van", click the button named
`Done: Pack books`, see `Steps: 1 of 2 done`, see that the details is still open (the "Book a
van" step is visible), and that "Move house" is not done and "Book a van" is not crossed out.
Find buttons by these full names: `get_by_role("listitem").filter(has_text="Pack books")` would
also match the "Move house" row, because the step is inside it.

Then run **all** existing tests. The to-do row now contains a `<details>`; the old tests should
still pass, because a closed `<details>` hides its buttons from `get_by_role`.

### 10. Docs

- `AGENTS.md`: in the table, `models.py` gets `Subtask`, `urls.py` gets the three new addresses.
- `README.md`: update the test numbers under "Run the tests".

### 11. Before the commit

- Run `make check`. It runs the commit checks, the migration check and the tests.
- Run `make run`. Add a to-do with steps, finish some, finish the to-do (the steps must not be
  crossed out), delete the to-do. Look at it on a narrow window, and with dark mode on.

## Open questions

None that need a person to decide. Everything above is decided; see the Review section.

## Review

What changed in this review, and why:

- Removed the "view only" sharing case (test and "no buttons" rule): sharing (#18) has no view-only role.
- Fixed "clear completed needs no change": its message would count cascaded steps as to-dos; the plan now checks and fixes it, with a test.
- Fixed the CSS: `li.done .title` would cross out every step of a done to-do; steps now use `.step-title`.
- Gave step buttons unique names (`Done: Pack books`): with steps open, a row had several "Done" buttons, which breaks Playwright locators and confuses screen readers.
- Required `reverse()` in tests: with typed addresses the "other user gets 404" tests pass before any code exists.
- Cut `test_other_user_does_not_see_steps`: it would pass even with no access check.
- Added tests: logged out, extra `todo` field in the POST, a bad `?open=` value, the 200-character edge.
- Wrote out the views (`get_visible_todo`, `get_visible_subtask`, `back_to_steps`) and explained why the redirect cannot be an open redirect.
- Named the right view (`list_detail`, not `todo_list`) and the right CSS file (`base.html`).
- Made the query-count test precise (`CaptureQueriesContext`, compare two numbers, show it failing) and warned against `filter().count()`, which ignores the prefetch.
- Summary text is now `Steps: 2 of 5 done`, so no `aria-label` is needed (an `aria-label` that hides the visible text is an accessibility problem).
- Said that a normal user cannot change a step's title (the admin is for staff only).
- Decided the recurring question (copy steps, not done) and dropped the two other open questions (decided, or not needed).
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- No open questions.

## Post-review check

- "`list_detail` prefetches steps": the to-do query of the list page is in #10's
  `render_list_page` (used by `list_detail` and by an invalid add), so the prefetch goes there.
