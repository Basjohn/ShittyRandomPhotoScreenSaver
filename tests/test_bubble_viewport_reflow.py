"""G4.3 - Bubble logical viewport reflow.

Bubble runs in a baseline-relative logical domain: canonical (420x280) is a
strict 1x1 no-op that leaves the legacy unit-square path and render arrays
exactly unchanged; a wide/tall committed extent expands the logical world while
authored population and Bubble personality stay unchanged (a larger world is
naturally less dense). The render seam normalizes positions/trails back to
[0,1], retains historical card-height-normalized radius, maps that radius back
into expanded-world collision units, and lets the shader keep circles round.
Stream/drift movement projects onto expanded domain axes once so its normalized
content travel and trail remain stable at canonical, wide and tall extents.
These bars prove that contract deterministically; H5c B9 remains the operator
physical-acceptance gate.
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.bubble_simulation import (
    BubbleSimulation,
    BubbleState,
)


_NO_KEY = object()


def _settings(extent=_NO_KEY, **over):
    settings = {
        "bubble_big_count": 6,
        "bubble_small_count": 20,
        "bubble_stream_direction": "up",
        "bubble_drift_direction": "random",
    }
    if extent is not _NO_KEY:
        settings["_bubble_viewport_extent"] = extent
    settings.update(over)
    return settings


_ENERGY = {"bass": 0.3, "mid": 0.2, "high": 0.1, "overall": 0.3}


def _run(extent, *, seed=20260829, ticks=1, **over):
    random.seed(seed)
    sim = BubbleSimulation()
    for _ in range(ticks):
        sim.tick(0.016, dict(_ENERGY), _settings(extent, **over))
    return sim


def test_canonical_extent_is_a_strict_noop() -> None:
    # Absent key, explicit None, and canonical (420,280) all take the exact
    # legacy 1x1 path: identical bubbles and byte-identical render arrays.
    baseline = _run(_NO_KEY)
    none_extent = _run(None)
    canonical = _run((420.0, 280.0))

    def _positions(sim):
        return [(b.x, b.y, b.radius) for b in sim._bubbles]

    assert _positions(none_extent) == _positions(baseline)
    assert _positions(canonical) == _positions(baseline)
    assert none_extent.snapshot() == baseline.snapshot()
    assert canonical.snapshot() == baseline.snapshot()
    assert baseline._domain_w == 1.0 and baseline._domain_h == 1.0


def test_wide_extent_expands_logical_x_and_normalizes_output() -> None:
    wide = _run((630.0, 280.0))
    assert wide._domain_w == pytest.approx(1.5)
    assert wide._domain_h == pytest.approx(1.0)

    # Bubbles fill the wider logical world: some logical x exceeds the unit box.
    assert max(b.x for b in wide._bubbles) > 1.0
    # Height is untouched.
    assert max(b.y for b in wide._bubbles) <= 1.0 + 1e-6

    pos, _extra, _trails = wide.snapshot()
    for idx, b in enumerate(wide._bubbles):
        assert pos[idx * 4] == pytest.approx(b.x / 1.5)
        assert pos[idx * 4 + 1] == pytest.approx(b.y)


def test_tall_extent_expands_logical_y_and_normalizes_output() -> None:
    tall = _run((420.0, 560.0))
    assert tall._domain_w == pytest.approx(1.0)
    assert tall._domain_h == pytest.approx(2.0)

    assert max(b.y for b in tall._bubbles) > 1.0
    assert max(b.x for b in tall._bubbles) <= 1.0 + 1e-6

    pos, _extra, _trails = tall.snapshot()
    for idx, b in enumerate(tall._bubbles):
        assert pos[idx * 4] == pytest.approx(b.x)
        assert pos[idx * 4 + 1] == pytest.approx(b.y / 2.0)


def test_authored_counts_are_unchanged_by_viewport_extent() -> None:
    # Population is authored; a larger viewport is simply less dense, never a
    # silently larger particle count.
    baseline = _run(_NO_KEY)
    wide = _run((630.0, 280.0))
    tall = _run((420.0, 560.0))

    def _counts(sim):
        big = sum(1 for b in sim._bubbles if b.is_big)
        small = sum(1 for b in sim._bubbles if not b.is_big)
        return big, small

    assert _counts(wide) == _counts(baseline)
    assert _counts(tall) == _counts(baseline)
    assert _counts(baseline) == (6, 20)


class _OneShotSnareScheduler:
    """Production-shaped consume-once scheduler with observable delivery."""

    def __init__(self) -> None:
        self.snare_delivery_count = 0

    def consume_next(self, event_type, max_age_s=0.5):
        del max_age_s
        if event_type == "snare" and self.snare_delivery_count == 0:
            self.snare_delivery_count += 1
            return SimpleNamespace(strength=1.0)
        return None


def _run_viewport_transient_motion(
    extent,
    *,
    stream_direction,
    drift_direction,
    diag_key,
    start=(0.5, 0.5),
    group_drift=False,
):
    random.seed(20260831)
    domain_w = float(extent[0]) / 420.0
    domain_h = float(extent[1]) / 280.0
    sim = BubbleSimulation()
    sim._apply_viewport_domain(extent)
    sim._bubbles = [
        BubbleState(
            x=start[0] * domain_w,
            y=start[1] * domain_h,
            radius=0.03,
            is_big=True,
            reaches_surface=False,
            phase=0.55,
            drift_bias=0.35,
            speed_mult=1.0,
            display_radius=0.03,
            trail_tail_x=start[0] * domain_w,
            trail_tail_y=start[1] * domain_h,
        )
    ]
    scheduler = _OneShotSnareScheduler()
    settings = {
        "_bubble_viewport_extent": extent,
        "_event_scheduler": scheduler,
        "bubble_big_count": 0,
        "bubble_small_count": 0,
        "bubble_stream_direction": stream_direction,
        "bubble_stream_constant_speed": 0.12,
        "bubble_stream_speed_cap": 1.8,
        "bubble_stream_reactivity": 1.0,
        "bubble_drift_direction": drift_direction,
        "bubble_drift_amount": 0.65,
        "bubble_drift_speed": 0.65,
        "bubble_drift_frequency": 0.45,
        "bubble_group_drift": group_drift,
        "bubble_trail_strength": 1.0,
        "bubble_bounce_big_pct": 0.0,
        "bubble_bounce_small_pct": 0.0,
    }
    body = {
        "bass": 0.26,
        "mid": 0.22,
        "high": 0.09,
        "overall": 0.22,
        "smooth_mid": 0.22,
        "smooth_high": 0.09,
        "crest": 0.0,
    }
    previous = start
    path = 0.0
    radii = []
    diag_steps = []
    positions = []
    trails = []
    for _frame in range(10):
        sim.tick(1.0 / 90.0, body, settings)
        position_data, _extra_data, trail_data = sim.snapshot()
        current = (position_data[0], position_data[1])
        path += math.hypot(current[0] - previous[0], current[1] - previous[1])
        previous = current
        positions.append(current)
        radii.append(position_data[2])
        diag_steps.append(sim.get_big_lane_diagnostics()[diag_key])
        trails.append(tuple(trail_data))

    final_trail = trails[-1]
    trail_vector = (
        final_trail[6] - final_trail[0],
        final_trail[7] - final_trail[1],
    )
    return {
        "delivery_count": scheduler.snare_delivery_count,
        "positions": positions,
        "path": path,
        "radii": radii,
        "diag_steps": diag_steps,
        "trail_vector": trail_vector,
        "trail_length": math.hypot(*trail_vector),
    }


@pytest.mark.parametrize(
    ("stream_direction", "drift_direction", "diag_key", "expanded_extent"),
    (
        ("right", "none", "stream_step_mean", (840.0, 280.0)),
        ("up", "none", "stream_step_mean", (420.0, 560.0)),
        ("none", "swish_horizontal", "drift_step_mean", (840.0, 280.0)),
        ("none", "swish_vertical", "drift_step_mean", (420.0, 560.0)),
    ),
)
def test_transient_stream_and_drift_preserve_content_space_motion_across_viewports(
    stream_direction,
    drift_direction,
    diag_key,
    expanded_extent,
) -> None:
    """The same edge must remain equally visible at every viewport extent.

    Bubble's world expands with the committed viewport, but the renderer consumes
    normalized head/trail coordinates. Stream and drift therefore need to cover
    the same fraction of the chosen viewport per authored step; fixed raw-world
    deltas silently halve visible motion in a doubled axis. Radius/BTF authority
    stays independent from this spatial projection.
    """

    canonical = _run_viewport_transient_motion(
        (420.0, 280.0),
        stream_direction=stream_direction,
        drift_direction=drift_direction,
        diag_key=diag_key,
    )
    expanded = _run_viewport_transient_motion(
        expanded_extent,
        stream_direction=stream_direction,
        drift_direction=drift_direction,
        diag_key=diag_key,
    )

    assert canonical["delivery_count"] == expanded["delivery_count"] == 1
    assert canonical["path"] > 0.0
    assert canonical["trail_length"] > 0.0
    assert expanded["positions"] == pytest.approx(canonical["positions"], abs=1e-12)
    assert expanded["path"] == pytest.approx(canonical["path"], abs=1e-12)
    assert expanded["trail_vector"] == pytest.approx(
        canonical["trail_vector"], abs=1e-12
    )
    assert expanded["trail_length"] == pytest.approx(
        canonical["trail_length"], abs=1e-12
    )
    assert expanded["diag_steps"] == pytest.approx(
        canonical["diag_steps"], abs=1e-12
    )
    assert expanded["radii"] == pytest.approx(canonical["radii"], abs=1e-12)


@pytest.mark.parametrize("expanded_extent", ((840.0, 280.0), (420.0, 560.0)))
def test_swirl_orbit_uses_content_space_geometry_across_viewports(
    expanded_extent,
) -> None:
    """Swirl tangent/radial geometry must not change with domain aspect."""

    kwargs = {
        "stream_direction": "none",
        "drift_direction": "swirl_cw",
        "diag_key": "drift_step_mean",
        "start": (0.6, 0.6),
    }
    canonical = _run_viewport_transient_motion((420.0, 280.0), **kwargs)
    expanded = _run_viewport_transient_motion(expanded_extent, **kwargs)

    assert canonical["delivery_count"] == expanded["delivery_count"] == 1
    assert expanded["positions"] == pytest.approx(canonical["positions"], abs=1e-12)
    assert expanded["path"] == pytest.approx(canonical["path"], abs=1e-12)
    assert expanded["trail_vector"] == pytest.approx(
        canonical["trail_vector"], abs=1e-12
    )
    assert expanded["diag_steps"] == pytest.approx(
        canonical["diag_steps"], abs=1e-12
    )
    assert expanded["radii"] == pytest.approx(canonical["radii"], abs=1e-12)


@pytest.mark.parametrize("expanded_extent", ((840.0, 280.0), (420.0, 560.0)))
def test_swirl_spawn_radius_is_content_relative(expanded_extent) -> None:
    def _spawn(extent):
        random.seed(20260831)
        sim = BubbleSimulation()
        sim._apply_viewport_domain(extent)
        sim._spawn_bubble(False, "none", 0.6, "swirl_cw")
        bubble = sim._bubbles[0]
        return (
            bubble.x / sim._domain_w - 0.5,
            bubble.y / sim._domain_h - 0.5,
        )

    canonical_offset = _spawn((420.0, 280.0))
    expanded_offset = _spawn(expanded_extent)

    assert math.hypot(*canonical_offset) > 0.0
    assert expanded_offset == pytest.approx(canonical_offset, abs=1e-12)


@pytest.mark.parametrize("drift_direction", ("diagonal", "random"))
@pytest.mark.parametrize("expanded_extent", ((840.0, 280.0), (420.0, 560.0)))
def test_group_drift_inherits_content_space_projection(
    drift_direction,
    expanded_extent,
) -> None:
    kwargs = {
        "stream_direction": "none",
        "drift_direction": drift_direction,
        "diag_key": "drift_step_mean",
        "group_drift": True,
    }
    canonical = _run_viewport_transient_motion((420.0, 280.0), **kwargs)
    expanded = _run_viewport_transient_motion(expanded_extent, **kwargs)

    assert canonical["delivery_count"] == expanded["delivery_count"] == 1
    assert expanded["positions"] == pytest.approx(canonical["positions"], abs=1e-12)
    assert expanded["path"] == pytest.approx(canonical["path"], abs=1e-12)
    assert expanded["trail_vector"] == pytest.approx(
        canonical["trail_vector"], abs=1e-12
    )
    assert expanded["diag_steps"] == pytest.approx(
        canonical["diag_steps"], abs=1e-12
    )
    assert expanded["radii"] == pytest.approx(canonical["radii"], abs=1e-12)


@pytest.mark.parametrize("stream_direction", ("up", "left", "top_right"))
@pytest.mark.parametrize("expanded_extent", ((840.0, 280.0), (420.0, 560.0)))
def test_directional_refill_entry_is_content_relative(
    stream_direction,
    expanded_extent,
) -> None:
    def _spawn(extent):
        random.seed(20260831)
        sim = BubbleSimulation()
        sim._apply_viewport_domain(extent)
        sim._spawn_bubble(False, stream_direction, 0.6, "none")
        bubble = sim._bubbles[0]
        return (bubble.x / sim._domain_w, bubble.y / sim._domain_h)

    canonical_position = _spawn((420.0, 280.0))
    expanded_position = _spawn(expanded_extent)

    assert expanded_position == pytest.approx(canonical_position, abs=1e-12)


@pytest.mark.parametrize("expanded_extent", ((840.0, 280.0), (420.0, 560.0)))
def test_refill_cluster_spread_is_content_relative(expanded_extent) -> None:
    def _record_spawn_positions(extent):
        random.seed(1)  # first refill chooses the authored cluster branch
        sim = BubbleSimulation()
        sim._apply_viewport_domain(extent)
        sim._time = 1.0
        recorded = []

        def _record(_is_big, x, y, *_args, **_kwargs):
            recorded.append((x / sim._domain_w, y / sim._domain_h))

        sim._spawn_bubble_at = _record  # type: ignore[method-assign]
        sim.tick(
            1.0 / 90.0,
            dict(_ZERO_ENERGY),
            {
                "_bubble_viewport_extent": extent,
                "bubble_big_count": 0,
                "bubble_small_count": 3,
                "bubble_stream_direction": "none",
                "bubble_drift_direction": "none",
                "bubble_drift_amount": 0.0,
                "bubble_bounce_big_pct": 0.0,
                "bubble_bounce_small_pct": 0.0,
            },
        )
        return recorded

    canonical_positions = _record_spawn_positions((420.0, 280.0))
    expanded_positions = _record_spawn_positions(expanded_extent)

    assert len(canonical_positions) == len(expanded_positions) == 3
    assert expanded_positions == pytest.approx(canonical_positions, abs=1e-12)


@pytest.mark.parametrize(
    ("axis", "expanded_extent"),
    (("x", (840.0, 280.0)), ("y", (420.0, 560.0))),
)
@pytest.mark.parametrize(
    ("normalized_position", "expected_exiting"),
    ((1.075, False), (1.125, True)),
)
def test_surface_exit_margin_is_content_relative(
    axis,
    expanded_extent,
    normalized_position,
    expected_exiting,
) -> None:
    def _exit_state(extent):
        sim = BubbleSimulation()
        sim._apply_viewport_domain(extent)
        x = normalized_position * sim._domain_w if axis == "x" else 0.5 * sim._domain_w
        y = normalized_position * sim._domain_h if axis == "y" else 0.5 * sim._domain_h
        bubble = BubbleState(
            x=x,
            y=y,
            radius=0.03,
            is_big=True,
            reaches_surface=True,
            max_age=999.0,
            alpha=1.0,
            trail_ready=True,
            trail_tail_x=0.5 * sim._domain_w,
            trail_tail_y=0.5 * sim._domain_h,
            trail_strength=1.0,
        )
        sim._bubbles = [bubble]
        sim.tick(
            1.0 / 90.0,
            dict(_ZERO_ENERGY),
            {
                "_bubble_viewport_extent": extent,
                "bubble_big_count": 0,
                "bubble_small_count": 0,
                "bubble_stream_direction": "none",
                "bubble_drift_direction": "none",
                "bubble_drift_amount": 0.0,
                "bubble_trail_strength": 1.0,
                "bubble_bounce_big_pct": 0.0,
                "bubble_bounce_small_pct": 0.0,
            },
        )
        return bubble.exiting

    assert _exit_state((420.0, 280.0)) is expected_exiting
    assert _exit_state(expanded_extent) is expected_exiting


@pytest.mark.parametrize(
    ("stream_direction", "expanded_extent"),
    (("right", (840.0, 280.0)), ("up", (420.0, 560.0))),
)
def test_pre_entry_prediction_distance_is_content_relative(
    stream_direction,
    expanded_extent,
) -> None:
    def _prediction(extent):
        sim = BubbleSimulation()
        sim._apply_viewport_domain(extent)
        x, y = sim._predict_stream_position(
            0.5 * sim._domain_w,
            0.5 * sim._domain_h,
            stream_direction,
        )
        return (x / sim._domain_w, y / sim._domain_h)

    canonical = _prediction((420.0, 280.0))
    expanded = _prediction(expanded_extent)

    assert expanded == pytest.approx(canonical, abs=1e-12)


def test_geometry_change_creates_no_extra_tick() -> None:
    random.seed(7)
    sim = BubbleSimulation()
    sim.tick(0.016, dict(_ENERGY), _settings(None))
    assert sim._diag_tick_count == 1
    # Changing the extent between steps is configuration, not an authored step.
    sim.tick(0.016, dict(_ENERGY), _settings((630.0, 280.0)))
    assert sim._diag_tick_count == 2
    sim.tick(0.016, dict(_ENERGY), _settings((420.0, 560.0)))
    assert sim._diag_tick_count == 3


def test_output_radius_preserves_historical_card_height_normalization() -> None:
    # Two fresh sims with one identical authored bubble: position belongs to the
    # expanded logical world and therefore normalizes, but radius remains a
    # fraction of the actual card height exactly as in the historical renderer.
    # This is the reactivity-critical distinction: dividing by domain_h made a
    # restored tall viewport physically under-react by that same factor.
    def _sim_with_bubble(domain_w, domain_h):
        sim = BubbleSimulation()
        sim._domain_w = domain_w
        sim._domain_h = domain_h
        sim._bubbles.append(
            BubbleState(x=0.6, y=0.5, radius=0.03, is_big=False, alpha=1.0)
        )
        return sim

    base_pos, _e, _t = _sim_with_bubble(1.0, 1.0).snapshot()
    tall_pos, _e2, _t2 = _sim_with_bubble(1.0, 2.0).snapshot()

    assert base_pos[0] == pytest.approx(0.6)
    assert base_pos[1] == pytest.approx(0.5)
    assert tall_pos[0] == pytest.approx(0.6)
    assert tall_pos[1] == pytest.approx(0.25)
    assert tall_pos[2] == pytest.approx(base_pos[2])


def test_active_profile_radius_projection_restores_the_exact_three_x_class_loss() -> None:
    extent_h = 772.8311688311688
    domain_h = extent_h / 280.0
    authored_radius = 0.03

    sim = BubbleSimulation()
    sim._domain_w = 1275.1714285714286 / 420.0
    sim._domain_h = domain_h
    sim._bubbles.append(
        BubbleState(
            x=0.5 * sim._domain_w,
            y=0.5 * domain_h,
            radius=authored_radius,
            is_big=True,
            alpha=1.0,
        )
    )

    positions, _extras, _trails = sim.snapshot(big_size_clamp=4.0)
    payload_radius = positions[2]
    authored_render_radius = sim.get_big_render_diagnostics()[
        "max_big_render_radius"
    ]
    removed_projection_radius = authored_render_radius / domain_h

    assert payload_radius == pytest.approx(authored_render_radius)
    assert payload_radius / removed_projection_radius == pytest.approx(domain_h)
    assert domain_h == pytest.approx(2.7601113172541742)


def test_card_relative_radius_stays_authored_in_expanded_collision_world() -> None:
    """R-69: viewport expansion must not multiply Bubble reaction radius."""

    radius = 0.03

    def _sim(extent: tuple[float, float]) -> BubbleSimulation:
        sim = BubbleSimulation()
        sim._apply_viewport_domain(extent)
        sim._bubbles = [
            BubbleState(
                x=0.50 * sim._domain_w,
                y=0.50 * sim._domain_h,
                radius=radius,
                is_big=True,
                alpha=1.0,
                pulse_energy=0.27,
                size_gate_energy=0.27,
            )
        ]
        return sim

    baseline = _sim((420.0, 280.0))
    tall = _sim((420.0, 772.8311688311688))
    wide = _sim((990.0, 280.0))

    # Radius is authored in canonical renderer-content units. Expanded CUSTOM
    # domains normalize positions/collision geometry, not the reaction radius.
    baseline_radius = baseline._effective_collision_radius(
        baseline._bubbles[0],
        big_bass_pulse=0.5,
        small_freq_pulse=0.5,
        big_contraction_bias=1.0,
        big_size_clamp=4.0,
    )
    for sim in (tall, wide):
        actual = sim._effective_collision_radius(
            sim._bubbles[0],
            big_bass_pulse=0.5,
            small_freq_pulse=0.5,
            big_contraction_bias=1.0,
            big_size_clamp=4.0,
        )
        assert actual == pytest.approx(baseline_radius)

    # The same normalized candidate has the same overlap decision at canonical,
    # tall and wide extents; there is no hidden radius*domain transfer.
    decisions = []
    for sim in (baseline, tall, wide):
        decisions.append(
            sim._overlaps_existing(
                0.555 * sim._domain_w,
                0.50 * sim._domain_h,
                radius,
                candidate_is_big=True,
            )
        )
    assert decisions == [True, True, True]

def test_overlap_retry_clamp_uses_actual_logical_domain() -> None:
    # The overlap-retry jitter clamp must bound to the actual logical world plus
    # the same off-world allowance, not the legacy unit box. Starting far past
    # the ceiling makes the clamp bind exactly, so baseline stays [-0.25,1.25]
    # while the off-world allowance preserves that same content fraction on an
    # expanded axis.
    def _forced_overlap_spawn(domain_w, domain_h):
        random.seed(3)
        sim = BubbleSimulation()
        sim._domain_w = domain_w
        sim._domain_h = domain_h
        calls = {"n": 0}

        def _overlaps_once(*_a, **_k):
            calls["n"] += 1
            return calls["n"] == 1  # overlap on the first check, then settle

        sim._overlaps_existing = _overlaps_once  # type: ignore[method-assign]
        sim._spawn_bubble_at(True, 2.0, 2.0, "up", 0.6, "random")
        return sim._bubbles[-1]

    baseline = _forced_overlap_spawn(1.0, 1.0)
    assert baseline.x == pytest.approx(1.25)
    assert baseline.y == pytest.approx(1.25)

    wide = _forced_overlap_spawn(1.5, 1.0)
    assert wide.x == pytest.approx(1.875)  # domain_w + 0.25 * domain_w
    assert wide.y == pytest.approx(1.25)  # y untouched

    tall = _forced_overlap_spawn(1.0, 1.5)
    assert tall.x == pytest.approx(1.25)  # x untouched
    assert tall.y == pytest.approx(1.875)  # domain_h + 0.25 * domain_h


_ZERO_ENERGY = {"bass": 0.0, "mid": 0.0, "high": 0.0, "overall": 0.0}


def _quiet_settings(extent):
    return {
        "_bubble_viewport_extent": extent,
        "bubble_big_count": 0,
        "bubble_small_count": 0,
    }


def test_specular_offsets_are_local_and_domain_independent() -> None:
    # spec_ox/spec_oy are dimensionless local bubble-space mutations (a fraction
    # of the bubble's own radius in the shader), NOT viewport positions. They
    # must pass through unchanged for every domain while radius remains
    # card-height-normalized,
    # so a wide/tall aspect cannot create a specular displacement stretch.
    def _snapshot_with_spec(domain_w, domain_h):
        sim = BubbleSimulation()
        sim._domain_w = domain_w
        sim._domain_h = domain_h
        sim._bubbles.append(
            BubbleState(
                x=0.6, y=0.5, radius=0.03, is_big=False, alpha=1.0,
                spec_ox=0.021, spec_oy=-0.017, spec_size_mut=1.1,
            )
        )
        return sim.snapshot()

    base_pos, base_extra, _bt = _snapshot_with_spec(1.0, 1.0)
    wide_pos, wide_extra, _wt = _snapshot_with_spec(1.5, 1.0)
    tall_pos, tall_extra, _tt = _snapshot_with_spec(1.0, 2.0)

    # Baseline payload exact.
    assert base_extra[2] == pytest.approx(0.021)
    assert base_extra[3] == pytest.approx(-0.017)
    # Offsets are identical across domains (not projected).
    assert wide_extra[2] == pytest.approx(base_extra[2])
    assert wide_extra[3] == pytest.approx(base_extra[3])
    assert tall_extra[2] == pytest.approx(base_extra[2])
    assert tall_extra[3] == pytest.approx(base_extra[3])
    # Position is projected; authored card-relative radius is not.
    assert tall_pos[1] == pytest.approx(base_pos[1] / 2.0)
    assert tall_pos[2] == pytest.approx(base_pos[2])


def test_shader_applies_specular_offset_relative_to_radius() -> None:
    # Source-level contract lock: the shader must keep spec_ox/spec_oy as a
    # fraction of the bubble radius (local space), never a viewport-absolute
    # offset. If this changes, the coordinate audit must be revisited.
    shader = (
        Path(__file__).resolve().parents[1]
        / "widgets" / "spotify_visualizer" / "shaders" / "bubble.frag"
    ).read_text(encoding="utf-8")
    assert "spec_ox * r" in shader
    assert "spec_oy * r" in shader


def test_contraction_retire_pops_only_non_surface_off_domain_bubbles() -> None:
    sim = BubbleSimulation()
    sim._domain_w = 1.0
    sim._domain_h = 1.0
    ns_outside = BubbleState(x=1.3, y=0.5, radius=0.02, reaches_surface=False, max_age=999.0, alpha=1.0)
    ns_inside = BubbleState(x=0.5, y=0.5, radius=0.02, reaches_surface=False, max_age=999.0, alpha=1.0)
    surf_outside = BubbleState(x=1.3, y=0.5, radius=0.02, reaches_surface=True, alpha=1.0)
    already_popping = BubbleState(
        x=1.4, y=0.5, radius=0.02, reaches_surface=False, popping=True, pop_timer=0.3, alpha=1.0
    )
    sim._bubbles.extend([ns_outside, ns_inside, surf_outside, already_popping])

    sim._retire_non_surface_bubbles_outside_domain()

    # Non-surface off-domain -> existing pop path, timer reset to start the fade.
    assert ns_outside.popping is True and ns_outside.pop_timer == 0.0
    # Interior non-surface is untouched.
    assert ns_inside.popping is False
    # Surface bubbles are reconciled by the head/tail exit path, not popped here.
    assert surf_outside.popping is False
    # An already-popping bubble is not restarted.
    assert already_popping.pop_timer == pytest.approx(0.3)


@pytest.mark.parametrize(
    ("axis", "domain_w", "domain_h"),
    (("x", 2.0, 1.0), ("y", 1.0, 2.0)),
)
@pytest.mark.parametrize(
    ("normalized_position", "expected_popping"),
    ((1.075, False), (1.125, True)),
)
def test_contraction_retire_margin_is_content_relative(
    axis,
    domain_w,
    domain_h,
    normalized_position,
    expected_popping,
) -> None:
    sim = BubbleSimulation()
    sim._domain_w = domain_w
    sim._domain_h = domain_h
    bubble = BubbleState(
        x=normalized_position * domain_w if axis == "x" else 0.5 * domain_w,
        y=normalized_position * domain_h if axis == "y" else 0.5 * domain_h,
        radius=0.02,
        reaches_surface=False,
        max_age=999.0,
        alpha=1.0,
    )
    sim._bubbles = [bubble]

    sim._retire_non_surface_bubbles_outside_domain()

    assert bubble.popping is expected_popping


def test_contraction_via_tick_routes_surface_and_non_surface_correctly() -> None:
    sim = BubbleSimulation()
    sim._domain_w = 1.5  # start wide
    sim._domain_h = 1.0
    ns_outside = BubbleState(x=1.4, y=0.5, radius=0.02, reaches_surface=False, max_age=999.0, alpha=1.0)
    interior = BubbleState(x=0.4, y=0.5, radius=0.02, reaches_surface=False, max_age=999.0, alpha=1.0)
    surf_outside = BubbleState(x=1.4, y=0.5, radius=0.02, reaches_surface=True, alpha=1.0)
    sim._bubbles.extend([ns_outside, interior, surf_outside])

    # Contract to baseline; no spawns/energy so the transition is isolated.
    sim.tick(0.016, dict(_ZERO_ENERGY), _quiet_settings((420.0, 280.0)))

    assert ns_outside.popping is True          # retired promptly via pop
    assert surf_outside.exiting is True         # surface uses exit/drain
    assert interior.popping is False            # interior untouched
    assert interior.exiting is False
    assert 0.0 <= interior.x <= 1.0             # not teleported or rescaled


def test_growth_or_stable_domain_never_retires_bubbles() -> None:
    sim = BubbleSimulation()
    sim._domain_w = 1.0
    sim._domain_h = 1.0
    # A bubble that would be off a *baseline* world but is inside the wider world.
    off_baseline = BubbleState(x=1.3, y=0.5, radius=0.02, reaches_surface=False, max_age=999.0, alpha=1.0)
    sim._bubbles.append(off_baseline)

    # Grow to wide: no contraction, so nothing is retired.
    sim.tick(0.016, dict(_ZERO_ENERGY), _quiet_settings((630.0, 280.0)))
    assert off_baseline.popping is False
    # Stable wide: still no contraction event.
    sim.tick(0.016, dict(_ZERO_ENERGY), _quiet_settings((630.0, 280.0)))
    assert off_baseline.popping is False


def test_contracted_population_replenishes_to_authored_targets() -> None:
    # Fill a wide world, then contract and let it settle. Off-domain bubbles
    # retire and spawns refill to the authored counts (never scaled by area).
    sim = _run((760.0, 280.0), ticks=1, seed=99)
    for _ in range(120):
        sim.tick(0.016, dict(_ENERGY), _settings((420.0, 280.0)))

    big = sum(1 for b in sim._bubbles if b.is_big and not b.exiting and not b.popping)
    small = sum(1 for b in sim._bubbles if not b.is_big and not b.exiting and not b.popping)
    # Replenished back to (near) the authored targets - not permanently depleted
    # by stranded off-domain bubbles, and never scaled up by viewport area.
    assert 5 <= big <= 6
    assert 18 <= small <= 20
    # No non-surface bubble is left stranded materially outside the shrunk world.
    assert all(
        not (b.x > 1.1 and not b.reaches_surface and not b.popping)
        for b in sim._bubbles
    )
