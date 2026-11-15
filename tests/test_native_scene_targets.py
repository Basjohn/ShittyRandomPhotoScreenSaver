"""N3.1's scene targets (Current_Plan.md item 8b; decision D14), GPU-free.

- The rules in Python (``rendering.native.scene_targets``, the reference the module is held to): the bucket is the
  Python renderer's; the allocation grows at once and shrinks only two or more buckets below (a drag across one bucket
  boundary does not thrash; control: a rule that re-buckets at every change thrashes); the content viewport puts the
  content at the image's bottom rows on OpenGL (F1's flipped core targets) and Vulkan alike (control: one viewport for
  both backends puts it at the top on OpenGL); the clamp.
- The one sampling request owner (``rendering.gl_programs.scene3d.scene_samples``): every Visualizer consumer's request
  is the expression it had before, for every tier (pixels do not move); fixed requests ignore the tier.
- The Python face's declarations (``rendering.native.mode``): targets, passes on targets, captures.
- On the built module (``release/native_module``, compiled only on GitHub; these skip without it): its GPU-free rules
  equal the Python reference, and the program admission's refusals with their reasons.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from rendering.gl_programs.scene3d import SCENE3D_DETAIL_TIERS, scene_samples
from rendering.native import loader
from rendering.native.mode import CapturePass, ModePass, ModeTarget, PassOutput, PassSampler, TargetAttachment, \
    program_json
from rendering.native.scene_targets import (SCENE_BUCKET, bucket_pixels, clamp_samples, content_rows, content_viewport,
                                            next_allocation)

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))


# ------------------------------------------------------------------------------------------------- the rules

def test_the_bucket_is_the_python_renderers():
    from rendering.quick.scene3d import target

    assert SCENE_BUCKET == target.SCENE_TARGET_BUCKET
    for pixels in range(1, 4400, 7):
        assert bucket_pixels(pixels) == target._bucket(pixels)


def _drag(rule, sizes):
    """Reallocations of a target dragged through ``sizes`` (each the content's (w, h)) under ``rule``."""
    current, count = (0, 0), 0
    for size in sizes:
        allocation, reason = rule(current, size)
        assert allocation[0] >= size[0] and allocation[1] >= size[1], "an allocation always covers its content"
        if allocation != current:
            count += 1
        current = allocation
    return count


def _rebucket_every_change(current, needed):
    """The control: an allocation that follows the needed size's bucket both ways at once."""
    bucketed = (bucket_pixels(needed[0]), bucket_pixels(needed[1]))
    return bucketed, "" if bucketed == tuple(current) else "changed"


def test_the_allocation_grows_at_once_and_shrinks_only_two_buckets_below():
    assert next_allocation((0, 0), (100, 70)) == ((128, 128), "made")
    assert next_allocation((128, 128), (129, 70)) == ((192, 128), "grown")      # one axis past: grown at once
    assert next_allocation((128, 128), (128, 128)) == ((128, 128), "")
    assert next_allocation((256, 256), (130, 250)) == ((256, 256), "")          # one bucket below: kept
    assert next_allocation((256, 256), (128, 250)) == ((128, 256), "shrunk")    # two buckets below on one axis
    assert next_allocation((1024, 640), (900, 100)) == ((960, 128), "shrunk")


def test_a_drag_across_one_bucket_boundary_does_not_thrash():
    width = 1024                                                                # a bucket boundary
    across = [(w, 500) for w in range(width - 20, width + 21)] * 3 + [(w, 500) for w in range(width + 20, width - 21, -1)]
    assert _drag(next_allocation, across) == 2                                  # made, then grown once; never shrunk
    # The control: re-bucketing at every change reallocates at every crossing of 1024 (the plan's thrash).
    assert _drag(_rebucket_every_change, across) > 4
    # A long drag reallocates at bucket crossings only (800 -> 1000 px, 1 px steps): at most one per bucket passed.
    grow = [(w, 600) for w in range(800, 1001)]
    assert _drag(next_allocation, grow) <= 1 + (bucket_pixels(1000) - bucket_pixels(800)) // SCENE_BUCKET


def _memory_rows(y_up: bool, allocation, viewport) -> tuple[int, int]:
    """The memory rows (row 0 first) a QRhi viewport covers on a core target: on OpenGL the viewport's y counts from
    memory row 0 (F1 flips the core's targets, so memory row 0 is the image's top); elsewhere QRhi turns it into
    allocation height - (y + h) from the top."""
    _x, y, _w, h = viewport
    top = y if y_up else allocation[1] - (y + h)
    return top, top + h


@pytest.mark.parametrize("allocation,content", [((128, 128), (100, 70)), ((1920, 1088), (1900, 1080)),
                                                ((64, 64), (64, 64)), ((320, 192), (301, 131))])
def test_the_content_lies_at_the_images_bottom_rows_on_both_backends(allocation, content):
    rows = content_rows(allocation, content)
    assert rows == (allocation[1] - content[1], allocation[1])
    for y_up in (True, False):                                                  # OpenGL, Vulkan (and D3D)
        viewport = content_viewport(y_up, allocation, content)
        assert viewport[0] == 0 and viewport[2:] == content
        assert _memory_rows(y_up, allocation, viewport) == rows
    # The control: one viewport for every backend (y 0) puts OpenGL's content at the image's top rows.
    if content[1] < allocation[1]:
        assert _memory_rows(True, allocation, (0, 0, *content)) != rows


def test_the_clamp_takes_the_largest_supported_count_not_above_the_request():
    assert clamp_samples([1, 2, 4, 8], 8) == 8
    assert clamp_samples([1, 2, 4], 8) == 4                                     # 8 removed: drawn as 4
    assert clamp_samples([1, 2, 4, 8], 3) == 2
    assert clamp_samples([1], 4) == 1
    assert clamp_samples([], 4) == 1


# ------------------------------------------------------------------------------------------------- the request owner

@pytest.mark.parametrize("tier", list(SCENE3D_DETAIL_TIERS))
def test_every_visualizer_request_is_its_former_expression(tier):
    from rendering.quick.visualizer.implementations.extruded_bubble import _scene_samples
    from rendering.quick.visualizer.implementations.extruded_spectrum import extruded_quality
    from rendering.quick.visualizer.implementations.sphere_voxel import sphere_samples

    detail = SCENE3D_DETAIL_TIERS[tier]
    assert _scene_samples({"scene3d_detail": tier}) == max(1, detail.overlay_samples)
    assert sphere_samples({"scene3d_detail": tier}) == max(1, detail.overlay_samples)
    assert scene_samples(detail) == detail.overlay_samples                      # Neon Lake's (shockwave_quality)
    for smooth in (False, True):
        parameters = {"scene3d_detail": tier, "extruded_spectrum_smooth_edges": smooth,
                      "extruded_spectrum_face_mirror": 0.5, "backdrop": None}
        assert extruded_quality(parameters)[0] == detail.overlay_samples * (2 if smooth else 1)
    # Declared fixed requests ignore the tier (D14 choice D).
    assert scene_samples(detail, fixed=4) == 4 and scene_samples(detail, fixed=1) == 1


def test_the_fixed_requests_are_declared_once_through_the_owner():
    from rendering.quick.scene3d import waveform
    from rendering.quick.visualizer.implementations import oscilloscope

    assert waveform.SCENE_SAMPLES == scene_samples(None, fixed=4)
    assert oscilloscope._SCENE_SAMPLES == scene_samples(None, fixed=1)
    with pytest.raises(ValueError):
        scene_samples(None)                                                     # a tier request needs its tier


# ------------------------------------------------------------------------------------------------- the declarations

def test_the_program_declares_its_targets_and_captures():
    scene = ModeTarget("scene", (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f",
                                                                                         (0.0, 0.0, 0.0, 1.0))),
                       depth=True, samples=4)
    ambient = ModeTarget("ambient", (TargetAttachment("coverage"),), size=(300, 170))
    passes = (ModePass("draw", b"a", "replace", target="scene", outputs=(PassOutput(), PassOutput(False)),
                       depth_test="less", depth_write=True),
              CapturePass("background", "scene"),
              ModePass("show", b"b", "alpha", samplers=(PassSampler("u_scene", "scene.capture_colour"),)))
    declared, packs = program_json(passes, (scene, ambient))
    program = json.loads(declared)
    assert packs == [b"a", b"", b"b"]                                           # a capture has no fragment
    assert program["targets"][0] == {"name": "scene", "size": "surface",
                                     "colour": [{"name": "colour", "format": "rgba16f"},
                                                {"name": "emission", "format": "rgba16f", "clear": [0.0, 0.0, 0.0, 1.0]}],
                                     "depth": True, "samples": 4}
    assert program["targets"][1]["size"] == [300, 170] and "depth" not in program["targets"][1]
    assert program["passes"][0]["target"] == "scene"
    assert program["passes"][0]["attachments"] == [{"write": True}, {"write": False}]
    assert program["passes"][0]["depth"] == {"test": "less", "write": True}
    assert program["passes"][1] == {"name": "background", "capture": "scene"}
    assert "target" not in program["passes"][2]
    # A program with no targets declares as N2.9's did.
    assert set(json.loads(program_json((ModePass("x", b"c"),))[0])) == {"passes"}


def test_the_face_refuses_what_it_can_tell():
    with pytest.raises(ValueError):
        TargetAttachment("colour", "rg16f")                                     # QRhi has no RG16F
    with pytest.raises(ValueError):
        ModeTarget("scene", ())
    with pytest.raises(ValueError):
        ModeTarget("scene", (TargetAttachment("a"),), samples=16)
    with pytest.raises(ValueError):
        ModePass("p", b"", depth_test="sometimes")
    with pytest.raises(ValueError):
        PassOutput(True, "screen")
    with pytest.raises(ValueError):
        TargetAttachment("lin", "r32f", resolve="median")
    with pytest.raises(ValueError):
        TargetAttachment("lin", "rgba16f", resolve="nearest")               # the minimum of one float channel


def test_a_nearest_attachment_declares_its_resolve():
    """D14 point 10 (b): an R32F attachment resolved to the nearest sample says so; the average is the default."""
    target = ModeTarget("lin", (TargetAttachment("colour"), TargetAttachment("lin", "r32f", (1.0, 1.0, 1.0, 1.0),
                                                                             resolve="nearest")), depth=True, samples=4)
    colour, lin = target.declaration()["colour"]
    assert "resolve" not in colour
    assert lin == {"name": "lin", "format": "r32f", "clear": [1.0, 1.0, 1.0, 1.0], "resolve": "nearest"}


# ------------------------------------------------------------------------------------------------- the built module

built = pytest.mark.skipif(
    not BUILT, reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")


@pytest.fixture(scope="module")
def core():
    from rendering import native

    loaded = native.load(MODULE_DIR)
    if loaded.abi < 17:
        pytest.skip(f"the built module speaks ABI {loaded.abi}; scene targets are ABI 17")
    return loaded


@built
def test_the_modules_rules_are_the_python_reference(core):
    for current in ((0, 0), (128, 128), (256, 192), (1024, 640)):
        for needed in ((1, 1), (100, 70), (129, 70), (130, 250), (128, 250), (900, 100), (1025, 641)):
            assert core.scene_target_next_allocation(current, needed) == next_allocation(current, needed)
    for allocation, content in (((128, 128), (100, 70)), ((320, 192), (301, 131)), ((64, 64), (64, 64))):
        for y_up in (True, False):
            assert core.scene_target_viewport(y_up, allocation, content) == content_viewport(y_up, allocation, content)
    for supported in ([1, 2, 4, 8], [1, 2, 4], [1], []):
        for requested in range(1, 9):
            assert core.scene_target_clamp(supported, requested) == clamp_samples(supported, requested)


@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    import scene_targets

    return scene_targets.bake_all(tmp_path_factory.mktemp("scene_targets"))


@built
@pytest.mark.qt
def test_the_harness_program_is_admitted_with_its_reads(core, packs, qt_app):
    import scene_targets

    layout = core.mode_program_layout(scene_targets.passes(packs), scene_targets.targets(samples=4))
    scene, ambient = layout["targets"]
    assert scene["capture"] and scene["depth_read"] and scene["colour"][0]["read"]
    assert not scene["colour"][1]["read"]                                       # emission: never sampled
    assert ambient["colour"][0]["read"] and ambient["colour"][1]["read"]
    by_name = {p["name"]: p for p in layout["passes"]}
    assert by_name["planes"]["frag_depth"] and by_name["planes"]["target"] == "scene"
    assert by_name["background"]["capture"]
    assert by_name["show"]["target"] == "surface"
    assert [a["blend"] for a in by_name["ambient"]["attachments"]] == ["premultiplied", "additive"]


def _refused(core, passes, targets, fragment: str):
    with pytest.raises(ValueError) as caught:
        core.mode_program_layout(passes, targets)
    assert fragment in str(caught.value), str(caught.value)


@built
@pytest.mark.qt
def test_the_admission_refuses_with_its_reasons(core, packs, qt_app):
    import scene_targets

    scene, ambient = scene_targets.targets()
    no_depth = ModeTarget("scene", scene.colour)
    planes = ModePass("planes", packs["planes"], "replace", target="scene", depth_test="always", depth_write=True)
    # Admitted as declared (the control of every refusal below).
    core.mode_program_layout((planes,), (scene,))
    _refused(core, (ModePass("planes", packs["planes"], "replace", target="nowhere"),), (scene,), "no declared target")
    _refused(core, (planes,), (no_depth,), "depth")                             # a depth state without a depth
    _refused(core, (ModePass("planes", packs["planes"], "replace", target="scene"),), (no_depth,), "gl_FragDepth")
    _refused(core, (ModePass("planes", packs["planes"], "replace"),), (scene,), "one vec4 at location 0")
    _refused(core, (ModePass("planes", packs["planes"], "replace", target="scene", outputs=(PassOutput(),),
                             depth_test="always", depth_write=True),), (scene,), "attachments")
    _refused(core, (CapturePass("background", "scene"), planes), (scene,), "before any pass drew")
    show = scene_targets.passes(packs)[-1]
    _refused(core, (planes, show), (scene, ambient), "before a capture step")
    reads_own = ModePass("planes", packs["planes"], "replace", target="scene", depth_test="always", depth_write=True,
                         samplers=(PassSampler("u_x", "scene.colour"),))
    _refused(core, (reads_own,), (scene,), "the target the pass draws into")     # never its own target's attachment
    _refused(core, (planes, ModePass("show", packs["show"], "replace", samplers=(
        PassSampler("u_scene", "scene.colour", mips="linear"), PassSampler("u_depth", "scene.depth"),
        PassSampler("u_cover", "ambient.coverage"), PassSampler("u_light", "ambient.light")))), (scene, ambient),
             "no mips")
    _refused(core, (planes, ModePass("show", packs["show"], "replace", samplers=(
        PassSampler("u_scene", "scene.velocity"), PassSampler("u_depth", "scene.depth"),
        PassSampler("u_cover", "ambient.coverage"), PassSampler("u_light", "ambient.light")))), (scene, ambient),
             "has no attachment")


@built
@pytest.mark.qt
def test_a_new_program_clears_the_sizes_set_before_it(core, packs, qt_app):
    """Audit 2, M3: an explicit size set through ``target_size`` holds until the next program, whose declarations size
    its targets (before the fix the old size went on being drawn: the audit's probe drew 400 x 220 for a program
    declaring 500 x 280)."""
    import scene_targets
    from PySide6.QtQuick import QQuickItem

    parent = QQuickItem()
    mode = core.mode(parent)
    try:
        mode.still()
        settings = scene_targets.settings(ambient_size=(300, 170))
        mode.program(scene_targets.passes(packs), settings, targets=scene_targets.targets(ambient_size=(300, 170)))
        assert mode.state()["target_sizes"] == {}
        mode.target_size("ambient", (400, 220))
        assert mode.state()["target_sizes"] == {"ambient": [400, 220]}       # the control: the size is held
        mode.program(scene_targets.passes(packs), settings, targets=scene_targets.targets(ambient_size=(500, 280)))
        assert mode.state()["target_sizes"] == {}
        declared = {t["name"]: t["size"] for t in mode.state()["program"]["targets"]}
        assert declared["ambient"] == [500, 280]
        # A refused program keeps the program and the sizes set for it.
        mode.target_size("ambient", (410, 230))
        with pytest.raises(ValueError):
            mode.program(scene_targets.passes(packs), {"u_no_such_member": 1.0},
                         targets=scene_targets.targets(ambient_size=(520, 290)))
        assert mode.state()["target_sizes"] == {"ambient": [410, 230]}
    finally:
        mode.composite.destroy()


@built
@pytest.mark.qt
def test_the_nearest_resolve_is_admitted_where_it_applies(core, packs, qt_app):
    """D14 point 10: the lin program (a nearest R32F attachment and a sampled depth) is admitted with both read; a
    nearest attachment in first place (the capture's averaged colour) is refused with its reason."""
    import scene_targets

    passes, targets, _values = scene_targets.lin_program(packs, samples=4, mask_band=0.08)
    (lin,) = core.mode_program_layout(passes, targets)["targets"]
    assert lin["depth_read"] and lin["depth_sampled"]
    assert lin["colour"][1]["read"] and lin["colour"][1]["resolve"] == "nearest"
    assert not lin["colour"][0]["read"] and lin["colour"][0]["resolve"] == "average"
    first = ModeTarget("lin", (TargetAttachment("lin", "r32f", resolve="nearest"), TargetAttachment("colour")),
                       depth=True, samples=4)
    _refused(core, passes[:1], (first,), "past the first")
