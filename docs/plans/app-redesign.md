# Plan: redesign of the app pages

Status: **draft**, for the person to review. Not started.

Starts after: **(1)** the fix for the to-do row layout (another session is working on it now: a
long title runs over the priority label, and "Repeats every …" pushes Done and Delete onto a new
line) is merged, and **(2)** the landing page (`feature/landing`) is merged. Step 1 below needs
the landing page's `landing.css` on `main`.

Mockup: [`app-redesign-mockup.html`](app-redesign-mockup.html) (open it in a browser; make the
window narrow, and switch the system between light and dark, to see each version).

## Goal

The pages a person sees after logging in (the list page, the edit page, "New list", "Rename list"
and "Delete list") look calm, clear and finished, and look like **one product with the landing
page**: the same colors, the same font, the same corners, the same buttons. Nothing a person does
changes: every address, form field, button label and keyboard path stays the same.

Words used in this plan:

- A **token** is a named value in CSS, like `--accent: #1f4f8f`. The pages use the name, never
  the value, so one change updates every page.
- The **contrast ratio** compares how bright two colors are, from 1 : 1 (the same color) to
  21 : 1 (black on white). **WCAG AA** is the usual rule: at least 4.5 : 1 for text, and 3 : 1 for
  the edge of a control (a text field's border, a focus ring).
- A **focus ring** is the outline that shows which button or field the keyboard is on.

## The design read and the dials

Design read (approved by the person): *Redesign of a daily-use to-do app for one person and a
few people they share lists with, with a calm, restrained language, leaning toward native CSS
variables + system sans + system light/dark.*

Mode: **redesign, visual overhaul, information architecture kept** (taste skill, Section 11:
"Redesign - Overhaul": new look on top of the same content and structure).

| Dial | Value | What it means here |
|---|---|---|
| `DESIGN_VARIANCE` | 4 | One centered column, left-aligned text, no tricks. |
| `MOTION_INTENSITY` | 3 | No automatic animation. Only short color changes on hover and a 1 px press on buttons. |
| `VISUAL_DENSITY` | 5 | A daily app: rows close enough to see 6 to 8 to-dos at once on a laptop. |

**The skill is not made for product UI.** The taste skill says so itself (Section 13: "not for
dashboards / dense product UI"). So this plan uses only the parts that fit an app: typography
(4.1), one accent and one gray family (4.2), one corner system (4.4), every state (4.5), form
patterns (4.6), dark mode (8), the AI tells (9, including zero em-dashes), and the redesign audit
(11 and the redesign skill). It does **not** use the landing-page rules: no hero, no pictures,
no bento, no eyebrows, no scroll motion, no icon library.

## Audit (before)

Screenshots of today's pages, with invented sample data, at 1280 and 390 px wide, light and dark:
`scratchpad/app-audit-shots/` (not in git; for the review only). Pages: the list (default,
steps open, search, no match, filter, manual order, owner with members, member view, empty list),
edit, new list, delete list, a form error on "New list", an add error, and a message.

### Current tokens (`todos/templates/base.html`)

| Token | Light | Dark | Contrast on `--bg` (light / dark) |
|---|---|---|---|
| `--bg` | `#ffffff` | `#121212` | |
| `--text` | `#000000` | `#e8e8e8` | 21.0 / 15.3 |
| `--muted` | `#666666` | `#a0a0a0` | 5.7 / 7.2 |
| `--border` | `#dddddd` | `#3a3a3a` | 1.4 / 1.6 (lines only) |
| `--overdue` | `#b00020` | `#ff6b6b` | 7.3 / 6.8 |
| `--priority-high` | `#a14a00` | `#ffb366` | 6.0 / 10.6 |
| `--tag-bg` / `--tag-text` | `#e6eef8` / `#1d3b5c` | `#233447` / `#cfe1f5` | 9.8 / 9.5 (text on tag) |
| `--drag-bg` | `#eef3fa` | `#1f2a36` | |

Type: `system-ui, sans-serif`, browser default sizes. Width: `max-width: 32rem` (512 px). Radius:
none on most things; `0.6rem` on tags, `0.25rem` on the priority label. Buttons, fields and
selects are the browser's own. No accent color. No focus style of our own.

All text passes AA today. The problems are in shape, layout and states, not in contrast.

### Problems found

Most important first.

1. **The to-do row breaks.** All parts of a row are one flex line. A long title gets squeezed to
   one word per line (19 lines for one to-do at 1280 px); the priority label overlaps the title
   ("Pay rent" is written over by "Medium"); "Repeats every Thursday" pushes Delete onto its own
   line; at 390 px Done and Delete land on a second line under the title in most rows. (Being
   fixed now in another session; this plan's row must keep that fix.)
2. **No visual system.** Buttons, selects and the date field are browser defaults; the
   priority select on the add form is bigger than the sort select; the edit page's selects and
   textarea are tiny and the textarea uses a monospace font. Three different corner styles
   (square controls, round tags, small-round priority).
3. **The page does not look like the landing page.** Different background (pure white vs.
   `#f6f7f9`), pure black text, no accent, no header bar, different widths. Pure `#000` and
   `#fff` are also an AI tell (skill 8.B, 9.A).
4. **Errors are hard to see and far from their field.** "Enter a valid date." shows above the
   whole add form, in the normal text color. On the edit page and "New list", Django puts the
   error between the label and the field, in black. Fields with an error get no red border.
5. **Placeholder used as the label.** The add form ("What needs doing?"), search ("Search"), the
   share field ("Username") and "Add step" (empty field, no hint at all) have no visible label.
   Skill 4.6: "No placeholder-as-label. Ever."
6. **No hierarchy between actions.** "Add", "Done", "Delete", "Log out", "Sort", "Search",
   "Remove" all look the same. Edit is an underlined link between two buttons. "Delete list" (it
   deletes everything) looks like "Rename". "Yes, delete them" looks like any other button.
7. **No focus, hover or pressed states of our own.** Only the browser's defaults. The selected
   list and filter are only bold.
8. **The search, sort and filter controls are three loose rows** that take 150 px before the
   first to-do, with nothing grouping them.
9. **Too narrow on a laptop.** 512 px of content in a 1280 px window; titles wrap early.
10. **Empty and "no match" states are a plain bullet row** with a line under it, the same as a
    to-do.
11. **Messages** ("Shared with ines.") are a gray-bordered box that looks like an input;
    errors from `messages.error` look the same as success.
12. **The header** ("Logged in as mara" and "Log out") has no product name; the page has no
    anchor at the top.
13. **Edit page**: "Save" and "Cancel" touch each other; the tag help text sits between the
    label and the field.
14. **Dark mode** uses `#121212` and neutral grays, while the tags are blue-gray: two gray
    families (skill 4.2: one gray family).

Checked and fine: no em-dashes or en-dashes in any visible text, no exclamation marks, no fake
names, no decorative dots, no emoji. Keyboard order is logical. `aria-label`s on row buttons
name their to-do. Reduced motion: nothing moves today.

### Patterns to keep (skill 11.C)

Every address; the order of the parts of the list page; every form field, its `name` and its
order; every button and link label; every `id` (`todo-<pk>`, `sharing-heading`, `my-lists`,
`shared-lists`, `reorder-csrf`); every `aria-label`, `aria-current`, `aria-invalid` and
`aria-describedby`; `role="status"` on messages and `role="search"`; the `next` field on Done and
Delete; `?open=` opening the steps; `<details>` for notes, steps and clear completed (they work
without JavaScript); the Move up / Move down buttons; the light/dark switch by the system only.

## Decisions

- **One shared token file: `todos/static/todos/tokens.css`.** Both `base.html` (the app) and
  `landing.html` load it first; `landing.css` and the new `app.css` only use the names. Why not
  copy the landing values into `base.html`: two copies drift apart, and the login and sign-up
  redesign (a separate task, see below) will need the same tokens a third time. The landing
  page's values are the starting point and do not change, so the landing page looks the same
  after step 1.
- **The app's CSS moves out of `base.html` into `todos/static/todos/app.css`.** It grows from
  ~70 to ~300 lines; a file is easier to read and review, and the browser can cache it. The
  landing page already serves CSS this way (WhiteNoise), so nothing new is needed. `base.html`
  keeps only `<link>`s. No build step, no Tailwind, no JavaScript framework, no external request.
- **Font: the system font stack**, the same as the landing page:
  `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif`. No web font.
- **One accent, `--accent`** (`#1f4f8f` light, `#8fb6ec` dark), from the landing page. It marks
  the primary button, links, the current list, the focus ring and tags. Nothing else is blue.
- **One gray family, cool**, from the landing page (`--text`, `--muted`, `--border`, plus the new
  `--control` for field and button edges).
- **Two status colors, only for status**, never for decoration: `--danger` (red: overdue, form
  errors, destructive buttons) and `--priority-high` (amber: the High label). They must stay
  different (the color test checks this). Success and info messages use the same calm accent
  band, so a message never introduces a third status color.
- **Corners: one rule.** `--radius: 8px` on everything you can click or type into and on boxes
  (buttons, fields, selects, messages, the clear-completed box, the filter group). `--radius-label:
  4px` on the small inline labels under 24 px tall (priority, tag, focus ring on text). Nothing is
  a pill. (Skill 4.4 allows a mixed system when the rule is written down and followed everywhere.)
- **No cards.** Rows are separated by one bottom line, as today. The only boxes are the ones that
  carry meaning: a message, the "Clear completed" confirmation, the filter group.
- **No icons.** Text labels, as on the landing page. The ↑ / ↓ move buttons and the ⠿ handle are
  text characters and stay.
- **Visible labels above fields** on the list page: "New to-do", "Due date", "Repeat", "Priority",
  "Search to-dos", "Sort by:", "New step", "Username". The visible text is the same as (or the
  start of) the existing `aria-label`, so screen readers and the tests find the same names
  (WCAG 2.5.3, "label in name"). The label **wraps** the field (`<label>text <input></label>`), so
  no field gets a new `id` (some tests compare the whole `<input>` tag). Placeholders that are
  hints, not labels, stay ("What needs doing?", "Search").
- **Errors under their field, in red, and the field gets a red border** (`[aria-invalid="true"]`).
  On the edit, new-list and rename pages, Django prints the error before the field; CSS `order`
  in a flex column puts it below, with no template change for Django's field HTML.
- **Width: 46rem (736 px)** for the list page and 36rem for the forms on the edit page. Still one
  column; titles wrap much less.
- **A header bar** like the landing page's: "To-do list" on the left (a link to `/`, which already
  sends the person to their first list), "Logged in as mara" and "Log out" on the right. This is
  the only new link; see Open questions.
- **Motion**: only `background-color`, `color`, `border-color` and `transform` change, in 150 ms,
  `ease-out`. Buttons move down 1 px while pressed. Under `prefers-reduced-motion: reduce` there
  is no transition and no press movement.
- **Copy**: no visible text changes, except the new visible labels above. No string a test checks
  changes.

## Tokens

All in `todos/static/todos/tokens.css`. The dark values apply under
`@media (prefers-color-scheme: dark)`, as today.

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--bg` | `#f6f7f9` | `#0e1013` | page background (landing) |
| `--surface` | `#fcfcfd` | `#15181d` | fields, selects, secondary buttons, filter group |
| `--band` | `#e6edf6` | `#172231` | messages, hover background, current filter, tags, dragged row (landing) |
| `--text` | `#15181d` | `#e8eaee` | normal text (landing) |
| `--muted` | `#545b66` | `#a3aab5` | meta line, done title, header, labels of quiet buttons (landing) |
| `--border` | `#d3d8e0` | `#2d333b` | lines between rows and sections (landing) |
| `--control` | `#868e9a` | `#6b7480` | the edge of fields and secondary buttons (new) |
| `--accent` | `#1f4f8f` | `#8fb6ec` | primary button, links, current list, focus ring (landing) |
| `--accent-hover` | `#173d70` | `#b0cbf2` | primary button and link on hover (landing) |
| `--on-accent` | `#f6f7f9` | `#0e1013` | text on the primary button (landing) |
| `--focus` | `= --accent` | `= --accent` | focus ring, 2 px, 2 px away from the element |
| `--danger` | `#b3261e` | `#ff8a80` | overdue date and label, errors, danger button (new; replaces `--overdue`) |
| `--danger-hover` | `#8f1d17` | `#ffaba3` | danger button on hover |
| `--on-danger` | `#f6f7f9` | `#0e1013` | text on the danger button |
| `--danger-bg` | `#fbeceb` | `#2a1716` | error message, hover of a quiet Delete |
| `--priority-high` | `#8a4b00` | `#f0b46a` | the High label |
| `--tag-bg` | `= --band` | `= --band` | tag background |
| `--tag-text` | `#1f4f8f` | `#b0cbf2` | tag text |
| `--drag-bg` | `= --band` | `= --band` | the row being dragged |
| `--radius` | `8px` | | controls and boxes |
| `--radius-label` | `4px` | | priority, tag, focus ring on text |
| `--font` | system stack | | everything |

Light `--bg` has a relative luminance of 0.93, so the existing check "the light background is
light" (above 0.9) still passes. Dark `--bg` is 0.005 and dark `--tag-bg` 0.015 (both under 0.1).

### Contrast (computed with the WCAG formula)

| Pair | Tokens | Light | Dark | Needs | Pass |
|---|---|---|---|---|---|
| body text on page | `text` on `bg` | 16.6 : 1 | 15.8 : 1 | 4.5 : 1 | yes |
| input text on input | `text` on `surface` | 17.4 : 1 | 14.8 : 1 | 4.5 : 1 | yes |
| muted text (meta, done title, header) | `muted` on `bg` | 6.4 : 1 | 8.1 : 1 | 4.5 : 1 | yes |
| placeholder, help, quiet button on input | `muted` on `surface` | 6.7 : 1 | 7.6 : 1 | 4.5 : 1 | yes |
| muted text on band (hovered quiet button) | `muted` on `band` | 5.8 : 1 | 6.9 : 1 | 4.5 : 1 | yes |
| message text | `text` on `band` | 15.1 : 1 | 13.3 : 1 | 4.5 : 1 | yes |
| link, current list, new list | `accent` on `bg` | 7.6 : 1 | 9.1 : 1 | 4.5 : 1 | yes |
| accent text on band | `accent` on `band` | 6.9 : 1 | 7.7 : 1 | 4.5 : 1 | yes |
| primary button label | `on-accent` on `accent` | 7.6 : 1 | 9.1 : 1 | 4.5 : 1 | yes |
| primary button, hover | `on-accent` on `accent-hover` | 10.1 : 1 | 11.5 : 1 | 4.5 : 1 | yes |
| overdue, error text | `danger` on `bg` | 6.1 : 1 | 8.3 : 1 | 4.5 : 1 | yes |
| error message text | `danger` on `danger-bg` | 5.7 : 1 | 7.5 : 1 | 4.5 : 1 | yes |
| normal text in error box | `text` on `danger-bg` | 15.5 : 1 | 14.1 : 1 | 4.5 : 1 | yes |
| danger button label | `on-danger` on `danger` | 6.1 : 1 | 8.3 : 1 | 4.5 : 1 | yes |
| danger button, hover | `on-danger` on `danger-hover` | 8.3 : 1 | 10.5 : 1 | 4.5 : 1 | yes |
| High label | `priority-high` on `bg` | 6.3 : 1 | 10.4 : 1 | 4.5 : 1 | yes |
| tag | `tag-text` on `tag-bg` | 6.9 : 1 | 9.7 : 1 | 4.5 : 1 | yes |
| title on the dragged row | `text` on `drag-bg` | 15.1 : 1 | 13.3 : 1 | 4.5 : 1 | yes |
| field and button edge on page | `control` on `bg` | 3.1 : 1 | 4.0 : 1 | 3 : 1 | yes |
| field edge on the field | `control` on `surface` | 3.2 : 1 | 3.8 : 1 | 3 : 1 | yes |
| focus ring on page | `focus` on `bg` | 7.6 : 1 | 9.1 : 1 | 3 : 1 | yes |
| focus ring on a field | `focus` on `surface` | 8.0 : 1 | 8.5 : 1 | 3 : 1 | yes |

`--border` (1.3 : 1 light, 1.5 : 1 dark) is only for lines between rows, never the only edge of a control, so the
3 : 1 rule does not apply to it. The script that made this table is short (WCAG relative
luminance, then `(L1 + 0.05) / (L2 + 0.05)`); the CUJ test below does the same in the browser.

## Type, spacing and shape

**Type scale** (rem; 1 rem = 16 px). One family, weights 400, 550, 650, 700.

| Use | Size | Weight | Line height |
|---|---|---|---|
| List name (`h1`), "Edit to-do" | 1.75 | 650, letter-spacing -0.015em | 1.2 |
| "Sharing" (`h2`) | 1.125 | 650 | 1.2 |
| Body, to-do title, inputs | 1 | 400 (title 550) | 1.5 |
| Buttons, menu, list actions, filter | 0.9375 | 550 (menu 400) | 1.5 |
| Labels, meta line, help, errors, summaries | 0.875 | labels and errors 550 | 1.5 |
| Priority, tag | 0.8125 | High 650, others 400 | 1.5 |

Dates and counts use `font-variant-numeric: tabular-nums`. Headings use `text-wrap: balance`.
Notes are at most 65 characters wide.

**Spacing scale**: `--space-1` 4 px, `--space-2` 8, `--space-3` 12, `--space-4` 16, `--space-5`
24, `--space-6` 32, `--space-7` 48. Nothing uses another value except 2 px and 3 px for borders
and the filter group's inner padding.

**Control heights**: 40 px (fields, buttons), 32 px (`.small`: header button, row actions, step
actions, Remove, Add step). At 390 px every target is at least 32 x 32 px (WCAG 2.5.8 asks 24).

## Components

### Header

A full-width bar, 56 px high, bottom line `--border`. Inside the 46rem column: the wordmark "To-do
list" (700, `--text`, no underline) left; "Logged in as mara" (`--muted`, 0.9375rem) and the
**Log out** button (secondary, small) right. One line at 390 px too. The logout form keeps
`<form method="post" action="/accounts/logout/"` at the start of its tag (a test checks it); a
`class` may only come after `action`.

### Messages

Under the header, 24 px space. Each message: `--band` background, `--text`, `--radius`, padding
12 / 16 px. `messages.error` (`.message.error`, from `message.tags`) uses `--danger-bg` and
`--danger`. Still `role="status"`. No icon, no close button (it goes away on the next page).

### List menu (`nav.lists`)

Two lines, as today: "My lists:" and "Shared with me:" in `--muted`, then the links in `--text`
without underline, 16 px apart. Hover: a 2 px `--border` line under the link. **Current list**
(`aria-current="page"`): weight 650 and a 2 px `--accent` line under it. "+ New list" in
`--accent`. A shared list's owner, "(theo)", is wrapped in a `<span class="owner">` in `--muted`:
the link's name stays "Band practice (theo)". Wraps on small screens.

### List title and owner actions

`h1` on the left, and on the same line on the right: **Rename** (`--accent`) and **Delete list**
(`--danger`), both quiet text links with an 8 px-radius `--band` hover background. A member sees
"Shared by theo" in `--muted` in the same place. They wrap under the name when the name is long.

### Add form

Two rows. Row 1: label "New to-do", the title field, full width. Row 2 on a grid: "Due date",
"Repeat", "Priority" (each a label above its field), then **Add** (primary) lined up with the
fields. At 390 px: Due date full width, Repeat and Priority side by side, Add full width. Errors
from the add (`form.title.errors` etc.) move from above the form to under their own field; their
`id`s (`id_title_error`, ...) and the fields' `aria-describedby` stay.

### Search, filter, sort (one "find" bar)

One row under a `--border` line, 32 px below the add form: the search field with its label
"Search to-dos" and the **Search** button (secondary) joined; the filter links as one segmented
group (`--surface`, `--border` edge, 8 px radius; the current link gets `--band` and weight 600;
the others `--muted`); "Sort by:" with its select and the **Sort** button (secondary). "Show all"
stays a text link after Search. At 390 px the three stack. The filter `<a>`s and "Show all" get
**no new attributes** (tests compare the whole tag with `html=True`); they are styled through
`nav.filter a` and `form.search a`.

### To-do row (`ul.todos > li`)

A CSS grid instead of one flex line. This is what keeps the fix from the other session.

```
desktop                       title (wraps)                 | Edit  Done  Delete
                               High  Due 7 Oct 2026  Overdue  Repeats every Thursday
                               #admin  #home
                               > Notes
                               > Steps: 2 of 5 done   (full width when open)

manual order (?sort=manual)  ⠿ | title ...                   | ↑ ↓  Edit  Done  Delete

390 px                        title (wraps)
                              High  Due 7 Oct 2026  Overdue  Repeats ...
                              #admin
                              Edit  Done  Delete
                              > Steps ...
```

- Columns: `[handle] minmax(0, 1fr) auto`. The handle column exists only when the list can be
  reordered (`ul.todos[data-reorder-url]`). Grid areas: `"handle main actions" "handle steps
  steps"`. At under 768 px: `"handle main" "handle actions" "handle steps"`.
- **Markup change** in `_todo_item.html`: the priority label, due date, Overdue and the repeat
  text move into `<p class="meta">` inside `.main`, under the title; the move form, Edit, Done and
  Delete move into `<div class="actions">`. Tags and notes stay in `.main`. Nothing else changes:
  same classes on the `li` (`done`, `overdue`), same `.title`, `.priority priority-N`,
  `.visually-hidden`, `time`, `.overdue-label`, `.repeat`, `.tag`, `details.notes`,
  `details.steps`, `aria-label`s and `id`. Reading order becomes title, meta, tags, notes,
  actions (today: title, notes, tags, meta, actions).
- **Title**: weight 550, `overflow-wrap: anywhere`, `min-width: 0` on its column. It can never be
  narrower than the space left by the actions, so it never squeezes to one word per line and
  nothing overlaps it.
- **Meta line**: 0.875rem `--muted`, wraps with a 4 / 12 px gap. Repeat text and dates wrap
  inside this line, so they can never push the actions.
- **Actions**: one line that never wraps, top-aligned with the title. **Edit** (quiet text
  button), **Done / Undo** (secondary, small: the one bordered button in the row), **Delete**
  (quiet text button, `--muted`, red text and `--danger-bg` on hover and focus). ↑ / ↓ are small
  secondary square buttons, before Edit.
- **Priority label**: 1 px border in `currentColor`, `--radius-label`. High: `--priority-high`,
  650. Medium and Low: `--muted`, 400. In a done row: `--muted`, 400 (equal to the done title
  color; the test checks this).
- **Overdue**: date and the "Overdue" label in `--danger`; the label in 650. No dot, no icon.
- **Tags**: `--tag-bg`, `--tag-text`, `--radius-label`, 0.8125rem; the HTML stays
  `<span class="tag">#home</span>`.
- **Done row**: title `--muted` with a line through, weight 400; priority muted; tags and notes
  stay as they are (not crossed out).
- **Notes**: `<details class="notes">` (the tag stays exactly so), summary "Notes" 0.875rem
  `--muted`, `--text` on hover; open text 0.9375rem `--muted`, max 65ch.
- **Steps**: `<details class="steps">` (exactly so, plus `open` from `?open=`). Summary as notes.
  When open: the steps in a list with a 2 px `--border` line on the left; each step's title and
  its quiet **Done / Undo** and **Delete** text buttons on one line; done steps crossed out in
  `--muted`. Then a small "New step" label, its field (32 px) and **Add step** (secondary, small).
- **Drag**: the dragged row gets `--drag-bg` and a 2 px dashed `--control` outline. The handle
  ⠿ is `--muted`, `cursor: grab`.
- **Hover** on a row: none (rows are not clickable as a whole).

### Buttons

| Kind | Look | Used for |
|---|---|---|
| Primary | `--accent` fill, `--on-accent` text | Add, Save (all forms), Share |
| Secondary | `--surface` fill, 1 px `--control` edge, `--text`; hover `--band` | Done/Undo (row), Search, Sort, Log out, Remove, Add step, Leave this list, ↑ / ↓, Cancel (a link that looks like this) |
| Danger | `--danger` fill, `--on-danger` text | Delete list (on the confirm page), Yes, delete them |
| Quiet text | no edge, `--muted`; hover `--band` and `--text` | Edit (row), Delete (row, red on hover), step Done/Undo/Delete |

All: 8 px radius, 0.9375rem, weight 550, never wrap, 1 px down while pressed, focus ring 2 px
`--focus` 2 px away. The class goes on the `<button>`; no button label changes.

### Fields

`--surface` fill, 1 px `--control` edge, 8 px radius, 40 px high, text 1rem (so iOS does not zoom
in), `font: inherit` (also the textarea: no more monospace). Placeholder `--muted`. Focus: edge
and ring `--accent`. Error: edge `--danger` (`[aria-invalid="true"]`), the message under the field,
0.875rem 550 `--danger`. Help text under the field, 0.875rem `--muted`. Labels above, 0.875rem 550
`--text`. Select and date fields get the same height and edge as text fields.

### "Clear completed" and the other confirmations

`details.clear-completed`: a box with a 1 px `--border` edge and 8 px radius; the summary
"Clear completed (2)" in `--muted`; open: the sentence in `--text`, then **Yes, delete them**
(danger). "Delete list" page: `h1` question, "This cannot be undone." in `--muted`, then **Delete
list** (danger) and **Cancel** (secondary link-button), 8 px apart.

### Sharing (owner) and Leave (member)

Its own section 48 px below the list, with a `--border` line on top. `h2` "Sharing". Members: one
row each, name left, **Remove** (secondary, small) right, a `--border` line under each row (the
HTML `<span class="title">ines</span>` stays). "Only you can see this list." in `--muted` when
there are no members. The share form: label "Username" above the field, **Share** (primary). A
member instead sees **Leave this list** (secondary) in the same place.

### Empty states (copy unchanged)

- Empty list: "Nothing to do yet. Add something above." as one `--muted` line with 32 px
  space above and below, no line under it (`<li class="empty">`).
- No match: "No to-dos match “bicycle”." the same way; "Show all" is already next to Search.
- Manual order with a filter: "Clear the filter to change the order." in `--muted`, as today.
- No members: "Only you can see this list." in `--muted`, as today.

### Edit page, "New list", "Rename list"

`h1`, then the form as one column, 36rem wide, 16 px between fields. Each Django field `div` is
a flex column: label (order 1), field (2), help (3), error (4). Labels keep Django's colon
("Notes:"; a test checks it). Buttons in a row at the end: **Save** (primary) and **Cancel**
(secondary link-button). On the edit page the order of the fields stays: Title, Due date,
Repeat, Notes, Priority, Tags.

### Mobile (390 px)

16 px side space; no horizontal scroll (the existing CUJ check stays). The header stays one line.
The add form and the find bar stack as described above. Each row: text first, then its actions on
their own line, left-aligned. Step actions stay on the step's line.

### States, checked on every page

Hover, pressed, focus (keyboard), disabled (not used today), error, empty, done, overdue,
dragging, open/closed `details`. There is no loading state: every action is a normal page load.

## Not part of this task

- **The login and sign-up pages** (`accounts/templates/registration/*.html`). They will be
  redesigned separately, with the same design as the landing page and CSS shared with
  `landing.css`. This plan does not spec them. Until that task, they only change as much as
  `base.html` changes (the new background, header and field styles apply to them too, because
  they extend `base.html`); they must keep working, and the tests for them must keep passing.
- A light/dark toggle (the system decides, as today).
- Icons, an icon library, a web font, pictures.
- New features or changed behaviour: no new pages, no new fields, no JavaScript beyond
  `reorder.js` (unchanged), no change to what the server sends after an action.
- Moving error messages from `messages.error` (bad step title, bad share username) to the field.
  They keep showing at the top, now in the error style.
- The Django admin.

## Changes to files

| File | Change |
|---|---|
| `todos/static/todos/tokens.css` | **New.** All tokens in the table above, light and dark. |
| `todos/static/todos/app.css` | **New.** All app CSS, moved out of `base.html` and redesigned. |
| `todos/static/todos/landing.css` | Its `:root` blocks are removed; it uses `tokens.css`. No visual change. |
| `todos/templates/todos/landing.html` | One `<link>` to `tokens.css` before `landing.css`. |
| `todos/templates/base.html` | The `<style>` block becomes two `<link>`s; the header gets the wordmark and an inner container; `<main>` around the content. |
| `todos/templates/todos/todo_list.html` | Wrapping `<label>`s with visible text; errors under their fields; the find bar wrapper; `<span class="owner">`; classes on buttons; `li.empty`. |
| `todos/templates/todos/_todo_item.html` | `.meta` and `.actions` wrappers; classes on buttons; a "New step" label. |
| `todos/templates/todos/todo_edit.html`, `list_form.html`, `list_confirm_delete.html` | Classes on buttons; a wrapper for Save and Cancel. |
| `todos/tests/cuj/test_journeys.py` | The color test grows; one new row-layout test (see Tests). |
| `AGENTS.md`, `README.md` | The CSS now lives in `tokens.css` and `app.css`, not in `base.html`. |
| `todos/static/todos/landing/*.webp` | Retaken at the very end (last step). |

No model, migration, view, form, URL or package change.

## Tests

Rule: test each rule once, in the lowest layer where a person would notice it. Colors and layout
are only real in a browser, so new checks are CUJ tests.

### Existing tests that check colors, layout or exact HTML

None of them has to change, **if** the constraints below are kept. Each was checked by reading it.

| Test | What it checks | Effect of the redesign |
|---|---|---|
| `cuj/test_journeys.py` `test_readable_in_light_and_dark` | Light `body` background luminance > 0.9, dark < 0.1; AA for text, done title, header, overdue, High, tag; High ≠ overdue; a done High label has the done color; dark tag background < 0.1 | Passes with the new tokens (0.93 / 0.005; all pairs above). **Extended** (see below). |
| `cuj/test_journeys.py` `test_fix_a_typo` | No horizontal scroll at 375 px; a done title's line-through does not reach the notes | Passes: `min-width: 0` and `overflow-wrap: anywhere` on the title and notes; line-through only on `.title`. |
| `cuj/test_journeys.py` `test_reorder_by_drag`, `test_escape_cancels_a_drag` | Drags `.handle` onto a row's box; `li.dragging` | Passes: the handle and the row classes stay. |
| `cuj` tests using `get_by_label("New to-do" / "Due date" / "Priority" / "Search to-dos" / "Title" / "Notes" / "Tags")` and button names (Add, Done, Undo, Delete, Edit, Share, Remove carol, Move down: Third, Add step, Yes, delete them, Leave this list, Log out, New list, Groceries (alice)) | Accessible names | Pass: `aria-label`s stay and every visible label is the same text; link text "Groceries (alice)" stays when "(alice)" is in a span. |
| `integration/test_filter.py` (filter links, `html=True`), `test_search.py` and `test_sort.py` ("Show all", `html=True`) | The whole `<a>` tag | **Constraint**: no `class` or other attribute on these links. |
| `integration/test_search.py` `test_search_box_keeps_typed_text` (`html=True`) | The whole search `<input>` | **Constraint**: no new attribute on it (no `id`, no `class`); the label wraps it. |
| `integration/test_views.py` `test_add_input_keeps_its_browser_checks` | `placeholder="What` on the title input | Passes: the placeholder stays as a hint. |
| `integration/test_search.py` (`<details class="steps" open>`), `test_views.py` (`<details class="notes">`, `<summary aria-label="Notes for …">Notes</summary>`, `<span class="overdue-label">Overdue</span>`, `<h1>Edit to-do</h1>`, `Notes:</label>`), `test_sharing.py` (`<span class="tag">#work</span>`, `<span class="title">&lt;b&gt;ben</span>`) | Exact HTML | **Constraint**: these tags keep exactly these attributes. |
| `integration/test_lists.py` `test_menu_shows_my_lists` | `aria-current="page">` exactly twice | **Constraint**: no new `aria-current` on the page (the wordmark gets none). |
| `accounts/tests/integration/test_accounts.py` | `<form method="post" action="/accounts/logout/"` and "Logged in as alice" | **Constraint**: keep the start of the tag; the text stays visible at 390 px. |

### New and extended tests (CUJ, `todos/tests/cuj/test_journeys.py`)

| Test | What it checks |
|---|---|
| `test_readable_in_light_and_dark` (extended) | Also: the primary button's text on its background, a link (`nav.lists a[aria-current]`), a field's edge on the page (≥ 3 : 1), the focus ring on a focused field (≥ 3 : 1), the meta line, an error under a field. Same helper, same two modes. |
| `test_row_keeps_its_shape` (new, unless the row fix already added one like it) | At 1280 and 390 px, a to-do with a 140-character title, High, a due date and "Repeats every …": the title's box does not overlap the priority label's box; the Edit, Done and Delete buttons have the same `y` (one line); at 1280 px they are to the right of the title; no horizontal scroll. |

Every new test is shown failing before its change and passing after (`AGENTS.md`).

## Steps

Each step is one small commit that keeps `make check` green. Look at the pages in light and dark,
at 1280 and 390 px, after each one.

0. **Wait** for the row fix and the landing page to be on `main`. Rebase on `main`.
1. **Tokens.** Add `tokens.css` with the landing values plus the new tokens. Make `landing.css`
   use it (landing looks the same: compare screenshots). Move the app CSS from `base.html` into
   `app.css`, using the new token names. Extend the color test first and see it fail on the old
   colors where it should (the field edge), then pass.
2. **Typography and frame.** Font stack, type scale, `tabular-nums`, the 46rem column, the
   header bar with the wordmark, `<main>`, spacing scale.
3. **Buttons and fields.** The four button kinds and their classes, field styles, focus ring,
   pressed state, reduced motion, label/field/help/error order, red edge on errors.
4. **The to-do row.** Write `test_row_keeps_its_shape` (or check the one from the row fix), then
   the `.meta` / `.actions` markup and the grid. Steps, notes, tags, priority, overdue, drag.
5. **Page sections.** List menu, title and owner actions, add form with visible labels and errors
   under fields, the find bar, clear completed, sharing and leave.
6. **The other app pages.** Edit, New list, Rename list, Delete list.
7. **Empty, error and message states.** `li.empty`, the error message style, the "no match" and
   "clear the filter" lines.
8. **Docs.** `AGENTS.md` (the `base.html` row and two new rows: `tokens.css`, `app.css`) and
   `README.md`. Run `make check`.
9. **Last: retake the landing page screenshots** (`todos/static/todos/landing/*.webp`, light and
   dark) so the landing page shows the new app. Same names and sizes; check the `alt` texts still
   describe what the pictures show.

## Open questions

1. **The wordmark in the header.** "To-do list" at the top left, linking to `/` (your first
   list), like on the landing page. It is the only new link. Keep it, or show it as plain text?
2. **Row actions on a phone.** The plan puts Edit, Done and Delete on their own line under the
   text at 390 px, so the title gets the full width. The other choice is a narrow column on the
   right with smaller buttons. Is a taller row on the phone fine?
3. **A quiet Delete.** In each row, Delete is gray text that turns red on hover, so the list is
   calmer. It still deletes at once with no question, as today. Fine, or keep a bordered button?
4. **Visible labels.** The add form, search, "Username" and "New step" get a small label above
   the field (the skill asks for it; today only screen readers hear these names). This makes the
   top of the list page about 40 px taller. OK?
