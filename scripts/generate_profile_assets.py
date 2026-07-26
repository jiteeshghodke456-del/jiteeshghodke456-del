#!/usr/bin/env python3
"""Build every SVG the profile README points at.

Standard library only. Fonts and icons were compiled to JSON ahead of time by
``vendor_glyphs.py`` and ``vendor_icons.py``, so the daily workflow installs
nothing and cannot break on somebody else's release day.

    python3 scripts/generate_profile_assets.py --out-dir dist
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from cockpit import fetch, tokens  # noqa: E402
from cockpit.cards import cluster, nameplate, stack, tetris, work  # noqa: E402

CARDS = {
    "nameplate": nameplate,
    "cluster": cluster,
    "bays": work,
    "tetris": tetris,
    "stack": stack,
}


def collect(username: str, handle: str, token: str | None) -> dict:
    user, repos, languages = fetch.fetch_github(username, token)
    contributions = fetch.fetch_contributions(username, token)
    submissions = fetch.fetch_codeforces(handle)

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
        "codeforces_submissions": submissions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument(
        "--username", default=os.environ.get("GITHUB_USER", "jiteeshghodke456-del")
    )
    parser.add_argument(
        "--handle", default=os.environ.get("CODEFORCES_HANDLE", "SobaDango")
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = collect(args.username, args.handle, token)
    print(
        f"  data: {data['streaks']['total']} contributions, "
        f"{data['codeforces']['solved']} problems solved, "
        f"{data['repo_count']} repos, day {data['account_age_days']}"
    )

    for name, module in CARDS.items():
        for suffix, width in (("", tokens.WIDE), ("-mobile", tokens.NARROW)):
            target = out_dir / f"{name}{suffix}.svg"
            target.write_text(module.build(data, width=width), encoding="utf-8")
            print(f"  {target.name}  {target.stat().st_size / 1024:.0f} KB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
