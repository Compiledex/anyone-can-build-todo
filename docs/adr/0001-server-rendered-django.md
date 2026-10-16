# 0001. Server-rendered Django pages, almost no JavaScript

| | |
|---|---|
| Type | Architecture decision record |
| Phase | Design |
| Written by | Tech lead (in this project: the owner and Claude) |
| Status | Accepted |
| Date | 2026-10-16 (written after the fact; decided 2026-10-09) |
| Data | REAL |

> **What this document is.** An ADR records one technical choice and why it was made. This one
> is about how pages are made: on the server, as plain HTML, or in the browser with a JavaScript
> framework.

## Context

- The app is small: lists, to-dos, steps, sharing. One person and a few people they share with.
- The owner is learning to program. Code must be easy to read and to test.
- Every change must be safe: a double click, an old tab, or JavaScript turned off must not break
  data.
- Django already has forms, sessions, CSRF protection (a token that stops other sites from posting
  forms in your name), login and a test client.

## Decision

Every page is HTML made on the server by Django templates. Every change is a normal HTML form
that sends `POST`, and the server answers with a redirect to a normal page
("Post/Redirect/Get"). There is no API and no frontend framework.

The only JavaScript is one small file, `todos/static/todos/reorder.js`: drag and drop for the
manual order, with the browser's own HTML5 drag and drop, no library. The Move up and Move down
buttons do the same without JavaScript.

## Consequences

- Easy: one language for the logic (Python), one place for the rules (the view), and Django's
  test client can test a whole feature from the address to the database. Most tests are
  integration tests for this reason (577 of 731).
- Easy: the app works with a keyboard and without JavaScript.
- Easy: a reload never sends a form twice, because every `POST` ends with a redirect.
- Harder: every click loads a new page. To keep the person's place, buttons send a `next` address
  with an anchor (`#todo-7`) (PR #44).
- Harder: no live updates. A member sees another person's change after a reload.
- Rule: no script or style from another site (no CDN). The landing page loads nothing from
  other sites.

## Alternatives considered

| Option | Why not |
|---|---|
| A single-page app (React or similar) with a JSON API *(added here, not in the plans)* | Two programs to build and test, and an API to secure. Too much for this app and for a beginner. |
| htmx or another small library for partial page updates *(added here, not in the plans)* | Nice, but a new dependency and new patterns. Plain forms were enough. |
| SortableJS for drag and drop | Better on touch screens, but a third party (CDN) can break or change the page. The Move buttons cover phones (drag-and-drop plan). |

## Source

- [`docs/plans/foundation.md`](../plans/foundation.md) (PR #5): `base.html`, forms, the row template.
- [`docs/plans/drag-and-drop.md`](../plans/drag-and-drop.md) (PR #25): "Plain JavaScript ... no library from a CDN".
- `AGENTS.md`, rules "Use what Django already has" and "Change data only with POST".

## Related documents

- [ADR index](README.md)
- [Design doc](../design/design-doc.md)
