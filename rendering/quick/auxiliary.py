"""Generation-scoped retained dimming and pixel-shift state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import random

from PySide6.QtCore import QObject, QTimer, Signal

from .state import QuickInputState


_HALO_SHAPES = frozenset(
    {
        "circle",
        "ring",
        "crosshair",
        "diamond",
        "dot",
        "cursor_light",
        "cursor_dark",
    }
)


@dataclass(frozen=True, slots=True)
class QuickAuxiliaryState:
    """Primitive auxiliary presentation facts for one display generation."""

    screen_index: int
    runtime_generation: int | None
    dimming_enabled: bool = False
    dimming_opacity: float = 0.0
    pixel_shift_enabled: bool = False
    pixel_shift_x: int = 0
    pixel_shift_y: int = 0
    shifts_per_minute: int = 1
    halo_enabled: bool = False
    native_cursor_visible: bool = False
    halo_shape: str = "cursor_light"
    admission_open: bool = True


class QuickAuxiliaryController(QObject):
    """Own retained auxiliary cadence without owning settings or pixels."""

    MAX_PIXEL_SHIFT = 4
    state_changed = Signal(object)

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = QuickAuxiliaryState(
            screen_index=int(screen_index),
            runtime_generation=(
                None if runtime_generation is None else int(runtime_generation)
            ),
        )
        self._pixel_shift_timer = QTimer(self)
        self._pixel_shift_timer.timeout.connect(self._advance_pixel_shift)
        self._paused = True
        self._pixel_shift_defer_check: Callable[[], bool] | None = None
        self._halo_input_active = False
        self._halo_suppressed = False

    @property
    def state(self) -> QuickAuxiliaryState:
        return self._state

    def set_dimming(self, enabled: bool, opacity: float) -> bool:
        if not self._state.admission_open:
            return False
        bounded_opacity = max(0.0, min(1.0, float(opacity)))
        return self._publish(
            dimming_enabled=bool(enabled),
            dimming_opacity=bounded_opacity,
        )

    def configure_pixel_shift(self, enabled: bool, shifts_per_minute: int) -> bool:
        if not self._state.admission_open:
            return False
        rate = max(1, min(5, int(shifts_per_minute)))
        normalized_enabled = bool(enabled)
        changed = self._publish(
            pixel_shift_enabled=normalized_enabled,
            shifts_per_minute=rate,
            **(
                {}
                if normalized_enabled
                else {"pixel_shift_x": 0, "pixel_shift_y": 0}
            ),
        )
        if (
            normalized_enabled
            and not self._paused
            and (changed or not self._pixel_shift_timer.isActive())
        ):
            self._pixel_shift_timer.start(max(1, int(60_000 / rate)))
        else:
            self._pixel_shift_timer.stop()
        return changed

    def set_pixel_shift_defer_check(
        self,
        check: Callable[[], bool] | None,
    ) -> None:
        self._pixel_shift_defer_check = check

    def apply_input_state(self, state: QuickInputState) -> bool:
        if not isinstance(state, QuickInputState):
            raise TypeError("Quick auxiliary input requires QuickInputState")
        if (
            state.screen_index != self._state.screen_index
            or state.runtime_generation != self._state.runtime_generation
        ):
            return False
        self._halo_input_active = bool(
            state.admission_open
            and not state.exiting
            and not state.context_menu_active
            and (state.interaction_mode_enabled or state.ctrl_held)
        )
        # Pointer coordinates and inactivity are presentation-local, high-rate
        # facts.  Python owns only semantic admission.  A retained context menu
        # intentionally suppresses the Halo and exposes one ordinary cursor.
        return self._sync_halo_admission(
            native_cursor_visible=bool(
                state.admission_open and state.context_menu_active and not state.exiting
            )
        )

    def set_halo_shape(self, shape: object) -> bool:
        normalized = str(shape or "").strip().lower()
        if normalized not in _HALO_SHAPES:
            normalized = "cursor_light"
        return self._publish(halo_shape=normalized)

    def set_halo_suppressed(self, suppressed: bool) -> bool:
        normalized = bool(suppressed)
        if normalized == self._halo_suppressed:
            return False
        self._halo_suppressed = normalized
        return self._sync_halo_admission()

    def resume(self) -> bool:
        if not self._state.admission_open or not self._paused:
            return False
        self._paused = False
        if self._state.pixel_shift_enabled:
            self._pixel_shift_timer.start(
                max(1, int(60_000 / self._state.shifts_per_minute))
            )
        self._sync_halo_admission()
        return True

    def pause(self) -> bool:
        if self._paused:
            return False
        self._paused = True
        self._pixel_shift_timer.stop()
        self._sync_halo_admission()
        return True

    def close(self) -> bool:
        if not self._state.admission_open:
            return False
        self._paused = True
        self._pixel_shift_timer.stop()
        self._pixel_shift_defer_check = None
        return self._publish(
            admission_open=False,
            dimming_enabled=False,
            dimming_opacity=0.0,
            pixel_shift_enabled=False,
            pixel_shift_x=0,
            pixel_shift_y=0,
            halo_enabled=False,
            native_cursor_visible=False,
        )

    def describe(self) -> dict[str, object]:
        state = self._state
        return {
            "screen_index": state.screen_index,
            "runtime_generation": state.runtime_generation,
            "admission_open": state.admission_open,
            "dimming_enabled": state.dimming_enabled,
            "dimming_opacity": state.dimming_opacity,
            "pixel_shift_enabled": state.pixel_shift_enabled,
            "pixel_shift": [state.pixel_shift_x, state.pixel_shift_y],
            "shifts_per_minute": state.shifts_per_minute,
            "pixel_shift_timer_active": self._pixel_shift_timer.isActive(),
            "paused": self._paused,
            "halo_enabled": state.halo_enabled,
            "native_cursor_visible": state.native_cursor_visible,
            "halo_shape": state.halo_shape,
            "halo_pointer_owner": "qml_retained_scene",
        }

    def _advance_pixel_shift(self) -> None:
        state = self._state
        if not state.admission_open or not state.pixel_shift_enabled:
            return
        defer_check = self._pixel_shift_defer_check
        if defer_check is not None and defer_check():
            return
        next_x, next_y = self._next_pixel_shift(
            state.pixel_shift_x,
            state.pixel_shift_y,
        )
        self._publish(pixel_shift_x=next_x, pixel_shift_y=next_y)

    def _sync_halo_admission(
        self,
        *,
        native_cursor_visible: bool | None = None,
    ) -> bool:
        state = self._state
        native_visible = (
            state.native_cursor_visible
            if native_cursor_visible is None
            else bool(native_cursor_visible)
        )
        halo_enabled = bool(
            state.admission_open
            and self._halo_input_active
            and not self._halo_suppressed
            and not self._paused
        )
        if halo_enabled:
            native_visible = False
        return self._publish(
            halo_enabled=halo_enabled,
            native_cursor_visible=native_visible,
        )

    @classmethod
    def _next_pixel_shift(cls, current_x: int, current_y: int) -> tuple[int, int]:
        directions = (
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
            (-1, -1),
            (1, -1),
            (-1, 1),
            (1, 1),
        )
        current_distance = abs(current_x) + abs(current_y)
        candidates = [
            (current_x + dx, current_y + dy)
            for dx, dy in directions
            if abs(current_x + dx) <= cls.MAX_PIXEL_SHIFT
            and abs(current_y + dy) <= cls.MAX_PIXEL_SHIFT
        ]
        if not candidates:
            return (0, 0)
        if abs(current_x) >= cls.MAX_PIXEL_SHIFT or abs(current_y) >= cls.MAX_PIXEL_SHIFT:
            inward = [
                point
                for point in candidates
                if abs(point[0]) <= abs(current_x)
                and abs(point[1]) <= abs(current_y)
            ]
            return random.choice(inward or candidates)
        outward = [
            point
            for point in candidates
            if abs(point[0]) + abs(point[1]) > current_distance
        ]
        neutral = [
            point
            for point in candidates
            if abs(point[0]) + abs(point[1]) == current_distance
        ]
        if outward and random.random() < 0.8:
            return random.choice(outward)
        if neutral and random.random() < 0.75:
            return random.choice(neutral)
        inward = [point for point in candidates if point not in outward and point not in neutral]
        return random.choice(inward or neutral or outward or candidates)

    def _publish(self, **changes: object) -> bool:
        next_state = replace(self._state, **changes)
        if next_state == self._state:
            return False
        self._state = next_state
        self.state_changed.emit(next_state)
        return True


__all__ = ["QuickAuxiliaryController", "QuickAuxiliaryState"]
