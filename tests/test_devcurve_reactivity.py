"""DevCurve reactivity (operator 2026-11-05: "its smoothness is great but it has almost no reactivity").

Production seams with test-owned settings: the frame runtime on recorded lanes from the shipped Studio clips (reach,
never pinned), the solver under strong synthetic beats (no twitch, with a snap-attack negative control), silence,
the travelling swell (born outside the view, travelling with the flow) and the flow-rule share. Structure only:
no preset or default values are pinned."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import widgets.spotify_visualizer.devcurve_runtime as devcurve
from widgets.spotify_visualizer.compact_clip import load_feature_clip
from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
from widgets.spotify_visualizer.devcurve_runtime import DevCurveRuntimeState, flow_share, solve_devcurve_frame
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.render_state import VisualizerEnergyState, VisualizerTransientState
from widgets.spotify_visualizer.transient_bus import PassageIntensity, TransientEnergyBands
from tests.test_qtquick_visualizer_devcurve import _nodes, _parameters

CLIPS = Path(__file__).resolve().parents[1] / "assets" / "production" / "studio_clips"
_LAYERS = ("bass", "vocals", "mids", "transients")
_BODY = ("bass", "vocals", "mids")


def _recorded_drives(name: str):
    """Replay a shipped clip's recorded lanes through the production frame runtime, as dispatch feeds it."""
    clip = load_feature_clip(CLIPS / f"{name}.srclip")
    runtime = DevCurveFrameRuntime()
    intensity = PassageIntensity()
    parameters = _parameters()
    origin, last = clip.frames[0].timestamp_us, None
    shares, drives = [], []
    for frame in clip.frames:
        t = (frame.timestamp_us - origin) / 1e6
        intensity.update(frame.real.musical_level[0], 0.0 if last is None else t - last)
        last = t
        lanes = frame.energy
        resolved = runtime.advance(
            now_ts=100.0 + t, runtime_generation=1, engine_generation=1, activation_id=1, source_generation=1,
            source_activation_id=1, source_timestamp=100.0 + t, playing=True,
            energy=VisualizerEnergyState(bass=lanes.pre_agc.bass, mid=lanes.pre_agc.mid, high=lanes.pre_agc.high,
                                         overall=lanes.pre_agc.overall),
            transient=VisualizerTransientState(bass=lanes.transient.bass, mid=lanes.transient.mid,
                                               high=lanes.transient.high),
            musical_level=tuple(frame.real.musical_level), musical_intensity=intensity.value,
            layer_shape_nodes=_nodes(), parameters=parameters,
        )
        if t < 4.0:                     # activation ramp and the response memory's first reach
            continue
        shares.append(lanes.pre_agc.bass)
        drives.append([resolved.diagnostics["drives"][f"height_{key}"] for key in _BODY])
    return np.asarray(shares), np.asarray(drives)


@pytest.mark.parametrize("name", ["human", "growing_pains", "rag_doll"])
def test_recorded_music_uses_the_height_range_without_pinning(name):
    shares, drives = _recorded_drives(name)
    # Negative control: the shared control lane is a band SHARE (band over the loudest band); on its own it sits
    # at its ceiling through ordinary music, which is why DevCurve's heights used to barely react.
    assert (shares > 0.9).mean() > 0.5
    for column in range(drives.shape[1]):
        values = drives[:, column]
        p05, p95 = np.percentile(values, [5, 95])
        # The drive's own top: the body's remembered peak (with its soft overshoot) plus the accents' room.
        key = _BODY[column]
        top = devcurve.DEVCURVE_BODY_TOP[key] * (1.0 + devcurve.DEVCURVE_BODY_OVER) + devcurve.DEVCURVE_ACCENT_ROOM[key]
        assert p95 - p05 > 0.25 * devcurve.DEVCURVE_BODY_TOP[key], (name, column, p05, p95)  # the music moves the height
        assert (values > 0.9 * top).mean() < 0.1, (name, column)   # and never pins it (kick peaks may touch the top)


def _beats(seconds=8.0, period=0.5, dt=1 / 90):
    """Strong synthetic beats: loud kicks every ``period`` over a quieter bed, with flux spikes."""
    for index in range(round(seconds / dt)):
        t = index * dt
        on = (t % period) < 0.06
        yield dt, (14.0 if on else 5.0), (0.9 if on else 0.02)


def _drive(state, dt, loudness, flux, *, now, strength=1.0, playing=True):
    settings = {name: {"enabled": True, "power": 1.0, "offset": 0.0, "order": i + 1} for i, name in enumerate(_LAYERS)}
    nodes = {name: [[0.0, 0.5], [1.0, 0.5]] for name in _LAYERS}
    return solve_devcurve_frame(
        state, dt=dt, now_ts=now, playing=playing,
        energy_bands=EnergyBands(bass=1.0, mid=0.8, high=0.5, overall=0.8),
        transient_bus=TransientEnergyBands(bass_transient=flux, mid_transient=flux, high_transient=flux),
        layer_shape_nodes=nodes, base_level=0.5, motion_power=1.0, idle_motion=0.0, idle_speed=0.1,
        smoothness=0.5, layer_settings=settings, passage_intensity=0.7, loudness=loudness,
        swell_strength=strength, swell_speed=1.0,
    )


def _twitch_ratio():
    """Per x-band: the largest per-tick acceleration of the same curve points over their largest per-tick speed.
    Velocity-continuous motion changes speed over several ticks (small ratio); a snap does it in one (ratio ~1)."""
    state, curves, now = DevCurveRuntimeState(), [], 10.0
    for dt, loudness, flux in _beats():
        now += dt
        curves.append(_drive(state, dt, loudness, flux, now=now)["layers"]["bass"])
    y = np.asarray(curves[180:])
    speed = np.abs(np.diff(y, axis=0))
    accel = np.abs(np.diff(y, 2, axis=0))
    xs = np.linspace(0.0, 1.0, y.shape[1])
    ratios = []
    for lo, hi in ((0.0, 0.2), (0.4, 0.6), (0.8, 1.0)):
        band = (xs >= lo) & (xs <= hi)
        ratios.append(float(accel[:, band].max() / speed[:, band].max()))
    return max(ratios), float(np.ptp(y, axis=0).mean())


def test_strong_beats_move_the_curve_without_twitch(monkeypatch):
    ratio, swing = _twitch_ratio()
    assert swing > 0.05                     # the beats visibly move the curve ...
    assert ratio < 0.5, ratio               # ... with continuous velocity (a snap measures ~0.9)
    # Negative control: snap attacks (the old single fast follower taken to its limit, a swell landing in one tick).
    monkeypatch.setattr(devcurve, "DEVCURVE_SWING_STAGE_S", (1e-4, devcurve.DEVCURVE_SWING_STAGE_S[1]))
    monkeypatch.setattr(devcurve, "DEVCURVE_ACCENT_STAGE_S", (1e-4, devcurve.DEVCURVE_ACCENT_STAGE_S[1]))
    monkeypatch.setattr(devcurve, "DEVCURVE_SWELL_STAGE_S", 1e-4)
    snapped, _ = _twitch_ratio()
    assert snapped > ratio * 1.6, (snapped, ratio)


def test_silence_authors_nothing_and_reactions_fade_out():
    state, twin, now = DevCurveRuntimeState(), DevCurveRuntimeState(), 10.0
    for dt, loudness, flux in _beats(seconds=4.0):
        now += dt
        _drive(state, dt, loudness, flux, now=now)
        _drive(twin, dt, 0.0, 0.0, now=now)
    peaks, drives = [], []
    for _ in range(900):                  # ten seconds of digital silence while "playing"
        now += 1 / 90
        frame = _drive(state, 1 / 90, 0.0, 0.0, now=now)
        rest = _drive(twin, 1 / 90, 0.0, 0.0, now=now)
        peaks.append(frame["drives"]["swell_bass"])
        drives.append(frame["drives"]["height_bass"])
    assert drives[0] > 0.05 and peaks[0] > 0.0          # the music had reacted
    assert max(abs(b - a) for a, b in zip(drives, drives[1:])) < 0.1 * drives[0]   # fades, never vanishes
    assert drives[-1] < 1e-3 and peaks[-1] < 1e-6
    np.testing.assert_allclose(frame["layers"]["bass"], rest["layers"]["bass"], atol=1e-3)
    # A cold start in silence never reacts at all: identical to the no-energy twin from the first tick.
    cold, cold_twin = DevCurveRuntimeState(), DevCurveRuntimeState()
    for index in range(90):
        a = _drive(cold, 1 / 90, 0.0, 0.0, now=50.0 + index / 90)
        b = _drive(cold_twin, 1 / 90, 0.0, 0.0, now=50.0 + index / 90, strength=0.0)
        assert a["layers"] == b["layers"]


def test_swell_is_born_outside_the_view_and_travels_with_the_flow():
    state, now = DevCurveRuntimeState(), 10.0
    for _ in range(90):                   # a steady bed, no accents
        now += 1 / 90
        _drive(state, 1 / 90, 8.0, 0.02, now=now)
    positions, first_visible = [], None
    for index in range(150):
        now += 1 / 90
        _drive(state, 1 / 90, 8.0, 0.9 if index < 4 else 0.02, now=now)
        field = state.swell_field["bass"]
        peak = float(devcurve.DEVCURVE_SWELL_GRID[int(np.argmax(field))])
        visible = field[(devcurve.DEVCURVE_SWELL_GRID >= 0.0) & (devcurve.DEVCURVE_SWELL_GRID <= 1.0)]
        if first_visible is None and visible.max() > 1e-3 * field.max() > 0.0:
            first_visible = peak
        if field.max() > 0.05:
            positions.append(peak)
    assert first_visible is not None and first_visible > 1.0     # it slides in already formed
    assert all(b <= a + 1e-9 for a, b in zip(positions, positions[1:]))   # and travels one way, with the flow
    assert positions[-1] < positions[0] - 0.5


def test_swell_strength_zero_leaves_only_the_height_reaction():
    state, now = DevCurveRuntimeState(), 10.0
    for dt, loudness, flux in _beats(seconds=3.0):
        now += dt
        frame = _drive(state, dt, loudness, flux, now=now, strength=0.0)
        assert frame["drives"]["swell_bass"] == 0.0


def test_flow_share_is_the_largest_admissible_share():
    """Closed form against a fine search of the bound itself: |g'|/g <= SLOPE k and |g''|/g <= CURVE k^2."""
    rng = np.random.default_rng(7)
    grid, dx, k = devcurve.DEVCURVE_SWELL_GRID, devcurve.DEVCURVE_SWELL_DX, devcurve.DEVCURVE_FLOW_WAVENUMBER

    def admissible(swell, share):
        g = 1.0 + share * swell
        first = devcurve._uniform_gradient(g, dx)
        second = devcurve._uniform_gradient(first, dx)
        return bool((np.abs(first) <= devcurve.DEVCURVE_FLOW_SLOPE * k * g + 1e-9).all()
                    and (np.abs(second) <= devcurve.DEVCURVE_FLOW_CURVE * k * k * g + 1e-9).all())

    for _ in range(20):
        centre, sigma, height = rng.uniform(0.0, 1.0), rng.uniform(0.03, 0.2), rng.uniform(0.2, 3.0)
        swell = height * np.exp(-0.5 * ((grid - centre) / sigma) ** 2)
        share = flow_share(swell)
        assert 0.0 < share <= 1.0
        assert admissible(swell, share)
        if share < 1.0:
            assert not admissible(swell, min(1.0, share * 1.01))
