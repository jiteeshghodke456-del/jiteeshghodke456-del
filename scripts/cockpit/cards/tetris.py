"""Codeforces submissions as a Tetris board.

One column per problem, ordered by when it was first attempted. Each block is
one submission, stacked bottom-up in the order they were sent. Ice means the
judge accepted it, rose means it did not, and brightness picks the failure
apart - two hues carry the whole legend, so the board reads before anyone
reads the key.

Bucketing by problem rather than by date is what makes the board worth
looking at: a single ice block is a first-try accept, and a tall rose column
with ice on top is a problem that took all afternoon. Calendar weeks produced
a board that was 83% empty and said nothing.
"""

from __future__ import annotations

import collections

from .. import svg, tokens
from ..typography import TypeSetter, fmt

MAX_STACK = 14
CELL = 11
GUTTER = 2


def _verdict_key(verdict: str) -> str:
    return verdict if verdict in tokens.VERDICT_COLORS else "OTHER"


def columns_from(submissions: list[dict], limit: int) -> list[list[str]]:
    """One column per problem, oldest first attempt on the left."""
    buckets: dict[str, list[str]] = collections.defaultdict(list)
    for submission in sorted(
        submissions, key=lambda row: row.get("creationTimeSeconds") or 0
    ):
        problem = submission.get("problem") or {}
        key = f"{problem.get('contestId')}-{problem.get('index')}"
        buckets[key].append(_verdict_key(str(submission.get("verdict") or "OTHER")))

    columns = list(buckets.values())
    if len(columns) > limit:
        # Keep the most recent problems; the board is a running log, not an
        # archive, and the older columns are the ones already summarised above.
        columns = columns[-limit:]
    return columns


def first_try_accepts(columns: list[list[str]]) -> int:
    return sum(1 for column in columns if column and column[0] == "OK")


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    pad = tokens.PAD_NARROW if narrow else tokens.PAD
    available = width - pad * 2

    cell = 7 if narrow else CELL
    step = cell + GUTTER
    slots = max(1, int((available - 4) // step))

    submissions = data.get("codeforces_submissions") or []
    columns = columns_from(submissions, slots)
    stats = data["codeforces"]
    board_w = max(1, len(columns)) * step - GUTTER
    # Centre the well: a short log should not sit hard against the left wall.
    board_x = pad + (available - board_w) / 2

    setter = TypeSetter()
    motion = svg.Motion()
    body: list[str] = []

    top = 68 if not narrow else 84
    board_h = MAX_STACK * step
    legend_y = top + board_h + 34

    # Measure the legend and the caption before drawing anything: both wrap,
    # and the card frame has to be tall enough for whatever they turn into.
    seen = [key for key in tokens.VERDICT_COLORS if stats["verdicts"].get(key)]
    legend_entries = []
    cursor_x, legend_rows = pad + 4, 0
    for key in seen:
        label = f"{tokens.VERDICT_LABELS[key]} {stats['verdicts'][key]}"
        entry_w = 16 + setter.width(label, tokens.MONO, 10) + (14 if not narrow else 10)
        if cursor_x + entry_w > width - pad and cursor_x > pad + 4:
            legend_rows += 1
            cursor_x = pad + 4
        legend_entries.append((key, label, cursor_x, legend_rows))
        cursor_x += entry_w

    first = first_try_accepts(columns)
    caption_lines = setter.wrap(
        f"{first} of {len(columns)} went in on the first try. "
        f"The tall rose columns are the other {len(columns) - first}.",
        tokens.MONO,
        11,
        available - 8,
    )
    caption_y = legend_y + legend_rows * 18 + 26
    height = int(caption_y + len(caption_lines) * 16 + 14)

    body.append(svg.card(pad - 12, 8, available + 24, height - 16))
    eyebrow_text = "TETRIS, BUT CODEFORCES" if narrow else "CODEFORCES, BUT IT IS TETRIS"
    body.append(svg.eyebrow(setter, pad + 4, 36, eyebrow_text))
    meta = f"{len(columns)} problems · {stats['total']} submissions"
    if narrow:
        # No room beside the eyebrow on a phone, so the count sits under it.
        body.append(
            setter.text(pad + 4, 52, meta, face=tokens.MONO, size=9, fill=tokens.DIM)
        )
    else:
        body.append(
            setter.text(
                width - pad - 4, 36, meta, face=tokens.MONO, size=10,
                fill=tokens.DIM, anchor="end",
            )
        )

    floor = top + board_h

    # Well walls, so the empty board still reads as a board.
    body.append(
        f'<rect x="{fmt(board_x - 4)}" y="{fmt(top)}" width="{fmt(board_w + 8)}"'
        f' height="{fmt(board_h)}" fill="{tokens.VOID}" stroke="{tokens.HAIRLINE}"'
        ' rx="4"/>'
    )
    body.append(
        f'<rect x="{fmt(board_x - 4)}" y="{fmt(floor - 1)}"'
        f' width="{fmt(board_w + 8)}" height="2" fill="{tokens.HAIRLINE}"/>'
    )

    overflow = 0
    for column_index, column in enumerate(columns):
        x = board_x + column_index * step
        for row_index, verdict in enumerate(column[:MAX_STACK]):
            y = floor - (row_index + 1) * step + GUTTER
            color = tokens.VERDICT_COLORS[verdict]
            name = motion.shared(
                "drop",
                f"transform:translateY({fmt(-(top + 40))}px);opacity:0",
                "transform:translateY(0);opacity:1",
                0.1 + (column_index % 14) * 0.06 + row_index * 0.04,
                duration=0.9,
            )
            body.append(
                f'<rect class="{name}" x="{fmt(x)}" y="{fmt(y)}"'
                f' width="{cell}" height="{cell}" rx="2" fill="{color}"/>'
            )

        overflow += max(0, len(column) - MAX_STACK)

    if overflow:
        body.append(
            setter.text(
                pad + 4,
                top - 8,
                f"+{overflow} more stacked past the ceiling",
                face=tokens.MONO,
                size=9,
                fill=tokens.DIM,
            )
        )

    # Legend, using the positions measured above.
    for key, label, entry_x, row in legend_entries:
        row_y = legend_y + row * 18
        body.append(
            f'<rect x="{fmt(entry_x)}" y="{fmt(row_y - 9)}" width="10" height="10"'
            f' rx="2" fill="{tokens.VERDICT_COLORS[key]}"/>'
        )
        body.append(
            setter.text(
                entry_x + 16, row_y, label, face=tokens.MONO, size=10,
                fill=tokens.MUTED,
            )
        )

    for offset, line in enumerate(caption_lines):
        body.append(
            setter.text(
                pad + 4, caption_y + offset * 16, line,
                face=tokens.MONO, size=11, fill=tokens.TEXT, opacity=0.7,
            )
        )

    return svg.document(
        width,
        height,
        "".join(body),
        defs=setter.defs() + motion.style(),
        title="Codeforces submissions stacked as a Tetris board",
        description=(
            f"{stats['total']} submissions across {len(columns)} problems, "
            f"{stats['accepted']} accepted. One block per submission, "
            "ice for accepted and rose for rejected."
        ),
    )
