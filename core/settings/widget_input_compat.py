"""Bounded persisted Widget-input compatibility transforms.

These helpers sit at settings/import boundaries only.  Runtime/UI/presentation
code consumes canonical Widget schema and must not grow duplicate legacy reads.
Each transform is intentionally narrow so its compatibility horizon can later
be closed without disturbing current normalization or defaults authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


_CLOCK_SECTION = "clock"
_CLOCK_SEPARATOR_CURRENT_KEY = "show_separator"
_CLOCK_SEPARATOR_LEGACY_KEY = "show_digital_separator"


def promote_legacy_clock_separator(
    widgets: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Promote the retired Clock separator key into current Widget schema.

    Profiles predating the shared analogue/digital separator stored the base
    Clock flag as ``show_digital_separator``.  Current ownership is the
    mode-neutral ``show_separator``.  A current key always wins when both are
    present; the retired key is then removed so downstream code sees canonical
    input only.
    """

    projected = dict(widgets)
    clock = projected.get(_CLOCK_SECTION)
    if not isinstance(clock, Mapping):
        return projected, False

    clock_projected = deepcopy(dict(clock))
    if _CLOCK_SEPARATOR_LEGACY_KEY not in clock_projected:
        return projected, False

    if _CLOCK_SEPARATOR_CURRENT_KEY not in clock_projected:
        clock_projected[_CLOCK_SEPARATOR_CURRENT_KEY] = deepcopy(
            clock_projected[_CLOCK_SEPARATOR_LEGACY_KEY]
        )
    clock_projected.pop(_CLOCK_SEPARATOR_LEGACY_KEY, None)
    projected[_CLOCK_SECTION] = clock_projected
    return projected, True


__all__ = ["promote_legacy_clock_separator"]
