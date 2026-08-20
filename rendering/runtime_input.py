"""Presentation-neutral runtime keyboard and pointer input ownership."""

from __future__ import annotations

from collections.abc import Callable
import math
import time

from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent

from core.logging.logger import get_logger


logger = get_logger(__name__)


class RuntimeInputOwner(QObject):
    """Own shared runtime hotkeys and exit gestures for any presentation host."""

    exit_requested = Signal()
    settings_requested = Signal()
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

    MOUSE_EXIT_THRESHOLD = 10

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

    def is_ctrl_mode_active(self) -> bool:
        if self._ctrl_held:
            return True
        provider = self._global_ctrl_held_provider
        if provider is None:
            return False
        try:
            return bool(provider())
        except Exception:
            logger.exception("[RUNTIME_INPUT] Global Ctrl-state provider failed")
            return False

    def set_context_menu_active(self, active: bool) -> None:
        self._context_menu_active = bool(active)

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
        if key_text == "s" or key == Qt.Key.Key_S or native_vk == 0x53:
            self.settings_requested.emit()
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
        return False

    def handle_mouse_press(
        self,
        event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        ctrl_mode_active = self.is_ctrl_mode_active() or bool(global_ctrl_held)
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
        del global_ctrl_held
        self._mouse_press_pos = None
        self._mouse_press_time = 0.0
        return False

    def handle_mouse_double_click(self, _event: QMouseEvent) -> bool:
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
