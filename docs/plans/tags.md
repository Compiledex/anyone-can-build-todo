# Plan: tags on a to-do

Status: **done** (2026-10-09, PR #15). The decisions are in "Decided by the person" at the end.

Builds on: **#17 accounts** (log in; each user sees only their own data), **#10 lists** (every
to-do is in a `TodoList`, and **the owner of a to-do is `todo.todo_list.owner`**), **#4 edit** (the
page `todo_edit`, which draws `TodoForm` with `{{ form.as_div }}`), **#20 dark mode**, and the
wave 0 foundation (`TodoForm` in `todos/forms.py`, the row partial
`todos/templates/todos/_todo_item.html`, CSS variables on `:root` in `todos/templates/base.html`).

Same wave (3), built at the same time: #5 description, #9 priority, #19 clear completed and
**#18 sharing**. This plan works with or without #18 (see "Sharing" below).

## Goal

A person can give a to-do some **tags**. A tag is a short label, like `#important` or `#home`. One
to-do can have several tags, and one tag can be on several to-dos.

The person types the tags on the edit page, as one line of text with commas between them. The list
shows the tags of each to-do.

Tags are **private to the owner of the list**. Two users can both have a tag called `work`; they
are two different tags.

## Decisions

- **A `Tag` model of our own, not a package.** A `Tag` has an `owner` (a user) and a `name`. A
  `Todo` gets a `tags` field: a *many-to-many* field. "Many-to-many" means one to-do can have many
  tags, and one tag can belong to many to-dos. Django keeps the links in an extra table by itself.
- **No `django-taggit`.** That package is popular, but it does not help here:
  - Its tags are **shared by everyone** by default. Making them per user needs a custom "through"
    model and custom code — more work than our own model.
  - It uses a *generic* foreign key (a link that can point to any table). That is harder to read and
    to check for a beginner, and the database cannot protect it.
  - It is one more package to update. Our own model is about 15 lines.
- **A tag name is unique per user.** The database enforces it with a `UniqueConstraint` on
  `(owner, name)`. So user A cannot have two `work` tags, but A and B can each have one. Names are
  always stored in lower case (see "Normalisation"), so `Work` and `work` cannot both exist.
- **Tags belong to the owner of the to-do, and that is `todo.todo_list.owner`.** When a to-do is
  saved, its tags are looked up (or made) for that owner — never for `request.user`, and never by
  a tag id sent from the browser. This is the one rule that keeps tags from leaking between users.
  `Todo.owner` does not exist after #10, so do not use it.
- **The field goes into `TodoForm`, not into a new form.** #4 draws `TodoForm` on the edit page with
  `{{ form.as_div }}`, so a new field there shows up on the edit page by itself. The add form on
  the list page is hand-written and only sends `title`, so it does not change.
- **The form field is called `tag_names`, not `tags`.** `tags` is already the name of the model
  field. A form field with the same name as a model field is easy to get wrong in a `ModelForm`:
  if `"tags"` ever got into `Meta.fields`, Django would try to save a list of words as tag ids and
  crash. A different name avoids that for good. The label on the page is still "Tags".
- **The form saves the tags itself**, in `TodoForm.save()`. So the edit view from #4 does not
  change at all, and the to-do and its tags are saved in one database transaction (all or nothing).
- **How tags are typed:** one text field "Tags", for example `important, Home, #work trip`. The
  field shows the current tags, so the person can add or remove one by editing the text. Saving
  the field empty removes all tags from the to-do.
- **Normalisation** — making different spellings into one standard form. The text is cleaned by
  one small function, `parse_tags(text)`, with these rules, in this order:
  1. Split the text on commas.
  2. Remove spaces at the start and end of each piece.
  3. Remove any `#` at the start (`#work` and `work` are the same tag). The page adds the `#` back
     when it shows a tag.
  4. Change several spaces inside a name into one space (`work   trip` → `work trip`).
  5. Make it lower case (`Important` → `important`). So `Work`, `work` and `#WORK` are one tag.
  6. Drop empty pieces (`a,, ,b,` gives `a` and `b`; `#` alone gives nothing).
  7. Drop repeats, and keep the first one (`work, Work` gives `work` once).
- **Limits:** a tag name is at most **30 characters** (counted after the cleaning), and a to-do has
  at most **10 tags**. If the text breaks a limit, the edit page shows an error, keeps what was
  typed, and changes nothing — not the title, not the tags. Spaces inside a name are allowed
  (people type `work trip`). A comma is not, because the comma separates tags.
- **Unused tags are kept.** If a tag is removed from its last to-do, the `Tag` row stays. It is
  invisible on the page, and it is used again if the person types the same name later. Deleting it
  would mean extra code in edit, delete and "clear completed" (#19), for no visible gain.
- **Tags are not links.** Clicking a tag does nothing in this task. Showing "only the to-dos with
  this tag" belongs to **#13 filter**.
- **The order of tags is by name** (A to Z), on the row and in the edit field, so it does not change
  by chance.
- **No admin page for `Tag`.** It is not needed for the feature. (Staff can still see a to-do's
  tags in the existing `Todo` admin. The admin is staff only and does not follow the per-user
  rule; that is accepted.)

### Sharing (#18, same wave)

Decided here, so it does not wait: **a member of a shared list can change the tags of its to-dos,
and those tags go into the list owner's tags.** This follows #18 (every member can edit) and the
suggestion in `docs/plans/sharing.md`. It needs no extra code: `set_tags` already uses
`todo.todo_list.owner`. A member sees only the tags that are on to-dos in the shared list, never
the owner's other tags. A member's own tags are never used on the owner's to-do, even when the
member types a name they also use themselves.

Whichever of #11 and #18 merges **second** adds the test `test_member_tags_go_to_list_owner`
(see "Tests").

## Not part of this task

- Clicking a tag to show only its to-dos: **#13 filter** (wave 5). #13 should offer only tags that
  are on at least one visible to-do, because unused tags are kept.
- Searching by tag: **#12 search** (wave 4) already plans to include tag names.
- A page to rename, delete or color tags.
- Typing tags on the add form.
- Suggestions while typing (autocomplete).
- Moving a to-do to a list with a **different owner**. No feature does this today. If one is added
  later, it must call `set_tags` again with the same names, so the tags move to the new owner.

## Changes to files

| File | Change |
|---|---|
| `todos/tags.py` (new) | `parse_tags(text)`: the normalisation rules and the limits. Plain Python: no database, no request. |
| `todos/models.py` | New `Tag` model. New field `Todo.tags`. New method `Todo.set_tags(names)`. |
| `todos/migrations/` | One new migration, made by Django. |
| `todos/forms.py` | `TodoForm` gets a `tag_names` text field, fills it from the to-do, and saves the tags in `save()`. |
| `todos/views.py` | Only the list page view (`list_detail` from #10): add `.prefetch_related("tags")`. The edit view does not change. |
| `todos/templates/todos/_todo_item.html` | Show the tags of the to-do. |
| `todos/templates/base.html` | CSS for `.tag`, with new CSS variables and their dark values. |
| `todos/tests/...` | The tests in the table below. |
| `AGENTS.md`, `README.md` | Add `todos/tags.py` and the `Tag` model to the file tables. |

The edit page template (`todo_edit.html`) does **not** change: `{{ form.as_div }}` draws the new
field, its label and its errors.

## Steps

The order follows the rule in `AGENTS.md`: write a test, see it fail, then write the code.

### 1. Tests first

Write the tests in the table under "Tests". Run `make test` and show that they fail. Start with
`test_parse_tags_lower_case_and_hash` (unit) and `test_edit_sets_tags` (integration).

### 2. `parse_tags` — new file `todos/tags.py`

```python
import re

from django.core.exceptions import ValidationError

MAX_TAG_LENGTH = 30
MAX_TAGS = 10


def parse_tags(text):
    names = []
    for piece in text.split(","):
        name = re.sub(r"\s+", " ", piece.strip().lstrip("#").strip()).lower()
        if name and name not in names:
            names.append(name)
    for name in names:
        if len(name) > MAX_TAG_LENGTH:
            raise ValidationError(f"A tag can have at most {MAX_TAG_LENGTH} characters: “{name}”.")
    if len(names) > MAX_TAGS:
        raise ValidationError(f"A to-do can have at most {MAX_TAGS} tags.")
    return names
```

It uses Django's `ValidationError`, so a form can show the message. It does not touch the
database, so the unit tests are fast.

### 3. The model — `todos/models.py`

```python
from django.conf import settings

from .tags import MAX_TAG_LENGTH


class Tag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=MAX_TAG_LENGTH)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_tag_name_per_owner"),
        ]

    def __str__(self):
        return f"#{self.name}"
```

In `Todo`:

```python
    tags = models.ManyToManyField(Tag, blank=True, related_name="todos")

    def set_tags(self, names):
        owner = self.todo_list.owner
        tags = [Tag.objects.get_or_create(owner=owner, name=name)[0] for name in names]
        self.tags.set(tags)
```

- `on_delete=models.CASCADE`: when a user is deleted, their tags are deleted too. When a to-do or
  a list is deleted, Django removes the links to its tags by itself.
- `blank=True`: a to-do with no tags is fine.
- `get_or_create` finds the tag if it exists, and makes it if not.
- `self.tags.set(...)` makes the to-do's tags exactly this list: it adds new links and removes old
  ones.
- `self.todo_list.owner` is the owner of the to-do (#10). It is **never** `request.user`: with
  sharing (#18), the person editing may be a member, not the owner.
- `MAX_TAG_LENGTH` comes from `tags.py`, so the limit is written in one place only.
- If the merged #10 code kept a `Todo.owner` field after all, still use `self.todo_list.owner`.

### 4. Migration — `todos/migrations/`

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

Django makes one file. It adds the `Tag` table and the link table. Existing to-dos get no tags.
Nothing else changes. Do not edit the file by hand.

**Wave 3 note.** #5, #9, #18 and #19 may also add a migration. If one of them merges first, both
migrations depend on the same older one, and Django stops with "Conflicting migrations detected".
Fix: update this branch from `main`, **delete this branch's own new migration file** (it was never
used on a live server), and run `makemigrations` again. Django then makes a new file that comes
after theirs. That is not editing a migration by hand.

### 5. The form — `todos/forms.py`

Add to `TodoForm` (keep everything it already has, including fields from #5, #6 and #9):

```python
from django.db import transaction

from .tags import parse_tags


class TodoForm(forms.ModelForm):
    tag_names = forms.CharField(
        required=False,
        max_length=400,
        label="Tags",
        help_text="Separate tags with commas, for example: work, home",
    )

    # class Meta: unchanged. Do NOT add "tags" or "tag_names" to Meta.fields.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["tag_names"] = ", ".join(tag.name for tag in self.instance.tags.all())

    def clean_tag_names(self):
        return parse_tags(self.cleaned_data["tag_names"])

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        with transaction.atomic():
            todo = super().save()
            todo.set_tags(self.cleaned_data["tag_names"])
        return todo
```

- `if self.instance.pk`: a new to-do (on the add form) has no id yet, and asking for its tags
  would crash. So the field is only filled for a saved to-do.
- `clean_tag_names` turns the text into a list of clean names, or shows the error.
- `save()`: the add view from #10 calls `form.save(commit=False)` and sets the list first. That
  path does not touch tags, which is right: the add form sends no tags. The edit view from #4 calls
  `form.save()`, which saves the title and the tags together, or nothing.
- When the form is not valid, `save()` is never called, so nothing changes, and Django shows what
  was typed.

### 6. The list view — `todos/views.py`

In the list page view (`list_detail` from #10), add `.prefetch_related("tags")` to the to-do
query. Without it, Django runs one extra database query for every row. With it, all tags are
loaded in one query. (#12 later passes this query through `apply_list_query`; the prefetch stays.)

The edit view does not change.

### 7. The page

- `_todo_item.html`: after the title:

  ```django
  {% for tag in todo.tags.all %}<span class="tag">#{{ tag.name }}</span>{% endfor %}
  ```

  `todo.tags.all` uses the prefetched tags, already sorted by name. Django escapes the name, so a
  tag like `<b>` is shown as text, not run as HTML.
- `base.html`: a small style for `.tag` (small text, rounded corners, a soft background, a little
  space between tags). Use new CSS variables `--tag-bg` and `--tag-text` on `:root`, and give them
  dark values in the dark mode block from #20. The text must have at least 4.5:1 contrast on its
  background in both light and dark mode.

### 8. Docs

- `AGENTS.md`: in the file table, add `todos/tags.py`, and add `Tag` and `tags` to the line for
  `models.py`.
- `README.md`: the same, and update the test numbers if the README lists them.

### 9. Before the commit

- Run `make check`. It runs the commit checks, the migration check and the tests.
- Run `make run`. Log in as two users. Give to-dos tags, with mixed case, `#`, extra commas and
  spaces. Check that each user sees only their own tags, and look at the page on a narrow window
  and in dark mode.

## Tests

Rule from `docs/plans/test-pyramid.md`: test each rule once, in the lowest layer where a person
would notice it.

### Unit — `todos/tests/unit/test_tags.py` (`SimpleTestCase`, no database)

| Test | What it checks |
|---|---|
| `test_parse_tags_splits_and_strips` | `" work , home "` → `["work", "home"]`. |
| `test_parse_tags_lower_case_and_hash` | `"#Important, ##WORK, # trip"` → `["important", "work", "trip"]`. |
| `test_parse_tags_drops_empty_pieces` | `"a,, ,b,"` → `["a", "b"]`; `""` → `[]`; `"#"` → `[]`. |
| `test_parse_tags_drops_repeats` | `"work, Work, #WORK"` → `["work"]`. |
| `test_parse_tags_joins_inner_spaces` | `"work   trip"` → `["work trip"]`. |
| `test_parse_tags_too_long_name` | A 31-character name raises `ValidationError`; 30 characters is fine. |
| `test_parse_tags_too_many` | 11 different names raise `ValidationError`; 10 are fine; 11 pieces with one repeat are fine. |

### Integration — `todos/tests/integration/test_views.py`, new class `TagTests`

Set-up: users A and B, each with their own `TodoList` (as the tests from #10 do), to-dos inside
those lists. Each test logs in with `self.client.force_login(user)`. Addresses come from
`reverse("todo_edit", args=[todo.pk])` and `reverse("list_detail", args=[the_list.pk])`, never typed
by hand. Every edit `POST` sends the title too, because the edit form needs it.

| Test | What it checks |
|---|---|
| `test_edit_sets_tags` | Saving the edit page with `"Work, #home"` gives the to-do exactly the tags `home` and `work`, and both have `owner` = A. |
| `test_edit_page_shows_current_tags` | The edit page's `tag_names` input has the value `home, work` (sorted by name). |
| `test_edit_with_empty_tags_removes_them` | Saving with `""` leaves the to-do with no tags. |
| `test_same_tag_name_is_reused` | Two to-dos tagged `work` by the same user share one `Tag` row (`Tag.objects.filter(owner=A).count() == 1`). |
| `test_bad_tags_show_error_and_change_nothing` | Post a **new title** and 11 tags: status 200, the error is shown, the typed text is still in the field, and the to-do's title **and** tags are unchanged (read again from the database). |
| `test_list_shows_tags_sorted` | The list page shows `#home` before `#work` for the tagged to-do. |
| `test_list_query_count_does_not_grow_with_tags` | The number of database queries for the list page is the same with 1 tagged to-do and with 5 (`CaptureQueriesContext`). Guards the `prefetch_related`. Show it failing first by removing `prefetch_related`. |
| `test_same_name_for_two_users_is_two_tags` | A and B both tag a to-do `work`: there are two `Tag` rows, one per owner, and each to-do is linked only to its own owner's tag. |
| `test_other_users_tags_are_not_shown` | A tags a to-do `secret`. B's list page and the edit page of B's own to-do do not contain `secret`. |
| `test_cannot_tag_other_users_todo` | B posts a title and tags to the edit address of A's to-do: **404**, A's to-do keeps its title and tags, and B owns no `Tag` rows. |
| `test_add_still_works` | Adding a to-do from the list page (which sends no tags) still works and gives a to-do with no tags. Guards the `save()` change. |

Added by whichever of #11 and #18 merges **second**:

| Test | What it checks |
|---|---|
| `test_member_tags_go_to_list_owner` | A shares a list with B. B, who also owns a tag `work`, saves `"work, new"` on a to-do in A's list: the to-do's tags are owned by **A**, B's own `work` tag is not linked to it, and B owns no new `Tag` rows. |

The existing #4 test `test_edit_page_shows_every_form_field` must still pass: it now also finds
the `tag_names` input.

### CUJ — `todos/tests/cuj/test_journeys.py`

No new journey. Tags are not a critical journey, and the integration tests cover every rule. If
#4 added an edit journey, add one step to it: type `Work, #urgent` in the Tags field, save, and
check that the row shows `#urgent` and `#work`.

## Open questions

1. **Lower case on the page.** Tags are stored and shown in lower case, so `NASA` is shown as
   `#nasa`. This plan accepts that, because it is simple and makes `Work` and `work` one tag.
   Keeping the first spelling the person typed is possible, but needs a second column. Is lower
   case OK?

## Review

What changed in this review, and why:

- `set_tags` now uses `self.todo_list.owner`: after #10, `Todo.owner` is removed, and the old text
  guessed a wrong name (`self.list`).
- The field is added to `TodoForm`, not to an "edit form from #4": #4 has no separate edit form; it
  draws `TodoForm` with `{{ form.as_div }}`.
- The form field is renamed `tags` → `tag_names`: the same name as the model field is a trap in a
  `ModelForm` (Django could try to save the words as tag ids).
- Tags are saved in `TodoForm.save()` inside `transaction.atomic()`, so the #4 edit view does not
  change; the hand-written `<input name="tags">` was removed, because `as_div` draws the field.
- The edit field is filled in the form's `__init__`, only when the to-do already has an id (a new
  to-do would crash on `.tags.all()`).
- Sharing is decided, not left open: members may change tags, and the tags belong to the list
  owner, as `sharing.md` suggests; one test for it is added by whoever merges second.
- CSS moves to `base.html`, where wave 0 put the CSS, with the 4.5:1 contrast rule for dark mode.
- The list view is named (`list_detail`) and the query-count test renamed and shown failing first.
- Tests now use lists from #10, `reverse(...)`, send a title with every edit, check the title too
  on a bad save, check the tag order, and check that adding a to-do still works.
- The migration conflict advice was wrong ("same number"); it now says to delete this branch's own
  unmerged migration and run `makemigrations` again.
- The `TagAdmin` was removed: not needed for the feature (smaller scope).
- `max_length` of `Tag.name` uses `MAX_TAG_LENGTH`, so the limit is written once.
- Former open questions 2 (merge order) and 3 (allowed characters: spaces allowed) are decided in
  the text above.

## Decided by the person (2026-10-09)

The plan is **approved**.

- Tags are stored and shown in lower case (`NASA` becomes `#nasa`).
