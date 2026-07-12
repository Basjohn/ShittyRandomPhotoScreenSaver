"""Blob-only contour advancement outside the GL paint hot path.

The overlay receives one coherent audio/settings snapshot in ``set_state``.
Blob profiles must advance exactly once for that snapshot; recomputing them in
every ``paintGL`` call made spring timing depend on paint cadence and spent
several milliseconds on the UI/GL thread per paint.  This module owns the
cached CPU profile update for both concrete Blob subtypes.
"""
from __future__ import annotations

import time
from typing import Any, Sequence

from core.settings.visualizer_blob_contract import (
    BLOB_TYPE_MIGHTY,
    BLOB_TYPE_SHAPED,
    normalize_blob_type,
)
from widgets.spotify_visualizer.blob_pockets import build_blob_pocket_uniform_payload
from widgets.spotify_visualizer.renderers.blob_shaper_runtime import (
    _build_energy_routing,
    _get_shaper_energy_bands,
    _resample_nodes,
    _resolve_runtime_shaper_profile,
)
from widgets.spotify_visualizer.renderers.blob_unshaped_runtime import (
    _resolve_runtime_unshaped_profile,
)

PROFILE_SIZE = 128


def _freeze_signature(value: Any) -> Any:
    """Return a stable, hashable signature for authored node payloads."""

    if isinstance(value, dict):
        return tuple(
            (str(key), _freeze_signature(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_signature(item) for item in value)
    if isinstance(value, float):
        return round(value, 8)
    return value


def _mighty_live_bands(state: Any) -> tuple[float, float, float, float]:
    fallback = getattr(state, "_energy_bands", None)

    def _read(attr: str, band: str) -> float:
        value = getattr(state, attr, None)
        if value is None:
            value = getattr(fallback, band, 0.0) if fallback is not None else 0.0
        return float(value or 0.0)

    return (
        _read("_blob_live_bass_energy", "bass"),
        _read("_blob_live_mid_energy", "mid"),
        _read("_blob_live_high_energy", "high"),
        _read("_blob_live_overall_energy", "overall"),
    )


def _shaped_geometry(
    state: Any,
) -> tuple[list[float], list[float], list[list[float]]]:
    base_nodes = getattr(
        state,
        "_blob_shape_base_nodes",
        [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]],
    )
    reaction_nodes = getattr(
        state,
        "_blob_shape_reaction_nodes",
        [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]],
    )
    energy_nodes = getattr(state, "_blob_shape_energy_nodes", [])
    signature = (
        PROFILE_SIZE,
        _freeze_signature(base_nodes),
        _freeze_signature(reaction_nodes),
        _freeze_signature(energy_nodes),
    )
    if getattr(state, "_blob_shaper_geometry_signature", None) != signature:
        base_profile = _resample_nodes(base_nodes, PROFILE_SIZE)
        reaction_profile = _resample_nodes(reaction_nodes, PROFILE_SIZE)
        energy_weights = _build_energy_routing(
            energy_nodes,
            PROFILE_SIZE,
            base_profile=base_profile,
            react_profile=reaction_profile,
        )
        setattr(state, "_blob_shaper_cached_base_profile", base_profile)
        setattr(state, "_blob_shaper_cached_reaction_profile", reaction_profile)
        setattr(state, "_blob_shaper_cached_energy_weights", energy_weights)
        setattr(state, "_blob_shaper_geometry_signature", signature)
        setattr(
            state,
            "_blob_shaper_geometry_build_count",
            int(getattr(state, "_blob_shaper_geometry_build_count", 0) or 0) + 1,
        )
    return (
        list(getattr(state, "_blob_shaper_cached_base_profile")),
        list(getattr(state, "_blob_shaper_cached_reaction_profile")),
        list(getattr(state, "_blob_shaper_cached_energy_weights")),
    )


def advance_blob_runtime_profile(state: Any) -> list[float]:
    """Advance the selected Blob subtype once for the current state snapshot."""

    started = time.perf_counter()
    blob_type = normalize_blob_type(
        getattr(state, "_blob_type", None),
        legacy_shaper_enabled=getattr(state, "_blob_shaper_enabled", None),
    )
    if blob_type == BLOB_TYPE_SHAPED:
        base_profile, reaction_profile, energy_weights = _shaped_geometry(state)
        bass, mid, high, overall = _get_shaper_energy_bands(state)
        profile = _resolve_runtime_shaper_profile(
            state,
            base_profile=base_profile,
            react_profile=reaction_profile,
            weights=energy_weights,
            bass=bass,
            mid=mid,
            high=high,
            overall=overall,
        )
    else:
        pocket_data, pocket_mix = build_blob_pocket_uniform_payload(
            getattr(state, "_blob_pocket_state", None)
        )
        bass, mid, high, overall = _mighty_live_bands(state)
        profile = _resolve_runtime_unshaped_profile(
            state,
            pocket_data=pocket_data,
            pocket_mix=pocket_mix,
            bass=bass,
            mid=mid,
            high=high,
            overall=overall,
        )

    generation = int(getattr(state, "_blob_profile_generation", 0) or 0) + 1
    setattr(state, "_blob_profile_generation", generation)
    setattr(state, "_blob_profile_generation_type", blob_type)
    setattr(state, "_blob_profile_compute_ms", (time.perf_counter() - started) * 1000.0)
    setattr(
        state,
        "_blob_profile_compute_count",
        int(getattr(state, "_blob_profile_compute_count", 0) or 0) + 1,
    )
    return list(profile)


def cached_blob_runtime_profile(state: Any, blob_type: str) -> list[float]:
    """Return the set-state profile, with a one-shot cold/prewarm fallback."""

    attr = (
        "_blob_shaper_runtime_profile"
        if blob_type == BLOB_TYPE_SHAPED
        else "_blob_unshaped_runtime_profile"
    )
    profile: Sequence[float] | None = getattr(state, attr, None)
    generation_type = getattr(state, "_blob_profile_generation_type", None)
    if profile is None or len(profile) != PROFILE_SIZE or generation_type != blob_type:
        profile = advance_blob_runtime_profile(state)
    return [float(value) for value in profile]


__all__ = [
    "PROFILE_SIZE",
    "advance_blob_runtime_profile",
    "cached_blob_runtime_profile",
]
