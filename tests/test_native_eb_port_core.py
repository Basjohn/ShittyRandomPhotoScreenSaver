"""N5.6, Extruded Bubble's core C++ boxes (ABI 42), GPU-free (``native/core/src/abi.h`` 42).

Box 1, the scene probe (``scene_targets.h`` cube targets, ``cube_prefilter.h``): Python's ``SceneProbe``
(``rendering/quick/scene3d/probe.py``) is the oracle for the faces' order and orientation, the prefilter's filter and
its cone. Each test's negative control is a mutated form of the source, seen failing. The drawn proofs (every face and
level read back against Python's capture on both backends, a lookup across a face edge) run on the built module.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"
SHADERS = ROOT / "native" / "core" / "shaders"


def _source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def _function(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


def _probe_prefilter_body() -> str:
    """probe.py's prefilter fragment as authored (before portable_program rewrites it), from ``vec3 helper`` on."""
    text = (ROOT / "rendering" / "quick" / "scene3d" / "probe.py").read_text(encoding="utf-8")
    fragment = text[text.index('_PREFILTER_FRAGMENT = """'):]
    fragment = fragment[:fragment.index('"""\n', len('_PREFILTER_FRAGMENT = """'))]
    return fragment[fragment.index("    vec3 helper"):fragment.rindex("}")]


# ------------------------------------------------------------------------------------------ box 1: the prefilter

def prefilter_is_probes(frag: str, probe_body: str) -> bool:
    """The core's prefilter filters as probe.py's: the same body from the cone's frame to the stored level, its axis
    from the face's rotation over an NDC that reads OpenGL's rows (fragPixel's memory row 0 at NDC -1), no gl_Layer."""
    if "gl_Layer =" in frag or "layout(triangles" in frag:
        return False
    body = frag[frag.index("    vec3 helper"):frag.rindex("}")]
    return (body == probe_body
            and "vec2 fNdc = fragPixel(vec2(uSide)) / uSide * 2.0 - 1.0;" in frag
            and "vec3 axis = transpose(mat3(uWorldToFace[uFace])) * normalize(vec3(fNdc, -1.0));" in frag
            and "uniform samplerCube uSource;" in frag)


def test_the_prefilter_is_probe_pys_filter_tap_for_tap():
    frag = (SHADERS / "cube_prefilter.frag").read_text(encoding="utf-8")
    probe_body = _probe_prefilter_body()
    assert prefilter_is_probes(frag, probe_body)
    # Negative controls: fewer taps, a mirrored row order, a layered geometry-shader form.
    assert not prefilter_is_probes(frag.replace("i < 32", "i < 16").replace("/ 32.0", "/ 16.0"), probe_body)
    assert not prefilter_is_probes(frag.replace("/ uSide * 2.0 - 1.0;", "/ uSide * -2.0 + 1.0;"), probe_body)
    assert not prefilter_is_probes(frag + "\n// gl_Layer = face;\n", probe_body)


def _core_faces(cpp: str):
    table = cpp[cpp.index("constexpr double kFaces[kCubeFaces][2][3] = {"):]
    table = table[:table.index("};")]
    numbers = [float(v) for v in re.findall(r"-?\d+\.\d+", table)]
    return [((numbers[6 * f:6 * f + 3]), (numbers[6 * f + 3:6 * f + 6])) for f in range(6)]


def _rotation(forward, up):
    right = (forward[1] * up[2] - forward[2] * up[1], forward[2] * up[0] - forward[0] * up[2],
             forward[0] * up[1] - forward[1] * up[0])
    return (*right, *up, *(-v for v in forward))


def faces_match_probe(cpp: str) -> bool:
    from rendering.quick.scene3d.probe import scene3d_probe_face_rotation
    faces = _core_faces(cpp)
    return len(faces) == 6 and all(
        tuple(_rotation(*faces[f])) == tuple(scene3d_probe_face_rotation(f)) for f in range(6))


def test_the_faces_are_opengls_cube_map_order_and_probe_pys_rotations():
    cpp = _source("cube_prefilter.cpp")
    assert faces_match_probe(cpp)
    # The block holds GLSL's mat3 as the row-major rotation (probe.py's _FACE_COLUMNS).
    assert "rotations[f * 16 + column * 4 + row] = float(r[3 * row + column]);" in cpp
    # Negative control: +X and -X swapped.
    swapped = cpp.replace("{ { 1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },\n    { { -1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },",
                          "{ { -1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },\n    { { 1.0, 0.0, 0.0 }, { 0.0, -1.0, 0.0 } },")
    assert swapped != cpp and not faces_match_probe(swapped)


def test_the_cone_and_the_level_read_are_probe_pys():
    cpp = _source("cube_prefilter.cpp")
    assert "return qMin(2.2 * (kPi / 2.0) / double(levelSide), kPi / 2.0);" in cpp
    assert "const float sourceLod = float(level - 1);" in cpp

    def core_cone(side, level):                 # cubePrefilterCone, line for line
        return min(2.2 * (math.pi / 2.0) / max(1, side >> level), math.pi / 2.0)

    for size in (256, 128, 64):                 # the probe's face sizes by tier (eb.py)
        for level in range(1, int(math.log2(size)) + 1):
            side = max(size >> level, 1)
            assert core_cone(size, level) == min(2.2 * (math.pi / 2.0) / side, math.pi / 2.0)


# ------------------------------------------------------------------------------------------ box 1: the cube target

def cube_target_is_wired(targets_h: str, targets_cpp: str, prefilter_cpp: str) -> bool:
    """One RGBA16F cube (CubeMap | MipMapped), a render target per face over level 0 (setLayer), a stage cube per level
    the prefilter draws and copies from, every face and level read back; never generateMips."""
    step = _function(targets_cpp, "bool SceneTargets::step(", "QRhiTexture *SceneTargets::sampledTexture(")
    return ("flags |= QRhiTexture::CubeMap | QRhiTexture::MipMapped;" in step
            and "attachment.setLayer(f);\n                    attachment.setLevel(0);" in step and "t.faceTarget[f]->setRenderPassDescriptor(t.renderPass.get());" in step
            and "QRhiTexture::CubeMap | QRhiTexture::RenderTarget" in step
            and "generateMips" not in prefilter_cpp
            and "description.setDestinationLevel(level);" in prefilter_cpp
            and "copy->copyTexture(t.colour[0].get(), t.stage[level].get(), description);" in prefilter_cpp
            and "description.setLayer(texture.layer);" in targets_cpp
            and "RhiOwned<QRhiTextureRenderTarget> faceTarget[kCubeFaces];" in targets_h)


def test_a_cube_target_is_six_face_targets_and_a_prefiltered_chain():
    h, cpp, pre = _source("scene_targets.h"), _source("scene_targets.cpp"), _source("cube_prefilter.cpp")
    assert cube_target_is_wired(h, cpp, pre)
    # Negative controls: QRhi's generateMips for the chain; the faces drawn into one layer.
    assert not cube_target_is_wired(h, cpp, pre.replace("cb->resourceUpdate(copy);",
                                                        "copy->generateMips(t.colour[0].get());\n        cb->resourceUpdate(copy);"))
    assert not cube_target_is_wired(h, cpp.replace("attachment.setLayer(f);\n                    attachment.setLevel(0);",
                                                   "attachment.setLevel(0);"), pre)


def cube_declaration_rules(targets_cpp: str) -> bool:
    parse = _function(targets_cpp, "bool parseTargetDeclaration(", "int bucketPixels(")
    return ("d.size.width() != d.size.height()" in parse and "d.colour.at(0).format != TargetFormat::RGBA16F" in parse
            and "d.samples != 1" in parse and "d.mips" in parse and "d.exact = true;" in parse
            and 'QStringLiteral("cube") };' in parse)


def test_a_cube_is_square_rgba16f_single_sampled_and_exact():
    cpp = _source("scene_targets.cpp")
    assert cube_declaration_rules(cpp)
    assert not cube_declaration_rules(cpp.replace("d.size.width() != d.size.height() || ", ""))


def cube_passes_are_wired(mode_cpp: str) -> bool:
    """A run on a cube is one face's passes into that face's target, cleared per face, over the rows-up triangle; the
    prefilter step runs outside any run; a vertex stage's uMatrix gains the cube's Y flip."""
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    return ("&& program.passes.at(last + 1).face == pass.face)" in passes
            and "cube ? t.faceRenderTarget(pass.face) : t.renderTarget.get()" in passes
            and "cleared[runTarget] = false;" in passes
            and "cube ? cubeInput : t.decl.surfaceSized() ? sceneInput : ownInput" in passes
            and "m_cubePrefilter.record(rhi, cb, *cube, &pending, &prefilterError)" in passes
            and "cubeCorrection[c] = (c % 4 == 1) ? -clipCorrection[c] : clipCorrection[c];" in mode_cpp
            and "o[3] = 1.0f - in[3];" in mode_cpp and "o[5] = 1.0f - in[5];" in mode_cpp)


def test_a_cube_face_run_draws_its_face_rows_up_and_is_cleared():
    cpp = _source("mode_content.cpp")
    assert cube_passes_are_wired(cpp)
    # Negative controls: the faces merged into one run; the face drawn in the core's own rows (no flip).
    assert not cube_passes_are_wired(cpp.replace("\n               && program.passes.at(last + 1).face == pass.face)",
                                                 ")"))
    assert not cube_passes_are_wired(cpp.replace("o[3] = 1.0f - in[3];", "o[3] = in[3];"))


def test_the_rows_up_triangle_puts_uv_zero_at_the_faces_bottom_row():
    # cubeTriangle, line for line, over the own triangle's uv: a vertex at the target's top row (vUv.y 1, v_uv.y 0)
    # lands at the face's bottom-row uv (vUv.y 0, v_uv.y 1); the map stays affine (the triangle's far corners too).
    own = [(-1.0, -1.0, 0.0, 1.0, 0.0, 0.0), (3.0, -1.0, 2.0, 1.0, 2.0, 0.0), (-1.0, 3.0, 0.0, -1.0, 0.0, 2.0)]
    flipped = [(x, y, u, 1.0 - v, s, 1.0 - t) for x, y, u, v, s, t in own]
    for (x, y, u, v, s, t), (_, _, fu, fv, fs, ft) in zip(own, flipped):
        assert fu == u and fs == s and fv + v == 1.0 and ft + t == 1.0


def test_a_face_pass_and_the_prefilter_are_checked_at_the_parse():
    cpp = _source("mode_content.cpp")
    assert 'QStringLiteral("face") };   // ABI 42' in cpp
    assert "a pass into a cube target declares its \\\"face\\\" (0 to 5)" in cpp
    assert "each of its six faces is drawn by a pass, then one prefilter step" in cpp
    assert "a transparency, mipped or cube target has no capture" in cpp
    assert "type == QShaderDescription::SamplerCube ? kCubeSamplerDimensions" in cpp
    assert "|| prefilter;                     // ABI 42" in _source("mode_content.h")


def test_the_abi_is_42_and_the_loader_speaks_it():
    from rendering.native import loader
    assert "#define SRPSS_NATIVE_CORE_ABI 42" in _source("abi.h")
    assert loader.EXPECTED_ABI == 42
    assert "src/cube_prefilter.cpp" in (ROOT / "native" / "core" / "CMakeLists.txt").read_text(encoding="utf-8")
