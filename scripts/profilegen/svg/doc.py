"""SVG document assembly.

The two things worth knowing:

* ``Defs`` deduplicates by caller-supplied key.  The monolith had two functions
  (``svg_shell`` and ``render_terminal_intro``) independently emitting a
  ``<filter id="particle-glow">`` into the *same* document -- a duplicate ID, which browsers
  resolve to whichever came first and no test could see.  Registering defs through one
  registry makes that structurally impossible.
* ``anim_group`` enforces the split that the whole animation strategy rests on: absolute
  placement on an outer ``<g transform=...>`` attribute, relative motion on an inner ``<g>``
  via CSS.  A CSS ``transform`` completely overrides the ``transform`` attribute, so putting
  both on one element silently discards the placement.
"""

from __future__ import annotations

import html
from collections.abc import Iterable

from .num import n


def esc(value: object) -> str:
    """Escape text for use in attribute values or text content."""
    return html.escape(str(value), quote=True)


class Defs:
    """A `<defs>` block that cannot contain duplicate ids."""

    def __init__(self, prefix: str = "d") -> None:
        self._prefix = prefix
        self._by_key: dict[str, str] = {}
        self._markup: list[str] = []

    def add(self, key: str, build: str | Iterable[str]) -> str:
        """Register a def under ``key`` and return its ``#id`` reference.

        Calling twice with the same key is a no-op that returns the same id, so callers can
        ask for "the mino square symbol" without coordinating with each other.
        """
        if key in self._by_key:
            return f"#{self._by_key[key]}"
        ident = f"{self._prefix}{len(self._by_key)}"
        self._by_key[key] = ident
        markup = build if isinstance(build, str) else "".join(build)
        self._markup.append(markup.replace("{id}", ident))
        return f"#{ident}"

    def ref(self, key: str) -> str:
        """Return the ``#id`` for an already-registered key."""
        return f"#{self._by_key[key]}"

    def render(self) -> str:
        if not self._markup:
            return ""
        return "<defs>" + "".join(self._markup) + "</defs>"

    def __len__(self) -> int:
        return len(self._by_key)


def use(ref: str, x: float = 0.0, y: float = 0.0, cls: str | None = None) -> str:
    """Instance a registered def.  Plain ``href``, not ``xlink:href`` (SVG2, Safari 12+)."""
    parts = [f'<use href="{ref}"']
    if x:
        parts.append(f' x="{n(x)}"')
    if y:
        parts.append(f' y="{n(y)}"')
    if cls:
        parts.append(f' class="{cls}"')
    parts.append("/>")
    return "".join(parts)


def anim_group(cls: str | None, x: float, y: float, children: str) -> str:
    """Place a group absolutely, then animate it relatively.

    The outer ``<g>`` carries a ``transform`` *attribute* for position; the inner ``<g>``
    carries the CSS class that animates.  Keeping these on separate elements is mandatory:
    a CSS ``transform`` overrides the attribute entirely, so a combined element would jump
    to the origin the moment its animation applied.

    Keeping animated motion relative to each element's own origin is also what lets the
    keyframe emitter deduplicate -- two blocks falling the same distance in different
    columns produce byte-identical keyframes only because neither encodes its own position.
    """
    inner = f'<g class="{cls}">{children}</g>' if cls else f"<g>{children}</g>"
    if not x and not y:
        return inner
    return f'<g transform="translate({n(x)} {n(y)})">{inner}</g>'


class SvgDoc:
    """Accumulates defs, CSS and body markup, then renders one standalone SVG file."""

    def __init__(self, width: int, height: int, title: str, *, defs_prefix: str = "d") -> None:
        self.width = width
        self.height = height
        self.title = title
        self.defs = Defs(defs_prefix)
        self._css: list[str] = []
        self._body: list[str] = []

    def css(self, text: str) -> None:
        self._css.append(text)

    def add(self, markup: str) -> None:
        self._body.append(markup)

    def render(self) -> str:
        style = "".join(self._css)
        # role/aria-label rather than a <title> child: this is decorative-with-meaning and
        # the alt text on the <img> in the README is what assistive tech actually reads.
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}" '
            f'fill="none" role="img" aria-label="{esc(self.title)}">'
            f"{self.defs.render()}"
            f"<style>{style}</style>"
            f"{''.join(self._body)}"
            "</svg>\n"
        )
