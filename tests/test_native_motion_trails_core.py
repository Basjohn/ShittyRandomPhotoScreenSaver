"""N4.i (motion blur and trails) for N5.2d, the core's ABI 37 additions, GPU-free (``native/core/src/abi.h`` 37).

The motion blur and the trails are data on the core (``Current_Plan.md`` N5.2d's design): the velocity two R16F
attachments of the scene target, the tile max a compute entry over them into a storage image, the gather a pass into a
second target the composite reads, the ghosts passes into an R8 target and their edges a pass onto the scene. What the
core lacked, each additive (no earlier program declares it):

- a compute entry triggered by ``"draw"`` (every record that draws the passes), the one trigger a still admits (the
  background layer's scene transitions are stills: a still drew no compute at ABI 36);
- the target format ``"r8"`` (the ghost buffer, Python's GL_R8);
- an attachment a pass masks (``"write": false``) left unwritten by its shader (the passes that do not move);
- a setting scoped to one pass (``"<member>@<pass>"``: one ghost a pass, from one pack);
- a pass's ``"viewport": "allocation"`` (the trails' edges over the whole allocation, as Python draws them);
- an RGBA32F item texture (Crumble's motion table) and 16 attributes a mesh layout (Glass Shatter's shards).

Each source check has its negative control: the ABI 36 form of the same text, seen failing here. The drawn proofs are
``transition_route_check.py``'s rounds on the built module.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"


def _source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def _function(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


# ------------------------------------------------------------------------------------------- the draw trigger

def draw_trigger_wired(compute_cpp: str, mode_cpp: str) -> bool:
    """"draw" parses to Kind::Draw and prints back; such an entry is due at every record that draws (decideDispatches
    runs only for one), its trigger rising; a still admits compute only when every entry is triggered by "draw"."""
    parse = _function(compute_cpp, "bool parseComputeTrigger(", "// ----")
    printed = _function(compute_cpp, "QJsonValue ComputeTrigger::toJson()", "bool parseComputeTrigger(")
    decide = _function(mode_cpp, "void ModeContent::decideDispatches()", "quint64 ModeContent::entryFreshKey(")
    admit = _function(mode_cpp, "bool ModeSource::admit(", "bool ModeSource::acceptStream(")
    only = _function(mode_cpp, "bool ModeProgram::computeOnDrawOnly() const", "void ModeProgram::passTargetSizes(")
    return ('value.toString() == QLatin1String("draw")' in parse and "ComputeTrigger::Kind::Draw" in parse
            and 'return QStringLiteral("draw");' in printed
            and "const bool drawn = pass.trigger.kind == ComputeTrigger::Kind::Draw;" in decide
            and "const bool due = drawn || " in decide
            and "program.hasCompute() && !program.computeOnDrawOnly()" in admit
            and "pass.trigger.kind != ComputeTrigger::Kind::Draw" in only)


def test_a_draw_trigger_dispatches_at_every_drawn_record_and_is_a_stills_compute():
    compute_cpp, mode_cpp = _source("compute_passes.cpp"), _source("mode_content.cpp")
    assert draw_trigger_wired(compute_cpp, mode_cpp)
    assert "enum class Kind { Frame = 0, Field = 1, Draw = 2" in _source("compute_passes.h")   # ABI 42 adds Once = 3
    # Negative controls: the ABI 36 forms (no "draw" in the parse; a draw entry due only on new work; a still refusing
    # every compute entry) each fail.
    assert not draw_trigger_wired(compute_cpp.replace('value.toString() == QLatin1String("draw")',
                                                      'value.toString() == QLatin1String("never")'), mode_cpp)
    assert not draw_trigger_wired(compute_cpp, mode_cpp.replace("const bool due = drawn || ", "const bool due = "))
    assert not draw_trigger_wired(compute_cpp, mode_cpp.replace("program.hasCompute() && !program.computeOnDrawOnly()",
                                                                "program.hasCompute()"))


def test_the_face_declares_the_draw_trigger():
    from rendering.native.mode import COMPUTE_TRIGGERS, ComputePass

    assert "draw" in COMPUTE_TRIGGERS
    assert ComputePass("tiles", b"", groups=(1, 1, 1), trigger="draw").declaration()["trigger"] == "draw"
    # Control: a field's name is still declared as a field (the face's other form).
    assert ComputePass("tiles", b"", groups=(1, 1, 1), trigger="beat").declaration()["trigger"] == {"field": "beat"}


# ------------------------------------------------------------------------------------------- the R8 target format

def _core_target_formats(scene_cpp: str) -> list[str]:
    names = re.search(r"const char \*const kFormatNames\[\] = \{([^}]*)\};", scene_cpp).group(1)
    return re.findall(r'"(\w+)"', names)


def _enum_order(header: str) -> list[str]:
    body = re.search(r"enum class TargetFormat \{([^}]*)\};", header).group(1)
    return [name.strip().split("=")[0].strip().lower() for name in body.split(",")]


def test_r8_is_a_target_format_of_the_core_and_the_face_in_one_order():
    from rendering.native.mode import TARGET_FORMATS, TargetAttachment

    scene_cpp, header = _source("scene_targets.cpp"), _source("scene_targets.h")
    assert _core_target_formats(scene_cpp) == list(TARGET_FORMATS) == _enum_order(header)
    assert "case TargetFormat::R8:\n        return QRhiTexture::R8;" in scene_cpp
    assert "case QRhiTexture::R8:\n        return 1;" in scene_cpp
    assert TargetAttachment("ghost", "r8").declaration() == {"name": "ghost", "format": "r8"}
    # Negative control: the ABI 36 list has no r8, so the face's list is not the core's.
    old = scene_cpp.replace('"r32f", "r8" }', '"r32f" }')
    assert _core_target_formats(old) != list(TARGET_FORMATS)


# ------------------------------------------------------------------------------------------- masked attachments

def masked_outputs_admitted(mode_cpp: str) -> bool:
    check = _function(mode_cpp, "bool checkPassOutputs(ModePass &pass", "pass.fragDepth = false;")
    return ("const bool masked = i < int(pass.outputs.size()) && !pass.outputs.at(i).write;" in check
            and "if (!seen[i] && !masked) {" in check)


def test_a_masked_attachment_may_be_left_unwritten_and_its_mask_is_empty():
    mode_cpp = _source("mode_content.cpp")
    assert masked_outputs_admitted(mode_cpp)
    # The masked attachment's pipeline state writes nothing (outputBlend), so the unwritten output reaches nothing.
    blend = _function(mode_cpp, "QRhiGraphicsPipeline::TargetBlend outputBlend(", "bool sameBlendState(")
    assert "b.colorWrite = QRhiGraphicsPipeline::ColorMask();" in blend
    # Negative control: the ABI 36 check (every attachment written) fails.
    assert not masked_outputs_admitted(mode_cpp.replace("if (!seen[i] && !masked) {", "if (!seen[i]) {"))


# ------------------------------------------------------------------------------------------- scoped settings

def scoped_settings_wired(mode_cpp: str) -> bool:
    check = _function(mode_cpp, "bool ModeProgram::check(", "bool ModeProgram::packSettings(")
    pack = _function(mode_cpp, "bool ModeProgram::packSettings(", "bool ModeProgram::packFrame(")
    return ("const qsizetype at = name.indexOf('@');" in check and "name = member;" in check
            and "member.name + '@' + pass.name" in check
            and "for (int scopedRound = 0; scopedRound < 2; ++scopedRound) {" in pack
            and "(at < 0 || passes.at(i).name == scope)" in pack)


def test_a_setting_scoped_to_one_pass_fills_that_pass_over_the_unscoped_one():
    mode_cpp = _source("mode_content.cpp")
    assert scoped_settings_wired(mode_cpp)
    # A pass name and a member name are identifiers, so the scope's '@' is never part of either (passName).
    assert "c == '_'" in _function(_source("scene_targets.cpp"), "bool identifier(", "int textureBytesPerSample(")
    # Negative controls: the ABI 36 packing (every key fills every pass declaring it) and check (no scope) fail.
    flat = mode_cpp.replace("(at < 0 || passes.at(i).name == scope)", "true")
    assert not scoped_settings_wired(flat)
    assert not scoped_settings_wired(mode_cpp.replace("const qsizetype at = name.indexOf('@');", ""))


# ------------------------------------------------------------------------------------------- the allocation viewport

def allocation_viewport_wired(mode_cpp: str) -> bool:
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    parse = _function(mode_cpp, "bool ModeProgram::fromJson(", "QJsonObject ModeProgram::toJson(")
    return ("if (program.passes.at(k).allocationViewport)" in passes
            and "drawPass(rhi, cb, k, whole, ownInput, whole);" in passes
            and 'QStringLiteral("viewport") }; // ABI 37' in parse and "pass.allocationViewport = allocation;" in parse)


def test_a_pass_may_draw_over_its_targets_whole_allocation():
    from rendering.native.mode import PASS_VIEWPORTS, ModePass, PassGeometry

    assert allocation_viewport_wired(_source("mode_content.cpp"))
    assert PASS_VIEWPORTS == ("content", "allocation")
    edges = ModePass("trail_edges", b"", "alpha", target="scene", viewport="allocation")
    assert edges.declaration()["viewport"] == "allocation"
    assert "viewport" not in ModePass("slab", b"", "replace", target="scene").declaration()   # the default: unchanged
    # The face refuses what the core refuses: no target, or a pass with its own vertex stage.
    with pytest.raises(ValueError, match="allocation viewport"):
        ModePass("edges", b"", "alpha", viewport="allocation")
    with pytest.raises(ValueError, match="allocation viewport"):
        ModePass("edges", b"", "alpha", target="scene", viewport="allocation", geometry=PassGeometry(b""))
    with pytest.raises(ValueError, match="unknown viewport"):
        ModePass("edges", b"", "alpha", target="scene", viewport="window")
    # Negative control: the ABI 36 run loop (every pass over the content viewport) fails.
    assert not allocation_viewport_wired(_source("mode_content.cpp").replace(
        "if (program.passes.at(k).allocationViewport)", "if (false)"))


# ------------------------------------------------------------------------------------------- N5.2d's two gaps

def test_an_rgba32f_item_texture_is_sixteen_bytes_a_texel_without_mips():
    from rendering.native.mode import TEXTURE_FORMATS, NativeMode

    mode_cpp = _source("mode_content.cpp")
    assert "rgba32f" in TEXTURE_FORMATS
    texel = _function(mode_cpp, "int modeTextureTexelBytes(", "qint64 modeTextureBytes(")
    assert "case ModeTextureFormat::RGBA32F:\n        return 16;" in texel
    assert "case ModeTextureFormat::RGBA32F:\n        return QRhiTexture::RGBA32F;" in mode_cpp
    assert "if (mips && format == ModeTextureFormat::RGBA32F) {" in mode_cpp
    assert '"Ls(ii)O|pppp"' in _source("module.cpp")
    # The face hands the core half_float False and full_float True; mips are refused before the core.
    calls = []
    module = SimpleNamespace(composite_mode_texture=lambda *args: calls.append(args))
    mode = NativeMode(module, SimpleNamespace(_live=lambda: 1))
    mode._handle = lambda: 7
    mode.texture("motion", bytes(16 * 4), (4, 1), format="rgba32f")
    assert calls[-1][5:] == (False, False, True)
    mode.texture("slope", bytes(8 * 4), (4, 1), format="rgba16f")
    assert calls[-1][5:] == (False, True)                         # control: ABI 33's form is unchanged
    with pytest.raises(ValueError, match="no mips"):
        mode.texture("motion", bytes(16 * 4), (4, 1), format="rgba32f", mips=True)


def test_a_mesh_layout_holds_the_glass_shards_sixteen_attributes():
    from rendering.quick.transitions.run_geometry import CRUMBLE_CHUNK_ATTRIBUTES, GLASS_ATTRIBUTES

    header = _source("mesh_buffers.h")
    limit = int(re.search(r"constexpr int kMaxMeshAttributes = (\d+);", header).group(1))
    inputs = int(re.search(r"constexpr int kMaxPassInputs = (\d+);", header).group(1))
    assert len(GLASS_ATTRIBUTES) <= limit and len(CRUMBLE_CHUNK_ATTRIBUTES) <= limit
    assert inputs == 16                                       # GL_MAX_VERTEX_ATTRIBS' guaranteed floor, as before
    assert 4 * sum(GLASS_ATTRIBUTES) <= 256                   # the layout's stride bound (mesh_buffers.cpp)
    assert "pass.inputs.size() > kMaxPassInputs" in _source("mode_content.cpp")
    # Negative control: the ABI 36 bound (8) refuses both meshes.
    assert len(GLASS_ATTRIBUTES) > 8 and len(CRUMBLE_CHUNK_ATTRIBUTES) > 8


# ------------------------------------------------------------------------------------------- the Python conversions

_OUTPUT = re.compile(r"layout\s*\(\s*location\s*=\s*(\d+)\s*\)\s*out\s+vec4\s+(\w+)\s*;")


def test_a_motion_fragment_writes_x_and_y_at_one_and_y_at_two_and_a_ghost_its_colour_only():
    """Checklist 16 (N5.2d): the native velocity is two R16F attachments, so the motion variants write y again at
    location 2 (Python's RG16F at 1 keeps (x, y); its location 2 has no draw buffer); a ghost writes FragColor alone
    (the core refuses outputs past its one-attachment ghost target). Stills before and after: byte-identical
    (evidence native_core/n5_2d)."""
    from rendering.gl_programs import blockspin_program, crumble_program, glass_shatter_program, pixel_accretion_program
    from rendering.gl_programs import exploding_tiles_program
    from rendering.gl_programs.scene3d import scene3d_ghost_fragment

    motions = (blockspin_program.BLOCK_SPIN_MOTION_FRAGMENT_SOURCE, crumble_program.CRUMBLE_MOTION_FRAGMENT,
               crumble_program.DEBRIS_MOTION_FRAGMENT, glass_shatter_program.GLASS_MOTION_FRAGMENT,
               pixel_accretion_program.PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE)
    ghosts = (blockspin_program.BLOCK_SPIN_GHOST_FRAGMENT_SOURCE, crumble_program.CRUMBLE_GHOST_FRAGMENT,
              crumble_program.DEBRIS_GHOST_FRAGMENT, glass_shatter_program.GLASS_GHOST_FRAGMENT,
              pixel_accretion_program.PIXEL_ACCRETION_GHOST_FRAGMENT_SOURCE,
              exploding_tiles_program.EXPLODING_TILES_GHOST_FRAGMENT_SOURCE)
    for text in motions:
        # N5.2h: the motion (x, y) at location 1 alone (the native core's one RGBA16F velocity, Python's RG16F).
        assert sorted(_OUTPUT.findall(text)) == [("0", "FragColor"), ("1", "SceneMotion")]
        assert "SceneMotion = vec4(motion, 0.0, 1.0);" in text
    for text in ghosts:
        assert _OUTPUT.findall(text) == [("0", "FragColor")]
    # Negative controls: a ghost keeping the motion outputs (the ABI 36 ghost kept SceneMotion) fails the check, and a
    # source without a motion output is refused rather than passed through.
    assert _OUTPUT.findall(motions[0]) != [("0", "FragColor")]
    with pytest.raises(ValueError, match="SceneMotion output once"):
        scene3d_ghost_fragment(motions[0].replace("layout(location = 1) out vec4 SceneMotion;", "vec4 SceneMotion;"))


def post_texts_read_in_pythons_frame(tile: str, gather: str, edges: str) -> bool:
    """The tile max, the gather and the edges read every texel through the frame helpers (motion.NATIVE_FRAME_GLSL):
    no plain read of the velocity, the scene or the ghosts is left, and the gather's and the edges' own texel is
    flipped back from the fragment's."""
    plain = ("texelFetch(uVelocity, texel, 0).xy;\n            float", "texelFetch(uVelocity, pixel, 0)",
             "texelFetch(uVelocity, tap, 0)", "texelFetch(uScene, pixel, 0)", "texelFetch(uScene, tap, 0)")
    return (all("sceneVelocityAt(uVelocity, " in text for text in (tile, gather))
            and not any(p in tile or p in gather for p in plain)
            and "ivec2 pixel = sceneMemoryTexel(fragTexel(uSize), uSize);" in gather
            and "ivec2 pixel = sceneMemoryTexel(fragTexel(uSize), uSize);" in edges
            and "sceneMemoryTexel(clamp(texel, ivec2(0), uSize - 1), uSize)" in edges)


def test_the_post_passes_read_in_pythons_frame_under_the_native_define():
    """Checklist 16 (N5.2d): one text per pass for both renderers; the native packs are baked with
    ``SRPSS_NATIVE_CORE`` (the core's scene target is Python's allocation flipped whole, its motion y negated, its
    velocity one RGBA16F: N5.2h). Python's stills before and after: byte-identical (evidence native_core/n5_2d)."""
    from rendering.quick.scene3d.motion import MOTION_BLUR_PROGRAMS, NATIVE_FRAME_DEFINE, NATIVE_FRAME_GLSL
    from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM

    (_k, tile), (_g, _v, gather) = MOTION_BLUR_PROGRAMS
    edges = TRAIL_EDGES_PROGRAM[2]
    assert post_texts_read_in_pythons_frame(tile, gather, edges)
    native, plain = NATIVE_FRAME_GLSL.split("#else")
    assert f"#ifdef {NATIVE_FRAME_DEFINE}" in native and "size.y - 1 - texel.y" in native
    assert "return vec2(motion.x, -motion.y);" in native and "uVelocityY" not in tile + gather   # one attachment
    assert "return texel;" in plain and "texelFetch(velocity, texel, 0).xy" in plain   # identity without the define
    # Negative control: the ABI 36 texts (plain reads, the fragment's own texel) fail.
    assert not post_texts_read_in_pythons_frame(
        tile.replace("sceneVelocityAt(uVelocity, texel)", "texelFetch(uVelocity, texel, 0).xy"), gather, edges)
    assert not post_texts_read_in_pythons_frame(
        tile, gather, edges.replace("sceneMemoryTexel(fragTexel(uSize), uSize)", "fragTexel(uSize)"))


def test_the_abi_is_37_or_later():
    from rendering.native import loader

    defined = int(re.search(r"#define SRPSS_NATIVE_CORE_ABI (\d+)", _source("abi.h")).group(1))
    # 37 brought these additions; a later ABI keeps them. The module and its importer agree.
    assert defined >= 37 and loader.EXPECTED_ABI == defined
