"""The work bays: four things that exist, each with somewhere to click.

Every bay points at a repository that is actually reachable. Projects with no
public trace are not listed - a wall of "coming soon" cards costs the reader
the same attention as real work and returns none of it.
"""

from __future__ import annotations

from .. import icons, svg, tokens
from ..typography import TypeSetter, fmt

BAYS = [
    {
        "name": "ATALEIR",
        "status": "INVITE BETA",
        "hot": True,
        "line": "Spoiler-free hints for story games, as a Windows overlay.",
        "aside": "Tells you where the key is. Not who dies.",
        "repo": "ataleir-beta-updates",
        "stack": ["electron", "typescript"],
    },
    {
        "name": "DRISHTI",
        "status": "HACKATHON BUILD",
        "hot": False,
        "line": "Cash-flow early warning for rural micro-enterprises.",
        "aside": "NABARD Hackathon at GFF 2026. Deadlines are a design constraint.",
        "repo": "ruraldrushtiteam5idiots",
        "stack": ["typescript", "supabase"],
    },
    {
        "name": "MAGI",
        "status": "COURSE PROJECT",
        "hot": False,
        "line": "Deepfake detection that admits when it is unsure.",
        "aside": "Started as coursework. Kept going well past the marking scheme.",
        "repo": "Magi_Deepfake_AI",
        "stack": ["python"],
    },
    {
        "name": "NEETCODE LOG",
        "status": "ONGOING",
        "hot": True,
        "line": "Every solution I have written down, including the ugly ones.",
        "aside": "Especially the ugly ones. That is the point of a log.",
        "repo": "neetcode-submissions",
        "stack": ["python"],
    },
]


def _status_pill(
    setter: TypeSetter, x: float, y: float, text: str, color: str
) -> tuple[str, float]:
    text_width = setter.width(text, tokens.DISPLAY, 8, tokens.TRACK_LABEL)
    width = text_width + 20
    body = (
        f'<rect x="{fmt(x)}" y="{fmt(y - 11)}" width="{fmt(width)}" height="18"'
        f' rx="9" fill="{color}" opacity="0.14"/>'
        f'<rect x="{fmt(x)}" y="{fmt(y - 11)}" width="{fmt(width)}" height="18"'
        f' rx="9" fill="none" stroke="{color}" stroke-width="1" opacity="0.45"/>'
        + setter.text(
            x + 10,
            y + 2,
            text,
            face=tokens.DISPLAY,
            size=8,
            fill=color,
            tracking=tokens.TRACK_LABEL,
        )
    )
    return body, width


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD
    available = width - pad * 2

    setter = TypeSetter()
    body: list[str] = []

    top = 62
    text_x = pad + 62
    # On a phone the copy has to wrap, so rows are measured rather than fixed.
    copy_width = width - pad - 8 - text_x if narrow else available - 200
    line_size, aside_size = 11.5, 10

    layout = []
    for bay in BAYS:
        lines = setter.wrap(bay["line"], tokens.MONO, line_size, copy_width)
        asides = setter.wrap(bay["aside"], tokens.MONO, aside_size, copy_width)
        body_h = 22 + len(lines) * 16 + len(asides) * 14
        if narrow:
            body_h += 30  # status pill and stack icons sit below the copy
        layout.append((bay, lines, asides, body_h + 22))

    height = int(top + sum(entry[3] for entry in layout) - 4)

    body.append(svg.card(pad - 12, 8, available + 24, height - 16))
    body.append(svg.eyebrow(setter, pad + 4, 36, "THE BAYS"))
    if not narrow:
        body.append(
            setter.text(
                width - pad - 4,
                36,
                f"{len(BAYS)} things that exist",
                face=tokens.MONO,
                size=10,
                fill=tokens.DIM,
                anchor="end",
            )
        )

    y = top
    for index, (bay, lines, asides, row_h) in enumerate(layout):
        color = tokens.ROSE if bay["hot"] else tokens.ICE

        if index:
            body.append(svg.hairline(pad + 4, y - 16, available - 8))

        # Bay number and the accent rail beside it
        body.append(
            setter.text(
                pad + 6,
                y + 22,
                f"{index + 1:02d}",
                face=tokens.DISPLAY,
                size=22,
                fill=tokens.DIM,
                tracking=20,
            )
        )
        body.append(
            f'<rect x="{fmt(pad + 46)}" y="{fmt(y - 2)}" width="3"'
            f' height="{fmt(row_h - 34)}" rx="1.5" fill="{color}" opacity="0.8"/>'
        )

        body.append(
            setter.text(
                text_x,
                y + 16,
                bay["name"],
                face=tokens.DISPLAY,
                size=17 if narrow else 19,
                fill=tokens.TEXT,
                tracking=40,
            )
        )
        cursor = y + 36
        for line in lines:
            body.append(
                setter.text(
                    text_x, cursor, line, face=tokens.MONO, size=line_size,
                    fill=tokens.TEXT, opacity=0.74,
                )
            )
            cursor += 16
        for line in asides:
            body.append(
                setter.text(
                    text_x, cursor, line, face=tokens.MONO, size=aside_size,
                    fill=tokens.MUTED,
                )
            )
            cursor += 14

        # Status pill and stack icons, right-aligned on wide layouts and
        # tucked under the copy when the card is narrow.
        if narrow:
            pill, pill_w = _status_pill(setter, text_x, cursor + 14, bay["status"], color)
            body.append(pill)
            icon_x = text_x + pill_w + 12
            icon_y = cursor + 4
        else:
            pill_text_w = setter.width(
                bay["status"], tokens.DISPLAY, 8, tokens.TRACK_LABEL
            )
            pill_x = width - pad - 6 - (pill_text_w + 20)
            pill, _ = _status_pill(setter, pill_x, y + 16, bay["status"], color)
            body.append(pill)
            icon_x = width - pad - 6 - len(bay["stack"]) * 24
            icon_y = y + 32

        for slot, slug in enumerate(bay["stack"]):
            if not icons.has(slug):
                continue
            body.append(
                icons.icon(
                    slug, icon_x + slot * 24, icon_y, 16, fill=tokens.MUTED, opacity=0.9
                )
            )

        y += row_h

    return svg.document(
        width,
        height,
        "".join(body),
        defs=setter.defs(),
        title="Project bays: Ataleir, Drishti, Magi, NeetCode log",
        description="; ".join(f"{bay['name']}: {bay['line']}" for bay in BAYS),
    )
