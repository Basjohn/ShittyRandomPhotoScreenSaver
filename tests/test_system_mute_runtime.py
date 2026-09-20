"""Shared event-driven Media audio ownership, with no Core Audio device access."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from core.media.audio_event_session import AudioEventState
from widgets.system_mute_runtime import (
    SystemMuteRuntimeService,
    reset_shared_system_mute_runtime_for_tests,
    shared_system_mute_owner_count,
)


def test_registry_import_is_system_audio_implementation_dormant_in_fresh_process():
    proc = subprocess.run(
        [sys.executable, "-c", '''import json,sys
import rendering.widget_runtime_services
forbidden={"widgets.system_mute_runtime", "core.media.system_mute", "core.media.audio_qt_wake", "pycaw", "comtypes"}
print(json.dumps(sorted(forbidden & set(sys.modules))))'''],
        cwd=Path.cwd(), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


class _Backend:
    def __init__(self):
        self.available = True
        self.muted = False
        self.volume = 0.5
        self.callback = None
        self.starts = self.stops = self.refreshes = self.toggle_calls = 0
        self.step_calls = []
        self.revision = 0
        self.token = 0

    def start(self, callback):
        self.starts += 1
        self.callback = callback
        self.emit(source="initial")
        return True

    def stop(self):
        self.stops += 1
        self.callback = None

    def emit(self, *, source="notification", endpoint_token=None):
        self.revision += 1
        token = self.token if endpoint_token is None else endpoint_token
        event = AudioEventState(
            revision=self.revision, available=self.available,
            volume=self.volume if self.available else None,
            muted=self.muted if self.available else None,
            endpoint_token=token, source=source,
        )
        if self.callback:
            self.callback(event)
        return event

    def request_snapshot(self):
        self.refreshes += 1
        self.emit(source="requested_snapshot")
        return self.available

    def toggle_mute(self):
        self.toggle_calls += 1
        if not self.available:
            return None
        self.muted = not self.muted
        self.emit()
        return self.muted

    def step_volume(self, delta):
        self.step_calls.append(float(delta))
        if not self.available:
            return None
        self.volume = max(0.0, min(1.0, self.volume + float(delta)))
        self.emit()
        return self.volume


class _BackendFactory:
    def __init__(self):
        self.backends = []

    def __call__(self):
        backend = _Backend()
        self.backends.append(backend)
        return backend


class _Consumer:
    def __init__(self, thread_manager, generation=81):
        self._thread_manager = thread_manager
        self._runtime_generation = generation
        self.alive = True
        self.snapshots = []

    def is_system_mute_consumer_alive(self):
        return self.alive

    def on_system_mute_runtime_snapshot(self, snapshot):
        self.snapshots.append(snapshot)


def _lease(consumer, factory, *, shared=True):
    service = SystemMuteRuntimeService(shared=shared, backend_factory=factory)
    service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    return service


@pytest.fixture(autouse=True)
def _isolated_audio_owners():
    reset_shared_system_mute_runtime_for_tests()
    yield
    reset_shared_system_mute_runtime_for_tests()


def test_two_display_leases_share_one_callback_without_poll():
    manager, factory = object(), _BackendFactory()
    first, second = _Consumer(manager), _Consumer(manager)
    a, b = _lease(first, factory), _lease(second, factory)
    assert a.start() and b.start()
    assert shared_system_mute_owner_count() == 1
    assert len(factory.backends) == 1 and factory.backends[0].starts == 1
    assert first.snapshots[-1].volume == second.snapshots[-1].volume == 0.5
    factory.backends[0].muted = True
    factory.backends[0].emit()
    assert first.snapshots[-1].muted and second.snapshots[-1].muted
    assert "single_shot" not in Path("widgets/system_mute_runtime.py").read_text()
    a.retire(); b.retire()
    assert factory.backends[0].stops == 1


def test_first_display_retirement_keeps_endpoint_until_final_active_lease():
    manager, factory = object(), _BackendFactory()
    first, second = _Consumer(manager), _Consumer(manager)
    a, b = _lease(first, factory), _lease(second, factory)
    assert a.start() and b.start()
    owner = a.shared_owner
    a.retire()
    assert not owner.is_retired() and owner.active_consumer_count() == 1
    assert factory.backends[0].stops == 0
    b.retire()
    assert owner.is_retired() and factory.backends[0].stops == 1
    assert shared_system_mute_owner_count() == 0


def test_stop_and_restart_drops_inactive_notifications_and_reattaches_once():
    factory, manager = _BackendFactory(), object()
    consumer = _Consumer(manager)
    lease = _lease(consumer, factory)
    assert lease.start()
    backend = factory.backends[0]
    first_count = len(consumer.snapshots)
    lease.stop()
    backend.muted = True
    backend.emit()
    assert len(consumer.snapshots) == first_count
    assert backend.stops == 1
    assert lease.start() and backend.starts == 2
    assert consumer.snapshots[-1].muted is True
    lease.retire()


def test_retired_generation_cannot_publish_into_new_generation():
    manager, factory = object(), _BackendFactory()
    old_consumer = _Consumer(manager, generation=81)
    old = _lease(old_consumer, factory)
    assert old.start()
    stale_publish = factory.backends[0].callback
    old.retire()
    current_consumer = _Consumer(manager, generation=82)
    current = _lease(current_consumer, factory)
    assert current.start()
    before = len(current_consumer.snapshots)
    stale_publish(AudioEventState(999, True, 0.2, True, 99, "late"))
    assert len(current_consumer.snapshots) == before
    assert current_consumer.snapshots[-1].volume == 0.5
    current.retire()


def test_media_controls_use_same_event_source_and_fan_out_once():
    manager, factory = object(), _BackendFactory()
    first, second = _Consumer(manager), _Consumer(manager)
    a, b = _lease(first, factory), _lease(second, factory)
    assert a.start() and b.start()
    backend = factory.backends[0]
    assert a.toggle_mute()
    assert backend.toggle_calls == 1
    assert first.snapshots[-1].muted and second.snapshots[-1].muted
    assert a.step_system_volume(0.05) == pytest.approx(0.55)
    assert backend.step_calls == [pytest.approx(0.05)]
    assert first.snapshots[-1].volume == pytest.approx(0.55)
    assert second.snapshots[-1].volume == pytest.approx(0.55)
    assert a.request_refresh(force=True, source="native_key")
    assert backend.refreshes == 1
    a.retire(); b.retire()


def test_default_output_switch_and_unavailable_recovery_without_poll():
    factory, manager = _BackendFactory(), object()
    consumer = _Consumer(manager)
    lease = _lease(consumer, factory)
    assert lease.start()
    backend = factory.backends[0]
    backend.available = False
    backend.token = 1
    backend.emit(source="device_handover")
    assert not consumer.snapshots[-1].available
    assert lease.toggle_mute() is False
    assert lease.step_system_volume(0.05) is None
    backend.available = True
    backend.volume = 0.8
    backend.token = 1
    backend.emit(source="device_snapshot")
    assert consumer.snapshots[-1].available
    assert consumer.snapshots[-1].volume == 0.8
    assert backend.starts == 1
    lease.retire()


def test_repeated_or_stale_event_is_not_republished():
    factory, manager = _BackendFactory(), object()
    consumer = _Consumer(manager)
    lease = _lease(consumer, factory)
    assert lease.start()
    backend = factory.backends[0]
    start_count = len(consumer.snapshots)
    backend.emit()
    assert len(consumer.snapshots) == start_count
    backend.token = 2
    backend.emit(source="device_handover")
    after_handover = len(consumer.snapshots)
    stale = AudioEventState(999, True, 0.1, True, 1, "stale_endpoint")
    backend.callback(stale)
    assert len(consumer.snapshots) == after_handover
    lease.retire()


def test_shared_lease_requires_generation_or_thread_manager():
    consumer = type("Consumer", (), {
        "_runtime_generation": None,
        "_thread_manager": None,
        "is_system_mute_consumer_alive": lambda self: True,
        "on_system_mute_runtime_snapshot": lambda self, snapshot: None,
        "parent": lambda self: None,
    })()
    service = SystemMuteRuntimeService(shared=True, backend_factory=_BackendFactory())
    with pytest.raises(RuntimeError, match="requires runtime generation or ThreadManager"):
        service.attach_consumer(consumer)
    assert shared_system_mute_owner_count() == 0


def test_event_source_methods_stay_on_the_owner_ui_thread():
    ui_thread = threading.get_ident()
    calls = []
    class Recording(_Backend):
        def start(self, callback):
            calls.append(threading.get_ident())
            return super().start(callback)
        def stop(self):
            calls.append(threading.get_ident())
            return super().stop()
        def toggle_mute(self):
            calls.append(threading.get_ident())
            return super().toggle_mute()
        def step_volume(self, delta):
            calls.append(threading.get_ident())
            return super().step_volume(delta)
    manager, consumer = object(), _Consumer(object())
    service = SystemMuteRuntimeService(shared=False, backend_factory=Recording)
    service.set_thread_manager(manager)
    service.attach_consumer(consumer)
    assert service.start()
    assert service.toggle_mute()
    assert service.step_system_volume(0.05) == pytest.approx(0.55)
    service.retire()
    assert calls and set(calls) == {ui_thread}
