# Plan: dark mode

Status: **done** (2026-10-09, PR #6). The decisions are in "Decided by the person" at the end.

Builds on: wave 0 (the shared template `todos/templates/base.html` that every page extends, and
the colors of the page as CSS variables on `:root`). It does not need accounts (wave 1, built at
the same time), and works the same for every user. If accounts is merged first, the test must log
in first (see "Tests").

## Goal

When a person's computer or phone is set to dark mode, every page of the app has a dark
background and light text. When it is set to light mode, the pages look as they do today. All
text that we color stays easy to read in both modes: it meets **WCAG AA**.

**WCAG AA** is a common rule for readable text: the *contrast ratio* between text and its
background must be at least **4.5 to 1** for normal text. The contrast ratio compares how bright
two colors are. Black on white is 21 to 1, the highest. The same color on itself is 1 to 1.

## Decisions

- **Follow the operating system only. No toggle button.** CSS can ask the browser which mode the
  person chose in their system settings, with the *media query* `prefers-color-scheme: dark`. A
  media query is a CSS rule that only applies when a condition is true. This needs no Python, no
  JavaScript, no database field, no cookie and no new view. It is the smallest version.
- **Why not a toggle.** A toggle needs a place to save the choice (a cookie, `localStorage`, or a
  field on the user), a `POST` view or some JavaScript, and more tests. Most people already set
  dark mode once, for their whole device. A toggle can be its own task later (see "Not part of
  this task").
- **All the CSS is in `base.html`.** Wave 0 made one shared template that every page extends. The
  dark-mode CSS goes there, so the list page, and later the login, sign-up and edit pages, are
  all dark with no copying.
- **Only the color variables change.** Wave 0 put the colors in CSS variables on `:root`. Dark
  mode gives the same variables new values inside one `@media (prefers-color-scheme: dark)` block.
  If wave 0 has no variable yet for the page background and the normal text (today the page uses
  the browser's default white and black), add `--bg` and `--text`, and use them on `body`.
- **Light mode looks exactly as today.** The light values are today's colors: white background,
  black text, `#666` for a done title, `#ddd` for the line.
- **The browser draws the form controls.** `color-scheme: light dark` tells the browser the page
  supports both modes. The browser then draws the text field, the buttons and the scroll bar in
  dark colors too, by itself. We do not style the buttons by hand. Their colors are the browser's
  job, so we check them by eye (Steps), not in a test.
- **A `<meta name="color-scheme" content="light dark">` tag** in `<head>`. It lets the browser
  choose the dark background before it reads any CSS, so there is no white flash. Our CSS is
  inside the page, so the flash would be very short anyway; the tag is one line, so we add it.

### The colors

The variable names below are examples. Use the names wave 0 chose; the values are what matter.

| Variable | Light (as today) | Dark | Used for |
|---|---|---|---|
| `--bg` | `#ffffff` | `#121212` | page background |
| `--text` | `#000000` | `#e8e8e8` | normal text |
| `--muted` | `#666666` | `#a0a0a0` | the title of a done to-do |
| `--border` | `#dddddd` | `#3a3a3a` | the line between to-dos |

Contrast, computed with the WCAG formula:

| Pair | Light | Dark | AA needs |
|---|---|---|---|
| text on background | 21 : 1 | 15.3 : 1 | 4.5 : 1 |
| done title on background | 5.7 : 1 | 7.2 : 1 | 4.5 : 1 |

The border line is decoration, not text, so the 4.5 rule does not apply to it.

The dark background is very dark grey, not pure black, and the text is light grey, not pure
white. This is easier on the eyes, and still far above AA.

If wave 0 or accounts adds any other color (for example a red for form errors), it gets a dark
value in the same block, with at least 4.5 : 1 on `--bg` in both modes.

## Not part of this task

- **A toggle button**, and saving the choice in a cookie, `localStorage` or the user's account.
  This can be a later task. It would build on these same variables.
- **Colors added by later features.** For example, the red date of an overdue to-do (wave 2, due
  date) and colors for priority or tags (wave 3). Each of those plans must give its new color a
  dark value too, and check it is at least 4.5 : 1 on `--bg` in both modes. (Checked: the
  due-date plan's light red `#b00020` is only 2.6 : 1 on `#121212`; its dark red `#ff6b6b` is
  6.8 : 1, which is fine.) Those features can add their color to the CUJ test below.
- **The Django admin** (`/admin/`). Django 5.2's admin already has its own dark mode.

## Changes to files

| File | Change |
|---|---|
| `todos/templates/base.html` | Add the `<meta name="color-scheme">` tag. In the `<style>`: `color-scheme: light dark;` on `:root`, `background`/`color` from the variables on `body`, and one `@media (prefers-color-scheme: dark)` block with the dark values. |
| `todos/tests/cuj/test_journeys.py` | One new CUJ test (see "Tests"). |
| `AGENTS.md`, `README.md` | One line each: the pages follow the system's light or dark mode. |

No model, no migration, no view, no URL, no new package.

**Accounts is built in the same wave** and also edits `base.html` (a header with "Log out"). This
only means a small merge conflict in one file. Whoever merges second keeps both changes, and
checks that every color variable in `:root` has a dark value.

The CSS looks like this (with wave 0's variable names):

```css
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --text: #000000;
  --muted: #666666;
  --border: #dddddd;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121212;
    --text: #e8e8e8;
    --muted: #a0a0a0;
    --border: #3a3a3a;
  }
}
body { background: var(--bg); color: var(--text); /* ...the rest as today */ }
```

## Tests

Rule: test each rule once, in the lowest layer where a person would notice it. A person notices
colors only in a real browser, and only a browser knows which mode the system is in. So the test
is a **CUJ** test. An integration test that only looks for the text `prefers-color-scheme` in the
HTML would prove nothing about what a person sees, so we do not write one.

Playwright can pretend the system is in light or dark mode on the page the test already has:
`self.page.emulate_media(color_scheme="dark")`. The test uses the normal `BrowserTestCase` page,
so `tearDown` closes it even when the test fails. (Playwright's default is light.)

| Test | Layer | What it checks |
|---|---|---|
| `test_readable_in_light_and_dark` | CUJ, in `todos/tests/cuj/test_journeys.py` | Add two to-dos, mark one done. Then, first in light mode and then in dark mode: the page background is light (or dark); the contrast of normal text and of the done title on the background is at least 4.5 : 1. |

One test, not two: the steps in the browser (adding to-dos) are the slow part, so we do them once
and check both modes on the same page. Light mode is checked too, so that changing the variables
cannot break today's look without a test failing.

How the test reads the colors: `getComputedStyle` in the page, through `page.evaluate`, gives the
real color the browser uses, for example `rgb(18, 18, 18)`. Read the background of `body`, the
color of a normal to-do's `.title`, and the color of the done to-do's `.title`. A small function
in the test file turns two such colors into a contrast ratio with the WCAG formula.

- The function accepts only a solid `rgb(r, g, b)`. For anything else it **fails the test** with a
  clear message. This matters: if `body` has no background, the browser says
  `rgba(0, 0, 0, 0)` (see-through). Read as black, that would make the dark check pass by mistake.
- "Dark background" means its *relative luminance* (brightness, from 0 for black to 1 for white)
  is below 0.1; "light" means above 0.9.

**If accounts is merged first**, the list page needs a logged-in user. The test then makes a user
and calls `self.log_in_as(user)` (the helper accounts adds to `todos/tests/cuj/browser.py`)
before it opens the page.

This is the only new test. The existing tests must all still pass.

## Steps

The order follows `AGENTS.md`: write the test, see it fail, then write the code.

1. **Test first.** Write the CUJ test. Run `make test`. It fails in the dark part, because the
   background is still white. Show this failure to the person.
2. **The CSS.** Add `color-scheme`, the `<meta>` tag, the `body` background and the dark block
   to `todos/templates/base.html`.
3. **Run `make test`.** The test passes.
4. **Look at it.** `make run`, then switch the system to dark mode and back (on a Mac: System
   Settings, Appearance). Check the text field and its grey hint text, the buttons, the
   empty-list message, and (if accounts is merged) the login page and the header. Also look at a
   narrow window.
5. **Docs.** One line in `AGENTS.md` and `README.md`.
6. **Run `make check`**, then commit.

## Open questions

- **Is a toggle wanted later?** If yes, the smallest version is a cookie read by the template
  (no JavaScript needed, works without an account). Not now.

## Review

- Moved all CSS changes from `todo_list.html` to `todos/templates/base.html`, because wave 0 now
  makes that shared template; removed the "where does the CSS live" open question.
- Fixed the dark done-title contrast: it is 7.2 : 1, not 7.9 : 1 (recomputed all ratios).
- Light text is `#000000` (today's browser default), so light mode really looks as today.
- Said to add `--bg` and `--text` if wave 0 did not make them (today the page has no background
  or text color).
- Added: if accounts is merged first, the test must log in with `log_in_as`, or it would only see
  the login page.
- The contrast helper must fail on a see-through `rgba(0, 0, 0, 0)` background, which would
  otherwise pass the dark check even when the CSS is broken.
- Two CUJ tests became one test that checks both modes on one page: same coverage, half the slow
  browser steps.
- Used `page.emulate_media` on the normal test page instead of new contexts, so nothing is left
  open when a test fails.
- Corrected the due-date note: that plan now uses `#ff6b6b` for dark mode (6.8 : 1, fine).
- Said that the merge with accounts is a small conflict in `base.html`, and who checks the colors.
- Made clear that browser-drawn controls (buttons, hint text) are checked by eye, not by the test.
- Names aligned with lists.md and accounts.md (orchestrator pass).

## Decided by the person (2026-10-09)

The plan is **approved**.

- Follow the operating system only. No toggle button for now.
