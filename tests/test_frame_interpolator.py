import pytest

from core.animation.frame_interpolator import FrameState
from core.animation.types import EasingCurve


def test_frame_state_wall_clock_progress_outruns_stale_sample_stream(monkeypatch):
    import core.animation.frame_interpolator as frame_interpolator

    now = [100.0]
    monkeypatch.setattr(frame_interpolator.time, "time", lambda: now[0])

    state = FrameState(duration=1.0)
    state.begin_timeline(start_time=100.0, easing=EasingCurve.LINEAR)

    now[0] = 100.05
    state.push(0.05)

    now[0] = 100.70

    assert state.get_interpolated_progress() == pytest.approx(0.70)


def test_frame_state_delayed_timeline_does_not_advance_before_delay(monkeypatch):
    import core.animation.frame_interpolator as frame_interpolator

    now = [200.0]
    monkeypatch.setattr(frame_interpolator.time, "time", lambda: now[0])

    state = FrameState(duration=1.0)
    state.begin_timeline(start_time=200.5, easing=EasingCurve.LINEAR)

    now[0] = 200.25
    assert state.get_interpolated_progress() == 0.0

    now[0] = 200.75
    assert state.get_interpolated_progress() == pytest.approx(0.25)


def test_frame_state_reset_clears_wall_clock_authority(monkeypatch):
    import core.animation.frame_interpolator as frame_interpolator

    now = [300.0]
    monkeypatch.setattr(frame_interpolator.time, "time", lambda: now[0])

    state = FrameState(duration=1.0)
    state.begin_timeline(start_time=300.0, easing=EasingCurve.LINEAR)

    now[0] = 300.5
    assert state.get_interpolated_progress() == 0.5

    state.reset()
    assert state.get_interpolated_progress() == 0.0
