#!/usr/bin/env python3
"""Validate generated profile SVGs and their README references.

Runs in the workflow after generation and before publish, so a broken asset
never reaches the ``output`` branch and never shows up as a broken image on
the profile.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

CARDS = ("nameplate", "cluster", "bays", "tetris", "stack")

EXPECTED_ASSETS = {f"{name}{suffix}.svg" for name in CARDS for suffix in ("", "-mobile")}
EXPECTED_ASSETS.add("github-contribution-grid-snake.svg")

# Assets from the previous design. If one of these is still produced or still
# referenced, something was half-migrated.
RETIRED_ASSETS = {
    "about-terminal.svg",
    "about-terminal-mobile.svg",
    "codeforces-tetris.svg",
    "codeforces-tetris-mobile.svg",
    "github-activity.svg",
    "github-activity-mobile.svg",
    "github-contribution-grid-snake-dark.svg",
    "github-overview.svg",
    "github-overview-mobile.svg",
    "profile-hero.svg",
    "profile-hero-mobile.svg",
    "projects-showcase.svg",
    "projects-showcase-mobile.svg",
    "trophies.svg",
    "trophies-mobile.svg",
}

PLACEHOLDERS = ("YOUR_LINK", "YOUR_EMAIL", "Pranit Dhanade", "TODO", "Lorem ipsum")

# The brand is Ataleir. "Atelier" is the French word and was a long-running
# typo in the old project list; it must not come back on a public surface.
FORBIDDEN = ("Atelier",)

PALETTE = ("#FF2D75", "#3AA0FF", "#07070A")

# Entity-expansion attacks against ElementTree need a DOCTYPE or an ENTITY
# declaration. None of our assets have one - we generate them, and the snake
# comes from Platane/snk - so rejecting the construct outright is cheaper and
# more certain than adding a defusedxml dependency to a pipeline whose whole
# point is that it installs nothing.
UNSAFE_XML = re.compile(r"<!(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def validate(asset_dir: pathlib.Path, readme_path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    readme = readme_path.read_text(encoding="utf-8")

    for name in sorted(EXPECTED_ASSETS):
        path = asset_dir / name
        if not path.exists():
            errors.append(f"missing generated asset: {path}")
            continue

        source = path.read_text(encoding="utf-8")
        if UNSAFE_XML.search(source):
            errors.append(f"{name} declares a DOCTYPE or ENTITY; refusing to parse")
            continue
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

        # Filters are banned on purpose: renderers drop them silently and a
        # soft pool of light becomes a hard-edged coloured blob.
        if "feGaussianBlur" in source:
            errors.append(f"{name} uses an SVG filter; use gradients instead")

        if name.startswith("github-contribution-grid-snake"):
            if 'class="c c' in source and "profile-growing-snake:start" not in source:
                errors.append(f"snake growth layer is missing from {path}")
            if "#FF2D75" not in source:
                errors.append(f"{name} was not recoloured to the cockpit palette")
        elif not any(colour in source for colour in PALETTE):
            errors.append(f"{name} contains none of the palette colours")

    for name in sorted(RETIRED_ASSETS):
        if (asset_dir / name).exists():
            errors.append(f"retired asset still generated: {name}")
        if name in readme:
            errors.append(f"README still references retired asset: {name}")

    for placeholder in PLACEHOLDERS:
        if placeholder in readme:
            errors.append(f"README still contains placeholder text: {placeholder}")

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", readme):
            errors.append(f"README says {word!r}; the brand is spelled Ataleir")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", type=pathlib.Path, default=pathlib.Path("dist"))
    parser.add_argument(
        "--readme", type=pathlib.Path, default=pathlib.Path("README.md")
    )
    args = parser.parse_args()

    errors = validate(args.asset_dir, args.readme)
    if errors:
        print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"validated {len(EXPECTED_ASSETS)} profile assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
