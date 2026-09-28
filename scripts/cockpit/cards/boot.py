"""CH.01 BOOT: the cabinet powers on.

The tube snaps on, a striped sun climbs out of the horizon behind a city that never stops
scrolling, the name drops in one letter at a time and tears itself apart every few seconds
like a sign with a bad transformer. Then Bit walks in, waves, and explains where the reader
has landed. Every other chapter is a game; this one is the attract screen that makes someone
put a coin in.

The static frame (reduced motion, or a renderer with no CSS animation) is the finished
title screen: sun up, name landed, Bit standing, first line of his speech already printed.
"""

from __future__ import annotations

import math
import random

from profilegen.svg import pixelfont

from .. import fx, mascot, scene, tokens
from ..typography import fmt, load_face

T = 16.0

NAME = "JITEESH GHODKE"
NAME_LINES = ("JITEESH", "GHODKE")
TAGLINE = "SOFTWARE ENGINEER · SYSTEM DESIGN · BTECH '29"
TAGLINE_NARROW = "SYSTEM DESIGN · BTECH '29"
CAPTIONS = (
    "Hi, I'm Bit. I live inside Jiteesh's GitHub.",
    "He builds things that keep running when nobody is watching them.",
    "The arcade is open all night. Scroll down and press start.",
)

DROP_AT = 0.95
STAGGER = 0.07
FALL = 0.32
GLITCHES = (2.4, 6.5, 10.7, 13.9)
FLICKERS = (4.7, 9.2, 12.5)
CRT_OFF = (15.25, 16.0)


def _drop_frames(land: float, height_units: float, extra: list[tuple[float, dict]] | None = None) -> list:
    """A letter falling under gravity in 40 ms steps, then a one-pixel bounce."""
    rest = {"transform": "translate(0px,0px)", "opacity": "1"}
    points: list[tuple[float, dict]] = [
        (0.0, {"transform": f"translate(0px,{fmt(height_units)}px)", "opacity": "0"}),
        (land - FALL - fx.HOLD, {"transform": f"translate(0px,{fmt(height_units)}px)", "opacity": "0"}),
    ]
    ticks = 8
    for tick in range(ticks):
        share = tick / ticks
        points.append(
            (land - FALL + FALL * share,
             {"transform": f"translate(0px,{fmt(height_units * (1 - share * share))}px)", "opacity": "1"})
        )
    points += [
        (land, rest),
        (land + 0.05, {"transform": f"translate(0px,{fmt(-height_units * 0.06)}px)", "opacity": "1"}),
        (land + 0.1, rest),
    ]
    points += extra or []
    return fx.steps(points, T)


def _name(s: scene.Scene, lines: tuple[str, ...], x: float, baselines: list[float], size: float) -> str:
    """The name, landing letter by letter, with two chromatic ghosts that tear on each glitch."""
    setter, anim = s.setter, s.anim
    upem = load_face(tokens.ARCADE)["upem"]
    per_px = upem / size
    fall_units = 90 * per_px  # glyph space is y-up, so positive is above the baseline
    order = 0
    main: list[str] = []

    flicker_letter = "O"
    for line, baseline in zip(lines, baselines):
        classes: dict[int, str | None] = {}
        for index, char in enumerate(line):
            if not char.strip():
                continue
            land = DROP_AT + order * STAGGER + FALL
            extra = None
            if char == flicker_letter:
                rest = "translate(0px,0px)"
                extra = [(t, {"transform": rest, **props})
                         for t, props in ((f.t, f.props) for f in fx.flicker_frames(FLICKERS, T))
                         if t > land + 0.2 and t < T]
            classes[index] = fx.track(anim, _drop_frames(land, fall_units, extra))
            order += 1
        main.append(
            setter.text(x, baseline, line, face=tokens.ARCADE, size=size, fill=tokens.TEXT,
                        tracking=tokens.TRACK_ARCADE,
                        cls_for=lambda i, _c, classes=classes: classes.get(i))
        )

    landed = DROP_AT + order * STAGGER + FALL + 0.1
    rng = random.Random(41)
    ghost_markup: list[str] = []
    for color, sign, seed in ((tokens.HOT_VIOLET, -1, 3), (tokens.ACID, 1, 5)):
        base = f"translate({fmt(sign * 3)}px,0px)"
        points: list[tuple[float, dict]] = [
            (0.0, {"transform": base, "opacity": "0"}),
            (landed, {"transform": base, "opacity": "0.55"}),
        ]
        local = random.Random(seed)
        for t in fx.glitch_times(GLITCHES, rng):
            dx = sign * (3 + local.random() * 14)
            dy = (local.random() * 2 - 1) * 3
            points.append((t, {"transform": f"translate({fmt(dx)}px,{fmt(dy)}px)", "opacity": fmt(0.5 + local.random() * 0.5)}))
        for start in GLITCHES:
            points.append((start + 0.46, {"transform": base, "opacity": "0.55"}))
        points.append((CRT_OFF[1] - 0.05, {"transform": base, "opacity": "0"}))
        cls = fx.track(anim, fx.steps(points, T), base={"opacity": "0.55", "transform": base})
        runs = "".join(
            setter.text(x, baseline, line, face=tokens.ARCADE, size=size, fill=color,
                        tracking=tokens.TRACK_ARCADE)
            for line, baseline in zip(lines, baselines)
        )
        ghost_markup.append(fx.wrap(cls, runs))

    shake = fx.jitter(anim, GLITCHES, T, amp=5, seed=13)
    top = baselines[0] - size - 6
    bottom = baselines[-1] + 8
    bands = fx.glitch_bands(anim, x - 20, top, s.width - 2 * x + 40, bottom - top, GLITCHES, T,
                            count=7, seed=17)
    return fx.wrap(shake, "".join(ghost_markup) + "".join(main)) + bands


def _stars(s: scene.Scene, x0: float, y0: float, x1: float, y1: float, count: int) -> str:
    rng = random.Random(7)
    groups: list[list[str]] = [[] for _ in range(4)]
    for _ in range(count):
        x = rng.uniform(x0, x1)
        y = y0 + (y1 - y0) * rng.random() ** 1.4
        size = rng.choice((1.5, 2, 2, 3))
        groups[rng.randrange(4)].append(f"M{fmt(x)} {fmt(y)}h{fmt(size)}v{fmt(size)}h{fmt(-size)}z")
    colors = (tokens.TEXT, tokens.ACID_BRIGHT, tokens.VIOLET_BRIGHT, tokens.TEXT)
    parts = []
    for index, group in enumerate(groups):
        if not group:
            continue
        phase = index * T / 16
        points = []
        for beat in range(8):
            t = (beat * T / 8 + phase) % T
            points.append((t, {"opacity": "0.9" if beat % 2 == 0 else "0.2"}))
        cls = fx.track(s.anim, fx.steps(points, T), easing="ease-in-out")
        parts.append(f'<path{fx.cls_attr(cls)} fill="{colors[index]}" d="{"".join(group)}"/>')
    return "".join(parts)


def _shooting_star(s: scene.Scene, x: float, y: float, at: float, reach: float) -> str:
    angle = math.radians(18)
    dx, dy = math.cos(angle) * reach, math.sin(angle) * reach
    cls = fx.track(
        s.anim,
        fx.steps(
            [
                (0.0, {"transform": "translate(0px,0px)", "opacity": "0"}),
                (at - fx.HOLD, {"transform": "translate(0px,0px)", "opacity": "0"}),
                (at, {"transform": "translate(0px,0px)", "opacity": "1"}),
                (at + 0.75, {"transform": f"translate({fmt(dx)}px,{fmt(dy)}px)", "opacity": "0"}),
                (at + 0.76, {"transform": "translate(0px,0px)", "opacity": "0"}),
            ],
            T,
        ),
        easing="linear",
    )
    grad = s.ids.next()
    s.defs.append(
        f'<linearGradient id="{grad}" x1="1" y1="0" x2="0" y2="0">'
        f'<stop offset="0" stop-color="#FFFFFF"/><stop offset="0.2" stop-color="{tokens.ACID_BRIGHT}"/>'
        f'<stop offset="1" stop-color="{tokens.ACID}" stop-opacity="0"/></linearGradient>'
    )
    tail = 70
    return fx.place(
        x, y, cls,
        f'<g transform="rotate(18)"><rect x="{-tail}" y="-1" width="{tail}" height="2" fill="url(#{grad})"/></g>',
        hidden=True,
    )


def _sun(s: scene.Scene, cx: float, horizon: float, radius: float) -> str:
    grad, halo, clip, horizon_clip = s.ids.next(), s.ids.next(), s.ids.next(), s.ids.next()
    stripes = []
    band_top = -radius * 0.42
    stripes.append(f'<rect x="{fmt(-radius)}" y="{fmt(-radius)}" width="{fmt(radius * 2)}" height="{fmt(radius + band_top)}"/>')
    y = band_top
    gap = 2.0
    solid = radius * 0.16
    while y < radius:
        y += gap
        stripes.append(f'<rect x="{fmt(-radius)}" y="{fmt(y)}" width="{fmt(radius * 2)}" height="{fmt(solid)}"/>')
        y += solid
        gap += 2.2
        solid = max(3.0, solid * 0.72)
    s.defs.append(
        f'<linearGradient id="{grad}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{tokens.ACID}"/>'
        f'<stop offset="0.22" stop-color="{tokens.EMERALD}"/>'
        f'<stop offset="0.45" stop-color="{tokens.HOT_VIOLET}"/>'
        f'<stop offset="0.7" stop-color="{tokens.VIOLET_DEEP}"/></linearGradient>'
        + f'<radialGradient id="{halo}">'
        f'<stop offset="0.3" stop-color="{tokens.HOT_VIOLET}" stop-opacity="0.45"/>'
        f'<stop offset="0.6" stop-color="{tokens.VIOLET}" stop-opacity="0.16"/>'
        f'<stop offset="1" stop-color="{tokens.VIOLET}" stop-opacity="0"/></radialGradient>'
        + f'<clipPath id="{clip}">{"".join(stripes)}</clipPath>'
        + f'<clipPath id="{horizon_clip}"><rect x="0" y="0" width="{s.width}" height="{fmt(horizon)}"/></clipPath>'
    )
    rise = fx.track(
        s.anim,
        fx.steps(
            [
                (0.0, {"transform": f"translate(0px,{fmt(radius * 1.15)}px)"}),
                (0.35, {"transform": f"translate(0px,{fmt(radius * 1.15)}px)"}),
                (2.8, {"transform": "translate(0px,0px)"}),
                (CRT_OFF[0], {"transform": "translate(0px,0px)"}),
                (T, {"transform": f"translate(0px,{fmt(radius * 0.3)}px)"}),
            ],
            T,
        ),
        easing=fx.EASE_OUT,
    )
    breathe = fx.track(
        s.anim,
        fx.steps([(0.0, {"opacity": "0.7"}), (T / 4, {"opacity": "1"}), (T / 2, {"opacity": "0.7"}),
                  (T * 3 / 4, {"opacity": "1"})], T),
        easing="ease-in-out",
    )
    disc = (
        f'<circle class="{breathe}" r="{fmt(radius * 2.1)}" fill="url(#{halo})"/>'
        f'<g clip-path="url(#{clip})"><circle r="{fmt(radius)}" fill="url(#{grad})"/></g>'
    )
    return (
        f'<g clip-path="url(#{horizon_clip})">'
        + fx.place(cx, horizon - radius * 0.3, rise, disc)
        + "</g>"
    )


def _skyline(s: scene.Scene, horizon: float) -> str:
    rng = random.Random(23)
    tall = 42 if s.narrow else 50
    blocks: list[str] = []
    edges: list[str] = []
    lit: dict[str, list[str]] = {tokens.ACID: [], tokens.VIOLET_BRIGHT: [], tokens.HOT_VIOLET: []}
    flicker: list[str] = []
    x = 0.0
    while x < s.width:
        w = rng.choice((18, 22, 26, 30, 36, 44))
        h = rng.randint(12, tall - 8) if rng.random() < 0.8 else rng.randint(tall - 12, tall)
        w = min(w, s.width - x)
        top = tall - h
        blocks.append(f"M{fmt(x)} {fmt(top)}h{fmt(w)}v{fmt(h)}h{fmt(-w)}z")
        edges.append(f"M{fmt(x)} {fmt(top)}h{fmt(w)}v0.8h{fmt(-w)}z")
        if h > 20 and rng.random() < 0.3:
            blocks.append(f"M{fmt(x + w / 2 - 0.5)} {fmt(top - 7)}h1v7h-1z")
        wy = top + 5
        while wy < tall - 5:
            wx = x + 3
            while wx < x + w - 4:
                roll = rng.random()
                if roll < 0.2:
                    color = rng.choice(list(lit))
                    rect = f"M{fmt(wx)} {fmt(wy)}h2v2h-2z"
                    (flicker if roll < 0.03 else lit[color]).append(rect)
                wx += 5
            wy += 6
        x += w + rng.choice((0, 0, 2, 4))
    body = f'<path fill="{tokens.PLUM}" d="{"".join(blocks)}"/>'
    body += f'<path fill="{tokens.VIOLET}" opacity="0.55" d="{"".join(edges)}"/>'
    for color, rects in lit.items():
        if rects:
            body += f'<path fill="{color}" opacity="0.8" d="{"".join(rects)}"/>'
    if flicker:
        cls = fx.track(s.anim, fx.flicker_frames((1.3, 5.8, 8.1, 11.6, 14.2), T))
        body += f'<path{fx.cls_attr(cls)} fill="{tokens.ACID_BRIGHT}" d="{"".join(flicker)}"/>'
    markup, defs = fx.marquee(s.anim, s.ids, body, s.width, 0, horizon - tall, s.width, tall, T)
    s.defs.append(defs)
    return markup


def _floor(s: scene.Scene, horizon: float, depth: float) -> str:
    width = s.width
    vanish = width / 2
    bottom = horizon + depth
    ground, clip = s.ids.next(), s.ids.next()
    s.defs.append(
        f'<linearGradient id="{ground}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{tokens.GRAPE}"/>'
        f'<stop offset="0.6" stop-color="{tokens.FOREST}"/>'
        f'<stop offset="1" stop-color="{tokens.VOID}" stop-opacity="0"/></linearGradient>'
        f'<clipPath id="{clip}"><rect x="0" y="{fmt(horizon)}" width="{width}" height="{fmt(depth)}"/></clipPath>'
    )
    parts = [f'<rect x="0" y="{fmt(horizon)}" width="{width}" height="{fmt(depth)}" fill="url(#{ground})"/>']
    spread = width / 9
    rails = []
    for index in range(-14, 15):
        near = vanish + index * spread
        far = vanish + index * spread * 0.05
        rails.append(f"M{fmt(far)} {fmt(horizon)}L{fmt(near)} {fmt(bottom + 20)}")
    parts.append(f'<path d="{"".join(rails)}" stroke="{tokens.VIOLET}" stroke-width="1" opacity="0.5"/>')

    # One line travelling horizon to viewer on a perspective curve, replayed at staggered
    # delays: every row is the same row, a beat later.
    lap = 4.0
    rows = 6
    samples = 24
    frames = []
    for index in range(samples + 1):
        p = index / samples
        y = depth * p ** 2.2
        frames.append((lap * p, {"transform": f"translate(0px,{fmt(y)}px)", "opacity": fmt(0.1 + 0.8 * p)}))
    points = []
    for repeat in range(int(T / lap)):
        points += [(t + repeat * lap, props) for t, props in frames]
    cls = fx.track(s.anim, fx.steps(points, T), easing="linear")
    line = f'<rect x="0" y="-0.75" width="{width}" height="1.5" fill="{tokens.ACID}"/>'
    for row in range(rows):
        rule = s.anim.use(cls, delay=-row * lap / rows) if row else cls
        parts.append(fx.place(0, horizon, rule, line))
    horizon_glow = (
        f'<rect x="0" y="{fmt(horizon - 3)}" width="{width}" height="6" fill="{tokens.ACID}" opacity="0.12"/>'
        f'<rect x="0" y="{fmt(horizon - 1)}" width="{width}" height="2" fill="{tokens.ACID}" opacity="0.9"/>'
    )
    return f'<g clip-path="url(#{clip})">{"".join(parts)}</g>' + horizon_glow


def _bubble(s: scene.Scene, x: float, y: float, w: float, h: float, tail_x: float) -> str:
    """Bit's speech bubble: pops in, types three captions, and folds away before the loop."""
    size = 11.5 if s.narrow else 13
    inner = w - 32
    appear, gone = 3.3, 15.1
    pop = fx.track(
        s.anim,
        fx.steps(
            [
                (0.0, {"transform": "scale(0.001)", "opacity": "0"}),
                (appear - fx.HOLD, {"transform": "scale(0.001)", "opacity": "0"}),
                (appear, {"transform": "scale(0.2)", "opacity": "1"}),
                (appear + 0.12, {"transform": "scale(1.08)", "opacity": "1"}),
                (appear + 0.2, {"transform": "scale(1)", "opacity": "1"}),
                (gone, {"transform": "scale(1)", "opacity": "1"}),
                (gone + 0.12, {"transform": "scale(0.001)", "opacity": "0"}),
            ],
            T,
        ),
    )
    frame = (
        f'<path d="M0 0H{fmt(w)}V{fmt(h)}H{fmt(tail_x + 16)}L{fmt(tail_x)} {fmt(h + 12)}L{fmt(tail_x + 4)} {fmt(h)}H0Z"'
        f' fill="{tokens.PANEL}" stroke="{tokens.ACID}" stroke-width="1.5"/>'
        f'<path d="M0 0H{fmt(w)}V{fmt(h)}H0Z" fill="none" stroke="{tokens.ACID}" stroke-width="6" stroke-opacity="0.08"/>'
        f'<rect x="4" y="4" width="{fmt(w - 8)}" height="3" fill="{tokens.VIOLET}" opacity="0.35"/>'
    )
    captions = []
    spans = ((3.55, 6.95), (7.15, 10.95), (11.15, 14.95))
    lines_per = [s.setter.wrap(text, tokens.MONO_SEMI, size, inner) for text in CAPTIONS]
    for index, (lines, (start, end)) in enumerate(zip(lines_per, spans)):
        captions.append(
            fx.typewriter(
                s.anim, s.setter, 16, 26, lines, face=tokens.MONO_SEMI, size=size,
                fill=tokens.TEXT, start=start, end=end, duration=T, cps=30,
                static=index == 0,
            )
        )
    # Anchored at the tail, so the pop grows out of Bit's mouth rather than from a corner.
    return (
        f'<g transform="translate({fmt(x + tail_x)} {fmt(y + h + 12)})">'
        + fx.wrap(pop, f'<g transform="translate({fmt(-tail_x)} {fmt(-h - 12)})">{frame}{"".join(captions)}</g>')
        + "</g>"
    )


def _hud(s: scene.Scene, y: int, data: dict) -> str:
    scale = 2
    fill = tokens.ACID
    days = data.get("account_age_days") or 0
    rating = (data.get("codeforces_profile") or {}).get("rating") or 0
    left = f"1UP DAY {days:03d}"
    mid = f"HI {rating:06d}"
    right = "CREDIT 01"
    x0 = s.pad + 8
    parts = [pixelfont.render_path(left, x0, y, scale=scale, fill=tokens.VIOLET_BRIGHT)]
    if not s.narrow:
        mw, _ = pixelfont.measure(mid, scale=scale)
        parts.append(pixelfont.render_path(mid, (s.width - mw) / 2, y, scale=scale, fill=fill))
    rw, _ = pixelfont.measure(right, scale=scale)
    blink = fx.track(s.anim, fx.blink_frames(0.0, T, 1.2, T, low="0.25"))
    parts.append(
        fx.wrap(blink, pixelfont.render_path(right, s.width - s.pad - 8 - rw, y, scale=scale, fill=fill))
    )
    return "".join(parts)


def _press_start(s: scene.Scene, y: float) -> str:
    size = 11 if s.narrow else 13
    text = "PRESS START"
    blink = fx.track(s.anim, fx.blink_frames(3.0, CRT_OFF[0], 0.9, T, low="0"))
    w = s.setter.width(text, tokens.ARCADE, size, tokens.TRACK_ARCADE)
    cx = s.width / 2
    arrow = fx.track(
        s.anim,
        fx.steps([(t * 0.5, {"transform": f"translate(0px,{3 if t % 2 else 0}px)"}) for t in range(int(T * 2))], T),
    )
    chevrons = "".join(
        f'<path d="M{fmt(dx - 6)} 0l6 6l6 -6" stroke="{tokens.ACID}" stroke-width="2" fill="none"/>'
        for dx in (cx - w / 2 - 26, cx + w / 2 + 26)
    )
    return (
        fx.wrap(blink, s.setter.text(cx, y, text, face=tokens.ARCADE, size=size, fill=tokens.ACID,
                                     tracking=tokens.TRACK_ARCADE, anchor="middle"))
        + fx.place(0, y - size + 2, arrow, chevrons)
    )


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    s = scene.Scene(width, T, prefix="b")
    narrow = s.narrow
    body = s.body

    hud_y = 60
    body.append(_hud(s, hud_y, data))

    if narrow:
        size = 34
        baselines = [128, 172]
        lines = NAME_LINES
        tagline_y = 200
        horizon = 318
        radius = 62
        depth = 118
    else:
        size = 44
        baselines = [140]
        lines = (NAME,)
        tagline_y = 172
        horizon = 312
        radius = 96
        depth = 120

    name_w = max(s.setter.width(line, tokens.ARCADE, size, tokens.TRACK_ARCADE) for line in lines)
    name_x = (width - name_w) / 2

    sky_top = 84
    body.append(_stars(s, s.pad, sky_top, width - s.pad, horizon - 20, 34 if narrow else 60))
    body.append(_shooting_star(s, width * 0.2, sky_top + 14, 5.3, width * 0.5))
    body.append(_shooting_star(s, width * 0.55, sky_top + 30, 11.6, width * 0.35))
    body.append(_sun(s, width / 2, horizon, radius))
    body.append(_skyline(s, horizon))
    body.append(_floor(s, horizon, depth))

    slot = s.ids.next()
    slot_top = hud_y + 20
    s.defs.append(
        f'<clipPath id="{slot}"><rect x="0" y="{slot_top}" width="{width}"'
        f' height="{fmt(baselines[-1] + 14 - slot_top)}"/></clipPath>'
    )
    body.append(f'<g clip-path="url(#{slot})">{_name(s, lines, name_x, baselines, size)}</g>')

    tag = TAGLINE_NARROW if narrow else TAGLINE
    tag_size = 9.5 if narrow else 11
    fade = fx.track(
        s.anim,
        fx.steps([(0.0, {"opacity": "0"}), (2.3, {"opacity": "0.4"}), (2.45, {"opacity": "1"}),
                  (CRT_OFF[1] - 0.05, {"opacity": "0"})], T),
    )
    body.append(
        fx.wrap(fade, s.setter.text(width / 2, tagline_y, tag, face=tokens.DISPLAY, size=tag_size,
                                    fill=tokens.ACID_BRIGHT, tracking=tokens.TRACK_EYEBROW, anchor="middle"))
    )

    px = 3 if narrow else 4
    bit_x = s.pad + (14 if narrow else 44)
    feet = horizon + depth - 12
    bit_y = feet - mascot.height(px)
    body.append(
        mascot.bit(
            s.anim, T, bit_x, bit_y, px,
            walk=(-(bit_x + 80), 1.1, 3.1),
            wave=[(3.2, 4.4), (11.1, 12.1)],
            point=[(7.2, 8.6)],
            jumps=[14.3],
            blinks=[5.2, 8.9, 12.6],
        )
    )

    bubble_x = bit_x + mascot.width(px) + 18
    bubble_w = width - s.pad - 8 - bubble_x if narrow else min(500, width - s.pad - 8 - bubble_x)
    bubble_h = 74 if narrow else 64
    bubble_y = horizon + 14
    body.append(_bubble(s, bubble_x, bubble_y, bubble_w, bubble_h, 6))

    start_y = horizon + depth + 34
    body.append(_press_start(s, start_y))
    height = start_y + 30

    s.front.append(fx.crt(s.anim, width, height, T, on=(0.0, 0.8), off=CRT_OFF))

    return s.render(
        height,
        chapter=0,
        title="Jiteesh Ghodke: software engineer, system design, competitive programming",
        description=(
            "Chapter one, boot. An arcade title screen powers on: a striped neon sun rises over "
            "a scrolling city, the name Jiteesh Ghodke drops in letter by letter, and Bit the "
            "robot walks in to say the arcade is open all night."
        ),
        note="INSERT COIN",
    )
