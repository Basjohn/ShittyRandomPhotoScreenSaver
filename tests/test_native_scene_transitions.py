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


VARIANTS = tuple(_trc().N52C_VARIANTS)
LOGICAL = (1600.0, 900.0)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_member_is_filled_and_every_value_is_declared(variant):
    from rendering.native.mode import MODE_CORE_MEMBERS
    from rendering.quick.render.native_background import scene_settings
    from rendering.quick.transitions.native_scene import SHOW_EFFECT

    run = _run(variant)
    renderer = _renderer(run.request.transition_id)
    scene = renderer.native_scene(run, LOGICAL)
    for progress in (0.05, 0.5, 0.9):
        sample = run.sample(run.start_ns + round(progress * (run.end_ns - run.start_ns)))
        if renderer.scene_show(run, sample) != SHOW_EFFECT:
            continue
        settings = scene_settings(renderer, run, sample, LOGICAL)
        declared: set[str] = set()
        for scene_pass in scene.passes:
            members = _members(scene_pass.vertex_source) | _members(scene_pass.fragment_source)
            declared |= members
            unfilled = sorted(m for m in members if m not in MODE_CORE_MEMBERS and m not in settings)
            assert not unfilled, f"{variant} {scene_pass.name}: unfilled {unfilled}"
        unknown = sorted(name for name in settings if name not in declared)
        assert not unknown, f"{variant}: settings no pass declares {unknown}"
        json.dumps(settings)                                  # the core's settings are JSON numbers


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_vertex_input_is_its_meshs_and_every_sampler_the_shaders(variant):
    from rendering.quick.transitions.native_scene import QUAD_MESH, SCENE_TEXTURES

    run = _run(variant)
    scene = _renderer(run.request.transition_id).native_scene(run, LOGICAL)
    meshes = {mesh.name: mesh for mesh in scene.meshes}
    for scene_pass in scene.passes:
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

    run = _run(variant)
    renderer = _renderer(run.request.transition_id)
    scene = renderer.native_scene(run, LOGICAL)
    passes, targets = nb.scene_program(renderer, scene, nb.TEXTURE, nb.NEXT_TEXTURE, (2560, 1440))
    declared, packs = program_json(passes, targets)
    program = json.loads(declared)
    steps = [p for p in passes if isinstance(p, EnvironmentStep)]
    assert len(steps) == (1 if scene.environment else 0)
    if steps:
        assert passes[0] is steps[0] and steps[0].source == nb.NEXT_TEXTURE
        assert tuple(steps[0].size) == environment_size((2560, 1440))
    drawn = [p for p in passes if isinstance(p, ModePass)]
    assert [p.name for p in drawn] == [p.name for p in scene.passes]
    for native, scene_pass in zip(drawn, scene.passes):
        vertex, fragment = nb.scene_pack_paths(renderer.transition_id, scene_pass.name)
        assert native.pack == fragment.read_bytes() and native.geometry.vertex_pack == vertex.read_bytes()
        assert native.target == nb.SCENE_TARGET and (native.depth_test == "less") == scene_pass.depth
    assert isinstance(passes[-1], CompositeStep) and passes[-1].form == "opaque"
    (target,) = program["targets"]
    assert target["depth"] is True and target.get("samples", 1) == max(1, scene.samples)
    assert len(packs) == len(program["passes"]) + len(drawn)   # each drawn pass's vertex pack after its fragment's


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

    sources = regen_qrc.transition_scene_sources()
    classes = regen_qrc._native_scene_classes()
    assert {cls.transition_id for cls in classes} == set(_trc().N52C_TRANSITIONS)
    for cls in classes:
        for scene_pass in cls.native_scene_passes():
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
