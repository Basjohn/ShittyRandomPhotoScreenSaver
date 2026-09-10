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
    from core.settings.visualizer_mode_registry import get_resolved_mode_setting_keys
    from widgets.spotify_visualizer.config_applier import (
        apply_presentation_vis_mode_kwargs,
    )

    defaults = dict(get_raw_default_settings()["widgets"]["spotify_visualizer"])
    mode_id = str(state.runtime_controller.mode_id)
    shared_bar_keys = get_resolved_mode_setting_keys(mode_id, "shared_bar")
    for shared_key, persisted_key in shared_bar_keys.items():
        if persisted_key not in defaults:
            raise KeyError(
                "canonical Visualizer defaults missing resolved shared-bar key "
                f"{persisted_key!r} for mode {mode_id!r}"
            )
        defaults[shared_key] = defaults[persisted_key]
    apply_presentation_vis_mode_kwargs(state, defaults)


__all__ = ["VisualizerPresentationState", "install_default_presentation_state"]
