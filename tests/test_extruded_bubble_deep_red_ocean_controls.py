"""The deep red ocean controls (Lit Glass, Stream Lanes, Ember Band, Wake Tint, Hero Shell): each reaches the native
pixels when raised and is dormant at 0. Inputs are test-owned (a short simulation run on synthetic music); no preset
values and no pixel goldens. HEAD pixel identity of the accepted presets is recorded evidence
(Extruded_Bubble/Investigation.md section 73), not a golden here."""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from rendering.gl_programs import extruded_bubble_scene as scene
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput, gather_toward_stream_axis,
)

PATH = (-1.0, 0.375, 0.15, 1.0, -0.975, -0.15)


def _axis_and_direction(path=PATH):
    from core.constants.extruded_bubble_world import WORLD_HALF
    from core.settings.visualizer_paths import direction_of, world_point
    source, end = np.asarray(world_point(path[:3], WORLD_HALF)), np.asarray(world_point(path[3:], WORLD_HALF))
    return (source + end) / 2, np.asarray(direction_of(path))


def _perpendicular(point, axis, direction):
    rel = np.asarray(point) - axis
    return np.linalg.norm(rel - direction * rel.dot(direction))


def test_stream_lanes_draw_births_toward_the_stream_axis_keeping_their_place_along_it():
    axis, direction = _axis_and_direction()
    point = axis + np.asarray((3.0, 5.0, -7.0))
    for amount in (0.25, 0.5, 1.0):
        gathered = np.asarray(gather_toward_stream_axis(tuple(point), tuple(direction), PATH, amount))
        assert (gathered - axis).dot(direction) == pytest.approx((point - axis).dot(direction))
        assert _perpendicular(gathered, axis, direction) < _perpendicular(point, axis, direction)
    assert gather_toward_stream_axis(tuple(point), tuple(direction), PATH, 0.0) == pytest.approx(tuple(point))


def _run(controls, seconds=6.0, seed=73):
    sim = ExtrudedBubbleSimulation(seed)
    snapshot = None
    for i in range(int(seconds * 60)):
        loud = 0.55 + 0.35 * math.sin(i / 37.0)
        onsets = (("kick", 0.9),) if i % 30 == 0 else ()
        snapshot = sim.advance(MusicInput(1 / 60, True, loud, onsets, (loud, loud * 0.6, loud * 0.3)), controls)
    return snapshot


def test_stream_lanes_zero_leaves_the_population_exactly_as_it_was_and_one_gathers_it():
    plain = ExtrudedBubbleControls(emission_geometry="SCENE", stream_path=PATH, large_count=(8, 8),
                                   mid_count=(30, 30), collision_scope="off")
    assert _run(plain) == _run(dataclasses.replace(plain, stream_lanes=0.0))
    axis, direction = _axis_and_direction()

    def spread(snapshot):
        rows = np.asarray(snapshot.bubbles).reshape(-1, 8)
        return np.median([_perpendicular(row[:3], axis, direction) for row in rows if row[4] > 0.5])
    assert spread(_run(dataclasses.replace(plain, stream_lanes=1.0))) < 0.8 * spread(_run(plain))


def test_hero_shell_sits_where_authored_in_the_frame_in_front_of_the_focus():
    view_to_world, world_to_view, eye, tan, _projection = scene.physical_camera(0.1, 0.05, 16 / 9)
    state = type("State", (), {"motion_phase": 0.0, "sustain": 0.5})()
    knobs = {"hero_shell": 0.5, "hero_at": (-0.7, -0.5), "focus": scene.focal_depth(0.6)}
    row = scene.hero_shell_instance(knobs, state, view_to_world, eye, tan)
    assert row.shape == (1, scene.SHELL_FLOATS)
    rel = row[0, :3] - np.asarray(eye)
    axes = np.asarray(view_to_world).reshape(3, 3)              # rows: right, up, back
    x, y, z = axes @ rel
    assert -z < knobs["focus"]                                  # nearer than focus: the near layer defocuses it
    assert (x / -z / tan[0], y / -z / tan[1]) == pytest.approx((-0.7, -0.5), abs=0.04)
    assert row[0, 5] == 0.0 and row[0, 6] == 1.0                # an ordinary, fully present shell
    bigger = scene.hero_shell_instance({**knobs, "hero_shell": 1.0}, state, view_to_world, eye, tan)
    assert bigger[0, 3] == pytest.approx(2 * row[0, 3])


@pytest.fixture
def target(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_qtquick_extruded_spectrum import _Target

    capture, host = _Target(), QuickVisualizerRenderHost()
    try:
        yield capture, host
    finally:
        assert capture.capture.context.makeCurrent(capture.capture.surface)
        host.release_resources()
        capture.close()


def _live(**parameters):
    """The preview snapshot carrying a real simulated population (bubbles, wakes, chains) for these Settings."""
    from tests.test_extruded_bubble_renderer import _snapshot
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters
    from widgets.spotify_visualizer.render_state import wake_record_bytes

    base = {"extruded_bubble_emission_geometry": "SCENE", "extruded_bubble_large_bubbles": [8, 8],
            "extruded_bubble_mid_bubbles": [30, 30], "extruded_bubble_bead_chains": [3, 3],
            "extruded_bubble_wake_trails": 1.0, "extruded_bubble_dust": 1.0,
            "extruded_bubble_stream_direction": list(PATH), **parameters}
    snapshot = _snapshot(**base)
    sim = _run(controls_from_parameters(snapshot.logical.mode_state.parameters))
    state = dataclasses.replace(
        snapshot.logical.mode_state, bubbles=sim.bubbles, clusters=sim.clusters, level=sim.level, flash=sim.flash,
        sustain=sim.sustain, emission=sim.emission, stream=sim.stream, travel=sim.travel, rays=sim.rays,
        motion_phase=sim.motion_phase, wakes=wake_record_bytes(sim.wakes), chain_activity=sim.chain_activity,
        chain_drive=sim.chain_drive)
    return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))


def _same(a, b):
    """The same picture within EB's own run-to-run noise (weighted transparency sums thousands of overlapping
    micro-glass fragments in half float, in whatever order the GPU rasterises them): a level or two on a few pixels."""
    d = np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))
    return d.max() <= 2.0 and (d > 0.0).mean() < 1e-4


@pytest.mark.qt
def test_each_control_reaches_the_pixels_and_is_dormant_where_it_has_nothing_to_act_on(target):
    capture, host = target

    def render(**parameters):
        snapshot = _live(**parameters)
        capture.render(host, snapshot)                          # a changed setting settles in one frame
        return capture.render(host, snapshot).astype(np.float64)

    base = render()
    for _ in range(2):                                          # warm: the first frames compile
        base = render()
    assert _same(render(), base)                       # the same inputs draw the same pixels
    for key, value in (("lit_glass", 1.0), ("stream_lanes", 1.0), ("ember_band", 1.0), ("wake_tint", 1.0),
                       ("hero_shell", 0.6)):
        changed = render(**{f"extruded_bubble_{key}": value})
        assert np.abs(changed - base).mean() > 0.05, key
    # Lit Glass only adds light to the glass: the frame brightens, nothing is darkened beyond noise.
    lit = render(extruded_bubble_lit_glass=1.0)
    assert (lit - base)[..., :3].mean() > 0.1 and np.percentile(lit - base, 0.5) > -2.0
    # Each control acts only on its own subject: none where that subject is absent, and Hero position nothing at 0.
    assert _same(render(extruded_bubble_dust=0.0, extruded_bubble_ember_band=1.0),
                          render(extruded_bubble_dust=0.0))
    assert _same(render(extruded_bubble_wake_trails=0.0, extruded_bubble_wake_tint=1.0),
                          render(extruded_bubble_wake_trails=0.0))
    assert _same(render(extruded_bubble_hero_across=0.4, extruded_bubble_hero_height=0.3), base)


@pytest.mark.qt
def test_ember_band_darkens_the_water_away_from_the_stream_axis(target):
    """The dust burns in a band along the stream's axis: where the band is absent the embers go, so the frame's
    dimmest dust regions get darker while the band keeps (or gains) its light."""
    capture, host = target
    plain = capture.render(host, _live(extruded_bubble_large_bubbles=[0, 0], extruded_bubble_mid_bubbles=[0, 0],
                                       extruded_bubble_bead_chains=[0, 0], extruded_bubble_wake_trails=0.0))
    plain = capture.render(host, _live(extruded_bubble_large_bubbles=[0, 0], extruded_bubble_mid_bubbles=[0, 0],
                                       extruded_bubble_bead_chains=[0, 0], extruded_bubble_wake_trails=0.0))
    banded = capture.render(host, _live(extruded_bubble_large_bubbles=[0, 0], extruded_bubble_mid_bubbles=[0, 0],
                                        extruded_bubble_bead_chains=[0, 0], extruded_bubble_wake_trails=0.0,
                                        extruded_bubble_ember_band=1.0))
    change = banded[..., :3].astype(np.float64).mean(-1) - plain[..., :3].astype(np.float64).mean(-1)
    # Some regions lose their embers and some keep or gain them: a spatial mask, not a uniform dimming.
    assert np.percentile(change, 5) < -1.0 and np.percentile(change, 99) > -0.5
