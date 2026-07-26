"""What the code actually is: measured language mix, then the toolkit.

The bar is bytes on disk across every non-fork repository, not a list of
things that sound good in a profile. The two are rarely the same, and the
caption says so.
"""

from __future__ import annotations

from .. import icons, svg, tokens
from ..typography import TypeSetter, fmt

SHIPS_IN = ["typescript", "react", "python", "electron", "supabase", "postgresql", "nodedotjs"]
LEARNING = ["rust", "cplusplus"]

CAPTION = (
    "GitHub says TypeScript. Codeforces says Python. "
    "The C++ on my old toolkit list was aspirational."
)


def mix(first: str, second: str, amount: float) -> str:
    """Blend two hex colours. Keeps the ramp inside the rose-ice pair."""
    amount = max(0.0, min(1.0, amount))
    parts = []
    for offset in (1, 3, 5):
        a = int(first[offset : offset + 2], 16)
        b = int(second[offset : offset + 2], 16)
        parts.append(round(a + (b - a) * amount))
    return "#" + "".join(f"{value:02X}" for value in parts)


def top_languages(languages: dict, limit: int = 6, floor: float = 0.01) -> list[tuple[str, int]]:
    """Rank languages by bytes, folding the long tail into one segment.

    Anything under ``floor`` of the total joins Other rather than being listed
    at "0%", which is a label that occupies a row and says nothing.
    """
    total = sum(languages.values())
    ranked = sorted(languages.items(), key=lambda row: row[1], reverse=True)

    head: list[tuple[str, int]] = []
    tail = 0
    for name, count in ranked:
        if len(head) < limit and (not total or count / total >= floor):
            head.append((name, count))
        else:
            tail += count
    # Only name the tail if it would round to at least 1%. An "Other 0%" row
    # costs a line of the reader's attention and reports nothing.
    if tail and (not total or tail / total >= 0.005):
        head.append(("Other", tail))
    return head


def _icon_row(
    setter: TypeSetter,
    x: float,
    y: float,
    label: str,
    slugs: list[str],
    color: str,
) -> str:
    parts = [
        svg.eyebrow(setter, x, y + 12, label, color=tokens.DIM, size=9),
    ]
    offset = x + 96
    for slug in slugs:
        if not icons.has(slug):
            continue
        parts.append(icons.icon(slug, offset, y, 20, fill=color, opacity=0.85))
        offset += 30
    return "".join(parts)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD
    available = width - pad * 2

    languages = top_languages(dict(data.get("languages") or {}))
    total = sum(count for _, count in languages) or 1

    setter = TypeSetter()
    motion = svg.Motion()
    body: list[str] = []

    top = 62
    bar_h = 22
    columns = 2 if narrow else 4
    # Ceiling division. Flooring here left the last row of labels sitting
    # underneath the divider that is supposed to come after them.
    label_rows = -(-len(languages) // columns)
    labels_h = 22 * max(1, label_rows) + 10
    rows_y = top + bar_h + labels_h + 34
    height = int(rows_y + (108 if narrow else 92))

    body.append(svg.card(pad - 12, 8, available + 24, height - 16))
    body.append(
        svg.eyebrow(
            setter, pad + 4, 36,
            "THE CODE, MEASURED" if narrow else "WHAT THE CODE ACTUALLY IS",
        )
    )
    if not narrow:
        body.append(
            setter.text(
                width - pad - 4, 36, f"{total / 1_000_000:.1f}M bytes measured",
                face=tokens.MONO, size=10, fill=tokens.DIM, anchor="end",
            )
        )

    # Stacked bar. Rank drives the blend, so first place is fully rose and
    # last place is fully ice - the ramp is the ordering.
    offset = pad + 4
    bar_w = available - 8
    for index, (name, count) in enumerate(languages):
        share = count / total
        segment = bar_w * share
        color = mix(tokens.ROSE, tokens.ICE, index / max(1, len(languages) - 1))
        radius = 4 if index in (0, len(languages) - 1) else 0
        cls = motion.shared(
            "grow",
            "transform:scaleX(0)",
            "transform:scaleX(1)",
            0.1 + index * 0.08,
            duration=1.0,
        )
        body.append(
            f'<g class="{cls}" style="transform-box:view-box;'
            f'transform-origin:{fmt(offset)}px 0">'
            f'<rect x="{fmt(offset)}" y="{fmt(top)}" width="{fmt(max(1.0, segment - 1))}"'
            f' height="{bar_h}" rx="{radius}" fill="{color}"/>'
            "</g>"
        )
        offset += segment

    # Labels under the bar
    column_w = (available - 8) / columns
    for index, (name, count) in enumerate(languages):
        share = count / total * 100
        column = index % columns
        row = index // columns
        label_x = pad + 4 + column * column_w
        label_y = top + bar_h + 26 + row * 22
        color = mix(tokens.ROSE, tokens.ICE, index / max(1, len(languages) - 1))
        body.append(
            f'<rect x="{fmt(label_x)}" y="{fmt(label_y - 8)}" width="8" height="8"'
            f' rx="2" fill="{color}"/>'
        )
        body.append(
            setter.text(
                label_x + 14,
                label_y,
                f"{name} {share:.0f}%",
                face=tokens.MONO,
                size=10.5,
                fill=tokens.TEXT,
                opacity=0.78,
            )
        )

    body.append(svg.hairline(pad + 4, rows_y - 22, available - 8))
    body.append(_icon_row(setter, pad + 4, rows_y - 6, "SHIPS IN", SHIPS_IN, tokens.ICE))
    body.append(
        _icon_row(setter, pad + 4, rows_y + 30, "LEARNING", LEARNING, tokens.ROSE)
    )

    caption = CAPTION if not narrow else "GitHub says TypeScript.\nCodeforces says Python."
    for index, line in enumerate(caption.split("\n")):
        body.append(
            setter.text(
                pad + 4,
                rows_y + (70 if not narrow else 74) + index * 16,
                line,
                face=tokens.MONO,
                size=11,
                fill=tokens.TEXT,
                opacity=0.68,
            )
        )

    return svg.document(
        width,
        height,
        "".join(body),
        defs=setter.defs() + motion.style(),
        title="Language mix and toolkit",
        description=", ".join(
            f"{name} {count / total * 100:.0f}%" for name, count in languages
        ),
    )
