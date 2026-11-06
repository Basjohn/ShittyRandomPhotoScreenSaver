"""Oscilloscope's Studio adapter on the shared Studio framework.

Structural: no preset counts, preset values or UI wording are pinned (presets are authored, mutable content); inputs
are the code-owned canonical defaults and registry choices. Truthfulness is proven against Oscilloscope's production
owners: the production offline replay (``logical_tick`` under the pinned clock, in the out-of-process worker's
``extract``) records what the engine answered the mode's step (the capture history *by identity*, the waveform,
onsets, musical level and intensity, the analysis spectrum), and the Studio's in-process production step over those
answers publishes the same ``VisualizerLogicalFrame`` byte for byte at every tick, on a synthetic fixture and a
shipped clip; the production renderer draws them identically. The engine-owned / mode-owned split is proven in both
directions on the production replay. The Settings link, Save To <Preset> and every exit run on the real Settings
owners. Nothing shows a window.
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
from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers
from ui.studio.engine_answers import source_of
from ui.studio.oscilloscope_adapter import (
    OscilloscopeStudioAdapter, OscilloscopeStudioEvaluator, build_schema, engine_key, engine_values, owned_keys,
)
from ui.studio.oscilloscope_recorded_inputs import extract, frame_digest, to_inputs

MODE = "oscilloscope"
PREFIX = "osc_"
ROOT = Path(__file__).resolve().parents[1]
CLIP_SECONDS = 3.0


def spec():
    return require_mode_settings(MODE)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults (never an authored preset)."""
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec().controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    return out


def variant_section(variant: str) -> dict:
    """``normal``: canonical. ``phase``: the registry's last display (the X/Y figure), the longest afterglow and the
    reactions at full (every mode-owned path the music drives)."""
    values = canonical_section()
    if variant == "phase":
        control = spec().control
        values[PREFIX + "display"] = control(PREFIX + "display").choices[-1]
        for key in ("afterglow", "spectral", "flare", "pulse", "delay"):
            values[PREFIX + key] = control(PREFIX + key).high
    return values


def technical_keys():
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    return {_storage_key(MODE, d) for d in _control_defs_for_mode(MODE)}


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
    evaluator = OscilloscopeStudioEvaluator(loader=loader or InlineLoader())
    evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
    evaluator.select(clip.id)
    return evaluator


def _at(data, time: float) -> dict:
    """The production step published at fixture ``time`` (the last tick at or before it)."""
    return min((s for s in data["steps"] if s["frame_sha256"] and s["now_ts"] - data["origin"] <= time + 1e-9),
               key=lambda s: time - (s["now_ts"] - data["origin"]))


# ------------------------------------------------------------------------------------------ schema
def _uncovered(properties) -> set:
    """Registry keys (every spec control, every Custom row's keys, every technical control) with no Studio property,
    and colour alphas no property edits."""
    paths = {tuple(p.path) for p in properties}
    roots = {p.path[0] for p in properties}
    custom_keys = {key for e in spec().entries if isinstance(e, Custom) for key in e.keys}
    keys = {c.key for c in spec().controls} | custom_keys | technical_keys()
    alphas = {(c.key, 3) for c in spec().controls if isinstance(c, Colour) and c.alpha}
    return (keys - roots) | (alphas - paths)


def test_every_oscilloscope_control_is_reachable_in_the_studio():
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
    properties = build_schema().properties
    alpha = next(c.key for c in spec().controls if isinstance(c, Colour) and c.alpha)
    for dropped in (PREFIX + "display", PREFIX + "afterglow", PREFIX + "beam_color", MODE + "_sensitivity"):
        assert dropped in _uncovered([p for p in properties if p.path[0] != dropped]), dropped
    assert (alpha, 3) in _uncovered([p for p in properties if tuple(p.path) != (alpha, 3)])


def test_instruments_bounds_choices_and_conditions_come_from_the_registry():
    """Every slider is one bounded scalar (Oscilloscope has no quiet/peak interval: no ``Range`` control), choices
    carry the registry's stored values, colours have an opacity row exactly where the registry stores alpha, and
    every row keeps the registry's condition (Phase Delay only for Phase, the graticule colour only with a scale)."""
    from ui.studio.adapter import control_condition
    from ui.studio.schema import QUIET_PEAK
    schema = build_schema()
    for control in spec().controls:
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
        assert prop.when == control_condition(control), control.key
    assert not any(p.instrument == QUIET_PEAK for p in schema.properties)
    assert not OscilloscopeStudioAdapter().capabilities().as_map()["camera"]
    with pytest.raises(KeyError):
        schema.admit("not_an_oscilloscope_key", 1, 0)


# ------------------------------------------------------------------------------------ array recording
def test_recorded_arrays_are_numbered_by_identity_and_served_as_one_object():
    """The shared recorder numbers arrays by identity (equal content in another object is another number), the
    payload round-trips the bytes exactly, and the Studio side serves one read-only object per number; without a
    pool an array is still refused (every other engine-answer mode records exactly as before)."""
    import numpy as np
    from ui.studio.replay_engine import RecordedArrays, decode_answer, encode_answer, served_arrays
    first = np.frombuffer(np.arange(8, dtype="<f4").tobytes(), dtype="<f4")
    twin = np.frombuffer(first.tobytes(), dtype="<f4")
    pool = RecordedArrays()
    assert encode_answer(first, pool) == encode_answer(first, pool) == {"array": 0}
    assert encode_answer(twin, pool) == {"array": 1}
    with pytest.raises(TypeError):
        encode_answer(first)
    payload = pool.payload()
    arrays = served_arrays(json.loads(json.dumps({k: v for k, v in payload.items() if k != "blob"})), payload["blob"])
    assert len(arrays) == 2 and all(np.array_equal(a, first) and not a.flags.writeable for a in arrays)
    assert decode_answer({"array": 1}, arrays) is decode_answer({"tuple": [{"array": 1}]}, arrays)[0] is arrays[1]


# ------------------------------------------------------------------- engine-owned / mode-owned split
def _flipped(key: str, value):
    """Another admissible value of a mode-owned key (from the registry)."""
    control = spec().control(key)
    if isinstance(value, bool):
        return not value
    if isinstance(value, list):
        return [255 - int(v) for v in value[:3]] + [int(value[3])]
    if isinstance(value, str):
        return next(v for v in control.choices if v != value)
    return control.high if abs(float(value) - control.high) > 1e-6 else control.low


def _answers(data):
    return [(s["now_ts"], s["answers"]) for s in data["steps"]]


def test_mode_owned_edits_leave_the_engine_answers_unchanged(qt_app):
    """Every key the Studio treats as mode-owned (instant, no re-analysis) leaves every engine answer of the
    production replay unchanged, the recorded arrays included."""
    clip = shipped_clip().description
    values = canonical_section()
    base = extract(clip, values, seconds=1.0)
    owned = owned_keys()
    assert owned <= build_schema().keys and owned == {c.key for c in spec().controls}
    for key in sorted(owned):
        edited = {**values, key: _flipped(key, values[key])}
        assert engine_key(edited) == engine_key(values), key
        data = extract(clip, edited, seconds=1.0)
        assert _answers(data) == _answers(base), key
        assert data["arrays"] == base["arrays"], key


def test_engine_owned_edits_change_the_engine_answers_negative_control(qt_app):
    """The other direction: an engine-owned (audio analysis) edit changes the answers and the key, which is what
    sends it to the worker; the two sets partition the mode's stored keys."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    edits = {MODE + "_dynamic_floor": not values[MODE + "_dynamic_floor"],
             MODE + "_bar_count": int(values[MODE + "_bar_count"]) + 8}
    for key, value in edits.items():
        assert key in engine_values(values)
        edited = {**values, key: value}
        assert engine_key(edited) != engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) != baseline, key
    prefixes = ("osc_", MODE + "_")
    every = {k for k in values if k.startswith(prefixes)}
    assert set(engine_values(values)) | (owned_keys() & every) == every               # a partition
    assert not set(engine_values(values)) & owned_keys()
    assert technical_keys() <= set(engine_values(values))


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


@pytest.mark.parametrize("variant", ["normal", "phase"])
@pytest.mark.parametrize("source", ["synthetic", "shipped_clip"])
def test_studio_frames_equal_the_production_replay_tick_for_tick(qt_app, source, variant):
    """The Studio's in-process step publishes the production replay's logical frame (every trace's points, the
    afterglow alphas, flare, drive, tone, animation time and every renderer parameter) at every tick, and the
    fixture drives the music paths: afterglow traces, onsets into the flare, loudness into the drive."""
    values = variant_section(variant)
    if source == "synthetic":
        evaluator = OscilloscopeStudioEvaluator(loader=InlineLoader(seconds=None))
        evaluator.select("mid")
        data = recorded(source_of(evaluator.fixture), values, None)
    else:
        clip = shipped_clip()
        data = recorded(clip.description, values)
        evaluator = _clip_evaluator(clip, values=values)
    assert data["arrays"]["dtypes"]                                  # the capture history, recorded as bytes
    assert _assert_parity(evaluator, data, values) >= 200
    flares = []
    for step in data["steps"][::9]:
        frame = evaluator.evaluate(max(0.0, step["now_ts"] - data["origin"]), values)
        flares.append(frame.mode_state.flare)
    frame = evaluator.evaluate(evaluator.fixture.duration * 0.6, values)
    assert frame.mode_id == MODE and dict(frame.mode_state.parameters)[PREFIX + "display"] == values[PREFIX + "display"]
    assert len(frame.mode_state.trace_alphas) > 1 and frame.mode_state.drive > 0.0
    assert max(flares) > 0.0
    evaluator.release()


def test_the_served_history_keeps_the_engines_identity_across_ticks_and_rewinds(qt_app):
    """The runtime tells a new capture history from a held one by identity. The record keeps the engine's pattern:
    a new number exactly where the source's capture serial changes (a held serial is the same number), and the
    Studio's step holds the very object the view serves for that number, also after a rewind to a checkpoint
    (``StepState`` shares the recorded arrays instead of copying them)."""
    clip = shipped_clip()
    values = canonical_section()
    data = recorded(clip.description, values)
    features, _origin = engine_answers.load_source(clip.description)
    serials = [f.capture_history.capture_serial for f in features[:len(data["steps"])]]
    numbers = [s["answers"]["get_waveform_history"]["array"] for s in data["steps"]]
    assert any(a == b for a, b in zip(serials, serials[1:]))           # the clip holds some serials (the case)
    for k in range(1, len(numbers)):
        assert (numbers[k] == numbers[k - 1]) == (serials[k] == serials[k - 1]), k
    evaluator = _clip_evaluator(clip, data=data)
    evaluator.evaluate(data["duration"] * 0.8, values)
    inputs = evaluator._inputs
    runtime = evaluator._controller.peek_logical_mode_state(MODE)
    assert any(runtime._source_key is array for array in inputs.arrays)
    evaluator.evaluate(data["duration"] * 0.5, {**values, PREFIX + "gain": spec().control(PREFIX + "gain").high})
    evaluator.evaluate(data["duration"] * 0.6, values)                     # rewound to a checkpoint of these values
    runtime = evaluator._controller.peek_logical_mode_state(MODE)
    assert evaluator.rewinds >= 2 and any(runtime._source_key is array for array in inputs.arrays)
    evaluator.release()


def test_parity_check_detects_a_perturbed_engine_answer_negative_control(qt_app):
    from ui.studio.replay_engine import encode_answer
    clip = shipped_clip()
    values = canonical_section()
    original = recorded(clip.description, values)
    data = {**original, "steps": json.loads(json.dumps(original["steps"]))}
    middle = len(data["steps"]) // 2
    for step in data["steps"][middle:]:           # a loud, present stretch it never had (whichever tick the beam reads it on)
        step["answers"]["get_musical_level"] = encode_answer((17.0, 2.0))
    evaluator = _clip_evaluator(clip, data=data)
    step = data["steps"][-1]
    assert frame_digest(evaluator.evaluate(step["now_ts"] - data["origin"], values)) != step["frame_sha256"]
    evaluator.release()


def test_a_mode_owned_edit_replays_exactly_without_reanalysis(qt_app):
    """The Phase figure, the longest afterglow and the reactions at full: all at once, no worker."""
    clip = shipped_clip()
    values = canonical_section()
    loader = InlineLoader()
    evaluator = _clip_evaluator(clip, loader)
    at = recorded(clip.description, values)["duration"] * 0.7
    before = evaluator.evaluate(at, values)
    calls = len(loader.calls)
    edited = variant_section("phase")
    edited[PREFIX + "beam_width"] = spec().control(PREFIX + "beam_width").high
    after = evaluator.evaluate(at, edited)
    assert len(loader.calls) == calls                                 # no worker for mode-owned values
    assert frame_digest(after) == _at(recorded(clip.description, edited), at)["frame_sha256"] != frame_digest(before)
    assert evaluator.unrecorded_reads == 0
    evaluator.release()


def test_mode_owned_edits_rewind_under_the_frame_budget_and_equal_production(qt_app):
    """The shared evaluator's exact replay without a stall, on this mode's state (the afterglow ring, the trigger
    template, the flare and drive): a mode-owned edit under the frame budget converges over several evaluations to
    the production frame, rewinding the step state (the recorded arrays shared, never copied) instead of configuring
    a new controller."""
    clip = shipped_clip()
    values = variant_section("phase")
    evaluator = _clip_evaluator(clip, values=values)
    at = recorded(clip.description, values)["duration"] * 0.9
    evaluator.evaluate(at, values)
    replays = evaluator.replays
    evaluator.set_frame_budget(0.0)
    edited = {**values, PREFIX + "span": spec().control(PREFIX + "span").low,
              PREFIX + "afterglow": spec().control(PREFIX + "afterglow").low + 0.2,
              PREFIX + "gain": spec().control(PREFIX + "gain").high}
    for target in (edited, values):                    # an edit, then undo back to checkpointed values
        frame = evaluator.evaluate(at, target)
        for _ in range(400):
            if not evaluator.converging:
                break
            frame = evaluator.evaluate(at, target)
        assert not evaluator.converging
        assert frame_digest(frame) == _at(recorded(clip.description, target), at)["frame_sha256"]
    assert evaluator.replays == replays and evaluator.rewinds >= 2
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
    edited = {**values, MODE + "_bar_count": int(values[MODE + "_bar_count"]) + 8}
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
    evaluator = OscilloscopeStudioEvaluator(loader=loader)
    evaluator.select("peak")
    frame = evaluator.evaluate(2.0, canonical_section())
    assert frame.playing is False and frame.mode_id == MODE and evaluator.analysing
    assert loader.calls == [("peak", engine_key(canonical_section()))]
    evaluator.release()
    assert not evaluator.analysing and not loader.waiting                 # release cancels the analysis


def test_the_worker_runs_out_of_process_and_ships_the_arrays_in_a_binary_sidecar(qt_app):
    """The evaluator's default loader: ``ui.studio.oscilloscope_recorded_inputs`` in its own process
    (``ClipLoadJob``), event driven; the history arrays travel as raw bytes beside the JSON and its answers replay
    to the in-process production replay."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop
    values = canonical_section()
    evaluator = OscilloscopeStudioEvaluator()
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
    inputs = engine_answers.analysed(MODE, (source_of(evaluator.fixture), engine_key(values)))
    assert len(inputs.arrays) == len(data["arrays"]["dtypes"])
    assert _assert_parity(evaluator, data, values) >= 200
    evaluator.release()


def test_the_worker_writes_the_arrays_beside_the_json(qt_app, tmp_path):
    """The worker's own output: the answers as JSON naming each array's number, the bytes in a sidecar file."""
    from ui.studio.oscilloscope_recorded_inputs import main
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(canonical_section()), encoding="utf-8")
    output = tmp_path / "inputs.json"
    assert main([shipped_clip().description, str(settings), str(output), "0.5"]) == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    sidecar = Path(data["arrays"]["file"])
    assert sidecar.parent == tmp_path and sidecar.is_file() and "blob" not in data["arrays"]
    assert "array" in json.dumps(data["steps"][-1]["answers"]["get_waveform_history"])
    inputs = to_inputs(data, replace(shipped_clip(), duration=float(data["duration"])))
    assert sum(a.nbytes for a in inputs.arrays) == sidecar.stat().st_size


# ------------------------------------------------------------------------------------ instruments + clips
def test_instruments_read_the_trace_level_and_the_afterglow_decay(qt_app):
    """Level follows the live trace's swing, Afterglow / Ghosts the afterglow ring (none with Afterglow at zero),
    Flare / Drive / Tone the beam; the transport overview follows the recording's loudness."""
    clip = shipped_clip()
    values = canonical_section()
    evaluator = _clip_evaluator(clip)
    at = evaluator.fixture.duration * 0.7
    evaluator.evaluate(at, values)
    signals = evaluator.measurements()["signals"]
    assert {"Level", "Afterglow", "Ghosts", "Flare", "Drive", "Tone"} <= set(signals)
    assert 0.0 < signals["Level"] <= 1.0 and 0.0 < signals["Afterglow"] <= 1.0 and 0.0 < signals["Ghosts"] <= 1.0
    evaluator.evaluate(at, {**values, PREFIX + "afterglow": 0.0})
    dark = evaluator.measurements()["signals"]
    assert dark["Afterglow"] == dark["Ghosts"] == 0.0 and dark["Level"] > 0.0
    timeline = evaluator.timeline()
    assert max(timeline) == 1.0 and min(timeline) < 1.0
    schema = build_schema()
    traced = {name for _group, names in schema.group_traces for name in names}
    assert traced <= set(signals)
    evaluator.release()


def test_shipped_clips_lead_the_recorded_fixtures(qt_app):
    from ui.studio.waveform_recorded_inputs import shipped_clips
    clips = OscilloscopeStudioAdapter().recorded_clips()
    shipped = shipped_clips()
    assert shipped and [c.description for c in clips[:len(shipped)]] == [c.description for c in shipped]


def test_the_studio_adds_nothing_to_the_saver_or_settings_until_opened():
    """Dormancy: asking whether Oscilloscope has a Studio (Settings' preset row) imports no adapter, worker or
    renderer."""
    code = ("import sys; from ui.studio.registry import has_studio; assert has_studio('oscilloscope'); "
            "bad = [m for m in ('ui.studio.oscilloscope_adapter', 'ui.studio.oscilloscope_recorded_inputs', "
            "'ui.studio.engine_answers', 'rendering.quick.visualizer.implementations.oscilloscope') "
            "if m in sys.modules]; assert not bad, bad")
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]


# ------------------------------------------------------------------------------------ Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="OscilloscopeStudio",
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


class InlineAdapter(OscilloscopeStudioAdapter):
    """The real adapter with the worker run in this process and no recorded clips offered."""

    def recorded_clips(self):
        return ()

    def create_evaluator(self):
        return OscilloscopeStudioEvaluator(loader=InlineLoader(seconds=None))


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


def test_the_preset_row_offers_the_oscilloscope_studio(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    from ui.studio.registry import has_studio
    assert has_studio(MODE)
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{spec().prefix}_studio_button")
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
    # A slider, a choice, a colour, a colour's opacity and a technical value, each through Settings' own save.
    afterglow = spec().control(PREFIX + "afterglow")
    bridge.commitValue(PREFIX + "afterglow", 0, afterglow.high)
    assert stored()[PREFIX + "afterglow"] == pytest.approx(afterglow.high)
    display = build_schema().find(PREFIX + "display")
    other = next(v for v in display.choice_values if v != session.values[PREFIX + "display"])
    bridge.commitValue(PREFIX + "display", 0, display.choices[display.choice_values.index(other)])
    assert stored()[PREFIX + "display"] == other
    alpha = next(c.key for c in spec().controls if isinstance(c, Colour) and c.alpha)
    bridge.commitValue(f"{alpha}.3", 0, 120)
    assert stored()[alpha][3] == 120
    bridge.commitValue(MODE + "_input_gain", 0, 0.9)
    assert stored()[MODE + "_input_gain"] == pytest.approx(0.9)
    bridge.undo()
    assert stored()[MODE + "_input_gain"] != pytest.approx(0.9)                  # one undoable edit
    assert session.values[PREFIX + "display"] == other                          # nothing reverted by a later save
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


def test_fill_framing_follows_the_live_card(qt_app):
    adapter = OscilloscopeStudioAdapter()
    card = (900.0, 260.0)
    framings = adapter.framings(card, {"border_width": 2.0})
    assert adapter.default_framing() == framings[0].id == "fill" and framings[0].fill
    assert framings[0].extent == card and framings[1].extent == card and not framings[1].fill
    assert all(f.extent[0] >= card[0] and f.extent[1] >= card[1] for f in framings)


def test_the_production_renderer_draws_the_production_frame_identically(qt_app, dialog_tab, no_gl_checks):
    """The Studio's live viewport draws the beam, and the production frame and the Studio's frame of the same
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
    assert surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3].std() > 2.0          # the beam is drawn

    clip = shipped_clip()
    frames = {}
    for variant in ("normal", "phase"):
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
    for variant in ("normal", "phase"):
        assert images[f"{variant}/live"][..., :3].std() > 2.0
        assert np.array_equal(images[f"{variant}/live"], images[f"{variant}/studio"]), variant
    assert np.abs(images["normal/live"] - images["phase/live"]).max() > 20
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
    assert not np.array_equal(renders[0], 255 - renders[0])          # the comparison sees a real change
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
        manager = SettingsManager(organization="SRPSSFocusedTests", application="OscilloscopeStudioPreset",
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
    """A tmp copy of Oscilloscope's real curated folder, made the preset owner's root (then restored)."""
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
    """The preset row's own Open Studio click, with the Oscilloscope Studio on the hidden offscreen surface."""
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


def test_save_to_preset_writes_only_the_edited_key_into_a_curated_oscilloscope_preset(
        real_dialog, offscreen_launch, preset_copy, popups):
    """Open Studio on a curated Oscilloscope slot (the real SettingsDialog's preset row), edit one scalar that slot's
    file authors, and Save To <that preset>: a confirmation first (Cancel writes nothing), then only that key's line
    changes, the file keeps its shape and the preset owner reloads it; Custom stays selected."""
    from core.settings import visualizer_presets as vp
    from core.settings.visualizer_preset_file import key_order
    from ui.studio.schema import SCALAR
    seen, state = popups
    dialog, tab = real_dialog()
    slider = tab._get_visualizer_preset_slider(MODE)
    launcher = getattr(tab, f"_{spec().prefix}_studio_button")
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
                if p.instrument == SCALAR and not p.integer and len(p.path) == 1 and not p.when
                and p.id in authored and text.count(f'"{p.id}"') == 1)
    shown = bridge.values[prop.id]
    span = prop.maximum - prop.minimum
    target = round(prop.minimum + span * (0.25 if float(shown) > prop.minimum + span / 2 else 0.75), prop.decimals)
    bridge.commitValue(prop.id, 0, target)
    assert slider.preset_index() == slider.custom_index()          # a Studio edit lands in Custom
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
    assert slider.preset_index() == slider.custom_index()
