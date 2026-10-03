"""Input-only compatibility for the 3D Detail tier.

``transitions.detail_3d`` (High / Balanced / Performance, on the Transitions Setup page) was the
only 3D tier before the 3D Settings tab. It now lives as the 3D Transitions family tier,
``scene3d.transitions_detail``. While loading persisted data or an SST payload a stored
Balanced or Performance (a choice someone made) becomes that family tier; High, the old default,
becomes "General" (the new default: Auto, High on a discrete GPU). The retired leaf is then
removed. An explicit current family tier always wins. Runtime never reads the retired key.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

LEGACY_TRANSITIONS_DETAIL_KEY = "transitions.detail_3d"
SCENE3D_TRANSITIONS_DETAIL_KEY = "scene3d.transitions_detail"
_PRESERVED = ("Balanced", "Performance")


def migrate_legacy_transitions_detail(value: Any) -> str | None:
    """The family tier an old stored value becomes, or None to keep the current default."""
    return str(value) if value in _PRESERVED else None


def promote_legacy_transitions_detail(
    transitions: Mapping[str, Any],
    scene3d: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    """Promote ``detail_3d`` out of one persisted/SST Transitions section.

    Returns the Transitions section without the retired member, the ``scene3d`` section with
    the promoted family tier (None when there was none and nothing to promote), and whether
    anything changed."""
    projected = deepcopy(dict(transitions))
    if "detail_3d" not in projected:
        return projected, None if scene3d is None else dict(scene3d), False
    legacy = projected.pop("detail_3d")
    target = None if scene3d is None else deepcopy(dict(scene3d))
    tier = migrate_legacy_transitions_detail(legacy)
    if tier is not None and (target is None or "transitions_detail" not in target):
        target = {} if target is None else target
        target["transitions_detail"] = tier
    return projected, target, True


__all__ = [
    "LEGACY_TRANSITIONS_DETAIL_KEY",
    "SCENE3D_TRANSITIONS_DETAIL_KEY",
    "migrate_legacy_transitions_detail",
    "promote_legacy_transitions_detail",
]
