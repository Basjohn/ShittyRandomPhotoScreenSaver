"""Standalone top-level window owner for one physical Qt Quick display."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QMetaObject, Signal, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QScreen
from PySide6.QtQuick import QQuickWindow

from .state import (
    QuickDisplayBindingLoss,
    QuickDisplayIdentity,
    QuickWindowPolicy,
    capture_display_identity,
)
from .input_controller import QuickInputController


class QuickDisplayWindow(QQuickWindow):
    """QWindow-only owner for a selected display's single accelerated surface."""

    display_identity_changed = Signal(object)
    binding_lost = Signal(object)
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
        self._binding_loss: QuickDisplayBindingLoss | None = None
        self._input_controller: QuickInputController | None = None
        self._desired_visible = False
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
        self.visibleChanged.connect(self._on_window_visibility_changed)

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
    def binding_loss(self) -> QuickDisplayBindingLoss | None:
        return self._binding_loss

    @property
    def is_close_queued(self) -> bool:
        return self._close_queued

    def bind_input_controller(self, controller: QuickInputController) -> None:
        """Bind the exact generation-scoped event owner before first show."""

        if self._input_controller is not None:
            raise RuntimeError("Quick display input controller is already bound")
        if (
            controller.screen_index != self._screen_index
            or controller.runtime_generation != self._runtime_generation
        ):
            raise ValueError("Quick input identity does not match its display window")
        self._input_controller = controller

    def show_on_screen(self) -> None:
        """Commit exact physical-screen placement before making the window visible."""

        if self._close_queued:
            raise RuntimeError("cannot show a retiring Quick display window")
        if self._binding_loss is not None:
            raise RuntimeError("cannot show a topology-displaced Quick display window")
        screen = self._bound_screen
        if screen is None:
            raise RuntimeError("Quick display window has no bound screen")
        if self.screen() is not screen:
            self.setScreen(screen)
        self._apply_screen_geometry(screen)
        self._desired_visible = True
        self._queue_meta_call("show")

    def queue_hide(self) -> None:
        """Hide through Qt's event loop so Python never waits on the render thread."""

        self._desired_visible = False
        self._queue_meta_call("hide")

    def queue_close(self) -> None:
        """Queue render-safe scene invalidation and native-window retirement once."""

        if self._close_queued:
            return
        self._close_queued = True
        self._desired_visible = False
        try:
            for method in ("hide", "releaseResources", "close"):
                self._queue_meta_call(method)
        except Exception:
            self._close_queued = False
            raise
        self.close_queued.emit()

    def refresh_display_identity(self) -> QuickDisplayIdentity:
        """Refresh primitive display facts after a QScreen metric change."""

        if self._binding_loss is not None:
            return self.display_identity
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
            "desired_visible": self._desired_visible,
            "close_queued": self._close_queued,
            "binding_loss": (
                None if self._binding_loss is None else self._binding_loss.as_dict()
            ),
            "input_controller_bound": self._input_controller is not None,
            "geometry": [rect.x(), rect.y(), rect.width(), rect.height()],
            "display_identity": self.display_identity.as_dict(),
        }

    def keyPressEvent(self, event: QKeyEvent) -> None:
        controller = self._input_controller
        if controller is not None and controller.handle_key_press(event):
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        controller = self._input_controller
        if controller is not None and controller.handle_key_release(event):
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_press(event):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_move(event):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_release(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_double_click(event):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

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
        if (
            screen is self._bound_screen
            or self._close_queued
            or self._binding_loss is not None
        ):
            return

        observed_screen_key: str | None = None
        observed_screen_name: str | None = None
        if screen is not None:
            try:
                observed = capture_display_identity(
                    screen_index=self._screen_index,
                    runtime_generation=self._runtime_generation,
                    screen=screen,
                )
                observed_screen_key = observed.screen_key
                observed_screen_name = observed.name
            except (RuntimeError, TypeError):
                # Topology loss must still quiesce the old generation even if
                # Qt is already invalidating the replacement QScreen wrapper.
                try:
                    observed_screen_name = str(screen.name() or "")
                except RuntimeError:
                    pass

        loss = QuickDisplayBindingLoss(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            expected_screen_key=self.display_identity.screen_key,
            observed_screen_key=observed_screen_key,
            observed_screen_name=observed_screen_name,
        )
        self._binding_loss = loss
        self._disconnect_screen_signals()
        # Never rebind a live generation. Queueing the hide keeps Python out
        # of blocking threaded-render-loop window teardown paths.
        self.queue_hide()
        self.binding_lost.emit(loss)

    def _on_screen_metrics_changed(self, *_args: object) -> None:
        screen = self._bound_screen
        if screen is None or self._close_queued or self._binding_loss is not None:
            return
        self._apply_screen_geometry(screen)
        self.refresh_display_identity()

    def _on_window_visibility_changed(self, visible: bool) -> None:
        if not visible or not self._desired_visible or self._close_queued:
            return
        self.raise_()
        if self._policy.accepts_focus:
            self.requestActivate()

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
