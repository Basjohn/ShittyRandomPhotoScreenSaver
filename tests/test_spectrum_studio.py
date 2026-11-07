"""Spectrum's Studio adapter (Rainbow Ghost included) on the shared Studio framework.

Structural: no preset counts, preset values or UI wording are pinned (presets are authored, mutable content); inputs
are the code-owned canonical defaults. Truthfulness is proven against Spectrum's production owners: the production
offline replay (``logical_tick`` under the pinned clock, in the out-of-process worker's ``extract``) records what the
engine answered Spectrum's step, and the Studio's in-process production step over those answers publishes the same
``VisualizerLogicalFrame`` byte for byte at every tick, on a synthetic fixture and a shipped clip; the production
renderer draws them identically. The engine-owned / Spectrum-owned split is proven in both directions on the
production replay. Nothing shows a window.
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
from ui.studio import spectrum_adapter
from ui.studio.spectrum_adapter import (
    LANES, NOTCHES, SHAPE_NODES, SpectrumStudioAdapter, SpectrumStudioEvaluator, build_schema, engine_key,
    engine_values, source_of, spectrum_owned_keys,
)
from ui.studio.spectrum_recorded_inputs import extract, frame_digest, to_inputs

MODE = "spectrum"
PREFIX = MODE + "_"
ROOT = Path(__file__).resolve().parents[1]
CLIP_SECONDS = 3.0


def spec():
    return require_mode_settings(MODE)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults, never an authored preset."""
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec().body_controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    return out


def rainbow_ghost_section():
    """Canonical values with the Rainbow Ghost variant on: ghosting and Rainbow Ghost, segmented bars."""
    values = canonical_section()
    values.update({PREFIX + "ghosting_enabled": True, PREFIX + "rainbow_ghost": True,
                   PREFIX + "render_mode": "segment", PREFIX + "ghost_alpha": spec().control(PREFIX + "ghost_alpha").high})
    return values


def decorated_section():
    """Canonical values with every optional decoration on (ghost colour and gradient, fill gradient, gloss, peak
    caps and a pattern), from the registry's own choices."""
    from rendering.gl_programs.spectrum_options import SPECTRUM_GHOST_COLOUR_SOURCES, SPECTRUM_PATTERNS
    values = canonical_section()
    values.update({PREFIX + "ghost_color_source": SPECTRUM_GHOST_COLOUR_SOURCES[-1], PREFIX + "ghost_gradient": True,
                   PREFIX + "fill_gradient": True, PREFIX + "gloss": 0.5, PREFIX + "peak_caps": True,
                   PREFIX + "pattern": SPECTRUM_PATTERNS[-1], PREFIX + "rainbow_ghost": False})
    return values


def technical_keys():
    from core.settings.visualizer_mode_settings import require_mode_settings
    return {control.key for control in require_mode_settings(MODE).technical_controls()}


def family_keys():
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    return set(get_owned_mode_setting_keys(MODE, "shared_bar").values()) | set(
        get_owned_mode_setting_keys(MODE, "rainbow").values())


def shipped_clip():
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips
    clips = studio_clips(recordings_directory())
    if not clips:
        pytest.skip("No shipped Studio clip in this checkout")
    return clips[0]


_EXTRACTS: dict = {}


def recorded(source: str, values, seconds: float | None = CLIP_SECONDS) -> dict:
    """The production replay's record for ``source`` under ``values`` (memoised per engine-owned values)."""
    key = (source, engine_key(values), json.dumps(sorted((k, repr(v)) for k, v in values.items())), seconds)
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
    spectrum_adapter._ANALYSED.clear()
    yield
    spectrum_adapter._ANALYSED.clear()


def _clip_evaluator(clip, loader=None, values=None, data=None):
    """An evaluator on ``clip`` as the controller hands it one: the clip analysed (``add_recorded``), then selected."""
    data = data if data is not None else recorded(clip.description, values or canonical_section())
    evaluator = SpectrumStudioEvaluator(loader=loader or InlineLoader())
    evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
    evaluator.select(clip.id)
    return evaluator


def _loudest_instant(data) -> float:
    """The fixture time a quarter second after the clip's loudest recorded tick: the clip's content decides where a
    falling peak (a ghost) is on screen, so a test of ghosts looks there, not at a fixed fraction of the clip."""
    from ui.studio.replay_engine import decode_answer
    levels = []
    for step in data["steps"]:
        bars = decode_answer(step["answers"].get("get_smoothed_bars", {"list": []})) or [0.0]
        levels.append((sum(bars) / len(bars), step["now_ts"] - data["origin"]))
    return min(float(data["duration"]), max(levels)[1] + 0.25)


# ------------------------------------------------------------------------------------- schema
def _vector_elements() -> set[tuple]:
    """Every element of a vector value Settings edits: colour alphas, every shape-node slot (both axes), every
    frequency boundary and lane strength of both layouts."""
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    shared = get_owned_mode_setting_keys(MODE, "shared_bar")
    canonical = require_canonical_default("widgets.spotify_visualizer")
    out = {(c.key, 3) for c in spec().body_controls if isinstance(c, Colour) and c.alpha}
    out |= {(shared["bar_fill_color"], 3), (shared["bar_border_color"], 3)}
    out |= {(SHAPE_NODES, i, axis) for i in range(_MAX_NODES) for axis in (0, 1)}
    for mirrored in (True, False):
        out |= {(NOTCHES[mirrored], i, 0) for i in range(len(canonical[NOTCHES[mirrored]]))}
        out |= {(LANES[mirrored], label) for label in canonical[LANES[mirrored]]}
    return out


def _uncovered(properties) -> set:
    """Registry keys (every spec control, every Custom row's keys, every technical control, the mode's shared bar
    and rainbow families) with no Studio property, plus vector elements no property edits."""
    paths = {tuple(p.path) for p in properties}
    roots = {p.path[0] for p in properties}
    custom_keys = {key for e in spec().entries if isinstance(e, Custom) for key in e.keys}
    keys = {c.key for c in spec().body_controls} | custom_keys | technical_keys() | family_keys()
    return (keys - roots) | {element for element in _vector_elements() if element not in paths}


def test_every_spectrum_and_rainbow_ghost_control_is_editable_in_the_studio():
    assert _uncovered(build_schema().properties) == set()
    assert PREFIX + "rainbow_ghost" in build_schema().keys


def test_coverage_check_detects_a_missing_control_negative_control():
    properties = build_schema().properties
    for dropped in (PREFIX + "rainbow_ghost", PREFIX + "render_mode", SHAPE_NODES, PREFIX + "visual_smoothing",
                    PREFIX + "bar_border_opacity", PREFIX + "rainbow_speed", PREFIX + "sensitivity"):
        assert dropped in _uncovered([p for p in properties if p.path[0] != dropped]), dropped
    lanes = LANES[False]
    label = next(iter(require_canonical_default("widgets.spotify_visualizer")[lanes]))
    assert (lanes, label) in _uncovered([p for p in properties if tuple(p.path) != (lanes, label)])


def test_instruments_bounds_choices_and_conditions_come_from_the_registry():
    from ui.studio.adapter import control_condition
    schema = build_schema()
    for control in spec().body_controls:
        prop = schema.find(control.key)
        if isinstance(control, Slider):
            assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
        elif isinstance(control, Choice):
            assert tuple(prop.choice_values or prop.choices) == tuple(control.choices), control.key
        elif isinstance(control, Toggle):
            assert prop.instrument == "switch"
        assert prop.when == control_condition(control), control.key


def test_shape_rules_follow_the_shape_editor():
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    schema = build_schema()
    nodes = [list(n) for n in canonical_section()[SHAPE_NODES]]
    moved = [list(n) for n in nodes]
    moved[1][0] = 1.0                                         # past its right neighbour: stops at it
    admitted = schema.admit(SHAPE_NODES, moved, nodes)
    xs = [x for x, _y in admitted]
    assert admitted[1] == [pytest.approx(nodes[2][0]), nodes[1][1]] and xs == sorted(xs)
    too_many = nodes + [[0.5, 0.5]] * _MAX_NODES
    assert schema.admit(SHAPE_NODES, too_many, nodes) == nodes
    for mirrored in (True, False):
        key = NOTCHES[mirrored]
        notches = canonical_section()[key]
        bent = [[x, "Renamed"] for x, _label in notches]
        bent[0][0] = 1.0
        out = schema.admit(key, bent, notches)
        assert [label for _x, label in out] == [label for _x, label in notches]        # labels never change
        assert out[0][0] == pytest.approx(notches[1][0])
        lanes = canonical_section()[LANES[mirrored]]
        assert set(schema.admit(LANES[mirrored], {**lanes, "Extra": 0.3}, lanes)) == set(lanes)
    with pytest.raises(KeyError):
        schema.admit("not_a_spectrum_key", 1, 0)


# ------------------------------------------------------------------- engine-owned / Spectrum-owned split
def _flipped(key: str, value):
    """Another admissible value of a Spectrum-owned key."""
    schema = build_schema()
    if isinstance(value, bool):
        return not value
    if isinstance(value, list):
        return [255 - int(v) for v in value[:3]] + [int(value[3])]
    if isinstance(value, str):
        prop = schema.find(key)
        return next(v for v in prop.choice_values if v != value)
    prop = schema.find(key)
    return prop.maximum if abs(float(value) - prop.maximum) > 1e-6 else prop.minimum


def _answers(data):
    return [(s["now_ts"], s["answers"]) for s in data["steps"]]


def test_spectrum_owned_edits_leave_the_engine_answers_unchanged(qt_app):
    """Every key the Studio treats as Spectrum-owned (instant, no re-analysis) leaves every engine answer of the
    production replay unchanged, so no Spectrum-owned edit can need the worker."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    owned = spectrum_owned_keys()
    assert owned and owned <= build_schema().keys
    for key in sorted(owned):
        edited = dict(values)
        edited[key] = _flipped(key, values[key])
        assert engine_key(edited) == engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) == baseline, key


def test_engine_owned_edits_change_the_engine_answers_negative_control(qt_app):
    """The other direction: an engine-owned edit (shape, lanes, Audio sliders, analysis) changes the answers and
    the key, which is what sends it to the worker."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    mirrored = bool(values[PREFIX + "mirrored"])
    lanes = dict(values[LANES[mirrored]])
    first = next(iter(lanes))
    nodes = [list(n) for n in values[SHAPE_NODES]]
    nodes[1][1] = 0.0 if nodes[1][1] > 0.5 else 1.0
    edits = {SHAPE_NODES: nodes, LANES[mirrored]: {**lanes, first: 0.0 if lanes[first] > 0.5 else 1.0},
             PREFIX + "wave_amplitude": 1.0 if values[PREFIX + "wave_amplitude"] < 0.9 else 0.1,
             PREFIX + "mirrored": not mirrored, PREFIX + "bar_count": int(values[PREFIX + "bar_count"]) + 8}
    for key, value in edits.items():
        assert key in engine_values(values)
        edited = {**values, key: value}
        assert engine_key(edited) != engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) != baseline, key
    every = set(k for k in values if k.startswith(PREFIX))
    assert set(engine_values(values)) | (spectrum_owned_keys() & every) == every       # a partition


def test_decoration_controls_are_spectrum_owned_instant_edits():
    """The decoration is read by Spectrum's own capture and renderer: editing it never re-runs the analysis."""
    from widgets.spotify_visualizer.spectrum_decor import DECOR_KEYS
    assert set(DECOR_KEYS) <= spectrum_owned_keys()
    assert engine_key(decorated_section()) == engine_key(canonical_section())


# --------------------------------------------------------------------------------- production parity
def _assert_parity(evaluator, data, values) -> int:
    compared = 0
    for step in data["steps"]:
        if step["frame_sha256"] is None or step["now_ts"] < data["origin"]:
            continue
        frame = evaluator.evaluate(step["now_ts"] - data["origin"], values)
        assert frame_digest(frame) == step["frame_sha256"], step["now_ts"]
        compared += 1
    assert evaluator.unrecorded_reads == 0           # every engine read was served from the record
    return compared


@pytest.mark.parametrize("variant", ["normal", "rainbow_ghost", "decorated"])
@pytest.mark.parametrize("source", ["synthetic", "shipped_clip"])
def test_studio_frames_equal_the_production_replay_tick_for_tick(qt_app, source, variant):
    """The Studio's in-process Spectrum step publishes the production replay's logical frame (common bars and
    style, peaks, ghosts, animation time, every renderer parameter, identities and flags) at every tick."""
    values = {"normal": canonical_section, "rainbow_ghost": rainbow_ghost_section,
              "decorated": decorated_section}[variant]()
    if source == "synthetic":
        evaluator = SpectrumStudioEvaluator(loader=InlineLoader(seconds=None))
        evaluator.select("mid")
        data = recorded(source_of(evaluator.fixture), values, None)
    else:
        clip = shipped_clip()
        data = recorded(clip.description, values)
        evaluator = _clip_evaluator(clip, values=values)
    assert _assert_parity(evaluator, data, values) >= 200
    if variant == "rainbow_ghost":
        frame = evaluator.evaluate(evaluator.fixture.duration * 0.6, values)
        assert frame.mode_state.ghost_bars and dict(frame.mode_state.parameters)["spectrum_rainbow_ghost"] is True
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


def test_a_spectrum_owned_edit_replays_exactly_without_reanalysis(qt_app):
    clip = shipped_clip()
    values = canonical_section()
    loader = InlineLoader()
    evaluator = _clip_evaluator(clip, loader)
    at = recorded(clip.description, values)["duration"] * 0.7
    before = evaluator.evaluate(at, values)
    calls = len(loader.calls)
    edited = rainbow_ghost_section()
    edited[PREFIX + "ghost_decay"] = spec().control(PREFIX + "ghost_decay").low
    edited[PREFIX + "visual_smoothing"] = 0.9
    edited[PREFIX + "bar_fill_color"] = [200, 40, 90, 255]
    after = evaluator.evaluate(at, edited)
    assert len(loader.calls) == calls                                 # no worker for Spectrum-owned values
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
    nodes = [list(n) for n in values[SHAPE_NODES]]
    nodes[1][1] = 0.0 if nodes[1][1] > 0.5 else 1.0
    edited[SHAPE_NODES] = nodes
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


def test_before_the_first_analysis_lands_the_studio_shows_spectrums_resting_scene(qt_app):
    loader = InlineLoader(deferred=True, seconds=None)
    evaluator = SpectrumStudioEvaluator(loader=loader)
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
    evaluator = SpectrumStudioEvaluator()
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


def test_the_app_entry_point_runs_the_spectrum_worker_as_a_frozen_build_does(tmp_path):
    """``main.py --studio-clip-worker ui.studio.spectrum_recorded_inputs`` (the frozen path) records the same
    answers as the in-process replay."""
    from ui.studio.waveform_recorded_inputs import run_frozen_worker, WORKER_FLAG
    clip = shipped_clip()
    values = canonical_section()
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(values), encoding="utf-8")
    output = tmp_path / "inputs.json"
    done = subprocess.run([sys.executable, str(ROOT / "main.py"), WORKER_FLAG, "ui.studio.spectrum_recorded_inputs",
                           clip.description, str(settings), str(output), "1.0", "/s"], cwd=ROOT,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    data = json.loads(output.read_text(encoding="utf-8"))
    assert _answers(data) == _answers(extract(clip.description, values, seconds=1.0))
    assert [s["frame_sha256"] for s in data["steps"]] == [s["frame_sha256"] for s in
                                                          extract(clip.description, values, seconds=1.0)["steps"]]
    assert run_frozen_worker(["exe", WORKER_FLAG, "ui.studio.spectrum_recorded_inputs"]) is None   # too few args


# ------------------------------------------------------------------------------------ Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="SpectrumStudio",
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


class InlineAdapter(SpectrumStudioAdapter):
    """The real adapter with the worker run in this process and no recorded clips offered."""

    def recorded_clips(self):
        return ()

    def create_evaluator(self):
        return SpectrumStudioEvaluator(loader=InlineLoader(seconds=None))


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


def test_custom_body_offers_the_spectrum_studio(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    assert getattr(tab, f"_{MODE}_settings_container").isAncestorOf(button)
    calls = []
    monkeypatch.setattr(settings_link, "open_mode_studio", lambda t, m: calls.append((t, m)))
    button.click()
    assert calls == [(tab, MODE)]


def test_edits_save_through_spectrums_settings_owners_and_every_exit_restores_settings(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert controller.state == "presented" and controller.presence.concealed
    bridge = controller.bridge
    session = controller.session
    stored = lambda: settings_manager.get("widgets")["spotify_visualizer"]      # noqa: E731
    # Spec controls (a Choice, Rainbow Ghost, a slider), the Custom rows (smoothing, shape node, boundary, lane), the
    # shared families (fill alpha, border opacity, rainbow) and a technical value, each through Settings' save.
    render = session.values[PREFIX + "render_mode"]
    other = next(v for v in build_schema().find(PREFIX + "render_mode").choice_values if v != render)
    label = build_schema().find(PREFIX + "render_mode").choices[
        build_schema().find(PREFIX + "render_mode").choice_values.index(other)]
    bridge.commitValue(PREFIX + "render_mode", 0, label)
    assert stored()[PREFIX + "render_mode"] == other
    ghost = not bool(session.values[PREFIX + "rainbow_ghost"])
    bridge.commitValue(PREFIX + "rainbow_ghost", 0, ghost)
    assert stored()[PREFIX + "rainbow_ghost"] is ghost
    bridge.commitValue(PREFIX + "ghost_decay", 0, 0.8)
    assert stored()[PREFIX + "ghost_decay"] == pytest.approx(0.8)
    bridge.commitValue(PREFIX + "visual_smoothing", 0, 0.73)
    assert stored()[PREFIX + "visual_smoothing"] == pytest.approx(0.73)
    height = session.values[SHAPE_NODES][0][1]
    bridge.commitValue(f"{SHAPE_NODES}.0.1", 0, round(1.0 - height, 3))
    assert stored()[SHAPE_NODES][0][1] == pytest.approx(round(1.0 - height, 3))
    mirrored = bool(session.values[PREFIX + "mirrored"])
    notches, lanes = NOTCHES[mirrored], LANES[mirrored]
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
    enabled = not bool(session.values[PREFIX + "rainbow_enabled"])
    bridge.commitValue(PREFIX + "rainbow_enabled", 0, enabled)
    bridge.commitValue(PREFIX + "rainbow_speed", 0, 0.37)
    assert stored()[PREFIX + "rainbow_enabled"] is enabled
    assert stored()[PREFIX + "rainbow_speed"] == pytest.approx(0.37)
    bridge.commitValue(PREFIX + "transient_clamp", 0, 0.9)
    assert stored()[PREFIX + "transient_clamp"] == pytest.approx(0.9)
    assert session.values[PREFIX + "render_mode"] == other                # nothing reverted by a later save
    bridge.requestClose()
    assert _settings_restored(controller, dialog)
    from ui.tabs.media.visualizer_mode_binding import FAMILY_CACHE_ATTR
    assert getattr(tab, FAMILY_CACHE_ATTR)[PREFIX + "rainbow_enabled"] is enabled   # Settings holds the Studio's edits
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


def test_absent_shape_node_slots_are_not_shown(qt_app, dialog_tab, no_gl_checks):
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    count = len(controller.session.values[SHAPE_NODES])
    hidden = controller.bridge.conditionHidden
    assert all(not hidden.get(f"{SHAPE_NODES}.{i}.1") for i in range(count))
    assert all(hidden.get(f"{SHAPE_NODES}.{i}.1") for i in range(count, _MAX_NODES))
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
    for _ in range(200):
        surface.pump()
        QCoreApplication.processEvents()
        if len(images) == len(frames):
            break
    surface.viewport.snapshotReady.disconnect(ready)
    assert set(images) == set(frames)
    return images


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
    for variant, values in (("normal", canonical_section()), ("rainbow_ghost", rainbow_ghost_section())):
        captured: list = []
        data = extract(clip.description, values, seconds=CLIP_SECONDS, frames_out=captured)
        evaluator = _clip_evaluator(clip, data=data)
        now, live = captured[int(len(captured) * 0.8)]
        studio = evaluator.evaluate(now - data["origin"], values)
        assert frame_digest(studio) == frame_digest(live)
        frames[f"{variant}/live"], frames[f"{variant}/studio"] = live, studio
        evaluator.release()
    images = _snapshots(surface, frames, controller.presented_extent())
    for variant in ("normal", "rainbow_ghost"):
        assert images[f"{variant}/live"][..., :3].std() > 2.0
        assert np.array_equal(images[f"{variant}/live"], images[f"{variant}/studio"]), variant
    # Rainbow Ghost colours the falling peaks: the variant renders differently (negative control on the pair).
    assert np.abs(images["normal/live"] - images["rainbow_ghost/live"]).max() > 20
    controller.close()


def test_rainbow_ghost_colours_only_the_peak_ghosts(qt_app, dialog_tab, no_gl_checks):
    """Same instant with Rainbow Ghost on and off: the pixels it changes are a subset of the pixels the ghosts
    themselves draw (ghosting on vs off), so bar fill and borders are untouched; with ghosting off it changes
    nothing."""
    import numpy as np
    _dialog, tab = dialog_tab()
    controller, surface = _open_live(tab, InlineAdapter())
    clip = shipped_clip()
    frames = {}
    for ghosting in (True, False):
        for rainbow in (True, False):
            values = rainbow_ghost_section()
            values[PREFIX + "ghosting_enabled"] = ghosting
            values[PREFIX + "rainbow_ghost"] = rainbow
            evaluator = _clip_evaluator(clip, values=values)
            frames[(ghosting, rainbow)] = evaluator.evaluate(_loudest_instant(recorded(clip.description, values)), values)
            evaluator.release()
    images = _snapshots(surface, {repr(k): f for k, f in frames.items()}, controller.presented_extent())
    on, off = images[repr((True, True))], images[repr((True, False))]
    assert np.abs(on - off).max() > 20                                       # ghosts recoloured
    recoloured = np.abs(on - off).max(axis=2) > 0
    ghost_pixels = np.abs(on - images[repr((False, True))]).max(axis=2) > 0
    assert recoloured.any() and not (recoloured & ~ghost_pixels).any()
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


# ------------------------------------------------------------------------------------ analysis failures
class FlakyLoader(InlineLoader):
    """The inline worker, failing (as a crashed worker reports) while ``fail`` is set."""

    fail = False

    def __call__(self, fixture, values, finished):
        if self.fail:
            self.calls.append((fixture.id, engine_key(values)))
            finished(None, "worker exited with code 1")
            return None
        return super().__call__(fixture, values, finished)


class FlakyAdapter(LightAdapter):
    def __init__(self):
        super().__init__()
        self.loader = FlakyLoader(seconds=None)

    def create_evaluator(self):
        return SpectrumStudioEvaluator(loader=self.loader)


def test_a_failed_out_of_process_worker_is_reported_by_the_evaluator(qt_app):
    """A forced failure of the real worker process (a clip that does not exist): the job reports it, the evaluator
    keeps it as the current values' failure, and a retry clears it so the next evaluation runs the worker again."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop
    from ui.studio.adapter import RECORDED, StudioFixture
    values = canonical_section()
    evaluator = SpectrumStudioEvaluator()
    missing = StudioFixture("clip:missing", "Missing", RECORDED, 3.0, str(ROOT / "no_such_clip.srclip"))
    evaluator._clips[missing.id] = missing
    evaluator.select(missing.id)
    landed = []
    evaluator.set_invalidate(lambda: landed.append(True))
    frame = evaluator.evaluate(0.0, values)
    assert evaluator.analysing and evaluator.analysis_failure == ""
    timer = QElapsedTimer()
    timer.start()
    while not landed and timer.elapsed() < 120_000:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    assert landed and not evaluator.analysing and evaluator.analysis_failure
    assert frame_digest(evaluator.evaluate(0.0, values)) == frame_digest(frame)       # nothing replaced
    assert not evaluator.analysing                                                     # no retry loop
    evaluator.retry_analysis()
    assert evaluator.analysis_failure == ""
    evaluator.evaluate(0.0, values)
    assert evaluator.analysing                                                         # retried
    evaluator.release()                                # cancels the retried job: its whole worker tree ends
    from tests.studio_worker_probe import wait_gone
    from ui.studio.waveform_recorded_inputs import worker_tag
    assert wait_gone(worker_tag(), 15.0) == []


def _pump_until(surface, condition, frames=400):
    for _ in range(frames):
        surface.pump()
        if condition():
            return True
    return condition()


def test_a_failed_reanalysis_shows_a_notice_keeps_the_preview_and_retry_lands(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    adapter = FlakyAdapter()
    controller = open_mode_studio(tab, MODE, adapter=adapter, surface_factory=_surfaces(surfaces))
    surface = surfaces[0]
    assert _pump_until(surface, lambda: controller.last_frame is not None and not controller.evaluator.analysing)
    surface.pump(2)
    before = frame_digest(controller.last_frame)
    bridge = controller.bridge
    adapter.loader.fail = True
    nodes = controller.session.values[SHAPE_NODES]
    bridge.commitValue(f"{SHAPE_NODES}.0.1", 0, 0.0 if nodes[0][1] > 0.5 else 1.0)    # engine-owned: re-analyse
    assert _pump_until(surface, lambda: bridge.messageAction == "Retry")
    assert "worker exited" in bridge.message
    from PySide6.QtCore import QObject
    button = surface.host.root.findChild(QObject, "noticeAction")
    assert button is not None and button.property("visible") and button.property("text") == "Retry"
    assert frame_digest(controller.last_frame) == before            # the previous answers stay on screen
    calls = len(adapter.loader.calls)
    surface.pump(5)
    assert len(adapter.loader.calls) == calls and bridge.messageAction == "Retry"     # no retry loop, one notice
    adapter.loader.fail = False
    bridge.runMessageAction()
    assert _pump_until(surface, lambda: frame_digest(controller.last_frame) != before)
    assert controller.evaluator.analysis_failure == "" and bridge.message == ""
    controller.close()


def test_a_failure_without_the_evaluator_report_stays_silent_negative_control(qt_app, dialog_tab, no_gl_checks,
                                                                              monkeypatch):
    """Without the evaluator's ``analysis_failure`` the shell has nothing to show (the original defect: logged only)."""
    from ui.studio.settings_link import open_mode_studio
    monkeypatch.setattr(SpectrumStudioEvaluator, "analysis_failure", property(lambda self: ""))
    _dialog, tab = dialog_tab()
    surfaces = []
    adapter = FlakyAdapter()
    controller = open_mode_studio(tab, MODE, adapter=adapter, surface_factory=_surfaces(surfaces))
    surface = surfaces[0]
    assert _pump_until(surface, lambda: controller.last_frame is not None and not controller.evaluator.analysing)
    adapter.loader.fail = True
    nodes = controller.session.values[SHAPE_NODES]
    bridge = controller.bridge
    bridge.commitValue(f"{SHAPE_NODES}.0.1", 0, 0.0 if nodes[0][1] > 0.5 else 1.0)
    surface.pump(10)
    assert controller.evaluator.errors and bridge.messageAction == ""
    controller.close()


# ------------------------------------------------------------------------------------ Save Preset As
@pytest.fixture
def preset_catalog(tmp_path, monkeypatch):
    """A temporary curated catalog holding copies of the shipped Spectrum presets (none is ever written to)."""
    import shutil
    from core.settings import visualizer_presets as vp
    root = tmp_path / "catalog"
    shutil.copytree(vp.get_visualizer_presets_dir(MODE), root / MODE)
    for name in ("_PRESETS", "_PRESET_SOURCE_PATHS", "_PRESET_SOURCE_SLOTS", "_LOADED_SOURCE_PATHS"):
        monkeypatch.setattr(vp, name, dict(getattr(vp, name)))
    monkeypatch.setattr(vp, "_presets_root", lambda: root)
    monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: tmp_path / "overrides")
    vp.reload_presets(MODE)
    yield root / MODE
    vp.reload_presets(MODE)


def test_save_preset_as_from_the_studio_writes_a_valid_curated_preset(qt_app, dialog_tab, settings_manager,
                                                                      no_gl_checks, preset_catalog, monkeypatch):
    """Studio edits (a structural shape edit, an awkward hundredth, a choice) then the shell's Save Preset As: the
    Settings preset owner writes the file, the canonical loader lists it with the Studio's values, the repair
    tool's sanitizer accepts it unchanged for those values, and it authors every Spectrum artwork key."""
    from PySide6.QtWidgets import QDialog
    from core.settings import visualizer_presets as vp
    from tools import visualizer_preset_repair as repair
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.spectrum_adapter import ADD_NODE
    from ui.tabs.media import preset_slider as module
    path = preset_catalog / "studio_authored.json"
    monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    monkeypatch.setattr(module.StyledPopup, "exec", lambda *a: QDialog.DialogCode.Accepted)
    before = {p.name for p in vp.get_presets(MODE)}
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    bridge, session = controller.bridge, controller.session
    bridge.setWorkspace("shape")
    bridge.runAction(ADD_NODE)
    bridge.commitValue(PREFIX + "ghost_decay", 0, 0.29)
    schema = build_schema()
    render = schema.find(PREFIX + "render_mode")
    other = next(v for v in render.choice_values if v != session.values[PREFIX + "render_mode"])
    bridge.commitValue(PREFIX + "render_mode", 0, render.choices[render.choice_values.index(other)])
    authored = {key: session.values[key] for key in (SHAPE_NODES, PREFIX + "ghost_decay", PREFIX + "render_mode")}
    bridge.savePresetAs()
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    saved = next(p for p in vp.get_presets(MODE) if p.name not in before)
    for key, value in authored.items():
        assert saved.settings[key] == value, key
    assert set(vp.preset_artwork_keys(MODE)) <= set(saved.settings)
    cleaned, _changes = repair._sanitize_settings(MODE, payload)
    for key, value in authored.items():
        assert cleaned[key] == value, key
    assert controller.state == "presented"                     # the Studio session carries on
    bridge.commitValue(PREFIX + "ghost_decay", 0, 0.57)
    assert settings_manager.get("widgets")["spotify_visualizer"][PREFIX + "ghost_decay"] == pytest.approx(0.57)
    controller.close()
