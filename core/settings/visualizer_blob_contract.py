"""Canonical Blob subtype settings and forward-migration helpers.

``blob_type`` is the only persisted subtype authority.  The retired
``blob_shaper_enabled`` boolean and the old ``normal`` / ``unshaped`` names
are accepted only while upgrading older settings and preset payloads.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict


BLOB_TYPE_MIGHTY = "mighty"
BLOB_TYPE_SHAPED = "shaped"
DEFAULT_BLOB_TYPE = BLOB_TYPE_MIGHTY
BLOB_TYPE_VALUES: tuple[str, ...] = (
    BLOB_TYPE_MIGHTY,
    BLOB_TYPE_SHAPED,
)

LEGACY_BLOB_TYPE_ALIASES: dict[str, str] = {
    "normal": BLOB_TYPE_MIGHTY,
    "unshaped": BLOB_TYPE_MIGHTY,
}
LEGACY_BLOB_SHAPER_KEY = "blob_shaper_enabled"

# These fields author or decorate the Shaped Blob contour.  Mighty payloads
# must not ferry them through Custom snapshots or curated preset switches.
BLOB_SHAPED_ONLY_KEYS: frozenset[str] = frozenset(
    {
        "blob_shape_base_nodes",
        "blob_shape_reaction_nodes",
        "blob_shape_energy_nodes",
        "blob_shaper_base_strength",
        "blob_shaper_react_strength",
        "blob_shaper_idle_motion",
        "blob_shaper_audio_motion",
        "blob_topology",
        "blob_ring_thickness",
    }
)

# These fields own Mighty Blob's procedural contour.  Shaped payloads must
# not retain them as dormant authority because a later hot switch could
# otherwise resurrect stale Mighty tuning after an authored-shape preset.
BLOB_MIGHTY_ONLY_KEYS: frozenset[str] = frozenset(
    {
        "blob_reactive_deformation",
        "blob_constant_wobble",
        "blob_reactive_wobble",
        "blob_stretch",
        "blob_stretch_tendency",
        "blob_stretch_inner",
        "blob_stretch_outer",
    }
)


def _coerce_legacy_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def normalize_blob_type(
    value: Any = None,
    *,
    legacy_shaper_enabled: Any = None,
    fallback: str = DEFAULT_BLOB_TYPE,
) -> str:
    """Return one canonical ``mighty`` / ``shaped`` Blob subtype.

    A present ``blob_type`` value owns the result.  The retired boolean is
    consulted only when the explicit subtype is absent, which prevents stale
    compatibility data from overriding canonical preset intent.
    """
    normalized = str(value).strip().lower() if value is not None else ""
    if normalized in BLOB_TYPE_VALUES:
        return normalized
    if normalized in LEGACY_BLOB_TYPE_ALIASES:
        return LEGACY_BLOB_TYPE_ALIASES[normalized]
    if not normalized and legacy_shaper_enabled is not None:
        return BLOB_TYPE_SHAPED if _coerce_legacy_bool(legacy_shaper_enabled) else BLOB_TYPE_MIGHTY

    normalized_fallback = str(fallback).strip().lower()
    if normalized_fallback in BLOB_TYPE_VALUES:
        return normalized_fallback
    return DEFAULT_BLOB_TYPE


def migrate_blob_type_mapping(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, Any]:
    """Forward-migrate Blob subtype keys without re-emitting legacy forms.

    Both section-style mappings and full dotted-key mappings are supported.
    Existing canonical ``blob_type`` values always take precedence over the
    retired boolean, even if both are present.
    """
    if not isinstance(data, Mapping):
        return {}

    migrated = dict(data)
    dotted_type = f"{prefix}.blob_type"
    dotted_legacy = f"{prefix}.{LEGACY_BLOB_SHAPER_KEY}"

    plain_type_present = "blob_type" in migrated
    dotted_type_present = dotted_type in migrated
    plain_legacy_present = LEGACY_BLOB_SHAPER_KEY in migrated
    dotted_legacy_present = dotted_legacy in migrated

    if plain_type_present:
        migrated["blob_type"] = normalize_blob_type(migrated.get("blob_type"))
    if dotted_type_present:
        migrated[dotted_type] = normalize_blob_type(migrated.get(dotted_type))

    if not plain_type_present and not dotted_type_present:
        if plain_legacy_present:
            migrated["blob_type"] = normalize_blob_type(
                None,
                legacy_shaper_enabled=migrated.get(LEGACY_BLOB_SHAPER_KEY),
            )
        elif dotted_legacy_present:
            migrated[dotted_type] = normalize_blob_type(
                None,
                legacy_shaper_enabled=migrated.get(dotted_legacy),
            )

    migrated.pop(LEGACY_BLOB_SHAPER_KEY, None)
    migrated.pop(dotted_legacy, None)
    return migrated


def strip_inactive_blob_shaped_payload(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, Any]:
    """Drop every inactive subtype's fields from an active Blob payload.

    The historical function name is retained for call-site compatibility,
    but the contract is now symmetric: Mighty payloads lose Shaped contour
    fields and Shaped payloads lose Mighty procedural-contour fields.
    """
    migrated = migrate_blob_type_mapping(data, prefix=prefix)
    if not migrated:
        return {}

    dotted_mode = f"{prefix}.mode"
    active_mode = migrated.get(dotted_mode) if dotted_mode in migrated else migrated.get("mode")
    if str(active_mode).strip().lower() != "blob":
        return migrated

    dotted_type = f"{prefix}.blob_type"
    explicit_type = (
        migrated.get(dotted_type)
        if dotted_type in migrated
        else migrated.get("blob_type")
    )
    cleaned = dict(migrated)
    resolved_type = normalize_blob_type(explicit_type)
    inactive_keys = (
        BLOB_MIGHTY_ONLY_KEYS
        if resolved_type == BLOB_TYPE_SHAPED
        else BLOB_SHAPED_ONLY_KEYS
    )
    for key in inactive_keys:
        cleaned.pop(key, None)
        cleaned.pop(f"{prefix}.{key}", None)
    return cleaned
