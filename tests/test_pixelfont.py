from __future__ import annotations

import dataclasses
import re
import string
import unittest
import xml.etree.ElementTree as ET

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from profilegen.svg.pixelfont import (
    GLYPH_H,
    GLYPH_W,
    GLYPHS,
    MISSING_GLYPH,
    Rect,
    bitrows,
    decompose,
    digit_slot,
    measure,
    render_path,
    render_rects,
)

# Every string a real caller renders.  A character missing from GLYPHS is exactly the failure
# that let the old eight-letter font dictate the README's project names for nineteen commits,
# so this list is the regression test for that: add to it whenever a renderer gains a label.
HUD_STRINGS = [
    "SCORE",
    "LEVEL",
    "LINES",
    "NEXT",
    "HIGH",
    "TOP",
    "AC",
    "WA",
    "TLE",
    "MLE",
    "RE",
    "CE",
    "ETC",
    "PAUSED",
    "GAME OVER",
    "SNAKE",
    "0123456789",
    "JITEESH GHODKE",
    "CODEFORCES",
    "SOBADANGO",
    "GITHUB",
    "REPOS",
    "STARS",
    "DAYS",
    "STREAK",
]

REQUIRED_CHARSET = (
    string.ascii_uppercase + string.digits + " " + ".,:;!?'\"-+=/\\|()[]<>*#%&_@$^~"
)

# Strings whose ink touches both outer columns and both outer rows, so the bounding box of
# their blocks is the whole advance and can be compared to measure() exactly.
FULL_EXTENT_STRINGS = ("E", "HZ", "0123456789", "GAME OVER", "JITEESH GHODKE")


def popcount(rows: tuple[int, ...] | list[int]) -> int:
    return sum(mask.bit_count() for mask in rows)


def lit_cells(text: str, tracking: int = 1) -> set[tuple[int, int]]:
    """Every ``(col, row)`` that bitrows() lights, decoded independently of decompose()."""
    width, _ = measure(text, tracking=tracking)
    return {
        (width - 1 - bit, row)
        for row, mask in enumerate(bitrows(text, tracking=tracking))
        for bit in range(width)
        if mask >> bit & 1
    }


def paint(rects: list[Rect]) -> set[tuple[int, int]]:
    """Paint blocks into a set of cells, failing the moment two blocks share one."""
    cells: set[tuple[int, int]] = set()
    for rect in rects:
        for col in range(rect.col, rect.col + rect.w):
            for row in range(rect.row, rect.row + rect.h):
                if (col, row) in cells:
                    raise AssertionError(f"{rect} overlaps an earlier block at {(col, row)}")
                cells.add((col, row))
    return cells


def row_run_count(text: str) -> int:
    """How many blocks the first pass alone (maximal horizontal runs per row) would emit."""
    width, _ = measure(text)
    return sum(len(re.findall("1+", format(mask, f"0{width}b"))) for mask in bitrows(text))


class GlyphTableTests(unittest.TestCase):
    def test_every_glyph_is_seven_rows_that_fit_five_columns(self) -> None:
        for char, rows in GLYPHS.items():
            with self.subTest(char=char):
                self.assertEqual(len(rows), GLYPH_H)
                for mask in rows:
                    self.assertIsInstance(mask, int)
                    self.assertGreaterEqual(mask, 0)
                    self.assertLess(mask, 1 << GLYPH_W)

    def test_required_charset_is_complete(self) -> None:
        self.assertEqual([char for char in REQUIRED_CHARSET if char not in GLYPHS], [])

    def test_every_hud_string_is_drawable(self) -> None:
        for text in HUD_STRINGS:
            with self.subTest(text=text):
                missing = sorted({char for char in text if char not in GLYPHS})
                self.assertEqual(missing, [], f"{text!r} needs glyphs for {missing}")
                bitrows(text)

    def test_only_space_is_blank_and_no_two_glyphs_are_identical(self) -> None:
        seen: dict[tuple[int, ...], str] = {}
        for char, rows in GLYPHS.items():
            with self.subTest(char=char):
                if char != " ":
                    self.assertGreater(popcount(rows), 0)
                self.assertNotIn(rows, seen, f"{char!r} is a copy of {seen.get(rows)!r}")
                seen[rows] = char

    def test_rect_is_frozen(self) -> None:
        rect = Rect(0, 0, 5, 1)
        self.assertEqual(rect.area, 5)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rect.w = 2  # type: ignore[misc]


class CompositionTests(unittest.TestCase):
    def test_single_glyph_bitrows_equal_the_table_entry(self) -> None:
        self.assertEqual(bitrows("A"), list(GLYPHS["A"]))

    def test_bitrows_shift_earlier_glyphs_left_by_cell_plus_tracking(self) -> None:
        a = GLYPHS["A"]
        self.assertEqual(bitrows("AA"), [(mask << 6) | mask for mask in a])
        self.assertEqual(bitrows("AA", tracking=3), [(mask << 8) | mask for mask in a])
        self.assertEqual(bitrows("AA", tracking=0), [(mask << 5) | mask for mask in a])

    def test_empty_and_blank_text(self) -> None:
        self.assertEqual(bitrows(""), [0] * GLYPH_H)
        self.assertEqual(decompose(""), [])
        self.assertEqual(measure("", scale=3), (0, GLYPH_H * 3))
        self.assertEqual(render_path("", 0, 0, scale=3), "")
        self.assertEqual(render_rects("", 0, 0, scale=3), "")
        self.assertEqual(render_path("   ", 0, 0, scale=3), "")
        self.assertEqual(measure("   ", scale=3), (17 * 3, GLYPH_H * 3))

    def test_lowercase_and_uppercase_produce_identical_output(self) -> None:
        self.assertEqual(bitrows("game over"), bitrows("GAME OVER"))
        self.assertEqual(decompose("Jiteesh Ghodke"), decompose("JITEESH GHODKE"))
        self.assertEqual(
            render_path("score", 4, 8, scale=3), render_path("SCORE", 4, 8, scale=3)
        )

    def test_strict_raises_key_error_on_an_unknown_character(self) -> None:
        for func in (bitrows, decompose, measure):
            with self.subTest(func=func.__name__):
                with self.assertRaises(KeyError):
                    func("SCORÉ")
        with self.assertRaises(KeyError):
            render_path("café", 0, 0)
        with self.assertRaises(KeyError):
            render_rects("™", 0, 0)
        with self.assertRaises(KeyError) as raised:
            bitrows("{")
        self.assertIn("'{'", str(raised.exception))

    def test_lenient_mode_substitutes_a_filled_box(self) -> None:
        self.assertEqual(bitrows("é", strict=False), list(MISSING_GLYPH))
        self.assertEqual(decompose("é", strict=False), [Rect(0, 0, GLYPH_W, GLYPH_H)])
        self.assertEqual(measure("Aé", strict=False), (2 * GLYPH_W + 1, GLYPH_H))
        ET.fromstring(render_path("é", 0, 0, strict=False))

    def test_invalid_scale_and_tracking_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            measure("A", scale=0)
        with self.assertRaises(ValueError):
            render_path("A", 0, 0, scale=-1)
        with self.assertRaises(ValueError):
            bitrows("AB", tracking=-1)
        with self.assertRaises(ValueError):
            digit_slot(0, 0, scale=0)


class DecomposeTests(unittest.TestCase):
    def test_e_decomposes_into_exactly_four_blocks(self) -> None:
        # top bar, one 1x6 stem running through the middle bar, middle bar, bottom bar
        self.assertEqual(
            decompose("E"),
            [Rect(0, 0, 5, 1), Rect(0, 1, 1, 6), Rect(1, 3, 3, 1), Rect(1, 6, 4, 1)],
        )

    def test_block_area_equals_popcount_for_every_glyph(self) -> None:
        for char, rows in GLYPHS.items():
            with self.subTest(char=char):
                self.assertEqual(sum(rect.area for rect in decompose(char)), popcount(rows))

    def test_blocks_never_overlap_and_cover_exactly_the_lit_pixels(self) -> None:
        for char in GLYPHS:
            with self.subTest(char=char):
                self.assertEqual(paint(decompose(char)), lit_cells(char))

    def test_multi_character_area_is_the_sum_of_glyph_popcounts(self) -> None:
        for text in ("GAME OVER", "0123456789", "JITEESH GHODKE"):
            for tracking in (0, 1, 2):
                with self.subTest(text=text, tracking=tracking):
                    rects = decompose(text, tracking=tracking)
                    self.assertEqual(
                        sum(rect.area for rect in rects),
                        sum(popcount(GLYPHS[char]) for char in text),
                    )
                    self.assertEqual(paint(rects), lit_cells(text, tracking))

    def test_coalescing_never_loses_to_plain_row_runs(self) -> None:
        for char in GLYPHS:
            with self.subTest(char=char):
                self.assertLessEqual(len(decompose(char)), row_run_count(char))

    def test_letters_compress_well_below_one_block_per_pixel(self) -> None:
        pixels = sum(popcount(GLYPHS[char]) for char in string.ascii_uppercase)
        blocks = sum(len(decompose(char)) for char in string.ascii_uppercase)
        # 3.09 when this was written; the bound leaves room for glyph tweaks, not for a
        # broken coalescer, which would fall to about 1.4.
        self.assertGreaterEqual(pixels / blocks, 2.5)

    def test_blocks_lie_within_the_measured_box(self) -> None:
        for text in HUD_STRINGS:
            with self.subTest(text=text):
                width, height = measure(text)
                for rect in decompose(text):
                    self.assertGreaterEqual(rect.col, 0)
                    self.assertGreaterEqual(rect.row, 0)
                    self.assertLessEqual(rect.col + rect.w, width)
                    self.assertLessEqual(rect.row + rect.h, height)

    def test_measure_equals_the_extent_of_full_cell_text(self) -> None:
        for text in FULL_EXTENT_STRINGS:
            for scale in (1, 3, 4):
                with self.subTest(text=text, scale=scale):
                    rects = decompose(text)
                    extent = (
                        max(rect.col + rect.w for rect in rects) * scale,
                        max(rect.row + rect.h for rect in rects) * scale,
                    )
                    self.assertEqual(measure(text, scale=scale), extent)

    def test_measure_counts_the_advance_not_the_ink(self) -> None:
        # "1" lights columns 1..3 only, but still occupies a whole cell on the grid
        self.assertEqual(max(rect.col + rect.w for rect in decompose("1")), 4)
        self.assertEqual(measure("1"), (GLYPH_W, GLYPH_H))
        self.assertEqual(measure("AB", tracking=2, scale=3), ((5 + 2 + 5) * 3, 7 * 3))


class RenderTests(unittest.TestCase):
    def test_render_path_is_one_path_with_a_subpath_per_block(self) -> None:
        markup = render_path("SCORE", 10, 20, scale=3, fill="#39FF14", cls="hud")
        element = ET.fromstring(markup)
        self.assertEqual(element.tag, "path")
        self.assertEqual(element.get("class"), "hud")
        self.assertEqual(element.get("fill"), "#39FF14")
        data = element.get("d")
        self.assertTrue(data)
        self.assertEqual(data.count("M"), len(decompose("SCORE")))
        self.assertEqual(markup.count("<"), 1)

    def test_render_path_scales_and_offsets_every_block(self) -> None:
        data = ET.fromstring(render_path("E", 10, 20, scale=3)).get("d")
        self.assertEqual(data, "M10 20h15v3h-15zM10 23h3v18h-3zM13 29h9v3h-9zM13 38h12v3h-12z")

    def test_render_path_always_writes_a_fill(self) -> None:
        # the document root is fill="none", so an inherited fill would be invisible
        self.assertIn('fill="currentColor"', render_path("A", 0, 0))
        self.assertIn('fill="currentColor"', render_rects("A", 0, 0))
        self.assertIn('fill="currentColor"', digit_slot(0, 0))

    def test_coordinates_use_the_shared_number_formatter(self) -> None:
        data = ET.fromstring(render_path("E", 10.0, 20.5, scale=3)).get("d")
        self.assertTrue(data.startswith("M10 20.5h15"))
        self.assertNotIn(".0", data)

    def test_render_rects_emits_one_rect_per_block(self) -> None:
        rects = decompose("PAUSED")
        markup = render_rects(
            "PAUSED",
            4,
            8,
            scale=3,
            fill="#C9FFD6",
            cls_for=lambda index, rect: f"px-{index}" if index % 2 == 0 else None,
        )
        element = ET.fromstring(markup)
        self.assertEqual(element.tag, "g")
        self.assertEqual(element.get("fill"), "#C9FFD6")
        children = list(element)
        self.assertEqual(len(children), len(rects))
        self.assertEqual(markup.count("<rect"), len(rects))
        self.assertTrue(all(child.tag == "rect" for child in children))
        self.assertEqual(children[0].get("class"), "px-0")
        self.assertIsNone(children[1].get("class"))
        self.assertEqual(rects[0], Rect(0, 0, 4, 1))
        self.assertEqual(
            (children[0].get("x"), children[0].get("y")),
            ("4", "8"),
        )
        self.assertEqual(
            (children[0].get("width"), children[0].get("height")),
            ("12", "3"),
        )

    def test_render_rects_passes_index_and_block_to_cls_for(self) -> None:
        seen: list[tuple[int, Rect]] = []
        render_rects("E", 0, 0, cls_for=lambda index, rect: seen.append((index, rect)))
        self.assertEqual(seen, list(enumerate(decompose("E"))))

    def test_digit_slot_emits_ten_stacked_paths(self) -> None:
        markup = digit_slot(30, 40, scale=3, fill="#39FF14", cls_for=lambda d: f"score-d{d}")
        element = ET.fromstring(markup)
        self.assertEqual(element.tag, "g")
        self.assertEqual(element.get("fill"), "#39FF14")
        paths = list(element)
        self.assertEqual(len(paths), 10)
        self.assertEqual(markup.count("<path"), 10)
        for digit, path in enumerate(paths):
            with self.subTest(digit=digit):
                self.assertEqual(path.tag, "path")
                self.assertEqual(path.get("class"), f"score-d{digit}")
                expected = ET.fromstring(render_path(str(digit), 30, 40, scale=3)).get("d")
                self.assertEqual(path.get("d"), expected)
        self.assertEqual(len({path.get("d") for path in paths}), 10)

    def test_digit_slot_without_classes_still_emits_ten_paths(self) -> None:
        paths = list(ET.fromstring(digit_slot(0, 0, scale=3)))
        self.assertEqual(len(paths), 10)
        self.assertTrue(all(path.get("class") is None for path in paths))

    def test_attribute_values_are_escaped(self) -> None:
        markup = render_path("A", 0, 0, fill='url("#g")', cls='a"b')
        element = ET.fromstring(markup)
        self.assertEqual(element.get("fill"), 'url("#g")')
        self.assertEqual(element.get("class"), 'a"b')

    def test_output_is_deterministic(self) -> None:
        pairs = (
            (render_path("HIGH SCORE", 1, 2, scale=3), render_path("HIGH SCORE", 1, 2, scale=3)),
            (
                render_rects("NEXT", 1, 2, scale=3, cls_for=lambda i, r: f"n{i}"),
                render_rects("NEXT", 1, 2, scale=3, cls_for=lambda i, r: f"n{i}"),
            ),
            (
                digit_slot(5, 6, scale=4, cls_for=lambda d: f"d{d}"),
                digit_slot(5, 6, scale=4, cls_for=lambda d: f"d{d}"),
            ),
        )
        for first, second in pairs:
            self.assertEqual(first, second)
