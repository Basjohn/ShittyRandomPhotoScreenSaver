"""N5.4, the Waveform port's two core gaps (ABI 35), GPU-free (``native/core/src/abi.h`` 35).

- C1: an item texture with mips has its chain made by the core's box kernel (the lead's decision of 21 Nov: every level
  chain a sampler reads), both upload routes, one kernel owner (``mip_chain.h``) for the textures and the self-mipped
  targets; the two shader files are the Python renderer's texts (``rendering/gl_programs/mip_chain.py``).
- C2: a composite step's ``scene_frame`` ``"oriented"`` (Python's ``orient_visualizer_scene_frame``): the card's
  ``scene_oriented`` and ``scene_from_window`` (``rendering.native.spectrum.oriented_scene_card``), the core's anchor
  and its composite map.

Each test's negative control is the pre-change form (the ABI 33 source or face), seen failing. The drawn proofs run on
the built module (``scene_target_check.py`` and the Waveform port's own harness).
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"
SHADERS = ROOT / "native" / "core" / "shaders"


def _source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def _function(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


# ------------------------------------------------------------------------------------------- C1: the item chains

def item_chains_are_wired(mode_cpp: str, jobs_cpp: str) -> bool:
    """Both routes upload level 0 only into a MipMapped | UsedWithLoadStore texture and leave its chain pending; the
    record makes every pending chain (its uploads handed to the command buffer first) before any pass."""
    if "void ModeContent::recordTextureChains(" not in mode_cpp:
        return False
    upload = _function(mode_cpp, "bool ModeContent::uploadInFrame(", "void ModeContent::recordTextureChains(")
    chains = _function(mode_cpp, "void ModeContent::recordTextureChains(", "RhiOwned<QRhiTexture> ModeContent::importTexture(")
    imported = _function(mode_cpp, "RhiOwned<QRhiTexture> ModeContent::importTexture(", "void ModeContent::adoptImport(")
    adopt = _function(mode_cpp, "void ModeContent::adoptImport(", "QString ModeContent::advanceTextures(")
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    flags = "(QRhiTexture::MipMapped | QRhiTexture::UsedWithLoadStore)"
    return (flags in upload and flags in imported and flags in jobs_cpp
            and "generateMips(" not in upload and "generateMips(" not in jobs_cpp
            and "gpu.chainPending = image->mips;" in upload and "gpu.chainPending = job.mips;" in adopt
            and "cb->resourceUpdate(*pending);" in chains and "m_textureChains.record(cb, gpu.chain);" in chains
            and chains.index("cb->resourceUpdate(*pending);") < chains.index("m_textureChains.record(")
            and passes.index("recordTextureChains(rhi, cb, &pending);") < passes.index("while (i < count)"))


def test_an_item_textures_chain_is_the_box_kernels_on_both_routes():
    mode_cpp, jobs_cpp = _source("mode_content.cpp"), _source("job_service.cpp")
    assert item_chains_are_wired(mode_cpp, jobs_cpp)
    # A device without compute refuses the texture with its reason; a chain that cannot be made releases the front.
    assert "which need QRhi::Compute (the core's box kernel)" in mode_cpp
    chains = _function(mode_cpp, "void ModeContent::recordTextureChains(", "RhiOwned<QRhiTexture> ModeContent::importTexture(")
    assert "releaseFront(gpu);" in chains
    # Counted for the harness (composite_live's mode_texture_chains), released with the content.
    assert '"mode_texture_chains"' in _source("module.cpp") and "m_textureChains.release();" in mode_cpp
    # Negative controls: the ABI 33 forms (QRhi's generateMips on the in-frame route, or on the job's) are caught.
    assert not item_chains_are_wired(mode_cpp.replace(
        "    gpu.chainPending = image->mips;\n", "    if (image->mips)\n        updates->generateMips(gpu.texture.get());\n"),
        jobs_cpp)
    assert not item_chains_are_wired(mode_cpp, jobs_cpp.replace(
        "        cb->resourceUpdate(updates); // the staging copy, on this thread",
        "        updates->generateMips(texture.get());\n        cb->resourceUpdate(updates); // the staging copy"))
    # ... and the chain recorded after the passes began.
    assert not item_chains_are_wired(mode_cpp.replace(
        "    recordTextureChains(rhi, cb, &pending);\n", "").replace(
        "    if (computeOpen)\n        cb->endComputePass();                 // N3.3: the program ended on compute entries\n",
        "    recordTextureChains(rhi, cb, &pending);\n    if (computeOpen)\n        cb->endComputePass();\n"), jobs_cpp)


def test_the_kernel_files_are_the_python_renderers_texts():
    from rendering.gl_programs.mip_chain import MIP_BOX_COMP, MIP_BOX_RGBA8_COMP, MIP_BOX_TEXTS

    assert (SHADERS / "mip_box.comp").read_text(encoding="utf-8") == MIP_BOX_COMP
    assert (SHADERS / "mip_box_rgba8.comp").read_text(encoding="utf-8") == MIP_BOX_RGBA8_COMP
    assert set(MIP_BOX_TEXTS) == {"rgba8", "rgba16f"}
    for fmt, text in MIP_BOX_TEXTS.items():
        assert f"layout(binding = 0, {fmt}) readonly uniform image2D u_source;" in text
        assert f"layout(binding = 1, {fmt}) writeonly uniform image2D u_dest;" in text
    # The two differ in their images' format and the 8-bit text's integer sums: every load taken back to its 8-bit
    # value (NVIDIA's OpenGL loads RGBA8 at half-float precision, its Vulkan at single), the level rounded once to the
    # nearest value and stored exact.
    unorm8 = "    return floor(imageLoad(u_source, p) * 255.0 + 0.5);\n"
    store = "    precise vec4 level = floor(sum + 0.5) / 255.0;\n    imageStore(u_dest, dst, level);\n"
    assert unorm8 in MIP_BOX_RGBA8_COMP and store in MIP_BOX_RGBA8_COMP
    assert MIP_BOX_RGBA8_COMP.count("unorm8(ivec2(") == 3 and MIP_BOX_RGBA8_COMP.count("imageLoad(") == 1
    assert "imageStore(u_dest, dst, sum);" in MIP_BOX_COMP and "unorm8" not in MIP_BOX_COMP
    rebuilt = MIP_BOX_COMP.replace("rgba16f", "rgba8")
    for tap in ("ax.x", "ax.z", "ax.y"):
        rebuilt = rebuilt.replace(f"imageLoad(u_source, ivec2({tap}, y))", f"unorm8(ivec2({tap}, y))")
    rebuilt = rebuilt.replace("    imageStore(u_dest, dst, sum);\n",
                              "    // The level in 8-bit units, rounded once to the nearest value and stored exactly.\n"
                              + store)
    assert rebuilt == MIP_BOX_RGBA8_COMP.replace(MIP_BOX_RGBA8_COMP[MIP_BOX_RGBA8_COMP.index("// An 8-bit texel"):
                                                                    MIP_BOX_RGBA8_COMP.index("vec4 row(")], "")
    # Negative control: a file drifting from its text is caught (the RGBA8 file is not the RGBA16F text).
    assert (SHADERS / "mip_box_rgba8.comp").read_text(encoding="utf-8") != MIP_BOX_COMP


def test_the_kernel_owner_is_one_and_its_levels_are_the_full_chain():
    from rendering.gl_programs.mip_chain import mip_levels

    owner = _source("mip_chain.cpp")
    assert "QRhiTexture::RGBA8" in owner and "QRhiTexture::RGBA16F" in owner
    assert "m_chainKernel" in _source("scene_targets.h") and "MipChainKernel m_textureChains;" in _source("mode_content.h")
    assert "src/mip_chain.cpp" in (ROOT / "native" / "core" / "CMakeLists.txt").read_text(encoding="utf-8")

    def core_levels(width: int, height: int) -> int:                   # mipChainLevels, line for line
        levels = 1
        while width > 1 or height > 1:
            width, height, levels = max(1, width // 2), max(1, height // 2), levels + 1
        return min(levels, 15)

    for size in ((1, 1), (2, 1), (3, 3), (333, 187), (1254, 1254), (1254, 627), (4096, 2160), (7, 1024)):
        assert mip_levels(size) == core_levels(*size) == max(size).bit_length(), size
    # Negative control: a log2 rounding (Python's former levels_of on a power of two plus one) is caught somewhere.
    assert any(int(math.log2(max(size))) != core_levels(*size) for size in ((3, 3), (333, 187)))


def _box(level, axis: int):
    """The kernel's separable step along ``axis`` (numpy, float64): the reference model of mip_box.comp."""
    import numpy as np

    level = np.moveaxis(np.asarray(level, float), axis, 0)
    s = level.shape[0]
    if s == 1:
        out = level.copy()
    elif s % 2 == 0:
        out = 0.5 * level[0::2] + 0.5 * level[1::2]
    else:
        d = s // 2
        i = np.arange(d).reshape((-1,) + (1,) * (level.ndim - 1))
        out = ((d - i) * level[0:2 * d:2] + (i + 1) * level[2:2 * d + 1:2]) / s + d * level[1:2 * d:2] / s
    return np.moveaxis(out, 0, axis)


def test_the_box_is_the_exact_area_average_and_blind_to_the_row_order():
    import numpy as np

    rng = np.random.default_rng(54)
    image = rng.random((187, 333))
    level = _box(_box(image, 0), 1)
    # The exact area average: every source texel weighs n / s in its level, so the mean is kept exactly.
    assert level.shape == (93, 166) and math.isclose(level.mean(), image.mean(), rel_tol=1e-12)
    # Blind to the row order: the level of the flipped picture is the flipped level.
    flipped = _box(_box(image[::-1], 0), 1)[::-1]
    assert np.allclose(level, flipped, rtol=0.0, atol=1e-15)

    # Negative control: the driver's NPOT reduction anchored at row 0 (pairs 2i, 2i + 1, the last row dropped) keeps
    # neither.
    def anchored(a):
        return 0.5 * a[0:-1:2] + 0.5 * a[1::2]

    assert not math.isclose(anchored(image).mean(), image.mean(), rel_tol=1e-6)
    assert not np.allclose(anchored(image), anchored(image[::-1])[::-1])


# ------------------------------------------------------------------------------------------- C2: the oriented frame

def _python_frame(matrix, size, viewport, quarters):
    return SimpleNamespace(matrix_values=tuple(matrix), logical_size=size, viewport=viewport,
                           content_rotation_quarters=quarters, scene_output_rotation=0)


def _item_matrix(window, origin):
    from rendering.native.spectrum import _ortho_item_matrix

    return _ortho_item_matrix(window, origin, single=True)


@pytest.mark.parametrize("quarters", (1, 2, 3))
@pytest.mark.parametrize("window,origin,item", (((1707.0, 960.0), (101.0, 57.0), (640.0, 360.0)),
                                                 ((1280.0, 720.0), (33.5, 17.25), (301.0, 187.0))))
def test_the_cards_oriented_frame_is_pythons_oriented_scene_target(quarters, window, origin, item):
    """``oriented_scene_card``'s rect is ``item_pixel_rect`` of ``orient_visualizer_scene_frame``'s frame, and its map
    takes every pixel of the item's physical cover onto that rect exactly as the oriented composite's ``sceneTexel``
    does (target.py): Python's texel of each window pixel, the core's composite input (ABI 35)."""
    from rendering.native.spectrum import oriented_scene_card
    from rendering.quick.scene3d.frame import item_pixel_rect, oriented_scene_geometry

    viewport = (0, 0, int(window[0]), int(window[1]))
    matrix = _item_matrix(window, origin)
    oriented_size = (item[1], item[0]) if quarters & 1 else item
    card = oriented_scene_card(matrix, item, oriented_size, viewport, quarters)
    turned, oriented_viewport = oriented_scene_geometry(matrix, item, viewport, quarters)
    rect = item_pixel_rect(SimpleNamespace(matrix_values=tuple(turned), logical_size=oriented_size,
                                           viewport=oriented_viewport))
    assert card["scene_oriented"] == [float(v) for v in rect]
    ox, oy, ow, oh = (int(v) for v in rect)
    assert (ow, oh) == ((rect[2], rect[3]))
    s = card["scene_from_window"]
    vw, vh = viewport[2], viewport[3]
    bx, by, bw, bh = item_pixel_rect(SimpleNamespace(matrix_values=tuple(matrix), logical_size=item, viewport=viewport))
    assert (bw, bh) == ((oh, ow) if quarters & 1 else (ow, oh))
    seen = set()
    for px in range(bx, bx + bw):
        for py in range(by, by + bh):
            # Python's sceneTexel (integer form) and the card's continuous map at the pixel's centre, floored.
            if quarters == 1:
                python = (vh - 1 - py, px)
            elif quarters == 2:
                python = (vw - 1 - px, vh - 1 - py)
            else:
                python = (py, vw - 1 - px)
            centre = (px + 0.5, py + 0.5)
            mapped = (math.floor(s[0] * centre[0] + s[1] * centre[1] + s[2]),
                      math.floor(s[3] * centre[0] + s[4] * centre[1] + s[5]))
            assert mapped == python
            texel = (python[0] - ox, python[1] - oy)
            assert 0 <= texel[0] < ow and 0 <= texel[1] < oh
            seen.add(texel)
    assert len(seen) == ow * oh                                        # one to one onto the oriented rect
    # Negative control: the turn the other way (4 - quarters) does not land on Python's texels.
    if quarters != 2:
        other = oriented_scene_card(matrix, item, oriented_size, viewport, 4 - quarters)["scene_from_window"]
        px, py = bx, by
        centre = (px + 0.5, py + 0.5)
        wrong = (math.floor(other[0] * centre[0] + other[1] * centre[1] + other[2]),
                 math.floor(other[3] * centre[0] + other[4] * centre[1] + other[5]))
        right = (vh - 1 - py, px) if quarters == 1 else (py, vw - 1 - px)
        assert wrong != right


def test_orient_visualizer_scene_frame_is_unchanged_by_its_shared_geometry():
    """The refactor that shares ``oriented_scene_geometry`` keeps ``orient_visualizer_scene_frame``'s frame bit for bit
    (the pre-change arithmetic, restated here, is the oracle)."""
    from dataclasses import dataclass, replace

    from rendering.quick.scene3d.frame import _clip_turn, orient_visualizer_scene_frame

    @dataclass(frozen=True)
    class Presentation:
        outer_rect: tuple = (0.0, 0.0, 640.0, 360.0)
        content_rect: tuple = (0.0, 0.0, 640.0, 360.0)
        viewport_extent: tuple = (640.0, 360.0)
        logical_viewport_extent: tuple = (360.0, 640.0)
        content_rotation_quarters: int = 1

    @dataclass(frozen=True)
    class Snapshot:
        presentation: Presentation

    @dataclass(frozen=True)
    class Frame:
        snapshot: Snapshot
        viewport: tuple
        logical_size: tuple
        matrix_values: tuple
        content_rotation_quarters: int
        oriented_logical_size: tuple
        logical_content_rect: tuple
        scene_output_rotation: int = 0
        scene_output_viewport: tuple | None = None

    def before(frame):                        # the pre-change body, verbatim
        quarters = frame.content_rotation_quarters
        width, height = frame.logical_size
        matrix = frame.matrix_values
        x_basis, y_basis, translation = ((0, 1), (-1, 0), (width, 0)) if quarters == 1 else (
            ((-1, 0), (0, -1), (width, height)) if quarters == 2 else ((0, -1), (1, 0), (0, height)))
        turned = list(matrix)
        for row in range(4):
            turned[row] = matrix[row] * x_basis[0] + matrix[4 + row] * x_basis[1]
            turned[4 + row] = matrix[row] * y_basis[0] + matrix[4 + row] * y_basis[1]
            turned[12 + row] = matrix[12 + row] + matrix[row] * translation[0] + matrix[4 + row] * translation[1]
        turned = _clip_turn(turned, quarters)
        _vx, _vy, vw, vh = frame.viewport
        return turned, ((0, 0, vh, vw) if quarters & 1 else (0, 0, vw, vh))

    for quarters in (1, 2, 3):
        size = (640.0, 360.0)
        frame = Frame(Snapshot(Presentation(content_rotation_quarters=quarters)), (0, 0, 1707, 960), size,
                      _item_matrix((1707.0, 960.0), (101.0, 57.0)), quarters,
                      (size[1], size[0]) if quarters & 1 else size, (0.0, 0.0, 360.0, 640.0))
        oriented = orient_visualizer_scene_frame(frame)
        assert (oriented.matrix_values, oriented.viewport) == before(frame)
        assert oriented.scene_output_rotation == quarters and oriented.scene_output_viewport == frame.viewport
        # Control: the unturned frame is returned as it is (q0 is exactly the original frame).
        assert orient_visualizer_scene_frame(replace(frame, content_rotation_quarters=0)).matrix_values \
            == frame.matrix_values


def oriented_frame_is_wired(mode_cpp: str) -> bool:
    if "bool ModeProgram::sceneFrameOriented() const" not in mode_cpp:
        return False
    anchor = _function(mode_cpp, "bool sceneAnchor(", "const ModeCoreMember kModeCoreMembers[] =")
    value = _function(mode_cpp, "void valueSceneFromTarget(", "void valueSceneFromTargetX(")
    refusal = _function(mode_cpp, "QString ModeProgram::turnedStagesRefusal(", "QString ModeProgram::textureFits(")
    pack = _function(mode_cpp, "bool ModeProgram::packFrame(", "bool modeBlocks(")
    card = _function(mode_cpp, "bool ModeCard::fromJson(", "QJsonObject ModeCard::toJson(")
    return ("const bool oriented = program.sceneFrameOriented() && card.hasSceneOriented;" in anchor
            and "sceneCard->quarters = 0;" in anchor and "bucketPixels(ow), bucketPixels(oh)" in anchor
            and "card.orientedFrame && card.hasSceneOriented" in value
            and "s[0] * w[2] + s[1] * w[5] + s[2] - card.sceneOriented[row]" in value
            and "if (card.hasSceneOriented)" in refusal
            and "surfaceCard.orientedFrame = sceneFrameOriented();" in pack
            and "? *sceneCard : surfaceCard;" in pack
            and '"scene_oriented"' in card and '"scene_from_window"' in card
            and 'frame != QJsonValue(QStringLiteral("oriented"))' in mode_cpp)


def test_the_core_anchors_an_oriented_scene_and_maps_its_composite():
    mode_cpp = _source("mode_content.cpp")
    assert oriented_frame_is_wired(mode_cpp)
    assert "bool hasSceneOriented = false;" in _source("mode_content.h")
    # Negative controls: without the packed surface card's frame the composite keeps the window's map; without the
    # anchor's branch the turned card is refused (ABI 33's M3).
    assert not oriented_frame_is_wired(mode_cpp.replace("surfaceCard.orientedFrame = sceneFrameOriented();", ""))
    assert not oriented_frame_is_wired(mode_cpp.replace(
        "const bool oriented = program.sceneFrameOriented() && card.hasSceneOriented;", "const bool oriented = false;"))


def test_the_face_declares_the_oriented_frame_and_carries_the_cards_keys():
    from rendering.native.mode import (MODE_CARD_KEYS, MODE_CARD_ORIENTED_KEYS, SCENE_FRAMES, CompositeStep,
                                       mode_card)

    step = CompositeStep("show", "overlay_glow", "scene.colour", glow="bloom.glow", scene_frame="oriented")
    assert step.declaration()["scene_frame"] == "oriented" and set(SCENE_FRAMES) == {None, "window", "oriented"}
    with pytest.raises(ValueError):
        CompositeStep("show", "overlay", "scene.colour", scene_frame="turned")
    assert not set(MODE_CARD_ORIENTED_KEYS) & set(MODE_CARD_KEYS)
    import inspect

    assert "MODE_CARD_KEYS + MODE_CARD_ORIENTED_KEYS" in inspect.getsource(mode_card)
    spectrum = (ROOT / "rendering" / "native" / "spectrum.py").read_text(encoding="utf-8")
    assert "extra.update(oriented_scene_card(" in spectrum and "        if quarters:\n" in spectrum


def test_the_abi_is_35_or_later_with_34_retired():
    import re

    from rendering.native import loader

    abi = _source("abi.h")
    # 35 brought these gaps; a later ABI (36: N5.2c) keeps them. The module and its importer agree.
    defined = int(re.search(r"#define SRPSS_NATIVE_CORE_ABI (\d+)", abi).group(1))
    assert defined >= 35 and loader.EXPECTED_ABI == defined
    assert "// 35 (N5.4, the Waveform port's two core gaps)" in abi
    assert "// 34: retired unused" in abi
