"""The instrument cluster: four dials and an odometer.

A gauge states its own scale, which is the point. Seventy-one contributions on
a printed 0-365 face reads as a position and a direction; the same number in a
stat card reads as a magnitude, and magnitude is the wrong question for an
account that is ten months old.

The accept-rate dial goes further and splits its arc: ice for the submissions
the judge accepted, rose for the ones it did not. The gauge is the data.
"""

from __future__ import annotations

import math

from .. import svg, tokens
from ..typography import TypeSetter, fmt

START_ANGLE = 135.0
SWEEP = 270.0


def _tick_marks(cx: float, cy: float, radius: float, count: int = 10) -> str:
    parts = []
    for index in range(count + 1):
        angle = START_ANGLE + SWEEP * index / count
        major = index % 2 == 0
        inner = radius - (9 if major else 5)
        x1, y1 = svg.polar(cx, cy, inner, angle)
        x2, y2 = svg.polar(cx, cy, radius - 1, angle)
        parts.append(
            f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}"'
            f' stroke="{tokens.HAIRLINE if not major else tokens.DIM}"'
            f' stroke-width="{2 if major else 1}" stroke-linecap="round"/>'
        )
    return "".join(parts)


def _arc_length(radius: float, degrees: float) -> float:
    return 2 * math.pi * radius * degrees / 360.0


def _needle(
    motion: svg.Motion,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    color: str,
    index: int,
) -> str:
    """Needle plus hub. Rests at the reading; the sweep is how it gets there."""
    tip = radius - 12
    name = f"nd{index}"
    motion.origin(name, cx, cy)
    motion.sweep(
        name,
        f"transform:rotate({fmt(START_ANGLE)}deg)",
        f"transform:rotate({fmt(angle)}deg)",
        delay=0.15 + index * 0.12,
    )
    return (
        f'<g class="{name}" transform="rotate({fmt(angle)} {fmt(cx)} {fmt(cy)})">'
        f'<line x1="{fmt(cx - 6)}" y1="{fmt(cy)}" x2="{fmt(cx + tip)}" y2="{fmt(cy)}"'
        f' stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
        "</g>"
        f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="6" fill="{tokens.PANEL_HI}"'
        f' stroke="{color}" stroke-width="1.5"/>'
        f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="2" fill="{color}"/>'
    )


def _dial(
    setter: TypeSetter,
    motion: svg.Motion,
    cx: float,
    cy: float,
    radius: float,
    gauge: dict,
    index: int,
) -> str:
    fraction = 0.0 if gauge["max"] <= 0 else min(1.0, gauge["value"] / gauge["max"])
    angle = START_ANGLE + SWEEP * fraction
    full_length = _arc_length(radius, SWEEP)
    value_length = full_length * fraction

    parts = [
        # Track
        f'<path d="{svg.arc(cx, cy, radius, START_ANGLE, START_ANGLE + SWEEP)}"'
        f' fill="none" stroke="{tokens.PANEL_HI}" stroke-width="7"'
        ' stroke-linecap="round"/>',
        _tick_marks(cx, cy, radius - 10),
    ]

    if gauge.get("split"):
        # Accept-rate dial: the remainder of the arc is drawn as the failures
        # rather than left empty, so the ratio is legible without a legend.
        parts.append(
            f'<path d="{svg.arc(cx, cy, radius, angle, START_ANGLE + SWEEP)}"'
            f' fill="none" stroke="{tokens.ROSE}" stroke-width="7"'
            ' stroke-linecap="butt" opacity="0.55"/>'
        )

    # Value arc, drawn twice: a wide faint copy for the light it throws, then
    # the crisp stroke on top. The dasharray holds the reading; the animation
    # only supplies the fill-in.
    track = svg.arc(cx, cy, radius, START_ANGLE, START_ANGLE + SWEEP)
    gap = fmt(full_length + 4)
    for layer, (stroke_width, opacity) in enumerate(((16, 0.13), (7, 1.0))):
        name = motion.sweep(
            f"ar{index}{layer}",
            f"stroke-dasharray:0 {gap}",
            f"stroke-dasharray:{fmt(value_length)} {gap}",
            delay=0.15 + index * 0.12,
        )
        parts.append(
            f'<path class="{name}" d="{track}" fill="none"'
            f' stroke="{gauge["color"]}" stroke-width="{stroke_width}"'
            f' stroke-linecap="round" opacity="{fmt(opacity)}"'
            f' stroke-dasharray="{fmt(value_length)} {gap}"/>'
        )

    parts.append(_needle(motion, cx, cy, radius, angle, gauge["color"], index))

    # Readout sits clear of the hub: number above, scale below.
    parts.append(
        setter.text(
            cx,
            cy - 8,
            gauge["display"],
            face=tokens.MONO_SEMI,
            size=gauge.get("value_size", 21 if radius < 56 else 24),
            fill=tokens.TEXT,
            anchor="middle",
        )
    )
    parts.append(
        setter.text(
            cx,
            cy + 28,
            gauge["scale_note"],
            face=tokens.MONO,
            size=9,
            fill=tokens.MUTED,
            anchor="middle",
        )
    )

    # Scale ends, printed on the face like a real instrument
    left_x, left_y = svg.polar(cx, cy, radius + 12, START_ANGLE)
    right_x, right_y = svg.polar(cx, cy, radius + 12, START_ANGLE + SWEEP)
    parts.append(
        setter.text(
            left_x - 2, left_y + 4, gauge["min_label"], face=tokens.MONO, size=8,
            fill=tokens.DIM, anchor="end",
        )
    )
    parts.append(
        setter.text(
            right_x + 2, right_y + 4, gauge["max_label"], face=tokens.MONO, size=8,
            fill=tokens.DIM, anchor="start",
        )
    )
    return "".join(parts)


def _odometer(
    setter: TypeSetter, x: float, y: float, width: float, digits: str, caption: str
) -> str:
    """Mechanical drum readout. One recessed cell per digit."""
    cell_w, cell_h, gap = 22, 34, 4
    parts = [
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" height="{fmt(cell_h + 20)}"'
        f' rx="8" fill="{tokens.PANEL_HI}" stroke="{tokens.HAIRLINE}"/>',
        svg.eyebrow(setter, x + 14, y + 21, "ODO", color=tokens.DIM, size=9),
    ]
    origin = x + 52
    for index, digit in enumerate(digits):
        cell_x = origin + index * (cell_w + gap)
        parts.append(
            f'<rect x="{fmt(cell_x)}" y="{fmt(y + 10)}" width="{cell_w}"'
            f' height="{cell_h}" rx="4" fill="{tokens.VOID}"'
            f' stroke="{tokens.HAIRLINE}"/>'
        )
        parts.append(
            setter.text(
                cell_x + cell_w / 2,
                y + 34,
                digit,
                face=tokens.MONO_SEMI,
                size=20,
                fill=tokens.TEXT if digit != "0" else tokens.DIM,
                anchor="middle",
            )
        )
    caption_x = origin + len(digits) * (cell_w + gap) + 14
    parts.append(
        setter.text(
            caption_x, y + 30, caption, face=tokens.MONO, size=11, fill=tokens.MUTED
        )
    )
    return "".join(parts)


def gauges_from(data: dict) -> list[dict]:
    contributions = data["streaks"]["total"]
    codeforces = data["codeforces"]
    repos = data["repo_count"]
    return [
        {
            "label": "CONTRIBUTIONS",
            "sub": "last 365 days",
            "value": contributions,
            "max": 365,
            "display": str(contributions),
            "scale_note": "of 365",
            "min_label": "0",
            "max_label": "365",
            "color": tokens.ROSE,
        },
        {
            "label": "PROBLEMS SOLVED",
            "sub": "codeforces, unique",
            "value": codeforces["solved"],
            "max": 100,
            "display": str(codeforces["solved"]),
            "scale_note": "of 100",
            "min_label": "0",
            "max_label": "100",
            "color": tokens.ICE,
        },
        {
            "label": "ACCEPT RATE",
            "sub": f"{codeforces['accepted']} of {codeforces['total']} submissions",
            "value": codeforces["accept_rate"],
            "max": 100,
            "display": f"{codeforces['accept_rate']:.0f}%",
            "scale_note": "accepted",
            "min_label": "0",
            "max_label": "100",
            "color": tokens.ICE,
            "split": True,
        },
        {
            "label": "REPOSITORIES",
            "sub": "public, excluding forks",
            "value": repos,
            "max": 30,
            "display": str(repos),
            "scale_note": "of 30",
            "min_label": "0",
            "max_label": "30",
            "color": tokens.ROSE,
        },
    ]


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD
    available = width - pad * 2
    gauges = gauges_from(data)

    setter = TypeSetter()
    motion = svg.Motion()
    body: list[str] = []

    columns = 2 if narrow else 4
    rows = math.ceil(len(gauges) / columns)
    radius = 52 if narrow else 58
    cell_w = available / columns
    row_h = 200 if narrow else 196
    top = 58

    height = int(top + rows * row_h + 74)
    body.append(svg.card(pad - 12, 8, available + 24, height - 16))
    body.append(svg.eyebrow(setter, pad + 4, 36, "INSTRUMENT CLUSTER"))
    body.append(
        setter.text(
            width - pad - 4,
            36,
            "live, rebuilt daily",
            face=tokens.MONO,
            size=10,
            fill=tokens.DIM,
            anchor="end",
        )
    )

    for index, gauge in enumerate(gauges):
        column = index % columns
        row = index // columns
        cx = pad + cell_w * column + cell_w / 2
        cy = top + row * row_h + radius + 22
        body.append(_dial(setter, motion, cx, cy, radius, gauge, index))
        body.append(
            setter.text(
                cx,
                cy + radius + 34,
                gauge["label"],
                face=tokens.DISPLAY,
                size=9,
                fill=tokens.TEXT,
                tracking=tokens.TRACK_LABEL,
                anchor="middle",
            )
        )
        body.append(
            setter.text(
                cx,
                cy + radius + 50,
                gauge["sub"],
                face=tokens.MONO,
                size=9,
                fill=tokens.DIM,
                anchor="middle",
            )
        )

    odo_y = top + rows * row_h + 2
    digits = f"{data['account_age_days']:06d}"
    caption = "days since the first commit" if not narrow else "days in"
    body.append(_odometer(setter, pad, odo_y, available, digits, caption))

    return svg.document(
        width,
        height,
        "".join(body),
        defs=setter.defs() + motion.style(),
        title="Instrument cluster: contributions, problems solved, accept rate, repositories",
        description=(
            f"{data['streaks']['total']} contributions in the last 365 days, "
            f"{data['codeforces']['solved']} Codeforces problems solved, "
            f"{data['codeforces']['accept_rate']:.0f}% accept rate, "
            f"{data['repo_count']} repositories."
        ),
    )
