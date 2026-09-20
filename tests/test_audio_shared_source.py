"""One GUI-apartment Core Audio source even during overlapping display generations."""
from __future__ import annotations

import threading

import pytest

from core.media.audio_event_session import AudioEventState
from core.media import audio_shared_source as module


class FakeSession:
    built = []

    def __init__(self, *, publish):
        self.publish = publish
        self.starts = self.retires = 0
        self.volume = 0.4
        self.muted = False
        self.revision = 0
        self.endpoint_token = 0
        self.__class__.built.append(self)

    def start(self):
        self.starts += 1
        self.emit()
        return True

    def retire(self):
        self.retires += 1

    def emit(self, *, available=True, source="notification"):
        self.revision += 1
        self.publish(AudioEventState(self.revision, available,
                                     self.volume if available else None,
                                     self.muted if available else None,
                                     self.endpoint_token, source))

    def toggle_mute(self):
        self.muted = not self.muted
        self.emit()
        return self.muted

    def step_volume(self, delta):
        self.volume = max(0.0, min(1.0, self.volume + delta))
        self.emit()
        return self.volume

    def request_snapshot(self):
        self.emit()
        return True


@pytest.fixture(autouse=True)
def fake_session_factory(monkeypatch):
    assert module.active_shared_audio_source_count() == 0
    FakeSession.built.clear()
    module._SESSION_BY_THREAD.clear()
    monkeypatch.setattr(module, "SharedCoreAudioSource",
                        lambda: SOURCE_CLASS(session_factory=FakeSession))
    yield
    assert module.active_shared_audio_source_count() == 0
    module._SESSION_BY_THREAD.clear()


SOURCE_CLASS = module.SharedCoreAudioSource


def test_two_generation_leases_share_one_endpoint_and_late_join_receives_snapshot():
    first, second = module.SharedCoreAudioBackend(), module.SharedCoreAudioBackend()
    a, b = [], []
    assert first.start(a.append)
    assert first.start(a.append)
    assert len(FakeSession.built) == 1 and len(a) == 1
    assert second.start(b.append)
    assert module.active_shared_audio_source_count() == 1
    assert len(b) == 1 and b[-1].volume == 0.4
    assert second.step_volume(0.1) == pytest.approx(0.5)
    assert a[-1].volume == b[-1].volume == pytest.approx(0.5)
    first.stop()
    assert FakeSession.built[0].retires == 0
    assert second.toggle_mute() is True
    assert len(a) == 2 and b[-1].muted is True
    second.stop()
    assert FakeSession.built[0].retires == 1
    assert module.active_shared_audio_source_count() == 0


def test_unavailable_device_uses_same_subscription_and_recovers():
    backend = module.SharedCoreAudioBackend()
    values = []
    assert backend.start(values.append)
    session = FakeSession.built[0]
    session.endpoint_token = 1
    session.emit(available=False, source="device_handover")
    assert not backend.is_available() and values[-1].volume is None
    session.volume = 0.7
    session.emit(source="device_snapshot")
    assert backend.is_available() and values[-1].volume == 0.7
    assert len(FakeSession.built) == 1
    backend.stop()


def test_wrong_thread_cannot_unsubscribe_or_write_endpoint():
    backend = module.SharedCoreAudioBackend()
    assert backend.start(lambda *_: None)
    errors = []

    def worker():
        for action in (lambda: backend.step_volume(0.1), backend.stop):
            try:
                action()
            except RuntimeError as error:
                errors.append(str(error))

    thread = threading.Thread(target=worker)
    thread.start(); thread.join()
    assert len(errors) == 2 and all("GUI apartment" in item for item in errors)
    backend.stop()


def test_media_generation_overlap_and_other_display_share_one_native_subscription():
    """Default Media leases consume the *same* retained event-source session."""
    from widgets.system_mute_runtime import (
        SystemMuteRuntimeService,
        reset_shared_system_mute_runtime_for_tests,
    )

    class Consumer:
        def __init__(self, generation, manager):
            self._runtime_generation = generation
            self._thread_manager = manager
            self.snapshots = []

        def is_system_mute_consumer_alive(self):
            return True

        def on_system_mute_runtime_snapshot(self, snapshot):
            self.snapshots.append(snapshot)

    def lease(consumer):
        service = SystemMuteRuntimeService(shared=True)
        service.set_thread_manager(consumer._thread_manager)
        service.attach_consumer(consumer)
        assert service.start()
        return service

    manager = object()
    first, second = Consumer(81, manager), Consumer(81, manager)
    replacement = Consumer(82, manager)
    try:
        a, b = lease(first), lease(second)
        c = lease(replacement)
        assert len(FakeSession.built) == 1
        assert module.active_shared_audio_source_count() == 1
        FakeSession.built[0].volume = 0.85
        FakeSession.built[0].emit()
        assert all(person.snapshots[-1].volume == 0.85
                   for person in (first, second, replacement))
        a.retire(); b.retire()
        assert FakeSession.built[0].retires == 0
        assert c.toggle_mute()
        assert replacement.snapshots[-1].muted
        c.retire()
        assert FakeSession.built[0].retires == 1
        assert module.active_shared_audio_source_count() == 0
    finally:
        reset_shared_system_mute_runtime_for_tests()
