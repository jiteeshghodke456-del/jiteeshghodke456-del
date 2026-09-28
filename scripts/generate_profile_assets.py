#!/usr/bin/env python3
"""Build every SVG the profile README points at.

Standard library only. Fonts and icons were compiled to JSON ahead of time by
``vendor_glyphs.py`` and ``vendor_icons.py``, so the daily workflow installs
nothing and cannot break on somebody else's release day.

    python3 scripts/generate_profile_assets.py --out-dir dist
    python3 scripts/generate_profile_assets.py --fixture tests/fixtures/profile.json

``--fixture`` builds from a saved snapshot instead of the network, which is how the
chapters are previewed locally without a token. ``--save-fixture`` writes one.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from cockpit import fetch, tokens  # noqa: E402
from cockpit.cards import (  # noqa: E402
    boot,
    credits,
    inventory,
    player,
    snake,
    tetris,
    warps,
    worlds,
)

# In story order. The README shows them top to bottom in exactly this sequence.
CARDS = {
    "boot": boot,
    "player": player,
    "worlds": worlds,
    "tetris": tetris,
    "snake": snake,
    "inventory": inventory,
    "credits": credits,
}

WARPS = tuple(f"warp-{index}" for index in range(1, len(warps.WARPS) + 1))

REPO_KEYS = ("name", "fork", "language", "stargazers_count", "forks_count", "pushed_at", "html_url")


def fetch_raw(username: str, handle: str, token: str | None) -> dict:
    """Everything the cards need from the network, and nothing derived from it."""
    user, repos, languages = fetch.fetch_github(username, token)
    return {
        "user": user,
        "repos": [{key: repo.get(key) for key in REPO_KEYS} for repo in repos],
        "languages": dict(languages),
        "contributions": fetch.fetch_contributions(username, token),
        "codeforces_submissions": fetch.fetch_codeforces(handle),
        "codeforces_profile": fetch.fetch_codeforces_profile(handle),
    }


def derive(raw: dict) -> dict:
    """The numbers the cards render, computed the same way for live and saved data."""
    languages = collections.Counter(raw.get("languages") or {})
    repos = raw.get("repos") or []
    contributions = raw.get("contributions") or []
    submissions = raw.get("codeforces_submissions") or []
    user = raw.get("user") or {}
    return {
        "user": user,
        "repos": repos,
        "languages": languages,
        # Forks are somebody else's work and the API cannot see private
        # repositories from a repo-scoped token, so this counts exactly what
        # a visitor can click: public repositories I actually wrote.
        "repo_count": sum(1 for repo in repos if not repo.get("fork")),
        "contributions": contributions,
        "streaks": fetch.streaks(contributions),
        "account_age_days": fetch.account_age_days(user),
        "codeforces": fetch.codeforces_stats(submissions),
        "codeforces_profile": raw.get("codeforces_profile") or {},
        "codeforces_submissions": submissions,
    }


def build_all(data: dict, out_dir: pathlib.Path) -> list[pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[pathlib.Path] = []
    for name, module in CARDS.items():
        for suffix, width in (("", tokens.WIDE), ("-mobile", tokens.NARROW)):
            target = out_dir / f"{name}{suffix}.svg"
            target.write_text(module.build(data, width=width), encoding="utf-8")
            written.append(target)
    for index, name in enumerate(WARPS):
        for suffix, width in (("", tokens.WIDE), ("-mobile", tokens.NARROW)):
            target = out_dir / f"{name}{suffix}.svg"
            target.write_text(warps.build(index, width=width), encoding="utf-8")
            written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument(
        "--username", default=os.environ.get("GITHUB_USER", "jiteeshghodke456-del")
    )
    parser.add_argument(
        "--handle", default=os.environ.get("CODEFORCES_HANDLE", "SobaDango")
    )
    parser.add_argument("--fixture", type=pathlib.Path, help="build from a saved snapshot")
    parser.add_argument("--save-fixture", type=pathlib.Path, help="write the fetched snapshot")
    args = parser.parse_args()

    if args.fixture:
        raw = json.loads(args.fixture.read_text(encoding="utf-8"))
    else:
        raw = fetch_raw(args.username, args.handle, os.environ.get("GITHUB_TOKEN"))
        if args.save_fixture:
            args.save_fixture.parent.mkdir(parents=True, exist_ok=True)
            args.save_fixture.write_text(
                json.dumps(raw, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )

    data = derive(raw)
    print(
        f"  data: {data['streaks']['total']} contributions, "
        f"{data['codeforces']['solved']} problems solved, "
        f"{data['repo_count']} repos, day {data['account_age_days']}"
    )
    for target in build_all(data, pathlib.Path(args.out_dir)):
        print(f"  {target.name:<24} {target.stat().st_size / 1024:6.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
