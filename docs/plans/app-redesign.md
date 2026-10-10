# Plan: redesign of the app pages

Status: **approved with changes** (review below). Not started.

Starts after: the row fix (#28) and the landing page (#29), both merged, **and** the login and
sign-up redesign (`feature/auth-pages`), which creates `todos/static/todos/tokens.css`. Step 1b
needs that file on `main`.

Mockup: [`app-redesign-mockup.html`](app-redesign-mockup.html) (open it in a browser; make the
window narrow, and switch the system between light and dark, to see each version).

## Goal

The pages a person sees after logging in (the list page, the edit page, "New list", "Rename list"
and "Delete list") look calm, clear and finished, and look like **one product with the landing
page and the login pages**: the same colors, font, corners and buttons. Nothing a person does
changes: every address, form field, button label and keyboard path stays the same.

Words used in this plan:

- A **token** is a named value in CSS, like `--accent: #1f4f8f`. The pages use the name, never
  the value, so one change updates every page.
- The **contrast ratio** compares how bright two colors are, from 1 : 1 (the same color) to
  21 : 1 (black on white). **WCAG AA** is the usual rule: at least 4.5 : 1 for text, and 3 : 1 for
  the edge of a control (a text field's border, a focus ring).
- A **focus ring** is the outline that shows which button or field the keyboard is on.
- **Grid areas** are named places in a CSS grid ("main", "actions"); each part of a row is put in
  one by name, so the layout can change at a small width without changing the HTML.
- **Specificity** is how CSS decides which of two rules wins: a more exact selector
  (`ul.todos > li .title`) beats a shorter one (`.title`).

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

Screenshots of the pages before the row fix, with invented sample data, at 1280 and 390 px wide,
light and dark: `scratchpad/app-audit-shots/` (not in git; for the review only). Pages: the list
(default, steps open, search, no match, filter, manual order, owner with members, member view,
empty list), edit, new list, delete list, a form error on "New list", an add error, and a message.

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

1. **The to-do row broke** (one word per line, labels on top of the title, buttons pushed onto a
   new line). **Fixed by #28**: the row now has `.main > .title + div.meta`, then notes, then tags,
   and `.actions` that stay on one line. This plan keeps that markup and only restyles it.
2. **No visual system.** Buttons, selects and the date field are browser defaults; the edit
   page's selects are tiny and its textarea uses a monospace font. Three corner styles.
3. **The app does not look like the landing and login pages.** Pure white and pure black (an AI
   tell, skill 8.B and 9.A), no accent, no header bar, a narrower column.
4. **Errors are hard to see and far from their field.** "Enter a valid date." shows above the
   whole add form in the normal text color. On the edit page and "New list", Django puts the
   error between the label and the field. Fields with an error get no red border.
5. **Placeholder used as the label** on the add form, search, the share field, and "Add step"
   (an empty field with no hint at all). Skill 4.6: "No placeholder-as-label. Ever."
6. **No hierarchy between actions.** Add, Done, Delete, Log out, Sort, Search and Remove all look
   the same. "Delete list" looks like "Rename". "Yes, delete them" looks like any other button.
7. **No focus, hover or pressed states of our own.** The current list and filter are only bold.
8. **Search, sort and filter are three loose rows** that take 150 px before the first to-do.
9. **Too narrow on a laptop.** 512 px of content in a 1280 px window.
10. **Empty and "no match" states are a plain row** with a line under it, like a to-do.
11. **Messages** look like an input; `messages.error` looks the same as success.
12. **Edit page**: Save and Cancel touch each other; the tag help text sits between label and
    field.
13. **Dark mode** uses `#121212` and neutral grays while tags are blue-gray: two gray families.

Checked and fine: no em-dashes or en-dashes in any visible text, no exclamation marks, no fake
names, no decorative dots, no emoji. Keyboard order is logical. Row buttons' `aria-label`s name
their to-do. Nothing moves today, so reduced motion is fine.

### Patterns to keep (skill 11.C)

Every address; the order of the parts of the list page and of each row; every form field, its
`name` and its order; every button and link label; every `id` (`todo-<pk>`, `sharing-heading`,
`my-lists`, `shared-lists`, `reorder-csrf`); every `aria-label`, `aria-current`, `aria-invalid`
and `aria-describedby`; `role="status"` on messages and `role="search"`; the `next` field on Done
and Delete; `?open=` opening the steps; `<details>` for notes, steps and clear completed (they work
without JavaScript); Move up / Move down; light/dark by the system only.

## Decisions

- **One token file: `todos/static/todos/tokens.css`.** It holds only `:root` (light and dark):
  colors, `--radius`, `--radius-label`, `--font`, the spacing scale, control heights and `--ease`.
  The auth-pages branch creates it with the landing values plus `--surface`, `--control` and
  `--danger`; there, `site_base.html` loads `tokens.css`, then `site.css`, then the page's own CSS.
  **The app loads `tokens.css`, then `app.css`.** `app.css` never loads `site.css`. This plan only
  **adds** the tokens the app needs (Step 1b); it does not change a value the other pages use.
- **The app's CSS moves out of `base.html` into `todos/static/todos/app.css`**, served by
  WhiteNoise like `site.css`. No build step, no Tailwind, no JavaScript framework, no external
  request.
- **Font: the system font stack** (`--font`), as on the other pages. No web font.
- **One accent, `--accent`** (`#1f4f8f` light, `#8fb6ec` dark). It marks the primary button,
  links, the current list and filter, the focus ring and tag text. Nothing else is blue.
- **One gray family, cool** (`--text`, `--muted`, `--border`, `--control`).
- **Two status colors, only for status**: `--danger` (red: overdue, errors, destructive actions)
  and `--priority-high` (amber: the High label). The color test keeps them apart. Success and info
  messages use the calm `--band`, so a message never adds a third status color.
- **Corners: two values, one rule.** `--radius` (8px) on everything you click or type into and on
  boxes (buttons, fields, messages, the clear-completed box, the filter group). `--radius-label`
  (4px) on small things under 24px tall: priority, tag, and each filter link inside its group.
  Nothing is a pill. No third radius. (Skill 4.4 allows a written rule followed everywhere.)
- **One button vocabulary for the whole product**, the same class names as `site.css`:
  `.button` plus one of `.button-primary`, `.button-secondary`, `.button-danger`,
  `.button-quiet`, and the size `.button-small`. The app adds one size in `app.css`:
  `.button-compact` (32px, for row, step and header actions). `app.css` repeats the shared button
  rules (it does not load `site.css`), and a CUJ test checks that the primary button looks the
  same on both sides (background, radius, font weight).
- **No cards.** Rows are separated by one bottom line. The only boxes carry meaning: a message,
  the clear-completed confirmation, the filter group.
- **No icons.** Text labels, as on the landing page. The ↑ / ↓ buttons and the ⠿ handle are text
  characters and stay.
- **Fields: one structure, in DOM order**: `<div class="field">` with the label, the input, the
  error, then the help text, the same as the auth pages. No CSS `order`, so screen readers and
  sighted people get the same order. On the edit, new-list and rename pages, the forms render each
  field with the auth pages' include `todos/_field.html` (`{{ field.label_tag }}`, `{{ field }}`,
  `{{ field.errors }}`, help). The include keeps `{{ field.label_tag }}`, so Django still
  writes the `<label for>` and the required mark.
- **Labels have no colon** ("Notes", not "Notes:"), as on the new login and sign-up pages. The
  person decided this. The Django way: the app's forms (`TodoForm`, `TodoListForm`,
  `SubtaskForm`, `ShareForm`, `TodoQueryForm`) get `label_suffix = ""` (set in each form's
  `__init__`, or as a class attribute on a small shared base form in `todos/forms.py`). Then
  `label_tag` writes "Notes" and "Sort by" without a colon, everywhere the form is used. One
  test changes because of it (see Tests).
- **Visible labels on the list page**: "New to-do", "Due date", "Repeat", "Priority", "Search
  to-dos", "Sort by", "New step", "Username". The visible text is the same as, or the start of,
  the existing `aria-label`, so screen readers and the tests find the same names (WCAG 2.5.3).
  Fields that Django renders with an `id` (repeat, priority, sort) get `<label for>`. Fields
  written by hand in the template (title, due date, search, new step, username) are wrapped by
  their label, because they must not get a new `id` (tests compare the whole tag). **An error
  list or a button is never inside a `<label>`**: the error comes after the label, inside the
  `div.field`. Placeholders that are hints stay ("What needs doing?", "Search").
- **Errors under their field, in red; the field gets a red edge** (`[aria-invalid="true"]`), and
  keeps it while focused (the focus ring is accent, around the red edge).
- **Focus**: `:focus-visible` sets only `outline: 2px solid var(--accent)` and `outline-offset`.
  It never changes `border-radius` or size.
- **Width: 46rem (736px)** for the list page, 36rem for the edit and list forms.
- **A header bar** like `site_base.html`'s: the wordmark "To-do list" left (a link to `/`, as on
  the visitor pages), "Logged in as mara" (in a `<span class="who">`) and Log out right.
- **Motion**: only `background-color`, `color`, `border-color` and `transform`, 150ms
  `ease-out` (`--ease`). Buttons move down 1px while pressed. Under
  `prefers-reduced-motion: reduce`: no transition, no movement.
- **Touch**: under `@media (pointer: coarse)` (a finger, not a mouse), row and step actions are
  at least 44px tall with at least 8px between them.
- **Copy**: no visible text changes, except the new visible labels above and the colons that
  go away after labels.

## Tokens

All in `todos/static/todos/tokens.css`. "auth" = created by the auth-pages branch; "app" = added
by this plan. Dark values apply under `@media (prefers-color-scheme: dark)`.

| Token | Light | Dark | From | Used for |
|---|---|---|---|---|
| `--bg` | `#f6f7f9` | `#0e1013` | auth (landing) | page background |
| `--surface` | `#fcfcfd` | `#15181d` | auth | fields, secondary buttons, filter group |
| `--band` | `#e6edf6` | `#172231` | auth (landing) | messages, hover, current filter, tag background |
| `--text` | `#15181d` | `#e8eaee` | auth (landing) | normal text |
| `--muted` | `#545b66` | `#a3aab5` | auth (landing) | meta line, done title, header text, quiet buttons |
| `--border` | `#d3d8e0` | `#2d333b` | auth (landing) | lines between rows and sections |
| `--control` | `#737b87` | `#6f7885` | auth | edge of fields and secondary buttons |
| `--accent` | `#1f4f8f` | `#8fb6ec` | auth (landing) | primary button, links, current list, focus ring |
| `--accent-hover` | `#173d70` | `#b0cbf2` | auth (landing) | primary button and links on hover |
| `--on-accent` | `#f6f7f9` | `#0e1013` | auth (landing) | text on the primary button |
| `--danger` | `#b42318` | `#ff8f85` | auth | overdue, errors, danger button (replaces `--overdue`) |
| `--danger-hover` | `#912018` | `#ffb0a8` | app | danger button on hover |
| `--on-danger` | `#f6f7f9` | `#0e1013` | app | text on the danger button |
| `--danger-bg` | `#fbeceb` | `#2a1716` | app | error message, quiet Delete on hover and focus |
| `--priority-high` | `#8a4b00` | `#f0b46a` | app | the High label |
| `--tag-text` | `#1f4f8f` | `#b0cbf2` | app | tag text (background: `--band`) |
| `--drag-bg` | `#e6edf6` | `#172231` | app | the row being dragged |
| `--radius` | `8px` | | auth | controls and boxes |
| `--radius-label` | `4px` | | app | priority, tag, filter links |
| `--font` | system stack | | auth | everything |
| `--space-1` to `--space-7` | 4, 8, 12, 16, 24, 32, 48px | | app | all spacing |
| `--control-h`, `--control-h-compact`, `--control-h-touch` | 40, 32, 44px | | app | button and field heights |
| `--ease` | `150ms ease-out` | | app | every transition |

Light `--bg` has a relative luminance of 0.93, so the existing check "the light background is
light" (above 0.9) still passes. Dark `--bg` is 0.005 and dark `--band` (tag background) 0.015
(both under 0.1).

### Contrast (computed with the WCAG formula)

| Pair | Tokens | Light | Dark | Needs | Pass |
|---|---|---|---|---|---|
| body text on page | `text` on `bg` | 16.6 : 1 | 15.8 : 1 | 4.5 : 1 | yes |
| input text on input | `text` on `surface` | 17.4 : 1 | 14.8 : 1 | 4.5 : 1 | yes |
| muted text (meta, done title, header) | `muted` on `bg` | 6.4 : 1 | 8.1 : 1 | 4.5 : 1 | yes |
| placeholder/help on input | `muted` on `surface` | 6.7 : 1 | 7.6 : 1 | 4.5 : 1 | yes |
| muted text on band | `muted` on `band` | 5.8 : 1 | 6.9 : 1 | 4.5 : 1 | yes |
| message text on band | `text` on `band` | 15.1 : 1 | 13.3 : 1 | 4.5 : 1 | yes |
| link / current list / text button | `accent` on `bg` | 7.6 : 1 | 9.1 : 1 | 4.5 : 1 | yes |
| accent text on band (secondary hover) | `accent` on `band` | 6.9 : 1 | 7.7 : 1 | 4.5 : 1 | yes |
| primary button label | `on-accent` on `accent` | 7.6 : 1 | 9.1 : 1 | 4.5 : 1 | yes |
| primary button hover | `on-accent` on `accent-hover` | 10.1 : 1 | 11.5 : 1 | 4.5 : 1 | yes |
| overdue date, Overdue label, danger text | `danger` on `bg` | 6.1 : 1 | 8.6 : 1 | 4.5 : 1 | yes |
| error message text | `danger` on `danger-bg` | 5.7 : 1 | 7.7 : 1 | 4.5 : 1 | yes |
| body text in error box | `text` on `danger-bg` | 15.5 : 1 | 14.1 : 1 | 4.5 : 1 | yes |
| danger button label | `on-danger` on `danger` | 6.1 : 1 | 8.6 : 1 | 4.5 : 1 | yes |
| danger button hover | `on-danger` on `danger-hover` | 8.1 : 1 | 10.9 : 1 | 4.5 : 1 | yes |
| High priority label | `priority-high` on `bg` | 6.3 : 1 | 10.4 : 1 | 4.5 : 1 | yes |
| tag text on tag | `tag-text` on `band` | 6.9 : 1 | 9.7 : 1 | 4.5 : 1 | yes |
| title on dragged row | `text` on `drag-bg` | 15.1 : 1 | 13.3 : 1 | 4.5 : 1 | yes |
| current filter underline vs filter group (non-text) | `accent` on `surface` | 8.0 : 1 | 8.5 : 1 | 3.0 : 1 | yes |
| red edge of an invalid field vs field (non-text) | `danger` on `surface` | 6.4 : 1 | 8.1 : 1 | 3.0 : 1 | yes |
| quiet Delete on hover band | `danger` on `band` | 5.6 : 1 | 7.3 : 1 | 4.5 : 1 | yes |
| input/button border vs page (non-text) | `control` on `bg` | 4.0 : 1 | 4.3 : 1 | 3.0 : 1 | yes |
| input border vs input | `control` on `surface` | 4.2 : 1 | 4.0 : 1 | 3.0 : 1 | yes |
| focus ring vs page (non-text) | `accent` on `bg` | 7.6 : 1 | 9.1 : 1 | 3.0 : 1 | yes |
| focus ring vs input | `accent` on `surface` | 8.0 : 1 | 8.5 : 1 | 3.0 : 1 | yes |
luminance bg light 0.93 dark 0.005 dark band 0.015

Not a pass on its own: the current filter's `--band` fill on `--surface` is only 1.2 : 1 (light)
and 1.1 : 1 (dark). So the current filter link also gets a 2px `--accent` line under it (8.0 :
1 / 8.5 : 1), plus weight 600. `--border` (1.3 : 1 light, 1.5 : 1 dark) is only for lines between
rows, never the only edge of a control, so the 3 : 1 rule does not apply to it.

## Type, spacing and shape

**Type scale** (rem; 1rem = 16px). One family, weights 400, 550, 600, 650, 700.

| Use | Size | Weight | Line height |
|---|---|---|---|
| List name (`h1`), "Edit to-do" | 1.75 | 650, letter-spacing -0.015em | 1.2 |
| "Sharing" (`h2`) | 1.125 | 650 | 1.2 |
| Body, to-do title, inputs | 1 | 400 (title 550) | 1.5 |
| Buttons, menu, list actions, filter | 0.9375 | buttons 600 (as `site.css`), menu 400 | 1.5 |
| Labels, meta line, help, errors, summaries | 0.875 | labels and errors 600 | 1.5 |
| Priority, tag | 0.8125 | High 650, others 400 | 1.5 |

Dates and counts use `font-variant-numeric: tabular-nums`. Headings use `text-wrap: balance`.
Notes are at most 65 characters wide. `overflow-wrap: anywhere` and `min-width: 0` on every
text a person types: the list `h1`, `nav.lists a`, "Shared by <username>", the to-do title, notes,
step titles and member names. So one very long word can never make the page wider than a phone.

**Spacing scale**: `--space-1` to `--space-7` (above). Only borders (1 to 3px) use other values.

**Control heights**: 40px (fields, buttons), 32px (`.button-compact`), 44px for row and step
actions on a touch screen. Every target is at least 32 x 32px with a mouse.

## Components

### Header

A full-width bar, at least 56px high, bottom line `--border`. Inside the 46rem column: the
wordmark "To-do list" (700, `--text`, no underline, a link to `/`) left; `<span class="who">Logged
in as mara</span>` (`--muted`, 0.9375rem) and **Log out** (`.button-secondary .button-compact`)
right. The logout form keeps `<form method="post" action="/accounts/logout/"` at the start of its
tag (a test checks it); a `class` may only come after `action`. At 320px "Logged in as mara" may
wrap to two lines; it stays visible.

### Messages

Under the header, 24px space. Each message: `--band`, `--text`, `--radius`, padding 12 / 16px.
`.message.error` (from `message.tags`): `--danger-bg` and `--danger`. Still `role="status"`. No
icon, no close button.

### List menu (`nav.lists`)

Two lines, as today: "My lists:" and "Shared with me:" in `--muted`, then the links in `--text`
without underline, 16px apart, wrapping. Hover: a 2px `--border` line under the link. **Current
list** (`aria-current="page"`): weight 650 and a 2px `--accent` line under it. "+ New list" in
`--accent`. A shared list's owner, "(theo)", is in a `<span class="owner">` in `--muted`: the
link's name stays "Band practice (theo)".

### List title and owner actions

`h1` left; on the same line right: **Rename** (`--accent`) and **Delete list** (`--danger`), quiet
text links with an 8px `--band` hover background. A member sees "Shared by theo" in `--muted` in
the same place. They wrap under the name when the name is long.

### Add form

Two rows. Row 1: "New to-do" and the title field, full width. Row 2 on a grid: "Due date",
"Repeat", "Priority" (label above each), then **Add** (`.button-primary`) lined up with the fields.
At 390px: Due date full width, Repeat and Priority side by side, Add full width. Each error
(`form.title.errors` and so on) moves from above the form into its field's `div.field`, after the
input; its `id` (`id_title_error`, ...) and the field's `aria-describedby` stay. The priority and
repeat selects stay exactly as Django renders them (no new widget attributes or classes in
`forms.py`, no new `id`).

### Search, sort, filter (one "find" bar)

One row under a `--border` line, 32px below the add form, **in the HTML order: search, sort,
filter** (no DOM move). Search: the label "Search to-dos" wraps the field and the **Search**
button sits after the label (`.button-secondary`), "Show all" after it. Sort: "Sort by" (Django's
`label_tag`, no colon), its select, **Sort** (`.button-secondary`). Filter: the three links as one group
(`--surface`, 1px `--border` edge, `--radius`); each link has `--radius-label`; the current one
gets `--band`, weight 600 and a 2px `--accent` line under it; the others `--muted`. At 390px the
three stack. The filter `<a>`s and "Show all" get **no new attributes** (tests compare whole tags);
they are styled through `nav.filter a` and `form.search a`. `<form class="sort" method="get">`
keeps exactly that start; `<form class="search"` keeps `class` first.

### To-do row (`ul.todos > li`) - CSS only

The markup from #28 stays as it is: `.handle` (manual order only), `.main` (`.title`, then
`div.meta` with priority, due date, Overdue and repeat, then `details.notes`, then `.tags`),
`.actions` (move form, Edit, Done/Undo form, Delete form), `details.steps`. This plan changes only
CSS, plus button classes.

```
1280px, normal         title (wraps)                         | Edit  Done  Delete
                       High  Due 7 Oct 2026  Overdue  Repeats every Thursday
                       > Notes
                       #admin  #home
                       > Steps: 2 of 5 done   (full width when open)

1280px, manual order  ⠿ | title ...                           | ↓  Edit  Done  Delete

390px, normal          title / meta / notes / tags
                       Edit  Done  Delete
                       > Steps

390px, manual order   ⠿ | title / meta / notes / tags
                        | ↑ ↓  Edit  Done  Delete
                        | > Steps
```

Grid (columns, then areas):

| Width | Normal | Manual order (`ul.todos[data-reorder-url]`) |
|---|---|---|
| 768px and up | `minmax(0, 1fr) auto`; `"main actions" "steps steps"` | `auto minmax(0, 1fr) auto`; `"handle main actions" "handle steps steps"` |
| under 768px | `minmax(0, 1fr)`; `"main" "actions" "steps"` | `auto minmax(0, 1fr)`; `"handle main" "handle actions" "handle steps"` |

- **Title**: 550, `display: block`, `overflow-wrap: anywhere`; `.main` has `min-width: 0`. The
  actions column takes only what it needs, so the title never squeezes to one word per line and
  nothing overlaps it.
- **Meta line**: 0.875rem `--muted`, wraps with a 4 / 12px gap, inside `.main`, so a long repeat
  text can never push the actions.
- **Actions**: one line (`flex-wrap: nowrap`) at 768px and up, top-aligned with the title.
  **Edit** (`.button-quiet .button-compact`; it stays a plain link with its `aria-label`),
  **Done / Undo** (`.button-secondary .button-compact`: the one bordered button in the row),
  **Delete** (`.button-quiet .button-compact`; `--muted`, and `--danger` on `--danger-bg` on
  hover **and** on `:focus-visible`). ↑ / ↓: `.button-secondary .button-compact`, before Edit.
  Under 768px the actions get their own line and may wrap; with a finger they are 44px tall,
  8px apart.
- **Priority label**: 1px `currentColor` edge, `--radius-label`. High: `--priority-high`, 650.
  Medium and Low: `--muted`, 400. In a done row: `--muted`, 400 (the test checks it equals the
  done title).
- **Overdue**: date and "Overdue" in `--danger`, the label 650. No dot, no icon.
- **Tags**: `--band`, `--tag-text`, `--radius-label`, 0.8125rem; the HTML stays
  `<span class="tag">#home</span>`.
- **Done row**: title `--muted`, line-through, 400; priority muted; tags and notes are not
  crossed out.
- **Notes**: summary "Notes" 0.875rem `--muted`; the open text 0.9375rem `--muted`, max 65ch,
  `overflow-wrap: anywhere` (a long URL wraps).
- **Steps**: summary as notes. Open: a 2px `--border` line on the left; each step's title and its
  quiet **Done / Undo** and **Delete** on one line; done steps crossed out in `--muted`. Then the
  "New step" label wrapping its field (32px), and **Add step** (`.button-secondary
  .button-compact`) after the label.
- **Drag**: the dragged row gets `--drag-bg` and a 2px dashed `--control` outline. The handle is
  `--muted`, `cursor: grab`, in its own grid area.

### Buttons

| Class | Look | Used for |
|---|---|---|
| `.button .button-primary` | `--accent` fill, `--on-accent` text | Add, Save, Share |
| `.button .button-secondary` | `--surface`, 1px `--control` edge, `--text`; hover `--band` | Done/Undo (row), Search, Sort, Log out, Remove, Add step, Leave this list, ↑ / ↓ |
| `.button .button-danger` | `--danger` fill, `--on-danger` text | Delete list (confirm page), Yes, delete them |
| `.button .button-quiet` | no edge, `--muted`; hover `--band` and `--text` | Edit, Delete (row, red on hover and focus), step Done/Undo/Delete |
| `.button-small` / `.button-compact` | 40px / 32px tall | header, rows, steps, Remove |

All: `--radius`, 0.9375rem, weight 600, never wrap, 1px down while pressed, the focus ring.
Labels do not change. **Cancel** stays a plain `<a href="...">Cancel</a>` with no class (a test
compares the whole tag); `.form-actions > a` gives it the secondary look.

### Fields

`--surface` fill, 1px `--control` edge, `--radius`, 40px, text 1rem (so iOS does not zoom),
`font: inherit` (also the textarea: no monospace). Placeholder `--muted`. Focus: edge `--accent`
and the ring. Error: edge `--danger`, kept while focused; the message after the input, 0.875rem
600 `--danger`. Help after the error, 0.875rem `--muted`. Labels 0.875rem 600 `--text`.

### "Clear completed" and the other confirmations

`details.clear-completed`: 1px `--border` edge, `--radius`; summary "Clear completed (2)" in
`--muted`; open: the sentence, then **Yes, delete them** (`.button-danger`). "Delete list" page:
`h1` question, "This cannot be undone." in `--muted`, then **Delete list** (`.button-danger`) and
Cancel (plain link, secondary look), 8px apart, in `.form-actions`.

### Sharing (owner) and Leave (member)

Its own section 48px below the list, a `--border` line on top. `h2` "Sharing". One row per
member: name left (`<span class="title">ines</span>` stays), **Remove** (`.button-secondary
.button-compact`) right. "Only you can see this list." in `--muted` when empty. The share form:
the label "Username" wraps its field, **Share** (`.button-primary`) after the label. A member
sees **Leave this list** (`.button-secondary`) instead.

### Empty states (copy unchanged)

- Empty list: "Nothing to do yet. Add something above." as one `--muted` line, 32px above and
  below, no line under it (`<li class="empty">`).
- No match: "No to-dos match “bicycle”." the same way; "Show all" is next to Search.
- Manual order with a filter: "Clear the filter to change the order." in `--muted`.
- No members: "Only you can see this list." in `--muted`.

### Edit page, "New list", "Rename list"

`h1`, then one column, 36rem wide, 16px between fields. Each field through `todos/_field.html`:
label (no colon), input, error, help, in DOM order. The edit page's field order stays:
Title, Due date, Repeat, Notes, Priority, Tags. "A repeating to-do needs a due date." is an error
of the **Repeat** field, so it shows under Repeat. Save (`.button-primary`) and Cancel in
`.form-actions`.

### Mobile (390px and 320px)

16px side space; no horizontal scroll at 390 or 320px. The header stays one bar. The add form and
the find bar stack. Each row: text first, then its actions on their own line. Step actions stay on
the step's line.

### States, checked on every page

Hover, pressed, focus (keyboard), invalid, invalid and focused, empty, done, overdue, dragging,
open/closed `details`, touch sizes. There is no loading state: every action is a normal page load.

## Not part of this task

- **The login and sign-up pages.** They are redesigned separately (`feature/auth-pages`): they
  now extend `todos/site_base.html` and use `site.css`, not `base.html`, so this plan does not
  touch them. This plan reuses that branch's `tokens.css` and `todos/_field.html`.
- **The landing page.** `landing.html` and its CSS are not touched, except its screenshots (last
  step).
- A light/dark toggle; icons, an icon library, a web font, pictures.
- New features or changed behaviour: no new page, field or JavaScript; `reorder.js` unchanged.
- Moving `messages.error` texts (bad step title, bad share username) to the field. They keep
  showing at the top, now in the error style.
- The Django admin.

## Changes to files

| File | Change |
|---|---|
| `todos/static/todos/tokens.css` | Add the "app" tokens in the table. No existing value changes. |
| `todos/static/todos/app.css` | **New.** First the current app CSS word for word (1a), then the redesign. |
| `todos/templates/base.html` | `<style>` becomes `<link>`s to `tokens.css` and `app.css`; header with wordmark, inner container and `<span class="who">`; `<main class="container">`. |
| `todos/templates/todos/todo_list.html` | `div.field`s and labels; errors after their inputs; the find bar wrapper; `<span class="owner">`; button classes; `li.empty`. |
| `todos/templates/todos/_todo_item.html` | Button classes and the "New step" label only. |
| `todos/forms.py` | `label_suffix = ""` on the app's forms (no colon after labels). No other change: no widget attribute or class. |
| `todos/templates/todos/todo_edit.html`, `list_form.html`, `list_confirm_delete.html` | Fields through `todos/_field.html`; `.form-actions`; button classes. |
| `todos/tests/cuj/test_journeys.py` | Color test extended; row layout test extended; the header color selector; the shared-button check (see Tests). |
| `scripts/landing_shots.py`, `scripts/landing_seed.py`, `Makefile` | **New.** The landing screenshot tool and `make landing-shots` (Step 9). |
| `todos/static/todos/landing/*.webp` | Retaken at the end. |
| `AGENTS.md`, `README.md` | `app.css` and `tokens.css` rows; `base.html` no longer holds CSS; `make landing-shots`. |

No model, migration, view, URL or package change. The only form change is `label_suffix = ""`. `landing.css`, `landing.html`,
`site.css` and `site_base.html` are not changed.

## Tests

Rule: test each rule once, in the lowest layer where a person would notice it. Colors and layout
are only real in a browser, so the new checks are CUJ tests.

### Existing tests that check colors, layout or exact HTML

Two existing lines have to change, and the rest pass **if** the constraints in this table are
kept. Each was checked by reading it.

**Tests that must change:**

| Test | Today | After | Why |
|---|---|---|---|
| `integration/test_views.py` line 579 (the edit page shows the Notes field) | `assertContains(response, "Notes:</label>")` | `assertContains(response, "Notes</label>")` | The person decided no colon after labels (`label_suffix = ""`). |
| `cuj/test_journeys.py` line 183 (`test_readable_in_light_and_dark`) | `color("header.site", "color")` | `color("header.site .who", "color")` | The header now holds the wordmark in `--text`; the muted "Logged in as" text is the span. |

Checked and not affected by the colon: `test_views.py` lines 193-195 (`id="id_title_error"`,
`aria-describedby`, `aria-invalid`), and the CUJ `get_by_label("Name")`, `("Title")`, `("Notes")`,
`("Tags")` (Playwright matches the label text without the colon too).

| Test | What it checks | Effect / constraint |
|---|---|---|
| `cuj/test_journeys.py` `ColorSchemeTests.test_readable_in_light_and_dark` | Light `body` luminance > 0.9, dark < 0.1; AA for text, done title, header, overdue, High, tag; High ≠ overdue; done High = done title; dark tag background < 0.1 | Passes (0.93 / 0.005; all pairs above). **Changes** at line 183 (see above). **Extended** (below). |
| `cuj/test_journeys.py` `RowLayoutTests.test_a_full_row_stays_readable` | Title and priority do not overlap; title fits its box; Done and Delete on one line; 1280 and 390, normal and manual, light and dark | Passes with the CSS grid. **Extended** (below). |
| `cuj/test_journeys.py` `test_fix_a_typo` | No horizontal scroll at 375px; the line-through does not reach the notes | Passes (`overflow-wrap`, line-through only on `.title`). |
| `cuj/test_journeys.py` `test_reorder_by_drag`, `test_escape_cancels_a_drag` | Drags `.handle` onto a row; `li.dragging` | Passes: classes stay. |
| CUJ `get_by_label(...)` and button names | Accessible names | Pass: `aria-label`s stay; visible labels use the same text. |
| `integration/test_filter.py` (filter links), `test_search.py` and `test_sort.py` ("Show all"), all `html=True` | The whole `<a>` tag | No `class` or other attribute on these links. |
| `integration/test_search.py` `test_search_box_keeps_typed_text` (`html=True`) | The whole search `<input>` | No new attribute (no `id`, no `class`); its label wraps it. |
| `integration/test_sort.py` `test_forms_keep_each_other` (lines 109-115) | `<form class="sort" method="get">` exact start; finds `<form class="search"` | Keep both starts exactly. |
| `integration/test_views.py` `test_add_input_keeps_its_browser_checks` | `placeholder="What` on the title input | The placeholder stays as a hint. |
| `integration/test_views.py` lines 688-693 (`assertInHTML` of the add form's priority select with an error) | `<select name="priority" aria-label="Priority" aria-invalid="true" aria-describedby="id_priority_error" id="id_priority">` | No widget attribute or class added in `forms.py`; no new `id`; the `<label for="id_priority">` is outside the select. |
| `integration/test_views.py` line 912 | `aria-label="Repeat"` | Stays on the repeat select. |
| `integration/test_views.py` line 114 | The title's `</span>` comes before `<details class="notes">` | Row order unchanged (CSS only). |
| `integration/test_views.py` lines 467-471, `test_sharing.py` line 701 | `<a href="...">Cancel</a>` exactly | Cancel gets no class; styled by `.form-actions > a`. |
| `integration/test_views.py` (`<details class="notes">`, `<summary aria-label="Notes for …">Notes</summary>`, `<span class="overdue-label">Overdue</span>`, `<h1>Edit to-do</h1>`), `test_search.py` (`<details class="steps" open>`), `test_sharing.py` (`<span class="tag">#work</span>`, `<span class="title">&lt;b&gt;ben</span>`) | Exact HTML | These tags keep exactly these attributes. |
| `integration/test_lists.py` `test_menu_shows_my_lists` | `aria-current="page">` exactly twice | No new `aria-current` (the wordmark gets none). |
| `accounts/tests/integration/test_accounts.py` | `<form method="post" action="/accounts/logout/"` and "Logged in as alice" | Keep the start of the tag; the text stays visible at 390px. |

### New and extended tests (CUJ, `todos/tests/cuj/test_journeys.py`)

| Test | What it checks |
|---|---|
| `test_readable_in_light_and_dark` (extended) | Also: the primary button's text on its background; a link (`nav.lists a[aria-current]`); a field's edge on the page (≥ 3 : 1); the focus ring on a focused field (≥ 3 : 1); the meta line; an error under a field; the current filter's underline on its group (≥ 3 : 1). Same helper, both modes. |
| `RowLayoutTests.test_a_full_row_stays_readable` (extended) | The to-do gets a 140-character title, notes with an 80-character unbroken URL, and steps; notes and steps are open (`?open=`). Widths 1280, 390 **and 320**. New checks: at 1280 the actions are to the right of the title (`actions.x >= title.x + title.width`); no horizontal scroll (`scrollWidth <= clientWidth`); the open notes and steps stay inside the row. |
| `test_primary_button_is_the_same_everywhere` (new) | On `/` logged out (landing, `.button-primary`) and on the list page (Add): the computed `background-color`, `border-radius` and `font-weight` are equal, in light and dark. |

Every new check is shown failing before its change and passing after (`AGENTS.md`).

## Steps

Each step is one small commit that keeps `make check` green. Look at the pages in light and dark,
at 1280, 390 and 320px, after each one.

0. **Wait** for `feature/auth-pages` (it creates `tokens.css` and `todos/_field.html`). Rebase on
   `main`.
1. **a. Move.** Move the current CSS from `base.html` into `app.css` word for word; `base.html`
   links it. No visual change (compare screenshots).
   **b. Tokens.** Extend the color test first and see it fail (the field edge, the current filter
   line). Add the app tokens to `tokens.css`, link `tokens.css` before `app.css`, switch `app.css`
   to the new names and values. The test passes.
2. **Typography and frame.** `label_suffix = ""` on the app's forms and the `Notes</label>`
   test change (change the test first and show it failing). Type scale, `tabular-nums`, the
   46rem column, the header bar with the wordmark and `.who` (change the test selector here),
   `<main>`, spacing.
3. **Buttons and fields.** The button classes on every button, field styles, the focus ring,
   pressed state, reduced motion, touch sizes, `div.field` structure, `_field.html` on the edit
   and list forms, red edge on errors. Add `test_primary_button_is_the_same_everywhere` first.
4. **The to-do row (CSS only).** Extend `RowLayoutTests` first (it fails at 320px or on the
   actions position), then the grid for both widths and the manual order, steps, notes, tags,
   priority, overdue, drag.
5. **Page sections.** List menu, title and owner actions, add form with labels and errors after
   their fields, the find bar, clear completed, sharing and leave.
6. **The other app pages.** Edit, New list, Rename list, Delete list.
7. **Empty, error and message states.** `li.empty`, the error message style, the "no match" and
   "clear the filter" lines.
8. **Docs.** `AGENTS.md` and `README.md`. Run `make check`.
9. **Last: retake the landing page screenshots.** Commit the tool first: `scripts/landing_shots.py`
   and its seed `scripts/landing_seed.py` (a scratch database, never `db.sqlite3`; a free port,
   never 8000), and `make landing-shots`. Then retake the 7 pairs in
   `todos/static/todos/landing/`, each `-light.webp` and `-dark.webp`, 1088px wide (544 CSS px at
   2x): `list` (1088 x 1266), `share-owner` (1088 x 466), `share-member` (1088 x 334), `steps`
   (1088 x 612), `find` (1088 x 896), `order` (1088 x 734), `compare` (1088 x 838; the light and
   dark halves). Heights will change with the new layout: update `width`/`height` in
   `landing.html` to match, and check each `alt` text still describes the picture. The login and
   sign-up pages reuse `list-*.webp`, so check them too.

## Open questions

Each with a recommendation.

1. **One look for the secondary button across the whole product?** Today the visitor pages'
   secondary button is a blue outline; this plan's app buttons use a gray edge (`--control`),
   because a list page has many secondary buttons and blue everywhere would be loud.
   *Recommendation:* one gray-edge look everywhere (change `site.css` to match, in the auth-pages
   branch or a small follow-up), so "one product" holds. The other choice: blue outline on
   visitor pages, gray in the app.
2. **Row actions on phones, and the row Delete.** On phones the actions get their own line, at
   least 44px tall. The row Delete is quiet gray, red on hover and keyboard focus, or always red.
   *Recommendation:* own line on phones; quiet gray Delete (a list of red words is loud, and the
   row already has one bordered button). On a phone there is no hover, so it shows gray until
   tapped.
3. **Visible labels** above "New to-do", search, "Username" and "New step" (about 40px more at the
   top of the list page). *Recommendation:* yes: the skill and WCAG both ask for a visible label,
   and "New step" has no hint at all today.
4. **Keep the landing screenshot script in the repo**, with `make landing-shots`.
   *Recommendation:* yes: every later visual change needs new screenshots, and a script makes them
   the same each time with invented data only.

## Review

Changes after the review (approved with changes):

- The row fix (#28) is merged: the row is now **CSS only**. The plan keeps `div.meta`, notes
  before tags, `.actions`. The new row test was dropped; `RowLayoutTests.test_a_full_row_stays_readable`
  is extended instead (140-character title, 80-character URL in notes, notes and steps open, 320px,
  actions right of the title at 1280px, no horizontal scroll). The mockup uses this markup.
- **One token file** `tokens.css`, from the auth-pages branch (with its `--control` and `--danger`
  values, contrast recomputed); this plan only adds tokens. `landing.css` and `landing.html` are no
  longer changed. The auth pages extend `site_base.html`, not `base.html`.
- **One button vocabulary** (`.button`, `-primary`, `-secondary`, `-danger`, `-quiet`, `-small`,
  plus the app's `-compact`), buttons at weight 600 like `site.css`, and a new CUJ check that the
  primary button looks the same on the landing page and in the app.
- Cancel stays a plain link, styled by `.form-actions > a`.
- More constraints in the test table: the priority select `assertInHTML`, the sort and search form
  starts, `aria-label="Repeat"`, title before notes, and the header color test now reads
  `header.site .who`.
- The current filter gets a 2px accent line (its fill alone is 1.2 : 1); filter links use
  `--radius-label` (no third radius).
- Accessibility: fields in DOM order through `todos/_field.html` (no CSS `order`); no error list
  or button inside a `<label>`; `:focus-visible` sets only the outline; an invalid focused field
  keeps its red edge; 44px touch targets with 8px gaps; Delete red on focus too. The mockup's
  "needs a due date" error moved under Repeat, where Django puts it.
- The find bar keeps the HTML order: search, sort, filter.
- Both grid layouts for the manual order (with a handle area) are written out; long words wrap in
  the `h1`, the list menu and "Shared by"; 320px is checked.
- Step 1 is split into 1a (move, no visual change) and 1b (tokens). Step 9 commits the screenshot
  tool with `make landing-shots` and lists the 7 image pairs. "Grid areas" and "specificity" are
  explained. The wordmark question is gone (kept, as on `site_base.html`). New open questions.
- Decided by the person: **no colon after labels**. `label_suffix = ""` on the app's forms;
  `todos/_field.html` keeps `{{ field.label_tag }}`; `test_views.py` line 579 (`Notes:</label>`)
  changes to `Notes</label>`. Lines 193-195 do not check a colon and stay.
