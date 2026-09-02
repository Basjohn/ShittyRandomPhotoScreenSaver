"""Semantic visual-role inheritance for retained Widget Themes.

The retained Qt Quick widget scene deliberately uses one small cascade rather than
family-local colour fallback logic:

1. an explicit per-widget override (when the caller says the stored value is authored),
2. the active theme's exact role,
3. the active theme's semantic parent chain,
4. a caller-supplied local semantic value (``local.*`` roles),
5. the caller's preserved current visual fallback.

``local.*`` roles are presentation context, never serialized theme tokens.  They let
specialized elements inherit the widget's already-resolved text/card/accent colours
when a theme does not care about that specialization.  A theme can override only the
roles it wants, so adding theming support never requires flooding Settings with
swatches or recolouring Default Dark.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ui.settings_theme_spec import Rgba
from ui.widget_theme_spec import WidgetThemeSpec


# ``local.*`` terminals are deliberately absent from the theme schema.  Callers
# supply them from the family config that already owns the current visual.
WIDGET_VISUAL_ROLE_PARENTS: Mapping[str, str] = {
    # Shared retained-widget roles.
    "header.fill": "local.header.fill",
    "header.border": "local.header.border",
    "header.text": "local.header.text",
    "widget.panel": "local.surface",
    "widget.panel.alt": "local.surface.alt",
    "widget.outline": "local.border",
    "widget.separator": "local.separator",
    "widget.icon": "local.text",
    "widget.muted": "local.muted",
    "widget.accent": "local.accent",
    "widget.gradient.start": "local.gradient.start",
    "widget.gradient.middle": "local.gradient.middle",
    "widget.gradient.end": "local.gradient.end",

    # Context Menu detail roles. The main menu/submenu palette remains a strict
    # core theme surface. These smaller details are schema-v2 optional so older
    # themes stay valid; they inherit from the closest menu semantic when omitted.
    "context.menu.indicator.border": "context.menu.border",
    "context.menu.indicator.fill": "context.menu.selected_surface",
    "context.menu.arrow": "context.menu.border",
    "context.submenu.indicator.border": "context.submenu.checked_text",
    "context.submenu.indicator.fill": "context.menu.indicator.fill",

    # Shared separator specialization (Visualizer intentionally owns its own lines).
    "clock.separator": "widget.separator",
    "weather.separator": "widget.separator",
    "gmail.separator": "widget.separator",
    "gmail.boundary_separator": "widget.separator",
    "gmail.action.surface": "widget.panel",
    "gmail.action.border": "widget.outline",
    "gmail.action.hover": "widget.panel.alt",
    "gmail.action.text": "widget.icon",
    "reddit.separator": "widget.separator",
    "reddit2.separator": "reddit.separator",

    # Branded-header family specialization.
    "media.header.fill": "header.fill",
    "media.header.border": "header.border",
    "media.header.text": "header.text",
    "gmail.header.fill": "header.fill",
    "gmail.header.border": "header.border",
    "gmail.header.text": "header.text",
    "reddit.header.fill": "header.fill",
    "reddit.header.border": "header.border",
    "reddit.header.text": "header.text",
    "reddit2.header.fill": "reddit.header.fill",
    "reddit2.header.border": "reddit.header.border",
    "reddit2.header.text": "reddit.header.text",
    "achievement_pulse.header.fill": "header.fill",
    "achievement_pulse.header.border": "header.border",
    "achievement_pulse.header.text": "header.text",
    "abandonment_issues.header.fill": "header.fill",
    "abandonment_issues.header.border": "header.border",
    "abandonment_issues.header.text": "header.text",

    # Media internal surfaces.  These are intentionally semantic, not GUI controls.
    "media.transport.surface": "widget.panel",
    "media.transport.border": "widget.outline",
    "media.transport.separator": "widget.separator",
    "media.transport.icon": "widget.icon",
    "media.mute.surface": "widget.panel.alt",
    "media.mute.border": "widget.outline",
    "media.mute.inner_border": "widget.outline",
    "media.mute.icon": "widget.icon",
    "media.mute.muted_icon": "widget.muted",
    "media.volume.track": "widget.panel",
    "media.volume.fill": "widget.accent",
    "media.volume.outline": "widget.outline",
    "media.progress.track": "widget.panel.alt",
    "media.progress.fill": "widget.accent",
    "media.progress.glow": "widget.accent",
    "media.progress.shadow": "widget.muted",

    # Steam-family secondary surface vocabulary.  Wiring can proceed incrementally.
    "steam.panel.surface": "widget.panel",
    "steam.panel.alt_surface": "widget.panel.alt",
    "steam.panel.border": "widget.outline",
    "steam.separator": "widget.separator",
    "steam.badge.surface": "widget.panel.alt",
    "steam.badge.border": "widget.outline",
    "steam.gradient.start": "widget.gradient.start",
    "steam.gradient.middle": "widget.gradient.middle",
    "steam.gradient.end": "widget.gradient.end",
    "steam.info.surface": "steam.badge.surface",
    "steam.info.border": "steam.badge.border",
    "steam.info.text": "widget.icon",
    "steam.tooltip.surface": "steam.panel.surface",
    "steam.tooltip.border": "steam.panel.border",
    "steam.tooltip.text": "widget.icon",
    "steam.artwork.surface": "steam.panel.alt_surface",
    "steam.artwork.border": "steam.panel.border",
    "steam.artwork.stripe": "steam.separator",
    "steam.artwork.gradient.start": "steam.gradient.start",
    "steam.artwork.gradient.middle": "steam.gradient.middle",
    "steam.artwork.gradient.end": "steam.gradient.end",
    "steam.metric.surface": "steam.badge.surface",
    "steam.metric.border": "steam.badge.border",
    "steam.metric.inner_border": "steam.badge.border",
    "steam.metric.separator": "steam.separator",
}


WIDGET_THEME_OPTIONAL_COLOR_ROLES = frozenset(WIDGET_VISUAL_ROLE_PARENTS)


def _validate_role(role: str) -> str:
    normalized = str(role or "").strip()
    if not normalized:
        raise ValueError("Widget visual role cannot be empty")
    return normalized


def is_known_widget_theme_color_role(role: str, *, core_roles: Mapping[str, Rgba]) -> bool:
    """Return whether ``role`` is legal in a serialized Widget Theme."""

    normalized = _validate_role(role)
    return normalized in core_roles or normalized in WIDGET_THEME_OPTIONAL_COLOR_ROLES


@dataclass(frozen=True, slots=True)
class ResolvedWidgetVisualColor:
    """One resolved colour plus the role/source that supplied it."""

    color: Rgba
    requested_role: str
    source_role: str
    source_kind: str  # explicit | theme | local | fallback


def resolve_widget_visual_color(
    theme: WidgetThemeSpec,
    role: str,
    *,
    local_roles: Mapping[str, Rgba] | None = None,
    fallback: Rgba,
    explicit: Rgba | None = None,
) -> ResolvedWidgetVisualColor:
    """Resolve one semantic role without inventing another family-local cascade.

    ``explicit`` is only passed when persistence/UI knows the value is an authored
    family override.  ``local_roles`` contains context such as ``local.surface`` or
    ``local.text`` derived from the family's already-resolved card/text values.
    Missing optional theme roles therefore inherit naturally without changing the
    accepted Default Dark appearance.
    """

    if not isinstance(theme, WidgetThemeSpec):
        raise TypeError("theme must be a WidgetThemeSpec")
    requested = _validate_role(role)
    if not isinstance(fallback, Rgba):
        raise TypeError("fallback must be an Rgba")
    if explicit is not None and not isinstance(explicit, Rgba):
        raise TypeError("explicit must be an Rgba or None")

    if explicit is not None:
        return ResolvedWidgetVisualColor(
            color=explicit,
            requested_role=requested,
            source_role=requested,
            source_kind="explicit",
        )

    locals_map = dict(local_roles or {})
    current = requested
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        themed = theme.colors.get(current)
        if themed is not None:
            return ResolvedWidgetVisualColor(
                color=themed,
                requested_role=requested,
                source_role=current,
                source_kind="theme",
            )
        local = locals_map.get(current)
        if local is not None:
            if not isinstance(local, Rgba):
                raise TypeError(f"local role {current!r} must be an Rgba")
            return ResolvedWidgetVisualColor(
                color=local,
                requested_role=requested,
                source_role=current,
                source_kind="local",
            )
        current = WIDGET_VISUAL_ROLE_PARENTS.get(current, "")

    return ResolvedWidgetVisualColor(
        color=fallback,
        requested_role=requested,
        source_role=requested,
        source_kind="fallback",
    )


def materialize_widget_theme_colors(
    theme: WidgetThemeSpec,
    *,
    core_roles: Mapping[str, Rgba],
    optional_fallbacks: Mapping[str, Rgba] | None = None,
) -> dict[str, Rgba]:
    """Materialize a sparse theme for a user-owned Custom snapshot/export.

    Theme files are intentionally allowed to omit specialized roles.  A Custom
    snapshot, however, must freeze the currently resolved appearance so a later
    parent-theme edit cannot silently alter it.  Optional roles without a supplied
    concrete fallback are left sparse; callers that own presentation-specific
    fallbacks can pass them when they need a complete export.
    """

    resolved = dict(core_roles)
    resolved.update(theme.colors)
    fallbacks = dict(optional_fallbacks or {})
    for role in WIDGET_THEME_OPTIONAL_COLOR_ROLES:
        if role in resolved:
            continue
        fallback = fallbacks.get(role)
        if fallback is None:
            continue
        resolved[role] = resolve_widget_visual_color(
            theme,
            role,
            local_roles=None,
            fallback=fallback,
        ).color
    return resolved


__all__ = [
    "ResolvedWidgetVisualColor",
    "WIDGET_THEME_OPTIONAL_COLOR_ROLES",
    "WIDGET_VISUAL_ROLE_PARENTS",
    "is_known_widget_theme_color_role",
    "materialize_widget_theme_colors",
    "resolve_widget_visual_color",
]
