"""N1.6: an OpenGL program's sources rewritten into Vulkan GLSL (``rendering.gl_programs.portable``), and the blocks
an owner packs from a shader's own declaration."""
import struct

import pytest

from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block, portable_program
from rendering.gl_programs.scene3d import SCENE3D_PASS_BLOCK_BINDING, Scene3DBlockLayout
from tools.vulkan_shader_readiness import _qsb, compile_source

_VERTEX = """#version 460 core
layout(location = 0) in vec2 aPosition;
uniform mat4 uMatrix;
uniform vec2 uItemSize;
out vec2 vUv;
flat out int vIndex;
void main() {
    vUv = aPosition;
    vIndex = gl_InstanceID + gl_VertexID;
    gl_Position = uMatrix * vec4(aPosition * uItemSize, 0.0, 1.0);
}
"""
_FRAGMENT = """#version 460 core
const int STOPS=3;
flat in int vIndex;
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uImage;   // a sampler with a unit, not a block member
uniform vec4 uStops[STOPS]; // an array sized by a constant
uniform float uGain;
void main() { FragColor = texture(uImage, vUv) * uGain + uStops[vIndex % STOPS]; }
"""


def _require_qsb():
    if not _qsb().exists():
        pytest.skip("this PySide6 has no qsb")


def test_an_opengl_program_becomes_one_that_bakes_for_every_target(tmp_path):
    _require_qsb()
    # Negative control: the OpenGL sources as authored do not bake.
    assert not compile_source(_qsb(), _VERTEX, tmp_path / "gl.vert")[0]
    assert not compile_source(_qsb(), _FRAGMENT, tmp_path / "gl.frag")[0]
    vertex, (fragment,), layout = portable_program(_VERTEX, (_FRAGMENT,), block="Probe", samplers={"uImage": 3})
    assert compile_source(_qsb(), vertex, tmp_path / "v.vert")[0]
    assert compile_source(_qsb(), fragment, tmp_path / "f.frag")[0]
    # One block, every loose uniform of both stages, in first-seen order; the same declaration in both stages.
    assert [name for name, _ in layout.fields] == ["uMatrix", "uItemSize", "uStops", "uGain"]
    assert dict(layout.fields)["uStops"] == "vec4[3]"
    declaration = block_declaration(fragment, "Probe")
    assert declaration in vertex and f"binding = {SCENE3D_PASS_BLOCK_BINDING}" in declaration
    assert block_layout_from_glsl(declaration) == layout
    # Varyings matched by location, the sampler bound to its unit, the indices through the macro.
    assert "layout(location = 0) out vec2 vUv" in vertex and "layout(location = 1) flat out int vIndex" in vertex
    assert "layout(location = 0) in vec2 vUv" in fragment and "layout(location = 1) flat in int vIndex" in fragment
    assert "layout(binding = 3) uniform sampler2D uImage" in fragment
    assert "vIndex = srpssInstanceIndex + srpssVertexIndex;" in vertex


def test_declarations_sharing_a_line_are_each_rewritten(tmp_path):
    # Several transitions declare ``uniform mat4 uMatrix; uniform vec2 uItemSize;`` and ``out vec2 a; out vec2 b;`` on
    # one line: every one of them is a declaration (control: a rewrite that read only line starts left the second
    # loose, which does not bake).
    _require_qsb()
    vertex = ("#version 460 core\nlayout(location = 0) in vec2 aPosition;\n"
              "uniform mat4 uMatrix; uniform vec2 uItemSize;\nout vec2 vUv; out vec2 vFace;\n"
              "void main() { vUv = aPosition; vFace = aPosition * uItemSize;"
              " gl_Position = uMatrix * vec4(aPosition, 0.0, 1.0); }\n")
    fragment = ("#version 460 core\nin vec2 vUv; in vec2 vFace;\nout vec4 FragColor;\n"
                "uniform sampler2D uImage; uniform float uGain;\n"
                "void main() { FragColor = texture(uImage, vUv + vFace) * uGain; }\n")
    vertex, (fragment,), layout = portable_program(vertex, (fragment,), block="Line", samplers={"uImage": 0})
    assert [name for name, _ in layout.fields] == ["uMatrix", "uItemSize", "uGain"]
    assert "layout(location = 1) out vec2 vFace" in vertex and "layout(location = 1) in vec2 vFace" in fragment
    assert compile_source(_qsb(), vertex, tmp_path / "v.vert")[0]
    assert compile_source(_qsb(), fragment, tmp_path / "f.frag")[0]


def test_declarations_of_several_names_are_split_and_each_rewritten(tmp_path):
    # Crumble declares ``uniform float uProgress,uDepth;`` and ``out vec2 vUv,vCrack;``: each name is one declaration
    # (control: a rewrite that read only single names left them loose and unlocated, which does not bake).
    _require_qsb()
    vertex = ("#version 460 core\nlayout(location=0) in vec2 aUv;\n"
              "uniform mat4 uMatrix; uniform float uProgress,uDepth; uniform sampler2D uMotion;\n"
              "out vec2 vUv,vCrack; flat out float vPhase,vSide;\n"
              "vec3 turn(vec3 p,vec3 a,float t){float c=cos(t),s=sin(t);return p*c+cross(a,p)*s;}\n"
              "void main(){vUv=aUv;vCrack=aUv*uDepth;vPhase=uProgress;vSide=texelFetch(uMotion,ivec2(0),0).x;"
              "gl_Position=uMatrix*vec4(turn(vec3(aUv,0.),vec3(0.,0.,1.),uProgress),1.);}\n")
    fragment = ("#version 460 core\nin vec2 vUv,vCrack;\nflat in float vPhase,vSide;\nout vec4 FragColor;\n"
                "uniform float uProgress,uSeed;\n"
                "void main(){FragColor=vec4(vUv+vCrack,vPhase*vSide,uProgress+uSeed);}\n")
    vertex, (fragment,), layout = portable_program(vertex, (fragment,), block="Lists", samplers={"uMotion": 1})
    assert [name for name, _ in layout.fields] == ["uMatrix", "uProgress", "uDepth", "uSeed"]
    assert "layout(location = 1) out vec2 vCrack" in vertex and "layout(location = 3) flat out float vSide" in vertex
    assert "layout(location = 1) in vec2 vCrack" in fragment and "layout(location = 3) flat in float vSide" in fragment
    assert "float c=cos(t),s=sin(t);" in vertex           # a local list is not a declaration
    assert compile_source(_qsb(), vertex, tmp_path / "v.vert")[0]
    assert compile_source(_qsb(), fragment, tmp_path / "f.frag")[0]


def test_a_sampler_without_a_binding_in_the_plan_is_refused():
    with pytest.raises(ValueError, match="uImage"):
        portable_program(_VERTEX, (_FRAGMENT,), block="Probe", samplers={})


def test_the_block_packs_the_values_a_program_set_and_zero_for_the_rest():
    layout = Scene3DBlockLayout.of("Probe", (("uGain", "float"), ("uStops", "vec4[2]"), ("uCount", "int")))
    flat = pack_block(layout, {"uGain": 2.0, "uStops": (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0), "ignored": 9})
    nested = pack_block(layout, {"uGain": 2.0, "uStops": ((1.0, 2.0, 3.0, 4.0), (5.0, 6.0, 7.0, 8.0))})
    assert flat == nested
    assert struct.unpack_from("<f", flat, 0)[0] == 2.0
    assert struct.unpack_from("<4f", flat, layout.offsets[1] + 16) == (5.0, 6.0, 7.0, 8.0)
    assert struct.unpack_from("<i", pack_block(layout, {}), layout.offsets[2])[0] == 0
    # An array already in std140 form (Jigsaw's pieces: float32 vec4s) packs as given, every element; a short one is
    # refused rather than packed partly.
    stops = struct.pack("<8f", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    assert pack_block(layout, {"uGain": 2.0, "uStops": stops}) == flat
    with pytest.raises(ValueError, match="vec4"):
        pack_block(layout, {"uStops": stops[:16]})


def test_bool_and_uvec4_members_pack_as_32_bit_integers():
    # Bubble's block holds a uvec4 of class bits and two bools (N1.6); a member never set packs as integer zero.
    layout = Scene3DBlockLayout.of("Probe", (("uOn", "bool"), ("uBits", "uvec4"), ("uAlso", "bool")))
    assert layout.offsets == (0, 16, 32) and layout.size == 48
    data = pack_block(layout, {"uOn": 1, "uBits": (0xFFFFFFFF, 1, 2, 3)})
    assert struct.unpack_from("<i4Ii", data, 0)[0] == 1
    assert struct.unpack_from("<4I", data, 16) == (0xFFFFFFFF, 1, 2, 3)
    assert struct.unpack_from("<i", data, 32)[0] == 0
    assert pack_block(layout, {}) == bytes(48)
    assert "bool uOn;" in layout.glsl(18) and "uvec4 uBits;" in layout.glsl(18)


def test_a_family_sharing_stages_declares_one_block_over_every_stage():
    # Extruded Bubble's fullscreen vertex is drawn with three fragments and one fragment with two vertex stages
    # (N1.6): each shared stage converts once, and every stage of the family declares the one union block.
    from rendering.gl_programs.portable import portable_family

    vertex = "#version 460 core\nuniform vec2 uShift;\nout vec2 vNdc;\nvoid main(){vNdc=uShift;gl_Position=vec4(0.0);}\n"
    other = "#version 460 core\nuniform float uScale;\nout vec2 vNdc;\nvoid main(){vNdc=vec2(uScale);gl_Position=vec4(0.0);}\n"
    fragment_a = "#version 460 core\nin vec2 vNdc;\nout vec4 c;\nuniform float uA;\nvoid main(){c=vec4(vNdc,uA,1.0);}\n"
    fragment_b = ("#version 460 core\nin vec2 vNdc;\nout vec4 c;\nuniform sampler2D uImage;\nuniform vec3 uB;\n"
                  "void main(){c=texture(uImage,vNdc)*vec4(uB,1.0);}\n")
    converted, layout = portable_family({"v": vertex, "w": other, "a": fragment_a, "b": fragment_b},
                                        (("v", ("a",)), ("v", ("b",)), ("w", ("a",))), block="Family",
                                        samplers={"uImage": 3})
    assert [name for name, _kind in layout.fields] == ["uShift", "uA", "uB", "uScale"]
    declaration = layout.glsl(SCENE3D_PASS_BLOCK_BINDING)
    assert all(declaration in text and "uniform float" not in text for text in converted.values())
    assert "layout(binding = 3) uniform sampler2D uImage;" in converted["b"]
    # A shared fragment whose vertex stages place their outputs differently cannot convert once: refused.
    moved = "#version 460 core\nout vec3 vExtra;\nout vec2 vNdc;\nvoid main(){vExtra=vec3(0.0);vNdc=vec2(0.0);}\n"
    with pytest.raises(ValueError, match="converts differently"):
        portable_family({"v": vertex, "m": moved, "a": fragment_a}, (("v", ("a",)), ("m", ("a",))), block="Family",
                        samplers={})


def test_mat3_members_pack_as_three_padded_columns():
    # Extruded Bubble's rotations and the probe's six face rotations are mat3 (N1.6): std140 aligns each column as a
    # vec4, so nine column-major values take 48 bytes; a mat3 array strides 48; a member never set packs as zeros.
    layout = Scene3DBlockLayout.of("Probe", (("uA", "float"), ("uM", "mat3"), ("uFaces", "mat3[2]"), ("uB", "float")))
    assert layout.offsets == (0, 16, 64, 160) and layout.size == 176
    rotation = tuple(float(v) for v in range(1, 10))
    data = pack_block(layout, {"uM": rotation, "uFaces": (rotation, tuple(-v for v in rotation)), "uB": 2.0})
    for column in range(3):
        assert struct.unpack_from("<3f", data, 16 + 16 * column) == rotation[3 * column:3 * column + 3]
        assert struct.unpack_from("<f", data, 16 + 16 * column + 12) == (0.0,)
        assert struct.unpack_from("<3f", data, 64 + 48 + 16 * column) == tuple(-v for v in rotation[3 * column:3 * column + 3])
    assert struct.unpack_from("<f", data, 160) == (2.0,)
    assert pack_block(layout, {}) == bytes(176)
    assert "mat3 uM;" in layout.glsl(18) and "mat3 uFaces[2];" in layout.glsl(18)


@pytest.mark.parametrize(("mode", "block"), (("bubble", "BubbleDraw"), ("devcurve", "DevCurveDraw")))
def test_the_2d_modes_draw_one_block_declared_once_in_their_shader(mode, block):
    import importlib

    from widgets.spotify_visualizer.shaders import load_fragment_shader

    module = importlib.import_module(f"rendering.quick.visualizer.implementations.{mode}")
    prefix = mode.upper()
    fragment = load_fragment_shader(mode)
    declaration = block_declaration(fragment, block)
    assert declaration in getattr(module, f"{prefix}_VERTEX_SOURCE")
    assert getattr(module, f"{prefix}_BLOCK") == block_layout_from_glsl(declaration)
    loose = [line for line in fragment.splitlines()
             if line.startswith("uniform ") and not line.startswith(f"uniform {block}")]
    assert not loose
    assert "uniform mat4 uMatrix" not in getattr(module, f"{prefix}_VERTEX_SOURCE")


def test_spectrum_draws_one_block_declared_once_in_its_shader():
    from rendering.quick.visualizer.implementations import spectrum
    from widgets.spotify_visualizer.shaders import load_fragment_shader

    fragment = load_fragment_shader("spectrum")
    declaration = block_declaration(fragment, "SpectrumDraw")
    assert declaration in spectrum.SPECTRUM_VERTEX_SOURCE
    assert spectrum.SPECTRUM_BLOCK == block_layout_from_glsl(declaration)
    assert "\nuniform " not in fragment.replace("\nuniform SpectrumDraw", "")
