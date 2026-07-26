"""Inline Simple Icons glyphs, recoloured to the card palette.

The icons ship as CC0 path data on a 24-unit grid (see ``vendor_icons.py``),
so they scale and recolour like any other vector in the system instead of
arriving as a foreign PNG with its own idea of stroke weight.
"""

from __future__ import annotations

import functools
import json
import pathlib

from .typography import fmt

ICON_FILE = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "assets"
    / "icons"
    / "simple-icons.json"
)


@functools.lru_cache(maxsize=1)
def _table() -> dict:
    if not ICON_FILE.exists():
        raise FileNotFoundError(
            f"missing {ICON_FILE}. Run: python3 scripts/vendor_icons.py"
        )
    return json.loads(ICON_FILE.read_text(encoding="utf-8"))["icons"]


def label(slug: str) -> str:
    return _table()[slug]["label"]


def has(slug: str) -> bool:
    return slug in _table()


def icon(
    slug: str,
    x: float,
    y: float,
    size: float,
    *,
    fill: str,
    opacity: float | None = None,
) -> str:
    """Draw ``slug`` with its top-left corner at ``x, y``."""
    entry = _table()[slug]
    scale = size / entry["viewbox"]
    attrs = [
        f'transform="translate({fmt(x)} {fmt(y)}) scale({fmt(scale)})"',
        f'fill="{fill}"',
    ]
    if opacity is not None:
        attrs.append(f'opacity="{fmt(opacity)}"')
    return f'<g {" ".join(attrs)}><path d="{entry["d"]}"/></g>'
