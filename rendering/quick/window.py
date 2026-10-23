"""Standalone top-level window owner for one physical Qt Quick display."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from PySide6.QtCore import QEvent, QMetaObject, QObject, QPointF, QRect, QRectF, Signal, SIGNAL, Slot, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QMouseEvent, QPointingDevice, QScreen
from PySide6.QtQuick import QQuickWindow

from .bootstrap import validate_or_quit_current_opengl_context
from .state import (
    QuickDisplayBindingLoss,
    QuickDisplayIdentity,
    QuickWindowPolicy,
    capture_display_identity,
)
from .cursor_controller import QuickCursorController
from .device_geometry import compat_native_rect, visible_rect_in_window
from .input_controller import QuickInputController


logger = logging.getLogger(__name__)


class QuickDisplayWindow(QQuickWindow):
    """QWindow-only owner for a selected display's single accelerated surface."""

    display_identity_changed = Signal(object)
    binding_lost = Signal(object)
    close_queued = Signal()
    orbit_cleanup_completed = Signal()
    # The window's on-desktop rectangle (for the R-63 window, exactly its
    # monitor) in logical coordinates; the scene root is laid out on it.
    scene_rect_changed = Signal(object)

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
        self._custom_layout_input_blocked = False
        self._plain_orbit_target = None
        self._plain_orbit_grabber_blocks = None
        self._plain_orbit_pending = None
        self._plain_orbit_press_device = None
        self._plain_orbit_capture = None
        self._plain_orbit_card = None
        self._plain_orbit_releasing = False
        self._plain_orbit_acquiring = False
        self._plain_orbit_acquire_cancel = None
        self._framed_scene_filter_installed = False
        self._desired_visible = False
        self._close_queued = False
        self._scene_rect: QRectF | None = None
        # Logical rects this window's own R-63 placement produced. The native
        # device-pixel correction applies only while the window still has one
        # of them; a window placed by anything else is left alone.
        self._compat_logical_rects: set[tuple[int, int, int, int]] = set()

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
        self.activeChanged.connect(self._cancel_orbit_on_deactivation)
        # This is the first actual context boundary even when the retained
        # background has no image/node yet. Direct delivery keeps the scene
        # graph context current for the one startup validation query.
        self.sceneGraphInitialized.connect(
            self._validate_scene_graph_opengl,
            Qt.ConnectionType.DirectConnection,
        )
        # Geometry edges are rare (show, screen changes, resume); each re-derives
        # whether the scene sits on the monitor or fills the window.
        for changed in (self.xChanged, self.yChanged, self.widthChanged, self.heightChanged):
            changed.connect(self._refresh_scene_rect)
        # A filter returns to C++ before normal window/render event delivery.
        # Overriding event() and forwarding to QQuickWindow can hold the GIL
        # across its blocking scene-graph startup synchronization.
        self.installEventFilter(self)

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
        controller.scene_transform_admission_changed.connect(self._refresh_framed_scene_input_filter)
        controller.plain_orbit_cancel_requested.connect(self.cancel_plain_orbit)
        controller.input_state_changed.connect(self._cancel_orbit_on_input_state)
        self._refresh_framed_scene_input_filter()

    def _validate_scene_graph_opengl(self) -> None:
        """Enforce the one graphics contract at actual scene-graph startup."""

        generation_label = (
            "none"
            if self._runtime_generation is None
            else str(self._runtime_generation)
        )
        validate_or_quit_current_opengl_context(
            reason=(
                f"quick-display-scene-graph-screen-{self._screen_index}-"
                f"generation-{generation_label}"
            )
        )

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

    def set_custom_layout_input_blocked(self, blocked: bool) -> None:
        """Let CUSTOM Edit own pointer delivery without runtime semantic leakage.

        The window still forwards pointer events to QQuickWindow/QML so the
        editor overlay can drag/resize normally. While blocked, native runtime
        semantics (next-image double click, visualizer middle click, exit
        gestures) are deliberately bypassed. Right-click remains routed to the
        editor/global context-menu authority rather than leaking into family QML.
        """

        if blocked:
            self.cancel_plain_orbit()
        self._custom_layout_input_blocked = bool(blocked)
        self._refresh_framed_scene_input_filter()

    def bind_plain_orbit_target(self, target, *, grabber_blocks=None) -> None:
        """Retained scene supplies actual card ownership, not a second hit map."""
        self.cancel_plain_orbit()
        self._plain_orbit_target = target
        self._plain_orbit_grabber_blocks = grabber_blocks

    def watch_plain_orbit_card(self, card) -> None:
        for name in ('visibleChanged', 'enabledChanged', 'xChanged', 'yChanged', 'widthChanged', 'heightChanged'):
            getattr(card, name).connect(self._cancel_plain_orbit_card)
        card.destroyed.connect(self._cancel_plain_orbit_card)
        # QML-declared property notification is not a Python attribute on every
        # PySide-created root; use its real Qt signal, once at root creation.
        self.connect(card, SIGNAL('cardShellEnabledChanged()'), self._cancel_plain_orbit_card)
        self.connect(card, SIGNAL('presentationActiveChanged()'), self._cancel_plain_orbit_card)

    def _cancel_plain_orbit_card(self, *_args) -> None:
        if self._plain_orbit_pending is None and self._plain_orbit_capture is None:
            return
        card = self.sender()
        if self._plain_orbit_card is card or (self._plain_orbit_pending is not None
                                            and self._plain_orbit_pending[1] is card):
            self.cancel_plain_orbit()

    def _cancel_orbit_on_input_state(self, _state) -> None:
        if not self._input_controller.plain_orbit_admitted:
            self.cancel_plain_orbit()

    def _cancel_orbit_on_deactivation(self) -> None:
        if not self.isActive():
            self.cancel_plain_orbit()

    def cancel_plain_orbit(self, *_args) -> None:
        """One idempotent unwind for pending press, native resources and orbit."""
        if self._plain_orbit_pending is not None or self._plain_orbit_card is not None or self._plain_orbit_acquiring:
            logger.debug('[ORBIT_CAPTURE] Cancel reason=%r acquiring=%s', _args, self._plain_orbit_acquiring)
        if self._plain_orbit_acquiring:
            # Native calls can synchronously deliver cancellation. Let their
            # atomic acquisition return, then unwind its actual resource state.
            self._plain_orbit_acquire_cancel = _args or ('cancel',)
            return
        active = self._plain_orbit_card is not None
        self._clear_plain_orbit_pending()
        self._plain_orbit_card = None
        capture = self._plain_orbit_capture
        if capture is None or self._plain_orbit_releasing:
            return
        self._plain_orbit_releasing = True
        try:
            capture.release()
        except Exception:
            logger.exception('[ORBIT_CAPTURE] Native release failed; cleanup retained until next cancel/close')
        else:
            self._plain_orbit_capture = None
        finally:
            self._plain_orbit_releasing = False
            if active:
                if self._cursor_controller is not None:
                    self._cursor_controller.end_orbit_fade()
                if self._input_controller is not None:
                    self._input_controller.finish_plain_orbit(settle=not (_args and _args[0] == 'reset'))
        if self._plain_orbit_capture is None and not active:
            self.orbit_cleanup_completed.emit()

    @property
    def orbit_cleanup_pending(self) -> bool:
        return self._plain_orbit_capture is not None

    def _new_plain_orbit_capture(self):
        from .pointer_capture import NativeOrbitCapture
        return NativeOrbitCapture(self)

    def _clear_plain_orbit_pending(self):
        self._plain_orbit_pending = None
        device, self._plain_orbit_press_device = self._plain_orbit_press_device, None
        if device is not None:
            device.grabChanged.disconnect(self._plain_orbit_retained_grab)

    @Slot(QObject, QPointingDevice.GrabTransition)
    def _plain_orbit_retained_grab(self, grabber, transition):
        # PySide exposes grabChanged but not QPointerEvent.passiveGrabbers.
        # Observe real passive/exclusive first refusal during this press only;
        # never retain the transient native event or point objects.
        if (self._plain_orbit_pending is not None and grabber is not None
                and transition in (QPointingDevice.GrabTransition.GrabPassive,
                                   QPointingDevice.GrabTransition.GrabExclusive)):
            if not self._plain_orbit_grab_blocks(grabber):
                return
            logger.debug('[ORBIT_CAPTURE] Retained press owned by %s name=%r transition=%s',
                         grabber.metaObject().className(), grabber.objectName(), transition)
            self._clear_plain_orbit_pending()

    def _plain_orbit_grab_blocks(self, grabber):
        if grabber is None:
            return False
        policy = self._plain_orbit_grabber_blocks
        return policy is None or policy(grabber, self._plain_orbit_pending[1])

    def _promote_plain_orbit(self, event) -> bool:
        pending = self._plain_orbit_pending
        if pending is None:
            return False
        if not event.buttons() & Qt.MouseButton.LeftButton:
            self.cancel_plain_orbit()
            return False
        origin, card, threshold = pending
        if (event.position() - origin).manhattanLength() < threshold:
            return False
        controller = self._input_controller
        target = self._plain_orbit_target
        if (controller is None or not controller.plain_orbit_admitted or target is None
                or self._plain_orbit_grab_blocks(self.mouseGrabberItem())
                or self._plain_orbit_grab_blocks(event.exclusiveGrabber(event.point(0)))
                or target(origin) is not card):
            self.cancel_plain_orbit()
            return False
        cursor = self._cursor_controller
        if cursor is None or not cursor.begin_orbit_fade():
            self.cancel_plain_orbit()
            return False
        capture = None
        # Only lower retained branches can still hold passive grabs here; all
        # card/above-card controls have already declined this gesture.
        event.clearPassiveGrabbers(event.point(0))
        self._clear_plain_orbit_pending()
        try:
            self._plain_orbit_acquiring = True
            try:
                capture = self._new_plain_orbit_capture()
                # Own acquisition before it can partially succeed. Native acquire
                # makes its one immediate unwind attempt; failed cleanup stays here.
                self._plain_orbit_capture = capture
                rect = card.mapRectToScene(QRectF(0., 0., card.width(), card.height()))
                capture.acquire(rect)
            finally:
                self._plain_orbit_acquiring = False
            if self._plain_orbit_acquire_cancel is not None:
                reason, self._plain_orbit_acquire_cancel = self._plain_orbit_acquire_cancel, None
                self.cancel_plain_orbit(*reason)
                cursor.end_orbit_fade()
                return False
            self._plain_orbit_card = card
            self._plain_orbit_pending = None
            if not controller.begin_plain_orbit(origin):
                self.cancel_plain_orbit()
                return False
        except Exception:
            logger.exception('[ORBIT_CAPTURE] Held-left orbit declined: capture/confinement failed')
            self._plain_orbit_pending = None
            self._plain_orbit_card = None
            self._plain_orbit_acquire_cancel = None
            if capture is None or not capture.cleanup_pending:
                self._plain_orbit_capture = None
            cursor.end_orbit_fade()
            return False
        return True

    def eventFilter(self, watched, event):
        if watched is not self:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseMove:
            if (self._plain_orbit_pending is not None or self._plain_orbit_card is not None):
                if not event.buttons() & Qt.MouseButton.LeftButton:
                    self.cancel_plain_orbit()
                else:
                    if self._plain_orbit_pending is not None:
                        self._promote_plain_orbit(event)
                    if self._plain_orbit_card is not None:
                        # The window now owns this gesture. Retained hover
                        # cursors (e.g. a glyph's pointing hand) must not override
                        # its fading/hidden native cursor while crossing them.
                        self.mouseMoveEvent(event)
                        return True
        if kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._plain_orbit_card is not None:
                self.mouseReleaseEvent(event)
                return True
            self.cancel_plain_orbit()
        if kind in (QEvent.Type.MouseButtonDblClick, QEvent.Type.UngrabMouse, QEvent.Type.WindowDeactivate,
                            QEvent.Type.Hide, QEvent.Type.Close, QEvent.Type.DeferredDelete,
                            QEvent.Type.PlatformSurface):
            if hasattr(self, '_plain_orbit_pending'):
                self.cancel_plain_orbit(kind.name)
        return False

    def nativeEvent(self, event_type, message):
        # Qt does not promise an UngrabMouse event for a native capture stolen
        # by another HWND; observe only this discrete cancellation edge.
        if getattr(self, '_plain_orbit_capture', None) is not None and not self._plain_orbit_releasing:
            import ctypes
            from ctypes import wintypes
            native = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if native.message in (0x0215, 0x001F, 0x0002):  # CAPTURECHANGED / CANCELMODE / DESTROY
                self.cancel_plain_orbit(f'native-{native.message:x}')
        # Leave native delivery unhandled, as QWindow's default does. Calling
        # the protected PySide wrapper rejects otherwise-valid MSG pointers on
        # the current binding; no native default work is needed here.
        return False, 0

    def _refresh_framed_scene_input_filter(self, _enabled=None) -> None:
        controller = self._input_controller
        admitted = bool(self._custom_layout_input_blocked and controller is not None
                        and controller.scene_transform_enabled)
        if admitted == self._framed_scene_filter_installed:
            return
        if admitted:
            self.installEventFilter(controller)
        elif controller is not None:
            self.removeEventFilter(controller)
        self._framed_scene_filter_installed = admitted

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

        self.cancel_plain_orbit()
        self._desired_visible = False
        self._queue_meta_call("hide")

    def queue_close(self) -> None:
        """Queue render-safe scene invalidation and native-window retirement once."""

        self.cancel_plain_orbit()
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

    def revalidate_bound_screen_geometry(self) -> QuickDisplayIdentity:
        """Reapply authoritative screen geometry after a suspend/resume edge.

        This is intentionally not a topology-rebinding API.  If Qt has rebound
        the native window to another ``QScreen``, the existing ``screenChanged``
        path owns binding loss and generation replacement.  When the same screen
        remains authoritative, reapplying its geometry repairs a native window
        that Windows displaced while the displays/system were asleep.
        """

        if self._binding_loss is not None or self._close_queued:
            return self.display_identity
        screen = self._bound_screen
        if screen is None:
            raise RuntimeError("Quick display window has no bound screen")
        if self.screen() is not screen:
            self._on_window_screen_changed(self.screen())
            return self.display_identity
        self._apply_screen_geometry(screen)
        return self.refresh_display_identity()

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
            "orbit_cleanup_pending": self.orbit_cleanup_pending,
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
        if self._plain_orbit_pending is not None or self._plain_orbit_capture is not None:
            self.cancel_plain_orbit()
        # CUSTOM is an explicit pointer owner. The short-lived runtime-recreation
        # guard suppresses product actions, not editor chrome; checking it first
        # can swallow a resize-handle press before QML receives it.
        if self._custom_layout_input_blocked:
            controller = self._input_controller
            if (
                event.button() == Qt.MouseButton.RightButton
                and not event.modifiers() & Qt.KeyboardModifier.AltModifier
                and controller is not None
                and controller.handle_custom_layout_context_press(event)
            ):
                event.accept()
                return
            super().mousePressEvent(event)
            return
        if self._runtime_discrete_pointer_event_is_suppressed("mousePressEvent"):
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            hit_test = self._semantic_middle_click_hit_test
            if hit_test is not None and hit_test(event.position()):
                event.accept()
                return
        controller = self._input_controller
        candidate = None
        if (self._plain_orbit_capture is None and controller is not None
                and controller.plain_orbit_admitted and self._plain_orbit_target is not None
                and event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier)):
            candidate = self._plain_orbit_target(event.position())
        if controller is not None and controller.handle_mouse_press(event):
            event.accept()
            return
        super().mousePressEvent(event)
        # Retained controls get first refusal. Their exclusive grab, including
        # PointerHandler grabs, must never be stolen by camera orbit.
        if candidate is not None:
            self._plain_orbit_pending = (QPointF(event.position()), candidate,
                                         QGuiApplication.styleHints().startDragDistance())
            self._plain_orbit_press_device = event.pointingDevice()
            self._plain_orbit_press_device.grabChanged.connect(self._plain_orbit_retained_grab)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._plain_orbit_card is not None and not event.buttons() & Qt.MouseButton.LeftButton:
            self.cancel_plain_orbit()
        # Halo motion is a native-cursor timestamp only.  In interaction/Ctrl
        # mode the input controller is deliberately bypassed, so passive mouse
        # movement does not query Settings/providers or publish semantic state.
        cursor = self._cursor_controller
        if cursor is not None and cursor.tracks_pointer_motion:
            cursor.note_pointer_motion()

        if self._custom_layout_input_blocked:
            super().mouseMoveEvent(event)
            return

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
        if event.button() == Qt.MouseButton.LeftButton:
            active = self._plain_orbit_card is not None
            self.cancel_plain_orbit()
            if active:
                event.accept()
                return
        if self._custom_layout_input_blocked:
            # Ordinary right-click opened the retained context menu. Alt-right
            # may instead be grabbed by Edit's move area; finish that same QML
            # grab even when Alt was released before the mouse button.
            if (
                event.button() == Qt.MouseButton.RightButton
                and self.mouseGrabberItem() is None
            ):
                event.accept()
                return
            super().mouseReleaseEvent(event)
            return
        if self._runtime_discrete_pointer_event_is_suppressed("mouseReleaseEvent"):
            event.accept()
            return
        controller = self._input_controller
        if controller is not None and controller.handle_mouse_release(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        # Alt + wheel over a shown 3D Visualizer resizes it outside Edit; the input owner
        # declines every other wheel, which goes on to QML (volume and Edit wheels) unchanged.
        if not self._custom_layout_input_blocked:
            controller = self._input_controller
            if controller is not None and controller.handle_wheel(event):
                event.accept()
                return
        super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.cancel_plain_orbit()
        if self._custom_layout_input_blocked:
            super().mouseDoubleClickEvent(event)
            return
        if self._runtime_discrete_pointer_event_is_suppressed("mouseDoubleClickEvent"):
            event.accept()
            return
        controller = self._input_controller
        if (
            event.button() == Qt.MouseButton.RightButton
            and not event.modifiers() & Qt.KeyboardModifier.AltModifier
            and controller is not None
            and controller.handle_mouse_double_click(event)
        ):
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
        self.cancel_plain_orbit()
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

    @property
    def scene_rect(self) -> QRectF | None:
        """The window's on-desktop rectangle (its monitor), once the native window exists."""

        return self._scene_rect

    def _native_rects(self):
        """``(hwnd, window, monitor, virtual)`` device rects from Win32, or ``None``."""

        import sys

        if sys.platform != "win32":
            return None
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
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int

        hwnd = wintypes.HWND(int(self.winId()))
        rect = _Rect()
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        handle = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        if (
            not user32.GetWindowRect(hwnd, ctypes.byref(rect))
            or not handle
            or not user32.GetMonitorInfoW(handle, ctypes.byref(info))
        ):
            return None
        mr = info.rcMonitor
        v_left = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        v_top = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
        virtual = (
            v_left,
            v_top,
            v_left + user32.GetSystemMetrics(78),  # SM_CXVIRTUALSCREEN
            v_top + user32.GetSystemMetrics(79),   # SM_CYVIRTUALSCREEN
        )
        return (
            hwnd,
            (rect.left, rect.top, rect.right, rect.bottom),
            (mr.left, mr.top, mr.right, mr.bottom),
            virtual,
        )

    def _apply_native_compat_geometry(self) -> None:
        """Place the window on device pixels, then publish the monitor's rect inside it.

        Qt's logical R-63 overscan (``_fullscreen_compat_geometry``) keeps the
        window from being exact cover, but at a fractional DPR it rounds a pixel
        onto the shared edge too: Display 0 at 150% was 2561 device pixels wide
        against its 2560-pixel monitor, overdrawing Display 1. Once the native
        window exists its rectangle is re-set in device pixels from the real
        monitor and virtual-desktop rectangles (``compat_native_rect``: the
        monitor plus overscan on one exterior edge only). Runs on show and
        screen-geometry edges only; never on render or pointer paths.
        """

        if self.geometry().getRect() not in self._compat_logical_rects:
            # Placed by something other than the R-63 screen geometry.
            self._refresh_scene_rect()
            return
        rects = self._native_rects()
        if rects is None:
            if self._native_rects_expected():
                logger.warning(
                    "[QUICK_NATIVE_GEOMETRY] native rects unavailable screen=%d; keeping Qt geometry",
                    self._screen_index,
                )
            return
        hwnd, current, monitor, virtual = rects
        dpr = float(self.effectiveDevicePixelRatio())
        desired = compat_native_rect(monitor, virtual, dpr)
        if current != desired:
            import ctypes
            from ctypes import wintypes

            set_window_pos = ctypes.windll.user32.SetWindowPos
            set_window_pos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, wintypes.UINT,
            ]
            set_window_pos.restype = wintypes.BOOL
            # SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER
            if not set_window_pos(
                hwnd, None, desired[0], desired[1],
                desired[2] - desired[0], desired[3] - desired[1], 0x0004 | 0x0010 | 0x0200,
            ):
                logger.warning(
                    "[QUICK_NATIVE_GEOMETRY] SetWindowPos failed screen=%d; keeping Qt geometry",
                    self._screen_index,
                )
            rects = self._native_rects() or rects
            _hwnd, current, monitor, _virtual = rects
            # Qt's logical view of the corrected native rect is ours too.
            self._compat_logical_rects.add(self.geometry().getRect())
        wl, wt, wr, wb = current
        logger.info(
            "[QUICK_NATIVE_GEOMETRY] screen=%d generation=%s "
            "window_device=(%d,%d,%d,%d) monitor_device=(%d,%d,%d,%d) "
            "overscan_device=(left=%d,top=%d,right=%d,bottom=%d) dpr=%.3f",
            self._screen_index,
            self._runtime_generation,
            wl, wt, wr - wl, wb - wt,
            monitor[0], monitor[1], monitor[2] - monitor[0], monitor[3] - monitor[1],
            monitor[0] - wl, monitor[1] - wt, wr - monitor[2], wb - monitor[3],
            dpr,
        )
        self._refresh_scene_rect()

    @staticmethod
    def _native_rects_expected() -> bool:
        import sys

        return sys.platform == "win32"

    def _refresh_scene_rect(self, *_args: object) -> None:
        self.cancel_plain_orbit()
        """Publish the window's on-desktop rect: exactly the monitor for the R-63 window.

        The R-63 overscan lies off the virtual desktop and is never visible, so
        the scene is not laid out on it. ``None`` (fill the window, as before)
        until the native window exists.
        """

        rects = self._native_rects() if self.isVisible() else None
        scene: QRectF | None = None
        if rects is not None:
            _hwnd, window, _monitor, virtual = rects
            visible = visible_rect_in_window(
                window, virtual, float(self.effectiveDevicePixelRatio())
            )
            if visible is not None:
                scene = QRectF(*visible)
        if scene != self._scene_rect:
            self._scene_rect = scene
            self.scene_rect_changed.emit(scene)

    def _on_screen_metrics_changed(self, *_args: object) -> None:
        self.cancel_plain_orbit()
        screen = self._bound_screen
        if screen is None or self._close_queued or self._binding_loss is not None:
            return
        self._apply_screen_geometry(screen)
        self.refresh_display_identity()

    def _on_window_visibility_changed(self, visible: bool) -> None:
        if not visible or not self._desired_visible or self._close_queued:
            return
        self._apply_native_compat_geometry()
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
        self._compat_logical_rects = {adjusted.getRect(), self.geometry().getRect()}

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
        if self.isVisible():
            # Qt just re-set the logical geometry; restore the device-exact rect.
            self._apply_native_compat_geometry()

    def _queue_meta_call(self, method: str) -> None:
        if not QMetaObject.invokeMethod(
            self,
            method,
            Qt.ConnectionType.QueuedConnection,
        ):
            raise RuntimeError(f"could not queue QQuickWindow.{method}()")
