"""Retired dotted Settings names accepted only at persisted/import boundaries."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


LEGACY_DOTTED_SETTING_ALIASES = {
    "input.hard_exit": "input.interaction_mode",
}

# Settings whose consumer no longer exists. They are removed from persisted
# profiles at load (``SettingsManager.validate_and_repair``) and skipped at SST
# import, so older exports cannot bring them back. The RSS worker process was
# registered but never started (wallpaper feeds run in-process on the shared
# feed core), and no FFT worker ever existed.
RETIRED_SETTING_KEYS = frozenset({
    "workers.rss.enabled",
    "workers.fft.enabled",
})


def is_legacy_setting_alias(key: object) -> bool:
    return str(key) in LEGACY_DOTTED_SETTING_ALIASES


def promote_legacy_section_aliases(
    section: str,
    values: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Promote retired dotted aliases inside one nested SST section.

    Current names always win when both representations are supplied. The
    retired member is removed from the projected mapping so later coercion and
    persistence consume current schema only.
    """

    section_name = str(section)
    projected = deepcopy(dict(values))
    changed = False
    prefix = f"{section_name}."
    for legacy_key, current_key in LEGACY_DOTTED_SETTING_ALIASES.items():
        if not legacy_key.startswith(prefix) or not current_key.startswith(prefix):
            continue
        legacy_member = legacy_key[len(prefix):]
        current_member = current_key[len(prefix):]
        if legacy_member not in projected:
            continue
        if current_member not in projected:
            projected[current_member] = deepcopy(projected[legacy_member])
        projected.pop(legacy_member, None)
        changed = True
    return projected, changed


__all__ = [
    "LEGACY_DOTTED_SETTING_ALIASES",
    "RETIRED_SETTING_KEYS",
    "is_legacy_setting_alias",
    "promote_legacy_section_aliases",
]
