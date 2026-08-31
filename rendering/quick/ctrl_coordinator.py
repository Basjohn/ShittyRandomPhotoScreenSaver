"""Authoritative event-driven cross-display Ctrl-state coordinator (H).

Each display publishes only its own Ctrl-held contribution.  The coordinator
computes the global OR and pushes changes to every live generation-scoped input
controller.  No display needs to poll a provider from mouse-move handling.
"""

from __future__ import annotations

from collections.abc import Callable


class SharedCtrlCoordinator:
    """One authoritative OR-of-displays Ctrl-held truth for a display set."""

    def __init__(self) -> None:
        self._by_display: dict[object, bool] = {}
        self._listeners: dict[object, Callable[[bool], object]] = {}
        self._last_global_held = False

    def is_held(self) -> bool:
        """Return whether Ctrl is currently held on any contributing display."""

        return any(self._by_display.values())

    def publisher_for(self, display_key: object) -> Callable[[bool], None]:
        """Return a publisher that records one display's own state and broadcasts."""

        def publish(held: bool) -> None:
            self._by_display[display_key] = bool(held)
            self._broadcast_if_changed()

        return publish

    def subscribe(
        self,
        display_key: object,
        listener: Callable[[bool], object],
    ) -> None:
        """Bind one live display input owner to event-driven global Ctrl truth."""

        self._listeners[display_key] = listener
        listener(self.is_held())

    def unsubscribe(self, display_key: object) -> None:
        self._listeners.pop(display_key, None)

    def is_display_held(self, display_key: object) -> bool:
        """Return one display's last-published Ctrl-held contribution."""

        return bool(self._by_display.get(display_key, False))

    def forget(self, display_key: object) -> None:
        """Drop one retired display from both contribution and listener sets."""

        self._listeners.pop(display_key, None)
        self._by_display.pop(display_key, None)
        self._broadcast_if_changed()

    def reset(self) -> None:
        """Clear every contribution/listener (terminal teardown of display set)."""

        self._by_display.clear()
        self._listeners.clear()
        self._last_global_held = False

    @property
    def contributing_display_count(self) -> int:
        return len(self._by_display)

    @property
    def listener_count(self) -> int:
        return len(self._listeners)

    def _broadcast_if_changed(self) -> None:
        held = self.is_held()
        if held == self._last_global_held:
            return
        self._last_global_held = held
        for display_key, listener in tuple(self._listeners.items()):
            try:
                listener(held)
            except RuntimeError:
                # A generation can retire while a sibling's key event is being
                # admitted. Drop the stale listener; do not retain dead QObjects.
                self._listeners.pop(display_key, None)


__all__ = ["SharedCtrlCoordinator"]
