"""Shockwave Grid: the onset-event ring (admission on a new onset, spacing, capacity, lifetime,
deterministic origins, retirement), the fit that frames the grid for any view, the real
capture seam turning transient-bus onsets into aged events, and the renderer through the
production render host on an offscreen context (no window): waves where events are, glow that
only adds light and allocates nothing at zero, the content fade, release, and dormancy."""
from __future__ import annotations

import dataclasses
import math
import random
import subprocess
import sys

import numpy as np
import pytest

from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_CAPACITY,
    SHOCKWAVE_DEPTH,
    SHOCKWAVE_FAR_LINE,
    SHOCKWAVE_LIFETIME,
    SHOCKWAVE_MAX_TILT,
    SHOCKWAVE_MAX_TURN,
    SHOCKWAVE_MIN_GAP,
    SHOCKWAVE_NEAR_LINE,
    SHOCKWAVE_VISIBLE,
    shockwave_camera,
    shockwave_fit,
    shockwave_height,
    shockwave_origin,
    shockwave_project,
)
from widgets.spotify_visualizer.shockwave_frame_runtime import ShockwaveGridFrameRuntime

pytestmark = pytest.mark.qt

W, H = 684, 418


def _record(runtime, now, onset=False, kind="kick", strength=1.0, playing=True):
    return runtime.record_onsets(onset=onset, kind=kind, strength=strength, now_ts=now, playing=playing)


def test_an_event_is_admitted_once_per_new_onset_spaced_bounded_and_aged():
    runtime = ShockwaveGridFrameRuntime()
    assert _record(runtime, 10.0) == ()
    events = _record(runtime, 10.01, onset=True)
    assert len(events) == 1 and events[0][0] == pytest.approx(0.0)
    assert len(_record(runtime, 10.02, onset=True)) == 1             # the same onset held: no new event
    _record(runtime, 10.03)
    assert len(_record(runtime, 10.03 + SHOCKWAVE_MIN_GAP / 2, onset=True)) == 1   # too soon after the last
    _record(runtime, 10.2)
    events = _record(runtime, 10.3, onset=True, kind="snare", strength=0.4)
    assert len(events) == 2 and events[0][0] == pytest.approx(0.29) and events[1][3] == pytest.approx(0.4)
    assert _record(runtime, 10.35, onset=False, playing=False) and len(_record(runtime, 10.4)) == 2
    _record(runtime, 10.5)
    assert len(_record(runtime, 10.6, onset=True, playing=False)) == 2   # paused: onsets are not admitted
    assert _record(runtime, 10.3 + SHOCKWAVE_LIFETIME + 0.01) == ()      # all expired
    now = 20.0
    for _ in range(SHOCKWAVE_CAPACITY + 5):
        _record(runtime, now, onset=True)
        _record(runtime, now + 0.01)
        now += SHOCKWAVE_MIN_GAP + 0.01
    events = _record(runtime, now)
    assert len(events) == SHOCKWAVE_CAPACITY
    assert [age for age, *_ in events] == sorted((age for age, *_ in events), reverse=True)   # oldest first
    # The clock going back (a new activation) starts afresh; a retired runtime authors nothing.
    assert _record(runtime, 1.0) == ()
    runtime.retire()
    assert _record(runtime, 2.0, onset=True) is None


def test_origins_are_deterministic_and_on_the_grid():
    for serial in range(200):
        for kind in ("kick", "snare", "vocal_swell", ""):
            x, z = shockwave_origin(serial, kind)
            assert (x, z) == shockwave_origin(serial, kind)
            assert -1.0 <= x <= 1.0 and -SHOCKWAVE_DEPTH < z < 0.0
    kicks = [shockwave_origin(serial, "kick") for serial in range(200)]
    others = [shockwave_origin(serial, "snare") for serial in range(200)]
    assert max(abs(x) for x, _ in kicks) < max(abs(x) for x, _ in others)   # kicks stay nearer the middle


def test_a_wave_is_a_travelling_crest_that_fades():
    events = [(0.5, 0.0, -1.0, 1.0)]
    speed, amplitude = 1.0, 0.2
    ring = [shockwave_height(0.5 * math.cos(a), -1.0 + 0.5 * math.sin(a), events, amplitude, speed)[0]
            for a in np.linspace(0.0, 2.0 * math.pi, 12)]
    assert max(ring) - min(ring) < 1e-9 and ring[0] > 0.5 * amplitude * math.exp(-0.5 / 1.1)   # a circle
    assert abs(shockwave_height(0.0, -1.0, events, amplitude, speed)[0]) < 0.05 * amplitude     # passed by
    late = shockwave_height(2.5, -1.0, [(2.5, 0.0, -1.0, 1.0)], amplitude, speed)[0]
    assert 0.0 < late < 0.2 * ring[0]                                                           # faded
    assert shockwave_height(0.3, -0.4, [], amplitude, speed) == (0.0, 0.0)


def test_the_fit_frames_the_visible_grid_for_any_view():
    rng = random.Random(3)
    for _ in range(300):
        tilt, turn = rng.uniform(0.05, SHOCKWAVE_MAX_TILT), rng.uniform(-SHOCKWAVE_MAX_TURN, SHOCKWAVE_MAX_TURN)
        half_width, ridge = rng.uniform(1.0, 5.0), rng.uniform(0.0, 0.6)
        scale, base = shockwave_fit(tilt, turn, half_width, ridge)
        camera = shockwave_camera(half_width)
        for x in (-SHOCKWAVE_VISIBLE * half_width, SHOCKWAVE_VISIBLE * half_width):
            for z in (0.0, -SHOCKWAVE_VISIBLE * SHOCKWAVE_DEPTH):
                assert math.hypot(x, z + 0.5 * SHOCKWAVE_DEPTH) < camera            # nothing reaches the camera
                y = base - shockwave_project((x, 0.0, z), tilt, turn, camera)[1] * scale
                assert SHOCKWAVE_FAR_LINE - 1e-9 <= y <= SHOCKWAVE_NEAR_LINE + 1e-9


def test_the_capture_turns_transient_onsets_into_aged_events():
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.instance() or QGuiApplication(sys.argv)
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="shockwave_grid")
    events = snapshot.logical.mode_state.events
    assert events and all(age > 0.0 for age, *_ in events)
    assert snapshot.logical.mode_state.mode_id == "shockwave_grid"
    assert "shockwave_grid_glow" in dict(snapshot.logical.mode_state.parameters)


@pytest.fixture
def target(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_qtquick_extruded_spectrum import _Target

    result = _Target()
    host = QuickVisualizerRenderHost()
    yield result, host
    host.release_resources()
    result.close()


def _snapshot(events=None, **parameters):
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="shockwave_grid")
    state = snapshot.logical.mode_state
    changes = {"parameters": {**dict(state.parameters), **parameters}}
    if events is not None:
        changes["events"] = tuple(events)
    state = dataclasses.replace(state, **changes)
    return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))


def test_waves_change_the_grid_and_the_glow_only_adds_light(target):
    capture, host = target
    calm = capture.render(host, _snapshot(events=(), shockwave_grid_glow=0.0))
    renderer = host._implementations["shockwave_grid"]
    assert not renderer._target._names["emission"]                    # Glow 0: no emission, no bloom
    wavy = capture.render(host, _snapshot(events=((0.6, 0.0, -1.0, 1.0),), shockwave_grid_glow=0.0))
    assert np.abs(wavy - calm)[..., :3].max(axis=2).astype(bool).sum() > 2000
    glowing = capture.render(host, _snapshot(events=((0.6, 0.0, -1.0, 1.0),), shockwave_grid_glow=1.0))
    assert renderer._target._names["emission"]
    drawn = wavy[..., 3] > 0
    assert (glowing[..., :3].sum(axis=2) >= wavy[..., :3].sum(axis=2) - 6)[drawn].all()   # glow never darkens
    assert glowing[..., :3].sum() > wavy[..., :3].sum()
    faded = dataclasses.replace(_snapshot(), presentation=dataclasses.replace(_snapshot().presentation,
                                                                                content_fade=0.0))
    assert capture.render(host, faded)[..., 3].max() == 0
    host.release_resources()
    assert not renderer.has_resources


def test_the_mode_borrows_spectrums_bars_and_stays_dormant_until_it_renders():
    from core.settings.visualizer_mode_registry import get_technical_profile_mode, get_visualizer_mode_descriptor

    descriptor = get_visualizer_mode_descriptor("shockwave_grid")
    assert get_technical_profile_mode("shockwave_grid") == "spectrum"
    assert descriptor.view_orbit_settings == ("shockwave_grid_turn", "shockwave_grid_tilt")
    code = ("import sys\n"
            "import core.settings.visualizer_mode_registry, rendering.quick.visualizer.implementation_registry\n"
            "import widgets.spotify_visualizer.logical_frame_capture\n"
            "print([m for m in sys.modules if 'shockwave' in m])\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True)
    assert result.stdout.strip() == "[]"
