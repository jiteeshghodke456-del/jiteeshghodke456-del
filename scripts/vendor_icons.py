#!/usr/bin/env python3
"""Fetch Simple Icons glyphs into a stdlib-readable table.

Run this by hand when the toolkit list changes::

    python3 scripts/vendor_icons.py

Simple Icons ships under CC0-1.0, so the path data can live in this repo.
Every icon is a single path on a 24x24 grid, which is why the renderer can
scale and recolour them without touching the source SVG.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icons"
SOURCE = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{slug}.svg"

# Slug -> label shown under the icon. Ordered as the toolkit row renders.
ICONS = {
    "typescript": "TypeScript",
    "python": "Python",
    "react": "React",
    "javascript": "JavaScript",
    "html5": "HTML",
    "css": "CSS",
    "postgresql": "Postgres",
    "supabase": "Supabase",
    "electron": "Electron",
    "nodedotjs": "Node",
    "rust": "Rust",
    "cplusplus": "C++",
    "git": "Git",
    "github": "GitHub",
    "linux": "Linux",
    "codeforces": "Codeforces",
    "x": "X",
}

# Simple Icons dropped LinkedIn over trademark policy, so the contact row sets
# that one as type instead of an icon. Do not re-add the slug; it 404s.

PATH_RE = re.compile(r'<path\b[^>]*\bd="([^"]+)"')
TITLE_RE = re.compile(r"<title>([^<]+)</title>")


def fetch(slug: str) -> dict | None:
    url = SOURCE.format(slug=slug)
    request = urllib.request.Request(url, headers={"User-Agent": "profile-icon-vendor"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  ! {slug}: {exc}", file=sys.stderr)
        return None

    paths = PATH_RE.findall(body)
    if not paths:
        print(f"  ! {slug}: no path found", file=sys.stderr)
        return None
    title = TITLE_RE.search(body)
    return {
        "d": paths[0],
        "title": title.group(1) if title else slug,
        "viewbox": 24,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ICON_DIR / "simple-icons.json"))
    args = parser.parse_args()

    table: dict[str, dict] = {}
    for slug, label in ICONS.items():
        icon = fetch(slug)
        if icon is None:
            continue
        icon["label"] = label
        table[slug] = icon
        print(f"  {slug:<12} {len(icon['d']):>5} bytes  {icon['title']}")

    missing = [slug for slug in ICONS if slug not in table]
    if missing:
        print(f"  ! missing: {', '.join(missing)}", file=sys.stderr)
        return 1

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "source": "https://github.com/simple-icons/simple-icons",
                "license": "CC0-1.0",
                "icons": table,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"  {out.relative_to(ROOT)}  {len(table)} icons  {out.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
