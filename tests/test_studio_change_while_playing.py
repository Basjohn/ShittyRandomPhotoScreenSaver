"""A change while the Studio plays never freezes the preview (operator, 7 Nov: "Studio stalls for a bit whenever you
change any reactivity setting at all. Usually until the next loop").

An exact replay of a change starts at the start of the pass (or a checkpoint) while the transport plays on: under the
frame budget it chased a moving instant and the frame shown stayed frozen for seconds (Waveform Ribbon, the operator's
session; DevCurve through the loop's wrap), and the one-shot evaluators (Bubble, Sphere, Extruded Bubble) replayed it
in one GUI-thread evaluation. Now, while playing, a long replay restarts the pass with the change applied
(``ui/studio/exact_replay.PassRestart``) and the transport waits for a converging replay instead of running ahead.

Driven through the real ``StudioController`` and each mode's real adapter on an offscreen surface (nothing is shown),
on a fake transport clock at 60 Hz and a zero frame budget (one production tick per evaluation, so the counts are
machine-independent). Proven for every Studio-backed mode on a shipped loop clip (new inputs landing at 6 s into the
second pass: a re-analysed clip) and for the operator's own edit (Waveform Ribbon's Reaction Mode, committed while
playing): the preview is live again after no more than the clip's analysis lead-in plus half a second of
production steps, and plays on from there. On main the preview stays frozen past the bound (the replay chases the
moving instant) or one evaluation replays the whole pass so far.
"""
from __future__ import annotations

import pytest

from tools import studio_clip_loop_wrap as wrap

CLIP = "growing_pains"                 # the shortest of the shipped clips to analyse
AT = 6.0                               # seconds into the second pass
TICK_HZ = 90.0                         # the logical cadence the recorded inputs are stepped at


class _Store:
    def __init__(self):
        self.values = wrap.values()    # the canonical section: the recorded inputs were analysed under it

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


@pytest.fixture
def playing_studio(qt_app, no_gl_checks):
    """``open(mode)`` -> (controller, surface, clock): a real Studio of ``mode`` on an offscreen surface, its
    transport on a fake clock the test advances."""
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    opened = []

    def open_mode(mode):
        adapter = create_adapter(mode)
        adapter.recorded_clips = lambda: ()          # no worker: the test hands the clip's inputs over itself
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(960, 600), present_on_show=False))
            return surfaces[0]
        controller = StudioController(adapter, _Store(), _Presence(), factory)
        now = [0.0]
        controller.transport._clock = lambda: now[0]
        assert controller.open()
        opened.append(controller)
        return controller, surfaces[0], now
    yield open_mode
    for controller in opened:
        controller.close()


def _frame(surface, now, step):
    now[0] += step
    surface.pump()


def _play_to(controller, surface, now, at, *, cycles=1):
    controller.set_playing(True)
    for _ in range(4000):
        if controller.transport.cycles >= cycles and controller.transport.time >= at:
            return
        _frame(surface, now, 0.1)                     # the run-up at the transport's largest step
    raise AssertionError("the transport did not reach the instant")


def _until_live(controller, surface, now, limit):
    """Frames at 60 Hz until the preview is live again (no replay converging) and the production steps run meanwhile;
    the largest number one evaluation ran is returned too."""
    evaluator = controller.evaluator
    steps, worst = evaluator.steps_run, 0
    for frames in range(1, limit + 1):
        before = evaluator.steps_run
        _frame(surface, now, 1.0 / 60.0)
        worst = max(worst, evaluator.steps_run - before)
        if not getattr(evaluator, "converging", False):
            return frames, evaluator.steps_run - steps, worst
    return None, evaluator.steps_run - steps, worst


BACKLOG_ALLOWANCE_S = 0.5             # test-owned: history a prompt preview may replay beyond the lead-in


def _bound() -> int:
    """Production steps a change may cost while playing: the clip's analysis lead-in (``clip_loop.PREROLL_S``) and
    half a second of history (``BACKLOG_ALLOWANCE_S``), at the logical cadence, plus slack. A replay up to an
    instant 6 s into the pass needs several times that."""
    from ui.studio import clip_loop
    return int((clip_loop.PREROLL_S + BACKLOG_ALLOWANCE_S) * TICK_HZ) + 30


def _plays_on(controller, surface, now):
    """The transport moves again (a held transport waits one frame to re-establish its wall reference)."""
    times = []
    for _ in range(4):
        _frame(surface, now, 1.0 / 60.0)
        times.append(controller.transport.unrolled)
    return times[-1] > times[0]


def _other_reaction_mode(controller) -> str:
    """A Reaction Mode choice (its label) other than the current one."""
    prop = controller.session.schema.find("waveform_ribbon_reaction_mode")
    current = controller.session.values["waveform_ribbon_reaction_mode"]
    values = prop.choice_values or prop.choices
    return next(label for label, value in zip(prop.choices, values) if value != current)


FAMILY_MODE = {family: ("waveform_ribbon" if family == "waveform" else family) for family in wrap.FAMILIES}


@pytest.mark.parametrize("family", sorted(wrap.FAMILIES))
def test_new_inputs_landing_while_playing_never_freeze_the_preview(playing_studio, family):
    """A re-analysed clip landing deep into a pass (the controller's landing: ``add_recorded`` + ``select``): the
    preview is live again within the lead-in plus the backlog bound, not after the pass so far, and plays on."""
    controller, surface, now = playing_studio(FAMILY_MODE[family])
    inputs = wrap.recorded_inputs(family, CLIP)
    controller.evaluator.add_recorded(inputs)
    controller.select_fixture(inputs.fixture.id)
    assert controller.evaluator.fixture.loop or getattr(inputs, "period", 0.0) > 0.0
    _play_to(controller, surface, now, AT)
    budget = getattr(controller.evaluator, "set_frame_budget", None)
    if callable(budget):
        budget(0.0)                                   # one production tick per evaluation from here
    controller.evaluator.add_recorded(inputs)        # the landing (``StudioController._load_clip`` refresh)
    controller.evaluator.select(inputs.fixture.id)
    controller._invalidate()
    bound = _bound()
    frames, steps, worst = _until_live(controller, surface, now, limit=bound + 20)
    assert frames is not None, f"{family}: the preview was still frozen after {bound + 20} frames"
    assert steps <= bound, f"{family}: {steps} production steps before the preview was live (bound {bound})"
    assert worst <= bound
    assert _plays_on(controller, surface, now)


def test_the_operators_reaction_mode_edit_while_playing_never_freezes_waveform(playing_studio):
    """The operator's session: Waveform Ribbon playing, Reaction Mode committed 6 s into the fixture."""
    controller, surface, now = playing_studio("waveform_ribbon")
    controller.select_fixture("peak")
    _play_to(controller, surface, now, AT, cycles=0)
    controller.evaluator.set_frame_budget(0.0)
    other = _other_reaction_mode(controller)
    commits = controller.session.commit_count
    controller.bridge.commitValue("waveform_ribbon_reaction_mode", 0, other)
    assert controller.session.commit_count == commits + 1
    bound = _bound()
    frames, steps, _worst = _until_live(controller, surface, now, limit=bound + 20)
    assert frames is not None, f"the preview was still frozen after {bound + 20} frames"
    assert steps <= bound
    assert _plays_on(controller, surface, now)


def test_a_change_while_paused_still_replays_to_the_instant_shown(playing_studio):
    """Paused, nothing moves: the change replays exactly to the instant on screen (no restart)."""
    controller, surface, now = playing_studio("waveform_ribbon")
    controller.select_fixture("peak")
    _play_to(controller, surface, now, AT, cycles=0)
    controller.set_playing(False)
    at = controller.transport.time
    other = _other_reaction_mode(controller)
    controller.bridge.commitValue("waveform_ribbon_reaction_mode", 0, other)
    for _ in range(400):
        _frame(surface, now, 1.0 / 60.0)
        if not controller.evaluator.converging:
            break
    assert not controller.evaluator.converging and controller.transport.time == at


def test_a_converging_change_shows_that_it_is_being_applied(playing_studio):
    """While the replay of a change converges for more than a moment, the preview says so ("Updating…"), and the
    notice goes when the preview is live."""
    controller, surface, now = playing_studio("waveform_ribbon")
    controller.select_fixture("peak")
    controller.set_playing(False)
    controller.seek(AT)
    for _ in range(400):
        surface.pump()
        if not controller.evaluator.converging:
            break
    controller.evaluator.set_frame_budget(0.0)
    other = _other_reaction_mode(controller)
    controller.bridge.commitValue("waveform_ribbon_reaction_mode", 0, other)
    seen = set()
    for _ in range(2000):
        surface.pump()
        seen.add(getattr(controller.bridge, "previewBusy", ""))
        if not controller.evaluator.converging:
            break
    surface.pump()
    assert "Updating…" in seen and getattr(controller.bridge, "previewBusy", "") == "", seen


def test_a_replay_after_an_edit_leaves_its_log_line(playing_studio, caplog):
    """The sidecar log names the replay an edit caused: its trigger, its duration and whether the pass restarted
    (operator, 7 Nov: the stall was invisible in ``logs/screensaver_studio.log``)."""
    import logging
    controller, surface, now = playing_studio("waveform_ribbon")
    controller.select_fixture("peak")
    _play_to(controller, surface, now, AT, cycles=0)
    with caplog.at_level(logging.INFO):
        controller.bridge.commitValue("waveform_ribbon_reaction_mode", 0, _other_reaction_mode(controller))
        _until_live(controller, surface, now, limit=_bound() + 20)
    lines = [r.getMessage() for r in caplog.records if "replay after commit" in r.getMessage()]
    assert len(lines) == 1 and "Reaction Mode" in lines[0] and "restarted the pass" in lines[0], lines
    assert " ms over " in lines[0]
