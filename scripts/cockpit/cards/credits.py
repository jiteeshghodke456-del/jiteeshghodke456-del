"""CH.07 CREDITS: PLAYER 2 WANTED.

The one action on the page, dressed as the continue screen: Bit waves, a countdown runs
from nine, and the ways to join in are printed as the controls. The end credits roll beside
it, written from the same data as every chapter above, and the card finishes on THANKS FOR
PLAYING before the tube powers off, which is exactly where the boot screen at the top of the
page powers on.

The ask itself never animates out. Whatever frame a reader lands on, the way to reach me is
on screen.
"""

from __future__ import annotations

import math

from profilegen.svg import pixelfont as pf

from .. import fx, mascot, scene, tokens
from ..typography import fmt

T = 16.0
COUNT_FROM = 1.2
CRT_ON = (0.0, 0.7)
CRT_OFF = (15.3, 16.0)
THANKS_AT = 13.2

CONTROLS = (
    ("INSERT COIN", "open an issue on this repo"),
    ("2P LINK", "find Jiteesh on LinkedIn"),
    ("CO-OP", "freelance, open source, system design"),
)


def _credits(data: dict) -> list[tuple[str, str]]:
    cf = data.get("codeforces") or {}
    profile = data.get("codeforces_profile") or {}
    streaks = data.get("streaks") or {}
    rows: list[tuple[str, str]] = [
        ("STARRING", "Jiteesh Ghodke"),
        ("AND", "Bit, the robot"),
        ("SNAKE PATHFINDING", "a Hamiltonian cycle"),
    ]
    attempts: dict[str, list[str]] = {}
    for submission in data.get("codeforces_submissions") or []:
        problem = submission.get("problem") or {}
        key = f"{problem.get('contestId')}{problem.get('index')}"
        attempts.setdefault(key, []).append(submission.get("verdict") or "")
    if attempts:
        name = max(attempts, key=lambda key: len(attempts[key]))
        wrong = attempts[name].count("WRONG_ANSWER")
        tries = len(attempts[name])
        rows.append((f"PROBLEM {name}", f"{tries} attempt{'s' * (tries != 1)}, "
                                        f"{wrong} regret{'s' * (wrong != 1)}"))
    total = int(cf.get("total") or 0)
    accepted = int(cf.get("accepted") or 0)
    if total:
        rows.append(("THE JUDGE", f"still standing at {round((1 - accepted / total) * 100)}% HP"))
    if profile.get("rating"):
        history = [int(c.get("new") or 0) for c in profile.get("contests") or []]
        climbing = len(history) > 1 and all(b > a for a, b in zip(history, history[1:]))
        rows.append(("RATING", f"{profile['rating']}, and it has never gone down" if climbing
                     else f"{profile['rating']}, and climbing"))
    rows += [
        ("XP", f"{int(streaks.get('total') or 0)} contributions this year"),
        ("LEVEL DESIGN", "system design, mostly at 2 a.m."),
        ("TYPE", "vector outlines, so it looks the same on your screen"),
        ("STAT CARDS", "none, everything here is drawn by one Python script"),
        ("BUGS", "also Jiteesh"),
        ("", "THANKS FOR PLAYING"),
    ]
    return rows


def _roll(s: scene.Scene, x: float, y: float, w: float, h: float, rows: list[tuple[str, str]]) -> str:
    """End credits scrolling upward forever, seamlessly, inside a window."""
    narrow = s.narrow
    role_size = 7.5 if narrow else 8.5
    name_size = 10.5 if narrow else 12
    cx = w / 2
    lines: list[str] = []
    cursor = 0.0
    for role, name in rows:
        if role:
            lines.append(s.setter.text(cx, cursor + role_size, role, face=tokens.ARCADE, size=role_size,
                                       fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE, anchor="middle"))
            cursor += role_size + 10
            for line in s.setter.wrap(name, tokens.MONO_SEMI, name_size, w - 20):
                lines.append(s.setter.text(cx, cursor + name_size, line, face=tokens.MONO_SEMI, size=name_size,
                                           fill=tokens.TEXT, anchor="middle"))
                cursor += name_size * 1.4
        else:
            cursor += 8
            lines.append(s.setter.text(cx, cursor + 14, name, face=tokens.ARCADE, size=11 if narrow else 13,
                                       fill=tokens.ACID, tracking=tokens.TRACK_ARCADE, anchor="middle"))
            cursor += 20
        cursor += 22
    content_h = max(cursor + 40, h)
    strip = "".join(lines)
    copies = (
        f'<g>{strip}</g><g transform="translate(0 {fmt(content_h)})">{strip}</g>'
    )
    cls = fx.track(s.anim, [fx.Keyframe(0.0, {"transform": "translate(0px,0px)"}),
                            fx.Keyframe(T, {"transform": f"translate(0px,{fmt(-content_h)}px)"})], easing="linear")
    clip, fade = s.ids.next(), s.ids.next()
    s.defs.append(
        f'<clipPath id="{clip}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/></clipPath>'
        f'<linearGradient id="{fade}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{tokens.PANEL}" stop-opacity="1"/>'
        f'<stop offset="0.14" stop-color="{tokens.PANEL}" stop-opacity="0"/>'
        f'<stop offset="0.86" stop-color="{tokens.PANEL}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{tokens.PANEL}" stop-opacity="1"/></linearGradient>'
    )
    return (
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="6" fill="{tokens.PANEL}" stroke="{tokens.HAIRLINE}"/>'
        f'<g clip-path="url(#{clip})"><g transform="translate({fmt(x)} {fmt(y + h * 0.35)})">{fx.wrap(cls, copies)}</g></g>'
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="6" fill="url(#{fade})"/>'
        f'<rect x="{fmt(x + 1)}" y="{fmt(y + 1)}" width="{fmt(w - 2)}" height="24" rx="5" fill="{tokens.PANEL_HI}"/>'
        f'<rect x="{fmt(x + 1)}" y="{fmt(y + 25)}" width="{fmt(w - 2)}" height="1" fill="{tokens.HAIRLINE}"/>'
        + s.setter.text(x + 12, y + 17, "END CREDITS", face=tokens.ARCADE, size=7, fill=tokens.MUTED,
                        tracking=tokens.TRACK_ARCADE)
        + s.setter.text(x + w - 12, y + 17, "ROLLING", face=tokens.ARCADE, size=7, fill=tokens.ACID,
                        tracking=tokens.TRACK_ARCADE, anchor="end")
    )


def _coin(s: scene.Scene, cx: float, cy: float, r: float) -> str:
    """A coin spinning on its edge: scaled flat and back, face swapping as it turns."""
    points = []
    for k in range(int(T / 0.1) + 1):
        t = k * 0.1
        sx = abs(round(math.cos(t * 5.0), 2))
        points.append((min(T, t), {"transform": f"scale({fmt(max(0.06, sx))},1)"}))
    cls = fx.track(s.anim, fx.steps(points, T))
    face = (
        f'<circle r="{fmt(r)}" fill="{tokens.ACID_DEEP}"/>'
        f'<circle r="{fmt(r - 2)}" fill="{tokens.ACID}"/>'
        f'<rect x="{fmt(-r * 0.18)}" y="{fmt(-r * 0.55)}" width="{fmt(r * 0.36)}" height="{fmt(r * 1.1)}" fill="{tokens.ACID_DEEP}"/>'
    )
    return fx.place(cx, cy, cls, face)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    s = scene.Scene(width, T, prefix="c")
    narrow = s.narrow
    left = s.pad + 8
    right = width - s.pad - 8
    top = 70

    if narrow:
        panel_w = right - left
        roll_x, roll_y, roll_w, roll_h = left, None, right - left, 230
    else:
        panel_w = (right - left) * 0.56
        roll_x = left + panel_w + 20
        roll_w = right - roll_x
        roll_y, roll_h = top, None

    # --- PLAYER 2 WANTED -------------------------------------------------------------------
    title_size = 17 if narrow else 24
    flick = fx.track(s.anim, fx.flicker_frames((2.6, 7.4, 11.9), T))
    title_y = top + title_size + 8
    title = s.setter.text(left, title_y, "PLAYER 2", face=tokens.ARCADE, size=title_size, fill=tokens.HOT_VIOLET,
                          tracking=tokens.TRACK_ARCADE)
    title2 = s.setter.text(left, title_y + title_size * 1.35, "WANTED", face=tokens.ARCADE, size=title_size,
                           fill=tokens.ACID, tracking=tokens.TRACK_ARCADE)
    ghost = s.setter.text(left + 2, title_y + 2, "PLAYER 2", face=tokens.ARCADE, size=title_size,
                          fill=tokens.VIOLET_DEEP, tracking=tokens.TRACK_ARCADE)
    ghost2 = s.setter.text(left + 2, title_y + title_size * 1.35 + 2, "WANTED", face=tokens.ARCADE, size=title_size,
                           fill=tokens.ACID_DEEP, tracking=tokens.TRACK_ARCADE)
    s.body.append(ghost + ghost2 + fx.wrap(flick, title) + title2)

    # Bit waves from beside the title.
    px = 4 if not narrow else 3
    title_w = s.setter.width("PLAYER 2", tokens.ARCADE, title_size, tokens.TRACK_ARCADE)
    bit_x = left + title_w + (26 if not narrow else 18)
    bit_y = title_y + title_size * 1.35 - mascot.height(px) + 2
    s.body.append(mascot.bit(s.anim, T, bit_x, bit_y, px,
                             wave=[(1.0, 3.2), (6.0, 7.6), (10.2, 11.6)], jumps=[THANKS_AT + 0.1],
                             cheer=[(THANKS_AT + 0.1, THANKS_AT + 1.6)], blinks=[4.2, 8.8, 12.5]))

    seek_y = title_y + title_size * 1.35 + 28
    ask_size = 11 if narrow else 12.5
    ask = "Looking for a software engineering internship."
    ask_lines = s.setter.wrap(ask, tokens.MONO, ask_size, panel_w - 8)
    for k, line in enumerate(ask_lines):
        s.body.append(s.setter.text(left, seek_y + k * ask_size * 1.45, line, face=tokens.MONO, size=ask_size,
                                    fill=tokens.TEXT))
    cursor = seek_y + len(ask_lines) * ask_size * 1.45 + 14

    key_w = max(s.setter.width(key, tokens.ARCADE, 8 if narrow else 9) + 16 for key, _ in CONTROLS)
    for k, (key, what) in enumerate(CONTROLS):
        ky = cursor + k * (30 if narrow else 32)
        glow = fx.track(s.anim, fx.windows([(COUNT_FROM + 3.3 * k, COUNT_FROM + 3.3 * k + 0.4)], T, on="1", off="0"))
        s.body.append(
            f'<rect x="{fmt(left)}" y="{fmt(ky - 15)}" width="{fmt(key_w)}" height="22" rx="3" fill="{tokens.PANEL_HI}"'
            f' stroke="{tokens.ACID if k == 0 else tokens.VIOLET}"/>'
            + f'<rect class="{glow}" opacity="0" x="{fmt(left)}" y="{fmt(ky - 15)}" width="{fmt(key_w)}" height="22" rx="3"'
            f' fill="{tokens.ACID if k == 0 else tokens.VIOLET}" fill-opacity="0.35"/>'
            + s.setter.text(left + 8, ky, key, face=tokens.ARCADE, size=8 if narrow else 9,
                            fill=tokens.ACID if k == 0 else tokens.VIOLET_BRIGHT)
            + s.setter.text(left + key_w + 12, ky, what, face=tokens.MONO, size=10.5 if narrow else 11.5,
                            fill=tokens.TEXT)
        )
    cursor += len(CONTROLS) * (30 if narrow else 32) + 18

    # --- CONTINUE? countdown ---------------------------------------------------------------
    count_y = cursor
    s.body.append(s.setter.text(left, count_y + 18, "CONTINUE?", face=tokens.ARCADE, size=11 if narrow else 13,
                                fill=tokens.TEXT, tracking=tokens.TRACK_ARCADE))
    digit_x = left + s.setter.width("CONTINUE?", tokens.ARCADE, 11 if narrow else 13, tokens.TRACK_ARCADE) + 18
    scale = 4 if narrow else 5
    for digit in range(9, -1, -1):
        start = COUNT_FROM + (9 - digit)
        cls = fx.track(s.anim, fx.windows([(start, start + 1.0)], T))
        color = tokens.ACID if digit > 3 else tokens.HOT_VIOLET
        s.body.append(fx.wrap(cls, pf.render_path(str(digit), digit_x, count_y - 8, scale=scale, fill=color),
                              hidden=digit != 9))
    coin_cls = fx.track(s.anim, fx.windows([(COUNT_FROM + 10, THANKS_AT)], T))
    coin_x = digit_x + 8 * scale
    s.body.append(fx.wrap(coin_cls, fx.wrap(fx.track(s.anim, fx.blink_frames(COUNT_FROM + 10, THANKS_AT, 0.5, T)),
                                            pf.render_path("INSERT COIN", digit_x, count_y + 2, scale=2,
                                                           fill=tokens.ACID)), hidden=True))
    s.body.append(_coin(s, left + panel_w - 20, count_y + 10, 9))
    panel_bottom = count_y + 34

    # --- credits roll ----------------------------------------------------------------------
    rows = _credits(data)
    if narrow:
        roll_y = panel_bottom + 22
        s.body.append(_roll(s, roll_x, roll_y, roll_w, roll_h, rows))
        height = roll_y + roll_h + 24
    else:
        roll_h = panel_bottom - top
        s.body.append(_roll(s, roll_x, roll_y, roll_w, roll_h, rows))
        height = panel_bottom + 26

    # --- THANKS FOR PLAYING, then power off -------------------------------------------------
    size = 15 if narrow else 22
    text = "THANKS FOR PLAYING"
    tw = s.setter.width(text, tokens.ARCADE, size, tokens.TRACK_ARCADE)
    stamp = fx.track(s.anim, fx.stamp_frames(THANKS_AT, CRT_OFF[0] - 0.05, T), base={"opacity": "0"})
    card_w, card_h = tw + 40, size * 4.2
    stamp_body = (
        f'<rect x="{fmt(-card_w / 2 - 8)}" y="{fmt(-card_h / 2 - 8)}" width="{fmt(card_w + 16)}" height="{fmt(card_h + 16)}"'
        f' fill="{tokens.VOID}" opacity="0.85"/>'
        + fx.glow_rect(-card_w / 2, -card_h / 2, card_w, card_h, tokens.ACID, stroke=2.5)
        + s.setter.text(0, -size * 0.2, text, face=tokens.ARCADE, size=size, fill=tokens.ACID,
                        tracking=tokens.TRACK_ARCADE, anchor="middle")
        + s.setter.text(0, size * 1.3, "PRESS START TO PLAY AGAIN", face=tokens.ARCADE, size=size * 0.42,
                        fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE, anchor="middle")
    )
    s.front.append(fx.place(width / 2, height / 2 + 10, stamp, stamp_body))
    s.front.append(fx.burst(s.anim, width / 2, height / 2 + 10, [THANKS_AT + 0.16], T, count=22,
                            radius=200 if not narrow else 140, size=5, seed=121))
    s.front.append(fx.crt(s.anim, width, height, T, on=CRT_ON, off=CRT_OFF))

    return s.render(
        height,
        chapter=6,
        title="Player 2 wanted: open an issue or find Jiteesh on LinkedIn",
        description=(
            "Chapter seven, credits. PLAYER 2 WANTED: Jiteesh is looking for a software engineering "
            "internship. Insert coin by opening an issue on this repository, or link up on LinkedIn. "
            "End credits roll beside it and the card ends on THANKS FOR PLAYING."
        ),
        note="GAME OVER? NOT YET",
    )
