"""The nameplate, as the title screen of a game nobody finished porting.

Press Start 2P for the name, letters landing one at a time, a perspective grid running away
to a vanishing point, and PRESS START blinking underneath. Everything else on the page is a
specific machine, a Game Boy and a 3310, so the banner is the cabinet they were all plugged
into.

Two rules this card is built around.

The canvas is derived from the content rather than asserted ahead of it. The previous
version hardcoded its height, the mobile layout outgrew it, and because the ambient bar was
pinned to the bottom edge instead of following the cursor, the bar was drawn straight
through the last status row. Both numbers now come from the same cursor.

The resting state is the base state. Every animated element sits where it belongs at t=0 and
the motion is a departure from that, not an arrival at it. An asset whose first frame is
blank is an asset that is blank whenever motion is suppressed, and this card is the first
thing anybody sees.
"""

from __future__ import annotations

from profilegen.svg.anim import AnimationSet, Keyframe, Timeline

from .. import svg, tokens
from ..typography import TypeSetter, fmt, load_face

NAME = "JITEESH GHODKE"
NAME_LINES = ("JITEESH", "GHODKE")
EYEBROW = "SOFTWARE ENGINEER · SYSTEM DESIGN · BTECH '29"
THESIS = "I build things that keep running when I am not watching them."
INDICATORS = [
    ("OPEN TO INTERNSHIPS", tokens.ICE, True),
    ("SHIPPING A DESKTOP APP", tokens.ROSE, True),
]
START_PROMPT = "PRESS START"

WASH_ROSE = "wr"
WASH_ICE = "wi"
NAME_CLIP = "npn"

# Geometry the height calculation depends on. TELLTALE_RADIUS is the halo drawn in
# _telltale; BAR_INSET is where svg.ambient_bar sits above the bottom edge.
TELLTALE_RADIUS = 8
BAR_CLEARANCE = 16
BAR_INSET = 20

CYCLE = 9.0          # one title drop per nine seconds is alive without being a nuisance
GRID_BAND = 74       # the floor gets its own strip; overlaying it on copy made the copy
                     # unreadable, and a backdrop that competes with the text is scenery
                     # in the wrong seat
DROP_AT = CYCLE - 1.7
STAGGER = 0.055
GRID_ROWS = 6


def _defs(clip_y: float, clip_h: float, width: int) -> str:
    # Letters enter from above their resting line, so without a clip they are simply drawn
    # outside the card: over the eyebrow and past the top edge. A cabinet bezel does this
    # for free. In SVG it has to be said, and it is the same omission that let a falling
    # tetromino land on the page rather than in the well.
    return (
        svg.radial_wash(WASH_ROSE, tokens.ROSE, 0.34)
        + svg.radial_wash(WASH_ICE, tokens.ICE, 0.30)
        + f'<clipPath id="{NAME_CLIP}"><rect x="0" y="{fmt(clip_y)}" '
        f'width="{width}" height="{fmt(clip_h)}"/></clipPath>'
    )


def _wash(width: int, height: int) -> str:
    """Two pools of cabin light, violet to the left, acid to the right.

    Radial gradients rather than blurred ellipses: the falloff is the fill, so there is no
    filter to drop and no hard edge to leak.
    """
    return (
        f'<ellipse cx="{fmt(width * 0.08)}" cy="{fmt(height * 0.16)}"'
        f' rx="{fmt(width * 0.52)}" ry="{fmt(height * 0.95)}"'
        f' fill="url(#{WASH_ROSE})"/>'
        f'<ellipse cx="{fmt(width * 0.94)}" cy="{fmt(height * 0.92)}"'
        f' rx="{fmt(width * 0.50)}" ry="{fmt(height * 0.90)}"'
        f' fill="url(#{WASH_ICE})"/>'
    )


def _fit_size(
    setter: TypeSetter,
    lines: str | tuple[str, ...],
    available: float,
    maximum: float,
    *,
    face: str = tokens.ARCADE,
    tracking: int = tokens.TRACK_ARCADE,
) -> float:
    """Largest size at which every line of ``lines`` still fits ``available``.

    Takes all the lines, not one of them. The mobile nameplate used to be fitted against
    "JITEESH" while the wider line is "GHODKE" by 2.8%, and it fitted only because the size
    cap happened to bind before the width constraint did. Raising that cap by two pushed
    GHODKE off the card while this function still reported success.

    The em size is read from the face rather than assumed to be 1000, which is true of all
    four faces today and is exactly the sort of thing that stops being true silently.
    """
    if isinstance(lines, str):
        lines = (lines,)
    units = max(
        (setter.advance_units(line, face, tracking) for line in lines), default=0
    )
    if units <= 0:
        return maximum
    return min(maximum, available * load_face(face)["upem"] / units)


def _grid(anim: AnimationSet, x: float, y: float, width: float, depth: float) -> str:
    """A perspective floor running away to a vanishing point on the horizon.

    Rows are spaced quadratically so they crowd toward the horizon, and each row animates
    into the position of the row in front of it over exactly one cycle. That is what makes
    the scroll seamless: at the loop point every row has taken its neighbour's place and the
    figure is identical to where it started.
    """
    vanish_x = x + width / 2
    parts: list[str] = []

    # Rails converging on the vanishing point. Static, because they are the thing the rows
    # move against.
    for index in range(-9, 10):
        far = vanish_x + index * 3
        near = vanish_x + index * (width / 7)
        parts.append(
            f'<line x1="{fmt(far)}" y1="{fmt(y)}" x2="{fmt(near)}" y2="{fmt(y + depth)}"'
            f' stroke="{tokens.ACID}" stroke-width="1" opacity="0.22"/>'
        )

    def row_y(step: float) -> float:
        return y + depth * (step / GRID_ROWS) ** 2.8

    for index in range(GRID_ROWS):
        start, end = row_y(index), row_y(index + 1)
        # Rows fade in at the horizon and out as they reach the viewer, so neither end of
        # the run pops.
        near = index / GRID_ROWS
        cls = anim.add(
            [
                Keyframe(0.0, {"transform": "translate(0px,0px)", "opacity": fmt(0.08 + near * 0.26)}),
                Keyframe(CYCLE, {"transform": f"translate(0px,{fmt(end - start)}px)",
                                 "opacity": fmt(0.08 + (near + 1 / GRID_ROWS) * 0.26)}),
            ],
            easing="linear",
        )
        parts.append(
            f'<g class="{cls}"><line x1="{fmt(x)}" y1="{fmt(start)}"'
            f' x2="{fmt(x + width)}" y2="{fmt(start)}"'
            f' stroke="{tokens.ACID}" stroke-width="1.5"/></g>'
        )

    parts.append(
        f'<line x1="{fmt(x)}" y1="{fmt(y)}" x2="{fmt(x + width)}" y2="{fmt(y)}"'
        f' stroke="{tokens.ACID}" stroke-width="1.25" opacity="0.40"/>'
    )
    return "".join(parts)


def _dropped_name(
    setter: TypeSetter,
    anim: AnimationSet,
    x: float,
    baseline: float,
    text: str,
    size: float,
    order_from: int = 0,
) -> tuple[str, int]:
    """Set ``text`` one glyph at a time so each can land on its own beat.

    Rendering the line as a single run would be cheaper, but then the whole name can only
    move as one block. A title screen lands its letters.
    """
    parts: list[str] = []
    pen = x
    step = size * load_face(tokens.ARCADE)["upem"] / 1000
    index = order_from
    for char in text:
        advance = setter.width(char, tokens.ARCADE, size, tokens.TRACK_ARCADE)
        if char.strip():
            land = DROP_AT + 0.12 + index * STAGGER
            cls = anim.add(
                [
                    Keyframe(0.0, {"transform": "translate(0px,0px)", "opacity": "1"}),
                    Keyframe(DROP_AT, {"transform": "translate(0px,0px)", "opacity": "1"}),
                    Keyframe(DROP_AT + 0.06, {"transform": f"translate(0px,{fmt(-step * 1.6)}px)", "opacity": "0"}),
                    Keyframe(land, {"transform": f"translate(0px,{fmt(-step * 1.6)}px)", "opacity": "1"}),
                    Keyframe(land + 0.16, {"transform": "translate(0px,0px)", "opacity": "1"}),
                    Keyframe(CYCLE, {"transform": "translate(0px,0px)", "opacity": "1"}),
                ],
                easing="linear",
            )
            parts.append(
                f'<g class="{cls}">'
                + setter.text(
                    pen, baseline, char,
                    face=tokens.ARCADE, size=size, fill=tokens.TEXT,
                    tracking=tokens.TRACK_ARCADE,
                )
                + "</g>"
            )
            index += 1
        pen += advance
    return "".join(parts), index


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD
    available = width - pad * 2

    setter = TypeSetter()
    anim = AnimationSet(Timeline(CYCLE), "n")
    body: list[str] = []

    eyebrow_text = "BTECH '29 · SYSTEM DESIGN" if narrow else EYEBROW
    body.append(
        svg.eyebrow(setter, pad, pad + 12, eyebrow_text, size=9 if narrow else 10)
    )

    if narrow:
        size = _fit_size(setter, NAME_LINES, available, 52)
        baseline = pad + 68
        order = 0
        name_parts: list[str] = []
        for line_index, line in enumerate(NAME_LINES):
            markup, order = _dropped_name(
                setter, anim, pad, baseline + line_index * size * 1.32, line, size, order
            )
            name_parts.append(markup)
        name_markup = "".join(name_parts)
        name_bottom = baseline + size * 1.32
        cursor = name_bottom + 36
    else:
        size = _fit_size(setter, NAME, available, 56)
        baseline = pad + 84
        name_markup, _ = _dropped_name(setter, anim, pad, baseline, NAME, size)
        name_bottom = baseline
        cursor = baseline + 36

    clip_top = pad + 22
    body.append(
        f'<g clip-path="url(#{NAME_CLIP})">{name_markup}</g>'
    )

    thesis = "Systems, contests, and one\nshipped desktop app." if narrow else THESIS
    for index, line in enumerate(thesis.split("\n")):
        body.append(
            setter.text(
                pad, cursor + index * 20, line,
                face=tokens.MONO, size=14 if narrow else 15,
                fill=tokens.TEXT, opacity=0.72,
            )
        )
    cursor += 20 * len(thesis.split("\n")) + 14

    if narrow:
        for index, (text, color, lit) in enumerate(INDICATORS):
            body.append(_telltale(setter, pad, cursor + index * 20, text, color, lit))
        last_row = cursor + 20 * (len(INDICATORS) - 1)
    else:
        offset = pad
        for text, color, lit in INDICATORS:
            body.append(_telltale(setter, offset, cursor, text, color, lit))
            offset += 22 + setter.width(text, tokens.DISPLAY, 9, tokens.TRACK_LABEL) + 34
        last_row = cursor

    # PRESS START, blinking on a slow duty cycle so it reads as waiting rather than warning.
    prompt_size = 9 if narrow else 11
    prompt_w = setter.width(START_PROMPT, tokens.ARCADE, prompt_size, tokens.TRACK_ARCADE)
    blink = anim.add(
        [
            Keyframe(0.0, {"opacity": "1"}),
            Keyframe(CYCLE * 0.42, {"opacity": "1"}),
            Keyframe(CYCLE * 0.48, {"opacity": "0.12"}),
            Keyframe(CYCLE * 0.92, {"opacity": "0.12"}),
            Keyframe(CYCLE * 0.97, {"opacity": "1"}),
            Keyframe(CYCLE, {"opacity": "1"}),
        ],
    )
    body.append(
        f'<g class="{blink}">'
        + setter.text(
            width - pad - prompt_w, last_row, START_PROMPT,
            face=tokens.ARCADE, size=prompt_size, fill=tokens.ACID,
            tracking=tokens.TRACK_ARCADE,
        )
        + "</g>"
    )

    ink_bottom = last_row + TELLTALE_RADIUS + 1
    height = int(ink_bottom + GRID_BAND + BAR_CLEARANCE + BAR_INSET)

    body.insert(0, _wash(width, height))
    # The floor gets a strip of its own below the content rather than running behind it.
    body.insert(1, _grid(anim, pad, ink_bottom + 6, available, GRID_BAND))
    body.append(svg.ambient_bar(pad, height - BAR_INSET, available))

    return svg.document(
        width,
        height,
        f"<style>{anim.css()}</style>" + "".join(body),
        defs=_defs(clip_top, name_bottom + 12 - clip_top, width) + setter.defs(),
        title="Jiteesh Ghodke, software engineer, system design, competitive programming",
        description=THESIS,
    )


def _telltale(
    setter: TypeSetter, x: float, y: float, text: str, color: str, lit: bool
) -> str:
    """A dashboard warning light: filled dot plus tracked caps."""
    dot = (
        f'<circle cx="{fmt(x + 5)}" cy="{fmt(y - 4)}" r="4" fill="{color}"'
        f' opacity="{1 if lit else 0.25}"/>'
    )
    halo = (
        f'<circle cx="{fmt(x + 5)}" cy="{fmt(y - 4)}" r="8" fill="{color}"'
        ' opacity="0.18"/>'
        if lit
        else ""
    )
    return (
        halo
        + dot
        + setter.text(
            x + 18,
            y,
            text,
            face=tokens.DISPLAY,
            size=9,
            fill=tokens.TEXT if lit else tokens.DIM,
            tracking=tokens.TRACK_LABEL,
        )
    )
