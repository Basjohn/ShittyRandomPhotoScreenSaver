"""Standalone top-level window owner for one physical Qt Quick display."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from PySide6.QtCore import QMetaObject, QPointF, QRect, Signal, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QScreen
from PySide6.QtQuick import QQuickWindow

from .state import (
    QuickDisplayBindingLoss,
    QuickDisplayIdentity,
    QuickWindowPolicy,
    capture_display_identity,
)
from .cursor_controller import QuickCursorController
from .input_controller import QuickInputController


logger = logging.getLogger(__name__)


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
        self._cursor_controller: QuickCursorController | None = None
        self._semantic_double_click_hit_test: Callable[[QPointF], bool] | None = None
        self._semantic_middle_click_hit_test: Callable[[QPointF], bool] | None = None
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

    @property
    def desired_visible(self) -> bool:
        """Return whether product state currently wants this window visible."""

        return bool(self._desired_visible)

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

    def bind_cursor_controller(self, controller: QuickCursorController) -> None:
        """Bind the native cursor owner; it never participates in scene geometry."""

        if self._cursor_controller is not None:
            raise RuntimeError("Quick display cursor controller is already bound")
        self._cursor_controller = controller

    def bind_semantic_double_click_hit_test(
        self,
        hit_test: Callable[[QPointF], bool] | None,
    ) -> None:
        self._semantic_double_click_hit_test = hit_test

    def bind_semantic_middle_click_hit_test(
        self,
        hit_test: Callable[[QPointF], bool] | None,
    ) -> None:
        self._semantic_middle_click_hit_test = hit_test

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
            "cursor_controller_bound": self._cursor_controller is not None,
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
        if self._runtime_discrete_pointer_event_is_suppressed("mousePressEvent"):
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            hit_test = self._semantic_middle_click_hit_test
            if hit_test is not None and hit_test(event.position()):
                event.accept()
                return
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_press(event):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # Halo motion is a native-cursor timestamp only.  In interaction/Ctrl
        # mode the input controller is deliberately bypassed, so passive mouse
        # movement does not query Settings/providers or publish semantic state.
        cursor = self._cursor_controller
        if cursor is not None and cursor.tracks_pointer_motion:
            cursor.note_pointer_motion()

        controller = self._input_controller
        if (
            controller is not None
            and controller.passive_mouse_move_requires_routing
            and controller.handle_mouse_move(event)
        ):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._runtime_discrete_pointer_event_is_suppressed("mouseReleaseEvent"):
            event.accept()
            return
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_release(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._runtime_discrete_pointer_event_is_suppressed("mouseDoubleClickEvent"):
            event.accept()
            return
        # Retained Quick hit regions own family-specific double-click semantics
        # (Clock mode, Media refresh). Let QML admit those first; the neutral
        # runtime input owner remains the unhandled-display fallback.
        event.ignore()
        super().mouseDoubleClickEvent(event)
        hit_test = self._semantic_double_click_hit_test
        if hit_test is not None and hit_test(event.position()):
            event.accept()
            return
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_double_click(event):
            event.accept()

    def _runtime_discrete_pointer_event_is_suppressed(self, source: str) -> bool:
        # Keep the R6 passive-move hot path untouched. This helper is reached
        # only for discrete pointer gestures that could otherwise leak through a
        # retained overlay/replacement boundary into QML semantic actions.
        from rendering.runtime_input import runtime_pointer_input_is_suppressed

        return runtime_pointer_input_is_suppressed(
            source,
            screen_index=self._screen_index,
        )

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

    def _log_native_window_geometry(self) -> None:
        """Log the real Win32 rect once the window exists.

        Qt's mixed-DPR virtual geometry is not a physical-pixel coordinate
        system. R7's remaining one-pixel seam therefore cannot be diagnosed by
        multiplying logical widths by DPR. Compare the actual HWND and monitor
        rectangles after show instead; this is bounded startup/reinit telemetry
        and never runs on the render/pointer hot paths.
        """
        import sys

        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            class _Rect(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class _MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", _Rect),
                    ("rcWork", _Rect),
                    ("dwFlags", wintypes.DWORD),
                ]

            user32 = ctypes.windll.user32
            user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_Rect)]
            user32.GetWindowRect.restype = wintypes.BOOL
            user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
            user32.MonitorFromWindow.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)
            ]
            user32.GetMonitorInfoW.restype = wintypes.BOOL

            hwnd = wintypes.HWND(int(self.winId()))
            window_rect = _Rect()
            if not user32.GetWindowRect(hwnd, ctypes.byref(window_rect)):
                return
            monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            info = _MonitorInfo()
            info.cbSize = ctypes.sizeof(_MonitorInfo)
            if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return
            wr = window_rect
            mr = info.rcMonitor
            logger.info(
                "[QUICK_NATIVE_GEOMETRY] screen=%d generation=%s "
                "window_device=(%d,%d,%d,%d) monitor_device=(%d,%d,%d,%d) "
                "overscan_device=(left=%d,top=%d,right=%d,bottom=%d)",
                self._screen_index,
                self._runtime_generation,
                wr.left,
                wr.top,
                wr.right - wr.left,
                wr.bottom - wr.top,
                mr.left,
                mr.top,
                mr.right - mr.left,
                mr.bottom - mr.top,
                mr.left - wr.left,
                mr.top - wr.top,
                wr.right - mr.right,
                wr.bottom - mr.bottom,
            )
        except Exception:
            logger.debug(
                "[QUICK_NATIVE_GEOMETRY] native rect unavailable screen=%d",
                self._screen_index,
                exc_info=True,
            )

    def _on_screen_metrics_changed(self, *_args: object) -> None:
        screen = self._bound_screen
        if screen is None or self._close_queued or self._binding_loss is not None:
            return
        self._apply_screen_geometry(screen)
        self.refresh_display_identity()

    def _on_window_visibility_changed(self, visible: bool) -> None:
        if not visible or not self._desired_visible or self._close_queued:
            return
        self._log_native_window_geometry()
        self.raise_()
        if self._policy.accepts_focus:
            self.requestActivate()

    @staticmethod
    def _fullscreen_compat_geometry(
        geometry: QRect,
        virtual_geometry: QRect | None = None,
    ) -> QRect:
        """Return a coverage-preserving non-exact-cover screen rectangle.

        R-63 is binding: an exact-cover borderless top-level window can be
        promoted by Windows into ``Hardware: Legacy Flip``, and the measured
        composition <-> flip transitions caused recurring black/stale frames.
        The compatibility geometry must therefore remain *larger* than the exact
        screen rectangle.

        The first R-63 implementation overscanned all four edges.  On mixed-DPR
        side-by-side displays that also perturbs the shared seam, where one
        logical pixel can round to a fractional device-pixel boundary.  Prefer a
        single virtual-desktop *exterior* edge instead: it is still non-exact
        cover, loses no visible pixel, and leaves every shared edge bit-for-bit at
        the screen geometry.  If topology exposes no exterior edge (for example a
        fully surrounded monitor), use top-only overscan as the narrowest safe
        compatibility fallback rather than returning exact cover.
        """

        adjusted = QRect(geometry)
        virtual = QRect(virtual_geometry) if virtual_geometry is not None else QRect()
        if virtual.isValid() and virtual.width() > 0 and virtual.height() > 0:
            if geometry.top() == virtual.top():
                adjusted.adjust(0, -1, 0, 0)
                return adjusted
            if geometry.bottom() == virtual.bottom():
                adjusted.adjust(0, 0, 0, 1)
                return adjusted
            if geometry.left() == virtual.left():
                adjusted.adjust(-1, 0, 0, 0)
                return adjusted
            if geometry.right() == virtual.right():
                adjusted.adjust(0, 0, 1, 0)
                return adjusted

        # Never return exact-cover geometry: preserving R-63 is more important
        # than guessing a shared-edge topology for an interior display.
        adjusted.adjust(0, -1, 0, 0)
        return adjusted

    def _apply_screen_geometry(self, screen: QScreen) -> None:
        geometry = screen.geometry()
        if not geometry.isValid() or geometry.width() <= 0 or geometry.height() <= 0:
            raise RuntimeError(
                f"screen {self._screen_index} has invalid geometry: {geometry.getRect()}"
            )
        try:
            virtual_geometry = screen.virtualGeometry()
        except Exception:
            virtual_geometry = QRect()
        adjusted = self._fullscreen_compat_geometry(geometry, virtual_geometry)
        self.setGeometry(adjusted)

        # Bounded surface-geometry evidence for the intermittent seam falsifier.
        # Size projections are useful across DPR without pretending Qt's virtual
        # desktop origins share one device-pixel coordinate scale.
        try:
            dpr = float(screen.devicePixelRatio())
        except Exception:
            dpr = 1.0
        logger.info(
            "[QUICK_GEOMETRY] screen=%d generation=%s dpr=%.3f "
            "screen_logical=%s window_logical=%s virtual_logical=%s "
            "screen_device_size=%dx%d window_device_size=%dx%d",
            self._screen_index,
            self._runtime_generation,
            dpr,
            geometry.getRect(),
            adjusted.getRect(),
            virtual_geometry.getRect() if virtual_geometry.isValid() else None,
            int(round(geometry.width() * dpr)),
            int(round(geometry.height() * dpr)),
            int(round(adjusted.width() * dpr)),
            int(round(adjusted.height() * dpr)),
        )

    def _queue_meta_call(self, method: str) -> None:
        if not QMetaObject.invokeMethod(
            self,
            method,
            Qt.ConnectionType.QueuedConnection,
        ):
            raise RuntimeError(f"could not queue QQuickWindow.{method}()")
