"""Mighty Blob renderer wiring and procedural contour ownership."""
from __future__ import annotations

from core.logging.logger import get_logger
from core.settings.visualizer_blob_contract import BLOB_TYPE_MIGHTY
from widgets.spotify_visualizer.blob_pockets import build_blob_pocket_uniform_payload
from widgets.spotify_visualizer.renderers.blob_common import (
    get_common_uniform_names,
    maybe_log_runtime_profile,
    upload_common_uniforms,
)
from widgets.spotify_visualizer.renderers.blob_unshaped_runtime import (
    _resolve_runtime_unshaped_profile,
)
from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1fv as _set1fv,
)

logger = get_logger(__name__)
_PROFILE_SIZE = 64


def get_uniform_names() -> list[str]:
    # Mighty contour controls and pocket state are solved on the CPU.  The
    # shader receives only the final profile, avoiding duplicate/dead contour
    # authority in GLSL.
    return get_common_uniform_names()


def upload_uniforms(gl, uniforms: dict, state) -> bool:
    bass, mid, high, overall = upload_common_uniforms(gl, uniforms, state)
    pocket_data, pocket_mix = build_blob_pocket_uniform_payload(
        getattr(state, "_blob_pocket_state", None)
    )
    profile = _resolve_runtime_unshaped_profile(
        state,
        pocket_data=pocket_data,
        pocket_mix=pocket_mix,
        bass=bass,
        mid=mid,
        high=high,
        overall=overall,
    )
    _set1fv(gl, uniforms, "u_blob_runtime_profile", profile, _PROFILE_SIZE)
    maybe_log_runtime_profile(logger, state, blob_type=BLOB_TYPE_MIGHTY, profile=profile)
    return True
