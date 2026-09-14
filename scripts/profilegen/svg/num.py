"""One place that turns floats into SVG attribute text.

Coordinate precision is a real size lever -- about 12% of the bytes in these files -- so it
is centralised rather than left to per-call f-strings.  It also keeps output byte-identical
between runs, which is what makes day-over-day git diffs of the generated assets reviewable.
"""

from __future__ import annotations


def n(value: float, places: int = 1) -> str:
    """Format a coordinate: fixed precision, trailing zeros and '.0' stripped."""
    text = f"{value:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def o(value: float) -> str:
    """Format an opacity or scale factor, which need more precision than coordinates."""
    return n(value, 3)


def pct(value: float) -> str:
    """Format a keyframe percentage."""
    return n(value, 2)
