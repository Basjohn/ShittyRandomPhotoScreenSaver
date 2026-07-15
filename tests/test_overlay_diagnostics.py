from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor

import widgets.spotify_visualizer.overlay_diagnostics as overlay_diag


class _CaptureLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def isEnabledFor(self, level: int) -> bool:
        return level == logging.DEBUG

    def debug(self, msg, *args, **kwargs) -> None:
        try:
            self.messages.append(msg % args if args else str(msg))
        except Exception:
            self.messages.append(str(msg))


def test_glow_diagnostics_log_only_on_signature_or_interval(monkeypatch):
    logger = _CaptureLogger()
    overlay = SimpleNamespace(
        _vis_mode="spectrum",
        _spectrum_glow_enabled=True,
        _spectrum_glow_intensity=0.55,
        _spectrum_glow_color=QColor(10, 20, 30, 40),
        _bar_count=35,
        _energy_bands=SimpleNamespace(bass=0.1, mid=0.2, high=0.3, overall=0.4),
        _glow_diag_last_ts=0.0,
        _glow_diag_last_sig=None,
    )
    monkeypatch.setattr(overlay_diag, "is_viz_diagnostics_enabled", lambda: True)

    times = iter((10.0, 11.0, 11.5, 24.2))
    monkeypatch.setattr(overlay_diag.time, "time", lambda: next(times))

    overlay_diag.maybe_log_glow_diagnostics(overlay, logger)
    overlay_diag.maybe_log_glow_diagnostics(overlay, logger)
    overlay._spectrum_glow_intensity = 0.77
    overlay_diag.maybe_log_glow_diagnostics(overlay, logger)
    overlay_diag.maybe_log_glow_diagnostics(overlay, logger)

    assert len(logger.messages) == 3
    assert all("[SPOTIFY_VIS][GLOW]" in msg for msg in logger.messages)


def test_sine_idle_diagnostics_respect_throttle(monkeypatch):
    logger = _CaptureLogger()
    overlay = SimpleNamespace(
        _vis_mode="sine_wave",
        _playing=False,
        _accumulated_time=2.5,
        _line_speed=0.4,
        _sine_wave_travel=1,
        _sine_travel_line2=0,
        _sine_travel_line3=0,
        _sine_travel_line4=0,
        _sine_travel_line5=0,
        _sine_travel_line6=0,
        _line_count=3,
        _last_sine_idle_diag_ts=0.0,
    )
    monkeypatch.setattr(overlay_diag, "is_viz_diagnostics_enabled", lambda: True)

    times = iter((5.0, 5.4, 6.1))
    monkeypatch.setattr(overlay_diag.time, "time", lambda: next(times))

    overlay_diag.maybe_log_sine_idle_state(overlay, logger, dt_seconds=0.016)
    overlay_diag.maybe_log_sine_idle_state(overlay, logger, dt_seconds=0.016)
    overlay_diag.maybe_log_sine_idle_state(overlay, logger, dt_seconds=0.016)

    assert len(logger.messages) == 2
    assert all("[SPOTIFY_VIS][SINE][IDLE_STATE]" in msg for msg in logger.messages)


def test_oscilloscope_diagnostics_build_signature_before_throttling(monkeypatch):
    logger = _CaptureLogger()
    overlay = SimpleNamespace(
        _vis_mode="oscilloscope",
        _line_speed=0.21,
        _osc_last_waveform_blend_alpha=0.08,
        _osc_last_waveform_delta=0.01,
        _osc_ghost_alpha=0.65,
        _ghost_waveform_ring=[object()] * 4,
        _ghost_delay_frames=4,
        _osc_transient_width_mix=0.35,
        _osc_last_transient_width_drive=0.8,
        _osc_last_sensitivity_mod=0.4,
        _line_smoothed_bass=0.3,
        _line_smoothed_mid=0.2,
        _line_smoothed_high=0.1,
        _energy_bands=SimpleNamespace(overall=0.25),
        _osc_diag_last_ts=0.0,
        _osc_diag_last_sig=None,
    )
    monkeypatch.setattr(overlay_diag, "is_viz_diagnostics_enabled", lambda: True)
    times = iter((10.0, 10.5, 12.0))
    monkeypatch.setattr(overlay_diag.time, "time", lambda: next(times))

    overlay_diag.maybe_log_oscilloscope_diagnostics(overlay, logger)
    overlay_diag.maybe_log_oscilloscope_diagnostics(overlay, logger)
    overlay._line_speed = 0.5
    overlay_diag.maybe_log_oscilloscope_diagnostics(overlay, logger)

    assert len(logger.messages) == 2
    assert all("[SPOTIFY_VIS][OSC]" in msg for msg in logger.messages)
