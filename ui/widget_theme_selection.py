"""Settings persistence + startup activation for retained Widget Themes.

This is the event/configuration boundary between the Qt-free theme resolver and
SettingsManager.  Retained presentations consume a process-local immutable
snapshot at construction; there is no catalogue polling, render-loop Settings
read, or recurring theme service.
"""
from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from typing import Any, Mapping, Protocol

from ui.widget_theme_active import set_active_widget_theme
from ui.widget_theme_catalog import (
    WidgetThemeCatalog,
    build_widget_theme_catalog,
    get_current_widget_theme_catalog,
    set_current_widget_theme_catalog,
)
from ui.widget_theme_runtime import (
    ResolvedWidgetTheme,
    WidgetThemeState,
    resolve_widget_theme,
)
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME_ID


def _canonical_widget_theme_defaults() -> tuple[str, bool, Mapping[str, Any] | None]:
    """Return Widget Theme defaults from the canonical defaults authority."""

    from core.settings.default_contract import require_canonical_default

    raw = require_canonical_default("widget_theme")
    if not isinstance(raw, Mapping):
        raise RuntimeError("Canonical widget_theme default must be a mapping")

    selected = raw.get("selected_id")
    if not isinstance(selected, str) or not selected.strip():
        raise RuntimeError(
            "Canonical defaults require non-empty widget_theme.selected_id"
        )

    keep_synced = raw.get("keep_synced")
    if not isinstance(keep_synced, bool):
        raise RuntimeError(
            "Canonical defaults require boolean widget_theme.keep_synced"
        )

    custom = raw.get("custom")
    if custom is not None and not isinstance(custom, Mapping):
        raise RuntimeError(
            "Canonical defaults require widget_theme.custom to be a mapping or None"
        )

    return (
        selected.strip(),
        keep_synced,
        dict(custom) if isinstance(custom, Mapping) else None,
    )


class WidgetThemeSelectionStore(Protocol):
    def get(self, key: str, default: Any = None) -> Any:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


@dataclass(frozen=True, slots=True)
class WidgetThemeStartupResult:
    catalog: WidgetThemeCatalog
    state: WidgetThemeState
    resolved: ResolvedWidgetTheme


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def read_widget_theme_state(settings: WidgetThemeSelectionStore) -> WidgetThemeState:
    """Read and normalize the structured ``widget_theme`` root."""

    default_selected, default_keep_synced, default_custom = (
        _canonical_widget_theme_defaults()
    )
    raw = settings.get("widget_theme")
    values = raw if isinstance(raw, Mapping) else {}
    selected = str(values.get("selected_id", default_selected) or "").strip()
    if not selected:
        selected = default_selected
    custom = values.get("custom", default_custom)
    custom_payload = dict(custom) if isinstance(custom, Mapping) else None
    migrated = "card_material_override" in values
    if custom_payload is not None and custom_payload.get("schema_version") in {1, 2}:
        # One-time state migration from the abandoned material-bearing Widget
        # Theme schemas. Drop only that retired field and retain stable identity,
        # link metadata, and every semantic colour. This is a migration, not a
        # runtime fallback: the persisted root is immediately rewritten as v3.
        custom_payload.pop("default_card_material_mode", None)
        custom_payload["schema_version"] = 3
        migrated = True
    state = WidgetThemeState(
        selected_id=selected,
        keep_synced=_to_bool(values.get("keep_synced"), default_keep_synced),
        custom_payload=custom_payload,
    )
    if migrated:
        persist_widget_theme_state(settings, state)
    return state


def persist_widget_theme_state(
    settings: WidgetThemeSelectionStore,
    state: WidgetThemeState,
) -> None:
    settings.set(
        "widget_theme",
        {
            "selected_id": state.selected_id,
            "keep_synced": bool(state.keep_synced),
            "custom": (
                dict(state.custom_payload) if state.custom_payload is not None else None
            ),
        },
    )


def synced_widget_theme_id_for_settings(
    catalog: WidgetThemeCatalog,
    settings_theme_id: str | None,
) -> str | None:
    """Resolve explicit Settings-theme -> Widget-theme link metadata."""

    requested = str(settings_theme_id or "").strip()
    if not requested:
        return None
    for entry in catalog.entries:
        if entry.theme.linked_settings_theme_id == requested:
            return entry.theme_id
    # Keep the compiled fallbacks linked even though Phase 1a used the older
    # internal name before the Settings catalogue identity was finalized.
    if requested in {"builtin:default-dark", "default_dark"}:
        return DEFAULT_DARK_WIDGET_THEME_ID
    return None


def synced_settings_theme_id_for_widget(
    catalog: WidgetThemeCatalog,
    widget_theme_id: str | None,
) -> str | None:
    """Resolve explicit Widget-theme -> Settings-theme link metadata.

    This is the reverse half of the linked-theme contract. Runtime/UI code must
    use the stored stable identity rather than matching display names. Custom has
    no paired Settings identity and therefore cannot be selected while linking is
    locked.
    """

    requested = str(widget_theme_id or "").strip()
    if not requested:
        return None
    entry = catalog.entry_by_id(requested)
    if entry is None:
        return None
    linked = entry.theme.linked_settings_theme_id
    return str(linked).strip() if linked is not None else None


def resolve_widget_theme_state(
    state: WidgetThemeState,
    *,
    catalog: WidgetThemeCatalog | None = None,
    settings_theme_id: str | None = None,
) -> ResolvedWidgetTheme:
    current_catalog = catalog or get_current_widget_theme_catalog()
    synced_id = synced_widget_theme_id_for_settings(current_catalog, settings_theme_id)
    return resolve_widget_theme(
        state,
        current_catalog,
        synced_widget_theme_id=synced_id,
    )


def activate_widget_theme_state(
    settings: WidgetThemeSelectionStore,
    state: WidgetThemeState,
    *,
    catalog: WidgetThemeCatalog | None = None,
    settings_theme_id: str | None = None,
    persist: bool = True,
) -> ResolvedWidgetTheme:
    """Resolve + publish one Widget Theme configuration snapshot."""

    resolved = resolve_widget_theme_state(
        state,
        catalog=catalog,
        settings_theme_id=settings_theme_id,
    )
    set_active_widget_theme(resolved.theme)
    if persist:
        persist_widget_theme_state(settings, state)
    return resolved


def activate_persisted_widget_theme(
    settings: WidgetThemeSelectionStore,
    widget_themes_directory: str | PathLike[str],
    *,
    settings_theme_id: str | None = None,
) -> WidgetThemeStartupResult:
    """Resolve persisted identity before retained runtime/UI construction."""

    catalog = build_widget_theme_catalog(widget_themes_directory)
    set_current_widget_theme_catalog(catalog)
    state = read_widget_theme_state(settings)
    resolved = activate_widget_theme_state(
        settings,
        state,
        catalog=catalog,
        settings_theme_id=settings_theme_id,
        persist=False,
    )
    return WidgetThemeStartupResult(catalog=catalog, state=state, resolved=resolved)


__all__ = [
    "WidgetThemeSelectionStore",
    "WidgetThemeStartupResult",
    "activate_persisted_widget_theme",
    "activate_widget_theme_state",
    "persist_widget_theme_state",
    "read_widget_theme_state",
    "resolve_widget_theme_state",
    "synced_settings_theme_id_for_widget",
    "synced_widget_theme_id_for_settings",
]
