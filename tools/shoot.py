#!/usr/bin/env python3
"""Screenshot generated SVGs the way GitHub actually serves them, so they can be judged.

Run locally, never in CI.  This is the "open the browser" half of the build loop: the unit
tests prove the geometry is self-consistent, and this proves it *looks* right.

Why it bothers with an HTTP server and an `<img>` tag instead of just opening the .svg:
GitHub embeds these through `<img src=...>`, which puts the SVG in the browser's secure
static mode.  Rendering the file as a top-level document instead would run it in a more
permissive mode and could make something work here that is dead on the real page.  Serving
over HTTP rather than file:// matters for the same reason -- file:// has its own quirks that
GitHub readers will never encounter.

Two views are captured per asset:

* native width at several times, to check motion, timing and loop seams;
* phone width, because GitHub forces `max-width: 100%` on README images.  A 920px asset
  renders at roughly 0.45x on a phone, and that is where font sizes and tight layouts fail.

Needs Playwright, which is deliberately kept out of the CI dependency set.  Run it with the
dedicated interpreter:

    /home/agent/.venvs/shoot/bin/python tools/shoot.py dist/tetris.svg
"""

from __future__ import annotations

import argparse
import http.server
import pathlib
import re
import socketserver
import threading

PHONE_WIDTH = 414
DEFAULT_TIMES = (0.0, 2.0, 4.0, 8.0)

PAGE = """<!doctype html><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:{bg};}}
  img{{display:block;width:{width}px;height:auto;}}
</style>
<img src="{name}" alt="">
"""


def serve(directory: pathlib.Path) -> tuple[str, socketserver.TCPServer]:
    """Serve ``directory`` on a free localhost port, quietly."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, *args, **kwargs) -> None:
            # SimpleHTTPRequestHandler logs every request to stderr; the only output a run
            # should produce is the list of screenshots it wrote.
            pass

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}", server


def svg_size(path: pathlib.Path) -> tuple[int, int]:
    head = path.read_text(encoding="utf-8")[:600]
    width = re.search(r'width="(\d+)"', head)
    height = re.search(r'height="(\d+)"', head)
    if not width or not height:
        raise SystemExit(f"{path.name}: no width/height on the root <svg>")
    return int(width.group(1)), int(height.group(1))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svgs", nargs="+", type=pathlib.Path)
    parser.add_argument("--out", default=pathlib.Path("/tmp/shots"), type=pathlib.Path)
    parser.add_argument(
        "--times",
        default=",".join(str(t) for t in DEFAULT_TIMES),
        help="comma-separated seconds at which to capture the native-width view",
    )
    parser.add_argument("--bg", default="#0d1117", help="page background behind the asset")
    parser.add_argument(
        "--phone-only", action="store_true", help="capture only the downscaled view"
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        raise SystemExit(
            "playwright is not installed for this interpreter.  This tool is local-only "
            "and intentionally absent from CI deps; run it with:\n"
            "  /home/agent/.venvs/shoot/bin/python tools/shoot.py <svg>..."
        ) from None

    times = [float(t) for t in args.times.split(",") if t.strip()]
    args.out.mkdir(parents=True, exist_ok=True)
    written: list[pathlib.Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for svg in args.svgs:
            svg = svg.resolve()
            if not svg.exists():
                raise SystemExit(f"missing: {svg}")
            base, server = serve(svg.parent)
            try:
                width, height = svg_size(svg)
                stem = svg.stem

                views: list[tuple[str, int, list[float]]] = []
                if not args.phone_only:
                    views.append(("native", width, times))
                views.append(("phone", PHONE_WIDTH, [times[0] if times else 0.0]))

                for label, render_width, view_times in views:
                    holder = svg.parent / f".shoot-{label}-{stem}.html"
                    holder.write_text(
                        PAGE.format(bg=args.bg, width=render_width, name=svg.name),
                        encoding="utf-8",
                    )
                    page = browser.new_page(
                        viewport={
                            "width": render_width,
                            "height": max(
                                80, round(height * render_width / width) + 2
                            ),
                        },
                        device_scale_factor=2 if label == "phone" else 1,
                    )
                    # The page must be SERVED, not injected: a relative <img src> cannot
                    # resolve on about:blank, which is where set_content leaves you.
                    page.goto(f"{base}/{holder.name}", wait_until="load")
                    page.wait_for_timeout(150)

                    previous = 0.0
                    for t in view_times:
                        wait_ms = max(0.0, (t - previous)) * 1000
                        if wait_ms:
                            page.wait_for_timeout(wait_ms)
                        previous = t
                        shot = args.out / f"{stem}.{label}.t{t:g}s.png"
                        page.locator("img").screenshot(path=str(shot))
                        written.append(shot)
                    page.close()
                    holder.unlink(missing_ok=True)
            finally:
                server.shutdown()
                server.server_close()
        browser.close()

    for shot in written:
        print(f"{shot}  ({shot.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
