"""Mighty Blob renderer wiring and procedural contour ownership."""
from __future__ import annotations

from core.logging.logger import get_logger
from core.settings.visualizer_blob_contract import BLOB_TYPE_MIGHTY
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
    set1fv as _set1fv,
)

logger = get_logger(__name__)
def get_uniform_names() -> list[str]:
    # Mighty contour controls and pocket state are solved on the CPU.  The
    # shader receives only the final profile, avoiding duplicate/dead contour
    # authority in GLSL.
    return get_common_uniform_names()


def upload_uniforms(gl, uniforms: dict, state) -> bool:
    upload_common_uniforms(gl, uniforms, state)
    profile = cached_blob_runtime_profile(state, BLOB_TYPE_MIGHTY)
    _set1fv(gl, uniforms, "u_blob_runtime_profile", profile, PROFILE_SIZE)
    transport_sig = (BLOB_TYPE_MIGHTY, uniforms.get("u_blob_runtime_profile", -1), PROFILE_SIZE)
    if getattr(state, "_blob_profile_transport_sig", None) != transport_sig:
        logger.info(
            "[SPOTIFY_VIS][BLOB][PROFILE_TRANSPORT] type=%s uniform_loc=%s samples=%d",
            BLOB_TYPE_MIGHTY,
            transport_sig[1],
            PROFILE_SIZE,
        )
        setattr(state, "_blob_profile_transport_sig", transport_sig)
    maybe_log_runtime_profile(logger, state, blob_type=BLOB_TYPE_MIGHTY, profile=profile)
    return True
