"""Bubble typed Settings binding and versioned gradient input migration."""
from collections.abc import Mapping

from core.settings.bubble_gradient_semantics import (
    CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
    get_bubble_gradient_semantics_version,
    resolve_bubble_gradient_direction,
)
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


def load_bubble_mode_settings(tab, spotify_vis_config) -> None:
    config = dict(spotify_vis_config) if isinstance(spotify_vis_config, Mapping) else {}
    default = tab._widget_default("spotify_visualizer", "bubble_gradient_direction")
    config["bubble_gradient_direction"] = resolve_bubble_gradient_direction(
        config.get("bubble_gradient_direction", default),
        semantics_version=get_bubble_gradient_semantics_version(config, prefix="widgets.spotify_visualizer"),
        default=default,
    )
    load_spec_mode_settings(tab, "bubble", config)
    tab._bubble_apply_swirl()


def collect_bubble_mode_settings(tab) -> dict:
    values = collect_spec_mode_settings(tab, "bubble")
    values["bubble_gradient_semantics_version"] = CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION
    return values
