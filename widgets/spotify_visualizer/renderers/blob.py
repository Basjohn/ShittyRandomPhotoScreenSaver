"""Compatibility facade for the split Mighty and Shaped Blob renderers.

Production shader dispatch resolves one concrete renderer before upload.  This
module remains import-compatible for older tests/tools and exposes the shaped
solver helpers that historically lived here.
"""
from __future__ import annotations

from core.settings.visualizer_blob_contract import (
    BLOB_TYPE_SHAPED,
    normalize_blob_type,
)
from widgets.spotify_visualizer.renderers.blob_mighty import (
    get_uniform_names as mighty_uniform_names,
    upload_uniforms as mighty_upload,
)
from widgets.spotify_visualizer.renderers.blob_shaped import (
    get_uniform_names as shaped_uniform_names,
    upload_uniforms as shaped_upload,
)
from widgets.spotify_visualizer.renderers.blob_shaper_runtime import (  # noqa: F401
    _build_energy_routing,
    _get_shaper_energy_bands,
    _resample_nodes,
    _resolve_runtime_shaper_profile,
    _resolve_shaper_radius_at_angle,
    _resolve_shaper_radius,
    _resolve_shaper_targets,
    _sample_routed_shaper_energy,
    _solve_runtime_shaper_profile_step,
)
from widgets.spotify_visualizer.renderers.blob_unshaped_runtime import (  # noqa: F401
    _resolve_runtime_unshaped_profile,
)


def get_uniform_names() -> list[str]:
    return list(dict.fromkeys(mighty_uniform_names() + shaped_uniform_names()))


def upload_uniforms(gl, uniforms: dict, state) -> bool:
    blob_type = normalize_blob_type(
        getattr(state, "_blob_type", None),
        legacy_shaper_enabled=getattr(state, "_blob_shaper_enabled", None),
    )
    if blob_type == BLOB_TYPE_SHAPED:
        return shaped_upload(gl, uniforms, state)
    return mighty_upload(gl, uniforms, state)
