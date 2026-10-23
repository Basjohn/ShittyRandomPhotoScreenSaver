"""Unaccepted EB source candidates: hard gates only, never visual-acceptance claims.

Native/recorded passages and operator inspection remain mandatory. These tests can
run without Qt by importing the simulation through its normal test environment.
"""
from __future__ import annotations

import math
from dataclasses import replace

import pytest

from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput,
)
from tools.visualizer_replay.eb_simulation_support import (
    synthetic_controls, simulation_module, summary, trace,
)


def test_new_sizes_are_three_independent_controls_with_identity_stable_physical_radii():
    controls = ExtrudedBubbleControls(large_count=(4, 4), mid_count=(8, 8),
                                      large_size=1.0, small_size=1.0,
                                      collision_scope="off")
    sim = ExtrudedBubbleSimulation(441)
    sim.advance(MusicInput(0.0, False), controls)
    before = {b.ident: (b.large, b.radius) for b in sim._bubbles}
    assert {b.large for b in sim._bubbles} == {True, False}
    modified = replace(controls, large_size=1.75, small_size=0.65)
    snap = sim.advance(MusicInput(1/60, False), modified)
    after = {b.ident: (b.large, b.radius) for b in sim._bubbles}
    assert before.keys() == after.keys() and snap.count == len(before)
    for ident, (large, radius) in before.items():
        assert after[ident][1] == pytest.approx(radius * (1.75 if large else 0.65))
    # Reapplying identical Settings cannot compound the scaling on every tick.
    sim.advance(MusicInput(1/60, False), modified)
    assert all(sim._bubbles[i].radius == pytest.approx(after[b.ident][1])
               for i, b in enumerate(sim._bubbles))
    reset = replace(modified, large_size=1.0, small_size=1.0)
    sim.advance(MusicInput(1/60, False), reset)
    for b in sim._bubbles:
        assert b.radius == pytest.approx(before[b.ident][1])


@pytest.mark.parametrize("profile", ["gentle", "strong"])
@pytest.mark.parametrize("scenario", ["already_hot", "play_ramp"])
def test_engine_ramp_metadata_prevents_unearned_hot_start_or_warmup_swell(profile, scenario):
    mod = simulation_module()
    controls = synthetic_controls(mod, profile)
    result = summary(trace(mod, controls, scenario))
    for lane in ("big", "small"):
        assert result[lane]["peak_to_final"] <= 1.30, (profile, scenario, lane, result)


def test_real_non_ramp_music_can_still_drive_big_and_small_changes():
    controls = ExtrudedBubbleControls(large_count=(2, 2), mid_count=(3, 3),
        breathing=(0.15, 0.6), small_pulse=(0.15, 0.8),
        stream_speed=(0, 0), drift=(0, 0), sway=0, collision_scope="off")
    sim = ExtrudedBubbleSimulation(4)
    for _ in range(240):
        before = sim.advance(MusicInput(1/60, True, 1.0, (), (0.1, 0.1, 0.05)), controls)
    kinds = {b.ident: b.large for b in sim._bubbles}
    peaks = {True: 0., False: 0.}
    base = {True: [], False: []}
    for i in range(0, len(before.bubbles), 8):
        rec = before.bubbles[i:i+8]
        base[kinds[int(rec[6])]].append(rec[3])
    for _ in range(30):
        current = sim.advance(MusicInput(1/60, True, 1.0, (), (0.38, 0.8, 0.5)), controls)
        for i in range(0, len(current.bubbles), 8):
            rec = current.bubbles[i:i+8]
            peaks[kinds[int(rec[6])]] = max(peaks[kinds[int(rec[6])]], rec[3])
    assert all(peaks[kind] > max(base[kind]) * 1.2 for kind in (True, False))


def test_canonical_spec_includes_sizes_and_narrower_camera_as_mutable_settings():
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    spec = require_mode_settings("extruded_bubble")
    defaults = require_canonical_default("widgets.spotify_visualizer")
    for suffix, bucket in (("large_size", "bubbles"), ("small_size", "bubbles"),
                           ("bead_size", "bubbles"), ("camera_fov", "camera")):
        key = "extruded_bubble_" + suffix
        control = spec.control(key)
        assert control.bucket == bucket
        assert control.low < defaults[key] < control.high
    # Mutable canonical values are never pinned to today's authoring choices.
    # Control schema and admissibility are the contract, not the exact value.
    for suffix in ("large_size", "small_size", "bead_size", "camera_fov"):
        key = "extruded_bubble_" + suffix
        control = spec.control(key)
        assert control.admit(defaults[key], defaults[key]) == pytest.approx(defaults[key])


def test_camera_pan_translates_world_eye_and_does_not_change_orbit():
    from rendering.gl_programs.extruded_bubble_scene import physical_camera
    at_rest = physical_camera(0., 0., 16/9, fov_y_degrees=45.)
    translated = physical_camera(0., 0., 16/9, pan_x=.15, pan_y=-.1, fov_y_degrees=45.)
    assert translated[0] == at_rest[0] and translated[1] == at_rest[1]
    assert translated[2] != at_rest[2]
    assert translated[4] == at_rest[4]
    assert translated[4][8] == translated[4][9] == 0.0
    assert physical_camera(0., 0., 16/9, fov_y_degrees=62.)[3][1] > translated[3][1]
