"""The five warps: short strips that sit between chapters and carry the story across the gap.

Each one is a loading screen from a different era of arcade: a progress bar Bit pushes along,
a dash across the screen, the flashing boss warning, a coin shower, and a pixel wipe. They share
the rails and the glass of the chapters, so stacked in the README the signal never breaks.

A warp has no header and no data. It is a transition, and it has to be readable in the one
second a scrolling reader spends on it.
"""

from __future__ import annotations

import random

from profilegen.svg import pixelfont as pf

from .. import fx, mascot, scene, tokens
from ..fx import Keyframe
from ..typography import fmt

HEIGHT = 64
T = 6.0
END = T - 0.3


def _lift(s: scene.Scene) -> tuple[float, float]:
    return s.pad + 8, s.width - s.pad - 8


def loading(s: scene.Scene) -> None:
    """LOADING PLAYER: Bit walks the bar full, then it reads READY."""
    left, right = _lift(s)
    narrow = s.narrow
    size = 8 if narrow else 9
    label = "LOADING" if narrow else "LOADING PLAYER"
    s.body.append(s.setter.text(left, 38, label, face=tokens.ARCADE, size=size, fill=tokens.ACID,
                                tracking=tokens.TRACK_ARCADE))
    label_w = s.setter.width(label, tokens.ARCADE, size, tokens.TRACK_ARCADE)
    for k in range(3):
        cls = fx.track(s.anim, fx.windows([(0.3 + k * 0.35 + j * 1.4, 1.4 + j * 1.4) for j in range(3)] +
                                          [(END, T)], T))
        s.body.append(f'<rect class="{cls}" x="{fmt(left + label_w + 6 + k * 6)}" y="34" width="3" height="3"'
                      f' fill="{tokens.ACID}"/>')

    bar_x = left + label_w + 36
    readout_w = 70 if not narrow else 58
    bar_w = right - readout_w - bar_x
    bar_y, bar_h = 42, 10
    segments = max(8, int(bar_w // 18))
    seg_w = bar_w / segments
    start, finish = 0.4, 4.6
    lit_at = [start + (finish - start) * (k + 1) / segments for k in range(segments)]
    s.body.append(f'<rect x="{fmt(bar_x - 3)}" y="{fmt(bar_y - 3)}" width="{fmt(bar_w + 6)}" height="{fmt(bar_h + 6)}"'
                  f' rx="2" fill="{tokens.PANEL}" stroke="{tokens.VIOLET}" stroke-opacity="0.6"/>')
    for k, at in enumerate(lit_at):
        color = tokens.ACID if k >= segments * 0.66 else (tokens.EMERALD if k >= segments * 0.33 else tokens.VIOLET)
        cls = fx.track(s.anim, fx.windows([(at, END)], T))
        s.body.append(f'<rect class="{cls}" x="{fmt(bar_x + k * seg_w + 1)}" y="{fmt(bar_y)}" width="{fmt(seg_w - 2)}"'
                      f' height="{bar_h}" fill="{color}"/>')

    # Percent readout: one lit state at a time, 100 at rest.
    edges = [0.0] + lit_at + [END]
    rx = right - readout_w + 10
    for k in range(segments + 1):
        value = round(100 * k / segments)
        spans = [(edges[k], edges[k + 1])]
        if k == 0:
            spans.append((END, T))
        cls = fx.track(s.anim, fx.windows(spans, T))
        color = tokens.ACID if value == 100 else tokens.TEXT
        s.body.append(fx.wrap(cls, pf.render_path(f"{value:>3}", rx, bar_y - 1, scale=2, fill=color),
                              hidden=value != 100))
    ready = fx.track(s.anim, fx.windows([(finish + 0.15, finish + 0.4), (finish + 0.55, END)], T))
    s.body.append(fx.wrap(ready, s.setter.text(bar_x + bar_w / 2, 30, "READY!", face=tokens.ARCADE, size=size,
                                               fill=tokens.HOT_VIOLET, tracking=tokens.TRACK_ARCADE,
                                               anchor="middle")))

    px = 2
    bit_end = bar_x + bar_w - mascot.width(px) - 4
    s.body.append(mascot.bit(s.anim, T, bit_end, bar_y - 3 - mascot.height(px), px,
                             walk=(-(bar_w - mascot.width(px) - 8), start, finish),
                             jumps=[finish + 0.15], cheer=[(finish + 0.2, END)], blinks=[2.0]))


def dash(s: scene.Scene) -> None:
    """Bit sprints across, skids to a stop, waves, and sprints off."""
    left, right = _lift(s)
    width = s.width
    narrow = s.narrow

    # Chevrons streaming the way Bit runs.
    chev_w = 22
    count = int(width // chev_w) + 1
    chevrons = "".join(
        f'<path d="M{fmt(k * chev_w)} 0l7 7l-7 7" fill="none" stroke="{tokens.VIOLET_DEEP}" stroke-width="2"/>'
        for k in range(count)
    )
    strip, defs = fx.marquee(s.anim, s.ids, chevrons, count * chev_w, 0, 25, width, 14, T, laps=3, reverse=True)
    s.defs.append(defs)
    s.body.append(f'<g opacity="0.5">{strip}</g>')
    s.body.append(f'<rect x="{fmt(left)}" y="52" width="{fmt(right - left)}" height="1" fill="{tokens.HAIRLINE}"/>')

    px = 2
    stop_x = width * (0.36 if narrow else 0.44)
    run_in = -(stop_x + 40)
    run_out = width - stop_x + 40
    t_in, t_stop, t_wave, t_go, t_gone = 0.2, 1.7, (1.95, 3.4), 3.7, 5.0
    s.body.append(mascot.bit(s.anim, T, stop_x, 52 - mascot.height(px), px,
                             walk=(run_in, t_in, t_stop), walk_out=(run_out, t_go, t_gone),
                             wave=[t_wave], blinks=[3.0]))

    # Speed lines riding behind Bit, only while it runs.
    def at(dx: float, opacity: str) -> dict:
        return {"transform": f"translate({fmt(dx)}px,0px)", "opacity": opacity}

    frames = [
        Keyframe(0.0, at(run_in, "0")),
        Keyframe(t_in - fx.HOLD, at(run_in, "0")),
        Keyframe(t_in, at(run_in, "1")),
        Keyframe(t_stop, at(0, "1")),
        Keyframe(t_stop + 0.25, at(0, "0")),
        Keyframe(t_go - fx.HOLD, at(0, "0")),
        Keyframe(t_go, at(0, "1")),
        Keyframe(t_gone, at(run_out, "1")),
        Keyframe(t_gone + fx.HOLD, at(run_out, "0")),
        Keyframe(T - fx.HOLD, at(run_in, "0")),
        Keyframe(T, at(run_in, "0")),
    ]
    lines_cls = s.anim.add(frames, easing="linear", base={"opacity": "0"})
    lines = "".join(
        f'<rect x="{fmt(-8 - length)}" y="{fmt(y)}" width="{fmt(length)}" height="2" fill="{color}"/>'
        for y, length, color in ((24, 26, tokens.ACID), (32, 40, tokens.VIOLET), (40, 20, tokens.EMERALD),
                                 (47, 32, tokens.HOT_VIOLET))
    )
    s.body.append(f'<g transform="translate({fmt(stop_x)} 0)"><g class="{lines_cls}" opacity="0">{lines}</g></g>')
    s.body.append(fx.burst(s.anim, stop_x + mascot.width(px) / 2, 50, [t_stop], T, count=8, radius=26, size=3,
                           seed=41))

    text = "NEXT: WORLD MAP" if not narrow else "WORLD MAP"
    size = 8 if narrow else 9
    tw = s.setter.width(text, tokens.ARCADE, size, tokens.TRACK_ARCADE)
    blink = fx.track(s.anim, fx.blink_frames(0.0, T, 0.5, T, low="0.35"))
    s.body.append(s.setter.text(right - tw - 22, 18, text, face=tokens.ARCADE, size=size,
                                fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE))
    s.body.append(fx.wrap(blink, f'<path d="M{fmt(right - 14)} 11l6 5l-6 5" fill="none" stroke="{tokens.ACID}"'
                                 f' stroke-width="2"/>'))


def boss(s: scene.Scene) -> None:
    """WARNING: the screen flashes, hazard tape scrolls, Bit shakes, the gavel slams."""
    left, right = _lift(s)
    width = s.width
    narrow = s.narrow
    hits = [0.6, 1.8, 3.0, 4.2]

    flash = s.anim.add(fx.steps(
        [(0.0, {"opacity": "0"})] + [p for t in hits for p in ((t, {"opacity": "0.22"}), (t + 0.18, {"opacity": "0"}))],
        T), base={"opacity": "0"})
    s.body.append(f'<rect class="{flash}" opacity="0" width="{fmt(width)}" height="{HEIGHT}" fill="{tokens.HOT_VIOLET}"/>')

    period = 16
    stripes = "".join(
        f'<path d="M{fmt(k * period)} 8l8 -8h8l-8 8Z" fill="{tokens.HOT_VIOLET}"/>' for k in range(int(width // period) + 2)
    )
    band_w = (int(width // period) + 1) * period
    for y, reverse in ((3, False), (HEIGHT - 11, True)):
        band, defs = fx.marquee(s.anim, s.ids, stripes, band_w, 0, y, width, 8, T, laps=2, reverse=reverse)
        s.defs.append(defs)
        s.body.append(f'<rect x="0" y="{y}" width="{fmt(width)}" height="8" fill="{tokens.VIOLET_DEEP}" opacity="0.35"/>'
                      f'<g opacity="0.75">{band}</g>')

    size = 12 if narrow else 15
    blink = fx.track(s.anim, fx.blink_frames(0.0, T, 0.6, T, low="0.2"))
    s.body.append(fx.wrap(blink, s.setter.text(width / 2, 35, "WARNING", face=tokens.ARCADE, size=size,
                                               fill=tokens.HOT_VIOLET, tracking=tokens.TRACK_ARCADE,
                                               anchor="middle")))
    s.body.append(s.setter.text(width / 2, 48, "A BOSS IS APPROACHING", face=tokens.ARCADE, size=6.5 if narrow else 7,
                                fill=tokens.TEXT, tracking=tokens.TRACK_ARCADE, anchor="middle"))

    px = 2
    shake = fx.jitter(s.anim, hits, T, amp=2.0, seed=17)
    bit = mascot.bit(s.anim, T, 0, 0, px, blinks=[1.2, 3.6], point=[(4.4, 5.6)])
    s.body.append(fx.place(left + 6, HEIGHT - 12 - mascot.height(px), shake, bit))

    # The Judge's gavel, slamming on each hit.
    swing_points: list[tuple[float, dict]] = [(0.0, {"transform": "rotate(-35deg)"})]
    for t in hits:
        swing_points += [(t - 0.12, {"transform": "rotate(-35deg)"}), (t, {"transform": "rotate(8deg)"}),
                         (t + 0.08, {"transform": "rotate(0deg)"}), (t + 0.4, {"transform": "rotate(-35deg)"})]
    swing = s.anim.add(fx.steps(swing_points, T), easing="ease-in")
    gavel = (
        f'<rect x="-3" y="-2" width="26" height="4" fill="{tokens.VIOLET_BRIGHT}"/>'
        f'<rect x="18" y="-8" width="10" height="16" rx="1" fill="{tokens.VIOLET}"/>'
        f'<rect x="20" y="-8" width="2" height="16" fill="{tokens.VIOLET_BRIGHT}"/>'
    )
    gx, gy = right - 44, 38
    s.body.append(f'<rect x="{fmt(gx + 10)}" y="{fmt(gy + 11)}" width="30" height="4" fill="{tokens.VIOLET_DEEP}"/>')
    s.body.append(fx.place(gx, gy, swing, gavel))
    for t in hits:
        s.body.append(fx.burst(s.anim, gx + 30, gy + 10, [t], T, count=5, radius=16, size=2, seed=int(t * 10),
                               life=0.35))


def bonus(s: scene.Scene) -> None:
    """A coin shower over BONUS STAGE, with Bit jumping for them."""
    left, right = _lift(s)
    width = s.width
    narrow = s.narrow
    rng = random.Random(78)

    fall = 2.4
    fall_frames = [
        Keyframe(0.0, {"transform": "translate(0px,-14px)", "opacity": "1"}),
        Keyframe(fall, {"transform": f"translate(0px,{HEIGHT + 14}px)", "opacity": "1"}),
        Keyframe(fall + 0.01, {"transform": "translate(0px,-14px)", "opacity": "0"}),
        Keyframe(T - fx.HOLD, {"transform": "translate(0px,-14px)", "opacity": "0"}),
        Keyframe(T, {"transform": "translate(0px,-14px)", "opacity": "1"}),
    ]
    widths = ("1", "0.6", "0.15", "0.6")
    spin_frames = fx.steps([(k * 0.12, {"transform": f"scale({widths[k % 4]},1)"})
                            for k in range(int(T / 0.12))], T)
    spin_cls = s.anim.add(spin_frames)
    fall_cls = s.anim.add(fall_frames, easing="linear", base={"opacity": "0"})
    coins = 34 if not narrow else 18
    parts: list[str] = []
    for k in range(coins):
        x = left + 12 + rng.random() * (right - left - 24)
        cls = s.anim.use(fall_cls, delay=-(k / coins) * T - rng.random() * 0.2, base={"opacity": "0"})
        spin_here = s.anim.use(spin_cls, delay=-rng.random() * 0.48)
        parts.append(
            f'<g transform="translate({fmt(x)} 0)"><g class="{cls}" opacity="0"><g class="{spin_here}">'
            f'<circle r="6" fill="{tokens.ACID_DEEP}"/><circle r="4.4" fill="{tokens.ACID}"/>'
            f'<rect x="-1" y="-3" width="2" height="6" fill="{tokens.ACID_DEEP}"/></g></g></g>'
        )
    s.body.append("".join(parts))

    size = 11 if narrow else 14
    pop = fx.track(s.anim, fx.steps(
        [(0.0, {"transform": "scale(1)"})] + [p for t in (1.0, 3.0, 5.0) for p in
                                               ((t, {"transform": "scale(1.18)"}), (t + 0.12, {"transform": "scale(1)"}))],
        T))
    title = s.setter.text(0, size / 2, "BONUS STAGE", face=tokens.ARCADE, size=size, fill=tokens.ACID,
                          tracking=tokens.TRACK_ARCADE, anchor="middle")
    ghost = s.setter.text(2, size / 2 + 2, "BONUS STAGE", face=tokens.ARCADE, size=size, fill=tokens.VIOLET_DEEP,
                          tracking=tokens.TRACK_ARCADE, anchor="middle")
    s.body.append(fx.place(width / 2, 28, pop, ghost + title))
    s.body.append(s.setter.text(width / 2, 50, "+1 FOR EVERY DAY SHIPPED", face=tokens.ARCADE, size=6.5,
                                fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE, anchor="middle"))

    px = 2
    jumps = [0.4, 1.4, 2.4, 3.4, 4.4]
    bx = left + (10 if narrow else 40)
    s.body.append(mascot.bit(s.anim, T, bx, HEIGHT - 8 - mascot.height(px), px, jumps=jumps,
                             cheer=[(t, t + 0.5) for t in jumps[::2]], blinks=[2.0]))
    pop_cls = s.anim.add(fx.pop_frames([jumps[0] + 0.25], T, rise=12, life=0.6), easing="ease-out",
                         base={"opacity": "0"})
    pops = [pop_cls] + [s.anim.use(pop_cls, delay=t - jumps[0], base={"opacity": "0"}) for t in jumps[1:]]
    label = pf.render_path("+1", 0, 0, scale=2, fill=tokens.ACID, strict=False)
    for cls in pops:
        s.body.append(fx.place(bx + mascot.width(px) + 4, 14, cls, label, hidden=True))


def wipe(s: scene.Scene) -> None:
    """A pixel wipe: violet cells sweep across, turn acid, and the text underneath changes."""
    left, right = _lift(s)
    width = s.width
    narrow = s.narrow
    cell = 16
    cols = int(width // cell) + 1
    rows = HEIGHT // cell
    sweep_start, sweep = 0.3, 2.6
    life = 0.9

    size = 10 if narrow else 12
    before, after = "SAVING PROGRESS", "LOOT INCOMING"
    swap = sweep_start + sweep / 2 + 0.3
    first = fx.track(s.anim, fx.windows([(0.0, swap)], T))
    second = fx.track(s.anim, fx.windows([(swap, T)], T))
    s.body.append(fx.wrap(first, s.setter.text(width / 2, 37, before, face=tokens.ARCADE, size=size,
                                               fill=tokens.MUTED, tracking=tokens.TRACK_ARCADE, anchor="middle"),
                          hidden=True))
    s.body.append(fx.wrap(second, s.setter.text(width / 2, 37, after, face=tokens.ARCADE, size=size,
                                                fill=tokens.ACID, tracking=tokens.TRACK_ARCADE, anchor="middle")))

    def frames(color_on: float, color_off: float) -> list[Keyframe]:
        return [
            Keyframe(0.0, {"opacity": "0"}),
            Keyframe(color_on, {"opacity": "0.9"}),
            Keyframe(color_off, {"opacity": "0"}),
            Keyframe(T, {"opacity": "0"}),
        ]

    violet = s.anim.add(frames(0.01, life * 0.5), base={"opacity": "0"})
    acid = s.anim.add(frames(life * 0.5, life), base={"opacity": "0"})
    rng = random.Random(64)
    cells: list[str] = []
    for c in range(cols):
        for r in range(rows):
            delay = sweep_start + sweep * (c / cols) + rng.random() * 0.25 + r * 0.04
            v = s.anim.use(violet, delay=delay, base={"opacity": "0"})
            a = s.anim.use(acid, delay=delay, base={"opacity": "0"})
            x, y = c * cell, r * cell
            cells.append(
                f'<rect class="{v}" opacity="0" x="{x}" y="{y}" width="{cell - 2}" height="{cell - 2}" fill="{tokens.VIOLET}"/>'
                f'<rect class="{a}" opacity="0" x="{x}" y="{y}" width="{cell - 2}" height="{cell - 2}" fill="{tokens.ACID}"/>'
            )
    s.front.append("".join(cells))

    px = 2
    s.body.append(mascot.bit(s.anim, T, right - mascot.width(px) - (6 if narrow else 30), HEIGHT - 10 - mascot.height(px),
                             px, jumps=[swap + 0.1], cheer=[(swap + 0.1, swap + 1.2)], blinks=[1.0, 4.6]))


WARPS = (
    ("LOADING PLAYER", loading),
    ("DASH", dash),
    ("BOSS APPROACHING", boss),
    ("BONUS", bonus),
    ("PIXEL WIPE", wipe),
)


def build(index: int, *, width: int = tokens.WIDE) -> str:
    """Warp ``index`` (0-based, in page order) at ``width``."""
    name, draw = WARPS[index]
    s = scene.Scene(width, T, prefix="w")
    draw(s)
    return s.render(
        HEIGHT,
        chapter=None,
        title=f"Warp {index + 1}: {name.lower()}",
        description=f"A short animated transition between chapters: {name.lower()}.",
    )
