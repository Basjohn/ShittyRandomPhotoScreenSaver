"""Authoritative cross-display Ctrl-state coordinator (H).

Each display's input owner publishes only its own Ctrl-held state; the global
provider answers whether Ctrl is held on *any* live display. This is the single
authoritative shared truth that fixed the G8 cross-display stuck-Ctrl defect:
a display that never releases Ctrl before focus moves cannot leave a second
display's local truth stuck, because the second display's
``QuickInputController`` consults this provider authoritatively.

The coordinator hands each display a bound ``(provider, publisher)`` pair:

- ``held_provider`` -> ``() -> bool`` : Ctrl held on any display;
- ``publisher_for(display_key)`` -> ``(bool) -> None`` : that display's own state.

When a display generation retires, ``forget(display_key)`` drops its
contribution so a retired display cannot pin Ctrl held forever.
"""

from __future__ import annotations

from collections.abc import Callable


class SharedCtrlCoordinator:
    """One authoritative OR-of-displays Ctrl-held truth for a display set."""

    def __init__(self) -> None:
        self._by_display: dict[object, bool] = {}

    def is_held(self) -> bool:
        """Return whether Ctrl is currently held on any contributing display."""

        return any(self._by_display.values())

    def held_provider(self) -> Callable[[], bool]:
        """Return the shared global-held provider for a runtime input owner."""

        return self.is_held

    def publisher_for(self, display_key: object) -> Callable[[bool], None]:
        """Return a publisher that records one display's own Ctrl-held state."""

        def publish(held: bool) -> None:
            self._by_display[display_key] = bool(held)

        return publish

    def is_display_held(self, display_key: object) -> bool:
        """Return one display's last-published Ctrl-held contribution."""

        return bool(self._by_display.get(display_key, False))

    def forget(self, display_key: object) -> None:
        """Drop a retired display's contribution so it cannot pin Ctrl held."""

        self._by_display.pop(display_key, None)

    def reset(self) -> None:
        """Clear every contribution (terminal teardown of the display set)."""

        self._by_display.clear()

    @property
    def contributing_display_count(self) -> int:
        return len(self._by_display)


__all__ = ["SharedCtrlCoordinator"]
