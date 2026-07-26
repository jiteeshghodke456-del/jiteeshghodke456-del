"""Set type as vector paths, using glyph tables built by ``vendor_glyphs.py``.

GitHub renders these SVGs inside an ``<img>``, which blocks external font
loading and makes ``font-family`` a guess about the reader's machine. Drawing
the outlines removes the guess: the nameplate looks the same everywhere, and
the standard library is enough to render it.

Each distinct glyph is emitted once into ``<defs>`` and referenced with
``<use>``, so a card that repeats "BAY" four times pays for those outlines
once.
"""

from __future__ import annotations

import functools
import json
import pathlib

GLYPH_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "assets" / "glyphs"

# Substituted for anything outside the vendored character set, so a stray
# character degrades to a visible marker instead of a silent gap.
FALLBACK = "?"


@functools.lru_cache(maxsize=None)
def load_face(key: str) -> dict:
    path = GLYPH_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"missing glyph table {path}. Run: python3 scripts/vendor_glyphs.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


class TypeSetter:
    """Collects glyph outlines while cards render, then emits them as defs.

    Build the card body first, then call :meth:`defs` and drop the result into
    the document head. The setter is per-document; two documents must not share
    one, or the second inherits the first's glyph ids.
    """

    def __init__(self) -> None:
        self._used: dict[tuple[str, str], str] = {}

    # -- measuring ---------------------------------------------------------

    def advance_units(self, text: str, face: str, tracking: int = 0) -> int:
        """Width of ``text`` in font units, before scaling."""
        table = load_face(face)["glyphs"]
        total = 0
        for char in text:
            glyph = table.get(char) or table.get(FALLBACK)
            if glyph is None:
                continue
            total += glyph["aw"] + tracking
        if text:
            total -= tracking  # no trailing gap after the final glyph
        return total

    def width(self, text: str, face: str, size: float, tracking: int = 0) -> float:
        """Rendered width in user units at ``size``."""
        upem = load_face(face)["upem"]
        return self.advance_units(text, face, tracking) * size / upem

    def wrap(
        self,
        text: str,
        face: str,
        size: float,
        max_width: float,
        tracking: int = 0,
    ) -> list[str]:
        """Greedy word wrap measured in real glyph advances.

        The cards have no layout engine, so any copy that is not wrapped here
        simply runs off the edge of the canvas - which is exactly what the
        narrow variants did before this existed.
        """
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if self.width(candidate, face, size, tracking) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def cap_height(self, face: str, size: float) -> float:
        table = load_face(face)
        return table["cap_height"] * size / table["upem"]

    # -- rendering ---------------------------------------------------------

    def _glyph_id(self, face: str, char: str) -> str | None:
        table = load_face(face)["glyphs"]
        glyph = table.get(char)
        if glyph is None:
            glyph = table.get(FALLBACK)
            char = FALLBACK
            if glyph is None:
                return None
        if "d" not in glyph:  # whitespace carries an advance but no outline
            return None
        key = (face, char)
        if key not in self._used:
            self._used[key] = f"t{len(self._used):x}"
        return self._used[key]

    def text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        face: str,
        size: float,
        fill: str,
        tracking: int = 0,
        anchor: str = "start",
        opacity: float | None = None,
        extra: str = "",
    ) -> str:
        """Return one ``<g>`` holding the run. ``y`` is the baseline."""
        if not text:
            return ""

        face_table = load_face(face)
        upem = face_table["upem"]
        glyphs = face_table["glyphs"]
        scale = size / upem

        run_units = self.advance_units(text, face, tracking)
        if anchor == "middle":
            x -= run_units * scale / 2
        elif anchor == "end":
            x -= run_units * scale

        parts: list[str] = []
        pen = 0
        for char in text:
            glyph = glyphs.get(char) or glyphs.get(FALLBACK)
            if glyph is None:
                continue
            glyph_id = self._glyph_id(face, char)
            if glyph_id is not None:
                parts.append(f'<use href="#{glyph_id}" x="{pen}"/>')
            pen += glyph["aw"] + tracking

        if not parts:
            return ""

        attrs = [
            f'transform="translate({fmt(x)} {fmt(y)}) scale({fmt(scale)} {fmt(-scale)})"',
            f'fill="{fill}"',
        ]
        if opacity is not None:
            attrs.append(f'opacity="{fmt(opacity)}"')
        if extra:
            attrs.append(extra)
        return f'<g {" ".join(attrs)}>{"".join(parts)}</g>'

    def defs(self) -> str:
        """Outline definitions for every glyph used so far."""
        if not self._used:
            return ""
        parts = []
        for (face, char), glyph_id in self._used.items():
            outline = load_face(face)["glyphs"][char]["d"]
            parts.append(f'<path id="{glyph_id}" d="{outline}"/>')
        return "".join(parts)


def fmt(value: float) -> str:
    """Trim float noise out of the emitted SVG without losing scale precision.

    Coordinates are happy at two decimals, but glyph scale factors live around
    0.07 - rounding those to two decimals stretched the nameplate 5% past the
    canvas. Values below 1 keep significant digits instead of decimal places.
    """
    if isinstance(value, int):
        return str(value)
    number = float(value)
    if number == int(number):
        return str(int(number))
    if abs(number) >= 1:
        rounded = round(number, 2)
        return str(int(rounded)) if rounded == int(rounded) else f"{rounded:g}"
    return f"{number:.5g}"
