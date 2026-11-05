"""Extruded Spectrum's Studio adapter (Rainbow Ghost included) on the shared Studio framework.

Structural: no preset counts, preset values or UI wording are pinned (presets are authored, mutable content); inputs
are the code-owned canonical defaults plus code-owned tier names. Truthfulness is proven against Extruded Spectrum's
production owners: the production offline replay (``logical_tick`` under the pinned clock, in the out-of-process
worker's ``extract``) records what the engine answered the mode's step, and the Studio's in-process production step
over those answers publishes the same ``VisualizerLogicalFrame`` byte for byte at every tick, on a synthetic fixture
and a shipped clip, with and without Mirror Faces reflecting a photograph; the production renderer draws them
identically. The engine-owned / mode-owned split is proven in both directions on the production replay. Nothing
shows a window.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers
from ui.studio.engine_answers import source_of
from ui.studio.extruded_spectrum_adapter import (
    SHAPE, VIEW_GROUP, ExtrudedSpectrumStudioAdapter, ExtrudedSpectrumStudioEvaluator, build_schema,
    control_available, engine_key, engine_values, owned_keys,
)
from ui.studio.extruded_spectrum_recorded_inputs import extract, frame_digest, to_inputs

MODE = "extruded_spectrum"
PREFIX = MODE + "_"
ROOT = Path(__file__).resolve().parents[1]
CLIP_SECONDS = 3.0
TIER = "High"                    # a code-owned 3D Detail tier with reflections (what the store hands the display)
WORKER = "ui.studio.extruded_spectrum_recorded_inputs"


def spec():
    return require_mode_settings(MODE)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults (never an authored preset) at a reflecting tier."""
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec().controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    out["scene3d_detail"] = TIER
    return out


def variant_section(variant: str) -> dict:
    """``normal``: canonical. ``plain``: ghosts without Rainbow Ghost, authored bar colours, a turned view, overflow
    off. ``mirror``: Mirror Faces at full strength (reflecting the environment photograph)."""
    values = canonical_section()
    if variant == "plain":
        turn, tilt = spec().control(PREFIX + "turn"), spec().control(PREFIX + "tilt")
        values.update({PREFIX + "ghosting_enabled": True, PREFIX + "rainbow_ghost": False,
                       PREFIX + "colouring": "Bar Colours", PREFIX + "allow_overflow": False,
                       PREFIX + "turn": turn.high * 0.4, PREFIX + "tilt": tilt.high * 0.6})
    elif variant == "rainbow_ghost":
        values.update({PREFIX + "ghosting_enabled": True, PREFIX + "rainbow_ghost": True,
                       PREFIX + "ghost_alpha": spec().control(PREFIX + "ghost_alpha").high})
    elif variant == "mirror":
        values[PREFIX + "face_mirror"] = spec().control(PREFIX + "face_mirror").high
    return values


def environment():
    from rendering.quick.display_image_route import presentation_image_from_processed_qimage
    from ui.studio.environment import neutral_image
    return presentation_image_from_processed_qimage(neutral_image(), image_path="studio:test-sky")


def technical_keys():
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    return {_storage_key(MODE, d) for d in _control_defs_for_mode(MODE)}


def family_keys():
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    return set(get_owned_mode_setting_keys(MODE, "shared_bar").values()) | set(
        get_owned_mode_setting_keys(MODE, "rainbow").values())


def unavailable_keys():
    return {c.key for c in spec().controls if not control_available(c)}


def shipped_clip():
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips
    clips = studio_clips(recordings_directory())
    if not clips:
        pytest.skip("No shipped Studio clip in this checkout")
    return clips[0]


_EXTRACTS: dict = {}


def recorded(source: str, values, seconds: float | None = CLIP_SECONDS, *, mirror: bool = False) -> dict:
    """The production replay's record for ``source`` under ``values`` (memoised)."""
    key = (source, json.dumps(sorted((k, repr(v)) for k, v in values.items())), seconds, mirror)
    if key not in _EXTRACTS:
        _EXTRACTS[key] = extract(source, values, seconds=seconds, environment=environment() if mirror else None)
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


def _clip_evaluator(clip, loader=None, values=None, data=None, *, mirror=False):
    """An evaluator on ``clip`` as the controller hands it one: the clip analysed (``add_recorded``), then selected."""
    data = data if data is not None else recorded(clip.description, values or canonical_section(), mirror=mirror)
    evaluator = ExtrudedSpectrumStudioEvaluator(loader=loader or InlineLoader())
    if mirror:
        evaluator.set_environment(environment())
    evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
    evaluator.select(clip.id)
    return evaluator


# ------------------------------------------------------------------------------------- schema
def _vector_elements() -> set[tuple]:
    """Every element of a vector value Settings edits: the shared colours' alphas, every shape-node slot (both
    axes), every frequency boundary and lane strength of both layouts."""
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    shared = get_owned_mode_setting_keys(MODE, "shared_bar")
    canonical = require_canonical_default("widgets.spotify_visualizer")
    out = {(c.key, 3) for c in spec().controls if isinstance(c, Colour) and c.alpha}
    out |= {(shared["bar_fill_color"], 3), (shared["bar_border_color"], 3)}
    out |= {(SHAPE.nodes, i, axis) for i in range(_MAX_NODES) for axis in (0, 1)}
    for mirrored in (True, False):
        out |= {(SHAPE.notches[mirrored], i, 0) for i in range(len(canonical[SHAPE.notches[mirrored]]))}
        out |= {(SHAPE.lanes[mirrored], label) for label in canonical[SHAPE.lanes[mirrored]]}
    return out


def _uncovered(properties) -> set:
    """Registry keys (every available spec control, every Custom row's keys, every technical control, the mode's
    shared bar and rainbow families) with no Studio property, plus vector elements no property edits."""
    paths = {tuple(p.path) for p in properties}
    roots = {p.path[0] for p in properties}
    custom_keys = {key for e in spec().entries if isinstance(e, Custom) for key in e.keys}
    keys = ({c.key for c in spec().controls} | custom_keys | technical_keys() | family_keys()) - unavailable_keys()
    return (keys - roots) | {element for element in _vector_elements() if element not in paths}


def test_every_extruded_spectrum_control_is_editable_in_the_studio():
    schema = build_schema()
    assert _uncovered(schema.properties) == set()
    for key in (PREFIX + "ghosting_enabled", PREFIX + "rainbow_ghost", PREFIX + "colouring",
                PREFIX + "solid_bar_hysteresis_enabled"):
        assert key in schema.keys, key
    groups = {(w.id, g) for w in schema.workspaces for g in w.groups}
    assert all((p.workspace, p.group) in groups for p in schema.properties)


def test_coverage_check_detects_a_missing_control_negative_control():
    properties = build_schema().properties
    for dropped in (PREFIX + "rainbow_ghost", PREFIX + "colouring", SHAPE.nodes, PREFIX + "visual_smoothing",
                    PREFIX + "solid_bar_hysteresis_enabled", PREFIX + "bar_border_opacity", PREFIX + "depth",
                    PREFIX + "turn", PREFIX + "sensitivity"):
        assert dropped in _uncovered([p for p in properties if p.path[0] != dropped]), dropped
    lanes = SHAPE.lanes[True]
    label = next(iter(require_canonical_default("widgets.spotify_visualizer")[lanes]))
    assert (lanes, label) in _uncovered([p for p in properties if tuple(p.path) != (lanes, label)])


def test_unavailable_controls_follow_settings_availability(monkeypatch):
    """A control Settings disables (its capability flag off) is not offered; the same registry flag on, it is."""
    from core.settings import visualizer_mode_registry
    flagged = {c.key: c.availability[0] for c in spec().controls if c.availability}
    if not flagged:
        pytest.skip("no Extruded Spectrum control declares an availability flag")
    hidden = unavailable_keys()
    assert hidden.isdisjoint(build_schema().keys)
    for path in set(flagged.values()):
        module, _, name = path.partition(":")
        assert module == visualizer_mode_registry.__name__
        monkeypatch.setattr(visualizer_mode_registry, name, True)
    assert set(flagged) <= build_schema().keys


def test_instruments_bounds_choices_and_conditions_come_from_the_registry():
    from ui.studio.adapter import control_condition
    schema = build_schema()
    for control in spec().controls:
        if control.key in unavailable_keys():
            continue
        prop = schema.find(control.key)
        if isinstance(control, Slider):
            assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
        elif isinstance(control, Choice):
            assert tuple(prop.choice_values or prop.choices) == tuple(control.choices), control.key
        elif isinstance(control, Toggle):
            assert prop.instrument == "switch"
        assert prop.when == control_condition(control), control.key
    # The live view pose (the descriptor's orbit keys) is preview-only, in its own group.
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    view = [p for p in schema.properties if p.group == VIEW_GROUP]
    assert {p.id for p in view} == set(get_visualizer_mode_descriptor(MODE).view_orbit_settings)
    assert all(p.view_pose for p in view)
    assert not any(p.view_pose for p in schema.properties if p.group != VIEW_GROUP)


def test_shape_rules_follow_the_shape_editor():
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    schema = build_schema()
    nodes = [list(n) for n in canonical_section()[SHAPE.nodes]]
    moved = [list(n) for n in nodes]
    moved[1][0] = 1.0                                         # past its right neighbour: stops at it
    admitted = schema.admit(SHAPE.nodes, moved, nodes)
    xs = [x for x, _y in admitted]
    assert admitted[1] == [pytest.approx(nodes[2][0]), nodes[1][1]] and xs == sorted(xs)
    assert schema.admit(SHAPE.nodes, nodes + [[0.5, 0.5]] * _MAX_NODES, nodes) == nodes
    for mirrored in (True, False):
        key = SHAPE.notches[mirrored]
        notches = canonical_section()[key]
        bent = [[x, "Renamed"] for x, _label in notches]
        bent[0][0] = 1.0
        out = schema.admit(key, bent, notches)
        assert [label for _x, label in out] == [label for _x, label in notches]        # labels never change
        assert out[0][0] == pytest.approx(notches[1][0])
        lanes = canonical_section()[SHAPE.lanes[mirrored]]
        assert set(schema.admit(SHAPE.lanes[mirrored], {**lanes, "Extra": 0.3}, lanes)) == set(lanes)
    with pytest.raises(KeyError):
        schema.admit("not_an_extruded_spectrum_key", 1, 0)


def test_structural_shape_edits_address_the_extruded_keys():
    adapter = ExtrudedSpectrumStudioAdapter()
    values = canonical_section()
    _label, removed = adapter.structure_edit("shape.remove_node.1", values)
    assert set(removed) == {(SHAPE.nodes,)} and len(removed[(SHAPE.nodes,)]) == len(values[SHAPE.nodes]) - 1
    fewer = {**values, SHAPE.nodes: removed[(SHAPE.nodes,)]}
    _label, added = adapter.structure_edit("shape.add_node", fewer)
    assert set(added) == {(SHAPE.nodes,)} and len(added[(SHAPE.nodes,)]) == len(values[SHAPE.nodes])
    _label, swapped = adapter.structure_edit("shape.lane_next.1.0", values)
    assert set(swapped) == {(SHAPE.notches[True],)}
    assert adapter.structure_edit("shape.no_such_action", values) is None


# ------------------------------------------------------------------- engine-owned / mode-owned split
def _flipped(key: str, value):
    """Another admissible value of a mode-owned key (from the registry, or a Studio row for Custom keys)."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, list):
        return [255 - int(v) for v in value[:3]] + [int(value[3])]
    control = next((c for c in spec().controls if c.key == key), None)
    if isinstance(value, str):
        return next(v for v in control.choices if v != value)
    low, high = (control.low, control.high) if control is not None else (0.0, 1.0)
    return high if abs(float(value) - high) > 1e-6 else low


def _answers(data):
    return [(s["now_ts"], s["answers"]) for s in data["steps"]]


def test_mode_owned_edits_leave_the_engine_answers_unchanged(qt_app):
    """Every key the Studio treats as mode-owned (instant, no re-analysis) leaves every engine answer of the
    production replay unchanged, so no mode-owned edit can need the worker; the 3D Detail tier neither."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    owned = owned_keys()
    assert owned and owned - unavailable_keys() <= build_schema().keys
    edits = {key: _flipped(key, values[key]) for key in sorted(owned)}
    edits["scene3d_detail"] = "KAK"
    for key, value in edits.items():
        edited = {**values, key: value}
        assert engine_key(edited) == engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) == baseline, key


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
    nodes[1][1] = 0.0 if nodes[1][1] > 0.5 else 1.0
    edits = {SHAPE.nodes: nodes, SHAPE.lanes[mirrored]: {**lanes, first: 0.0 if lanes[first] > 0.5 else 1.0},
             PREFIX + "wave_amplitude": 1.0 if values[PREFIX + "wave_amplitude"] < 0.9 else 0.1,
             PREFIX + "drop_speed": spec().control(PREFIX + "drop_speed").high,
             SHAPE.mirrored: not mirrored, PREFIX + "bar_count": int(values[PREFIX + "bar_count"]) + 8}
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


@pytest.mark.parametrize("variant", ["normal", "plain"])
@pytest.mark.parametrize("source", ["synthetic", "shipped_clip"])
def test_studio_frames_equal_the_production_replay_tick_for_tick(qt_app, source, variant):
    """The Studio's in-process step publishes the production replay's logical frame (common bars, peaks, ghosts,
    animation time, every renderer parameter incl. the view and the tier, identities and flags) at every tick."""
    values = variant_section(variant)
    if source == "synthetic":
        evaluator = ExtrudedSpectrumStudioEvaluator(loader=InlineLoader(seconds=None))
        evaluator.select("mid")
        data = recorded(source_of(evaluator.fixture), values, None)
    else:
        clip = shipped_clip()
        data = recorded(clip.description, values)
        evaluator = _clip_evaluator(clip, values=values)
    assert _assert_parity(evaluator, data, values) >= 200
    frame = evaluator.evaluate(evaluator.fixture.duration * 0.6, values)
    parameters = dict(frame.mode_state.parameters)
    assert frame.mode_id == MODE and frame.mode_state.ghost_bars and parameters["scene3d_detail"] == TIER
    assert parameters[PREFIX + "rainbow_ghost"] is (variant == "normal")
    evaluator.release()


def test_mirror_faces_reflect_the_same_photograph_as_production_tick_for_tick(qt_app):
    """With Mirror Faces on, the production replay and the Studio carry the same backdrop (production's reflection
    rule on the environment photograph) in every frame; without the environment there is none."""
    clip = shipped_clip()
    values = variant_section("mirror")
    data = recorded(clip.description, values, 1.5, mirror=True)
    evaluator = _clip_evaluator(clip, values=values, data=data, mirror=True)
    assert _assert_parity(evaluator, data, values, every=3) >= 30
    frame = evaluator.evaluate(1.0, values)
    assert dict(frame.mode_state.parameters)["backdrop"] is not None
    evaluator.release()
    bare = _clip_evaluator(clip, values=values, data=data)                        # no photograph: no backdrop
    assert dict(bare.evaluate(1.0, values).mode_state.parameters)["backdrop"] is None
    bare.release()


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


def test_one_production_step_per_recorded_tick_and_exact_replay(qt_app):
    clip = shipped_clip()
    values = canonical_section()
    data = recorded(clip.description, values)
    evaluator = _clip_evaluator(clip)
    end = data["duration"]
    evaluator.evaluate(end, values)
    assert evaluator.steps_run == len(data["steps"])
    again = evaluator.evaluate(end, values)
    assert evaluator.steps_run == len(data["steps"])                 # same instant: no step, same frame
    assert frame_digest(again) == data["steps"][-1]["frame_sha256"]
    evaluator.release()


def test_a_mode_owned_edit_replays_exactly_without_reanalysis(qt_app):
    clip = shipped_clip()
    values = canonical_section()
    loader = InlineLoader()
    evaluator = _clip_evaluator(clip, loader)
    at = recorded(clip.description, values)["duration"] * 0.7
    before = evaluator.evaluate(at, values)
    calls = len(loader.calls)
    edited = variant_section("plain")
    edited[PREFIX + "ghost_decay"] = spec().control(PREFIX + "ghost_decay").low
    edited[PREFIX + "depth"] = spec().control(PREFIX + "depth").high
    edited[PREFIX + "visual_smoothing"] = 0.9
    edited[PREFIX + "bar_fill_color"] = [200, 40, 90, 255]
    edited["scene3d_detail"] = "Balanced"
    after = evaluator.evaluate(at, edited)
    assert len(loader.calls) == calls                                 # no worker for mode-owned values
    production = recorded(clip.description, edited)
    expected = min((s for s in production["steps"] if s["now_ts"] - production["origin"] <= at + 1e-9),
                   key=lambda s: at - (s["now_ts"] - production["origin"]))
    assert frame_digest(after) == expected["frame_sha256"] != frame_digest(before)
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
    edited = dict(values)
    nodes = [list(n) for n in values[SHAPE.nodes]]
    nodes[1][1] = 0.0 if nodes[1][1] > 0.5 else 1.0
    edited[SHAPE.nodes] = nodes
    pending = evaluator.evaluate(1.0, edited)
    assert loader.calls[-1] == (clip.id, engine_key(edited)) and evaluator.analysing
    # Meanwhile the previous answers stay on screen, under the engine values they were recorded with.
    assert frame_digest(pending) == frame_digest(original)
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
    evaluator = ExtrudedSpectrumStudioEvaluator(loader=loader)
    evaluator.select("peak")
    frame = evaluator.evaluate(2.0, canonical_section())
    assert frame.playing is False and frame.mode_id == MODE and evaluator.analysing
    assert loader.calls == [("peak", engine_key(canonical_section()))]
    evaluator.release()
    assert not evaluator.analysing and not loader.waiting                 # release cancels the analysis


def test_the_worker_runs_out_of_process_through_the_studios_clip_job(qt_app):
    """The evaluator's default loader: the worker in its own process (``ClipLoadJob``), event driven."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop
    values = canonical_section()
    evaluator = ExtrudedSpectrumStudioEvaluator()
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


def test_the_app_entry_point_runs_the_worker_as_a_frozen_build_does(tmp_path):
    """``main.py --studio-clip-worker ui.studio.extruded_spectrum_recorded_inputs`` (the frozen path) records the
    same answers and frames as the in-process replay."""
    from ui.studio.waveform_recorded_inputs import run_frozen_worker, WORKER_FLAG
    clip = shipped_clip()
    values = canonical_section()
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(values), encoding="utf-8")
    output = tmp_path / "inputs.json"
    done = subprocess.run([sys.executable, str(ROOT / "main.py"), WORKER_FLAG, WORKER,
                           clip.description, str(settings), str(output), "1.0", "/s"], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    data = json.loads(output.read_text(encoding="utf-8"))
    local = extract(clip.description, values, seconds=1.0)
    assert _answers(data) == _answers(local)
    assert [s["frame_sha256"] for s in data["steps"]] == [s["frame_sha256"] for s in local["steps"]]
    assert run_frozen_worker(["exe", WORKER_FLAG, WORKER]) is None   # too few args


# ------------------------------------------------------------------------------------ Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="ExtrudedSpectrumStudio",
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


class InlineAdapter(ExtrudedSpectrumStudioAdapter):
    """The real adapter with the worker run in this process and no recorded clips offered."""

    def recorded_clips(self):
        return ()

    def create_evaluator(self):
        return ExtrudedSpectrumStudioEvaluator(loader=InlineLoader(seconds=None))


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


def test_custom_body_offers_the_extruded_spectrum_studio(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    from ui.studio.registry import has_studio
    assert has_studio(MODE)
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    assert getattr(tab, f"_{MODE}_settings_container").isAncestorOf(button)
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
    assert "scene3d_detail" in controller.session.values                  # the 3D tier the display would use
    bridge, session = controller.bridge, controller.session
    stored = lambda: settings_manager.get("widgets")["spotify_visualizer"]      # noqa: E731
    schema = build_schema()
    # The Rainbow row's colouring (a bucketless choice), Rainbow Ghost, sliders, the smoothing row (three keys), the
    # shape editor (node, boundary, lane), the shared bar family (alpha, border opacity) and a technical value,
    # each through Settings' own save.
    colouring = schema.find(PREFIX + "colouring")
    other = next(v for v in colouring.choice_values if v != session.values[PREFIX + "colouring"])
    bridge.commitValue(PREFIX + "colouring", 0, colouring.choices[colouring.choice_values.index(other)])
    assert stored()[PREFIX + "colouring"] == other
    ghost = not bool(session.values[PREFIX + "rainbow_ghost"])
    bridge.commitValue(PREFIX + "rainbow_ghost", 0, ghost)
    assert stored()[PREFIX + "rainbow_ghost"] is ghost
    bridge.commitValue(PREFIX + "ghost_decay", 0, 0.8)
    assert stored()[PREFIX + "ghost_decay"] == pytest.approx(0.8)
    bridge.commitValue(PREFIX + "depth", 0, 2.0)
    assert stored()[PREFIX + "depth"] == pytest.approx(2.0)
    bridge.commitValue(PREFIX + "visual_smoothing", 0, 0.73)
    assert stored()[PREFIX + "visual_smoothing"] == pytest.approx(0.73)
    stabilize = not bool(session.values[PREFIX + "solid_bar_hysteresis_enabled"])
    bridge.commitValue(PREFIX + "solid_bar_hysteresis_enabled", 0, stabilize)
    assert stored()[PREFIX + "solid_bar_hysteresis_enabled"] is stabilize
    height = session.values[SHAPE.nodes][0][1]
    bridge.commitValue(f"{SHAPE.nodes}.0.1", 0, round(1.0 - height, 3))
    assert stored()[SHAPE.nodes][0][1] == pytest.approx(round(1.0 - height, 3))
    mirrored = bool(session.values[SHAPE.mirrored])
    notches, lanes = SHAPE.notches[mirrored], SHAPE.lanes[mirrored]
    low, high = session.values[notches][0][0], session.values[notches][1][0]
    bridge.commitValue(f"{notches}.0", 0, round((low + high) / 2, 3))
    assert stored()[notches][0][0] == pytest.approx(round((low + high) / 2, 3))
    lane = next(iter(session.values[lanes]))
    bridge.commitValue(f"{lanes}.{lane}", 0, 0.25)
    assert stored()[lanes][lane] == pytest.approx(0.25)
    bridge.commitValue(PREFIX + "bar_fill_color.3", 0, 120)
    assert stored()[PREFIX + "bar_fill_color"][3] == 120
    bridge.commitValue(PREFIX + "bar_border_opacity", 0, 0.4)
    assert stored()[PREFIX + "bar_border_opacity"] == pytest.approx(0.4)
    bridge.commitValue(PREFIX + "transient_clamp", 0, 0.9)
    assert stored()[PREFIX + "transient_clamp"] == pytest.approx(0.9)
    assert session.values[PREFIX + "colouring"] == other                 # nothing reverted by a later save
    bridge.requestClose()
    assert _settings_restored(controller, dialog)
    assert tab.extruded_spectrum_shape_editor.get_nodes()[0][1] == pytest.approx(round(1.0 - height, 3))
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


def test_viewport_orbit_is_a_preview_view_of_the_modes_own_pose(qt_app, dialog_tab, settings_manager, no_gl_checks):
    """Drag orbits the descriptor's turn / tilt within the registry bounds; the evaluated frame carries the view;
    with no camera policy to save it the stored view never changes, and Reset returns to it."""
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
    assert (nav.zoom, nav.dolly, nav.pan_x, nav.pan_y) == (None, None, None, None)     # free orbit only
    stored_before = {k: settings_manager.get("widgets")["spotify_visualizer"].get(k) for k in (turn_key, tilt_key)}
    turn0 = float(controller.evaluation_values()[turn_key])
    controller.orbit_by(10_000.0, 10_000.0)                          # far past the bounds: clamped
    assert controller.evaluation_values()[turn_key] == pytest.approx(nav.orbit_h.bounds[1])
    assert controller.evaluation_values()[tilt_key] == pytest.approx(nav.orbit_v.bounds[1])
    assert _pump_until(surface, lambda: controller.last_frame is not None and dict(
        controller.last_frame.mode_state.parameters)[turn_key] == pytest.approx(nav.orbit_h.bounds[1]))
    controller.end_orbit()
    assert {k: settings_manager.get("widgets")["spotify_visualizer"].get(k)
            for k in (turn_key, tilt_key)} == stored_before                 # a preview view, never saved
    controller.reset_camera()
    assert float(controller.evaluation_values()[turn_key]) == pytest.approx(turn0)
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
    for _ in range(400):
        surface.pump()
        QCoreApplication.processEvents()
        if len(images) == len(frames):
            break
    surface.viewport.snapshotReady.disconnect(ready)
    assert set(images) == set(frames)
    return images


def _pump_until(surface, condition, frames=400):
    for _ in range(frames):
        surface.pump()
        if condition():
            return True
    return condition()


def test_fill_framing_follows_the_live_card(qt_app):
    """Fill (the default) is the live card's world grown to the viewport's shape; Live Card is the card exactly."""
    adapter = ExtrudedSpectrumStudioAdapter()
    card = (900.0, 260.0)
    framings = adapter.framings(card, {"border_width": 2.0})
    assert adapter.default_framing() == framings[0].id == "fill" and framings[0].fill
    assert framings[0].extent == card and framings[1].extent == card and not framings[1].fill
    assert all(f.extent[0] >= card[0] and f.extent[1] >= card[1] for f in framings)


def test_the_production_renderer_fills_the_viewport_and_draws_the_production_frame_identically(
        qt_app, dialog_tab, no_gl_checks):
    import numpy as np
    from PySide6.QtCore import QPointF
    _dialog, tab = dialog_tab()
    controller, surface = _open_live(tab, InlineAdapter())
    assert controller.bridge.framingId == "fill"
    assert surface.viewport.width() == pytest.approx(surface.host.slot.width())
    surface.pump(3)
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    x, y = int(origin.x()), int(origin.y())
    w, h = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    assert surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3].std() > 4.0           # bars drawn

    clip = shipped_clip()
    frames = {}
    for variant in ("normal", "plain", "mirror"):
        values = variant_section(variant)
        mirror = variant == "mirror"
        captured: list = []
        data = extract(clip.description, values, seconds=1.5, frames_out=captured,
                       environment=environment() if mirror else None)
        evaluator = _clip_evaluator(clip, data=data, mirror=mirror)
        now, live = captured[int(len(captured) * 0.8)]
        studio = evaluator.evaluate(now - data["origin"], values)
        assert frame_digest(studio) == frame_digest(live)
        frames[f"{variant}/live"], frames[f"{variant}/studio"] = live, studio
        evaluator.release()
    images = _snapshots(surface, frames, controller.presented_extent())
    for variant in ("normal", "plain", "mirror"):
        assert images[f"{variant}/live"][..., :3].std() > 2.0
        assert np.array_equal(images[f"{variant}/live"], images[f"{variant}/studio"]), variant
    # The variants render differently (negative control on the pairs): view and colouring; the reflection.
    assert np.abs(images["normal/live"] - images["plain/live"]).max() > 20
    assert np.abs(images["normal/live"] - images["mirror/live"]).max() > 20
    controller.close()


def test_rainbow_ghost_colours_only_the_ghost_columns(qt_app, dialog_tab, no_gl_checks):
    """Same instant with Rainbow Ghost on and off: the pixels it changes are a subset of the pixels the ghost
    columns themselves draw (ghosting on vs off, in either ghost colouring: a rainbow ghost over a spectral face of
    its own hue can leave that face's pixels as they were), so faces, edges and reflection are untouched; with
    ghosting off it changes nothing."""
    import numpy as np
    _dialog, tab = dialog_tab()
    controller, surface = _open_live(tab, InlineAdapter())
    clip = shipped_clip()
    frames = {}
    for ghosting in (True, False):
        for rainbow in (True, False):
            values = variant_section("rainbow_ghost")
            values[PREFIX + "ghosting_enabled"] = ghosting
            values[PREFIX + "rainbow_ghost"] = rainbow
            evaluator = _clip_evaluator(clip, values=values)
            frames[(ghosting, rainbow)] = evaluator.evaluate(evaluator.fixture.duration * 0.8, values)
            evaluator.release()
    images = _snapshots(surface, {repr(k): f for k, f in frames.items()}, controller.presented_extent())
    on, off = images[repr((True, True))], images[repr((True, False))]
    assert np.abs(on - off).max() > 20                                       # ghosts recoloured
    recoloured = np.abs(on - off).max(axis=2) > 0
    ghost_pixels = ((np.abs(on - images[repr((False, True))]).max(axis=2) > 0)
                    | (np.abs(off - images[repr((False, False))]).max(axis=2) > 0))
    assert recoloured.any() and not (recoloured & ~ghost_pixels).any()
    assert ghost_pixels.mean() < 0.5                         # the ghosts are a part of the picture (sanity)
    assert np.array_equal(images[repr((False, True))], images[repr((False, False))])   # no ghosts: no effect
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
    renders = []
    for path in themes:
        skin = studio_theme(load_settings_theme_file(path))
        controller.bridge.set_theme(skin)
        surface.pump(2)
        assert controller.bridge.theme["panel"] == skin["panel"]
        renders.append(_snapshots(surface, {"frame": frame}, controller.presented_extent())["frame"])
    assert np.array_equal(renders[0], renders[1])
    controller.close()


# ---------------------------------------------------------------- framework pieces a frameless 3D mode relies on
def _overflowing_grab(tab, adapter):
    """The Studio at Live Card framing with a steep turned view (the bars overflow their card): the window grab
    and the viewport slot's top edge in window pixels."""
    from PySide6.QtCore import QPointF
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    controller, surface = _open_live(tab, adapter)
    controller.bridge.selectFraming("card")
    turn_key, tilt_key = get_visualizer_mode_descriptor(MODE).view_orbit_settings
    controller.set_pose(turn_key, spec().control(turn_key).high * 0.6)
    controller.set_pose(tilt_key, spec().control(tilt_key).high * 0.8)
    controller.seek(controller.evaluator.fixture.duration * 0.6)
    surface.pump(20)
    top = int(surface.host.slot.mapToScene(QPointF(0.0, 0.0)).y())
    image = surface.grab()
    controller.close()
    return image, top


def test_overflow_stays_inside_the_viewport_slot(qt_app, dialog_tab, no_gl_checks, monkeypatch):
    """A frameless mode may overflow its card up to the window in production; in the Studio the viewport slot is
    that window: the chrome above it is drawn exactly as with no scene at all. Without the slot's clip the same
    view paints over the chrome (negative control)."""
    import numpy as np
    from ui.studio.viewport import StudioRenderNode
    _dialog, tab = dialog_tab()
    reference, top = _overflowing_grab(tab, LightAdapter())
    clipped, top_clipped = _overflowing_grab(tab, InlineAdapter())
    assert top == top_clipped and top > 20
    assert np.array_equal(clipped[:top - 1], reference[:top - 1])
    monkeypatch.setattr(StudioRenderNode, "apply_clip", staticmethod(lambda state: None))
    unclipped, _top = _overflowing_grab(tab, InlineAdapter())
    assert not np.array_equal(unclipped[:top - 1], reference[:top - 1])


def test_the_presentation_pixel_ratio_comes_from_the_item_mapping():
    """The live viewport draws into the whole window target (wider than a letterboxed item), a snapshot into a target
    of the item's own pixel size: both give the true target pixels per item unit."""
    from ui.studio.adapter import RenderCard
    from ui.studio.framed import ContractModeRenderer

    def card(viewport, logical, window_logical_width):
        matrix = (2.0 / window_logical_width,) + (0.0,) * 15
        return RenderCard(viewport=viewport, logical_size=logical, matrix_values=matrix, quad_vao=0)
    live = card((0, 0, 3200, 1800), (590.0, 393.0), 1600.0)            # a 2x window, a letterboxed item
    snapshot = card((0, 0, 960, 640), (480.0, 320.0), 480.0)
    assert ContractModeRenderer.pixel_ratio(live) == pytest.approx(2.0)
    assert ContractModeRenderer.pixel_ratio(snapshot) == pytest.approx(2.0)
    assert live.viewport[2] / live.logical_size[0] != pytest.approx(2.0)   # the target/item ratio would not be
