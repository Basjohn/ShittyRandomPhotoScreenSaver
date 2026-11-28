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
    if getattr(scene, "bloom", 0.0) > 0.0:
        # N5.2e: the glow composite's own member (the core's post stage block; ``STAGE_MEMBERS``), its others the core's.
        from post_stages import STAGE_MEMBERS

        found["scene_composite"] = set(STAGE_MEMBERS["opaque_glow"])
    for population in getattr(scene, "populations", ()):       # N5.2f: each compute entry's one block
        from rendering.quick.transitions.native_scene import population_scan_sources

        found[population.resource("count")] = _members(population.count_source())
        found[population.resource("scan")] = _members(next(iter(population_scan_sources().values())))
        found[population.resource("scatter")] = _members(population.scatter_source())
    return found


def _count_names(scene) -> set[str]:
    """The settings that fill a pass's draw count (N5.2d: Pixel Accretion's tile instances); N5.2f: a population's
    storage sizes and group count."""
    return ({count for p in scene.passes for count in (p.vertices, p.instances)
             if isinstance(count, str) and count != "mesh"}
            | {name for population in getattr(scene, "populations", ()) for name in population.settings()})


def test_every_route_variant_names_a_registered_transition():
    """The route check's every variant (its default run) resolves its production run: each transition id is the
    registry's (22 Nov: Warp's stale ``warp`` stopped a default route check with "unavailable transition warp")."""
    trc = _trc()
    failed = {}
    for variant in trc.VARIANTS:
        try:
            _run(variant)
        except ValueError as exc:
            failed[variant] = str(exc)
    assert failed == {}


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
        elif scene_pass.mesh is None:                           # N5.2f: a population's draw reads no vertex buffer
            assert scene_pass.name in {p.draw for p in scene.populations}
            attributes = set()
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


def scene_target_runs(drawn, target: str) -> int:
    """The core's runs on ``target`` (mode_content.cpp recordPasses: consecutive passes into one target are one run, and
    each run's end resolves its multisampled attachments)."""
    runs, previous = 0, None
    for p in drawn:
        if p.target == target and previous != target:
            runs += 1
        previous = p.target
    return runs


def velocity_is_one_attachment(target: dict) -> bool:
    """A motion-blurred scene target's attachments: its colour, then the velocity as one RGBA16F (the half floats of
    Python's RG16F in .xy; QRhi has no RG16F), and nothing else."""
    colour = target["colour"]
    return len(colour) == 2 and colour[1]["format"] == "rgba16f"


def clears_as_one(target: dict) -> bool:
    """N5.2h: every attachment of the target clears to the same four values, so OpenGL can clear the multisampled
    target by its pass (one clear colour for every attachment) instead of by the clearing draw."""
    clears = {tuple(a.get("clear", [0.0, 0.0, 0.0, 0.0])) for a in target["colour"]}
    return len(clears) == 1


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
    assert len(steps) == int(scene.environment) + int(scene.source_environment)
    if scene.environment:
        assert passes[0] is steps[0] and steps[0].source == nb.NEXT_TEXTURE
        assert tuple(steps[0].size) == environment_size((2560, 1440))
    if scene.source_environment:                                # N5.2f: the old picture's, second
        assert passes[len(steps) - 1] is steps[-1] and steps[-1].source == nb.TEXTURE
    # N5.2f: each population's count, scan and scatter after the environments and before every drawn pass.
    from rendering.native.mode import ComputePass

    computes = [p for p in passes if isinstance(p, ComputePass)]
    expected_computes = [population.resource(step) for population in scene.populations
                         for step in ("count", "scan", "scatter")]
    assert [p.name for p in computes if p.name in expected_computes] == expected_computes
    if computes and expected_computes:
        assert passes[len(steps):len(steps) + len(expected_computes)] == computes[:len(expected_computes)]
        assert all(p.trigger == "draw" for p in computes[:len(expected_computes)])
    drawn = [p for p in passes if isinstance(p, ModePass)]
    # N5.2d: each ghost pass once a ghost, the edges and (with motion blur) the gather.
    expected = []
    for scene_pass in scene.passes:
        ghost = scene_pass.target == "ghosts"
        names = [ghost_pass_name(scene_pass.name, a) for a in range(SCENE3D_TRAIL_GHOSTS)] if ghost else [scene_pass.name]
        expected += [(name, scene_pass) for name in names]
    # N5.2h: the ghost passes first (their own target), so the scene target is drawn in one run.
    expected = ([e for e in expected if e[1].target == "ghosts"] + [e for e in expected if e[1].target != "ghosts"])
    assert [p.name for p in drawn] == [name for name, _p in expected] + ([MOTION_GATHER] if scene.motion else [])
    assert scene_target_runs(drawn, nb.SCENE_TARGET) == (1 if any(p.target == nb.SCENE_TARGET for p in drawn) else 0)
    if scene.trails:
        # Negative control: the old order (the ghosts at their place among the scene's passes) splits the scene target.
        old = [p for p in drawn if p.target == nb.SCENE_TARGET][:1] + [p for p in drawn if p.target == nb.SCENE_GHOSTS] \
            + [p for p in drawn if p.target == nb.SCENE_TARGET][1:]
        assert scene_target_runs(old, nb.SCENE_TARGET) == 2
    for native, (_name, scene_pass) in zip(drawn, expected):
        if scene_pass.core_triangle:
            assert native.pack == nb.shared_pack_path(scene_pass.name, ".frag").read_bytes() and native.geometry is None
        else:
            vertex, fragment = nb.scene_pack_paths(renderer.transition_id, scene_pass.name)
            assert native.pack == fragment.read_bytes() and native.geometry.vertex_pack == vertex.read_bytes()
        assert native.target == (nb.SCENE_GHOSTS if scene_pass.target == "ghosts" else nb.SCENE_TARGET)
        assert (native.depth_test == "less") == scene_pass.depth
        assert native.depth_write == scene_pass.writes_depth             # N5.2e: the sparks test without a write
    shown = f"{nb.SCENE_BLURRED}.colour" if scene.motion else f"{nb.SCENE_TARGET}.colour"
    if scene.bloom > 0.0:
        # N5.2e: the bloom chain of what the composite shows, its glow added (Python's opaque composite with bloom).
        from rendering.native.mode import BloomStep

        assert isinstance(passes[-2], BloomStep) and passes[-2].source == shown
        assert passes[-1].form == "opaque_glow" and passes[-1].glow == f"{passes[-2].name}.glow"
        assert program["targets"][0]["colour"][0].get("clear", [0.0, 0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0, 0.0]
    else:
        assert passes[-1].form == "opaque"
    assert isinstance(passes[-1], CompositeStep) and passes[-1].scene == shown
    target = program["targets"][0]
    assert target["depth"] is True and target.get("samples", 1) == max(1, scene.samples)
    assert len(program["targets"]) == 1 + int(scene.trails) + int(scene.motion)
    # N5.2h: with motion blur the velocity is one four-channel half-float attachment (its .xy), never a pair of
    # single-channel ones (0.42 ms a 4K frame at 4x on OpenGL), and each scene pass writes one output per attachment.
    if scene.motion:
        assert velocity_is_one_attachment(target)
        assert all(len(p.outputs) == 2 for p in drawn if p.target == nb.SCENE_TARGET)
        # Negative control: the ABI 37 declaration (x and y as two R16F attachments) fails.
        pair = dict(target, colour=[target["colour"][0], {"name": "vx", "format": "r16f"},
                                    {"name": "vy", "format": "r16f"}])
        assert not velocity_is_one_attachment(pair)
        assert clears_as_one(target)
        # Negative control: a velocity whose alpha differs from the colour's (the first form, with bloom) fails.
        alpha = target["colour"][0].get("clear", [0.0, 0.0, 0.0, 0.0])[3]
        apart = dict(target, colour=[target["colour"][0], dict(target["colour"][1], clear=[0.0, 0.0, 0.0, 1.0 - alpha])])
        assert not clears_as_one(apart)
    else:
        assert len(target["colour"]) == 1
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
#: sceneClipDepth(w)``: OpenGL's -w..w, negative closer than twice the near plane), read in the code main runs; N5.2e:
#: the particles' ``sceneStreak`` (through ``sceneParticleStreak``: ``clip.z = sceneClipDepth(w) / w * clip.w``).
_OWN_DEPTH = re.compile(r"\b\w+\.z\s*=(?!=|\s*(?:sceneClipDepth|uMatrix\[2\]\[2\]))|\bsceneProject\w*\s*\("
                        r"|\bscene(?:Particle)?Streak\s*\(")


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
    # Membership is discovered, never listed: every writer was checked above, and some scene does write its own depth.
    assert writers
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


# ---------------------------------------------------------------- N5.2e (N4.l): the grid, the tiles, their frame block

def _own_blocks(text: str) -> dict[str, str]:
    """A stage's std140 blocks but the conventions' -> each block's body (comments dropped)."""
    return {name: body for binding, name, body in _BLOCK.findall(_COMMENT.sub("", text)) if int(binding) != 17}


def test_exploding_tiles_frame_block_is_merged_into_each_pass_block():
    """The core admits one block of its own a pass; Exploding Tiles' programs declare their pass block and the shared
    ``ExplodingTilesFrame``. Each native pack declares one block, the pass block with the frame block's members after
    its own, the same in both stages, at the pass block's binding."""
    from rendering.gl_programs import exploding_tiles_program as et
    from rendering.quick.transitions.implementations.exploding_tiles import QuickExplodingTilesRenderer

    frame = et.EXPLODING_TILES_FRAME_BLOCK
    frame_members = [name for name, _kind in frame.fields]
    originals = {"backdrop": (et.EXPLODING_TILES_BACKDROP_VERTEX_SOURCE, et.EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE),
                 "shadows": (et.EXPLODING_TILES_SHADOW_VERTEX_SOURCE, et.EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE),
                 "tiles_motion": (et.EXPLODING_TILES_VERTEX_SOURCE, et.EXPLODING_TILES_FRAGMENT_SOURCE),
                 "sparks": (et.EXPLODING_TILES_SPARK_VERTEX_SOURCE, et.EXPLODING_TILES_SPARK_FRAGMENT_SOURCE)}
    for scene_pass in QuickExplodingTilesRenderer.native_scene_passes():
        if scene_pass.core_triangle:
            continue
        stages = [_own_blocks(scene_pass.vertex_source), _own_blocks(scene_pass.fragment_source)]
        assert all(len(blocks) == 1 for blocks in stages), scene_pass.name
        assert stages[0] == stages[1], scene_pass.name
        (name, body), = stages[0].items()
        members = _MEMBER.findall(body)
        assert name != frame.name and members[-len(frame_members):] == frame_members, scene_pass.name
        assert len(set(members)) == len(members), scene_pass.name
    # Control: the Python renderer's own texts declare two blocks, which the core refuses.
    for name, texts in originals.items():
        declared = set().union(*(_own_blocks(text) for text in texts))
        assert frame.name in declared and len(declared) == 2, name


def test_the_n52e_bounds_cover_every_moving_form():
    """Every single-sampled Exploding Tiles and Page Curl form is judged by the piece-edge class (rule a), every
    Exploding Tiles form and Page Curl with options by it under rule (b); Membrane's 4x default by its own rule (b)."""
    trc = _trc()
    single = {v for v, o in trc.N52E_VARIANTS.items() if o.get("samples") == 0}
    moving = {v for v in single if not v.startswith("membrane")}
    assert set(trc.N52E_EDGE_FLIPS_A) == moving
    assert set(trc.N52E_EDGE_FLIPS_B) == {v for v in trc.N52E_VARIANTS if v.startswith("exploding_tiles")} | {
        "page_curl_options"}
    assert set(trc.EDGE_FLIPS_A) == set(trc.N52D_EDGE_FLIPS_A) | moving | set(trc.N52F_EDGE_FLIPS_A)
    # Control: the gather-free judgement (against Python in the core's frame) never takes a form with bloom.
    assert trc.n52d_gather_free("exploding_tiles_plain") and trc.n52d_gather_free("page_curl_options")
    assert not trc.n52d_gather_free("exploding_tiles_bloom") and not trc.n52d_gather_free("membrane_options")


def test_the_trail_edges_keep_the_scenes_alpha_as_python_blends_them():
    """Python blends the trails' edges with ``blend_scope(ADD, SRC_ALPHA, ONE_MINUS_SRC_ALPHA)``, whose alpha is
    (ZERO, ONE): kept. With bloom the alpha is emitted light; N5.2d's alpha (SRC_ALPHA, ONE_MINUS_SRC_ALPHA) lit every
    trail outline (n52e_r1: Exploding Tiles with bloom, motion and trails, 100k pixels off; 236 once kept)."""
    from unittest import mock

    from OpenGL import GL as gl

    from rendering.quick.scene3d import passes
    from rendering.quick.transitions.native_scene import TRAIL_EDGES_PASS

    names = {gl.GL_ZERO: "zero", gl.GL_ONE: "one", gl.GL_SRC_ALPHA: "src_alpha",
             gl.GL_ONE_MINUS_SRC_ALPHA: "one_minus_src_alpha", gl.GL_FUNC_ADD: "add"}
    calls = {}
    with mock.patch.object(passes, "gl") as fake:
        for constant in ("GL_ZERO", "GL_ONE", "GL_SRC_ALPHA", "GL_ONE_MINUS_SRC_ALPHA", "GL_FUNC_ADD", "GL_BLEND"):
            setattr(fake, constant, getattr(gl, constant))
        fake.glBlendFuncSeparate.side_effect = lambda *a: calls.setdefault("func", a)
        fake.glBlendEquationSeparate.side_effect = lambda *a: calls.setdefault("equation", a)
        with passes.blend_scope(gl.GL_FUNC_ADD, gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA):
            pass
    src, dst, src_a, dst_a = (names[v] for v in calls["func"])
    python = ((names[calls["equation"][0]], src, dst), (names[calls["equation"][1]], src_a, dst_a))
    assert tuple(map(tuple, TRAIL_EDGES_PASS.blend)) == python
    # Control: N5.2d's blend (the colour's factors on the alpha too) is not Python's.
    assert (("add", "src_alpha", "one_minus_src_alpha"), ("add", "src_alpha", "one_minus_src_alpha")) != python


def test_the_merge_refuses_a_doubled_member_and_a_third_block():
    from rendering.gl_programs import exploding_tiles_program as et
    from rendering.quick.transitions.native_scene import native_one_block

    frame = et.EXPLODING_TILES_FRAME_BLOCK.name
    vertex, fragment = et.EXPLODING_TILES_BACKDROP_VERTEX_SOURCE, et.EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE
    assert native_one_block((vertex, fragment), frame)                                  # the plain merge passes
    doubled = fragment.replace("uniform ExplodingTilesFrame {", "uniform ExplodingTilesFrame {\n    mat4 uMatrix;")
    with pytest.raises(ValueError, match="both"):
        native_one_block((vertex, doubled), frame)
    third = fragment.replace("#version 460 core\n", "#version 460 core\nlayout(std140, binding = 3) uniform Extra {\n"
                             "    float uExtra;\n};\n", 1)
    with pytest.raises(ValueError, match="one block of its own"):
        native_one_block((vertex, third), frame)
    with pytest.raises(ValueError, match="frame block"):
        native_one_block((vertex, fragment), "NoSuchFrame")


def test_the_motion_free_tiles_write_no_motion_and_the_motion_tiles_both_axes():
    """Without motion blur the scene target has its colour alone and the core refuses outputs past it: the tiles' pack
    writes FragColor only; with it, (x, y) at location 1 (N5.2h: the core's one RGBA16F, Python's RG16F)."""
    from rendering.quick.transitions.implementations.exploding_tiles import QuickExplodingTilesRenderer
    from rendering.quick.transitions.native_scene import native_without_motion

    output = re.compile(r"layout\s*\(\s*location\s*=\s*(\d+)\s*\)\s*out\s+vec4\s+(\w+)\s*;")
    plain = QuickExplodingTilesRenderer.scene_pass("tiles").fragment_source
    moving = QuickExplodingTilesRenderer.scene_pass("tiles_motion").fragment_source
    assert output.findall(plain) == [("0", "FragColor")]
    assert output.findall(moving) == [("0", "FragColor"), ("1", "SceneMotion")]
    assert "SceneMotion = vec4(motion, 0.0, 1.0);" in moving
    # Control: a fragment without the outputs is refused (it is not a motion-writing fragment).
    with pytest.raises(ValueError):
        native_without_motion(plain)


def test_exploding_tiles_values_are_the_python_renderers_frame_block():
    """The frame block's values are ``_frame_values`` (the one owner ``render`` packs), the tile count its grid of the
    item's device pixels, the sparks' count 0 outside their life, and each ghost its own moment."""
    from rendering.gl_programs.exploding_tiles_program import exploding_tiles_blast, exploding_tiles_grid
    from rendering.gl_programs.scene3d import scene3d_trail_ghosts
    from rendering.quick.render.native_background import scene_settings
    from rendering.quick.transitions.implementations.exploding_tiles import SPARK_INSTANCES, TILE_INSTANCES

    run = _run("exploding_tiles_both")
    renderer = _renderer("exploding_tiles")
    scene = renderer.native_scene(run, LOGICAL)
    columns = run.request.parameter_dict()["columns"]
    early = run.sample(run.start_ns + (run.end_ns - run.start_ns) // 50)
    late = run.sample(run.start_ns + (run.end_ns - run.start_ns) * 9 // 10)
    for sample in (early, late):
        settings = scene_settings(renderer, run, sample, LOGICAL, PIXELS, scene)
        grid = exploding_tiles_grid(columns, *PIXELS)
        assert settings["uGrid"] == grid and settings[TILE_INSTANCES] == grid[0] * grid[1]
        assert settings["uViewport"] == (float(PIXELS[0]), float(PIXELS[1])) and settings["uEmissive"] == 1.0
        assert settings["u_bloom_strength"] == run.request.parameter_dict()["bloom"]
        progress = float(sample.eased_progress)
        for age, (time, fade) in enumerate(scene3d_trail_ghosts(progress, run.request.duration_ms)):
            assert settings[f"uProgress@tiles_ghost_{age}"] == time
            assert settings[f"uBlast@tiles_ghost_{age}"] == exploding_tiles_blast(time)
            assert settings[f"uShutter@tiles_ghost_{age}"] == time - progress
            assert settings[f"uGhostFade@tiles_ghost_{age}"] == fade
    # Before the detonation no spark can live (Python skips the pass); later they do.
    assert scene_settings(renderer, run, early, LOGICAL, PIXELS, scene).get(SPARK_INSTANCES) == 0
    assert scene_settings(renderer, run, run.sample(run.start_ns + (run.end_ns - run.start_ns) // 8), LOGICAL,
                          PIXELS, scene)[SPARK_INSTANCES] > 0


# ------------------------------------------------------------------------------- N5.2f (N4.c): compacted populations

def _populations():
    return [(transition_id, population) for transition_id in ("disintegrate", "volumetric_dissolve")
            for population in _renderer(transition_id).native_scene_populations()]


def test_each_population_pack_holds_one_block_with_the_frame_merged_into_the_dispatch_block():
    """The core admits one block a pass: the count and scatter packs merge the hooks' frame block into
    PopulationDispatch (``native_one_block``); the control, the product's own two-block text, is caught."""
    from rendering.quick.scene3d.population import population_count_source

    for _transition_id, population in _populations():
        for text in (population.count_source(), population.scatter_source()):
            own = _own_blocks(text)
            assert list(own) == ["PopulationDispatch"]
            members = set(_MEMBER.findall(own["PopulationDispatch"]))
            assert {"uPopulation", "uGroups", "uVertices", "uProgress", "uSeed", "uGrid"} <= members
        assert len(_own_blocks(population_count_source(population.hooks))) == 2      # control: unmerged


def test_population_values_are_the_compacted_populations_dispatch_and_allocation():
    from rendering.quick.scene3d.population import _DISPATCH_BLOCK, POPULATION_GROUP
    from rendering.quick.transitions.native_scene import population_values

    _transition_id, population = _populations()[0]
    values = population_values(population, 518_400, 4)
    assert {name for name, _kind in _DISPATCH_BLOCK.fields} <= set(values)
    groups = -(-518_400 // POPULATION_GROUP)
    assert values["uGroups"] == values[population.resource("groups")] == groups
    assert values[population.resource("group_bytes")] == 4 * groups
    assert values[population.resource("id_bytes")] == 4 * 518_400
    assert values[population.resource("state_bytes")] == 16 * 518_400
    with pytest.raises(ValueError):
        population_values(population, 0, 4)


def test_a_population_draw_is_indirect_over_its_storage(monkeypatch):
    from rendering.quick.render import native_background as nb

    for transition_id in ("disintegrate", "volumetric_dissolve"):
        run = _run(transition_id)
        renderer = _renderer(transition_id)
        scene = renderer.native_scene(run, LOGICAL)
        passes, _targets, _images = nb.scene_program(renderer, scene, nb.TEXTURE, nb.NEXT_TEXTURE, (2560, 1440),
                                                     PIXELS, source_size=(1920, 1080))
        buffers = {b.name: b for b in nb.scene_storage(scene)}
        for population in scene.populations:
            draw = next(p for p in passes if getattr(p, "name", None) == population.draw)
            assert draw.geometry.indirect == population.resource("command") and draw.geometry.draw_count == 1
            assert dict(draw.geometry.storage) == {"PopulationIds": population.resource("ids"),
                                                   "PopulationStates": population.resource("states")}
            assert buffers[population.resource("command")].indirect
            assert all(buffers[population.resource(s)] for s in ("counts", "offsets", "ids", "states"))


def test_a_population_pack_missing_from_the_bake_refuses_the_native_route(monkeypatch, tmp_path):
    from rendering.quick.render import native_background as nb

    assert nb.native_transition_renderer("disintegrate") is not None
    monkeypatch.setattr(nb, "population_pack_paths", lambda transition_id, population: (tmp_path / "missing.qsb",) * 2)
    assert nb.native_transition_renderer("disintegrate") is None                    # control: drawn as Crossfade


def test_the_n52f_bounds_cover_every_form_and_the_sampler_rule_keeps_its_guards():
    """Every single-sampled N5.2f form is judged by the piece-edge class against Python in the core's frame (rule a),
    every form by it under rule (b); Volumetric Dissolve's rule (b) takes its sampler scatter with compact groups past
    one level only. Controls: a compact patch two levels off still fails the sampler rule, and the same one-level
    band fails the default class."""
    import numpy as np

    trc = _trc()
    single = {v for v, o in trc.N52F_VARIANTS.items() if o.get("samples") == 0}
    assert set(trc.N52F_EDGE_FLIPS_A) == single and set(trc.N52F_EDGE_FLIPS_B) == set(trc.N52F_VARIANTS)
    assert all(trc.n52d_gather_free(v) for v in single)
    assert set(trc.N52F_SAMPLER_RULE_B) == {v for v in trc.N52F_VARIANTS if v.startswith("volumetric")}
    reference = np.full((120, 160, 4), 100, np.uint8)
    band = reference.copy()
    band[20:60, 20:100, :3] += 1                                  # a one-level compact band (the mips' filtering)
    allowed = np.zeros((120, 160), bool)
    assert trc.judge_piece_edges(band, reference, 0, allowed, scatter_pixels=4305, compact_past=1)["pass"]
    assert not trc.judge_piece_edges(band, reference, 0, allowed)["pass"]                     # control: default class
    patch = reference.copy()
    patch[20:30, 20:30, :3] += 2                                  # a compact patch past one level
    assert not trc.judge_piece_edges(patch, reference, 1000, np.ones_like(allowed), scatter_pixels=4305,
                                     compact_past=1)["pass"]                                  # control: still caught


# ------------------------------------------------------------------------------------ the pass-clear rule, on the module


def _built_core():
    """The built module (release/native_module) with N5.2h's scene_target_pass_clear, or a skip saying why."""
    import os

    from rendering.native import loader

    module_dir = ROOT / "release" / "native_module"
    if not (os.name == "nt" and (module_dir / f"{loader.MODULE_NAME}.pyd").is_file()):
        pytest.skip(f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd")
    from rendering import native

    core = native.load(module_dir)
    if not hasattr(core.module, "scene_target_pass_clear"):
        pytest.skip("the built module predates scene_target_pass_clear (N5.2h audit): build the branch")
    return core


def _pass_clears(core, program: dict, packs, samples: int = 0) -> dict:
    return json.loads(core.module.scene_target_pass_clear(json.dumps(program), packs, samples))


def test_the_motion_scene_clears_by_its_pass_and_a_target_the_rule_refuses_keeps_the_draw():
    """N5.2h (audit, behaviour): the core's own scenePassClearColour answers the scene target crumble_both_4x declares
    (RGBA8 colour, RGBA16F velocity, four samples) with one clear colour, the colour's; each refused shape answers
    null (the clearing draw). The source is never matched: the module decides."""
    from rendering.native.mode import program_json
    from rendering.quick.render import native_background as nb

    core = _built_core()
    run = _run("crumble_both_4x")
    renderer = _renderer(run.request.transition_id)
    scene = renderer.native_scene(run, LOGICAL)
    passes, targets, images = nb.scene_program(renderer, scene, nb.TEXTURE, nb.NEXT_TEXTURE, (2560, 1440), PIXELS)
    declared, packs = program_json(passes, targets, images=images)
    program = json.loads(declared)
    index = next(i for i, t in enumerate(program["targets"]) if t["name"] == nb.SCENE_TARGET)
    target = program["targets"][index]
    assert target.get("samples", 1) > 1 and velocity_is_one_attachment(target)
    colour = target["colour"][0].get("clear", [0.0, 0.0, 0.0, 0.0])
    assert _pass_clears(core, program, packs)[nb.SCENE_TARGET] == pytest.approx(colour)

    def answer(**changes) -> list | None:
        edited = json.loads(declared)
        velocity = edited["targets"][index]["colour"][1]
        velocity.update(changes)
        return _pass_clears(core, edited, packs)[nb.SCENE_TARGET]

    # Negative controls: the velocity's alpha apart from the colour's (no one clear colour), a clear value other than
    # 0 or 1, and the ABI 37 form's multisampled R16F (measured slower by glClear) each keep the draw.
    assert answer(clear=[0.0, 0.0, 0.0, 1.0 - colour[3]]) is None
    assert answer(clear=[0.5, 0.0, 0.0, colour[3]]) is None
    assert answer(format="r16f", clear=[0.0, 0.0, 0.0, colour[3]]) is None
    # ... while the same R16F single-sampled clears by its pass (the rule's multisample clause alone refused it).
    single = json.loads(declared)
    single["targets"][index]["colour"][1].update(format="r16f", clear=[0.0, 0.0, 0.0, colour[3]])
    assert _pass_clears(core, single, packs, samples=1)[nb.SCENE_TARGET] is not None
