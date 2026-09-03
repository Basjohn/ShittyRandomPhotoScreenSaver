"""Widget Theme resolution + state transitions (pure, persistence-agnostic).

This module owns the *rules* that turn persisted Widget Theme state into one
active :class:`WidgetThemeSpec`. It reads
no SettingsManager and touches no Qt runtime; the persistence layer supplies the
stored values and the disk catalogue, and the UI layer drives the transitions.

Persisted state (all in normal SRPSS Settings data — ``Custom`` is never a file):

- ``widget_theme.selected_id``            portable catalogue id, or ``"custom"``;
- ``widget_theme.keep_synced``            bool, default True;
- ``widget_theme.custom``                 a serialized WidgetThemeSpec payload | None.

``Keep Synced`` links Widget-theme identity to the Settings theme's explicit mirror.
Card material is intentionally not part of Widget Theme state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from ui.settings_theme_spec import Rgba
from ui.widget_theme_catalog import (
    WidgetThemeCatalog,
    resolve_widget_theme_selection,
)
from ui.widget_theme_io import widget_theme_from_payload, widget_theme_to_payload
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_CORE_COLOR_ROLES,
    WidgetThemeSpec,
)
from ui.widget_visual_roles import (
    WIDGET_THEME_OPTIONAL_COLOR_ROLES,
    materialize_widget_theme_colors,
)


WIDGET_THEME_SELECTED_ID_KEY = "widget_theme.selected_id"
WIDGET_THEME_KEEP_SYNCED_KEY = "widget_theme.keep_synced"
WIDGET_THEME_CUSTOM_KEY = "widget_theme.custom"

# Sentinel selection id for the user-owned working snapshot (not a catalogue file).
CUSTOM_WIDGET_THEME_ID = "custom"
CUSTOM_WIDGET_THEME_NAME = "Custom"

DEFAULT_KEEP_SYNCED = True


@dataclass(frozen=True, slots=True)
class WidgetThemeState:
    """The persisted Widget Theme selection state, normalised."""

    selected_id: str = DEFAULT_DARK_WIDGET_THEME.theme_id
    keep_synced: bool = DEFAULT_KEEP_SYNCED
    custom_payload: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ResolvedWidgetTheme:
    """The active Widget theme resolved for a generation."""

    theme: WidgetThemeSpec
    is_custom: bool
    used_fallback: bool
    error: str | None = None


def effective_selected_widget_theme_id(
    state: WidgetThemeState,
    synced_widget_theme_id: str | None,
) -> str:
    """Apply the Keep Synced identity rule.

    With sync ON and a resolved mirrored Widget theme id available for the current
    Settings theme, that linked id is authoritative; otherwise the explicitly
    stored selection wins. A ``Custom`` selection
    is preserved when unsynced; sync ON deliberately reselects the linked named
    theme (the Custom snapshot itself is retained by the persistence layer).
    """

    if state.keep_synced and synced_widget_theme_id:
        return str(synced_widget_theme_id)
    return state.selected_id


def _custom_theme_from_payload(
    payload: Mapping[str, Any] | None,
) -> tuple[WidgetThemeSpec | None, str | None]:
    if not payload:
        return None, "No Custom Widget theme snapshot is stored."
    try:
        return widget_theme_from_payload(dict(payload)), None
    except (TypeError, ValueError) as exc:
        return None, f"Stored Custom Widget theme is invalid: {exc}"


def resolve_widget_theme(
    state: WidgetThemeState,
    catalog: WidgetThemeCatalog,
    *,
    synced_widget_theme_id: str | None = None,
) -> ResolvedWidgetTheme:
    """Resolve one always-valid active Widget theme.

    A missing/invalid Custom snapshot or catalogue id falls back to the compiled
    Default Dark.
    """

    selected_id = effective_selected_widget_theme_id(state, synced_widget_theme_id)

    if selected_id == CUSTOM_WIDGET_THEME_ID:
        custom_theme, error = _custom_theme_from_payload(state.custom_payload)
        if custom_theme is not None:
            return ResolvedWidgetTheme(
                theme=custom_theme,
                is_custom=True,
                used_fallback=False,
                error=None,
            )
        return ResolvedWidgetTheme(
            theme=DEFAULT_DARK_WIDGET_THEME,
            is_custom=False,
            used_fallback=True,
            error=error,
        )

    resolution = resolve_widget_theme_selection(catalog, selected_id)
    return ResolvedWidgetTheme(
        theme=resolution.entry.theme,
        is_custom=False,
        used_fallback=resolution.used_fallback,
        error=resolution.error,
    )


# ---------------------------------------------------------------------------
# Pure state transitions (the persistence/UI layer applies + saves the results)
# ---------------------------------------------------------------------------


def to_custom_snapshot(theme: WidgetThemeSpec) -> WidgetThemeSpec:
    """Return ``theme`` recast as the user-owned Custom snapshot identity."""

    return replace(
        theme,
        theme_id=CUSTOM_WIDGET_THEME_ID,
        name=CUSTOM_WIDGET_THEME_NAME,
    )


def with_color(theme: WidgetThemeSpec, token: str, color: Rgba) -> WidgetThemeSpec:
    """Return a copy of ``theme`` with one semantic colour role replaced.

    Editing a theme-owned value is what drives the named-theme -> Custom transition.
    Schema-v3 themes may be sparse for specialized roles, so editing a known role
    may add that explicit role to the Custom snapshot. Unedited theme roles remain
    untouched; family-local overrides stay outside the Widget Theme bundle.
    """

    known = set(DEFAULT_DARK_WIDGET_THEME.colors) | set(WIDGET_THEME_OPTIONAL_COLOR_ROLES)
    if token not in known:
        raise KeyError(f"Unknown Widget theme colour token: {token}")
    if not isinstance(color, Rgba):
        raise TypeError("color must be an Rgba value")
    new_colors = dict(theme.colors)
    new_colors[token] = color
    return replace(theme, colors=new_colors)


def begin_theme_owned_edit(
    current_state: WidgetThemeState,
    active_theme: WidgetThemeSpec,
    token: str,
    color: Rgba,
    *,
    resolved_optional_colors: Mapping[str, Rgba] | None = None,
) -> tuple[WidgetThemeSpec, WidgetThemeState]:
    """Perform the theme-owned-edit ownership transition.

    Snapshot the currently resolved Widget Theme into user-owned Custom, apply the
    edit, and return the new persisted state (selection = Custom, Keep Synced OFF).
    ``resolved_optional_colors`` is the presentation/configuration authority's
    current concrete value for sparse specialized roles. Phase-1b UI wiring must
    supply that map when creating Custom so an inherited role is frozen rather than
    silently changing if a later parent/default changes. The optional argument keeps
    legacy/core-only callers source-compatible until that UI lands.

    The shipped ``.srwtheme`` is never mutated.
    """

    custom_base = to_custom_snapshot(active_theme)
    if resolved_optional_colors:
        custom_base = replace(
            custom_base,
            colors=materialize_widget_theme_colors(
                active_theme,
                core_roles={
                    role: DEFAULT_DARK_WIDGET_THEME.colors[role]
                    for role in WIDGET_THEME_CORE_COLOR_ROLES
                },
                optional_fallbacks=resolved_optional_colors,
            ),
        )
    snapshot = with_color(custom_base, token, color)
    state = WidgetThemeState(
        selected_id=CUSTOM_WIDGET_THEME_ID,
        keep_synced=False,
        custom_payload=widget_theme_to_payload(snapshot),
    )
    return snapshot, state


__all__ = [
    "CUSTOM_WIDGET_THEME_ID",
    "CUSTOM_WIDGET_THEME_NAME",
    "DEFAULT_KEEP_SYNCED",
    "ResolvedWidgetTheme",
    "WIDGET_THEME_CUSTOM_KEY",
    "WIDGET_THEME_KEEP_SYNCED_KEY",
    "WIDGET_THEME_SELECTED_ID_KEY",
    "WidgetThemeState",
    "begin_theme_owned_edit",
    "effective_selected_widget_theme_id",
    "resolve_widget_theme",
    "to_custom_snapshot",
    "with_color",
]
