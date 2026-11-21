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
