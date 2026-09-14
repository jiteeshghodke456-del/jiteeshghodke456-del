"""Render a planned run as a Nokia 3310 playing Snake II.

The screen is *backlit*: dark ground, bright pixels.  A real 3310 was the other way round --
dark pixels on pale green -- but a backlit 3310 in a dark room looks exactly like this, so
the neon reading is period-accurate rather than a liberty taken for the palette.

How the motion is encoded, because it is the whole size argument.  Every segment follows the
identical path, so one @keyframes block holds the head's track and all N segments point at
it with different delays:

    segment i at step s occupies track[start_offset + s - i]

which falls out of `animation-delay = (i - start_offset) * step_dt`.  Position and visibility
are split across two nested groups: the inner group carries the shared, delayed path, and the
outer one carries a per-segment opacity track in wall-clock time.  They cannot share an
element because they need different delays, and a segment that has not been eaten into
existence yet must be hidden while its path animation is already running.
"""

from __future__ import annotations

from ..svg import pixelfont as pf
from ..svg.anim import AnimationSet, Keyframe, Timeline
from ..svg.doc import SvgDoc, anim_group, use
from ..svg.num import n, o
from cockpit import tokens
from cockpit.tokens import lerp
from .recorder import SnakeRecord

CELL = 13
GAP = 2
PITCH = CELL + GAP
LCD_PAD = 14
HUD_H = 34
SHELL_X = 26
SHELL_TOP = 48
SHELL_BOTTOM = 34
FADE = 1.1          # seconds for the tail-first fade during the reset window
FONT = 3            # pixel-font scale; below 3 the art dissolves at phone width
BODY_SHADES = 8     # head-to-tail brightness steps


HOLD = 0.01         # a hold frame sits this far before a transition


def _hold(frames: list[Keyframe], duration: float) -> list[Keyframe]:
    """Repeat the final state at ``duration`` so the track actually holds it.

    A @keyframes block with no 100% stop does NOT freeze on its last value.  CSS synthesises
    the missing stop from the element's base computed style and interpolates toward it, so a
    pulse that ends at opacity 0 quietly ramps back to the default 1 over the remainder of
    the timeline -- which is how fourteen spent eat-pulses ended up glowing at once, and how
    the score was about to dissolve two seconds before the loop ended.
    """
    if frames and frames[-1].t < duration:
        frames = [*frames, Keyframe(duration, dict(frames[-1].props))]
    return frames


def _appear(at: float, *, until: float, fade_out: float) -> list[Keyframe]:
    """Opacity frames for something that snaps on at ``at`` and fades out at ``until``.

    The hold frame before ``at`` is not optional.  With linear easing, two frames at 0 and
    ``at`` interpolate across the whole interval between them, so a segment meant to pop into
    existence when it is eaten instead ghosts in gradually from t=0 -- and thirty eat-pulses
    meant to last 0.42s each end up all faintly visible at once.  Holding the start value
    right up to the transition is what makes the change read as an event.
    """
    frames = [Keyframe(0.0, {"opacity": "0"})]
    if at > HOLD:
        frames.append(Keyframe(at - HOLD, {"opacity": "0"}))
    frames.append(Keyframe(at, {"opacity": "1"}))
    frames.append(Keyframe(until, {"opacity": "1"}))
    frames.append(Keyframe(until + fade_out, {"opacity": "0"}))
    return frames


def _cell_xy(col: int, row: int) -> tuple[float, float]:
    return col * PITCH, row * PITCH


def render(record: SnakeRecord, field, path) -> str:
    """Write the snake asset and return the markup."""
    grid_w = record.cols * PITCH - GAP
    grid_h = record.rows * PITCH - GAP
    lcd_w = grid_w + 2 * LCD_PAD
    lcd_h = HUD_H + grid_h + 2 * LCD_PAD
    width = lcd_w + 2 * SHELL_X
    height = lcd_h + SHELL_TOP + SHELL_BOTTOM

    doc = SvgDoc(width, height, "Nokia Snake eating a year of GitHub contributions", defs_prefix="s")
    timeline = Timeline(record.duration)
    anim = AnimationSet(timeline, "k")

    grid_x = SHELL_X + LCD_PAD
    grid_y = SHELL_TOP + LCD_PAD + HUD_H

    # ---- shell and screen -------------------------------------------------
    doc.add(
        f'<rect width="{width}" height="{height}" rx="26" fill="{tokens.NOKIA["shell"]}"/>'
        f'<rect x="3" y="3" width="{width - 6}" height="{height - 6}" rx="23" '
        f'fill="none" stroke="{tokens.HAIRLINE}" stroke-width="1.5"/>'
        f'<rect x="{SHELL_X - 8}" y="{SHELL_TOP - 10}" width="{lcd_w + 16}" '
        f'height="{lcd_h + 20}" rx="10" fill="{tokens.NOKIA["bezel"]}"/>'
        f'<rect x="{SHELL_X}" y="{SHELL_TOP}" width="{lcd_w}" height="{lcd_h}" rx="4" '
        f'fill="{tokens.NOKIA["screen"]}"/>'
    )

    # Brand strip, drawn in the bitmap font so it sits on the same pixel grid as the HUD.
    doc.add(
        pf.render_path("NOKIA", SHELL_X + 2, 16, scale=2, fill=tokens.DIM)
        + pf.render_path(
            "SNAKE II", width - SHELL_X - pf.measure("SNAKE II", scale=2)[0] - 2, 16,
            scale=2, fill=tokens.MUTED,
        )
    )

    # ---- HUD --------------------------------------------------------------
    hud_y = SHELL_TOP + LCD_PAD
    doc.add(pf.render_path("EATEN", grid_x, hud_y, scale=FONT, fill=tokens.NOKIA["l2"]))

    total = len(record.meals)
    counter_x = grid_x + pf.measure("EATEN ", scale=FONT)[0]
    for place, divisor in ((0, 10), (1, 1)):
        digit_x = counter_x + place * (pf.GLYPH_W + 1) * FONT
        slots = []
        for digit in range(10):
            frames = []
            for index, meal in enumerate([None, *record.meals]):
                value = (index // divisor) % 10
                at = 0.0 if meal is None else meal.step * record.step_dt
                frames.append(Keyframe(at, {"opacity": "1" if value == digit else "0"}))

            shown = {frame.props["opacity"] for frame in frames}
            if shown == {"0"}:
                continue                      # this digit never comes up; emit nothing
            glyph = pf.render_path(
                str(digit), digit_x, hud_y, scale=FONT, fill=tokens.NOKIA["l4"]
            )
            if shown == {"1"}:
                # A digit that is always on -- the tens place of a small score, say -- is
                # static markup.  Animating it would be a track that animates nothing, which
                # the emitter rightly refuses as dead bytes.
                slots.append(glyph)
                continue
            # step-end keeps the numerals crisp; a linear counter would dissolve one digit
            # into the next instead of ticking over.
            cls = anim.add(_hold(frames, record.duration), base={"opacity": "0"})
            slots.append(f'<g class="{cls}">{glyph}</g>')
        doc.add("".join(slots))

    label = f"{total} DAYS"
    doc.add(
        pf.render_path(
            label,
            grid_x + grid_w - pf.measure(label, scale=FONT)[0],
            hud_y,
            scale=FONT,
            fill=tokens.NOKIA["l2"],
        )
    )

    # ---- static grid ------------------------------------------------------
    # One symbol per contribution level, instanced 364 times.  A <use> is roughly half the
    # bytes of a full <rect>, and this is the largest single block in the file.
    symbols = {
        level: doc.defs.add(
            f"cell{level}",
            f'<rect id="{{id}}" width="{CELL}" height="{CELL}" rx="1" '
            f'fill="{tokens.NOKIA[f"l{level}"]}"/>',
        )
        for level in range(5)
    }

    eaten_at = {(m.col, m.row): m.step * record.step_dt for m in record.meals}
    cells: list[str] = []
    for col in range(record.cols):
        for row in range(record.rows):
            level = field.level_at(col, row)
            x, y = _cell_xy(col, row)
            when = eaten_at.get((col, row))
            if when is None:
                cells.append(use(symbols[level], grid_x + x, grid_y + y))
            else:
                # An eaten cell drops to the empty shade the moment the head arrives, and
                # comes back during the reset so the loop starts from a full board.
                cls = anim.add(
                    [
                        Keyframe(0.0, {"opacity": "1"}),
                        Keyframe(max(0.0, when - HOLD), {"opacity": "1"}),
                        Keyframe(when, {"opacity": "0.16"}),
                        Keyframe(record.reset_at + FADE, {"opacity": "0.16"}),
                        Keyframe(record.reset_at + FADE + 0.3, {"opacity": "1"}),
                        Keyframe(record.duration, {"opacity": "1"}),
                    ],
                    easing="linear",
                    base={"opacity": "1"},
                )
                cells.append(
                    f'<g class="{cls}">{use(symbols[level], grid_x + x, grid_y + y)}</g>'
                )
    doc.add("".join(cells))

    # ---- eat pulses -------------------------------------------------------
    # Centred on its own origin on purpose.  The ring scales via CSS, and a CSS transform
    # REPLACES the transform attribute rather than composing with it -- so a companion
    # translate on the same element would be silently discarded the moment it animated.
    ring = (CELL + 8) / 2
    pulse_ref = doc.defs.add(
        "pulse",
        f'<rect id="{{id}}" x="{-ring}" y="{-ring}" width="{ring * 2}" height="{ring * 2}" '
        f'rx="3" fill="none" stroke="{tokens.NOKIA["snake"]}" stroke-width="2"/>',
    )
    pulses: list[str] = []
    for meal in record.meals:
        when = meal.step * record.step_dt
        cls = anim.add(
            _hold(
                [
                    Keyframe(0.0, {"opacity": "0", "transform": "scale(0.6)"}),
                    Keyframe(max(0.0, when - HOLD), {"opacity": "0", "transform": "scale(0.6)"}),
                    Keyframe(when, {"opacity": "0.9", "transform": "scale(0.6)"}),
                    Keyframe(when + 0.42, {"opacity": "0", "transform": "scale(1.9)"}),
                    Keyframe(when + 0.43, {"opacity": "0", "transform": "scale(0.6)"}),
                ],
                record.duration,
            ),
            easing="linear",
            base={"opacity": "0"},
        )
        x, y = _cell_xy(meal.col, meal.row)
        pulses.append(
            f'<g transform="translate({n(grid_x + x + CELL / 2)} {n(grid_y + y + CELL / 2)})">'
            f'<g class="{cls}">{use(pulse_ref)}</g></g>'
        )
    doc.add("".join(pulses))

    # ---- the snake --------------------------------------------------------
    # A 7-row playfield means a long snake folds back on itself every seven cells, so a
    # 25-segment body packs adjacent columns solid.  Two things keep it readable: the cells
    # stay a gap apart so the dark screen shows between them, and brightness ramps from head
    # to tail.  Even coiled into a block the direction of travel stays obvious, which is
    # exactly how a 3310 looked when the snake got long.
    shades = [
        lerp(tokens.NOKIA["snake"], tokens.NOKIA["l2"], (index / (BODY_SHADES - 1)) ** 0.72)
        for index in range(BODY_SHADES)
    ]
    body_refs = [
        doc.defs.add(
            f"seg{index}",
            f'<rect id="{{id}}" width="{CELL}" height="{CELL}" rx="1.5" fill="{shade}"/>',
        )
        for index, shade in enumerate(shades)
    ]
    head_ref = doc.defs.add(
        "head",
        f'<rect id="{{id}}" x="-1" y="-1" width="{CELL + 2}" height="{CELL + 2}" rx="2" '
        f'fill="{tokens.NOKIA["snake"]}"/>',
    )

    # The shared path: one keyframe per track entry, held at the last position so the snake
    # sits still through the reset window instead of running off the end of its own data.
    path_frames = [
        Keyframe(
            index * record.step_dt,
            {"transform": f"translate({n(grid_x + _cell_xy(*cell)[0])}px,"
                          f"{n(grid_y + _cell_xy(*cell)[1])}px)"},
        )
        for index, cell in enumerate(record.track)
    ]
    last = record.track[-1]
    path_frames.append(
        Keyframe(
            record.duration,
            {"transform": f"translate({n(grid_x + _cell_xy(*last)[0])}px,"
                          f"{n(grid_y + _cell_xy(*last)[1])}px)"},
        )
    )
    path_cls = anim.add(path_frames)

    birth = {index: 0.0 for index in range(record.start_length)}
    for step, length in record.growth:
        birth[length - 1] = step * record.step_dt

    segments: list[str] = []
    for index in range(record.max_length):
        delay = (index - record.start_offset) * record.step_dt
        moving = anim.use(path_cls, delay=delay)
        born = birth.get(index, 0.0)
        # Tail-first fade: the last segment goes first, so the snake retracts rather than
        # blinking out all at once.
        fade_start = record.reset_at + FADE * (1 - index / max(1, record.max_length))
        visible = anim.add(
            _hold(_appear(born, until=fade_start, fade_out=0.25), record.duration),
            easing="linear",
            base={"opacity": "0"},
        )
        shade_ref = (
            head_ref
            if index == 0
            else body_refs[min(BODY_SHADES - 1, index * BODY_SHADES // record.max_length)]
        )
        segments.append(
            f'<g class="{visible}"><g class="{moving}">{use(shade_ref)}</g></g>'
        )
    doc.add("".join(segments))

    # ---- LCD grain --------------------------------------------------------
    scan = doc.defs.add(
        "scan",
        '<pattern id="{id}" width="3" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="3" height="1" fill="{tokens.VOID}" opacity="0.30"/></pattern>',
    )
    doc.add(
        f'<rect x="{SHELL_X}" y="{SHELL_TOP}" width="{lcd_w}" height="{lcd_h}" rx="4" '
        f'fill="url({scan})" pointer-events="none"/>'
    )

    doc.css(anim.css())
    markup = doc.render()
    path.write_text(markup, encoding="utf-8")
    return markup
