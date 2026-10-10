"""Forward-only cleanup for retired transitions.

Retired 2026-10-10 on the operator's call: Diffuse, Block Puzzle Flip, Ink Bloom, Relief Rise and
Accordion Fold. A stored profile may still name them in the per-transition activation, pool and
duration maps, select one as the current type, or hold their own settings section; startup drops
all of it. A retired current type falls back through the registry's canonicalisation (Crossfade).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

RETIRED_TRANSITIONS = {
    "Diffuse": "diffuse",
    "Block Puzzle Flip": "block_flip",
    "Ink Bloom": "ink_bloom",
    "Relief Rise": "relief_rise",
    "Accordion Fold": "accordion_fold",
}
_NAMED_MAPS = ("activation", "pool", "durations")


def strip_retired_transition_settings(transitions: Mapping[str, Any]) -> tuple[Dict[str, Any], bool]:
    """The ``transitions`` root without retired transitions, and whether anything was removed."""
    cleaned: Dict[str, Any] = {}
    changed = False
    for key, value in transitions.items():
        if key in RETIRED_TRANSITIONS.values():
            changed = True
            continue
        if key in _NAMED_MAPS and isinstance(value, Mapping):
            kept = {name: entry for name, entry in value.items() if name not in RETIRED_TRANSITIONS}
            changed = changed or len(kept) != len(value)
            value = kept
        elif key == "type" and value in RETIRED_TRANSITIONS:
            from rendering.transition_registry import canonicalize_transition_name

            value = canonicalize_transition_name(value)
            changed = True
        cleaned[key] = value
    return cleaned, changed
