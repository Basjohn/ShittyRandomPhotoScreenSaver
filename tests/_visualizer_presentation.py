"""Shared neutral card/shadow inputs for visualizer-presentation tests.

Production assembles the visualizer card's border/background/shadow inputs from
the widget theme and shadow settings in ``engine/display_manager.py`` and passes
them explicitly into ``resolve_visualizer_presentation`` /
``QuickDisplayVisualizerOwner``.  The card contract is:

* ``outer_rect``, ``viewport_extent``, ``uniform_visual_scale`` and the baseline
  aspect are derived from display/extent/scale alone -- card inputs never move
  them;
* border/inset/shadow only affect ``content_rect``, ``border_width`` and
  ``shell_style``.

Tests that exercise pure geometry therefore supply a *neutral* card (no border,
no shadow) so results isolate the geometry contract, while tests that exercise
the card itself override just the fields they care about.  This is test
scaffolding, not a second production authority for card defaults.
"""
from __future__ import annotations

from typing import Any, Mapping


NEUTRAL_CARD_SHADOW_KWARGS: dict[str, Any] = {
    "border_width": 0.0,
    "corner_radius": 0.0,
    "content_inset": 0.0,
    "background_color": (0, 0, 0, 0),
    "border_color": (255, 255, 255, 255),
    "shadow_enabled": False,
    "shadow_color": (0, 0, 0, 0),
    "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0),
    "shadow_spread": 0.0,
    "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}


def neutral_card_shadow_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a complete card/shadow kwargs mapping, neutral unless overridden."""
    merged = dict(NEUTRAL_CARD_SHADOW_KWARGS)
    merged.update(overrides)
    return merged


def resolve_presentation(**kwargs: Any):
    """Call the production resolver, filling any unspecified card fields neutrally."""
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_visualizer_presentation,
    )

    merged = dict(NEUTRAL_CARD_SHADOW_KWARGS)
    merged.update(kwargs)
    return resolve_visualizer_presentation(**merged)


def default_visualizer_model_and_cache():
    """Build a canonical settings model + per-mode technical cache.

    Mirrors what ``engine/display_manager.py`` assembles for a real owner
    (``SpotifyVisualizerSettings.from_mapping`` + ``build_technical_cache``), so
    owner-lifecycle tests can resolve technical config without a live widget.
    """
    from core.settings.default_contract import get_raw_default_settings
    from core.settings.models import SpotifyVisualizerSettings
    from widgets.spotify_visualizer.technical_config import build_technical_cache

    config = dict(get_raw_default_settings()["widgets"]["spotify_visualizer"])
    model = SpotifyVisualizerSettings.from_mapping(config)
    return model, build_technical_cache(None, model)


def neutral_bubble_settings(*, event_scheduler: Any = None,
                            viewport_extent: Any = (420.0, 280.0), **overrides: Any) -> dict:
    """Return a complete BubbleSimulation settings payload from canonical defaults.

    The simulation reads the full ``bubble_*`` control set plus the runtime-only
    ``_event_scheduler`` / ``_bubble_viewport_extent`` keys; supplying the
    canonical bubble config keeps these tests aligned with the shipped contract
    instead of a hand-maintained subset.
    """
    from core.settings.default_contract import get_raw_default_settings

    cfg = get_raw_default_settings()["widgets"]["spotify_visualizer"]
    settings = {key: value for key, value in cfg.items() if key.startswith("bubble_")}
    settings["_event_scheduler"] = event_scheduler
    settings["_bubble_viewport_extent"] = viewport_extent
    settings.update(overrides)
    return settings


def neutral_bubble_pulse(**overrides: Any) -> dict:
    """Return a complete Bubble snapshot pulse payload (big/small pulse terms)."""
    pulse = {
        "bass": 0.0,
        "mid_high": 0.0,
        "big_bass_pulse": 0.0,
        "small_freq_pulse": 0.0,
        "big_specular_max_size": 1.0,
        "big_visual_smoothing": 0.0,
        "big_contraction_bias": 0.0,
        "big_size_clamp": 1.0,
    }
    pulse.update(overrides)
    return pulse


def make_visualizer_owner(*args: Any, **kwargs: Any):
    """Construct a QuickDisplayVisualizerOwner the way the display owner does.

    Injects the neutral card/shadow kwargs and a canonical settings model +
    technical cache (both mandatory for configure/sync to resolve) unless the
    caller already supplied them.
    """
    from widgets.spotify_visualizer.quick_display_visualizer_owner import (
        QuickDisplayVisualizerOwner,
    )

    kwargs.setdefault("card_shadow_kwargs", neutral_card_shadow_kwargs())
    owner = QuickDisplayVisualizerOwner(*args, **kwargs)
    controller = owner.controller
    if getattr(controller, "settings_model", None) is None or not controller.technical_config_cache:
        model, cache = default_visualizer_model_and_cache()
        if getattr(controller, "settings_model", None) is None:
            controller.settings_model = model
        if not controller.technical_config_cache:
            controller.technical_config_cache = cache
    return owner
