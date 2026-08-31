"""Generation-scoped input admission for one Qt Quick display runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent

from rendering.runtime_input import RuntimeInputOwner

from .state import QuickInputState


class QuickInputController(RuntimeInputOwner):
    """Apply shared product input policy without hot-path Settings/provider reads."""

    input_state_changed = Signal(object)
    custom_layout_save_requested = Signal()
    custom_layout_cancel_requested = Signal()

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int | None,
        interaction_mode_enabled: bool = False,
        ctrl_state_publisher: Callable[[bool], None] | None = None,
        custom_layout_active_provider: Callable[[], bool] | None = None,
        parent: QObject | None = None,
    ) -> None:
        # Quick owns interaction/Ctrl as event-updated generation-scoped facts.
        # Do not retain live providers here: passive pointer motion must never
        # query Settings or cross-display state at mouse polling frequency.
        super().__init__(
            parent,
            interaction_mode_provider=None,
            global_ctrl_held_provider=None,
            ctrl_state_publisher=ctrl_state_publisher,
            consume_control_key=True,
        )
        self._state = QuickInputState(
            screen_index=int(screen_index),
            runtime_generation=(
                None if runtime_generation is None else int(runtime_generation)
            ),
            interaction_mode_enabled=bool(interaction_mode_enabled),
        )
        self._custom_layout_active_provider = custom_layout_active_provider

    @property
    def screen_index(self) -> int:
        return self._state.screen_index

    @property
    def runtime_generation(self) -> int | None:
        return self._state.runtime_generation

    @property
    def input_state(self) -> QuickInputState:
        return self._state

    @property
    def passive_mouse_move_requires_routing(self) -> bool:
        """Whether pointer motion can still trigger the non-interaction exit gesture."""

        state = self._state
        return bool(
            state.admission_open
            and not state.exiting
            and not state.context_menu_active
            and not state.interaction_mode_enabled
            and not state.ctrl_held
        )

    def set_interaction_mode_enabled(self, enabled: bool) -> bool:
        """Publish event-driven interaction admission; never re-read Settings here."""

        if not self._state.admission_open:
            return False
        return self._publish_state(interaction_mode_enabled=bool(enabled))

    def is_interaction_mode_enabled(self) -> bool:
        return bool(self._state.interaction_mode_enabled)

    def set_ctrl_held(self, held: bool) -> None:
        """Publish this display's Ctrl contribution to the shared coordinator."""

        has_shared_publisher = self._ctrl_state_publisher is not None
        super().set_ctrl_held(held)
        if not has_shared_publisher:
            self.set_shared_ctrl_held(bool(held))

    def set_shared_ctrl_held(self, held: bool) -> bool:
        """Accept the coordinator's event-driven global Ctrl truth."""

        if not self._state.admission_open:
            return False
        return self._publish_state(ctrl_held=bool(held))

    def is_ctrl_mode_active(self) -> bool:
        return bool(self._state.ctrl_held)

    def set_context_menu_active(self, active: bool) -> None:
        super().set_context_menu_active(active)
        self._publish_state(context_menu_active=bool(active))

    def handle_key_press(self, event: QKeyEvent) -> bool:
        if not self._state.admission_open:
            return True
        provider = self._custom_layout_active_provider
        custom_active = bool(provider is not None and provider())
        if custom_active and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self.custom_layout_save_requested.emit()
            return True
        if custom_active and event.key() == Qt.Key.Key_Escape:
            self.custom_layout_cancel_requested.emit()
            return True
        return super().handle_key_press(event)

    def handle_key_release(self, event: QKeyEvent) -> bool:
        if not self._state.admission_open:
            return True
        return super().handle_key_release(event)

    def handle_mouse_press(
        self,
        event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        if not self._state.admission_open:
            return True
        return super().handle_mouse_press(event, global_ctrl_held)

    def handle_mouse_move(
        self,
        event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        if not self._state.admission_open:
            return True
        return super().handle_mouse_move(event, global_ctrl_held)

    def handle_mouse_release(
        self,
        event: QMouseEvent,
        global_ctrl_held: bool = False,
    ) -> bool:
        if not self._state.admission_open:
            return True
        return super().handle_mouse_release(event, global_ctrl_held)

    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        if not self._state.admission_open:
            return True
        return super().handle_mouse_double_click(event)

    def close_input(self) -> bool:
        """Close admission before scene/window retirement begins."""

        if not self._state.admission_open:
            return False
        super().cleanup()
        self._custom_layout_active_provider = None
        self._publish_state(
            admission_open=False,
            interaction_mode_enabled=False,
            ctrl_held=False,
            context_menu_active=False,
        )
        return True

    def describe_input_state(self) -> dict[str, object]:
        state = self._state.as_dict()
        state["interaction_owner"] = "event_cached"
        state["ctrl_owner"] = "event_cached_shared"
        state["passive_mouse_move_requires_routing"] = (
            self.passive_mouse_move_requires_routing
        )
        return state

    def _request_exit(self) -> None:
        self._exiting = True
        self._publish_state(exiting=True)
        self.exit_requested.emit()

    def _publish_state(self, **changes: object) -> bool:
        next_state = replace(self._state, **changes)
        if next_state == self._state:
            return False
        self._state = next_state
        self.input_state_changed.emit(next_state)
        return True
