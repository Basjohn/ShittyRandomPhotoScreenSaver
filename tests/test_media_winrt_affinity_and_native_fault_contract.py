from __future__ import annotations

import faulthandler
import importlib.util
from pathlib import Path
import threading
import sys

from core.logging import crash_capture
from core.media.media_controller import WindowsGlobalMediaController

_AFFINITY_PATH = Path(__file__).parents[1] / "core" / "threading" / "affinity_lanes.py"
_SPEC = importlib.util.spec_from_file_location("srpss_affinity_lanes_test", _AFFINITY_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_AFFINITY = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _AFFINITY
_SPEC.loader.exec_module(_AFFINITY)
AffinityLaneScheduler = _AFFINITY.AffinityLaneScheduler


class _FakeThreadManager:
    def __init__(self) -> None:
        self.scheduler = AffinityLaneScheduler()

    def create_affinity_lane(self, **kwargs):
        owner = kwargs.get("owner")
        return self.scheduler.register_lane(
            lane_id=kwargs["lane_id"],
            category=kwargs["category"],
            runtime_generation=kwargs.get("runtime_generation"),
            owner_class=type(owner).__name__ if owner is not None else None,
            owner_id=id(owner) if owner is not None else None,
        )


class _FakeNativeObject:
    def __init__(self) -> None:
        self.add_threads: list[int] = []
        self.remove_threads: list[int] = []
        self.handlers: dict[str, object] = {}
        self._next_token = 1

    def _add(self, name: str, handler):
        self.add_threads.append(threading.get_ident())
        token = (name, self._next_token)
        self._next_token += 1
        self.handlers[name] = handler
        return token

    def _remove(self, name: str, token) -> None:
        del token
        self.remove_threads.append(threading.get_ident())
        self.handlers.pop(name, None)


class _FakeManager(_FakeNativeObject):
    def add_current_session_changed(self, handler):
        return self._add("current_session_changed", handler)

    def remove_current_session_changed(self, token):
        self._remove("current_session_changed", token)

    def add_sessions_changed(self, handler):
        return self._add("sessions_changed", handler)

    def remove_sessions_changed(self, token):
        self._remove("sessions_changed", token)


class _FakeSession(_FakeNativeObject):
    def add_playback_info_changed(self, handler):
        return self._add("playback_info_changed", handler)

    def remove_playback_info_changed(self, token):
        self._remove("playback_info_changed", token)

    def add_media_properties_changed(self, handler):
        return self._add("media_properties_changed", handler)

    def remove_media_properties_changed(self, token):
        self._remove("media_properties_changed", token)

    def add_timeline_properties_changed(self, handler):
        return self._add("timeline_properties_changed", handler)

    def remove_timeline_properties_changed(self, token):
        self._remove("timeline_properties_changed", token)


def _make_controller(tm: _FakeThreadManager, manager, session) -> WindowsGlobalMediaController:
    controller = WindowsGlobalMediaController(thread_manager=tm)
    controller._available = True
    controller._MediaManager = object()
    controller._run_coro_in_isolated_loop = lambda factory: manager
    controller._select_media_session = lambda selected_manager: session
    return controller


def test_retained_winrt_subscribe_and_release_share_one_affinity_thread() -> None:
    tm = _FakeThreadManager()
    manager = _FakeManager()
    session = _FakeSession()
    controller = _make_controller(tm, manager, session)
    established = threading.Event()

    assert controller.start_event_observation(
        lambda reason: None,
        lambda ok, detail: established.set(),
    )
    assert established.wait(1.0)
    assert controller.is_event_observation_active()

    controller.stop_event_observation()

    native_threads = manager.add_threads + manager.remove_threads + session.add_threads + session.remove_threads
    assert native_threads
    assert len(set(native_threads)) == 1
    assert native_threads[0] != threading.get_ident()
    assert manager.remove_threads
    assert session.remove_threads
    assert controller._event_manager is None
    assert controller._event_session is None
    assert controller._manager_tokens == []
    assert controller._session_tokens == []
    assert tm.scheduler.shutdown(wait=True, timeout=1.0)



def test_pending_owner_transaction_blocks_overlapping_observation_start() -> None:
    tm = _FakeThreadManager()
    manager = _FakeManager()
    session = _FakeSession()
    controller = _make_controller(tm, manager, session)

    class _FinishingLane:
        is_stopped = True

    controller._observation_lane = _FinishingLane()
    assert controller.start_event_observation(lambda reason: None) is False
    assert tm.scheduler.diagnostic_snapshot()["registered_lanes"] == 0
    controller._observation_lane = None
    assert tm.scheduler.shutdown(wait=True, timeout=1.0)


def test_manager_dirty_callback_rebinds_on_affinity_owner_not_callback_thread() -> None:
    tm = _FakeThreadManager()
    manager = _FakeManager()
    first_session = _FakeSession()
    second_session = _FakeSession()
    selected = [first_session]
    controller = _make_controller(tm, manager, first_session)
    controller._select_media_session = lambda selected_manager: selected[0]
    established = threading.Event()
    dirty = threading.Event()

    assert controller.start_event_observation(
        lambda reason: dirty.set(),
        lambda ok, detail: established.set(),
    )
    assert established.wait(1.0)
    callback_thread = threading.get_ident()
    selected[0] = second_session
    handler = manager.handlers["current_session_changed"]
    handler(None, None)
    assert dirty.wait(1.0)

    assert first_session.remove_threads
    assert second_session.add_threads
    all_rebind_threads = first_session.remove_threads + second_session.add_threads
    assert len(set(all_rebind_threads)) == 1
    assert all_rebind_threads[0] != callback_thread

    controller.stop_event_observation()
    assert tm.scheduler.shutdown(wait=True, timeout=1.0)


def test_debug_native_fault_capture_uses_companion_and_watchdog_cannot_retarget(tmp_path: Path) -> None:
    crash_capture.close_diagnostic_crash_capture()
    path = crash_capture.enable_diagnostic_crash_capture(tmp_path, allow_runtime_capture=True)
    try:
        assert path == tmp_path / "native_faults.log"
        assert path.is_file()
        assert faulthandler.is_enabled()
        source = (Path(__file__).parents[1] / "core" / "diagnostics" / "hang_watchdog.py").read_text()
        executable_source = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        assert "faulthandler.enable(" not in executable_source
        assert "faulthandler.dump_traceback_later(" in executable_source
    finally:
        crash_capture.close_diagnostic_crash_capture()



def test_native_fault_capture_does_not_report_active_when_faulthandler_enable_fails(
    tmp_path: Path, monkeypatch
) -> None:
    crash_capture.close_diagnostic_crash_capture()
    monkeypatch.setattr(crash_capture.faulthandler, "is_enabled", lambda: False)

    def _fail_enable(*_args, **_kwargs):
        raise RuntimeError("native handler unavailable")

    monkeypatch.setattr(crash_capture.faulthandler, "enable", _fail_enable)
    path = crash_capture.enable_diagnostic_crash_capture(tmp_path, allow_runtime_capture=True)
    assert path is None
    assert crash_capture._capture_enabled is False
    assert crash_capture._stream is None
    assert crash_capture._capture_path is None


def test_ordinary_non_debug_release_does_not_open_native_fault_companion(
    tmp_path: Path, monkeypatch
) -> None:
    crash_capture.close_diagnostic_crash_capture()
    monkeypatch.setattr(crash_capture, "is_diagnostic_build", lambda: False)

    path = crash_capture.enable_diagnostic_crash_capture(tmp_path, allow_runtime_capture=False)

    assert path is None
    assert not (tmp_path / "native_faults.log").exists()
    assert crash_capture._capture_enabled is False
    assert crash_capture._stream is None
    assert crash_capture._capture_path is None


def test_main_capture_policy_covers_source_and_debug_but_excludes_plain_compiled_release() -> None:
    source = (Path(__file__).parents[1] / "main.py").read_text()
    assert "or not is_compiled_runtime()" in source
    assert "or logging_profile.debug" in source
    assert "or logging_profile.verbose" in source
    assert "allow_runtime_capture=bool(" in source
    assert "[NATIVE_FAULT_CAPTURE]" in source
