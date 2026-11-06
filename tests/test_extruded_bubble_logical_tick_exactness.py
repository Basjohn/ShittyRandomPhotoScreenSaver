"""Extruded Bubble's logical tick publishes exactly what its straightforward forms publish (6 Nov 2026 cut).

The production hot paths (contact discovery, cluster layout and motion, wake records, the snapshot, drift steering,
renderer-parameter freezing, controls resolution, wake float32 packing) were rewritten to hold the logical thread's
GIL for less time. EB is accepted, protected behaviour, so every rewrite must be byte-identical. These tests replay a
short clip through the production logical path twice, once with the straightforward forms
(``tests/_extruded_bubble_reference_forms.py``) patched in, and compare a digest of every published frame; focused
tests pin each helper against its reference with a negative control. Settings are the frozen test copy plus
test-owned overrides; no preset or default value is pinned.
"""
from __future__ import annotations

from array import array
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import math
import random
from unittest.mock import patch

import numpy as np
import pytest

from tests import _extruded_bubble_reference_forms as reference
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tools.visualizer_replay.driver import load_clips, replay_clip
from widgets.spotify_visualizer import extruded_bubble_drift as drift
from widgets.spotify_visualizer import extruded_bubble_frame_runtime as frame_runtime
from widgets.spotify_visualizer import extruded_bubble_simulation as sim
from widgets.spotify_visualizer import render_state
from widgets.spotify_visualizer.feature_frame import FeatureClip

# Test-owned workloads that exercise every rewritten path: dense populations, contacts (fuse, pop, bounce),
# three-member clusters, wakes, and both a swirl and a fixed-heading Drift Direction.
_CASES = {
    "scene_swirl": {"extruded_bubble_large_bubbles": (10, 14), "extruded_bubble_mid_bubbles": (30, 48),
                    "extruded_bubble_doublets": 0.4, "extruded_bubble_wake_trails": 0.5,
                    "extruded_bubble_collision_scope": "All", "extruded_bubble_large_size": 1.6,
                    "extruded_bubble_small_size": 1.6, "extruded_bubble_drift_direction": "Clockwise",
                    "extruded_bubble_emission_geometry": "SCENE"},
    "beam_swish": {"extruded_bubble_large_bubbles": (8, 12), "extruded_bubble_mid_bubbles": (24, 40),
                   "extruded_bubble_doublets": 0.3, "extruded_bubble_wake_trails": 0.3,
                   "extruded_bubble_collision_scope": "Big", "extruded_bubble_large_size": 1.8,
                   "extruded_bubble_drift_direction": "Swish (Across)", "extruded_bubble_emission_geometry": "BEAM"},
}


@pytest.fixture(scope="module")
def clip():
    """A synthetic feature fixture looped to ~11 s so populations fill, touch, fuse and pop."""
    base = load_clips()["representative_music_features"]
    span = base.frames[-1].timestamp_us - base.frames[0].timestamp_us + 11_111
    frames = tuple(replace(frame, timestamp_us=frame.timestamp_us + loop * span)
                   for loop in range(8) for frame in base.frames)
    return FeatureClip("eb_exactness_loop", frames)


def _published_digests(clip, case: str) -> list[str]:
    settings = {**frozen_visualizer_settings("extruded_bubble"), **_CASES[case]}
    series = replay_clip(clip, "extruded_bubble", settings=settings)["logical_series"]
    # repr is exact for floats and bytes: every published field of every frame, parameters included.
    return [hashlib.sha256(repr(frame).encode()).hexdigest() for frame in series]


def _reference_forms(stack: ExitStack, *, snapshot=reference.snapshot) -> None:
    S = sim.ExtrudedBubbleSimulation
    stack.enter_context(patch.object(S, "_collide", reference.collide))
    stack.enter_context(patch.object(S, "_place_cluster", reference.place_cluster))
    stack.enter_context(patch.object(S, "_advance_clusters", reference.advance_clusters))
    stack.enter_context(patch.object(S, "_wakes", reference.wakes))
    stack.enter_context(patch.object(S, "_snapshot", snapshot))
    stack.enter_context(patch.object(sim, "_drift_steer", reference.steer))
    stack.enter_context(patch.object(render_state.FrozenFieldsMemo, "freeze",
                                     lambda self, values: render_state.freeze_render_fields(values)))
    stack.enter_context(patch.object(frame_runtime.ExtrudedBubbleFrameRuntime, "controls_for",
                                     lambda self, parameters: frame_runtime.controls_from_parameters(parameters)))
    stack.enter_context(patch.object(render_state, "wake_record_bytes", lambda values: array("f", values).tobytes()))


def _rearranged_snapshot(self, direction, speed, controls, dt):
    """The reference snapshot with each swell written (r - R) / R instead of r / R - 1: equal on paper, a last-bit
    difference in floats."""
    state = reference.snapshot(self, direction, speed, controls, dt)
    records = list(state.bubbles)
    for i, b in enumerate(self._bubbles):
        records[8 * i + 5] = (b.visual_radius - b.radius) / b.radius
    return replace(state, bubbles=tuple(records))


@pytest.mark.parametrize("case", sorted(_CASES))
def test_every_published_frame_matches_the_straightforward_forms(clip, case):
    production = _published_digests(clip, case)
    with ExitStack() as stack:
        _reference_forms(stack)
        straightforward = _published_digests(clip, case)
    assert len(production) == len(straightforward) == len(clip.frames)
    first = next((i for i, (a, b) in enumerate(zip(production, straightforward)) if a != b), None)
    assert first is None, f"{case}: published frame {first} differs from the straightforward forms"


def test_negative_control_a_last_bit_change_is_seen(clip):
    """The digest sees a change no wider than one float rounding in one published field."""
    production = _published_digests(clip, "scene_swirl")
    with ExitStack() as stack:
        _reference_forms(stack, snapshot=_rearranged_snapshot)
        rearranged = _published_digests(clip, "scene_swirl")
    assert production != rearranged


# -- contact discovery ----------------------------------------------------------------------------------------------

class _Body:
    __slots__ = ("x", "y", "z", "current_radius", "ident")

    def __init__(self, ident, x, y, z):
        self.ident, self.x, self.y, self.z, self.current_radius = ident, x, y, z, 0.0


def _populations():
    rng = random.Random(0xEB)
    cases = []
    for trial in range(60):
        cell = rng.choice((0.1, 0.37, 1.0, 2.5))
        span = cell * rng.choice((2.0, 4.0, 9.0))
        bodies = []
        for ident in range(1, rng.randint(2, 120)):
            if rng.random() < 0.15:       # on a cell boundary, including negative ones
                point = [cell * rng.randint(-4, 4) for _ in range(3)]
            else:
                point = [rng.uniform(-span, span) for _ in range(3)]
            bodies.append(_Body(ident, *point))
        cases.append((bodies, cell))
    return cases


def _pairs(candidates):
    return [(a.ident, b.ident) for a, b in candidates]


def test_contact_candidates_are_the_dictionary_grid_scan_in_its_order():
    for bodies, cell in _populations():
        assert _pairs(sim._contact_candidates(bodies, cell)) == _pairs(reference.contact_candidates(bodies, cell))


def test_negative_control_the_populations_exercise_scan_order():
    """A scan visiting depth neighbours before columns finds the same pairs in another order on these populations,
    so the equality above checks order, not just the pair set."""
    def depth_first(members, cell):
        grid = {}
        for b in members:
            grid.setdefault((math.floor(b.x / cell), math.floor(b.y / cell), math.floor(b.z / cell)), []).append(b)
        out = []
        for (cx, cy, cz), bucket in grid.items():
            near = [b for dz in (-1, 0, 1) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    for b in grid.get((cx + dx, cy + dy, cz + dz), ())]
            out.extend((a, b) for a in bucket for b in near if b.ident > a.ident)
        return out

    differs = 0
    for bodies, cell in _populations():
        expected, other = _pairs(reference.contact_candidates(bodies, cell)), _pairs(depth_first(bodies, cell))
        assert sorted(expected) == sorted(other)
        differs += expected != other
    assert differs


# -- cluster layout ---------------------------------------------------------------------------------------------------

def _cluster_cases():
    rng = random.Random(0x5EB)
    for trial in range(200):
        count = rng.choice((2, 3))
        members = [sim._Bubble(ident, True, rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-3, 3),
                               rng.uniform(0.02, 0.4), 0.0, current_radius=rng.uniform(0.02, 0.5),
                               visual_radius=rng.choice((0.0, rng.uniform(0.02, 0.5))))
                   for ident in range(10, 10 + count)]
        ids = [m.ident for m in members]

        def axis():
            w = [rng.uniform(-1, 1) for _ in range(3)]
            norm = math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2])
            return (w[0] / norm, w[1] / norm, w[2] / norm)
        edges = [(ids[0], ids[1], axis(), rng.uniform(0.6, 1.1))]
        if count == 3:
            # a chain from either end, or a branch from the first member; listed in any order
            pick = rng.choice(((ids[1], ids[2]), (ids[2], ids[1]), (ids[0], ids[2]), (ids[2], ids[0])))
            edges.append((*pick, axis(), rng.uniform(0.6, 1.1)))
            rng.shuffle(edges)
        cluster = sim._Cluster(ids[0], rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(-2, 2), ids, edges)
        yield cluster, members


def _laid_out(place, cluster, members):
    copies = [replace(m) for m in members]
    place(None, cluster, copies)
    return [(m.x, m.y, m.z, m.offset) for m in copies]


def test_cluster_layout_is_the_generator_form_exactly():
    for cluster, members in _cluster_cases():
        rng_order = members if cluster.ident % 2 else list(reversed(members))
        assert (_laid_out(sim.ExtrudedBubbleSimulation._place_cluster, cluster, rng_order)
                == _laid_out(reference.place_cluster, cluster, rng_order))


def test_negative_control_layout_comparison_sees_a_reordered_centre():
    """The centre as a sum of each member's weighted share (equal on paper) lays some clusters out differently, so the
    equality above checks float bits, not just geometry."""
    def shares(self, cluster, members):
        by_id = {m.ident: m for m in members}
        positions = {members[0].ident: (0.0, 0.0, 0.0)}
        for _ in range(sim.CLUSTER_MAX - 1):
            for left, right, axis, ratio in cluster.edges:
                if left in by_id and right in by_id:
                    length = ratio * (sim._shown_radius(by_id[left]) + sim._shown_radius(by_id[right]))
                    if left in positions and right not in positions:
                        positions[right] = tuple(p + a * length for p, a in zip(positions[left], axis))
                    elif right in positions and left not in positions:
                        positions[left] = tuple(p - a * length for p, a in zip(positions[right], axis))
        weight = sum(m.radius ** 3 for m in members)
        center = tuple(sum(positions[m.ident][i] * (m.radius ** 3 / weight) for m in members) for i in range(3))
        for m in members:
            m.offset = tuple(positions[m.ident][i] - center[i] for i in range(3))
            m.x, m.y, m.z = (c + d for c, d in zip((cluster.x, cluster.y, cluster.z), m.offset))

    differs = sum(_laid_out(shares, cluster, members) != _laid_out(reference.place_cluster, cluster, members)
                  for cluster, members in _cluster_cases())
    assert differs


# -- drift steering ---------------------------------------------------------------------------------------------------

def test_steer_is_the_closure_form_for_every_direction_scalar_and_batched():
    rng = random.Random(7)
    direction, across, depth = (0.0, 0.6, 0.8), (1.0, 0.0, 0.0), (0.0, 0.8, -0.6)
    origin = (0.1, -0.2, 0.3)
    for kind in (*drift.DRIFT_DIRECTIONS, "unknown"):
        for _ in range(50):
            position = tuple(rng.uniform(-3, 3) for _ in range(3))
            on_axis = tuple(o + d * rng.uniform(-1, 1) for o, d in zip(origin, direction))   # the near-axis branch
            for point in (position, on_axis):
                args = (kind, point, rng.uniform(0, math.tau), rng.uniform(0, 50), direction, across, depth, origin,
                        rng.uniform(-2, 2))
                assert drift.steer(*args) == reference.steer(*args)
        points = np.array([[rng.uniform(-3, 3) for _ in range(64)] for _ in range(3)])
        points[:, :4] = np.array(origin)[:, None]
        args = (kind, points, np.linspace(0, math.tau, 64), 3.7, direction, across, depth, origin, 0.9)
        for got, want in zip(drift.steer(*args, ops=np), reference.steer(*args, ops=np)):
            assert np.array_equal(np.broadcast_to(got, (64,)), np.broadcast_to(want, (64,)))


# -- free-motion phase terms ------------------------------------------------------------------------------------------

def test_phase_terms_give_the_inline_sines_exactly():
    rng = random.Random(11)
    for _ in range(2000):
        phase, t = rng.uniform(0.0, math.tau), rng.uniform(0.0, 5000.0)
        _phase, rate, sway_offset, wander_offset, deep_offset = sim._phase_terms(phase)
        assert math.sin(t * rate + sway_offset) == math.sin(t * (1.1 + 0.5 * math.sin(phase)) + 3.0 * phase)
        assert math.sin(t * .83 + wander_offset) == math.sin(t * .83 + 2.1 * phase)
        assert math.sin(t * .29 + deep_offset) == math.sin(t * .29 + 1.7 * phase)


# -- renderer parameters ----------------------------------------------------------------------------------------------

def _same_freeze(got, values):
    want = render_state.freeze_render_fields(values)
    assert repr(got) == repr(want)          # exact: types, float bits and order
    assert got == want


def test_frozen_fields_memo_equals_freezing_afresh_through_edits():
    memo = render_state.FrozenFieldsMemo()
    palette = [0.5, 0.25]
    values = {"b_gain": 1.0, "a_mode": "Sunlit", "c_range": (0.2, 0.8), "d_list": palette, "e_flag": True,
              "f_count": 3, "g_zero": 0.0, "h_nested": render_state.freeze_render_fields({"x": 1.0}), "i_none": None}
    first = memo.freeze(values)
    _same_freeze(first, values)
    again = memo.freeze(dict(values, c_range=(0.2, 0.8)))      # fresh but equal objects
    _same_freeze(again, values)
    for edit in ({"b_gain": 1.25}, {"g_zero": -0.0}, {"f_count": 3.0}, {"e_flag": 1}, {"c_range": (0.2, 0.9)},
                 {"c_range": (0.2, 0.8, 1.0)}, {"a_mode": "Deep"}, {"h_nested": render_state.freeze_render_fields({"x": 2.0})},
                 {"i_none": 0}):
        values = dict(values, **edit)
        _same_freeze(memo.freeze(values), values)
    palette[0] = 0.75                                     # the same list object, mutated in place
    _same_freeze(memo.freeze(values), values)
    reordered = dict(reversed(list(values.items())))
    _same_freeze(memo.freeze(reordered), reordered)


def test_frozen_fields_memo_returns_the_same_fields_when_nothing_changed():
    memo = render_state.FrozenFieldsMemo()
    values = {"gain": 1.0, "range": (0.1, 0.2), "mode": "x"}
    first = memo.freeze(values)
    assert memo.freeze({"gain": 1.0, "range": (0.1, 0.2), "mode": "x"}) is first
    assert memo.freeze({"gain": 1.5, "range": (0.1, 0.2), "mode": "x"}) is not first


def test_frozen_fields_memo_refuses_what_freezing_refuses_and_starts_over():
    memo = render_state.FrozenFieldsMemo()
    values = {"a": 1.0, "b": 2.0}
    memo.freeze(values)
    with pytest.raises(ValueError):
        memo.freeze({"a": 3.0, "b": math.nan})
    _same_freeze(memo.freeze(values), values)           # not left holding "a": 3.0
    with pytest.raises(ValueError):
        memo.freeze({" ": 1.0})


def test_negative_control_strict_equality_tells_apart_what_freezing_does():
    strict = render_state.strictly_equal_render_value
    palette = [1.0]
    assert not strict(palette, palette)                   # mutable: never reused, even by identity
    assert not strict(0.0, -0.0) and not strict(1, 1.0) and not strict(True, 1) and not strict(math.nan, math.nan)
    assert not strict((0.0,), (-0.0,)) and strict((1.0, "a", (2, None)), (1.0, "a", (2, None)))
    assert repr(render_state.freeze_render_value(0.0)) != repr(render_state.freeze_render_value(-0.0))


# -- controls ---------------------------------------------------------------------------------------------------------

def _parameters(**edits):
    values = {**frozen_visualizer_settings("extruded_bubble"), **_CASES["scene_swirl"], **edits}
    return {key: tuple(value) if isinstance(value, list) else value for key, value in values.items()}


def test_controls_are_resolved_again_only_when_a_value_they_read_changes():
    runtime = frame_runtime.ExtrudedBubbleFrameRuntime()
    calls = []
    original = frame_runtime.controls_from_parameters

    def counted(parameters):
        calls.append(1)
        return original(parameters)

    with patch.object(frame_runtime, "controls_from_parameters", counted):
        first = runtime.controls_for(_parameters())
        assert first == original(_parameters()) and len(calls) == 1
        assert runtime.controls_for(_parameters()) is first and len(calls) == 1    # fresh mapping, same values
        assert runtime.controls_for(_parameters(unrelated_presentation_key=1.0)) is first
        edited = runtime.controls_for(_parameters(extruded_bubble_sway=0.9))
        assert len(calls) == 2 and edited == original(_parameters(extruded_bubble_sway=0.9)) and edited != first
        runtime.controls_for(_parameters(extruded_bubble_stream_direction=(0.0, 0.0)))
        count = len(calls)
        runtime.controls_for(_parameters(extruded_bubble_stream_direction=(-0.0, 0.0)))
        assert len(calls) == count + 1                    # a signed zero is a change
        missing = _parameters()
        missing.pop("extruded_bubble_large_size")         # read with a default: absence is a change too
        assert runtime.controls_for(missing) == original(missing)


# -- wake packing -----------------------------------------------------------------------------------------------------

def test_wake_bytes_are_the_float32_array_bytes():
    rng = random.Random(3)
    values = tuple(rng.uniform(-1e4, 1e4) for _ in range(5000)) + (0, 7, -0.0, 1e-50, 3.4e38)
    assert render_state.wake_record_bytes(values) == array("f", values).tobytes()
    assert render_state.wake_record_bytes(()) == b""
    beyond = (1.0, 1e300, -1e300, math.inf, math.nan)       # out of float32 range: array's inf, as before
    assert render_state.wake_record_bytes(beyond) == array("f", beyond).tobytes()
