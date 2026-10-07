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
    shockwave_strength,
)
from widgets.spotify_visualizer.shockwave_frame_runtime import ShockwaveGridFrameRuntime
from tests._visualizer_frozen_settings import frozen_visualizer_settings

pytestmark = pytest.mark.qt

W, H = 684, 418


class _Onsets:
    """Published onsets as the transient bus makes them (serial, timestamp, kind, strength)."""

    def __init__(self) -> None:
        self.published = []
        self.serial = 1000          # serials are process-wide: never assume they start at 1

    def onset(self, timestamp, kind="kick", strength=1.0):
        from widgets.spotify_visualizer.transient_bus import MusicalOnset

        self.serial += 1
        self.published.append(MusicalOnset(serial=self.serial, timestamp=timestamp, kind=kind, strength=strength,
                                           magnitude=strength, loudness=1.0, presence=1.0))

    def after(self, serial):
        return tuple(onset for onset in self.published if onset.serial > serial)


def _record(runtime, bus, now, playing=True):
    return runtime.record_onsets(onsets=bus.after(runtime.onset_serial), now_ts=now, playing=playing, passage_intensity=1.0)


def test_an_event_is_admitted_once_per_onset_spaced_bounded_and_aged():
    runtime, bus = ShockwaveGridFrameRuntime(), _Onsets()
    assert _record(runtime, bus, 10.0) == ()
    bus.onset(10.005)
    events = _record(runtime, bus, 10.01)
    assert len(events) == 1 and events[0][0] == pytest.approx(0.005)      # born when it happened
    assert len(_record(runtime, bus, 10.02)) == 1                          # taken once
    bus.onset(10.005 + SHOCKWAVE_MIN_GAP / 2)
    assert len(_record(runtime, bus, 10.08)) == 1                          # too soon after the last
    bus.onset(10.3, kind="snare", strength=0.4)
    events = _record(runtime, bus, 10.3)
    assert len(events) == 2 and events[0][0] == pytest.approx(0.295)
    assert events[1][3] == pytest.approx(shockwave_strength(0.4, 1.0, 1.0))   # from its magnitude
    bus.onset(10.6)
    assert len(_record(runtime, bus, 10.6, playing=False)) == 2             # paused: not admitted...
    assert len(_record(runtime, bus, 10.7)) == 2                            # ...nor later
    assert _record(runtime, bus, 10.3 + SHOCKWAVE_LIFETIME + 0.01) == ()    # all expired
    now = 20.0
    for _ in range(SHOCKWAVE_CAPACITY + 5):
        bus.onset(now)
        now += SHOCKWAVE_MIN_GAP + 0.01
    events = _record(runtime, bus, now)                                     # read once, after them all
    assert len(events) == SHOCKWAVE_CAPACITY
    assert [age for age, *_ in events] == sorted((age for age, *_ in events), reverse=True)   # oldest first
    # The clock going back (a new activation) starts afresh; a retired runtime authors nothing.
    assert _record(runtime, bus, 1.0) == ()
    runtime.retire()
    bus.onset(2.0)
    assert _record(runtime, bus, 2.0) is None


def test_the_bus_publishes_every_onset_exactly_once_whatever_the_reading_cadence(monkeypatch):
    """Onsets inside one logical tick are each delivered (sampling the bus's onset flag per tick
    merged or missed them); serials stay unique across a replaced bus."""
    from widgets.spotify_visualizer import transient_bus
    from widgets.spotify_visualizer.transient_bus import TransientBus

    clock = [100.0]
    monkeypatch.setattr(transient_bus.time, "time", lambda: clock[0])
    bus = TransientBus()
    times = []
    for step in range(60):                      # 2.7 ms analysis frames: a quiet floor with three hits
        clock[0] = 100.0 + step * 0.0027
        hit = step in (20, 40, 58)
        bus.update(1.5 if hit else 0.1, 0.1, 0.1, loudness=2.0 if hit else 0.2)
        if hit:
            times.append(clock[0])
    onsets = bus.recent_onsets
    assert [round(onset.timestamp, 6) for onset in onsets] == [round(t, 6) for t in times]
    assert all(onset.kind == "kick" and onset.magnitude > 0.0 for onset in onsets)
    assert [o.serial for o in onsets] == sorted({o.serial for o in onsets})
    runtime = ShockwaveGridFrameRuntime()
    events = runtime.record_onsets(onsets=onsets, now_ts=clock[0], playing=True, passage_intensity=1.0)
    assert len(events) == 2                     # the middle one came within SHOCKWAVE_MIN_GAP of the first
    assert runtime.record_onsets(onsets=onsets, now_ts=clock[0] + 0.01, playing=True, passage_intensity=1.0) is not None
    assert runtime.onset_serial == onsets[-1].serial
    fresh = TransientBus()                      # a replaced bus (an activation) keeps serials unique
    clock[0] += 1.0
    fresh.update(0.1, 0.1, 0.1)
    clock[0] += 0.003
    fresh.update(1.5, 0.1, 0.1)
    assert fresh.recent_onsets and fresh.recent_onsets[0].serial > onsets[-1].serial


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

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="shockwave_grid", settings=frozen_visualizer_settings("shockwave_grid"))
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

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="shockwave_grid", settings=frozen_visualizer_settings("shockwave_grid"))
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


def test_the_mode_owns_its_shared_source_profile_and_keeps_renderer_import_lazy():
    from core.settings.visualizer_mode_registry import get_technical_profile_mode, get_visualizer_mode_descriptor

    descriptor = get_visualizer_mode_descriptor("shockwave_grid")
    assert get_technical_profile_mode("shockwave_grid") == descriptor.mode_id
    assert descriptor.view_orbit_settings == ("shockwave_grid_turn", "shockwave_grid_tilt")
    code = ("import sys\n"
            "import core.settings.visualizer_mode_registry, rendering.quick.visualizer.implementation_registry\n"
            "import widgets.spotify_visualizer.logical_frame_capture\n"
            "print([m for m in sys.modules if 'shockwave' in m])\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True)
    assert result.stdout.strip() == "[]"


def test_quiet_onsets_make_no_wave_and_big_hits_stand_well_apart_from_medium_ones():
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_MAX_STRENGTH, SHOCKWAVE_MIN_STRENGTH
    from widgets.spotify_visualizer.transient_bus import MUSICAL_QUIET

    from widgets.spotify_visualizer.transient_bus import MUSICAL_USUAL_LOUDNESS as usual

    medium = shockwave_strength(1.5, usual, 1.0)
    big = shockwave_strength(3.0, 1.6 * usual, 1.6)       # a hit well above the usual loudness
    assert SHOCKWAVE_MIN_STRENGTH < medium <= 1.0 and big >= 2.5 * medium and big <= SHOCKWAVE_MAX_STRENGTH
    assert shockwave_strength(3.0, MUSICAL_QUIET[0], 1.0) == 0.0                 # near-silent level
    assert shockwave_strength(3.0, usual, 0.1) < SHOCKWAVE_MIN_STRENGTH          # quiet passage of a loud track
    # More magnitude, loudness or presence never weakens a wave.
    for low, high in (((1.0, usual, 1.0), (2.0, usual, 1.0)), ((1.0, 0.3 * usual, 1.0), (1.0, 0.6 * usual, 1.0)),
                      ((1.0, usual, 0.5), (1.0, usual, 1.2))):
        assert shockwave_strength(*low) <= shockwave_strength(*high)


def test_a_big_hit_stands_out_on_the_fixed_scale_and_a_loud_chorus_keeps_its_emphasis():
    """Emphasis is read on the fixed loudness scale (operator 2026-10-04): the same loud hit makes
    the same wave on its first and its twelfth repeat (a learned usual level flattened it), a
    bigger hit stands out, near-silence makes none."""
    from widgets.spotify_visualizer.transient_bus import MUSICAL_USUAL_LOUDNESS as usual, MusicalOnset

    runtime = ShockwaveGridFrameRuntime()
    serial, now, strengths = 5000, 50.0, []

    def onset(magnitude, loudness, presence):
        nonlocal serial, now
        serial += 1
        now += 0.25
        event = MusicalOnset(serial=serial, timestamp=now, kind="kick", strength=min(1.0, magnitude),
                             magnitude=magnitude, loudness=loudness, presence=presence)
        before = runtime.record_onsets(onsets=(), now_ts=now, playing=True, passage_intensity=1.0)
        after = runtime.record_onsets(onsets=(event,), now_ts=now, playing=True, passage_intensity=1.0)
        strengths.append(after[-1][3] if len(after) > len(before) or (after and after[-1][0] == 0.0) else None)

    for _ in range(12):
        onset(2.0, 1.3 * usual, 1.0)                       # a sustained loud chorus
    assert strengths[0] is not None and strengths[-1] == pytest.approx(strengths[0])
    chorus = strengths[-1]
    onset(3.0, 1.9 * usual, 1.6)                           # a hit well above it
    assert strengths[-1] is not None and strengths[-1] >= 1.6 * chorus
    onset(2.0, 0.05, 0.05)                                  # near-silence between songs
    assert strengths[-1] is None


def test_how_often_and_how_strong_waves_come_ramps_with_the_passage():
    """The same onsets (eight a second, ordinary loud music) make few, soft waves in the track's
    quietest passage and frequent, full ones in its loudest. Without the ramp both were the same
    (~9 waves a second at every level on real music)."""
    from widgets.spotify_visualizer.transient_bus import MusicalOnset

    def waves(intensity):
        runtime, born = ShockwaveGridFrameRuntime(), []
        for index in range(80):
            now = 20.0 + index * 0.125
            onset = MusicalOnset(serial=7000 + index, timestamp=now, kind="kick", strength=1.0,
                                 magnitude=2.0, loudness=9.0, presence=1.2)
            events = runtime.record_onsets(onsets=(onset,), now_ts=now, playing=True,
                                           passage_intensity=intensity)
            born += [event[3] for event in events if event[0] == 0.0]
        return len(born), (sum(born) / len(born) if born else 0.0)

    (quiet_count, quiet_strength), (usual_count, usual_strength), (loud_count, loud_strength) = (
        waves(0.0), waves(0.5), waves(1.0))
    assert loud_count == 80 and quiet_count <= 0.25 * loud_count
    assert quiet_count < usual_count < loud_count
    assert quiet_strength < usual_strength < loud_strength
    assert quiet_strength <= 0.35 * loud_strength


def test_a_big_wave_is_wider_taller_and_trails_an_echo_ring():
    amplitude, speed, age = 0.2, 1.0, 0.8
    ring = speed * age
    for strength in (1.0, 2.0):
        height, crest = shockwave_height(ring, -1.0, [(age, 0.0, -1.0, strength)], amplitude, speed)
        assert height > 0.0 and crest > 0.0
    full = shockwave_height(ring, -1.0, [(age, 0.0, -1.0, 1.0)], amplitude, speed)
    big = shockwave_height(ring, -1.0, [(age, 0.0, -1.0, 2.0)], amplitude, speed)
    assert full[0] < big[0] < 2.0 * full[0] and big[1] > 1.5 * full[1]      # taller, more slowly; brighter
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_ECHO_SPEED

    echo = SHOCKWAVE_ECHO_SPEED * speed * age
    assert shockwave_height(echo, -1.0, [(age, 0.0, -1.0, 1.0)], amplitude, speed)[1] < 0.05
    assert shockwave_height(echo, -1.0, [(age, 0.0, -1.0, 2.0)], amplitude, speed)[1] > 0.2     # the echo


def test_the_idle_swell_drifts_side_to_side_and_moves_the_empty_grid(target):
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_IDLE_PERIOD, shockwave_idle

    centres = [shockwave_idle(0.5, 1.0, t, 2.0)[1] for t in np.linspace(0.0, SHOCKWAVE_IDLE_PERIOD, 40)]
    assert max(centres) > 1.5 and min(centres) < -1.5 and max(abs(c) for c in centres) <= 2.2
    assert max(abs(a - b) for a, b in zip(centres, centres[1:])) < 0.5          # gradual, no jumps
    assert shockwave_idle(0.5, 0.0, 3.0, 2.0)[0] == 0.0
    capture, host = target
    still = capture.render(host, _snapshot(events=(), shockwave_grid_idle=0.0, shockwave_grid_glow=0.0))
    swell = capture.render(host, _snapshot(events=(), shockwave_grid_idle=1.0, shockwave_grid_glow=0.0))
    assert np.abs(swell - still)[..., :3].max(axis=2).astype(bool).sum() > 500
