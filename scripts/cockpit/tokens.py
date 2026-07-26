"""Design tokens for the profile cards.

One accent pair, one neutral ramp. Every other shade in the system is an
opacity or luminance step of these values - adding a hue here is the single
easiest way to make the page look assembled from parts.
"""

from __future__ import annotations

# --- colour ---------------------------------------------------------------

VOID = "#07070A"      # page backdrop, the cabin at night
PANEL = "#0E0F16"     # card fill
PANEL_HI = "#141724"  # raised surface inside a card
HAIRLINE = "#1C1F2B"  # 1px structure
ROSE = "#FF2D75"      # hot zone
ICE = "#3AA0FF"       # cold zone
TEXT = "#E8EBF2"
MUTED = "#79808F"
DIM = "#4A5160"

# Luminance steps, used where a chart needs more than two levels. These stay
# inside the rose and ice families on purpose: hue carries meaning, brightness
# carries detail. See VERDICT_COLORS for the payoff.
ROSE_BRIGHT = "#FF6E9C"
ROSE_DEEP = "#B21048"
ICE_BRIGHT = "#8CCBFF"
ICE_DEEP = "#1B6AC4"

# Codeforces verdicts. Ice means the judge accepted it, rose means it did not,
# and brightness separates the failure modes. A reader learns the whole legend
# from two colours instead of six.
VERDICT_COLORS = {
    "OK": ICE,
    "WRONG_ANSWER": ROSE,
    "TIME_LIMIT_EXCEEDED": ROSE_BRIGHT,
    "RUNTIME_ERROR": ROSE_DEEP,
    "MEMORY_LIMIT_EXCEEDED": "#8C1F5A",
    "COMPILATION_ERROR": ICE_DEEP,
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

# Contribution heat ramp for the activity strip: empty, then four steps
# walking ice to rose so the busiest days read hot.
HEAT = [PANEL_HI, "#173653", ICE_DEEP, "#7C4A8E", ROSE]

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
