"""Semantic runtime Widget Theme specification.

A Widget Theme is a named visual bundle supplying the retained Qt Quick runtime's
global/default card palette and the Context Menu palette, plus a recommended card
**surface material**. Explicit per-widget card swatches remain higher-precedence
family overrides; the Context Menu has no family override layer. It is the runtime-scene counterpart of the QWidget
Settings theme (`ui/settings_theme_spec.py`) and deliberately mirrors that module's
shape (frozen dataclass, schema version, semantic role maps, compiled Default Dark)
so the two theme systems share one mental model and one file root.

Boundaries (durable design owners: `Docs/Contracts.md`,
`Docs/Custom_Style_Implementation.md`, `Future_Work.md` §10):

* Widget Theme owns runtime palette + a recommended surface material only. It does
  **not** own widget activation, provider/account state, geometry, cadence or any
  business logic.
* Glass/Acrylic are scene-local Qt Quick materials. This spec only names the
  *recommended default* material; it never routes the Settings HWND AccentPolicy
  onto the screensaver window.
* The final runtime material is resolved from this recommendation plus a separate
  persisted user Surface Style override (see :func:`resolve_effective_card_material_mode`).

Rgba/palette primitives are shared with the Settings theme spec so both systems use
one colour type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from ui.settings_theme_spec import Rgba


WIDGET_THEME_SCHEMA_VERSION = 1


# The material a Widget Theme may recommend as its default surface.
CARD_MATERIAL_MODES = frozenset({"normal", "glass", "acrylic"})

# The persisted user Surface Style preference. ``theme`` (the "Theme Default"
# choice) is the no-override state that follows the theme recommendation.
CARD_MATERIAL_OVERRIDES = frozenset({"theme", "normal", "glass", "acrylic"})


def resolve_effective_card_material_mode(
    default_card_material_mode: str,
    card_material_override: str,
) -> str:
    """Resolve the single runtime material consumed by retained card owners.

    ``card_material_override == "theme"`` (Surface Style = "Theme Default") follows
    the Widget Theme's recommendation; any explicit override wins for material only.
    Both inputs are validated/normalised and anything unexpected fails safe to
    ``normal`` so the runtime can never reach a card with no coherent surface.
    """

    default_mode = str(default_card_material_mode or "").strip().lower()
    if default_mode not in CARD_MATERIAL_MODES:
        default_mode = "normal"

    override = str(card_material_override or "").strip().lower()
    if override not in CARD_MATERIAL_OVERRIDES:
        override = "theme"

    resolved = default_mode if override == "theme" else override
    return resolved if resolved in CARD_MATERIAL_MODES else "normal"


@dataclass(frozen=True, slots=True)
class WidgetThemeSpec:
    """Resolved semantic Widget Theme values consumed by runtime surfaces.

    ``theme_id`` is the stable, path-independent identity used for selection and
    Settings<->Widget link resolution (never a display-name heuristic).
    ``linked_settings_theme_id`` names the Settings theme this Widget Theme mirrors
    for ``Keep Synced``; ``None`` means unlinked.

    ``colors`` is a semantic role map (mirroring ``SettingsThemeSpec.colors``).
    Card roles are global defaults beneath explicit ``widgets.<family>.card.*``
    settings; Context Menu roles are direct/global because it has no family layer.
    Phase 1 ships the schema/Default Dark values before retained runtime wiring.
    """

    theme_id: str
    name: str
    default_card_material_mode: str = "normal"
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

        material = self.default_card_material_mode
        material = material.strip().lower() if isinstance(material, str) else material
        if material not in CARD_MATERIAL_MODES:
            raise ValueError(
                "Widget theme default_card_material_mode must be one of "
                f"{sorted(CARD_MATERIAL_MODES)!r}, got {self.default_card_material_mode!r}"
            )
        object.__setattr__(self, "default_card_material_mode", material)

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
# no external .srwtheme exists. Default Dark recommends the cheap ``normal`` card
# material and links to the compiled Default Dark Settings theme.
#
# Card baseline defaults mirror OverlayCardStyle; Context Menu roles mirror the Settings
# theme ``context.*`` values so the menu can later inherit the Widget Theme rather
# than the QWidget Settings theme.

_DEFAULT_DARK_WIDGET_COLORS: dict[str, Rgba] = {
    # Ordinary card surface (mirrors OverlayCardStyle defaults / OverlayCard.qml).
    "card.background": Rgba(16, 16, 16, 179),
    "card.border": Rgba(255, 255, 255, 230),
    "card.text": Rgba(255, 255, 255, 255),

    # Retained runtime Context Menu (mirrors settings_theme_spec context.* roles).
    "context.menu.surface": Rgba(25, 25, 25, 205),
    "context.menu.border": Rgba(255, 255, 255, 255),
    "context.menu.text": Rgba(255, 255, 255, 255),
    "context.menu.selected_surface": Rgba(62, 62, 62, 220),
    "context.menu.disabled_text": Rgba(120, 120, 130, 150),
    "context.menu.separator": Rgba(90, 90, 90, 150),
    "context.submenu.surface": Rgba(25, 25, 25, 205),
    "context.submenu.border": Rgba(255, 255, 255, 255),
    "context.submenu.text": Rgba(255, 255, 255, 255),
    "context.submenu.selected_surface": Rgba(62, 62, 62, 220),
    "context.submenu.checked_text": Rgba(255, 255, 255, 255),
    "context.submenu.checked_surface": Rgba(62, 62, 62, 220),
}


DEFAULT_DARK_WIDGET_THEME_ID = "default_dark"


DEFAULT_DARK_WIDGET_THEME = WidgetThemeSpec(
    theme_id=DEFAULT_DARK_WIDGET_THEME_ID,
    name="Default Dark",
    default_card_material_mode="normal",
    linked_settings_theme_id="default_dark",
    colors=_DEFAULT_DARK_WIDGET_COLORS,
)


__all__ = [
    "CARD_MATERIAL_MODES",
    "CARD_MATERIAL_OVERRIDES",
    "DEFAULT_DARK_WIDGET_THEME",
    "DEFAULT_DARK_WIDGET_THEME_ID",
    "WIDGET_THEME_SCHEMA_VERSION",
    "WidgetThemeSpec",
    "resolve_effective_card_material_mode",
]
