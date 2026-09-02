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


RgbaTuple = tuple[int, int, int, int]


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
    "resolve_header_colors",
    "resolve_rgba_role",
]
