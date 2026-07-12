"""Shaped Blob renderer wiring and authored-contour ownership."""
from __future__ import annotations

from core.logging.logger import get_logger
from core.settings.visualizer_blob_contract import BLOB_TYPE_SHAPED
from widgets.spotify_visualizer.renderers.blob_common import (
    get_common_uniform_names,
    maybe_log_runtime_profile,
    upload_common_uniforms,
)
from widgets.spotify_visualizer.renderers.blob_shaper_runtime import (
    _build_energy_routing,
    _get_shaper_energy_bands,
    _resample_nodes,
    _resolve_runtime_shaper_profile,
)
from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1fv as _set1fv,
    set1i as _set1i,
)

logger = get_logger(__name__)
_PROFILE_SIZE = 128
_logged_shape_signature: tuple | None = None


def get_uniform_names() -> list[str]:
    return get_common_uniform_names() + [
        "u_blob_ring_mode",
        "u_blob_ring_thickness",
    ]


def upload_uniforms(gl, uniforms: dict, state) -> bool:
    upload_common_uniforms(gl, uniforms, state)
    ring_enabled = getattr(state, "_blob_topology", "circle") == "ring"
    ring_thickness = float(getattr(state, "_blob_ring_thickness", 0.3))
    _set1i(gl, uniforms, "u_blob_ring_mode", 1 if ring_enabled else 0)
    _set1f(gl, uniforms, "u_blob_ring_thickness", ring_thickness)

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
    base_profile = _resample_nodes(base_nodes, _PROFILE_SIZE)
    reaction_profile = _resample_nodes(reaction_nodes, _PROFILE_SIZE)
    energy_weights = _build_energy_routing(
        energy_nodes,
        _PROFILE_SIZE,
        base_profile=base_profile,
        react_profile=reaction_profile,
    )
    bass, mid, high, overall = _get_shaper_energy_bands(state)
    runtime_profile = _resolve_runtime_shaper_profile(
        state,
        base_profile=base_profile,
        react_profile=reaction_profile,
        weights=energy_weights,
        bass=bass,
        mid=mid,
        high=high,
        overall=overall,
    )
    _set1fv(gl, uniforms, "u_blob_runtime_profile", runtime_profile, _PROFILE_SIZE)
    transport_sig = (BLOB_TYPE_SHAPED, uniforms.get("u_blob_runtime_profile", -1), _PROFILE_SIZE)
    if getattr(state, "_blob_profile_transport_sig", None) != transport_sig:
        logger.info(
            "[SPOTIFY_VIS][BLOB][PROFILE_TRANSPORT] type=%s uniform_loc=%s samples=%d",
            BLOB_TYPE_SHAPED,
            transport_sig[1],
            _PROFILE_SIZE,
        )
        setattr(state, "_blob_profile_transport_sig", transport_sig)

    global _logged_shape_signature
    signature = (ring_enabled, round(ring_thickness, 3), len(energy_nodes))
    if signature != _logged_shape_signature:
        logger.info(
            "[SPOTIFY_VIS] Shaped Blob renderer active: ring=%s ring_thickness=%.2f energy_nodes=%d",
            ring_enabled,
            ring_thickness,
            len(energy_nodes),
        )
        _logged_shape_signature = signature
    maybe_log_runtime_profile(
        logger,
        state,
        blob_type=BLOB_TYPE_SHAPED,
        profile=runtime_profile,
    )
    return True
