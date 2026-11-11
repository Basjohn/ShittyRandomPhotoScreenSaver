"""Neon Lake's Studio adapter (mode id ``shockwave_grid``) on the shared Studio framework.

Structural: no preset counts, preset values or UI wording are pinned (presets are authored, mutable content); inputs
are the code-owned canonical defaults plus code-owned tier names. Truthfulness is proven against Neon Lake's
production owners: the production offline replay (``logical_tick`` under the pinned clock, in the out-of-process
worker's ``extract``) records what the engine answered the mode's step (bars, onsets, musical level and intensity,
the analysis spectrum), and the Studio's in-process production step over those answers publishes the same
``VisualizerLogicalFrame`` byte for byte at every tick, on a synthetic fixture and a shipped clip; the production
renderer draws them identically. The engine-owned / mode-owned split is proven in both directions on the production
replay. The Settings link, Save To <Preset> and every exit run on the real Settings owners. Nothing shows a window.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import (
    Choice, Colour, Custom, SceneCameraPosition, Slider, Toggle, require_mode_settings,
)
from ui.studio import engine_answers
from ui.studio.engine_answers import source_of
from ui.studio.shockwave_grid_adapter import (
    SHAPE, SHAPER, TERRAIN, VIEW_GROUP, NeonLakeStudioAdapter, NeonLakeStudioEvaluator, build_schema,
    camera_position_bounds, engine_key, engine_values, owned_keys, structure_edit,
)
from ui.studio.shockwave_grid_recorded_inputs import extract, frame_digest, to_inputs

MODE = "shockwave_grid"
PREFIX = MODE + "_"
ROOT = Path(__file__).resolve().parents[1]
CLIP_SECONDS = 3.0
TIER = "High"                    # a code-owned 3D Detail tier (what the store hands the display)


def spec():
    return require_mode_settings(MODE)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults (never an authored preset) at a code-owned tier."""
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec().body_controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    out["scene3d_detail"] = TIER
    return out


def variant_section(variant: str) -> dict:
    """``normal``: canonical. ``reactive``: Terrain Reaction at full strength, Starscape Beat, Glass + Vertices, the
    Moon and a turned view (every mode-owned path the music drives)."""
    values = canonical_section()
    if variant == "reactive":
        control = spec().control
        values.update({PREFIX + "terrain_reaction_enabled": True, PREFIX + "sky_enabled": True,
                       PREFIX + "starscape_beat": True, PREFIX + "sun_enabled": True,
                       PREFIX + "wire_display": control(PREFIX + "wire_display").choices[-1],
                       PREFIX + "sun_mode": control(PREFIX + "sun_mode").choices[-1]})
        for part in ("reaction_strength", "pulses", "peaks", "swell"):
            values[PREFIX + "terrain_" + part] = control(PREFIX + "terrain_" + part).high
        values[PREFIX + "turn"] = control(PREFIX + "turn").high * 0.4
        values[PREFIX + "tilt"] = control(PREFIX + "tilt").high * 0.3
    return values


def technical_keys():
    from core.settings.visualizer_mode_settings import require_mode_settings
    return {control.key for control in require_mode_settings(MODE).technical_controls()}


def shipped_clip():
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips
    clips = studio_clips(recordings_directory())
    if not clips:
        pytest.skip("No shipped Studio clip in this checkout")
    return clips[0]


_EXTRACTS: dict = {}


def recorded(source: str, values, seconds: float | None = CLIP_SECONDS) -> dict:
    """The production replay's record for ``source`` under ``values`` (memoised)."""
    key = (source, json.dumps(sorted((k, repr(v)) for k, v in values.items())), seconds)
    if key not in _EXTRACTS:
        _EXTRACTS[key] = extract(source, values, seconds=seconds)
    return _EXTRACTS[key]


class InlineLoader:
    """The worker's ``extract`` run in this (test) process, finishing at once or when ``land()`` is called."""

    def __init__(self, *, deferred: bool = False, seconds: float | None = CLIP_SECONDS) -> None:
        self.deferred = deferred
        self.seconds = seconds
        self.calls: list = []
        self.waiting: list = []

    def __call__(self, fixture, values, finished):
        self.calls.append((fixture.id, engine_key(values)))
        data = recorded(source_of(fixture), values, self.seconds)
        result = to_inputs(data, replace(fixture, duration=float(data["duration"])))
        if self.deferred:
            self.waiting.append((finished, result))
            return self
        finished(result, "")
        return None

    def land(self) -> None:
        waiting, self.waiting = self.waiting, []
        for finished, result in waiting:
            finished(result, "")

    def cancel(self) -> None:
        self.waiting.clear()


@pytest.fixture(autouse=True)
def _fresh_analysis_cache():
    engine_answers.analysed_cache(MODE).clear()
    yield
    engine_answers.analysed_cache(MODE).clear()


def _clip_evaluator(clip, loader=None, values=None, data=None):
    """An evaluator on ``clip`` as the controller hands it one: the clip analysed (``add_recorded``), then selected."""
    data = data if data is not None else recorded(clip.description, values or canonical_section())
    evaluator = NeonLakeStudioEvaluator(loader=loader or InlineLoader())
    evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
    evaluator.select(clip.id)
    return evaluator


# ------------------------------------------------------------------------------------------ schema
def _vector_elements() -> set[tuple]:
    """Every element of a vector value Settings edits: colour alphas, Camera Position's axes, every Frequency Response
    node slot and both layouts' boundaries and lane strengths, every terrain-shaper node slot, its movable
    boundaries (the first is pinned at the shoreline by the canonical shaper rule) and its lane strengths."""
    from rendering.gl_programs.neon_terrain_reaction import REACTION_LANES
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    canonical = require_canonical_default("widgets.spotify_visualizer")
    out = {(c.key, 3) for c in spec().body_controls if isinstance(c, Colour) and c.alpha}
    out |= {(c.key, i) for c in spec().body_controls if isinstance(c, SceneCameraPosition) for i in range(3)}
    out |= {(SHAPE.nodes, i, axis) for i in range(_MAX_NODES) for axis in (0, 1)}
    for mirrored in (True, False):
        out |= {(SHAPE.notches[mirrored], i, 0) for i in range(len(canonical[SHAPE.notches[mirrored]]))}
        out |= {(SHAPE.lanes[mirrored], label) for label in canonical[SHAPE.lanes[mirrored]]}
    out |= {(SHAPER, "nodes", i, axis) for i in range(_MAX_NODES) for axis in (0, 1)}
    out |= {(SHAPER, "notches", i, 0) for i in range(1, len(REACTION_LANES))}
    out |= {(SHAPER, "lanes", label) for label in REACTION_LANES}
    return out


def _uncovered(properties, schema=None) -> set:
    """Registry keys (every spec control, every Custom row's keys, every technical control) with no Studio property,
    vector elements nothing edits (neither a property nor a shape instrument of ``schema``), and the terrain record
    without its whole-record actions."""
    from tests.test_studio_shape_instrument import shape_uncovered
    schema = schema or build_schema()
    roots = {p.path[0] for p in properties}
    custom_keys = {key for e in spec().entries if isinstance(e, Custom) for key in e.keys}
    keys = {c.key for c in spec().body_controls} | custom_keys | technical_keys()
    missing = (keys - roots) | shape_uncovered(properties, schema.shapes, _vector_elements())
    terrain_actions = {a.id for _group, actions in schema.group_actions for a in actions if a.id.startswith("terrain.")}
    if TERRAIN in roots and not terrain_actions:
        missing.add((TERRAIN, "actions"))
    return missing


def test_every_neon_lake_control_is_reachable_in_the_studio():
    schema = build_schema()
    assert _uncovered(schema.properties) == set()
    groups = {(w.id, g) for w in schema.workspaces for g in w.groups}
    assert all((p.workspace, p.group) in groups for p in schema.properties)
    # Groups are Settings' bucket titles, every bucket has exactly one home, in Settings' order within a workspace.
    titles = [bucket.title for bucket in spec().buckets]
    shown = [g for w in schema.workspaces for g in w.groups if g in titles]
    assert sorted(shown) == sorted(titles)
    for workspace in schema.workspaces:
        buckets = [g for g in workspace.groups if g in titles]
        assert sorted(buckets, key=titles.index) == buckets, workspace.id


def test_coverage_check_detects_a_missing_control_negative_control():
    schema = build_schema()
    properties = schema.properties
    for dropped in (PREFIX + "terrain_height", PREFIX + "wire_display", PREFIX + "starscape_beat", SHAPE.nodes, SHAPER,
                    TERRAIN, PREFIX + "visual_smoothing", PREFIX + "camera_position", PREFIX + "sensitivity",
                    PREFIX + "turn"):
        assert dropped in _uncovered([p for p in properties if p.path[0] != dropped]), dropped
    # Without their shape instruments nothing edits a shaper lane, a shaper node or a Frequency Response node.
    lane = (SHAPER, "lanes", next(iter(require_canonical_default("widgets.spotify_visualizer")[SHAPER]["lanes"])))
    assert {lane, (SHAPER, "nodes", 0, 1), (SHAPE.nodes, 0, 0)} <= _uncovered(properties, replace(
        schema, properties=tuple(p for p in properties if p.instrument != "shape"), shapes=()))
    bare = replace(schema, group_actions=tuple((g, tuple(a for a in acts if not a.id.startswith("terrain.")))
                                               for g, acts in schema.group_actions))
    assert (TERRAIN, "actions") in _uncovered(properties, bare)


def test_instruments_bounds_choices_and_conditions_come_from_the_registry():
    """Every slider is one bounded scalar (Neon Lake has no quiet/peak interval: no ``Range`` control), switches,
    choices with the registry's stored values, colours with an opacity row where the registry stores alpha."""
    from ui.studio.adapter import control_condition
    from ui.studio.schema import QUIET_PEAK
    schema = build_schema()
    view = {a.key for a in (lambda n: (n.orbit_h, n.orbit_v, n.dolly, n.pan_x, n.pan_y))(
        NeonLakeStudioAdapter().navigation())}
    for control in spec().body_controls:
        if isinstance(control, SceneCameraPosition):
            continue
        prop = schema.find(control.key)
        if isinstance(control, Slider):
            assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
            assert prop.instrument == "scalar", control.key
        elif isinstance(control, Choice):
            assert tuple(prop.choice_values or prop.choices) == tuple(control.choices), control.key
        elif isinstance(control, Toggle):
            assert prop.instrument == "switch"
        elif isinstance(control, Colour):
            assert prop.instrument == "colour"
            assert any(p.path == (control.key, 3) for p in schema.properties) == bool(control.alpha)
        if control.key not in view:
            assert prop.when == control_condition(control), control.key
    assert not any(p.instrument == QUIET_PEAK for p in schema.properties)
    # The live view (the framed camera's navigation keys) is preview-only, in its own group.
    in_view = [p for p in schema.properties if p.group == VIEW_GROUP]
    assert {p.id for p in in_view} == view and all(p.view_pose for p in in_view)
    assert not any(p.view_pose for p in schema.properties if p.group != VIEW_GROUP)
    # Camera Position spans the framed camera's eye box in its stored units, inside the registry's admission.
    position = spec().control(PREFIX + "camera_position")
    for index, (low, high) in enumerate(camera_position_bounds()):
        prop = schema.find(f"{position.key}.{index}")
        assert (prop.minimum, prop.maximum) == (low, high) and low < 0.0 < high
        assert position.admit([high] * 3, [0.0] * 3)[index] == pytest.approx(high)


def test_shaper_rules_follow_the_settings_shaper():
    from rendering.gl_programs.neon_terrain_reaction import normalize_terrain_shaper
    schema = build_schema()
    shaper = canonical_section()[SHAPER]
    moved = deepcopy(shaper)
    moved["nodes"][1][0] = 1.0                                   # past its right neighbour: stops at it
    admitted = schema.admit(SHAPER, moved, shaper)
    assert admitted["nodes"][1][0] == pytest.approx(shaper["nodes"][2][0])
    assert admitted == normalize_terrain_shaper(admitted, shaper)              # always a canonical record
    renamed = deepcopy(shaper)
    renamed["notches"][1] = [renamed["notches"][1][0], "Renamed"]
    assert [n[1] for n in schema.admit(SHAPER, renamed, shaper)["notches"]] == [n[1] for n in shaper["notches"]]
    assert set(schema.admit(SHAPER, {**shaper, "lanes": {**shaper["lanes"], "Extra": .3}}, shaper)["lanes"]) == set(
        shaper["lanes"])
    one = {**shaper, "nodes": shaper["nodes"][:1]}
    assert len(schema.admit(SHAPER, one, shaper)["nodes"]) == len(shaper["nodes"])     # never below two nodes
    with pytest.raises(KeyError):
        schema.admit("not_a_neon_lake_key", 1, 0)


def test_structural_edits_shaper_shape_and_terrain():
    from rendering.gl_programs.heightfield import normalize_heightfield
    from rendering.gl_programs.neon_terrain_extent import horizon_extension_cells
    values = {**canonical_section(), PREFIX + "terrain_reaction_enabled": False}
    assert structure_edit("terrain_shaper.add_node", values) is None          # hidden shaper: no shaper edits
    values[PREFIX + "terrain_reaction_enabled"] = True
    count = len(values[SHAPER]["nodes"])
    _label, removed = structure_edit("terrain_shaper.remove_node.1", values)
    assert len(removed[(SHAPER,)]["nodes"]) == count - 1
    _label, added = structure_edit("terrain_shaper.add_node", {**values, SHAPER: removed[(SHAPER,)]})
    assert len(added[(SHAPER,)]["nodes"]) == count
    _label, swapped = structure_edit("terrain_shaper.lane_next.1", values)
    before, after = values[SHAPER]["notches"], swapped[(SHAPER,)]["notches"]
    assert [n[0] for n in after] == [n[0] for n in before] and (after[1][1], after[2][1]) == (before[2][1], before[1][1])
    _label, shape = structure_edit("shape.remove_node.1", values)
    assert set(shape) == {(SHAPE.nodes,)}
    # Terrain: Extend keeps every basin cell exactly; Reset (offered only off the canonical basin) returns to it.
    assert structure_edit("terrain.reset", values) is None
    _label, extended = structure_edit("terrain.extend", values)
    grown = extended[(TERRAIN,)]
    assert grown == normalize_heightfield(grown) and grown["size"] > values[TERRAIN]["size"]
    x0, y0, cells = grown["basin"]
    n, size = values[TERRAIN]["size"], grown["size"]
    assert all(grown["heights"][(y0 + r) * size + x0 + c] == values[TERRAIN]["heights"][r * n + c]
               for r in range(n) for c in range(n))
    _label, reset = structure_edit("terrain.reset", {**values, TERRAIN: grown})
    assert reset[(TERRAIN,)] == normalize_heightfield(values[TERRAIN])
    assert horizon_extension_cells(values[TERRAIN]) is not None
    assert structure_edit("terrain.no_such_action", values) is None


# ------------------------------------------------------------------- engine-owned / mode-owned split
def _flipped(key: str, value):
    """Another admissible value of a mode-owned key (from the registry, or the record's own editor rules)."""
    if key == TERRAIN:
        return structure_edit("terrain.extend", {TERRAIN: value})[1][(TERRAIN,)]
    if key == SHAPER:
        lanes = {label: 1.0 - strength for label, strength in value["lanes"].items()}
        return {**value, "lanes": lanes}
    control = next((c for c in spec().body_controls if c.key == key), None)
    if isinstance(value, bool):
        return not value
    if isinstance(control, SceneCameraPosition):
        return [0.3, 0.2, -0.4]
    if isinstance(value, list):
        return [255 - int(v) for v in value[:3]] + [int(value[3])]
    if isinstance(value, str):
        return next(v for v in control.choices if v != value)
    low, high = (control.low, control.high) if control is not None else (0.0, 1.0)
    return high if abs(float(value) - high) > 1e-6 else low


def _answers(data):
    return [(s["now_ts"], s["answers"]) for s in data["steps"]]


def test_mode_owned_edits_leave_the_engine_answers_unchanged(qt_app):
    """Every key the Studio treats as mode-owned (instant, no re-analysis), Terrain Reaction's switch and amounts
    included, leaves every engine answer of the production replay unchanged; the 3D Detail tier neither."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    owned = owned_keys()
    assert owned <= build_schema().keys
    assert {PREFIX + "terrain_reaction_enabled", TERRAIN, SHAPER} <= owned
    edits = {key: _flipped(key, values[key]) for key in sorted(owned)}
    edits["scene3d_detail"] = "KAK"
    for key, value in edits.items():
        edited = {**values, key: value}
        assert engine_key(edited) == engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) == baseline, key


def test_reaction_reads_are_recorded_even_while_it_is_off_negative_control(qt_app):
    """Without the conditional reads, turning Terrain Reaction on would read engine answers the record lacks."""
    clip = shipped_clip().description
    values = {**canonical_section(), PREFIX + "terrain_reaction_enabled": False}
    bare = engine_answers.EngineAnswerMode(MODE)
    lacking = engine_answers.extract(bare, clip, values, seconds=0.5)
    full = extract(clip, values, seconds=0.5)
    for name in ("get_musical_level", "get_pre_agc_analysis_spectrum"):
        assert all(name in s["answers"] for s in full["steps"]), name
        assert not any(name in s["answers"] for s in lacking["steps"]), name


def test_engine_owned_edits_change_the_engine_answers_negative_control(qt_app):
    """The other direction: an engine-owned edit (shape, lanes, Response sliders, analysis) changes the answers and
    the key, which is what sends it to the worker; the two sets partition the mode's stored keys."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    mirrored = bool(values[SHAPE.mirrored])
    lanes = dict(values[SHAPE.lanes[mirrored]])
    first = next(iter(lanes))
    nodes = [list(n) for n in values[SHAPE.nodes]]
    nodes[0][1] = 0.0 if nodes[0][1] > 0.5 else 1.0
    edits = {SHAPE.nodes: nodes, SHAPE.lanes[mirrored]: {**lanes, first: 0.0 if lanes[first] > 0.5 else 1.0},
             PREFIX + "wave_amplitude": 1.0 if values[PREFIX + "wave_amplitude"] < 0.9 else 0.1,
             PREFIX + "drop_speed": spec().control(PREFIX + "drop_speed").high,
             PREFIX + "bar_count": int(values[PREFIX + "bar_count"]) + 8}
    for key, value in edits.items():
        assert key in engine_values(values)
        edited = {**values, key: value}
        assert engine_key(edited) != engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) != baseline, key
    every = set(k for k in values if k.startswith(PREFIX))
    assert set(engine_values(values)) | (owned_keys() & every) == every               # a partition
    assert not set(engine_values(values)) & owned_keys()


# --------------------------------------------------------------------------------- production parity
def _assert_parity(evaluator, data, values, every: int = 1) -> int:
    compared = 0
    steps = [s for s in data["steps"] if s["frame_sha256"] is not None and s["now_ts"] >= data["origin"]]
    for step in steps[::every]:
        frame = evaluator.evaluate(step["now_ts"] - data["origin"], values)
        assert frame_digest(frame) == step["frame_sha256"], step["now_ts"]
        compared += 1
    assert evaluator.unrecorded_reads == 0           # every engine read was served from the record
    return compared


@pytest.mark.parametrize("variant", ["normal", "reactive"])
@pytest.mark.parametrize("source", ["synthetic", "shipped_clip"])
def test_studio_frames_equal_the_production_replay_tick_for_tick(qt_app, source, variant):
    """The Studio's in-process step publishes the production replay's logical frame (levels, waves, Terrain
    Reaction drives and phase, animation time, every renderer parameter incl. the view, terrain and tier) at every
    tick, and the fixture drives the music paths: waves from onsets, the land from the analysis spectrum."""
    values = variant_section(variant)
    if source == "synthetic":
        evaluator = NeonLakeStudioEvaluator(loader=InlineLoader(seconds=None))
        evaluator.select("mid")
        data = recorded(source_of(evaluator.fixture), values, None)
    else:
        clip = shipped_clip()
        data = recorded(clip.description, values)
        evaluator = _clip_evaluator(clip, values=values)
    assert _assert_parity(evaluator, data, values) >= 200
    frame = evaluator.evaluate(evaluator.fixture.duration * 0.6, values)
    parameters = dict(frame.mode_state.parameters)
    assert frame.mode_id == MODE and parameters["scene3d_detail"] == TIER
    assert frame.mode_state.events                                   # waves from the fixture's onsets
    reacting = any(v > 0.0 for v in frame.mode_state.terrain_bands)
    assert reacting == (variant == "reactive")                       # the land moves only with Terrain Reaction
    evaluator.release()


def test_parity_check_detects_a_perturbed_engine_answer_negative_control(qt_app):
    from ui.studio.replay_engine import encode_answer
    clip = shipped_clip()
    values = canonical_section()
    data = json.loads(json.dumps(recorded(clip.description, values)))
    middle = len(data["steps"]) // 2
    answers = data["steps"][middle]["answers"]
    answers["get_smoothed_bars"] = encode_answer([1.0] * len(answers["get_smoothed_bars"]["list"]))
    evaluator = _clip_evaluator(clip, data=data)
    step = data["steps"][middle]
    assert frame_digest(evaluator.evaluate(step["now_ts"] - data["origin"], values)) != step["frame_sha256"]
    evaluator.release()


def test_a_mode_owned_edit_replays_exactly_without_reanalysis(qt_app):
    """Terrain Reaction switched on, waves, the extended terrain, the shaper and the view: all at once, no worker."""
    clip = shipped_clip()
    values = canonical_section()
    loader = InlineLoader()
    evaluator = _clip_evaluator(clip, loader)
    at = recorded(clip.description, values)["duration"] * 0.7
    before = evaluator.evaluate(at, values)
    calls = len(loader.calls)
    edited = variant_section("reactive")
    edited[PREFIX + "wave_height"] = spec().control(PREFIX + "wave_height").high
    edited[TERRAIN] = _flipped(TERRAIN, values[TERRAIN])
    edited[SHAPER] = _flipped(SHAPER, values[SHAPER])
    edited["scene3d_detail"] = "Balanced"
    after = evaluator.evaluate(at, edited)
    assert len(loader.calls) == calls                                 # no worker for mode-owned values
    production = recorded(clip.description, edited)
    expected = min((s for s in production["steps"] if s["now_ts"] - production["origin"] <= at + 1e-9),
                   key=lambda s: at - (s["now_ts"] - production["origin"]))
    assert frame_digest(after) == expected["frame_sha256"] != frame_digest(before)
    assert evaluator.unrecorded_reads == 0
    evaluator.release()


def test_mode_owned_edits_rewind_under_the_frame_budget_and_equal_production(qt_app):
    """The shared evaluator's exact replay without a stall, on this mode's state (onset ring, Terrain Reaction): a
    mode-owned edit under the Studio's frame budget converges over several evaluations to the production frame,
    rewinding the step state instead of configuring a new controller."""
    clip = shipped_clip()
    values = variant_section("reactive")
    evaluator = _clip_evaluator(clip, values=values)
    at = recorded(clip.description, values)["duration"] * 0.9
    evaluator.evaluate(at, values)
    replays = evaluator.replays
    evaluator.set_frame_budget(0.0)
    edited = {**values, PREFIX + "terrain_motion_speed": spec().control(PREFIX + "terrain_motion_speed").high,
              PREFIX + "terrain_growth_attack": spec().control(PREFIX + "terrain_growth_attack").low,
              PREFIX + "turn": spec().control(PREFIX + "turn").low * 0.3}
    frame = evaluator.evaluate(at, edited)
    for _ in range(400):
        if not evaluator.converging:
            break
        frame = evaluator.evaluate(at, edited)
    assert not evaluator.converging and evaluator.replays == replays and evaluator.rewinds >= 1
    production = recorded(clip.description, edited)
    expected = min((s for s in production["steps"] if s["now_ts"] - production["origin"] <= at + 1e-9),
                   key=lambda s: at - (s["now_ts"] - production["origin"]))
    assert frame_digest(frame) == expected["frame_sha256"]
    evaluator.release()


def test_an_engine_owned_edit_reruns_the_worker_and_lands_exactly(qt_app):
    clip = shipped_clip()
    values = canonical_section()
    loader = InlineLoader(deferred=True)
    evaluator = _clip_evaluator(clip, loader)
    landed = []
    evaluator.set_invalidate(lambda: landed.append(True))
    original = evaluator.evaluate(1.0, values)
    assert not loader.calls                                           # analysed already: no worker
    edited = {**values, PREFIX + "wave_amplitude": 1.0 if values[PREFIX + "wave_amplitude"] < 0.9 else 0.1}
    pending = evaluator.evaluate(1.0, edited)
    assert loader.calls[-1] == (clip.id, engine_key(edited)) and evaluator.analysing
    assert frame_digest(pending) == frame_digest(original)           # the previous answers stay on screen
    production = recorded(clip.description, edited)
    target = next(s for s in production["steps"] if s["now_ts"] - production["origin"] >= 1.0 - 1e-9)
    loader.land()
    assert landed and not evaluator.analysing
    landed_frame = evaluator.evaluate(target["now_ts"] - production["origin"], edited)
    assert frame_digest(landed_frame) == target["frame_sha256"]
    assert frame_digest(pending) != target["frame_sha256"]           # the re-run was needed (negative control)
    evaluator.release()


def test_before_the_first_analysis_lands_the_studio_shows_the_resting_scene(qt_app):
    loader = InlineLoader(deferred=True, seconds=None)
    evaluator = NeonLakeStudioEvaluator(loader=loader)
    evaluator.select("peak")
    frame = evaluator.evaluate(2.0, canonical_section())
    assert frame.playing is False and frame.mode_id == MODE and evaluator.analysing
    assert loader.calls == [("peak", engine_key(canonical_section()))]
    evaluator.release()
    assert not evaluator.analysing and not loader.waiting                 # release cancels the analysis


def test_the_worker_runs_out_of_process_through_the_studios_clip_job(qt_app):
    """The evaluator's default loader: ``ui.studio.shockwave_grid_recorded_inputs`` in its own process
    (``ClipLoadJob``), event driven; its answers replay to the in-process production replay."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop
    values = canonical_section()
    evaluator = NeonLakeStudioEvaluator()
    evaluator.select("quiet")
    landed = []
    evaluator.set_invalidate(lambda: landed.append(True))
    evaluator.evaluate(0.0, values)
    assert evaluator.analysing
    timer = QElapsedTimer()
    timer.start()
    while not landed and timer.elapsed() < 120_000:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert landed and not evaluator.errors, evaluator.errors
    data = recorded(source_of(evaluator.fixture), values, None)        # the same replay, in this process
    assert _assert_parity(evaluator, data, values) >= 200
    evaluator.release()


# ------------------------------------------------------------------------------------- clips + environment
def test_shipped_clips_lead_the_recorded_fixtures_and_drive_waves_and_land(qt_app):
    """The Studio lists the shipped clips first; a shipped clip analysed through Neon Lake's worker carries the
    recording's own onsets and analysis spectrum into waves and Terrain Reaction."""
    from ui.studio.waveform_recorded_inputs import shipped_clips
    adapter = NeonLakeStudioAdapter()
    clips = adapter.recorded_clips()
    shipped = shipped_clips()
    assert shipped and [c.description for c in clips[:len(shipped)]] == [c.description for c in shipped]
    values = variant_section("reactive")
    data = recorded(clips[0].description, values)
    evaluator = _clip_evaluator(clips[0], values=values, data=data)
    seen_events = seen_land = False
    for step in data["steps"][::15]:
        frame = evaluator.evaluate(max(0.0, step["now_ts"] - data["origin"]), values)
        seen_events |= bool(frame.mode_state.events)
        seen_land |= any(v > 0.0 for v in frame.mode_state.terrain_bands)
    assert seen_events and seen_land
    evaluator.release()


def test_neon_lake_reads_no_wallpaper_backdrop(qt_app):
    """Neon Lake renders its own sky: its descriptor declares no backdrop setting, the Studio hands the evaluator no
    photograph, and the frame carries none."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from rendering.quick.display_image_route import presentation_image_from_processed_qimage
    from ui.studio.environment import neutral_image
    assert not get_visualizer_mode_descriptor(MODE).backdrop_setting
    evaluator = NeonLakeStudioEvaluator(loader=InlineLoader(seconds=None))
    evaluator.set_environment(presentation_image_from_processed_qimage(neutral_image(), image_path="studio:test"))
    assert evaluator._environment is None
    evaluator.select("mid")
    frame = evaluator.evaluate(1.0, canonical_section())
    assert dict(frame.mode_state.parameters).get("backdrop") is None
    evaluator.release()


def test_the_studio_adds_nothing_to_the_saver_or_settings_until_opened():
    """Dormancy: asking whether Neon Lake has a Studio (Settings' preset row) imports no adapter, worker or renderer."""
    code = ("import sys; from ui.studio.registry import has_studio; assert has_studio('shockwave_grid'); "
            "bad = [m for m in ('ui.studio.shockwave_grid_adapter', 'ui.studio.shockwave_grid_recorded_inputs', "
            "'ui.studio.engine_answers', 'rendering.quick.visualizer.implementations.shockwave_grid') "
            "if m in sys.modules]; assert not bad, bad")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]


# ------------------------------------------------------------------------------------ Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="NeonLakeStudio",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


@pytest.fixture(autouse=True)
def _no_open_studio():
    from ui.studio.controller import StudioController
    yield
    active = StudioController.active()
    if active is not None:
        active.close()
    assert StudioController.active() is None


@pytest.fixture
def dialog_tab(qt_app, settings_manager):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab
    built = []

    def build():
        settings_manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": MODE,
            "mode_activation": build_visualizer_mode_activation([MODE]),
            f"preset_{MODE}": get_custom_preset_index(MODE)}})
        dialog = QDialog()
        QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
        tab._select_mode_page(MODE)
        built.append(dialog)
        return dialog, tab
    yield build
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


class InlineAdapter(NeonLakeStudioAdapter):
    """The real adapter with the worker run in this process and no recorded clips offered."""

    def recorded_clips(self):
        return ()

    def create_evaluator(self):
        return NeonLakeStudioEvaluator(loader=InlineLoader(seconds=None))


class QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class LightAdapter(InlineAdapter):
    def create_renderer(self):
        return QuietRenderer()


def _surfaces(store, size=(1280, 760)):
    from ui.studio.surface import OffscreenStudioSurface

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=size, present_on_show=False)
        store.append(surface)
        return surface
    return factory


def _settings_restored(controller, dialog) -> bool:
    from ui.studio.controller import StudioController
    presence = controller.presence
    return (controller.state == "closed" and StudioController.active() is None and not presence.concealed
            and presence.widget is dialog and dialog.isEnabled())


def test_the_preset_row_offers_the_neon_lake_studio(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    from ui.studio.registry import has_studio
    assert has_studio(MODE)
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    slider = tab._get_visualizer_preset_slider(MODE)
    assert slider.isAncestorOf(button)
    calls = []
    monkeypatch.setattr(settings_link, "open_mode_studio", lambda t, m: calls.append((t, m)))
    button.click()
    assert calls == [(tab, MODE)]


def test_edits_save_through_the_settings_owners_and_every_exit_restores_settings(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert controller.state == "presented" and controller.presence.concealed
    bridge, session = controller.bridge, controller.session
    stored = lambda: settings_manager.get("widgets")["spotify_visualizer"]      # noqa: E731
    # A slider, a switch, a choice, a colour's opacity, Camera Position, the shaper (node, lane), the Frequency
    # Response shape, the smoothing row, a technical value, and the terrain's Extend action, each through Settings'
    # own save (the Custom rows through their own editors).
    bridge.commitValue(PREFIX + "terrain_height", 0, 0.9)
    assert stored()[PREFIX + "terrain_height"] == pytest.approx(0.9)
    reaction = not bool(session.values[PREFIX + "terrain_reaction_enabled"])
    bridge.commitValue(PREFIX + "terrain_reaction_enabled", 0, reaction)
    assert stored()[PREFIX + "terrain_reaction_enabled"] is reaction
    style = build_schema().find(PREFIX + "wire_display")
    other = next(v for v in style.choice_values if v != session.values[PREFIX + "wire_display"])
    bridge.commitValue(PREFIX + "wire_display", 0, style.choices[style.choice_values.index(other)])
    assert stored()[PREFIX + "wire_display"] == other
    bridge.commitValue(PREFIX + "water_color.3", 0, 120)
    assert stored()[PREFIX + "water_color"][3] == 120
    bridge.commitValue(PREFIX + "camera_position.0", 0, 0.25)
    assert stored()[PREFIX + "camera_position"][0] == pytest.approx(0.25)
    height = session.values[SHAPER]["nodes"][1][1]
    bridge.shapeCommitText(SHAPER, "node", 1, 1, f"{round(1.0 - height, 3)}")
    assert stored()[SHAPER]["nodes"][1][1] == pytest.approx(round(1.0 - height, 3))
    lane = session.values[SHAPER]["notches"][1][1]
    bridge.shapeCommitText(SHAPER, "lane", 1, 1, "0.25")
    assert stored()[SHAPER]["lanes"][lane] == pytest.approx(0.25)
    shape_height = session.values[SHAPE.nodes][0][1]
    bridge.shapeCommitText(SHAPE.nodes, "node", 0, 1, f"{round(1.0 - shape_height, 3)}")
    assert stored()[SHAPE.nodes][0][1] == pytest.approx(round(1.0 - shape_height, 3))
    bridge.commitValue(PREFIX + "visual_smoothing", 0, 0.73)
    assert stored()[PREFIX + "visual_smoothing"] == pytest.approx(0.73)
    bridge.commitValue(PREFIX + "transient_clamp", 0, 0.9)
    assert stored()[PREFIX + "transient_clamp"] == pytest.approx(0.9)
    size = int(session.values[TERRAIN]["size"])
    bridge.runAction("terrain.extend")
    assert int(stored()[TERRAIN]["size"]) > size
    assert int(tab._shockwave_grid_lazy_values[TERRAIN]["size"]) == int(stored()[TERRAIN]["size"])
    assert tab._shockwave_grid_lazy_values[PREFIX + "terrain_shaper"]["lanes"][lane] == pytest.approx(0.25)
    bridge.undo()
    assert int(stored()[TERRAIN]["size"]) == size                                 # one undoable edit
    assert session.values[PREFIX + "wire_display"] == other                     # nothing reverted by a later save
    bridge.requestClose()
    assert _settings_restored(controller, dialog)
    for path in ("escape", "window"):
        surfaces.clear()
        controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
        surfaces[0].pump(2)
        if path == "escape":
            from PySide6.QtCore import QCoreApplication, QEvent, Qt
            from PySide6.QtGui import QKeyEvent
            surfaces[0].host.root.forceActiveFocus()
            for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QCoreApplication.sendEvent(surfaces[0].window, QKeyEvent(kind, Qt.Key.Key_Escape,
                                                                         Qt.KeyboardModifier.NoModifier))
            for _ in range(5):
                QCoreApplication.processEvents()
        else:
            surfaces[0].closeRequested.emit()
        assert _settings_restored(controller, dialog), path


def test_restore_check_detects_a_concealed_settings_negative_control(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert not _settings_restored(controller, dialog)
    controller.close()
    assert _settings_restored(controller, dialog)


def _pump_until(surface, condition, frames=400):
    for _ in range(frames):
        surface.pump()
        if condition():
            return True
    return condition()


def test_the_framed_camera_navigates_and_saves_only_under_the_camera_policy(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    """Orbit = turn / tilt, wheel = the lens (Camera Field of View), Shift+wheel = dolly, pan: the shared framed
    camera's keys and the registry's bounds. The evaluated frame carries the view; without a camera policy that
    saves it the stored view never changes, and Reset returns to it."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surface = surfaces[0]
    surface.pump(2)
    turn_key, tilt_key = get_visualizer_mode_descriptor(MODE).view_orbit_settings
    nav = controller.navigation()
    assert controller.capabilities.as_map()["camera"] and nav is not None
    assert (nav.orbit_h.key, nav.orbit_v.key) == (turn_key, tilt_key)
    assert nav.zoom.key == PREFIX + "camera_fov" and nav.dolly.key in get_visualizer_mode_descriptor(
        MODE).scene_transform_settings
    assert nav.saved_with_camera_policy == {turn_key, tilt_key}
    for axis in (nav.orbit_h, nav.orbit_v, nav.zoom, nav.dolly, nav.pan_x, nav.pan_y):
        control = spec().control(axis.key)
        assert axis.bounds == (control.low, control.high)
    def stored_view():
        return {k: settings_manager.get("widgets")["spotify_visualizer"].get(k) for k in (turn_key, tilt_key)}
    controller.store.set_include_view(False)                         # the preset's camera choice: off
    assert not controller.store.camera_commit_allowed()
    stored_before = stored_view()
    turn0 = float(controller.evaluation_values()[turn_key])
    controller.orbit_by(10_000.0, 10_000.0)                          # far past the bounds: clamped
    assert controller.evaluation_values()[turn_key] == pytest.approx(nav.orbit_h.bounds[1])
    assert controller.evaluation_values()[tilt_key] == pytest.approx(nav.orbit_v.bounds[1])
    assert _pump_until(surface, lambda: controller.last_frame is not None and dict(
        controller.last_frame.mode_state.parameters)[turn_key] == pytest.approx(nav.orbit_h.bounds[1]))
    controller.end_orbit()
    assert stored_view() == stored_before                             # a preview view, never saved
    controller.reset_camera()
    assert float(controller.evaluation_values()[turn_key]) == pytest.approx(turn0)
    # Negative control: with "Include current camera view" on, the same orbit is saved through Settings.
    controller.store.set_include_view(True)
    controller.orbit_by(-10_000.0, -10_000.0)
    controller.end_orbit()
    saved = stored_view()
    assert saved[turn_key] == pytest.approx(nav.orbit_h.bounds[0]) and saved[tilt_key] == pytest.approx(
        nav.orbit_v.bounds[0])
    controller.close()


def _open_live(tab, adapter):
    from ui.studio.settings_link import open_mode_studio
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=adapter, surface_factory=_surfaces(surfaces))
    surface = surfaces[0]
    for _ in range(400):
        surface.pump()
        if controller.bridge.viewportStatus != "preparing":
            break
    assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
    return controller, surface


def _snapshots(surface, frames: dict, extent):
    import numpy as np
    from PySide6.QtCore import QCoreApplication
    images = {}

    def ready(key, width, height, raw):
        images[key] = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4).astype(int)
    surface.viewport.snapshotReady.connect(ready)
    for key, frame in frames.items():
        surface.viewport.request_snapshot(key, frame, (480, 320), (480.0, 320.0), extent, ())
    for _ in range(600):
        surface.pump()
        QCoreApplication.processEvents()
        if len(images) == len(frames):
            break
    surface.viewport.snapshotReady.disconnect(ready)
    assert set(images) == set(frames)
    return images


def _draw_noise(surface, frame, extent):
    """The production renderer's own draw-to-draw difference for one identical frame (largest channel step,
    differing pixels): Neon Lake's renderer is not bit-reproducible across draws (at most a 1/255 step on a small
    share of land pixels), so equal frames are judged against this, measured, never assumed."""
    import numpy as np
    first = _snapshots(surface, {"a": frame}, extent)["a"]
    second = _snapshots(surface, {"b": frame}, extent)["b"]
    diff = np.abs(first - second).max(axis=2)
    return int(diff.max()), int((diff > 0).sum())


def _same_picture(a, b, noise) -> bool:
    """Equal up to the renderer's measured draw noise (one step, at most a percent of the pixels)."""
    import numpy as np
    diff = np.abs(a - b).max(axis=2)
    step = max(1, noise[0])
    return int(diff.max()) <= step and int((diff > 0).sum()) <= max(4 * noise[1], diff.size // 100)


def test_fill_framing_follows_the_live_card(qt_app):
    adapter = NeonLakeStudioAdapter()
    card = (900.0, 260.0)
    framings = adapter.framings(card, {"border_width": 2.0})
    assert adapter.default_framing() == framings[0].id == "fill" and framings[0].fill
    assert framings[0].extent == card and framings[1].extent == card and not framings[1].fill
    assert all(f.extent[0] >= card[0] and f.extent[1] >= card[1] for f in framings)


def test_the_production_renderer_draws_the_production_frame_identically(qt_app, dialog_tab, no_gl_checks):
    """The Studio's live viewport draws the scene, and the production frame and the Studio's frame of the same
    instant render to identical pixels through the production renderer; the variants differ (negative control)."""
    import numpy as np
    from PySide6.QtCore import QPointF
    _dialog, tab = dialog_tab()
    controller, surface = _open_live(tab, InlineAdapter())
    assert controller.bridge.framingId == "fill"
    surface.pump(3)
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    x, y = int(origin.x()), int(origin.y())
    w, h = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    assert surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3].std() > 4.0          # the scene is drawn

    clip = shipped_clip()
    frames = {}
    for variant in ("normal", "reactive"):
        values = variant_section(variant)
        captured: list = []
        data = extract(clip.description, values, seconds=1.5, frames_out=captured)
        evaluator = _clip_evaluator(clip, data=data)
        now, live = captured[int(len(captured) * 0.8)]
        studio = evaluator.evaluate(now - data["origin"], values)
        assert frame_digest(studio) == frame_digest(live)
        frames[f"{variant}/live"], frames[f"{variant}/studio"] = live, studio
        evaluator.release()
    images = _snapshots(surface, frames, controller.presented_extent())
    noise = _draw_noise(surface, frames["reactive/live"], controller.presented_extent())
    assert noise[0] <= 1                                             # the renderer's own draw noise stays tiny
    for variant in ("normal", "reactive"):
        assert images[f"{variant}/live"][..., :3].std() > 2.0
        assert _same_picture(images[f"{variant}/live"], images[f"{variant}/studio"], noise), variant
    assert np.abs(images["normal/live"] - images["reactive/live"]).max() > 20
    controller.close()


def test_scene_colours_never_follow_the_studio_theme(qt_app, dialog_tab, no_gl_checks):
    """Chrome follows the Settings theme; the production render of a frame does not."""
    import numpy as np
    from ui.settings_theme_io import load_settings_theme_file
    from ui.studio.theme import studio_theme
    themes = sorted((ROOT / "themes").glob("*.srtheme"))[:2]
    if len(themes) < 2:
        pytest.skip("needs two theme files")
    _dialog, tab = dialog_tab()
    controller, surface = _open_live(tab, InlineAdapter())
    frame = controller.last_frame
    noise = _draw_noise(surface, frame, controller.presented_extent())
    renders = []
    for path in themes:
        skin = studio_theme(load_settings_theme_file(path))
        controller.bridge.set_theme(skin)
        surface.pump(2)
        assert controller.bridge.theme["panel"] == skin["panel"]
        renders.append(_snapshots(surface, {"frame": frame}, controller.presented_extent())["frame"])
    assert _same_picture(renders[0], renders[1], noise)
    assert not _same_picture(renders[0], 255 - renders[0], noise)       # the comparison sees a real change
    controller.close()


# ---------------------------------------------------------------------- Save To <Preset> (real SettingsDialog)
@pytest.fixture
def real_dialog(qt_app, tmp_path):
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from PySide6.QtCore import QCoreApplication, QEvent
    from ui.settings_dialog import SettingsDialog
    from ui.studio.controller import StudioController
    built = []

    def make():
        manager = SettingsManager(organization="SRPSSFocusedTests", application="NeonLakeStudioPreset",
                                  storage_base_dir=tmp_path / "profile")
        config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
        config.update({"enabled": True, "visualizers_enabled": True, "mode": MODE,
                       "mode_activation": build_visualizer_mode_activation([MODE])})
        widgets = manager.get("widgets", {})
        widgets["spotify_visualizer"] = config
        for family in ("media", "visualizers"):
            set_widget_family_activated(widgets, family, True)
        manager.set("widgets", widgets)
        dialog = SettingsDialog(manager, AnimationManager())
        QCoreApplication.processEvents()
        dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
        built.append((dialog, manager))
        tab = dialog.visualizers_tab
        tab._select_mode_page(MODE)
        return dialog, tab

    yield make
    active = StudioController.active()
    if active is not None:
        active.close()
    for dialog, manager in built:
        dialog.close()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)


@pytest.fixture
def preset_copy(tmp_path, monkeypatch):
    """A tmp copy of Neon Lake's real curated folder, made the preset owner's root (then restored)."""
    from core.settings import visualizer_presets as vp
    root = tmp_path / "presets"
    shutil.copytree(vp.get_visualizer_presets_dir(MODE), root / MODE)
    monkeypatch.setattr(vp, "_presets_root", lambda: root)
    vp.reload_presets(MODE)
    yield root
    monkeypatch.undo()
    vp.reload_presets(MODE)
    for path in (root / MODE).glob("*.json"):
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


@pytest.fixture
def popups(monkeypatch):
    """Patched StyledPopup.exec: records each prompt and answers with ``state['answer']``."""
    from ui.styled_popup import StyledPopup
    seen: list = []
    state = {"answer": "cancel"}

    def fake_exec(popup):
        seen.append({"icon": popup._icon_type, "buttons": [value for _label, value in popup._buttons]})
        popup._result_value = state["answer"] if state["answer"] in seen[-1]["buttons"] else None
        return 1

    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    return seen, state


@pytest.fixture
def offscreen_launch(monkeypatch, no_gl_checks):
    """The preset row's own Open Studio click, with the Neon Lake Studio on the hidden offscreen surface."""
    from ui.studio import settings_link
    real = settings_link.open_mode_studio
    opened = []

    def launch(tab, mode_id):
        surfaces = []
        controller = real(tab, mode_id, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, (960, 600)))
        surfaces[0].pump()
        opened.append(controller)
        return controller

    monkeypatch.setattr(settings_link, "open_mode_studio", launch)
    return opened


def test_save_to_preset_writes_only_the_edited_key_into_a_curated_neon_lake_preset(
        real_dialog, offscreen_launch, preset_copy, popups):
    """Open Studio on a curated Neon Lake slot (the real SettingsDialog's preset row), edit one scalar that slot's
    file authors, and Save To <that preset>: a confirmation first (Cancel writes nothing), then only that key's line
    changes, the file keeps its shape and the preset owner reloads it; Custom stays selected."""
    from core.settings import visualizer_presets as vp
    from core.settings.visualizer_preset_file import key_order
    from ui.studio.schema import SCALAR
    seen, state = popups
    dialog, tab = real_dialog()
    slider = tab._get_visualizer_preset_slider(MODE)
    launcher = getattr(tab, f"_{MODE}_studio_button")
    curated = slider.custom_index() - 1                      # the last curated slot (never the default first)
    path = vp.get_preset_file_path(MODE, curated)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    vp.reload_presets(MODE)
    slider._slider.setValue(curated)
    launcher.click()
    bridge = offscreen_launch[-1].bridge
    names = vp.get_preset_names(MODE)
    assert bridge.presetLabel == names[curated] and bridge.savePresetTarget == ""
    text = path.read_text(encoding="utf-8")
    authored = vp.resolve_preset_payload_settings(MODE, json.loads(text))
    prop = next(p for p in build_schema().properties
                if p.instrument == SCALAR and not p.integer and len(p.path) == 1 and not p.view_pose
                and p.id in authored and text.count(f'"{p.id}"') == 1)
    shown = bridge.values[prop.id]
    span = prop.maximum - prop.minimum
    target = round(prop.minimum + span * (0.25 if float(shown) > prop.minimum + span / 2 else 0.75), 2)
    bridge.commitValue(prop.id, 0, target)
    assert slider.preset_index() == curated                        # held on the preset: no switch to Custom
    assert bridge.savePresetTarget == names[curated]
    before = path.read_bytes()

    state["answer"] = "cancel"
    bridge.saveToPreset()
    assert [p["icon"] for p in seen] == ["question"] and path.read_bytes() == before

    state["answer"] = "save"
    bridge.saveToPreset()
    after = path.read_bytes()
    old_text, new_text = before.decode("utf-8"), after.decode("utf-8")
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    differing = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    assert len(old_lines) == len(new_lines) and len(differing) == 1 and f'"{prop.id}"' in new_lines[differing[0]]
    assert new_text.endswith("\n") == old_text.endswith("\n")
    old_payload, new_payload = json.loads(old_text), json.loads(new_text)
    assert key_order(old_payload) == key_order(new_payload)
    old_resolved = vp.resolve_preset_payload_settings(MODE, old_payload)
    new_resolved = vp.resolve_preset_payload_settings(MODE, new_payload)
    assert new_resolved[prop.id] == pytest.approx(target)
    assert {k: v for k, v in new_resolved.items() if k != prop.id} == {
        k: v for k, v in old_resolved.items() if k != prop.id}
    assert vp.get_preset_settings(MODE, curated)[prop.id] == pytest.approx(target)    # presets were reloaded
    assert slider.preset_index() == curated                        # the preset stays selected, now holding it
