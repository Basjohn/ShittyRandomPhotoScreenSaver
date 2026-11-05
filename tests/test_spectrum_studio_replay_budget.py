"""Spectrum Studio exact replays never stall the GUI: they rewind instead of re-configuring, and spread over frames.

A Spectrum-owned commit used to configure a new production controller and replay every tick from the fixture start
in one evaluation (about 0.3 s late in the longest clip). Now the evaluator rewinds its production step state to a
capture taken right after configuration (or to a checkpoint of the same values), restyles it, and, under the frame
budget the Studio sets, steps on across frames while the live-applied frame stays on screen. Proven here: the rewound
replay equals the production replay for *every* Spectrum-owned key (negative control: without the restyle it does
not), an evaluation never steps more than its budget allows, undo and seeks back resume from checkpoints, and the
Studio keeps asking for frames until the replay has converged. Timings are measured by
``tools/spectrum_studio_replay_budget.py`` (evidence), not pinned here. Nothing shows a window.
"""
from __future__ import annotations

import pytest

from ui.studio.spectrum_adapter import SpectrumStudioEvaluator, spectrum_owned_keys
from ui.studio.spectrum_recorded_inputs import frame_digest

from tests.test_spectrum_studio import (  # noqa: F401  (fixtures and helpers)
    InlineAdapter, LightAdapter, _clip_evaluator, _flipped, _fresh_analysis_cache, _surfaces, canonical_section,
    dialog_tab, no_gl_checks, recorded, settings_manager, shipped_clip,
)

PREFIX = "spectrum_"


def _expected(data, at: float) -> str:
    steps = [s for s in data["steps"] if s["now_ts"] - data["origin"] <= at + 1e-9 and s["frame_sha256"]]
    return steps[-1]["frame_sha256"]


def _converge(evaluator, at, values, limit=5000):
    frames = []
    while True:
        before = evaluator.steps_run
        frame = evaluator.evaluate(at, values)
        frames.append((frame, evaluator.steps_run - before))
        if not evaluator.converging or len(frames) > limit:
            return frames


def test_every_spectrum_owned_edit_rewinds_without_reconfiguring_and_replays_exactly(qt_app):
    """Pristine rewind + restyle equals the production replay under the edited values, key by key."""
    clip = shipped_clip()
    values = canonical_section()
    evaluator = _clip_evaluator(clip, values=values, data=recorded(clip.description, values, 1.0))
    evaluator.evaluate(1.0, values)
    replays = evaluator.replays
    for key in sorted(spectrum_owned_keys()):
        edited = dict(values)
        edited[key] = _flipped(key, values[key])
        frame = evaluator.evaluate(1.0, edited)
        assert frame_digest(frame) == _expected(recorded(clip.description, edited, 1.0), 1.0), key
    assert evaluator.replays == replays                 # never a new controller (no ~20 ms configuration)
    assert evaluator.unrecorded_reads == 0
    evaluator.release()


def test_a_rewind_without_the_restyle_is_caught_negative_control(qt_app, monkeypatch):
    clip = shipped_clip()
    values = canonical_section()
    evaluator = _clip_evaluator(clip, values=values, data=recorded(clip.description, values, 1.0))
    evaluator.evaluate(1.0, values)
    edited = dict(values)
    edited[PREFIX + "ghost_decay"] = _flipped(PREFIX + "ghost_decay", values[PREFIX + "ghost_decay"])
    edited[PREFIX + "ghosting_enabled"] = True

    def unstyled(self, vals, signature=None):
        self._signature = self._own_signature(vals) if signature is None else signature
    monkeypatch.setattr(SpectrumStudioEvaluator, "_restyle", unstyled)
    frame = evaluator.evaluate(1.0, edited)
    assert frame_digest(frame) != _expected(recorded(clip.description, edited, 1.0), 1.0)
    evaluator.release()


@pytest.mark.parametrize("key", [PREFIX + "ghost_decay", PREFIX + "visual_smoothing", PREFIX + "bar_fill_color"])
def test_under_a_budget_a_commit_shows_the_live_frame_then_converges_a_tick_per_evaluation(qt_app, key):
    """A zero budget allows one production tick per evaluation (deterministic): the commit's first evaluation
    shows the live-applied frame, every later one steps at most one tick, and the last one is the exact frame."""
    clip = shipped_clip()
    values = canonical_section()
    data = recorded(clip.description, values)
    evaluator = _clip_evaluator(clip, values=values, data=data)
    end = evaluator.fixture.duration
    before = evaluator.evaluate(end, values)
    evaluator.set_frame_budget(0.0)
    edited = dict(values)
    edited[key] = _flipped(key, values[key])
    replays = evaluator.replays
    frames = _converge(evaluator, end, edited)
    live, first_steps = frames[0]
    assert first_steps <= 1 and frame_digest(live) != frame_digest(before)      # the change shows at once
    assert len(frames) > 20 and all(steps <= 1 for _frame, steps in frames[1:])
    assert all(frame is live for frame, _s in frames[1:-1])                      # the live frame stays meanwhile
    assert frame_digest(frames[-1][0]) == _expected(recorded(clip.description, edited), end)
    assert evaluator.replays == replays
    evaluator.release()


def test_undo_and_seeks_back_resume_from_checkpoints(qt_app):
    clip = shipped_clip()
    values = canonical_section()
    data = recorded(clip.description, values)
    evaluator = _clip_evaluator(clip, values=values, data=data)
    end = evaluator.fixture.duration
    evaluator.evaluate(end, values)
    full = evaluator.steps_run
    edited = dict(values)
    edited[PREFIX + "visual_smoothing"] = 0.9
    evaluator.evaluate(end, edited)
    # Undo: the previous values' checkpoints are kept, so only the ticks after the last one are stepped.
    steps = evaluator.steps_run
    frame = evaluator.evaluate(end, values)
    assert evaluator.steps_run - steps < evaluator.CHECKPOINT_TICKS
    assert frame_digest(frame) == _expected(data, end)
    # A seek back lands exactly from the checkpoint before it.
    at = end * 0.6
    steps = evaluator.steps_run
    frame = evaluator.evaluate(at, values)
    assert evaluator.steps_run - steps < evaluator.CHECKPOINT_TICKS
    assert frame_digest(frame) == _expected(data, at)
    assert full >= len(data["steps"]) and evaluator.rewinds >= 2
    evaluator.release()


def test_the_studio_sets_the_budget_and_requests_frames_until_the_replay_converges(qt_app, dialog_tab,
                                                                                   no_gl_checks):
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, "spectrum", adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surface = surfaces[0]
    for _ in range(200):
        surface.pump()
        if controller.last_frame is not None and not controller.evaluator.converging:
            break
    evaluator = controller.evaluator
    assert evaluator._budget == StudioController.EVALUATION_BUDGET_S
    controller.seek(controller.transport.duration)
    for _ in range(400):
        surface.pump()
        if not evaluator.converging:
            break
    evaluations = controller.evaluations
    evaluator.set_frame_budget(0.0)                        # one tick per frame from here (deterministic)
    controller.bridge.commitValue(PREFIX + "visual_smoothing", 0, 0.91)
    for _ in range(5000):
        surface.pump()
        if not evaluator.converging:
            break
    assert not evaluator.converging and controller.evaluations - evaluations > 20      # frames kept coming
    values = controller.evaluation_values()
    expected = SpectrumStudioEvaluator(loader=evaluator._loader)       # the same answers (process cache), unbudgeted
    expected.select(evaluator.fixture.id)
    assert frame_digest(expected.evaluate(controller.transport.time, values)) == frame_digest(controller.last_frame)
    expected.release()
    controller.close()
