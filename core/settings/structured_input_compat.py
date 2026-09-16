"""Compatibility promotion for retired flattened structured-settings input.

Current runtime storage keeps declared structured roots as mappings.  Older
JSON/reset/SST/QSettings paths could instead emit dotted members inside a root
mapping or as top-level ``root.member`` keys.  Accept those shapes only at
persisted/import boundaries and promote them immediately to the current nested
representation.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS


def _assign_nested_if_missing(
    target: dict[str, Any],
    parts: list[str],
    value: Any,
) -> bool:
    """Assign one retired dotted value without overriding canonical nesting."""

    if not parts:
        return False
    current = target
    for part in parts[:-1]:
        existing = current.get(part)
        if existing is None and part not in current:
            child: dict[str, Any] = {}
            current[part] = child
            current = child
            continue
        if not isinstance(existing, Mapping):
            return False
        child = deepcopy(dict(existing))
        current[part] = child
        current = child

    leaf = parts[-1]
    if leaf in current:
        return False
    current[leaf] = deepcopy(value)
    return True


def normalize_legacy_structured_mapping_shape(
    mapping: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Expand retired dotted members inside one declared structured root.

    Only immediate root member names are interpreted. Nested mappings may
    legitimately contain semantic dotted keys (for example Widget Theme colour
    roles such as ``card.background``), so those nested keys are preserved.
    Canonical nested members win when both old and current forms are present.
    """

    normalized: dict[str, Any] = {}
    dotted_members: list[tuple[str, Any]] = []
    changed = False
    for raw_key, value in mapping.items():
        key = str(raw_key)
        if "." in key:
            dotted_members.append((key, value))
            changed = True
            continue
        normalized[key] = deepcopy(value)

    for dotted, value in dotted_members:
        _assign_nested_if_missing(
            normalized,
            [part for part in dotted.split(".") if part],
            value,
        )
    return normalized, changed


def promote_legacy_structured_store_shape(
    data: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Promote retired flattened structured roots in one persisted store image.

    Handles both historical forms:

    * ``{"ui": {"dialog_geometry.width": 1389}}``
    * ``{"ui.dialog_geometry.width": 1389}``

    Current nested root members are authoritative over either retired form.
    The returned mapping contains only current structured-root storage shape.
    """

    normalized = deepcopy(dict(data))
    repaired_roots: list[str] = []

    for root in sorted(STRUCTURED_SETTINGS_ROOTS):
        raw_root = normalized.get(root)
        if isinstance(raw_root, Mapping):
            root_mapping, changed = normalize_legacy_structured_mapping_shape(raw_root)
        else:
            root_mapping = {}
            changed = False

        prefix = f"{root}."
        flat_keys = [key for key in list(normalized) if str(key).startswith(prefix)]
        for flat_key in flat_keys:
            tail = str(flat_key)[len(prefix):]
            _assign_nested_if_missing(
                root_mapping,
                [part for part in tail.split(".") if part],
                normalized[flat_key],
            )
            normalized.pop(flat_key, None)
            changed = True

        if changed:
            normalized[root] = root_mapping
            repaired_roots.append(root)

    return normalized, tuple(repaired_roots)


__all__ = [
    "normalize_legacy_structured_mapping_shape",
    "promote_legacy_structured_store_shape",
]
