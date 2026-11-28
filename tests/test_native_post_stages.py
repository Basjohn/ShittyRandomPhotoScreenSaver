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
    assert "RhiOwned<QRhiTexture> levels[kBloomLevels];" in header
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
    """D17 choice G: QRhi's generateMips for the defocus layer (its two attachments, in the defocus step); ABI 33 (N5.4)
    adds one other scene-target chain, a self-mipped target's read attachments after its run, made by the core's box
    kernel (shaders/mip_box.comp, the Python reference's text too), not generateMips: never a bloom or HDR chain.
    ABI 35: the item textures' chains are the box kernel's too (the lead's decision of 21 Nov), on both upload routes."""
    content = (CORE / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    record = content[content.index("void ModeContent::recordDefocus("):content.index("bool ModeContent::syncTargets(")]
    assert record.count("->generateMips(") == 2
    # ABI 35: no other generateMips: an item texture's chain (in the frame, or after a job's import) is the kernel's.
    assert content.count("->generateMips(") == 2
    assert "generateMips(" not in (CORE / "src" / "job_service.cpp").read_text(encoding="utf-8")
    assert "generateMips(" not in (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8").replace(
        "never generateMips", "")
    # ABI 33: the scene targets' one chain is generateSelfMips, gated on a self-mipped single-sampled target and an
    # attachment read at its levels, through the core's one kernel owner (mip_chain.h, ABI 35), called once, after a
    # run of passes on a target; the kernel dispatches once a level, each level its own compute pass.
    targets = (CORE / "src" / "scene_targets.cpp").read_text(encoding="utf-8")
    own = targets[targets.index("int SceneTargets::generateSelfMips("):
                  targets.index("int SceneTargets::Target::chainBindings(")]
    assert "generateMips(" not in targets
    assert "!t->decl.selfMips" in own and ".mipsRead" in own and "m_chainKernel.record(cb, t->chain[c]);" in own
    kernel = (CORE / "src" / "mip_chain.cpp").read_text(encoding="utf-8")
    recorded = kernel[kernel.index("void MipChainKernel::record("):kernel.index("void MipChainKernel::release(")]
    assert recorded.count("cb->dispatch(") == recorded.count("cb->beginComputePass();") == 1
    assert "for (int level = 1; level < chain.levels; ++level)" in recorded
    assert "imageStore(1, cs, texture, level)" in kernel and "imageLoad(0, cs, texture, level - 1)" in kernel
    assert "mip_box_comp_qsb" in kernel and "mip_box_rgba8_comp_qsb" in kernel and "generateMips(" not in kernel
    passes = content[content.index("void ModeContent::recordPasses("):content.index("bool ModeContent::record(")]
    assert content.count("generateSelfMips(") == passes.count("generateSelfMips(") == 1
    # ABI 36 (N5.2c): the photo environment's copy gets its levels from the same kernel, after its copy pass, its
    # bindings made with its texture (MipMapped | UsedWithLoadStore).
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    environment = stages[stages.index("bool PostStages::recordEnvironment("):]
    environment = environment[:environment.index("\n}\n")]
    assert environment.index("cb->endPass();") < environment.index("m_environmentChains.record(cb, e->chain);")
    synced = stages[stages.index("bool PostStages::syncEnvironments("):stages.index("bool PostStages::environmentBindings(")]
    assert "m_environmentChains.bind(rhi, e.texture.get(), spec.size, &e.chain," in synced
    assert "QRhiTexture::UsedWithLoadStore" in synced and "UsedWithGenerateMips" not in synced


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


def test_the_defocus_read_level_cap_keeps_reads_on_even_built_levels() -> None:
    """The lead's cap (15 Nov): two levels above the last level made only from even-sized levels; the core's function
    and the harness's mirror agree, and the sync refuses past it."""
    import sys

    sys.path.insert(0, str(CORE / "python"))
    import post_stages

    assert post_stages.read_level_cap((640, 384)) == 5        # 5 x 3 is level 7, made from 10 x 6
    assert post_stages.read_level_cap((64, 64)) == 4          # down to 1 x 1, every level even-built
    assert post_stages.read_level_cap((3840, 2176)) == 5      # 30 x 17 is level 7
    # Negative control: a cap that ignored odd sides would allow 8 at 640 x 384.
    assert post_stages.read_level_cap((640, 384)) != max((640).bit_length() - 2, 0)
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    cap = stages[stages.index("int defocusReadLevelCap("):]
    assert "(s.width() > 1 && s.width() % 2) || (s.height() > 1 && s.height() % 2)" in cap
    assert "return qMax(0, exact - 2);" in cap
    sync = stages[stages.index("bool PostStages::sync("):]
    assert "const int maxLevel = defocusReadLevelCap(layer);" in sync


def test_the_defocus_draw_timer_is_opengl_only_and_off_by_default() -> None:
    """The defocus cost's diagnosis (time_defocus_draws): marks around the gather and the sprites, OpenGL only, nothing
    at all while the control is off (no query object, no external block), results latched (never waited for)."""
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    mark = stages[stages.index("void PostStages::markDefocus("):stages.index("void PostStages::releaseDrawTimer(")]
    assert "if (!m_rhi || m_rhi->backend() != QRhi::OpenGLES2)\n        return;" in mark
    assert "const int control = m_defocusDrawControl;" in mark and "loadAcquire" not in mark
    sync = stages[stages.index("bool PostStages::sync("):stages.index("bool PostStages::build(")]
    assert sync.index("m_defocusDrawControl = g_timeDefocusDraws.loadAcquire();") < sync.index("m_defocusPassFlags =")
    assert "if (rhi->backend() == QRhi::OpenGLES2)" in sync
    assert "if (m_defocusDrawControl & 31)" in sync
    assert "m_defocusPassFlags |= QRhiCommandBuffer::ExternalContent;" in sync
    assert "if (m_defocusDrawControl & 32)" in sync
    assert "m_defocusPassFlags |= QRhiCommandBuffer::DoNotTrackResourcesForCompute;" in sync
    assert mark.index("if (!control)") < mark.index("g_defocusExternalPasses.fetchAndAddRelaxed(1)")
    assert mark.index("if (!control)") < mark.index("g_defocusUntrackedPasses.fetchAndAddRelaxed(1)")
    assert mark.index("if (!control)") < mark.index("if (!(control & 1))") < mark.index("std::make_unique<DrawTimer>()")
    boundary = mark[mark.index("if (!(control & 1))"):mark.index("if (!m_drawTimer)")]
    assert boundary.index("cb->beginExternal();") < boundary.index("cb->endExternal();") < boundary.index("return;")
    assert "kGlQueryResultAvailable" in mark and "GL_QUERY_RESULT_NO_WAIT" not in mark
    onto = stages[stages.index("void PostStages::recordDefocusOnto("):]
    assert onto.index("markDefocus(cb, 0);") < onto.index("cb->draw(3);") < onto.index("markDefocus(cb, 1);") \
        < onto.index("cb->draw(4, sprites);") < onto.index("markDefocus(cb, 2);")
    assert "QAtomicInteger<int> g_timeDefocusDraws { 0 };" in stages
    assert "if (control & (2 << mark))" in boundary


def test_the_core_reads_every_stage_shader_it_bakes() -> None:
    stages = (CORE / "src" / "post_stages.cpp").read_text(encoding="utf-8")
    for name in ("scene_oit_resolve.frag", "scene_oit_resolve_samples.frag", "scene_oit_resolve_sample0.frag",
                 "bloom_down_first.frag", "bloom_down.frag", "bloom_up.frag", "composite_overlay.frag",
                 "composite_overlay_glow.frag", "composite_opaque_glow.frag", "defocus_clip.frag", "defocus_gather.frag",
                 "defocus_sprites.vert", "defocus_sprites.frag",
                 "composite_opaque.frag", "environment.frag"):   # N5.2c
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


def test_the_gl_errors_round_is_a_proof_only_on_a_debug_context_with_an_empty_log() -> None:
    """post_stage_check's gl_errors verdict (N5.2h): a message fails it, and so does a run that could not read the log
    (no debug context, no logger, nothing drawn): a log nobody read proves nothing."""
    import sys

    sys.path.insert(0, str(CORE / "python"))
    import post_stage_check as psc

    clean = {"debug_context": True, "logger": True,
             "cases": {"eb_4x": {"samples": 4, "frames": 4, "messages": []},
                       "eb_1x": {"samples": 1, "frames": 4, "messages": []}}}
    assert psc.gl_errors_verdict(clean)["pass"]
    logged = json.loads(json.dumps(clean))
    logged["cases"]["eb_4x"]["messages"] = ["frame 0: id 1280: GL_INVALID_ENUM error generated."]
    assert not psc.gl_errors_verdict(logged)["pass"]
    for fact in ("debug_context", "logger"):
        assert not psc.gl_errors_verdict(dict(clean, **{fact: False}))["pass"], fact
    assert not psc.gl_errors_verdict(dict(clean, cases={}))["pass"]
    undrawn = json.loads(json.dumps(clean))
    undrawn["cases"]["eb_1x"]["frames"] = 0
    assert not psc.gl_errors_verdict(undrawn)["pass"]


def _bypasses_of_the_sampler_state_helpers(sources: dict) -> list:
    """Every pipeline set not through set*PipelineAdopting, and every explicit setShaderResources(srb) whose previous
    statement is not adoptMultisampleSamplerState(srb)."""
    import re

    found = []
    for name, text in sources.items():
        lines = text.splitlines()
        for number, line in enumerate(lines):
            if re.search(r"\bcb->set(Graphics|Compute)Pipeline\(", line):
                found.append(f"{name}:{number + 1}")
            hit = re.search(r"\bcb->setShaderResources\(([^,)]+)", line)
            if hit and hit.group(1).strip() != "nullptr":
                previous = lines[number - 1].strip() if number else ""
                if not previous.startswith("adoptMultisampleSamplerState("):
                    found.append(f"{name}:{number + 1}")
    return found


def test_every_pipeline_set_and_shader_resource_bind_adopts_the_multisample_sampler_state() -> None:
    """N5.2h (found by N5.6; the lead's 7df944fb build still logged eb_4x 5, eb_band_4x 5, tiles_4x 1 with only the two
    resolves marked): every multisampled texture is a scene target's and reaches shaders through many passes, so every
    pipeline set in the core goes through set*PipelineAdopting (its own bindings: what setShaderResources(nullptr)
    binds) and every explicit bind follows adoptMultisampleSamplerState; the helper acts on OpenGL and sampleCount > 1
    alone. Negative control: one bare cb->setGraphicsPipeline is caught."""
    sources = {path.name: path.read_text(encoding="utf-8") for path in sorted((CORE / "src").glob("*.cpp"))
               if path.name != "gl_sampler_state.cpp"}
    assert _bypasses_of_the_sampler_state_helpers(sources) == []
    assert sum(text.count("setGraphicsPipelineAdopting(cb, ") for text in sources.values()) > 10
    altered = dict(sources, **{"mode_content.cpp": sources["mode_content.cpp"].replace(
        "setGraphicsPipelineAdopting(cb, n.pipeline.get());", "cb->setGraphicsPipeline(n.pipeline.get());")})
    assert altered["mode_content.cpp"] != sources["mode_content.cpp"]
    assert len(_bypasses_of_the_sampler_state_helpers(altered)) == 1
    explicit = dict(sources, **{"post_stages.cpp": sources["post_stages.cpp"].replace(
        "    adoptMultisampleSamplerState(e->bindings.get());\n", "", 1)})
    assert explicit["post_stages.cpp"] != sources["post_stages.cpp"]
    assert len(_bypasses_of_the_sampler_state_helpers(explicit)) == 1
    helper = (CORE / "src" / "gl_sampler_state.cpp").read_text(encoding="utf-8")
    assert "rhi->backend() != QRhi::OpenGLES2" in helper and "texture->sampleCount() <= 1" in helper
    assert "src/gl_sampler_state.cpp" in (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
