"""Retained visualizer double-click semantic admission (H Finding E).

Product semantics:

    double-click visualizer      -> cycle visualizer mode
    unhandled display double-click -> next image

The Quick window gives retained ordinary-family semantic hit regions first
refusal, then falls back to the neutral runtime input owner's global next-image
action. The visualizer must join that retained semantic hit/action admission
*before* the fallback: a double-click inside the retained visualizer region
cycles the visualizer mode (a semantic Python action) and consumes the event, so
it never reaches next-image. QML/Quick may identify the hit region, but Python
remains the mode-cycle/business authority - this does not add a second global
mouse router and does not change the global fallback meaning.
"""

from __future__ import annotations

from typing import Any, Callable

from core.settings.visualizer_mode_registry import (
    coerce_visualizer_mode_id,
    iter_visualizer_mode_descriptors,
    resolve_effective_enabled_modes,
)


def next_visualizer_mode_id(
    current_mode_id: str,
    enabled_modes: object = None,
) -> str:
    """Return the next visualizer mode id, cycling only enabled modes.

    Mirrors the legacy ``mode_transition.cycle_mode`` order exactly: canonical
    descriptor order, wrapping ``(idx + 1) % len``. When ``enabled_modes`` is
    given, cycling is restricted to that effective enabled set (V3) so a disabled
    mode is never reachable by cycling; when it is ``None`` the full registered
    active set is used (legacy callers / no enable-state context). An unknown
    current id starts the cycle at the first mode.
    """

    if enabled_modes is None:
        ids = tuple(desc.mode_id for desc in iter_visualizer_mode_descriptors())
    else:
        ids = resolve_effective_enabled_modes(enabled_modes)
    if not ids:
        return coerce_visualizer_mode_id(current_mode_id)
    current = coerce_visualizer_mode_id(current_mode_id)
    try:
        idx = ids.index(current)
    except ValueError:
        idx = -1
    return ids[(idx + 1) % len(ids)]


class QuickVisualizerDoubleClickAdmission:
    """Retained semantic hit/action admission for the visualizer double-click.

    ``region_contains(scene_position) -> bool`` identifies the retained
    visualizer hit region; ``is_active() -> bool`` reports whether the visualizer
    is currently presenting/admitting (a retired or hidden visualizer declines);
    ``cycle_mode() -> None`` performs the Python mode-cycle business action.
    """

    def __init__(
        self,
        *,
        region_contains: Callable[[Any], bool],
        is_active: Callable[[], bool],
        cycle_mode: Callable[[], None],
    ) -> None:
        if not (callable(region_contains) and callable(is_active) and callable(cycle_mode)):
            raise TypeError("region_contains, is_active and cycle_mode must be callable")
        self._region_contains = region_contains
        self._is_active = is_active
        self._cycle_mode = cycle_mode

    def handles_semantic_double_click_at(self, scene_position: Any) -> bool:
        """Cycle the mode and consume the event iff the visualizer owns the hit."""

        if not self._is_active():
            return False
        if not self._region_contains(scene_position):
            return False
        self._cycle_mode()
        return True


def compose_semantic_double_click_hit_tests(
    *hit_tests: Callable[[Any], bool] | None,
) -> Callable[[Any], bool]:
    """Compose ordered semantic double-click hit tests (first-handled wins).

    The ordinary-family host is passed first (families keep first refusal), the
    visualizer admission after it, so the composition is tried before the neutral
    runtime input owner's global next-image fallback. ``None`` entries are skipped.
    """

    tests = [test for test in hit_tests if test is not None]

    def _composed(scene_position: Any) -> bool:
        for test in tests:
            if test(scene_position):
                return True
        return False

    return _composed


__all__ = [
    "QuickVisualizerDoubleClickAdmission",
    "compose_semantic_double_click_hit_tests",
    "next_visualizer_mode_id",
]
