#!/usr/bin/env python3
"""Validate generated profile SVGs and their README references."""

from __future__ import annotations

import argparse
import pathlib
import sys
import xml.etree.ElementTree as ET


EXPECTED_ASSETS = {
    "about-terminal-mobile.svg",
    "about-terminal.svg",
    "codeforces-tetris-mobile.svg",
    "codeforces-tetris.svg",
    "github-activity-mobile.svg",
    "github-activity.svg",
    "github-contribution-grid-snake-dark.svg",
    "github-contribution-grid-snake.svg",
    "github-overview-mobile.svg",
    "github-overview.svg",
    "projects-showcase-mobile.svg",
    "projects-showcase.svg",
    "profile-hero-mobile.svg",
    "profile-hero.svg",
    "trophies-mobile.svg",
    "trophies.svg",
}


def validate(asset_dir: pathlib.Path, readme_path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    readme = readme_path.read_text(encoding="utf-8")

    for name in sorted(EXPECTED_ASSETS):
        path = asset_dir / name
        if not path.exists():
            errors.append(f"missing generated asset: {path}")
            continue

        source = path.read_text(encoding="utf-8")
        try:
            root = ET.fromstring(source)
        except ET.ParseError as exc:
            errors.append(f"invalid SVG XML in {path}: {exc}")
            continue

        if not root.tag.endswith("svg"):
            errors.append(f"unexpected root element in {path}: {root.tag}")
        if not root.get("viewBox"):
            errors.append(f"missing viewBox in {path}")
        if name not in readme:
            errors.append(f"README does not reference {name}")
        if (
            name.startswith("github-contribution-grid-snake")
            and 'class="c c' in source
            and "profile-growing-snake:start" not in source
        ):
            errors.append(f"snake growth layer is missing from {path}")

    for placeholder in ("YOUR_LINK", "YOUR_EMAIL", "Pranit Dhanade"):
        if placeholder in readme:
            errors.append(f"README still contains placeholder text: {placeholder}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", type=pathlib.Path, default=pathlib.Path("dist"))
    parser.add_argument("--readme", type=pathlib.Path, default=pathlib.Path("README.md"))
    args = parser.parse_args()

    errors = validate(args.asset_dir, args.readme)
    if errors:
        print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"validated {len(EXPECTED_ASSETS)} profile assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
