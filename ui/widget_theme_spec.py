"""Semantic runtime Widget Theme specification.

A Widget Theme is a named visual bundle supplying the retained Qt Quick runtime's
global/default card palette and the Context Menu palette. Explicit per-widget card
swatches remain higher-precedence family overrides; the Context Menu has no family
override layer. It is the runtime-scene counterpart of the QWidget
Settings theme (`ui/settings_theme_spec.py`) and deliberately mirrors that module's
shape (frozen dataclass, schema version, semantic role maps, compiled Default Dark)
so the two theme systems share one mental model and one file root.

Boundaries (durable design owners: `Docs/Contracts.md`,
`Docs/Custom_Style_Implementation.md`, `Future_Work.md` §10):

* Widget Theme owns runtime semantic colours only. It does **not** own widget
  activation, provider/account state, geometry, cadence, compositor state, native
  Settings-window backdrop mode, or other business logic.
* Runtime cards are ordinary RGBA Qt Quick surfaces. Settings Glass/Acrylic remain
  a separate QWidget/native-HWND theme concern and are never projected into cards.

Rgba/palette primitives are shared with the Settings theme spec so both systems use
one colour type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ui.settings_theme_spec import Rgba


WIDGET_THEME_SCHEMA_VERSION = 3


# Core roles are the schema-stable whole-or-reject payload. Schema-v3 themes may
# add sparse optional roles from ``ui.widget_visual_roles`` without making those
# additions mandatory for older themes. Keep this set independent from the
# compiled Default Dark colour map, because Default Dark is allowed to materialize
# optional roles needed to reproduce the accepted current pixels exactly.
WIDGET_THEME_CORE_COLOR_ROLES = frozenset(
    {
        "card.background",
        "card.border",
        "card.text",
        "context.menu.surface",
        "context.menu.border",
        "context.menu.text",
        "context.menu.selected_surface",
        "context.menu.disabled_text",
        "context.menu.separator",
        "context.submenu.surface",
        "context.submenu.border",
        "context.submenu.text",
        "context.submenu.selected_surface",
        "context.submenu.checked_text",
        "context.submenu.checked_surface",
    }
)


@dataclass(frozen=True, slots=True)
class WidgetThemeSpec:
    """Resolved semantic Widget Theme values consumed by runtime surfaces.

    ``theme_id`` is the stable, path-independent identity used for selection and
    Settings<->Widget link resolution (never a display-name heuristic).
    ``linked_settings_theme_id`` names the Settings theme this Widget Theme mirrors
    for ``Keep Synced``; ``None`` means unlinked.

    ``colors`` is a semantic role map (mirroring ``SettingsThemeSpec.colors``).
    Core card/context roles are complete; specialized Widget Theme roles may be
    sparse and inherit through ``ui.widget_visual_roles``. Card roles are global
    defaults beneath explicit ``widgets.<family>.card.*`` settings; Context Menu
    roles are direct/global because it has no family layer.
    """

    theme_id: str
    name: str
    linked_settings_theme_id: str | None = None
    colors: Mapping[str, Rgba] = field(default_factory=dict)
    schema_version: int = WIDGET_THEME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.theme_id, str) or not self.theme_id.strip():
            raise ValueError("Widget theme theme_id cannot be empty")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Widget theme name cannot be empty")
        if self.schema_version != WIDGET_THEME_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported Widget theme schema version: {self.schema_version}"
            )

        link = self.linked_settings_theme_id
        if link is not None:
            if not isinstance(link, str) or not link.strip():
                raise ValueError(
                    "Widget theme linked_settings_theme_id must be a non-empty "
                    "string or None"
                )
            object.__setattr__(self, "linked_settings_theme_id", link.strip())

        for key in self.colors:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Widget theme colour keys must be non-empty strings")
        for key, value in self.colors.items():
            if not isinstance(value, Rgba):
                raise TypeError(
                    f"Widget theme colour {key!r} must be an Rgba value"
                )

        object.__setattr__(self, "theme_id", self.theme_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "colors", MappingProxyType(dict(self.colors)))

    def color(self, token: str) -> Rgba:
        """Return one semantic colour or raise a useful error."""

        try:
            return self.colors[token]
        except KeyError as exc:
            raise KeyError(f"Unknown Widget theme colour token: {token}") from exc


# ---------------------------------------------------------------------------
# Default Dark — the unconditional Widget Theme fallback.
# ---------------------------------------------------------------------------
#
# Mirrors the current runtime surface defaults so the runtime looks unchanged when
# no external .srwtheme exists. It links to the compiled Default Dark Settings theme.
#
# Card baseline defaults mirror the accepted ordinary retained-family surface. Context Menu roles mirror the
# physically accepted retained ContextMenu.qml pixels so moving those literals into
# Widget Theme ownership is visually neutral; they intentionally do not inherit the
# QWidget Settings theme directly.

_DEFAULT_DARK_WIDGET_COLORS: dict[str, Rgba] = {
    # Ordinary card surface: canonical [35,35,35,255] at 0.3 opacity,
    # plus the canonical opaque white border. Alpha is pre-composed because the
    # shared Widget Theme owns RGBA directly.
    "card.background": Rgba(35, 35, 35, 76),
    "card.border": Rgba(255, 255, 255, 255),
    "card.text": Rgba(255, 255, 255, 230),

    # Retained runtime Context Menu. These values intentionally mirror the
    # physically accepted current QML pixels; semantic ownership must not recolour
    # Default Dark merely by replacing literals with theme roles.
    "context.menu.surface": Rgba(27, 29, 36, 242),
    "context.menu.border": Rgba(216, 243, 255, 255),
    "context.menu.text": Rgba(246, 248, 255, 255),
    "context.menu.selected_surface": Rgba(119, 185, 232, 79),
    "context.menu.disabled_text": Rgba(120, 120, 130, 150),
    "context.menu.separator": Rgba(89, 119, 138, 255),
    "context.submenu.surface": Rgba(27, 29, 36, 242),
    "context.submenu.border": Rgba(216, 243, 255, 255),
    "context.submenu.text": Rgba(246, 248, 255, 255),
    "context.submenu.selected_surface": Rgba(119, 185, 232, 79),
    "context.submenu.checked_text": Rgba(185, 234, 255, 255),
    "context.submenu.checked_surface": Rgba(78, 113, 139, 51),

    # Optional Context Menu detail roles materialized by Default Dark so the
    # accepted indicator/arrow palette also survives the semantic migration.
    "context.menu.indicator.border": Rgba(185, 234, 255, 255),
    "context.menu.indicator.fill": Rgba(130, 205, 255, 255),
    "context.menu.arrow": Rgba(216, 243, 255, 255),
    "context.submenu.indicator.border": Rgba(185, 234, 255, 255),
    "context.submenu.indicator.fill": Rgba(130, 205, 255, 255),
}


DEFAULT_DARK_WIDGET_THEME_ID = "default_dark"


DEFAULT_DARK_WIDGET_THEME = WidgetThemeSpec(
    theme_id=DEFAULT_DARK_WIDGET_THEME_ID,
    name="Default Dark",
    linked_settings_theme_id="builtin:default-dark",
    colors=_DEFAULT_DARK_WIDGET_COLORS,
)


__all__ = [
    "DEFAULT_DARK_WIDGET_THEME",
    "DEFAULT_DARK_WIDGET_THEME_ID",
    "WIDGET_THEME_CORE_COLOR_ROLES",
    "WIDGET_THEME_SCHEMA_VERSION",
    "WidgetThemeSpec",
]
