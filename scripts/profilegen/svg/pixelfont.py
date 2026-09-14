"""A 5x7 bitmap font drawn as SVG rectangles, for the LCD panels.

Why a bitmap font
-----------------
Every asset here reaches the reader through ``<img>`` in the README, which runs the SVG in
the browser's *secure static mode*: no scripts and no external resources.  A web font is an
external resource, so **web fonts never load**.  The previous generator asked for
``font-family: 'Space Mono'`` and has been silently falling back to whatever monospace the
viewer's machine had -- the README has never rendered the way its author intended.

For the retro panels (the Game Boy Tetris HUD, the Nokia 3310 snake score) the answer is
not an embedded TTF either.  A smooth outline font on a simulated LCD breaks the illusion:
those panels are drawn on a pixel grid and their type has to sit on exactly that grid.  So
this module *is* the font.  Glyphs are 5x7 bitmaps and text is emitted as rectangles, which
land on the grid by construction.

Why unknown characters raise
----------------------------
The font this replaces, ``PARTICLE_GLYPHS`` in ``generate_profile_assets.py``, held exactly
eight letters (A G I J K Q S T) and ``particle_text_pattern()`` silently dropped every other
character.  Nobody noticed for nineteen commits, because every placeholder project in the
README had been *named to fit the font* -- Atelier, Stenokun, Tiffinology, Quippiq, Krushi.
A font that swallows what it cannot draw ends up shaping the content around itself.  So
``strict`` defaults to ``True`` on every function that takes text, and an unknown character
is a ``KeyError`` at generation time rather than a blank on the page.  ``strict=False``
substitutes a filled box and exists only for callers that genuinely prefer visible tofu to
a failed build.

Lowercase folds to uppercase on purpose, not by accident: a DMG-era Game Boy HUD and a Nokia
3310 HUD are both caps-only, and a mixed-case label would look wrong on either panel.

Element budget
--------------
The naive bitmap font is one ``<rect>`` per lit pixel, and the LCD panels carry enough text
for that to dominate file size.  ``decompose`` merges pixels into maximal blocks -- row runs
first, then vertical coalescing -- and across A-Z that is 3.1x fewer elements than
per-pixel (measured: 396 lit pixels become 128 blocks, 4.9 per letter).  ``render_path``
then folds every block of a label into a single ``<path>``, one element with one ``fill``
attribute, which for ``SCORE`` is 64% smaller than the same blocks as separate ``<rect>``
elements.  Static labels use it; only pixels that animate individually need
``render_rects``.

Scale
-----
``scale`` multiplies logical font pixels into user units.  **Callers must use ``scale >= 3``.**
GitHub forces ``max-width: 100%`` on README images, so a 920 px wide asset renders at
roughly 0.45x on a phone.  At ``scale=2`` a font pixel is then under one device pixel and
the pixel art turns to mush; at ``scale=3`` it is still 1.35 device pixels and survives.

Every coordinate goes through :func:`num.n`, the formatter the rest of the SVG code shares,
so output is byte-identical between runs and diffs of the generated assets stay reviewable.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from .doc import esc
from .num import n

GLYPH_W: int = 5
GLYPH_H: int = 7

# Each glyph is seven row masks, top row first, with bit 4 as the *leftmost* pixel.  Written
# as five-digit binary literals the source reads like the bitmap (``0b01110`` is a centred
# bar), and a whole string composes with shifts alone -- see ``bitrows``.  The shapes follow
# the classic 5x7 character-LCD forms (the HD44780 ROM font that every hobby LCD ships with)
# because that is the look readers already associate with a dot-matrix panel.  To eyeball a
# glyph while editing:  for m in GLYPHS["R"]: print(format(m, "05b").translate({48: ".", 49: "#"}))
GLYPHS: dict[str, tuple[int, ...]] = {
    # ---- letters
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11100, 0b10010, 0b10001, 0b10001, 0b10001, 0b10010, 0b11100),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b11111),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    # ---- digits.  Zero is slashed so a score never reads as the letter O.
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111),
    "3": (0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    # ---- space and punctuation
    " ": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b01100, 0b01100),
    ",": (0b00000, 0b00000, 0b00000, 0b00000, 0b01100, 0b00100, 0b01000),
    ":": (0b00000, 0b01100, 0b01100, 0b00000, 0b01100, 0b01100, 0b00000),
    ";": (0b00000, 0b01100, 0b01100, 0b00000, 0b01100, 0b00100, 0b01000),
    "!": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100),
    "?": (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b00000, 0b00100),
    "'": (0b01100, 0b00100, 0b01000, 0b00000, 0b00000, 0b00000, 0b00000),
    '"': (0b01010, 0b01010, 0b01010, 0b00000, 0b00000, 0b00000, 0b00000),
    "-": (0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000),
    "+": (0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000),
    "=": (0b00000, 0b00000, 0b11111, 0b00000, 0b11111, 0b00000, 0b00000),
    "/": (0b00000, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b00000),
    "\\": (0b00000, 0b10000, 0b01000, 0b00100, 0b00010, 0b00001, 0b00000),
    "|": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "(": (0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010),
    ")": (0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000),
    "[": (0b01110, 0b01000, 0b01000, 0b01000, 0b01000, 0b01000, 0b01110),
    "]": (0b01110, 0b00010, 0b00010, 0b00010, 0b00010, 0b00010, 0b01110),
    "<": (0b00010, 0b00100, 0b01000, 0b10000, 0b01000, 0b00100, 0b00010),
    ">": (0b01000, 0b00100, 0b00010, 0b00001, 0b00010, 0b00100, 0b01000),
    "*": (0b00000, 0b00100, 0b10101, 0b01110, 0b10101, 0b00100, 0b00000),
    "#": (0b01010, 0b01010, 0b11111, 0b01010, 0b11111, 0b01010, 0b01010),
    "%": (0b11000, 0b11001, 0b00010, 0b00100, 0b01000, 0b10011, 0b00011),
    "&": (0b01100, 0b10010, 0b10100, 0b01000, 0b10101, 0b10010, 0b01101),
    "_": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111),
    "@": (0b01110, 0b10001, 0b00001, 0b01101, 0b10101, 0b10101, 0b01110),
    "$": (0b00100, 0b01111, 0b10100, 0b01110, 0b00101, 0b11110, 0b00100),
    "^": (0b00100, 0b01010, 0b10001, 0b00000, 0b00000, 0b00000, 0b00000),
    "~": (0b00000, 0b00000, 0b01000, 0b10101, 0b00010, 0b00000, 0b00000),
}

# What ``strict=False`` draws for a character the font lacks: a solid cell.  A solid block is
# the one substitute that cannot be mistaken for a real glyph or for a space, which is the
# whole lesson of the eight-letter font -- if the fallback ever fires it has to be seen.
MISSING_GLYPH: tuple[int, ...] = (0b11111,) * GLYPH_H


@dataclass(frozen=True, slots=True)
class Rect:
    """One axis-aligned block of lit pixels, in logical (unscaled) cells of a text run."""

    col: int
    row: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return self.w * self.h


def _glyph(char: str, *, strict: bool) -> tuple[int, ...]:
    """Look up one character, folding case; ``KeyError`` or the box for unknown ones."""
    try:
        return GLYPHS[char.upper()]
    except KeyError:
        if strict:
            raise KeyError(
                f"no 5x7 glyph for {char!r} (U+{ord(char):04X}): add it to GLYPHS, or pass "
                "strict=False to draw a filled box in its place"
            ) from None
        return MISSING_GLYPH


def _check_scale(scale: int) -> None:
    # Zero or negative scale would silently emit zero-area or inverted rects, and n() would
    # format them without complaint -- an invisible label with no error is exactly the failure
    # mode this module exists to remove.
    if scale < 1:
        raise ValueError(f"scale must be a positive integer, got {scale!r}")


def _check_tracking(tracking: int) -> None:
    # Negative tracking would make glyphs overlap and the shift in bitrows corrupt the row.
    if tracking < 0:
        raise ValueError(f"tracking must be >= 0, got {tracking!r}")


def _advance(count: int, tracking: int) -> int:
    """Logical width of ``count`` glyphs: the cells plus a ``tracking`` gap between each pair."""
    _check_tracking(tracking)
    if count <= 0:
        return 0
    return count * GLYPH_W + (count - 1) * tracking


def measure(
    text: str, *, scale: int = 1, tracking: int = 1, strict: bool = True
) -> tuple[int, int]:
    """Return ``(width, height)`` in user units for ``text`` at ``scale``.

    The height is always ``GLYPH_H * scale``, even for an empty string, so layout code can
    stack lines without special-casing blanks.  The width is the *advance* -- the last cell
    counts in full even when its rightmost column is dark -- because labels are placed on a
    tile grid and the next thing along must not creep into the cell.

    Unknown characters raise here too, not only at render time: the failure should surface at
    the first call the layout makes, not after the panel has already been positioned around a
    width that can never be drawn.
    """
    _check_scale(scale)
    for char in text:
        _glyph(char, strict=strict)
    return _advance(len(text), tracking) * scale, GLYPH_H * scale


def bitrows(text: str, *, tracking: int = 1, strict: bool = True) -> list[int]:
    """Composite ``text`` into seven wide integers, one per pixel row.

    Column ``c`` (``0`` = leftmost) is bit ``width - 1 - c`` where ``width`` is the logical
    advance from :func:`measure`.  Each glyph is appended with a shift-and-or, so a whole label
    is seven ints however long it is -- Python ints are arbitrary precision -- and there is no
    grid of lists to index.  ``tracking`` blank columns sit between glyphs; the default of one
    reproduces the single-dot gap between characters on a real 5x7 character LCD.

    The first glyph needs no special case: shifting an all-zero accumulator is still zero, so
    it lands in the low bits and each later glyph pushes it left.
    """
    _check_tracking(tracking)
    rows = [0] * GLYPH_H
    step = GLYPH_W + tracking
    for char in text:
        glyph = _glyph(char, strict=strict)
        for index, mask in enumerate(glyph):
            rows[index] = (rows[index] << step) | mask
    return rows


def _runs(mask: int, width: int) -> list[tuple[int, int]]:
    """Maximal horizontal runs of set bits in one row, as ``(col, w)`` pairs, left to right."""
    if width <= 0:
        return []
    bits = format(mask, f"0{width}b")
    return [(match.start(), match.end() - match.start()) for match in re.finditer("1+", bits)]


def decompose(text: str, *, tracking: int = 1, strict: bool = True) -> list[Rect]:
    """Cover every lit pixel of ``text`` with non-overlapping rectangles, as few as practical.

    Two passes.  First, per row, each maximal horizontal run of set bits becomes one block.
    Second, working down the rows, a block still "open" from the row directly above is
    extended by one row whenever the current row has lit pixels across exactly its columns;
    the run it sits inside is split around it and the leftovers become new blocks.

    The split is the important part.  ``E`` is ``11111 / 10000 / 11110 / 10000 / 10000 /
    10000 / 11111``: 18 pixels, 7 row runs.  Merging only runs with an *identical* ``(col, w)``
    in adjacent rows would leave the stem broken in two by the middle bar and give 5 blocks.
    Letting the stem continue through the bar -- the bar shrinks to the 3 columns beside it --
    gives 4: the top bar, one 1x6 stem, the middle bar and the bottom bar.  Letterforms are
    stems and crossbars, so this is the case that matters.  Across A-Z the result is 128
    blocks for 396 lit pixels, 3.1x fewer elements than per-pixel and 2.2x fewer than the
    283 row runs alone.

    Blocks are returned in creation order (top row first, then left to right), which is
    deterministic and keeps the generated files diffable.
    """
    rows = bitrows(text, tracking=tracking, strict=strict)
    width = _advance(len(text), tracking)
    # Blocks are mutable [col, row, w, h] lists while they can still grow; frozen at the end.
    blocks: list[list[int]] = []
    open_blocks: list[list[int]] = []  # blocks whose bottom edge is the previous row, by col
    for row, mask in enumerate(rows):
        still_open: list[list[int]] = []
        for col, w in _runs(mask, width):
            end = col + w
            cursor = col
            for block in open_blocks:
                b_col, b_w = block[0], block[2]
                if b_col < cursor or b_col + b_w > end:
                    continue  # not wholly inside this run: it cannot stay rectangular
                if b_col > cursor:
                    piece = [cursor, row, b_col - cursor, 1]
                    blocks.append(piece)
                    still_open.append(piece)
                block[3] += 1
                still_open.append(block)
                cursor = b_col + b_w
            if cursor < end:
                piece = [cursor, row, end - cursor, 1]
                blocks.append(piece)
                still_open.append(piece)
        open_blocks = still_open
    return [Rect(*block) for block in blocks]


def _path_data(rects: list[Rect], x: float, y: float, scale: int) -> str:
    # One absolute move per block, then relative edges: "M x y h w v h h -w z".  Relative edges
    # are shorter than four absolute corners and the closing "z" draws the fourth side.
    return "".join(
        f"M{n(x + rect.col * scale)} {n(y + rect.row * scale)}"
        f"h{n(rect.w * scale)}v{n(rect.h * scale)}h{n(-rect.w * scale)}z"
        for rect in rects
    )


def render_path(
    text: str,
    x: float,
    y: float,
    *,
    scale: int = 1,
    fill: str = "currentColor",
    cls: str | None = None,
    tracking: int = 1,
    strict: bool = True,
) -> str:
    """Render ``text`` as ONE ``<path>`` with every block as a subpath.

    This is the default for every static label.  One element and one ``fill`` attribute
    instead of one of each per block: for ``SCORE`` the path is 64% smaller than the same
    blocks emitted through :func:`render_rects`.  Anchoring on the top-left of the first cell
    at ``(x, y)`` keeps the maths trivial for callers that lay panels out on a tile grid.

    ``fill`` is always written, never left to inherit, because :class:`doc.SvgDoc` sets
    ``fill="none"`` on the root -- a path that relied on inheritance would be invisible.
    Returns an empty string when nothing would be drawn (empty text, or only spaces), so
    callers can concatenate without checking.
    """
    _check_scale(scale)
    rects = decompose(text, tracking=tracking, strict=strict)
    if not rects:
        return ""
    class_attr = f' class="{esc(cls)}"' if cls else ""
    return f'<path{class_attr} fill="{esc(fill)}" d="{_path_data(rects, x, y, scale)}"/>'


def render_rects(
    text: str,
    x: float,
    y: float,
    *,
    scale: int = 1,
    fill: str = "currentColor",
    cls_for: Callable[[int, Rect], str | None] | None = None,
    tracking: int = 1,
    strict: bool = True,
) -> str:
    """Render ``text`` as individual ``<rect>`` elements inside one ``<g fill=...>``.

    Only for text whose pixels animate *individually* -- a cursor that blinks, a letter that
    flickers in -- where each block needs its own CSS class.  ``cls_for(index, rect)`` names
    the class per block (``None`` for no class).  Everything else should use
    :func:`render_path`, which is a fraction of the size.

    The blocks are the same ones :func:`decompose` returns, in the same order, so ``index``
    is stable across runs.  ``fill`` goes on the wrapping group once rather than on each rect;
    the root of every document is ``fill="none"`` so something has to set it, and a CSS rule
    on a per-rect class still wins over the inherited value when an animation needs its own
    colour.  Returns an empty string when nothing would be drawn.
    """
    _check_scale(scale)
    rects = decompose(text, tracking=tracking, strict=strict)
    if not rects:
        return ""
    parts = [f'<g fill="{esc(fill)}">']
    for index, rect in enumerate(rects):
        cls = cls_for(index, rect) if cls_for is not None else None
        class_attr = f' class="{esc(cls)}"' if cls else ""
        parts.append(
            f'<rect{class_attr} x="{n(x + rect.col * scale)}" y="{n(y + rect.row * scale)}" '
            f'width="{n(rect.w * scale)}" height="{n(rect.h * scale)}"/>'
        )
    parts.append("</g>")
    return "".join(parts)


def digit_slot(
    x: float,
    y: float,
    *,
    scale: int = 1,
    fill: str = "currentColor",
    cls_for: Callable[[int], str | None] | None = None,
) -> str:
    """Render all ten digits ``0``-``9`` on top of each other at ``(x, y)``, in one ``<g>``.

    This is how a SCORE counter counts up inside a README image.  The SVG is served through
    GitHub's Camo proxy and displayed via ``<img>``, so there is no JavaScript and no way to
    change text after load; what *can* change is CSS ``opacity``.  Each digit is its own
    ``<path>`` carrying the class ``cls_for(digit)`` returns, and the caller's ``@keyframes``
    show exactly one of the ten at any moment -- ten paths per digit position is the entire
    cost of a counter that appears to tick.

    Without classes all ten overlap into a solid blob, so a caller that passes no ``cls_for``
    must target the paths some other way (``:nth-child`` on the group, for instance).
    """
    _check_scale(scale)
    parts = [f'<g fill="{esc(fill)}">']
    for digit in range(10):
        cls = cls_for(digit) if cls_for is not None else None
        class_attr = f' class="{esc(cls)}"' if cls else ""
        data = _path_data(decompose(str(digit)), x, y, scale)
        parts.append(f'<path{class_attr} d="{data}"/>')
    parts.append("</g>")
    return "".join(parts)
