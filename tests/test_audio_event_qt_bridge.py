"""Real Qt queue tests; NO Core Audio device is opened by this test."""
from __future__ import annotations

import threading

from PySide6.QtCore import QCoreApplication

from core.media.audio_event_session import CoreAudioEventSession
from core.media.audio_qt_wake import AudioEventQtBridge


def test_one_wake_for_burst_and_ui_thread_only_delivery(qt_app):
    ui_thread = threading.get_ident()
    results = []
    bridge = AudioEventQtBridge(lambda snapshot: results.append(
        (snapshot.volume, snapshot.muted, threading.get_ident())))
    post_count = []
    original_post = bridge.mailbox._post_wake
    bridge.mailbox._post_wake = lambda: post_count.append(1) or original_post()

    def callback_thread():
        for i in range(300):
            assert bridge.mailbox.push_volume(0, i / 299, bool(i % 2))

    try:
        sender = threading.Thread(target=callback_thread)
        sender.start(); sender.join()
        assert len(post_count) == 1 and results == []
        QCoreApplication.processEvents()
        assert results == [(1.0, True, ui_thread)]
        # A repeated effective value after delivery is not a second UI event.
        for _ in range(300):
            assert bridge.mailbox.push_volume(0, 1.0, True)
        assert len(post_count) == 1
        QCoreApplication.processEvents()
        assert results == [(1.0, True, ui_thread)]
        assert bridge.mailbox.push_device_change()
        assert len(post_count) == 2
        QCoreApplication.processEvents()
        assert results == [(1.0, True, ui_thread), (None, None, ui_thread)]
        assert not bridge.mailbox.push_volume(0, 0.1, False)
        assert bridge.mailbox.finish_handover(1)
        assert bridge.mailbox.push_volume(1, 0.1, False)
        assert len(post_count) == 3
        bridge.close()
        QCoreApplication.processEvents()
        # The second-endpoint update was queued but never delivered after close.
        assert results == [(1.0, True, ui_thread), (None, None, ui_thread)]
    finally:
        bridge.close()
        bridge.deleteLater()


def test_real_qt_queue_retains_one_session_through_burst_device_change_and_retire(qt_app):
    """Use the actual queued Qt bridge with a fake, read-only COM transport."""
    ui_thread = threading.get_ident()
    states, probes = [], []

    class Probe:
        def __init__(self, on_volume, on_default_device, initial):
            self.on_volume = on_volume
            self.on_default_device = on_default_device
            self.initial = initial
            self.starts = self.stops = 0

        def start(self):
            self.starts += 1
            return True

        def stop(self):
            self.stops += 1

        def snapshot(self):
            return self.initial

    def probe_factory(*, on_volume, on_default_device):
        initial = [(0.25, False), (0.6, True)][len(probes)]
        probe = Probe(on_volume, on_default_device, initial)
        probes.append(probe)
        return probe

    session = CoreAudioEventSession(
        publish=lambda state: states.append((state, threading.get_ident())),
        probe_factory=probe_factory,
    )
    try:
        assert session.start() and session.start()
        assert len(probes) == 1 and probes[0].starts == 1
        QCoreApplication.processEvents()
        assert len(states) == 1 and states[0][0].volume == 0.25
        assert states[0][1] == ui_thread

        def burst():
            for i in range(1000):
                probes[0].on_volume(i / 999, bool(i % 2))

        sender = threading.Thread(target=burst)
        sender.start(); sender.join()
        assert len(states) == 1
        QCoreApplication.processEvents()
        assert len(states) == 2 and states[-1][0].volume == 1.0
        assert states[-1][0].muted and states[-1][1] == ui_thread

        old = probes[0]
        sender = threading.Thread(target=old.on_default_device)
        sender.start(); sender.join()
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()  # Snapshot wake may be posted by handover.
        assert old.stops == 1 and len(probes) == 2
        assert [(state.available, state.endpoint_token) for state, _ in states[-2:]] == [
            (False, 1), (True, 1)
        ]
        assert states[-1][0].volume == 0.6 and states[-1][0].muted
        assert all(owner == ui_thread for _, owner in states)
        count = len(states)
        old.on_volume(0.01, False)
        QCoreApplication.processEvents()
        assert len(states) == count  # A late old-endpoint callback is inert.
        probes[1].on_volume(0.7, False)
        session.retire()  # A queued new-endpoint notification cannot outlive its owner.
        QCoreApplication.processEvents()
        assert len(states) == count and probes[1].stops == 1
    finally:
        session.retire()


def test_real_qt_media_generations_share_one_event_source_through_switch_and_retire(
    qt_app, monkeypatch,
):
    """Exercise the production Media lease path through an actual queued Qt wake."""
    from core.media import audio_shared_source as audio_source
    from widgets.system_mute_runtime import (
        SystemMuteRuntimeService,
        reset_shared_system_mute_runtime_for_tests,
    )

    ui_thread = threading.get_ident()
    probes = []
    source_type = audio_source.SharedCoreAudioSource

    class FakeProbe:
        def __init__(self, *, on_volume, on_default_device):
            self.on_volume = on_volume
            self.on_default_device = on_default_device
            self.stops = 0
            self.current = [(0.2, False), (0.7, True)][len(probes)]
            probes.append(self)

        def start(self):
            return True

        def stop(self):
            self.stops += 1

        def snapshot(self):
            return self.current

        def set_mute(self, muted):
            self.current = (self.current[0], bool(muted))
            self.on_volume(*self.current)
            return True

        def set_volume(self, level):
            self.current = (float(level), self.current[1])
            self.on_volume(*self.current)
            return True

    def session_factory(*, publish):
        return CoreAudioEventSession(publish=publish, probe_factory=FakeProbe)

    monkeypatch.setattr(
        audio_source, "SharedCoreAudioSource",
        lambda: source_type(session_factory=session_factory),
    )

    class Consumer:
        def __init__(self, generation, manager):
            self._runtime_generation = generation
            self._thread_manager = manager
            self.received = []

        def is_system_mute_consumer_alive(self):
            return True

        def on_system_mute_runtime_snapshot(self, state):
            self.received.append((state, threading.get_ident()))

    def attach(consumer):
        service = SystemMuteRuntimeService(shared=True)
        service.set_thread_manager(consumer._thread_manager)
        service.attach_consumer(consumer)
        assert service.start()
        return service

    reset_shared_system_mute_runtime_for_tests()
    manager = object()
    a, b = Consumer(10, manager), Consumer(11, manager)
    first = second = None
    try:
        first = attach(a)
        second = attach(b)
        assert len(probes) == 1 and audio_source.active_shared_audio_source_count() == 1
        QCoreApplication.processEvents()
        assert a.received[-1][0].volume == b.received[-1][0].volume == 0.2
        assert all(owner == ui_thread for consumer in (a, b)
                   for _, owner in consumer.received)

        def external_burst():
            for i in range(500):
                probes[0].on_volume(i / 499, False)

        worker = threading.Thread(target=external_burst)
        worker.start(); worker.join()
        QCoreApplication.processEvents()
        assert a.received[-1][0].volume == b.received[-1][0].volume == 1.0
        assert first.request_refresh(force=True)
        # Explicit request reads current endpoint, not a process-global peer.
        QCoreApplication.processEvents()
        assert a.received[-1][0].volume == 0.2
        assert b.received[-1][0].volume == 0.2

        probes[0].on_default_device()
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        assert len(probes) == 2 and probes[0].stops == 1
        assert a.received[-1][0].volume == b.received[-1][0].volume == 0.7
        old_count = len(a.received)
        probes[0].on_volume(0.01, False)
        QCoreApplication.processEvents()
        assert len(a.received) == old_count

        first.retire()
        assert audio_source.active_shared_audio_source_count() == 1
        assert second.toggle_mute()
        QCoreApplication.processEvents()
        assert b.received[-1][0].muted is False
        assert len(a.received) == old_count
        second.retire()
        assert probes[1].stops == 1
        assert audio_source.active_shared_audio_source_count() == 0
    finally:
        if first is not None:
            first.retire()
        if second is not None:
            second.retire()
        reset_shared_system_mute_runtime_for_tests()
