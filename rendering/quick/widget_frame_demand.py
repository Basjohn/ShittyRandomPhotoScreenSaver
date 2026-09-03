"""Event-driven continuous-frame demand for running widget QML animations.

The threaded Quick scene is driven by :class:`QuickFramePacer`, which presents
frames only while a wallpaper transition or the visualizer demands them. Widget
opacity/crossfade animations (Media artwork/metadata, Steam content rotations,
lifecycle fades) otherwise render only their first and last frame and read as a
hard flash rather than a gentle fade.

Each such animation calls ``setAnimationActive(animation, running)`` from its
``onRunningChanged`` handler — event-driven, no timer, no polling. This gate
refcounts the set of currently-running animations and raises exactly one
``WIDGET_ANIMATION`` pacer demand while any are active, releasing it when the
last one stops. An animation destroyed mid-run (e.g. a widget retiring during a
fade) auto-releases via its ``destroyed()`` signal, so the demand can never leak
the scene into a permanent continuous-render state.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Slot

from core.logging.logger import get_logger

logger = get_logger(__name__)


class QuickWidgetFrameDemand(QObject):
    """One per-display gate: WIDGET_ANIMATION demand == any widget animation runs."""

    def __init__(self, frame_pacer: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pacer = frame_pacer
        self._active: set[int] = set()
        self._tracked: dict[int, QObject] = {}

    @Slot(QObject, bool)
    def setAnimationActive(  # noqa: N802 (QML-facing camelCase)
        self,
        animation: QObject | None,
        active: bool,
    ) -> None:
        if animation is None:
            return
        key = id(animation)
        if active:
            if key not in self._tracked:
                self._tracked[key] = animation
                # Only the captured integer key is used in the slot, never the
                # object being destroyed, so this stays safe during teardown.
                animation.destroyed.connect(lambda *_a, k=key: self._release(k))
            self._active.add(key)
        else:
            self._active.discard(key)
        self._sync_demand()

    def _release(self, key: int) -> None:
        self._active.discard(key)
        self._tracked.pop(key, None)
        self._sync_demand()

    def _sync_demand(self) -> None:
        pacer = self._pacer
        if pacer is None:
            return
        try:
            pacer.set_widget_animation_active(bool(self._active))
        except Exception:
            logger.debug(
                "[QUICK] widget-animation frame demand toggle failed", exc_info=True
            )

    def clear(self) -> None:
        """Release every demand and detach the pacer (display retire)."""

        self._active.clear()
        self._tracked.clear()
        self._sync_demand()
        self._pacer = None


__all__ = ["QuickWidgetFrameDemand"]
