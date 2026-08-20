"""Standalone top-level window owner for one physical Qt Quick display."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMetaObject, Signal, Qt
from PySide6.QtGui import QColor, QScreen
from PySide6.QtQuick import QQuickWindow

from .state import (
    QuickDisplayIdentity,
    QuickWindowPolicy,
    capture_display_identity,
)


class QuickDisplayWindow(QQuickWindow):
    """QWindow-only owner for a selected display's single accelerated surface."""

    display_identity_changed = Signal(object)
    close_queued = Signal()

    _SCREEN_SIGNAL_NAMES = (
        "geometryChanged",
        "availableGeometryChanged",
        "logicalDotsPerInchChanged",
        "physicalDotsPerInchChanged",
        "refreshRateChanged",
    )

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int | None,
        screen: QScreen,
        policy: QuickWindowPolicy,
    ) -> None:
        super().__init__()
        if screen is None:
            raise ValueError("QuickDisplayWindow requires an exact QScreen")

        self._screen_index = int(screen_index)
        if self._screen_index < 0:
            raise ValueError("screen_index must be non-negative")
        self._runtime_generation = (
            None if runtime_generation is None else int(runtime_generation)
        )
        self._policy = policy
        self._bound_screen: QScreen | None = None
        self._display_identity: QuickDisplayIdentity | None = None
        self._close_queued = False

        generation_label = (
            "none" if self._runtime_generation is None else str(self._runtime_generation)
        )
        self.setObjectName(
            f"srpss-quick-display-{self._screen_index}-generation-{generation_label}"
        )
        self.setColor(QColor("#000000"))
        self.setPersistentGraphics(False)
        self.setPersistentSceneGraph(False)
        self.setFlags(policy.flags())
        if policy.blank_cursor:
            self.setCursor(Qt.CursorShape.BlankCursor)

        # Screen selection is deliberately complete before the first show.
        self.setScreen(screen)
        self._bind_screen(screen, apply_geometry=False)
        self.screenChanged.connect(self._on_window_screen_changed)

    @property
    def screen_index(self) -> int:
        return self._screen_index

    @property
    def runtime_generation(self) -> int | None:
        return self._runtime_generation

    @property
    def policy(self) -> QuickWindowPolicy:
        return self._policy

    @property
    def display_identity(self) -> QuickDisplayIdentity:
        identity = self._display_identity
        if identity is None:
            raise RuntimeError("Quick display identity is unavailable")
        return identity

    @property
    def is_close_queued(self) -> bool:
        return self._close_queued

    def show_on_screen(self) -> None:
        """Commit exact physical-screen placement before making the window visible."""

        if self._close_queued:
            raise RuntimeError("cannot show a retiring Quick display window")
        screen = self._bound_screen
        if screen is None:
            raise RuntimeError("Quick display window has no bound screen")
        if self.screen() is not screen:
            self.setScreen(screen)
        self._apply_screen_geometry(screen)
        self.show()
        self.raise_()
        if self._policy.accepts_focus:
            self.requestActivate()

    def queue_hide(self) -> None:
        """Hide through Qt's event loop so Python never waits on the render thread."""

        self._queue_meta_call("hide")

    def queue_close(self) -> None:
        """Queue render-safe scene invalidation and native-window retirement once."""

        if self._close_queued:
            return
        self._close_queued = True
        try:
            for method in ("hide", "releaseResources", "close"):
                self._queue_meta_call(method)
        except Exception:
            self._close_queued = False
            raise
        self.close_queued.emit()

    def refresh_display_identity(self) -> QuickDisplayIdentity:
        """Refresh primitive display facts after a QScreen metric change."""

        screen = self._bound_screen
        if screen is None:
            raise RuntimeError("Quick display window has no bound screen")
        identity = capture_display_identity(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            screen=screen,
        )
        if identity != self._display_identity:
            self._display_identity = identity
            self.display_identity_changed.emit(identity)
        return identity

    def describe_window_state(self) -> dict[str, Any]:
        rect = self.geometry()
        return {
            "object_name": self.objectName(),
            "screen_index": self._screen_index,
            "runtime_generation": self._runtime_generation,
            "visible": bool(self.isVisible()),
            "active": bool(self.isActive()),
            "close_queued": self._close_queued,
            "geometry": [rect.x(), rect.y(), rect.width(), rect.height()],
            "display_identity": self.display_identity.as_dict(),
        }

    def _bind_screen(self, screen: QScreen, *, apply_geometry: bool) -> None:
        if screen is self._bound_screen:
            if apply_geometry:
                self._apply_screen_geometry(screen)
            self.refresh_display_identity()
            return

        self._disconnect_screen_signals()
        self._bound_screen = screen
        for name in self._SCREEN_SIGNAL_NAMES:
            getattr(screen, name).connect(self._on_screen_metrics_changed)
        if apply_geometry:
            self._apply_screen_geometry(screen)
        self.refresh_display_identity()

    def _disconnect_screen_signals(self) -> None:
        screen = self._bound_screen
        if screen is None:
            return
        for name in self._SCREEN_SIGNAL_NAMES:
            try:
                getattr(screen, name).disconnect(self._on_screen_metrics_changed)
            except (RuntimeError, TypeError):
                pass

    def _on_window_screen_changed(self, screen: QScreen | None) -> None:
        if screen is None or screen is self._bound_screen:
            return
        self._bind_screen(screen, apply_geometry=self.isVisible())

    def _on_screen_metrics_changed(self, *_args: object) -> None:
        screen = self._bound_screen
        if screen is None or self._close_queued:
            return
        self._apply_screen_geometry(screen)
        self.refresh_display_identity()

    def _apply_screen_geometry(self, screen: QScreen) -> None:
        geometry = screen.geometry()
        if not geometry.isValid() or geometry.width() <= 0 or geometry.height() <= 0:
            raise RuntimeError(
                f"screen {self._screen_index} has invalid geometry: {geometry.getRect()}"
            )
        self.setGeometry(geometry)

    def _queue_meta_call(self, method: str) -> None:
        if not QMetaObject.invokeMethod(
            self,
            method,
            Qt.ConnectionType.QueuedConnection,
        ):
            raise RuntimeError(f"could not queue QQuickWindow.{method}()")
