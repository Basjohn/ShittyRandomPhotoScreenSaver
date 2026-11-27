"""N5.6 "Native record and route", sub-box 3: Extruded Bubble's worker record, its route settings and its program as
the native core admits them (``extruded_bubble_native_schema``, ``rendering.native.extruded_bubble_values``,
``rendering.native.extruded_bubble_program``). Each check has a negative control seen failing."""
from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
WINDOW = (1920.0, 1080.0)
#: The core's field-name rule (``mode_schema.cpp`` ``identifier``): lower case, digits and ``_``, 1 to 64 long.
_FIELD_NAME = re.compile(r"[a-z0-9_]{1,64}")


def _mutated(module, *edits):
    """A copy of ``module`` with each (old, new) applied once: a negative control's broken rule."""
    source = Path(module.__file__).read_text(encoding="utf-8")
    for old, new in edits:
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    copy = types.ModuleType(module.__name__ + "_control")
    copy.__file__ = module.__file__
    sys.modules[copy.__name__] = copy
    try:
        exec(compile(source, module.__file__, "exec"), copy.__dict__)
    finally:
        sys.modules.pop(copy.__name__, None)
    return copy


def _presentation(extent=(640.0, 360.0)):
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from tests._visualizer_presentation import resolve_presentation

    return resolve_presentation(policy=get_visualizer_presentation_policy("extruded_bubble"), display_size=WINDOW,
                                viewport_extent=extent, outer_origin=(803.0, 517.0), dpr=1.5, border_width=2.0,
                                corner_radius=8.0)


def _card(presentation) -> dict:
    from rendering.native.composite import composite_geometry, window_pixel_ratio
    from rendering.quick.visualizer.native_route import NativeVisualizerRoute

    pixels = (int(round(WINDOW[0] * 1.5)), int(round(WINDOW[1] * 1.5)))
    geometry = composite_geometry(presentation, quad_aligned=True, pixel_ratio=window_pixel_ratio(WINDOW, pixels))
    route = NativeVisualizerRoute(None, SimpleNamespace())
    return route.card(presentation, SimpleNamespace(presentation=presentation), geometry, (WINDOW, pixels))


def _snapshot(extent=(640.0, 360.0), **state):
    from tests.test_extruded_bubble_renderer import _snapshot as preview

    snapshot = preview()
    logical = snapshot.logical
    if state:
        logical = dataclasses.replace(logical, mode_state=dataclasses.replace(logical.mode_state, **state))
    return dataclasses.replace(snapshot, logical=logical, presentation=_presentation(extent))


def _programs():
    from rendering.native.extruded_bubble_shaders import PROGRAMS
    from rendering.native.extruded_bubble_values import block_members

    return {program: block_members(program) for program in PROGRAMS}


# ------------------------------------------------------------------------------------------------ the names

def _check_names(member_name):
    for program, members in _programs().items():
        for member in members:
            assert _FIELD_NAME.fullmatch(member_name(program, member)), (program, member)


def test_every_member_is_named_by_the_cores_field_name_rule():
    from core.visualizer_engine import extruded_bubble_native_schema as schema
    from rendering.native import extruded_bubble_shaders as shaders

    _check_names(shaders.member_name)
    assert all(_FIELD_NAME.fullmatch(name) for name in schema.FIELD_NAMES)


def test_control_the_programs_own_member_spelling_is_refused_by_the_rule():
    from rendering.native import extruded_bubble_shaders as shaders

    camel = _mutated(shaders, ("    return f\"{program}_{re.sub(r'(?<!^)(?=[A-Z])', '_', member).lower()}\"",
                               "    return f\"{program}_{member}\""))
    with pytest.raises(AssertionError):
        _check_names(camel.member_name)


def test_the_schema_is_a_runtime_schema_of_its_mode():
    from core.visualizer_engine import extruded_bubble_native_schema as schema
    from core.visualizer_engine.native_schema import runtime_schemas, schema_for_mode

    assert runtime_schemas()[schema.SCHEMA_ID] is schema.SCHEMA is schema_for_mode("extruded_bubble")


# ------------------------------------------------------------------------- the record and the settings, split

def _check_filled(settings: dict, record_names: set):
    """Every non-core member of every program is filled exactly once: by the record, by an unscoped setting, or by a
    setting scoped to each of the program's passes; nothing is both a record field and a setting."""
    from rendering.native.extruded_bubble_shaders import member_name
    from rendering.native.extruded_bubble_values import BLUR_PASSES, FACE_PASSES, PROXY_PASSES

    passes = {"probe_backdrop": FACE_PASSES, "proxies": PROXY_PASSES, "blur": BLUR_PASSES}
    plain = {name for name in settings if "@" not in name}
    scoped: dict[str, set] = {}
    for name in settings:
        if "@" in name:
            member, step = name.split("@")
            scoped.setdefault(member, set()).add(step)
    assert not plain & record_names
    for program, members in _programs().items():
        for member in members:
            name = member_name(program, member)
            sources = (name in record_names) + (name in plain) + (scoped.get(name) == set(passes.get(program, ())))
            assert sources == 1, (program, member, sources)


@pytest.mark.qt
def test_the_record_and_the_settings_fill_every_member_once(qt_app):
    from core.visualizer_engine import extruded_bubble_native_schema as schema
    from rendering.native.extruded_bubble_values import settings

    snapshot = _snapshot()
    names = {name for name, _kind, _count in schema.MEMBER_ENTRIES}
    _check_filled(settings(snapshot, _card(snapshot.presentation)), names)


@pytest.mark.qt
def test_control_a_member_no_side_fills_is_seen(qt_app):
    from core.visualizer_engine import extruded_bubble_native_schema as schema
    from rendering.native.extruded_bubble_values import settings

    snapshot = _snapshot()
    values = dict(settings(snapshot, _card(snapshot.presentation)))
    values.pop("shells_u_eye")
    with pytest.raises(AssertionError):
        _check_filled(values, {name for name, _kind, _count in schema.MEMBER_ENTRIES})


def _check_moves(state_values):
    """The frame's phase moves the record's members and nothing of the settings; the card's size moves the settings
    and nothing of the record."""
    from rendering.native.extruded_bubble_values import settings_values, card_geometry

    a, b = _snapshot(motion_phase=1.25), _snapshot(motion_phase=2.5)
    members_a, members_b = state_values(a.logical.mode_state)[0], state_values(b.logical.mode_state)[0]
    assert members_a["backdrop"]["uTime"] != members_b["backdrop"]["uTime"]
    assert members_a["trails"]["uTrailTime"] != members_b["trails"]["uTrailTime"]
    parameters = a.logical.mode_state.parameters
    assert settings_values(parameters, card_geometry(a.presentation)) == settings_values(
        b.logical.mode_state.parameters, card_geometry(b.presentation))
    wide = _snapshot((800.0, 360.0), motion_phase=1.25)
    moved = settings_values(parameters, card_geometry(wide.presentation))
    assert moved["backdrop_u_frame_size"] != settings_values(parameters, card_geometry(a.presentation))[
        "backdrop_u_frame_size"]
    assert state_values(wide.logical.mode_state)[0] == members_a


@pytest.mark.qt
def test_the_frame_moves_the_record_and_the_card_the_settings(qt_app):
    from rendering.native.extruded_bubble_values import state_values

    _check_moves(state_values)


@pytest.mark.qt
def test_control_a_record_that_ignores_the_phase_is_seen(qt_app):
    from rendering.native import extruded_bubble_values as values

    frozen = _mutated(values, ('    common = {"uTime": float(state.motion_phase),', '    common = {"uTime": 0.0,'),
                      ('"trails": {"uTrailTime": float(state.motion_phase)}', '"trails": {"uTrailTime": 0.0}'))
    with pytest.raises(AssertionError):
        _check_moves(frozen.state_values)


# ------------------------------------------------------------------------------------- the core's admission

def _core():
    if not BUILT:
        pytest.skip("the native core is not built in this checkout")
    from rendering import native

    try:
        core = native.load(MODULE_DIR)
    except native.NativeCoreUnavailable as exc:
        pytest.skip(f"the built module is not this commit's ABI ({exc.reason})")
    if int(core.abi) < 47:
        pytest.skip("the module predates ABI 47 (a capture read between transparent passes): its build is pending")
    return core


def _admit(core, mutate=None):
    """The built core's admission of the program with a frame's record and its settings (``mode_blocks``)."""
    from core.visualizer_engine import extruded_bubble_native_schema as schema
    from rendering.native import extruded_bubble_program as program_module
    from rendering.native.extruded_bubble_values import settings
    from rendering.native.mode import _card as card_json, _settings as settings_json, program_json, schema_table_entry
    from rendering.quick.visualizer.native_route import _ModeContent

    snapshot = _snapshot()
    card = _card(snapshot.presentation)
    values = settings(snapshot, card)
    program = program_module.program(program_module.variant_of(snapshot))
    if mutate is not None:
        program, values = mutate(program, dict(values))
    declared, packs = program_json(program["passes"], program["targets"], program["streams"], program["buffers"],
                                   unread=program["unread"])
    shown = card_json(_ModeContent.shown_card(None, card, snapshot))
    blocks, facts = core.module.mode_blocks(json.dumps(dict(schema_table_entry(schema.SCHEMA))), declared, packs,
                                            settings_json(values), schema.encode(snapshot.logical), shown,
                                            tuple(int(v) for v in card["target_size"]))
    return blocks, json.loads(facts)


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
def test_the_built_core_admits_the_program_with_its_record_and_settings(qt_app):
    from rendering.native import extruded_bubble_program as program_module

    blocks, _facts = _admit(_core())
    assert len(blocks) == len(program_module.program((4,))["passes"])


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
def test_control_a_setting_left_out_is_refused_unfilled(qt_app):
    def drop(program, values):
        values.pop("shells_u_eye")
        return program, values
    with pytest.raises(ValueError, match="unfilled"):
        _admit(_core(), drop)


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout")
@pytest.mark.qt
def test_control_a_glass_pass_sampling_the_live_scene_is_still_refused(qt_app):
    """ABI 47 lets the glass passes after the first read the scene's capture; the scene's own colour stays refused."""
    def live(program, values):
        passes = []
        for p in program["passes"]:
            if p.name == "clusters":
                p = dataclasses.replace(p, samplers=tuple(
                    dataclasses.replace(s, texture="scene.colour") if s.texture == "scene.capture_colour" else s
                    for s in p.samplers))
            passes.append(p)
        return {**program, "passes": passes}, values
    with pytest.raises(ValueError, match="reads 'scene' between its transparency target's first pass"):
        _admit(_core(), live)
