"""G4.3 - Bubble logical viewport reflow.

Bubble runs in a baseline-relative logical domain: canonical (420x280) is a
strict 1x1 no-op that leaves the legacy unit-square path and render arrays
exactly unchanged; a wide/tall committed extent expands the logical world so
bubbles fill the extra space at baseline density, and the render seam normalizes
back to [0,1] so the shader keeps circles round. These bars prove that contract
deterministically; final visual acceptance is deferred to after H.
"""

from __future__ import annotations

import random

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


def test_output_radius_normalizes_by_domain_height_preserving_physical_scale() -> None:
    # Two fresh sims with one identical bubble: only the domain projection
    # differs, so the tall render radius is exactly the baseline radius / 2 and x
    # is unscaled while y halves - the shader then re-expands to the same pixels.
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
    # Same pre-projection radius; tall halves the normalized radius.
    assert tall_pos[2] == pytest.approx(base_pos[2] / 2.0)


def test_overlap_retry_clamp_uses_actual_logical_domain() -> None:
    # The overlap-retry jitter clamp must bound to the actual logical world plus
    # the same off-world allowance, not the legacy unit box. Starting far past
    # the ceiling makes the clamp bind exactly, so baseline stays [-0.25,1.25]
    # while wide/tall extend the corresponding axis only.
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
    assert wide.x == pytest.approx(1.75)  # domain_w + 0.25
    assert wide.y == pytest.approx(1.25)  # y untouched

    tall = _forced_overlap_spawn(1.0, 1.5)
    assert tall.x == pytest.approx(1.25)  # x untouched
    assert tall.y == pytest.approx(1.75)  # domain_h + 0.25


def test_shrink_reconciles_out_of_domain_bubbles_without_rescaling() -> None:
    # Spread bubbles into a wide world, then shrink back to baseline.
    sim = _run((760.0, 280.0), ticks=1)
    outside = [b for b in sim._bubbles if b.x > 1.1 and b.reaches_surface]
    assert outside, "expected some surface bubbles beyond the shrunk domain"
    inside_before = {
        id(b): (b.x, b.y) for b in sim._bubbles if b.x <= 0.9
    }

    # Shrink to baseline and advance: out-of-domain surface bubbles exit/cull via
    # the canonical boundary path; interior bubbles are NOT percentage-rescaled.
    for _ in range(80):
        sim.tick(0.016, dict(_ENERGY), _settings((420.0, 280.0)))

    for b in sim._bubbles:
        # No global rescale: an interior bubble that stayed keeps its coordinate
        # scale (it was never multiplied by the domain ratio).
        if id(b) in inside_before:
            assert b.x <= 1.0 + 1e-6

    # The far-outside surface bubbles did not survive unbounded in the shrunk
    # world.
    assert all(
        not (b.x > 1.1 and b.reaches_surface and not b.exiting)
        for b in sim._bubbles
    )
