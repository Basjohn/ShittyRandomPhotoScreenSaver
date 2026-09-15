"""Qt-Quick-owned continuous-frame demand for wall-time transitions.

Visualizer presentation is intentionally *not* paced here. Fresh visualizer
publications wake their retained QQuickItem directly with latest-wins/coalesced
semantics. Ordinary QML animations are owned by Qt Quick's animation driver.

The remaining custom continuous-frame consumer is the wallpaper transition
render node, whose progress is sampled from monotonic wall time.  This owner is
therefore only a *demand/lifecycle coordinator*: it publishes transition-active
and per-display target-Hz state into DisplayScene.qml.  A QML ``FrameAnimation``
uses Qt Quick's native animation driver as the tick source and asks the retained
background ``QQuickItem`` to update no more often than that display's refresh
interval.

There is deliberately no Python refresh timer, no ``frameSwapped`` feedback
loop, and no Python per-frame callback.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import IntFlag, auto
import math

from PySide6.QtCore import QObject
from PySide6.QtQuick import QQuickWindow


class QuickFrameDemand(IntFlag):
    """Independent reasons that require custom continuously changing frames."""

    NONE = 0
    TRANSITION = auto()


@dataclass
class QuickPacerState:
    """Static per-display metadata for the Qt Quick transition frame driver."""

    target_hz: float

    def __post_init__(self) -> None:
        rate = float(self.target_hz)
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError("target_hz must be finite and greater than zero")
        self.target_hz = rate
        self.interval_ns = max(1, int(round(1_000_000_000.0 / rate)))


class QuickFramePacer(QObject):
    """Coordinate transition frame demand without owning a frame clock.

    The historical name is retained for the existing PERF/runtime schema, but
    pacing is now wholly Qt Quick/QML-owned. ``driver_state_setter`` is invoked
    only when demand, visibility, target display, or lifecycle state changes.
    ``driver_state_provider`` is sampled only by diagnostics (normally ~1 Hz).
    """

    def __init__(
        self,
        window: QQuickWindow,
        target_hz: float,
        *,
        driver_state_setter: Callable[[bool, float], None],
        driver_state_provider: Callable[[], Mapping[str, object]] | None = None,
    ) -> None:
        super().__init__(window)
        if not callable(driver_state_setter):
            raise TypeError("transition frame driver state setter must be callable")
        if driver_state_provider is not None and not callable(driver_state_provider):
            raise TypeError("transition frame driver state provider must be callable")
        self._window = window
        self._state = QuickPacerState(float(target_hz))
        self._driver_state_setter = driver_state_setter
        self._driver_state_provider = driver_state_provider
        self._demands = QuickFrameDemand.NONE
        # Runtime windows are normally constructed hidden and bound before first
        # show. Do not start a native animation job until the window is visible.
        self._paused = not bool(window.isVisible())
        self._closed = False
        self._control_publications = 0

    @property
    def target_hz(self) -> float:
        return self._state.target_hz

    @property
    def demands(self) -> QuickFrameDemand:
        return self._demands

    def is_active(self) -> bool:
        return bool(self._demands) and not self._paused and not self._closed

    def set_demand(self, reason: QuickFrameDemand, active: bool) -> None:
        """Add/remove one custom-frame reason and publish native driver state."""

        if self._closed:
            raise RuntimeError("Quick frame pacer is closed")
        allowed = int(QuickFrameDemand.TRANSITION)
        reason_value = int(reason)
        if reason_value == 0 or reason_value & ~allowed:
            raise ValueError(f"unsupported Quick frame demand: {reason!r}")
        reason = QuickFrameDemand(reason_value)

        previous = self._demands
        if active:
            self._demands |= reason
        else:
            self._demands &= ~reason
        if self._demands == previous:
            return
        self._publish_driver_state()

    def set_transition_active(self, active: bool) -> None:
        self.set_demand(QuickFrameDemand.TRANSITION, active)

    def set_target_hz(self, target_hz: float) -> None:
        """Retarget the native per-display frame gate after QScreen changes."""

        if self._closed:
            raise RuntimeError("Quick frame pacer is closed")
        replacement = QuickPacerState(float(target_hz))
        if math.isclose(
            replacement.target_hz,
            self._state.target_hz,
            rel_tol=0.0,
            abs_tol=0.001,
        ):
            return
        self._state = replacement
        self._publish_driver_state()

    def stop(self) -> None:
        """Clear custom demand without changing visibility suspension."""

        if self._closed:
            return
        if self._demands == QuickFrameDemand.NONE:
            return
        self._demands = QuickFrameDemand.NONE
        # ``_paused`` is owned by window visibility/lifecycle. Clearing demand
        # must not make a hidden runtime eligible to start a later transition.
        self._publish_driver_state()

    def pause(self) -> bool:
        """Suspend native frame demand while preserving active reasons."""

        if self._closed or self._paused:
            return False
        self._paused = True
        self._publish_driver_state()
        return True

    def resume(self) -> bool:
        """Resume native frame demand from current wall-time transition state."""

        if self._closed or not self._paused:
            return False
        self._paused = False
        self._publish_driver_state()
        return True

    def close(self) -> None:
        """Permanently stop native frame demand before scene retirement."""

        if self._closed:
            return
        self._demands = QuickFrameDemand.NONE
        self._paused = False
        # Publish the inactive state while the QML scene still exists; runtime
        # teardown orders this before scene retirement.
        self._publish_driver_state()
        self._closed = True

    def describe(self) -> dict[str, object]:
        native: Mapping[str, object] = {}
        provider = self._driver_state_provider
        if provider is not None:
            try:
                native = provider()
            except (RuntimeError, TypeError):
                native = {}

        animation_ticks = int(native.get("animation_ticks", 0) or 0)
        update_requests = int(native.get("update_requests", 0) or 0)
        animation_running = bool(native.get("animation_running", False))
        native_target_hz = float(native.get("target_hz", self._state.target_hz) or 0.0)
        return {
            "driver": "qml_frame_animation",
            "target_hz": self._state.target_hz,
            "native_target_hz": native_target_hz,
            "interval_ns": self._state.interval_ns,
            "active": self.is_active(),
            "paused": self._paused,
            "closed": self._closed,
            "demands": [
                demand.name.lower()
                for demand in (QuickFrameDemand.TRANSITION,)
                if self._demands & demand
            ],
            # Preserve the existing PERF schema. These are now native QML
            # animation opportunities and actual BackgroundRenderItem.update()
            # requests, sampled without a Python per-frame callback.
            "requested_opportunities": animation_ticks,
            "issued_update_requests": update_requests,
            "animation_running": animation_running,
            "control_publications": self._control_publications,
        }

    def _publish_driver_state(self) -> None:
        self._control_publications += 1
        self._driver_state_setter(self.is_active(), self._state.target_hz)


__all__ = [
    "QuickFrameDemand",
    "QuickFramePacer",
    "QuickPacerState",
]
