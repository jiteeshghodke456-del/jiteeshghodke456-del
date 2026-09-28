"""CH.02 PLAYER SELECT: the character sheet.

Bit steps into the portrait frame under a rotating spotlight, and four stat bars fill one
segment at a time while slot-machine counters spin up to the real numbers. Every bar prints
its own scale next to it, because a bar with no scale is a bar that is lying about something.
Then the special moves type out, PLAYER 1 READY slams down hard enough to shake the screen,
and the whole sheet glitches out for the next chapter.
"""

from __future__ import annotations

import math

from .. import fx, mascot, scene, tokens
from ..typography import fmt

T = 14.0
GLITCH_IN = (0.0, 0.55)
GLITCH_OUT = (13.35, 14.0)
STAMP_AT = 9.7
FILL_AT = 1.0
FILL_STAGGER = 0.45
FILL_TIME = 1.7
SEGMENTS = 20

MOVES = (
    ("SYSTEM DESIGN", "draws the boxes, then asks what happens when one of them dies"),
    ("THE GRIND", "{total} Codeforces submissions, {wrong} wrong answers, zero rage quits"),
    ("SHIP IT", "a Windows desktop app, out in private beta at v1.0.6"),
)


def _stats(data: dict) -> list[dict]:
    days = int(data.get("account_age_days") or 0)
    streaks = data.get("streaks") or {}
    cf = data.get("codeforces") or {}
    own = int(data.get("repo_count") or 0)
    public = max(own, int((data.get("user") or {}).get("public_repos") or 0))
    tracked = int(streaks.get("tracked_days") or 365) or 365
    solved = int(cf.get("solved") or 0)
    attempted = max(solved, int(cf.get("attempted") or 0))
    # The account is measured in whole years, so the bar is progress through the current one
    # and the label says which year that is.
    year = days // 365 + 1
    return [
        {"key": "HP", "label": f"DAYS ON GITHUB · YEAR {year}", "value": days,
         "scale": year * 365, "unit": "", "color": tokens.ACID},
        {"key": "STA", "label": "ACTIVE DAYS THIS YEAR", "value": int(streaks.get("active_days") or 0),
         "scale": tracked, "unit": "", "color": tokens.EMERALD},
        {"key": "ATK", "label": "CF PROBLEMS SOLVED", "value": solved,
         "scale": max(1, attempted), "unit": " TRIED", "color": tokens.VIOLET},
        {"key": "INT", "label": "REPOS I WROTE", "value": own,
         "scale": max(1, public), "unit": " PUBLIC", "color": tokens.HOT_VIOLET},
    ]


def _bar(s: scene.Scene, x: float, y: float, w: float, h: float, share: float, color: str,
         start: float) -> str:
    """Twenty segments, lit one at a time, dark again only once the sheet glitches out."""
    gap = 2.0
    seg = (w - gap * (SEGMENTS - 1)) / SEGMENTS
    lit = max(0, min(SEGMENTS, round(share * SEGMENTS)))
    if share > 0 and lit == 0:
        lit = 1
    parts = [f'<rect x="{fmt(x - 3)}" y="{fmt(y - 3)}" width="{fmt(w + 6)}" height="{fmt(h + 6)}"'
             f' fill="none" stroke="{tokens.HAIRLINE}"/>']
    dim = "".join(
        f"M{fmt(x + k * (seg + gap))} {fmt(y)}h{fmt(seg)}v{fmt(h)}h{fmt(-seg)}z"
        for k in range(SEGMENTS)
    )
    parts.append(f'<path fill="{tokens.PANEL_HI}" d="{dim}"/>')
    light, base, _dark = tokens.bevel(color)
    for k in range(lit):
        at = start + FILL_TIME * (k + 1) / max(1, lit)
        cls = fx.track(s.anim, fx.windows([(at, GLITCH_OUT[0] + 0.1)], T))
        sx = x + k * (seg + gap)
        parts.append(
            fx.wrap(
                cls,
                f'<rect x="{fmt(sx)}" y="{fmt(y)}" width="{fmt(seg)}" height="{fmt(h)}" fill="{base}"/>'
                f'<rect x="{fmt(sx)}" y="{fmt(y)}" width="{fmt(seg)}" height="2" fill="{light}"/>',
            )
        )
    if lit:
        # The tip of the bar glows while it is still filling, then holds.
        tip_x = x + (lit - 1) * (seg + gap) + seg / 2
        cls = fx.track(
            s.anim,
            fx.steps([(0.0, {"opacity": "0"}), (start + FILL_TIME - fx.HOLD, {"opacity": "0"}),
                      (start + FILL_TIME, {"opacity": "0.55"}), (start + FILL_TIME + 0.6, {"opacity": "0.18"}),
                      (GLITCH_OUT[0], {"opacity": "0.18"}), (GLITCH_OUT[0] + fx.HOLD, {"opacity": "0"})], T),
            easing="ease-out",
            base={"opacity": "0.18"},
        )
        parts.append(
            f'<rect{fx.cls_attr(cls)} x="{fmt(tip_x - seg)}" y="{fmt(y - 4)}" width="{fmt(seg * 2)}"'
            f' height="{fmt(h + 8)}" rx="3" fill="{color}" opacity="0.18"/>'
        )
    return "".join(parts)


def _portrait(s: scene.Scene, x: float, y: float, w: float, h: float, px: float) -> str:
    cx, cy = x + w / 2, y + h / 2
    grid, clip = s.ids.next(), s.ids.next()
    s.defs.append(
        f'<pattern id="{grid}" width="12" height="12" patternUnits="userSpaceOnUse">'
        f'<rect width="12" height="12" fill="{tokens.PLUM}"/>'
        f'<path d="M0 0.5H12M0.5 0V12" stroke="{tokens.GRAPE}" stroke-width="1"/></pattern>'
        f'<clipPath id="{clip}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/></clipPath>'
    )
    beam_len = max(w, h)
    spin = fx.track(
        s.anim,
        [fx.Keyframe(0.0, {"transform": "rotate(0deg)"}), fx.Keyframe(T, {"transform": "rotate(360deg)"})],
        easing="linear",
    )
    beams = "".join(
        f'<path d="M0 0L{fmt(beam_len * math.cos(math.radians(a - 9)))} {fmt(beam_len * math.sin(math.radians(a - 9)))}'
        f'L{fmt(beam_len * math.cos(math.radians(a + 9)))} {fmt(beam_len * math.sin(math.radians(a + 9)))}Z"'
        f' fill="{tokens.VIOLET if i % 2 else tokens.ACID}" opacity="0.13"/>'
        for i, a in enumerate(range(0, 360, 45))
    )
    parts = [
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" fill="url(#{grid})"/>',
        f'<g clip-path="url(#{clip})">{fx.place(cx, cy + h * 0.12, spin, beams)}'
        f'<ellipse cx="{fmt(cx)}" cy="{fmt(y + h - 16)}" rx="{fmt(w * 0.32)}" ry="7" fill="{tokens.ACID}" opacity="0.18"/>'
        f'<ellipse cx="{fmt(cx)}" cy="{fmt(y + h - 16)}" rx="{fmt(w * 0.2)}" ry="4" fill="{tokens.ACID}" opacity="0.35"/></g>',
        fx.glow_rect(x, y, w, h, tokens.ACID, radius=2),
    ]
    bw, bh = mascot.width(px), mascot.height(px)
    parts.append(
        mascot.bit(
            s.anim, T, cx - bw / 2, y + h - 16 - bh + px, px,
            jumps=[0.7, STAMP_AT + 0.1],
            cheer=[(STAMP_AT, STAMP_AT + 1.4)],
            point=[(6.3, 7.3)],
            blinks=[3.1, 5.6, 8.4, 12.2],
        )
    )
    # Selector arrows either side, nudging inward like a menu waiting on a button press.
    nudge = fx.track(
        s.anim,
        fx.steps([(k * 0.35, {"transform": f"translate({fmt(4 if k % 2 else 0)}px,0px)"}) for k in range(40)], T),
    )
    back = fx.track(
        s.anim,
        fx.steps([(k * 0.35, {"transform": f"translate({fmt(-4 if k % 2 else 0)}px,0px)"}) for k in range(40)], T),
    )
    arrow = 9
    parts.append(fx.place(x - 18, cy, nudge, f'<path d="M0 {-arrow}L{arrow} 0L0 {arrow}Z" fill="{tokens.ACID}"/>'))
    parts.append(fx.place(x + w + 18, cy, back, f'<path d="M0 {-arrow}L{-arrow} 0L0 {arrow}Z" fill="{tokens.ACID}"/>'))
    badge = s.setter.text(x + 8, y + 18, "P1", face=tokens.ARCADE, size=9, fill=tokens.VOID)
    parts.append(f'<rect x="{fmt(x)}" y="{fmt(y)}" width="30" height="26" fill="{tokens.ACID}"/>' + badge)
    return "".join(parts)


def _stat_row(s: scene.Scene, stat: dict, x: float, y: float, w: float, index: int) -> tuple[str, str]:
    """Key, label, bar and a spinning counter with its scale printed after it."""
    narrow = s.narrow
    start = FILL_AT + index * FILL_STAGGER
    key_size = 10 if narrow else 12
    parts = [
        s.setter.text(x, y + 14, stat["key"], face=tokens.ARCADE, size=key_size, fill=stat["color"],
                      tracking=tokens.TRACK_ARCADE),
        s.setter.text(x + (44 if narrow else 58), y + 13, stat["label"], face=tokens.DISPLAY,
                      size=8.5 if narrow else 9.5, fill=tokens.MUTED, tracking=tokens.TRACK_LABEL),
    ]
    scale_text = f"/{stat['scale']}{stat['unit']}"
    scale_size = 9 if narrow else 10
    scale_w = s.setter.width(scale_text, tokens.MONO, scale_size)
    value = str(stat["value"])
    num_size = 14 if narrow else 16
    num_w = s.setter.width(value, tokens.ARCADE, num_size, 0)
    right = x + w
    parts.append(s.setter.text(right, y + 38, scale_text, face=tokens.MONO, size=scale_size,
                               fill=tokens.MUTED, anchor="end"))
    num_x = right - scale_w - 6 - num_w
    markup, defs = fx.drum(s.anim, s.setter, s.ids, num_x, y + 39, value, face=tokens.ARCADE,
                           size=num_size, fill=tokens.TEXT, start=start, stop=start + FILL_TIME,
                           duration=T, rewind=GLITCH_OUT[1] - GLITCH_OUT[0])
    parts.append(markup)
    bar_x = x + (44 if narrow else 58)
    bar_w = num_x - 16 - bar_x
    share = stat["value"] / stat["scale"] if stat["scale"] else 0
    parts.append(_bar(s, bar_x, y + 24, bar_w, 12 if narrow else 14, share, stat["color"], start))
    return "".join(parts), defs


def _stamp(s: scene.Scene, cx: float, cy: float, size: float) -> str:
    text = "PLAYER 1 READY"
    tw = s.setter.width(text, tokens.ARCADE, size, tokens.TRACK_ARCADE)
    w, h = tw + size * 2.2, size * 2.8
    cls = fx.track(s.anim, fx.stamp_frames(STAMP_AT, GLITCH_OUT[0] - 0.2, T), base={"opacity": "0"})
    frame = (
        f'<rect x="{fmt(-w / 2 - 6)}" y="{fmt(-h / 2 - 6)}" width="{fmt(w + 12)}" height="{fmt(h + 12)}"'
        f' fill="{tokens.VOID}" opacity="0.7"/>'
        + fx.glow_rect(-w / 2, -h / 2, w, h, tokens.ACID, stroke=3)
        + f'<rect x="{fmt(-w / 2 + 5)}" y="{fmt(-h / 2 + 5)}" width="{fmt(w - 10)}" height="{fmt(h - 10)}"'
        f' fill="none" stroke="{tokens.ACID}" stroke-width="1"/>'
        + s.setter.text(0, size * 0.5, text, face=tokens.ARCADE, size=size, fill=tokens.ACID,
                        tracking=tokens.TRACK_ARCADE, anchor="middle")
    )
    return (
        f'<g transform="translate({fmt(cx)} {fmt(cy)}) rotate(-6)">'
        + fx.wrap(cls, frame)
        + "</g>"
        + fx.burst(s.anim, cx, cy, [STAMP_AT + 0.16], T, count=18, radius=150 if not s.narrow else 110,
                   size=5, seed=21)
    )


def _moves(s: scene.Scene, data: dict, x: float, y: float, w: float) -> tuple[str, float]:
    cf = data.get("codeforces") or {}
    verdicts = cf.get("verdicts") or {}
    fill = {"total": cf.get("total", 0), "wrong": verdicts.get("WRONG_ANSWER", 0)}
    narrow = s.narrow
    parts = [s.setter.text(x, y, "SPECIAL MOVES", face=tokens.ARCADE, size=9 if narrow else 10,
                           fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE)]
    size = 11 if narrow else 12.5
    name_w = 0 if narrow else 150
    cursor_y = y + (24 if narrow else 28)
    start = 6.0
    for name, text in MOVES:
        text = text.format(**fill)
        appear = fx.track(
            s.anim,
            fx.steps([(0.0, {"opacity": "0"}), (start, {"opacity": "1"}), (GLITCH_OUT[0], {"opacity": "0"})], T),
        )
        parts.append(
            fx.wrap(appear,
                    f'<rect x="{fmt(x)}" y="{fmt(cursor_y - 8)}" width="6" height="6" fill="{tokens.ACID}"/>'
                    + s.setter.text(x + 14, cursor_y, name, face=tokens.ARCADE, size=8.5 if narrow else 9,
                                    fill=tokens.ACID, tracking=tokens.TRACK_ARCADE))
        )
        text_x = x + 14 if narrow else x + name_w
        text_y = cursor_y + 18 if narrow else cursor_y
        lines = s.setter.wrap(text, tokens.MONO, size, w - (text_x - x))
        parts.append(
            fx.typewriter(s.anim, s.setter, text_x, text_y, lines, face=tokens.MONO, size=size,
                          fill=tokens.TEXT, start=start + 0.15, end=GLITCH_OUT[0] - 0.4, duration=T,
                          cps=55, cursor=None)
        )
        start += 0.15 + len(text) / 55 + 0.25
        cursor_y = text_y + size * 1.45 * len(lines) + (12 if narrow else 10)
    return "".join(parts), cursor_y


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    s = scene.Scene(width, T, prefix="p")
    narrow = s.narrow
    left = s.pad + 8
    right = width - s.pad - 8
    stats = _stats(data)
    streaks = data.get("streaks") or {}
    content: list[str] = []

    if narrow:
        pw, ph, px = 128, 150, 5
        portrait_x, portrait_y = left + 18, 74
        content.append(_portrait(s, portrait_x, portrait_y, pw, ph, px))
        info_x = portrait_x + pw + 30
        info_y = portrait_y + 12
        stats_x, stats_y, stats_w = left, portrait_y + ph + 24, right - left
    else:
        pw, ph, px = 200, 236, 8
        portrait_x, portrait_y = left + 22, 78
        content.append(_portrait(s, portrait_x, portrait_y, pw, ph, px))
        info_x = portrait_x
        info_y = portrait_y + ph + 34
        stats_x, stats_y, stats_w = portrait_x + pw + 60, 74, right - (portrait_x + pw + 60)

    # Name plate under (wide) or beside (narrow) the portrait.
    name_size = 13 if narrow else 16
    lines = [
        (s.setter.text(info_x, info_y, "JITEESH", face=tokens.ARCADE, size=name_size, fill=tokens.TEXT,
                       tracking=tokens.TRACK_ARCADE), 0),
    ]
    facts = (("CLASS", "SYSTEMS ENGINEER"), ("GUILD", "BTECH '29"), ("SHIFT", "NIGHT"))
    fy = info_y + (22 if narrow else 26)
    for label, value in facts:
        if narrow:
            lines.append((s.setter.text(info_x, fy, label, face=tokens.DISPLAY, size=8, fill=tokens.MUTED,
                                        tracking=tokens.TRACK_LABEL), 0))
            lines.append((s.setter.text(info_x, fy + 14, value, face=tokens.MONO_SEMI, size=10.5,
                                        fill=tokens.ACID_BRIGHT), 0))
            fy += 34
        else:
            lines.append((s.setter.text(info_x, fy, label, face=tokens.DISPLAY, size=9, fill=tokens.MUTED,
                                        tracking=tokens.TRACK_LABEL), 0))
            lines.append((s.setter.text(info_x + 62, fy, value, face=tokens.MONO_SEMI, size=11.5,
                                        fill=tokens.ACID_BRIGHT), 0))
            fy += 20
    content.extend(markup for markup, _ in lines)
    info_bottom = fy

    # Stats panel.
    row_h = 50 if narrow else 54
    content.append(s.setter.text(stats_x, stats_y + 8, "STATS", face=tokens.ARCADE, size=9 if narrow else 10,
                                 fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE))
    content.append(
        s.setter.text(stats_x + stats_w, stats_y + 8, "every bar prints its scale", face=tokens.MONO,
                      size=9 if narrow else 10, fill=tokens.DIM, anchor="end")
    )
    y = stats_y + 18
    for index, stat in enumerate(stats):
        markup, defs = _stat_row(s, stat, stats_x, y, stats_w, index)
        content.append(markup)
        s.defs.append(defs)
        y += row_h

    # XP: the year's contributions as one big counter, with the best combo beside it.
    xp_y = y + 14
    total = str(int(streaks.get("total") or 0))
    xp_size = 22 if narrow else 28
    content.append(s.setter.text(stats_x, xp_y + xp_size - 4, "XP", face=tokens.ARCADE, size=xp_size * 0.55,
                                 fill=tokens.ACID, tracking=tokens.TRACK_ARCADE))
    xp_x = stats_x + xp_size * 1.5
    markup, defs = fx.drum(s.anim, s.setter, s.ids, xp_x, xp_y + xp_size, total, face=tokens.ARCADE,
                           size=xp_size, fill=tokens.ACID, start=4.0, stop=5.6, duration=T, spins=3,
                           rewind=GLITCH_OUT[1] - GLITCH_OUT[0])
    content.append(markup)
    s.defs.append(defs)
    xp_w = s.setter.width(total, tokens.ARCADE, xp_size)
    note_x = xp_x + xp_w + 14
    content.append(s.setter.text(note_x, xp_y + 12, "CONTRIBUTIONS THIS YEAR", face=tokens.DISPLAY,
                                 size=8.5 if narrow else 9.5, fill=tokens.MUTED, tracking=tokens.TRACK_LABEL))
    combo = int(streaks.get("longest") or 0)
    combo_cls = fx.track(s.anim, fx.pop_frames([5.8], T, rise=0, life=GLITCH_OUT[0] - 5.8),
                         base={"opacity": "1"})
    content.append(
        fx.wrap(combo_cls, s.setter.text(note_x, xp_y + 30, f"BEST COMBO x{combo} DAYS", face=tokens.ARCADE,
                                         size=9 if narrow else 10, fill=tokens.HOT_VIOLET,
                                         tracking=tokens.TRACK_ARCADE))
    )
    stats_bottom = xp_y + xp_size + 12

    moves_y = max(stats_bottom, info_bottom) + (22 if narrow else 26)
    moves_x = left if narrow else left + 22
    markup, bottom = _moves(s, data, moves_x, moves_y, right - moves_x)
    content.append(markup)
    height = bottom + 18

    stamp_cy = stats_y + 18 + row_h * 2
    content.append(_stamp(s, stats_x + stats_w / 2, stamp_cy, 15 if narrow else 22))

    shake = fx.track(s.anim, fx.shake_frames([STAMP_AT + 0.16], T, amp=6))
    s.body.append(fx.wrap(shake, "".join(content)))

    # Glitch in and out: torn bands over a void that snaps away, then back.
    bursts = [GLITCH_IN[0] + 0.02, GLITCH_OUT[0]]
    cover = fx.track(
        s.anim,
        fx.steps([(0.0, {"opacity": "1"}), (0.12, {"opacity": "0.6"}), (0.2, {"opacity": "1"}),
                  (0.3, {"opacity": "0.3"}), (0.38, {"opacity": "0.8"}), (GLITCH_IN[1], {"opacity": "0"}),
                  (GLITCH_OUT[0] + 0.15, {"opacity": "0.4"}), (GLITCH_OUT[0] + 0.25, {"opacity": "0"}),
                  (GLITCH_OUT[0] + 0.35, {"opacity": "0.8"}), (GLITCH_OUT[0] + 0.5, {"opacity": "1"})], T),
    )
    s.front.append(f'<rect class="{cover}" width="{width}" height="{fmt(math.ceil(height))}" fill="{tokens.VOID}" opacity="0"/>')
    s.front.append(fx.glitch_bands(s.anim, 0, 60, width, height - 60, bursts, T, count=10, seed=31))
    jitter = fx.jitter(s.anim, bursts, T, amp=10, seed=33)
    s.body[:] = [fx.wrap(jitter, "".join(s.body))]

    return s.render(
        height,
        chapter=1,
        title="Player select: Jiteesh, class systems engineer",
        description=(
            f"Chapter two, player select. Bit stands in a portrait frame beside four stat bars: "
            f"{stats[0]['value']} days on GitHub, {stats[1]['value']} active days, "
            f"{stats[2]['value']} of {stats[2]['scale']} Codeforces problems solved, and "
            f"{stats[3]['value']} repositories, then {total} contributions of XP and a PLAYER 1 READY stamp."
        ),
        note="CHOOSE YOUR FIGHTER",
    )
