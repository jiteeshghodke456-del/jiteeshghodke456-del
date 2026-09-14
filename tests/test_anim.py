from __future__ import annotations

import dataclasses
import re
import unittest

from scripts.profilegen.svg.anim import AnimationSet, EmitterStats, Keyframe, Timeline


KEYFRAMES = re.compile(r"@keyframes ([A-Za-z_][\w-]*)\{")
# A class rule is ".name{...}" with no nested braces; keyframe selectors such as "37.42%{"
# never match because the character after the dot is a digit.
CLASS_RULE = re.compile(r"\.([A-Za-z_][\w-]*)\{([^{}]*)\}")
DURATION = re.compile(r"animation:[\w-]+ ([\d.]+)s ")
ANIMATION_NAME = re.compile(r"animation:([\w-]+) ")
REDUCED_MOTION = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def fall(distance: float) -> list[Keyframe]:
    return [
        Keyframe(0, {"transform": "translate(0,0)"}),
        Keyframe(2, {"transform": f"translate(0,{distance}px)"}),
    ]


def blink(on: float, off: float) -> list[Keyframe]:
    return [Keyframe(on, {"opacity": "1"}), Keyframe(off, {"opacity": "0"})]


def rules_by_class(css: str) -> dict[str, str]:
    return {name: body for name, body in CLASS_RULE.findall(css)}


def build_snake_like_set() -> AnimationSet:
    """A representative mix: shared path block, delayed uses, a linear track, bases."""
    anim = AnimationSet(Timeline(104.5))
    head = anim.add(
        [
            Keyframe(0, {"transform": "translate(0,0)"}),
            Keyframe(10.25, {"transform": "translate(16px,0)"}),
            Keyframe(20.5, {"transform": "translate(16px,16px)", "opacity": "0.5"}),
        ]
    )
    for segment in range(1, 5):
        anim.use(head, delay=-0.5 * segment, base={"transform": "translate(0,-16px)"})
    anim.add(blink(0, 52.25))
    anim.add(
        [Keyframe(0, {"transform": "rotate(0)"}), Keyframe(104.5, {"transform": "rotate(360)"})],
        easing="linear",
    )
    anim.add(blink(1, 2), delay=3.75, base={"opacity": "0"})
    return anim


class TimelineTests(unittest.TestCase):
    def test_percentages_are_monotonic_and_clamped(self) -> None:
        for duration in (1, 7.5, 14, 60, 104.5, 3600):
            timeline = Timeline(duration)
            samples = [-3.0, -0.0001, 0.0, duration + 0.0001, duration * 2]
            samples.extend(duration * step / 97 for step in range(98))
            texts = [timeline.pct(t) for t in sorted(samples)]
            values = [float(text) for text in texts]

            self.assertEqual(values, sorted(values), duration)
            self.assertTrue(all(0.0 <= value <= 100.0 for value in values), duration)
            self.assertEqual(texts[0], "0")
            self.assertEqual(texts[-1], "100")
            for text in texts:
                self.assertFalse(text.startswith("-"), text)
                self.assertFalse(text.endswith("."), text)

    def test_precision_controls_decimals(self) -> None:
        self.assertEqual(Timeline(3).pct(1), "33.33")
        self.assertEqual(Timeline(3, precision=0).pct(1), "33")
        self.assertEqual(Timeline(3, precision=4).pct(1), "33.3333")
        self.assertEqual(Timeline(104.5).duration, 104.5)

    def test_rejects_unusable_durations(self) -> None:
        for duration in (0, -1, float("inf"), float("nan"), "ten"):
            with self.assertRaises(ValueError, msg=repr(duration)):
                Timeline(duration)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            Timeline(10, precision=-1)
        with self.assertRaises(ValueError):
            Timeline(10).pct(float("nan"))


class AnimationSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timeline = Timeline(104.5)
        self.anim = AnimationSet(self.timeline)

    # ------------------------------------------------------------ dedup and use()

    def test_identical_tracks_share_one_keyframe_block(self) -> None:
        first = self.anim.add(fall(48))
        second = self.anim.add(fall(48))
        css = self.anim.css()

        self.assertNotEqual(first, second)
        self.assertEqual(len(KEYFRAMES.findall(css)), 1)
        rules = rules_by_class(css)
        self.assertEqual(set(rules), {first, second})
        names = {ANIMATION_NAME.search(body).group(1) for body in rules.values()}
        self.assertEqual(names, set(KEYFRAMES.findall(css)))
        self.assertEqual(self.anim.stats().keyframe_blocks, 1)
        self.assertEqual(self.anim.stats().rules, 2)

    def test_spelling_and_order_do_not_defeat_dedup(self) -> None:
        self.anim.add(
            [
                Keyframe(2, {"transform": "translate(0px, 48px)", "opacity": "1"}),
                Keyframe(0, {"opacity": 1.0, "transform": "translate(0,0)"}),
            ]
        )
        self.anim.add(
            [
                Keyframe(0, {"transform": " translate( 0 , 0 ) ", "opacity": "1.000"}),
                Keyframe(2, {"transform": "translate(0,48)", "opacity": "1"}),
            ]
        )

        self.assertEqual(self.anim.stats().keyframe_blocks, 1)

    def test_different_tracks_get_separate_blocks(self) -> None:
        self.anim.add(fall(48))
        self.anim.add(fall(64))
        css = self.anim.css()

        names = KEYFRAMES.findall(css)
        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2)

    def test_use_replays_an_existing_block_at_a_new_delay(self) -> None:
        head = self.anim.add(fall(48))
        tail = self.anim.use(head, delay=-1.25)
        css = self.anim.css()

        (name,) = KEYFRAMES.findall(css)
        rules = rules_by_class(css)
        self.assertEqual(len(rules), 2)
        self.assertIn(f"animation:{name} 104.5s step-end -1.25s infinite", rules[tail])
        self.assertIn(f"animation:{name} 104.5s step-end infinite", rules[head])
        self.assertEqual(self.anim.stats().keyframe_blocks, 1)
        self.assertEqual(self.anim.stats().tracks, 2)

    def test_use_requires_a_class_returned_by_add(self) -> None:
        head = self.anim.add(fall(48))
        tail = self.anim.use(head, delay=-1)
        other = AnimationSet(self.timeline, "s")
        other.add(fall(48))

        with self.assertRaises(ValueError):
            self.anim.use("nope", delay=0)
        with self.assertRaises(ValueError):
            self.anim.use(tail, delay=-2)
        with self.assertRaises(ValueError):
            other.use(head, delay=0)

    def test_use_inherits_easing_from_add(self) -> None:
        spin = self.anim.add(fall(8), easing="linear")
        copy = self.anim.use(spin, delay=1)

        self.assertIn(" linear ", rules_by_class(self.anim.css())[copy])

    # ------------------------------------------------------------ validation

    def test_geometry_properties_raise(self) -> None:
        for name in ("x", "y", "width", "height", "cx", "cy", "r", "rx", "ry", "d", "points"):
            with self.assertRaises(ValueError, msg=name):
                self.anim.add([Keyframe(0, {name: "0"}), Keyframe(1, {name: "10"})])
        for name in ("fill-opacity", "color", "stroke-width"):
            with self.assertRaises(ValueError, msg=name):
                self.anim.add([Keyframe(0, {name: "0"}), Keyframe(1, {name: "1"})])
        with self.assertRaises(ValueError):
            self.anim.add(fall(8), base={"x": "0"})
        cls = self.anim.add(fall(8))
        with self.assertRaises(ValueError):
            self.anim.use(cls, delay=0, base={"width": "1"})

    def test_percentage_and_other_bad_transforms_raise(self) -> None:
        bad = (
            "translate(50%,0)",
            "translate(0,100%)",
            "scale(50%)",
            "translate(1em,0)",
            "translate(1rem,0)",
            "rotate(1rad)",
            "rotate(0.5turn)",
            "scale(2px)",
            "translateX(4px)",
            "skew(10deg)",
            "matrix(1,0,0,1,0,0)",
            "rotate(45,8,8)",
            "translate(1px,2px,3px)",
            "translate(1px,2px) junk",
            "none",
            "",
        )
        for value in bad:
            with self.assertRaises(ValueError, msg=value):
                self.anim.add(
                    [
                        Keyframe(0, {"transform": "translate(0,0)"}),
                        Keyframe(1, {"transform": value}),
                    ]
                )
        with self.assertRaises(ValueError):
            self.anim.add(fall(8), base={"transform": "translate(-50%,0)"})

        good = (
            "translate(4px, 0)",
            "translate(4,-3)",
            "translate(4px)",
            "rotate(90)",
            "rotate(90deg)",
            "scale(1.5)",
            "scale(2,3)",
            "translate(1px,2px) rotate(45deg) scale(2)",
        )
        for value in good:
            self.anim.add(
                [Keyframe(0, {"transform": "translate(0,0)"}), Keyframe(1, {"transform": value})]
            )

    def test_transform_values_are_canonical(self) -> None:
        self.anim.add(
            [
                Keyframe(0, {"transform": "translate(0px, 0px)"}),
                Keyframe(
                    1, {"transform": " translate( 12.34567px , 7 )  rotate(90) scale(2, 2) "}
                ),
                Keyframe(2, {"transform": "translate(-0.04px, 3) scale(1.5, 0.25)"}),
            ]
        )
        css = self.anim.css()

        self.assertIn("{transform:translate(0,0)}", css)
        self.assertIn("{transform:translate(12.3px,7px) rotate(90deg) scale(2)}", css)
        self.assertIn("{transform:translate(0,3px) scale(1.5,0.25)}", css)

    def test_noop_track_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.anim.add([Keyframe(0, {"opacity": "1"}), Keyframe(5, {"opacity": "1"})])
        with self.assertRaises(ValueError):
            self.anim.add([Keyframe(5, {"opacity": "1"})])
        with self.assertRaises(ValueError):
            self.anim.add(
                [
                    Keyframe(0, {"transform": "translate(0,0)"}),
                    Keyframe(5, {"transform": "translate(0px,0px)"}),
                ]
            )
        with self.assertRaises(ValueError):
            self.anim.add([])

    def test_keyframes_are_validated_on_construction(self) -> None:
        with self.assertRaises(ValueError):
            Keyframe(0, {})
        with self.assertRaises(ValueError):
            Keyframe(float("nan"), {"opacity": "1"})
        with self.assertRaises(ValueError):
            Keyframe("soon", {"opacity": "1"})  # type: ignore[arg-type]

    def test_easing_is_validated_and_step_end_is_default(self) -> None:
        default = self.anim.add(fall(8))
        linear = self.anim.add(fall(16), easing="linear")
        steps = self.anim.add(fall(24), easing="steps(4, end)")
        bezier = self.anim.add(fall(32), easing="cubic-bezier(0.4, 0, 0.2, 1)")
        rules = rules_by_class(self.anim.css())

        self.assertIn(" step-end ", rules[default])
        self.assertIn(" linear ", rules[linear])
        self.assertIn(" steps(4,end) ", rules[steps])
        self.assertIn(" cubic-bezier(0.4,0,0.2,1) ", rules[bezier])
        for easing in ("stepend", "ease-in-out-x", "steps(0)", "", "linear;"):
            with self.assertRaises(ValueError, msg=easing):
                self.anim.add(fall(40), easing=easing)

    def test_opacity_values_are_validated(self) -> None:
        for value in ("abc", "1.2", "-0.5", ""):
            with self.assertRaises(ValueError, msg=value):
                self.anim.add([Keyframe(0, {"opacity": "0"}), Keyframe(1, {"opacity": value})])
        self.anim.add(
            [
                Keyframe(0, {"opacity": ".5", "stroke-opacity": "1.0000001"}),
                Keyframe(1, {"opacity": 0, "stroke-opacity": "0"}),
            ]
        )
        css = self.anim.css()

        self.assertIn("{opacity:0.5;stroke-opacity:1}", css)
        self.assertIn("{opacity:0;stroke-opacity:0}", css)

    def test_values_that_would_end_the_rule_early_raise(self) -> None:
        for value in ("#fff}", "#fff;", "#fff{", "url(#g)}"):
            with self.assertRaises(ValueError, msg=value):
                self.anim.add([Keyframe(0, {"fill": "#000"}), Keyframe(1, {"fill": value})])

    def test_prefix_isolates_sets_and_is_validated(self) -> None:
        first = AnimationSet(self.timeline, "a")
        second = AnimationSet(self.timeline, "s")
        first.add(fall(8))
        second.add(fall(8))
        a_names = set(KEYFRAMES.findall(first.css())) | set(rules_by_class(first.css()))
        s_names = set(KEYFRAMES.findall(second.css())) | set(rules_by_class(second.css()))

        self.assertTrue(a_names)
        self.assertFalse(a_names & s_names)
        for prefix in ("", "1", "-x", "a b"):
            with self.assertRaises(ValueError, msg=repr(prefix)):
                AnimationSet(self.timeline, prefix)

    # ------------------------------------------------------------ rendered CSS

    def test_every_rule_shares_the_timeline_duration(self) -> None:
        anim = build_snake_like_set()
        css = anim.css()
        durations = DURATION.findall(css)

        self.assertEqual(len(durations), anim.stats().rules)
        self.assertGreater(len(durations), 5)
        self.assertEqual(set(durations), {"104.5"})

        short = AnimationSet(Timeline(14))
        short.add(fall(8))
        short.use(short.add(blink(0, 7)), delay=-2)
        self.assertEqual(set(DURATION.findall(short.css())), {"14"})

    def test_stats_match_rendered_css(self) -> None:
        anim = build_snake_like_set()
        stats = anim.stats()
        css = anim.css()

        self.assertIsInstance(stats, EmitterStats)
        self.assertEqual(stats.keyframe_blocks, len(KEYFRAMES.findall(css)))
        self.assertEqual(stats.keyframe_blocks, 4)
        self.assertEqual(stats.rules, len(CLASS_RULE.findall(css)))
        self.assertEqual(stats.tracks, 8)
        self.assertEqual(stats.rules, stats.tracks)
        self.assertEqual(stats.bytes, len(css))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            stats.bytes = 0  # type: ignore[misc]

    def test_base_declarations_land_in_the_class_rule(self) -> None:
        cls = self.anim.add(fall(48), base={"transform": "translate(0,-16px)", "opacity": "0"})
        copy = self.anim.use(cls, delay=-2, base={"opacity": ".5"})
        css = self.anim.css()

        self.assertIn(
            f".{cls}{{opacity:0;transform:translate(0,-16px);"
            f"animation:a0 104.5s step-end infinite;transform-origin:0 0}}",
            css,
        )
        self.assertIn(
            f".{copy}{{opacity:0.5;animation:a0 104.5s step-end -2s infinite;"
            "transform-origin:0 0}",
            css,
        )

    def test_delays_round_trip(self) -> None:
        head = self.anim.add(fall(48))
        negative = self.anim.use(head, delay=-3.5)
        positive = self.anim.add(blink(0, 1), delay=2.25)
        zero = self.anim.use(head, delay=-0.0)
        tiny = self.anim.use(head, delay=0.0004)
        rules = rules_by_class(self.anim.css())

        self.assertIn(" -3.5s infinite", rules[negative])
        self.assertIn(" 2.25s infinite", rules[positive])
        self.assertIn("animation:a0 104.5s step-end infinite", rules[head])
        self.assertIn("animation:a0 104.5s step-end infinite", rules[zero])
        self.assertIn("animation:a0 104.5s step-end infinite", rules[tiny])
        self.assertNotIn("0s infinite", rules[zero])
        with self.assertRaises(ValueError):
            self.anim.use(head, delay=float("nan"))

    def test_output_is_deterministic(self) -> None:
        first = build_snake_like_set()
        second = build_snake_like_set()

        self.assertEqual(first.css(), second.css())
        self.assertEqual(first.stats(), second.stats())
        self.assertEqual(first.css(), first.css())

    def test_css_orders_sections_and_ends_with_reduced_motion(self) -> None:
        moving = self.anim.add(fall(48))
        fading = self.anim.add(blink(0, 1))
        css = self.anim.css()
        rules = rules_by_class(css)

        self.assertLess(css.index("@keyframes"), css.index(f".{moving}{{"))
        self.assertLess(css.rindex("@keyframes"), css.index(f".{moving}{{"))
        self.assertLess(css.index(f".{fading}{{"), css.index("@media"))
        self.assertTrue(css.endswith(REDUCED_MOTION))
        self.assertEqual(css.count("prefers-reduced-motion"), 1)
        self.assertIn("transform-origin:0 0", rules[moving])
        self.assertNotIn("transform-origin", rules[fading])
        self.assertEqual(css.count("\n"), 0)

    def test_empty_set_still_emits_the_reduced_motion_block(self) -> None:
        self.assertEqual(self.anim.css(), REDUCED_MOTION)
        self.assertEqual(self.anim.stats(), EmitterStats(0, 0, 0, len(REDUCED_MOTION)))

    # ------------------------------------------------------------ body canonicalisation

    def test_adjacent_identical_states_coalesce_per_easing(self) -> None:
        timeline = Timeline(100)
        frames = [
            Keyframe(0, {"opacity": "0"}),
            Keyframe(10, {"opacity": "0"}),
            Keyframe(20, {"opacity": "0"}),
            Keyframe(30, {"opacity": "1"}),
            Keyframe(40, {"opacity": "1"}),
        ]
        stepped = AnimationSet(timeline)
        stepped.add(frames)
        smooth = AnimationSet(timeline)
        smooth.add(frames, easing="linear")

        self.assertIn("@keyframes a0{0%{opacity:0}30%{opacity:1}}", stepped.css())
        self.assertIn("@keyframes a0{0%,20%{opacity:0}30%,40%{opacity:1}}", smooth.css())

    def test_same_stop_frames_merge_property_wise(self) -> None:
        anim = AnimationSet(Timeline(100))
        anim.add(
            [
                Keyframe(0, {"opacity": "1", "transform": "translate(0,0)"}),
                Keyframe(10.001, {"opacity": "0.2"}),
                Keyframe(10.004, {"transform": "translate(1px,0)"}),
                Keyframe(20.001, {"opacity": "0.3"}),
                Keyframe(20.002, {"opacity": "0.7"}),
            ]
        )
        css = anim.css()

        self.assertIn("10%{opacity:0.2;transform:translate(1px,0)}", css)
        self.assertIn("20%{opacity:0.7}", css)
        self.assertNotIn("0.3", css)

    def test_frames_outside_the_timeline_are_clamped(self) -> None:
        anim = AnimationSet(Timeline(10))
        anim.add([Keyframe(-5, {"opacity": "0"}), Keyframe(15, {"opacity": "1"})])

        self.assertIn("@keyframes a0{0%{opacity:0}100%{opacity:1}}", anim.css())

    def test_repeated_states_share_a_selector_list(self) -> None:
        anim = AnimationSet(Timeline(100))
        anim.add(
            [
                Keyframe(0, {"opacity": "0"}),
                Keyframe(25, {"opacity": "1"}),
                Keyframe(50, {"opacity": "0"}),
                Keyframe(75, {"opacity": "1"}),
            ]
        )

        self.assertIn("@keyframes a0{0%,50%{opacity:0}25%,75%{opacity:1}}", anim.css())

    def test_class_and_keyframe_names_are_base36(self) -> None:
        anim = AnimationSet(Timeline(100))
        names = [
            anim.add(
                [Keyframe(0, {"opacity": "0"}), Keyframe(index + 1, {"opacity": "1"})]
            )
            for index in range(37)
        ]
        css = anim.css()

        self.assertEqual(names[:3], ["a0", "a1", "a2"])
        self.assertEqual(names[9], "a9")
        self.assertEqual(names[10], "aa")
        self.assertEqual(names[35], "az")
        self.assertEqual(names[36], "a10")
        self.assertEqual(len(set(names)), 37)
        self.assertEqual(KEYFRAMES.findall(css)[36], "a10")
        self.assertEqual(anim.stats().keyframe_blocks, 37)
