"""N5.4 (ABI 33): Waveform's five C++ boxes, GPU-free (Current_Plan.md N5.4; ``native/core/src/abi.h`` 33).

- The face and the core agree on the new limits (passes, storage images, targets) and they hold Waveform's counts.
- A drawable mipped target: ``allocation`` ``"exact"``, a depth and an explicit size on a mipped target; an RGBA16F
  item texture sent with its flag; the face refuses what the core would.
- The core's sources: the exact allocation, the self-mipped chain after a run made by the core's box kernel (one text
  with the Python reference's, an RGBA16F attachment read at its levels only), the defocus layer kept to D17 G and H,
  the half-float upload on both routes, the linear-filter check (its Vulkan fact and its harness control); the
  shader-side anisotropy's continuous lattice; the harness scenes bake for every shipped target.
- On the built module (skipped without ``release/native_module`` at ABI 33): the admission, a light shader's two
  outputs refused on the one-attachment reflection, and every refusal one past a limit, with its reason.

The drawn proofs are ``native/core/python/scene_target_check.py --rounds wave_floor wave_limits wave_filter`` (hidden
hosts, both APIs, the Python reference).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "core" / "src"
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
MODULE_DIR = ROOT / "release" / "native_module"


def _source(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def _constant(text: str, name: str) -> int:
    match = re.search(rf"constexpr int {name} = (\d+);", text)
    assert match, name
    return int(match.group(1))


def _function(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end, text.index(start))]


# ------------------------------------------------------------------------------------------- the limits (box 4)

def limits_hold_waveform(mode_h: str, compute_h: str, targets_h: str) -> bool:
    """The core's limits are the face's and hold Waveform's shape (the reading's counts)."""
    import waveform_primitives as wp
    from rendering.native import mode

    passes = _constant(mode_h, "kMaxModePasses")
    images = _constant(compute_h, "kMaxStorageImages")
    targets = _constant(targets_h, "kMaxSceneTargets")
    return (passes == mode.MAX_PASSES and images == mode.MAX_STORAGE_IMAGES and targets == mode.MAX_TARGETS
            and passes >= wp.SHAPE_PASSES and images >= wp.SHAPE_IMAGE_COUNT and targets >= 4
            and passes <= 64)            # a pass's missing meshes are a bit of a quint64 (missingMeshMask)


def test_the_limits_are_the_faces_and_hold_waveforms_shape():
    assert limits_hold_waveform(_source("mode_content.h"), _source("compute_passes.h"), _source("scene_targets.h"))
    # Negative control: the ABI 31 limits (16 passes, 8 images) do not hold Waveform's shape.
    old_mode = re.sub(r"constexpr int kMaxModePasses = \d+;", "constexpr int kMaxModePasses = 16;",
                      _source("mode_content.h"))
    old_compute = re.sub(r"constexpr int kMaxStorageImages = \d+;", "constexpr int kMaxStorageImages = 8;",
                         _source("compute_passes.h"))
    assert not limits_hold_waveform(old_mode, _source("compute_passes.h"), _source("scene_targets.h"))
    assert not limits_hold_waveform(_source("mode_content.h"), old_compute, _source("scene_targets.h"))


def test_the_shape_program_is_waveforms_count_and_one_past_each_limit():
    import waveform_primitives as wp
    from rendering.native import mode

    packs = {name: b"X" for name in wp.texts()}
    layers = {"eb_layer1": b"L", "eb_layer1_sorted": b"S"}
    passes, targets, images = wp.shape_program(packs, layers)
    assert (len(passes), len(images), len(targets)) == (wp.SHAPE_PASSES, wp.SHAPE_IMAGE_COUNT, 4)
    assert sum(1 for p in passes if isinstance(p, mode.ComputePass)) == 7
    passes, _targets, images = wp.shape_program(packs, layers, extra_pass=True, extra_image=True)
    assert len(passes) == mode.MAX_PASSES + 1 and len(images) == mode.MAX_STORAGE_IMAGES + 1


# ------------------------------------------------------------------------------------------- the face (boxes 1 and 3)

def test_a_drawable_mipped_target_declares_its_exact_allocation():
    from rendering.native.mode import ModeTarget, TargetAttachment, program_json

    colour = (TargetAttachment("colour", "rgba16f"),)
    reflection = ModeTarget("reflection", colour, size=(333, 187), depth=True, mips=True, allocation="exact")
    declared = json.loads(program_json((), (reflection,))[0])["targets"][0]
    assert declared["mips"] is True and declared["depth"] is True and declared["allocation"] == "exact"
    assert declared["size"] == [333, 187]
    # D14 point 2's buckets stay the default (no key: the declaration as it was).
    assert "allocation" not in ModeTarget("scene", colour).declaration()
    # Negative controls: an unknown rule, and a mipped multisampled or previous-frame target, are refused here.
    with pytest.raises(ValueError):
        ModeTarget("x", colour, allocation="tight")
    with pytest.raises(ValueError):
        ModeTarget("x", colour, mips=True, samples=4)
    with pytest.raises(ValueError):
        ModeTarget("x", colour, mips=True, previous_frame=True)


def test_the_light_shaders_reach_the_one_attachment_reflection_as_their_one_output_variant():
    """Vulkan names a pipeline whose shader writes past its target's attachments (Undefined-Value-
    ShaderOutputNotConsumed), so the core refuses it: Waveform's light shaders, which write colour and emission, are
    drawn into the reflection as the same text with ``WAVE_ONE_OUTPUT`` defined (the port's wrapper file)."""
    import waveform_primitives as wp

    sky = wp.one_output(wp.texts()["refl_sky"])
    assert sky.splitlines()[0].startswith("#version") and "\n#define WAVE_ONE_OUTPUT\n" in sky
    assert sky.replace("\n#define WAVE_ONE_OUTPUT", "") == wp.texts()["refl_sky"]
    assert set(wp.ONE_OUTPUT) == {"refl_sky", "refl_light"}
    for name in wp.ONE_OUTPUT:
        assert "#ifndef WAVE_ONE_OUTPUT" in wp.texts()[name]
    # Negative control: the refusal round's text is the two-output file itself.
    assert "#define WAVE_ONE_OUTPUT" not in wp.texts()["refl_sky_two_outputs"]


def test_a_half_float_texture_is_sent_with_its_flag_and_rgba8_as_before():
    from rendering.native.composite import CompositeItem
    from rendering.native.mode import NativeMode

    calls: list = []

    class Module:
        def __getattr__(self, name):
            def call(*args):
                calls.append((name, args))
            return call

    module = Module()
    mode = NativeMode(module, CompositeItem(module, 5))
    mode.texture("slope", b"\0" * 32, (2, 2), mips=True, format="rgba16f")
    mode.texture("map", b"\0" * 16, (2, 2), mips=True)
    assert calls[0] == ("composite_mode_texture", (5, "slope", (2, 2), b"\0" * 32, True, False, True))
    assert calls[1] == ("composite_mode_texture", (5, "map", (2, 2), b"\0" * 16, True))   # ABI 32's call, unchanged
    with pytest.raises(ValueError):
        mode.texture("x", b"\0" * 16, (2, 2), format="rgb10a2")


# ------------------------------------------------------------------------------------------- the core's sources

def exact_allocation_is_wired(targets_cpp: str) -> bool:
    sync = _function(targets_cpp, "bool SceneTargets::sync(", "bool SceneTargets::complete(")
    same = _function(targets_cpp, "bool TargetDeclaration::sameLayout(", "int TargetDeclaration::colourIndex(")
    return ("d.exact ? exactAllocation(" in sync and "exact != o.exact" in same
            and 'QStringLiteral("allocation")' in targets_cpp)


def test_an_exact_target_is_allocated_at_its_content_and_is_a_layout():
    assert exact_allocation_is_wired(_source("scene_targets.cpp"))
    exact = _function(_source("scene_targets.cpp"), "QSize exactAllocation(", "QRect contentViewport(")
    assert "return exact;" in exact and "bucketPixels" not in exact
    # Negative control: the bucket rule in its place is caught.
    assert not exact_allocation_is_wired(_source("scene_targets.cpp").replace("d.exact ? exactAllocation(", "("))


def self_mips_are_wired(mode_cpp: str) -> bool:
    parse = _function(mode_cpp, "bool ModeProgram::fromJson(", "QJsonObject ModeProgram::toJson(")
    passes = _function(mode_cpp, "void ModeContent::recordPasses(", "bool ModeContent::record(")
    run = passes[passes.index("recordNearest(cb, runTarget, last, readback);"):]
    return ("target.selfMips = target.mips && !layer;" in parse and "read.colour[colour].mipsRead = true;" in parse
            and "generateSelfMips(" in run and run.index("generateSelfMips(") < run.index("i = last + 1;")
            and "m_reason = chainError;" in run)


def test_a_self_mipped_target_makes_its_chain_after_its_run_and_the_defocus_layer_keeps_d17():
    mode_cpp = _source("mode_content.cpp")
    assert self_mips_are_wired(mode_cpp)
    stage = _function(mode_cpp, "bool parseStageStep(", "bool ModeProgram::fromJson(")
    assert "!layer.surfaceSized() || layer.exact || layer.depth" in stage
    sampler = _function(mode_cpp, "bool checkTargetSampler(", "int inputComponents(")
    assert "!t.mips || capture" in sampler                       # mips of a target without them are refused
    # Negative control: the chain dropped from the run is caught.
    run = "m_targets.generateSelfMips(rhi, cb, runTarget, &chained, &chainError);"
    assert mode_cpp.count(run) == 1 and not self_mips_are_wired(mode_cpp.replace(run, ""))


def box_chain_is_wired(targets_cpp: str, mode_cpp: str, kernel: str, chain_cpp: str = "") -> bool:
    """A self-mipped target's chain is the core's box kernel, one text with the Python reference's
    (``rendering/gl_programs/mip_chain.py``): never QRhi's generateMips, whose GL chain is the driver's (NVIDIA's
    non-power-of-two reduction is anchored at memory row 0, the core's top row and Python's bottom one) and whose
    Vulkan chain is one bilinear tap a texel; the box kernel's odd-size weights are symmetric, so neither the storage
    orientation nor the driver moves a level. ABI 35: through the core's one kernel owner (``mip_chain.cpp``)."""
    from rendering.gl_programs.mip_chain import MIP_BOX_COMP

    chain_cpp = chain_cpp or _source("mip_chain.cpp")
    if "int SceneTargets::Target::chainBindings(" not in targets_cpp:
        return False                          # no kernel owner of the core's own (before ABI 35)
    chain = _function(targets_cpp, "int SceneTargets::generateSelfMips(", "int SceneTargets::Target::chainBindings(")
    parse = _function(mode_cpp, "bool ModeProgram::fromJson(", "QJsonObject ModeProgram::toJson(")
    return (kernel == MIP_BOX_COMP and "generateMips(" not in targets_cpp and "generateMips(" not in chain_cpp
            and "m_chainKernel.bind(rhi, t->colour[c].get(), t->allocation, &t->chain[c], error)" in chain
            and "mip_box_comp_qsb" in chain_cpp and "imageLoad(0, cs, texture, level - 1)" in chain_cpp
            and "flags |= QRhiTexture::UsedWithLoadStore;" in targets_cpp
            and "rgba16f attachment only" in parse and "precise vec4" in kernel)


def test_a_self_mipped_targets_chain_is_the_shared_box_kernel():
    kernel = (ROOT / "native" / "core" / "shaders" / "mip_box.comp").read_text(encoding="utf-8")
    assert box_chain_is_wired(_source("scene_targets.cpp"), _source("mode_content.cpp"), kernel)
    # The odd-size weights: three taps (d - i, d, i + 1) / (2d + 1), symmetric under a flip of the source.
    assert "vec3(float(d - i), float(d), float(i + 1)) / float(s)" in kernel
    # Negative controls: the kernel's text drifting from the reference's, and QRhi's chain in its place, are caught.
    assert not box_chain_is_wired(_source("scene_targets.cpp"), _source("mode_content.cpp"),
                                  kernel.replace("precise vec4 sum", "vec4 sum"))
    assert not box_chain_is_wired(_source("scene_targets.cpp"), _source("mode_content.cpp"), kernel,
                                  _source("mip_chain.cpp").replace(
                                      "        cb->beginComputePass();\n",
                                      "        cb->resourceUpdate(nullptr); // generateMips(\n"
                                      "        cb->beginComputePass();\n"))


def half_float_is_wired(mode_cpp: str, jobs_cpp: str) -> bool:
    upload = _function(mode_cpp, "bool ModeContent::uploadInFrame(", "RhiOwned<QRhiTexture> ModeContent::importTexture(")
    imported = _function(mode_cpp, "RhiOwned<QRhiTexture> ModeContent::importTexture(", "void ModeContent::adoptImport(")
    return ("modeTextureRhiFormat(image->format)" in upload and "modeTextureBytes(image->size" in upload
            and "modeTextureRhiFormat(job.format)" in imported
            and "modeTextureRhiFormat(job.format)" in jobs_cpp and "QRhiTexture::RGBA8, job.size" not in jobs_cpp)


def test_a_half_float_texture_takes_its_format_on_both_upload_routes():
    assert half_float_is_wired(_source("mode_content.cpp"), _source("job_service.cpp"))
    setter = _function(_source("mode_content.cpp"), "bool ModeSource::setTexture(", "bool ModeSource::removeTexture(")
    assert "modeTextureTexelBytes(format)" in setter               # 8 bytes a texel for RGBA16F, refused otherwise
    # Negative control: the job route left at RGBA8 is caught.
    assert not half_float_is_wired(_source("mode_content.cpp"), _source("job_service.cpp").replace(
        "modeTextureRhiFormat(job.format)", "QRhiTexture::RGBA8"))


def linear_filter_is_checked(mode_cpp: str, vulkan_cpp: str) -> bool:
    build = _function(mode_cpp, "bool ModeContent::build(", "const QShader vs = shaderFrom(mode_vert_qsb")
    return ("storageImageLinearFilter(rhi, image->format, &why)" in build
            and "VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT" in vulkan_cpp
            and 'QStringLiteral("linear_filter_formats")' in vulkan_cpp)


def test_a_linear_sampler_over_a_storage_image_is_checked_against_the_device():
    assert linear_filter_is_checked(_source("mode_content.cpp"), _source("vulkan_context.cpp"))
    compute = _source("compute_passes.cpp")
    check = _function(compute, "bool storageImageLinearFilter(", "QJsonObject computeDeviceFacts(")
    assert "computeNoFloat32Linear()" in check and "QRhiTexture::RGBA32F" in check and "QRhiTexture::R32F" in check
    assert '"no_float32_linear"' in _source("module.cpp")
    # Negative control: the build without its check is caught.
    assert not linear_filter_is_checked(_source("mode_content.cpp").replace(
        "storageImageLinearFilter(rhi, image->format, &why)", "true"), _source("vulkan_context.cpp"))


def test_the_abi_is_35_or_later_on_both_sides():
    # ABI 33's boxes, at ABI 35 since the Waveform port's two core gaps (tests/test_native_waveform_port_core.py), kept
    # by a later ABI (36: N5.2c).
    import re

    defined = int(re.search(r"#define SRPSS_NATIVE_CORE_ABI (\d+)", _source("abi.h")).group(1))
    assert defined >= 35 and loader.EXPECTED_ABI == defined


# ------------------------------------------------------------------------------------------- the harness scenes

def test_the_harness_scenes_bake_for_every_shipped_target(tmp_path):
    import waveform_primitives as wp

    packs = wp.bake_all(tmp_path)
    assert set(packs) == set(wp.texts()) and all(packs.values())
    # The floor reads the shared anisotropic text (one text for both renderers).
    from rendering.gl_programs.anisotropic import ANISOTROPIC_GLSL

    assert ANISOTROPIC_GLSL in wp.floor_text()


def anisotropy_is_continuous(text: str) -> bool:
    """The footprint's ratio r = Pmax / Pmin (up to the maximum) covered by taps on a fixed lattice one minor width
    apart, symmetric about the coordinate, each weighted by its overlap with [-r/2, r/2] and filtered at the minor
    axis's footprint: continuous in the gradients (no tap count jumping at an integer ratio, which moved pixels by
    several levels between the two renderers) and blind to the gradients' signs, which differ between backends."""
    return ("float r = clamp(pMax / max(pMin, 1e-8), 1.0, min(maxAnisotropy," in text
            and "float w = max(0.0, min(t + 0.5, 0.5 * r) - max(t - 0.5, -0.5 * r));" in text
            and "textureGrad(tex, uv + stepUv * t, stepUv, minor)" in text and "return sum / r;" in text
            and "ceil(pMax" not in text)


def test_the_anisotropic_taps_are_continuous_in_the_footprint():
    from rendering.gl_programs.anisotropic import ANISOTROPIC_GLSL, ANISOTROPIC_MAX_TAPS

    assert anisotropy_is_continuous(ANISOTROPIC_GLSL)
    assert f"min(maxAnisotropy, {ANISOTROPIC_MAX_TAPS}.0)" in ANISOTROPIC_GLSL
    reach = (ANISOTROPIC_MAX_TAPS - 1) // 2
    assert f"for (int j = -{reach}; j <= {reach}; ++j)" in ANISOTROPIC_GLSL
    # The weights cover the footprint exactly: they sum to r for every ratio the clamp admits.
    for r in (1.0, 1.3, 2.0, 2.5, 7.99, float(ANISOTROPIC_MAX_TAPS)):
        reach_r = math.ceil((r - 1.0) * 0.5)
        total = sum(max(0.0, min(t + 0.5, 0.5 * r) - max(t - 0.5, -0.5 * r)) for t in range(-reach_r, reach_r + 1))
        assert total == pytest.approx(r)
    # Negative control: the integer tap count in its place is caught.
    assert not anisotropy_is_continuous(ANISOTROPIC_GLSL.replace(
        "int reach = int(ceil((r - 1.0) * 0.5));", "float n = ceil(pMax / max(pMin, 1e-8));"))


# ------------------------------------------------------------------------------------------- the built module

BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()


@pytest.fixture(scope="module")
def core():
    if not BUILT:
        pytest.skip(f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")
    from rendering import native

    try:
        return native.load(MODULE_DIR)
    except native.NativeCoreUnavailable as exc:
        pytest.skip(f"the built module is not this checkout's: {exc.reason}")


@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    import waveform_primitives as wp

    return wp.bake_all(tmp_path_factory.mktemp("wave"))


def _layout(core, passes, targets=(), images=()):
    from rendering.native.mode import program_json

    declared, program_packs = program_json(passes, targets, (), (), images)
    return json.loads(core.module.mode_program_layout(declared, program_packs))


def test_the_built_core_admits_the_floor_scene_with_its_self_mipped_exact_reflection(core, packs):
    import waveform_primitives as wp

    passes, targets = wp.floor_program(packs)
    layout = _layout(core, passes, targets)
    reflection = layout["targets"][0]
    assert reflection["self_mips"] is True and reflection["allocation"] == "exact" and reflection["depth"] is True
    assert reflection["colour"][0]["mips_read"] is True
    # Negative control: the light shader's two-output file on the one-attachment reflection is refused.
    two, _ = wp.floor_program(dict(packs, refl_sky=packs["refl_sky_two_outputs"]))
    with pytest.raises(ValueError, match="location 1"):
        _layout(core, two, targets)


def test_the_built_core_admits_waveforms_shape_and_refuses_one_past_each_limit(core, packs, tmp_path):
    import post_stages
    import waveform_primitives as wp

    layers = post_stages.bake_all(tmp_path)
    passes, targets, images = wp.shape_program(packs, layers)
    layout = _layout(core, passes, targets, images)
    assert len(layout["passes"]) == wp.SHAPE_PASSES
    passes, targets, images = wp.shape_program(packs, layers, extra_pass=True)
    from rendering.native.mode import MAX_PASSES
    with pytest.raises(ValueError, match=f"1 to {MAX_PASSES} passes"):
        _layout(core, passes, targets, images)
    passes, targets, images = wp.shape_program(packs, layers, extra_image=True)
    with pytest.raises(ValueError, match="at most 9 storage images"):
        _layout(core, passes, targets, images)
