"""Background work in the shared Studio controller (any mode): clip analyses and evaluator analyses run while the
user keeps working, and their results never take a choice away from the user.

A test-only flat mode (``test_waveform_studio_second_mode``'s toy) with recorded clips whose analysis finishes when
the test says so. Nothing shows a window.
"""
from __future__ import annotations

import pytest

from ui.studio.adapter import RECORDED, StudioFixture

from tests.test_waveform_studio_second_mode import Presence, ToyAdapter, ToyEvaluator, ToyRenderer, ToyStore

CLIPS = (StudioFixture("clip:first", "First", RECORDED, 5.0, "first.srclip"),
         StudioFixture("clip:second", "Second", RECORDED, 7.0, "second.srclip"))


class ClipEvaluator(ToyEvaluator):
    def add_recorded(self, inputs):
        if inputs.id not in {f.id for f in self._fixtures}:
            self._fixtures = self._fixtures + (inputs,)


class Job:
    def __init__(self, clip, finished):
        self.clip, self.finished, self.cancelled = clip, finished, False

    def cancel(self):
        self.cancelled = True


class ClipAdapter(ToyAdapter):
    """The toy mode with recorded clips analysed in the background (``land`` finishes one)."""

    def __init__(self):
        self.jobs: dict[str, Job] = {}

    def recorded_clips(self):
        return CLIPS

    def create_evaluator(self):
        return ClipEvaluator()

    def start_clip_load(self, clip, values, finished):
        self.jobs[clip.id] = Job(clip, finished)
        return self.jobs[clip.id]

    def land(self, clip_id: str, error: str = "") -> None:
        job = self.jobs.pop(clip_id)
        job.finished(None if error else job.clip, error)


@pytest.fixture
def clip_studio(qt_app):
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    ToyRenderer.drawn, ToyRenderer.released = [], 0
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(900, 600), present_on_show=False))
        return surfaces[-1]
    adapter = ClipAdapter()
    controller = StudioController(adapter, ToyStore(), Presence(), factory)
    assert controller.open()
    surfaces[0].pump(2)
    yield controller, adapter
    if StudioController.active() is controller:
        controller.close()


def test_the_default_clip_selects_itself_when_the_user_chose_nothing(clip_studio):
    controller, adapter = clip_studio
    assert set(adapter.jobs) == {"clip:first"}               # the default recorded clip, analysing
    adapter.land("clip:first")
    assert controller.bridge.fixtureId == "clip:first"


def test_a_late_default_clip_never_overrides_the_users_choice(clip_studio):
    """The default clip is still analysing when the user picks another clip; the default lands first, then the
    user's clip: the user's clip is selected throughout, and the default only becomes available."""
    controller, adapter = clip_studio
    controller.bridge.selectFixture("clip:second")
    assert set(adapter.jobs) == {"clip:first", "clip:second"}
    adapter.land("clip:first")
    assert controller.bridge.fixtureId != "clip:first"
    assert "clip:first" in {f.id for f in controller.evaluator.fixtures()}
    adapter.land("clip:second")
    assert controller.bridge.fixtureId == "clip:second"


def test_a_late_clip_never_overrides_a_later_ready_choice(clip_studio):
    """The user picks a clip, then (before it lands) a ready fixture: neither landing load moves the selection."""
    controller, adapter = clip_studio
    controller.bridge.selectFixture("clip:second")
    controller.bridge.selectFixture("pulse")
    adapter.land("clip:second")
    adapter.land("clip:first")
    assert controller.bridge.fixtureId == "pulse"


def test_the_selection_check_detects_the_old_override_negative_control(clip_studio, monkeypatch):
    """Negative control: a controller that does not record the user's request (the original defect: a user choice
    only cleared the default) lets the default landing afterwards take the selection."""
    controller, adapter = clip_studio
    original = type(controller).select_fixture

    def forgetful(self, fixture_id, *, user=True):
        wanted = self._wanted_source
        original(self, fixture_id, user=user)
        if user:
            self._wanted_source = wanted
    monkeypatch.setattr(type(controller), "select_fixture", forgetful)
    controller.bridge.selectFixture("clip:second")
    adapter.land("clip:first")
    assert controller.bridge.fixtureId == "clip:first"


def test_the_automatic_source_notice_goes_when_the_user_picks_another_source(clip_studio):
    """The notice naming the automatically chosen clip is withdrawn as soon as the user picks another source (it would
    name the wrong one), whether that source is ready or still analysing; picking it again keeps no stale notice."""
    controller, adapter = clip_studio
    bridge = controller.bridge
    adapter.land("clip:first")
    first = next(c for c in CLIPS if c.id == "clip:first")
    assert first.label in bridge.message                         # the default announced itself
    bridge.selectFixture("pulse")
    assert bridge.message == "" and bridge.fixtureId == "pulse"
    bridge.selectFixture("clip:second")                          # analysing: still no stale notice
    assert bridge.message == ""
    adapter.land("clip:second")
    assert bridge.fixtureId == "clip:second" and bridge.message == ""


def test_picking_a_source_keeps_any_other_notice(clip_studio):
    """Only the automatic-source notice is withdrawn: a clip failure's notice (with its Retry) stays when the user
    picks another source."""
    controller, adapter = clip_studio
    bridge = controller.bridge
    adapter.land("clip:first", error="decoder exploded")
    bridge.selectFixture("pulse")
    assert "decoder exploded" in bridge.message and bridge.messageAction == "Retry"


def test_the_stale_notice_check_detects_the_old_behaviour_negative_control(clip_studio):
    """Negative control: a controller that does not remember which notice announced the automatic source (the
    original behaviour) leaves 'Preview source: First' up after the user picked another source."""
    controller, adapter = clip_studio
    bridge = controller.bridge
    adapter.land("clip:first")
    controller._source_notice = ""
    bridge.selectFixture("pulse")
    assert "First" in bridge.message and bridge.fixtureId == "pulse"


# ------------------------------------------------------------------------------- failures are surfaced
def test_a_failed_clip_analysis_is_shown_with_a_retry_that_reanalyses(clip_studio):
    controller, adapter = clip_studio
    adapter.land("clip:first", error="decoder exploded")
    bridge = controller.bridge
    assert "decoder exploded" in bridge.message and bridge.messageAction == "Retry"
    assert controller.clip_status("clip:first") == "error"
    bridge.runMessageAction()
    assert bridge.message == "" and set(adapter.jobs) == {"clip:first"}         # analysing again
    adapter.land("clip:first")
    assert bridge.fixtureId == "clip:first" and controller.clip_status("clip:first") == "available"


class FailingEvaluator(ClipEvaluator):
    """A background-analysing evaluator (the Spectrum shape): the analysis the values need failed until retried."""

    def __init__(self):
        super().__init__()
        self.failure = "worker crashed"
        self.retries = 0

    @property
    def analysis_failure(self):
        return self.failure

    def retry_analysis(self):
        self.retries += 1
        self.failure = ""


def test_a_failed_evaluator_analysis_is_shown_once_with_retry(qt_app):
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    surfaces = []
    adapter = ClipAdapter()
    adapter.create_evaluator = FailingEvaluator
    controller = StudioController(adapter, ToyStore(), Presence(), lambda c: surfaces.append(
        OffscreenStudioSurface(c, size=(900, 600), present_on_show=False)) or surfaces[-1])
    assert controller.open()
    surfaces[0].pump(2)
    bridge = controller.bridge
    assert "worker crashed" in bridge.message and bridge.messageAction == "Retry"
    bridge.dismissMessage()
    controller.seek(1.0)
    surfaces[0].pump(2)
    assert bridge.message == ""                                  # one notice per failure, not one per frame
    bridge.notify("Analysis failed: worker crashed", "Retry", controller.retry_analysis)
    bridge.runMessageAction()
    assert controller.evaluator.retries == 1 and bridge.messageAction == ""
    controller.close()
