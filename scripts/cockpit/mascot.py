"""Bit, the arcade's resident robot, who walks the reader down the page.

Bit is a 13x16 pixel sprite drawn as crisp ``<path>`` runs, one path per colour, so a whole
robot costs about a dozen elements however large it is drawn. Every chapter uses the same
sprite at the same proportions; that is what makes seven separate images read as one story.

Poses are layers rather than whole sprites. The head and torso never change, so they are
drawn once, and only the parts that move (legs, arms, eyes) exist in more than one version,
each switched on and off by an opacity track. Motion across the scene is a separate transform
on a wrapping group, sampled on a coarse clock so it moves the way sprites did: in steps.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from profilegen.svg.anim import AnimationSet

from . import fx, tokens
from .typography import fmt

W = 13
H = 16

PALETTE = {
    "k": "#140A26",
    "b": tokens.VIOLET,
    "d": tokens.VIOLET_DEEP,
    "l": tokens.VIOLET_BRIGHT,
    "v": tokens.FOREST,
    "g": tokens.MOSS,
    "e": tokens.ACID,
    "a": tokens.ACID,
    "c": tokens.EMERALD,
}

# Head and torso: never animated, so drawn once.
TORSO = (
    "......a......",
    "......k......",
    "..kkkkkkkkk..",
    ".kllbbbbbbbk.",
    ".kbvvvvvvvbk.",
    ".kbvgvvvvvbk.",
    ".kbv..v..vbk.",
    ".kbv..v..vbk.",
    ".kbvvvvvvvbk.",
    ".kdbbbbbbbdk.",
    "..kkkkkkkkk..",
    "..kbbbcbbbk..",
    "..kdbbbbbdk..",
    "...kkkkkkk...",
    ".............",
    ".............",
)

EYES = (
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
    ".............",
    "....ee.ee....",
    "....ee.ee....",
)

# Moving parts, as sparse overlays on the same 13x16 grid.
PARTS: dict[str, tuple[str, ...]] = {
    "legs_idle": (
        "",) * 14 + (
        "...dd...dd...",
        "..bbb...bbb..",
    ),
    "legs_a": ("",) * 14 + (
        "..dd.....dd..",
        ".bbb.....bbb.",
    ),
    "legs_b": ("",) * 14 + (
        "....dd.dd....",
        "....bbbbb....",
    ),
    "legs_jump": ("",) * 14 + (
        "...ddd.ddd...",
        ".............",
    ),
    "left_down": ("",) * 11 + (
        ".d...........",
        ".d...........",
        ".l...........",
    ),
    "right_down": ("",) * 11 + (
        "...........d.",
        "...........d.",
        "...........l.",
    ),
    "right_wave_a": ("",) * 6 + (
        "............l",
        "............d",
        "............d",
        "............d",
        "...........d.",
    ),
    "right_wave_b": ("",) * 7 + (
        "............l",
        "...........ld",
        "...........d.",
        "...........d.",
    ),
    "left_up": ("",) * 7 + (
        "l............",
        "d............",
        "d............",
        ".d...........",
    ),
    "right_up": ("",) * 7 + (
        "............l",
        "............d",
        "............d",
        "...........d.",
    ),
    "right_point": ("",) * 11 + (
        "...........dl",
    ),
}


def _paths(rows: Sequence[str], x: float, y: float, px: float) -> str:
    """One ``<path>`` per colour, each a run of row-merged blocks."""
    by_color: dict[str, list[str]] = {}
    for row_index, row in enumerate(rows):
        col = 0
        while col < len(row):
            key = row[col]
            if key == ".":
                col += 1
                continue
            end = col
            while end < len(row) and row[end] == key:
                end += 1
            by_color.setdefault(PALETTE[key], []).append(
                f"M{fmt(x + col * px)} {fmt(y + row_index * px)}"
                f"h{fmt((end - col) * px)}v{fmt(px)}h{fmt(-(end - col) * px)}z"
            )
            col = end
    return "".join(
        f'<path fill="{color}" d="{"".join(runs)}"/>' for color, runs in by_color.items()
    )


def sprite(px: float, *, legs: str = "legs_idle", arms: Sequence[str] = ("left_down", "right_down")) -> str:
    """A still Bit at the origin, for places that do not animate him."""
    return (
        _paths(TORSO, 0, 0, px)
        + _paths(EYES, 0, 0, px)
        + _paths(PARTS[legs], 0, 0, px)
        + "".join(_paths(PARTS[arm], 0, 0, px) for arm in arms)
    )


def _alternate(spans: Iterable[tuple[float, float]], period: float) -> list[tuple[float, float, int]]:
    """Split each span into ``period``-long beats, numbered 0, 1, 0, 1..."""
    beats: list[tuple[float, float, int]] = []
    for start, end in spans:
        t = start
        phase = 0
        while t < end - 1e-6:
            beats.append((t, min(end, t + period), phase))
            phase ^= 1
            t += period
    return beats


def bit(
    anim: AnimationSet,
    duration: float,
    x: float,
    y: float,
    px: float,
    *,
    walk: tuple[float, float, float] | None = None,
    walk_out: tuple[float, float, float] | None = None,
    wave: Sequence[tuple[float, float]] = (),
    cheer: Sequence[tuple[float, float]] = (),
    point: Sequence[tuple[float, float]] = (),
    jumps: Sequence[float] = (),
    blinks: Sequence[float] = (),
    bob: float | None = 0.6,
    glow: bool = True,
    flip: bool = False,
) -> str:
    """Bit resting at ``(x, y)`` (top-left of the sprite), with optional choreography.

    ``walk`` is ``(dx, start, end)``: he walks in from ``dx`` pixels away and arrives at his
    resting spot at ``end``. ``walk_out`` is ``(dx, start, end)`` the other way, leaving. The
    resting position is the static frame, so a reader with reduced motion sees him standing
    where the scene expects him.
    """
    moving_spans: list[tuple[float, float]] = []
    if walk:
        moving_spans.append((walk[1], walk[2]))
    if walk_out:
        moving_spans.append((walk_out[1], walk_out[2]))
    jump_spans = [(t, t + 0.5) for t in jumps]

    def busy(t: float) -> bool:
        return any(a <= t < b for a, b in moving_spans + jump_spans)

    # --- position: walk, jumps and an idle bob, sampled in steps -------------------------
    tick = 0.05
    points: list[tuple[float, dict]] = []
    samples = int(duration / tick) + 1
    last = None
    for index in range(samples + 1):
        t = min(duration, index * tick)
        dx = 0.0
        dy = 0.0
        if walk and t < walk[2]:
            start, end = walk[1], walk[2]
            share = 0.0 if t <= start else (t - start) / (end - start)
            dx = walk[0] * (1 - min(1.0, share))
        if walk_out and t >= walk_out[1]:
            start, end = walk_out[1], walk_out[2]
            share = min(1.0, (t - start) / (end - start))
            dx = walk_out[0] * share
        for jump in jumps:
            if jump <= t < jump + 0.5:
                phase = (t - jump) / 0.5
                dy = -math.sin(phase * math.pi) * px * 6
        if bob and not busy(t) and not (walk and t < walk[1]):
            if int(t / bob) % 2:
                dy -= px
        # Snap to the sprite's own pixel so motion reads as stepped, not smeared.
        dx = round(dx / px) * px
        dy = round(dy / px) * px
        state = f"translate({fmt(dx)}px,{fmt(dy)}px)"
        if state != last:
            points.append((t, {"transform": state}))
            last = state
    move_cls = fx.track(anim, fx.steps(points, duration)) if len(points) > 1 else None

    # --- legs ---------------------------------------------------------------------------
    stride = _alternate(moving_spans, 0.14)
    legs_idle: list[tuple[float, float]] = []
    legs_a: list[tuple[float, float]] = []
    legs_b: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end, phase in stride:
        if start > cursor:
            legs_idle.append((cursor, start))
        (legs_a if phase == 0 else legs_b).append((start, end))
        cursor = end
    legs_idle.append((cursor, duration))
    legs_jump = jump_spans

    def layer(name: str, spans: list[tuple[float, float]], *, default: bool = False) -> str:
        markup = _paths(PARTS[name], 0, 0, px)
        if not spans:
            return markup if default else ""
        if default and spans == [(0.0, duration)]:
            return markup
        frames = fx.windows(spans, duration)
        cls = fx.track(anim, frames, base=None if default else {"opacity": "0"})
        return fx.wrap(cls, markup) if cls else (markup if default else "")

    # Idle legs are hidden during jumps; jump legs cover those spans.
    idle_spans = _subtract(legs_idle, legs_jump)
    legs = (
        layer("legs_idle", idle_spans, default=True)
        + layer("legs_a", legs_a)
        + layer("legs_b", legs_b)
        + layer("legs_jump", legs_jump)
    )

    # --- arms ---------------------------------------------------------------------------
    wave_beats = _alternate(wave, 0.22)
    wave_a = [(a, b) for a, b, p in wave_beats if p == 0]
    wave_b = [(a, b) for a, b, p in wave_beats if p == 1]
    right_busy = list(wave) + list(cheer) + list(point)
    left_busy = list(cheer)
    arms = (
        layer("left_down", _subtract([(0.0, duration)], left_busy), default=True)
        + layer("right_down", _subtract([(0.0, duration)], right_busy), default=True)
        + layer("right_wave_a", wave_a)
        + layer("right_wave_b", wave_b)
        + layer("left_up", list(cheer))
        + layer("right_up", list(cheer))
        + layer("right_point", list(point))
    )

    # --- eyes ---------------------------------------------------------------------------
    eyes = _paths(EYES, 0, 0, px)
    if blinks:
        spans = _subtract([(0.0, duration)], [(t, t + 0.14) for t in blinks])
        cls = fx.track(anim, fx.windows(spans, duration))
        eyes = fx.wrap(cls, eyes)

    halo = ""
    if glow:
        # The antenna bulb breathes, so a Bit standing still is still visibly on.
        cls = fx.track(
            anim,
            fx.steps(
                [(0.0, {"opacity": "0.15"}), (duration / 4, {"opacity": "0.55"}),
                 (duration / 2, {"opacity": "0.15"}), (duration * 3 / 4, {"opacity": "0.55"})],
                duration,
            ),
            easing="ease-in-out",
        )
        halo = (
            f'<circle class="{cls}" cx="{fmt(6.5 * px)}" cy="{fmt(0.5 * px)}" r="{fmt(px * 2.2)}"'
            f' fill="{tokens.ACID}" opacity="0.35"/>'
        )

    body = halo + _paths(TORSO, 0, 0, px) + eyes + legs + arms
    if flip:
        body = f'<g transform="translate({fmt(W * px)} 0) scale(-1 1)">{body}</g>'
    return fx.place(x, y, move_cls, body)


def _subtract(spans: list[tuple[float, float]], holes: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """``spans`` with every ``hole`` cut out of it."""
    result = list(spans)
    for hole_start, hole_end in holes:
        cut: list[tuple[float, float]] = []
        for start, end in result:
            if hole_end <= start or hole_start >= end:
                cut.append((start, end))
                continue
            if start < hole_start:
                cut.append((start, hole_start))
            if hole_end < end:
                cut.append((hole_end, end))
        result = cut
    return [(a, b) for a, b in result if b - a > 1e-6]


def width(px: float) -> float:
    return W * px


def height(px: float) -> float:
    return H * px
