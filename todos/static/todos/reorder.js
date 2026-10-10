// Drag and drop to reorder the to-dos of a list. Plain JavaScript, no library.
// It uses the browser's own drag and drop (the HTML5 drag-and-drop API).
// Without JavaScript, or on a phone, the Move up / Move down buttons do the same.
(function () {
  "use strict";

  // Only when the page allows reordering (todo_list.html adds data-reorder-url).
  const list = document.querySelector("ul.todos[data-reorder-url]");
  const csrfForm = document.getElementById("reorder-csrf");
  if (!list || !csrfForm) {
    return;
  }

  let dragged = null; // The row being moved.
  let nextRow = null; // The row after it at the start, to put it back on cancel.
  let startOrder = "";

  // Only the direct rows of the list. The steps of a to-do are in their own
  // <ul> inside its row: they are never moved.
  function order() {
    return Array.from(list.querySelectorAll(":scope > li[data-id]"), (row) => row.dataset.id);
  }

  // The direct row of the list that this element is in, or null.
  function rowOf(element) {
    let row = element.closest ? element.closest("li") : null;
    while (row && row.parentElement !== list) {
      row = row.parentElement.closest("li");
    }
    return row;
  }

  list.addEventListener("dragstart", (event) => {
    // Only the handle starts a drag, not a link or selected text.
    if (!event.target.classList || !event.target.classList.contains("handle")) {
      return;
    }
    dragged = rowOf(event.target);
    if (!dragged) {
      return;
    }
    nextRow = dragged.nextElementSibling;
    startOrder = order().join(",");
    dragged.classList.add("dragging");
    event.dataTransfer.effectAllowed = "move";
    // Firefox does not start a drag at all without setData.
    event.dataTransfer.setData("text/plain", dragged.dataset.id);
    // Show the whole row moving, not only the handle.
    event.dataTransfer.setDragImage(dragged, 0, 0);
  });

  list.addEventListener("dragover", (event) => {
    if (!dragged) {
      return;
    }
    event.preventDefault(); // Needed, or the browser does not allow a drop.
    event.dataTransfer.dropEffect = "move";
    const row = rowOf(event.target);
    if (!row || row === dragged) {
      return;
    }
    // The top half of a row: before it. The bottom half: after it.
    const box = row.getBoundingClientRect();
    const after = event.clientY > box.top + box.height / 2;
    list.insertBefore(dragged, after ? row.nextElementSibling : row);
  });

  list.addEventListener("drop", (event) => {
    if (dragged) {
      event.preventDefault(); // So the browser does not open the text as a link.
    }
  });

  list.addEventListener("dragend", (event) => {
    if (!dragged) {
      return;
    }
    const row = dragged;
    dragged = null;
    row.classList.remove("dragging");
    // Escape, or dropped outside the list: put the row back, send nothing.
    if (event.dataTransfer.dropEffect === "none") {
      list.insertBefore(row, nextRow);
      return;
    }
    const ids = order();
    if (ids.join(",") === startOrder) {
      return;
    }
    // Sent once, here (not also in drop). The CSRF token comes from the page.
    const data = new FormData(csrfForm);
    ids.forEach((id) => data.append("id", id));
    fetch(list.dataset.reorderUrl, { method: "POST", body: data, credentials: "same-origin" })
      .then((response) => {
        // 400: someone changed the list a moment ago. Show what the server has.
        if (response.status !== 204) {
          location.reload();
        }
      })
      .catch(() => location.reload()); // No network.
  });
})();
