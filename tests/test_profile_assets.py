"""Tests for the profile cockpit pipeline.

Several of these exist because the corresponding bug shipped during the
rebuild: the glyph scale factor lost precision to rounding and pushed the
nameplate past the canvas, and the gauges were briefly legible only while an
animation was running.
"""

from __future__ import annotations

import collections
import json
import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from cockpit import fetch, icons, svg, tokens  # noqa: E402
from cockpit.cards import cluster, nameplate, stack, tetris, work  # noqa: E402
from cockpit.typography import TypeSetter, fmt, load_face  # noqa: E402

CARDS = {
    "nameplate": nameplate,
    "cluster": cluster,
    "bays": work,
    "tetris": tetris,
    "stack": stack,
}

SAMPLE_SUBMISSIONS = [
    # problem A: three tries, accepted last
    {"creationTimeSeconds": 100, "verdict": "WRONG_ANSWER", "problem": {"contestId": 1, "index": "A"}, "programmingLanguage": "Python 3"},
    {"creationTimeSeconds": 200, "verdict": "TIME_LIMIT_EXCEEDED", "problem": {"contestId": 1, "index": "A"}, "programmingLanguage": "Python 3"},
    {"creationTimeSeconds": 300, "verdict": "OK", "problem": {"contestId": 1, "index": "A"}, "problem_rating": 800, "programmingLanguage": "Python 3"},
    # problem B: accepted first try
    {"creationTimeSeconds": 400, "verdict": "OK", "problem": {"contestId": 1, "index": "B", "rating": 900}, "programmingLanguage": "Python 3"},
    # problem C: never accepted
    {"creationTimeSeconds": 500, "verdict": "RUNTIME_ERROR", "problem": {"contestId": 2, "index": "C"}, "programmingLanguage": "GNU C11"},
]


def sample_data() -> dict:
    return {
        "user": {"login": "example", "created_at": "2025-09-27T07:22:04Z"},
        "repos": [],
        "repo_count": 27,
        "languages": collections.Counter(
            {"TypeScript": 1_908_767, "Python": 377_677, "CSS": 253_356, "Shell": 23_505}
        ),
        "contributions": [
            {"date": "2026-01-01", "count": 3, "level": 2},
            {"date": "2026-01-02", "count": 0, "level": 0},
            {"date": "2026-01-03", "count": 5, "level": 3},
        ],
        "streaks": {
            "total": 71,
            "longest": 6,
            "current": 0,
            "active_days": 41,
            "busiest_day": 9,
            "tracked_days": 365,
        },
        "account_age_days": 302,
        "codeforces": fetch.codeforces_stats(SAMPLE_SUBMISSIONS),
        "codeforces_submissions": SAMPLE_SUBMISSIONS,
    }


class FormattingTests(unittest.TestCase):
    def test_small_values_keep_significant_digits(self):
        """Glyph scale factors live near 0.07.

        Rounding those to two decimal places stretched every text run by up to
        7%, which is how the nameplate ended up wider than its canvas.
        """
        self.assertEqual(fmt(0.06655), "0.06655")
        self.assertNotEqual(fmt(0.06655), "0.07")
        self.assertLess(abs(float(fmt(0.012345)) - 0.012345), 1e-6)

    def test_large_values_stay_compact(self):
        self.assertEqual(fmt(880), "880")
        self.assertEqual(fmt(12.0), "12")
        self.assertEqual(fmt(12.456), "12.46")


class TypographyTests(unittest.TestCase):
    def test_every_face_loads(self):
        for face in (tokens.DISPLAY, tokens.MONO, tokens.MONO_SEMI):
            table = load_face(face)
            self.assertGreater(len(table["glyphs"]), 90, face)
            self.assertEqual(table["upem"], 1000, face)

    def test_measured_width_matches_emitted_scale(self):
        setter = TypeSetter()
        text = "JITEESH GHODKE"
        size = 66.5
        width = setter.width(text, tokens.DISPLAY, size, tokens.TRACK_NAMEPLATE)
        markup = setter.text(
            0, 0, text, face=tokens.DISPLAY, size=size,
            fill="#fff", tracking=tokens.TRACK_NAMEPLATE,
        )
        scale = float(markup.split("scale(")[1].split(" ")[0])
        units = setter.advance_units(text, tokens.DISPLAY, tokens.TRACK_NAMEPLATE)
        self.assertAlmostEqual(units * scale, width, delta=width * 0.001)

    def test_unknown_character_degrades_visibly(self):
        setter = TypeSetter()
        self.assertNotEqual(setter.text(0, 0, "☃", face=tokens.MONO, size=10, fill="#fff"), "")

    def test_glyphs_are_defined_once_and_reused(self):
        setter = TypeSetter()
        setter.text(0, 0, "AAAA", face=tokens.MONO, size=10, fill="#fff")
        self.assertEqual(setter.defs().count("<path id="), 1)


class NameplateTests(unittest.TestCase):
    def test_name_fits_inside_the_canvas(self):
        """The whole card is a first impression; overflow is a failed one."""
        for width in (tokens.WIDE, tokens.NARROW):
            document = nameplate.build(sample_data(), width=width)
            root = ET.fromstring(document)
            for group in root.iter("{http://www.w3.org/2000/svg}g"):
                transform = group.get("transform") or ""
                if "scale(" not in transform:
                    continue
                start_x = float(transform.split("translate(")[1].split(" ")[0])
                self.assertGreaterEqual(start_x, 0, f"text starts off-canvas at {width}px")
            self.assertLessEqual(
                _widest_text_run(document), width,
                f"a text run overflows the {width}px canvas",
            )


def _widest_text_run(document: str) -> float:
    """Right-most edge of any glyph run in the document."""
    setter = TypeSetter()
    widest = 0.0
    root = ET.fromstring(document)
    namespace = "{http://www.w3.org/2000/svg}"
    for group in root.iter(f"{namespace}g"):
        transform = group.get("transform") or ""
        if "translate(" not in transform or "scale(" not in transform:
            continue
        start_x = float(transform.split("translate(")[1].split(" ")[0])
        scale = float(transform.split("scale(")[1].split(" ")[0])
        uses = list(group.iter(f"{namespace}use"))
        if not uses:
            continue
        last = max(float(use.get("x") or 0) for use in uses)
        widest = max(widest, start_x + (last + 1000) * scale)
    return widest


class ClusterTests(unittest.TestCase):
    def test_gauges_are_legible_without_animation(self):
        """Static attributes must hold the reading, not the starting point."""
        document = cluster.build(sample_data(), width=tokens.WIDE)
        root = ET.fromstring(document)
        namespace = "{http://www.w3.org/2000/svg}"

        arcs = [
            element
            for element in root.iter(f"{namespace}path")
            if element.get("stroke-dasharray")
        ]
        self.assertTrue(arcs, "no value arcs were drawn")
        for arc in arcs:
            drawn = float(arc.get("stroke-dasharray").split(" ")[0])
            self.assertGreater(drawn, 0, "value arc is empty before animation")

        needles = [
            element
            for element in root.iter(f"{namespace}g")
            if (element.get("class") or "").startswith("nd")
        ]
        self.assertEqual(len(needles), 4)
        for needle in needles:
            angle = float(needle.get("transform").split("rotate(")[1].split(" ")[0])
            self.assertNotAlmostEqual(
                angle, cluster.START_ANGLE, msg="needle is parked at zero",
            )

    def test_motion_is_guarded_by_reduced_motion(self):
        document = cluster.build(sample_data(), width=tokens.WIDE)
        self.assertIn("prefers-reduced-motion:no-preference", document)

    def test_gauge_values_track_the_data(self):
        data = sample_data()
        gauges = cluster.gauges_from(data)
        by_label = {gauge["label"]: gauge for gauge in gauges}
        self.assertEqual(by_label["CONTRIBUTIONS"]["value"], 71)
        self.assertEqual(by_label["REPOSITORIES"]["value"], 27)
        self.assertEqual(
            by_label["ACCEPT RATE"]["value"], data["codeforces"]["accept_rate"]
        )

    def test_odometer_shows_one_cell_per_digit(self):
        setter = TypeSetter()
        drum = cluster._odometer(setter, 0, 0, 800, "000302", "days in")
        self.assertEqual(drum.count(f'fill="{tokens.VOID}"'), 6)

    def test_card_copy_is_drawn_as_outlines_not_text_nodes(self):
        """Type is vector, which is why copy cannot be asserted as a string.

        It also means the cards do not depend on a font being installed, and
        do not shift when GitHub changes its own stylesheet.
        """
        document = cluster.build(sample_data(), width=tokens.WIDE)
        root = ET.fromstring(document)
        self.assertEqual(list(root.iter("{http://www.w3.org/2000/svg}text")), [])
        self.assertTrue(list(root.iter("{http://www.w3.org/2000/svg}use")))
        # The reading is still exposed to screen readers through desc.
        desc = root.find("{http://www.w3.org/2000/svg}desc")
        self.assertIn("71 contributions", desc.text)


class TetrisTests(unittest.TestCase):
    def test_one_column_per_problem(self):
        columns = tetris.columns_from(SAMPLE_SUBMISSIONS, 60)
        self.assertEqual(len(columns), 3)
        self.assertEqual(columns[0], ["WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "OK"])
        self.assertEqual(columns[1], ["OK"])

    def test_no_submission_is_lost_within_the_limit(self):
        columns = tetris.columns_from(SAMPLE_SUBMISSIONS, 60)
        self.assertEqual(sum(len(column) for column in columns), len(SAMPLE_SUBMISSIONS))

    def test_first_try_accepts_counts_only_leading_ok(self):
        columns = tetris.columns_from(SAMPLE_SUBMISSIONS, 60)
        self.assertEqual(tetris.first_try_accepts(columns), 1)

    def test_verdict_colours_split_by_outcome(self):
        """Hue carries accepted-or-not; brightness separates failure modes."""
        self.assertEqual(tokens.VERDICT_COLORS["OK"], tokens.ICE)
        rejected = ("WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "RUNTIME_ERROR")
        for key in rejected:
            self.assertNotEqual(tokens.VERDICT_COLORS[key], tokens.ICE)
        self.assertEqual(
            len({tokens.VERDICT_COLORS[key] for key in rejected}), len(rejected),
            "failure modes must stay distinguishable",
        )


class StackTests(unittest.TestCase):
    def test_language_shares_sum_to_the_whole(self):
        languages = stack.top_languages(
            {"A": 50, "B": 30, "C": 10, "D": 5, "E": 3, "F": 1, "G": 1}, limit=3
        )
        self.assertEqual(languages[-1][0], "Other")
        self.assertEqual(sum(count for _, count in languages), 100)

    def test_no_segment_is_labelled_zero_percent(self):
        """Every listed language must round to at least one percent."""
        languages = {"A": 10_000, "B": 4_000, "C": 12, "D": 8}
        listed = stack.top_languages(languages)
        total = sum(count for _, count in listed)
        for name, count in listed:
            self.assertGreaterEqual(
                round(count / total * 100), 1, f"{name} would render as 0%"
            )

    def test_mix_stays_within_the_pair(self):
        self.assertEqual(stack.mix(tokens.ROSE, tokens.ICE, 0), tokens.ROSE.upper())
        self.assertEqual(stack.mix(tokens.ROSE, tokens.ICE, 1), tokens.ICE.upper())

    def test_every_referenced_icon_exists(self):
        referenced = set(stack.SHIPS_IN) | set(stack.LEARNING)
        for bay in work.BAYS:
            referenced.update(bay["stack"])
        missing = sorted(slug for slug in referenced if not icons.has(slug))
        self.assertEqual(missing, [], f"vendor_icons.py has not fetched: {missing}")


class WorkTests(unittest.TestCase):
    def test_every_bay_points_at_a_repository(self):
        for bay in work.BAYS:
            self.assertTrue(bay["repo"], f"{bay['name']} has no repo to open")

    def test_brand_is_spelled_ataleir(self):
        names = " ".join(bay["name"] for bay in work.BAYS)
        self.assertIn("ATALEIR", names)
        self.assertNotIn("ATELIER", names)


class DocumentTests(unittest.TestCase):
    def test_all_cards_render_valid_svg_at_both_widths(self):
        data = sample_data()
        for name, module in CARDS.items():
            for width in (tokens.WIDE, tokens.NARROW):
                document = module.build(data, width=width)
                with self.subTest(card=name, width=width):
                    root = ET.fromstring(document)
                    self.assertTrue(root.get("viewBox"))
                    self.assertTrue(root.findall("{http://www.w3.org/2000/svg}title"))

    def test_no_card_relies_on_svg_filters(self):
        """Filters are dropped silently by some renderers; gradients are not."""
        data = sample_data()
        for name, module in CARDS.items():
            document = module.build(data, width=tokens.WIDE)
            with self.subTest(card=name):
                self.assertNotIn("feGaussianBlur", document)
                self.assertNotIn("<filter", document)

    def test_cards_survive_missing_data(self):
        """A Codeforces outage must produce honest zeroes, not a crash."""
        empty = sample_data()
        empty["codeforces"] = fetch.codeforces_stats([])
        empty["codeforces_submissions"] = []
        empty["languages"] = collections.Counter()
        empty["streaks"] = dict(empty["streaks"], total=0)
        for name, module in CARDS.items():
            with self.subTest(card=name):
                ET.fromstring(module.build(empty, width=tokens.WIDE))


class FetchTests(unittest.TestCase):
    def test_streaks_counts_active_days_and_longest_run(self):
        days = [
            {"date": "2026-01-01", "count": 1},
            {"date": "2026-01-02", "count": 2},
            {"date": "2026-01-03", "count": 0},
            {"date": "2026-01-04", "count": 4},
        ]
        result = fetch.streaks(days)
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["active_days"], 3)
        self.assertEqual(result["longest"], 2)
        self.assertEqual(result["busiest_day"], 4)

    def test_codeforces_stats_counts_unique_problems(self):
        stats = fetch.codeforces_stats(SAMPLE_SUBMISSIONS)
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["accepted"], 2)
        self.assertEqual(stats["solved"], 2)
        self.assertEqual(stats["attempted"], 3)
        self.assertAlmostEqual(stats["accept_rate"], 40.0)

    def test_account_age_handles_a_missing_timestamp(self):
        self.assertEqual(fetch.account_age_days({}), 0)
        self.assertEqual(fetch.account_age_days({"created_at": "nonsense"}), 0)


class PaletteTests(unittest.TestCase):
    def test_accents_are_limited_to_the_declared_pair(self):
        """Every accent must be rose, ice, or a luminance step of one of them.

        The old design drifted to seven hues across three rendering systems.
        This is the guard that stops that happening again.
        """
        allowed = {
            tokens.ROSE, tokens.ICE, tokens.ROSE_BRIGHT, tokens.ROSE_DEEP,
            tokens.ICE_BRIGHT, tokens.ICE_DEEP, tokens.DIM, "#8C1F5A",
        }
        self.assertTrue(set(tokens.VERDICT_COLORS.values()).issubset(allowed))


class ReadmeTests(unittest.TestCase):
    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def test_readme_references_every_generated_asset(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        for name in CARDS:
            for suffix in ("", "-mobile"):
                self.assertIn(f"{name}{suffix}.svg", readme)
        self.assertIn("github-contribution-grid-snake.svg", readme)

    def test_readme_has_no_third_party_badge_services(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        for service in ("shields.io", "skillicons.dev", "komarev.com", "github-readme-stats"):
            self.assertNotIn(service, readme)

    def test_readme_spells_the_brand_correctly(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Ataleir", readme)
        self.assertNotIn("Atelier", readme)

    def test_vendored_assets_are_committed(self):
        for relative in (
            "assets/glyphs/display.json",
            "assets/glyphs/mono.json",
            "assets/glyphs/mono-semibold.json",
            "assets/icons/simple-icons.json",
        ):
            self.assertTrue((self.ROOT / relative).exists(), relative)

    def test_icon_table_records_its_licence(self):
        table = json.loads(
            (self.ROOT / "assets/icons/simple-icons.json").read_text(encoding="utf-8")
        )
        self.assertEqual(table["license"], "CC0-1.0")


if __name__ == "__main__":
    unittest.main()
