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
import sys
import urllib.error
import urllib.request


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


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def http_json(url: str, token: str | None = None) -> object:
    headers = {
        "User-Agent": "jiteesh-profile-asset-generator",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_json(url: str, token: str | None = None) -> object | None:
    try:
        return http_json(url, token)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"warning: could not fetch {url}: {exc}", file=sys.stderr)
        return None


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
  </style>
  <rect width="{width}" height="{height}" rx="18" fill="{PALETTE['bg']}"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="17.5" stroke="{PALETTE['border']}"/>
  <circle cx="{width - 54}" cy="38" r="72" fill="{PALETTE['gold']}" opacity="0.07"/>
  <circle cx="48" cy="{height - 18}" r="82" fill="{PALETTE['blue']}" opacity="0.05"/>
{body}
</svg>
"""


def metric_card(x: int, y: int, width: int, label: str, value: object, accent: str) -> str:
    return f"""
  <rect x="{x}" y="{y}" width="{width}" height="58" rx="12" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
  <rect x="{x}" y="{y}" width="4" height="58" rx="2" fill="{accent}"/>
  <text x="{x + 16}" y="{y + 23}" class="muted">{esc(label)}</text>
  <text x="{x + 16}" y="{y + 48}" class="number">{esc(value)}</text>"""


def render_github_stats(path: pathlib.Path, username: str, user: dict, repos: list[dict], languages: collections.Counter[str]) -> None:
    stars = sum(int(repo.get("stargazers_count") or 0) for repo in repos)
    forks = sum(int(repo.get("forks_count") or 0) for repo in repos)
    public_repos = int(user.get("public_repos") or len(repos))
    followers = int(user.get("followers") or 0)
    lang_count = len(languages)
    updated = dt.datetime.now(dt.UTC).strftime("%d %b")

    body = f"""
  <text x="24" y="38" class="title">GitHub Analytics</text>
  <text x="24" y="60" class="muted">Stable local SVG. The rented Vercel card had a small lie down.</text>
  {metric_card(24, 80, 126, "Repos", public_repos, PALETTE['gold'])}
  {metric_card(164, 80, 126, "Stars", stars, PALETTE['blue'])}
  {metric_card(304, 80, 126, "Forks", forks, PALETTE['pink'])}
  {metric_card(24, 148, 126, "Followers", followers, PALETTE['green'])}
  {metric_card(164, 148, 126, "Languages", lang_count, PALETTE['gold'])}
  {metric_card(304, 148, 126, "Updated", updated, PALETTE['blue'])}
  <text x="24" y="234" class="tiny">Source: GitHub public API for {esc(username)}</text>"""
    path.write_text(svg_shell(455, 250, body, "GitHub analytics"), encoding="utf-8")


def render_top_languages(path: pathlib.Path, languages: collections.Counter[str]) -> None:
    items = languages.most_common(7)
    if not items:
        items = [("Python", 1), ("JavaScript", 1), ("C++", 1)]
    total = sum(count for _, count in items) or 1
    colors = [PALETTE["gold"], PALETTE["blue"], PALETTE["pink"], PALETTE["green"], "#D19A66", "#A78BFA", "#60A5FA"]

    rows = []
    y = 76
    for index, (language, count) in enumerate(items):
        pct = count / total
        width = max(8, int(326 * pct))
        color = colors[index % len(colors)]
        rows.append(
            f"""
  <text x="24" y="{y + 10}" class="label">{esc(language)}</text>
  <text x="392" y="{y + 10}" class="muted" text-anchor="end">{pct * 100:0.1f}%</text>
  <rect x="24" y="{y + 18}" width="380" height="8" rx="4" fill="{PALETTE['panel_2']}"/>
  <rect x="24" y="{y + 18}" width="{width}" height="8" rx="4" fill="{color}">
    <animate attributeName="width" values="0;{width}" dur="0.9s" begin="{index * 0.08:0.2f}s" fill="freeze"/>
  </rect>"""
        )
        y += 24

    body = f"""
  <text x="24" y="38" class="title">Top Languages</text>
  <text x="24" y="60" class="muted">Approximate byte share across public non-fork repos.</text>
  {''.join(rows)}"""
    path.write_text(svg_shell(455, 260, body, "Top languages"), encoding="utf-8")


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
    submissions = fetch_codeforces(args.codeforces_handle)

    render_github_stats(out_dir / "github-stats.svg", args.github_user, user, repos, languages)
    render_top_languages(out_dir / "top-langs.svg", languages)
    render_trophies(out_dir / "trophies.svg", user, repos, languages)
    render_codeforces_tetris(out_dir / "codeforces-tetris.svg", args.codeforces_handle, submissions)

    print(f"wrote profile SVG assets to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
