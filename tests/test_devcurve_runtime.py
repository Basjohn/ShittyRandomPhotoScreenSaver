from __future__ import annotations

import math

from widgets.spotify_visualizer.devcurve_runtime import DevCurveRuntimeState, solve_devcurve_frame
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands


def _layer_defaults():
    return {
        "bass": {"enabled": True, "power": 1.0, "offset": 0.0},
        "vocals": {"enabled": True, "power": 1.0, "offset": 0.0},
        "mids": {"enabled": True, "power": 1.0, "offset": 0.0},
        "transients": {"enabled": True, "power": 1.0, "offset": 0.0},
    }


def _layer_shapes():
    return {
        "bass": [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]],
        "vocals": [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]],
        "mids": [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]],
        "transients": [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]],
    }


def test_devcurve_active_amplitude_exceeds_idle_amplitude():
    state = DevCurveRuntimeState()
    idle = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=1.0,
        playing=False,
        energy_bands=EnergyBands(bass=0.02, mid=0.02, high=0.02, overall=0.02),
        transient_bus=None,
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.0,
        idle_motion=0.2,
        idle_speed=0.6,
        smoothness=0.55,
        growth=3.0,
        layer_settings=_layer_defaults(),
    )
    active = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=1.5,
        playing=True,
        energy_bands=EnergyBands(bass=0.75, mid=0.62, high=0.55, overall=0.70),
        transient_bus=TransientEnergyBands(bass_transient=0.9, mid_transient=0.3, high_transient=0.2),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.0,
        idle_motion=0.2,
        idle_speed=0.6,
        smoothness=0.55,
        growth=3.0,
        layer_settings=_layer_defaults(),
    )
    assert active["active_amplitude"] > idle["active_amplitude"]


def test_devcurve_curves_are_finite_and_bounded():
    state = DevCurveRuntimeState()
    frame = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=2.0,
        playing=True,
        energy_bands=EnergyBands(bass=1.0, mid=1.0, high=1.0, overall=1.0),
        transient_bus=TransientEnergyBands(bass_transient=1.5, mid_transient=1.0, high_transient=1.0),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.5,
        idle_motion=0.25,
        idle_speed=0.9,
        smoothness=0.55,
        growth=3.0,
        layer_settings=_layer_defaults(),
    )
    curves = list(frame["layers"].values())
    for curve in curves:
        for v in curve:
            assert math.isfinite(v)
            assert 0.04 <= v <= 0.96


def test_devcurve_smoothness_guardrail_caps_local_step():
    state = DevCurveRuntimeState()
    frame = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=3.0,
        playing=True,
        energy_bands=EnergyBands(bass=0.95, mid=0.88, high=0.80, overall=0.91),
        transient_bus=TransientEnergyBands(bass_transient=1.2, mid_transient=0.7, high_transient=0.6),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.6,
        idle_motion=0.2,
        idle_speed=0.7,
        smoothness=0.55,
        growth=3.0,
        layer_settings=_layer_defaults(),
    )
    assert frame["smoothness_max_step"] <= 0.03


def test_devcurve_growth_preserves_top_headroom():
    state_low = DevCurveRuntimeState()
    low = solve_devcurve_frame(
        state_low,
        dt=0.016,
        now_ts=4.0,
        playing=True,
        energy_bands=EnergyBands(bass=1.05, mid=0.98, high=0.85, overall=1.0),
        transient_bus=TransientEnergyBands(bass_transient=1.4, mid_transient=0.9, high_transient=0.7),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.9,
        idle_motion=0.2,
        idle_speed=0.9,
        smoothness=0.65,
        growth=1.0,
        layer_settings=_layer_defaults(),
    )
    state_high = DevCurveRuntimeState()
    high = solve_devcurve_frame(
        state_high,
        dt=0.016,
        now_ts=4.0,
        playing=True,
        energy_bands=EnergyBands(bass=1.05, mid=0.98, high=0.85, overall=1.0),
        transient_bus=TransientEnergyBands(bass_transient=1.4, mid_transient=0.9, high_transient=0.7),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.9,
        idle_motion=0.2,
        idle_speed=0.9,
        smoothness=0.65,
        growth=5.0,
        layer_settings=_layer_defaults(),
    )
    low_max = max(max(curve) for curve in low["layers"].values())
    high_max = max(max(curve) for curve in high["layers"].values())
    assert high_max <= low_max


def test_devcurve_foreground_layer_follows_enabled_order():
    state = DevCurveRuntimeState()
    settings = _layer_defaults()
    settings["bass"]["order"] = 4
    settings["vocals"]["order"] = 1
    settings["mids"]["order"] = 2
    settings["transients"]["order"] = 3

    frame = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=5.0,
        playing=True,
        energy_bands=EnergyBands(bass=0.6, mid=0.6, high=0.6, overall=0.6),
        transient_bus=TransientEnergyBands(bass_transient=0.4, mid_transient=0.2, high_transient=0.1),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.0,
        idle_motion=0.2,
        idle_speed=0.6,
        smoothness=0.55,
        growth=3.0,
        layer_settings=settings,
    )
    assert frame["draw_order"] == ["vocals", "mids", "transients", "bass"]
    assert frame["foreground_layer"] == "bass"
    assert frame["foreground_layer_id"] == 0

    settings["bass"]["enabled"] = False
    frame2 = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=5.2,
        playing=True,
        energy_bands=EnergyBands(bass=0.6, mid=0.6, high=0.6, overall=0.6),
        transient_bus=TransientEnergyBands(bass_transient=0.4, mid_transient=0.2, high_transient=0.1),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.0,
        idle_motion=0.2,
        idle_speed=0.6,
        smoothness=0.55,
        growth=3.0,
        layer_settings=settings,
    )
    assert frame2["foreground_layer"] == "transients"
    assert frame2["foreground_layer_id"] == 3


def test_devcurve_foreground_layer_disables_when_all_layers_off():
    state = DevCurveRuntimeState()
    settings = _layer_defaults()
    for src in settings:
        settings[src]["enabled"] = False
    frame = solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=6.0,
        playing=True,
        energy_bands=EnergyBands(bass=0.6, mid=0.6, high=0.6, overall=0.6),
        transient_bus=TransientEnergyBands(bass_transient=0.4, mid_transient=0.2, high_transient=0.1),
        layer_shape_nodes=_layer_shapes(),
        base_level=0.58,
        motion_power=1.0,
        idle_motion=0.2,
        idle_speed=0.6,
        smoothness=0.55,
        growth=3.0,
        layer_settings=settings,
    )
    assert frame["foreground_layer"] == ""
    assert frame["foreground_layer_id"] == -1
