"""One transactional Settings-theme selection owner shared by Settings surfaces."""
from __future__ import annotations

from ui.settings_theme_catalog import (
    activate_catalog_theme, get_current_settings_theme_catalog, persist_settings_theme_selection,
    read_persisted_theme_id, resolve_persisted_settings_theme,
)
from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
from ui.widget_theme_catalog import get_current_widget_theme_catalog
from ui.widget_theme_runtime import WidgetThemeState
from ui.widget_theme_selection import activate_widget_theme_state, read_widget_theme_state, synced_widget_theme_id_for_settings


def apply_settings_theme_selection(settings, catalog, theme_id: str):
    """Apply one Settings theme and linked Widget-theme state atomically."""
    entry = catalog.entry_by_id(str(theme_id))
    if entry is None:
        raise ValueError(f"unknown Settings theme: {theme_id!r}")
    state = read_widget_theme_state(settings)
    linked = synced_widget_theme_id_for_settings(get_current_widget_theme_catalog(), entry.theme_id)
    if state.keep_synced and linked is None:
        raise ValueError("linked Settings theme has no Widget-theme counterpart")
    old_theme = get_active_settings_theme(); old_id = read_persisted_theme_id(settings)
    try:
        activate_catalog_theme(entry)
        persist_settings_theme_selection(settings, catalog, entry.theme_id)
        if state.keep_synced:
            activate_widget_theme_state(settings, WidgetThemeState(selected_id=linked, keep_synced=True, custom_payload=state.custom_payload), settings_theme_id=entry.theme_id, persist=True)
    except Exception:
        set_active_settings_theme(old_theme)
        old_entry = catalog.entry_by_id(old_id)
        if old_entry is not None:
            persist_settings_theme_selection(settings, catalog, old_entry.theme_id)
        if state.keep_synced:
            activate_widget_theme_state(settings, state, settings_theme_id=old_id, persist=True)
        raise
    return entry


def rederive_active_themes(settings) -> None:
    """Re-derive both process-local active themes from what is persisted now.

    Reset to Defaults and Import rewrite ``ui.settings_theme_selection`` and ``widget_theme`` wholesale; this is
    the one step that makes the active Settings and Widget themes follow, on the dialog's existing reset/import
    reload edge (never a store subscription, so an unchanged write never reaches it). It resolves exactly as
    startup does, against the catalogs already built (no rescan), and persists nothing. Both activations are no-ops
    when the resolved theme is already active.
    """
    resolution = resolve_persisted_settings_theme(settings, get_current_settings_theme_catalog())
    activate_catalog_theme(resolution.entry)
    activate_widget_theme_state(
        settings, read_widget_theme_state(settings), settings_theme_id=resolution.entry.theme_id, persist=False)
