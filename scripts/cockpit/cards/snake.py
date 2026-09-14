"""The contribution snake, as a Nokia 3310.

Replaces a dependency on the Platane/snk action.  Two things that action cannot do are the
whole reason for writing our own: its snake never grows, and its body is thin and rounded
rather than the blocky segments a 3310 actually drew.

The route is planned, not approximated.  A Hamiltonian cycle over the playfield gives an
escape that is always available, and shortcuts are only taken when they provably preserve
it -- so the snake cannot trap itself, and every contribution day is eaten.  That matters
because this regenerates on a daily cron: a trapped snake is a broken panel discovered by
whoever visits next, not by us.
"""

from __future__ import annotations

from profilegen.snake import ai, grid
from profilegen.snake import render as snake_render

from .. import tokens


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    field = grid.build(data.get("contributions") or [])
    record = ai.plan(field)
    # The panel sizes itself from the cell, so the narrow variant is the same drawing at a
    # smaller pitch rather than a second layout to keep in step.
    return snake_render.render(
        record, field, cell=6 if narrow else 13, font=2 if narrow else 3
    )
