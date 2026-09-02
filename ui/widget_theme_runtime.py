"""Widget Theme resolution + state transitions (pure, persistence-agnostic).

This module owns the *rules* that turn persisted Widget Theme state into one
active :class:`WidgetThemeSpec` plus one ``effective_card_material_mode``. It reads
no SettingsManager and touches no Qt runtime; the persistence layer supplies the
stored values and the disk catalogue, and the UI layer drives the transitions.

Persisted state (all in normal SRPSS Settings data — ``Custom`` is never a file):

- ``widget_theme.selected_id``            portable catalogue id, or ``"custom"``;
- ``widget_theme.keep_synced``            bool, default True;
- ``widget_theme.card_material_override``  theme | normal | glass | acrylic;
- ``widget_theme.custom``                 a serialized WidgetThemeSpec payload | None.

Two orthogonal axes are honoured here: ``Keep Synced`` links theme *identity* to the
Settings theme's mirrored Widget theme; Surface Style (``card_material_override``)
overrides *material only* and never dirties the theme or clears sync.
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
    WidgetThemeSpec,
    resolve_effective_card_material_mode,
)


WIDGET_THEME_SELECTED_ID_KEY = "widget_theme.selected_id"
WIDGET_THEME_KEEP_SYNCED_KEY = "widget_theme.keep_synced"
WIDGET_THEME_CARD_MATERIAL_OVERRIDE_KEY = "widget_theme.card_material_override"
WIDGET_THEME_CUSTOM_KEY = "widget_theme.custom"

# Sentinel selection id for the user-owned working snapshot (not a catalogue file).
CUSTOM_WIDGET_THEME_ID = "custom"
CUSTOM_WIDGET_THEME_NAME = "Custom"

DEFAULT_KEEP_SYNCED = True
DEFAULT_CARD_MATERIAL_OVERRIDE = "theme"


@dataclass(frozen=True, slots=True)
class WidgetThemeState:
    """The persisted Widget Theme selection state, normalised."""

    selected_id: str = DEFAULT_DARK_WIDGET_THEME.theme_id
    keep_synced: bool = DEFAULT_KEEP_SYNCED
    card_material_override: str = DEFAULT_CARD_MATERIAL_OVERRIDE
    custom_payload: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ResolvedWidgetTheme:
    """The active Widget theme + resolved runtime material for a generation."""

    theme: WidgetThemeSpec
    effective_card_material_mode: str
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
    stored selection wins. Sync never touches Surface Style. A ``Custom`` selection
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
    """Resolve one always-valid active Widget theme + effective material.

    Never returns without a coherent theme/material: a missing/invalid Custom
    snapshot or catalogue id falls back to the compiled Default Dark, and the
    material resolver clamps anything unexpected to ``normal``.
    """

    selected_id = effective_selected_widget_theme_id(state, synced_widget_theme_id)

    if selected_id == CUSTOM_WIDGET_THEME_ID:
        custom_theme, error = _custom_theme_from_payload(state.custom_payload)
        if custom_theme is not None:
            return ResolvedWidgetTheme(
                theme=custom_theme,
                effective_card_material_mode=resolve_effective_card_material_mode(
                    custom_theme.default_card_material_mode,
                    state.card_material_override,
                ),
                is_custom=True,
                used_fallback=False,
                error=None,
            )
        return ResolvedWidgetTheme(
            theme=DEFAULT_DARK_WIDGET_THEME,
            effective_card_material_mode=resolve_effective_card_material_mode(
                DEFAULT_DARK_WIDGET_THEME.default_card_material_mode,
                state.card_material_override,
            ),
            is_custom=False,
            used_fallback=True,
            error=error,
        )

    resolution = resolve_widget_theme_selection(catalog, selected_id)
    return ResolvedWidgetTheme(
        theme=resolution.entry.theme,
        effective_card_material_mode=resolve_effective_card_material_mode(
            resolution.entry.theme.default_card_material_mode,
            state.card_material_override,
        ),
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

    Editing a theme-owned value is what drives the named-theme -> Custom transition;
    the caller snapshots the full resolved theme, applies the edit here, selects
    Custom and turns Keep Synced OFF. Unedited roles are preserved exactly.
    """

    if token not in theme.colors:
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
) -> tuple[WidgetThemeSpec, WidgetThemeState]:
    """Perform the theme-owned-edit ownership transition.

    Snapshot the full currently-resolved theme into user-owned Custom, apply the
    edit to that snapshot, and return the new Custom spec plus the new persisted
    state (selection = Custom, Keep Synced OFF). The existing Surface Style override
    is preserved unchanged — a theme-owned edit never alters material ownership. The
    shipped ``.srwtheme`` is never mutated.
    """

    snapshot = with_color(to_custom_snapshot(active_theme), token, color)
    state = WidgetThemeState(
        selected_id=CUSTOM_WIDGET_THEME_ID,
        keep_synced=False,
        card_material_override=current_state.card_material_override,
        custom_payload=widget_theme_to_payload(snapshot),
    )
    return snapshot, state


__all__ = [
    "CUSTOM_WIDGET_THEME_ID",
    "CUSTOM_WIDGET_THEME_NAME",
    "DEFAULT_CARD_MATERIAL_OVERRIDE",
    "DEFAULT_KEEP_SYNCED",
    "ResolvedWidgetTheme",
    "WIDGET_THEME_CARD_MATERIAL_OVERRIDE_KEY",
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
