"""CH.03 WORLD MAP: four projects, four worlds, one robot hopping between them.

An iris opens on World 1, Bit hops along the dotted overworld path, and whichever world he is
standing on lights up underneath. Each world is a tiny looping diorama of what the project
actually does, so a reader gets the idea before reading a word of it.

A world carries a repository only when that repository is public. Two of these are private
and say so on the card, because a link that 404s for every visitor is worse than no link.
They are still on the map, because they are real work and a reader can be told what a thing
is without being handed the source.
"""

from __future__ import annotations

import math
import random

from .. import fx, icons, mascot, scene, tokens
from ..typography import fmt

T = 16.0
PERIOD = 4.0
IRIS_OPEN = (0.0, 0.9)
IRIS_CLOSE = (15.1, 16.0)
ARRIVE = (0.0, 4.8, 8.6, 12.4)   # when Bit lands on each world
HOP = 1.0                         # two half-second jumps between worlds

WORLDS = [
    {
        "name": "ATALEIR",
        "status": "PRIVATE BETA",
        "private": True,
        "line": "Spoiler-free hints for story games, as a Windows overlay.",
        "aside": "Tells you where the key is. Never who dies.",
        "repo": None,
        "stack": ["electron", "typescript"],
        "color": tokens.ACID,
    },
    {
        "name": "ANTARCTIC NAVIGATION",
        "short": "ANTARCTIC NAV",
        "status": "PRIVATE",
        "private": True,
        "line": "Sea ice forecasting and route planning for polar research vessels.",
        "aside": "Smart India Hackathon. The ice moves faster than the schedule.",
        "repo": None,
        "stack": ["python"],
        "color": tokens.EMERALD,
    },
    {
        "name": "DRISHTI",
        "status": "HACKATHON BUILD",
        "private": False,
        "line": "Voice-first cash-flow forecasting for rural micro-enterprises.",
        "aside": "NABARD hackathon, Global Fintech Fest. Live demo below.",
        "repo": "ruraldrushtiteam5idiots",
        "stack": ["typescript", "supabase"],
        "color": tokens.VIOLET,
    },
    {
        "name": "PLOT TWIST",
        "status": "AWS BUILD",
        "private": False,
        "line": "One line of premise becomes a short story, then mutates on demand.",
        "aside": "Runs on Bedrock. The chaos slider goes to ten.",
        "repo": "awschallenge2026jiteeshghodke",
        "stack": ["javascript", "nodedotjs"],
        "color": tokens.HOT_VIOLET,
    },
]


def _cycle(points: list[tuple[float, dict]], period: float = PERIOD) -> list[tuple[float, dict]]:
    """Repeat one period's worth of points across the whole timeline."""
    out: list[tuple[float, dict]] = []
    for lap in range(int(round(T / period))):
        out += [(t + lap * period, props) for t, props in points]
    return out


def _clip(s: scene.Scene, x: float, y: float, w: float, h: float) -> str:
    ident = s.ids.next()
    s.defs.append(f'<clipPath id="{ident}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/></clipPath>')
    return ident


# --------------------------------------------------------------------------- dioramas


def _ataleir(s: scene.Scene, x: float, y: float, w: float, h: float) -> str:
    """A game window gets scanned once, a hint pops up, and the spoiler stays redacted."""
    bar = 11
    parts = [
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{tokens.PLUM}"/>',
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{bar}" fill="{tokens.GRAPE}"/>',
    ]
    for k, color in enumerate((tokens.HOT_VIOLET, tokens.VIOLET, tokens.ACID)):
        parts.append(f'<rect x="{fmt(x + 5 + k * 7)}" y="{fmt(y + 3.5)}" width="4" height="4" fill="{color}"/>')
    floor = y + h - 18
    parts.append(f'<rect x="{fmt(x)}" y="{fmt(floor)}" width="{fmt(w)}" height="2" fill="{tokens.MOSS}"/>')
    # A door, a clock on the wall, and the key hiding behind the clock.
    door_x = x + w * 0.14
    parts.append(f'<rect x="{fmt(door_x)}" y="{fmt(floor - 34)}" width="20" height="34" fill="{tokens.VIOLET_DEEP}"/>'
                 f'<rect x="{fmt(door_x + 14)}" y="{fmt(floor - 18)}" width="3" height="3" fill="{tokens.ACID}"/>')
    clock_x, clock_y = x + w * 0.62, floor - 40
    parts.append(f'<circle cx="{fmt(clock_x)}" cy="{fmt(clock_y)}" r="9" fill="{tokens.PANEL_HI}" stroke="{tokens.VIOLET_BRIGHT}" stroke-width="1.5"/>'
                 f'<path d="M{fmt(clock_x)} {fmt(clock_y)}v-6M{fmt(clock_x)} {fmt(clock_y)}h4" stroke="{tokens.VIOLET_BRIGHT}" stroke-width="1.5"/>')
    # Scan line: the overlay only ever looks at one frame, when asked.
    scan = fx.track(
        s.anim,
        fx.steps(_cycle([(0.0, {"transform": "translate(0px,0px)", "opacity": "0"}),
                         (0.3, {"transform": "translate(0px,0px)", "opacity": "1"}),
                         (1.0, {"transform": f"translate(0px,{fmt(h - bar - 2)}px)", "opacity": "1"}),
                         (1.01, {"transform": f"translate(0px,{fmt(h - bar - 2)}px)", "opacity": "0"})]), T),
        easing="linear",
        base={"opacity": "0"},
    )
    parts.append(fx.place(x, y + bar, scan,
                          f'<rect width="{fmt(w)}" height="2" fill="{tokens.ACID}"/>'
                          f'<rect y="-6" width="{fmt(w)}" height="6" fill="{tokens.ACID}" opacity="0.15"/>'))
    # The ring that finds the key, then the hint.
    ring = fx.track(
        s.anim,
        fx.steps(_cycle([(0.0, {"transform": "scale(2.4)", "opacity": "0"}),
                         (1.0, {"transform": "scale(2.4)", "opacity": "1"}),
                         (1.3, {"transform": "scale(1)", "opacity": "1"}),
                         (3.6, {"transform": "scale(1)", "opacity": "1"}),
                         (3.7, {"transform": "scale(1)", "opacity": "0"})]), T),
        easing=fx.EASE_OUT,
    )
    parts.append(fx.place(clock_x, clock_y, ring,
                          f'<circle r="13" fill="none" stroke="{tokens.ACID}" stroke-width="1.5" stroke-dasharray="3 3"/>'))
    hint_w = min(w - 12, s.setter.width("look behind the clock", tokens.MONO, 7.5) + 12)
    hint_h = 26
    hint_x, hint_y = x + w - hint_w - 6, y + bar + 6
    pop = fx.track(
        s.anim,
        fx.steps(_cycle([(0.0, {"transform": "scale(0.001)", "opacity": "0"}),
                         (1.35, {"transform": "scale(0.001)", "opacity": "0"}),
                         (1.45, {"transform": "scale(1.1)", "opacity": "1"}),
                         (1.55, {"transform": "scale(1)", "opacity": "1"}),
                         (3.7, {"transform": "scale(1)", "opacity": "1"}),
                         (3.8, {"transform": "scale(0.001)", "opacity": "0"})]), T),
    )
    hint = (
        f'<rect width="{fmt(hint_w)}" height="{hint_h}" fill="{tokens.PANEL}" stroke="{tokens.ACID}"/>'
        + s.setter.text(6, 10, "HINT", face=tokens.ARCADE, size=6, fill=tokens.ACID)
        + s.setter.text(6, 21, "look behind the clock", face=tokens.MONO, size=7.5, fill=tokens.TEXT)
    )
    parts.append(fx.place(hint_x, hint_y, pop, hint))
    # The spoiler, forever redacted, flickering like it wants out.
    red_y = y + h - 11
    flick = fx.track(s.anim, fx.flicker_frames((1.9, 5.9, 9.9, 13.9), T))
    parts.append(s.setter.text(x + 6, red_y + 5, "who dies:", face=tokens.MONO, size=7.5, fill=tokens.MUTED))
    parts.append(f'<rect{fx.cls_attr(flick)} x="{fmt(x + 52)}" y="{fmt(red_y - 2)}" width="{fmt(w - 60)}" height="8" fill="{tokens.VIOLET}"/>')
    parts.append(fx.glow_rect(x, y, w, h, tokens.ACID, spread=((4, 0.1),), stroke=1))
    return f'<g clip-path="url(#{_clip(s, x - 3, y - 3, w + 6, h + 6)})">{"".join(parts)}</g>'


def _antarctic(s: scene.Scene, x: float, y: float, w: float, h: float) -> str:
    """Ice floes drift past while a ship plots a route between them, dot by dot."""
    sea = s.ids.next()
    s.defs.append(
        f'<pattern id="{sea}" width="14" height="14" patternUnits="userSpaceOnUse">'
        f'<rect width="14" height="14" fill="{tokens.PLUM}"/>'
        f'<path d="M0 0.5H14M0.5 0V14" stroke="{tokens.FOREST}" stroke-width="1"/></pattern>'
    )
    parts = [f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="url(#{sea})"/>']
    rng = random.Random(61)
    floes = []
    for k in range(6):
        fx0 = (k + 0.3) * w / 6 + rng.uniform(-6, 6)
        fy0 = rng.uniform(10, h - 16)
        r = rng.uniform(7, 13)
        pts = []
        for j in range(6):
            a = j * math.tau / 6 + rng.uniform(-0.3, 0.3)
            rr = r * rng.uniform(0.7, 1.1)
            pts.append(f"{fmt(fx0 + math.cos(a) * rr)} {fmt(fy0 + math.sin(a) * rr * 0.7)}")
        floes.append("M" + "L".join(pts) + "Z")
    floe_markup = (f'<path d="{"".join(floes)}" fill="{tokens.TEXT}" opacity="0.85"/>'
                   f'<path d="{"".join(floes)}" fill="none" stroke="{tokens.EMERALD}" stroke-width="1" opacity="0.6"/>')
    markup, defs = fx.marquee(s.anim, s.ids, floe_markup, w, x, y, w, h, T, reverse=False)
    s.defs.append(defs)
    parts.append(markup)
    # Route: dots appear one at a time from the ship's berth to the research station.
    route = [(0.1, 0.85), (0.22, 0.62), (0.36, 0.7), (0.48, 0.45), (0.6, 0.52), (0.7, 0.3),
             (0.8, 0.36), (0.9, 0.18)]
    route = [(x + rx * w, y + ry * h) for rx, ry in route]
    for k, (dx, dy) in enumerate(route[1:-1], start=1):
        at = 0.4 + k * 0.28
        cls = fx.track(s.anim, fx.steps(_cycle([(0.0, {"opacity": "0"}), (at, {"opacity": "1"}),
                                                  (3.6, {"opacity": "0"})]), T))
        parts.append(f'<rect{fx.cls_attr(cls)} x="{fmt(dx - 1.5)}" y="{fmt(dy - 1.5)}" width="3" height="3" fill="{tokens.ACID}"/>')
    flag_x, flag_y = route[-1]
    parts.append(f'<path d="M{fmt(flag_x)} {fmt(flag_y + 8)}v-16h9l-3 4l3 4h-9" fill="{tokens.HOT_VIOLET}" stroke="{tokens.HOT_VIOLET}" stroke-width="1"/>')
    points: list[tuple[float, dict]] = []
    sx, sy = route[0]
    for k, (dx, dy) in enumerate(route):
        points.append((0.4 + k * 0.28, {"transform": f"translate({fmt(dx - sx)}px,{fmt(dy - sy)}px)"}))
    points.insert(0, (0.0, {"transform": "translate(0px,0px)"}))
    points.append((3.7, {"transform": "translate(0px,0px)"}))
    ship = fx.track(s.anim, fx.steps(_cycle(points), T), easing="ease-in-out")
    hull = (f'<path d="M-7 0h14l-3 4h-8z" fill="{tokens.ACID}"/>'
            f'<rect x="-3" y="-5" width="6" height="5" fill="{tokens.TEXT}"/>'
            f'<rect x="-1" y="-9" width="2" height="4" fill="{tokens.HOT_VIOLET}"/>')
    parts.append(fx.place(sx, sy, ship, hull))
    parts.append(s.setter.text(x + 6, y + 12, "ICE 71%", face=tokens.ARCADE, size=6, fill=tokens.EMERALD))
    parts.append(fx.glow_rect(x, y, w, h, tokens.EMERALD, spread=((4, 0.1),), stroke=1))
    return f'<g clip-path="url(#{_clip(s, x - 3, y - 3, w + 6, h + 6)})">{"".join(parts)}</g>'


def _drishti(s: scene.Scene, x: float, y: float, w: float, h: float) -> str:
    """A shopkeeper's voice note, then the same bars as a cash-flow forecast."""
    parts = [f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{tokens.PLUM}"/>']
    count = 12
    base_y = y + h - 16
    inner_x = x + 12
    gap = 3
    bw = (w - 24 - gap * (count - 1)) / count
    full = h - 40
    rng = random.Random(77)
    chart = [0.22, 0.3, 0.26, 0.38, 0.35, 0.48, 0.44, 0.58, 0.55, 0.7, 0.78, 0.92]
    for k in range(count):
        points: list[tuple[float, dict]] = []
        t = 0.0
        while t < 1.9:
            level = 0.15 + rng.random() * 0.8 * math.sin((k + 1) / (count + 1) * math.pi)
            points.append((t, {"transform": f"scale(1,{fmt(max(0.08, level))})", "fill": tokens.VIOLET}))
            t += 0.12
        points.append((2.0 + k * 0.04, {"transform": f"scale(1,{fmt(chart[k])})", "fill": tokens.ACID}))
        points.append((3.8, {"transform": f"scale(1,{fmt(chart[k])})", "fill": tokens.ACID}))
        cls = fx.track(s.anim, fx.steps(_cycle(points), T))
        parts.append(fx.place(inner_x + k * (bw + gap), base_y, cls,
                              f'<rect x="0" y="{fmt(-full)}" width="{fmt(bw)}" height="{fmt(full)}" fill="{tokens.VIOLET}"/>'))
    parts.append(f'<rect x="{fmt(x + 8)}" y="{fmt(base_y)}" width="{fmt(w - 16)}" height="1" fill="{tokens.MUTED}"/>')
    voice = fx.track(s.anim, fx.windows([(k * PERIOD, k * PERIOD + 2.0) for k in range(4)], T))
    cash = fx.track(s.anim, fx.windows([(k * PERIOD + 2.0, k * PERIOD + 4.0) for k in range(4)], T),
                    base={"opacity": "0"})
    parts.append(fx.wrap(voice, s.setter.text(x + 8, y + 13, "VOICE NOTE", face=tokens.ARCADE, size=6,
                                              fill=tokens.VIOLET_BRIGHT)
                         + f'<circle cx="{fmt(x + w - 12)}" cy="{fmt(y + 10)}" r="3.5" fill="{tokens.HOT_VIOLET}"/>'))
    parts.append(fx.wrap(cash, s.setter.text(x + 8, y + 13, "NEXT 30 DAYS", face=tokens.ARCADE, size=6,
                                             fill=tokens.ACID)
                         + s.setter.text(x + w - 8, y + 13, "+18%", face=tokens.ARCADE, size=6, fill=tokens.ACID,
                                         anchor="end")))
    parts.append(fx.glow_rect(x, y, w, h, tokens.VIOLET, spread=((4, 0.1),), stroke=1))
    return f'<g clip-path="url(#{_clip(s, x - 3, y - 3, w + 6, h + 6)})">{"".join(parts)}</g>'


def _plot_twist(s: scene.Scene, x: float, y: float, w: float, h: float) -> str:
    """The chaos slider slams to ten and the story rewrites itself in a panic."""
    parts = [f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="{tokens.PLUM}"/>']
    rng = random.Random(89)
    lines_y = [y + 12 + k * 11 for k in range(5)]
    story = []
    for k, ly in enumerate(lines_y):
        lw = (w - 20) * rng.uniform(0.55, 1.0)
        story.append(f"M{fmt(x + 10)} {fmt(ly)}h{fmt(lw)}v4h{fmt(-lw)}z")
    slam = 1.5
    calm = [(0.0, {"transform": "translate(0px,0px)", "fill": tokens.MUTED})]
    for k in range(8):
        t = slam + k * 0.2
        calm.append((t, {"transform": f"translate({fmt(rng.uniform(-5, 5))}px,{fmt(rng.uniform(-1.5, 1.5))}px)",
                         "fill": (tokens.HOT_VIOLET, tokens.ACID, tokens.VIOLET_BRIGHT)[k % 3]}))
    calm.append((slam + 1.7, {"transform": "translate(0px,0px)", "fill": tokens.TEXT}))
    calm.append((3.7, {"transform": "translate(0px,0px)", "fill": tokens.MUTED}))
    cls = fx.track(s.anim, fx.steps(_cycle(calm), T))
    parts.append(f'<path{fx.cls_attr(cls)} fill="{tokens.MUTED}" d="{"".join(story)}"/>')
    # Slider.
    track_y = y + h - 16
    tx0, tx1 = x + 44, x + w - 30
    parts.append(s.setter.text(x + 8, track_y + 3, "CHAOS", face=tokens.ARCADE, size=5.5, fill=tokens.HOT_VIOLET))
    parts.append(f'<rect x="{fmt(tx0)}" y="{fmt(track_y - 1)}" width="{fmt(tx1 - tx0)}" height="2" fill="{tokens.GRAPE}"/>')
    ticks = "".join(f"M{fmt(tx0 + (tx1 - tx0) * k / 9)} {fmt(track_y + 3)}v3" for k in range(10))
    parts.append(f'<path d="{ticks}" stroke="{tokens.DIM}" stroke-width="1"/>')
    knob = fx.track(
        s.anim,
        fx.steps(_cycle([(0.0, {"transform": "translate(0px,0px)"}), (1.0, {"transform": "translate(0px,0px)"}),
                         (slam, {"transform": f"translate({fmt(tx1 - tx0)}px,0px)"}),
                         (3.3, {"transform": f"translate({fmt(tx1 - tx0)}px,0px)"}),
                         (3.8, {"transform": "translate(0px,0px)"})]), T),
        easing="cubic-bezier(0.7,0,0.9,0.4)",
    )
    parts.append(fx.place(tx0, track_y, knob,
                          f'<rect x="-4" y="-6" width="8" height="12" fill="{tokens.HOT_VIOLET}"/>'
                          f'<rect x="-2" y="-4" width="4" height="8" fill="{tokens.TEXT}"/>'))
    one = fx.track(s.anim, fx.windows([(k * PERIOD + slam, k * PERIOD + 3.5) for k in range(4)], T,
                                      on="0", off="1"))
    ten = fx.track(s.anim, fx.windows([(k * PERIOD + slam, k * PERIOD + 3.5) for k in range(4)], T),
                   base={"opacity": "0"})
    parts.append(fx.wrap(one, s.setter.text(x + w - 8, track_y + 3, "1", face=tokens.ARCADE, size=7,
                                            fill=tokens.MUTED, anchor="end")))
    parts.append(fx.wrap(ten, s.setter.text(x + w - 6, track_y + 3, "10", face=tokens.ARCADE, size=7,
                                            fill=tokens.HOT_VIOLET, anchor="end")))
    parts.append(fx.burst(s.anim, tx1, track_y, [k * PERIOD + slam for k in range(4)], T, count=8, radius=22,
                          size=3, life=0.5, seed=91))
    parts.append(fx.glow_rect(x, y, w, h, tokens.HOT_VIOLET, spread=((4, 0.1),), stroke=1))
    return f'<g clip-path="url(#{_clip(s, x - 3, y - 3, w + 6, h + 6)})">{"".join(parts)}</g>'


DIORAMAS = (_ataleir, _antarctic, _drishti, _plot_twist)


# --------------------------------------------------------------------------- map and cards


def _presence(index: int) -> list[tuple[float, float]]:
    """When Bit is standing on world ``index``, which is when its card is lit."""
    start = ARRIVE[index]
    end = ARRIVE[index + 1] - HOP if index + 1 < len(ARRIVE) else T
    return [(start, end)]


def _pill_width(s: scene.Scene, text: str) -> float:
    return s.setter.width(text, tokens.DISPLAY, 7.5, tokens.TRACK_LABEL) + 16


def _card(s: scene.Scene, index: int, world: dict, x: float, y: float, w: float, h: float) -> str:
    narrow = s.narrow
    color = world["color"]
    parts = [f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="6" fill="{tokens.PANEL}"'
             f' stroke="{tokens.HAIRLINE}"/>']
    # Lit while Bit stands on this world.
    spans = _presence(index)
    lit = fx.track(s.anim, fx.windows(spans, T))
    here = fx.glow_rect(x, y, w, h, color, radius=6, stroke=1.5)
    here += s.setter.text(x + w - 10, y + 16, "YOU ARE HERE", face=tokens.ARCADE, size=6, fill=color, anchor="end")
    parts.append(fx.wrap(lit, here, hidden=index != 0))
    dw, dh = (126, h - 24) if narrow else (164, h - 28)
    parts.append(DIORAMAS[index](s, x + 12, y + (h - dh) / 2, dw, dh))
    tx = x + 12 + dw + 14
    tw = x + w - 12 - tx
    ty = y + 30
    label = f"W{index + 1}"
    parts.append(s.setter.text(tx, ty, label, face=tokens.ARCADE, size=8, fill=color))
    name_size = 9.5 if narrow else 10.5
    name = world["name"]
    if s.setter.width(name, tokens.ARCADE, name_size, tokens.TRACK_ARCADE) > tw - 26:
        name = world.get("short", name)
    parts.append(s.setter.text(tx + 26, ty, name, face=tokens.ARCADE, size=name_size, fill=tokens.TEXT,
                               tracking=tokens.TRACK_ARCADE))
    pill_y = ty + 20
    status = world["status"]
    pw = _pill_width(s, status)
    parts.append(
        f'<rect x="{fmt(tx)}" y="{fmt(pill_y - 10)}" width="{fmt(pw)}" height="15" rx="7.5" fill="{color}" opacity="0.14"/>'
        f'<rect x="{fmt(tx)}" y="{fmt(pill_y - 10)}" width="{fmt(pw)}" height="15" rx="7.5" fill="none" stroke="{color}" opacity="0.5"/>'
        + s.setter.text(tx + 8, pill_y + 1, status, face=tokens.DISPLAY, size=7.5, fill=color, tracking=tokens.TRACK_LABEL)
    )
    access = "SOURCE PRIVATE" if world["private"] else "LINK BELOW"
    parts.append(s.setter.text(tx + pw + 8, pill_y + 1, access, face=tokens.DISPLAY, size=7,
                               fill=tokens.DIM if world["private"] else tokens.ACID_BRIGHT, tracking=tokens.TRACK_LABEL))
    size = 10 if narrow else 11
    cursor = pill_y + 20
    for line in s.setter.wrap(world["line"], tokens.MONO, size, tw)[:3]:
        parts.append(s.setter.text(tx, cursor, line, face=tokens.MONO, size=size, fill=tokens.TEXT))
        cursor += size * 1.4
    if not narrow:
        for line in s.setter.wrap(world["aside"], tokens.MONO, size - 1, tw)[:2]:
            parts.append(s.setter.text(tx, cursor + 2, line, face=tokens.MONO, size=size - 1, fill=tokens.MUTED))
            cursor += (size - 1) * 1.4
    ix = tx
    iy = y + h - 26
    for slug in world["stack"]:
        if not icons.has(slug):
            continue
        parts.append(icons.icon(slug, ix, iy, 12, fill=tokens.MUTED))
        lab = icons.label(slug)
        parts.append(s.setter.text(ix + 17, iy + 10, lab, face=tokens.MONO, size=9, fill=tokens.MUTED))
        ix += 17 + s.setter.width(lab, tokens.MONO, 9) + 14
    return "".join(parts)


def _map(s: scene.Scene, nodes: list[tuple[float, float]], px: float) -> str:
    parts: list[str] = []
    # The dotted road between worlds, drawn as little squares.
    dots = []
    for (x0, y0), (x1, y1) in zip(nodes, nodes[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        steps = int(length / 11)
        for k in range(1, steps):
            f = k / steps
            bump = math.sin(f * math.pi) * -14
            dots.append(f"M{fmt(x0 + (x1 - x0) * f - 1.5)} {fmt(y0 + (y1 - y0) * f + bump - 1.5)}h3v3h-3z")
    parts.append(f'<path d="{"".join(dots)}" fill="{tokens.VIOLET}" opacity="0.7"/>')
    for index, ((nx, ny), world) in enumerate(zip(nodes, WORLDS)):
        color = world["color"]
        spans = _presence(index)
        pulse_points: list[tuple[float, dict]] = [(0.0, {"transform": "scale(1)", "opacity": "0"})]
        for start, end in spans:
            t = start
            while t < end - 0.8:
                pulse_points += [(t, {"transform": "scale(1)", "opacity": "0.9"}),
                                 (t + 0.8, {"transform": "scale(2.6)", "opacity": "0"}),
                                 (t + 0.81, {"transform": "scale(1)", "opacity": "0"})]
                t += 1.0
        cls = fx.track(s.anim, fx.steps(pulse_points, T), easing="ease-out", base={"opacity": "0"})
        parts.append(fx.place(nx, ny, cls, f'<ellipse rx="10" ry="4" fill="none" stroke="{color}" stroke-width="1.5"/>'))
        parts.append(
            f'<ellipse cx="{fmt(nx)}" cy="{fmt(ny)}" rx="14" ry="5.5" fill="{color}" opacity="0.2"/>'
            f'<ellipse cx="{fmt(nx)}" cy="{fmt(ny)}" rx="9" ry="3.5" fill="{color}"/>'
            f'<ellipse cx="{fmt(nx)}" cy="{fmt(ny - 1)}" rx="5" ry="1.5" fill="#FFFFFF" opacity="0.5"/>'
        )
        parts.append(s.setter.text(nx, ny + 20, f"W{index + 1}", face=tokens.ARCADE, size=8, fill=color, anchor="middle"))
        # A flag on every world, raised once Bit has visited.
        raised = ARRIVE[index] + 0.1
        flag = fx.track(
            s.anim,
            fx.steps([(0.0, {"transform": "scale(1,0.001)"}), (raised, {"transform": "scale(1,1)"}),
                      (IRIS_CLOSE[1] - 0.01, {"transform": "scale(1,1)"})], T),
        ) if index else None
        pole_x = nx + 16
        parts.append(f'<rect x="{fmt(pole_x)}" y="{fmt(ny - 26)}" width="1.5" height="26" fill="{tokens.MUTED}"/>')
        parts.append(fx.place(pole_x + 1.5, ny - 26, flag,
                              f'<path d="M0 0h11l-3 4l3 4h-11z" fill="{color}"/>'))

    # Bit: horizontal travel on the outer group, the hop arc from his own jump.
    bw, bh = mascot.width(px), mascot.height(px)
    home_x, home_y = nodes[0]
    points: list[tuple[float, dict]] = []
    for index in range(1, len(nodes)):
        start = ARRIVE[index] - HOP
        (x0, y0), (x1, y1) = nodes[index - 1], nodes[index]
        samples = 20
        for k in range(samples + 1):
            f = k / samples
            dx = x0 + (x1 - x0) * f - home_x
            dy = y0 + (y1 - y0) * f - home_y
            points.append((start + HOP * f, {"transform": f"translate({fmt(round(dx))}px,{fmt(round(dy))}px)"}))
    points.insert(0, (0.0, {"transform": "translate(0px,0px)"}))
    last_x, last_y = nodes[-1][0] - home_x, nodes[-1][1] - home_y
    points.append((T - 0.01, {"transform": f"translate({fmt(last_x)}px,{fmt(last_y)}px)"}))
    travel = fx.track(s.anim, fx.steps(points, T))
    jumps = [ARRIVE[i] - HOP + k * 0.5 for i in range(1, len(nodes)) for k in range(2)]
    sprite = mascot.bit(s.anim, T, home_x - bw / 2, home_y - bh + px, px, jumps=jumps,
                        wave=[(ARRIVE[3] + 0.3, ARRIVE[3] + 1.6)], blinks=[2.2, 6.5, 10.1, 14.0], bob=0.5)
    parts.append(fx.wrap(travel, sprite))
    return "".join(parts)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    s = scene.Scene(width, T, prefix="w")
    narrow = s.narrow
    left = s.pad + 8
    right = width - s.pad - 8

    if narrow:
        map_y = 128
        xs = [left + 34 + k * (right - left - 68) / 3 for k in range(4)]
        nodes = [(nx, map_y + (8 if k % 2 else 0)) for k, nx in enumerate(xs)]
        px = 3
    else:
        map_y = 150
        xs = [left + 90 + k * (right - left - 180) / 3 for k in range(4)]
        nodes = [(nx, map_y + (10 if k % 2 else -4)) for k, nx in enumerate(xs)]
        px = 3
    # Terrain strip behind the road: violet hills far, green hills near.
    horizon = map_y + 28
    rng = random.Random(5)
    far = [f"M0 {fmt(horizon)}"]
    near = [f"M0 {fmt(horizon + 8)}"]
    for k in range(0, width + 40, 40):
        far.append(f"L{k} {fmt(horizon - rng.uniform(8, 26))}")
        near.append(f"L{k + 20} {fmt(horizon + 8 - rng.uniform(2, 12))}")
    far.append(f"L{width} {fmt(horizon + 30)}L0 {fmt(horizon + 30)}Z")
    near.append(f"L{width} {fmt(horizon + 30)}L0 {fmt(horizon + 30)}Z")
    s.body.append(f'<path d="{"".join(far)}" fill="{tokens.GRAPE}" opacity="0.7"/>')
    s.body.append(f'<path d="{"".join(near)}" fill="{tokens.FOREST}"/>')
    s.body.append(f'<rect x="0" y="{fmt(horizon + 30)}" width="{width}" height="1" fill="{tokens.MOSS}"/>')
    s.body.append(s.setter.text(left, 74, "PICK A WORLD", face=tokens.ARCADE, size=9 if narrow else 10,
                                fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE))
    s.body.append(s.setter.text(right, 74, "4 WORLDS · 2 PUBLIC · 2 PRIVATE", face=tokens.MONO,
                                size=9 if narrow else 10, fill=tokens.MUTED, anchor="end"))
    s.body.append(_map(s, nodes, px))

    top = horizon + 46
    gap = 14
    if narrow:
        cw, ch = right - left, 150
        for index, world in enumerate(WORLDS):
            s.body.append(_card(s, index, world, left, top + index * (ch + gap), cw, ch))
        height = top + 4 * (ch + gap) + 10
    else:
        cw, ch = (right - left - gap) / 2, 176
        for index, world in enumerate(WORLDS):
            col, row = index % 2, index // 2
            s.body.append(_card(s, index, world, left + col * (cw + gap), top + row * (ch + gap), cw, ch))
        height = top + 2 * (ch + gap) + 10

    s.front.append(fx.iris(s.anim, nodes[0][0], nodes[0][1] - 20, width, height, T,
                           opening=IRIS_OPEN, closing=None))
    s.front.append(fx.iris(s.anim, nodes[-1][0], nodes[-1][1] - 20, width, height, T,
                           opening=None, closing=IRIS_CLOSE))

    return s.render(
        height,
        chapter=2,
        title="World map: Ataleir, Antarctic Navigation, Drishti, Plot Twist",
        description=(
            "Chapter three, world map. Bit hops across four worlds, one per project: Ataleir, a "
            "spoiler-free hint overlay for story games; Antarctic Navigation, sea ice forecasting "
            "for polar ships; Drishti, voice-first cash-flow forecasting; and Plot Twist, a story "
            "generator with a chaos slider."
        ),
    )
