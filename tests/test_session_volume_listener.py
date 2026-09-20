"""Pure event/lifetime tests for the selected-session COM adapter."""
from __future__ import annotations

import threading

from core.media.audio_event_mailbox import AudioEventMailbox
from core.media.session_volume_listener import SessionVolumeListener


class _Bridge:
    def __init__(self, deliver):
        self.wakes = 0
        self.mailbox = AudioEventMailbox(post_wake=self._wake, deliver=deliver)

    def _wake(self):
        self.wakes += 1
        return True

    def close(self):
        self.mailbox.retire()


class _Events:
    pass


class _Session:
    def __init__(self, name):
        self.Process = type("Process", (), {"name": lambda _self: name})()
        self.callback = None
        self.registrations = 0
        self.unregistrations = 0

    def register_notification(self, callback):
        self.callback = callback
        self.registrations += 1

    def unregister_notification(self):
        self.unregistrations += 1
        self.callback = None


def _listener(sessions):
    updates, disconnected, bridges = [], [], []

    def bridge_factory(deliver):
        bridge = _Bridge(deliver)
        bridges.append(bridge)
        return bridge

    listener = SessionVolumeListener(
        on_volume=lambda level, muted: updates.append((level, muted)),
        on_disconnected=lambda: disconnected.append(True),
        bridge_factory=bridge_factory,
        sessions_factory=lambda: sessions,
        events_factory=_Events,
    )
    return listener, updates, disconnected, bridges


def test_selected_session_burst_duplicate_retirement_and_stale_notifications():
    target = _Session("Spotify.exe")
    unrelated = _Session("Discord.exe")
    listener, updates, _, bridges = _listener([unrelated, target])
    assert listener.start(("spotify.exe",))
    assert listener.start(("spotify.exe",))
    assert target.registrations == 1
    callback = target.callback
    for n in range(1000):
        callback.on_simple_volume_changed(n / 999, False, None)
    assert bridges[0].wakes == 1
    bridges[0].mailbox.drain()
    assert updates == [(1.0, False)]
    callback.on_simple_volume_changed(1.0, False, None)
    assert bridges[0].wakes == 1
    listener.close()
    assert target.unregistrations == 1
    callback.on_simple_volume_changed(0.4, False, None)
    assert bridges[0].mailbox.drain() is False
    assert updates == [(1.0, False)]


def test_session_disconnect_retires_selected_binding():
    target = _Session("MusicBee.exe")
    listener, updates, disconnected, bridges = _listener([target])
    assert listener.start(("musicbee.exe",))
    callback = target.callback
    callback.on_session_disconnected("DeviceRemoval", 0)
    bridges[0].mailbox.drain()
    assert disconnected == [True]
    assert target.unregistrations == 1
    assert not listener.active
    callback.on_simple_volume_changed(0.8, False, None)
    assert updates == []


def test_ambiguous_browser_session_is_not_selected():
    listener, _, _, bridges = _listener([_Session("chrome.exe"), _Session("chrome.exe")])
    assert not listener.start(("chrome.exe",))
    assert bridges == []
    listener.close()


def test_absent_session_stays_dormant_and_wrong_thread_cannot_retire():
    listener, _, _, bridges = _listener([])
    assert not listener.start(("spotify.exe",))
    assert bridges == []
    errors = []

    def other_thread():
        try:
            listener.close()
        except RuntimeError as error:
            errors.append(str(error))

    worker = threading.Thread(target=other_thread)
    worker.start()
    worker.join()
    assert len(errors) == 1
    listener.close()


def test_application_owned_event_context_is_suppressed_without_hiding_external_changes():
    from core.media.audio_event_context import SESSION_VOLUME_EVENT_CONTEXT

    target = _Session("Spotify.exe")
    listener, updates, _, bridges = _listener([target])
    assert listener.start(("spotify.exe",))
    callback = target.callback
    callback.on_simple_volume_changed(0.6, False, SESSION_VOLUME_EVENT_CONTEXT)
    assert bridges[0].wakes == 0
    callback.on_simple_volume_changed(0.35, False, None)
    bridges[0].mailbox.drain()
    assert updates == [(0.35, False)]
    listener.close()


def test_selected_session_discovery_is_admission_only_and_notification_bursts_do_not_scan():
    """The native session list must never be queried from audio callbacks or GUI wakes."""
    target = _Session("Spotify.exe")
    enumerations = []
    bridges = []

    def sessions_factory():
        enumerations.append(True)
        return [target]

    def bridge_factory(deliver):
        bridge = _Bridge(deliver)
        bridges.append(bridge)
        return bridge

    listener = SessionVolumeListener(
        on_volume=lambda _level, _muted: None,
        on_disconnected=lambda: None,
        bridge_factory=bridge_factory,
        sessions_factory=sessions_factory,
        events_factory=_Events,
    )
    try:
        assert listener.start(("spotify.exe",))
        assert listener.start(("spotify.exe",))
        assert len(enumerations) == 1
        callback = target.callback
        for value in range(1000):
            callback.on_simple_volume_changed(value / 999, False, None)
        assert bridges[0].wakes == 1
        bridges[0].mailbox.drain()
        assert len(enumerations) == 1
        assert target.registrations == 1
    finally:
        listener.close()
    assert target.unregistrations == 1
