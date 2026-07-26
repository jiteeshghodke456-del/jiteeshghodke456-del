#!/usr/bin/env python3
"""Precompile vendored fonts into stdlib-readable glyph tables.

Run this by hand whenever ``assets/fonts`` changes::

    pip install fonttools brotli
    python3 scripts/vendor_glyphs.py

The daily workflow never runs this. It reads the JSON produced here, which
keeps ``generate_profile_assets.py`` on the standard library alone.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

try:
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
except ImportError:  # pragma: no cover - developer tooling only
    sys.exit("vendor_glyphs.py needs fonttools: pip install fonttools brotli")


ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
GLYPH_DIR = ROOT / "assets" / "glyphs"

# Latin text, digits, and the punctuation the cards actually set. Anything
# outside this set is drawn as geometry instead of type.
CHARSET = "".join(chr(c) for c in range(0x20, 0x7F)) + "·–—°×"

FACES = [
    {
        "key": "display",
        "file": "Archivo[wdth,wght].ttf",
        "axes": {"wght": 800, "wdth": 125},
        "note": "Archivo, extra bold at the widest width. Nameplate and headings.",
    },
    {
        "key": "mono",
        "file": "IBMPlexMono-Regular.ttf",
        "axes": None,
        "note": "IBM Plex Mono regular. Labels and body copy inside cards.",
    },
    {
        "key": "mono-semibold",
        "file": "IBMPlexMono-SemiBold.ttf",
        "axes": None,
        "note": "IBM Plex Mono semibold. Readouts and gauge numerals.",
    },
]


def round_coords(value: float) -> str:
    """Quantise to whole font units. At 1000 upem that is far below a pixel."""
    return str(int(round(value)))


def build_face(spec: dict) -> dict:
    path = FONT_DIR / spec["file"]
    font = TTFont(path)
    if spec["axes"]:
        font = instancer.instantiateVariableFont(font, spec["axes"], inplace=False)

    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    head = font["head"]
    hhea = font["hhea"]
    os2 = font["OS/2"]

    glyphs: dict[str, dict] = {}
    missing: list[str] = []
    for char in CHARSET:
        name = cmap.get(ord(char))
        if name is None:
            missing.append(char)
            continue
        pen = SVGPathPen(glyph_set, ntos=round_coords)
        glyph_set[name].draw(pen)
        entry = {"aw": int(round(glyph_set[name].width))}
        commands = pen.getCommands()
        if commands:
            entry["d"] = commands
        glyphs[char] = entry

    if missing:
        print(f"  ! {spec['key']}: no glyph for {''.join(missing)!r}", file=sys.stderr)

    return {
        "key": spec["key"],
        "source": spec["file"],
        "axes": spec["axes"],
        "note": spec["note"],
        "upem": head.unitsPerEm,
        "ascender": hhea.ascent,
        "descender": hhea.descent,
        "cap_height": getattr(os2, "sCapHeight", None) or hhea.ascent,
        "x_height": getattr(os2, "sxHeight", None) or 0,
        "glyphs": glyphs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(GLYPH_DIR))
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for spec in FACES:
        face = build_face(spec)
        target = out_dir / f"{spec['key']}.json"
        target.write_text(
            json.dumps(face, separators=(",", ":"), sort_keys=True), encoding="utf-8"
        )
        size_kb = target.stat().st_size / 1024
        print(f"  {target.relative_to(ROOT)}  {len(face['glyphs'])} glyphs  {size_kb:.0f} KB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
