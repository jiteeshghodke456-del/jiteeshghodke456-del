"""Codeforces submissions as an actual Game Boy playing Tetris.

The data mapping is unchanged and still literal: one column per problem, one block per
submission, stacked bottom-up in the order they were sent.  Green means the judge accepted
it, violet means it did not, and brightness picks the failure apart.

What changed is the selection and the costume.

**Selection.** A Game Boy playfield is ten columns wide, and the ten *most recent* problems
have one or two submissions each -- a board four rows deep in an eighteen-row well, which
looks like a spreadsheet with the lights off.  The ten problems that took the most attempts
give heights of 13, 10, 7, 7, 6, 6, 6, 6, 5 and 5: a real stack, and a more honest subject.
They are ordered by when each was first attempted, not by height, because a sorted staircase
reads as a bar chart and a jumbled one reads as Tetris.

**The costume.** Blocks are bevelled -- lit top-left, shadowed bottom-right -- which is how
every console Tetris drew them and the single cheapest thing that makes a flat grid look
like hardware.  The HUD is set in the bitmap font rather than the vector faces used
elsewhere on the page: a smooth outline face on a simulated LCD breaks the illusion, because
real hardware type sat exactly on the pixel grid.

The bottom row is always full -- ten columns, every problem attempted at least once -- so
the line clear in the idle loop is not staged.  It is the board telling the truth about
itself.
"""

from __future__ import annotations

import collections

from profilegen.svg import pixelfont as pf
from profilegen.svg.anim import AnimationSet, Keyframe, Timeline
from .. import svg, tokens
from ..typography import TypeSetter

COLS = 10
ROWS = 18
CELL = 15
BEVEL = 3
HUD_W = 150
SCREEN_PAD = 16
GAP = 18
FONT = 3                 # pixel-font scale; below 3 it dissolves at phone width

CYCLE = tokens.TETRIS_CYCLE      # 14s, shared with the rest of the page
LAND_ONE = 3.4
LAND_TWO = 6.6
FLASH_AT = 7.4
CLEAR_AT = 8.3
RESET_AT = 12.4

# Real tetrominoes, as (col, row) offsets with row 0 at the top of the piece.
PIECES = {
    "I": ((0, 0), (1, 0), (2, 0), (3, 0)),
    "O": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "T": ((0, 0), (1, 0), (2, 0), (1, 1)),
    "S": ((1, 0), (2, 0), (0, 1), (1, 1)),
    "Z": ((0, 0), (1, 0), (1, 1), (2, 1)),
    "J": ((0, 0), (0, 1), (1, 1), (2, 1)),
    "L": ((2, 0), (0, 1), (1, 1), (2, 1)),
}


def _verdict_key(verdict: str) -> str:
    return verdict if verdict in tokens.VERDICT_COLORS else "OTHER"


def columns_from(submissions: list[dict], limit: int) -> list[list[str]]:
    """The ``limit`` most-attempted problems, ordered by first attempt.

    Selecting by attempt count rather than recency is what fills the well; ordering by first
    attempt rather than by height is what stops it looking like a sorted bar chart.
    """
    buckets: dict[str, list[str]] = collections.defaultdict(list)
    first_seen: dict[str, int] = {}
    for submission in sorted(
        submissions, key=lambda row: row.get("creationTimeSeconds") or 0
    ):
        problem = submission.get("problem") or {}
        key = f"{problem.get('contestId')}{problem.get('index')}"
        buckets[key].append(_verdict_key(str(submission.get("verdict") or "OTHER")))
        first_seen.setdefault(key, submission.get("creationTimeSeconds") or 0)

    tallest = sorted(buckets, key=lambda key: (-len(buckets[key]), first_seen[key]))[:limit]
    return [buckets[key] for key in sorted(tallest, key=lambda key: first_seen[key])]


def first_try_accepts(columns: list[list[str]]) -> int:
    return sum(1 for column in columns if column and column[0] == "OK")


def _block(ident: str, color: str, cell: int = CELL) -> str:
    """A bevelled block: lit top-left, shadowed bottom-right, flat face between.

    This is the whole reason the board reads as hardware rather than as a chart.  The two
    edge colours are derived from the verdict colour, so adding a verdict never means
    hand-picking three hexes.
    """
    light, base, dark = tokens.bevel(color)
    c, b = cell, BEVEL
    return (
        f'<g id="{ident}">'
        f'<rect width="{c}" height="{c}" fill="{base}"/>'
        f'<path d="M0 0H{c}L{c - b} {b}H{b}V{c - b}L0 {c}Z" fill="{light}"/>'
        f'<path d="M{c} 0V{c}H0L{b} {c - b}H{c - b}V{b}Z" fill="{dark}"/>'
        "</g>"
    )


def _cross(cx: float, cy: float, arm: float, half: float) -> str:
    return (
        f'M{cx - half} {cy - arm}h{half * 2}v{arm - half}h{arm - half}'
        f'v{half * 2}h{-(arm - half)}v{arm - half}h{-half * 2}v{-(arm - half)}'
        f'h{-(arm - half)}v{-half * 2}h{arm - half}Z'
    )


def _dpad(cx: float, cy: float) -> str:
    """Recessed well, raised cross, lit top edge -- the same bevel logic as the blocks."""
    return (
        f'<path d="{_cross(cx, cy, 30, 11)}" fill="{tokens.VOID}" '
        f'stroke="{tokens.HAIRLINE}"/>'
        f'<path d="{_cross(cx, cy - 1, 26, 9)}" fill="{tokens.PANEL_HI}"/>'
        f'<path d="{_cross(cx, cy - 2, 24, 8)}" fill="{tokens.HAIRLINE}" opacity="0.8"/>'
        f'<circle cx="{cx}" cy="{cy - 1}" r="4" fill="{tokens.VOID}" opacity="0.55"/>'
    )


def _power_led(cx: float, cy: float) -> str:
    """The one thing on the shell that is always on."""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="9" fill="{tokens.VOID}" '
        f'stroke="{tokens.HAIRLINE}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="{tokens.ACID}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="8" fill="{tokens.ACID}" opacity="0.18"/>'
        + pf.render_path("POWER", cx + 16, cy - 5, scale=2, fill=tokens.DIM)
    )


def _button(cx: float, cy: float, label: str) -> str:
    """A face button: recessed well, raised cap, letter cut into the shell below."""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="23" fill="{tokens.VOID}" '
        f'stroke="{tokens.HAIRLINE}"/>'
        f'<circle cx="{cx}" cy="{cy - 1}" r="19" fill="{tokens.VIOLET_DEEP}"/>'
        f'<circle cx="{cx}" cy="{cy - 2}" r="16" fill="{tokens.VIOLET}" opacity="0.55"/>'
        + pf.render_path(
            label,
            cx - pf.measure(label, scale=2)[0] / 2,
            cy + 26,
            scale=2,
            fill=tokens.DIM,
        )
    )


def _pill(cx: float, cy: float, label: str, setter: TypeSetter) -> str:
    return (
        f'<rect x="{cx - 22}" y="{cy - 5}" width="44" height="10" rx="5" '
        f'fill="{tokens.PANEL_HI}" stroke="{tokens.HAIRLINE}" '
        f'transform="rotate(-18 {cx} {cy})"/>'
        + setter.text(
            cx, cy + 20, label, face=tokens.MONO, size=8,
            fill=tokens.DIM, anchor="middle",
        )
    )


def _landing_depth(shape: tuple[tuple[int, int], ...], col: int, heights: list[int]) -> int:
    """How far above the floor a piece comes to rest on the existing stack.

    A piece has to sit ON the contour, not hover over its deepest column.  Taking the
    maximum stack height under the piece leaves an L or a T floating over the notch it
    should be filling, which is the difference between a game and a sticker.

    For each column the piece occupies, the lowest cell in that column must clear the stack
    there; the binding constraint is whichever column gives the largest required depth.
    """
    bottom: dict[int, int] = {}
    for dx, dy in shape:
        bottom[dx] = max(bottom.get(dx, dy), dy)
    span = max(dy for _dx, dy in shape)
    required = []
    for dx, lowest in bottom.items():
        column = col + dx
        stacked = heights[column] if 0 <= column < len(heights) else 0
        required.append(stacked - (span - lowest))
    return max(0, max(required))


def _speaker(x: float, y: float) -> str:
    """Six raked slots, as every handheld of the era had."""
    slots = []
    for index in range(6):
        offset = x + index * 12
        slots.append(
            f'<rect x="{offset}" y="{y}" width="6" height="56" rx="3" '
            f'fill="{tokens.VOID}" stroke="{tokens.HAIRLINE}" stroke-width="1" '
            f'transform="rotate(-22 {offset} {y})"/>'
        )
    return "".join(slots)


def _hud(
    anim: AnimationSet, x: float, y: float, stats: dict, cleared_label: str
) -> str:
    """SCORE, LINES, LEVEL and a NEXT well, in the bitmap font.

    Set in bitmap rather than the page's vector faces on purpose: a smooth outline face on a
    simulated LCD is the one detail that breaks the illusion, because real hardware type sat
    exactly on the pixel grid.
    """
    total = int(stats.get("total", 0))
    accepted = int(stats.get("accepted", 0))
    parts: list[str] = []
    rows = (
        ("SCORE", f"{total:06d}"),
        ("LINES", f"{accepted:03d}"),
        ("LEVEL", f"{accepted // 10:03d}"),
    )
    cursor = y
    for label, value in rows:
        parts.append(pf.render_path(label, x, cursor, scale=2, fill=tokens.GB[2]))
        parts.append(
            pf.render_path(value, x, cursor + 16, scale=FONT, fill=tokens.GB[3])
        )
        cursor += 52

    # NEXT well, holding the piece that is currently falling.
    parts.append(pf.render_path("NEXT", x, cursor, scale=2, fill=tokens.GB[2]))
    box_y = cursor + 16
    parts.append(
        f'<rect x="{x}" y="{box_y}" width="{CELL * 4 + 8}" height="{CELL * 2 + 8}" '
        f'fill="none" stroke="{tokens.GB[1]}" stroke-width="1.5"/>'
    )
    for col, row in PIECES["T"]:
        parts.append(
            f'<use href="#bOK" x="{x + 4 + col * CELL}" y="{box_y + 4 + row * CELL}"/>'
        )
    parts.append(
        pf.render_path(cleared_label, x, box_y + CELL * 2 + 22, scale=2, fill=tokens.GB[2])
    )
    return "".join(parts)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD

    submissions = data.get("codeforces_submissions") or []
    stats = data.get("codeforces") or {}
    columns = columns_from(submissions, COLS)

    cell = 11 if narrow else CELL
    rows = 14 if narrow else ROWS
    well_w = COLS * cell
    well_h = rows * cell

    hud_w = 0 if narrow else HUD_W
    gap = 0 if narrow else GAP
    screen_w = well_w + gap + hud_w + SCREEN_PAD * 2
    screen_h = well_h + SCREEN_PAD * 2
    top = 62
    height = top + screen_h + 28 + (52 if not narrow else 26)

    setter = TypeSetter()
    anim = AnimationSet(Timeline(CYCLE), "t")
    body: list[str] = []
    defs: list[str] = []

    body.append(svg.card(0, 0, width, height))
    body.append(svg.eyebrow(setter, pad, 34, "Codeforces, but it is Tetris"))
    if not narrow:
        body.append(
            setter.text(
                width - pad, 34,
                f"{stats.get('solved', 0)} problems  {stats.get('total', 0)} submissions",
                face=tokens.MONO, size=10, fill=tokens.DIM, anchor="end",
            )
        )

    screen_x = (width - screen_w) / 2
    screen_y = top
    if not narrow:
        # The shell. Without it the d-pad and buttons float on the page and the whole thing
        # reads as a chart with decorations rather than as a device someone was holding.
        body.append(
            f'<rect x="{pad}" y="{top - 16}" width="{width - pad * 2}" '
            f'height="{height - top - 4}" rx="20" fill="{tokens.PANEL}" '
            f'stroke="{tokens.HAIRLINE}"/>'
        )
    body.append(
        f'<rect x="{screen_x - 14}" y="{screen_y - 14}" width="{screen_w + 28}" '
        f'height="{screen_h + 28}" rx="12" fill="{tokens.PANEL_HI}" '
        f'stroke="{tokens.HAIRLINE}"/>'
        f'<rect x="{screen_x}" y="{screen_y}" width="{screen_w}" height="{screen_h}" '
        f'rx="5" fill="{tokens.GB[0]}"/>'
    )

    well_x = screen_x + SCREEN_PAD
    well_y = screen_y + SCREEN_PAD

    defs.append(
        f'<clipPath id="gbwell"><rect x="{well_x}" y="{well_y}" width="{well_w}" '
        f'height="{well_h}"/></clipPath>'
    )

    grid = []
    for col in range(COLS):
        for row in range(rows):
            grid.append(
                f'<rect x="{well_x + col * cell}" y="{well_y + row * cell}" '
                f'width="{cell - 1}" height="{cell - 1}" fill="{tokens.GB[1]}" '
                f'opacity="0.22"/>'
            )
    body.append("".join(grid))

    used = {verdict for column in columns for verdict in column} | {"OK"}
    for verdict in sorted(used):
        defs.append(_block(f"b{verdict}", tokens.VERDICT_COLORS[verdict], cell))

    drop = anim.add(
        [
            Keyframe(0.0, {"transform": "translate(0px,0px)"}),
            Keyframe(CLEAR_AT, {"transform": "translate(0px,0px)"}),
            Keyframe(CLEAR_AT + 0.25, {"transform": f"translate(0px,{cell}px)"}),
            Keyframe(RESET_AT, {"transform": f"translate(0px,{cell}px)"}),
            Keyframe(RESET_AT + 0.4, {"transform": "translate(0px,0px)"}),
            Keyframe(CYCLE, {"transform": "translate(0px,0px)"}),
        ],
        easing="linear",
    )
    flash = anim.add(
        [
            Keyframe(0.0, {"opacity": "1"}),
            Keyframe(FLASH_AT, {"opacity": "1"}),
            Keyframe(FLASH_AT + 0.16, {"opacity": "0.2"}),
            Keyframe(FLASH_AT + 0.32, {"opacity": "1"}),
            Keyframe(FLASH_AT + 0.48, {"opacity": "0.2"}),
            Keyframe(CLEAR_AT, {"opacity": "1"}),
            Keyframe(CLEAR_AT + 0.22, {"opacity": "0"}),
            Keyframe(RESET_AT + 0.4, {"opacity": "0"}),
            Keyframe(RESET_AT + 0.7, {"opacity": "1"}),
            Keyframe(CYCLE, {"opacity": "1"}),
        ],
        easing="linear",
    )

    stack: list[str] = []
    for index, column in enumerate(columns[:COLS]):
        for depth, verdict in enumerate(column[:rows]):
            x = well_x + index * cell
            y = well_y + well_h - (depth + 1) * cell
            piece = f'<use href="#b{verdict}" x="{x}" y="{y}"/>'
            stack.append(f'<g class="{flash if depth == 0 else drop}">{piece}</g>')
    well_contents: list[str] = ["".join(stack)]

    # Two pieces fall in over the loop, land, and clear away at the reset.  They are the
    # only authored part of the board -- the stack underneath is entirely the real data.
    heights = [len(column) for column in columns[:COLS]]
    for shape, col, land_at in (("T", 3, LAND_ONE), ("L", 6, LAND_TWO)):
        cells = PIECES[shape]
        span = max(dy for _dx, dy in cells)
        depth = _landing_depth(cells, col, heights)
        # rest_y is the top row of the piece; its lowest cell lands at `depth` above the floor.
        rest_y = well_y + well_h - (depth + span + 1) * cell
        travel = anim.add(
            [
                Keyframe(0.0, {"transform": f"translate(0px,{-well_h}px)", "opacity": "0"}),
                Keyframe(max(0.0, land_at - 2.6), {"opacity": "1", "transform": f"translate(0px,{-well_h}px)"}),
                Keyframe(land_at, {"transform": "translate(0px,0px)", "opacity": "1"}),
                Keyframe(CLEAR_AT, {"transform": "translate(0px,0px)", "opacity": "1"}),
                Keyframe(CLEAR_AT + 0.25, {"transform": f"translate(0px,{cell}px)", "opacity": "1"}),
                Keyframe(RESET_AT, {"transform": f"translate(0px,{cell}px)", "opacity": "1"}),
                Keyframe(RESET_AT + 0.3, {"transform": f"translate(0px,{cell}px)", "opacity": "0"}),
                Keyframe(CYCLE, {"transform": f"translate(0px,{-well_h}px)", "opacity": "0"}),
            ],
            easing="linear",
        )
        blocks = "".join(
            f'<use href="#bOK" x="{well_x + (col + dx) * cell}" y="{rest_y + dy * cell}"/>'
            for dx, dy in cells
        )
        well_contents.append(f'<g class="{travel}">{blocks}</g>')

    # Everything inside the well is clipped to it, so a piece entering from above cannot
    # escape the screen and land on the page.
    body.append(f'<g clip-path="url(#gbwell)">{"".join(well_contents)}</g>')

    if not narrow:
        body.append(
            _hud(anim, well_x + well_w + gap, well_y + 4, stats, "CLEARED")
        )
        # Console furniture.  A board floating in space is a chart; a board inside a
        # handheld is a game someone was playing.
        body.append(_power_led(pad + 32, screen_y + 14))
        body.append(_dpad(pad + 96, screen_y + 116))
        body.append(_pill(pad + 66, screen_y + 216, "SELECT", setter))
        body.append(_pill(pad + 134, screen_y + 216, "START", setter))
        body.append(_button(width - 178, screen_y + 152, "B"))
        body.append(_button(width - 110, screen_y + 112, "A"))
        body.append(_speaker(width - 196, screen_y + 226))
        # The DMG said DOT MATRIX WITH STEREO SOUND. This one is being honest.
        body.append(
            pf.render_path(
                "DOT MATRIX WITH EMOTIONAL DAMAGE",
                (width - pf.measure("DOT MATRIX WITH EMOTIONAL DAMAGE", scale=2)[0]) / 2,
                screen_y + screen_h + 26,
                scale=2,
                fill=tokens.DIM,
            )
        )

    # LCD scanlines, one pattern rather than a rect per line.
    defs.append(
        '<pattern id="gbscan" width="3" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="3" height="1" fill="{tokens.VOID}" opacity="0.34"/></pattern>'
    )
    body.append(
        f'<rect x="{screen_x}" y="{screen_y}" width="{screen_w}" height="{screen_h}" '
        f'rx="5" fill="url(#gbscan)"/>'
    )

    style = f"<style>{anim.css()}</style>"
    return svg.document(
        width,
        int(height),
        style + "".join(body),
        defs=setter.defs() + "".join(defs),
        title="Codeforces submissions as a Game Boy Tetris board",
        description=(
            "The ten problems that took the most attempts, one column each, one block "
            "per submission, stacked in a Game Boy playfield."
        ),
    )
