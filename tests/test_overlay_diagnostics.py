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


def test_blob_diagnostics_skip_duplicate_quiet_state(monkeypatch):
    logger = _CaptureLogger()
    overlay = SimpleNamespace(
        _vis_mode="blob",
        _blob_kick_event_strength=0.12,
        _blob_snare_event_strength=0.09,
        _blob_diag_last_ts=0.0,
        _blob_diag_last_sig=None,
        _blob_diag_base_bass=0.1,
        _blob_diag_base_mid=0.2,
        _blob_diag_base_high=0.3,
        _blob_diag_base_overall=0.4,
        _blob_diag_transient_bass=0.01,
        _blob_diag_transient_mid=0.02,
        _blob_diag_transient_high=0.03,
    )
    monkeypatch.setattr(overlay_diag, "is_viz_diagnostics_enabled", lambda: True)

    times = iter((10.0, 10.2, 10.9))
    monkeypatch.setattr(overlay_diag.time, "time", lambda: next(times))

    kwargs = dict(
        dt_seconds=0.016,
        blob_dt=0.016,
        kick_raw=0.10,
        snare_raw=0.08,
        raw_live=(0.1, 0.2, 0.3, 0.4),
        filtered_live=(0.1, 0.2, 0.3, 0.4),
        prev_smoothed=0.4,
        raw_e=0.41,
        smoothed_e=0.42,
        stage_raw=(0.1, 0.2, 0.3),
        stage_filtered=(0.1, 0.2, 0.3),
        prev_stage_filtered=(0.1, 0.2, 0.3),
    )

    overlay_diag.maybe_log_blob_diagnostics(overlay, logger, **kwargs)
    overlay_diag.maybe_log_blob_diagnostics(overlay, logger, **kwargs)
    overlay_diag.maybe_log_blob_diagnostics(overlay, logger, **kwargs)

    assert len(logger.messages) == 1
    assert all("[SPOTIFY_VIS][BLOB]" in msg for msg in logger.messages)
