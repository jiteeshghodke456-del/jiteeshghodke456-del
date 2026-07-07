#!/usr/bin/env python3
"""Dress up a Platane/snk contribution snake.

Adds a themed card frame, a glowing head with directional eyes, an
eat-pulse ring on every consumed cell, a devoured-days counter, and one
extra gradient tail segment per active contribution day eaten.
"""

from __future__ import annotations

import argparse
import pathlib
import re


STYLE_MARKER_START = "/* profile-growing-snake:start */"
STYLE_MARKER_END = "/* profile-growing-snake:end */"
ELEMENT_MARKER_START = "<!-- profile-growing-snake:start -->"
ELEMENT_MARKER_END = "<!-- profile-growing-snake:end -->"
UNDERLAY_MARKER_START = "<!-- profile-growing-snake:underlay-start -->"
UNDERLAY_MARKER_END = "<!-- profile-growing-snake:underlay-end -->"

THEMES = {
    "dark": {
        "bg": "#0D1117",
        "border": "#2B3642",
        "title": "#8B949E",
        "accent": "#F5C16C",
        "tail_from": "#F5C16C",
        "tail_to": "#F472B6",
        "pupil": "#0D1117",
    },
    "light": {
        "bg": "#FFFFFF",
        "border": "#D0D7DE",
        "title": "#57606A",
        "accent": "#B45309",
        "tail_from": "#E09B3D",
        "tail_to": "#DB2777",
        "pupil": "#FFFFFF",
    },
}


def extract_block(source: str, marker: str) -> str:
    start = source.find(marker)
    if start < 0:
        raise ValueError(f"missing CSS block: {marker}")
    opening = source.find("{", start)
    if opening < 0:
        raise ValueError(f"missing opening brace for: {marker}")

    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise ValueError(f"missing closing brace for: {marker}")


def parse_rules(block: str) -> list[tuple[list[float], str]]:
    rules: list[tuple[list[float], str]] = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", block):
        percentages = [
            float(value)
            for value in re.findall(r"(-?\d+(?:\.\d+)?)%", match.group(1))
        ]
        if percentages:
            rules.append((percentages, match.group(2)))
    return rules


def parse_route(css: str, animation_name: str = "s0") -> list[tuple[float, float, float]]:
    route: dict[float, tuple[float, float]] = {}
    for percentages, declarations in parse_rules(
        extract_block(css, f"@keyframes {animation_name}")
    ):
        transform = re.search(
            r"translate\(\s*(-?\d+(?:\.\d+)?)px\s*,\s*(-?\d+(?:\.\d+)?)px\s*\)",
            declarations,
        )
        if not transform:
            continue
        point = (float(transform.group(1)), float(transform.group(2)))
        for percentage in percentages:
            route[percentage] = point

    if 0.0 not in route:
        raise ValueError("snake route has no 0% keyframe")
    route.setdefault(100.0, route[0.0])
    return [(percentage, *route[percentage]) for percentage in sorted(route)]


def route_at(route: list[tuple[float, float, float]], percentage: float) -> tuple[float, float]:
    percentage %= 100.0
    for index in range(1, len(route)):
        p0, x0, y0 = route[index - 1]
        p1, x1, y1 = route[index]
        if percentage <= p1:
            if p1 == p0:
                return x1, y1
            ratio = (percentage - p0) / (p1 - p0)
            return x0 + (x1 - x0) * ratio, y0 + (y1 - y0) * ratio
    return route[-1][1], route[-1][2]


def movement_step(route: list[tuple[float, float, float]]) -> float:
    differences = [
        current[0] - previous[0]
        for previous, current in zip(route, route[1:])
        if current[0] - previous[0] > 0.1
    ]
    if not differences:
        raise ValueError("snake route has no movement intervals")
    return min(differences)


def consumption_events(css: str) -> list[tuple[float, str]]:
    """Return (percentage, cell class name) for every consumed cell, by time."""
    names = sorted(
        set(re.findall(r'class="c c(\d+)"', css)),
        key=int,
    )
    consumed: list[tuple[float, str]] = []
    for name in names:
        block = extract_block(css, f"@keyframes c{name}")
        times: list[float] = []
        for percentages, declarations in parse_rules(block):
            if "fill:var(--ce)" in declarations.replace(" ", ""):
                times.extend(value for value in percentages if value < 100)
        if times:
            consumed.append((min(times), f"c{name}"))
    return sorted(consumed)


def cell_color_vars(css: str) -> dict[str, str]:
    """Map cell class name to its resting fill variable, e.g. c3 -> --c2."""
    return {
        f"c{index}": f"--{variable}"
        for index, variable in re.findall(
            r"\.c\.c(\d+)\{fill:var\(--(c\d+)\)", css
        )
    }


def direction_windows(
    route: list[tuple[float, float, float]],
) -> list[tuple[float, float, str]]:
    """Split the route into (start%, end%, facing) windows."""
    windows: list[tuple[float, float, str]] = []
    facing: str | None = None
    for (p0, x0, y0), (p1, x1, y1) in zip(route, route[1:]):
        if p1 <= p0:
            continue
        dx, dy = x1 - x0, y1 - y0
        if dx == 0 and dy == 0:
            heading = facing or "R"
        elif abs(dx) >= abs(dy):
            heading = "R" if dx > 0 else "L"
        else:
            heading = "D" if dy > 0 else "U"
        if windows and windows[-1][2] == heading and windows[-1][1] >= p0:
            windows[-1] = (windows[-1][0], p1, heading)
        else:
            windows.append((p0, p1, heading))
        facing = heading
    return windows or [(0.0, 100.0, "R")]


def shifted_route_keyframes(
    route: list[tuple[float, float, float]],
    delay: float,
) -> str:
    breakpoints = {0.0, 100.0}
    breakpoints.update((percentage + delay) % 100.0 for percentage, _, _ in route)

    frames = []
    for percentage in sorted(breakpoints):
        x, y = route_at(route, percentage - delay)
        frames.append(
            f"{percentage:.2f}%{{transform:translate({x:.2f}px,{y:.2f}px)}}"
        )
    return "".join(frames)


def lerp_hex(start: str, end: str, ratio: float) -> str:
    start_value = int(start.lstrip("#"), 16)
    end_value = int(end.lstrip("#"), 16)
    channels = []
    for shift in (16, 8, 0):
        a = (start_value >> shift) & 255
        b = (end_value >> shift) & 255
        channels.append(round(a + (b - a) * ratio))
    return "#{:02X}{:02X}{:02X}".format(*channels)


def parse_view_box(svg: str) -> tuple[float, float, float, float]:
    match = re.search(
        r'viewBox="(-?[\d.]+)[ ,]+(-?[\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)"', svg
    )
    if not match:
        raise ValueError("snake SVG has no viewBox")
    return tuple(float(value) for value in match.groups())  # type: ignore[return-value]


def strip_existing_growth(svg: str) -> str:
    for start, end in (
        (STYLE_MARKER_START, STYLE_MARKER_END),
        (ELEMENT_MARKER_START, ELEMENT_MARKER_END),
        (UNDERLAY_MARKER_START, UNDERLAY_MARKER_END),
    ):
        svg = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            "",
            svg,
            flags=re.DOTALL,
        )
    return svg


def build_underlay(svg: str, theme: dict[str, str], eaten: int) -> str:
    x, y, width, height = parse_view_box(svg)
    dots = []
    for index in range(10):
        dot_x = x + 22 + (index * 97 + 31) % max(1.0, width - 44)
        dot_y = y + 26 + (index * 53 + 17) % max(1.0, height - 44)
        dots.append(
            f'<circle cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="{1.0 + (index % 3) * 0.4:.1f}" '
            f'fill="{theme["accent"]}" opacity="{0.05 + (index % 4) * 0.02:.2f}"/>'
        )
    label = f"{eaten} DAY{'S' if eaten != 1 else ''} DEVOURED"
    return (
        f"{UNDERLAY_MARKER_START}"
        f'<defs><filter id="pgs-glow" x="-80%" y="-80%" width="260%" height="260%">'
        f'<feGaussianBlur stdDeviation="1.6" result="blur"/>'
        f'<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>'
        f"</filter></defs>"
        f'<g class="pgs-underlay">'
        f'<rect x="{x + 0.5:.1f}" y="{y + 0.5:.1f}" width="{width - 1:.1f}" '
        f'height="{height - 1:.1f}" rx="12" fill="{theme["bg"]}" stroke="{theme["border"]}"/>'
        f"{''.join(dots)}"
        f'<text class="pgs-title" x="{x + 14:.1f}" y="{y + 21:.1f}">SNAKE.EXE</text>'
        f'<text class="pgs-title pgs-count" x="{x + width - 14:.1f}" y="{y + 21:.1f}" '
        f'text-anchor="end">{label}</text>'
        f"</g>{UNDERLAY_MARKER_END}"
    )


def build_head(
    route: list[tuple[float, float, float]],
    duration: int,
    theme: dict[str, str],
) -> tuple[list[str], list[str]]:
    styles = [
        f"@keyframes pgs_head{{{shifted_route_keyframes(route, 0.0)}}}",
        ".pgs-head-track{animation:pgs_head "
        f"{duration}ms linear infinite;"
        f"transform:translate({route[0][1]:.2f}px,{route[0][2]:.2f}px)}}",
    ]
    eye_layouts = {
        "R": ((10.6, 5.2), (10.6, 10.8)),
        "L": ((5.4, 5.2), (5.4, 10.8)),
        "D": ((5.2, 10.6), (10.8, 10.6)),
        "U": ((5.2, 5.4), (10.8, 5.4)),
    }
    windows = direction_windows(route)
    eye_groups = []
    for heading, positions in eye_layouts.items():
        frames: list[tuple[float, int]] = []
        for start, _, window_heading in windows:
            value = 1 if window_heading == heading else 0
            if frames and frames[-1][1] == value:
                continue
            frames.append((start, value))
        if not any(value for _, value in frames):
            continue
        frames.append((100.0, frames[0][1]))
        keyframes = "".join(
            f"{pct:.2f}%{{opacity:{value}}}" for pct, value in frames
        )
        styles.append(f"@keyframes pgs_eyes_{heading}{{{keyframes}}}")
        styles.append(
            f".pgs-eyes-{heading}{{animation:pgs_eyes_{heading} "
            f"{duration}ms step-end infinite;opacity:0}}"
        )
        pupils = "".join(
            f'<circle cx="{cx}" cy="{cy}" r="1.7" fill="{theme["pupil"]}"/>'
            for cx, cy in positions
        )
        eye_groups.append(f'<g class="pgs-eyes pgs-eyes-{heading}">{pupils}</g>')

    elements = [
        '<g class="pgs-fx pgs-head-track">'
        '<g filter="url(#pgs-glow)">'
        '<rect x="0.5" y="0.5" width="15" height="15" rx="5" fill="var(--cs)"/>'
        f"{''.join(eye_groups)}"
        "</g></g>"
    ]
    return styles, elements


def build_rings(
    events: list[tuple[float, str]],
    route: list[tuple[float, float, float]],
    colors: dict[str, str],
    duration: int,
    theme: dict[str, str],
) -> tuple[list[str], list[str]]:
    styles: list[str] = []
    elements: list[str] = []
    for index, (at, cell_name) in enumerate(events):
        x, y = route_at(route, at)
        variable = colors.get(cell_name)
        stroke = f"var({variable})" if variable else theme["accent"]
        pre = max(0.0, at - 1.2)
        post = min(99.6, at + 2.6)
        styles.append(
            f"@keyframes pgs_ring_{index}{{"
            f"0%,{pre:.2f}%{{opacity:0;transform:scale(0.25)}}"
            f"{at:.2f}%{{opacity:0.9;transform:scale(0.55)}}"
            f"{post:.2f}%,100%{{opacity:0;transform:scale(1.35)}}"
            "}"
        )
        styles.append(
            f".pgs-ring.pgs-r{index}{{animation:pgs_ring_{index} "
            f"{duration}ms linear infinite;opacity:0;transform:scale(0.25)}}"
        )
        elements.append(
            f'<g class="pgs-fx" transform="translate({x + 8:.2f} {y + 8:.2f})">'
            f'<g class="pgs-ring pgs-r{index}">'
            f'<circle r="8.5" fill="none" stroke="{stroke}" stroke-width="2"/>'
            "</g></g>"
        )
    return styles, elements


def enhance_svg(svg: str, theme_name: str = "dark") -> tuple[str, int]:
    svg = strip_existing_growth(svg)
    theme = THEMES[theme_name]
    events = consumption_events(svg)
    if not events:
        return svg, 0

    duration_match = re.search(r"\.s\s*\{[^}]*?(\d+)ms", svg, re.DOTALL)
    if not duration_match:
        raise ValueError("could not determine snake animation duration")
    duration = int(duration_match.group(1))

    route = parse_route(svg)
    step = movement_step(route)
    base_segments = len(set(re.findall(r'class="s s(\d+)"', svg)))
    if not base_segments:
        raise ValueError("could not determine the base snake length")

    styles = [STYLE_MARKER_START]
    elements = [ELEMENT_MARKER_START]

    styles.append(
        ".pgs-title{font:700 11px 'Space Mono','SFMono-Regular',Consolas,monospace;"
        f"fill:{theme['title']};letter-spacing:2px}}"
    )
    styles.append(f".pgs-count{{fill:{theme['accent']}}}")

    total = len(events)
    for growth_index, (reveal_at, _) in enumerate(events):
        segment_index = base_segments + growth_index
        delay = segment_index * step
        path_name = f"grow_path_{growth_index}"
        reveal_name = f"grow_reveal_{growth_index}"
        reveal_before = max(0.0, reveal_at - 0.02)

        tail_age = max(0, growth_index - 20)
        opacity = max(0.22, 0.92 - tail_age * 0.025)
        size = max(3.8, 9.2 - growth_index * 0.18)
        inset = (16.0 - size) / 2
        radius = min(4.0, size / 2.5)
        tint = lerp_hex(
            theme["tail_from"],
            theme["tail_to"],
            growth_index / max(1, total - 1),
        )
        initial_x, initial_y = route_at(route, -delay)

        styles.append(
            f"@keyframes {path_name}{{{shifted_route_keyframes(route, delay)}}}"
        )
        styles.append(
            f"@keyframes {reveal_name}{{"
            f"0%,{reveal_before:.2f}%{{opacity:0}}"
            f"{reveal_at:.2f}%,100%{{opacity:{opacity:.2f}}}"
            "}"
        )
        styles.append(
            f".grow-segment.g{growth_index}{{"
            f"fill:{tint};"
            f"transform:translate({initial_x:.2f}px,{initial_y:.2f}px);"
            f"animation:{path_name} {duration}ms linear infinite,"
            f"{reveal_name} {duration}ms step-end infinite"
            "}"
        )
        elements.append(
            f'<rect class="s grow-segment g{growth_index}" '
            f'x="{inset:.2f}" y="{inset:.2f}" width="{size:.2f}" height="{size:.2f}" '
            f'rx="{radius:.2f}" ry="{radius:.2f}"/>'
        )

    ring_styles, ring_elements = build_rings(
        events, route, cell_color_vars(svg), duration, theme
    )
    head_styles, head_elements = build_head(route, duration, theme)
    styles.extend(ring_styles)
    styles.extend(head_styles)
    elements.extend(ring_elements)
    elements.extend(head_elements)

    styles.append(
        "@media (prefers-reduced-motion:reduce){"
        ".c,.u,.s{animation:none!important}"
        ".grow-segment{display:none}"
        ".pgs-fx{display:none}"
        "}"
    )
    styles.append(STYLE_MARKER_END)
    elements.append(ELEMENT_MARKER_END)

    if "</style>" not in svg or "</svg>" not in svg:
        raise ValueError("invalid SVG structure")
    svg_open_end = svg.index(">", svg.index("<svg")) + 1
    underlay = build_underlay(svg, theme, len(events))
    svg = svg[:svg_open_end] + underlay + svg[svg_open_end:]
    svg = svg.replace("</style>", "".join(styles) + "</style>", 1)
    svg = svg.replace("</svg>", "".join(elements) + "</svg>", 1)
    return svg, len(events)


def process_file(path: pathlib.Path) -> int:
    theme_name = "dark" if "dark" in path.stem else "light"
    original = path.read_text(encoding="utf-8")
    enhanced, count = enhance_svg(original, theme_name)
    path.write_text(enhanced, encoding="utf-8")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    args = parser.parse_args()

    for path in args.paths:
        count = process_file(path)
        print(f"{path}: added {count} contribution-driven tail segments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
