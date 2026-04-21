"""Goo mode uniform renderer.

Uploads all Goo-specific uniforms, including the per-source vec4 array
produced by ``goo_liquid_field.pack_sources_for_upload``.
"""
from __future__ import annotations

import numpy as np
import time

from core.logging.logger import get_logger
from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1i as _set1i,
    set_color4 as _set_color4,
)

logger = get_logger(__name__)

GOO_SOURCE_COUNT_MAX = 64  # must match ``const int GOO_SOURCE_COUNT`` in goo.frag


def get_uniform_names() -> list[str]:
    return [
        "u_playing",
        "u_ghost_alpha",
        "u_overall_energy",
        "u_bass_energy",
        "u_mid_energy",
        "u_high_energy",
        "u_goo_color",
        "u_goo_outline_color",
        "u_goo_shadow_color",
        "u_goo_outline_width",
        "u_goo_inward_outline_width",
        "u_goo_shadow_strength",
        "u_goo_specular_density",
        "u_goo_void_size",
        "u_goo_edge_inward_depth",
        "u_goo_threshold",
        "u_goo_sources",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    """Upload Goo mode uniforms.  *s* is the GL overlay instance."""
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ga = float(s._goo_ghost_alpha if s._goo_ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", eb.bass)
    _set1f(gl, u, "u_mid_energy", eb.mid)
    _set1f(gl, u, "u_high_energy", eb.high)

    _set_color4(gl, u, "u_goo_color", s._goo_color)
    _set_color4(gl, u, "u_goo_outline_color", s._goo_outline_color)
    _set_color4(gl, u, "u_goo_shadow_color", s._goo_shadow_color)
    _set1f(gl, u, "u_goo_outline_width", s._goo_outline_width)
    _set1f(gl, u, "u_goo_inward_outline_width", getattr(s, "_goo_inward_outline_width", s._goo_outline_width))
    _set1f(gl, u, "u_goo_shadow_strength", s._goo_shadow_strength)
    _set1f(gl, u, "u_goo_specular_density", s._goo_specular_density)
    _set1f(gl, u, "u_goo_void_size", getattr(s, "_goo_void_size", 0.025))
    _set1f(gl, u, "u_goo_edge_inward_depth", getattr(s, "_goo_edge_inward_depth", 0.18))
    _set1f(gl, u, "u_goo_threshold", getattr(s, "_goo_threshold", 0.5))

    def _upload_source_array(uniform_name: str, source_data) -> bool:
        loc = u.get(uniform_name, -1)
        if loc < 0:
            return False
        sources = source_data or []
        buf = np.zeros(GOO_SOURCE_COUNT_MAX * 4, dtype="float32")
        count = min(len(sources), GOO_SOURCE_COUNT_MAX)
        for i in range(count):
            src = sources[i]
            if not src:
                continue
            buf[i * 4 + 0] = float(src[0]) if len(src) > 0 else 0.0
            buf[i * 4 + 1] = float(src[1]) if len(src) > 1 else 0.0
            buf[i * 4 + 2] = float(src[2]) if len(src) > 2 else 0.0
            buf[i * 4 + 3] = float(src[3]) if len(src) > 3 else 0.0
        gl.glUniform4fv(loc, GOO_SOURCE_COUNT_MAX, buf)
        return True

    # Upload unified source array
    sources_data = getattr(s, "_goo_sources", None)
    ok = _upload_source_array("u_goo_sources", sources_data)

    if not ok:
        now = time.monotonic()
        last = float(getattr(s, "_goo_missing_sources_uniform_logged_at", 0.0) or 0.0)
        if now - last >= 5.0:
            logger.warning(
                "[SPOTIFY_VIS][GOO] u_goo_sources uniform missing; Goo field upload skipped"
            )
            setattr(s, "_goo_missing_sources_uniform_logged_at", now)

    return True
