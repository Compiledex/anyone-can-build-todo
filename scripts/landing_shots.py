"""Take the landing page's screenshots of the app again: `make landing-shots`.

It makes a scratch database in a new temporary folder (never db.sqlite3), fills it
with invented sample data (scripts/landing_seed.py), starts the app on a free port
(never 8000), and takes each picture in light and dark mode with Playwright's
Chromium. The window is 800 CSS pixels wide, so the app shows its laptop layout
(768px and up). The pictures are WebP files, 1088 pixels wide (the 704 CSS pixels
of the page's column and 8px of background on each side, at about 1.5x), in
todos/static/todos/landing/. At the end it stops the server, deletes the temporary
folder, and prints the size of each picture.

If a height changed, update `width` and `height` in todos/templates/todos/landing.html
(and in accounts/templates/registration/_auth_shot.html for `list`), so the page does
not jump while the pictures load.
"""

import base64
import json
import math
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "todos/static/todos/landing"
VIEWPORT_WIDTH = 800  # Wide enough for the laptop layout of a row.
SIDE = 8  # Background on the left and right of the page's column.
IMAGE_WIDTH = 1088  # Pixels; the landing page shows it at most 544px wide.
SPACE = 16  # Background above a picture.
# Background below a picture. Less than a row's own 16px of space at the top, so
# the edge of the next row's buttons never shows at the bottom of a picture.
BELOW = 12
MAX_BYTES = 200_000

# name: (who, address, the top element, the space above it, the bottom element)
# The address uses the ids from landing_seed.py: {home}, {trip}, {garden}, {paint}.
# The space above is SPACE, but no picture may show a line of the part above it:
# "find" and "compare" start at the search form (under the find bar's top line),
# "share-owner" at its heading (under the Sharing line), and "order" and "steps"
# at the to-do itself with no space (a row has its own 16px of space at the top,
# and the line over it belongs to the row before).
SHOTS = {
    "list": (
        "mara",
        "/lists/{home}/",
        "nav.lists",
        SPACE,
        "ul.todos > li:nth-child(2)",
    ),
    "steps": (
        "mara",
        "/lists/{home}/?open={paint}",
        "#todo-{paint}",
        0,
        "#todo-{paint}",
    ),
    "share-owner": ("mara", "/lists/{trip}/", "#sharing-heading", SPACE, ".sharing"),
    "share-member": ("theo", "/lists/{trip}/", "nav.lists", SPACE, ".list-head"),
    "find": (
        "mara",
        "/lists/{home}/?status=open&sort=due",
        "form.search",
        SPACE,
        "ul.todos > li:nth-child(3)",
    ),
    "order": ("mara", "/lists/{trip}/?sort=manual", "ul.todos", 0, "ul.todos"),
    "compare": ("mara", "/lists/{garden}/", "form.search", SPACE, "ul.todos"),
}

# Turns a PNG into a WebP in the browser, so no image package is needed.
TO_WEBP = """async ([data, quality]) => {
    const img = new Image();
    img.src = data;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.getContext("2d").drawImage(img, 0, 0);
    return canvas.toDataURL("image/webp", quality);
}"""


def free_port():
    """A port no other program uses right now (the system picks it)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(port, seconds=30):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    sys.exit(f"The server did not start on port {port}.")


def to_webp(converter, png):
    data = "data:image/png;base64," + base64.b64encode(png).decode()
    for quality in [0.86, 0.8, 0.7, 0.6]:
        webp = converter.evaluate(TO_WEBP, [data, quality])
        raw = base64.b64decode(webp.split(",", 1)[1])
        if len(raw) < MAX_BYTES:
            break
    return raw


def png_size(png):
    """The width and height of a PNG, from its header."""
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


# Where the page's column starts and how wide it is, without its padding.
COLUMN = """() => {
    const main = document.querySelector("main");
    const style = getComputedStyle(main);
    const box = main.getBoundingClientRect();
    const left = box.left + parseFloat(style.paddingLeft);
    return {left, width: box.right - parseFloat(style.paddingRight) - left};
}"""


def take_shots(base, seed):
    sizes = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        converter = browser.new_page()
        # Find the column once, then pick the scale that makes it 1088px wide.
        page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": 1400})
        page.context.add_cookies(
            [
                {
                    "name": seed["cookie_name"],
                    "value": seed["cookies"]["mara"],
                    "url": base,
                }
            ]
        )
        page.goto(base + "/lists/{home}/".format(**seed))
        column = page.evaluate(COLUMN)
        page.close()
        clip_x = column["left"] - SIDE
        clip_width = column["width"] + 2 * SIDE
        scale = IMAGE_WIDTH / clip_width
        for scheme in ["light", "dark"]:
            for name, (who, address, top, above, bottom) in SHOTS.items():
                context = browser.new_context(
                    viewport={"width": VIEWPORT_WIDTH, "height": 1400},
                    device_scale_factor=scale,
                    color_scheme=scheme,
                )
                context.add_cookies(
                    [
                        {
                            "name": seed["cookie_name"],
                            "value": seed["cookies"][who],
                            "url": base,
                        }
                    ]
                )
                page = context.new_page()
                page.goto(base + address.format(**seed))
                # No blinking cursor or focus ring in the picture.
                page.evaluate("document.activeElement && document.activeElement.blur()")
                top_box = page.locator(top.format(**seed)).first.bounding_box()
                bottom_box = page.locator(bottom.format(**seed)).first.bounding_box()
                # Rounded up: a box can start at 675.8px, and the 1px line just above
                # it would show at the top edge of the picture.
                y0 = max(math.ceil(top_box["y"] - above), 0)
                y1 = math.floor(bottom_box["y"] + bottom_box["height"] + BELOW)
                clip = {"x": clip_x, "y": y0, "width": clip_width, "height": y1 - y0}
                # full_page: the clip may be below the first screen.
                png = page.screenshot(clip=clip, full_page=True)
                raw = to_webp(converter, png)
                context.close()
                (OUT / f"{name}-{scheme}.webp").write_bytes(raw)
                width, height = png_size(png)
                sizes[f"{name}-{scheme}"] = {
                    "width": width,
                    "height": height,
                    "kB": round(len(raw) / 1000),
                }
        browser.close()
    return sizes


def main():
    folder = Path(tempfile.mkdtemp(prefix="landing-shots-"))
    port = free_port()
    server = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts/landing_seed.py"),
            str(folder / "shots.sqlite3"),
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # The server logs every request; not needed.
        text=True,
    )
    try:
        seed = json.loads(server.stdout.readline())
        wait_for(port)
        sizes = take_shots(f"http://127.0.0.1:{port}", seed)
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(folder, ignore_errors=True)
    for name, size in sizes.items():
        print(f"{name:20} {size['width']} x {size['height']}  {size['kB']} kB")


if __name__ == "__main__":
    main()
