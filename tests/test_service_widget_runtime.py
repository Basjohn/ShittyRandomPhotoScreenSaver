from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from widgets.service_widget_runtime import (
    get_automatic_startup_refresh_decision,
    should_run_automatic_startup_refresh,
)

ROOT = Path(__file__).resolve().parents[1]


def test_startup_refresh_runs_without_cache_timestamp(monkeypatch):
    monkeypatch.setattr(
        "widgets.service_widget_runtime.automatic_service_updates_enabled",
        lambda: True,
    )
    decision = get_automatic_startup_refresh_decision(cache_timestamp=None)
    assert decision.run is True
    assert decision.reason == "missing_cache_timestamp"
    assert should_run_automatic_startup_refresh(cache_timestamp=None) is True


def test_startup_refresh_skips_when_cache_is_fresh(monkeypatch):
    monkeypatch.setattr(
        "widgets.service_widget_runtime.automatic_service_updates_enabled",
        lambda: True,
    )
    fresh_time = datetime.now() - timedelta(minutes=5)
    decision = get_automatic_startup_refresh_decision(cache_timestamp=fresh_time)
    assert decision.run is False
    assert decision.reason == "cache_fresh"


def test_startup_refresh_runs_when_cache_is_stale(monkeypatch):
    monkeypatch.setattr(
        "widgets.service_widget_runtime.automatic_service_updates_enabled",
        lambda: True,
    )
    stale_time = datetime.now() - timedelta(hours=1)
    decision = get_automatic_startup_refresh_decision(cache_timestamp=stale_time)
    assert decision.run is True
    assert decision.reason == "cache_stale"


def test_startup_refresh_stops_when_noupdates_is_active(monkeypatch):
    monkeypatch.setattr(
        "widgets.service_widget_runtime.automatic_service_updates_enabled",
        lambda: False,
    )
    stale_time = datetime.now() - timedelta(hours=1)
    decision = get_automatic_startup_refresh_decision(cache_timestamp=stale_time)
    assert decision.run is False
    assert decision.reason == "automatic_updates_disabled"


def test_overlay_recurring_timer_has_one_threadmanager_authority():
    source = (ROOT / "widgets" / "overlay_timers.py").read_text(encoding="utf-8")
    assert "tm.schedule_recurring(" in source
    assert "ThreadManager unavailable" in source
    assert "raise RuntimeError(" in source
    assert "QTimer(widget)" not in source
    assert "QTimer.singleShot" not in source


def test_weather_and_media_keep_only_overlay_timer_handles():
    weather = (ROOT / "widgets" / "weather_runtime.py").read_text(encoding="utf-8")
    media = (ROOT / "widgets" / "media_runtime.py").read_text(encoding="utf-8")
    service = (ROOT / "widgets" / "service_widget_runtime.py").read_text(encoding="utf-8")

    assert "_update_timer =" not in weather
    assert 'getattr(handle, "_timer"' not in weather
    assert "_reconcile_timer =" not in media
    assert 'getattr(handle, "_timer"' not in media
    assert "ensure_single_shot_timer" not in service
    assert "stop_qtimer_attr" not in service
    assert "stop_overlay_timer_pair" not in service
    assert "PySide6" not in service
