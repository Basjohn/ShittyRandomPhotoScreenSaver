"""Presentation-neutral runtime keyboard and pointer input ownership."""

from __future__ import annotations

from collections.abc import Callable
import math
import time

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

from core.logging.logger import get_logger


logger = get_logger(__name__)


_pointer_input_suppressed_until_ts = 0.0
_pointer_input_suppression_reason = ""


def suppress_runtime_pointer_input(
    duration_ms: int = 700,
    *,
    reason: str = "",
) -> None:
    """Arm the process-wide pointer guard across a runtime replacement."""

    global _pointer_input_suppressed_until_ts
    global _pointer_input_suppression_reason

    duration_sec = max(0.0, float(duration_ms) / 1000.0)
    _pointer_input_suppressed_until_ts = max(
        _pointer_input_suppressed_until_ts,
        time.monotonic() + duration_sec,
    )
    _pointer_input_suppression_reason = str(reason or "").strip()


def clear_runtime_pointer_input_suppression() -> None:
    """Clear the replacement pointer guard (primarily for deterministic tests)."""

    global _pointer_input_suppressed_until_ts
    global _pointer_input_suppression_reason

    _pointer_input_suppressed_until_ts = 0.0
    _pointer_input_suppression_reason = ""


def runtime_pointer_input_is_suppressed(
    source: str,
    *,
    screen_index: int | str = "?",
) -> bool:
    """Return whether one pointer event belongs to the replacement guard window."""

    deadline = float(_pointer_input_suppressed_until_ts or 0.0)
    if deadline <= 0.0:
        return False
    now = time.monotonic()
    if now >= deadline:
        clear_runtime_pointer_input_suppression()
        return False
    logger.debug(
        "[INPUT_GUARD] Suppressed %s on screen=%s during runtime recreation "
        "(reason=%s, remaining_ms=%.1f)",
        source,
        screen_index,
        _pointer_input_suppression_reason or "unspecified",
        max(0.0, (deadline - now) * 1000.0),
    )
    return True


class RuntimeInputOwner(QObject):
    """Own shared runtime hotkeys and exit gestures for any presentation host."""

    exit_requested = Signal()
    next_image_requested = Signal()
    previous_image_requested = Signal()
    cycle_transition_requested = Signal()
    play_pause_requested = Signal()
    home_play_pause_requested = Signal()
    previous_track_requested = Signal()
    next_track_requested = Signal()
    slider_volume_up_requested = Signal()
    slider_volume_down_requested = Signal()
    global_volume_up_requested = Signal()
    global_volume_down_requested = Signal()
    global_mute_toggle_requested = Signal()
    context_menu_requested = Signal(QPoint)
    layout_slot_load_requested = Signal(str)
    layout_slot_save_requested = Signal(str)
    # While a 3D freeform Visualizer is shown: W/A/S/D publish the held keys' combined direction
    # (turn, tilt) whenever it changes (the view turns at a steady rate while held, whatever the
    # OS key repeat does); an Alt + left drag on it in interaction/Ctrl mode steps it (a step per
    # DRAG_PIXELS_PER_STEP pixels); orbiting finishes once no key is held and no drag is on.
    view_orbit_rates_changed = Signal(float, float)
    view_orbit_requested = Signal(float, float)
    view_orbit_finished = Signal()
    VIEW_ORBIT_DRAG_PIXELS_PER_STEP = 4.0
    # On the same shown 3D Visualizer, Alt + right drag moves it and Alt + wheel resizes it,
    # outside Edit (in interaction or Ctrl mode, like the orbit): the move as the pointer's
    # global offset since the press (and its global position), the resize one wheel step at a
    # time. The gesture finishes at the drag's release, or when Alt is released after wheeling.
    visualizer_move_started = Signal()
    visualizer_move_requested = Signal(QPoint, QPoint)
    visualizer_scale_requested = Signal(int)
    visualizer_gesture_finished = Signal()

    MOUSE_EXIT_THRESHOLD = 10
    # The camera moves around the scene: W up over it, S down, A left, D right.
    _VIEW_ORBIT_KEYS = {
        Qt.Key.Key_W: (0, 1), Qt.Key.Key_S: (0, -1), Qt.Key.Key_A: (1, 0), Qt.Key.Key_D: (-1, 0),
    }
    _VIEW_ORBIT_VK = {0x57: Qt.Key.Key_W, 0x53: Qt.Key.Key_S, 0x41: Qt.Key.Key_A, 0x44: Qt.Key.Key_D}

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        interaction_mode_provider: Callable[[], bool] | None = None,
        global_ctrl_held_provider: Callable[[], bool] | None = None,
        ctrl_state_publisher: Callable[[bool], None] | None = None,
        consume_control_key: bool = False,
    ) -> None:
        super().__init__(parent)
        self._interaction_mode_provider = interaction_mode_provider
        self._global_ctrl_held_provider = global_ctrl_held_provider
        self._ctrl_state_publisher = ctrl_state_publisher
        self._consume_control_key = bool(consume_control_key)
        self._mouse_press_pos: QPoint | None = None
        self._mouse_press_time = 0.0
        self._last_mouse_pos: QPoint | None = None
        self._initial_mouse_pos: QPoint | None = None
        self._ctrl_held = False
        self._exit_gesture_active = False
        self._exiting = False
        self._context_menu_active = False
        self._view_orbit_enabled = False
        self._view_orbit_held: set[Qt.Key] = set()
        # Whether a scene point lies on the shown Visualizer (set by the display's runtime).
        self._view_orbit_hit_test: Callable[[QPointF], bool] | None = None
        self._view_orbit_drag: QPointF | None = None      # the last drag position while dragging
        self._visualizer_drag_origin: QPoint | None = None   # Alt + right drag: the global press point
        self._visualizer_wheeling = False                    # Alt + wheel steps since Alt went down

    def is_interaction_mode_enabled(self) -> bool:
        provider = self._interaction_mode_provider
        if provider is None:
            return False
        try:
            return bool(provider())
        except Exception:
            logger.exception("[RUNTIME_INPUT] Interaction-mode provider failed")
            return False

    def set_ctrl_held(self, held: bool) -> None:
        normalized = bool(held)
        self._ctrl_held = normalized
        publisher = self._ctrl_state_publisher
        if publisher is not None:
            try:
                publisher(normalized)
            except Exception:
                logger.exception("[RUNTIME_INPUT] Ctrl-state publisher failed")

    def is_ctrl_held(self) -> bool:
        return self._ctrl_held

    def _global_ctrl_held(self) -> bool | None:
        """Coordinator Ctrl state, or None when no cross-display coordinator wired."""

        provider = self._global_ctrl_held_provider
        if provider is None:
            return None
        try:
            return bool(provider())
        except Exception:
            logger.exception("[RUNTIME_INPUT] Global Ctrl-state provider failed")
            return None

    def is_ctrl_mode_active(self) -> bool:
        if self._ctrl_held:
            return True
        global_state = self._global_ctrl_held()
        return bool(global_state) if global_state is not None else False

    def set_context_menu_active(self, active: bool) -> None:
        self._context_menu_active = bool(active)

    def set_view_orbit_enabled(self, enabled: bool) -> None:
        """Event-published fact: a 3D freeform Visualizer is shown, so W/A/S/D orbit it."""
        enabled = bool(enabled)
        if not enabled and self._view_orbiting():
            self._view_orbit_held.clear()
            self._view_orbit_drag = None
            self.view_orbit_finished.emit()
        if not enabled:
            self._end_visualizer_gesture()
        self._view_orbit_enabled = enabled

    def set_view_orbit_hit_test(self, hit_test: Callable[[QPointF], bool] | None) -> None:
        """The display runtime's test for a scene point on its shown Visualizer (None at retirement)."""
        self._view_orbit_hit_test = hit_test
        if hit_test is None:
            self._view_orbit_drag = None

    def _held_view_orbit_rates(self) -> tuple[float, float]:
        turn = sum(self._VIEW_ORBIT_KEYS[key][0] for key in self._view_orbit_held)
        tilt = sum(self._VIEW_ORBIT_KEYS[key][1] for key in self._view_orbit_held)
        return float(turn), float(tilt)

    def _view_orbiting(self) -> bool:
        return bool(self._view_orbit_held) or self._view_orbit_drag is not None

    @classmethod
    def view_orbit_drag_steps(cls, delta_x: float, delta_y: float) -> tuple[float, float]:
        """Convert a physical drag delta through the one shared orbit gesture scale."""

        step = cls.VIEW_ORBIT_DRAG_PIXELS_PER_STEP
        return float(delta_x) / step, float(delta_y) / step

    def _finish_view_orbit_if_idle(self) -> None:
        if not self._view_orbiting():
            self.view_orbit_finished.emit()

    def _alt_gesture_on_visualizer(self, modifiers, position: QPointF, ctrl_mode_active: bool) -> bool:
        """Alt held over the shown 3D Visualizer, in interaction or Ctrl mode."""
        hit_test = self._view_orbit_hit_test
        return bool(
            self._view_orbit_enabled
            and hit_test is not None
            and modifiers & Qt.KeyboardModifier.AltModifier
            and (self.is_interaction_mode_enabled() or ctrl_mode_active)
            and hit_test(position)
        )

    def _starts_view_orbit_drag(self, event: QMouseEvent, ctrl_mode_active: bool) -> bool:
        return (event.button() == Qt.MouseButton.LeftButton
                and self._alt_gesture_on_visualizer(event.modifiers(), event.position(), ctrl_mode_active))

    def _visualizer_gesture_active(self) -> bool:
        return self._visualizer_drag_origin is not None or self._visualizer_wheeling

    def _end_visualizer_gesture(self) -> None:
        """End any direct Visualizer gesture (finished once, by whichever part ends last)."""
        active = self._visualizer_gesture_active()
        self._visualizer_drag_origin = None
        self._visualizer_wheeling = False
        if active:
            self.visualizer_gesture_finished.emit()

    def handle_wheel(self, event: QWheelEvent, global_ctrl_held: bool = False) -> bool:
        """Alt + wheel over the shown 3D Visualizer resizes it (before its volume wheel)."""
        if self._should_suppress_runtime_pointer_input("wheelEvent"):
            return False
        ctrl_mode_active = self.is_ctrl_mode_active() or bool(global_ctrl_held)
        if not self._alt_gesture_on_visualizer(event.modifiers(), event.position(), ctrl_mode_active):
            return False
        # With Alt held Qt may report the vertical wheel as horizontal.
        delta = event.angleDelta()
        step = self.wheel_angle_step(delta.x(), delta.y())
        if step:
            self._visualizer_wheeling = True
            self.visualizer_scale_requested.emit(step)
        return True

    @staticmethod
    def wheel_angle_step(delta_x: int, delta_y: int) -> int:
        """Preserve Qt's signed wheel delta, including its Alt axis remapping."""
        return int(delta_y or delta_x)

    def is_view_orbit_enabled(self) -> bool:
        return self._view_orbit_enabled

    def _view_orbit_key(self, event: QKeyEvent) -> Qt.Key | None:
        key = event.key()
        if key in self._VIEW_ORBIT_KEYS:
            return Qt.Key(key)
        try:
            return self._VIEW_ORBIT_VK.get(int(event.nativeVirtualKey() or 0))
        except Exception:
            return None

    def is_context_menu_active(self) -> bool:
        return self._context_menu_active

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Route the shared hotkey/exit policy and report event consumption."""

        key = event.key()
        try:
            key_text = event.text().lower() if event.text() else ""
        except Exception:
            key_text = ""
        try:
            native_vk = int(event.nativeVirtualKey() or 0)
        except Exception:
            native_vk = 0

        logger.debug(
            "[RUNTIME_INPUT] Key press: key=%s text=%s native_vk=%s",
            key,
            key_text,
            native_vk,
        )

        if key == Qt.Key.Key_Control:
            if self._consume_control_key:
                self.set_ctrl_held(True)
                return True
            return False
        if key == Qt.Key.Key_Shift:
            return True
        if self._is_media_key(event):
            self._handle_media_key_passthrough(event)
            return False

        slot_id = self._layout_slot_id_for_key_event(event)
        if slot_id is not None:
            if bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.layout_slot_save_requested.emit(slot_id)
            else:
                self.layout_slot_load_requested.emit(slot_id)
            return True
        if key_text == "z" or key == Qt.Key.Key_Z or native_vk == 0x5A:
            self.previous_image_requested.emit()
            return True
        if key == Qt.Key.Key_Left:
            self.previous_track_requested.emit()
            return True
        if key_text == "x" or key == Qt.Key.Key_X or native_vk == 0x58:
            self.next_image_requested.emit()
            return True
        if key == Qt.Key.Key_Right:
            self.next_track_requested.emit()
            return True
        if key_text == "c" or key == Qt.Key.Key_C or native_vk == 0x43:
            self.cycle_transition_requested.emit()
            return True
        if self._view_orbit_enabled:
            orbit_key = self._view_orbit_key(event)
            if orbit_key is not None:
                # Key repeat changes nothing: the view already turns while the key is held.
                if not event.isAutoRepeat() and orbit_key not in self._view_orbit_held:
                    self._view_orbit_held.add(orbit_key)
                    self.view_orbit_rates_changed.emit(*self._held_view_orbit_rates())
                return True
        if key == Qt.Key.Key_Space:
            self.play_pause_requested.emit()
            return True
        if key == Qt.Key.Key_Up:
            self.slider_volume_up_requested.emit()
            return True
        if key == Qt.Key.Key_Down:
            self.slider_volume_down_requested.emit()
            return True
        if key == Qt.Key.Key_PageUp:
            self.global_volume_up_requested.emit()
            return True
        if key == Qt.Key.Key_PageDown:
            self.global_volume_down_requested.emit()
            return True
        if key == Qt.Key.Key_Home:
            self.home_play_pause_requested.emit()
            return True
        if key == Qt.Key.Key_End:
            self.global_mute_toggle_requested.emit()
            return True
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            self._request_exit()
            return True
        if self.is_interaction_mode_enabled() or self.is_ctrl_mode_active():
            return False

        self._request_exit()
        return True

    def handle_key_release(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Control and self._consume_control_key:
            self.set_ctrl_held(False)
            return True
        if event.key() == Qt.Key.Key_Alt and self._visualizer_wheeling and not event.isAutoRepeat():
            self._visualizer_wheeling = False
            if self._visualizer_drag_origin is None:
                self.visualizer_gesture_finished.emit()
            return True
        orbit_key = self._view_orbit_key(event) if self._view_orbit_held else None
        if orbit_key is not None:
            # Key repeat delivers release/press pairs while the key stays down: orbiting ends
            # only on the real release of the last held key, so the result is saved once.
            if not event.isAutoRepeat() and orbit_key in self._view_orbit_held:
                self._view_orbit_held.discard(orbit_key)
                self.view_orbit_rates_changed.emit(*self._held_view_orbit_rates())
                self._finish_view_orbit_if_idle()
            return True
        return False

    def handle_mouse_press(
        self,
        event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        if self._should_suppress_runtime_pointer_input("mousePressEvent"):
            return True
        ctrl_mode_active = self.is_ctrl_mode_active() or bool(global_ctrl_held)
        if self._starts_view_orbit_drag(event, ctrl_mode_active):
            self._view_orbit_drag = QPointF(event.position())
            return True
        if (event.button() == Qt.MouseButton.RightButton
                and self._alt_gesture_on_visualizer(event.modifiers(), event.position(), ctrl_mode_active)):
            # Alt + right on the Visualizer moves it; no context menu while Alt is held there.
            self._visualizer_drag_origin = self._global_mouse_point(event)
            self.visualizer_move_started.emit()
            return True
        self._mouse_press_pos = self._local_mouse_point(event)
        self._mouse_press_time = time.time()

        if event.button() == Qt.MouseButton.RightButton:
            if self.is_interaction_mode_enabled() or ctrl_mode_active:
                self.context_menu_requested.emit(self._global_mouse_point(event))
                return True
        if event.button() == Qt.MouseButton.LeftButton:
            if ctrl_mode_active or self.is_interaction_mode_enabled():
                return False
            if not self._context_menu_active:
                self._request_exit()
                return True
        return False

    def handle_mouse_move(
        self,
        event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        if self._should_suppress_runtime_pointer_input("mouseMoveEvent"):
            return True
        if self._visualizer_drag_origin is not None:
            cursor = self._global_mouse_point(event)
            self.visualizer_move_requested.emit(cursor - self._visualizer_drag_origin, cursor)
            return True
        if self._view_orbit_drag is not None:
            # Dragging right moves the camera left round the scene (it turns toward the drag);
            # dragging down raises the camera over it.
            position = QPointF(event.position())
            delta = position - self._view_orbit_drag
            self._view_orbit_drag = position
            if delta.x() or delta.y():
                self.view_orbit_requested.emit(*self.view_orbit_drag_steps(delta.x(), delta.y()))
            return True
        if self._context_menu_active:
            return False
        if (
            self.is_interaction_mode_enabled()
            or self.is_ctrl_mode_active()
            or bool(global_ctrl_held)
        ):
            return False

        current_pos = self._local_mouse_point(event)
        if self._initial_mouse_pos is None:
            self._initial_mouse_pos = current_pos
            return False
        delta = current_pos - self._initial_mouse_pos
        if math.hypot(delta.x(), delta.y()) > self.MOUSE_EXIT_THRESHOLD:
            self._request_exit()
            return True
        return False

    def handle_mouse_release(
        self,
        _event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        if self._should_suppress_runtime_pointer_input("mouseReleaseEvent"):
            return True
        del global_ctrl_held
        if self._view_orbit_drag is not None and _event.button() == Qt.MouseButton.LeftButton:
            self._view_orbit_drag = None
            self._finish_view_orbit_if_idle()
            return True
        if self._visualizer_drag_origin is not None and _event.button() == Qt.MouseButton.RightButton:
            self._visualizer_drag_origin = None
            if not self._visualizer_wheeling:
                self.visualizer_gesture_finished.emit()
            return True
        self._mouse_press_pos = None
        self._mouse_press_time = 0.0
        return False

    def handle_mouse_double_click(self, _event: QMouseEvent) -> bool:
        if self._should_suppress_runtime_pointer_input("mouseDoubleClickEvent"):
            return True
        if self._context_menu_active:
            return False
        self.next_image_requested.emit()
        return True

    def reset_initial_position(self) -> None:
        self._initial_mouse_pos = None

    def is_exiting(self) -> bool:
        return self._exiting

    def set_exiting(self, exiting: bool) -> None:
        self._exiting = bool(exiting)

    def _should_suppress_runtime_pointer_input(self, source: str) -> bool:
        return runtime_pointer_input_is_suppressed(
            source,
            screen_index=getattr(self, "screen_index", "?"),
        )

    def cleanup(self) -> None:
        if self._ctrl_held:
            self.set_ctrl_held(False)
        self._mouse_press_pos = None
        self._last_mouse_pos = None
        self._initial_mouse_pos = None
        self._ctrl_held = False
        self._exit_gesture_active = False
        self._context_menu_active = False
        self._interaction_mode_provider = None
        self._global_ctrl_held_provider = None
        self._ctrl_state_publisher = None
        # A closed input holds nothing of its scene; an orbit in progress ends here.
        orbiting = self._view_orbiting()
        self._end_visualizer_gesture()
        self._view_orbit_hit_test = None
        self._view_orbit_drag = None
        self._view_orbit_held.clear()
        self._view_orbit_enabled = False
        if orbiting:
            self.view_orbit_finished.emit()

    def _request_exit(self) -> None:
        self._exiting = True
        self.exit_requested.emit()

    def _handle_media_key_passthrough(self, _event: QKeyEvent) -> None:
        """Extension point for legacy visual key feedback."""

    @staticmethod
    def _local_mouse_point(event: QMouseEvent) -> QPoint:
        position = getattr(event, "position", None)
        if callable(position):
            return position().toPoint()
        return event.pos()

    @staticmethod
    def _global_mouse_point(event: QMouseEvent) -> QPoint:
        position = getattr(event, "globalPosition", None)
        if callable(position):
            return position().toPoint()
        return event.globalPos()

    @staticmethod
    def _layout_slot_id_for_key_event(event: QKeyEvent) -> str | None:
        key_map = {
            Qt.Key.Key_1: "1",
            Qt.Key.Key_2: "2",
            Qt.Key.Key_3: "3",
            Qt.Key.Key_4: "4",
            Qt.Key.Key_5: "5",
            Qt.Key.Key_6: "6",
            Qt.Key.Key_7: "7",
            Qt.Key.Key_8: "8",
            Qt.Key.Key_9: "9",
            Qt.Key.Key_0: "0",
            Qt.Key.Key_Exclam: "1",
            Qt.Key.Key_At: "2",
            Qt.Key.Key_NumberSign: "3",
            Qt.Key.Key_Dollar: "4",
            Qt.Key.Key_Percent: "5",
            Qt.Key.Key_AsciiCircum: "6",
            Qt.Key.Key_Ampersand: "7",
            Qt.Key.Key_Asterisk: "8",
            Qt.Key.Key_ParenLeft: "9",
            Qt.Key.Key_ParenRight: "0",
        }
        slot_id = key_map.get(event.key())
        if slot_id is not None:
            return slot_id
        try:
            native_vk = int(event.nativeVirtualKey() or 0)
        except Exception:
            native_vk = 0
        if 0x30 <= native_vk <= 0x39:
            return chr(native_vk)
        return None

    @staticmethod
    def _is_media_key(event: QKeyEvent) -> bool:
        if event.key() in {
            Qt.Key.Key_MediaPlay,
            Qt.Key.Key_MediaPause,
            Qt.Key.Key_MediaTogglePlayPause,
            Qt.Key.Key_MediaNext,
            Qt.Key.Key_MediaPrevious,
            Qt.Key.Key_VolumeUp,
            Qt.Key.Key_VolumeDown,
            Qt.Key.Key_VolumeMute,
        }:
            return True
        try:
            native_vk = int(event.nativeVirtualKey() or 0)
        except Exception:
            native_vk = 0
        return native_vk in {
            0xAD,
            0xAE,
            0xAF,
            0xB0,
            0xB1,
            0xB2,
            0xB3,
        }
