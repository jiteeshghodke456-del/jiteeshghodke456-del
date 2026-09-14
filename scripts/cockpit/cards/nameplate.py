"""The nameplate: name, thesis, and the ambient bar that names the system.

This card carries the whole first impression, so it is legible with every
animation disabled - the light sweep is garnish, never load-bearing.
"""

from __future__ import annotations

from .. import svg, tokens
from ..typography import TypeSetter, fmt, load_face

NAME = "JITEESH GHODKE"
EYEBROW = "SOFTWARE ENGINEER · SYSTEM DESIGN · BTECH '29"
THESIS = "I build things that keep running when I am not watching them."
INDICATORS = [
    ("OPEN TO INTERNSHIPS", tokens.ICE, True),
    ("SHIPPING A DESKTOP APP", tokens.ROSE, True),
]

WASH_ROSE = "wr"
WASH_ICE = "wi"

# Geometry the height calculation depends on. TELLTALE_RADIUS is the halo drawn in
# _telltale; BAR_INSET is where svg.ambient_bar sits above the bottom edge.
TELLTALE_RADIUS = 8
BAR_CLEARANCE = 16
BAR_INSET = 20


def _defs() -> str:
    return svg.radial_wash(WASH_ROSE, tokens.ROSE, 0.34) + svg.radial_wash(
        WASH_ICE, tokens.ICE, 0.30
    )


def _wash(width: int, height: int) -> str:
    """Two pools of cabin light, rose to the left, ice to the right.

    Radial gradients rather than blurred ellipses: the falloff is the fill, so
    there is no filter to drop and no hard edge to leak.
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
    face: str = tokens.DISPLAY,
    tracking: int = tokens.TRACK_NAMEPLATE,
) -> float:
    """Largest size at which every line of ``lines`` still fits ``available``.

    Takes all the lines, not one of them. The mobile nameplate used to be fitted against
    "JITEESH" while the wider line is "GHODKE" by 2.8%, and it fitted only because the size
    cap of 62 happened to bind before the width constraint did. Raising that cap by two
    pushed GHODKE off the card while this function still reported that it fitted.

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
    upem = load_face(face)["upem"]
    return min(maximum, available * upem / units)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD
    available = width - pad * 2

    setter = TypeSetter()
    body: list[str] = []

    # Eyebrow
    eyebrow_text = "BTECH '29 · SYSTEM DESIGN" if narrow else EYEBROW
    body.append(
        svg.eyebrow(setter, pad, pad + 12, eyebrow_text, size=9 if narrow else 10)
    )

    # Name. On mobile it stacks so the type can stay large instead of shrinking
    # to fit one line at a size nobody can read on a phone.
    if narrow:
        size = _fit_size(setter, ("JITEESH", "GHODKE"), available, 62)
        baseline = pad + 78
        for index, line in enumerate(("JITEESH", "GHODKE")):
            body.append(
                setter.text(
                    pad,
                    baseline + index * (size * 0.92),
                    line,
                    face=tokens.DISPLAY,
                    size=size,
                    fill=tokens.TEXT,
                    tracking=tokens.TRACK_NAMEPLATE,
                )
            )
        cursor = baseline + size * 0.92 + 34
    else:
        size = _fit_size(setter, NAME, available, 74)
        baseline = pad + 86
        body.append(
            setter.text(
                pad,
                baseline,
                NAME,
                face=tokens.DISPLAY,
                size=size,
                fill=tokens.TEXT,
                tracking=tokens.TRACK_NAMEPLATE,
            )
        )
        cursor = baseline + 34

    # Thesis
    thesis = "Systems, contests, and one\nshipped desktop app." if narrow else THESIS
    for index, line in enumerate(thesis.split("\n")):
        body.append(
            setter.text(
                pad,
                cursor + index * 20,
                line,
                face=tokens.MONO,
                size=14 if narrow else 15,
                fill=tokens.TEXT,
                opacity=0.72,
            )
        )
    cursor += 20 * len(thesis.split("\n")) + 14

    # Status indicators, lit like dashboard telltales.
    if narrow:
        for index, (text, color, lit) in enumerate(INDICATORS):
            row_y = cursor + index * 20
            body.append(_telltale(setter, pad, row_y, text, color, lit))
        last_row = cursor + 20 * (len(INDICATORS) - 1)
    else:
        offset = pad
        for text, color, lit in INDICATORS:
            body.append(_telltale(setter, offset, cursor, text, color, lit))
            offset += 22 + setter.width(text, tokens.DISPLAY, 9, tokens.TRACK_LABEL) + 34
        last_row = cursor

    # The canvas is derived from the content, not asserted ahead of it. This card used to
    # hardcode its height while every sibling computed one, and the mobile layout quietly
    # grew 13px past the constant. Nothing fell off the canvas, because the ambient bar was
    # pinned to height - 20 rather than following the cursor, so instead the bar was drawn
    # straight through the last telltale and its dot. Deriving both from the same cursor is
    # what makes that impossible rather than merely fixed.
    ink_bottom = last_row + TELLTALE_RADIUS + 1
    height = int(ink_bottom + BAR_CLEARANCE + BAR_INSET)

    body.insert(0, _wash(width, height))
    body.append(svg.ambient_bar(pad, height - BAR_INSET, available))

    return svg.document(
        width,
        height,
        "".join(body),
        defs=_defs() + setter.defs(),
        title="Jiteesh Ghodke - software engineer, system design, competitive programming",
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
