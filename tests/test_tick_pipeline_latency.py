"""Focused coverage for the viz latency diagnostic's stale-source gate.

Regression target: a source frame carried across a long pause->resume boundary
must be reported as ``stale_source`` at DEBUG, never as a multi-hour "high"
latency WARNING (observed in the 2026-09-04 soak as lag_ms=26,120,276). Real
post-resume latency, which rides a fresh frame produced after the playback
epoch, must still surface as a WARNING.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import widgets.spotify_visualizer.tick_pipeline as tick_pipeline
from widgets.spotify_visualizer.tick_pipeline import log_audio_latency_metrics


def _make_widget() -> SimpleNamespace:
    return SimpleNamespace(
        _enabled=True,
        _spotify_playing=True,
        _latency_activation_started_ts=0.0,
        _latency_audio_ready=False,
        _latency_authority=None,
        _latency_last_log_ts=0.0,
        _latency_log_interval=10.0,
        _latency_warn_ms=80.0,
        _latency_error_ms=150.0,
        _latency_last_signature=None,
        _mode_transition_phase=0,
        _mode_transition_pending=None,
        _vis_mode_str="bubble",
    )


def _make_engine(*, source_ts: float, playback_epoch_ts: float) -> SimpleNamespace:
    return SimpleNamespace(
        get_generation_id=lambda: 1,
        get_activation_id=lambda: 1,
        get_latest_generation_with_frame=lambda: 1,
        get_latest_authoritative_frame=lambda: (source_ts, 1, 1),
        _last_playback_state_ts=playback_epoch_ts,
    )


def test_stale_pre_resume_frame_is_debug_stale_source(monkeypatch, caplog):
    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    widget = _make_widget()
    # Playback resumed at epoch; the authoritative frame is ~7.26h older
    # (pre-pause carry) but still a positive timestamp. ``now`` is just after
    # resume, before a fresh frame lands.
    epoch = 26_200.0
    engine = _make_engine(source_ts=80.0, playback_epoch_ts=epoch)

    with caplog.at_level(logging.DEBUG, logger="widgets.spotify_visualizer.tick_pipeline"):
        log_audio_latency_metrics(widget, engine, now_ts=epoch + 0.1)

    latency = [r for r in caplog.records if "[SPOTIFY_VIS][LATENCY]" in r.message]
    assert len(latency) == 1
    record = latency[0]
    assert record.levelno == logging.DEBUG
    assert "severity=stale_source" in record.message
    # An impossible multi-hour age must never be reported as a WARNING.
    assert not any(
        r.levelno >= logging.WARNING and "[SPOTIFY_VIS][LATENCY]" in r.message
        for r in caplog.records
    )


def test_fresh_post_resume_high_latency_still_warns(monkeypatch, caplog):
    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    widget = _make_widget()
    # A genuinely fresh frame (produced after the playback epoch) that is 500 ms
    # behind: real processing latency, must still warn at severity=high.
    epoch = 10_000.0
    source_ts = epoch + 1.0
    engine = _make_engine(source_ts=source_ts, playback_epoch_ts=epoch)

    with caplog.at_level(logging.DEBUG, logger="widgets.spotify_visualizer.tick_pipeline"):
        log_audio_latency_metrics(widget, engine, now_ts=source_ts + 0.5)

    latency = [r for r in caplog.records if "[SPOTIFY_VIS][LATENCY]" in r.message]
    assert len(latency) == 1
    record = latency[0]
    assert record.levelno == logging.WARNING
    assert "severity=high" in record.message
    assert "severity=stale_source" not in record.message


def test_healthy_fresh_frame_emits_no_latency_line(monkeypatch, caplog):
    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    widget = _make_widget()
    epoch = 10_000.0
    source_ts = epoch + 1.0
    engine = _make_engine(source_ts=source_ts, playback_epoch_ts=epoch)

    with caplog.at_level(logging.DEBUG, logger="widgets.spotify_visualizer.tick_pipeline"):
        # 20 ms behind: under the 80 ms warn threshold -> no diagnostic line.
        log_audio_latency_metrics(widget, engine, now_ts=source_ts + 0.020)

    assert not any("[SPOTIFY_VIS][LATENCY]" in r.message for r in caplog.records)
