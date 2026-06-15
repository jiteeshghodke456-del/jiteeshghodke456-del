from __future__ import annotations

import collections
import datetime as dt
import pathlib
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts.generate_profile_assets import (
    ContributionHTMLParser,
    calculate_streaks,
    render_github_activity,
    render_github_activity_mobile,
    render_github_overview,
    render_github_overview_mobile,
    render_codeforces_tetris,
    render_codeforces_tetris_mobile,
    render_projects_showcase,
    render_projects_showcase_mobile,
    render_terminal_intro,
    render_terminal_mobile,
)
from scripts.grow_contribution_snake import enhance_svg


SNAKE_FIXTURE = """<svg viewBox="-16 -32 160 96" xmlns="http://www.w3.org/2000/svg">
<style>
:root{--ce:#000;--cs:#fff}.c{animation:none 10000ms linear infinite}.s{animation:none linear 10000ms infinite}
@keyframes c0{20%{fill:red}20.1%,100%{fill:var(--ce)}}
@keyframes c1{60%{fill:blue}60.1%,100%{fill:var(--ce)}}
@keyframes s0{0%,90%{transform:translate(0px,-16px)}10%{transform:translate(0px,0px)}50%{transform:translate(64px,0px)}70%{transform:translate(64px,32px)}100%{transform:translate(0px,-16px)}}
</style>
<rect class="c c0" x="0" y="0" width="12" height="12"/>
<rect class="c c1" x="16" y="0" width="12" height="12"/>
<rect class="s s0" x="1" y="1" width="14" height="14"/>
<rect class="s s1" x="2" y="2" width="12" height="12"/>
<rect class="s s2" x="3" y="3" width="10" height="10"/>
<rect class="s s3" x="4" y="4" width="8" height="8"/>
</svg>"""


class ProfileAssetTests(unittest.TestCase):
    def test_terminal_has_paced_and_reduced_motion_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / "terminal.svg"
            mobile_path = root / "terminal-mobile.svg"
            render_terminal_intro(path)
            render_terminal_mobile(mobile_path)
            source = path.read_text(encoding="utf-8")
            ET.parse(path)
            ET.parse(mobile_path)

        self.assertIn("command-clip-0", source)
        self.assertIn("prefers-reduced-motion", source)
        self.assertIn("static-session", source)
        self.assertNotIn("scanline", source)

    def test_public_contribution_markup_parses_tooltip_counts(self) -> None:
        parser = ContributionHTMLParser()
        parser.feed(
            '<td id="day-1" data-date="2026-06-14" data-level="2"></td>'
            '<tool-tip for="day-1">3 contributions on June 14th.</tool-tip>'
        )
        self.assertEqual(parser.days[0]["count"], 3)

    def test_activity_streaks_allow_today_to_be_empty(self) -> None:
        today = dt.datetime.now(dt.UTC).date()
        contributions = [
            {"date": (today - dt.timedelta(days=3)).isoformat(), "count": 0},
            {"date": (today - dt.timedelta(days=2)).isoformat(), "count": 1},
            {"date": (today - dt.timedelta(days=1)).isoformat(), "count": 2},
            {"date": today.isoformat(), "count": 0},
        ]
        self.assertEqual(calculate_streaks(contributions), (3, 2, 2, 2))

    def test_overview_and_activity_are_valid_svg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            overview = root / "overview.svg"
            overview_mobile = root / "overview-mobile.svg"
            activity = root / "activity.svg"
            activity_mobile = root / "activity-mobile.svg"
            user = {"public_repos": 4, "followers": 2}
            repos = [{"stargazers_count": 3, "forks_count": 1}]
            languages = collections.Counter({"Python": 700, "C++": 300})
            render_github_overview(
                overview,
                "jiteeshghodke456-del",
                user,
                repos,
                languages,
            )
            render_github_overview_mobile(
                overview_mobile,
                "jiteeshghodke456-del",
                user,
                repos,
                languages,
            )
            render_github_activity(activity, [])
            render_github_activity_mobile(activity_mobile, [])
            ET.parse(overview)
            ET.parse(overview_mobile)
            ET.parse(activity)
            ET.parse(activity_mobile)

    def test_project_showcases_are_valid_and_colorful(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            desktop = root / "projects.svg"
            mobile = root / "projects-mobile.svg"
            render_projects_showcase(desktop)
            render_projects_showcase_mobile(mobile)
            desktop_source = desktop.read_text(encoding="utf-8")
            ET.parse(desktop)
            ET.parse(mobile)

        self.assertIn("Georgia", desktop_source)
        self.assertIn("USEFUL IDEAS", desktop_source)
        self.assertGreaterEqual(desktop_source.count("project-status"), 7)
        for color in ("#F5C16C", "#7DD3FC", "#F472B6", "#98C379"):
            self.assertIn(color, desktop_source)

    def test_codeforces_tetris_replays_at_a_readable_pace(self) -> None:
        now = int(dt.datetime.now(dt.UTC).timestamp())
        submissions = [
            {"creationTimeSeconds": now, "verdict": "OK"},
            {"creationTimeSeconds": now - 86400, "verdict": "WRONG_ANSWER"},
        ]

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            desktop = root / "tetris.svg"
            mobile = root / "tetris-mobile.svg"
            render_codeforces_tetris(desktop, "SobaDango", submissions)
            render_codeforces_tetris_mobile(mobile, "SobaDango", submissions)
            sources = [
                desktop.read_text(encoding="utf-8"),
                mobile.read_text(encoding="utf-8"),
            ]
            ET.parse(desktop)
            ET.parse(mobile)

        for source in sources:
            self.assertIn('dur="14s"', source)
            self.assertIn('repeatCount="indefinite"', source)
            self.assertIn('keyTimes="0.0000;', source)
            self.assertNotIn('fill="freeze"', source)

    def test_snake_grows_once_per_consumed_active_day(self) -> None:
        enhanced, count = enhance_svg(SNAKE_FIXTURE)
        ET.fromstring(enhanced)

        self.assertEqual(count, 2)
        self.assertEqual(enhanced.count('class="s grow-segment'), 2)
        self.assertIn("@keyframes grow_reveal_0", enhanced)
        self.assertIn("20.10%,100%", enhanced)
        self.assertIn("prefers-reduced-motion", enhanced)

    def test_snake_enhancement_is_idempotent(self) -> None:
        first, _ = enhance_svg(SNAKE_FIXTURE)
        second, count = enhance_svg(first)

        self.assertEqual(count, 2)
        self.assertEqual(second.count("profile-growing-snake:start"), 2)
        self.assertEqual(second.count('class="s grow-segment'), 2)


if __name__ == "__main__":
    unittest.main()
