"""Dev Curve mode uniform renderer."""
from __future__ import annotations

import numpy as np

from widgets.spotify_visualizer.renderers.gl_helpers import (
    set1f as _set1f,
    set1i as _set1i,
    set_color4 as _set_color4,
)

DEVCURVE_SAMPLE_COUNT_MAX = 96


def get_uniform_names() -> list[str]:
    return [
        "u_playing",
        "u_ghost_alpha",
        "u_devcurve_sample_count",
        "u_devcurve_base_level",
        "u_devcurve_layer_bass_color",
        "u_devcurve_layer_bass_outline_color",
        "u_devcurve_layer_bass_outline_width",
        "u_devcurve_layer_bass_enabled",
        "u_devcurve_layer_bass_alpha",
        "u_devcurve_curve_bass",
        "u_devcurve_layer_vocals_color",
        "u_devcurve_layer_vocals_outline_color",
        "u_devcurve_layer_vocals_outline_width",
        "u_devcurve_layer_vocals_enabled",
        "u_devcurve_layer_vocals_alpha",
        "u_devcurve_curve_vocals",
        "u_devcurve_layer_mids_color",
        "u_devcurve_layer_mids_outline_color",
        "u_devcurve_layer_mids_outline_width",
        "u_devcurve_layer_mids_enabled",
        "u_devcurve_layer_mids_alpha",
        "u_devcurve_curve_mids",
        "u_devcurve_layer_transients_color",
        "u_devcurve_layer_transients_outline_color",
        "u_devcurve_layer_transients_outline_width",
        "u_devcurve_layer_transients_enabled",
        "u_devcurve_layer_transients_alpha",
        "u_devcurve_curve_transients",
        "u_devcurve_order0",
        "u_devcurve_order1",
        "u_devcurve_order2",
        "u_devcurve_order3",
        "u_devcurve_foreground_layer_id",
        "u_devcurve_foreground_shadow_enabled",
        "u_devcurve_foreground_shadow_alpha",
        "u_devcurve_foreground_shadow_darken",
        "u_devcurve_foreground_shadow_offset",
        "u_devcurve_foreground_specular_enabled",
        "u_devcurve_foreground_specular_alpha",
        "u_devcurve_foreground_specular_width",
        "u_devcurve_foreground_specular_offset",
        "u_devcurve_foreground_specular_crest_bias",
        "u_devcurve_specular_slot0",
        "u_devcurve_specular_slot1",
        "u_devcurve_specular_slot2",
    ]


def _upload_curve(gl, uniforms: dict, uniform_name: str, values) -> None:
    loc = uniforms.get(uniform_name, -1)
    if loc < 0:
        return
    arr = np.zeros(DEVCURVE_SAMPLE_COUNT_MAX, dtype="float32")
    src = values or []
    n = min(len(src), DEVCURVE_SAMPLE_COUNT_MAX)
    for i in range(n):
        arr[i] = float(src[i])
    gl.glUniform1fv(loc, DEVCURVE_SAMPLE_COUNT_MAX, arr)


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1i(gl, u, "u_playing", 1 if s._playing else 0)
    _set1f(
        gl,
        u,
        "u_ghost_alpha",
        float(getattr(s, "_devcurve_ghost_alpha", 0.0) if getattr(s, "_devcurve_ghosting_enabled", False) else 0.0),
    )

    _set1i(gl, u, "u_devcurve_sample_count", int(getattr(s, "_devcurve_sample_count", DEVCURVE_SAMPLE_COUNT_MAX)))
    _set1f(gl, u, "u_devcurve_base_level", float(getattr(s, "_devcurve_base_level", 0.58)))

    _set_color4(gl, u, "u_devcurve_layer_bass_color", getattr(s, "_devcurve_layer_bass_color", None))
    _set_color4(gl, u, "u_devcurve_layer_bass_outline_color", getattr(s, "_devcurve_layer_bass_outline_color", None))
    _set1f(gl, u, "u_devcurve_layer_bass_outline_width", float(getattr(s, "_devcurve_layer_bass_outline_width", 0.006)))
    _set1i(gl, u, "u_devcurve_layer_bass_enabled", 1 if bool(getattr(s, "_devcurve_layer_bass_enabled", True)) else 0)
    _set1f(gl, u, "u_devcurve_layer_bass_alpha", float(getattr(s, "_devcurve_layer_bass_alpha", 0.55)) if bool(getattr(s, "_devcurve_layer_bass_enabled", True)) else 0.0)
    _upload_curve(gl, u, "u_devcurve_curve_bass", getattr(s, "_devcurve_curve_bass", None))

    _set_color4(gl, u, "u_devcurve_layer_vocals_color", getattr(s, "_devcurve_layer_vocals_color", None))
    _set_color4(gl, u, "u_devcurve_layer_vocals_outline_color", getattr(s, "_devcurve_layer_vocals_outline_color", None))
    _set1f(gl, u, "u_devcurve_layer_vocals_outline_width", float(getattr(s, "_devcurve_layer_vocals_outline_width", 0.006)))
    _set1i(gl, u, "u_devcurve_layer_vocals_enabled", 1 if bool(getattr(s, "_devcurve_layer_vocals_enabled", True)) else 0)
    _set1f(gl, u, "u_devcurve_layer_vocals_alpha", float(getattr(s, "_devcurve_layer_vocals_alpha", 0.42)) if bool(getattr(s, "_devcurve_layer_vocals_enabled", True)) else 0.0)
    _upload_curve(gl, u, "u_devcurve_curve_vocals", getattr(s, "_devcurve_curve_vocals", None))

    _set_color4(gl, u, "u_devcurve_layer_mids_color", getattr(s, "_devcurve_layer_mids_color", None))
    _set_color4(gl, u, "u_devcurve_layer_mids_outline_color", getattr(s, "_devcurve_layer_mids_outline_color", None))
    _set1f(gl, u, "u_devcurve_layer_mids_outline_width", float(getattr(s, "_devcurve_layer_mids_outline_width", 0.006)))
    _set1i(gl, u, "u_devcurve_layer_mids_enabled", 1 if bool(getattr(s, "_devcurve_layer_mids_enabled", True)) else 0)
    _set1f(gl, u, "u_devcurve_layer_mids_alpha", float(getattr(s, "_devcurve_layer_mids_alpha", 0.46)) if bool(getattr(s, "_devcurve_layer_mids_enabled", True)) else 0.0)
    _upload_curve(gl, u, "u_devcurve_curve_mids", getattr(s, "_devcurve_curve_mids", None))

    _set_color4(gl, u, "u_devcurve_layer_transients_color", getattr(s, "_devcurve_layer_transients_color", None))
    _set_color4(gl, u, "u_devcurve_layer_transients_outline_color", getattr(s, "_devcurve_layer_transients_outline_color", None))
    _set1f(gl, u, "u_devcurve_layer_transients_outline_width", float(getattr(s, "_devcurve_layer_transients_outline_width", 0.006)))
    _set1i(gl, u, "u_devcurve_layer_transients_enabled", 1 if bool(getattr(s, "_devcurve_layer_transients_enabled", True)) else 0)
    _set1f(gl, u, "u_devcurve_layer_transients_alpha", float(getattr(s, "_devcurve_layer_transients_alpha", 0.66)) if bool(getattr(s, "_devcurve_layer_transients_enabled", True)) else 0.0)
    _upload_curve(gl, u, "u_devcurve_curve_transients", getattr(s, "_devcurve_curve_transients", None))

    layer_names = ("bass", "vocals", "mids", "transients")
    layer_id = {name: idx for idx, name in enumerate(layer_names)}
    order_from_runtime = getattr(s, "_devcurve_draw_order", None)
    if isinstance(order_from_runtime, list) and len(order_from_runtime) == 4:
        ordered = [str(x).strip().lower() for x in order_from_runtime]
        if all(name in layer_id for name in ordered):
            final_order = ordered
        else:
            final_order = list(layer_names)
    else:
        ranked = []
        for idx, name in enumerate(layer_names):
            rank = int(getattr(s, f"_devcurve_layer_{name}_order", idx + 1))
            ranked.append((rank, idx, name))
        ranked.sort(key=lambda item: (item[0], item[1]))
        final_order = [name for (_rank, _idx, name) in ranked]
    _set1i(gl, u, "u_devcurve_order0", layer_id[final_order[0]])
    _set1i(gl, u, "u_devcurve_order1", layer_id[final_order[1]])
    _set1i(gl, u, "u_devcurve_order2", layer_id[final_order[2]])
    _set1i(gl, u, "u_devcurve_order3", layer_id[final_order[3]])
    _set1i(gl, u, "u_devcurve_foreground_layer_id", int(getattr(s, "_devcurve_foreground_layer_id", -1)))
    _set1i(
        gl,
        u,
        "u_devcurve_foreground_shadow_enabled",
        1 if bool(getattr(s, "_devcurve_foreground_shadow_enabled", False)) else 0,
    )
    _set1f(gl, u, "u_devcurve_foreground_shadow_alpha", float(getattr(s, "_devcurve_foreground_shadow_alpha", 0.36)))
    _set1f(gl, u, "u_devcurve_foreground_shadow_darken", float(getattr(s, "_devcurve_foreground_shadow_darken", 0.42)))
    _set1f(gl, u, "u_devcurve_foreground_shadow_offset", float(getattr(s, "_devcurve_foreground_shadow_offset", 0.10)))
    _set1i(
        gl,
        u,
        "u_devcurve_foreground_specular_enabled",
        1 if bool(getattr(s, "_devcurve_foreground_specular_enabled", False)) else 0,
    )
    _set1f(gl, u, "u_devcurve_foreground_specular_alpha", float(getattr(s, "_devcurve_foreground_specular_alpha", 0.78)))
    _set1f(gl, u, "u_devcurve_foreground_specular_width", float(getattr(s, "_devcurve_foreground_specular_width", 0.022)))
    _set1f(gl, u, "u_devcurve_foreground_specular_offset", float(getattr(s, "_devcurve_foreground_specular_offset", 0.028)))
    _set1f(gl, u, "u_devcurve_foreground_specular_crest_bias", float(getattr(s, "_devcurve_foreground_specular_crest_bias", 1.05)))
    _slot0 = getattr(s, "_devcurve_specular_slot0", [0.0, 0.0, 0.0])
    _slot1 = getattr(s, "_devcurve_specular_slot1", [0.0, 0.0, 0.0])
    _slot2 = getattr(s, "_devcurve_specular_slot2", [0.0, 0.0, 0.0])
    _loc0 = u.get("u_devcurve_specular_slot0", -1)
    if _loc0 >= 0:
        gl.glUniform4f(
            _loc0,
            float(_slot0[0] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 0 else 0.0),
            float(_slot0[1] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 1 else 0.0),
            float(_slot0[2] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 2 else 0.0),
            float(_slot0[3] if isinstance(_slot0, (list, tuple)) and len(_slot0) > 3 else 0.0),
        )
    _loc1 = u.get("u_devcurve_specular_slot1", -1)
    if _loc1 >= 0:
        gl.glUniform4f(
            _loc1,
            float(_slot1[0] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 0 else 0.0),
            float(_slot1[1] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 1 else 0.0),
            float(_slot1[2] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 2 else 0.0),
            float(_slot1[3] if isinstance(_slot1, (list, tuple)) and len(_slot1) > 3 else 0.0),
        )
    _loc2 = u.get("u_devcurve_specular_slot2", -1)
    if _loc2 >= 0:
        gl.glUniform4f(
            _loc2,
            float(_slot2[0] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 0 else 0.0),
            float(_slot2[1] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 1 else 0.0),
            float(_slot2[2] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 2 else 0.0),
            float(_slot2[3] if isinstance(_slot2, (list, tuple)) and len(_slot2) > 3 else 0.0),
        )
    return True
