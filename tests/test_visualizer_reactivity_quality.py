from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor


def _push_blob_frame(
    overlay,
    *,
    dt: float,
    energy,
    kick: float = 0.0,
    snare: float = 0.0,
    blob_pulse_cap: float = 1.0,
    blob_pulse_release_ms: float = 220.0,
) -> None:
    overlay._last_time_ts = time.time() - dt
    overlay.set_state(
        rect=QRect(0, 0, 320, 180),
        bars=[0.0],
        bar_count=1,
        segments=1,
        fill_color=QColor(255, 255, 255),
        border_color=QColor(255, 255, 255),
        fade=1.0,
        playing=True,
        visible=True,
        vis_mode='blob',
        energy_bands=energy,
        blob_kick_event_strength=kick,
        blob_snare_event_strength=snare,
        blob_pulse_cap=blob_pulse_cap,
        blob_pulse_release_ms=blob_pulse_release_ms,
    )


def _make_spectrum_soak_worker(np_module, bar_count: int = 15):
    from utils.lockfree import TripleBuffer
    from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig
    from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker, _AudioFrame

    worker = SpotifyVisualizerAudioWorker(bar_count=bar_count, buffer=TripleBuffer())
    worker._np = np_module  # type: ignore[attr-defined]
    worker._spectrum_shape_nodes = [[0.0, 0.9], [0.5, 0.9], [1.0, 0.9]]
    worker._spectrum_mirrored = False
    worker._spectrum_notch_positions = [
        [0.0, "Bass"],
        [0.25, "Low"],
        [0.50, "Mid"],
        [0.75, "Hi-Mid"],
        [1.0, "Treble"],
    ]
    worker._spectrum_shape_config = SpectrumShapeConfig(
        bass_emphasis=0.7,
        vocal_peak_position=0.5,
        mid_suppression=0.5,
        wave_amplitude=0.9,
        profile_floor=0.05,
    )
    worker._use_recommended = False
    worker._user_sensitivity = 1.0
    worker._use_dynamic_floor = False
    worker._manual_floor = 0.12
    worker._applied_noise_floor = 0.12
    worker._raw_bass_avg = 0.12
    return worker


def _make_lane_fft(np_module, low: float, mid: float, high: float, size: int = 2048):
    fft = np_module.zeros(size, dtype="float32")
    fft[2:24] = low
    fft[48:180] = mid
    fft[260:640] = high
    return fft


@pytest.mark.qt
def test_blob_mid_hit_releases_over_multiple_frames(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._vis_mode = "blob"

    calm = SimpleNamespace(bass=0.12, mid=0.14, high=0.05, overall=0.11)
    hit = SimpleNamespace(bass=0.14, mid=0.58, high=0.08, overall=0.21)

    _push_blob_frame(overlay, dt=0.016, energy=calm)
    base_mid = overlay._blob_live_mid_energy

    _push_blob_frame(overlay, dt=0.016, energy=hit, snare=1.0)
    peak_mid = overlay._blob_live_mid_energy

    _push_blob_frame(overlay, dt=0.016, energy=calm)
    release_1 = overlay._blob_live_mid_energy

    _push_blob_frame(overlay, dt=0.016, energy=calm)
    release_2 = overlay._blob_live_mid_energy

    assert peak_mid > base_mid
    assert release_1 > base_mid
    assert release_2 > base_mid
    assert release_1 < peak_mid
    assert release_2 < release_1
    assert (peak_mid - release_1) < (peak_mid - base_mid) * 0.85


@pytest.mark.qt
def test_blob_hitch_soak_stays_bounded_and_recovers(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._vis_mode = "blob"

    quiet = SimpleNamespace(bass=0.10, mid=0.11, high=0.04, overall=0.09)
    loud = SimpleNamespace(bass=0.34, mid=0.42, high=0.16, overall=0.28)

    max_overall = 0.0
    max_stage = 0.0
    for idx in range(80):
        dt = 0.120 if idx % 9 == 0 else 0.016
        energy = loud if idx % 7 in (0, 1) else quiet
        kick = 1.0 if idx % 11 == 0 else 0.0
        snare = 1.0 if idx % 13 == 0 else 0.0
        _push_blob_frame(overlay, dt=dt, energy=energy, kick=kick, snare=snare)
        max_overall = max(max_overall, overlay._blob_live_overall_energy)
        max_stage = max(max_stage, *overlay._blob_stage_progress_filtered)

    for _ in range(40):
        _push_blob_frame(overlay, dt=0.016, energy=quiet)

    assert max_overall <= 1.5
    assert 0.0 <= max_stage <= 1.0
    assert overlay._blob_live_overall_energy < 0.25
    assert overlay._blob_stage_progress_filtered[0] < max_stage
    assert overlay._blob_stage_progress_filtered[0] < 0.55


@pytest.mark.qt
def test_blob_kick_assist_requires_real_low_end_support(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 1.0
    overlay._blob_snare_event_strength = 0.0

    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.03,
        mid_transient=0.26,
        high_transient=0.10,
    )
    piano_like = SimpleNamespace(bass=0.04, mid=0.22, high=0.12, overall=0.10)
    piano_live = overlay._compute_blob_live_bands(piano_like)

    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.42,
        mid_transient=0.05,
        high_transient=0.02,
    )
    bass_hit = SimpleNamespace(bass=0.28, mid=0.07, high=0.03, overall=0.16)
    bass_live = overlay._compute_blob_live_bands(bass_hit)

    assert piano_live[0] < bass_live[0] * 0.70
    assert piano_live[3] < bass_live[3] * 0.75


@pytest.mark.qt
def test_blob_kick_assist_prefers_stage_growth_over_live_bass_blowout(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 1.0
    overlay._blob_snare_event_strength = 0.0
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.10,
        mid_transient=0.04,
        high_transient=0.02,
    )

    phrase = SimpleNamespace(bass=0.18, mid=0.08, high=0.03, overall=0.12)
    live = overlay._compute_blob_live_bands(phrase)

    assert live[0] <= float(phrase.bass) + 0.08
    assert overlay._blob_stage_input_bass > live[0]
    assert overlay._blob_stage_input_overall > live[3]


@pytest.mark.qt
def test_blob_snare_assist_does_not_drive_stage_on_vocal_phrase(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 1.0
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.02,
        mid_transient=0.24,
        high_transient=0.12,
    )

    vocal_phrase = SimpleNamespace(bass=0.05, mid=0.24, high=0.14, overall=0.11)
    live = overlay._compute_blob_live_bands(vocal_phrase)

    assert live[3] < 0.18


@pytest.mark.qt
def test_blob_stage_inputs_stay_bass_biased_on_snare_phrase(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 1.0
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.02,
        mid_transient=0.22,
        high_transient=0.12,
    )

    vocal_phrase = SimpleNamespace(bass=0.05, mid=0.24, high=0.14, overall=0.11)
    live = overlay._compute_blob_live_bands(vocal_phrase)

    live_stage = compute_stage_progress(
        bass_energy=live[0],
        mid_energy=live[1],
        high_energy=live[2],
        overall_energy=live[3],
        smoothed_energy=live[3],
    )
    staged_stage = compute_stage_progress(
        bass_energy=overlay._blob_stage_input_bass,
        mid_energy=overlay._blob_stage_input_mid,
        high_energy=overlay._blob_stage_input_high,
        overall_energy=overlay._blob_stage_input_overall,
        smoothed_energy=live[3],
    )

    assert overlay._blob_stage_input_mid < live[1] * 0.65
    assert overlay._blob_stage_input_high < live[2] * 0.60
    assert overlay._blob_stage_input_bass < live[0]
    assert staged_stage[0] <= live_stage[0]


@pytest.mark.qt
def test_blob_stage_inputs_favor_kick_over_snare_on_light_passages(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)

    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.02,
        mid_transient=0.20,
        high_transient=0.09,
    )
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 1.0
    overlay._compute_blob_live_bands(
        SimpleNamespace(bass=0.05, mid=0.22, high=0.12, overall=0.10)
    )
    snare_stage_inputs = (
        overlay._blob_stage_input_bass,
        overlay._blob_stage_input_mid,
        overlay._blob_stage_input_high,
        overlay._blob_stage_input_overall,
    )

    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.34,
        mid_transient=0.05,
        high_transient=0.02,
    )
    overlay._blob_kick_event_strength = 1.0
    overlay._blob_snare_event_strength = 0.0
    overlay._compute_blob_live_bands(
        SimpleNamespace(bass=0.24, mid=0.07, high=0.03, overall=0.15)
    )
    kick_stage_inputs = (
        overlay._blob_stage_input_bass,
        overlay._blob_stage_input_mid,
        overlay._blob_stage_input_high,
        overlay._blob_stage_input_overall,
    )

    assert snare_stage_inputs[3] < kick_stage_inputs[3]
    assert snare_stage_inputs[0] < kick_stage_inputs[0]


@pytest.mark.qt
def test_blob_pulse_cap_limits_low_support_reactive_lift(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 1.0
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.02,
        mid_transient=0.20,
        high_transient=0.10,
    )
    phrase = SimpleNamespace(bass=0.05, mid=0.22, high=0.12, overall=0.10)

    overlay._blob_pulse_cap = 1.0
    default_live = overlay._compute_blob_live_bands(phrase)
    default_stage_overall = overlay._blob_stage_input_overall

    overlay._blob_pulse_cap = 0.35
    capped_live = overlay._compute_blob_live_bands(phrase)
    capped_stage_overall = overlay._blob_stage_input_overall

    assert capped_live[1] < default_live[1]
    assert capped_stage_overall <= default_stage_overall


@pytest.mark.qt
def test_blob_pulse_release_slows_decay_without_slowing_attack(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    calm = SimpleNamespace(bass=0.10, mid=0.12, high=0.04, overall=0.09)
    hit = SimpleNamespace(bass=0.16, mid=0.52, high=0.09, overall=0.20)

    fast = SpotifyBarsGLOverlay(None)
    fast._vis_mode = "blob"

    slow = SpotifyBarsGLOverlay(None)
    slow._vis_mode = "blob"

    _push_blob_frame(fast, dt=0.016, energy=calm, blob_pulse_release_ms=120.0)
    _push_blob_frame(slow, dt=0.016, energy=calm, blob_pulse_release_ms=420.0)

    _push_blob_frame(fast, dt=0.016, energy=hit, snare=1.0, blob_pulse_release_ms=120.0)
    fast_peak = fast._blob_live_mid_energy
    _push_blob_frame(slow, dt=0.016, energy=hit, snare=1.0, blob_pulse_release_ms=420.0)
    slow_peak = slow._blob_live_mid_energy

    _push_blob_frame(fast, dt=0.016, energy=calm, blob_pulse_release_ms=120.0)
    fast_release = fast._blob_live_mid_energy
    _push_blob_frame(slow, dt=0.016, energy=calm, blob_pulse_release_ms=420.0)
    slow_release = slow._blob_live_mid_energy

    assert abs(fast_peak - slow_peak) < 0.02
    assert slow_release > fast_release


def test_spectrum_lane_isolation_survives_long_run():
    import numpy as np

    worker = _make_spectrum_soak_worker(np)

    def _tail_lane_mean(sequence, lane_slice: slice) -> float:
        tail = sequence[-8:]
        totals = []
        for bars in tail:
            totals.append(sum(bars[lane_slice]) / max(1, len(bars[lane_slice])))
        return sum(totals) / len(totals)

    phases = {
        "vocal": [_make_lane_fft(np, low=0.0, mid=12.0, high=10.0) for _ in range(28)],
        "bass": [_make_lane_fft(np, low=10.0, mid=0.0, high=2.0) for _ in range(28)],
        "treble": [_make_lane_fft(np, low=1.0, mid=2.0, high=12.0) for _ in range(28)],
    }

    vocal_bars = [worker._fft_to_bars(fft) for fft in phases["vocal"]]
    bass_bars = [worker._fft_to_bars(fft) for fft in phases["bass"]]
    treble_bars = [worker._fft_to_bars(fft) for fft in phases["treble"]]

    vocal_lane = _tail_lane_mean(vocal_bars, slice(5, 10))
    vocal_bass_lane = _tail_lane_mean(vocal_bars, slice(0, 4))
    bass_lane = _tail_lane_mean(bass_bars, slice(0, 4))
    bass_vocal_lane = _tail_lane_mean(bass_bars, slice(5, 10))
    treble_lane = _tail_lane_mean(treble_bars, slice(11, 15))
    treble_bass_lane = _tail_lane_mean(treble_bars, slice(0, 4))
    treble_vocal_lane = _tail_lane_mean(treble_bars, slice(5, 10))

    assert vocal_bass_lane < vocal_lane * 0.55
    assert bass_vocal_lane < bass_lane * 0.70
    assert treble_bass_lane < treble_lane * 0.70
    assert treble_vocal_lane < treble_lane * 0.85
