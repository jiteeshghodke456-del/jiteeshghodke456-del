"""CSS ``@keyframes`` emitter shared by the animated SVG generators.

Why CSS keyframes
-----------------
GitHub's markdown sanitiser deletes inline ``<svg>``, escapes ``<style>`` and strips
``style=`` attributes, so every visual is a standalone ``.svg`` referenced through ``<img>``.
An SVG loaded that way runs in the browser's *secure static mode*: no scripts, no external
resources.  All motion therefore has to be CSS ``@keyframes`` inside the file.  That is also
how the reference this repo is measured against does it -- fetching Platane/snk's live SVG
shows one internal ``<style>``, 257 ``@keyframes`` rules, zero SMIL, and a single shared
``animation-duration`` (104.5 s) keeping every track in sync.

Why one emitter
---------------
The previous generators hand-computed ``value / cycle * 100`` in about eight places, each an
independent chance to be wrong, and ``grow_contribution_snake.py`` (line 388) emitted one
full keyframe block *per snake segment* -- O(segments x steps) bytes, roughly the 70 KB by
which it lost to snk.  This module owns both problems:

* callers speak **absolute seconds** on a shared :class:`Timeline` and never see a
  percentage;
* identical keyframe bodies collapse into **one** ``@keyframes`` block by content, and
  :meth:`AnimationSet.use` replays an existing block from any number of elements at
  different delays, so a 34-segment snake is one path block plus 34 one-line rules.

Everything a browser would fail on *silently* -- geometry properties Firefox ignores,
percentage transforms that resolve differently per engine, a typo in an easing keyword that
invalidates the whole ``animation`` shorthand, a stray ``}`` in a colour pulled from an API
-- is turned into a ``ValueError`` at generation time instead.  Every misuse this module
detects raises ``ValueError``: one contract, not a taxonomy of exceptions.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .num import n, o

__all__ = ["ANIMATABLE", "AnimationSet", "EmitterStats", "Keyframe", "Timeline"]

# ------------------------------------------------------------------ property policy

#: The closed set of properties a track may animate.  Each of these animates identically in
#: Chrome, Firefox and Safari when driven from CSS inside an ``<img>``-loaded SVG.  Extend it
#: only after checking the candidate in Firefox specifically -- that is where the silent
#: failures live.
ANIMATABLE: frozenset[str] = frozenset(
    {"transform", "opacity", "fill", "stroke", "stroke-opacity", "filter"}
)

# SVG geometry attributes.  Chrome and Safari animate these from CSS; Firefox accepts the
# declaration and then does nothing, so a track built on them looks right on the machine it
# was written on and is frozen for a large share of readers.  Named separately from "not in
# the whitelist" so the error can say *what to do instead*.
_GEOMETRY: frozenset[str] = frozenset(
    {"x", "y", "width", "height", "cx", "cy", "r", "rx", "ry", "d", "points"}
)

# Characters that would end a declaration or a rule early.  Colours and filter references
# sometimes originate in remote data (GitHub language colours, for one); a stray "}" would
# truncate every rule after it with no error anywhere.  Whitespace is collapsed before this
# check, so a trailing newline is treated as the harmless artefact it is.
_STRUCTURAL = frozenset(";{}")

# ------------------------------------------------------------------ CSS grammar bits

_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_FUNCTION_CALL = re.compile(r"\s*([A-Za-z]+)\(([^()]*)\)\s*")
_ARGUMENT = re.compile(rf"^({_NUMBER})([A-Za-z%]*)$")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")

_EASING_KEYWORDS = frozenset(
    {"step-end", "step-start", "linear", "ease", "ease-in", "ease-out", "ease-in-out"}
)
_EASING_FUNCTION = re.compile(
    r"^(?:steps\([1-9]\d*(?:,(?:start|end|jump-start|jump-end|jump-none|jump-both))?\)"
    rf"|cubic-bezier\({_NUMBER}(?:,{_NUMBER}){{3}}\))$"
)

# Emitted verbatim at the end of every css().  Readers who asked their OS for less motion
# get the static frame of every element; renderers that need a designed still image for
# that case add their own rule after this block.
_REDUCED_MOTION = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"

_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(value: int) -> str:
    """Shortest identifier suffix: ``0``..``9``, ``a``..``z``, ``10``, ...

    Two or three characters cover thousands of tracks.  Do NOT try to save further bytes
    with CSS custom properties: ``var(--g3)`` is nine characters where ``#39FF14`` is seven,
    so indirection through ``:root`` makes these files *larger*, not smaller.
    """
    digits = ""
    while True:
        value, remainder = divmod(value, 36)
        digits = _BASE36[remainder] + digits
        if not value:
            return digits


def _clean(text: str) -> str:
    """``num.n`` renders ``-0.04`` as ``-0``; CSS accepts it but no reader should see it."""
    return "0" if text == "-0" else text


def _seconds(value: float) -> str:
    """A CSS ``<time>``.  Seconds, not milliseconds: ``104.5s`` beats ``104500ms``."""
    return f"{_clean(n(value, 3))}s"


def _finite(value: object, what: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number, got {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return number


# ------------------------------------------------------------------ value canonicalisation


def _argument(text: str, where: str) -> tuple[float, str]:
    match = _ARGUMENT.match(text)
    if match is None:
        raise ValueError(f"{where}: cannot read {text!r} as a number")
    return _finite(match.group(1), where), match.group(2).lower()


def _length(text: str, where: str) -> float:
    """Accept ``12px`` or bare ``12`` (SVG-attribute habit); always emitted with ``px``.

    A bare number is *invalid* in a CSS transform except for zero, which is exactly the
    kind of thing that works in the ``transform`` attribute and then fails in ``<style>``.
    Relative units are refused because ``em``/``rem``/``vw`` scale with font or viewport and
    make one keyframe render differently per viewer.
    """
    value, unit = _argument(text, where)
    if unit not in ("", "px"):
        raise ValueError(f"{where}: {text!r} must be in px (or unitless, read as px)")
    return value


def _angle(text: str, where: str) -> float:
    value, unit = _argument(text, where)
    if unit not in ("", "deg"):
        raise ValueError(f"{where}: {text!r} must be in deg (or unitless, read as deg)")
    return value


def _scalar(text: str, where: str) -> float:
    value, unit = _argument(text, where)
    if unit:
        raise ValueError(f"{where}: scale factors are unitless, got {text!r}")
    return value


def _px(value: float) -> str:
    text = _clean(n(value))
    return text if text == "0" else f"{text}px"


def _canonical_function(name: str, args: list[str], where: str) -> str:
    if name == "translate":
        if not 1 <= len(args) <= 2:
            raise ValueError(f"{where}: translate() takes one or two lengths")
        x = _length(args[0], where)
        y = _length(args[1], where) if len(args) == 2 else 0.0
        return f"translate({_px(x)},{_px(y)})"
    if name == "scale":
        if not 1 <= len(args) <= 2:
            raise ValueError(f"{where}: scale() takes one or two factors")
        sx = _clean(o(_scalar(args[0], where)))
        sy = _clean(o(_scalar(args[1], where))) if len(args) == 2 else sx
        return f"scale({sx})" if sx == sy else f"scale({sx},{sy})"
    if name == "rotate":
        # The three-argument rotate(a, cx, cy) exists only in the SVG attribute grammar.
        # In CSS it is a parse error that silently disables the whole transform list.
        if len(args) != 1:
            raise ValueError(f"{where}: rotate() takes exactly one angle in CSS")
        return f"rotate({_clean(n(_angle(args[0], where)))}deg)"
    raise ValueError(
        f"{where}: {name}() is not allowed; only translate(), scale() and rotate() are"
    )


def _canonical_transform(value: str, where: str) -> str:
    """Validate a transform list and rewrite it in one canonical spelling.

    Canonical spelling is what makes content-addressed dedup work: ``translate(0px, 48px)``
    and ``translate(0,48)`` must hash the same.  Only ``translate()``, ``scale()`` and
    ``rotate()`` with ``px``/``deg``/unitless arguments are allowed.  Percentages are refused
    outright -- a percentage translate resolves against the bounding box in some engines and
    the viewport in others, so the same file moves differently per browser.
    """
    text = value.strip()
    if not text:
        raise ValueError(f"{where}: transform value is empty")
    if "%" in text:
        raise ValueError(
            f"{where}: transform {value!r} uses a percentage, which resolves against a "
            "different box per browser; use absolute px"
        )
    parts: list[str] = []
    position = 0
    while position < len(text):
        match = _FUNCTION_CALL.match(text, position)
        if match is None:
            raise ValueError(
                f"{where}: cannot parse transform {value!r} at {text[position:]!r}; only "
                "translate(), scale() and rotate() are allowed"
            )
        args = [arg for arg in re.split(r"[,\s]+", match.group(2).strip()) if arg]
        parts.append(_canonical_function(match.group(1), args, where))
        position = match.end()
    return " ".join(parts)


def _canonical_opacity(name: str, value: str, where: str) -> str:
    number = _finite(value, f"{where}: {name}")
    text = _clean(o(number))
    # Round first so float noise such as 1.0000001 passes; a real 1.2 is still a bug.
    if not 0.0 <= float(text) <= 1.0:
        raise ValueError(f"{where}: {name} {value!r} is outside 0..1")
    return text


def _canonical_props(props: Mapping[str, object], where: str) -> dict[str, str]:
    """Whitelist, validate and canonicalise one declaration block, keys sorted.

    Sorting is part of canonicalisation: ``{opacity, transform}`` and
    ``{transform, opacity}`` are the same keyframe and must dedupe together.
    """
    result: dict[str, str] = {}
    for raw_name, raw_value in props.items():
        name = str(raw_name).strip()
        if name in _GEOMETRY:
            raise ValueError(
                f"{where}: '{name}' is an SVG geometry attribute; CSS animates it in Chrome "
                "and Safari and silently does nothing in Firefox -- express the motion as a "
                "transform instead"
            )
        if name not in ANIMATABLE:
            raise ValueError(
                f"{where}: '{name}' is not animatable here; allowed: "
                f"{', '.join(sorted(ANIMATABLE))}"
            )
        value = " ".join(str(raw_value).split())
        if not value:
            raise ValueError(f"{where}: '{name}' has an empty value")
        if _STRUCTURAL & set(value):
            raise ValueError(
                f"{where}: '{name}' value {raw_value!r} contains a character that would "
                "end the rule early"
            )
        if name == "transform":
            value = _canonical_transform(value, where)
        elif name in ("opacity", "stroke-opacity"):
            value = _canonical_opacity(name, value, where)
        result[name] = value
    return dict(sorted(result.items()))


def _canonical_easing(easing: str) -> str:
    """Refuse anything that is not a CSS timing function.

    A misspelt keyword does not degrade gracefully: it invalidates the entire ``animation``
    shorthand and the element simply never moves, with nothing in any console.
    """
    text = "".join(str(easing).split())
    if text in _EASING_KEYWORDS or _EASING_FUNCTION.match(text):
        return text
    raise ValueError(
        f"easing {easing!r} is not a CSS timing function (step-end, linear, ease*, "
        "step-start, steps(...), cubic-bezier(...))"
    )


# ------------------------------------------------------------------ public data types


@dataclass(frozen=True)
class Keyframe:
    """One state on the shared timeline.

    ``t`` is in **absolute seconds**, never a percentage: the conversion happens once, in
    :meth:`Timeline.pct`, instead of in every renderer.  ``props`` maps CSS property names
    from :data:`ANIMATABLE` to values, e.g. ``{"transform": "translate(0,48px)",
    "opacity": "1"}``.  Validation of the properties happens in :meth:`AnimationSet.add`, so
    frames stay cheap to build in bulk.
    """

    t: float
    props: Mapping[str, str]

    def __post_init__(self) -> None:
        _finite(self.t, "keyframe time")
        if not self.props:
            raise ValueError("a keyframe must declare at least one property")


@dataclass(frozen=True)
class EmitterStats:
    """What one :meth:`AnimationSet.css` call would emit; the numbers the size budget is
    argued in.  ``rules`` and ``tracks`` coincide today because every ``add()``/``use()``
    is exactly one class rule; they are reported separately so that stays a checked fact
    rather than an assumption."""

    keyframe_blocks: int
    rules: int
    tracks: int
    bytes: int


class Timeline:
    """The one clock every track in a document shares.

    All tracks in one file must run on the same ``animation-duration``, otherwise they
    drift apart after the first loop (snk pins everything to 104.5 s for the same reason).
    Callers place keyframes in absolute seconds; the percentage arithmetic lives here and
    nowhere else.

    ``precision`` is the number of decimals in an emitted percentage.  Two decimals is
    0.01 % -- about 10 ms on a 104.5 s timeline, finer than a 60 Hz frame -- and every extra
    decimal is paid once per keyframe selector for nothing visible.
    """

    def __init__(self, duration: float, *, precision: int = 2) -> None:
        seconds = _finite(duration, "timeline duration")
        if seconds <= 0:
            raise ValueError(f"timeline duration must be positive, got {duration!r}")
        if precision < 0:
            raise ValueError(f"precision must be >= 0, got {precision!r}")
        self._duration = seconds
        self._precision = int(precision)

    @property
    def duration(self) -> float:
        return self._duration

    def pct(self, t: float) -> str:
        """Absolute seconds -> keyframe percentage text such as ``37.42``.

        Clamped to 0..100.  A keyframe selector outside that range is not an error in CSS;
        the browser just drops the keyframe, so a caller's loop that lands on
        ``duration + 1e-9`` through float accumulation would lose its final state silently.
        """
        seconds = _finite(t, "keyframe time")
        value = min(100.0, max(0.0, seconds / self._duration * 100.0))
        return _clean(n(value, self._precision))


# ------------------------------------------------------------------ the emitter


@dataclass(frozen=True)
class _Block:
    name: str
    animates_transform: bool


@dataclass(frozen=True)
class _Track:
    block: _Block
    easing: str


@dataclass(frozen=True)
class _Rule:
    cls: str
    block_name: str
    easing: str
    delay: float
    base: Mapping[str, str]
    transform_origin: bool


class AnimationSet:
    """Collects tracks for one document and renders them as one ``<style>`` body.

    Two size levers live here and both are invisible to callers:

    * **Content-addressed dedup.**  ``add()`` canonicalises a frame list (sorted property
      keys, numbers rounded through ``num``, adjacent identical states coalesced) and keys
      the ``@keyframes`` block on that text, so two blocks falling the same distance in
      different columns share one block automatically.
    * **``use()``.**  A new class rule pointing at an *existing* block with a different
      ``animation-delay``.  The old snake generator emitted a separate full path block per
      segment; with ``use()`` a 34-segment snake is one ~150-entry block plus 34 one-line
      rules.  That is the ~70 KB difference against snk.

    ``prefix`` namespaces the generated class and keyframe names so two sets can share one
    document.  Keep prefixes to one letter and distinct: because the suffix alphabet is
    base36, the prefix ``a`` and the prefix ``ab`` would eventually mint the same name.
    """

    def __init__(self, timeline: Timeline, prefix: str = "a") -> None:
        if not _IDENTIFIER.match(prefix):
            raise ValueError(f"prefix {prefix!r} cannot start a CSS identifier")
        self._timeline = timeline
        self._prefix = prefix
        self._blocks: dict[str, _Block] = {}  # canonical body -> block, first-seen order
        self._tracks: dict[str, _Track] = {}  # classes returned by add()
        self._rules: list[_Rule] = []
        self._calls = 0

    # -------------------------------------------------------------- building

    def add(
        self,
        frames: Sequence[Keyframe],
        *,
        easing: str = "step-end",
        delay: float = 0.0,
        base: Mapping[str, str] | None = None,
    ) -> str:
        """Register a track and return the class name to put on the animated element.

        ``easing`` defaults to ``step-end`` because pixel art must not interpolate between
        frames -- a sprite sliding between cells reads as a bug, not as motion.  ``linear``
        is opt-in for the few smooth tracks (rotation, scanline sweeps).

        ``base`` is emitted as ordinary declarations in the class rule.  With ``step-end``
        an element shows its static value until the first keyframe, and the *static* value
        is whatever the cascade says -- so a not-yet-born element is parked off-screen by
        stating that here rather than by reasoning about attribute-versus-CSS precedence.

        ``delay`` may be negative: that phase-shifts the element into an already-running
        animation, which is how one shared block drives a whole trail of segments.

        Raises ``ValueError`` when the frames never change a property.  A no-op track is
        dead bytes and has always turned out to be a caller bug (a loop that produced one
        state, a typo that made two states equal).
        """
        timing = _canonical_easing(easing)
        body, animates_transform = self._canonical_body(frames, timing)
        block = self._blocks.get(body)
        if block is None:
            block = _Block(self._prefix + _base36(len(self._blocks)), animates_transform)
            self._blocks[body] = block
        cls = self._emit_rule(block, timing, delay, base)
        self._tracks[cls] = _Track(block, timing)
        return cls

    def use(
        self, cls: str, *, delay: float, base: Mapping[str, str] | None = None
    ) -> str:
        """Replay the block behind ``cls`` from another element at a different delay.

        Emits a new one-line class rule and *no* new ``@keyframes`` block, which is the
        single biggest size lever this module has (see the class docstring).  Easing is
        inherited from the original ``add()`` because the block's coalescing was computed
        for that easing.  ``cls`` must be a value returned by ``add()`` on this set.
        """
        track = self._tracks.get(cls)
        if track is None:
            raise ValueError(f"{cls!r} was never returned by add() on this AnimationSet")
        return self._emit_rule(track.block, track.easing, delay, base)

    def _emit_rule(
        self, block: _Block, easing: str, delay: float, base: Mapping[str, str] | None
    ) -> str:
        offset = _finite(delay, "animation delay")
        declarations = _canonical_props(base or {}, "base")
        cls = self._prefix + _base36(len(self._rules))
        self._rules.append(
            _Rule(
                cls,
                block.name,
                easing,
                offset,
                declarations,
                block.animates_transform or "transform" in declarations,
            )
        )
        self._calls += 1
        return cls

    def _canonical_body(
        self, frames: Sequence[Keyframe], easing: str
    ) -> tuple[str, bool]:
        """Turn a frame list into the exact text of a ``@keyframes`` body.

        Order of operations matters:

        1. Sort by time (stable, so a caller's later frame still wins a tie).
        2. Convert to percentages; frames that round to the same stop are merged
           property-wise, later declarations winning -- the same result the CSS cascade
           would give for duplicate selectors, made explicit so the body is canonical.
        3. Refuse a track whose states are all identical.
        4. Coalesce runs of identical adjacent states.  Under ``step-end`` a value holds
           until the next *change*, so only the first frame of a run matters.  Under any
           continuous easing the last frame of the run is where the next segment starts
           interpolating, so first *and* last are kept.
        5. Group stops that share a state into one selector list (``0%,50%{...}``): the
           declarations are the long part, and a blinking track repeats them every other
           frame.
        """
        frames = list(frames)
        if not frames:
            raise ValueError("a track needs at least one keyframe")
        for frame in frames:
            if not isinstance(frame, Keyframe):
                raise ValueError(f"expected Keyframe instances, got {frame!r}")

        merged: dict[str, dict[str, str]] = {}
        for frame in sorted(frames, key=lambda frame: frame.t):
            props = _canonical_props(frame.props, f"keyframe at {frame.t}s")
            stop = self._timeline.pct(frame.t)
            if stop in merged:
                merged[stop].update(props)
            else:
                merged[stop] = props

        states = list(merged.values())
        if all(state == states[0] for state in states):
            raise ValueError(
                "track never changes any property: every keyframe carries "
                f"{states[0]!r}; a no-op track is dead bytes (add the starting state as "
                "an explicit frame if the change is relative to the base value)"
            )

        kept: list[tuple[str, dict[str, str]]] = []
        for stop, props in merged.items():
            if kept and kept[-1][1] == props:
                if easing == "step-end":
                    continue
                if len(kept) >= 2 and kept[-2][1] == props:
                    kept.pop()
            kept.append((stop, props))

        groups: dict[tuple[tuple[str, str], ...], list[str]] = {}
        for stop, props in kept:
            groups.setdefault(tuple(props.items()), []).append(stop)
        body = "".join(
            ",".join(f"{stop}%" for stop in stops)
            + "{"
            + ";".join(f"{name}:{value}" for name, value in state)
            + "}"
            for state, stops in groups.items()
        )
        return body, any("transform" in state for state in states)

    # -------------------------------------------------------------- rendering

    def _render_rule(self, rule: _Rule) -> str:
        declarations = [f"{name}:{value}" for name, value in rule.base.items()]
        # Shorthand, not longhands: "animation-name:..;animation-duration:..;..." costs
        # about 90 more bytes per rule, and there are hundreds of rules per file.  The
        # duration is always the first <time> token; the delay, when present, the second.
        shorthand = (
            f"animation:{rule.block_name} {_seconds(self._timeline.duration)} {rule.easing}"
        )
        delay = _seconds(rule.delay)
        if delay != "0s":
            shorthand += f" {delay}"
        declarations.append(shorthand + " infinite")
        if rule.transform_origin:
            # CSS boxes default to "50% 50%", SVG elements to "0 0", and which model an
            # engine applies to an element inside an <img>-loaded SVG is not something to
            # rely on either way.  Emitted only where a transform is in play; on an
            # opacity-only rule it is dead bytes.
            declarations.append("transform-origin:0 0")
        return f".{rule.cls}{{{';'.join(declarations)}}}"

    def css(self) -> str:
        """Render, in order: ``@keyframes`` blocks, class rules, the reduced-motion block.

        Every class rule carries the same ``animation-duration`` -- the timeline's -- which
        is the sync guarantee ``tests/test_anim.py`` asserts.  Output is deterministic for a
        given call sequence, so regenerated assets diff cleanly day over day.
        """
        parts = [f"@keyframes {block.name}{{{body}}}" for body, block in self._blocks.items()]
        parts.extend(self._render_rule(rule) for rule in self._rules)
        parts.append(_REDUCED_MOTION)
        return "".join(parts)

    def stats(self) -> EmitterStats:
        return EmitterStats(
            keyframe_blocks=len(self._blocks),
            rules=len(self._rules),
            tracks=self._calls,
            bytes=len(self.css()),
        )
