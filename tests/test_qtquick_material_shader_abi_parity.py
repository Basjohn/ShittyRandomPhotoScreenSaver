"""Protect the Qt Quick ShaderEffect cross-stage ABI (R-240 material audit).

Qt's qsb packs compile vertex and fragment stages independently. A successful
`regen_qrc.py --shaders --check` does not validate the matching layout across
those packs. Requiring identical std140 block signatures prevents new material
uniforms from quietly changing the fragment stage alone. This regression was
caught after multi-widget surfaces became invalid after startup reveal.

Import-free: runs without Qt and before any actual rendering acceptance tests.
"""

from __future__ import annotations

import re
from pathlib import Path


SHADERS = Path(__file__).resolve().parents[1] / "rendering/quick/qml/shaders"
QML = SHADERS.parent / "MaterialSurface.qml"


def _uniform_block_signature(source: str) -> tuple[tuple[str, str], ...]:
    match = re.search(
        r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*0\s*\)"
        r"\s*uniform\s+buf\s*\{([^}]+)\}", source, re.S,
    )
    assert match is not None, "ShaderEffect requires the std140 uniform buf at binding 0"
    content = re.sub(r"//[^\n]*", "", match.group(1))
    members = re.findall(r"\b(mat4|float|vec2|vec3|vec4|int|uint)\s+(\w+)\s*;", content)
    assert members, "ShaderEffect uniform block is empty"
    return tuple(members)


def test_all_paired_qt_shader_stages_have_identical_uniform_layouts():
    pairs = sorted((v, v.with_suffix(".frag")) for v in SHADERS.rglob("*.vert")
                   if v.with_suffix(".frag").exists())
    checked = 0
    for vertex, fragment in pairs:
        vsource = vertex.read_text(encoding="utf-8")
        fsource = fragment.read_text(encoding="utf-8")
        if "uniform buf" not in vsource or "uniform buf" not in fsource:
            continue
        vertex_sig = _uniform_block_signature(vsource)
        fragment_sig = _uniform_block_signature(fsource)
        assert vertex_sig == fragment_sig, (
            f"QSB cross-stage uniform layout mismatch: {vertex.name} vs {fragment.name}\n"
            f"vertex={vertex_sig!r}\nfragment={fragment_sig!r}"
        )
        checked += 1
    assert checked >= 2, "Expected the material and text-legibility shader pairs"


def test_surface_material_qml_supplies_all_custom_shader_uniforms():
    fragment = _uniform_block_signature((SHADERS / "surface_material.frag").read_text(encoding="utf-8"))
    qml = QML.read_text(encoding="utf-8")
    for glsl_type, name in fragment:
        if name in {"qt_Matrix", "qt_Opacity"}:
            continue
        qml_type = {"float": "real", "vec2": "vector2d", "vec4": "vector4d"}.get(glsl_type)
        assert qml_type is not None, f"Unexpected custom uniform type: {glsl_type} {name}"
        accepted_types = (qml_type, "color") if glsl_type == "vec4" else (qml_type,)
        assert any(re.search(
            rf"\b(?:readonly\s+)?property\s+{kind}\s+{re.escape(name)}\b", qml,
        ) for kind in accepted_types), (
            f"MaterialSurface.qml must expose {name} as one of {accepted_types}"
        )
