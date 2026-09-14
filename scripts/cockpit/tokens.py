"""Design tokens for the profile cards.

One accent pair, one neutral ramp. Every other shade in the system is an
opacity or luminance step of these values - adding a hue here is the single
easiest way to make the page look assembled from parts.
"""

from __future__ import annotations

# --- colour ---------------------------------------------------------------
#
# One accent pair, one neutral ramp -- the discipline this file already had,
# rotated onto a green/purple axis. The pair is not decoration: across the
# Codeforces board the two dominant verdicts are 75 accepted and 96 rejected,
# so acid green against neon violet makes the real data legible AND lands the
# intended look with nothing cherry-picked.

VOID = "#04060A"      # page backdrop, the cabin at night
PANEL = "#080C12"     # card fill
PANEL_HI = "#0F1520"  # raised surface inside a card
HAIRLINE = "#1B2A22"  # 1px structure, faintly green so it reads as phosphor
ACID = "#39FF14"      # signal: accepted, alive, lit
VIOLET = "#9D4EFF"    # counter-signal: rejected, idle, cold
TEXT = "#D6FFE4"
MUTED = "#5E8570"
DIM = "#38493F"

# Back-compat aliases. The card modules were written against the rose/ice
# names; keeping them pointed at the new pair means the palette rotates in one
# place instead of scattering find-and-replace across every card.
ROSE = VIOLET
ICE = ACID

# Luminance steps. Hue carries meaning, brightness carries detail -- so a
# reader learns the whole legend from two colours instead of six.
ACID_BRIGHT = "#B4FFA3"
ACID_DEEP = "#149B2C"
VIOLET_BRIGHT = "#C99EFF"
VIOLET_DEEP = "#5B21B6"
ROSE_BRIGHT = VIOLET_BRIGHT
ROSE_DEEP = VIOLET_DEEP
ICE_BRIGHT = ACID_BRIGHT
ICE_DEEP = ACID_DEEP

# Codeforces verdicts. Green means the judge accepted it, violet means it did
# not, and brightness separates the failure modes.
VERDICT_COLORS = {
    "OK": ACID,
    "WRONG_ANSWER": VIOLET,
    "TIME_LIMIT_EXCEEDED": VIOLET_BRIGHT,
    "RUNTIME_ERROR": VIOLET_DEEP,
    "MEMORY_LIMIT_EXCEEDED": "#7A2BC4",
    "COMPILATION_ERROR": ACID_DEEP,
    "OTHER": DIM,
}

VERDICT_LABELS = {
    "OK": "accepted",
    "WRONG_ANSWER": "wrong answer",
    "TIME_LIMIT_EXCEEDED": "too slow",
    "RUNTIME_ERROR": "runtime error",
    "MEMORY_LIMIT_EXCEEDED": "out of memory",
    "COMPILATION_ERROR": "did not compile",
    "OTHER": "other",
}

# Contribution heat ramp: empty, then four steps walking violet to acid so the
# busiest days read hot.
HEAT = [PANEL_HI, "#2A1046", VIOLET_DEEP, "#2F8F3A", ACID]

# Nokia 3310 LCD, backlit: dark ground, bright pixels. Terrain levels stay in
# the mid greens deliberately -- if the busiest contribution day is as bright as
# the snake, the snake stops being findable and the panel reads as noise.
NOKIA = {
    "shell": "#0B1014",
    "bezel": "#05080A",
    "screen": "#081509",
    "l0": "#0C2110",
    "l1": "#16451F",
    "l2": "#1F6B2C",
    "l3": "#2A9B3C",
    "l4": "#35C74A",
    "snake": "#EAFFF0",
    "snake_dim": "#9CFFB8",
}

# Game Boy DMG had four shades of green. These are those four, pushed to neon
# and inverted to a backlit reading -- dark ground, bright pixels -- which is
# exactly how a DMG looks with a light behind it.
GB = ["#061A0B", "#0F4D22", "#1FA34A", ACID]

# --- canvas ---------------------------------------------------------------

WIDE = 880            # desktop card width; README renders around this
NARROW = 420          # mobile card width
PAD = 28              # card padding, desktop
PAD_NARROW = 18
RADIUS = 14           # card corner radius

# --- type -----------------------------------------------------------------

DISPLAY = "display"
MONO = "mono"
MONO_SEMI = "mono-semibold"

# Tracking in 1/1000 em. Wide display caps need air; mono does not.
TRACK_NAMEPLATE = 60
TRACK_EYEBROW = 180
TRACK_LABEL = 120

# --- motion ---------------------------------------------------------------

# One sweep, then rest. Instruments settle; they do not idle at a wobble.
SWEEP_DURATION = 1.6
SWEEP_EASE = "0.16 0.9 0.2 1"
TETRIS_CYCLE = 14.0


# --- colour maths ---------------------------------------------------------


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        *(max(0, min(255, round(channel))) for channel in rgb)
    )


def lerp(start: str, end: str, amount: float) -> str:
    """Blend two hex colours; ``amount`` 0 returns ``start``, 1 returns ``end``."""
    amount = max(0.0, min(1.0, amount))
    return _hex(
        tuple(a + (b - a) * amount for a, b in zip(_rgb(start), _rgb(end)))
    )


def bevel(base: str) -> tuple[str, str, str]:
    """Return ``(light, base, dark)`` for a bevelled block face.

    Lightening blends toward white rather than scaling the channels up: scaling a
    near-saturated neon green just clips to the same colour and the bevel vanishes,
    which is the whole reason the blocks would stop reading as three-dimensional.
    """
    return lerp(base, "#FFFFFF", 0.45), base, _hex(
        tuple(channel * 0.42 for channel in _rgb(base))
    )
