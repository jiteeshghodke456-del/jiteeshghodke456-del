"""Turn a GitHub contribution calendar into a snake playfield.

Two decisions are forced by real data rather than taste:

* The calendar is 53 weeks wide, and 53 x 7 = 371 is odd, so it admits no Hamiltonian cycle
  (see ``hamilton``).  The field is cropped to the most recent **52** weeks, which is both
  even and the more natural "last year" framing.
* This account has 30 active days out of 365.  The board is therefore mostly empty, and the
  renderer has to make that look deliberate -- dimmed rather than absent -- and make each
  of the 30 meals visibly worth something.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

COLS = 52
ROWS = 7


@dataclass(frozen=True)
class Playfield:
    cols: int
    rows: int
    levels: tuple[tuple[int, ...], ...]   # levels[col][row], 0-4
    counts: tuple[tuple[int, ...], ...]   # raw contribution counts
    targets: tuple[tuple[int, int], ...]  # (col, row) of every cell worth eating
    total: int
    first_date: str
    last_date: str

    def level_at(self, col: int, row: int) -> int:
        return self.levels[col][row]


_LEVEL_NAMES = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


def _level(day: dict) -> int:
    """Normalise a level, which arrives as an enum from GraphQL and an int from the scrape."""
    raw = day.get("level")
    if isinstance(raw, int):
        return max(0, min(4, raw))
    if isinstance(raw, str):
        return _LEVEL_NAMES.get(raw.upper(), 1 if day.get("count") else 0)
    return 1 if day.get("count") else 0


def build(
    days: list[dict],
    *,
    cols: int = COLS,
    rows: int = ROWS,
    today: dt.date | None = None,
) -> Playfield:
    """Lay days out as GitHub does -- a column per week, a row per weekday.

    Columns are keyed off each date's own weekday rather than the input order, so a partial
    or reordered response still lands on the right day.  Only the most recent ``cols`` weeks
    survive the crop.

    The window is anchored on ``today``, never on the newest date present in the input.  The
    tokenless contribution endpoint returns the whole calendar year, so anchoring on the data
    would place the board's right-hand edge in December and leave a quarter of it empty.
    """
    parsed: list[tuple[dt.date, int, int]] = []
    for day in days:
        try:
            date = dt.date.fromisoformat(str(day["date"]))
        except (KeyError, TypeError, ValueError):
            continue
        parsed.append((date, int(day.get("count") or 0), _level(day)))

    if not parsed:
        empty = tuple(tuple(0 for _ in range(rows)) for _ in range(cols))
        return Playfield(cols, rows, empty, empty, (), 0, "", "")

    parsed.sort(key=lambda item: item[0])
    anchor = today or dt.date.today()
    parsed = [item for item in parsed if item[0] <= anchor]
    if not parsed:
        empty = tuple(tuple(0 for _ in range(rows)) for _ in range(cols))
        return Playfield(cols, rows, empty, empty, (), 0, "", "")
    last = anchor

    # GitHub's calendar starts each column on Sunday; weekday() is Mon=0, so shift by one.
    def week_row(date: dt.date) -> int:
        return (date.weekday() + 1) % 7

    last_column_start = last - dt.timedelta(days=week_row(last))
    first_column_start = last_column_start - dt.timedelta(weeks=cols - 1)

    levels = [[0] * rows for _ in range(cols)]
    counts = [[0] * rows for _ in range(cols)]
    total = 0
    for date, count, level in parsed:
        column_start = date - dt.timedelta(days=week_row(date))
        col = (column_start - first_column_start).days // 7
        if not 0 <= col < cols:
            continue
        row = week_row(date)
        counts[col][row] = count
        levels[col][row] = level
        total += count

    targets = tuple(
        (col, row)
        for col in range(cols)
        for row in range(rows)
        if counts[col][row] > 0
    )
    return Playfield(
        cols=cols,
        rows=rows,
        levels=tuple(tuple(column) for column in levels),
        counts=tuple(tuple(column) for column in counts),
        targets=targets,
        total=total,
        first_date=first_column_start.isoformat(),
        last_date=last.isoformat(),
    )
