"""DevCurve's Studio adapter on the shared Studio framework.

Structural: no preset counts, preset values or UI wording are pinned (presets are authored, mutable content); inputs
are the code-owned canonical defaults. Truthfulness is proven against DevCurve's production owners: the production
offline replay (``logical_tick`` under the pinned clock, in the out-of-process worker's ``extract``) records what the
engine answered the tick, and the Studio's in-process production tick (``consume_engine_bars``, the DevCurve hook,
the capture) over those answers publishes the same ``VisualizerLogicalFrame`` byte for byte at every tick, on a
synthetic fixture and a shipped clip; the production renderer draws them identically. The engine-owned / mode-owned
split is proven in both directions on the production replay; the layer rows store what Settings' own layer binding
stores; the reactivity traces follow kicks. Settings is the real ``VisualizersTab`` / ``SettingsDialog``; Save To
<Preset> writes only a tmp copy of a curated preset folder. Nothing shows a window.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers
from ui.studio.devcurve_adapter import (
    ACTIVE_LAYER, ADD_NODE, REMOVE_NODE, DevCurveStudioAdapter, DevCurveStudioEvaluator, build_schema, engine_key,
    engine_values, follow, layer_key, layer_label, layers, node_limits, owned_keys,
)
from ui.studio.devcurve_recorded_inputs import extract, frame_digest, to_inputs
from ui.studio.engine_answers import source_of
from ui.studio.schema import SCALAR

MODE = "devcurve"
PREFIX = MODE + "_"
ROOT = Path(__file__).resolve().parents[1]
CLIP_SECONDS = 3.0
LAYER_SUFFIXES = ("enabled", "power", "offset", "order", "alpha", "color", "outline_color", "outline_width")


def spec():
    return require_mode_settings(MODE)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults (never an authored preset)."""
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec().controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    return out


def variant_section(variant: str) -> dict:
    """``normal``: canonical. ``plain``: one layer off, the stack reordered, the foreground shadow and specular
    flipped, the rainbow on, a reshaped layer."""
    values = canonical_section()
    if variant == "plain":
        names = layers()
        switch, order = layer_key(names[1], "enabled"), layer_key(names[0], "order")
        values[switch] = not values[switch]
        values.update(follow(switch, values[switch], values))            # Settings re-ranks the stack
        values[order] = len(names)
        values.update(follow(order, len(names), values))
        for key in (PREFIX + "foreground_shadow_enabled", PREFIX + "foreground_specular_enabled"):
            values[key] = not values[key]
        values[PREFIX + "rainbow_enabled"] = True
        nodes = [list(n) for n in values[layer_key(names[2], "shape_nodes")]]
        nodes[0][1] = 1.0 - nodes[0][1]
        values[layer_key(names[2], "shape_nodes")] = nodes
        values[PREFIX + "swell_strength"] = spec().control(PREFIX + "swell_strength").high
    return values


def technical_keys():
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    return {_storage_key(MODE, d) for d in _control_defs_for_mode(MODE)}


def rainbow_keys():
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    return set(get_owned_mode_setting_keys(MODE, "rainbow").values())


def custom_keys():
    return {key for entry in spec().entries if isinstance(entry, Custom) for key in entry.keys}


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
    evaluator = DevCurveStudioEvaluator(loader=loader or InlineLoader())
    evaluator.add_recorded(to_inputs(data, replace(clip, duration=float(data["duration"]))))
    evaluator.select(clip.id)
    return evaluator


def _synthetic_evaluator(fixture_id: str, values):
    evaluator = DevCurveStudioEvaluator(loader=InlineLoader(seconds=None))
    evaluator.select(fixture_id)
    return evaluator, recorded(source_of(evaluator.fixture), values, None)


# ------------------------------------------------------------------------------------- schema
def _vector_elements() -> set[tuple]:
    """Every element of a vector value Settings edits: each layer colour's alpha and every shape-node slot (both
    axes) of every layer, up to the shape editor's maximum."""
    _low, high = node_limits()
    out = set()
    for name in layers():
        out.add((layer_key(name, "color"), 3))
        out |= {(layer_key(name, "shape_nodes"), i, axis) for i in range(high) for axis in (0, 1)}
    return out


def _uncovered(properties) -> set:
    """Registry keys (every spec control, every Custom row key, every technical control and the rainbow family Settings
    shows on DevCurve's page) with no Studio property, plus vector elements no property edits. (The shared bar family
    DevCurve owns is not on its Settings page and DevCurve never draws it: Settings shows it for the Spectrum family
    only.)"""
    roots = {p.path[0] for p in properties}
    paths = {tuple(p.path) for p in properties}
    every = {c.key for c in spec().controls} | custom_keys() | technical_keys() | rainbow_keys()
    return (every - roots) | {element for element in _vector_elements() if element not in paths}


def test_every_devcurve_control_is_editable_in_the_studio():
    assert _uncovered(build_schema().properties) == set()
    assert custom_keys() and technical_keys()                       # the registry has both kinds (sanity)


def test_coverage_check_detects_a_missing_control_negative_control():
    properties = build_schema().properties
    first = layers()[0]
    for dropped in (PREFIX + "motion_power", layer_key(first, "power"), ACTIVE_LAYER, PREFIX + "transient_clamp",
                    next(iter(rainbow_keys()))):
        assert _uncovered([p for p in properties if p.path[0] != dropped]), dropped
    node = (layer_key(first, "shape_nodes"), node_limits()[1] - 1, 1)
    assert node in _uncovered([p for p in properties if tuple(p.path) != node])


def test_instruments_bounds_choices_and_conditions_come_from_the_registry():
    schema = build_schema()
    from ui.studio.adapter import control_condition
    for control in spec().controls:
        prop = schema.find(control.key)
        if isinstance(control, Slider):
            assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
            assert prop.instrument == SCALAR                       # no true interval: never a quiet/peak A/B
        elif isinstance(control, Toggle):
            assert prop.instrument == "switch", control.key
        elif isinstance(control, Choice):
            assert tuple(prop.choice_values or prop.choices) == tuple(control.choices), control.key
        elif isinstance(control, Colour):
            assert prop.instrument == "colour", control.key
        assert prop.when == control_condition(control), control.key
    # Workspaces follow Settings' buckets: every bucket's controls share one workspace and group.
    titles = {bucket.key: bucket.title for bucket in spec().buckets}
    for control in spec().controls:
        assert schema.find(control.key).group == titles[control.bucket]
    # One group per layer (the shaper's own layer names), each with its live reactivity trace.
    traces = dict(schema.group_traces)
    for name in layers():
        group = layer_label(name)
        assert {p.group for p in schema.properties if p.path[0].startswith(f"{PREFIX}layer_{name}_")} == {group}
        assert len(traces[group]) == 3 and all(group in channel for channel in traces[group])


def _devcurve_tab(qt_app, settings_manager):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": MODE,
        "mode_activation": build_visualizer_mode_activation([MODE]),
        f"preset_{MODE}": get_custom_preset_index(MODE)}})
    dialog = QDialog()
    QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
    tab._select_mode_page(MODE)
    return dialog, tab


def _settings_round_trip(tab, values: dict) -> dict:
    """``values`` loaded into Settings' own DevCurve layer row and collected back (``devcurve_settings_binding``)."""
    from ui.tabs.media.devcurve_settings_binding import collect_devcurve_layers, load_devcurve_layers
    load_devcurve_layers(tab, values)
    return collect_devcurve_layers(tab)


def test_layer_rows_store_what_settings_layer_binding_stores(qt_app, settings_manager):
    """Every layer value admitted by the Studio (in range, between Settings' steps, and out of range) is exactly what
    Settings' own layer row stores after a load and collect: the same steps, clamps and opaque outline."""
    dialog, tab = _devcurve_tab(qt_app, settings_manager)
    schema = build_schema()
    base = canonical_section()
    candidates = {"power": (0.4567, 9.0, -1.0), "offset": (0.123, 0.9, -0.9), "alpha": (0.337, 2.0, -0.5),
                  "outline_width": (0.0074, 0.5, 0.0), "color": ([10, 20, 30, 40], [300, -5, 7, 128]),
                  "outline_color": ([10, 20, 30, 40],), "shape_nodes": ([[0.0, 0.2], [0.42, 0.9], [1.0, 0.1]],)}
    checked = 0
    for name in layers():
        for suffix, options in candidates.items():
            key = layer_key(name, suffix)
            for candidate in options:
                admitted = schema.admit(key, candidate, base[key])
                stored = _settings_round_trip(tab, {**base, key: admitted})[key]
                if suffix == "shape_nodes":
                    assert stored == admitted, (key, candidate)
                else:
                    assert stored == pytest.approx(admitted), (key, candidate)
                checked += 1
    assert checked >= 4 * len(candidates)
    dialog.deleteLater()


def test_layer_order_follows_settings_stack_normalisation(qt_app, settings_manager):
    """Changing a layer's order, or switching a layer, re-ranks the stack exactly as Settings' shaper does
    (``_devcurve_normalize_layer_orders``), driven here on the real tab for every layer, rank and on/off state."""
    dialog, tab = _devcurve_tab(qt_app, settings_manager)
    names = layers()
    base = canonical_section()
    for target in names:
        for disabled in (None, *(n for n in names if n != target)):
            values = dict(base)
            for name in names:
                values[layer_key(name, "enabled")] = name != disabled
            for rank in range(1, len(names) + 1):
                key = layer_key(target, "order")
                ours = {**values, key: rank, **follow(key, rank, {**values, key: rank})}
                _settings_round_trip(tab, values)
                tab._devcurve_normalize_layer_orders(target_src=target, target_rank=rank, save=False)
                theirs = {layer_key(n, "order"): int(getattr(tab, f"_devcurve_layer_{n}_order")) for n in names}
                assert {k: ours[k] for k in theirs} == theirs, (target, disabled, rank)
            switch = layer_key(target, "enabled")
            flipped = {**values, switch: not values[switch]}
            ours = {**flipped, **follow(switch, flipped[switch], flipped)}
            _settings_round_trip(tab, flipped)
            theirs = {layer_key(n, "order"): int(getattr(tab, f"_devcurve_layer_{n}_order")) for n in names}
            assert {k: ours[k] for k in theirs} == theirs, (target, disabled, "switch")
    dialog.deleteLater()


def test_shape_nodes_keep_the_solvers_minimum_and_the_editors_maximum():
    """Add Node fills the widest gap on the current contour up to the shape editor's maximum; Remove Node stops at two,
    the fewest the production solver accepts (Settings' editor keeps the same two)."""
    from widgets.spotify_visualizer.devcurve_runtime import _smooth_points
    low, high = node_limits()
    assert low >= 2
    values = canonical_section()
    name = layers()[0]
    key = layer_key(name, "shape_nodes")
    adapter = DevCurveStudioAdapter()
    while len(values[key]) < high:
        before = [list(n) for n in values[key]]
        label, changes = adapter.structure_edit(f"{ADD_NODE}{name}", values)
        values[key] = changes[(key,)]
        assert len(values[key]) == len(before) + 1
        assert _smooth_points(values[key], 201) == pytest.approx(_smooth_points(before, 201), abs=0.08)
    assert adapter.structure_edit(f"{ADD_NODE}{name}", values) is None            # at the maximum: refused
    while len(values[key]) > low:
        _label, changes = adapter.structure_edit(f"{REMOVE_NODE}{name}.0", values)
        values[key] = changes[(key,)]
    assert adapter.structure_edit(f"{REMOVE_NODE}{name}.0", values) is None       # at the minimum: refused
    schema = build_schema()
    assert schema.admit(key, values[key][:1], values[key]) == values[key]          # one node: never admitted
    moved = [list(n) for n in values[key]]
    moved[0][0] = 1.0                                                              # past its neighbour: stops at it
    admitted = schema.admit(key, moved, values[key])
    assert admitted[0][0] == pytest.approx(values[key][1][0])


# ----------------------------------------------------------------------------- the engine split
def _answers(data):
    return [(s["now_ts"], s["answers"]) for s in data["steps"]]


def _flipped(key: str, value):
    """Another admissible value of a mode-owned key."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return next(n for n in layers() if n != value) if key == ACTIVE_LAYER else value
    if isinstance(value, list) and value and isinstance(value[0], list):
        return [[x, 1.0 - y] for x, y in value]
    if isinstance(value, list):
        return [255 - int(v) for v in value[:3]] + [int(value[3])]
    control = next((c for c in spec().controls if c.key == key), None)
    if control is not None:
        low, high = control.low, control.high
    else:
        prop = next((p for p in build_schema().properties if p.path == (key,)), None)
        low, high = (prop.minimum, prop.maximum) if prop is not None else (0.0, 1.0)
    target = high if abs(float(value) - high) > 1e-6 else low
    return int(target) if isinstance(value, int) else target


def test_mode_owned_edits_leave_the_engine_answers_unchanged(qt_app):
    """Every key the Studio treats as DevCurve-owned (instant, no re-analysis) leaves every engine answer of the
    production replay unchanged: all of them changed at once give the same answers, and none changes the key."""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    owned = owned_keys()
    off_page = set(get_owned_mode_setting_keys(MODE, "shared_bar").values())     # stored, never shown or drawn
    assert owned and owned - off_page <= build_schema().keys
    edits = {key: _flipped(key, values[key]) for key in sorted(owned)}
    edited = {**values, **edits}
    for key in edits:
        assert engine_key({**values, key: edits[key]}) == engine_key(values), key
    assert any(edits[k] != values[k] for k in edits)
    assert _answers(extract(clip, edited, seconds=1.0)) == baseline


def test_engine_owned_edits_change_the_engine_answers_negative_control(qt_app):
    """The other direction: an engine-owned edit (the technical analysis) changes the answers and the key, which is
    what sends it to the worker; the two sets partition the mode's stored keys. (DevCurve's layers read the pre-AGC
    control lanes the clip carries, so most analysis values leave them as they are: the bar count and the noise floor
    are among those that change what the engine answers.)"""
    clip = shipped_clip().description
    values = canonical_section()
    baseline = _answers(extract(clip, values, seconds=1.0))
    from ui.studio.technical import technical_properties
    technical = technical_properties(MODE, workspace="core")
    changed = 0
    for key in (PREFIX + "bar_count", PREFIX + "manual_floor"):
        if key not in technical:
            continue
        prop = technical[key][0]
        assert key in engine_values(values)
        target = prop.maximum if abs(float(values[key]) - prop.maximum) > 1e-6 else prop.minimum
        edited = {**values, key: target}
        assert engine_key(edited) != engine_key(values), key
        assert _answers(extract(clip, edited, seconds=1.0)) != baseline, key
        changed += 1
    assert changed >= 1
    every = {k for k in values if k.startswith(PREFIX)}
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


@pytest.mark.parametrize("variant", ["normal", "plain"])
@pytest.mark.parametrize("source", ["synthetic", "shipped_clip"])
def test_studio_frames_equal_the_production_replay_tick_for_tick(qt_app, source, variant):
    """The Studio's in-process tick publishes the production replay's logical frame (every layer curve, the draw
    order, specular slots, every renderer parameter, identities and flags) at every tick."""
    values = variant_section(variant)
    if source == "synthetic":
        evaluator, data = _synthetic_evaluator("mid", values)
    else:
        clip = shipped_clip()
        data = recorded(clip.description, values)
        evaluator = _clip_evaluator(clip, values=values)
    assert _assert_parity(evaluator, data, values) >= 200
    frame = evaluator.evaluate(evaluator.fixture.duration * 0.6, values)
    assert frame.mode_id == MODE and frame.playing and frame.mode_state.curves
    evaluator.release()


def test_parity_check_detects_a_perturbed_engine_answer_negative_control(qt_app):
    from ui.studio.replay_engine import decode_answer, encode_answer
    clip = shipped_clip()
    values = canonical_section()
    data = json.loads(json.dumps(recorded(clip.description, values)))
    middle = len(data["steps"]) // 2
    answers = data["steps"][middle]["answers"]
    bands = decode_answer(answers["get_energy_bands"])
    answers["get_energy_bands"] = encode_answer(type(bands)(1.0, 1.0, 1.0, 1.0))
    evaluator = _clip_evaluator(clip, data=data)
    later = [s for s in data["steps"][middle:middle + 4] if s["frame_sha256"]]
    assert any(frame_digest(evaluator.evaluate(s["now_ts"] - data["origin"], values)) != s["frame_sha256"]
               for s in later)
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
    edited[PREFIX + "motion_power"] = spec().control(PREFIX + "motion_power").high
    after = evaluator.evaluate(at, edited)
    assert len(loader.calls) == calls                                 # no worker for DevCurve-owned values
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
    key = PREFIX + "bar_count"
    edited = {**values, key: int(values[key]) + 8}
    pending = evaluator.evaluate(1.0, edited)
    assert loader.calls[-1] == (clip.id, engine_key(edited)) and evaluator.analysing
    assert frame_digest(pending) == frame_digest(original)           # previous answers on screen meanwhile
    production = recorded(clip.description, edited)
    target = next(s for s in production["steps"] if s["now_ts"] - production["origin"] >= 1.0 - 1e-9)
    loader.land()
    assert landed and not evaluator.analysing
    landed_frame = evaluator.evaluate(target["now_ts"] - production["origin"], edited)
    assert frame_digest(landed_frame) == target["frame_sha256"]
    assert frame_digest(pending) != target["frame_sha256"]           # the re-run was needed (negative control)
    evaluator.release()


# ------------------------------------------------------------------------------------ reactivity traces
def test_every_traced_channel_is_measured_and_reads_change_nothing(qt_app):
    """Each channel the schema traces is measured from the evaluator's own runtime, within the trace range; reading
    them never changes a frame (the same history without reads publishes the same frames)."""
    values = canonical_section()
    evaluator, data = _synthetic_evaluator("peak", values)
    plain, _ = _synthetic_evaluator("peak", values)
    channels = {c for _group, names in build_schema().group_traces for c in names}
    for at in (1.0, 2.5, 4.0):
        frame = evaluator.evaluate(at, values)
        signals = evaluator.measurements()["signals"]
        assert channels <= set(signals)
        assert all(-1e-9 <= signals[c] <= 1.6 for c in channels), signals
        assert frame_digest(frame) == frame_digest(plain.evaluate(at, values))
    evaluator.release()
    plain.release()


# The hit window: from just before the isolated kick to the accents' own reach (two stages of 0.025 s attack land a
# hit well inside 0.1 s), far shorter than the body's two slow stages (``DEVCURVE_BODY_STAGE_S``, 0.45 s attack).
HIT_WINDOW = (-0.05, 0.1)
BODY_LAYERS = ("bass", "vocals", "mids")         # the layers whose height is a slow body plus fast accents


def _hit_rises(values) -> dict[str, tuple[float, float]]:
    """Per body layer, (Accent rise, Body rise) of the traces across the hit window of the isolated-hit fixture."""
    from ui.studio.engine_answers import PREROLL, START, synthetic_score
    evaluator, _data = _synthetic_evaluator("transient", values)
    _pcm, events = synthetic_score("transient")
    hit = next(when for when, kind, _s in events if kind == "kick") - (START + PREROLL)
    traces = []
    for offset in HIT_WINDOW:
        evaluator.evaluate(hit + offset, values)
        traces.append(evaluator.measurements()["signals"])
    evaluator.release()
    before, after = traces
    return {name: tuple(after[f"{layer_label(name)} {part}"] - before[f"{layer_label(name)} {part}"]
                        for part in ("Accent", "Body")) for name in BODY_LAYERS}


def _hit_shows_in_the_accents(rises) -> bool:
    """Every body layer's Accent carries the hit (a clear rise) and its Body holds (a small fraction of that)."""
    return all(accent > 0.1 and max(body, 0.0) < 0.2 * accent for accent, body in rises.values())


def test_traces_show_a_hit_in_the_accents_while_the_body_holds(qt_app, monkeypatch):
    """On the isolated-hit fixture each body layer's Accent jumps within the hit window while its Body (the slow,
    normalised passage height) holds; the swell travels in afterwards. Negative controls on the production solver: with
    no accent room the hit has nowhere to show in the accents, and with the body as fast as the accents the hit lands
    in the body; either way the check fails. Before any audio there is nothing to trace."""
    from widgets.spotify_visualizer import devcurve_runtime as solver
    values = canonical_section()
    rises = _hit_rises(values)
    assert _hit_shows_in_the_accents(rises), rises
    evaluator, _data = _synthetic_evaluator("transient", values)
    evaluator.evaluate(4.0, values)
    assert evaluator.measurements()["signals"][f"{layer_label(layers()[0])} Swell"] > 0.0
    evaluator.release()
    with monkeypatch.context() as patch:                       # accents can no longer carry hits
        patch.setattr(solver, "DEVCURVE_ACCENT_ROOM", dict.fromkeys(solver.DEVCURVE_ACCENT_ROOM, 0.0))
        muted = _hit_rises(values)
    assert not _hit_shows_in_the_accents(muted), muted
    with monkeypatch.context() as patch:                       # the hit routed into the body: fast as an accent
        patch.setattr(solver, "DEVCURVE_BODY_STAGE_S", solver.DEVCURVE_ACCENT_STAGE_S)
        patch.setattr(solver, "DEVCURVE_RESPONSE_REACH_S", solver.DEVCURVE_RESPONSE_MEMORY_S)
        routed = _hit_rises(values)
    assert not _hit_shows_in_the_accents(routed), routed
    empty = DevCurveStudioEvaluator(loader=lambda *_a: None)
    assert empty.measurements()["signals"] == {}


# ------------------------------------------------------------------------------------ worker and clips
def test_the_studio_lists_the_shipped_clips_and_analyses_them_out_of_process(qt_app):
    """The adapter's recorded music is the Studios' shared list (shipped clips first); a clip is analysed by this
    mode's worker in its own process (``ClipLoadJob``), event driven, and replays as the in-process production."""
    from PySide6.QtCore import QCoreApplication, QElapsedTimer, QEventLoop
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips
    adapter = DevCurveStudioAdapter()
    clips = adapter.recorded_clips()
    assert clips == studio_clips(recordings_directory()) and clips
    clip = shipped_clip()
    values = canonical_section()
    results = []
    job = adapter.start_clip_load(clip, values, lambda result, error="": results.append((result, error)))
    assert job is not None
    timer = QElapsedTimer()
    timer.start()
    while not results and timer.elapsed() < 180_000:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    (inputs, error), = results
    assert not error and inputs.fixture.id == clip.id and inputs.engine_values == engine_values(values)
    cached = []
    assert adapter.start_clip_load(clip, values, lambda result, error="": cached.append(result)) is None
    assert cached == [inputs]                                         # analysed once per engine values
    evaluator = DevCurveStudioEvaluator(loader=lambda *_a: None)
    evaluator.add_recorded(inputs)
    evaluator.select(clip.id)
    from ui.studio.waveform_recorded_inputs import CLIP_SECONDS as WORKER_SECONDS
    data = recorded(clip.description, values, WORKER_SECONDS)
    assert _assert_parity(evaluator, data, values, every=25) >= 20
    evaluator.release()


# ------------------------------------------------------------------------------------ Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="DevCurveStudio",
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
    built = []

    def build():
        dialog, tab = _devcurve_tab(qt_app, settings_manager)
        built.append(dialog)
        return dialog, tab
    yield build
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


class InlineAdapter(DevCurveStudioAdapter):
    """The real adapter with the worker run in this process and no recorded clips offered."""

    def recorded_clips(self):
        return ()

    def create_evaluator(self):
        return DevCurveStudioEvaluator(loader=InlineLoader(seconds=None))


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


def test_the_preset_row_offers_the_devcurve_studio_instead_of_edit_preset(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    from ui.studio.registry import has_studio
    assert has_studio(MODE)
    _dialog, tab = dialog_tab()
    slider = tab._get_visualizer_preset_slider(MODE)
    button = getattr(tab, f"_{MODE}_studio_button")
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
    names = layers()
    # A Core slider, a layer's alpha, power, colour alpha and a node, the stack order (Settings re-ranks), a layer
    # switch, Add Node, the Edit Layer choice, the rainbow and a technical value, each through Settings' own save.
    bridge.commitValue(PREFIX + "swell_speed", 0, 1.5)
    assert stored()[PREFIX + "swell_speed"] == pytest.approx(1.5)
    bridge.commitValue(layer_key(names[2], "alpha"), 0, 0.37)
    assert stored()[layer_key(names[2], "alpha")] == pytest.approx(0.37)
    bridge.commitValue(layer_key(names[1], "power"), 0, 2.4)
    assert stored()[layer_key(names[1], "power")] == pytest.approx(2.4)
    bridge.commitValue(f"{layer_key(names[0], 'color')}.3", 0, 120)
    assert stored()[layer_key(names[0], "color")][3] == 120
    nodes_key = layer_key(names[3], "shape_nodes")
    height = session.values[nodes_key][0][1]
    bridge.commitValue(f"{nodes_key}.0.1", 0, round(1.0 - height, 3))
    assert stored()[nodes_key][0][1] == pytest.approx(round(1.0 - height, 3))
    count = len(session.values[nodes_key])
    if count < node_limits()[1]:
        bridge.runAction(f"{ADD_NODE}{names[3]}")
        assert len(stored()[nodes_key]) == count + 1
    enabled = [n for n in names if session.values[layer_key(n, "enabled")]]
    if len(enabled) >= 2:
        mover = enabled[-1]
        bridge.commitValue(layer_key(mover, "order"), 0, 1)
        ranks = {n: stored()[layer_key(n, "order")] for n in names}
        assert ranks[mover] == 1 and sorted(ranks.values()) == list(range(1, len(names) + 1))
    switch = layer_key(names[1], "enabled")
    flipped = not bool(session.values[switch])
    bridge.commitValue(switch, 0, flipped)
    assert stored()[switch] is flipped
    assert sorted(stored()[layer_key(n, "order")] for n in names) == list(range(1, len(names) + 1))
    other = next(n for n in names if n != session.values[ACTIVE_LAYER])
    bridge.commitValue(ACTIVE_LAYER, 0, layer_label(other))
    assert stored()[ACTIVE_LAYER] == other
    rainbow = sorted(rainbow_keys())
    on = next(k for k in rainbow if k.endswith("enabled"))
    bridge.commitValue(on, 0, True)
    assert stored()[on] is True
    bridge.commitValue(PREFIX + "transient_clamp", 0, 0.9)
    assert stored()[PREFIX + "transient_clamp"] == pytest.approx(0.9)
    assert stored()[PREFIX + "swell_speed"] == pytest.approx(1.5)                   # nothing reverted by later saves
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
    for _ in range(400):
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
    assert surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3].std() > 4.0           # curves drawn

    clip = shipped_clip()
    frames = {}
    for variant in ("normal", "plain"):
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
    for variant in ("normal", "plain"):
        assert images[f"{variant}/live"][..., :3].std() > 2.0
        assert np.array_equal(images[f"{variant}/live"], images[f"{variant}/studio"]), variant
    assert np.abs(images["normal/live"] - images["plain/live"]).max() > 20             # negative control
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


# --------------------------------------------------------------------------- Save To <Preset> (real Settings)
@pytest.fixture
def preset_copy(tmp_path, monkeypatch):
    """A tmp copy of DevCurve's real curated folder, made the preset owner's root (then restored)."""
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
    from ui.styled_popup import StyledPopup
    seen = []
    state = {"answer": "cancel"}

    def fake_exec(popup):
        seen.append({"icon": popup._icon_type, "buttons": [value for _label, value in popup._buttons]})
        popup._result_value = state["answer"] if state["answer"] in seen[-1]["buttons"] else None
        return 1

    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    return seen, state


@pytest.fixture
def real_dialog(qt_app, tmp_path, monkeypatch, no_gl_checks):
    """The real SettingsDialog on DevCurve; its Open Studio click opens this adapter on the hidden surface."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from ui.settings_dialog import SettingsDialog
    from ui.studio import settings_link
    manager = SettingsManager(organization="SRPSSFocusedTests", application="DevCurveStudioPreset",
                              storage_base_dir=tmp_path / "profile")
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": MODE,
                   "mode_activation": build_visualizer_mode_activation([MODE])})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    real = settings_link.open_mode_studio
    opened = []

    def launch(tab, mode_id):
        surfaces = []
        controller = real(tab, mode_id, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, (960, 600)))
        surfaces[0].pump()
        opened.append(controller)
        return controller
    monkeypatch.setattr(settings_link, "open_mode_studio", launch)
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
    tab = dialog.visualizers_tab
    tab._select_mode_page(MODE)
    yield dialog, tab, opened
    dialog.close()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert manager.flush(timeout=5.0)


def test_save_to_preset_writes_a_devcurve_edit_into_the_curated_files_own_shape(real_dialog, preset_copy, popups):
    """Open Studio on a curated DevCurve slot (real SettingsDialog), edit one authored scalar and a layer value, then
    Save To <that preset>: it asks first, Cancel writes nothing, Save patches only those keys in the file's own shape
    and the preset owner reloads them; Custom stays selected."""
    from core.settings import visualizer_presets as vp
    from core.settings.visualizer_preset_file import key_order
    dialog, tab, opened = real_dialog
    seen, state = popups
    slider = tab._get_visualizer_preset_slider(MODE)
    curated = slider.custom_index() - 1                      # the last curated slot (never the default first)
    path = vp.get_preset_file_path(MODE, curated)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    vp.reload_presets(MODE)
    slider._slider.setValue(curated)
    getattr(tab, f"_{MODE}_studio_button").click()
    bridge = opened[-1].bridge
    assert bridge.presetLabel == vp.get_preset_names(MODE)[curated]
    text = path.read_text(encoding="utf-8")
    authored = vp.resolve_preset_payload_settings(MODE, json.loads(text))
    schema = build_schema()
    prop = next(p for p in schema.properties
                if p.instrument == SCALAR and not p.integer and len(p.path) == 1 and p.id in authored
                and p.id in {c.key for c in spec().controls} and text.count(f'"{p.id}"') == 1)
    span = prop.maximum - prop.minimum
    shown = float(bridge.values[prop.id])
    target = round(prop.minimum + span * (0.25 if shown > prop.minimum + span / 2 else 0.75), 2)
    bridge.commitValue(prop.id, 0, target)
    alpha = layer_key(layers()[0], "alpha")
    alpha_target = 0.21 if abs(float(authored.get(alpha, 0.0)) - 0.21) > 1e-6 else 0.79
    bridge.commitValue(alpha, 0, alpha_target)
    assert slider.preset_index() == slider.custom_index()          # a Studio edit lands in Custom
    assert bridge.savePresetTarget == vp.get_preset_names(MODE)[curated]
    before = path.read_bytes()
    state["answer"] = "cancel"
    bridge.saveToPreset()
    assert [p["icon"] for p in seen] == ["question"] and path.read_bytes() == before
    state["answer"] = "save"
    bridge.saveToPreset()
    new_text = path.read_text(encoding="utf-8")
    old_payload, new_payload = json.loads(before.decode("utf-8")), json.loads(new_text)
    assert key_order(old_payload) == key_order(new_payload)
    old_resolved = vp.resolve_preset_payload_settings(MODE, old_payload)
    new_resolved = vp.resolve_preset_payload_settings(MODE, new_payload)
    assert new_resolved[prop.id] == pytest.approx(target) and new_resolved[alpha] == pytest.approx(alpha_target)
    changed = {k for k in set(old_resolved) | set(new_resolved) if old_resolved.get(k) != new_resolved.get(k)}
    assert changed == {prop.id, alpha}
    assert new_text.endswith("\n") == before.decode("utf-8").endswith("\n")
    assert vp.get_preset_settings(MODE, curated)[prop.id] == pytest.approx(target)    # presets were reloaded
    assert slider.preset_index() == slider.custom_index()                             # Custom stays as it was
