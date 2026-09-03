from __future__ import annotations

import importlib.util
import math
import random
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_bubble_module():
    # Avoid importing widgets.spotify_visualizer.__init__, which pulls Qt into
    # otherwise presentation-neutral Bubble math.
    package = types.ModuleType("widgets.spotify_visualizer")
    package.__path__ = [str(ROOT / "widgets" / "spotify_visualizer")]
    sys.modules["widgets.spotify_visualizer"] = package

    registry = types.ModuleType("core.settings.visualizer_mode_registry")
    registry.VisualizerClipPolicy = type("VisualizerClipPolicy", (), {})
    registry.VisualizerShellPolicy = type("VisualizerShellPolicy", (), {})
    sys.modules["core.settings.visualizer_mode_registry"] = registry

    _load_module(
        "widgets.spotify_visualizer.render_state",
        ROOT / "widgets" / "spotify_visualizer" / "render_state.py",
    )
    _load_module(
        "widgets.spotify_visualizer.signal_contract",
        ROOT / "widgets" / "spotify_visualizer" / "signal_contract.py",
    )
    return _load_module(
        "widgets.spotify_visualizer.bubble_simulation",
        ROOT / "widgets" / "spotify_visualizer" / "bubble_simulation.py",
    )


class BubbleViewportScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bubble = _load_bubble_module()

    def _impulse_delta(self, extent: tuple[float, float]) -> tuple[float, float]:
        bs = self.bubble
        sim = bs.BubbleSimulation()
        sim._apply_viewport_domain(extent)
        bubble = bs.BubbleState(
            x=0.5 * sim._domain_w,
            y=0.5 * sim._domain_h,
            radius=0.03,
            is_big=True,
            reaches_surface=False,
            max_age=999.0,
            impulse_vx=0.18,
            impulse_vy=0.12,
            trail_tail_x=0.5 * sim._domain_w,
            trail_tail_y=0.5 * sim._domain_h,
        )
        sim._bubbles = [bubble]
        before = (bubble.x / sim._domain_w, bubble.y / sim._domain_h)
        sim.tick(
            1.0 / 60.0,
            None,
            {
                "_bubble_viewport_extent": extent,
                "bubble_big_count": 1,
                "bubble_small_count": 0,
                "bubble_stream_direction": "none",
                "bubble_stream_constant_speed": 0.0,
                "bubble_stream_speed_cap": 0.0,
                "bubble_stream_reactivity": 0.0,
                "bubble_drift_amount": 0.0,
                "bubble_drift_speed": 0.0,
                "bubble_drift_frequency": 0.0,
                "bubble_drift_direction": "none",
                "bubble_trail_strength": 0.0,
                "bubble_bounce_big_pct": 0.0,
                "bubble_bounce_small_pct": 0.0,
            },
        )
        after = (bubble.x / sim._domain_w, bubble.y / sim._domain_h)
        return (after[0] - before[0], after[1] - before[1])

    def test_preloaded_rebound_impulse_is_content_space_invariant(self):
        expected = self._impulse_delta((420.0, 280.0))
        for extent in (
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
        ):
            actual = self._impulse_delta(extent)
            self.assertAlmostEqual(actual[0], expected[0], places=12)
            self.assertAlmostEqual(actual[1], expected[1], places=12)

    def test_swirl_vector_uses_equivalent_content_space_geometry(self):
        bs = self.bubble
        expected = None
        for extent in (
            (420.0, 280.0),
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
        ):
            sim = bs.BubbleSimulation()
            sim._apply_viewport_domain(extent)
            bubble = bs.BubbleState(
                x=0.68 * sim._domain_w,
                y=0.37 * sim._domain_h,
                drift_bias=0.42,
            )
            move = sim._swirl_motion(
                bubble,
                "swirl_cw",
                0.63,
                0.57,
                1.0 / 90.0,
                0.44,
            )
            if expected is None:
                expected = move
            else:
                self.assertAlmostEqual(move[0], expected[0], places=12)
                self.assertAlmostEqual(move[1], expected[1], places=12)

    def test_swirl_birth_offset_is_content_space_invariant(self):
        bs = self.bubble
        positions = []
        for extent in (
            (420.0, 280.0),
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
        ):
            random.seed(1847)
            sim = bs.BubbleSimulation()
            sim._apply_viewport_domain(extent)
            sim._spawn_bubble(
                False,
                "none",
                1.0,
                "swirl_ccw",
            )
            bubble = sim._bubbles[0]
            positions.append(
                (bubble.x / sim._domain_w, bubble.y / sim._domain_h)
            )
        for actual in positions[1:]:
            self.assertAlmostEqual(actual[0], positions[0][0], places=12)
            self.assertAlmostEqual(actual[1], positions[0][1], places=12)

    def _trail_payload(self, extent: tuple[float, float]) -> tuple[float, ...]:
        bs = self.bubble
        sim = bs.BubbleSimulation()
        sim._apply_viewport_domain(extent)
        domain_w = sim._domain_w
        domain_h = sim._domain_h
        bubble = bs.BubbleState(
            x=0.52 * domain_w,
            y=0.49 * domain_h,
            radius=0.03,
            is_big=True,
            reaches_surface=False,
            max_age=999.0,
            trail_tail_x=0.50 * domain_w,
            trail_tail_y=0.50 * domain_h,
        )
        sim._bubbles = [bubble]
        sim._update_trail_smear(
            bubble,
            1.0 / 60.0,
            0.02 * domain_w,
            -0.01 * domain_h,
        )
        positions, _extras, trails = sim.snapshot()
        return tuple(positions[:2]) + tuple(trails)

    def test_motion_tail_geometry_and_strength_are_content_space_invariant(self):
        expected = self._trail_payload((420.0, 280.0))
        self.assertTrue(expected[2:])
        for extent in (
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
            (724.0, 816.0),
        ):
            actual = self._trail_payload(extent)
            self.assertEqual(len(actual), len(expected))
            for lhs, rhs in zip(actual, expected):
                self.assertAlmostEqual(lhs, rhs, places=12)
    def _collision_positions(self, extent: tuple[float, float]) -> tuple[float, ...]:
        bs = self.bubble
        sim = bs.BubbleSimulation()
        sim._apply_viewport_domain(extent)
        a = bs.BubbleState(
            x=0.48 * sim._domain_w,
            y=0.50 * sim._domain_h,
            radius=0.050,
            is_big=True,
            reaches_surface=False,
            max_age=999.0,
            pulse_energy=1.0,
            size_gate_energy=1.0,
        )
        b = bs.BubbleState(
            x=0.56 * sim._domain_w,
            y=0.53 * sim._domain_h,
            radius=0.050,
            is_big=True,
            reaches_surface=False,
            max_age=999.0,
            pulse_energy=1.0,
            size_gate_energy=1.0,
        )
        sim._bubbles = [a, b]
        sim._apply_bubble_collision_response(
            1.0 / 60.0,
            bounce_big_pct=0.0,
            bounce_small_pct=0.0,
            bounce_big_speed=0.0,
            bounce_small_speed=0.0,
            big_bass_pulse=0.0,
            small_freq_pulse=0.0,
            big_contraction_bias=1.0,
            big_size_clamp=0.0,
        )
        return (
            a.x / sim._domain_w,
            a.y / sim._domain_h,
            b.x / sim._domain_w,
            b.y / sim._domain_h,
        )

    def test_collision_resolution_is_content_space_invariant(self):
        expected = self._collision_positions((420.0, 280.0))
        self.assertNotEqual(expected, (0.48, 0.50, 0.56, 0.53))
        for extent in (
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
            (724.0, 816.0),
        ):
            actual = self._collision_positions(extent)
            for lhs, rhs in zip(actual, expected):
                self.assertAlmostEqual(lhs, rhs, places=12)

    def test_bubble_outline_preserves_large_viewport_weight_without_heavy_baseline(self):
        # The operator judged the old ~1.2 authored-pixel stroke appropriate at
        # the ~2.9x-tall CUSTOM viewport but much too thick at canonical/small
        # sizes. Radius-proportional stroke preserves that large-card ratio.
        radius = 0.04
        canonical_inner_h = 272.0
        observed_tall_inner_h = 808.0

        def stroke_px(inner_h: float) -> float:
            px = 1.0 / inner_h
            stroke_norm = max(0.35 * px, min(1.8 * px, radius * 0.0375))
            return stroke_norm * inner_h

        canonical = stroke_px(canonical_inner_h)
        tall = stroke_px(observed_tall_inner_h)
        self.assertLess(canonical, 0.5)
        self.assertAlmostEqual(tall, 1.2, delta=0.03)

        shader = (ROOT / "widgets/spotify_visualizer/shaders/bubble.frag").read_text()
        self.assertIn("float stroke = clamp(r * 0.0375, 0.35 * px, 1.8 * px);", shader)
        self.assertNotIn("float base_stroke_px = 1.2;", shader)

    def test_motion_tail_complete_presentation_footprint_stays_authored_pixel_scaled(self):
        # Stored trail history remains normalized/content-space invariant. R4
        # corrected only the three source-centre offsets; the physically failed
        # tall run proved that each source's ripple radius/ring spacing must use
        # the same authored-pixel authority as well.
        baseline = (420.0, 280.0)
        head = (0.62, 0.44)
        sample = (0.52, 0.50)
        expected_source_px = (
            (sample[0] - head[0]) * baseline[0],
            (sample[1] - head[1]) * baseline[1],
        )
        expected_cap_px = 0.12 * baseline[1]
        expected_ring_spacing_px = (2.0 * math.pi / 220.0) * baseline[1]
        brad = 0.04
        age = 1.0
        trail_strength = 1.0
        expected_ripple_px = min(
            brad * (2.0 + age * 6.0) * trail_strength,
            0.12,
        ) * baseline[1]

        for extent in (
            baseline,
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
            (724.0, 816.0),
        ):
            axis = (
                min(1.0, baseline[0] / extent[0]),
                min(1.0, baseline[1] / extent[1]),
            )
            radial = min(1.0, baseline[1] / extent[1])
            rendered = (
                head[0] + (sample[0] - head[0]) * axis[0],
                head[1] + (sample[1] - head[1]) * axis[1],
            )
            actual_source_px = (
                (rendered[0] - head[0]) * extent[0],
                (rendered[1] - head[1]) * extent[1],
            )
            self.assertAlmostEqual(actual_source_px[0], expected_source_px[0], places=12)
            self.assertAlmostEqual(actual_source_px[1], expected_source_px[1], places=12)

            cap_px = (0.12 * radial) * extent[1]
            ring_spacing_px = (2.0 * math.pi / (220.0 / radial)) * extent[1]
            ripple_px = min(
                (brad * radial) * (2.0 + age * 6.0) * trail_strength,
                0.12 * radial,
            ) * extent[1]
            self.assertAlmostEqual(cap_px, expected_cap_px, places=12)
            self.assertAlmostEqual(ring_spacing_px, expected_ring_spacing_px, places=12)
            self.assertAlmostEqual(ripple_px, expected_ripple_px, places=12)

        quick = (ROOT / "rendering/quick/visualizer/implementations/bubble.py").read_text()
        shader = (ROOT / "widgets/spotify_visualizer/shaders/bubble.frag").read_text()
        self.assertIn("trail_axis_scale", quick)
        self.assertIn("trail_radial_scale", quick)
        self.assertIn("u_trail_axis_scale", shader)
        self.assertIn("u_trail_radial_scale", shader)
        self.assertIn("vec2 trail_axis_scale = (u_quick_item_coords == 1)", shader)
        self.assertIn("float trail_radial_scale = (u_quick_item_coords == 1)", shader)
        self.assertIn("sample_data.xy - bpos.xy", shader)
        self.assertIn("float ring_freq = 220.0 / trail_radial_scale;", shader)
        self.assertIn("float wake_brad = brad * trail_radial_scale;", shader)
        self.assertIn("float max_ripple_radius = 0.12 * trail_radial_scale;", shader)
        self.assertIn("ripple_bound", shader)

    def test_bubble_head_and_ghost_never_gain_a_second_viewport_compressor(self):
        """R-69 golden bar: preserve authored reactivity at wide/tall CUSTOM extents."""
        quick = (ROOT / "rendering/quick/visualizer/implementations/bubble.py").read_text()
        shader = (ROOT / "widgets/spotify_visualizer/shaders/bubble.frag").read_text()

        # The failed repair globally compressed head radius as viewport height
        # grew. That made Bubble appear nearly non-reactive at extreme CUSTOM
        # sizes even though the simulation remained lively. Never restore it.
        self.assertNotIn("head_radial_scale", quick)
        self.assertNotIn("u_head_radial_scale", quick)
        self.assertNotIn("u_head_radial_scale", shader)

        # Ripple wake is intentionally authored-pixel compact, but Ghost history
        # is already renderer-normalized and must be consumed exactly once.
        ghost = shader.split("// --- Ghost pass", 1)[1]
        self.assertIn("vec2 history_xy = history.xy;", ghost)
        self.assertNotIn("trail_axis_scale", ghost)
        self.assertNotIn("trail_radial_scale", ghost)
        self.assertIn("u_ghost_decay", ghost)
        self.assertIn("ghost_decay_exponent", ghost)

        # Extreme-size correction may strengthen only the presentation edge; it
        # must not change authored radius or motion amplitude.
        self.assertIn("large_viewport_stroke_bonus_px", quick)
        self.assertIn("large_viewport_stroke_bonus_px", shader)

    def test_spawn_overlap_policy_is_content_space_invariant(self):
        bs = self.bubble
        decisions = []
        for extent in (
            (420.0, 280.0),
            (840.0, 280.0),
            (420.0, 560.0),
            (840.0, 560.0),
            (724.0, 816.0),
        ):
            sim = bs.BubbleSimulation()
            sim._apply_viewport_domain(extent)
            sim._bubbles = [
                bs.BubbleState(
                    x=0.50 * sim._domain_w,
                    y=0.50 * sim._domain_h,
                    radius=0.040,
                    is_big=True,
                )
            ]
            decisions.append(
                (
                    sim._overlaps_existing(
                        0.57 * sim._domain_w,
                        0.50 * sim._domain_h,
                        0.040,
                        candidate_is_big=True,
                    ),
                    sim._overlaps_existing(
                        0.70 * sim._domain_w,
                        0.50 * sim._domain_h,
                        0.040,
                        candidate_is_big=True,
                    ),
                )
            )
        self.assertEqual(decisions[0], (True, False))
        self.assertTrue(all(value == decisions[0] for value in decisions[1:]))


class RetainedPresentationCoherenceTests(unittest.TestCase):
    def test_geometry_mismatch_keeps_last_valid_visualizer_pixels(self):
        bridge = (ROOT / "widgets/spotify_visualizer/render_bridge.py").read_text()
        item = (ROOT / "rendering/quick/visualizer/item.py").read_text()
        self.assertIn("required_presentation", bridge)
        self.assertIn("self._presentation_mismatch_count += 1", bridge)
        self.assertIn("required_presentation=presentation", item)
        self.assertNotIn(
            'clear_snapshot = True\n\n        if snapshot is not None and is_viz_diagnostics_enabled()',
            item,
        )

    def test_perf_hud_is_passive_and_perf_gated(self):
        scene = (ROOT / "rendering/quick/scene_controller.py").read_text()
        qml = (ROOT / "rendering/quick/qml/DisplayScene.qml").read_text()
        viz_qml = (
            ROOT / "rendering/quick/qml/VisualizerPresentation.qml"
        ).read_text()
        self.assertIn("is_perf_metrics_enabled", scene)
        self.assertIn("_update_perf_hud_on_swap", scene)
        self.assertIn("elapsed_ns < 1_000_000_000", scene)
        self.assertNotIn("QTimer", scene)
        self.assertIn("property bool perfHudEnabled", qml)
        self.assertIn("property bool perfHudEnabled", viz_qml)



class OtherModeViewportScalingTests(unittest.TestCase):
    @staticmethod
    def _spread_fraction(inner_height: float, viewport_height_scale: float) -> float:
        spacing_scale = viewport_height_scale
        base = max(
            20.0 * spacing_scale,
            min(80.0 * spacing_scale, inner_height * 0.25),
        )
        return base / inner_height

    def test_vertical_shift_default_spread_survives_tall_viewport(self):
        # Scale=1 card geometry: 4 px shell border each side. Osc then removes
        # 1 px per side; Sine removes 2 px per side.
        cases = (
            (270.0, 1.0, 550.0, 2.0),  # Oscilloscope
            (268.0, 1.0, 548.0, 2.0),  # Sine
        )
        for canonical_h, canonical_scale, tall_h, tall_scale in cases:
            canonical = self._spread_fraction(canonical_h, canonical_scale)
            tall = self._spread_fraction(tall_h, tall_scale)
            self.assertAlmostEqual(canonical, 0.25, places=12)
            self.assertAlmostEqual(tall, canonical, places=12)

        osc_shader = (ROOT / "widgets/spotify_visualizer/shaders/oscilloscope.frag").read_text()
        sine_shader = (ROOT / "widgets/spotify_visualizer/shaders/sine_wave.frag").read_text()
        for shader in (osc_shader, sine_shader):
            self.assertIn("u_viewport_height_scale", shader)
            self.assertIn("20.0 * spacing_scale", shader)
            self.assertIn("80.0 * spacing_scale", shader)

    def test_spectrum_height_transfer_is_resolved_once(self):
        spectrum_math = _load_module(
            "_viewport_spectrum_math",
            ROOT / "widgets/spotify_visualizer/spectrum_solid_hysteresis.py",
        )
        for height in (80.0, 280.0, 560.0, 815.92):
            resolved = spectrum_math.compute_spectrum_height_scale(height)
            self.assertGreaterEqual(resolved, 1.0)
            self.assertLessEqual(resolved, 1.85)

        shader = (ROOT / "widgets/spotify_visualizer/shaders/spectrum.frag").read_text()
        self.assertIn(
            "float height_scale = clamp(max(1.0, u_bar_height_scale), 1.0, 1.85);",
            shader,
        )
        self.assertNotIn("sqrt(raw_hs)", shader)

        quick = (ROOT / "rendering/quick/visualizer/implementations/spectrum.py").read_text()
        legacy = (ROOT / "widgets/spotify_visualizer/renderers/spectrum.py").read_text()
        self.assertIn("height_scale=compute_spectrum_height_scale(extent_height)", quick)
        self.assertIn("compute_spectrum_height_scale(cur_h)", legacy)

    def test_devcurve_keeps_authored_pixel_tuning_across_viewport_extent(self):
        # Quick DevCurve intentionally converts normalized controls by the
        # baseline/current content ratio so outlines/specular offsets keep the
        # same logical-pixel tuning while the curve domain reflows.
        baseline_w = 412.0
        baseline_h = 272.0
        for current_w, current_h in ((412.0, 272.0), (824.0, 552.0), (710.0, 792.0)):
            normalized_x_scale = baseline_w / current_w
            normalized_y_scale = baseline_h / current_h
            for authored_value, axis_scale, current_extent, baseline_extent in (
                (0.006, normalized_y_scale, current_h, baseline_h),
                (0.022, normalized_x_scale, current_w, baseline_w),
                (0.028, normalized_y_scale, current_h, baseline_h),
                (0.010, normalized_y_scale, current_h, baseline_h),
                (0.009, normalized_x_scale, current_w, baseline_w),
            ):
                physical_px = authored_value * axis_scale * current_extent
                self.assertAlmostEqual(
                    physical_px,
                    authored_value * baseline_extent,
                    places=12,
                )

        source = (ROOT / "rendering/quick/visualizer/implementations/devcurve.py").read_text()
        shader = (ROOT / "widgets/spotify_visualizer/shaders/devcurve.frag").read_text()
        self.assertIn("u_devcurve_normalized_scale", source)
        self.assertIn("* layout.normalized_y_scale", source)
        self.assertIn("* layout.normalized_x_scale", source)
        self.assertIn("_quick_norm_x(0.009)", shader)
        self.assertIn("_quick_norm_y(0.010)", shader)
        self.assertIn("_quick_norm_y(0.006)", shader)
        self.assertNotIn("float rx = max(0.009,", shader)
        self.assertNotIn("float offset = max(0.010,", shader)

    def test_devcurve_specular_cross_axis_geometry_stays_pixel_invariant(self):
        baseline_w, baseline_h = 412.0, 272.0
        authored_rx = 0.022
        lobe_ratio = 0.33
        expected_ry_px = authored_rx * lobe_ratio * baseline_h
        for current_w, current_h in (
            (412.0, 272.0),
            (824.0, 272.0),
            (412.0, 792.0),
            (710.0, 792.0),
        ):
            x_scale = baseline_w / current_w
            y_scale = baseline_h / current_h
            rx = authored_rx * x_scale
            x_to_y = y_scale / x_scale
            ry = rx * x_to_y * lobe_ratio
            self.assertAlmostEqual(ry * current_h, expected_ry_px, places=12)

        source = (ROOT / "rendering/quick/visualizer/implementations/devcurve.py").read_text()
        shader = (ROOT / "widgets/spotify_visualizer/shaders/devcurve.frag").read_text()
        self.assertIn("u_devcurve_x_to_y_scale", source)
        self.assertIn("layout.normalized_y_scale / layout.normalized_x_scale", source)
        self.assertIn("rx * xToY * mix(0.26, 0.40, r2)", shader)
        self.assertIn("_quick_norm_y(0.0010)", shader)

    def test_devcurve_authored_bounds_are_applied_before_viewport_projection(self):
        source = (ROOT / "rendering/quick/visualizer/implementations/devcurve.py").read_text()
        # Regression bar for the subtle failure where a projected value was
        # clamped back to a canonical normalized minimum/maximum.
        self.assertIn(")\n                * layout.normalized_y_scale,", source)
        self.assertIn(")\n            * layout.normalized_x_scale,", source)
        self.assertIn(")\n            * layout.normalized_y_scale,", source)

        # Concrete default at the user's ~2.9x-tall viewport: the old shader
        # floor forced 0.028 * (272/792) back up to 0.010. The projected floor
        # now stays below the authored projected offset instead.
        y_scale = 272.0 / 792.0
        projected_offset = 0.028 * y_scale
        projected_floor = 0.010 * y_scale
        self.assertLess(projected_floor, projected_offset)
        self.assertLess(projected_offset, 0.010)


if __name__ == "__main__":
    unittest.main()
