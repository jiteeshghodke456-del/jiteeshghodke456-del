"""Reusable motion for the arcade chapters.

Every effect here speaks absolute seconds on the card's one shared :class:`Timeline`, returns
markup, and registers its tracks on the card's :class:`AnimationSet`. Nothing here invents a
clock of its own, because two clocks in one file drift apart after the first loop.

Two rules every effect keeps:

* **The static frame is the finished frame.** Overlays that exist only for a transition (the
  CRT black, the iris, the dissolve cover) carry ``opacity="0"`` as an attribute, so a reader
  with reduced motion, or a renderer with no animation support, sees the scene rather than a
  black card.
* **Every track ends where it began.** A track that finishes somewhere other than its 0% value
  visibly snaps at the loop point; the helpers below always close the loop explicitly.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence

from profilegen.svg.anim import AnimationSet, Keyframe

from . import tokens
from .typography import TypeSetter, fmt

HOLD = 0.01

EASE_OUT = "cubic-bezier(0.16,0.9,0.2,1)"
EASE_IN_OUT = "cubic-bezier(0.65,0,0.35,1)"


class Ids:
    """Mints unique ``id`` values for defs a card declares (clips, gradients, patterns)."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._count = 0

    def next(self) -> str:
        ident = f"{self._prefix}{self._count:x}"
        self._count += 1
        return ident


def track(
    anim: AnimationSet,
    frames: Sequence[Keyframe],
    *,
    easing: str = "step-end",
    base: dict | None = None,
    delay: float = 0.0,
) -> str | None:
    """``anim.add`` that returns ``None`` for a track that would never change.

    Real data produces degenerate tracks -- a counter whose value is zero, a board with no
    blocks -- and the emitter rightly refuses to emit a no-op. The caller then draws the element
    statically instead of failing the build.
    """
    try:
        return anim.add(frames, easing=easing, base=base, delay=delay)
    except ValueError as exc:
        if "never changes" in str(exc):
            return None
        raise


def cls_attr(cls: str | None) -> str:
    return f' class="{cls}"' if cls else ""


def wrap(cls: str | None, children: str, *, hidden: bool = False) -> str:
    """A ``<g>`` carrying an animation class, or the bare children when there is none.

    ``hidden`` puts ``opacity="0"`` on the animated group itself: the animation overrides it
    while running, and the static frame drops the element. It has to sit on the classed
    element; on a child it would hide the element even while the parent animates.
    """
    if not cls:
        return children
    rest = ' opacity="0"' if hidden else ""
    return f'<g class="{cls}"{rest}>{children}</g>'


def place(x: float, y: float, cls: str | None, children: str, *, hidden: bool = False) -> str:
    """Absolute placement outside, relative animation inside.

    A CSS transform replaces the ``transform`` attribute rather than composing with it, so the
    two can never share an element.
    """
    inner = wrap(cls, children, hidden=hidden) if cls else children
    if not x and not y:
        return f"<g>{inner}</g>"
    return f'<g transform="translate({fmt(x)} {fmt(y)})">{inner}</g>'


def steps(points: Iterable[tuple[float, dict]], duration: float) -> list[Keyframe]:
    """Keyframes from ``(t, props)`` pairs, with a 0% stop and a closing 100% stop.

    The first state is repeated at ``duration`` so the loop closes on the value it opened
    with, which is what stops a step track from snapping at the seam.
    """
    ordered = sorted(points, key=lambda point: point[0])
    if not ordered:
        raise ValueError("steps() needs at least one point")
    frames = [Keyframe(max(0.0, min(duration, t)), props) for t, props in ordered]
    if frames[0].t > 0:
        frames.insert(0, Keyframe(0.0, frames[-1].props))
    if frames[-1].t < duration:
        frames.append(Keyframe(duration, frames[0].props))
    return frames


def merge(*tracks: Sequence[Keyframe]) -> list[Keyframe]:
    """Combine step tracks over different properties into one, with full state at every stop.

    One element can carry only one animation class, so a letter that both drops and flickers
    needs its transform and opacity histories in a single track. Under step easing each
    property simply holds its last value, which is what is replayed at every merged stop.
    """
    times = sorted({frame.t for frames in tracks for frame in frames})
    merged: list[Keyframe] = []
    for t in times:
        state: dict[str, str] = {}
        for frames in tracks:
            current = None
            for frame in frames:
                if frame.t <= t + 1e-9:
                    current = frame.props
                else:
                    break
            if current is None:
                current = frames[0].props
            state.update(current)
        merged.append(Keyframe(t, state))
    return merged


def windows(
    spans: Iterable[tuple[float, float]], duration: float, *, on: str = "1", off: str = "0"
) -> list[Keyframe]:
    """Opacity on inside each ``(start, end)`` span and off everywhere else, as step frames."""
    points: list[tuple[float, dict]] = [(0.0, {"opacity": off})]
    for start, end in spans:
        points.append((max(0.0, start), {"opacity": on}))
        points.append((min(duration, end), {"opacity": off}))
    return steps(points, duration)


def blink_frames(
    start: float, end: float, period: float, duration: float, *, low: str = "0.1"
) -> list[Keyframe]:
    """Hard on/off blink between ``start`` and ``end``, fully on outside it."""
    points: list[tuple[float, dict]] = [(0.0, {"opacity": "1"})]
    t = start
    lit = False
    while t < end:
        points.append((t, {"opacity": "1" if lit else low}))
        lit = not lit
        t += period / 2
    points.append((end, {"opacity": "1"}))
    return steps(points, duration)


# --------------------------------------------------------------------------- CRT


def crt(
    anim: AnimationSet,
    width: float,
    height: float,
    duration: float,
    *,
    on: tuple[float, float] | None = (0.0, 0.75),
    off: tuple[float, float] | None = None,
) -> str:
    """Tube power-on at ``on`` and power-off at ``off``, as an overlay above the scene.

    Power-on: a bright line snaps across the middle, then tears open vertically while the
    black cover fades. Power-off is the same thing played backwards. The overlay is invisible
    at rest, so the static frame is the lit screen.
    """
    cover: list[tuple[float, dict]] = []
    beam: list[tuple[float, dict]] = []
    tall = max(1.0, height / 3)
    if on:
        start, end = on
        span = end - start
        cover += [
            (start, {"opacity": "1"}),
            (start + span * 0.45, {"opacity": "1"}),
            (end, {"opacity": "0"}),
        ]
        beam += [
            (start, {"transform": "scale(0.001,1)", "opacity": "1"}),
            (start + span * 0.3, {"transform": "scale(1,1)", "opacity": "1"}),
            (start + span * 0.45, {"transform": "scale(1,1)", "opacity": "1"}),
            (end, {"transform": f"scale(1,{fmt(tall)})", "opacity": "0"}),
        ]
    if off:
        start, end = off
        span = end - start
        cover += [
            (start, {"opacity": "0"}),
            (start + span * 0.55, {"opacity": "1"}),
            (end, {"opacity": "1"}),
        ]
        beam += [
            (start, {"transform": f"scale(1,{fmt(tall)})", "opacity": "0"}),
            (start + span * 0.55, {"transform": "scale(1,1)", "opacity": "1"}),
            (start + span * 0.85, {"transform": "scale(0.001,1)", "opacity": "1"}),
            (end, {"transform": "scale(0.001,1)", "opacity": "1" if on else "0"}),
        ]
    if not cover:
        return ""
    if not off:
        cover.append((duration, {"opacity": "0"}))
        beam.append((duration, {"transform": f"scale(1,{fmt(tall)})", "opacity": "0"}))
    if not on:
        cover.insert(0, (0.0, {"opacity": "0"}))
        beam.insert(0, (0.0, {"transform": f"scale(1,{fmt(tall)})", "opacity": "0"}))

    cover_cls = track(anim, steps(cover, duration), easing="linear")
    beam_cls = track(anim, steps(beam, duration), easing="linear")
    return (
        f'<rect class="{cover_cls}" width="{fmt(width)}" height="{fmt(height)}"'
        f' fill="#000" opacity="0"/>'
        + place(
            width / 2,
            height / 2,
            beam_cls,
            f'<rect x="{fmt(-width / 2)}" y="-1.5" width="{fmt(width)}" height="3"'
            f' fill="{tokens.ACID_BRIGHT}"/>'
            f'<rect x="{fmt(-width / 2)}" y="-0.5" width="{fmt(width)}" height="1"'
            f' fill="#FFFFFF"/>',
            hidden=True,
        )
    )


# --------------------------------------------------------------------------- glitch


def glitch_times(bursts: Iterable[float], rng: random.Random, *, span: float = 0.42,
                 step: float = 0.045) -> list[float]:
    times: list[float] = []
    for start in bursts:
        t = start
        while t < start + span:
            times.append(round(t, 3))
            t += step * (0.6 + rng.random() * 0.8)
    return times


def jitter(
    anim: AnimationSet,
    bursts: Iterable[float],
    duration: float,
    *,
    amp: float = 4.0,
    seed: int = 7,
    vertical: bool = False,
) -> str | None:
    """A class that shakes its element sideways during each burst and rests at 0 otherwise."""
    rng = random.Random(seed)
    bursts = list(bursts)
    points: list[tuple[float, dict]] = [(0.0, {"transform": "translate(0px,0px)"})]
    for start in bursts:
        for t in glitch_times([start], rng):
            dx = (rng.random() * 2 - 1) * amp
            dy = (rng.random() * 2 - 1) * amp * 0.5 if vertical else 0.0
            points.append((t, {"transform": f"translate({fmt(dx)}px,{fmt(dy)}px)"}))
        points.append((start + 0.45, {"transform": "translate(0px,0px)"}))
    return track(anim, steps(points, duration))


def glitch_bands(
    anim: AnimationSet,
    x: float,
    y: float,
    width: float,
    height: float,
    bursts: Iterable[float],
    duration: float,
    *,
    count: int = 6,
    seed: int = 11,
) -> str:
    """Torn scanline bands in the two neons, flashing only during the bursts."""
    rng = random.Random(seed)
    bursts = list(bursts)
    parts: list[str] = []
    for index in range(count):
        band_y = y + rng.random() * height
        band_h = 2 + rng.random() * 12
        color = (tokens.VIOLET, tokens.ACID, tokens.HOT_VIOLET, tokens.EMERALD)[index % 4]
        points: list[tuple[float, dict]] = [
            (0.0, {"opacity": "0", "transform": "translate(0px,0px)"})
        ]
        for t in glitch_times(bursts, rng):
            if rng.random() < 0.55:
                points.append(
                    (t, {"opacity": fmt(0.25 + rng.random() * 0.5),
                         "transform": f"translate({fmt((rng.random() * 2 - 1) * width * 0.25)}px,0px)"})
                )
            else:
                points.append((t, {"opacity": "0", "transform": "translate(0px,0px)"}))
        for start in bursts:
            points.append((start + 0.46, {"opacity": "0", "transform": "translate(0px,0px)"}))
        cls = track(anim, steps(points, duration))
        if cls is None:
            continue
        parts.append(
            f'<rect class="{cls}" x="{fmt(x)}" y="{fmt(band_y)}" width="{fmt(width)}"'
            f' height="{fmt(band_h)}" fill="{color}" opacity="0"/>'
        )
    return "".join(parts)


def flicker_frames(bursts: Iterable[float], duration: float) -> list[Keyframe]:
    """A failing neon tube: a stutter of drop-outs, then back to full."""
    pattern = ((0.0, "0.15"), (0.06, "1"), (0.11, "0.1"), (0.2, "0.85"), (0.24, "0.05"),
               (0.36, "1"), (0.41, "0.3"), (0.47, "1"))
    points: list[tuple[float, dict]] = [(0.0, {"opacity": "1"})]
    for start in bursts:
        for offset, value in pattern:
            points.append((start + offset, {"opacity": value}))
    return steps(points, duration)


# --------------------------------------------------------------------------- type


def typewriter(
    anim: AnimationSet,
    setter: TypeSetter,
    x: float,
    y: float,
    lines: Sequence[str],
    *,
    face: str,
    size: float,
    fill: str,
    start: float,
    end: float,
    duration: float,
    cps: float = 28.0,
    leading: float = 1.45,
    tracking: int = 0,
    static: bool = True,
    cursor: str | None = tokens.ACID,
) -> str:
    """Type ``lines`` one character at a time from ``start``, then backspace out by ``end``.

    Each glyph gets its own appear/vanish track; the vanish runs from the last character to
    the first, so it reads as a backspace rather than a wipe. ``static`` decides whether the
    finished text is part of the reduced-motion frame: when several captions share one bubble
    only the first may be, or they would all print on top of each other.
    """
    base = None if static else {"opacity": "0"}
    total = sum(len(line) for line in lines)
    type_dt = 1.0 / cps
    erase_dt = min(type_dt / 2.5, max(0.004, (duration - end) / max(1, total) * 0.9))
    parts: list[str] = []
    cursor_points: list[tuple[float, dict]] = []
    order = 0
    for line_index, line in enumerate(lines):
        line_y = y + line_index * size * leading
        times: dict[int, str | None] = {}
        for index, char in enumerate(line):
            appear = start + order * type_dt
            vanish = end + (total - 1 - order) * erase_dt
            order += 1
            if not char.strip():
                continue
            times[index] = track(
                anim,
                steps(
                    [(0.0, {"opacity": "0"}), (appear, {"opacity": "1"}),
                     (vanish, {"opacity": "0"})],
                    duration,
                ),
                base=base,
            )
            if cursor:
                head = x + setter.width(line[: index + 1], face, size, tracking) + size * 0.12
                cursor_points.append(
                    (appear, {"transform": f"translate({fmt(head)}px,{fmt(line_y)}px)",
                              "opacity": "1"})
                )
        parts.append(
            setter.text(
                x, line_y, line, face=face, size=size, fill=fill, tracking=tracking,
                cls_for=lambda index, _char, times=times: times.get(index),
            )
        )
    if cursor and cursor_points:
        last = cursor_points[-1][1]["transform"]
        blink_at = cursor_points[-1][0] + 0.2
        t = blink_at
        lit = False
        while t < end - 0.05:
            cursor_points.append((t, {"transform": last, "opacity": "1" if lit else "0"}))
            lit = not lit
            t += 0.3
        cursor_points.append((end, {"transform": last, "opacity": "1"}))
        cursor_points.append(
            (end + total * erase_dt + 0.05, {"transform": last, "opacity": "0"})
        )
        cursor_points.insert(0, (0.0, {"transform": cursor_points[0][1]["transform"],
                                       "opacity": "0"}))
        cls = track(anim, steps(cursor_points, duration), base={"opacity": "0"})
        if cls:
            parts.append(
                f'<g class="{cls}"><rect x="0" y="{fmt(-size * 0.8)}" width="{fmt(size * 0.55)}"'
                f' height="{fmt(size * 0.9)}" fill="{cursor}"/></g>'
            )
    return "".join(parts)


def drum(
    anim: AnimationSet,
    setter: TypeSetter,
    ids: Ids,
    x: float,
    baseline: float,
    value: str,
    *,
    face: str,
    size: float,
    fill: str,
    start: float,
    stop: float,
    duration: float,
    spins: int = 2,
    tracking: int = 0,
    rewind: float = 0.5,
) -> tuple[str, str]:
    """A slot-machine readout: each digit is a clipped reel that spins and lands on ``value``.

    One track per reel, however long the spin. Reels stop left to right, which is the order a
    reader's eye checks them. The resting transform is the landed value, so the static frame
    reads correctly; at the end of the loop the reels rewind for the next spin.

    Returns ``(markup, defs)``.
    """
    cell = size * 1.25
    advance = setter.width("0", face, size, tracking) + size * tracking / 1000
    clip = ids.next()
    top = baseline - size * 1.02
    defs = (
        f'<clipPath id="{clip}"><rect x="{fmt(x - 1)}" y="{fmt(top)}"'
        f' width="{fmt(advance * len(value) + 2)}" height="{fmt(cell)}"/></clipPath>'
    )
    parts: list[str] = []
    digits = [char for char in value]
    for index, char in enumerate(digits):
        reel_x = x + index * advance
        if not char.isdigit():
            parts.append(setter.text(reel_x, baseline, char, face=face, size=size, fill=fill))
            continue
        final = int(char)
        sequence = [str(d) for d in range(10)] * spins + [str(d) for d in range(final + 1)]
        depth = (len(sequence) - 1) * cell
        land = start + (stop - start) * (index + 1) / len(digits)
        cls = track(
            anim,
            steps(
                [
                    (0.0, {"transform": f"translate(0px,{fmt(depth)}px)"}),
                    (start, {"transform": f"translate(0px,{fmt(depth)}px)"}),
                    (land, {"transform": "translate(0px,0px)"}),
                    (duration - rewind, {"transform": "translate(0px,0px)"}),
                ],
                duration,
            ),
            easing=EASE_OUT,
        )
        reel = "".join(
            setter.text(
                reel_x, baseline - (len(sequence) - 1 - k) * cell, digit,
                face=face, size=size, fill=fill,
            )
            for k, digit in enumerate(sequence)
        )
        parts.append(wrap(cls, reel))
    return f'<g clip-path="url(#{clip})">{"".join(parts)}</g>', defs


# --------------------------------------------------------------------------- particles


def burst(
    anim: AnimationSet,
    cx: float,
    cy: float,
    at: Iterable[float],
    duration: float,
    *,
    count: int = 14,
    radius: float = 60.0,
    size: float = 4.0,
    colors: Sequence[str] = (tokens.ACID, tokens.VIOLET, tokens.ACID_BRIGHT, tokens.HOT_VIOLET),
    life: float = 0.7,
    seed: int = 3,
) -> str:
    """Square sparks thrown outward from ``(cx, cy)`` at each time in ``at``."""
    rng = random.Random(seed)
    at = sorted(at)
    if not at:
        return ""
    parts: list[str] = []
    for index in range(count):
        angle = (index / count) * math.tau + rng.random() * 0.4
        reach = radius * (0.55 + rng.random() * 0.6)
        dx, dy = math.cos(angle) * reach, math.sin(angle) * reach
        points: list[tuple[float, dict]] = [
            (0.0, {"transform": "translate(0px,0px) scale(1)", "opacity": "0"})
        ]
        for t in at:
            points += [
                (t - HOLD, {"transform": "translate(0px,0px) scale(1)", "opacity": "0"}),
                (t, {"transform": "translate(0px,0px) scale(1)", "opacity": "1"}),
                (t + life, {"transform": f"translate({fmt(dx)}px,{fmt(dy)}px) scale(0.2)",
                            "opacity": "0"}),
                (t + life + HOLD, {"transform": "translate(0px,0px) scale(1)", "opacity": "0"}),
            ]
        cls = track(anim, steps(points, duration), easing="cubic-bezier(0.1,0.8,0.3,1)",
                    base={"opacity": "0"})
        s = size * (0.7 + rng.random() * 0.8)
        parts.append(
            place(cx, cy, cls,
                  f'<rect x="{fmt(-s / 2)}" y="{fmt(-s / 2)}" width="{fmt(s)}"'
                  f' height="{fmt(s)}" fill="{colors[index % len(colors)]}"/>')
        )
    return "".join(parts)


# --------------------------------------------------------------------------- wipes


def dissolve(
    anim: AnimationSet,
    x: float,
    y: float,
    width: float,
    height: float,
    duration: float,
    *,
    reveal: tuple[float, float] | None = (0.0, 0.8),
    cover: tuple[float, float] | None = None,
    cell: float = 20.0,
    groups: int = 8,
    color: str = tokens.VOID,
    seed: int = 5,
) -> str:
    """A pixel dissolve: the scene appears (and later vanishes) one random block at a time.

    Blocks are pooled into ``groups`` paths, one track each, so a full-card dissolve costs a
    handful of rules rather than one per block.
    """
    rng = random.Random(seed)
    cols = max(1, math.ceil(width / cell))
    rows = max(1, math.ceil(height / cell))
    pools: list[list[str]] = [[] for _ in range(groups)]
    for col in range(cols):
        for row in range(rows):
            pools[rng.randrange(groups)].append(
                f"M{fmt(x + col * cell)} {fmt(y + row * cell)}h{fmt(cell)}v{fmt(cell)}"
                f"h{fmt(-cell)}z"
            )
    order = list(range(groups))
    rng.shuffle(order)
    parts: list[str] = []
    for rank, group in enumerate(order):
        if not pools[group]:
            continue
        points: list[tuple[float, dict]] = []
        if reveal:
            start, end = reveal
            points += [(0.0, {"opacity": "1"}),
                       (start + (end - start) * rank / groups, {"opacity": "0"})]
        else:
            points.append((0.0, {"opacity": "0"}))
        if cover:
            start, end = cover
            points.append((start + (end - start) * rank / groups, {"opacity": "1"}))
        cls = track(anim, steps(points, duration))
        if cls is None:
            continue
        parts.append(
            f'<path class="{cls}" fill="{color}" opacity="0" d="{"".join(pools[group])}"/>'
        )
    return "".join(parts)


def iris(
    anim: AnimationSet,
    cx: float,
    cy: float,
    width: float,
    height: float,
    duration: float,
    *,
    opening: tuple[float, float] | None = (0.0, 0.9),
    closing: tuple[float, float] | None = None,
    color: str = tokens.VOID,
) -> str:
    """A circular wipe centred on ``(cx, cy)``: black everywhere except a growing hole.

    The cover is a huge square with a round hole cut by the even-odd rule, scaled about the
    hole's centre. It is sized so the square still covers the card when the hole is a pinprick.
    """
    reach = math.hypot(max(cx, width - cx), max(cy, height - cy)) + 4
    outer = reach * 110
    shut = "0.01"
    points: list[tuple[float, dict]] = []
    if opening:
        start, end = opening
        points += [
            (0.0, {"transform": f"scale({shut})", "opacity": "1"}),
            (start, {"transform": f"scale({shut})", "opacity": "1"}),
            (end, {"transform": "scale(1)", "opacity": "1"}),
            (end + HOLD, {"transform": "scale(1)", "opacity": "0"}),
        ]
    else:
        points.append((0.0, {"transform": "scale(1)", "opacity": "0"}))
    if closing:
        start, end = closing
        points += [
            (start - HOLD, {"transform": "scale(1)", "opacity": "0"}),
            (start, {"transform": "scale(1)", "opacity": "1"}),
            (end, {"transform": f"scale({shut})", "opacity": "1"}),
        ]
    else:
        # Without this the eased track would spend the rest of the loop drifting back to its
        # opening state, visibly closing over the scene.
        points.append((duration - HOLD, {"transform": "scale(1)", "opacity": "0"}))
    cls = track(anim, steps(points, duration), easing=EASE_IN_OUT)
    if cls is None:
        return ""
    hole = (
        f"M{fmt(-outer)} {fmt(-outer)}H{fmt(outer)}V{fmt(outer)}H{fmt(-outer)}Z"
        f"M{fmt(reach)} 0A{fmt(reach)} {fmt(reach)} 0 1 0 {fmt(-reach)} 0"
        f"A{fmt(reach)} {fmt(reach)} 0 1 0 {fmt(reach)} 0Z"
    )
    return place(
        cx, cy, cls,
        f'<path fill="{color}" fill-rule="evenodd" d="{hole}"/>'
        f'<circle r="{fmt(reach)}" fill="none" stroke="{tokens.ACID}" stroke-width="3"/>',
        hidden=True,
    )


def scanlines(ids: Ids, width: float, height: float, *, opacity: float = 0.22) -> tuple[str, str]:
    """``(defs, markup)`` for a one-pattern LCD scanline overlay."""
    pattern = ids.next()
    defs = (
        f'<pattern id="{pattern}" width="4" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="4" height="1" fill="#000"/></pattern>'
    )
    return defs, (
        f'<rect width="{fmt(width)}" height="{fmt(height)}" fill="url(#{pattern})"'
        f' opacity="{fmt(opacity)}"/>'
    )


def marquee(
    anim: AnimationSet,
    ids: Ids,
    content: str,
    content_w: float,
    x: float,
    y: float,
    clip_w: float,
    clip_h: float,
    duration: float,
    *,
    laps: int = 1,
    reverse: bool = False,
) -> tuple[str, str]:
    """Scroll ``content`` (drawn at origin, ``content_w`` wide) through a clipped window.

    Enough copies are laid side by side to fill the window, and the strip travels exactly
    ``laps`` copy-widths per cycle, so the seam at the loop point is invisible.
    """
    clip = ids.next()
    copies = max(2, math.ceil(clip_w / content_w) + 1)
    travel = content_w * laps
    frames = [
        Keyframe(0.0, {"transform": f"translate({fmt(-travel if reverse else 0)}px,0px)"}),
        Keyframe(duration, {"transform": f"translate({fmt(0 if reverse else -travel)}px,0px)"}),
    ]
    cls = track(anim, frames, easing="linear")
    strip = "".join(
        f'<g transform="translate({fmt(copy * content_w)} 0)">{content}</g>'
        for copy in range(copies + laps)
    )
    defs = (
        f'<clipPath id="{clip}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(clip_w)}"'
        f' height="{fmt(clip_h)}"/></clipPath>'
    )
    return (
        f'<g clip-path="url(#{clip})"><g transform="translate({fmt(x)} {fmt(y)})">'
        f"{wrap(cls, strip)}</g></g>",
        defs,
    )


def shake_frames(
    at: Iterable[float], duration: float, *, amp: float = 5.0, span: float = 0.36, seed: int = 9
) -> list[Keyframe]:
    """A whole-scene thump: fast decaying jitter after each hit."""
    rng = random.Random(seed)
    points: list[tuple[float, dict]] = [(0.0, {"transform": "translate(0px,0px)"})]
    for start in at:
        count = 8
        for index in range(count):
            decay = 1 - index / count
            dx = (rng.random() * 2 - 1) * amp * decay
            dy = (rng.random() * 2 - 1) * amp * decay
            points.append(
                (start + span * index / count,
                 {"transform": f"translate({fmt(dx)}px,{fmt(dy)}px)"})
            )
        points.append((start + span, {"transform": "translate(0px,0px)"}))
    return steps(points, duration)


def stamp_frames(at: float, gone: float, duration: float) -> list[Keyframe]:
    """Slam in from three times size with a small overshoot, hold, then fade."""
    return steps(
        [
            (0.0, {"transform": "scale(3)", "opacity": "0"}),
            (at - HOLD, {"transform": "scale(3)", "opacity": "0"}),
            (at, {"transform": "scale(3)", "opacity": "0.2"}),
            (at + 0.16, {"transform": "scale(0.92)", "opacity": "1"}),
            (at + 0.26, {"transform": "scale(1.04)", "opacity": "1"}),
            (at + 0.34, {"transform": "scale(1)", "opacity": "1"}),
            (gone, {"transform": "scale(1)", "opacity": "1"}),
            (gone + 0.3, {"transform": "scale(1)", "opacity": "0"}),
        ],
        duration,
    )


def pop_frames(at: Iterable[float], duration: float, *, rise: float = 26.0,
               life: float = 0.8) -> list[Keyframe]:
    """A score pop-up: appear, float upward, fade."""
    points: list[tuple[float, dict]] = [(0.0, {"transform": "translate(0px,0px)", "opacity": "0"})]
    for t in sorted(at):
        points += [
            (t - HOLD, {"transform": "translate(0px,0px)", "opacity": "0"}),
            (t, {"transform": "translate(0px,0px)", "opacity": "1"}),
            (t + life * 0.6, {"transform": f"translate(0px,{fmt(-rise * 0.8)}px)", "opacity": "1"}),
            (t + life, {"transform": f"translate(0px,{fmt(-rise)}px)", "opacity": "0"}),
            (t + life + HOLD, {"transform": "translate(0px,0px)", "opacity": "0"}),
        ]
    return steps(points, duration)


def glow_rect(x: float, y: float, width: float, height: float, color: str, *,
              radius: float = 0.0, spread: Sequence[tuple[float, float]] = ((6, 0.08), (3, 0.14)),
              stroke: float = 1.5, extra: str = "") -> str:
    """A neon outline: two soft translucent strokes under one crisp one. No filters."""
    parts = []
    for grow, opacity in spread:
        parts.append(
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" height="{fmt(height)}"'
            f' rx="{fmt(radius)}" stroke="{color}" stroke-width="{fmt(grow)}"'
            f' stroke-opacity="{fmt(opacity)}" fill="none"/>'
        )
    parts.append(
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" height="{fmt(height)}"'
        f' rx="{fmt(radius)}" stroke="{color}" stroke-width="{fmt(stroke)}" fill="none"{extra}/>'
    )
    return "".join(parts)
