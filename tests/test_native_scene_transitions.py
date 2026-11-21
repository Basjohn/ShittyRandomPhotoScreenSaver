"""N5.2c: the 3D transitions drawn as scenes (``NativeScenePasses``: Blinds, Cube Turn, Depth Card Cascade, Jigsaw) give
the native core programs it can draw from data alone. GPU-free, against the Python renderers' own texts:

- every member of every pass's block is filled by the core's members or the frame's ``scene_values`` (the core refuses
  an unfilled member), and every value is a member some pass of the run declares (it refuses an unknown setting);
- every vertex input of a pass is an attribute of the mesh it draws (bound by name);
- every sampler a pass declares names exactly the shader's samplers (an unknown or unbound sampler is refused);
- the program the layer builds (``scene_program``) is N4.j's environment step first when a pass reads it, the passes
  into the scene target, the opaque composite last, and its packs are the committed bakes of the same texts.

The drawn proof is ``native/core/python/transition_route_check.py`` (``N52C_VARIANTS``, hidden hosts, both backends).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from rendering.quick.image_state import PresentationImage

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "native" / "core" / "python"
_BLOCK = re.compile(r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+(\w+)\s*\{(.*?)\}\s*;", re.S)
_MEMBER = re.compile(r"^\s*\w+\s+(\w+)\s*(?:\[[^\]]*\])?\s*;", re.M)
_INPUT = re.compile(r"layout\s*\(\s*location\s*=\s*\d+\s*\)\s*in\s+\w+\s+(\w+)\s*;")
_SAMPLER = re.compile(r"uniform\s+sampler2D\s+(\w+)\s*;")
_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def _trc():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    import importlib

    return importlib.import_module("transition_route_check")


def _image(identity: str, size: tuple[int, int] = (64, 36)) -> PresentationImage:
    width, height = size
    return PresentationImage(identity=identity, source_path="", logical_size=(float(width), float(height)),
                             device_pixel_ratio=1.0, pixel_size=size, row_stride=width * 4,
                             rgba8=bytes((40, 80, 120, 255)) * (width * height))


def _members(text: str) -> set[str]:
    """The members of the text's own pass block (every std140 block but the conventions')."""
    names: set[str] = set()
    for binding, _name, body in _BLOCK.findall(_COMMENT.sub("", text)):
        if int(binding) != 17:
            names.update(_MEMBER.findall(body))
    return names


def _run(variant: str):
    trc = _trc()
    return trc.production_run(variant, [_image("old"), _image("new")], 1)


def _renderer(transition_id: str):
    from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer

    return resolve_quick_transition_renderer(transition_id, enabled_transition_ids=frozenset({transition_id}))


VARIANTS = tuple(_trc().SCENE_VARIANTS)
LOGICAL = (1600.0, 900.0)
PIXELS = (2400, 1350)                       # the item's device pixels at dpr 1.5 (N5.2d: the motion's uViewport)


def _program_members(scene) -> dict[str, set[str]]:
    """Each drawn pass of the scene's program by its name in the program -> its block's members (N5.2d: a ghost pass is
    one pass a ghost; the trails' edges and the motion blur's tile max and gather are the shared post passes)."""
    from rendering.gl_programs.scene3d import SCENE3D_TRAIL_GHOSTS
    from rendering.quick.transitions.native_scene import (MOTION_GATHER, MOTION_TILE_MAX, ghost_pass_name,
                                                          motion_post_sources)

    post = {name.rsplit(".", 1)[0]: text for name, text in motion_post_sources().items()}
    found: dict[str, set[str]] = {}
    for scene_pass in scene.passes:
        if scene_pass.core_triangle:
            found[scene_pass.name] = _members(post[scene_pass.name])
            continue
        members = _members(scene_pass.vertex_source) | _members(scene_pass.fragment_source)
        names = ([ghost_pass_name(scene_pass.name, age) for age in range(SCENE3D_TRAIL_GHOSTS)]
                 if scene_pass.target == "ghosts" else [scene_pass.name])
        for name in names:
            found[name] = members
    if scene.motion:
        found[MOTION_TILE_MAX] = _members(post[MOTION_TILE_MAX])
        found[MOTION_GATHER] = _members(post[MOTION_GATHER])
    return found


def _count_names(scene) -> set[str]:
    """The settings that fill a pass's draw count (N5.2d: Pixel Accretion's tile instances)."""
    return {count for p in scene.passes for count in (p.vertices, p.instances)
            if isinstance(count, str) and count != "mesh"}


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_member_is_filled_and_every_value_is_declared(variant):
    from rendering.native.mode import MODE_CORE_MEMBERS
    from rendering.quick.render.native_background import scene_settings
    from rendering.quick.transitions.native_scene import SHOW_EFFECT

    run = _run(variant)
    renderer = _renderer(run.request.transition_id)
    scene = renderer.native_scene(run, LOGICAL)
    drawn = _program_members(scene)
    counts = _count_names(scene)
    for progress in (0.05, 0.5, 0.9):
        sample = run.sample(run.start_ns + round(progress * (run.end_ns - run.start_ns)))
        if renderer.scene_show(run, sample) != SHOW_EFFECT:
            continue
        settings = scene_settings(renderer, run, sample, LOGICAL, PIXELS, scene)
        for name, members in drawn.items():
            unfilled = sorted(m for m in members
                              if m not in MODE_CORE_MEMBERS and m not in settings and f"{m}@{name}" not in settings)
            assert not unfilled, f"{variant} {name}: unfilled {unfilled}"
        declared = set().union(*drawn.values())
        unknown = sorted(key for key in settings if key not in counts and (
            key.split("@", 1)[0] not in drawn.get(key.split("@", 1)[1], ()) if "@" in key else key not in declared))
        assert not unknown, f"{variant}: settings no pass declares {unknown}"
        json.dumps(settings)                                  # the core's settings are JSON numbers


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_vertex_input_is_its_meshs_and_every_sampler_the_shaders(variant):
    from rendering.quick.transitions.native_scene import QUAD_MESH, SCENE_TEXTURES

    run = _run(variant)
    scene = _renderer(run.request.transition_id).native_scene(run, LOGICAL)
    meshes = {mesh.name: mesh for mesh in scene.meshes}
    for scene_pass in scene.passes:
        if scene_pass.core_triangle:                            # N5.2d: the core's triangle, no vertex stage
            assert scene_pass.vertex_source is None and all(kind in SCENE_TEXTURES for _n, kind in scene_pass.samplers)
            continue
        inputs = set(_INPUT.findall(_COMMENT.sub("", scene_pass.vertex_source)))
        if scene_pass.mesh == QUAD_MESH:
            attributes = {"aPosition"}
        else:
            mesh = meshes[scene_pass.mesh]
            attributes = {name for name, _n in mesh.attributes} | {name for name, _n in mesh.instance_attributes}
            stride = 4 * sum(n for _name, n in mesh.attributes)
            assert len(mesh.vertices) % stride == 0
        assert inputs <= attributes, f"{variant} {scene_pass.name}: inputs {sorted(inputs - attributes)}"
        shader = set(_SAMPLER.findall(_COMMENT.sub("", scene_pass.vertex_source + scene_pass.fragment_source)))
        assert {name for name, _kind in scene_pass.samplers} == shader, f"{variant} {scene_pass.name}"
        assert all(kind in SCENE_TEXTURES for _name, kind in scene_pass.samplers)
    reads = any(kind == "environment" for p in scene.passes for _name, kind in p.samplers)
    assert scene.environment == reads


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_program_is_the_environment_the_passes_and_the_opaque_composite(variant):
    from rendering.native.mode import CompositeStep, EnvironmentStep, ModePass, program_json
    from rendering.quick.render import native_background as nb
    from rendering.quick.scene3d.environment import environment_size

    from rendering.gl_programs.scene3d import SCENE3D_TRAIL_GHOSTS
    from rendering.quick.transitions.native_scene import MOTION_GATHER, ghost_pass_name

    run = _run(variant)
    renderer = _renderer(run.request.transition_id)
    scene = renderer.native_scene(run, LOGICAL)
    passes, targets, images = nb.scene_program(renderer, scene, nb.TEXTURE, nb.NEXT_TEXTURE, (2560, 1440), PIXELS)
    declared, packs = program_json(passes, targets, images=images)
    program = json.loads(declared)
    steps = [p for p in passes if isinstance(p, EnvironmentStep)]
    assert len(steps) == (1 if scene.environment else 0)
    if steps:
        assert passes[0] is steps[0] and steps[0].source == nb.NEXT_TEXTURE
        assert tuple(steps[0].size) == environment_size((2560, 1440))
    drawn = [p for p in passes if isinstance(p, ModePass)]
    # N5.2d: each ghost pass once a ghost, the edges and (with motion blur) the gather.
    expected = []
    for scene_pass in scene.passes:
        ghost = scene_pass.target == "ghosts"
        names = [ghost_pass_name(scene_pass.name, a) for a in range(SCENE3D_TRAIL_GHOSTS)] if ghost else [scene_pass.name]
        expected += [(name, scene_pass) for name in names]
    assert [p.name for p in drawn] == [name for name, _p in expected] + ([MOTION_GATHER] if scene.motion else [])
    for native, (_name, scene_pass) in zip(drawn, expected):
        if scene_pass.core_triangle:
            assert native.pack == nb.shared_pack_path(scene_pass.name, ".frag").read_bytes() and native.geometry is None
        else:
            vertex, fragment = nb.scene_pack_paths(renderer.transition_id, scene_pass.name)
            assert native.pack == fragment.read_bytes() and native.geometry.vertex_pack == vertex.read_bytes()
        assert native.target == (nb.SCENE_GHOSTS if scene_pass.target == "ghosts" else nb.SCENE_TARGET)
        assert (native.depth_test == "less") == scene_pass.depth
    assert isinstance(passes[-1], CompositeStep) and passes[-1].form == "opaque"
    assert passes[-1].scene == (f"{nb.SCENE_BLURRED}.colour" if scene.motion else f"{nb.SCENE_TARGET}.colour")
    target = program["targets"][0]
    assert target["depth"] is True and target.get("samples", 1) == max(1, scene.samples)
    assert len(program["targets"]) == 1 + int(scene.trails) + int(scene.motion)
    own_vertex = [p for p in drawn if p.geometry is not None]
    assert len(packs) == len(program["passes"]) + len(own_vertex)   # each own vertex pack after its fragment's


def _mips_read_check_exempts_environments(source: str) -> bool:
    """ModeProgram::fromJson's check of a sampler reading mips (ABI 33's self-mipped targets) passes an environment
    step's copy, which holds its own levels (found 21 Nov on the ABI 36 build: every scene with an environment was
    refused, "reads mips of 'environment.environment', which has none", and the run ended as a cut)."""
    parse = source[source.index("bool ModeProgram::fromJson("):source.index("QJsonObject ModeProgram::toJson(")]
    check = parse[parse.index("if (s.mips == SamplerMips::None || !targetTextureName(s.texture)"):]
    return "environmentOf(s.texture)" in check[:check.index("\n")]


def test_a_sampler_reads_the_environments_levels():
    source = (ROOT / "native" / "core" / "src" / "mode_content.cpp").read_text(encoding="utf-8")
    assert _mips_read_check_exempts_environments(source)
    # Negative control: the ABI 36 build's check (no exemption) is caught.
    assert not _mips_read_check_exempts_environments(source.replace(" || environmentOf(s.texture))\n", ")\n", 1))


def test_the_scene_packs_are_the_bakes_of_the_python_renderers_texts():
    """The committed packs are discovered from the renderers (``tools/regen_qrc.py --shaders``); the current-bake check
    for every pack is ``tests/test_quick_shader_packs.py``."""
    from rendering.quick.render import native_background as nb
    from tools import regen_qrc

    from rendering.quick.transitions.native_scene import motion_post_sources

    sources = regen_qrc.transition_scene_sources()
    classes = regen_qrc._native_scene_classes()
    assert {cls.transition_id for cls in classes} == set(_trc().SCENE_TRANSITIONS)
    for name, text in motion_post_sources().items():           # N5.2d: the shared post passes, baked once
        stem, suffix = name.rsplit(".", 1)
        assert sources[name] == text and nb.shared_pack_path(stem, f".{suffix}").is_file()
    for cls in classes:
        for scene_pass in cls.native_scene_passes():
            if scene_pass.core_triangle:
                continue
            vertex, fragment = nb.scene_pack_paths(cls.transition_id, scene_pass.name)
            assert vertex.is_file() and fragment.is_file()
            assert sources[f"{cls.transition_id}_{scene_pass.name}.vert"] == scene_pass.vertex_source
            assert sources[f"{cls.transition_id}_{scene_pass.name}.frag"] == scene_pass.fragment_source


def test_the_lost_edge_splits_meshes_from_textures_and_state():
    """Checklist 13: the core's one lost edge carries textures' names, "state:<resource>" and (N5.2c) "mesh:<name>";
    each owner callback gets only its own (a mesh name reaching the texture callback is the control: the old split)."""
    from types import SimpleNamespace

    from rendering.native.mode import NativeMode

    listened = []
    module = SimpleNamespace(composite_mode_on_lost=lambda handle, callback: listened.append(callback))
    mode = NativeMode(module, SimpleNamespace(_live=lambda: 1))
    got: dict = {}
    mode.on_textures_lost(lambda names: got.setdefault("textures", names))
    mode.on_state_lost(lambda names: got.setdefault("state", names))
    mode.on_meshes_lost(lambda names: got.setdefault("meshes", names))
    listened[-1](["photo", "state:fog", "mesh:cards"])
    assert got == {"textures": ["photo"], "state": ["fog"], "meshes": ["cards"]}


def test_a_missing_value_is_an_unfilled_member():
    """Negative control of the first test's rule: the box's lift dropped is an unfilled member."""
    from rendering.native.mode import MODE_CORE_MEMBERS
    from rendering.quick.render.native_background import scene_settings

    run = _run("cube_turn")
    renderer = _renderer("cube_turn")
    sample = run.sample(run.start_ns + (run.end_ns - run.start_ns) // 2)
    settings = scene_settings(renderer, run, sample, LOGICAL)
    del settings["uLift"]
    box = renderer.scene_pass("box")
    members = _members(box.vertex_source) | _members(box.fragment_source)
    assert [m for m in members if m not in MODE_CORE_MEMBERS and m not in settings] == ["uLift"]


# -------------------------------------------------------------------------------- the lead's rules (21 Nov), each with a control

def _scattered(count: int, *, level: int = 1, shape=(400, 640)):
    """A difference image with ``count`` one-pixel spots (every third pixel of every third row) at ``level``."""
    import numpy as np

    delta = np.zeros(shape, np.int32)
    spots = [(y, x) for y in range(1, shape[0], 3) for x in range(1, shape[1], 3)][:count]
    for y, x in spots:
        delta[y, x] = level
    return delta


def test_a_single_sampled_scene_admits_its_scatter_and_nothing_past_one_level():
    from tools import pixel_tolerance as pt

    trc = _trc()
    rule = trc.N52C_RULE_A
    assert pt.judge_delta(_scattered(trc.N52C_SCATTER_PIXELS), rule)["pass"]
    # Controls: one more scattered pixel, one pixel two levels off, and a compact one-level patch all fail.
    assert not pt.judge_delta(_scattered(trc.N52C_SCATTER_PIXELS + 1), rule)["pass"]
    past = _scattered(10)
    past[200, 200] = 2
    assert not pt.judge_delta(past, rule)["pass"]
    patch = _scattered(0)
    patch[100:106, 100:106] = 1                                        # 36 touching pixels: past the group bound
    assert not pt.judge_delta(patch, rule)["pass"]


def test_jigsaw_admits_one_outline_flip_and_blinds_flat_its_own_scatter():
    import numpy as np

    from tools import pixel_tolerance as pt

    trc = _trc()
    edges = np.zeros((400, 640), bool)
    edges[:, 300] = True                                               # a piece's outline
    flip = _scattered(10)
    flip[200, 300] = 12
    assert pt.judge_delta(flip, trc.JIGSAW_RULE_A, edges=edges)["pass"]
    # Controls: the other scenes admit no flip, a second flip fails, and a flip off the outline fails.
    assert not pt.judge_delta(flip, trc.N52C_RULE_A, edges=edges)["pass"]
    two = flip.copy()
    two[100, 300] = 12
    assert not pt.judge_delta(two, trc.JIGSAW_RULE_A, edges=edges)["pass"]
    off = _scattered(10)
    off[200, 200] = 12
    assert not pt.judge_delta(off, trc.JIGSAW_RULE_A, edges=edges)["pass"]
    assert pt.judge_delta(_scattered(192), trc.BLINDS_FLAT_RULE_A)["pass"]
    assert not pt.judge_delta(_scattered(193), trc.BLINDS_FLAT_RULE_A)["pass"]     # control: one more


def test_a_multisampled_scene_is_judged_by_rule_b_only_and_its_single_sampled_form_by_rule_a():
    trc = _trc()
    assert trc._rule_a("cube_turn", {"scene": True, "samples": 4}) is None
    # Control: the same scene single-sampled is judged by rule (a); Blinds' flat style is a fragment pass.
    assert trc._rule_a("cube_turn_options", {"scene": True, "samples": 0}) is trc.N52C_RULE_A
    assert trc._rule_a("jigsaw_options@1.5", {"scene": True, "samples": 0}) is trc.JIGSAW_RULE_A
    assert trc._rule_a("blinds_flat", {"scene": True, "samples": 0}) is trc.BLINDS_FLAT_RULE_A
    for variant, overrides in trc.N52C_VARIANTS.items():               # each 4x default has a single-sampled form
        if overrides.get("samples", 4) and variant != "blinds_flat":
            twin = [v for v, o in trc.N52C_VARIANTS.items()
                    if trc.variant_transition(v) == trc.variant_transition(variant) and o.get("samples") == 0]
            assert twin, variant


def test_the_environment_copy_count_is_read_or_refused_never_defaulted():
    from types import SimpleNamespace

    trc = _trc()
    live = lambda value: SimpleNamespace(composite_live=lambda: value)
    assert trc._environment_copies(live({"stage_environment_copies": 3, "stage_textures": 0})) == 3
    assert trc._environment_copies(live({"stage_environment_copies": 0})) == 0
    # Controls: a module without the count (or a broken one) is refused, never read as "no copy drawn".
    for broken in ({}, {"stage_environment_copies": None}, {"stage_environment_copies": -1},
                   {"stage_environment_copies": True}, {"stage_environment_copies": "2"}, None):
        with pytest.raises(RuntimeError, match="environment copy count"):
            trc._environment_copies(live(broken))


def test_blinds_slats_are_checked_a_hair_either_side_of_their_degenerate_half_turn():
    trc = _trc()
    for variant in trc.SLAT_VARIANTS:
        progress = trc.variant_progress(variant)
        assert 0.5 not in progress and set(trc.SLAT_PROGRESS) <= set(progress)
        assert len({trc.progress_key(p) for p in progress}) == len(progress)   # distinct frame keys
    # Control: every other variant keeps 0.5 and the stored two-place keys.
    assert trc.variant_progress("blinds_flat") == tuple(trc.PROGRESS) and trc.progress_key(0.5) == "0.50"


def test_rule_b_admits_three_isolated_edge_flips_a_frame():
    import numpy as np

    from tools import pixel_tolerance as pt

    trc = _trc()
    delta = np.zeros((100, 100), np.int32)
    edges = np.zeros((100, 100), bool)
    edges[:, 50] = True
    for y in (10, 40, 70):
        delta[y, 50] = 200
    assert pt.judge_delta(delta, trc.N52C_RULE_B, edges=edges)["pass"]
    # Controls: a fourth flip, and a flip off any content edge, fail.
    four = delta.copy()
    four[90, 50] = 200
    assert not pt.judge_delta(four, trc.N52C_RULE_B, edges=edges)["pass"]
    off_edge = delta.copy()
    off_edge[10, 50], off_edge[10, 20] = 0, 200
    assert not pt.judge_delta(off_edge, trc.N52C_RULE_B, edges=edges)["pass"]


# -------------------------------------------------------------------------------- N5.2d (N4.i): motion blur and trails

#: A vertex stage's own clip depth written after the matrix: Block Spins' ``projected.z``, Crumble's ``q.z``, Glass
#: Shatter's and Pixel Accretion's ``gl_Position.z``, and the shared camera's ``sceneProject*`` (``clip.z =
#: sceneClipDepth(w)``: OpenGL's -w..w, negative closer than twice the near plane), read in the code main runs.
_OWN_DEPTH = re.compile(r"\b\w+\.z\s*=(?!=|\s*(?:sceneClipDepth|uMatrix\[2\]\[2\]))|\bsceneProject\w*\s*\(")


def _main_code(vertex_source: str) -> str:
    """The code main runs: main, or (a motion variant) the renamed body it calls (``sceneVertexMain``)."""
    text = _COMMENT.sub("", vertex_source)
    start = text.find("void sceneVertexMain(")
    return text[start if start >= 0 else text.rfind("void main("):]


def _writes_own_depth(vertex_source: str) -> bool:
    return bool(_OWN_DEPTH.search(_main_code(vertex_source)))


def test_a_stage_writing_its_own_clip_depth_puts_it_through_the_matrix():
    """Found 21 Nov on the ABI 37 build: Vulkan's clip depth is 0..w, so a depth written after ``uMatrix`` (OpenGL's
    -w..w) lost every fragment in front of the slab's middle (half of each face gone, rule b 255 levels). Every such
    native stage ends with ``NATIVE_CLIP_DEPTH_LINE`` (the matrix's z row: OpenGL's (0, 0, 1, 0) leaves it exact),
    N5.2c's scenes through the shared camera included (the lead, 21 Nov); a stage whose depth is the matrix's own
    (Jigsaw's shadow, the item quads) has none, which would correct it twice."""
    from rendering.gl_programs.blockspin_program import BLOCK_SPIN_QUICK_VERTEX_SOURCE
    from rendering.quick.transitions.native_scene import NATIVE_CLIP_DEPTH_LINE, native_clip_depth
    from tools import regen_qrc

    writers, others = [], []
    for cls in regen_qrc._native_scene_classes():
        for scene_pass in cls.native_scene_passes():
            if scene_pass.core_triangle:
                continue
            body = scene_pass.vertex_source.rstrip()
            if _writes_own_depth(scene_pass.vertex_source):
                writers.append(cls.transition_id)
                assert body.endswith(NATIVE_CLIP_DEPTH_LINE + "}"), f"{cls.transition_id} {scene_pass.name}"
            else:
                others.append(scene_pass.name)
                assert NATIVE_CLIP_DEPTH_LINE not in body, f"{cls.transition_id} {scene_pass.name}"
    assert set(writers) == {"block_spins", "crumble", "glass_shatter", "pixel_accretion", "blinds", "cube_turn",
                            "depth_cascade", "jigsaw"}
    assert "shadow" in others and "underlay" in others
    # Controls: the Python renderer's own text is a writer without the line; the line is put once, at main's end.
    assert _writes_own_depth(BLOCK_SPIN_QUICK_VERTEX_SOURCE) and NATIVE_CLIP_DEPTH_LINE not in BLOCK_SPIN_QUICK_VERTEX_SOURCE
    with pytest.raises(ValueError):
        native_clip_depth(native_clip_depth(BLOCK_SPIN_QUICK_VERTEX_SOURCE))
    with pytest.raises(ValueError, match="last function"):
        native_clip_depth(BLOCK_SPIN_QUICK_VERTEX_SOURCE + "float later() {\n    return 1.0;\n}\n")


def test_a_ghost_pass_is_given_each_ghosts_own_values_and_the_motion_pass_none():
    """Trails: each ghost pass (``<pass>_<age>``) is given its moment, the piece now and its fade, scoped to it, so the
    core packs a block a ghost; the motion pass shares the ghost's block (``portable_program``) and is given the fade it
    never reads, scoped to it alone."""
    from rendering.gl_programs.scene3d import SCENE3D_TRAIL_GHOSTS, scene3d_trail_ghosts
    from rendering.quick.render.native_background import scene_settings

    run = _run("glass_shatter_both")
    renderer = _renderer("glass_shatter")
    scene = renderer.native_scene(run, LOGICAL)
    sample = run.sample(run.start_ns + (run.end_ns - run.start_ns) // 2)
    settings = scene_settings(renderer, run, sample, LOGICAL, PIXELS, scene)
    ghosts = scene3d_trail_ghosts(float(sample.eased_progress), run.request.duration_ms)
    assert len(ghosts) == SCENE3D_TRAIL_GHOSTS
    for age, (time, fade) in enumerate(ghosts):
        assert settings[f"uProgress@glass_ghost_{age}"] == time and settings[f"uGhostFade@glass_ghost_{age}"] == fade
        assert settings[f"uProgressBefore@glass_ghost_{age}"] == float(sample.eased_progress)
    assert settings["uGhostFade@glass_motion"] == 0.0 and "uGhostFade" not in settings
    assert settings["uViewport"] == (float(PIXELS[0]), float(PIXELS[1]))
    # Control: the ghosts differ in time and fade (a shared value would draw one ghost three times).
    assert len({settings[f"uProgress@glass_ghost_{age}"] for age in range(SCENE3D_TRAIL_GHOSTS)}) == SCENE3D_TRAIL_GHOSTS


def test_the_motion_table_and_the_tile_count_are_the_python_renderers():
    """Crumble's chunks read their motion table (RGBA32F, one row a chunk, sampled nearest); Pixel Accretion's tile count
    is its grid of the item's device pixels (``pixel_accretion_grid``), a setting the instanced pass's count names."""
    from rendering.gl_programs.pixel_accretion_program import pixel_accretion_grid, pixel_accretion_parameters
    from rendering.quick.render import native_background as nb
    from rendering.quick.transitions.crumble_dynamics import MOTION_FRAMES
    from rendering.quick.transitions.implementations.pixel_accretion import TILE_INSTANCES

    run = _run("crumble_motion")
    scene = _renderer("crumble").native_scene(run, LOGICAL)
    (table,) = scene.textures
    assert table.format == "rgba32f" and table.size[0] == MOTION_FRAMES
    assert len(table.pixels) == 16 * table.size[0] * table.size[1]
    passes, _targets, _images = nb.scene_program(_renderer("crumble"), scene, nb.TEXTURE, nb.NEXT_TEXTURE,
                                                 (2560, 1440), PIXELS)
    chunks = next(p for p in passes if getattr(p, "name", "") == "chunks_motion")
    motion = next(s for s in chunks.samplers if s.name == "uMotion")
    assert motion.texture == nb.SCENE_MOTION_TABLE and motion.filter == "nearest"
    accretion = _run("pixel_accretion_motion")
    renderer = _renderer("pixel_accretion")
    sample = accretion.sample(accretion.start_ns + (accretion.end_ns - accretion.start_ns) // 2)
    tile = pixel_accretion_parameters(accretion.request.parameter_dict())[1]
    columns, rows, _size = pixel_accretion_grid(*PIXELS, tile)
    values = renderer.scene_values(accretion, sample, LOGICAL, PIXELS)
    assert values[TILE_INSTANCES] == columns * rows and values["uGrid"] == (float(columns), float(rows))
    assert all(p.instances == TILE_INSTANCES for p in renderer.native_scene(accretion, LOGICAL).passes
               if p.mesh == "microquad")
    # Control: the logical size's grid is another count (the device pixels are what Python's viewport holds).
    assert pixel_accretion_grid(int(LOGICAL[0]), int(LOGICAL[1]), tile)[:2] != (columns, rows)


def _piece_scene():
    """Old picture dark, new picture light, one mid-grey piece in flight (rows 40-79, columns 60-139)."""
    import numpy as np

    old = np.zeros((160, 240, 4), np.uint8)
    old[..., :3], old[..., 3] = 30, 255
    new = old.copy()
    new[..., :3] = 220
    frame = old.copy()
    frame[40:80, 60:140, :3] = 128
    return old, new, frame


def test_the_piece_edge_class_admits_edge_rows_and_their_streaks_and_fails_planted_defects():
    """The lead's N5.2d rule (21 Nov): flips past one level only on a moving piece edge or its gather streak along the
    motion, at most the variant's count, no compact group past N52C_SCATTER_GROUP. Controls: a shifted piece, a patch,
    a colour shift and a streak across the motion all fail."""
    import numpy as np

    trc = _trc()
    old, new, reference = _piece_scene()
    velocity = (np.zeros((160, 240), np.float32), np.full((160, 240), 12.0, np.float32))   # moving down, 12 px

    def judged(candidate, flips=40, moved=velocity):
        allowed = trc.piece_edges(candidate, reference, [old, new], moved, trc.N52D_LONGEST)
        return trc.judge_piece_edges(candidate, reference, flips, allowed)

    edge_row = reference.copy()
    edge_row[80, 70:76, :3] = 128                       # the piece's bottom edge row covered one row further
    assert judged(edge_row)["pass"]
    streak = reference.copy()
    streak[81:93, 100, :3] = 90                         # a flip smeared down the piece's motion
    assert judged(streak)["pass"]
    assert not judged(streak, moved=None)["pass"]       # control: without motion there is no streak
    assert not judged(edge_row, flips=5)["pass"]        # control: past the variant's count
    across = reference.copy()
    across[100, 100:115, :3] = 90                       # a streak across the motion, away from the piece
    assert not judged(across)["pass"]
    shifted = old.copy()
    shifted[46:86, 66:146, :3] = 128                    # the piece drawn 6 px off
    assert not judged(shifted, flips=10_000)["pass"]
    patch = reference.copy()
    patch[50:58, 80:88, :3] = 160                       # a patch inside the piece
    assert not judged(patch, flips=10_000)["pass"]
    off_tie = reference.copy()
    off_tie[120, 200, :3] = 32                          # a two-level tie on the flat picture, off every edge
    allowed = trc.piece_edges(off_tie, reference, [old, new], velocity, trc.N52D_LONGEST)
    assert trc.judge_piece_edges(off_tie, reference, 40, allowed, ties=trc.TIE_PIXELS)["pass"]
    assert not trc.judge_piece_edges(off_tie, reference, 40, allowed)["pass"]             # control: no ties admitted
    many = reference.copy()
    many[120, 150:150 + 2 * (trc.TIE_PIXELS + 1):2, :3] = 32                               # one tie too many
    assert not trc.judge_piece_edges(many, reference, 40, allowed, ties=trc.TIE_PIXELS)["pass"]
    far = reference.copy()
    far[120, 200, :3] = 34                              # four levels off every edge: not a tie
    assert not trc.judge_piece_edges(far, reference, 40, allowed, ties=trc.TIE_PIXELS)["pass"]
    tinted = reference.copy()
    tinted[40:80, 60:140, 0] = 150                      # a colour shift of the whole piece
    assert not judged(tinted, flips=10_000)["pass"]


def test_the_n52d_bounds_cover_every_form_and_the_gather_free_ones_are_judged_in_the_core_frame():
    trc = _trc()
    single = {v for v, o in trc.N52D_VARIANTS.items() if o.get("samples") == 0}
    assert set(trc.N52D_EDGE_FLIPS_A) == single
    assert set(trc.N52D_EDGE_FLIPS_B) == set(trc.N52D_VARIANTS) | {"depth_cascade_options"}
    # Control: the gather-free forms are the plain ones and the defaults, never a form with motion blur or trails.
    assert trc.n52d_gather_free("crumble_plain") and trc.n52d_gather_free("crumble")
    assert not trc.n52d_gather_free("crumble_both") and not trc.n52d_gather_free("crumble_trails")
