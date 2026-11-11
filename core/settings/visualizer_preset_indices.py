"""Shared visualizer preset-index resolution helpers.

Missing/invalid persisted selection repairs to the canonical per-mode selection.
The user-authored preset registry owns runtime slot availability; authored file
slot numbers may be sparse and are compacted for the slider. There is no generic
"first preset" product-default authority.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping
from typing import Any, Dict

from core.logging.logger import get_logger
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    coerce_visualizer_mode_id,
    get_preset_key,
)

logger = get_logger(__name__)

#: The live section's stored preset references: ``{mode: {"preset": identity, "catalogue": signature}}``.
PRESET_REFERENCES_KEY = "preset_references"


def _get_visualizer_presets_module():
    from core.settings import visualizer_presets as _visualizer_presets

    return _visualizer_presets


def get_custom_preset_index(mode: str) -> int:
    """Return the trailing Custom slot index for *mode*."""
    module = _get_visualizer_presets_module()
    return module.get_custom_preset_index(mode)


def get_missing_preset_fallback_index(mode: str) -> int:
    """Resolve missing persisted state from canonical per-mode authority."""
    mode = coerce_visualizer_mode_id(mode)
    key = get_preset_key(mode)
    canonical = int(
        require_canonical_default(f"widgets.spotify_visualizer.{key}")
    )
    custom_idx = get_custom_preset_index(mode)
    if custom_idx <= 0:
        raise RuntimeError(f"visualizer mode {mode!r} has no authored presets")
    # Product defaults select authored content, never the user-owned trailing
    # Custom slot. Runtime positions are compact even when authored file slot
    # numbers are sparse.
    return max(0, min(custom_idx - 1, canonical))


_CUSTOM_IDENTITY = "Custom"
_SLOT_PREFIX = re.compile(r"^\s*preset\s*\d+\s*", re.IGNORECASE)
# (mode, stored reference, catalogue) already reported: the resolver runs on every read, the log line once.
_REPORTED: set[tuple[str, str, str]] = set()


def preset_identity(name: str) -> str:
    """The identity of a preset across catalogue changes: its authored name without the slot number.

    "Preset 7 (Prism)" and "Preset 5 (Prism)" are the same preset moved to another slot (both "Prism");
    "Custom" is the user's own slot wherever it sits. A name with no parenthesised part is its own identity."""
    text = str(name or "").strip()
    if text.lower() == _CUSTOM_IDENTITY.lower():
        return _CUSTOM_IDENTITY
    rest = _SLOT_PREFIX.sub("", text, count=1).strip()
    if rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1].strip()
    return rest or text


def _catalogue_identities(mode: str) -> list[str]:
    from core.settings.visualizer_presets import get_preset_names
    return [preset_identity(name) for name in get_preset_names(mode)]


def catalogue_signature(identities: list[str]) -> str:
    """A short signature of one mode's catalogue (its identities in slot order, Custom last)."""
    return hashlib.sha1("\n".join(identities).encode("utf-8")).hexdigest()[:12]


def _stored_reference(data: Mapping[str, Any], mode: str, prefix: str) -> tuple[str, str, int | None] | None:
    names = data.get(PRESET_REFERENCES_KEY, data.get(f"{prefix}.{PRESET_REFERENCES_KEY}"))
    entry = names.get(mode) if isinstance(names, Mapping) else None
    if not isinstance(entry, Mapping):
        return None
    identity, signature = entry.get("preset"), entry.get("catalogue")
    if not isinstance(identity, str) or not identity or not isinstance(signature, str):
        return None
    slot = entry.get("slot")
    return identity, signature, (slot if isinstance(slot, int) and not isinstance(slot, bool) else None)


def _report(mode: str, stored: str, signature: str, message: str, *args: Any) -> None:
    key = (mode, stored, signature)
    if key in _REPORTED:
        return
    _REPORTED.add(key)
    logger.info("[VIS_PRESETS] " + message, *args)


def resolve_preset_index_from_mapping(
    mode: str,
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> int:
    """Resolve a mode's preset index from a sparse mapping.

    The stored reference is the slot index plus, once written by this build, the preset's identity and the
    catalogue it was chosen from (``preset_references``). While the catalogue is the one the reference was written
    against, the index is the user's choice. When the catalogue changed since (presets removed, renamed or
    renumbered), the identity decides: the preset of the same name wherever it now sits, Custom as Custom, and
    Preset 1 when no preset of that name exists any more. A reference without an identity (a profile written
    before 11 Nov 2026) keeps its index while that index exists. Every fallback logs one line and raises nothing;
    the next save stores the resolved reference (``stamp_preset_references``)."""
    mode = coerce_visualizer_mode_id(mode)
    fallback = get_missing_preset_fallback_index(mode)
    if not isinstance(data, Mapping):
        return fallback

    key = get_preset_key(mode)
    raw = data.get(key, data.get(f"{prefix}.{key}", fallback))
    try:
        idx = int(raw)
    except (TypeError, ValueError):
        return fallback

    custom_idx = get_custom_preset_index(mode)
    reference = _stored_reference(data, mode, prefix)
    if reference is not None:
        identity, signature, slot = reference
        identities = _catalogue_identities(mode)
        current = catalogue_signature(identities)
        # A writer that chose another slot after the reference was written (a selection made against the catalogue
        # this process holds now) owns the index; the reference describes only the slot it was written with.
        chosen_since = slot is not None and slot != idx and 0 <= idx <= custom_idx
        if not chosen_since and (signature != current or not 0 <= idx <= custom_idx):
            if 0 <= idx <= custom_idx and identities[idx] == identity:
                return idx
            if identity in identities:
                found = identities.index(identity)
                _report(mode, f"{idx}:{identity}", current,
                        "%s preset %r moved from slot %d to slot %d after the preset catalogue changed",
                        mode, identity, idx + 1, found + 1)
                return found
            from core.settings.visualizer_preset_compat import retired_successor
            listed, successor = retired_successor(mode, identity)
            if listed and successor in identities:
                found = identities.index(successor)
                _report(mode, f"{idx}:{identity}", current,
                        "%s preset %r was retired; its successor %r selected", mode, identity, successor)
                return found
            _report(mode, f"{idx}:{identity}", current,
                    "%s preset %r no longer exists; %r selected instead",
                    mode, identity, identities[fallback])
            return fallback
    if idx < 0 or idx > custom_idx:
        _report(mode, str(idx), catalogue_signature(_catalogue_identities(mode)),
                "%s preset slot %d no longer exists; slot %d selected instead", mode, idx + 1, fallback + 1)
        return fallback
    return idx


def preset_reference(mode: str, index: int) -> dict[str, str]:
    """The stored reference for slot ``index`` of ``mode``'s current catalogue."""
    identities = _catalogue_identities(mode)
    index = max(0, min(len(identities) - 1, int(index)))
    return {"preset": identities[index], "catalogue": catalogue_signature(identities), "slot": index}


def stamp_preset_references(indices: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """``preset_references`` for resolved per-mode indices (``{preset_key: index}``), every registered mode."""
    references = {}
    for mode in VISUALIZER_MODE_IDS:
        value = indices.get(get_preset_key(mode))
        if value is None:
            continue
        references[mode] = preset_reference(mode, int(value))
    return references


def repair_preset_references(section: Mapping[str, Any]) -> dict[str, Any]:
    """A flat live section with every mode's preset index resolved against the current catalogue and its stored
    reference written beside it (the settings load's one repair; a second run changes nothing)."""
    repaired = dict(section)
    indices = resolve_all_preset_indices_from_mapping(section)
    repaired.update(indices)
    repaired[PRESET_REFERENCES_KEY] = stamp_preset_references(indices)
    return repaired


def normalize_preset_references(value: Any) -> dict[str, dict[str, str]]:
    """Admit a stored ``preset_references`` mapping: registered modes, string identity and signature only."""
    if not isinstance(value, Mapping):
        return {}
    admitted = {}
    for mode, entry in value.items():
        if mode not in VISUALIZER_MODE_IDS or not isinstance(entry, Mapping):
            continue
        identity, signature = entry.get("preset"), entry.get("catalogue")
        if isinstance(identity, str) and identity and isinstance(signature, str) and signature:
            admitted[str(mode)] = {"preset": identity, "catalogue": signature}
            slot = entry.get("slot")
            if isinstance(slot, int) and not isinstance(slot, bool):
                admitted[str(mode)]["slot"] = slot
    return admitted


def resolve_all_preset_indices_from_mapping(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, int]:
    return {
        get_preset_key(mode): resolve_preset_index_from_mapping(mode, data, prefix=prefix)
        for mode in VISUALIZER_MODE_IDS
    }


def resolve_all_preset_indices_from_getter(
    read_value: Callable[[str, Any], Any],
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, int]:
    return resolve_all_preset_indices_from_mapping(
        {
            f"{prefix}.{get_preset_key(mode)}": read_value(
                f"{prefix}.{get_preset_key(mode)}",
                get_missing_preset_fallback_index(mode),
            )
            for mode in VISUALIZER_MODE_IDS
        },
        prefix=prefix,
    )
