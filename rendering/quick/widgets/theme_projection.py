"""Qt-Quick family helpers for semantic Widget Theme colour projection.

This module is intentionally small: family configs keep their existing persisted
appearance fields, while unexposed decorative roles ask the single semantic resolver
for an optional theme override.  Stored values that differ from canonical defaults
remain explicit family overrides, so introducing Widget Themes cannot erase an
operator's authored colours.
"""

from __future__ import annotations

from collections.abc import Mapping

from ui.settings_theme_spec import Rgba
from ui.widget_theme_active import get_active_widget_theme
from ui.widget_visual_roles import resolve_widget_visual_color
from ui.theme_semantics import widget_theme_is_light
from rendering.quick.shadow_snapshot import QuickShadowSnapshot


def resolve_soft_text_shadow(shadow: QuickShadowSnapshot) -> bool:
    """Resolve the visible light-theme style modifier once per style build."""
    return (shadow.text_enabled and shadow.soft_text_on_light_themes
            and widget_theme_is_light(get_active_widget_theme()))


RgbaTuple = tuple[int, int, int, int]


def _is_border_field(name: str) -> bool:
    return "border" in name or "outline" in name


def hide_borders(config):
    """``config`` with every border or outline colour invisible (Style Overrides' Borderless).

    A family config is a dataclass of resolved fields. A field whose name says border or
    outline and whose value is an RGBA tuple keeps its colour but loses its alpha, whatever
    authored it; nested config dataclasses are walked. Nothing else changes.
    """

    import dataclasses

    if not dataclasses.is_dataclass(config) or isinstance(config, type):
        return config
    changes = {}
    for field in dataclasses.fields(config):
        value = getattr(config, field.name)
        if (_is_border_field(field.name) and isinstance(value, tuple) and len(value) == 4
                and all(isinstance(c, int) and not isinstance(c, bool) for c in value)):
            changes[field.name] = (value[0], value[1], value[2], 0)
        elif dataclasses.is_dataclass(value) and not isinstance(value, type):
            nested = hide_borders(value)
            if nested is not value:
                changes[field.name] = nested
    return dataclasses.replace(config, **changes) if changes else config


# The News/Feed story tile's fill: a faint wash of the body ink over the card's own surface.
# Every ordinary widget tile (Feed, Games You Follow, System Stats, Friend Pulse, Abandonment
# Issues) takes its fill from here and its hairline from the header border, never an opaque slab.
TILE_WASH_ALPHA = 0.055


def tile_wash(ink: RgbaTuple) -> RgbaTuple:
    """The tile fill for body ink ``ink``: its colour at the shared wash alpha."""

    r, g, b, _a = ink
    return (r, g, b, round(255 * TILE_WASH_ALPHA))


def with_borderless(config, widgets_config):
    """``config`` as Style Overrides' Borderless latch in ``widgets_config`` wants it drawn."""

    from core.settings.default_contract import resolve_widgets_borderless

    return hide_borders(config) if resolve_widgets_borderless(widgets_config) else config


def as_rgba(value: object, fallback: RgbaTuple) -> Rgba:
    if isinstance(value, Rgba):
        return value
    if isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            return Rgba(*(max(0, min(255, int(channel))) for channel in channels))
        except (TypeError, ValueError):
            pass
    return Rgba(*fallback)


def as_tuple(color: Rgba) -> RgbaTuple:
    return color.as_tuple()


def configured_rgba_override(
    values: Mapping[str, object],
    defaults: Mapping[str, object],
    key: str,
    fallback: RgbaTuple,
) -> Rgba | None:
    """Return an authored colour only when it differs from canonical default.

    Normal Settings snapshots may contain a key even when the operator never
    customized it. Comparing against canonical defaults gives today's swatches an
    implicit ``Inherit`` state without adding another visible checkbox/control.
    """

    if key not in values:
        return None
    configured = as_rgba(values.get(key), fallback)
    default = as_rgba(defaults.get(key), fallback)
    return configured if configured != default else None



def _mapping_value(
    values: Mapping[str, object],
    keys: tuple[str, ...],
    fallback: object,
) -> object:
    for key in keys:
        if key in values:
            return values.get(key)
    return fallback


def _mapping_has_any(values: Mapping[str, object], keys: tuple[str, ...]) -> bool:
    return any(key in values for key in keys)


def _bounded_opacity(value: object, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return max(0.0, min(1.0, float(fallback)))


def _scaled_alpha(color: Rgba, opacity: float) -> Rgba:
    return Rgba(
        color.r,
        color.g,
        color.b,
        max(0, min(255, int(round(color.a * _bounded_opacity(opacity, 1.0))))),
    )


def resolve_card_surface_colors(
    *,
    values: Mapping[str, object],
    defaults: Mapping[str, object],
    background_color: RgbaTuple,
    background_opacity: float,
    border_color: RgbaTuple,
    border_opacity: float,
    background_keys: tuple[str, ...] = ("bg_color", "background_color"),
    background_opacity_keys: tuple[str, ...] = ("bg_opacity", "background_opacity"),
    border_keys: tuple[str, ...] = ("border_color",),
    border_opacity_keys: tuple[str, ...] = ("border_opacity",),
) -> tuple[RgbaTuple, RgbaTuple]:
    """Resolve the shared Card Surface/Border baseline with family override precedence.

    Canonical/default-valued family settings are the implicit ``Inherit`` state.
    A family becomes explicit only when its stored colour *or* opacity differs from
    the canonical family default.  Explicit family values keep precedence; otherwise
    the process-local Widget Theme's ``card.background`` / ``card.border`` roles are
    consumed. Returned alpha is fully composed so downstream card styles use an
    opacity of ``1.0`` and do not double-apply alpha.
    """

    theme = get_active_widget_theme()

    default_bg = as_rgba(
        _mapping_value(defaults, background_keys, background_color),
        background_color,
    )
    default_bg_opacity = _bounded_opacity(
        _mapping_value(defaults, background_opacity_keys, background_opacity),
        background_opacity,
    )
    current_bg = as_rgba(
        _mapping_value(values, background_keys, background_color),
        background_color,
    )
    current_bg_opacity = _bounded_opacity(
        _mapping_value(values, background_opacity_keys, background_opacity),
        background_opacity,
    )
    background_explicit = (
        _mapping_has_any(values, background_keys + background_opacity_keys)
        and (current_bg != default_bg or current_bg_opacity != default_bg_opacity)
    )

    default_border = as_rgba(
        _mapping_value(defaults, border_keys, border_color),
        border_color,
    )
    default_border_opacity = _bounded_opacity(
        _mapping_value(defaults, border_opacity_keys, border_opacity),
        border_opacity,
    )
    current_border = as_rgba(
        _mapping_value(values, border_keys, border_color),
        border_color,
    )
    current_border_opacity = _bounded_opacity(
        _mapping_value(values, border_opacity_keys, border_opacity),
        border_opacity,
    )
    border_explicit = (
        _mapping_has_any(values, border_keys + border_opacity_keys)
        and (
            current_border != default_border
            or current_border_opacity != default_border_opacity
        )
    )

    background = (
        _scaled_alpha(current_bg, current_bg_opacity)
        if background_explicit
        else theme.color("card.background")
    )
    border = (
        _scaled_alpha(current_border, current_border_opacity)
        if border_explicit
        else theme.color("card.border")
    )
    return background.as_tuple(), border.as_tuple()


def resolve_primary_text_color(
    *,
    values: Mapping[str, object],
    defaults: Mapping[str, object],
    text_color: RgbaTuple,
    key: str = "color",
) -> RgbaTuple:
    """Resolve the shared primary Widget text baseline with override precedence.

    Canonical/default-valued family text swatches are the implicit ``Inherit``
    state, just like Card Surface/Border. A genuinely authored family colour stays
    explicit; otherwise the Widget Theme's core ``card.text`` role supplies the
    common body-text colour.
    """

    explicit = configured_rgba_override(values, defaults, key, text_color)
    if explicit is not None:
        return explicit.as_tuple()
    return get_active_widget_theme().color("card.text").as_tuple()

def resolve_rgba_role(
    role: str,
    *,
    local_roles: Mapping[str, Rgba | RgbaTuple] | None,
    fallback: Rgba | RgbaTuple,
    explicit: Rgba | RgbaTuple | None = None,
) -> RgbaTuple:
    theme = get_active_widget_theme()
    local = {
        token: color if isinstance(color, Rgba) else Rgba(*color)
        for token, color in dict(local_roles or {}).items()
    }
    fallback_rgba = fallback if isinstance(fallback, Rgba) else Rgba(*fallback)
    explicit_rgba = (
        explicit
        if isinstance(explicit, Rgba) or explicit is None
        else Rgba(*explicit)
    )
    return resolve_widget_visual_color(
        theme,
        role,
        local_roles=local,
        fallback=fallback_rgba,
        explicit=explicit_rgba,
    ).color.as_tuple()


def resolve_header_colors(
    family_id: str,
    *,
    values: Mapping[str, object],
    defaults: Mapping[str, object],
    fill: RgbaTuple,
    border: RgbaTuple,
    text: RgbaTuple,
) -> tuple[RgbaTuple, RgbaTuple, RgbaTuple]:
    """Resolve the common branded-header Fill/Border/Text contract.

    Existing non-default family swatches stay explicit. Default-valued swatches are
    the implicit Inherit state, allowing a future Widget Theme to style all headers
    through ``header.*`` or one family through ``<family>.header.*``.
    """

    family = str(family_id or "").strip()
    if not family:
        raise ValueError("family_id cannot be empty")
    local = {
        "local.header.fill": fill,
        "local.header.border": border,
        "local.header.text": text,
    }
    fill_explicit = configured_rgba_override(
        values, defaults, "header_fill_color", fill
    )
    border_explicit = configured_rgba_override(
        values, defaults, "header_border_color", border
    )
    text_explicit = configured_rgba_override(
        values, defaults, "header_text_color", text
    )
    return (
        resolve_rgba_role(
            f"{family}.header.fill",
            local_roles=local,
            fallback=fill,
            explicit=fill_explicit,
        ),
        resolve_rgba_role(
            f"{family}.header.border",
            local_roles=local,
            fallback=border,
            explicit=border_explicit,
        ),
        resolve_rgba_role(
            f"{family}.header.text",
            local_roles=local,
            fallback=text,
            explicit=text_explicit,
        ),
    )


__all__ = [
    "RgbaTuple",
    "as_rgba",
    "as_tuple",
    "configured_rgba_override",
    "resolve_card_surface_colors",
    "resolve_header_colors",
    "resolve_primary_text_color",
    "resolve_rgba_role",
    "resolve_soft_text_shadow",
]
