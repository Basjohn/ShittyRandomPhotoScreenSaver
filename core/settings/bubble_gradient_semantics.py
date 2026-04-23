"""Shared Bubble gradient direction semantics and migration helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION = 2

_SPECULAR_DIRECTIONS = {
    "top",
    "bottom",
    "left",
    "right",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
}

_GRADIENT_DIRECTIONS = _SPECULAR_DIRECTIONS | {
    "center_out",
    "center_out_reverse",
}

# Legacy labels -> canonical "brightest point location" labels that preserve the
# visuals produced by the old renderer/shader contract.
_LEGACY_GRADIENT_DIRECTION_MIGRATION = {
    "top": "bottom",
    "bottom": "top",
    "left": "right",
    "right": "left",
    "top_left": "bottom_right",
    "top_right": "bottom_left",
    "bottom_left": "top_right",
    "bottom_right": "top_left",
    "center_out": "center_out",
}

# Shader parameters for canonical brightest-point semantics.
_DIRECTIONAL_SHADER_VECTORS = {
    "top_left": (-0.707, -0.707),
    "top": (0.0, -1.0),
    "top_right": (0.707, -0.707),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "bottom_left": (-0.707, 0.707),
    "bottom": (0.0, 1.0),
    "bottom_right": (0.707, 0.707),
}


def _normalize(value: Any, valid: set[str], default: str) -> str:
    text = str(value).strip().lower()
    return text if text in valid else default


def normalize_bubble_specular_direction(value: Any, default: str = "top_left") -> str:
    """Normalize a Bubble specular direction string."""
    return _normalize(value, _SPECULAR_DIRECTIONS, default)


def normalize_bubble_gradient_direction(value: Any, default: str = "top") -> str:
    """Normalize a Bubble gradient direction string."""
    return _normalize(value, _GRADIENT_DIRECTIONS, default)


def get_bubble_gradient_semantics_version(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> int:
    """Return the persisted Bubble gradient semantics version for *data*."""
    if not isinstance(data, Mapping):
        return 0

    for key in (
        "bubble_gradient_semantics_version",
        f"{prefix}.bubble_gradient_semantics_version",
    ):
        raw = data.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return 0


def migrate_legacy_bubble_gradient_direction(value: Any) -> str:
    """Map a legacy Bubble gradient label to the canonical brightest-point label."""
    normalized = normalize_bubble_gradient_direction(value)
    return _LEGACY_GRADIENT_DIRECTION_MIGRATION.get(normalized, normalized)


def resolve_bubble_gradient_direction(
    value: Any,
    *,
    semantics_version: int,
    default: str = "top",
) -> str:
    """Return a canonical Bubble gradient label, migrating legacy values if needed."""
    normalized = normalize_bubble_gradient_direction(value, default=default)
    if semantics_version >= CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION:
        return normalized
    return migrate_legacy_bubble_gradient_direction(normalized)


def get_bubble_gradient_shader_mode(direction: str) -> int:
    """Return the shader mode for a canonical Bubble gradient direction."""
    normalized = normalize_bubble_gradient_direction(direction)
    if normalized == "center_out":
        return 1
    if normalized == "center_out_reverse":
        return 2
    return 0


def get_bubble_gradient_shader_vector(direction: str) -> tuple[float, float]:
    """Return the shader vector for a canonical Bubble gradient direction."""
    normalized = normalize_bubble_gradient_direction(direction)
    if normalized in {"center_out", "center_out_reverse"}:
        return (0.0, 0.0)
    return _DIRECTIONAL_SHADER_VECTORS.get(normalized, _DIRECTIONAL_SHADER_VECTORS["top"])
