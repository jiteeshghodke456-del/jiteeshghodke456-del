"""Tests for the profile arcade pipeline.

Several of these exist because the corresponding bug shipped during a rebuild: the glyph
scale factor lost precision to rounding and pushed the old nameplate past the canvas, a
mobile layout ran past a hardcoded height, and a private project was one typo away from
being linked.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from cockpit import fetch, icons, scene, tokens  # noqa: E402
from cockpit.cards import (  # noqa: E402
    boot,
    credits,
    inventory,
    player,
    snake,
    stack,
    tetris,
    warps,
    worlds,
)
from cockpit.typography import TypeSetter, fmt, load_face  # noqa: E402

CARDS = {
    "boot": boot,
    "player": player,
    "worlds": worlds,
    "tetris": tetris,
    "snake": snake,
    "inventory": inventory,
    "credits": credits,
}

SVG = "{http://www.w3.org/2000/svg}"

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
        "user": {"login": "example", "created_at": "2025-09-27T07:22:04Z", "public_repos": 30},
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
        "codeforces_profile": {
            "rating": 608,
            "max_rating": 608,
            "rank": "newbie",
            "contests": [{"new": 376, "at": 1000}, {"new": 608, "at": 2000}],
            "known": True,
        },
        "codeforces_submissions": SAMPLE_SUBMISSIONS,
    }


def _empty_data() -> dict:
    empty = sample_data()
    empty["codeforces"] = fetch.codeforces_stats([])
    empty["codeforces_submissions"] = []
    empty["codeforces_profile"] = {"rating": 0, "max_rating": 0, "rank": "", "contests": [], "known": False}
    empty["languages"] = collections.Counter()
    empty["contributions"] = []
    empty["streaks"] = dict(empty["streaks"], total=0, active_days=0, longest=0, busiest_day=0)
    return empty


class FormattingTests(unittest.TestCase):
    def test_small_values_keep_significant_digits(self):
        """Glyph scale factors live near 0.07.

        Rounding those to two decimal places stretched every text run by up to
        7%, which is how the old nameplate ended up wider than its canvas.
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


class WorldTests(unittest.TestCase):
    def test_private_projects_carry_no_repository(self):
        """A link that 404s for every visitor is worse than no link.

        Two worlds are private. They are on the map because they are real work, and a reader
        can be told what a thing is without being handed the source, but nothing may point
        at them.
        """
        for world in worlds.WORLDS:
            with self.subTest(world=world["name"]):
                if world["private"]:
                    self.assertIsNone(world["repo"], f"{world['name']} is private but carries a repo")
                else:
                    self.assertTrue(world["repo"], f"{world['name']} is public but has no repo")

    def test_public_worlds_are_linked_from_the_readme(self):
        readme = pathlib.Path("README.md").read_text(encoding="utf-8")
        for world in worlds.WORLDS:
            with self.subTest(world=world["name"]):
                if world["repo"]:
                    self.assertIn(world["repo"], readme)

    def test_private_worlds_are_never_linked_from_the_readme(self):
        """No markdown link may be labelled with a private project's name."""
        readme = pathlib.Path("README.md").read_text(encoding="utf-8")
        labels = {
            label.strip("* ").lower()
            for label in re.findall(r"\[([^\]]+)\]\(http", readme)
        }
        for world in worlds.WORLDS:
            if world["private"]:
                with self.subTest(world=world["name"]):
                    self.assertFalse(
                        any(world["name"].lower() in label for label in labels),
                        f"{world['name']} is linked",
                    )

    def test_private_worlds_are_never_linked_from_the_card(self):
        for width in (tokens.WIDE, tokens.NARROW):
            document = worlds.build(sample_data(), width=width)
            self.assertNotIn("<a ", document)

    def test_no_world_is_a_placeholder(self):
        for world in worlds.WORLDS:
            with self.subTest(world=world["name"]):
                self.assertNotIn("COMING SOON", world["status"].upper())

    def test_brand_is_spelled_ataleir(self):
        names = " ".join(world["name"] for world in worlds.WORLDS)
        self.assertIn("ATALEIR", names)
        self.assertNotIn("ATELIER", names)


class ReadmeStyleTests(unittest.TestCase):
    def test_no_dashes_are_used_to_split_sentences(self):
        """House style: complete sentences, and no double hyphen anywhere.

        Clauses bolted on after a dash read as an afterthought. The rule is enforced rather
        than remembered because it is the kind of thing that creeps back one line at a time.
        """
        readme = pathlib.Path("README.md").read_text(encoding="utf-8")
        offenders = [
            f"line {number}: {line.strip()[:90]}"
            for number, line in enumerate(readme.splitlines(), 1)
            if "\u2014" in line or re.search(r"--", line)
        ]
        self.assertEqual(offenders, [])

    def test_the_story_runs_in_chapter_order(self):
        """Chapters and warps interleave in the order the story is told."""
        readme = pathlib.Path("README.md").read_text(encoding="utf-8")
        order = ["boot", "warp-1", "player", "warp-2", "worlds", "warp-3", "tetris",
                 "warp-4", "snake", "warp-5", "inventory", "credits"]
        positions = [readme.index(f"output/{name}.svg") for name in order]
        self.assertEqual(positions, sorted(positions))

    def test_every_image_carries_the_current_cache_buster(self):
        from profilegen import ASSET_VERSION

        readme = pathlib.Path("README.md").read_text(encoding="utf-8")
        versions = set(re.findall(r"\.svg\?v=(\d+)", readme))
        self.assertEqual(versions, {str(ASSET_VERSION)})


class CardGeometryTests(unittest.TestCase):
    def test_no_card_hardcodes_its_height(self):
        """A canvas asserted ahead of the content will eventually disagree with it.

        The old nameplate did this and it is how the banner broke. Every chapter derives its
        height from its layout cursor; warps are fixed strips and say so with a constant.
        """
        cards = pathlib.Path("scripts/cockpit/cards")
        offenders = []
        for module in sorted(cards.glob("*.py")):
            for number, line in enumerate(module.read_text(encoding="utf-8").splitlines(), 1):
                if re.match(r"\s*height\s*=\s*[\d.]+(\s+if\b.*)?$", line):
                    offenders.append(f"{module.name}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "height must follow the content")

    def test_text_runs_stay_inside_the_canvas(self):
        for name, module in CARDS.items():
            if name == "snake":
                continue
            for width in (tokens.WIDE, tokens.NARROW):
                with self.subTest(card=name, width=width):
                    document = module.build(sample_data(), width=width)
                    self.assertLessEqual(_widest_text_run(document), width + 0.5)


def _widest_text_run(document: str) -> float:
    """Right-most edge of any unanimated glyph run placed directly on the canvas."""
    widest = 0.0
    root = ET.fromstring(document)
    for group in root.iter(f"{SVG}g"):
        transform = group.get("transform") or ""
        if not transform.startswith("translate(") or "scale(" not in transform:
            continue
        start_x = float(transform.split("translate(")[1].split(" ")[0])
        scale = float(transform.split("scale(")[1].split(" ")[0].rstrip(")"))
        uses = list(group.iter(f"{SVG}use"))
        if not uses:
            continue
        last = max(float(use.get("x") or 0) for use in uses)
        widest = max(widest, start_x + (last + 600) * scale)
    return widest


class ChapterTests(unittest.TestCase):
    def test_every_chapter_names_itself_in_the_header_order(self):
        self.assertEqual(
            scene.CHAPTERS,
            ("BOOT", "PLAYER SELECT", "WORLD MAP", "BOSS FIGHT", "BONUS STAGE", "INVENTORY", "CREDITS"),
        )

    def test_motion_is_guarded_by_reduced_motion(self):
        for name, module in CARDS.items():
            with self.subTest(card=name):
                document = module.build(sample_data(), width=tokens.WIDE)
                self.assertIn("prefers-reduced-motion", document)

    def test_card_copy_is_drawn_as_outlines_not_text_nodes(self):
        """Type is vector, so the cards do not depend on a font being installed."""
        for name, module in CARDS.items():
            with self.subTest(card=name):
                root = ET.fromstring(module.build(sample_data(), width=tokens.WIDE))
                self.assertEqual(list(root.iter(f"{SVG}text")), [])
                self.assertTrue(root.find(f"{SVG}desc").text)

    def test_nothing_uses_smil(self):
        for name, module in CARDS.items():
            with self.subTest(card=name):
                self.assertNotIn("<animate", module.build(sample_data(), width=tokens.WIDE))


class CreditsTests(unittest.TestCase):
    def test_the_tallest_problem_is_credited_with_its_real_count(self):
        rows = dict(credits._credits(sample_data()))
        self.assertEqual(rows["PROBLEM 1A"], "3 attempts, 1 regret")

    def test_the_rating_only_boasts_when_it_never_dropped(self):
        data = sample_data()
        self.assertIn("never gone down", dict(credits._credits(data))["RATING"])
        data["codeforces_profile"]["contests"].append({"new": 500, "at": 3000})
        self.assertNotIn("never gone down", dict(credits._credits(data))["RATING"])

    def test_the_ask_is_on_screen_at_rest(self):
        """With motion off, a reader still sees how to get in touch."""
        document = credits.build(sample_data(), width=tokens.WIDE)
        self.assertIn("internship", ET.fromstring(document).find(f"{SVG}desc").text)


class InventoryTests(unittest.TestCase):
    def test_rarity_tiers_follow_the_share(self):
        self.assertEqual(inventory.rarity(0.63)[0], "LEGENDARY")
        self.assertEqual(inventory.rarity(0.17)[0], "EPIC")
        self.assertEqual(inventory.rarity(0.05)[0], "RARE")
        self.assertEqual(inventory.rarity(0.02)[0], "UNCOMMON")
        self.assertEqual(inventory.rarity(0.001)[0], "COMMON")


class WarpTests(unittest.TestCase):
    def test_every_warp_renders_a_fixed_strip_at_both_widths(self):
        for index in range(len(warps.WARPS)):
            for width in (tokens.WIDE, tokens.NARROW):
                with self.subTest(warp=index + 1, width=width):
                    root = ET.fromstring(warps.build(index, width=width))
                    self.assertEqual(float(root.get("height")), warps.HEIGHT)
                    self.assertEqual(float(root.get("width")), width)
                    self.assertEqual(list(root.iter(f"{SVG}text")), [])

    def test_there_is_one_warp_between_each_pair_of_scrolling_chapters(self):
        self.assertEqual(len(warps.WARPS), 5)


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
        self.assertEqual(tokens.VERDICT_COLORS["OK"], tokens.ACID)
        rejected = ("WRONG_ANSWER", "TIME_LIMIT_EXCEEDED", "RUNTIME_ERROR")
        for key in rejected:
            self.assertNotEqual(tokens.VERDICT_COLORS[key], tokens.ACID)
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

    def test_every_referenced_icon_exists(self):
        referenced = set(stack.SHIPS_IN) | set(stack.LEARNING) | set(inventory.ICON_FOR.values())
        for world in worlds.WORLDS:
            referenced.update(world["stack"])
        missing = sorted(slug for slug in referenced if slug and not icons.has(slug))
        self.assertEqual(missing, [], f"vendor_icons.py has not fetched: {missing}")


class DocumentTests(unittest.TestCase):
    def test_all_cards_render_valid_svg_at_both_widths(self):
        data = sample_data()
        for name, module in CARDS.items():
            for width in (tokens.WIDE, tokens.NARROW):
                document = module.build(data, width=width)
                with self.subTest(card=name, width=width):
                    root = ET.fromstring(document)
                    self.assertTrue(root.get("viewBox"))
                    self.assertTrue(root.findall(f"{SVG}title"))

    def test_no_card_relies_on_svg_filters(self):
        """Filters are dropped silently by some renderers; gradients are not."""
        data = sample_data()
        for name, module in CARDS.items():
            document = module.build(data, width=tokens.WIDE)
            with self.subTest(card=name):
                self.assertNotIn("feGaussianBlur", document)
                self.assertNotIn("<filter", document)

    def test_cards_survive_missing_data(self):
        """A Codeforces or GitHub outage must produce honest zeroes, not a crash."""
        for name, module in CARDS.items():
            for width in (tokens.WIDE, tokens.NARROW):
                with self.subTest(card=name, width=width):
                    ET.fromstring(module.build(_empty_data(), width=width))


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
        """Every verdict colour must be acid, violet, or a luminance step of one of them."""
        allowed = {
            tokens.VIOLET, tokens.ACID, tokens.VIOLET_BRIGHT, tokens.VIOLET_DEEP,
            tokens.ACID_BRIGHT, tokens.ACID_DEEP, tokens.DIM, "#7A2BC4",
        }
        self.assertTrue(set(tokens.VERDICT_COLORS.values()).issubset(allowed))


class ReadmeTests(unittest.TestCase):
    ROOT = pathlib.Path(__file__).resolve().parent.parent

    def test_readme_references_every_generated_asset(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        names = list(CARDS) + [f"warp-{index}" for index in range(1, len(warps.WARPS) + 1)]
        for name in names:
            for suffix in ("", "-mobile"):
                with self.subTest(asset=f"{name}{suffix}"):
                    self.assertIn(f"{name}{suffix}.svg", readme)

    def test_readme_has_no_third_party_badge_services(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        for service in ("shields.io", "skillicons.dev", "komarev.com", "github-readme-stats"):
            self.assertNotIn(service, readme)

    def test_readme_spells_the_brand_correctly(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Ataleir", readme)
        self.assertNotIn("Atelier", readme)

    def test_the_drishti_demo_link_is_a_pages_url(self):
        readme = (self.ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("https://jiteeshghodke456-del.github.io/ruraldrushtiteam5idiots/", readme)
        self.assertNotIn("github.com/jiteeshghodke456-del.github.io", readme)

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
