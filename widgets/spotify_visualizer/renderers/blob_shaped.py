"""Shaped Blob renderer wiring and authored-contour ownership."""
from __future__ import annotations

from core.logging.logger import get_logger
from core.settings.visualizer_blob_contract import BLOB_TYPE_SHAPED
from widgets.spotify_visualizer.renderers.blob_common import (
    get_common_uniform_names,
    maybe_log_runtime_profile,
    upload_common_uniforms,
)
from widgets.spotify_visualizer.renderers.blob_runtime_update import (
    PROFILE_SIZE,
    cached_blob_runtime_profile,
)
from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1fv as _set1fv,
    set1i as _set1i,
)

logger = get_logger(__name__)
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

    energy_nodes = getattr(state, "_blob_shape_energy_nodes", [])
    runtime_profile = cached_blob_runtime_profile(state, BLOB_TYPE_SHAPED)
    _set1fv(gl, uniforms, "u_blob_runtime_profile", runtime_profile, PROFILE_SIZE)
    transport_sig = (BLOB_TYPE_SHAPED, uniforms.get("u_blob_runtime_profile", -1), PROFILE_SIZE)
    if getattr(state, "_blob_profile_transport_sig", None) != transport_sig:
        logger.info(
            "[SPOTIFY_VIS][BLOB][PROFILE_TRANSPORT] type=%s uniform_loc=%s samples=%d",
            BLOB_TYPE_SHAPED,
            transport_sig[1],
            PROFILE_SIZE,
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
