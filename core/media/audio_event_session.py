"""One retained Core Audio session, one latest-value mailbox and one GUI wake.

The shared system-audio owner admits this only while a Media or future OSD
consumer is active. It owns endpoint actions, callback registration and
unregistration on one GUI/COM apartment, without polling or per-event QObjects.
"""
from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any, Callable

from core.media.audio_event_mailbox import AudioNotification
from core.media.core_audio_callback_probe import CoreAudioCallbackProbe


@dataclass(frozen=True, slots=True)
class AudioEventState:
    revision: int
    available: bool
    volume: float | None
    muted: bool | None
    endpoint_token: int
    source: str


def _create_qt_bridge(deliver):
    from core.media.audio_qt_wake import AudioEventQtBridge
    return AudioEventQtBridge(deliver)


class CoreAudioEventSession:
    """GUI-apartment owner for the opt-in notification transport."""

    def __init__(
        self,
        *,
        publish: Callable[[AudioEventState], None],
        bridge_factory: Callable[[Callable[[AudioNotification], None]], Any] = _create_qt_bridge,
        probe_factory: Callable[..., Any] = CoreAudioCallbackProbe,
    ) -> None:
        self._ui_thread = threading.get_ident()
        self._publish = publish
        self._bridge_factory = bridge_factory
        self._probe_factory = probe_factory
        self._bridge = None
        self._probe = None
        self._bound_token: int | None = None
        self._retired = False
        self._revision = 0
        self._state: AudioEventState | None = None

    def _require_ui(self):
        if threading.get_ident() != self._ui_thread:
            raise RuntimeError("Core Audio event session must run on its GUI/COM apartment")

    def start(self) -> bool:
        self._require_ui()
        if self._retired:
            return False
        if self._bridge is not None:
            return True
        self._bridge = self._bridge_factory(self._consume)
        token = self._bridge.mailbox.endpoint_token
        if not self._bind(token):
            self.retire()
            return False
        self._initial_snapshot(token, source="initial")
        return True

    def _bind(self, token: int) -> bool:
        bridge = self._bridge
        if bridge is None:
            return False
        mailbox = bridge.mailbox
        probe = self._probe_factory(
            on_volume=lambda volume, muted: mailbox.push_volume(token, volume, muted),
            on_default_device=mailbox.push_device_change,
        )
        try:
            if not probe.start():
                probe.stop()
                return False
        except Exception:
            probe.stop()
            return False
        self._probe = probe
        self._bound_token = token
        return True

    def _initial_snapshot(self, token: int, *, source: str) -> None:
        probe = self._probe
        mailbox = self._bridge.mailbox
        try:
            snapshot = probe.snapshot() if probe is not None else None
        except Exception:
            snapshot = None
        if snapshot is None:
            self._emit(None, None, token=token, source=source)
        else:
            # Publish via the same bounded mailbox, not an independent delivery
            # path that could race with an already queued COM notification.
            mailbox.push_volume(token, snapshot[0], snapshot[1])

    def _consume(self, item: AudioNotification) -> None:
        self._require_ui()
        if self._retired or self._bridge is None:
            return
        mailbox = self._bridge.mailbox
        if item.endpoint_token != mailbox.endpoint_token:
            return
        if item.kind == "volume":
            self._emit(item.volume, item.muted,
                       token=item.endpoint_token, source="notification")
            return
        if item.kind != "device":
            return
        old = self._probe
        self._probe = None
        self._bound_token = None
        if old is not None:
            old.stop()
        self._emit(None, None, token=item.endpoint_token, source="device_handover")
        rebound = self._bind(item.endpoint_token)
        # Even when no speakers are available, re-arm device notifications.
        # The real transport retains its enumerator registration without an
        # active volume endpoint and the next default-output event can rebind.
        if mailbox.finish_handover(item.endpoint_token) and rebound:
            self._initial_snapshot(item.endpoint_token, source="device_snapshot")

    def _emit(self, volume: float | None, muted: bool | None,
              *, token: int, source: str) -> None:
        self._require_ui()
        available = volume is not None and muted is not None
        state = self._state
        if state is not None and (state.available, state.volume, state.muted,
                                  state.endpoint_token) == (available, volume, muted, token):
            return
        self._revision += 1
        next_state = AudioEventState(self._revision, available,
                                     volume if available else None,
                                     muted if available else None,
                                     token, source)
        self._state = next_state
        self._publish(next_state)

    def _active_probe(self):
        self._require_ui()
        bridge = self._bridge
        if (self._retired or bridge is None or self._probe is None or
                self._bound_token is None or
                not bridge.mailbox.accepts_endpoint_actions(self._bound_token)):
            return None
        return self._probe

    def request_snapshot(self) -> bool:
        """One explicit owner-requested read; no interval timer or background poll."""
        probe = self._active_probe()
        if probe is None:
            return False
        token = self._bound_token
        snapshot = probe.snapshot()
        if snapshot is None:
            self._emit(None, None, token=token, source="requested_snapshot")
            return False
        return self._bridge.mailbox.push_volume(token, snapshot[0], snapshot[1])

    def toggle_mute(self) -> bool | None:
        """Write through this session's existing endpoint, never a second COM owner."""
        probe = self._active_probe()
        if probe is None:
            return None
        snapshot = probe.snapshot()
        if snapshot is None:
            return None
        next_mute = not bool(snapshot[1])
        if not probe.set_mute(next_mute):
            return None
        self.request_snapshot()
        return next_mute

    def step_volume(self, delta: float) -> float | None:
        """One user-requested volume step; published by the bounded event mailbox."""
        probe = self._active_probe()
        if probe is None:
            return None
        snapshot = probe.snapshot()
        if snapshot is None:
            return None
        target = max(0.0, min(1.0, float(snapshot[0]) + float(delta)))
        if not probe.set_volume(target):
            return None
        updated = probe.snapshot()
        if updated is None or self._active_probe() is not probe:
            return None
        # Reuse the post-write read for both return value and UI admission;
        # another request_snapshot() would query the same COM endpoint twice.
        self._bridge.mailbox.push_volume(self._bound_token, updated[0], updated[1])
        return float(updated[0])

    def retire(self) -> None:
        self._require_ui()
        if self._retired:
            return
        self._retired = True
        bridge, probe = self._bridge, self._probe
        self._bridge = None
        self._probe = None
        self._bound_token = None
        if bridge is not None:
            bridge.mailbox.retire()
        try:
            if probe is not None:
                probe.stop()
        finally:
            if bridge is not None:
                bridge.close()
                # One bridge per *source admission*, not per event. Close its
                # signal immediately and retire the QObject on its GUI owner;
                # repeated enable/disable cycles must not accumulate bridges.
                defer_delete = getattr(bridge, "deleteLater", None)
                if callable(defer_delete):
                    defer_delete()

    @property
    def current_state(self) -> AudioEventState | None:
        return self._state
