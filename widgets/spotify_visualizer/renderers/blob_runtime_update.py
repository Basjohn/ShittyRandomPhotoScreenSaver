"""Blob-only contour advancement outside the GL paint hot path.

The overlay receives one coherent audio/settings snapshot in ``set_state``.
Blob profiles must advance exactly once for that snapshot; recomputing them in
every ``paintGL`` call made spring timing depend on paint cadence and spent
several milliseconds on the UI/GL thread per paint.  This module owns the
cached CPU profile update for both concrete Blob subtypes.
"""
from __future__ import annotations

import math
import time
from typing import Any, Sequence

from core.settings.visualizer_blob_contract import (
    BLOB_TYPE_SHAPED,
    normalize_blob_type,
)
from widgets.spotify_visualizer.blob_pockets import build_blob_pocket_uniform_payload
from widgets.spotify_visualizer.blob_tendril_runtime import (
    TENDRIL_COUNT,
    advance_blob_tendril_state,
    build_blob_tendril_payload,
)
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
PROFILE_MAX_HZ = 30.0
_PROFILE_MIN_INTERVAL = 1.0 / PROFILE_MAX_HZ - 1e-5
_MIGHTY_COLD_PROFILE = tuple(
    1.0
    + math.cos(math.tau * idx / PROFILE_SIZE + 0.65) * 0.072
    + math.cos(math.tau * 2.0 * idx / PROFILE_SIZE + 2.10) * 0.038
    + math.cos(math.tau * 3.0 * idx / PROFILE_SIZE + 4.20) * 0.018
    for idx in range(PROFILE_SIZE)
)
_SHAPED_COLD_PROFILE = tuple(
    1.0
    + math.cos(math.tau * idx / PROFILE_SIZE + 0.20) * 0.045
    + math.cos(math.tau * 2.0 * idx / PROFILE_SIZE + 2.70) * 0.024
    for idx in range(PROFILE_SIZE)
)


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
        getattr(state, "_blob_shaper_cached_base_profile"),
        getattr(state, "_blob_shaper_cached_reaction_profile"),
        getattr(state, "_blob_shaper_cached_energy_weights"),
    )


def _runtime_profile_attr(blob_type: str) -> str:
    return (
        "_blob_shaper_runtime_profile"
        if blob_type == BLOB_TYPE_SHAPED
        else "_blob_unshaped_runtime_profile"
    )


def _advance_tendril_transport(
    state: Any,
    *,
    blob_type: str,
    profile: Sequence[float],
) -> None:
    """Advance cheap Blob-only display geometry at every state handoff."""

    started = time.perf_counter()
    target_geometry, target_motion = build_blob_tendril_payload(
        state,
        blob_type=blob_type,
        profile=profile,
    )
    target_active_tendrils = sum(
        1
        for idx in range(TENDRIL_COUNT)
        if float(target_geometry[idx * 4 + 1]) > 0.002
    )
    setattr(state, "_blob_tendril_target_active_count", target_active_tendrils)
    tendril_geometry, _tendril_motion = advance_blob_tendril_state(
        state,
        blob_type=blob_type,
        target_geometry=target_geometry,
        target_motion=target_motion,
    )
    active_tendrils = sum(
        1
        for idx in range(TENDRIL_COUNT)
        if float(tendril_geometry[idx * 4 + 1]) > 0.002
    )
    setattr(state, "_blob_tendril_active_count", active_tendrils)
    setattr(
        state,
        "_blob_tendril_max_reach",
        max(
            (float(tendril_geometry[idx * 4 + 1]) for idx in range(TENDRIL_COUNT)),
            default=0.0,
        ),
    )
    transport_ms = (time.perf_counter() - started) * 1000.0
    setattr(state, "_blob_tendril_transport_ms", transport_ms)
    setattr(
        state,
        "_blob_tendril_transport_total_ms",
        float(getattr(state, "_blob_tendril_transport_total_ms", 0.0) or 0.0)
        + transport_ms,
    )
    setattr(
        state,
        "_blob_tendril_transport_max_ms",
        max(
            float(getattr(state, "_blob_tendril_transport_max_ms", 0.0) or 0.0),
            transport_ms,
        ),
    )
    setattr(
        state,
        "_blob_tendril_transport_count",
        int(getattr(state, "_blob_tendril_transport_count", 0) or 0) + 1,
    )


def advance_blob_runtime_profile(state: Any, *, force: bool = False) -> list[float]:
    """Advance the selected Blob subtype at a bounded contour cadence.

    Audio snapshots can arrive at roughly 90 Hz and compositor paints may be
    even more frequent. A 128-sample spring solve at that cadence multiplied
    poorly across displays. Thirty contour solves per second retain fluid body
    motion; the much cheaper tendril display transport still advances on every
    coherent state handoff so its visual easing does not become stair-stepped.
    """

    blob_type = normalize_blob_type(
        getattr(state, "_blob_type", None),
        legacy_shaper_enabled=getattr(state, "_blob_shaper_enabled", None),
    )
    setattr(
        state,
        "_blob_profile_advance_request_count",
        int(getattr(state, "_blob_profile_advance_request_count", 0) or 0) + 1,
    )
    profile_attr = _runtime_profile_attr(blob_type)
    existing: Sequence[float] | None = getattr(state, profile_attr, None)
    generation_type = getattr(state, "_blob_profile_generation_type", None)
    wall_ts = time.monotonic()
    previous_wall_ts = float(getattr(state, "_blob_profile_wall_ts", 0.0) or 0.0)
    cache_valid = (
        existing is not None
        and len(existing) == PROFILE_SIZE
        and generation_type == blob_type
    )
    if (
        not force
        and cache_valid
        and previous_wall_ts > 0.0
        and wall_ts - previous_wall_ts < _PROFILE_MIN_INTERVAL
    ):
        setattr(
            state,
            "_blob_profile_skip_count",
            int(getattr(state, "_blob_profile_skip_count", 0) or 0) + 1,
        )
        cached_profile = existing if isinstance(existing, list) else list(existing)
        _advance_tendril_transport(
            state,
            blob_type=blob_type,
            profile=cached_profile,
        )
        return cached_profile

    started = time.perf_counter()
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

    _advance_tendril_transport(
        state,
        blob_type=blob_type,
        profile=profile,
    )

    generation = int(getattr(state, "_blob_profile_generation", 0) or 0) + 1
    setattr(state, "_blob_profile_generation", generation)
    setattr(state, "_blob_profile_generation_type", blob_type)
    compute_ms = (time.perf_counter() - started) * 1000.0
    setattr(state, "_blob_profile_compute_ms", compute_ms)
    setattr(
        state,
        "_blob_profile_compute_total_ms",
        float(getattr(state, "_blob_profile_compute_total_ms", 0.0) or 0.0) + compute_ms,
    )
    setattr(
        state,
        "_blob_profile_compute_max_ms",
        max(float(getattr(state, "_blob_profile_compute_max_ms", 0.0) or 0.0), compute_ms),
    )
    setattr(
        state,
        "_blob_profile_compute_count",
        int(getattr(state, "_blob_profile_compute_count", 0) or 0) + 1,
    )
    setattr(state, "_blob_profile_wall_ts", wall_ts)
    return profile if isinstance(profile, list) else list(profile)


def cached_blob_runtime_profile(state: Any, blob_type: str) -> list[float]:
    """Return the set-state profile, with a one-shot cold/prewarm fallback."""

    attr = _runtime_profile_attr(blob_type)
    profile: Sequence[float] | None = getattr(state, attr, None)
    generation_type = getattr(state, "_blob_profile_generation_type", None)
    if profile is None or len(profile) != PROFILE_SIZE or generation_type != blob_type:
        # Paint is deliberately read-only. The state handoff owns expensive
        # contour generation; a failed/cold handoff gets a bounded, visibly
        # non-circular one-frame fallback instead of solving once per paint.
        if blob_type == BLOB_TYPE_SHAPED:
            authored = getattr(state, "_blob_shaper_cached_base_profile", None)
            profile = (
                authored
                if authored is not None and len(authored) == PROFILE_SIZE
                else _SHAPED_COLD_PROFILE
            )
        else:
            profile = _MIGHTY_COLD_PROFILE
    return profile if isinstance(profile, list) else list(profile)


__all__ = [
    "PROFILE_SIZE",
    "PROFILE_MAX_HZ",
    "advance_blob_runtime_profile",
    "cached_blob_runtime_profile",
]
