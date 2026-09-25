"""Every replacement shares one construction path and one construction-to-reveal hang window.

The 2026-09-25 double-wake freeze happened *after* the third replacement's
construction returned, while its first image and first frames were still
outstanding. The monitor-topology path had its own copy of replacement
construction that never armed the all-thread stack dump, and the settings/CUSTOM
path disarmed it as soon as construction returned — so neither window covered
the moment the process wedged.

These bars drive the real engine lifecycle methods; construction internals are
recorded stand-ins.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import engine.engine_handlers as engine_handlers
from core.diagnostics import hang_watchdog
from engine.screensaver_engine import EngineState, ScreensaverEngine
from sources.base_provider import ImageMetadata, ImageSourceType


@pytest.fixture(autouse=True)
def _always_disarm():
    yield
    hang_watchdog.disarm()


@pytest.fixture
def engine(qt_app, monkeypatch):
    engine = ScreensaverEngine()
    starts: list[bool] = []
    engine._state = EngineState.STOPPED
    engine._runtime_generation = 3
    engine.display_manager = object()

    def _start(*, show_first_image: bool = True) -> bool:
        starts.append(show_first_image)
        engine._state = EngineState.RUNNING
        return True

    monkeypatch.setattr(engine, "_initialize_display", lambda: True)
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "start", _start)
    monkeypatch.setattr(
        engine_handlers,
        "log_lifecycle_resource_snapshot",
        lambda *_args, **_kwargs: None,
    )
    engine._test_starts = starts
    yield engine
    engine._state = EngineState.SHUTTING_DOWN


def test_hang_window_stays_armed_until_the_generation_reveals(engine):
    assert engine_handlers._construct_and_start_replacement_runtime(
        engine,
        event="monitor_topology",
        show_first_image=False,
    )
    label = engine_handlers.replacement_watchdog_label("monitor_topology", 3)

    assert engine._test_starts == [False]
    # Construction returned; the first image/first frame/reveal are still
    # ahead, so the window must still be armed.
    assert hang_watchdog.armed_label() == label

    engine._on_startup_reveal_completed(3, engine.display_manager, 3)
    assert hang_watchdog.armed_label() is None


def test_retiring_generation_closes_its_hang_window(engine):
    assert engine_handlers._construct_and_start_replacement_runtime(
        engine,
        event="settings",
    )
    assert hang_watchdog.armed_label() is not None

    engine._advance_runtime_generation("monitor_topology")
    assert hang_watchdog.armed_label() is None


def test_failed_construction_closes_its_hang_window(engine, monkeypatch):
    quits: list[bool] = []
    monkeypatch.setattr(engine, "_initialize_display", lambda: False)
    monkeypatch.setattr(
        engine_handlers,
        "request_application_quit",
        lambda reason: quits.append(reason) or True,
    )

    assert not engine_handlers._construct_and_start_replacement_runtime(
        engine,
        event="custom_edit",
    )
    assert quits == ["replacement_initialize_failed"]
    assert hang_watchdog.armed_label() is None


def test_stale_reveal_edge_cannot_close_a_newer_window(engine):
    assert engine_handlers._construct_and_start_replacement_runtime(
        engine,
        event="monitor_topology",
    )
    stale_label = engine_handlers.replacement_watchdog_label("monitor_topology", 2)
    hang_watchdog.disarm(stale_label)
    assert hang_watchdog.armed_label() == engine_handlers.replacement_watchdog_label(
        "monitor_topology",
        3,
    )


def test_monitor_topology_rebuild_uses_the_shared_replacement_path(engine, monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(engine, "stop", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        engine_handlers,
        "_construct_and_start_replacement_runtime",
        lambda eng, **kwargs: calls.append(kwargs) or True,
    )
    import engine.runtime_destruction as runtime_destruction

    monkeypatch.setattr(
        runtime_destruction,
        "continue_after_runtime_destruction",
        lambda _engine, callback: callback(),
    )
    engine._current_image = ImageMetadata(
        source_type=ImageSourceType.FOLDER,
        source_id="test",
        image_id="current",
        local_path=Path("current.jpg"),
    )

    engine._on_monitors_changed(2)

    assert calls == [{"event": "monitor_topology", "show_first_image": False}]
    assert engine._pending_monitor_replay_image is engine._current_image
