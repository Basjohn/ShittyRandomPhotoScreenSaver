"""Input-only compatibility and normalization for wallpaper resampling.

``display.resample_filter`` is the only live setting.  The old
``display.use_lanczos`` flag is translated only while loading persisted data or
an SST payload, then removed.  Runtime callers must never use the retired flag
as a second authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from rendering.image_quality import RESAMPLE_FILTERS
from core.settings.default_contract import require_canonical_default


RESAMPLE_FILTER_KEY = "display.resample_filter"
LEGACY_USE_LANCZOS_KEY = "display.use_lanczos"


def normalize_resample_filter(value: Any, fallback: str | None = None) -> str:
    """Return one supported persisted filter identifier.

    Normalization accepts only the canonical string enum.  Unexpected values
    repair to the supplied canonical fallback instead of being interpreted as
    a legacy boolean at runtime.
    """

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in RESAMPLE_FILTERS:
            return normalized
    return fallback if fallback in RESAMPLE_FILTERS else require_canonical_default(RESAMPLE_FILTER_KEY)


def migrate_legacy_use_lanczos(value: Any) -> str:
    """Map one historical persisted bool-like value to the current enum."""

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on", "enabled"}:
            return "lanczos"
        if normalized in {"false", "0", "no", "off", "disabled"}:
            return "smooth"
    return "lanczos" if bool(value) else "smooth"


def promote_legacy_display_resample_filter(
    values: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Promote ``use_lanczos`` in one persisted/SST Display section.

    The explicit current enum always wins, including when it is malformed; the
    owning enum-normalization seam repairs malformed current input later.  The
    retired member is removed in either case so it cannot persist alongside the
    current authority.
    """

    projected = deepcopy(dict(values))
    if "use_lanczos" not in projected:
        return projected, False
    if "resample_filter" not in projected:
        projected["resample_filter"] = migrate_legacy_use_lanczos(
            projected["use_lanczos"]
        )
    projected.pop("use_lanczos", None)
    return projected, True


__all__ = [
    "LEGACY_USE_LANCZOS_KEY",
    "RESAMPLE_FILTER_KEY",
    "migrate_legacy_use_lanczos",
    "normalize_resample_filter",
    "promote_legacy_display_resample_filter",
]
