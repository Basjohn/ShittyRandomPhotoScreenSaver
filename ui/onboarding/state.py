"""Cheap Guided Setup state projections; no provider/runtime admission."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.settings.capability_activation import is_widget_family_effective
from core.settings.visualizer_mode_registry import resolve_admissible_enabled_modes
from core.settings.widget_family_catalog import get_widget_family_catalog


def _widgets(settings) -> Mapping[str, Any]:
    value = settings.get("widgets", {})
    return value if isinstance(value, Mapping) else {}


def _member_enabled(widgets: Mapping[str, Any], widget_id: str) -> bool:
    """Read a catalog member from its canonical Settings owner.

    Most members own an ``enabled`` mapping.  Media's volume and mute controls
    are intentionally leaves of ``widgets.media``; treating them as standalone
    widget sections makes Guided Setup summaries disagree with the actual
    runtime configuration.
    """

    if widget_id in {"spotify_volume", "mute_button"}:
        media = widgets.get("media")
        return bool(
            isinstance(media, Mapping)
            and media.get(f"{widget_id}_enabled", False)
        )
    section = widgets.get(widget_id)
    return bool(isinstance(section, Mapping) and section.get("enabled", False))


def selected_setup_dependencies(settings) -> tuple[str, ...]:
    """Return selected effective setup dependencies in wizard order."""
    widgets = _widgets(settings)
    selected: list[str] = []
    for family_id, dependency in (("weather", "weather"), ("steam", "steam"), ("gmail", "gmail"), ("reddit", "reddit"), ("feeds", "feeds")):
        if not is_widget_family_effective(widgets, family_id):
            continue
        family = next((entry for entry in get_widget_family_catalog() if entry.family_id == family_id), None)
        if family is None:
            continue
        if any(_member_enabled(widgets, member) for member in family.member_widget_ids):
            if dependency == "reddit":
                selected.extend(
                    item for item in ("reddit", "reddit2")
                    if _member_enabled(widgets, item)
                )
            else:
                selected.append(dependency)
    return tuple(selected)


def saved_account_states(settings) -> dict[str, bool]:
    """Read only persisted, non-secret account hints; never test/decrypt/connect."""
    from core.settings.storage_paths import get_app_data_dir
    from core.steam.credentials import get_storage_status
    steam = get_storage_status()
    app_data = get_app_data_dir()
    return {
        "steam": bool(steam.storage_available and steam.has_credentials),
        "gmail": bool((app_data / "gmail_imap_creds.enc").exists() or (app_data / "gmail_token.enc").exists()),
    }


def current_setup_summary(settings) -> dict[str, object]:
    widgets = _widgets(settings)
    from core.sources.readiness import has_image_sources
    sources = has_image_sources(settings)  # the one shared readiness rule
    enabled = sum(
        1 for family in get_widget_family_catalog()
        if is_widget_family_effective(widgets, family.family_id)
        and any(_member_enabled(widgets, member) for member in family.member_widget_ids)
    )
    visualizer = widgets.get("spotify_visualizer", {})
    modes = resolve_admissible_enabled_modes(visualizer.get("mode_activation") if isinstance(visualizer, Mapping) else None)
    transitions = settings.get("transitions", {})
    activation = transitions.get("activation", {}) if isinstance(transitions, Mapping) else {}
    display = settings.get("display.show_on_monitors")
    visualizer_active = (
        isinstance(visualizer, Mapping)
        and bool(visualizer.get("enabled"))
        and is_widget_family_effective(widgets, "visualizers")
    )
    return {"sources": sources, "folders": len(settings.get("sources.folders") or ()), "feeds": len(settings.get("sources.rss_feeds") or ()), "displays": display, "interaction": bool(settings.get("input.interaction_mode")), "families": enabled, "accounts": saved_account_states(settings), "visualizer_modes": modes if visualizer_active else (), "transitions": sum(bool(value) for value in activation.values()) if isinstance(activation, Mapping) else 0}
