"""N3.4, transparency and post-processing as shared stages on the native core (Current_Plan.md item 8b; decision D17),
GPU-free:

- the core's stage shaders are the Python stages' arithmetic (``native/core/shaders/scene_oit_resolve*.frag`` against
  ``rendering/quick/scene3d/target.py``'s resolves, ``bloom_*.frag`` against ``post.py``, ``defocus_*`` against
  ``defocus.py``, the composite's tone map and dither against ``target.py`` and ``scene3d.py``), each with the
  differences D17 names and nothing else (the coverage stored inverted; the core's rows run top first, so a tap Python
  takes at +y is the core's at -y), and each comparison with a negative control;
- the program's Python face declares the stages and orders the packs as the core reads them (a step's pack empty, a
  transparent pass's sorted pack last);
- N3.1's check of differing attachment states reads the core's device facts, never QRhi's always-true flag (D17's fix of
  the latent defect).

The GPU proof is ``native/core/python/post_stage_check.py`` (hidden host, both backends).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
SHADERS = CORE / "shaders"


def _shader(name: str) -> str:
    return (SHADERS / name).read_text(encoding="utf-8")


def _main(source: str) -> list[str]:
    """main()'s statements, whitespace-normalised (comments dropped)."""
    source = re.sub(r"//[^\n]*", "", source)
    body = source[source.index("void main()"):]
    body = body[body.index("{") + 1:body.rindex("}")]
    statements = [re.sub(r"\s+", " ", s).strip() for s in body.split(";")]
    return [s for s in statements if s]


def _renamed(statements: list[str], names: dict[str, str]) -> list[str]:
    out = []
    for s in statements:
        for old, new in names.items():
            s = re.sub(rf"\b{re.escape(old)}\b", new, s)
        out.append(s)
    return out


# --------------------------------------------------------------------------- the transparency resolve (D17 point 2)


# Python stores revealage (1 - coverage); the core stores coverage (D17 choice B): the one difference in the read.
_REVEAL = ("1.0 - texelFetch(uReveal, ", "texelFetch(uCoverage, ")


@pytest.mark.parametrize("python_name, core_file", [("_OIT_RESOLVE_FRAGMENT", "scene_oit_resolve.frag"),
                                                    ("_OIT_RESOLVE_SAMPLES_FRAGMENT", "scene_oit_resolve_samples.frag")])
def test_the_core_resolve_is_pythons_with_the_coverage_read_as_stored(python_name: str, core_file: str) -> None:
    from rendering.quick.scene3d import target

    python = [s.replace(*_REVEAL) for s in _main(getattr(target, python_name))]
    core = _main(_shader(core_file))
    assert core == python
    # Negative control: Python's revealage read (no inversion) is caught.
    assert _main(getattr(target, python_name)) != core


def test_the_transparent_pass_blends_store_coverage_inverted_and_equal_the_textbook_revealage() -> None:
    """D17 choice B: ONE, ONE_MINUS_SRC_COLOR from a clear of 0 is c' = a + c (1 - a), so 1 - c is Python's revealage
    (ZERO, ONE_MINUS_SRC_COLOR from a clear of 1) on any stack, in exact arithmetic."""
    source = (CORE / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    state = source[source.index("bool transparentPassState("):source.index("bool checkSortedPack(")]
    assert ("pass.outputs[1] = customOutput(blendOf(QRhiGraphicsPipeline::One, QRhiGraphicsPipeline::OneMinusSrcColor,"
            in state)
    assert "pass.outputs[0] = customOutput(blendOf(QRhiGraphicsPipeline::One, QRhiGraphicsPipeline::One," in state
    alphas = (0.3, 0.55, 0.12, 0.9, 0.05)
    coverage, revealage = 0.0, 1.0
    for a in alphas:
        coverage = a + coverage * (1.0 - a)    # the core's blend from its clear (0)
        revealage = 0.0 + revealage * (1.0 - a)  # Python's (ZERO, ONE_MINUS_SRC_COLOR) from its clear (1)
    assert abs((1.0 - coverage) - revealage) < 1e-12
    # Negative control: the textbook form read as coverage without the inversion is wrong.
    assert abs(revealage - coverage) > 0.1
    # Both of the transparency target's own attachments keep the default clear, 0 (scene_targets.cpp's declaration).
    targets = (CORE / "src" / "scene_targets.cpp").read_text(encoding="utf-8")
    declaration = targets[targets.index("static bool parseTransparencyDeclaration"):targets.index(
        "bool deriveTransparencyTargets")]
    assert ".clear[" not in declaration
    assert "float clear[4] = { 0.0f, 0.0f, 0.0f, 0.0f };" in (CORE / "src" / "scene_targets.h").read_text(
        encoding="utf-8")


# --------------------------------------------------------------------------- bloom (D17 point 4)


def _taps(source: str, call: str, uv: str) -> list[tuple[float, float]]:
    """The (x, y) texel offsets of each `call(uSource, <uv> ± offset)` in order (0, 0 for the centre)."""
    found = []
    for match in re.finditer(rf"{call}\(uSource, {re.escape(uv)}(.*?)(?:, 0\.0)?\)\.rgb", source):
        rest = match.group(1).strip()
        if not rest:
            found.append((0.0, 0.0))
            continue
        sign = -1.0 if rest.startswith("-") else 1.0
        term = rest[1:].strip()
        if term in ("uTexel", "texel"):
            found.append((sign, sign))
            continue
        inner = re.match(r"vec2\(([^,]+), ([^)]+)\)", term)
        values = []
        for part in (inner.group(1), inner.group(2)):
            part = part.strip()
            negative = part.startswith("-")
            part = part.lstrip("-")
            values.append(0.0 if part == "0.0" else (-1.0 if negative else 1.0))
        found.append((sign * values[0], sign * values[1]))
    return found


def test_the_core_downsamples_are_pythons_13_tap_filter_and_bright_pass() -> None:
    from rendering.quick.scene3d import post

    python_main = _main(post._DOWNSAMPLE_FRAGMENT)
    for name in ("bloom_down_first.frag", "bloom_down.frag"):
        core = _shader(name)
        assert _main(core) == python_main, name
        # The taps mirrored to the core's top-first rows: Python's offset (x, y) is read at (x, -y).
        assert "vec2(vUv.x, 1.0 - vUv.y) + vec2(offset.x, -offset.y) * texel" in core
    first = _shader("bloom_down_first.frag")
    for statement in ("float brightness = dot(value.rgb, vec3(0.2126, 0.7152, 0.0722));",
                      "return value.rgb * clamp(value.a / max(brightness, 1e-3), 0.0, 1.0);"):
        assert statement in post._DOWNSAMPLE_FRAGMENT and statement in first
    assert "brightness" not in _shader("bloom_down.frag")
    # Negative control: a weight changed is caught.
    assert _main(_shader("bloom_down.frag").replace("* 0.03125", "* 0.0625")) != python_main


def test_the_core_upsample_is_pythons_tent_mirrored_to_top_first_rows() -> None:
    from rendering.quick.scene3d import post

    python = _taps(post._UPSAMPLE_FRAGMENT, "texture", "vUv")
    core = _taps(_shader("bloom_up.frag"), "textureLod", "uv")
    assert len(python) == 9
    assert core == [(x, -y) for x, y in python]
    for weight in ("* 4.0", "* 2.0", "sum / 16.0"):
        assert weight in post._UPSAMPLE_FRAGMENT and weight in _shader("bloom_up.frag")
    # Negative control: Python's taps unmirrored are not the core's.
    assert core != python


def test_the_bloom_chain_is_one_texture_a_level_and_never_generate_mips() -> None:
    from rendering.quick.scene3d import post

    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    header = (CORE / "src" / "post_stages.h").read_text(encoding="utf-8")
    assert f"constexpr int kBloomLevels = {post.BLOOM_LEVELS};" in header
    sync = stages[stages.index("bool PostStages::sync("):stages.index("bool PostStages::bloomBindings(")]
    assert "size = QSize(qMax(1, size.width() / 2), qMax(1, size.height() / 2));" in sync
    assert "std::unique_ptr<QRhiTexture> levels[kBloomLevels];" in header
    assert "generateMips" not in stages[stages.index("void PostStages::recordBloom("):
                                        stages.index("void PostStages::recordDefocusClip(")]


# --------------------------------------------------------------------------- the defocus layer (D17 point 6)


_DEFOCUS_NAMES = {"uLevel": "u_defocus_level", "uHighlight": "u_defocus_highlight", "uMaxRadius": "u_defocus_radius"}


def test_the_core_clip_is_pythons() -> None:
    from rendering.quick.scene3d import defocus

    python = _renamed(_main(defocus._CLIP), _DEFOCUS_NAMES)
    core = _main(_shader("defocus_clip.frag"))
    assert core == python
    # The helper reads the mean two levels coarser, as Python's.
    assert "textureLod(colour, uv, float(level + 2))" in defocus._CLIP
    assert "textureLod(colour, uv, float(level + 2))" in _shader("defocus_clip.frag")
    # Negative control: the threshold's mix changed is caught.
    assert _main(_shader("defocus_clip.frag").replace("mix(1.0, limit / l, share)", "mix(1.0, l / limit, share)")) \
        != python


def test_the_core_gather_is_pythons_with_its_taps_mirrored() -> None:
    from rendering.quick.scene3d import defocus

    python = [s.replace("vec2(cos(a), sin(a))", "vec2(cos(a), -sin(a))") for s in _main(defocus._GATHER)]
    core = [s for s in _main(_shader("defocus_gather.frag")) if s != "float uMaxRadius = u_defocus_radius"]
    assert core == python
    # Negative control: Python's taps unmirrored are not the core's.
    assert _main(defocus._GATHER) != core


def test_the_core_sprites_are_pythons() -> None:
    from rendering.quick.scene3d import defocus

    names = {"uHighlight": "u_defocus_highlight", "uMaxRadius": "u_defocus_radius", "gl_InstanceID": "gl_InstanceIndex",
             "gl_VertexID": "gl_VertexIndex", "srpssVertexIndex": "gl_VertexIndex",
             "srpssInstanceIndex": "gl_InstanceIndex"}
    python = _renamed(_main(defocus._SPRITE_VERTEX), names)
    added = {"int uLevel = u_defocus_level", "vec2 uSize = vec2(textureSize(uColour, 0))", "vOffset = vec2(0.0)",
             "vCircle = 0.0", "vLight = vec3(0.0)"}
    core = [s for s in _main(_shader("defocus_sprites.vert")) if s not in added]
    assert core == python
    assert _main(_shader("defocus_sprites.frag")) == _main(defocus._SPRITE_FRAGMENT)
    # Negative control: the disc's rim changed is caught.
    assert _main(_shader("defocus_sprites.frag").replace("0.88 + 0.3", "0.9 + 0.3")) != _main(defocus._SPRITE_FRAGMENT)


def test_the_defocus_layer_alone_takes_generate_mips() -> None:
    """D17 choice G: QRhi's generateMips only for the defocus layer (its two attachments, in the defocus step)."""
    content = (CORE / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    record = content[content.index("void ModeContent::recordDefocus("):content.index("bool ModeContent::syncTargets(")]
    assert record.count("->generateMips(") == 2
    # The one other generateMips is N4.a's: an item texture uploaded with its mips (not a scene target's).
    upload = content[content.index("bool ModeContent::uploadInFrame("):content.index("std::unique_ptr<QRhiTexture> "
                                                                                   "ModeContent::importTexture(")]
    assert content.count("->generateMips(") == 2 + upload.count("->generateMips(")
    assert "generateMips(" not in (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8").replace(
        "never generateMips", "")


# --------------------------------------------------------------------------- the composite and the HDR resolve (point 5)


def test_the_core_composite_tone_map_and_dither_are_pythons() -> None:
    from rendering.gl_programs import scene3d
    from rendering.quick.scene3d import target

    glow = _shader("composite_overlay_glow.frag")
    tone = re.search(r"vec3 sceneToneMap\(vec3 x\) \{(.*?)\}", target._OVERLAY_BLOOM_GLSL, re.S).group(1)
    core_tone = re.search(r"vec3 sceneToneMap\(vec3 x\)\s*\{(.*?)\}", glow, re.S).group(1)
    norm = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731
    assert norm(core_tone) == norm(tone.replace("uHdrExposure", "u_hdr_exposure"))
    for line in ("x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;",
                 "return float(sceneMix(key * 0x9e3779b9u ^ sceneMix(seed * 0x85ebca6bu + salt))) * (1.0 / 4294967295.0);",
                 "uint key = uint(pixel.x & 0xffff) | (uint(pixel.y & 0xffff) << 16);"):
        assert line in scene3d.SCENE_OUTPUT_DITHER_GLSL and line in glow, line
    assert f"const float SCENE_DITHER_FLOOR = {scene3d.SCENE_DITHER_STEP / 4.0:.9f};" in glow
    assert f"(a + b - 1.0) * {scene3d.SCENE_DITHER_STEP:.9f};" in glow
    for statement in ("if (scene.a <= 0.0 && max(glow.r, max(glow.g, glow.b)) < 1.0 / 512.0) discard",
                      "vec3 light = scene.rgb + glow", "float cover = max(scene.a, 1e-4)",
                      "light = sceneToneMap(light / cover) * cover"):
        assert statement in _main(glow) or any(statement in s for s in _main(glow)), statement
    # Negative control: another ACES coefficient is caught.
    assert norm(core_tone.replace("2.43", "2.5")) != norm(tone.replace("uHdrExposure", "u_hdr_exposure"))


# --------------------------------------------------------------------------- the Python face


def test_the_program_declares_the_stages_and_orders_their_packs() -> None:
    from rendering.native.mode import (BloomStep, CompositeStep, DefocusStep, ModePass, ModeTarget, TargetAttachment,
                                       TransparencyResolve, TransparencyTarget, program_json)

    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f")),
                       depth=True, samples=4)
    oit = TransparencyTarget("oit", "scene", ("emission",))
    near = ModeTarget("near", (TargetAttachment("colour", "rgba16f"), TargetAttachment("circle", "rgba16f")), mips=True)
    passes = (
        ModePass("opaque", b"OPAQUE", "replace", target="scene", depth_test="less", depth_write=True),
        ModePass("shells", b"SHELLS", "replace", target="oit", sorted_pack=b"SORTED"),
        TransparencyResolve("resolve", "oit"),
        ModePass("near_shells", b"NEAR", "premultiplied", target="near"),
        DefocusStep("defocus", "near", "scene"),
        BloomStep("bloom", "scene.emission"),
        CompositeStep("composite", "overlay_glow", "scene.colour", "bloom.glow"),
    )
    declaration, packs = program_json(passes, (scene, oit, near))
    program = json.loads(declaration)
    assert packs == [b"OPAQUE", b"SHELLS", b"SORTED", b"", b"NEAR", b"", b"", b""]
    assert program["targets"][1] == {"name": "oit", "transparency": {"of": "scene", "borrow": ["emission"]}}
    assert program["targets"][2]["mips"] is True
    assert program["passes"][1]["sorted"] is True
    assert program["passes"][2] == {"name": "resolve", "transparency_resolve": "oit"}
    assert program["passes"][4] == {"name": "defocus", "defocus": "near", "onto": "scene"}
    assert program["passes"][5] == {"name": "bloom", "bloom": "scene.emission"}
    assert program["passes"][6] == {"name": "composite", "composite": "overlay_glow", "scene": "scene.colour",
                                    "glow": "bloom.glow"}
    # Negative controls: a glow form without its glow, and a mipped multisampled target, are refused here.
    with pytest.raises(ValueError):
        CompositeStep("composite", "overlay_glow", "scene.colour")
    with pytest.raises(ValueError):
        ModeTarget("near", (TargetAttachment("colour", "rgba16f"),), mips=True, samples=4)


def test_a_transparent_pass_declares_the_core_blends_empty() -> None:
    """The core refuses a transparent pass whose first two "attachments" entries are not {} (its accumulation and
    coverage blends are the core's); a borrowed attachment keeps its own entry."""
    from rendering.native.mode import ModePass, PassOutput, program_json

    outputs = (PassOutput(True, "replace"), PassOutput(True, "replace"), PassOutput(True, "additive"))
    shells = ModePass("shells", b"SHELLS", "replace", target="oit", sorted_pack=b"SORTED", outputs=outputs)
    declared = json.loads(program_json((shells,))[0])["passes"][0]["attachments"]
    assert declared == [{}, {}, {"write": True, "blend": "additive"}]
    # Negative control: the same outputs on a pass without a sorted pack keep every entry.
    plain = ModePass("plain", b"PLAIN", "replace", target="scene", outputs=outputs)
    assert json.loads(program_json((plain,))[0])["passes"][0]["attachments"][0] == {"write": True, "blend": "replace"}


def test_the_defocus_run_chains_its_two_stage_reads() -> None:
    """Qt 6.12.0's pass tracker keeps the earlier stage of a texture read in two stages of one pass, so the defocus
    run (the gather reads the layer in the fragment stage, the sprites in the vertex stage) is followed by the core's
    execution dependency from both stages (targets.cpp chainShaderReads), unless the harness's control skips it."""
    content = (CORE / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    defocus = content[content.index("void ModeContent::recordDefocus("):content.index("bool ModeContent::syncTargets(")]
    end = defocus.index("cb->endPass();")
    assert "if (!skipReadChain())\n        chainShaderReads(rhi, cb);" in defocus[end:]
    targets = (CORE / "src" / "targets.cpp").read_text(encoding="utf-8")
    chain = targets[targets.index("bool chainShaderReads("):]
    assert "VK_PIPELINE_STAGE_VERTEX_SHADER_BIT | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT" in chain
    assert "VK_PIPELINE_STAGE_ALL_COMMANDS_BIT" in chain[:chain.index("cb->endExternal();")]
    # Negative control: the gather and the sprites do read the layer in those two stages (else no chain is needed).
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    assert "sampledTexture(1, fragment, d.colour, d.mipSampler.get())" in stages
    assert "sampledTexture(1, vertex, d.colour, d.mipSampler.get())" in stages


def test_the_core_reads_every_stage_shader_it_bakes() -> None:
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    for name in ("scene_oit_resolve.frag", "scene_oit_resolve_samples.frag", "scene_oit_resolve_sample0.frag",
                 "bloom_down_first.frag", "bloom_down.frag", "bloom_up.frag", "composite_overlay.frag",
                 "composite_overlay_glow.frag", "composite_opaque_glow.frag", "defocus_clip.frag", "defocus_gather.frag",
                 "defocus_sprites.vert", "defocus_sprites.frag"):
        assert (SHADERS / name).is_file(), name
        symbol = re.sub(r"[^A-Za-z0-9]", "_", name) + "_qsb"
        assert f"shaderFrom({symbol}, {symbol}_size)" in stages, symbol
    assert "src/post_stages.cpp" in (CORE / "CMakeLists.txt").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- N3.1's latent defect (D17)


def test_n31_per_attachment_check_reads_the_core_device_facts() -> None:
    content = (CORE / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    build = content[content.index("bool ModeContent::build("):]
    start = build.index("N3.1: differing attachment states")
    check = build[start:build.index("if (!ok)", start)]
    assert content.count("N3.1: differing attachment states") == 1
    assert "perTargetBlendReal(rhi, &why)" in check
    # Negative control: the check as it stood (QRhi's flag, which Vulkan reports true whatever the device) is gone.
    assert "isFeatureSupported(QRhi::PerRenderTargetBlending)" not in check
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    real = stages[stages.index("bool perTargetBlendReal("):stages.index("// ----", stages.index("bool perTargetBlendReal("))]
    vulkan = real[real.index("if (rhi->backend() == QRhi::Vulkan)"):real.index("if (rhi->isFeatureSupported")]
    assert 'device.value(QStringLiteral("independent_blend")).toBool(false)' in vulkan
    assert "PerRenderTargetBlending" not in vulkan
    facts = (CORE / "src" / "vulkan_context.cpp").read_text(encoding="utf-8")
    assert 'facts.insert(QStringLiteral("independent_blend"), f2.features.independentBlend == VK_TRUE);' in facts
    assert "f2.features.independentBlend = VK_FALSE; // N3.4, harness only" in facts
