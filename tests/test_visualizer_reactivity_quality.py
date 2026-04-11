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
    blob_glow_drive_mode: str = "bass",
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
        blob_glow_drive_mode=blob_glow_drive_mode,
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
        [0.25, "Low-Mid"],
        [0.50, "Vocal"],
        [0.75, "Hi-Mid"],
        [1.0, "Treble"],
    ]
    worker._spectrum_shape_config = SpectrumShapeConfig(
        lane_strengths_linear={
            "Bass": 0.7,
            "Low-Mid": 0.6,
            "Vocal": 0.55,
            "Hi-Mid": 0.55,
            "Treble": 0.50,
        },
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
def test_blob_vocal_phrase_prefers_wobble_bands_over_body_size(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 0.8
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.03,
        mid_transient=0.26,
        high_transient=0.12,
    )

    vocal_phrase = SimpleNamespace(bass=0.06, mid=0.25, high=0.15, overall=0.11)
    live = overlay._compute_blob_live_bands(vocal_phrase)

    assert live[1] > live[0] * 1.35
    assert live[2] > live[0] * 0.95
    assert overlay._blob_stage_input_bass <= live[0] * 1.10
    assert overlay._blob_stage_input_overall < 0.20


@pytest.mark.qt
def test_blob_stage_inputs_keep_vocal_snare_phrase_off_upper_rungs(qt_app):
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
    assert overlay._blob_stage_input_bass <= live[0] * 1.10
    assert staged_stage[0] < 0.35
    assert staged_stage[1] < 0.08
    assert staged_stage[2] < 0.08


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
def test_blob_transient_rich_snare_phrase_can_seed_stage_progress(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_kick_event_strength = 0.05
    overlay._blob_snare_event_strength = 1.0
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.02,
        mid_transient=0.15,
        high_transient=0.12,
    )

    phrase = SimpleNamespace(bass=0.03, mid=0.03, high=0.03, overall=0.03)
    live = overlay._compute_blob_live_bands(phrase)
    stage = compute_stage_progress(
        bass_energy=overlay._blob_stage_input_bass,
        mid_energy=overlay._blob_stage_input_mid,
        high_energy=overlay._blob_stage_input_high,
        overall_energy=overlay._blob_stage_input_overall,
        smoothed_energy=live[3],
        stage_bias=overlay._blob_stage_bias,
    )

    assert overlay._blob_stage_input_overall > live[3]
    assert stage[0] > 0.01


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

    assert abs(fast_peak - slow_peak) < 0.03
    assert slow_release > fast_release


@pytest.mark.qt
def test_blob_pulse_release_honors_full_ui_range_above_800ms(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    calm = SimpleNamespace(bass=0.10, mid=0.12, high=0.04, overall=0.09)
    hit = SimpleNamespace(bass=0.16, mid=0.52, high=0.09, overall=0.20)

    capped = SpotifyBarsGLOverlay(None)
    capped._vis_mode = "blob"
    extended = SpotifyBarsGLOverlay(None)
    extended._vis_mode = "blob"

    _push_blob_frame(capped, dt=0.016, energy=calm, blob_pulse_release_ms=800.0)
    _push_blob_frame(extended, dt=0.016, energy=calm, blob_pulse_release_ms=1200.0)

    _push_blob_frame(capped, dt=0.016, energy=hit, snare=1.0, blob_pulse_release_ms=800.0)
    _push_blob_frame(extended, dt=0.016, energy=hit, snare=1.0, blob_pulse_release_ms=1200.0)

    _push_blob_frame(capped, dt=0.016, energy=calm, blob_pulse_release_ms=800.0)
    _push_blob_frame(extended, dt=0.016, energy=calm, blob_pulse_release_ms=1200.0)

    assert extended._blob_live_overall_energy > capped._blob_live_overall_energy


@pytest.mark.qt
def test_blob_body_response_drives_derived_runtime_scalars(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
    from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

    overlay = SpotifyBarsGLOverlay(None)
    apply_vis_mode_kwargs(overlay, {"blob_pulse": 0.45})
    low_cap = overlay._blob_pulse_cap
    low_stage_gain = overlay._blob_stage_gain

    apply_vis_mode_kwargs(overlay, {"blob_pulse": 1.85})
    high_cap = overlay._blob_pulse_cap
    high_stage_gain = overlay._blob_stage_gain

    assert low_cap == pytest.approx(1.0)
    assert low_stage_gain == pytest.approx(1.0)
    assert high_cap == pytest.approx(1.0)
    assert high_stage_gain == pytest.approx(1.0)


@pytest.mark.qt
def test_blob_glow_drive_mode_can_follow_vocal_energy(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    bass_overlay = SpotifyBarsGLOverlay(None)
    bass_overlay._vis_mode = "blob"
    vocal_overlay = SpotifyBarsGLOverlay(None)
    vocal_overlay._vis_mode = "blob"

    calm = SimpleNamespace(bass=0.05, mid=0.06, high=0.03, overall=0.05)
    vocal_phrase = SimpleNamespace(bass=0.06, mid=0.36, high=0.20, overall=0.18)

    _push_blob_frame(bass_overlay, dt=0.016, energy=calm, blob_glow_drive_mode="bass")
    _push_blob_frame(vocal_overlay, dt=0.016, energy=calm, blob_glow_drive_mode="vocal")
    _push_blob_frame(bass_overlay, dt=0.016, energy=vocal_phrase, blob_glow_drive_mode="bass")
    _push_blob_frame(vocal_overlay, dt=0.016, energy=vocal_phrase, blob_glow_drive_mode="vocal")

    assert vocal_overlay._blob_glow_energy > bass_overlay._blob_glow_energy * 1.35


def test_blob_negative_stage_bias_softens_stage_without_flattening_valid_bass_support():
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    vals = dict(
        bass_energy=0.1494,
        mid_energy=0.0314,
        high_energy=0.0189,
        overall_energy=0.1580,
        smoothed_energy=0.1750,
    )

    neutral = compute_stage_progress(**vals, stage_bias=0.0)
    softened = compute_stage_progress(**vals, stage_bias=-0.16)

    assert neutral[0] > 0.04
    assert softened[0] > 0.0
    assert softened[0] < neutral[0]
    assert softened[1] == pytest.approx(0.0)
    assert softened[2] == pytest.approx(0.0)


def test_blob_stage_progress_ladder_keeps_headroom_above_stage1():
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    moderate = compute_stage_progress(
        bass_energy=0.24,
        mid_energy=0.03,
        high_energy=0.02,
        overall_energy=0.18,
        smoothed_energy=0.19,
        stage_bias=-0.17,
    )
    strong = compute_stage_progress(
        bass_energy=0.38,
        mid_energy=0.08,
        high_energy=0.05,
        overall_energy=0.28,
        smoothed_energy=0.29,
        stage_bias=-0.17,
    )
    chorus = compute_stage_progress(
        bass_energy=0.50,
        mid_energy=0.14,
        high_energy=0.09,
        overall_energy=0.36,
        smoothed_energy=0.35,
        stage_bias=-0.17,
    )

    assert 0.10 < moderate[0] < 0.95
    assert strong[0] > moderate[0]
    assert strong[1] > moderate[1]
    assert chorus[1] > strong[1]
    assert chorus[2] > strong[2]
    assert chorus[2] > 0.05


@pytest.mark.qt
def test_blob_stage1_decay_does_not_leave_size_parked(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_stage_progress_ready = True
    overlay._blob_stage_progress_filtered = (0.92, 0.0, 0.0)

    decayed = overlay._filter_stage_progress((0.18, 0.0, 0.0), 0.10)

    assert decayed[0] < 0.70
    assert decayed[0] > 0.18


@pytest.mark.qt
def test_blob_stage_filter_keeps_ladder_order_during_decay(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._blob_stage_progress_ready = True
    overlay._blob_stage_progress_filtered = (0.70, 0.80, 0.71)

    decayed = overlay._filter_stage_progress((0.16, 0.0, 0.0), 0.020)

    assert decayed[1] <= decayed[0]
    assert decayed[2] <= decayed[1]


@pytest.mark.qt
def test_blob_preset1_stage_branch_still_answers_moderate_kick_support(qt_app):
    from core.settings.visualizer_presets import get_preset_settings
    from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
    from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._vis_mode = "blob"
    apply_vis_mode_kwargs(overlay, get_preset_settings("blob", 0))

    overlay._blob_kick_event_strength = 0.72
    overlay._blob_snare_event_strength = 0.0
    overlay._transient_energy = TransientEnergyBands(
        bass_transient=0.40,
        mid_transient=0.0,
        high_transient=0.0,
    )

    phrase = SimpleNamespace(bass=0.106, mid=0.159, high=0.118, overall=0.136)
    live = overlay._compute_blob_live_bands(phrase)

    stage = overlay._blob_stage_input_bass, overlay._blob_stage_input_mid, overlay._blob_stage_input_high, overlay._blob_stage_input_overall
    stage_progress = overlay._blob_stage_progress_raw = (0.0, 0.0, 0.0)
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    stage_progress = compute_stage_progress(
        bass_energy=stage[0],
        mid_energy=stage[1],
        high_energy=stage[2],
        overall_energy=stage[3],
        smoothed_energy=live[3],
        stage_bias=overlay._blob_stage_bias,
    )

    assert live[0] < 0.30
    assert stage[0] >= live[0]
    assert stage[3] >= live[3]
    assert stage_progress[0] > 0.10


@pytest.mark.qt
def test_blob_dynamic_floor_pressure_rebases_body_more_than_vocal_motion(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._apply_floor_snapshot(
        {
            "dynamic_enabled": True,
            "manual_floor": 0.15,
            "applied_floor": 0.92,
            "last_noise_floor": 0.90,
            "pressure": 0.90,
        }
    )
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 0.9
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.02,
        mid_transient=0.24,
        high_transient=0.10,
    )

    phrase = SimpleNamespace(bass=0.20, mid=0.31, high=0.18, overall=0.24)
    live = overlay._compute_blob_live_bands(phrase)

    assert live[1] > live[0] * 1.20
    assert live[2] > live[0] * 0.70
    assert live[3] <= float(phrase.overall) + 0.03
    assert live[3] < live[1] * 0.85


def test_blob_stage_progress_keeps_upper_stage_access_under_floor_pressure():
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    calm = compute_stage_progress(
        bass_energy=0.12,
        mid_energy=0.10,
        high_energy=0.06,
        overall_energy=0.13,
        smoothed_energy=0.14,
        stage_bias=-0.17,
    )
    strong = compute_stage_progress(
        bass_energy=0.34,
        mid_energy=0.11,
        high_energy=0.08,
        overall_energy=0.24,
        smoothed_energy=0.25,
        stage_bias=-0.17,
    )
    chorus = compute_stage_progress(
        bass_energy=0.48,
        mid_energy=0.16,
        high_energy=0.10,
        overall_energy=0.34,
        smoothed_energy=0.33,
        stage_bias=-0.17,
    )

    assert strong[0] > calm[0]
    assert strong[1] > calm[1]
    assert chorus[1] > strong[1]
    assert chorus[2] > strong[2]
    assert chorus[2] > 0.10


def test_blob_stage_progress_uses_vocals_for_upper_stage_support_without_overdriving_stage1():
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    sparse_vocal = compute_stage_progress(
        bass_energy=0.20,
        mid_energy=0.08,
        high_energy=0.07,
        overall_energy=0.19,
        smoothed_energy=0.20,
        stage_bias=-0.17,
    )
    vocal_supported = compute_stage_progress(
        bass_energy=0.20,
        mid_energy=0.28,
        high_energy=0.12,
        overall_energy=0.28,
        smoothed_energy=0.26,
        stage_bias=-0.17,
    )

    assert vocal_supported[0] >= sparse_vocal[0] * 0.95
    assert vocal_supported[1] > sparse_vocal[1]
    assert vocal_supported[2] > sparse_vocal[2]


def test_blob_stage_progress_reaches_upper_rungs_for_fast_drum_support():
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    rapid = compute_stage_progress(
        bass_energy=0.36,
        mid_energy=0.23,
        high_energy=0.18,
        overall_energy=0.31,
        smoothed_energy=0.28,
        stage_bias=-0.17,
    )

    assert rapid[0] > 0.45
    assert rapid[1] > 0.28
    assert rapid[2] > 0.12


@pytest.mark.qt
def test_blob_floor_pressure_preserves_stage_branch_better_than_live_body(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
    from widgets.spotify_visualizer.blob_math import compute_stage_progress

    overlay = SpotifyBarsGLOverlay(None)
    overlay._apply_floor_snapshot(
        {
            "dynamic_enabled": True,
            "manual_floor": 0.15,
            "applied_floor": 0.92,
            "last_noise_floor": 0.90,
            "pressure": 0.90,
        }
    )
    overlay._blob_kick_event_strength = 0.72
    overlay._blob_snare_event_strength = 0.88
    overlay._transient_energy = SimpleNamespace(
        bass_transient=0.16,
        mid_transient=0.22,
        high_transient=0.12,
    )

    phrase = SimpleNamespace(bass=0.16, mid=0.25, high=0.15, overall=0.18)
    live = overlay._compute_blob_live_bands(phrase)
    stage_progress = compute_stage_progress(
        bass_energy=overlay._blob_stage_input_bass,
        mid_energy=overlay._blob_stage_input_mid,
        high_energy=overlay._blob_stage_input_high,
        overall_energy=overlay._blob_stage_input_overall,
        smoothed_energy=live[3],
        stage_bias=overlay._blob_stage_bias,
    )

    assert overlay._blob_stage_input_bass >= live[0]
    assert overlay._blob_stage_input_overall >= live[3]
    assert stage_progress[1] > 0.08
    assert stage_progress[2] > 0.02


@pytest.mark.qt
def test_non_shaped_blob_moderate_phrase_does_not_live_in_hot_plateau(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._vis_mode = "blob"

    calm = SimpleNamespace(bass=0.12, mid=0.11, high=0.05, overall=0.10)
    phrase = SimpleNamespace(bass=0.34, mid=0.27, high=0.12, overall=0.24)

    for _ in range(12):
        _push_blob_frame(overlay, dt=0.016, energy=calm)

    hot_frames = 0
    stage_hot_frames = 0
    max_live = 0.0
    for i in range(120):
        _push_blob_frame(
            overlay,
            dt=0.016,
            energy=phrase,
            kick=1.0 if i % 8 == 0 else 0.0,
            snare=1.0 if i % 6 == 0 else 0.0,
        )
        max_live = max(max_live, overlay._blob_live_overall_energy)
        if overlay._blob_live_overall_energy >= 0.82:
            hot_frames += 1
        stage_progress = overlay._blob_stage_progress_filtered
        if (
            stage_progress[0] >= 0.95
            or stage_progress[1] >= 0.85
            or stage_progress[2] >= 0.70
        ):
            stage_hot_frames += 1

    assert max_live < 0.95, (
        f"Blob live overall peaked at {max_live:.3f} on a moderate phrase; "
        "continuous support is still too close to full blowout."
    )
    assert hot_frames < 20, (
        f"Blob spent {hot_frames} frames above the hot plateau threshold on a moderate phrase; "
        "non-shaped Blob is still living too high too often."
    )
    assert stage_hot_frames < 28, (
        f"Blob spent {stage_hot_frames} frames with near-saturated stage progress on a moderate phrase; "
        "the stage branch is still effectively parked at the top."
    )


@pytest.mark.qt
def test_non_shaped_blob_releases_out_of_hot_state_after_phrase(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._vis_mode = "blob"

    calm = SimpleNamespace(bass=0.12, mid=0.11, high=0.05, overall=0.10)
    phrase = SimpleNamespace(bass=0.36, mid=0.29, high=0.13, overall=0.25)

    for _ in range(12):
        _push_blob_frame(overlay, dt=0.016, energy=calm)

    for i in range(80):
        _push_blob_frame(
            overlay,
            dt=0.016,
            energy=phrase,
            kick=1.0 if i % 7 == 0 else 0.0,
            snare=1.0 if i % 5 == 0 else 0.0,
        )

    for _ in range(40):
        _push_blob_frame(overlay, dt=0.016, energy=calm)

    assert overlay._blob_live_overall_energy < 0.30, (
        f"Blob only released to {overlay._blob_live_overall_energy:.3f} after the phrase; "
        "the hot state is still too sticky."
    )
    assert overlay._blob_smoothed_energy < 0.34, (
        f"Blob smoothed energy only released to {overlay._blob_smoothed_energy:.3f}; "
        "the continuous support path is still carrying too much stale pressure."
    )


@pytest.mark.qt
def test_non_shaped_blob_log_shaped_hot_seed_unwinds_quickly(qt_app):
    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    overlay = SpotifyBarsGLOverlay(None)
    overlay._vis_mode = "blob"
    # Seed the same kind of hot carry we saw in the runtime logs:
    # live bands and whole-body support still near/above 1.0 even though
    # the next frames have already gone calm.
    overlay._blob_live_bass_energy = 1.28
    overlay._blob_live_mid_energy = 1.18
    overlay._blob_live_high_energy = 0.35
    overlay._blob_live_overall_energy = 1.13
    overlay._blob_smoothed_energy = 1.24
    overlay._blob_stage_progress_filtered = (1.0, 1.0, 1.0)
    overlay._blob_stage_progress_ready = True

    calm = SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    for _ in range(12):
        _push_blob_frame(overlay, dt=0.016, energy=calm)

    assert overlay._blob_live_overall_energy < 0.42, (
        f"Blob live overall only unwound to {overlay._blob_live_overall_energy:.3f} after "
        "twelve calm frames from a log-shaped hot seed; the body support is still sticking too hot."
    )
    assert overlay._blob_smoothed_energy < 0.65, (
        f"Blob smoothed energy only unwound to {overlay._blob_smoothed_energy:.3f}; the core/glow "
        "support path is still carrying far too much stale pressure."
    )
    assert overlay._blob_live_mid_energy < 0.40, (
        f"Blob live mid only unwound to {overlay._blob_live_mid_energy:.3f}; wobble/glow pressure "
        "is still hanging around long after the calm window started."
    )
    assert overlay._blob_stage_progress_filtered[0] < 0.50, (
        f"Blob stage rung 1 only unwound to {overlay._blob_stage_progress_filtered[0]:.3f}; "
        "stage support is still acting parked after the hot seed."
    )


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
