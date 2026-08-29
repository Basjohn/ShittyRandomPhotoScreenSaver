"""Generation-scoped input admission for one Qt Quick display runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent

from rendering.runtime_input import RuntimeInputOwner

from .state import QuickInputState


class QuickInputController(RuntimeInputOwner):
    """Apply shared product input policy without retaining widget-era owners."""

    input_state_changed = Signal(object)

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int | None,
        interaction_mode_provider: Callable[[], bool] | None = None,
        global_ctrl_held_provider: Callable[[], bool] | None = None,
        ctrl_state_publisher: Callable[[bool], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(
            parent,
            interaction_mode_provider=interaction_mode_provider,
            global_ctrl_held_provider=global_ctrl_held_provider,
            ctrl_state_publisher=ctrl_state_publisher,
            consume_control_key=True,
        )
        self._state = QuickInputState(
            screen_index=int(screen_index),
            runtime_generation=(
                None if runtime_generation is None else int(runtime_generation)
            ),
        )

    @property
    def screen_index(self) -> int:
        return self._state.screen_index

    @property
    def runtime_generation(self) -> int | None:
        return self._state.runtime_generation

    @property
    def input_state(self) -> QuickInputState:
        return self._state

    def is_interaction_mode_enabled(self) -> bool:
        enabled = super().is_interaction_mode_enabled()
        self._publish_state(interaction_mode_enabled=enabled)
        return enabled

    def set_ctrl_held(self, held: bool) -> None:
        super().set_ctrl_held(held)
        self.is_ctrl_mode_active()

    def is_ctrl_mode_active(self) -> bool:
        # The cross-display coordinator is authoritative for Ctrl mode. A display
        # must not stay stuck on a stale local Ctrl-held after focus moved to a
        # peer and the shared state cleared (the release lands on the focused
        # display). Local input still feeds the coordinator via set_ctrl_held()'s
        # publisher; when no coordinator is wired we keep the local base behavior.
        global_state = self._global_ctrl_held()
        active = (
            global_state
            if global_state is not None
            else super().is_ctrl_mode_active()
        )
        self._publish_state(ctrl_held=active)
        return active

    def set_context_menu_active(self, active: bool) -> None:
        super().set_context_menu_active(active)
        self._publish_state(context_menu_active=bool(active))

    def handle_key_press(self, event: QKeyEvent) -> bool:
        if not self._state.admission_open:
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
        self._publish_state(
            admission_open=False,
            interaction_mode_enabled=False,
            ctrl_held=False,
            context_menu_active=False,
        )
        return True

    def describe_input_state(self) -> dict[str, object]:
        return self._state.as_dict()

    def _request_exit(self) -> None:
        self._exiting = True
        self._publish_state(exiting=True)
        self.exit_requested.emit()

    def _publish_state(self, **changes: object) -> None:
        next_state = replace(self._state, **changes)
        if next_state == self._state:
            return
        self._state = next_state
        self.input_state_changed.emit(next_state)
