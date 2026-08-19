"""A paused mode switch must not be owned by the fallback timeout.

Current_Plan section 7.3: "each target mode becomes visible without a
0.35/1.5-second timeout being normal control flow. A timeout may remain
fail-safe. It must not be the normal successful reveal owner."

`check_mode_teardown_ready()` waited for the engine to deliver a frame at or
beyond the target generation. While paused there is no capture and no such frame
is coming, so for every paused mode switch the 0.35s fallback was the normal
path to readiness - a visible stall on exactly the edge the operator reports.

An idle-capable mode's first visible scene is idle-owned, so readiness is the
mode being idle-ready. The timeout stays as the fail-safe it was written to be.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer import mode_transition


class _Engine:
    """An engine that has produced nothing for the target generation."""

    def __init__(self, latest: int = -1, latest_waveform: int = -1):
        self._latest = latest
        self._latest_waveform = latest_waveform

    def get_latest_generation_with_frame(self):
        return self._latest

    def get_latest_generation_with_waveform(self):
        return self._latest_waveform


def _widget(*, mode: str, playing: bool, waited_s: float = 0.0):
    now = time.time()
    widget = SimpleNamespace(
        _mode_teardown_state="waiting_bars",
        _mode_teardown_wait_started_ts=now - waited_s,
        _mode_transition_ts=now - waited_s,
        _mode_teardown_target_generation=7,
        _mode_transition_ready=False,
        _vis_mode_str=mode,
        _spotify_playing=playing,
        _should_capture_audio_now=lambda: playing,
    )
    return widget, now


@pytest.fixture(autouse=True)
def _capture_fade(monkeypatch):
    started: list[float] = []
    monkeypatch.setattr(
        mode_transition,
        "begin_mode_fade_in",
        lambda widget, now_ts: started.append(now_ts),
    )
    return started


@pytest.fixture
def warnings(monkeypatch):
    recorded: list[str] = []

    def _warn(msg, *args, **kwargs):
        try:
            recorded.append(msg % args if args else str(msg))
        except Exception:
            recorded.append(str(msg))

    monkeypatch.setattr(mode_transition.logger, "warning", _warn)
    return recorded


class TestPausedSwitchIsReadyImmediately:
    @pytest.mark.parametrize(
        "mode", ["bubble", "sine_wave", "oscilloscope", "devcurve", "spectrum"]
    )
    def test_every_idle_capable_mode_is_ready_without_waiting(
        self, mode, _capture_fade, warnings
    ):
        widget, now = _widget(mode=mode, playing=False)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), now)

        assert widget._mode_teardown_state == "ready", (
            f"a paused switch into {mode} still waits for an engine frame"
        )
        assert _capture_fade, "the target mode never began its fade-in"
        assert warnings == [], "readiness came from the fallback timeout"

    def test_readiness_does_not_depend_on_elapsed_time(self, _capture_fade):
        """Zero elapsed time must already be ready, not merely past a deadline."""
        widget, now = _widget(mode="bubble", playing=False, waited_s=0.0)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), now)

        assert widget._mode_teardown_state == "ready"

    def test_an_unknown_mode_still_waits(self, _capture_fade, warnings):
        widget, now = _widget(mode="not_a_mode", playing=False)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), now)

        assert widget._mode_teardown_state == "waiting_bars"
        assert _capture_fade == []


class TestPlayingSwitchStillProvesItsSource:
    def test_a_playing_switch_waits_for_the_target_generation(
        self, _capture_fade, warnings
    ):
        widget, now = _widget(mode="bubble", playing=True)

        mode_transition.check_mode_teardown_ready(widget, _Engine(latest=3), now)

        assert widget._mode_teardown_state == "waiting_bars", (
            "a playing switch revealed before its source caught up"
        )
        assert _capture_fade == []

    def test_a_playing_switch_is_ready_once_the_frame_arrives(self, _capture_fade):
        widget, now = _widget(mode="bubble", playing=True)

        mode_transition.check_mode_teardown_ready(
            widget, _Engine(latest=7, latest_waveform=7), now
        )

        assert widget._mode_teardown_state == "ready"

    def test_waveform_modes_still_wait_for_a_waveform(self, _capture_fade):
        widget, now = _widget(mode="oscilloscope", playing=True)

        mode_transition.check_mode_teardown_ready(
            widget, _Engine(latest=7, latest_waveform=2), now
        )

        assert widget._mode_teardown_state == "waiting_bars"


class TestTheTimeoutRemainsAFailSafe:
    def test_a_stalled_playing_switch_still_times_out(self, _capture_fade, warnings):
        widget, now = _widget(mode="bubble", playing=True, waited_s=2.0)

        mode_transition.check_mode_teardown_ready(widget, _Engine(latest=3), now)

        assert widget._mode_teardown_state == "ready"
        assert warnings, "the fail-safe timeout was removed"

    def test_a_stalled_unknown_mode_still_times_out(self, _capture_fade, warnings):
        widget, now = _widget(mode="not_a_mode", playing=False, waited_s=1.0)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), now)

        assert widget._mode_teardown_state == "ready"
        assert warnings
