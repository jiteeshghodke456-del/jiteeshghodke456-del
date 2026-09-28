"""CH.06 INVENTORY: the languages, as loot.

Bytes on disk across every non-fork repository, not a list of things that sound good in a
profile. Each language drops into a slot and bounces, and its rarity is its share of the
total: the thing I actually write most is the legendary drop, which is the joke and also the
honest reading. The last slot is locked, because that is where the things I am learning live.

Below the bag is the hotbar: what I ship with, one selected at a time.
"""

from __future__ import annotations

from .. import fx, icons, mascot, scene, tokens
from ..typography import fmt
from .stack import LEARNING, SHIPS_IN, top_languages

T = 14.0
REVEAL = (0.0, 0.8)
COVER = (13.2, 14.0)
DROP_AT = 1.0
DROP_STAGGER = 0.28
SLOTS = 8

ICON_FOR = {
    "TypeScript": "typescript",
    "Python": "python",
    "CSS": "css",
    "JavaScript": "javascript",
    "C++": "cplusplus",
    "PLpgSQL": "postgresql",
    "HTML": "html5",
    "Rust": "rust",
    "Shell": "linux",
}

RARITY = (
    (0.40, "LEGENDARY", tokens.ACID),
    (0.12, "EPIC", tokens.HOT_VIOLET),
    (0.04, "RARE", tokens.EMERALD),
    (0.015, "UNCOMMON", tokens.VIOLET_BRIGHT),
    (0.0, "COMMON", tokens.MUTED),
)


def rarity(share: float) -> tuple[str, str]:
    for floor, name, color in RARITY:
        if share >= floor:
            return name, color
    return RARITY[-1][1], RARITY[-1][2]


def _bytes(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.2f} MB"
    if count >= 1_000:
        return f"{count / 1_000:.0f} KB"
    return f"{count} B"


def _slot(s: scene.Scene, index: int, x: float, y: float, w: float, h: float,
          item: tuple[str, int] | None, total: int) -> str:
    narrow = s.narrow
    clip = s.ids.next()
    s.defs.append(f'<clipPath id="{clip}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="6"/></clipPath>')
    parts = [f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" rx="6" fill="{tokens.PANEL}"/>']
    inner = f'<rect x="{fmt(x + 5)}" y="{fmt(y + 5)}" width="{fmt(w - 10)}" height="{fmt(h - 10)}" rx="3" fill="{tokens.PLUM}"/>'
    parts.append(inner)
    icon_size = 30 if narrow else 40
    cx = x + w / 2

    if item is None:
        # Locked: chains across a dim silhouette of what is being learned.
        slug = next((slug for slug in LEARNING if icons.has(slug)), None)
        content = ""
        if slug:
            content += icons.icon(slug, cx - icon_size / 2, y + (22 if narrow else 30), icon_size, fill=tokens.DIM, opacity=0.6)
        chain = "".join(
            f'<rect x="{fmt(x + 10 + k * 14)}" y="{fmt(y + h * 0.42 + (k % 2) * 3)}" width="10" height="5" rx="2.5"'
            f' fill="none" stroke="{tokens.MUTED}" stroke-width="1.5"/>'
            for k in range(int((w - 20) / 14))
        )
        rattle = fx.jitter(s.anim, [3.3, 8.8], T, amp=3, seed=71)
        lock_y = y + h * 0.42 + 2
        lock = (
            f'<rect x="{fmt(cx - 9)}" y="{fmt(lock_y - 4)}" width="18" height="14" rx="2" fill="{tokens.VIOLET_DEEP}"'
            f' stroke="{tokens.VIOLET_BRIGHT}"/>'
            f'<path d="M{fmt(cx - 5)} {fmt(lock_y - 4)}v-5a5 5 0 0 1 10 0v5" stroke="{tokens.VIOLET_BRIGHT}" stroke-width="2" fill="none"/>'
        )
        content += fx.wrap(rattle, chain + lock)
        names = ", ".join(icons.label(slug) for slug in LEARNING if icons.has(slug)) or "SOON"
        content += s.setter.text(cx, y + h - (30 if narrow else 36), "LOCKED", face=tokens.ARCADE, size=8 if narrow else 9,
                                 fill=tokens.MUTED, anchor="middle")
        content += s.setter.text(cx, y + h - (16 if narrow else 18), f"learning {names}", face=tokens.MONO,
                                 size=9 if narrow else 10, fill=tokens.DIM, anchor="middle")
        parts.append(content)
        parts.append(f'<rect x="{fmt(x + 0.5)}" y="{fmt(y + 0.5)}" width="{fmt(w - 1)}" height="{fmt(h - 1)}" rx="6"'
                     f' fill="none" stroke="{tokens.HAIRLINE}" stroke-dasharray="4 3"/>')
        return "".join(parts)

    name, count = item
    share = count / total if total else 0
    tier, color = rarity(share)
    slug = ICON_FOR.get(name)
    # Rarity border, doubled for the top tiers, pulsing on the legendary one.
    border = fx.glow_rect(x, y, w, h, color, radius=6, stroke=1.5 if tier != "COMMON" else 1)
    if tier == "LEGENDARY":
        pulse = fx.track(
            s.anim,
            fx.steps([(0.0, {"opacity": "0.35"}), (T / 4, {"opacity": "1"}), (T / 2, {"opacity": "0.35"}),
                      (3 * T / 4, {"opacity": "1"})], T),
            easing="ease-in-out",
        )
        border += fx.wrap(pulse, fx.glow_rect(x - 3, y - 3, w + 6, h + 6, color, radius=8, stroke=1,
                                              spread=((8, 0.1), (4, 0.18))))
    parts.append(border)

    drop = DROP_AT + index * DROP_STAGGER
    content = ""
    icon_y = y + (20 if narrow else 28)
    if slug and icons.has(slug):
        content += icons.icon(slug, cx - icon_size / 2, icon_y, icon_size, fill=color if tier != "COMMON" else tokens.TEXT)
    else:
        content += s.setter.text(cx, icon_y + icon_size * 0.75, name[:2].upper(), face=tokens.ARCADE,
                                 size=icon_size * 0.5, fill=color, anchor="middle")
    name_y = icon_y + icon_size + (16 if narrow else 22)
    name_size = 8 if narrow else 9.5
    label = name.upper()
    while s.setter.width(label, tokens.ARCADE, name_size) > w - 16 and name_size > 6:
        name_size -= 0.5
    content += s.setter.text(cx, name_y, label, face=tokens.ARCADE, size=name_size, fill=tokens.TEXT, anchor="middle")
    qty = f"x {_bytes(count)} · {share * 100:.0f}%" if share >= 0.01 else f"x {_bytes(count)} · <1%"
    content += s.setter.text(cx, name_y + (14 if narrow else 17), qty, face=tokens.MONO, size=9 if narrow else 10,
                             fill=tokens.MUTED, anchor="middle")
    fall = fx.track(
        s.anim,
        fx.steps([(0.0, {"transform": f"translate(0px,{fmt(-h)}px)", "opacity": "0"}),
                  (drop - fx.HOLD, {"transform": f"translate(0px,{fmt(-h)}px)", "opacity": "0"}),
                  (drop, {"transform": f"translate(0px,{fmt(-h)}px)", "opacity": "1"}),
                  (drop + 0.45, {"transform": "translate(0px,0px)", "opacity": "1"}),
                  (T - fx.HOLD, {"transform": "translate(0px,0px)", "opacity": "1"})], T),
        easing="cubic-bezier(0.34,1.56,0.64,1)",
    )
    pill_w = s.setter.width(tier, tokens.DISPLAY, 7, tokens.TRACK_LABEL) + 12
    pill = (
        f'<rect x="{fmt(x + 9)}" y="{fmt(y + 9)}" width="{fmt(pill_w)}" height="13" rx="2" fill="{color}" opacity="0.18"/>'
        + s.setter.text(x + 15, y + 19, tier, face=tokens.DISPLAY, size=7, fill=color, tracking=tokens.TRACK_LABEL)
    )
    # Share bar along the bottom of the slot.
    bar_w = w - 24
    bar = (
        f'<rect x="{fmt(x + 12)}" y="{fmt(y + h - 13)}" width="{fmt(bar_w)}" height="4" fill="{tokens.GRAPE}"/>'
        f'<rect x="{fmt(x + 12)}" y="{fmt(y + h - 13)}" width="{fmt(max(2, bar_w * share))}" height="4" fill="{color}"/>'
    )
    parts.append(f'<g clip-path="url(#{clip})">{fx.wrap(fall, content)}</g>')
    parts.append(pill + bar)
    parts.append(fx.burst(s.anim, cx, y + h - 20, [drop + 0.45], T, count=8, radius=34, size=3, life=0.5,
                          colors=(color, tokens.TEXT), seed=100 + index))

    if tier == "LEGENDARY":
        sweep = fx.track(
            s.anim,
            fx.steps([p for at in (3.4, 6.4, 9.4, 12.0) for p in (
                (at - fx.HOLD, {"transform": "translate(0px,0px)", "opacity": "0"}),
                (at, {"transform": "translate(0px,0px)", "opacity": "1"}),
                (at + 0.8, {"transform": f"translate({fmt(w + h)}px,0px)", "opacity": "1"}),
                (at + 0.8 + fx.HOLD, {"transform": "translate(0px,0px)", "opacity": "0"}),
            )] + [(0.0, {"transform": "translate(0px,0px)", "opacity": "0"})], T),
            easing="ease-in-out",
            base={"opacity": "0"},
        )
        grad = s.ids.next()
        s.defs.append(
            f'<linearGradient id="{grad}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.55"/>'
            f'<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
        )
        band = f'<path d="M-40 {fmt(h)}L0 0H34L-6 {fmt(h)}Z" fill="url(#{grad})"/>'
        parts.append(f'<g clip-path="url(#{clip})">{fx.place(x - 40, y, sweep, band)}</g>')
    return "".join(parts)


def _hotbar(s: scene.Scene, x: float, y: float, slot: float) -> tuple[str, float]:
    slugs = [slug for slug in SHIPS_IN if icons.has(slug)]
    gap = 6
    parts = [s.setter.text(x, y - 10, "HOTBAR · SHIPS WITH", face=tokens.ARCADE, size=8 if s.narrow else 9,
                           fill=tokens.VIOLET_BRIGHT, tracking=tokens.TRACK_ARCADE)]
    for k, slug in enumerate(slugs):
        sx = x + k * (slot + gap)
        parts.append(f'<rect x="{fmt(sx)}" y="{fmt(y)}" width="{fmt(slot)}" height="{fmt(slot)}" rx="4" fill="{tokens.PANEL}"'
                     f' stroke="{tokens.HAIRLINE}"/>')
        pad = slot * 0.22
        parts.append(icons.icon(slug, sx + pad, y + pad, slot - pad * 2, fill=tokens.ACID_BRIGHT, opacity=0.85))
        parts.append(s.setter.text(sx + 4, y + 10, str(k + 1), face=tokens.ARCADE, size=6, fill=tokens.DIM))
    # The selector walks the bar, pausing on each tool long enough to read its name.
    start, beat = 3.2, (COVER[0] - 3.4) / max(1, len(slugs))
    points: list[tuple[float, dict]] = [(0.0, {"transform": "translate(0px,0px)", "opacity": "0"}),
                                        (start - fx.HOLD, {"transform": "translate(0px,0px)", "opacity": "0"})]
    label_parts = []
    for k, slug in enumerate(slugs):
        at = start + k * beat
        points.append((at, {"transform": f"translate({fmt(k * (slot + gap))}px,0px)", "opacity": "1"}))
        cls = fx.track(s.anim, fx.windows([(at, at + beat)], T))
        label_parts.append(fx.wrap(cls, s.setter.text(x + len(slugs) * (slot + gap) + 10, y + slot / 2 + 4,
                                                      icons.label(slug), face=tokens.MONO_SEMI,
                                                      size=11 if not s.narrow else 10, fill=tokens.ACID), hidden=True)
                           if not s.narrow else
                           fx.wrap(cls, s.setter.text(x, y + slot + 18, icons.label(slug), face=tokens.MONO_SEMI,
                                                      size=10, fill=tokens.ACID), hidden=True))
    points.append((COVER[0], {"transform": f"translate({fmt((len(slugs) - 1) * (slot + gap))}px,0px)", "opacity": "0"}))
    sel = fx.track(s.anim, fx.steps(points, T), base={"opacity": "0"})
    parts.append(fx.place(x, y, sel, fx.glow_rect(-2, -2, slot + 4, slot + 4, tokens.ACID, radius=5, stroke=2)))
    parts.extend(label_parts)
    return "".join(parts), y + slot + (26 if s.narrow else 8)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    s = scene.Scene(width, T, prefix="i")
    narrow = s.narrow
    left = s.pad + 8
    right = width - s.pad - 8
    languages = top_languages(dict(data.get("languages") or {}), limit=SLOTS - 1, floor=0.001)
    languages = [(name, count) for name, count in languages if name != "Other"][: SLOTS - 1]
    total = sum(dict(data.get("languages") or {}).values()) or 1
    repos = int(data.get("repo_count") or 0)

    s.body.append(s.setter.text(left, 76, "THE BAG", face=tokens.ARCADE, size=10 if narrow else 12,
                                fill=tokens.ACID, tracking=tokens.TRACK_ARCADE))
    summary = f"{_bytes(total)} of code across {repos} repos, weighed in bytes"
    if narrow:
        summary = f"{_bytes(total)} across {repos} repos"
    s.body.append(s.setter.text(right, 76, summary, face=tokens.MONO, size=9.5 if narrow else 10.5,
                                fill=tokens.MUTED, anchor="end"))

    cols = 2 if narrow else 4
    gap = 12 if narrow else 16
    slot_w = (right - left - gap * (cols - 1)) / cols
    slot_h = 132 if narrow else 158
    top = 92
    items: list[tuple[str, int] | None] = list(languages) + [None] * (SLOTS - len(languages))
    items = items[:SLOTS]
    for index, item in enumerate(items):
        col, row = index % cols, index // cols
        s.body.append(_slot(s, index, left + col * (slot_w + gap), top + row * (slot_h + gap), slot_w, slot_h,
                            item, total))
    rows = -(-SLOTS // cols)
    grid_bottom = top + rows * slot_h + (rows - 1) * gap

    bar_y = grid_bottom + 42
    px = 3
    if narrow:
        hot, bottom = _hotbar(s, left, bar_y, 44)
    else:
        bit_w = mascot.width(px)
        hot, bottom = _hotbar(s, left + bit_w + 24, bar_y, 48)
        s.body.append(mascot.bit(s.anim, T, left + 4, bar_y + 48 - mascot.height(px), px,
                                 walk=(-120, 0.9, 2.4), point=[(3.2, 12.6)], blinks=[4.1, 7.7, 11.2], bob=None))
    s.body.append(hot)

    cf_langs = (data.get("codeforces") or {}).get("languages") or {}
    cf_top = max(cf_langs.items(), key=lambda row: row[1])[0] if cf_langs else ""
    cf_top = cf_top.split(" ")[0] if cf_top else ""
    gh_top = languages[0][0] if languages else ""
    caption = f"GitHub says {gh_top}. Codeforces says {cf_top}." if cf_top and gh_top else ""
    cap_y = bottom + (18 if narrow else 30)
    if caption:
        s.body.append(s.setter.text(left, cap_y, caption, face=tokens.MONO, size=10.5 if narrow else 11.5,
                                    fill=tokens.TEXT, opacity=0.7))
    height = cap_y + 22

    s.front.append(fx.dissolve(s.anim, 0, 0, width, height, T, reveal=REVEAL, cover=COVER, cell=20, groups=10))

    return s.render(
        height,
        chapter=5,
        title="Inventory: languages measured in bytes, shown as loot",
        description="Chapter six, inventory. " + ", ".join(
            f"{name} {count / total * 100:.0f} percent, {rarity(count / total)[0].lower()}" for name, count in languages
        ) + ". The last slot is locked: learning " + ", ".join(icons.label(s_) for s_ in LEARNING if icons.has(s_)) + ".",
        note="MEASURED IN BYTES",
    )
