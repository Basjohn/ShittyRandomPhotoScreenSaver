"""The maintained recorder owns private canonical capture/analysis lanes."""

from __future__ import annotations

import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from core.threading.manager import ThreadManager
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tools.visualizer_replay import record
from utils.audio_capture import AudioCaptureBackend


class _RecorderBackend(AudioCaptureBackend):
    def __init__(self, entered=None, release=None):
        self.entered = entered
        self.release = release
        self._callback = None
        self._negotiated_block_size = 512
        self.start_thread = None
        self.stop_calls = 0

    def start(self, callback):
        self.start_thread = threading.get_ident()
        self._callback = callback
        if self.entered is not None:
            self.entered.set()
            assert self.release.wait(2.0)
        callback(np.ones((32, 2), dtype="float32") * 0.25)
        return True

    def stop(self):
        self.stop_calls += 1
        self._callback = None
        self._note_capture_stopped()

    def is_running(self):
        return self._callback is not None

    @property
    def sample_rate(self):
        return 48000

    @property
    def channels(self):
        return 2

    def restart(self):
        raise AssertionError("recorder tests must not restart capture")


@pytest.fixture
def configured(monkeypatch, qt_app):
    monkeypatch.setattr("core.settings.settings_manager.SettingsManager", lambda: SimpleNamespace(
        get=lambda _: frozen_visualizer_settings("sphere"),
    ))
    controller, engine = record._configured_engine()
    yield controller, engine
    if not controller.thread_manager._shutdown:
        record._close_configured_engine(controller, engine)


def test_configured_recorder_injects_private_manager_before_live_capture(configured, monkeypatch):
    controller, engine = configured
    manager = controller.thread_manager
    assert isinstance(manager, ThreadManager)
    assert engine._thread_manager is manager
    assert manager is not ThreadManager.get_app_shared()
    assert manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"] == {}
    backend = _RecorderBackend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    engine.acquire()
    engine.set_playback_state(True)
    engine._capture_lane.call(lambda: None, timeout=1.0)
    assert backend.start_thread != threading.get_ident()
    assert engine._audio_worker.is_capture_healthy() is True
    assert engine._audio_buffer.consume_latest() is not None
    record._close_configured_engine(controller, engine)
    assert backend.stop_calls == 1
    assert manager.get_lifecycle_ownership_snapshot()["active_tasks"] == ()
    assert manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"] == {}
    assert manager._shutdown is True


def test_recorder_terminal_cleanup_fences_blocked_open_and_joins_owner(configured, monkeypatch):
    controller, engine = configured
    manager = controller.thread_manager
    entered = threading.Event()
    release = threading.Event()
    backend = _RecorderBackend(entered, release)
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    engine.acquire()
    engine.set_playback_state(True)
    assert entered.wait(1.0)
    shutdown = manager.shutdown
    calls = []

    def join_after_capture_fence(*, wait, timeout):
        calls.append((wait, timeout))
        assert engine._audio_worker.is_running() is False
        release.set()
        return shutdown(wait=wait, timeout=timeout)

    monkeypatch.setattr(manager, "shutdown", join_after_capture_fence)
    try:
        record._close_configured_engine(controller, engine)
        assert calls == [(True, 5.0)]
        assert backend.stop_calls == 1
        assert engine._audio_worker.has_capture_owner_work() is False
        assert engine._audio_buffer.consume_latest() is None
        assert manager.get_lifecycle_ownership_snapshot()["active_tasks"] == ()
    finally:
        release.set()


def test_recorder_main_cleans_private_lifetime_when_startup_admission_raises(configured, monkeypatch, tmp_path):
    controller, engine = configured
    monkeypatch.setattr(record, "_configured_engine", lambda: (controller, engine))
    monkeypatch.setattr(record, "OUTPUT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["record", "never_written", "--seconds", "1"])

    def fail_start():
        raise RuntimeError("injected recorder admission failure")

    monkeypatch.setattr(engine, "ensure_started", fail_start)
    with pytest.raises(RuntimeError, match="injected recorder admission failure"):
        record.main()
    assert controller.thread_manager._shutdown is True
    assert controller.thread_manager.get_lifecycle_ownership_snapshot()["active_tasks"] == ()
    assert not (tmp_path / "never_written.jsonl").exists()


def test_recorder_configuration_failure_drains_created_private_manager(monkeypatch, qt_app):
    managers = []
    create_helper = ThreadManager.create_helper_manager

    def create():
        manager = create_helper()
        managers.append(manager)
        return manager

    def fail_source_config(*_args, **_kwargs):
        raise RuntimeError("injected recorder configuration failure")

    monkeypatch.setattr(ThreadManager, "create_helper_manager", create)
    monkeypatch.setattr("core.settings.settings_manager.SettingsManager", lambda: SimpleNamespace(
        get=lambda _: frozen_visualizer_settings("sphere"),
    ))
    monkeypatch.setattr("widgets.spotify_visualizer.source_config_applier.apply_engine_vis_mode_kwargs", fail_source_config)
    with pytest.raises(RuntimeError, match="injected recorder configuration failure"):
        record._configured_engine()
    assert len(managers) == 1
    assert managers[0]._shutdown is True
    assert managers[0].get_lifecycle_ownership_snapshot()["active_tasks"] == ()


def test_recorder_refuses_success_when_private_shutdown_reports_native_debt(configured, monkeypatch):
    controller, engine = configured
    manager = controller.thread_manager
    shutdown = manager.shutdown
    calls = []
    monkeypatch.setattr(manager, "shutdown", lambda **kwargs: calls.append(kwargs) or False)
    try:
        with pytest.raises(RuntimeError, match="ownership did not drain"):
            record._close_configured_engine(controller, engine)
        assert calls == [{"wait": True, "timeout": 5.0}]
    finally:
        assert shutdown(wait=True, timeout=1.0) is True


@pytest.mark.parametrize("outcome", ["failed", "pending", "silent_valid"])
def test_recorder_main_requires_first_valid_native_callback_before_writing_clip(
    configured, monkeypatch, tmp_path, outcome
):
    controller, engine = configured
    entered = threading.Event()
    release = threading.Event()

    class Backend(_RecorderBackend):
        def start(self, callback):
            entered.set()
            if outcome == "failed":
                return False
            if outcome == "pending":
                assert release.wait(2.0)
            self._callback = callback
            callback(np.zeros((32, 2), dtype="float32"))
            return True

    backend = Backend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    monkeypatch.setattr(record, "_configured_engine", lambda: (controller, engine))
    monkeypatch.setattr(record, "OUTPUT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["record", "first_pcm", "--seconds", "1"])
    clock = iter([0.0, 2.0])
    monkeypatch.setattr(record, "time", SimpleNamespace(perf_counter=lambda: next(clock)))
    timers = []

    class Timer:
        def __init__(self):
            self.callback = None
            self.timeout = SimpleNamespace(connect=lambda callback: setattr(self, "callback", callback))
            timers.append(self)

        def setTimerType(self, _kind):
            pass

        def start(self, interval):
            assert interval == record.TICK_MS

        def stop(self):
            pass

    class Application:
        def quit(self):
            pass

        def exec(self):
            assert entered.wait(1.0)
            if outcome != "pending":
                engine._capture_lane.call(lambda: None, timeout=1.0)
            timers[0].callback()

    monkeypatch.setattr(record, "QTimer", Timer)
    monkeypatch.setattr(record, "QCoreApplication", SimpleNamespace(instance=lambda: Application()))
    shutdown = controller.thread_manager.shutdown

    def release_native_open_and_join(**kwargs):
        release.set()
        return shutdown(**kwargs)

    monkeypatch.setattr(controller.thread_manager, "shutdown", release_native_open_and_join)
    try:
        if outcome == "silent_valid":
            record.main()
            assert (tmp_path / "first_pcm.jsonl").is_file()
        else:
            with pytest.raises(RuntimeError, match="recording rejected"):
                record.main()
            assert not (tmp_path / "first_pcm.jsonl").exists()
        assert controller.thread_manager._shutdown is True
        assert backend.stop_calls == 1
        assert engine._audio_worker.has_capture_owner_work() is False
    finally:
        release.set()
