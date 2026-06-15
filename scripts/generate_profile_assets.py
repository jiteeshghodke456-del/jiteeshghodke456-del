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
        "description": "A calm workspace for unruly ideas and practical software.",
        "aside": "Risk: building the tool before finishing the task.",
        "accent": PALETTE["gold"],
        "symbol": "A",
    },
    {
        "name": "Stenokun",
        "status": "COMING SOON",
        "category": "SYSTEMS EXPERIMENT",
        "description": "Architecture notes slowly becoming working code.",
        "aside": "Naming complete. The easy two percent is thriving.",
        "accent": PALETTE["blue"],
        "symbol": "S",
    },
    {
        "name": "Unbiased AI Detection",
        "status": "IN THE LAB",
        "category": "AI / FAIRNESS",
        "description": "Fairer detection without confusing confidence for evidence.",
        "aside": "The model is currently being asked awkward questions.",
        "accent": PALETTE["pink"],
        "symbol": "AI",
    },
    {
        "name": "Tiffinology",
        "status": "COMING SOON",
        "category": "LOCAL FOOD",
        "description": "Simpler discovery and ordering for everyday tiffins.",
        "aside": "Lunch, but with infrastructure.",
        "accent": PALETTE["green"],
        "symbol": "T",
    },
    {
        "name": "Quippiq",
        "status": "COMING SOON",
        "category": "MOBILE PRODUCT",
        "description": "Fast mobile interactions without six onboarding screens.",
        "aside": "The app may eventually explain its own name.",
        "accent": "#FF8A65",
        "symbol": "Q",
    },
    {
        "name": "Krushi Sarthi",
        "status": "CONCEPT + BUILD",
        "category": "AGRI ADVISORY",
        "description": "Practical AI guidance for farmers and daily decisions.",
        "aside": "Useful first. Impressive second.",
        "accent": "#B39DDB",
        "symbol": "K",
    },
]


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


def svg_shell(width: int, height: int, body: str, title: str = "") -> str:
    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(title)}">
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


def metric_card(x: int, y: int, width: int, label: str, value: object, accent: str) -> str:
    return f"""
  <rect x="{x}" y="{y}" width="{width}" height="58" rx="12" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
  <rect x="{x}" y="{y}" width="4" height="58" rx="2" fill="{accent}"/>
  <text x="{x + 16}" y="{y + 23}" class="muted">{esc(label)}</text>
  <text x="{x + 16}" y="{y + 48}" class="number">{esc(value)}</text>"""


def render_terminal_intro(path: pathlib.Path) -> None:
    duration = 16.0
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
    symbol_size = 44 if mobile else 46
    symbol_x = x + 24
    symbol_y = y + 24
    text_x = x + 84
    title_y = y + 42
    category_y = y + 67
    description_y = y + 95
    aside_y = y + 121
    status_width = max(92, len(project["status"]) * 7 + 24)
    status_x = x + width - status_width - 18

    return f"""
  <g>
    <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10"
      fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
    <rect x="{x}" y="{y}" width="5" height="{height}" rx="2.5" fill="{accent}"/>
    <rect x="{symbol_x}" y="{symbol_y}" width="{symbol_size}" height="{symbol_size}" rx="9"
      fill="{accent}" opacity="0.16"/>
    <rect x="{symbol_x + 0.5}" y="{symbol_y + 0.5}" width="{symbol_size - 1}" height="{symbol_size - 1}" rx="8.5"
      stroke="{accent}" opacity="0.72"/>
    <text x="{symbol_x + symbol_size / 2}" y="{symbol_y + 29}" class="project-symbol"
      text-anchor="middle" fill="{accent}">{esc(project['symbol'])}</text>
    <text x="{text_x}" y="{title_y}" class="project-name">{esc(project['name'])}</text>
    <text x="{text_x}" y="{category_y}" class="project-category" fill="{accent}">{esc(project['category'])}</text>
    <rect x="{status_x}" y="{y + 18}" width="{status_width}" height="24" rx="12"
      fill="{accent}" opacity="0.13"/>
    <text x="{status_x + status_width / 2}" y="{y + 34}" class="project-status"
      text-anchor="middle" fill="{accent}">{esc(project['status'])}</text>
    <text x="{x + 24}" y="{description_y}" class="project-description">{esc(project['description'])}</text>
    <path d="M{x + 24} {y + 108}H{x + width - 24}" stroke="{PALETTE['border']}"/>
    <text x="{x + 24}" y="{aside_y}" class="project-aside">{esc(project['aside'])}</text>
    <circle cx="{x + width - 29}" cy="{y + height - 22}" r="4" fill="{accent}">
      <animate attributeName="opacity" values="0.35;1;0.35" dur="{2.4 + (x + y) % 5 * 0.2:.1f}s" repeatCount="indefinite"/>
    </circle>
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
    .project-heading {{ font: 700 23px Georgia, 'Times New Roman', serif; fill: {PALETTE['cream']}; }}
    .project-kicker {{ font: 600 11px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['muted']}; letter-spacing: 0; }}
    .project-name {{ font: 700 20px Georgia, 'Times New Roman', serif; fill: {PALETTE['cream']}; }}
    .project-category {{ font: 700 10px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-status {{ font: 700 9px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-description {{ font: 500 13px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['text']}; }}
    .project-aside {{ font: italic 12px Georgia, 'Times New Roman', serif; fill: {PALETTE['muted']}; }}
    .project-symbol {{ font: 800 15px 'Segoe UI', Arial, sans-serif; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
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
    .project-heading {{ font: 700 21px Georgia, 'Times New Roman', serif; fill: {PALETTE['cream']}; }}
    .project-kicker {{ font: 600 10px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['muted']}; letter-spacing: 0; }}
    .project-name {{ font: 700 18px Georgia, 'Times New Roman', serif; fill: {PALETTE['cream']}; }}
    .project-category {{ font: 700 9px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-status {{ font: 700 8px 'SFMono-Regular', Consolas, monospace; letter-spacing: 0; }}
    .project-description {{ font: 500 12px 'Segoe UI', Arial, sans-serif; fill: {PALETTE['text']}; }}
    .project-aside {{ font: italic 11px Georgia, 'Times New Roman', serif; fill: {PALETTE['muted']}; }}
    .project-symbol {{ font: 800 14px 'Segoe UI', Arial, sans-serif; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
  </style>
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
        x = 24 + index * 146
        chunks.append(
            f"""
  <g>
    <rect x="{x}" y="64" width="122" height="86" rx="16" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
    <path d="M{x + 35} 86h52l-8 38H{x + 43}z" fill="{color}" opacity="0.86"/>
    <rect x="{x + 51}" y="124" width="20" height="10" rx="2" fill="{color}"/>
    <rect x="{x + 42}" y="134" width="38" height="8" rx="2" fill="{color}" opacity="0.65"/>
    <text x="{x + 61}" y="101" class="label" text-anchor="middle" fill="{PALETTE['bg']}">{esc(value)}</text>
    <text x="{x + 61}" y="170" class="muted" text-anchor="middle">{esc(label)}</text>
    <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="{2.4 + index * 0.2:0.1f}s" repeatCount="indefinite"/>
  </g>"""
        )

    body = f"""
  <text x="24" y="38" class="title">GitHub Trophies</text>
  <text x="24" y="58" class="muted">Custom trophies, because the old trophy service asked for rent.</text>
  {''.join(chunks)}"""
    path.write_text(svg_shell(920, 200, body, "GitHub trophies"), encoding="utf-8")


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
        x = 24 + column * 198
        y = 76 + row * 92
        chunks.append(
            f"""
  <g>
    <rect x="{x}" y="{y}" width="174" height="74" rx="10" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
    <path d="M{x + 20} {y + 18}h38l-6 28H{x + 26}z" fill="{color}" opacity="0.88"/>
    <rect x="{x + 31}" y="{y + 46}" width="16" height="7" rx="2" fill="{color}"/>
    <text x="{x + 105}" y="{y + 34}" class="number" text-anchor="middle">{esc(value)}</text>
    <text x="{x + 105}" y="{y + 55}" class="muted" text-anchor="middle">{esc(label)}</text>
  </g>"""
        )

    body = f"""
  <text x="24" y="38" class="title">GitHub trophies</text>
  <text x="24" y="60" class="muted">Small numbers. Properly supervised.</text>
  {''.join(chunks)}"""
    path.write_text(svg_shell(420, 370, body, "Mobile GitHub trophies"), encoding="utf-8")


def verdict_key(submission: dict) -> str:
    verdict = str(submission.get("verdict") or "OTHER")
    return verdict if verdict in CODEFORCES_COLORS else "OTHER"


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
        begin = 0.03 * (col % 20) + 0.025 * row
        blocks.append(
            f"""<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}" opacity="{opacity:0.2f}">
    <animate attributeName="y" values="{y - fall};{y}" dur="0.72s" begin="{begin:0.2f}s" fill="freeze"/>
    <animate attributeName="opacity" values="0;{opacity:0.2f}" dur="0.72s" begin="{begin:0.2f}s" fill="freeze"/>
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
    <animateTransform attributeName="transform" type="translate" values="850 48;850 92;850 48" dur="3.8s" repeatCount="indefinite"/>
    <rect x="0" y="0" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
    <rect x="16" y="0" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
    <rect x="16" y="16" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
    <rect x="32" y="16" width="15" height="15" rx="3" fill="{PALETTE['gold']}"/>
  </g>"""

    body = f"""
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
        begin = 0.02 * (column % 20) + 0.018 * row
        blocks.append(
            f"""<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="1" fill="{color}" opacity="{opacity:.2f}">
    <animate attributeName="y" values="{y - fall};{y}" dur="0.65s" begin="{begin:.2f}s" fill="freeze"/>
    <animate attributeName="opacity" values="0;{opacity:.2f}" dur="0.65s" begin="{begin:.2f}s" fill="freeze"/>
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
