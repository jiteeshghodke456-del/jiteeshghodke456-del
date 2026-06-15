#!/usr/bin/env python3
"""Add contribution-driven tail growth to a Platane/snk SVG."""

from __future__ import annotations

import argparse
import pathlib
import re


STYLE_MARKER_START = "/* profile-growing-snake:start */"
STYLE_MARKER_END = "/* profile-growing-snake:end */"
ELEMENT_MARKER_START = "<!-- profile-growing-snake:start -->"
ELEMENT_MARKER_END = "<!-- profile-growing-snake:end -->"


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


def consumption_times(css: str) -> list[float]:
    names = sorted(
        set(re.findall(r'class="c c(\d+)"', css)),
        key=int,
    )
    consumed: list[float] = []
    for name in names:
        block = extract_block(css, f"@keyframes c{name}")
        times: list[float] = []
        for percentages, declarations in parse_rules(block):
            if "fill:var(--ce)" in declarations.replace(" ", ""):
                times.extend(value for value in percentages if value < 100)
        if times:
            consumed.append(min(times))
    return sorted(consumed)


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


def strip_existing_growth(svg: str) -> str:
    svg = re.sub(
        re.escape(STYLE_MARKER_START)
        + r".*?"
        + re.escape(STYLE_MARKER_END),
        "",
        svg,
        flags=re.DOTALL,
    )
    return re.sub(
        re.escape(ELEMENT_MARKER_START)
        + r".*?"
        + re.escape(ELEMENT_MARKER_END),
        "",
        svg,
        flags=re.DOTALL,
    )


def enhance_svg(svg: str) -> tuple[str, int]:
    svg = strip_existing_growth(svg)
    consumed = consumption_times(svg)
    if not consumed:
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

    for growth_index, reveal_at in enumerate(consumed):
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

    styles.append(
        "@media (prefers-reduced-motion:reduce){"
        ".c,.u,.s{animation:none!important}"
        ".grow-segment{display:none}"
        "}"
    )
    styles.append(STYLE_MARKER_END)
    elements.append(ELEMENT_MARKER_END)

    if "</style>" not in svg or "</svg>" not in svg:
        raise ValueError("invalid SVG structure")
    svg = svg.replace("</style>", "".join(styles) + "</style>", 1)
    svg = svg.replace("</svg>", "".join(elements) + "</svg>", 1)
    return svg, len(consumed)


def process_file(path: pathlib.Path) -> int:
    original = path.read_text(encoding="utf-8")
    enhanced, count = enhance_svg(original)
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
