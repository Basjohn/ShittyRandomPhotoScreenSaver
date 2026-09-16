"""Compatibility promotion for historical Settings-theme file inputs.

Current Settings-theme runtime and authoring use schema v6 exclusively.  This
module is the one removable bridge for user-authored schema-v5 ``.srtheme``
files, which predate the ``about.art.liquid`` semantic colour role.

The bridge is intentionally narrow: a v5 payload must contain the exact v5
colour-role set.  It is never default-merged or used to repair arbitrary
incomplete themes.  Current v6 payloads pass through untouched.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ui.settings_theme_spec import (
    DEFAULT_DARK_SETTINGS_THEME,
    SETTINGS_THEME_SCHEMA_VERSION,
)


LEGACY_SETTINGS_THEME_SCHEMA_VERSION = 5
ABOUT_ART_LIQUID_TOKEN = "about.art.liquid"
_PRIMARY_ACCENT_TOKEN = "chrome.outer_border"


class LegacySettingsThemeInputError(ValueError):
    """A historical theme payload is not a valid supported legacy shape."""


def _legacy_color_role_set() -> set[str]:
    return {
        token
        for token in DEFAULT_DARK_SETTINGS_THEME.colors
        if token != ABOUT_ART_LIQUID_TOKEN
    }


def promote_legacy_settings_theme_payload(
    payload: Mapping[str, Any],
) -> tuple[Mapping[str, Any], bool]:
    """Promote one exact schema-v5 theme payload to canonical schema v6.

    Returns ``(payload, changed)``.  Non-v5 input is returned untouched so the
    current strict parser remains responsible for current/future schema
    validation.  A v5 payload is accepted only when its colour vocabulary is
    exactly the historical v5 set; arbitrary missing/extra roles are rejected
    rather than silently repaired from defaults.
    """

    if payload.get("schema_version") != LEGACY_SETTINGS_THEME_SCHEMA_VERSION:
        return payload, False

    raw_colors = payload.get("colors")
    if not isinstance(raw_colors, dict):
        raise LegacySettingsThemeInputError("schema-v5 colors must be an object")

    expected = _legacy_color_role_set()
    actual = set(raw_colors)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing semantic roles {missing!r}")
        if unexpected:
            details.append(f"unknown semantic roles {unexpected!r}")
        raise LegacySettingsThemeInputError("; ".join(details))

    primary = raw_colors.get(_PRIMARY_ACCENT_TOKEN)
    if not isinstance(primary, list) or len(primary) != 4:
        raise LegacySettingsThemeInputError(
            f"schema-v5 {_PRIMARY_ACCENT_TOKEN} must be an [r, g, b, a] list"
        )

    migrated = dict(payload)
    migrated_colors = dict(raw_colors)
    liquid = list(primary)
    liquid[3] = 255
    migrated_colors[ABOUT_ART_LIQUID_TOKEN] = liquid
    migrated["colors"] = migrated_colors
    migrated["schema_version"] = SETTINGS_THEME_SCHEMA_VERSION
    return migrated, True


__all__ = [
    "ABOUT_ART_LIQUID_TOKEN",
    "LEGACY_SETTINGS_THEME_SCHEMA_VERSION",
    "LegacySettingsThemeInputError",
    "promote_legacy_settings_theme_payload",
]
