from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
from widgets.spotify_visualizer.oscilloscope_contract import (
    advance_ghost_ring,
    blend_waveform,
    condition_live_waveform,
    resolve_transient_sensitivity_modulation,
    resolve_waveform_blend_alpha,
)


ROOT = Path(__file__).resolve().parent.parent


def test_oscilloscope_low_speed_mapping_does_not_square_curated_presets_into_lag() -> None:
    timid = resolve_waveform_blend_alpha(0.12)
    electric = resolve_waveform_blend_alpha(0.18)
    night_drive = resolve_waveform_blend_alpha(0.24)
    classic = resolve_waveform_blend_alpha(0.33)

    assert timid <= 0.06
    assert electric > 0.06
    assert night_drive > electric
    assert classic > night_drive
    assert classic < 0.20
    assert electric > (0.18 * 0.18) * 1.8


def test_oscilloscope_waveform_response_reaches_audible_step_quickly_without_snapping() -> None:
    previous = [0.0] * 256
    incoming = [1.0] * 256

    path = []
    current = previous
    for _ in range(6):
        current = blend_waveform(current, incoming, 0.18)
        path.append(current[0])

    assert path[0] < 0.12, "Low authored speed should stay smooth, not become a strobe snap."
    assert path[2] >= 0.18, "Low authored speed must not lag several beats behind a clear waveform step."
    assert path[5] >= 0.32, "Oscilloscope low-speed presets should catch up inside a short visual window."


def test_oscilloscope_live_waveform_conditioning_aligns_phase_and_bounds_raw_pcm() -> None:
    import math

    raw = [math.sin(i * math.tau / 32.0) for i in range(256)]
    previous = condition_live_waveform([], raw)
    shifted_inverted = [-raw[(i + 18) % 256] for i in range(256)]
    unconditioned_delta = max(abs(shifted_inverted[i] - previous[i]) for i in range(256))
    conditioned = condition_live_waveform(previous, shifted_inverted)
    conditioned_delta = max(abs(conditioned[i] - previous[i]) for i in range(256))

    assert max(abs(v) for v in previous) < 0.45
    assert conditioned_delta < unconditioned_delta * 0.35


def test_oscilloscope_idle_to_live_boundary_does_not_blend_idle_carrier_into_live_waveform(qt_app) -> None:
    overlay = SpotifyBarsGLOverlay(parent=None)
    qt_app.processEvents()

    rect = QRect(0, 0, 320, 180)
    idle_waveform = [0.035] * 256
    live_waveform = [0.85] * 256

    overlay.set_state(
        rect,
        [0.02] * 8,
        8,
        8,
        QColor("white"),
        QColor("white"),
        1.0,
        False,
        True,
        vis_mode="oscilloscope",
        waveform=idle_waveform,
        waveform_count=256,
        line_speed=0.33,
        osc_ghosting_enabled=True,
        osc_ghost_intensity=0.5,
    )

    overlay.set_state(
        rect,
        [0.4] * 8,
        8,
        8,
        QColor("white"),
        QColor("white"),
        1.0,
        True,
        True,
        vis_mode="oscilloscope",
        waveform=live_waveform,
        waveform_count=256,
        line_speed=0.33,
        osc_ghosting_enabled=True,
        osc_ghost_intensity=0.5,
    )

    assert overlay._prev_waveform == []
    assert overlay._ghost_waveform_ring == []
    assert overlay._waveform[0] != idle_waveform[0]
    assert overlay._waveform[0] < live_waveform[0]


def test_oscilloscope_ghost_ring_uses_oldest_available_frame_during_fill_and_stable_delay_after_full() -> None:
    ring: list[list[float]] = []
    idx = 0
    ghosts = []
    for value in range(1, 8):
        ghost, idx = advance_ghost_ring(ring, idx, [float(value)] * 4, 3)
        ghosts.append(ghost[0])

    assert ghosts[:3] == [1.0, 1.0, 1.0]
    assert ghosts[3:] == [1.0, 2.0, 3.0, 4.0]
    assert len(ring) == 3


def test_oscilloscope_live_to_idle_accepts_idle_waveform_without_stale_ghost_blend(qt_app) -> None:
    overlay = SpotifyBarsGLOverlay(parent=None)
    qt_app.processEvents()

    rect = QRect(0, 0, 320, 180)
    hot_waveform = [0.85] * 256
    idle_waveform = [0.035] * 256

    for _ in range(2):
        overlay.set_state(
            rect,
            [0.1] * 8,
            8,
            8,
            QColor("white"),
            QColor("white"),
            1.0,
            True,
            True,
            vis_mode="oscilloscope",
            waveform=hot_waveform,
            waveform_count=256,
            line_speed=0.18,
            osc_ghosting_enabled=True,
            osc_ghost_intensity=0.5,
        )

    assert overlay._ghost_waveform_ring

    overlay.set_state(
        rect,
        [0.02] * 8,
        8,
        8,
        QColor("white"),
        QColor("white"),
        1.0,
        False,
        True,
        vis_mode="oscilloscope",
        waveform=idle_waveform,
        waveform_count=256,
        line_speed=0.18,
        osc_ghosting_enabled=True,
        osc_ghost_intensity=0.5,
    )

    assert overlay._prev_waveform
    assert overlay._prev_waveform[0] > idle_waveform[0]
    assert overlay._ghost_waveform_ring
    assert overlay._ghost_waveform_ring[0][0] > idle_waveform[0]
    assert overlay._waveform[0] == idle_waveform[0]


def test_oscilloscope_ghost_decay_controls_delayed_trail_duration(qt_app) -> None:
    overlay = SpotifyBarsGLOverlay(parent=None)
    qt_app.processEvents()

    rect = QRect(0, 0, 320, 180)
    waveform = [0.25] * 256

    overlay.set_state(
        rect,
        [0.1] * 8,
        8,
        8,
        QColor("white"),
        QColor("white"),
        1.0,
        True,
        True,
        vis_mode="oscilloscope",
        waveform=waveform,
        waveform_count=256,
        osc_ghosting_enabled=True,
        osc_ghost_intensity=0.5,
        osc_ghost_decay=0.10,
    )
    short_delay = overlay._ghost_delay_frames

    overlay.set_state(
        rect,
        [0.1] * 8,
        8,
        8,
        QColor("white"),
        QColor("white"),
        1.0,
        True,
        True,
        vis_mode="oscilloscope",
        waveform=waveform,
        waveform_count=256,
        osc_ghosting_enabled=True,
        osc_ghost_intensity=0.5,
        osc_ghost_decay=1.0,
    )
    long_delay = overlay._ghost_delay_frames

    assert short_delay <= 4
    assert long_delay >= 16
    assert long_delay > short_delay


def test_oscilloscope_transient_width_accent_is_bounded_and_continuous_body_led() -> None:
    base = 4.0
    quiet_event_sensitivity, quiet_event_drive = resolve_transient_sensitivity_modulation(
        base_sensitivity=base,
        smoothed_bass=0.05,
        kick_event=1.0,
        snare_event=0.6,
        width_mix=0.35,
    )
    hot_body_sensitivity, hot_body_drive = resolve_transient_sensitivity_modulation(
        base_sensitivity=base,
        smoothed_bass=0.85,
        kick_event=0.2,
        snare_event=0.1,
        width_mix=0.35,
    )
    old_shape = base * (1.0 + max(0.05, 1.0 * 0.95 + 0.6 * 0.35) * 0.35)

    assert quiet_event_sensitivity <= base * 1.01
    assert quiet_event_sensitivity < old_shape * 0.72
    assert hot_body_sensitivity > quiet_event_sensitivity
    assert hot_body_drive > quiet_event_drive
    assert hot_body_sensitivity <= base * 1.06


def test_oscilloscope_renderer_import_stays_mode_owned() -> None:
    import widgets.spotify_visualizer.renderers.oscilloscope as osc_renderer

    source = osc_renderer.__loader__.get_source(osc_renderer.__name__)  # type: ignore[union-attr]
    assert "_bubble_" not in source
    assert "_spectrum_" not in source
    assert "_blob_" not in source


def test_oscilloscope_shader_reactive_glow_uses_size_shape_more_than_alpha_pumping() -> None:
    source = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "oscilloscope.frag").read_text(encoding="utf-8")

    assert "sigma *= (0.94 + band_energy * (0.55 * react));" in source
    assert "glow_alpha *= (0.96 + band_energy * (0.10 * react));" in source
    assert "glow_alpha *= (0.80 + band_energy * (0.70 * react));" not in source


def test_oscilloscope_shader_ghosts_are_not_fully_occluded_by_live_line() -> None:
    source = (ROOT / "widgets" / "spotify_visualizer" / "shaders" / "oscilloscope.frag").read_text(encoding="utf-8")

    assert "float ghost_visibility = 1.0 - lines_a * 0.35;" in source
    assert "ghost_rgb * (1.0 - lines_a)" not in source
    assert "ghost_a * (1.0 - lines_a)" not in source
