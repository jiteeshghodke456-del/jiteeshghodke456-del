"""Hamiltonian cycle construction on a grid, and the parity rules that govern it.

This is the safety net the route planner is built on.  Following a Hamiltonian cycle with a
body shorter than the grid can never trap the snake, which is what turns "does not deadlock"
from a hopeful heuristic into a guarantee.  That matters because this runs on a daily cron:
a snake that traps itself is a silently broken README, discovered by whoever visits next.

The parity constraint is not a detail to paper over.  A grid graph is bipartite, so any
Hamiltonian *cycle* must alternate colours and therefore needs an even number of cells.  The
GitHub contribution calendar is 53 weeks wide -- 53 x 7 = 371, odd, and provably has no
cycle.  Hence the playfield is cropped to 52 columns.  Passing an odd-area grid here raises
rather than falling back to something subtly wrong.
"""

from __future__ import annotations

Cell = tuple[int, int]  # (col, row)


def hamiltonian_cycle(width: int, height: int) -> list[Cell]:
    """Return a Hamiltonian cycle over every cell of a ``width`` x ``height`` grid.

    The returned list visits each cell exactly once; consecutive cells are 4-adjacent, and
    the last cell is adjacent to the first, so it closes.

    Construction, for even ``width``: run left-to-right along row 0, then boustrophedon down
    and up the columns from ``width - 1`` back to 1 over rows 1..height-1, then climb column
    0 from the bottom to row 1 -- which lands adjacent to (0, 0) and closes the loop.

    The final climb only works if the boustrophedon leaves us at the *bottom* of column 1.
    Counting columns from the right, column ``width - 1`` is traversed downward, the next
    upward, and so on; a column ends at the bottom exactly when its distance from the right
    is even.  Column 1 sits at distance ``width - 2``, which is even precisely when
    ``width`` is even.  That is the whole reason for the even-width requirement, rather than
    an arbitrary restriction.

    For odd width but even height the transpose satisfies the same condition, so the grid is
    solved rotated and the coordinates swapped back.
    """
    if width < 2 or height < 2:
        raise ValueError(f"grid too small for a cycle: {width}x{height}")
    if (width * height) % 2:
        raise ValueError(
            f"{width}x{height} has {width * height} cells, which is odd; a grid graph is "
            "bipartite so no Hamiltonian cycle exists.  Crop to an even number of cells."
        )

    if width % 2:
        # Odd width with even area implies even height: solve the transpose and swap back.
        return [(col, row) for row, col in hamiltonian_cycle(height, width)]

    cycle: list[Cell] = [(col, 0) for col in range(width)]
    for distance_from_right, col in enumerate(range(width - 1, 0, -1)):
        rows = range(1, height) if distance_from_right % 2 == 0 else range(height - 1, 0, -1)
        cycle.extend((col, row) for row in rows)
    cycle.extend((0, row) for row in range(height - 1, 0, -1))
    return cycle


def cycle_order(cycle: list[Cell]) -> dict[Cell, int]:
    """Map each cell to its index along the cycle."""
    return {cell: index for index, cell in enumerate(cycle)}


def adjacent(a: Cell, b: Cell) -> bool:
    """True when two cells share an edge."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
