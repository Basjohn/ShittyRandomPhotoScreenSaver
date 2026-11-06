"""The Studio previews react to the Audio Analysis controls the way the live engine does.

The engine-processed Studios (DevCurve, Oscilloscope, Neon Lake's onset waves) and the recorded-input Studios
(Bubble, Extruded Bubble, Sphere) analyse a recorded clip out of process. They once replayed its *recorded* post-DSP
lanes, which no Sensitivity, floor or Gain value can move, so those edits did little or nothing on screen while the
live engine changed every frame. Their workers now replay on ``feature_replay.ProductionLaneEngine``: every lane
re-analysed from the clip's PCM through the production DSP under the edited values.

Proved per mode on a shipped clip, with test-owned frozen settings (``tools/freeze_visualizer_settings``) and
test-owned values (no preset or default is pinned):

* the worker's production frames move with Sensitivity (manual), the fixed noise floor and Input Gain, and the old
  recorded-lanes path leaves them bit-identical (negative control);
* the engine-answer worker's frames equal the independent production replay on re-analysed lanes (the live path
  ``tools/visualizer_replay/analysis_controls_audit`` measures), frame for frame;
* through the Studio itself (bridge edit, hidden offscreen surface, never-shown store), an Audio Analysis edit
  re-analyses the selected clip and moves the frame on screen; without the re-analysis it does not (negative
  control).

Nothing here shows a window or starts a worker process: analyses run in process.
"""
from __future__ import annotations

from dataclasses import replace
from importlib import import_module
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.qt

ENGINE_ANSWER_MODES = {"devcurve": "DEVCURVE", "oscilloscope": "OSCILLOSCOPE", "shockwave_grid": "NEON_LAKE"}
RECORDED_INPUT_MODES = ("bubble", "extruded_bubble", "sphere")
MODES = (*ENGINE_ANSWER_MODES, *RECORDED_INPUT_MODES)
CLIP, START, SECONDS = "human", 4.0, 3.0           # a hot passage of a shipped clip


def _variants(mode: str) -> dict:
    """Two test-owned settings of each control (the enabler it acts under forced alike)."""
    p = f"{mode}_"
    return {
        "sensitivity": ({p + "adaptive_sensitivity": False, p + "sensitivity": 0.5},
                        {p + "adaptive_sensitivity": False, p + "sensitivity": 2.0}),
        "floor": ({p + "dynamic_floor": False, p + "manual_floor": 0.1},
                  {p + "dynamic_floor": False, p + "manual_floor": 0.6}),
        "gain": ({p + "input_gain": 0.6}, {p + "input_gain": 1.6}),
    }


_CLIP = {}


def _clip():
    if "frames" not in _CLIP:
        from tools.visualizer_replay.analysis_controls_audit import load_clip
        _CLIP["frames"] = load_clip(CLIP, SECONDS, start=START).frames
    return _CLIP["frames"]


def _frozen(mode):
    from tools.visualizer_replay.analysis_controls_audit import frozen
    return frozen(mode)


def _answer_mode(mode):
    return getattr(import_module(f"ui.studio.{mode}_recorded_inputs"), ENGINE_ANSWER_MODES[mode])


def _worker_frames(mode: str, settings, *, recorded_lanes: bool = False):
    """(per-tick frame digests, the production frames) of the mode's clip worker run in process; ``recorded_lanes``:
    the old path (``ReplayBeatEngine``: the recording's post-DSP lanes)."""
    from widgets.spotify_visualizer import feature_replay
    frames: list = []
    if mode in ENGINE_ANSWER_MODES:
        from ui.studio import engine_answers
        answer_mode = replace(_answer_mode(mode), production_lanes=not recorded_lanes)
        data = engine_answers.extract(answer_mode, "test", settings, features=_clip(), frames_out=frames)
    else:
        worker = import_module(f"ui.studio.{mode}_recorded_inputs")
        engine = feature_replay.ReplayBeatEngine if recorded_lanes else feature_replay.ProductionLaneEngine
        with patch.object(feature_replay, "ProductionLaneEngine", engine):
            data = worker.extract("test", settings, features=list(_clip()))
    return [s["frame_sha256"] for s in data["steps"] if s.get("frame_sha256")], [f for _t, f in frames]


def _waves(frames) -> list:
    """Neon Lake's onset waves (each live wave's strength) per frame: what the recorded lanes left unmoved."""
    return [tuple(round(float(e[3]), 9) for e in frame.mode_state.events) for frame in frames]


def _moved(a, b) -> float:
    assert a and len(a) == len(b)
    return sum(1 for x, y in zip(a, b) if x != y) / len(a)


@pytest.mark.parametrize("control", ("sensitivity", "floor", "gain"))
@pytest.mark.parametrize("mode", MODES)
def test_production_lanes_move_with_the_control_and_recorded_lanes_do_not(qt_app, mode, control):
    base = _frozen(mode)
    low, high = _variants(mode)[control]
    moved = {}
    for recorded in (False, True):
        a, frames_a = _worker_frames(mode, {**base, **low}, recorded_lanes=recorded)
        b, frames_b = _worker_frames(mode, {**base, **high}, recorded_lanes=recorded)
        if mode == "shockwave_grid":       # its shaped bars were always re-analysed: the onset waves were not
            a, b = _waves(frames_a), _waves(frames_b)
        moved[recorded] = _moved(a, b)
    assert moved[False] >= 0.5, f"{mode} {control}: production lanes moved only {moved[False]:.0%} of frames"
    assert moved[True] == 0.0, f"{mode} {control}: the recorded-lanes negative control moved {moved[True]:.0%}"


@pytest.mark.parametrize("mode", tuple(ENGINE_ANSWER_MODES))
def test_the_worker_frames_are_the_live_paths_production_replay(qt_app, mode):
    """What the Studio's worker records under an edited value is what the production replay on re-analysed lanes
    publishes (the audit's live-path stand-in), field for field, every tick."""
    from tools.visualizer_replay import analysis_controls_audit as audit
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    overrides = _variants(mode)["sensitivity"][1]
    _digests, frames = _worker_frames(mode, {**_frozen(mode), **overrides})
    live = audit.replay(mode, FeatureClip(CLIP, tuple(_clip())), overrides)
    assert len(frames) == len(live)
    assert [audit._channels(frame, mode) for frame in frames] == live


# ------------------------------------------------------------------------------ through the Studio itself
class _Store:
    """A never-shown canonical store: the frozen settings in memory (nothing is saved)."""

    def __init__(self, values):
        self.values = dict(values)

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Custom"

    def presets(self):
        return []

    def preset_index(self):
        return 0


class _NoPresence:
    def conceal(self):
        pass

    def reveal(self):
        pass


class _QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


def _in_process(convert, extract):
    """A clip load that analyses in process (the worker's own ``extract``) and finishes at once."""
    def load(clip, values, finished):
        data = extract(clip, dict(values))
        finished(convert(data, replace(clip, duration=float(data["duration"]))), "")
        return None
    return load


def _studio(mode, *, reanalyse=True):
    from core.settings.default_contract import require_canonical_default
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()
    adapter = create_adapter(mode)
    adapter.create_renderer = _QuietRenderer
    clip = next(c for c in adapter.recorded_clips() if c.id == f"clip:{CLIP}")
    if mode in ENGINE_ANSWER_MODES:
        from ui.studio import engine_answers
        answer_mode = _answer_mode(mode)

        def extract(fixture, values):
            return engine_answers.extract(answer_mode, fixture.description, values, features=_clip())
        load = _in_process(engine_answers.to_inputs, extract)
        evaluator_type = type(adapter.create_evaluator())
        adapter.create_evaluator = lambda: evaluator_type(loader=load)
        adapter.start_clip_load = load
    else:
        worker = import_module(f"ui.studio.{mode}_recorded_inputs")
        adapter.start_clip_load = _in_process(
            worker.to_inputs, lambda fixture, values: worker.extract(fixture.description, values,
                                                                     features=list(_clip())))
        if not reanalyse:
            adapter.clip_analysis_keys = lambda: frozenset()       # the old Studio: a clip analysed once
    values = {**require_canonical_default("widgets.spotify_visualizer"), **_frozen(mode)}
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(800, 500), present_on_show=False))
        return surfaces[0]
    controller = StudioController(adapter, _Store(values), _NoPresence(), factory)
    assert controller.open()
    controller.select_fixture(clip.id)
    controller.select_fixture(clip.id)                 # landed in process: selected
    assert controller.evaluator.fixture.id == clip.id
    return controller, surfaces[0]


def _shown(controller, surface, at: float):
    from tools.visualizer_replay.analysis_controls_audit import _flat
    controller.seek(at)
    surface.pump()
    for _ in range(2000):
        if not getattr(controller.evaluator, "converging", False):
            break
        surface.pump()
    return _flat(controller.last_frame)


@pytest.mark.parametrize("mode", MODES)
def test_an_audio_analysis_edit_moves_the_studio_preview(qt_app, mode):
    p = f"{mode}_"
    controller, surface = _studio(mode)
    try:
        bridge = controller.bridge
        bridge.commitValue(p + "adaptive_sensitivity", 0, False)
        bridge.commitValue(p + "sensitivity", 0, 0.5)
        quiet = _shown(controller, surface, SECONDS * 0.6)
        bridge.commitValue(p + "sensitivity", 0, 2.0)
        loud = _shown(controller, surface, SECONDS * 0.6)
        assert loud != quiet, f"{mode}: Sensitivity did not move the preview"
        assert p + "sensitivity" in controller.release_only_keys      # one re-analysis, on release
        bridge.undo()
        assert _shown(controller, surface, SECONDS * 0.6) == quiet     # undo re-analyses back exactly
    finally:
        controller.close()


@pytest.mark.parametrize("mode", RECORDED_INPUT_MODES)
def test_without_reanalysis_the_preview_stays_put_negative_control(qt_app, mode):
    p = f"{mode}_"
    controller, surface = _studio(mode, reanalyse=False)
    try:
        bridge = controller.bridge
        bridge.commitValue(p + "adaptive_sensitivity", 0, False)
        bridge.commitValue(p + "sensitivity", 0, 0.5)
        quiet = _shown(controller, surface, SECONDS * 0.6)
        bridge.commitValue(p + "sensitivity", 0, 2.0)
        assert _shown(controller, surface, SECONDS * 0.6) == quiet
    finally:
        controller.close()
