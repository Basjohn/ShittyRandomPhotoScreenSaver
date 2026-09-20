"""One event-driven Core Audio endpoint owner shared by active UI-generation leases.

An active GUI thread owns at most one CoreAudioEventSession regardless of
how many displays, Media generations or future OSD presenters subscribe. An
inactive process imports no pycaw/comtypes or Qt audio bridge, and has no
recurring audio poll. Callbacks reach the retained GUI bridge before they fan
out to owners; endpoint writes use that same registered COM endpoint.
"""
from __future__ import annotations

import threading
from typing import Callable

from core.media.audio_event_session import AudioEventState, CoreAudioEventSession


_SESSION_BY_THREAD: dict[int, "SharedCoreAudioSource"] = {}


class SharedCoreAudioSource:
    """One per-UI-apartment source with explicit subscriber/endpoint lifetime."""

    def __init__(self, *, session_factory=CoreAudioEventSession) -> None:
        self._owner_thread = threading.get_ident()
        self._session_factory = session_factory
        self._session: CoreAudioEventSession | None = None
        self._subscribers: dict[int, Callable[[AudioEventState], None]] = {}
        self._next_id = 0
        self._state: AudioEventState | None = None

    def _require_owner(self) -> None:
        if threading.get_ident() != self._owner_thread:
            raise RuntimeError("Core Audio source lifetime and actions require its GUI apartment")

    def subscribe(self, callback: Callable[[AudioEventState], None]) -> int | None:
        self._require_owner()
        if self._session is None:
            session = self._session_factory(publish=self._publish)
            # Assign before start: some correctly synchronous fake sources can
            # publish the initial read before start() returns.
            self._session = session
            try:
                started = session.start()
            except Exception:
                self._session = None
                self._state = None
                session.retire()
                raise
            if not started:
                self._session = None
                self._state = None
                session.retire()
                return None
        self._next_id += 1
        subscriber_id = self._next_id
        self._subscribers[subscriber_id] = callback
        if self._state is not None:
            try:
                callback(self._state)
            except Exception:
                # A failed late-subscriber replay must not strand a callback
                # lease whose id was never returned to its consumer.
                self.unsubscribe(subscriber_id)
                raise
        return subscriber_id

    def unsubscribe(self, subscriber_id: int) -> None:
        self._require_owner()
        self._subscribers.pop(subscriber_id, None)
        if self._subscribers:
            return
        session, self._session = self._session, None
        self._state = None
        if session is not None:
            session.retire()
        if _SESSION_BY_THREAD.get(self._owner_thread) is self:
            _SESSION_BY_THREAD.pop(self._owner_thread, None)

    def _publish(self, state: AudioEventState) -> None:
        self._require_owner()
        if self._session is None:
            # During initial session.start the snapshot is queued, not emitted
            # synchronously. Keep this guard for a fake/abnormal transport.
            return
        self._state = state
        for callback in tuple(self._subscribers.values()):
            try:
                callback(state)
            except Exception:
                # One expired presentation must not block other display leases.
                # Consumer-level delivery owns its own detailed diagnostics.
                pass

    @property
    def current_state(self) -> AudioEventState | None:
        return self._state

    def toggle_mute(self) -> bool | None:
        self._require_owner()
        return self._session.toggle_mute() if self._session is not None else None

    def step_volume(self, delta: float) -> float | None:
        self._require_owner()
        return self._session.step_volume(delta) if self._session is not None else None

    def request_snapshot(self) -> bool:
        self._require_owner()
        return bool(self._session is not None and self._session.request_snapshot())


def _shared_source() -> SharedCoreAudioSource:
    thread_id = threading.get_ident()
    source = _SESSION_BY_THREAD.get(thread_id)
    if source is None:
        source = SharedCoreAudioSource()
        _SESSION_BY_THREAD[thread_id] = source
    return source


class SharedCoreAudioBackend:
    """One consumer-generation lease; neither a new endpoint nor a poller."""

    def __init__(self) -> None:
        self._source: SharedCoreAudioSource | None = None
        self._subscriber_id: int | None = None
        self._state: AudioEventState | None = None

    def start(self, publish: Callable[[AudioEventState], None]) -> bool:
        if self._subscriber_id is not None:
            return True
        source = _shared_source()

        def receive(state: AudioEventState) -> None:
            self._state = state
            publish(state)

        try:
            subscriber_id = source.subscribe(receive)
        except Exception:
            if not source._subscribers:
                _SESSION_BY_THREAD.pop(source._owner_thread, None)
            raise
        if subscriber_id is None:
            if not source._subscribers:
                _SESSION_BY_THREAD.pop(source._owner_thread, None)
            return False
        self._source = source
        self._subscriber_id = subscriber_id
        return True

    def stop(self) -> None:
        source, subscriber_id = self._source, self._subscriber_id
        # Verify apartment / unsubscribe *before* clearing the only retained
        # source reference. A rejected wrong-thread call must remain retryable
        # by the legitimate GUI owner, not orphan a live COM registration.
        if source is not None and subscriber_id is not None:
            source.unsubscribe(subscriber_id)
        self._source = None
        self._subscriber_id = None
        self._state = None

    def is_available(self) -> bool:
        return bool(self._state is not None and self._state.available)

    def request_snapshot(self) -> bool:
        return bool(self._source is not None and self._source.request_snapshot())

    def toggle_mute(self) -> bool | None:
        return self._source.toggle_mute() if self._source is not None else None

    def step_volume(self, delta: float) -> float | None:
        return self._source.step_volume(delta) if self._source is not None else None

    @property
    def current_state(self) -> AudioEventState | None:
        return self._state


def active_shared_audio_source_count() -> int:
    """Diagnostic for lifetime/cardinality tests, not a runtime polling hook."""
    return sum(bool(source._subscribers) for source in _SESSION_BY_THREAD.values())
