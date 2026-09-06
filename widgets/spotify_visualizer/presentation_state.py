"""Controller-owned presentation-only Visualizer configuration state.

The state is initialized once from canonical Visualizer defaults for the active
mode, then receives the resolved preset/settings overlay.  Immutable frame
capture therefore consumes a complete configuration contract and never owns a
second set of product fallback values.
"""
from __future__ import annotations

from typing import Any


class VisualizerPresentationState:
    """Single presentation-neutral host for one generation's renderer config."""

    def __init__(self, controller: Any) -> None:
        object.__setattr__(self, "_controller", controller)

    @property
    def runtime_controller(self) -> Any:
        return self._controller


def install_default_presentation_state(state: VisualizerPresentationState) -> None:
    """Initialize presentation config from the one canonical defaults source."""

    from core.settings.default_contract import get_raw_default_settings
    from widgets.spotify_visualizer.config_applier import (
        apply_presentation_vis_mode_kwargs,
    )

    defaults = dict(get_raw_default_settings()["widgets"]["spotify_visualizer"])
    mode_id = str(state.runtime_controller.mode_id)
    for shared_key in ("bar_fill_color", "bar_border_color", "bar_border_opacity"):
        mode_key = f"{mode_id}_{shared_key}"
        if mode_key not in defaults:
            raise KeyError(
                f"canonical Visualizer defaults missing active-mode key {mode_key!r}"
            )
        defaults[shared_key] = defaults[mode_key]
    apply_presentation_vis_mode_kwargs(state, defaults)


__all__ = ["VisualizerPresentationState", "install_default_presentation_state"]
