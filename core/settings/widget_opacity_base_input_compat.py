"""Input-only compatibility for the Widget Opacity baseline.

Until 21 Nov 2026 ``widgets.global.widget_opacity_adjust`` was measured from the authored
surface density: 0 was the authored look. The Widget surface now has a theme-authored base
(``core.settings.surface_opacity.WIDGET_OPACITY_BASE``) and the stored value is an offset
from it, so a stored value keeps its look only when the base is added to it once. The
profile marks that it has been written in the new meaning with ``opacity_base_version``;
a section without the marker holds an old-meaning value (or none) and is bridged before
current defaults are merged, because the default 0.0 would otherwise mask it.

An unset value is not touched: it is the offset 0, which now draws the base.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.settings.surface_opacity import WIDGET_OPACITY_BASE, admit_opacity_adjust

OPACITY_BASE_VERSION_KEY = "opacity_base_version"
OPACITY_BASE_VERSION = 1
WIDGET_OFFSET_KEY = "widget_opacity_adjust"


def bridge_widget_opacity_base(global_section: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Return the ``widgets.global`` section in the current meaning, and whether it changed."""
    projected = dict(global_section)
    if _version(projected.get(OPACITY_BASE_VERSION_KEY)) >= OPACITY_BASE_VERSION:
        return projected, False
    if WIDGET_OFFSET_KEY in projected:
        # Old meaning: the stored value was the whole adjustment; the new offset adds the base back.
        projected[WIDGET_OFFSET_KEY] = admit_opacity_adjust(
            admit_opacity_adjust(projected[WIDGET_OFFSET_KEY]) - WIDGET_OPACITY_BASE)
    projected[OPACITY_BASE_VERSION_KEY] = OPACITY_BASE_VERSION
    return projected, True


def _version(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


__all__ = ["OPACITY_BASE_VERSION", "OPACITY_BASE_VERSION_KEY", "bridge_widget_opacity_base"]
