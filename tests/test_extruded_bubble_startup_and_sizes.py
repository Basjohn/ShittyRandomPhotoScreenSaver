"""Pure logical gates. They are not a visual acceptance of Extruded Bubble."""
from __future__ import annotations

import pytest
from tools.visualizer_replay import eb_simulation_support as probe


def test_large_startup_avoids_false_song_start_on_both_join_and_engine_play_ramp():
    mod = probe.simulation_module()
    for profile in ("gentle", "strong"):
        controls = probe.synthetic_controls(mod, profile)
        for scenario in ("already_hot", "play_ramp", "play_ramp_untagged"):
            result = probe.summary(probe.trace(mod, controls, scenario))["big"]
            assert result["peak_to_final"] < 1.30, (profile, scenario, result)


def test_startup_recovery_does_not_erase_a_real_post_idle_musical_step():
    mod = probe.simulation_module()
    controls = probe.synthetic_controls(mod, "strong")
    step = probe.summary(probe.trace(mod, controls, "quiet_then_hot"))["big"]
    ramp = probe.summary(probe.trace(mod, controls, "play_ramp"))["big"]
    # Distinct from the 1-second artificial ramp reaching the same held level: the
    # real step swells well past where it settles; the ramp does not overshoot.
    assert step["peak_to_final"] > 1.5, step
    assert step["peak"] > 1.5 * ramp["peak"], (step, ramp)


def test_live_independent_population_size_edit_preserves_existing_shell_ids():
    mod = probe.simulation_module()
    base = mod.ExtrudedBubbleControls(
        large_count=(3, 3), mid_count=(4, 4), collision_scope="off", stream_speed=(0., 0.),
        drift=(0., 0.), sway=0.)
    sim = mod.ExtrudedBubbleSimulation(137)
    for _ in range(25):
        sim.advance(mod.MusicInput(1 / 60, True, 0., (), (0., 0., 0.)), base)
    before = {b.ident: (b.radius, b.large) for b in sim._bubbles}
    changed = mod.ExtrudedBubbleControls(
        large_count=(3, 3), mid_count=(4, 4), collision_scope="off", stream_speed=(0., 0.),
        drift=(0., 0.), sway=0., large_size=1.6, small_size=0.7)
    snap = sim.advance(mod.MusicInput(1 / 60, True, 0., (), (0., 0., 0.)), changed)
    assert snap.count == len(before) == 7
    assert {b.ident for b in sim._bubbles} == set(before)
    for b in sim._bubbles:
        nominal, large = before[b.ident]
        assert b.large == large
        assert b.radius == pytest.approx(nominal * (1.6 if large else 0.7))
    # No cumulative scaling on the next logical tick.
    sim.advance(mod.MusicInput(1 / 60, True, 0., (), (0., 0., 0.)), changed)
    for b in sim._bubbles:
        nominal, large = before[b.ident]
        assert b.radius == pytest.approx(nominal * (1.6 if large else 0.7))


def test_narrower_camera_is_authorable_and_reduces_outer_card_angular_stretch():
    probe.simulation_module()  # permit Qt-free import of the pure scene mapper
    from rendering.gl_programs import extruded_bubble_scene as scene
    assert scene.FOV_Y_DEGREES == 45.0
    wide_angle = __import__('math').atan(0.7 * 16 / 9 * __import__('math').tan(__import__('math').radians(62) / 2))
    narrow_angle = __import__('math').atan(0.7 * 16 / 9 * __import__('math').tan(__import__('math').radians(45) / 2))
    assert 0 < narrow_angle < wide_angle
    plain = scene.physical_camera(0., 0., 16 / 9, fov_y_degrees=45)
    panned = scene.physical_camera(0., 0., 16 / 9, pan_x=0.2, pan_y=0.1,
                                   fov_y_degrees=45)
    assert panned[0] == plain[0] and panned[1] == plain[1]  # no second orbit
    assert panned[2] != plain[2]  # translated eye
    assert panned[4][8] == panned[4][9] == 0.0  # centred lens
    wide = scene.physical_camera(0., 0., 16 / 9, fov_y_degrees=62)
    assert plain[3][1] < wide[3][1]
