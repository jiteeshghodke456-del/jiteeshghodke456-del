"""The chrome every chapter shares, which is what turns seven images into one arcade.

Three things repeat on every card and nowhere else:

* **The rails.** A violet rail on the left and an acid one on the right, the same distance from
  the edge on every card, each carrying a pulse that runs top to bottom at the same speed
  everywhere. Stacked in the README they read as one signal running down the page.
* **The header.** Chapter number, title, and seven progress pips, so a reader who lands halfway
  down knows where they are in the story.
* **The glass.** Scanlines and a vignette over everything, so every scene sits behind the same
  tube.

The top and bottom edges of every card are the page void, so wherever two images meet the
seam is the same colour on both sides of it.
"""

from __future__ import annotations

import math

from profilegen.svg.anim import AnimationSet

from . import fx, svg, tokens
from .typography import TypeSetter, fmt

CHAPTERS = (
    "BOOT",
    "PLAYER SELECT",
    "WORLD MAP",
    "BOSS FIGHT",
    "BONUS STAGE",
    "INVENTORY",
    "CREDITS",
)


def pad(width: int) -> int:
    return tokens.PAD_NARROW if width <= tokens.NARROW else tokens.PAD


def backdrop(ids: fx.Ids, width: float, height: float) -> tuple[str, str]:
    """Pools of violet overhead and green underfoot, fading to void at every edge."""
    violet, green = ids.next(), ids.next()
    defs = svg.radial_wash(violet, tokens.VIOLET, 0.22) + svg.radial_wash(green, tokens.EMERALD, 0.14)
    body = (
        f'<rect x="{fmt(-width * 0.25)}" y="{fmt(-height * 0.35)}" width="{fmt(width * 0.9)}"'
        f' height="{fmt(height * 1.1)}" fill="url(#{violet})"/>'
        f'<rect x="{fmt(width * 0.4)}" y="{fmt(height * 0.3)}" width="{fmt(width * 0.9)}"'
        f' height="{fmt(height * 1.0)}" fill="url(#{green})"/>'
    )
    return defs, body


def _pulse(anim: AnimationSet, ids: fx.Ids, x: float, height: float, duration: float,
           color: str, phase: float) -> tuple[str, str]:
    """A bright slug running down a rail at :data:`tokens.RAIL_SPEED`."""
    slug = 46.0
    travel = height + slug * 2
    run = travel / tokens.RAIL_SPEED
    laps = max(1, int(duration // (run + 0.4)))
    spacing = duration / laps
    points: list[tuple[float, dict]] = [
        (0.0, {"transform": f"translate(0px,{fmt(-slug)}px)", "opacity": "0"})
    ]
    for lap in range(laps):
        start = (lap * spacing + phase * spacing) % duration
        end = start + run
        if end > duration:
            start = max(0.0, duration - run - 0.02)
            end = start + run
        points += [
            (start, {"transform": f"translate(0px,{fmt(-slug)}px)", "opacity": "1"}),
            (end, {"transform": f"translate(0px,{fmt(height + slug)}px)", "opacity": "1"}),
            (end + 0.01, {"transform": f"translate(0px,{fmt(height + slug)}px)", "opacity": "0"}),
            (min(duration, end + 0.02), {"transform": f"translate(0px,{fmt(-slug)}px)", "opacity": "0"}),
        ]
    cls = fx.track(anim, fx.steps(points, duration), easing="linear", base={"opacity": "0"})
    grad = ids.next()
    defs = (
        f'<linearGradient id="{grad}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0"/>'
        f'<stop offset="0.8" stop-color="{color}" stop-opacity="1"/>'
        f'<stop offset="1" stop-color="#FFFFFF" stop-opacity="1"/>'
        "</linearGradient>"
    )
    body = fx.place(
        x, 0, cls,
        f'<rect x="-3" y="{fmt(-slug)}" width="6" height="{fmt(slug)}" rx="3" fill="url(#{grad})" opacity="0.35"/>'
        f'<rect x="-1" y="{fmt(-slug)}" width="2" height="{fmt(slug)}" fill="url(#{grad})"/>',
    )
    return defs, body


def rails(anim: AnimationSet, ids: fx.Ids, width: float, height: float, duration: float) -> tuple[str, str]:
    left = tokens.RAIL_INSET
    right = width - tokens.RAIL_INSET
    parts: list[str] = []
    for x, color in ((left, tokens.VIOLET), (right, tokens.ACID)):
        parts.append(
            f'<rect x="{fmt(x - 3)}" y="0" width="6" height="{fmt(height)}" fill="{color}" opacity="0.06"/>'
            f'<rect x="{fmt(x - 0.5)}" y="0" width="1" height="{fmt(height)}" fill="{color}" opacity="0.45"/>'
        )
    defs_l, pulse_l = _pulse(anim, ids, left, height, duration, tokens.VIOLET, 0.0)
    defs_r, pulse_r = _pulse(anim, ids, right, height, duration, tokens.ACID, 0.5)
    return defs_l + defs_r, "".join(parts) + pulse_l + pulse_r


def header(
    anim: AnimationSet,
    setter: TypeSetter,
    width: int,
    chapter: int,
    duration: float,
    *,
    note: str = "",
) -> str:
    """``CH.02 PLAYER SELECT`` on the left, the progress pips on the right."""
    narrow = width <= tokens.NARROW
    x = pad(width) + 8
    baseline = 34
    label = f"CH.{chapter + 1:02d}"
    size = 9 if narrow else 10
    title_size = 10 if narrow else 13
    parts = [
        setter.text(x, baseline, label, face=tokens.ARCADE, size=size, fill=tokens.ACID,
                    tracking=tokens.TRACK_ARCADE),
    ]
    title_x = x + setter.width(label, tokens.ARCADE, size, tokens.TRACK_ARCADE) + 12
    parts.append(
        setter.text(title_x, baseline + (title_size - size) / 2, CHAPTERS[chapter],
                    face=tokens.ARCADE, size=title_size, fill=tokens.TEXT,
                    tracking=tokens.TRACK_ARCADE)
    )

    # Pips: past chapters dim acid, this one lit and blinking, the rest unlit outlines.
    pip, gap = (6, 4) if narrow else (8, 5)
    count = len(CHAPTERS)
    pips_w = count * pip + (count - 1) * gap
    pips_x = width - pad(width) - 8 - pips_w
    top = baseline - pip - 1
    for index in range(count):
        px = pips_x + index * (pip + gap)
        if index < chapter:
            parts.append(f'<rect x="{fmt(px)}" y="{fmt(top)}" width="{pip}" height="{pip}" fill="{tokens.ACID_DEEP}"/>')
        elif index == chapter:
            cls = fx.track(anim, fx.blink_frames(0.0, duration, 1.0, duration, low="0.35"))
            parts.append(
                f'<rect x="{fmt(px - 2)}" y="{fmt(top - 2)}" width="{pip + 4}" height="{pip + 4}" fill="{tokens.ACID}" opacity="0.2"/>'
                f'<rect{fx.cls_attr(cls)} x="{fmt(px)}" y="{fmt(top)}" width="{pip}" height="{pip}" fill="{tokens.ACID}"/>'
            )
        else:
            parts.append(
                f'<rect x="{fmt(px + 0.5)}" y="{fmt(top + 0.5)}" width="{pip - 1}" height="{pip - 1}"'
                f' fill="none" stroke="{tokens.DIM}"/>'
            )
    if note and not narrow:
        parts.append(
            setter.text(pips_x - 16, baseline, note, face=tokens.MONO, size=10,
                        fill=tokens.MUTED, anchor="end")
        )
    rule_y = baseline + 12
    parts.append(
        f'<rect x="{fmt(x)}" y="{fmt(rule_y)}" width="{fmt(width - 2 * x)}" height="1" fill="url(#{svg.GRAD_AMBIENT})" opacity="0.55"/>'
    )
    return "".join(parts)


def glass(ids: fx.Ids, width: float, height: float) -> tuple[str, str]:
    """Scanlines and a vignette, painted over everything else."""
    scan_defs, scan = fx.scanlines(ids, width, height, opacity=0.2)
    vignette = ids.next()
    defs = scan_defs + (
        f'<radialGradient id="{vignette}" cx="0.5" cy="0.5" r="0.75">'
        f'<stop offset="0.55" stop-color="{tokens.VOID}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{tokens.VOID}" stop-opacity="0.75"/>'
        "</radialGradient>"
    )
    return defs, scan + f'<rect width="{fmt(width)}" height="{fmt(height)}" fill="url(#{vignette})"/>'


class Scene:
    """Collects one chapter: its clock, type, ids, defs, and three paint layers.

    ``back`` sits under the content, ``body`` is the content, ``front`` goes over everything
    (glass, then transitions). Cards append to the lists and call :meth:`render` last, once the
    height is known.
    """

    def __init__(self, width: int, duration: float, prefix: str = "a") -> None:
        from profilegen.svg.anim import AnimationSet as _Set, Timeline

        self.width = width
        self.narrow = width <= tokens.NARROW
        self.pad = pad(width)
        self.duration = duration
        self.anim = _Set(Timeline(duration), prefix)
        self.setter = TypeSetter()
        self.ids = fx.Ids("q")
        self.defs: list[str] = []
        self.body: list[str] = []
        self.front: list[str] = []

    def render(
        self,
        height: float,
        *,
        chapter: int | None,
        title: str,
        description: str,
        note: str = "",
        chrome: bool = True,
    ) -> str:
        height = int(math.ceil(height))
        back: list[str] = []
        top: list[str] = []
        if chrome:
            defs, wash = backdrop(self.ids, self.width, height)
            self.defs.append(defs)
            back.append(wash)
            defs, rail = rails(self.anim, self.ids, self.width, height, self.duration)
            self.defs.append(defs)
            back.append(rail)
            if chapter is not None:
                top.append(header(self.anim, self.setter, self.width, chapter, self.duration, note=note))
            defs, over = glass(self.ids, self.width, height)
            self.defs.append(defs)
        else:
            over = ""
        body = "".join(back) + "".join(top) + "".join(self.body) + over + "".join(self.front)
        style = f"<style>{self.anim.css()}</style>"
        return svg.document(
            self.width,
            height,
            style + body,
            defs=self.setter.defs() + "".join(self.defs),
            title=title,
            description=description,
        )
