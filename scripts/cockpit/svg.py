"""SVG document shell and the primitives every card shares.

Cards are always dark. The page is a cabin at night, not a document, so it
does not get a light variant - a hairline border keeps it from bleeding into
GitHub's light theme instead.
"""

from __future__ import annotations

import html
import math

from . import tokens
from .typography import fmt

# Gradient and filter ids live in one place because every card declares the
# same defs block; a card that invents its own id will collide with a sibling
# once two cards end up in the same README.
GRAD_AMBIENT = "amb"
GRAD_AMBIENT_V = "ambv"

# Glow is built from stacked translucent shapes rather than feGaussianBlur.
# Filters are the least portable part of SVG - some renderers drop them
# silently, which turns a soft pool of light into a hard-edged coloured blob.
# Gradients and opacity behave the same everywhere.
GLOW_STACK = ((5.0, 0.10), (2.6, 0.16), (1.0, 1.0))


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def polar(cx: float, cy: float, radius: float, degrees: float) -> tuple[float, float]:
    """Point on a circle. 0 degrees points right, angles run clockwise."""
    radians = math.radians(degrees)
    return cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def arc(cx: float, cy: float, radius: float, start: float, end: float) -> str:
    """Open arc path from ``start`` to ``end`` degrees, clockwise."""
    x1, y1 = polar(cx, cy, radius, start)
    x2, y2 = polar(cx, cy, radius, end)
    large = 1 if abs(end - start) > 180 else 0
    sweep = 1 if end > start else 0
    return (
        f"M{fmt(x1)} {fmt(y1)}"
        f"A{fmt(radius)} {fmt(radius)} 0 {large} {sweep} {fmt(x2)} {fmt(y2)}"
    )


def shared_defs(width: int) -> str:
    """Gradients and filters used across cards."""
    return (
        f'<linearGradient id="{GRAD_AMBIENT}" x1="0" y1="0" x2="{width}" y2="0"'
        ' gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{tokens.ROSE}"/>'
        f'<stop offset="0.5" stop-color="#9A5BC8"/>'
        f'<stop offset="1" stop-color="{tokens.ICE}"/>'
        "</linearGradient>"
        f'<linearGradient id="{GRAD_AMBIENT_V}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{tokens.ROSE}"/>'
        f'<stop offset="1" stop-color="{tokens.ICE}"/>'
        "</linearGradient>"
    )


def radial_wash(ident: str, color: str, peak: float = 0.55) -> str:
    """A soft pool of light with no filter involved."""
    return (
        f'<radialGradient id="{ident}">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="{fmt(peak)}"/>'
        f'<stop offset="0.55" stop-color="{color}" stop-opacity="{fmt(peak * 0.38)}"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>'
        "</radialGradient>"
    )


def document(
    width: int,
    height: int,
    body: str,
    *,
    defs: str = "",
    title: str = "",
    description: str = "",
) -> str:
    """Wrap a rendered body in a self-contained SVG document."""
    head = ""
    if title:
        head += f"<title>{esc(title)}</title>"
    if description:
        head += f"<desc>{esc(description)}</desc>"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{esc(title)}">'
        f"{head}"
        f"<defs>{shared_defs(width)}{defs}</defs>"
        f'<rect width="{width}" height="{height}" fill="{tokens.VOID}"/>'
        f"{body}"
        "</svg>"
    )


def card(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: str = tokens.PANEL,
    stroke: str = tokens.HAIRLINE,
    radius: float = tokens.RADIUS,
) -> str:
    return (
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" height="{fmt(height)}"'
        f' rx="{fmt(radius)}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def ambient_bar(x: float, y: float, width: float, *, thickness: float = 3) -> str:
    """The signature element: one rose-to-ice rule, reused as the page's spine.

    Drawn as a stack - wide and faint underneath, crisp on top - so the bloom
    survives renderers that ignore filters.
    """
    parts = []
    for spread, opacity in GLOW_STACK:
        height = thickness * spread
        parts.append(
            f'<rect x="{fmt(x)}" y="{fmt(y - (height - thickness) / 2)}"'
            f' width="{fmt(width)}" height="{fmt(height)}" rx="{fmt(height / 2)}"'
            f' fill="url(#{GRAD_AMBIENT})" opacity="{fmt(opacity)}"/>'
        )
    return "".join(parts)


def hairline(x: float, y: float, width: float, *, color: str = tokens.HAIRLINE) -> str:
    return (
        f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(width)}" height="1"'
        f' fill="{color}"/>'
    )


def eyebrow(
    setter,
    x: float,
    y: float,
    text: str,
    *,
    color: str = tokens.MUTED,
    size: float = 10,
    anchor: str = "start",
) -> str:
    """Small tracked-out caps used to name a region."""
    return setter.text(
        x,
        y,
        text.upper(),
        face=tokens.DISPLAY,
        size=size,
        fill=color,
        tracking=tokens.TRACK_EYEBROW,
        anchor=anchor,
    )


class Motion:
    """Collects CSS animations and emits them behind a reduced-motion guard.

    Every animated element carries its *finished* value as a plain attribute,
    and the animation only supplies the journey to get there. A reader who has
    asked for reduced motion, or a renderer with no animation support at all,
    sees a correct instrument rather than a needle pinned at zero.
    """

    EASE = "cubic-bezier(0.16, 0.9, 0.2, 1)"

    def __init__(self) -> None:
        self._rules: list[str] = []
        self._frames: list[str] = []
        self._registered: set[str] = set()

    def sweep(self, name: str, frm: str, to: str, *, delay: float = 0.15) -> str:
        """Register an animation and return the class name to apply."""
        self._frames.append(f"@keyframes {name}{{from{{{frm}}}to{{{to}}}}}")
        self._rules.append(
            f".{name}{{animation:{name} {tokens.SWEEP_DURATION}s {self.EASE}"
            f" {fmt(delay)}s both}}"
        )
        return name

    def shared(
        self,
        name: str,
        frm: str,
        to: str,
        delay: float,
        *,
        duration: float = tokens.SWEEP_DURATION,
        buckets: float = 0.05,
    ) -> str:
        """One keyframe, many start times.

        Cards that animate hundreds of small elements - the Tetris board drops
        one block per submission - would otherwise emit a keyframe per element.
        Delays are quantised into buckets so the stylesheet stays a fixed size
        no matter how many blocks there are.
        """
        if name not in self._registered:
            self._registered.add(name)
            self._frames.append(f"@keyframes {name}{{from{{{frm}}}to{{{to}}}}}")
        slot = int(round(delay / buckets))
        class_name = f"{name}{slot}"
        if class_name not in self._registered:
            self._registered.add(class_name)
            self._rules.append(
                f".{class_name}{{animation:{name} {duration}s {self.EASE}"
                f" {fmt(slot * buckets)}s both}}"
            )
        return class_name

    def origin(self, name: str, cx: float, cy: float) -> None:
        """Pin a rotation to a point in the view box."""
        self._rules.append(
            f".{name}{{transform-box:view-box;"
            f"transform-origin:{fmt(cx)}px {fmt(cy)}px}}"
        )

    def style(self) -> str:
        if not self._rules:
            return ""
        payload = "".join(self._rules) + "".join(self._frames)
        return (
            "<style>@media (prefers-reduced-motion:no-preference){"
            f"{payload}"
            "}</style>"
        )
