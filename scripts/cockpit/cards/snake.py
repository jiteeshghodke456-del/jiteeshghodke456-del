"""CH.05 BONUS STAGE: the contribution snake, on a Nokia 3310.

Replaces a dependency on the Platane/snk action. Two things that action cannot do are the
whole reason for writing our own: its snake never grows, and its body is thin and rounded
rather than the blocky segments a 3310 actually drew.

The route is planned, not approximated. A Hamiltonian cycle over the playfield gives an
escape that is always available, and shortcuts are only taken when they provably preserve
it, so the snake cannot trap itself and every contribution day is eaten. That matters
because this regenerates on a daily cron: a trapped snake is a broken panel discovered by
whoever visits next, not by us.

The chapter only frames the phone. The planner is untouched; the phone is rendered exactly as
before and nested inside the shared chrome, running on the same clock as the rails and Bit so
the whole card loops as one.
"""

from __future__ import annotations

import re

from profilegen.snake import ai, grid
from profilegen.snake import render as snake_render

from .. import fx, mascot, scene, tokens
from ..typography import fmt


def _nest(markup: str, x: float, y: float, width: float) -> tuple[str, float]:
    """Place a rendered phone at ``(x, y)`` scaled to ``width``; returns markup and height."""
    native_w = float(re.search(r'width="([\d.]+)"', markup).group(1))
    native_h = float(re.search(r'height="([\d.]+)"', markup).group(1))
    height = native_h * width / native_w
    head, rest = markup.split(">", 1)
    head = re.sub(r' width="[\d.]+"', f' width="{fmt(width)}"', head, count=1)
    head = re.sub(r' height="[\d.]+"', f' height="{fmt(height)}"', head, count=1)
    head += f' x="{fmt(x)}" y="{fmt(y)}"'
    return head + ">" + rest.rstrip(), height


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    narrow = width <= tokens.NARROW
    field = grid.build(data.get("contributions") or [])
    record = ai.plan(field)
    # The panel sizes itself from the cell, so the narrow variant is the same drawing at a
    # smaller pitch rather than a second layout to keep in step.
    phone = snake_render.render(record, field, cell=6 if narrow else 13, font=2 if narrow else 3)

    duration = record.duration
    s = scene.Scene(width, duration, prefix="z")
    left = s.pad + 4
    right = width - s.pad - 4
    meals = len(record.meals)
    streaks = data.get("streaks") or {}

    title_y = 76
    s.body.append(
        fx.wrap(
            fx.track(s.anim, fx.blink_frames(0.0, 2.4, 0.3, duration, low="0.2")),
            s.setter.text(left + 4, title_y, "BONUS STAGE!", face=tokens.ARCADE, size=12 if narrow else 15,
                          fill=tokens.ACID, tracking=tokens.TRACK_ARCADE),
        )
    )
    goal = f"EAT ALL {meals} DAYS" if meals else "NOTHING TO EAT YET"
    s.body.append(
        s.setter.text(right - 4, title_y, goal, face=tokens.ARCADE, size=9 if narrow else 10,
                      fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE, anchor="end")
    )
    sub = (
        "One segment per day committed. It plans on a Hamiltonian cycle, so it cannot trap itself."
    )
    sub_size = 10 if narrow else 11
    lines = s.setter.wrap(sub, tokens.MONO, sub_size, right - left - 8)
    for k, line in enumerate(lines):
        s.body.append(s.setter.text(left + 4, title_y + 22 + k * sub_size * 1.4, line, face=tokens.MONO,
                                    size=sub_size, fill=tokens.MUTED))
    phone_y = title_y + 22 + len(lines) * sub_size * 1.4 + (40 if narrow else 48)

    # Bit patrols the top edge of the phone, stopping to cheer when the board is cleared.
    px = 3
    bw, bh = mascot.width(px), mascot.height(px)
    home_x = right - bw - 30
    finish = record.reset_at
    stroll = min(duration * 0.35, 8.0)
    s.body.append(
        mascot.bit(
            s.anim, duration, home_x, phone_y - bh + 2, px,
            walk=(-(right - left - bw - 90), 0.6, 0.6 + stroll),
            cheer=[(finish, min(duration - 0.5, finish + 2.0))],
            jumps=[finish + 0.1, finish + 0.7],
            blinks=[3.0, 9.0, 15.0, 21.0],
            wave=[(0.6 + stroll + 0.3, 0.6 + stroll + 1.5)],
        )
    )
    nested, phone_h = _nest(phone, left, phone_y, right - left)
    s.body.append(nested)

    foot_y = phone_y + phone_h + 26
    best = int(streaks.get("longest") or 0)
    busiest = int(streaks.get("busiest_day") or 0)
    stats = f"LONGEST COMBO {best} DAYS · BUSIEST DAY {busiest} CONTRIBUTIONS"
    if narrow:
        stats = f"COMBO {best} · BUSIEST {busiest}"
    s.body.append(s.setter.text(width / 2, foot_y, stats, face=tokens.DISPLAY, size=9 if narrow else 10,
                                fill=tokens.MUTED, tracking=tokens.TRACK_LABEL, anchor="middle"))
    height = foot_y + 22

    return s.render(
        height,
        chapter=4,
        title="Bonus stage: Nokia Snake eating a year of GitHub contributions",
        description=(
            f"Chapter five, bonus stage. A Nokia 3310 plays Snake on the contribution calendar. The "
            f"snake grows one segment per contribution day and eats all {meals} of them, planning "
            f"its route on a Hamiltonian cycle so it can never trap itself."
        ),
        note="+1 PER DAY",
    )
