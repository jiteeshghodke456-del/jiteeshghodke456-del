"""The planner's output: everything the renderer needs, and nothing it must recompute."""

from __future__ import annotations

from dataclasses import dataclass

Cell = tuple[int, int]


@dataclass(frozen=True)
class Meal:
    col: int
    row: int
    level: int
    step: int   # the step at which the head arrives on this cell


@dataclass(frozen=True)
class SnakeRecord:
    """A recorded run.

    ``track`` holds the head's cell at every step, *prefixed* with the snake's initial body
    laid out tail-first.  That prefix is why ``start_offset`` exists, and it exists in the
    record rather than in the renderer on purpose: the central invariant is

        segment ``i`` at step ``s`` occupies ``track[start_offset + s - i]``

    which is what lets all N segments share a single ``@keyframes`` block and differ only by
    ``animation-delay = -i * step_dt``.  Getting that index off by one renders subtly wrong
    and passes every test that does not look at pixels, so it belongs to the data structure.
    """

    cols: int
    rows: int
    step_dt: float
    steps: int
    duration: float
    reset_at: float
    track: tuple[Cell, ...]
    start_offset: int
    start_length: int
    meals: tuple[Meal, ...]
    growth: tuple[tuple[int, int], ...]   # (step, length after eating)
    max_length: int

    def head_at(self, step: int) -> Cell:
        return self.track[self.start_offset + step]

    def segment_at(self, step: int, index: int) -> Cell:
        return self.track[self.start_offset + step - index]

    def length_at(self, step: int) -> int:
        length = self.start_length
        for at, new_length in self.growth:
            if at <= step:
                length = new_length
            else:
                break
        return length
