"""Lightweight canonical defaults lookup and profile overlay contract.

This module deliberately imports only the editable defaults data modules.  It is
safe for settings models and early-startup readers to use without importing the
heavier visualizer normalization/model graph owned by :mod:`core.settings.defaults`.

Product defaults have one authority:

* ``default_settings.DEFAULT_SETTINGS`` for the Normal/Screensaver profile;
* ``default_profile_overrides.PROFILE_DEFAULT_OVERRIDES`` for genuine profile
  differences such as Media Center always-on-top behavior.

No reader should invent a second persisted product default in a call-site
literal.  Defensive reads may ask this module for the canonical value instead.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any, Mapping

from .default_profile_overrides import PROFILE_DEFAULT_OVERRIDES
from .default_settings import DEFAULT_SETTINGS

NORMAL_PROFILE = "Screensaver"
MC_PROFILE = "Screensaver_MC"
MISSING_DEFAULT = object()


def _resolve_profile(application: str | None) -> str:
    return MC_PROFILE if application == MC_PROFILE else NORMAL_PROFILE


@lru_cache(maxsize=2)
def _canonical_defaults_readonly(profile: str) -> dict[str, Any]:
    """Cached, read-only canonical tree for a profile.

    Built once per profile from the immutable module-level ``DEFAULT_SETTINGS``
    (never mutated at runtime). Callers MUST treat the result as read-only:
    :func:`get_canonical_default` only traverses it and deep-copies the single
    leaf value it returns, so the shared tree is never mutated. This keeps a
    single-key lookup O(path depth) instead of deep-copying the whole ~1450-node
    defaults tree on every ``SettingsManager.get()`` (that per-call full-tree copy
    was ~0.5ms, enough to stall hot paths that read settings per frame/event).
    """
    defaults = deepcopy(DEFAULT_SETTINGS)
    if profile == MC_PROFILE:
        defaults = merge_default_overrides(
            defaults,
            PROFILE_DEFAULT_OVERRIDES.get(MC_PROFILE, {}),
        )
    return defaults


def merge_default_overrides(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Deep-merge one profile override mapping without mutating either input."""

    merged = deepcopy(dict(base))
    for key, value in overrides.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = merge_default_overrides(current, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def get_raw_default_settings(application: str | None = None) -> dict[str, Any]:
    """Return editable canonical defaults with the selected profile overlay.

    Unlike ``defaults.get_default_settings()``, this lightweight accessor does
    not invoke visualizer normalization.  It is intended for authority lookup,
    parser defaults and early startup where importing the model graph would
    create a cycle.
    """

    profile = MC_PROFILE if application == MC_PROFILE else NORMAL_PROFILE
    defaults = deepcopy(DEFAULT_SETTINGS)
    if profile == MC_PROFILE:
        defaults = merge_default_overrides(
            defaults,
            PROFILE_DEFAULT_OVERRIDES.get(MC_PROFILE, {}),
        )
    return defaults


def get_canonical_default(
    key: str,
    application: str | None = None,
    *,
    missing: Any = MISSING_DEFAULT,
) -> Any:
    """Return one canonical default by dotted path, or *missing* if absent.

    Dots are treated as path separators only while traversing mappings.  If the
    remaining suffix exists as one literal mapping key it wins, preserving
    semantic keys such as Widget Theme colour-role names that intentionally
    contain dots.
    """

    key_text = str(key or "").strip()
    if not key_text:
        return missing

    # Read-only, cached canonical tree: we only traverse it and deep-copy the
    # single leaf value returned below, so the shared tree is never mutated.
    current: Any = _canonical_defaults_readonly(_resolve_profile(application))
    parts = key_text.split(".")
    index = 0
    while index < len(parts):
        if not isinstance(current, Mapping):
            return missing

        remainder = ".".join(parts[index:])
        if remainder in current:
            return deepcopy(current[remainder])

        part = parts[index]
        if part not in current:
            return missing
        current = current[part]
        index += 1

    return deepcopy(current)


def require_canonical_default(
    key: str,
    application: str | None = None,
) -> Any:
    """Return one canonical default and fail loudly if the schema is incomplete."""

    value = get_canonical_default(key, application, missing=MISSING_DEFAULT)
    if value is MISSING_DEFAULT:
        raise KeyError(f"Canonical defaults are missing persisted product key: {key}")
    return value


__all__ = [
    "MC_PROFILE",
    "MISSING_DEFAULT",
    "NORMAL_PROFILE",
    "get_canonical_default",
    "get_raw_default_settings",
    "merge_default_overrides",
    "require_canonical_default",
]
