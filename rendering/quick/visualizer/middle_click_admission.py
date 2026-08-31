"""Retained Visualizer middle-click preset-cycle semantic admission (H8)."""

from __future__ import annotations

from typing import Any, Callable


class QuickVisualizerMiddleClickAdmission:
    """Consume one middle press inside the active retained Visualizer."""

    def __init__(
        self,
        *,
        region_contains: Callable[[Any], bool],
        is_active: Callable[[], bool],
        cycle_preset: Callable[[], None],
    ) -> None:
        if not (
            callable(region_contains)
            and callable(is_active)
            and callable(cycle_preset)
        ):
            raise TypeError(
                "region_contains, is_active and cycle_preset must be callable"
            )
        self._region_contains = region_contains
        self._is_active = is_active
        self._cycle_preset = cycle_preset

    def handles_semantic_middle_click_at(self, scene_position: Any) -> bool:
        if not self._is_active() or not self._region_contains(scene_position):
            return False
        self._cycle_preset()
        return True


__all__ = ["QuickVisualizerMiddleClickAdmission"]
