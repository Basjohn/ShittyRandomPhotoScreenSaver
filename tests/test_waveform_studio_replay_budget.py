"""Waveform Studio exact replays never stall the GUI: they spread over frames under the Studio's budget and resume
from checkpoints, through the shared ``ui.studio.exact_replay.ExactReplay`` (the Spectrum family's mechanism).

A Waveform commit used to replay every tick from the fixture start in one evaluation (about 120 ms late in a
fixture). Proven here with a zero budget (one production tick per evaluation, deterministic): the commit's first
evaluation shows the change live-applied, every later one steps at most one tick, the frame shown meanwhile is that
same frame, and the landed frame equals a fresh unbudgeted replay byte for byte; undo and seeks back resume from
checkpoints; the Studio sets the budget and keeps asking for frames until the replay lands. Negative control: with no
budget (the former behaviour) one evaluation steps the whole replay. Timings are measured by
``tools/studio_drag_profile.py`` (evidence), not pinned here. Nothing shows a window.
"""
from __future__ import annotations

import pytest

from ui.studio.exact_replay import ExactReplay
from ui.studio.waveform_adapter import WaveformStudioEvaluator

from tests.test_waveform_studio_evaluator import canonical_section

AT = 6.0


def _edited(values):
    """A test-owned edit of a ribbon card's height (a logical value: the history changes)."""
    edited = dict(values)
    cards = [dict(card) for card in values["waveform_ribbon_ribbons"]]
    cards[0]["height"] = min(2.0, cards[0]["height"] * 1.5)
    edited["waveform_ribbon_ribbons"] = cards
    return edited


def _fresh(values, at=AT, extent=None):
    """A fresh, unbudgeted exact replay (at the presented card ``extent`` when given)."""
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    if extent is not None:
        evaluator.set_viewport_extent(extent)
    payload = evaluator.evaluate(at, values).packet.payload
    evaluator.release()
    return payload


def _converge(evaluator, at, values, limit=5000):
    frames = []
    while True:
        before = evaluator.steps_run
        frame = evaluator.evaluate(at, values)
        frames.append((frame, evaluator.steps_run - before))
        if not evaluator.converging or len(frames) > limit:
            return frames


def test_the_waveform_evaluator_uses_the_shared_replay_mechanism():
    assert isinstance(WaveformStudioEvaluator(), ExactReplay)
    from ui.studio.engine_answers import EngineAnswerEvaluator
    assert issubclass(EngineAnswerEvaluator, ExactReplay)
    for name in ("_advance", "_rewind", "_checkpoint", "_replay", "set_frame_budget"):
        assert name not in vars(WaveformStudioEvaluator) and name not in vars(EngineAnswerEvaluator), name


def test_under_a_budget_a_commit_shows_the_live_frame_then_lands_exactly():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    before = evaluator.evaluate(AT, values)
    evaluator.set_frame_budget(0.0)
    edited = _edited(values)
    frames = _converge(evaluator, AT, edited)
    live, first_steps = frames[0]
    assert first_steps <= 1 and live.packet.payload != before.packet.payload        # the change shows at once
    assert len(frames) > 20 and all(steps <= 1 for _frame, steps in frames[1:])
    assert all(frame is live for frame, _s in frames[1:-1])                         # the shown frame stays
    assert frames[-1][0].packet.payload == _fresh(edited)                            # exact when it lands
    evaluator.release()


def test_without_a_budget_one_evaluation_replays_everything_negative_control():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    evaluator.evaluate(AT, values)
    frames = _converge(evaluator, AT, _edited(values))
    assert len(frames) == 1 and frames[0][1] > ExactReplay.CHECKPOINT_TICKS
    evaluator.release()


def test_a_gesture_release_keeps_the_last_live_frame_until_the_exact_replay_lands():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    evaluator.evaluate(AT, values)
    evaluator.set_frame_budget(0.0)
    edited = _edited(values)
    live = evaluator.evaluate(AT, edited, exact=False)                            # the drag's last frame
    frames = _converge(evaluator, AT, edited)                                       # the release
    assert len(frames) > 20 and all(frame is live for frame, _s in frames[:-1])
    assert frames[-1][0].packet.payload == _fresh(edited)
    evaluator.release()


def test_undo_and_seeks_back_resume_from_checkpoints():
    values = canonical_section()
    evaluator = WaveformStudioEvaluator()
    evaluator.select("peak")
    evaluator.evaluate(AT, values)
    edited = _edited(values)
    evaluator.evaluate(AT, edited)
    steps = evaluator.steps_run
    frame = evaluator.evaluate(AT, values)                                          # undo
    assert evaluator.steps_run - steps < evaluator.CHECKPOINT_TICKS
    assert frame.packet.payload == _fresh(values)
    at = AT * 0.6
    steps = evaluator.steps_run
    frame = evaluator.evaluate(at, values)                                          # a seek back
    assert evaluator.steps_run - steps < evaluator.CHECKPOINT_TICKS
    assert frame.packet.payload == _fresh(values, at)
    evaluator.release()


class _Store:
    def __init__(self):
        self.values = canonical_section()

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


def test_the_studio_sets_the_budget_and_requests_frames_until_the_replay_lands(qt_app, no_gl_checks):
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    adapter = create_adapter("waveform_ribbon")
    adapter.recorded_clips = lambda: ()
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False))
        return surfaces[0]
    controller = StudioController(adapter, _Store(), _Presence(), factory)
    try:
        assert controller.open()
        surface = surfaces[0]
        evaluator = controller.evaluator
        assert evaluator._budget == StudioController.EVALUATION_BUDGET_S
        controller.select_fixture("peak")
        controller.seek(AT)
        for _ in range(400):
            surface.pump()
            if controller.last_frame is not None and not evaluator.converging:
                break
        evaluations = controller.evaluations
        evaluator.set_frame_budget(0.0)                 # one tick per frame from here (deterministic)
        height = controller.session.values["waveform_ribbon_height"]
        commits = controller.session.commit_count
        controller.bridge.commitValue("waveform_ribbon_height", 1, float(height[1]) * 0.5)
        assert controller.session.commit_count == commits + 1
        for _ in range(5000):
            surface.pump()
            if not evaluator.converging:
                break
        assert not evaluator.converging and controller.evaluations - evaluations > 20     # frames kept coming
        assert controller.last_frame.packet.payload == _fresh(controller.evaluation_values(),
                                                              controller.transport.time, evaluator._extent)
    finally:
        controller.close()
