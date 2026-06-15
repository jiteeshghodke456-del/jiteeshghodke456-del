#!/usr/bin/env python3
"""Generate stable SVG assets for the GitHub profile README."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser


PALETTE = {
    "bg": "#0D1117",
    "panel": "#111820",
    "panel_2": "#17212B",
    "border": "#2B3642",
    "text": "#D8DEE9",
    "muted": "#8B949E",
    "gold": "#F5C16C",
    "cream": "#F7E7C4",
    "blue": "#7DD3FC",
    "pink": "#F472B6",
    "green": "#98C379",
    "red": "#EF6B73",
    "orange": "#FF7A3D",
}

CODEFORCES_COLORS = {
    "OK": PALETTE["green"],
    "WRONG_ANSWER": PALETTE["pink"],
    "TIME_LIMIT_EXCEEDED": PALETTE["gold"],
    "MEMORY_LIMIT_EXCEEDED": "#D19A66",
    "COMPILATION_ERROR": PALETTE["blue"],
    "RUNTIME_ERROR": PALETTE["red"],
    "OTHER": "#6B7280",
}

PROJECTS = [
    {
        "name": "Atelier",
        "status": "COMING SOON",
        "category": "PERSONAL SYSTEMS",
        "description": "A calm workspace for unruly ideas.",
        "aside": "Risk: building the tool before the task.",
        "accent": PALETTE["gold"],
        "symbol": "A",
    },
    {
        "name": "Stenokun",
        "status": "COMING SOON",
        "category": "SYSTEMS EXPERIMENT",
        "description": "Architecture notes slowly becoming working code.",
        "aside": "Naming done. The easy two percent thrives.",
        "accent": PALETTE["blue"],
        "symbol": "S",
    },
    {
        "name": "Unbiased AI Detection",
        "status": "IN THE LAB",
        "category": "AI / FAIRNESS",
        "description": "Fairer detection without confidence theatre.",
        "aside": "The model is being asked awkward things.",
        "accent": PALETTE["pink"],
        "symbol": "AI",
    },
    {
        "name": "Tiffinology",
        "status": "COMING SOON",
        "category": "LOCAL FOOD",
        "description": "Tiffin discovery and ordering, kept simple.",
        "aside": "Lunch, now with infrastructure.",
        "accent": PALETTE["green"],
        "symbol": "T",
    },
    {
        "name": "Quippiq",
        "status": "COMING SOON",
        "category": "MOBILE PRODUCT",
        "description": "Fast interactions. No onboarding novel.",
        "aside": "It may eventually explain its own name.",
        "accent": "#FF8A65",
        "symbol": "Q",
    },
    {
        "name": "Krushi Sarthi",
        "status": "CONCEPT + BUILD",
        "category": "AGRI ADVISORY",
        "description": "Practical AI guidance for farmers.",
        "aside": "Useful first. Impressive second.",
        "accent": "#B39DDB",
        "symbol": "K",
    },
]

PARTICLE_GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
}

TROPHY_PATTERN = (
    "0011100",
    "1111111",
    "1011101",
    "0111110",
    "0011100",
    "0011100",
    "0111110",
)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def http_json(
    url: str,
    token: str | None = None,
    payload: dict | None = None,
) -> object:
    headers = {
        "User-Agent": "jiteesh-profile-asset-generator",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_json(url: str, token: str | None = None) -> object | None:
    try:
        return http_json(url, token)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"warning: could not fetch {url}: {exc}", file=sys.stderr)
        return None


class ContributionHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict] = []
        self.days_by_id: dict[str, dict] = {}
        self.tooltip_day: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tool-tip":
            self.tooltip_day = self.days_by_id.get(values.get("for") or "")
            return
        if tag not in {"td", "rect"}:
            return
        date = values.get("data-date")
        count = values.get("data-count")
        level = values.get("data-level")
        if not date or level is None:
            return
        day = {
            "date": date,
            "count": int(count or 0),
            "level": int(level or 0),
        }
        self.days.append(day)
        if values.get("id"):
            self.days_by_id[str(values["id"])] = day

    def handle_data(self, data: str) -> None:
        if self.tooltip_day is None:
            return
        match = re.search(r"([\d,]+)\s+contributions?", data)
        if match:
            self.tooltip_day["count"] = int(match.group(1).replace(",", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip":
            self.tooltip_day = None


def fetch_github_contributions(username: str, token: str | None) -> list[dict]:
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=364)

    if token:
        query = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                weeks {
                  contributionDays {
                    date
                    contributionCount
                    contributionLevel
                  }
                }
              }
            }
          }
        }
        """
        try:
            data = http_json(
                "https://api.github.com/graphql",
                token,
                {
                    "query": query,
                    "variables": {
                        "login": username,
                        "from": f"{start.isoformat()}T00:00:00Z",
                        "to": f"{today.isoformat()}T23:59:59Z",
                    },
                },
            )
            weeks = (
                data["data"]["user"]["contributionsCollection"]
                ["contributionCalendar"]["weeks"]
            )
            return [
                {
                    "date": day["date"],
                    "count": int(day["contributionCount"]),
                    "level": day["contributionLevel"],
                }
                for week in weeks
                for day in week["contributionDays"]
            ]
        except (
            KeyError,
            TypeError,
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            print(f"warning: could not fetch GitHub contribution calendar: {exc}", file=sys.stderr)

    url = (
        f"https://github.com/users/{username}/contributions"
        f"?from={start.isoformat()}&to={today.isoformat()}"
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "jiteesh-profile-asset-generator",
            "Accept": "text/html",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            parser = ContributionHTMLParser()
            parser.feed(response.read().decode("utf-8"))
            return parser.days
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: could not fetch {url}: {exc}", file=sys.stderr)
        return []


def fetch_github(username: str, token: str | None) -> tuple[dict, list[dict], collections.Counter[str]]:
    user = safe_json(f"https://api.github.com/users/{username}", token)
    if not isinstance(user, dict):
        user = {
            "login": username,
            "public_repos": 0,
            "followers": 0,
            "following": 0,
            "public_gists": 0,
        }

    repos: list[dict] = []
    for page in range(1, 6):
        data = safe_json(
            f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&sort=updated",
            token,
        )
        if not isinstance(data, list):
            break
        repos.extend([repo for repo in data if isinstance(repo, dict)])
        if len(data) < 100:
            break

    languages: collections.Counter[str] = collections.Counter()
    for repo in repos:
        if repo.get("fork"):
            continue
        name = repo.get("name")
        if not name:
            continue
        lang_data = safe_json(f"https://api.github.com/repos/{username}/{name}/languages", token)
        if isinstance(lang_data, dict):
            for language, byte_count in lang_data.items():
                if isinstance(byte_count, int):
                    languages[str(language)] += byte_count
        elif repo.get("language"):
            languages[str(repo["language"])] += 1

    return user, repos, languages


def fetch_codeforces(handle: str) -> list[dict]:
    data = safe_json(f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=10000")
    if isinstance(data, dict) and data.get("status") == "OK" and isinstance(data.get("result"), list):
        return [row for row in data["result"] if isinstance(row, dict)]
    return []


def particle_text_pattern(text: str) -> tuple[str, ...]:
    glyphs = [PARTICLE_GLYPHS[character] for character in text if character in PARTICLE_GLYPHS]
    if not glyphs:
        return ()
    return tuple("00".join(glyph[row] for glyph in glyphs) for row in range(7))


def particle_matrix(
    pattern: tuple[str, ...],
    x: float,
    y: float,
    cell: float,
    primary: str,
    accent: str,
    prefix: str,
    duration: float = 16.0,
    opacity: float = 1.0,
) -> str:
    particles = []
    active = [
        (column, row)
        for row, line in enumerate(pattern)
        for column, value in enumerate(line)
        if value == "1"
    ]
    for index, (column, row) in enumerate(active):
        px = x + column * cell
        py = y + row * cell
        scatter_x = (((index * 17 + row * 5) % 15) - 7) * cell * 0.55
        scatter_y = (((index * 11 + column * 3) % 17) - 8) * cell * 0.48
        dissolve_x = (((index * 7 + column) % 13) - 6) * cell * 0.70
        dissolve_y = (((index * 13 + row) % 15) - 7) * cell * 0.62
        disperse = 0.055 + (index % 12) * 0.004
        assemble = disperse + 0.115
        color = accent if index % 17 == 0 else primary
        particle_opacity = opacity * (0.68 + (index % 4) * 0.09)
        key_times = f"0;{disperse:.3f};{assemble:.3f};0.72;0.90;1"
        transforms = (
            f"0 0;"
            f"{scatter_x:.1f} {scatter_y:.1f};"
            f"0 0;0 0;"
            f"{dissolve_x:.1f} {dissolve_y:.1f};"
            f"0 0"
        )
        if index % 4 == 0:
            size = cell * (0.30 if index % 8 else 0.40)
            shape = (
                f'<rect x="{px - size / 2:.1f}" y="{py - size / 2:.1f}" '
                f'width="{size:.1f}" height="{size:.1f}" rx="{size * 0.18:.1f}" '
                f'fill="{color}" opacity="{particle_opacity:.2f}">'
            )
            close = "</rect>"
        else:
            radius = cell * (0.16 + (index % 3) * 0.035)
            shape = (
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{radius:.1f}" '
                f'fill="{color}" opacity="{particle_opacity:.2f}">'
            )
            close = "</circle>"
        particles.append(
            f"""{shape}
      <animateTransform attributeName="transform" type="translate"
        values="{transforms}" keyTimes="{key_times}"
        dur="{duration:.0f}s" repeatCount="indefinite"/>
    {close}"""
        )

    return (
        f'<g id="{esc(prefix)}" class="particle-glyph">{"".join(particles)}</g>'
    )


def particle_glyph(
    text: str,
    x: float,
    y: float,
    cell: float,
    primary: str,
    accent: str,
    prefix: str,
    duration: float = 16.0,
    opacity: float = 1.0,
) -> str:
    return particle_matrix(
        particle_text_pattern(text),
        x,
        y,
        cell,
        primary,
        accent,
        prefix,
        duration,
        opacity,
    )


def particle_field(
    width: int,
    height: int,
    prefix: str,
    count: int = 28,
    accent: str | None = None,
) -> str:
    accent = accent or PALETTE["orange"]
    nodes = []
    for index in range(count):
        x = 14 + ((index * 83 + 29) % max(1, width - 28))
        y = 14 + ((index * 47 + 17) % max(1, height - 28))
        radius = 0.7 + (index % 4) * 0.35
        opacity = 0.10 + (index % 5) * 0.055
        color = accent if index % 13 == 0 else PALETTE["cream"]
        dx = ((index * 7) % 17) - 8
        dy = ((index * 11) % 19) - 9
        duration = 15 + index % 7
        nodes.append(
            f"""<circle id="{esc(prefix)}-{index}" cx="{x}" cy="{y}" r="{radius:.1f}"
      fill="{color}" opacity="{opacity:.2f}">
      <animateTransform attributeName="transform" type="translate"
        values="0 0;{dx} {dy};0 0" dur="{duration}s" repeatCount="indefinite"/>
      <animate attributeName="opacity"
        values="{opacity:.2f};{min(0.58, opacity + 0.18):.2f};{opacity:.2f}"
        dur="{duration}s" repeatCount="indefinite"/>
    </circle>"""
        )
    return f'<g class="particle-field">{"".join(nodes)}</g>'


def svg_shell(width: int, height: int, body: str, title: str = "") -> str:
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(title)}">
  <defs>
    <filter id="particle-glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="1.8" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <style>
    .title {{ font: 700 20px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['cream']}; }}
    .label {{ font: 600 12px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['text']}; }}
    .muted {{ font: 500 11px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .number {{ font: 800 24px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['gold']}; }}
    .tiny {{ font: 500 10px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['muted']}; }}
    @media (prefers-reduced-motion: reduce) {{
      * {{ animation: none !important; }}
    }}
  </style>
  <rect width="{width}" height="{height}" rx="12" fill="{PALETTE['bg']}"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="11.5" stroke="{PALETTE['border']}"/>
{body}
</svg>
"""


def render_particle_hero(path: pathlib.Path) -> None:
    glyph = particle_glyph(
        "JG",
        552,
        82,
        22,
        PALETTE["cream"],
        PALETTE["orange"],
        "hero-jg",
        duration=18,
    )
    body = f"""
  <style>
    .hero-name {{ font: 800 39px 'Arial Narrow', 'Roboto Condensed', Arial, sans-serif; fill: {PALETTE['cream']}; }}
    .hero-role {{ font: 700 13px 'Space Mono', Consolas, monospace; fill: {PALETTE['orange']}; }}
    .hero-copy {{ font: 500 12px 'Space Mono', Consolas, monospace; fill: {PALETTE['text']}; }}
    .hero-micro {{ font: 600 9px 'Space Mono', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .hero-line {{ stroke: {PALETTE['cream']}; stroke-width: 1; opacity: 0.18; stroke-dasharray: 4 7; }}
  </style>
  {particle_field(920, 330, 'hero-field', 42)}
  <path d="M504 54H872M504 276H872M516 42V288M858 42V288" class="hero-line">
    <animate attributeName="stroke-dashoffset" values="0;-44" dur="14s" repeatCount="indefinite"/>
  </path>
  <path d="M528 252L558 222L612 236L650 196L714 212L760 164L836 182"
    fill="none" stroke="{PALETTE['orange']}" stroke-width="1.5" opacity="0.42"
    stroke-dasharray="2 8">
    <animate attributeName="stroke-dashoffset" values="0;-60" dur="10s" repeatCount="indefinite"/>
  </path>
  <circle cx="558" cy="222" r="3" fill="{PALETTE['orange']}"/>
  <circle cx="650" cy="196" r="3" fill="{PALETTE['cream']}"/>
  <circle cx="760" cy="164" r="3" fill="{PALETTE['orange']}"/>
  {glyph}
  <rect x="42" y="50" width="4" height="212" fill="{PALETTE['orange']}" opacity="0.88">
    <animate attributeName="height" values="0;212;212;0" keyTimes="0;0.14;0.82;1"
      dur="18s" repeatCount="indefinite"/>
  </rect>
  <text x="68" y="91" class="hero-micro">PROFILE / SYSTEMS / 01</text>
  <text x="68" y="141" class="hero-name">JITEESH GHODKE
    <animate attributeName="x" values="42;42;68;68" keyTimes="0;0.05;0.11;1"
      dur="18s" repeatCount="indefinite"/>
  </text>
  <text x="68" y="172" class="hero-role">SYSTEMS DESIGN / ARCHITECTURE</text>
  <text x="68" y="214" class="hero-copy">Low-level details. High-level consequences.</text>
  <text x="68" y="239" class="hero-copy">Building systems I can explain when they fail.</text>
  <text x="68" y="286" class="hero-micro">PUNE / INDIA</text>
  <text x="454" y="286" class="hero-micro" text-anchor="end">DESIGNING FOR SCALE / DEBUGGING THE CONSEQUENCES</text>
  <text x="893" y="166" class="hero-micro" text-anchor="middle"
    transform="rotate(90 893 166)">POINT CLOUD / BUILD 2026</text>
  <rect x="68" y="303" width="386" height="1" fill="{PALETTE['border']}"/>
  <rect x="68" y="303" width="92" height="1" fill="{PALETTE['orange']}">
    <animate attributeName="x" values="68;362;68" dur="9s" repeatCount="indefinite"/>
  </rect>"""
    path.write_text(
        svg_shell(920, 330, body, "Particle portrait header for Jiteesh Ghodke"),
        encoding="utf-8",
    )


def render_particle_hero_mobile(path: pathlib.Path) -> None:
    glyph = particle_glyph(
        "JG",
        121,
        116,
        15,
        PALETTE["cream"],
        PALETTE["orange"],
        "mobile-hero-jg",
        duration=18,
    )
    body = f"""
  <style>
    .hero-name {{ font: 800 30px 'Arial Narrow', 'Roboto Condensed', Arial, sans-serif; fill: {PALETTE['cream']}; }}
    .hero-role {{ font: 700 11px 'Space Mono', Consolas, monospace; fill: {PALETTE['orange']}; }}
    .hero-copy {{ font: 500 11px 'Space Mono', Consolas, monospace; fill: {PALETTE['text']}; }}
    .hero-micro {{ font: 600 8px 'Space Mono', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .hero-line {{ stroke: {PALETTE['cream']}; stroke-width: 1; opacity: 0.16; stroke-dasharray: 3 7; }}
  </style>
  {particle_field(420, 440, 'mobile-hero-field', 28)}
  <path d="M88 98H332M88 236H332M102 84V250M318 84V250" class="hero-line">
    <animate attributeName="stroke-dashoffset" values="0;-40" dur="14s" repeatCount="indefinite"/>
  </path>
  {glyph}
  <text x="24" y="38" class="hero-micro">PROFILE / SYSTEMS / 01</text>
  <text x="24" y="76" class="hero-name">JITEESH GHODKE</text>
  <text x="24" y="96" class="hero-role">SYSTEMS DESIGN / ARCHITECTURE</text>
  <path d="M74 274L120 248L172 269L218 236L276 258L340 222"
    fill="none" stroke="{PALETTE['orange']}" stroke-width="1.4" opacity="0.44"
    stroke-dasharray="2 7">
    <animate attributeName="stroke-dashoffset" values="0;-52" dur="10s" repeatCount="indefinite"/>
  </path>
  <text x="24" y="326" class="hero-copy">Low-level details.</text>
  <text x="24" y="348" class="hero-copy">High-level consequences.</text>
  <text x="24" y="388" class="hero-copy">Building systems I can explain</text>
  <text x="24" y="410" class="hero-copy">when they fail. Eventually.</text>
  <text x="396" y="326" class="hero-micro" text-anchor="end">PUNE / INDIA</text>
  <rect x="24" y="424" width="372" height="1" fill="{PALETTE['border']}"/>
  <rect x="24" y="424" width="74" height="1" fill="{PALETTE['orange']}">
    <animate attributeName="x" values="24;322;24" dur="9s" repeatCount="indefinite"/>
  </rect>"""
    path.write_text(
        svg_shell(420, 440, body, "Mobile particle portrait header for Jiteesh Ghodke"),
        encoding="utf-8",
    )


def metric_card(x: int, y: int, width: int, label: str, value: object, accent: str) -> str:
    return f"""
  <rect x="{x}" y="{y}" width="{width}" height="58" rx="12" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
  <rect x="{x}" y="{y}" width="4" height="58" rx="2" fill="{accent}"/>
  <text x="{x + 16}" y="{y + 23}" class="muted">{esc(label)}</text>
  <text x="{x + 16}" y="{y + 48}" class="number">{esc(value)}</text>"""


def render_terminal_intro(path: pathlib.Path) -> None:
    duration = 16.0
    terminal_glyph = particle_glyph(
        "JG",
        724,
        84,
        9.0,
        PALETTE["cream"],
        PALETTE["orange"],
        "terminal-jg",
        duration=18,
        opacity=0.52,
    )
    sessions = [
        (
            "whoami",
            ["Jiteesh Ghodke / systems design &amp; architecture"],
            0.65,
            0.70,
        ),
        (
            "focus --current",
            ["scalable systems / competitive programming / software I can own"],
            0.65,
            2.20,
        ),
        (
            "learning --active",
            ["Rust / JavaScript / TypeScript / React / React Native"],
            0.78,
            3.90,
        ),
        (
            "ls ./builds",
            [
                "Atelier   Stenokun   Unbiased AI Detection",
                "Tiffinology   Quippiq   Krushi Sarthi",
                "human networking: experimental; documentation unavailable",
            ],
            0.72,
            5.75,
        ),
    ]
    y_positions = [92, 148, 204, 260]
    animated_rows: list[str] = []
    static_rows: list[str] = []
    clips: list[str] = []

    for index, ((command, outputs, type_time, start), y) in enumerate(
        zip(sessions, y_positions)
    ):
        width = max(16, len(command) * 9.4)
        end = start + type_time
        output_start = end + 0.20
        start_key = start / duration
        end_key = end / duration
        output_rows = []
        static_output_rows = []

        clips.append(
            f"""
      <clipPath id="command-clip-{index}">
        <rect x="220" y="{y - 18}" width="0" height="24">
          <animate attributeName="width" values="0;0;{width:.1f};{width:.1f}"
            keyTimes="0;{start_key:.4f};{end_key:.4f};1"
            dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
        </rect>
      </clipPath>"""
        )

        for output_index, output in enumerate(outputs):
            output_y = y + 28 + output_index * 26
            reveal = output_start + output_index * 0.20
            reveal_key = reveal / duration
            output_class = "aside" if output_index == 2 else "output"
            output_rows.append(
                f"""
        <text x="44" y="{output_y}" class="{output_class}" opacity="0">{output}
          <animate attributeName="opacity" values="0;0;1;1"
            keyTimes="0;{reveal_key:.4f};{min(1, reveal_key + 0.012):.4f};1"
            dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
        </text>"""
            )
            static_output_rows.append(
                f'<text x="44" y="{output_y}" class="{output_class}">{output}</text>'
            )

        if index == 0:
            prompt_opacity = "1"
            prompt_animation = ""
        else:
            prompt_opacity = "0"
            prompt_animation = f"""
          <animate attributeName="opacity" values="0;0;1;1"
            keyTimes="0;{start_key:.4f};{min(1, start_key + 0.006):.4f};1"
            dur="{duration}s" begin="-8s" repeatCount="indefinite"/>"""

        animated_rows.append(
            f"""
      <g>
        <text x="44" y="{y}" class="prompt" opacity="{prompt_opacity}">jiteesh@atelier:~$
          {prompt_animation}
        </text>
        <text x="220" y="{y}" class="command" clip-path="url(#command-clip-{index})">{esc(command)}</text>
        <rect x="220" y="{y - 16}" width="8" height="19" rx="1" class="cursor" opacity="0">
          <animate attributeName="x" values="220;220;{220 + width:.1f};{220 + width:.1f};{220 + width:.1f}"
            keyTimes="0;{start_key:.4f};{end_key:.4f};{min(1, end_key + 0.015):.4f};1"
            dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0;0;1;0;0"
            keyTimes="0;{start_key:.4f};{end_key:.4f};{min(1, end_key + 0.015):.4f};1"
            dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
        </rect>
        {''.join(output_rows)}
      </g>"""
        )
        static_rows.append(
            f"""
      <g>
        <text x="44" y="{y}" class="prompt">jiteesh@atelier:~$</text>
        <text x="220" y="{y}" class="command">{esc(command)}</text>
        {''.join(static_output_rows)}
      </g>"""
        )

    body = f"""<svg width="920" height="372" viewBox="0 0 920 372" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated terminal introduction for Jiteesh Ghodke">
  <defs>
    <linearGradient id="terminal-bg" x1="0" y1="0" x2="920" y2="372" gradientUnits="userSpaceOnUse">
      <stop stop-color="{PALETTE['bg']}"/>
      <stop offset="0.70" stop-color="{PALETTE['panel']}"/>
      <stop offset="1" stop-color="#151419"/>
    </linearGradient>
    <linearGradient id="title-bar" x1="0" y1="0" x2="920" y2="0" gradientUnits="userSpaceOnUse">
      <stop stop-color="{PALETTE['panel_2']}"/>
      <stop offset="0.58" stop-color="#211E20"/>
      <stop offset="1" stop-color="{PALETTE['panel']}"/>
    </linearGradient>
    <clipPath id="screen">
      <rect x="18" y="58" width="884" height="306"/>
    </clipPath>
    <filter id="particle-glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="1.8" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    {''.join(clips)}
  </defs>
  <style>
    .window-title {{ font: 600 12px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .prompt {{ font: 600 15px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['green']}; }}
    .command {{ font: 600 15px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['gold']}; }}
    .output {{ font: 500 15px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['text']}; }}
    .aside {{ font: 500 13px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .status {{ font: 600 10px 'Space Mono', 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['green']}; }}
    .cursor {{ fill: {PALETTE['cream']}; }}
    .static-session {{ display: none; }}
    @media (prefers-reduced-motion: reduce) {{
      .animated-session {{ display: none; }}
      .static-session {{ display: block; }}
    }}
  </style>
  <rect x="1" y="1" width="918" height="370" rx="12" fill="url(#terminal-bg)" stroke="{PALETTE['border']}" stroke-width="2"/>
  <path d="M18 18C18 8.6 25.6 1 35 1H885C894.4 1 902 8.6 902 18V58H18V18Z" fill="url(#title-bar)"/>
  <circle cx="42" cy="30" r="6" fill="{PALETTE['pink']}"/>
  <circle cx="64" cy="30" r="6" fill="{PALETTE['gold']}"/>
  <circle cx="86" cy="30" r="6" fill="{PALETTE['green']}"/>
  <text x="460" y="35" class="window-title" text-anchor="middle">jiteesh@atelier - ~/profile</text>
  <circle cx="842" cy="30" r="4" fill="{PALETTE['green']}"/>
  <text x="854" y="34" class="status">LIVE</text>
  <g clip-path="url(#screen)">
    {particle_field(920, 372, 'terminal-field', 22)}
    {terminal_glyph}
    <rect x="29" y="72" width="2" height="266" rx="1" fill="{PALETTE['border']}"/>
    <g class="animated-session">
      {''.join(animated_rows)}
      <rect x="44" y="342" width="8" height="19" rx="1" class="cursor" opacity="0">
        <animate attributeName="opacity" values="0;0;1;0;1"
          keyTimes="0;0.475;0.500;0.530;1"
          dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
      </rect>
    </g>
    <g class="static-session">
      {''.join(static_rows)}
      <rect x="44" y="342" width="8" height="19" rx="1" class="cursor"/>
    </g>
  </g>
  <path d="M18 58H902" stroke="{PALETTE['border']}"/>
</svg>
"""
    path.write_text(body, encoding="utf-8")


def render_terminal_mobile(path: pathlib.Path) -> None:
    duration = 16.0
    sessions = [
        ("whoami", ["Jiteesh Ghodke", "systems design &amp; architecture"], 0.2, 0.65),
        (
            "focus",
            ["scalable systems / competitive", "programming / software I can own"],
            2.1,
            0.55,
        ),
        (
            "learning",
            ["Rust / JavaScript / TypeScript", "React / React Native"],
            3.9,
            0.65,
        ),
        (
            "ls builds/",
            [
                "Atelier / Stenokun / AI Detection",
                "Tiffinology / Quippiq / Krushi Sarthi",
                "human networking: experimental",
            ],
            5.8,
            0.75,
        ),
    ]
    y_positions = [92, 175, 258, 341]
    clips = []
    animated = []
    static = []

    for index, ((command, outputs, start, type_time), y) in enumerate(
        zip(sessions, y_positions)
    ):
        end = start + type_time
        width = len(command) * 8.5
        clips.append(
            f"""<clipPath id="mobile-command-{index}">
      <rect x="56" y="{y - 17}" width="0" height="22">
        <animate attributeName="width" values="0;0;{width:.1f};{width:.1f}"
          keyTimes="0;{start / duration:.4f};{end / duration:.4f};1"
          dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
      </rect>
    </clipPath>"""
        )
        output_nodes = []
        static_output_nodes = []
        for output_index, output in enumerate(outputs):
            output_y = y + 25 + output_index * 22
            reveal = (end + 0.18 + output_index * 0.16) / duration
            output_class = "mobile-aside" if output_index == 2 else "mobile-output"
            output_nodes.append(
                f"""<text x="22" y="{output_y}" class="{output_class}" opacity="0">{output}
        <animate attributeName="opacity" values="0;0;1;1"
          keyTimes="0;{reveal:.4f};{min(1, reveal + 0.012):.4f};1"
          dur="{duration}s" begin="-8s" repeatCount="indefinite"/>
      </text>"""
            )
            static_output_nodes.append(
                f'<text x="22" y="{output_y}" class="{output_class}">{output}</text>'
            )

        prompt_animation = (
            ""
            if index == 0
            else f"""<animate attributeName="opacity" values="0;0;1;1"
          keyTimes="0;{start / duration:.4f};{min(1, start / duration + 0.008):.4f};1"
          dur="{duration}s" begin="-8s" repeatCount="indefinite"/>"""
        )
        animated.append(
            f"""<g>
      <text x="22" y="{y}" class="mobile-prompt" opacity="{'1' if index == 0 else '0'}">~ $
        {prompt_animation}
      </text>
      <text x="56" y="{y}" class="mobile-command" clip-path="url(#mobile-command-{index})">{esc(command)}</text>
      {''.join(output_nodes)}
    </g>"""
        )
        static.append(
            f"""<g>
      <text x="22" y="{y}" class="mobile-prompt">~ $</text>
      <text x="56" y="{y}" class="mobile-command">{esc(command)}</text>
      {''.join(static_output_nodes)}
    </g>"""
        )

    body = f"""<svg width="420" height="490" viewBox="0 0 420 490" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated mobile terminal introduction for Jiteesh Ghodke">
  <defs>
    <linearGradient id="mobile-terminal-bg" x1="0" y1="0" x2="420" y2="490" gradientUnits="userSpaceOnUse">
      <stop stop-color="{PALETTE['bg']}"/>
      <stop offset="1" stop-color="#151419"/>
    </linearGradient>
    <filter id="particle-glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="1.6" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    {''.join(clips)}
  </defs>
  <style>
    .mobile-title {{ font: 600 11px 'Space Mono', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .mobile-prompt {{ font: 700 14px 'Space Mono', Consolas, monospace; fill: {PALETTE['green']}; }}
    .mobile-command {{ font: 700 14px 'Space Mono', Consolas, monospace; fill: {PALETTE['gold']}; }}
    .mobile-output {{ font: 500 13px 'Space Mono', Consolas, monospace; fill: {PALETTE['text']}; }}
    .mobile-aside {{ font: 500 12px 'Space Mono', Consolas, monospace; fill: {PALETTE['muted']}; }}
    .mobile-static {{ display: none; }}
    @media (prefers-reduced-motion: reduce) {{
      .mobile-animated {{ display: none; }}
      .mobile-static {{ display: block; }}
      .mobile-cursor {{ display: none; }}
    }}
  </style>
  <rect x="1" y="1" width="418" height="488" rx="12" fill="url(#mobile-terminal-bg)" stroke="{PALETTE['border']}" stroke-width="2"/>
  <path d="M13 13C13 6.4 18.4 1 25 1H395C401.6 1 407 6.4 407 13V52H13V13Z" fill="{PALETTE['panel_2']}"/>
  <circle cx="28" cy="27" r="5" fill="{PALETTE['pink']}"/>
  <circle cx="47" cy="27" r="5" fill="{PALETTE['gold']}"/>
  <circle cx="66" cy="27" r="5" fill="{PALETTE['green']}"/>
  <text x="210" y="31" text-anchor="middle" class="mobile-title">jiteesh@atelier</text>
  <circle cx="378" cy="27" r="4" fill="{PALETTE['green']}"/>
  <path d="M13 52H407" stroke="{PALETTE['border']}"/>
  {particle_field(420, 490, 'mobile-terminal-field', 16)}
  <g class="mobile-animated">{''.join(animated)}</g>
  <g class="mobile-static">{''.join(static)}</g>
  <rect x="22" y="456" width="8" height="18" rx="1" fill="{PALETTE['cream']}" class="mobile-cursor">
    <animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>
  </rect>
</svg>
"""
    path.write_text(body, encoding="utf-8")


def project_card(
    project: dict,
    x: int,
    y: int,
    width: int,
    height: int,
    mobile: bool = False,
) -> str:
    accent = project["accent"]
    symbol = project["symbol"]
    symbol_cell = 5.5 if len(symbol) > 1 else (6.6 if mobile else 7.5)
    symbol_x = x + (20 if len(symbol) > 1 else 32)
    symbol_y = y + (30 if len(symbol) > 1 else 25)
    text_x = x + (112 if mobile else 118)
    title_y = y + 38
    category_y = y + 62
    description_y = y + 91
    aside_y = y + 128
    name_class = "project-name project-name-long" if len(project["name"]) > 18 else "project-name"
    glyph_id = re.sub(r"[^a-z0-9]+", "-", project["name"].lower()).strip("-")
    glyph = particle_glyph(
        symbol,
        symbol_x,
        symbol_y,
        symbol_cell,
        PALETTE["cream"],
        accent,
        f"project-{glyph_id}",
        duration=16,
    )

    return f"""
  <g>
    <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10"
      fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
    <path d="M{x + 14} {y + 18}V{y + height - 18}M{x + 14} {y + 18}H{x + 28}M{x + 14} {y + height - 18}H{x + 28}"
      stroke="{accent}" stroke-width="2" opacity="0.72"/>
    {glyph}
    <text x="{text_x}" y="{title_y}" class="{name_class}">{esc(project['name'])}</text>
    <text x="{text_x}" y="{category_y}" class="project-category" fill="{accent}">{esc(project['category'])}</text>
    <circle cx="{x + width - 105}" cy="{y + 58}" r="3" fill="{accent}"/>
    <text x="{x + width - 18}" y="{category_y}" class="project-status"
      text-anchor="end" fill="{accent}">{esc(project['status'])}</text>
    <text x="{text_x}" y="{description_y}" class="project-description">{esc(project['description'])}</text>
    <path d="M{text_x} {y + 107}H{x + width - 18}" stroke="{PALETTE['border']}"/>
    <text x="{text_x}" y="{aside_y}" class="project-aside">{esc(project['aside'])}</text>
    <path d="M{x + width - 54} {y + height - 13}H{x + width - 18}"
      stroke="{accent}" stroke-width="2" stroke-dasharray="4 5">
      <animate attributeName="stroke-dashoffset" values="0;-36" dur="6s" repeatCount="indefinite"/>
    </path>
  </g>"""


def render_projects_showcase(path: pathlib.Path) -> None:
    cards = []
    for index, project in enumerate(PROJECTS):
        column = index % 2
        row = index // 2
        cards.append(
            project_card(
                project,
                x=24 + column * 448,
                y=76 + row * 156,
                width=424,
                height=140,
            )
        )

    body = f"""
  <defs>
    <linearGradient id="project-title-accent" x1="24" y1="0" x2="300" y2="0">
      <stop stop-color="{PALETTE['gold']}"/>
      <stop offset="0.45" stop-color="{PALETTE['blue']}"/>
      <stop offset="1" stop-color="{PALETTE['pink']}"/>
    </linearGradient>
  </defs>
  <style>
    .project-heading {{ font: 800 25px 'Arial Narrow', 'Roboto Condensed', Arial, sans-serif; fill: {PALETTE['cream']}; }}
    .project-kicker {{ font: 600 11px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['muted']}; letter-spacing: 0; }}
    .project-name {{ font: 800 22px 'Arial Narrow', 'Roboto Condensed', Arial, sans-serif; fill: {PALETTE['cream']}; }}
    .project-name-long {{ font-size: 18px; }}
    .project-category {{ font: 700 10px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-status {{ font: 700 10px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-description {{ font: 500 13px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['text']}; }}
    .project-aside {{ font: 500 11px 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['muted']}; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
  {particle_field(920, 560, 'project-field', 24)}
  <text x="24" y="36" class="project-heading">Projects in various states of becoming real</text>
  <rect x="24" y="48" width="276" height="3" rx="1.5" fill="url(#project-title-accent)"/>
  <text x="896" y="38" class="project-kicker" text-anchor="end">USEFUL IDEAS / QUESTIONABLE SLEEP SCHEDULE</text>
  {''.join(cards)}"""
    path.write_text(
        svg_shell(920, 560, body, "Jiteesh Ghodke project showcase"),
        encoding="utf-8",
    )


def render_projects_showcase_mobile(path: pathlib.Path) -> None:
    cards = []
    for index, project in enumerate(PROJECTS):
        cards.append(
            project_card(
                project,
                x=18,
                y=86 + index * 154,
                width=384,
                height=138,
                mobile=True,
            )
        )

    body = f"""
  <defs>
    <linearGradient id="mobile-project-accent" x1="18" y1="0" x2="310" y2="0">
      <stop stop-color="{PALETTE['gold']}"/>
      <stop offset="0.45" stop-color="{PALETTE['blue']}"/>
      <stop offset="1" stop-color="{PALETTE['pink']}"/>
    </linearGradient>
  </defs>
  <style>
    .project-heading {{ font: 800 23px 'Arial Narrow', 'Roboto Condensed', Arial, sans-serif; fill: {PALETTE['cream']}; }}
    .project-kicker {{ font: 600 10px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['muted']}; letter-spacing: 0; }}
    .project-name {{ font: 800 20px 'Arial Narrow', 'Roboto Condensed', Arial, sans-serif; fill: {PALETTE['cream']}; }}
    .project-name-long {{ font-size: 16px; }}
    .project-category {{ font: 700 9px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-status {{ font: 700 9px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-description {{ font: 500 12px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['text']}; }}
    .project-aside {{ font: 500 10px 'SFMono-Regular', Consolas, monospace; fill: {PALETTE['muted']}; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
  {particle_field(420, 1022, 'mobile-project-field', 24)}
  <text x="18" y="36" class="project-heading">Projects becoming real</text>
  <rect x="18" y="49" width="250" height="3" rx="1.5" fill="url(#mobile-project-accent)"/>
  <text x="18" y="69" class="project-kicker">USEFUL IDEAS / QUESTIONABLE SLEEP SCHEDULE</text>
  {''.join(cards)}"""
    path.write_text(
        svg_shell(420, 1022, body, "Mobile project showcase"),
        encoding="utf-8",
    )


def render_github_overview(
    path: pathlib.Path,
    username: str,
    user: dict,
    repos: list[dict],
    languages: collections.Counter[str],
) -> None:
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in repos)
    forks = sum(int(repo.get("forks_count") or 0) for repo in repos)
    public_repos = int(user.get("public_repos") or len(repos))
    followers = int(user.get("followers") or 0)
    updated = dt.datetime.now(dt.UTC).strftime("%d %b")

    top = languages.most_common(5)
    top_total = sum(count for _, count in top)
    other = max(0, sum(languages.values()) - top_total)
    if other:
        top.append(("Other", other))
    if not top:
        top = [("No public language data", 1)]
    total = sum(count for _, count in top) or 1
    colors = [
        PALETTE["gold"],
        PALETTE["blue"],
        PALETTE["pink"],
        PALETTE["green"],
        "#D19A66",
        "#A78BFA",
    ]

    segments = []
    legend = []
    bar_x = 24.0
    bar_width = 872.0
    cursor = bar_x
    for index, (language, count) in enumerate(top):
        percentage = count / total
        width = bar_width * percentage
        color = colors[index % len(colors)]
        segments.append(
            f'<rect x="{cursor:.2f}" y="184" width="{width:.2f}" height="12" '
            f'fill="{color}"/>'
        )
        legend_x = 24 + index * 145
        legend.append(
            f'<circle cx="{legend_x + 5}" cy="222" r="5" fill="{color}"/>'
            f'<text x="{legend_x + 16}" y="226" class="tiny">'
            f'{esc(language)} {percentage * 100:.1f}%</text>'
        )
        cursor += width

    body = f"""
  <text x="24" y="38" class="title">GitHub overview</text>
  <text x="24" y="60" class="muted">Public repositories and language bytes. Updated {esc(updated)} UTC.</text>
  {metric_card(24, 80, 196, "Public repos", public_repos, PALETTE['gold'])}
  {metric_card(246, 80, 196, "Stars", stars, PALETTE['blue'])}
  {metric_card(468, 80, 196, "Forks", forks, PALETTE['pink'])}
  {metric_card(690, 80, 196, "Followers", followers, PALETTE['green'])}
  <text x="24" y="170" class="label">Language footprint</text>
  <defs><clipPath id="language-bar"><rect x="24" y="184" width="872" height="12" rx="6"/></clipPath></defs>
  <rect x="24" y="184" width="872" height="12" rx="6" fill="{PALETTE['panel_2']}"/>
  <g clip-path="url(#language-bar)">{''.join(segments)}</g>
  {''.join(legend)}
  <text x="896" y="246" class="tiny" text-anchor="end">github.com/{esc(username)}</text>"""
    path.write_text(svg_shell(920, 260, body, "GitHub overview"), encoding="utf-8")


def render_github_overview_mobile(
    path: pathlib.Path,
    username: str,
    user: dict,
    repos: list[dict],
    languages: collections.Counter[str],
) -> None:
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in repos)
    forks = sum(int(repo.get("forks_count") or 0) for repo in repos)
    public_repos = int(user.get("public_repos") or len(repos))
    followers = int(user.get("followers") or 0)
    updated = dt.datetime.now(dt.UTC).strftime("%d %b")

    items = languages.most_common(5)
    other = max(0, sum(languages.values()) - sum(count for _, count in items))
    if other:
        items.append(("Other", other))
    if not items:
        items = [("No public data", 1)]
    total = sum(count for _, count in items) or 1
    colors = [
        PALETTE["gold"],
        PALETTE["blue"],
        PALETTE["pink"],
        PALETTE["green"],
        "#D19A66",
        "#A78BFA",
    ]

    segments = []
    legend = []
    cursor = 24.0
    for index, (language, count) in enumerate(items):
        percentage = count / total
        width = 372.0 * percentage
        color = colors[index % len(colors)]
        segments.append(
            f'<rect x="{cursor:.2f}" y="246" width="{width:.2f}" height="12" fill="{color}"/>'
        )
        column = index % 2
        row = index // 2
        x = 24 + column * 190
        y = 286 + row * 26
        legend.append(
            f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{color}"/>'
            f'<text x="{x + 16}" y="{y}" class="tiny">{esc(language)} {percentage * 100:.1f}%</text>'
        )
        cursor += width

    body = f"""
  <text x="24" y="38" class="title">GitHub overview</text>
  <text x="24" y="60" class="muted">Public data. Updated {esc(updated)} UTC.</text>
  {metric_card(24, 78, 174, "Public repos", public_repos, PALETTE['gold'])}
  {metric_card(222, 78, 174, "Stars", stars, PALETTE['blue'])}
  {metric_card(24, 146, 174, "Forks", forks, PALETTE['pink'])}
  {metric_card(222, 146, 174, "Followers", followers, PALETTE['green'])}
  <text x="24" y="232" class="label">Language footprint</text>
  <defs><clipPath id="mobile-language-bar"><rect x="24" y="246" width="372" height="12" rx="6"/></clipPath></defs>
  <rect x="24" y="246" width="372" height="12" rx="6" fill="{PALETTE['panel_2']}"/>
  <g clip-path="url(#mobile-language-bar)">{''.join(segments)}</g>
  {''.join(legend)}
  <text x="396" y="374" class="tiny" text-anchor="end">@{esc(username)}</text>"""
    path.write_text(svg_shell(420, 390, body, "Mobile GitHub overview"), encoding="utf-8")


def calculate_streaks(contributions: list[dict]) -> tuple[int, int, int, int]:
    counts = {
        dt.date.fromisoformat(str(day["date"])): int(day.get("count") or 0)
        for day in contributions
        if day.get("date")
    }
    if not counts:
        return 0, 0, 0, 0

    active_days = sum(1 for count in counts.values() if count > 0)
    total = sum(counts.values())
    ordered = sorted(counts)

    longest = 0
    running = 0
    for day in ordered:
        if counts[day] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    today = dt.datetime.now(dt.UTC).date()
    cursor = today if counts.get(today, 0) > 0 else today - dt.timedelta(days=1)
    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= dt.timedelta(days=1)
    return total, active_days, current, longest


def render_github_activity(path: pathlib.Path, contributions: list[dict]) -> None:
    total, active_days, current, longest = calculate_streaks(contributions)
    counts = {
        dt.date.fromisoformat(str(day["date"])): int(day.get("count") or 0)
        for day in contributions
        if day.get("date")
    }
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=363)
    weekly = []
    for week in range(52):
        week_start = start + dt.timedelta(days=week * 7)
        weekly.append(
            sum(
                counts.get(week_start + dt.timedelta(days=offset), 0)
                for offset in range(7)
            )
        )

    maximum = max(weekly, default=0) or 1
    bars = []
    for index, count in enumerate(weekly):
        height = max(2.0, 70.0 * count / maximum) if count else 2.0
        x = 34 + index * 16.3
        y = 245 - height
        if index == len(weekly) - 1:
            color = PALETTE["blue"]
        elif count >= maximum * 0.66:
            color = PALETTE["pink"]
        elif count:
            color = PALETTE["gold"]
        else:
            color = PALETTE["panel_2"]
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="10" height="{height:.1f}" '
            f'rx="2" fill="{color}"/>'
        )

    body = f"""
  <text x="24" y="38" class="title">Contribution activity</text>
  <text x="24" y="60" class="muted">The useful kind of consistency: visible, imperfect, and still moving.</text>
  {metric_card(24, 76, 196, "Contributions", total, PALETTE['gold'])}
  {metric_card(246, 76, 196, "Active days", active_days, PALETTE['blue'])}
  {metric_card(468, 76, 196, "Current streak", current, PALETTE['green'])}
  {metric_card(690, 76, 196, "Longest streak", longest, PALETTE['pink'])}
  <path d="M34 175H886M34 210H886M34 245H886" stroke="{PALETTE['border']}" stroke-dasharray="3 5"/>
  {''.join(bars)}
  <text x="34" y="268" class="tiny">{esc(start.strftime('%b %Y'))}</text>
  <text x="886" y="268" class="tiny" text-anchor="end">{esc(today.strftime('%b %Y'))}</text>"""
    path.write_text(svg_shell(920, 280, body, "GitHub contribution activity"), encoding="utf-8")


def render_github_activity_mobile(path: pathlib.Path, contributions: list[dict]) -> None:
    total, active_days, current, longest = calculate_streaks(contributions)
    counts = {
        dt.date.fromisoformat(str(day["date"])): int(day.get("count") or 0)
        for day in contributions
        if day.get("date")
    }
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=363)
    weekly = [
        sum(
            counts.get(
                start + dt.timedelta(days=week * 7 + offset),
                0,
            )
            for offset in range(7)
        )
        for week in range(52)
    ]
    maximum = max(weekly, default=0) or 1
    bars = []
    for index, count in enumerate(weekly):
        height = max(2.0, 78.0 * count / maximum) if count else 2.0
        x = 25 + index * 7.15
        y = 350 - height
        color = (
            PALETTE["blue"]
            if index == 51
            else PALETTE["pink"]
            if count >= maximum * 0.66
            else PALETTE["gold"]
            if count
            else PALETTE["panel_2"]
        )
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="4.8" height="{height:.1f}" '
            f'rx="1.5" fill="{color}"/>'
        )

    body = f"""
  <text x="24" y="38" class="title">Contribution activity</text>
  <text x="24" y="60" class="muted">Visible, imperfect, still moving.</text>
  {metric_card(24, 78, 174, "Contributions", total, PALETTE['gold'])}
  {metric_card(222, 78, 174, "Active days", active_days, PALETTE['blue'])}
  {metric_card(24, 146, 174, "Current streak", current, PALETTE['green'])}
  {metric_card(222, 146, 174, "Longest streak", longest, PALETTE['pink'])}
  <path d="M25 270H395M25 310H395M25 350H395" stroke="{PALETTE['border']}" stroke-dasharray="3 5"/>
  {''.join(bars)}
  <text x="25" y="377" class="tiny">{esc(start.strftime('%b %Y'))}</text>
  <text x="395" y="377" class="tiny" text-anchor="end">{esc(today.strftime('%b %Y'))}</text>"""
    path.write_text(
        svg_shell(420, 395, body, "Mobile GitHub contribution activity"),
        encoding="utf-8",
    )


def render_trophies(path: pathlib.Path, user: dict, repos: list[dict], languages: collections.Counter[str]) -> None:
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in repos)
    forks = sum(int(repo.get("forks_count") or 0) for repo in repos)
    public_repos = int(user.get("public_repos") or len(repos))
    cards = [
        ("REPOS", public_repos, PALETTE["gold"]),
        ("STARS", stars, PALETTE["blue"]),
        ("FORKS", forks, PALETTE["pink"]),
        ("LANGS", len(languages), PALETTE["green"]),
        ("BUILDS", "6", "#D19A66"),
        ("MOOD", "SHIP", "#A78BFA"),
    ]
    chunks = []
    for index, (label, value, color) in enumerate(cards):
        column = index % 3
        row = index // 3
        x = 24 + column * 298
        y = 76 + row * 108
        trophy = particle_matrix(
            TROPHY_PATTERN,
            x + 31,
            y + 24,
            6.2,
            PALETTE["cream"],
            color,
            f"particle-trophy-{index}",
            duration=16,
        )
        chunks.append(
            f"""
  <g>
    <rect x="{x}" y="{y}" width="274" height="92" rx="10" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
    <path d="M{x + 14} {y + 14}V{y + 78}" stroke="{color}" stroke-width="3"/>
    {trophy}
    <text x="{x + 108}" y="{y + 43}" class="number">{esc(value)}</text>
    <text x="{x + 108}" y="{y + 68}" class="muted">{esc(label)}</text>
    <text x="{x + 252}" y="{y + 22}" class="tiny" text-anchor="end">0{index + 1}/06</text>
    <path d="M{x + 108} {y + 77}H{x + 252}" stroke="{color}" stroke-width="1.5"
      stroke-dasharray="3 7">
      <animate attributeName="stroke-dashoffset" values="0;-40" dur="8s" repeatCount="indefinite"/>
    </path>
  </g>"""
        )

    body = f"""
  <text x="24" y="38" class="title">GitHub Trophies</text>
  <text x="24" y="58" class="muted">Custom trophies, because the old trophy service asked for rent.</text>
  {particle_field(920, 300, 'trophy-field', 20)}
  {''.join(chunks)}"""
    path.write_text(svg_shell(920, 300, body, "GitHub trophies"), encoding="utf-8")


def render_trophies_mobile(
    path: pathlib.Path,
    user: dict,
    repos: list[dict],
    languages: collections.Counter[str],
) -> None:
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in repos)
    forks = sum(int(repo.get("forks_count") or 0) for repo in repos)
    cards = [
        ("REPOS", int(user.get("public_repos") or len(repos)), PALETTE["gold"]),
        ("STARS", stars, PALETTE["blue"]),
        ("FORKS", forks, PALETTE["pink"]),
        ("LANGS", len(languages), PALETTE["green"]),
        ("BUILDS", "6", "#D19A66"),
        ("MOOD", "SHIP", "#A78BFA"),
    ]
    chunks = []
    for index, (label, value, color) in enumerate(cards):
        column = index % 2
        row = index // 2
        x = 18 + column * 198
        y = 76 + row * 104
        trophy = particle_matrix(
            TROPHY_PATTERN,
            x + 24,
            y + 23,
            6.0,
            PALETTE["cream"],
            color,
            f"mobile-particle-trophy-{index}",
            duration=16,
        )
        chunks.append(
            f"""
  <g>
    <rect x="{x}" y="{y}" width="186" height="90" rx="10" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
    <path d="M{x + 12} {y + 13}V{y + 77}" stroke="{color}" stroke-width="3"/>
    {trophy}
    <text x="{x + 86}" y="{y + 42}" class="number">{esc(value)}</text>
    <text x="{x + 86}" y="{y + 66}" class="muted">{esc(label)}</text>
    <text x="{x + 170}" y="{y + 20}" class="tiny" text-anchor="end">0{index + 1}</text>
  </g>"""
        )

    body = f"""
  <text x="24" y="38" class="title">GitHub trophies</text>
  <text x="24" y="60" class="muted">Small numbers. Properly supervised.</text>
  {particle_field(420, 410, 'mobile-trophy-field', 18)}
  {''.join(chunks)}"""
    path.write_text(svg_shell(420, 410, body, "Mobile GitHub trophies"), encoding="utf-8")


def verdict_key(submission: dict) -> str:
    verdict = str(submission.get("verdict") or "OTHER")
    return verdict if verdict in CODEFORCES_COLORS else "OTHER"


def tetris_drop_animation(
    y: int,
    fall: int,
    opacity: float,
    order: int,
    total: int,
    row: int,
) -> str:
    cycle = 14.0
    progress = order / max(1, total - 1)
    drop_start = 0.55 + progress * 4.7 + row * 0.025
    drop_end = drop_start + 1.1
    hold_end = 11.8
    fade_end = 12.35
    reset_end = 12.36
    key_times = ";".join(
        f"{value / cycle:.4f}"
        for value in (0, drop_start, drop_end, hold_end, fade_end, reset_end, cycle)
    )
    start_y = y - fall

    return f"""
    <animate attributeName="y"
      values="{start_y};{start_y};{y};{y};{y};{start_y};{start_y}"
      keyTimes="{key_times}" dur="{cycle:.0f}s" repeatCount="indefinite"/>
    <animate attributeName="opacity"
      values="0;0;{opacity:.2f};{opacity:.2f};0;0;0"
      keyTimes="{key_times}" dur="{cycle:.0f}s" repeatCount="indefinite"/>"""


def render_codeforces_tetris(path: pathlib.Path, handle: str, submissions: list[dict]) -> None:
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=364)
    per_day: dict[dt.date, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    total = 0
    accepted = 0

    for submission in submissions:
        created = submission.get("creationTimeSeconds")
        if not isinstance(created, int):
            continue
        day = dt.datetime.fromtimestamp(created, dt.UTC).date()
        if day < start or day > today:
            continue
        key = verdict_key(submission)
        per_day[day][key] += 1
        total += 1
        if key == "OK":
            accepted += 1

    cell = 12
    gap = 3
    grid_x = 42
    grid_y = 88
    weeks = 53
    rows = 7
    blocks = []
    active_days = sum(
        bool(per_day.get(start + dt.timedelta(days=day_index)))
        for day_index in range(365)
    )
    active_index = 0

    for day_index in range(365):
        day = start + dt.timedelta(days=day_index)
        col = day_index // rows
        row = day_index % rows
        x = grid_x + col * (cell + gap)
        y = grid_y + row * (cell + gap)
        counts = per_day.get(day)
        if not counts:
            blocks.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{PALETTE["panel_2"]}" opacity="0.52"/>'
            )
            continue

        dominant = counts.most_common(1)[0][0]
        day_total = sum(counts.values())
        color = CODEFORCES_COLORS.get(dominant, CODEFORCES_COLORS["OTHER"])
        opacity = min(1.0, 0.42 + day_total * 0.14)
        fall = 42 + (row * 9) + ((col % 6) * 5)
        animation = tetris_drop_animation(
            y,
            fall,
            opacity,
            active_index,
            active_days,
            row,
        )
        active_index += 1
        blocks.append(
            f"""<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2"
    fill="{color}" opacity="{opacity:0.2f}" filter="url(#particle-glow)">
    {animation}
  </rect>"""
        )

    verdicts = collections.Counter(verdict_key(s) for s in submissions)
    wrong = verdicts.get("WRONG_ANSWER", 0)
    tle = verdicts.get("TIME_LIMIT_EXCEEDED", 0)
    runtime = verdicts.get("RUNTIME_ERROR", 0)
    compile_errors = verdicts.get("COMPILATION_ERROR", 0)

    legend = []
    legend_items = [
        ("Accepted", "OK"),
        ("Wrong answer", "WRONG_ANSWER"),
        ("TLE/MLE", "TIME_LIMIT_EXCEEDED"),
        ("Runtime/CE", "RUNTIME_ERROR"),
    ]
    for index, (label, key) in enumerate(legend_items):
        x = 42 + index * 152
        color = CODEFORCES_COLORS[key]
        legend.append(
            f'<rect x="{x}" y="218" width="11" height="11" rx="2" fill="{color}"/><text x="{x + 18}" y="228" class="tiny">{esc(label)}</text>'
        )

    side_piece = f"""
  <g transform="translate(850 92)">
    <animateTransform attributeName="transform" type="translate"
      values="850 48;850 48;850 92;850 92;850 48;850 48"
      keyTimes="0;0.0393;0.4643;0.8429;0.8821;1"
      dur="14s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;1;1;1;0;0"
      keyTimes="0;0.0393;0.4643;0.8429;0.8821;1"
      dur="14s" repeatCount="indefinite"/>
    <g filter="url(#particle-glow)">
      <rect x="0" y="0" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
      <rect x="16" y="0" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
      <rect x="16" y="16" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
      <rect x="32" y="16" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
    </g>
  </g>"""

    body = f"""
  {particle_field(920, 250, 'tetris-field', 16)}
  <text x="42" y="38" class="title">Codeforces Tetris</text>
  <text x="42" y="60" class="muted">@{esc(handle)} - submissions falling into place, emotionally and otherwise.</text>
  <rect x="28" y="76" width="824" height="126" rx="14" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
  {''.join(blocks)}
  {''.join(legend)}
  <text x="704" y="38" class="label">last 365 days</text>
  <text x="704" y="60" class="muted">{total} submissions - {accepted} accepted</text>
  <text x="704" y="228" class="tiny">WA {wrong} / TLE {tle} / RE {runtime} / CE {compile_errors}</text>
  {side_piece}"""
    path.write_text(svg_shell(920, 250, body, "Codeforces Tetris heatmap"), encoding="utf-8")


def render_codeforces_tetris_mobile(
    path: pathlib.Path,
    handle: str,
    submissions: list[dict],
) -> None:
    today = dt.datetime.now(dt.UTC).date()
    start = today - dt.timedelta(days=364)
    per_day: dict[dt.date, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    total = 0
    accepted = 0
    for submission in submissions:
        created = submission.get("creationTimeSeconds")
        if not isinstance(created, int):
            continue
        day = dt.datetime.fromtimestamp(created, dt.UTC).date()
        if not start <= day <= today:
            continue
        key = verdict_key(submission)
        per_day[day][key] += 1
        total += 1
        accepted += key == "OK"

    cell = 5
    gap = 1
    grid_x = 32
    grid_y = 116
    blocks = []
    active_days = sum(
        bool(per_day.get(start + dt.timedelta(days=day_index)))
        for day_index in range(365)
    )
    active_index = 0
    for day_index in range(365):
        day = start + dt.timedelta(days=day_index)
        column = day_index // 7
        row = day_index % 7
        x = grid_x + column * (cell + gap)
        y = grid_y + row * (cell + gap)
        counts = per_day.get(day)
        if not counts:
            blocks.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="1" '
                f'fill="{PALETTE["panel_2"]}" opacity="0.55"/>'
            )
            continue
        dominant = counts.most_common(1)[0][0]
        day_total = sum(counts.values())
        color = CODEFORCES_COLORS.get(dominant, CODEFORCES_COLORS["OTHER"])
        opacity = min(1.0, 0.46 + day_total * 0.14)
        fall = 24 + row * 4 + column % 5
        animation = tetris_drop_animation(
            y,
            fall,
            opacity,
            active_index,
            active_days,
            row,
        )
        active_index += 1
        blocks.append(
            f"""<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="1"
    fill="{color}" opacity="{opacity:.2f}" filter="url(#particle-glow)">
    {animation}
  </rect>"""
        )

    verdicts = collections.Counter(verdict_key(item) for item in submissions)
    legends = [
        ("Accepted", "OK", 28, 194),
        ("Wrong answer", "WRONG_ANSWER", 218, 194),
        ("TLE / MLE", "TIME_LIMIT_EXCEEDED", 28, 219),
        ("Runtime / CE", "RUNTIME_ERROR", 218, 219),
    ]
    legend_nodes = []
    for label, key, x, y in legends:
        legend_nodes.append(
            f'<rect x="{x}" y="{y - 9}" width="10" height="10" rx="2" fill="{CODEFORCES_COLORS[key]}"/>'
            f'<text x="{x + 17}" y="{y}" class="tiny">{esc(label)}</text>'
        )

    body = f"""
  {particle_field(420, 280, 'mobile-tetris-field', 12)}
  <text x="24" y="38" class="title">Codeforces Tetris</text>
  <text x="24" y="60" class="muted">@{esc(handle)} / last 365 days</text>
  <text x="24" y="83" class="label">{total} submissions / {accepted} accepted</text>
  <text x="396" y="83" class="tiny" text-anchor="end">WA {verdicts.get('WRONG_ANSWER', 0)} / TLE {verdicts.get('TIME_LIMIT_EXCEEDED', 0)}</text>
  <rect x="22" y="104" width="376" height="58" rx="10" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
  {''.join(blocks)}
  {''.join(legend_nodes)}
  <text x="24" y="260" class="muted">Verdicts remain keen to help.</text>"""
    path.write_text(
        svg_shell(420, 280, body, "Mobile Codeforces Tetris heatmap"),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="dist", help="Directory to write SVG assets into")
    parser.add_argument("--github-user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "jiteeshghodke456-del"))
    parser.add_argument("--codeforces-handle", default=os.environ.get("CODEFORCES_HANDLE", "SobaDango"))
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    github_token = os.environ.get("GITHUB_TOKEN")
    user, repos, languages = fetch_github(args.github_user, github_token)
    contributions = fetch_github_contributions(args.github_user, github_token)
    submissions = fetch_codeforces(args.codeforces_handle)

    render_particle_hero(out_dir / "profile-hero.svg")
    render_particle_hero_mobile(out_dir / "profile-hero-mobile.svg")
    render_terminal_intro(out_dir / "about-terminal.svg")
    render_terminal_mobile(out_dir / "about-terminal-mobile.svg")
    render_projects_showcase(out_dir / "projects-showcase.svg")
    render_projects_showcase_mobile(out_dir / "projects-showcase-mobile.svg")
    render_github_overview(
        out_dir / "github-overview.svg",
        args.github_user,
        user,
        repos,
        languages,
    )
    render_github_overview_mobile(
        out_dir / "github-overview-mobile.svg",
        args.github_user,
        user,
        repos,
        languages,
    )
    render_github_activity(out_dir / "github-activity.svg", contributions)
    render_github_activity_mobile(
        out_dir / "github-activity-mobile.svg",
        contributions,
    )
    render_trophies(out_dir / "trophies.svg", user, repos, languages)
    render_trophies_mobile(
        out_dir / "trophies-mobile.svg",
        user,
        repos,
        languages,
    )
    render_codeforces_tetris(out_dir / "codeforces-tetris.svg", args.codeforces_handle, submissions)
    render_codeforces_tetris_mobile(
        out_dir / "codeforces-tetris-mobile.svg",
        args.codeforces_handle,
        submissions,
    )

    print(f"wrote profile SVG assets to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
