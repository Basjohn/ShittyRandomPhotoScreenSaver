"""Opt-in, event-only observer for one selected Windows audio session.

Registration, session selection and unregistration run on the GUI COM apartment.
COM notifications copy scalars into one retained Qt mailbox and never touch QML.
No session enumeration occurs during render, callback delivery or on a timer.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from core.media.audio_event_mailbox import AudioNotification
from core.media.audio_event_context import is_owned_session_volume_event


class SessionVolumeListener:
    """One session subscription per active shared Media volume owner."""

    def __init__(
        self,
        *,
        on_volume: Callable[[float, bool], None],
        on_disconnected: Callable[[], None],
        bridge_factory: Callable[..., Any] | None = None,
        sessions_factory: Callable[[], Any] | None = None,
        events_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._thread = threading.get_ident()
        self._on_volume = on_volume
        self._on_disconnected = on_disconnected
        if bridge_factory is None:
            from core.media.audio_qt_wake import AudioEventQtBridge
            bridge_factory = AudioEventQtBridge
        self._bridge_factory = bridge_factory
        self._sessions_factory = sessions_factory
        self._events_factory = events_factory
        self._bridge = None
        self._session = None
        self._callback = None
        self._closed = False

    def _require_owner(self) -> None:
        if threading.get_ident() != self._thread:
            raise RuntimeError("audio-session COM lifecycle requires the owning GUI apartment")

    @property
    def active(self) -> bool:
        return self._session is not None and not self._closed

    def start(self, process_targets: tuple[str, ...]) -> bool:
        self._require_owner()
        if self._closed or self._session is not None:
            return self.active
        targets = tuple(dict.fromkeys(str(name).strip().casefold() for name in process_targets if name))
        if not targets:
            return False
        if self._sessions_factory is None:
            from pycaw.pycaw import AudioUtilities
            sessions_factory = AudioUtilities.GetAllSessions
        else:
            sessions_factory = self._sessions_factory
        if self._events_factory is None:
            from pycaw.callbacks import AudioSessionEvents
            events_factory = AudioSessionEvents
        else:
            events_factory = self._events_factory
        # Only resolve at explicit activation/source change, never from callbacks.
        sessions = sessions_factory()
        selected = None
        for target in targets:
            matches = []
            for session in sessions:
                try:
                    process = session.Process
                    name = process.name().casefold() if process is not None else ""
                except Exception:
                    continue
                if name == target:
                    matches.append(session)
            # Do not arbitrarily attach to a different browser tab/session.
            if len(matches) > 1:
                return False
            if matches:
                selected = matches[0]
                break
        if selected is None:
            return False
        bridge = self._bridge_factory(self._consume)
        token = bridge.mailbox.endpoint_token
        mailbox = bridge.mailbox

        class SelectedSessionEvents(events_factory):
            def on_simple_volume_changed(self, new_volume, new_mute, event_context):
                # The COM callback may run on another thread. Only copy scalars.
                if not is_owned_session_volume_event(event_context):
                    mailbox.push_volume(token, float(new_volume), bool(new_mute))

            def on_session_disconnected(self, disconnect_reason, disconnect_reason_id):
                mailbox.push_device_change()

        callback = SelectedSessionEvents()
        try:
            selected.register_notification(callback)
        except Exception:
            bridge.close()
            raise
        self._bridge = bridge
        self._session = selected
        self._callback = callback
        return True

    def _consume(self, event: AudioNotification) -> None:
        self._require_owner()
        if self._closed:
            return
        if event.kind == "volume" and self._session is not None:
            self._on_volume(float(event.volume), bool(event.muted))
        elif event.kind == "device":
            # Disconnect retires the old binding; the existing media-source
            # lifecycle can explicitly admit a new one on its next source event.
            self.stop()
            self._on_disconnected()

    def stop(self) -> None:
        self._require_owner()
        session, bridge = self._session, self._bridge
        self._session = self._callback = self._bridge = None
        if bridge is not None:
            bridge.close()  # Fence any late COM callback before unregistration.
        if session is not None:
            try:
                session.unregister_notification()
            except Exception:
                # The session may already have disconnected and released its
                # native control. The callback and mailbox are already fenced.
                pass

    def close(self) -> None:
        self._require_owner()
        if self._closed:
            return
        self._closed = True
        self.stop()
