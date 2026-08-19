"""Gates A-F for the pull-based visualizer presentation seam.

`Current_Plan.md` section 5-6. The old shape marshalled one GUI callback per
logical publication (`_publish_logical_state -> request_logical_present`), so the
~90 Hz logical producer continuously enqueued GUI work that competed with the
165 Hz display's transition delivery. The replacement: steady publications only
advance a thread-safe mailbox present-revision, and the physical display
presentation opportunity samples it and applies the freshest state during paint.

These bars are deterministic ownership/scheduling tests, not installed FPS
benchmarks.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QWidget

from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.logical_runtime import (
    LatestStateMailbox,
    VisualizerLogicalRuntime,
)

_MODES = {
    "bubble": VisualizerMode.BUBBLE,
    "spectrum": VisualizerMode.SPECTRUM,
    "sine_wave": VisualizerMode.SINE_WAVE,
    "oscilloscope": VisualizerMode.OSCILLOSCOPE,
    "devcurve": VisualizerMode.DEVCURVE,
}


def _set_mode(widget, name: str) -> None:
    widget._vis_mode = _MODES[name]


class _RecordingManager:
    """Records UI marshals; runs them inline so single-pending can re-arm."""

    def __init__(self, *, run_inline: bool):
        self.calls: list = []
        self._run_inline = run_inline

    def run_on_ui_thread(self, func, *args, **kwargs):
        self.calls.append((func, args))
        if self._run_inline:
            func(*args, **kwargs)


@pytest.fixture
def widget(qt_app, qtbot):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    w = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(w)
    w._enabled = True
    w._engine = None
    w._waiting_for_fresh_engine_frame = False
    w._waiting_for_fresh_frame = False
    w._has_pushed_first_frame = True  # past the first-frame edge
    w._logical_runtime = object()     # a dedicated runtime is active
    yield w
    w._logical_runtime = None
    w.cleanup()


class TestGateA_SteadyPublicationDoesNotEnqueueGuiWork:
    def test_steady_publications_post_no_gui_callback_when_pull_is_active(
        self, widget, monkeypatch
    ):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=True)
        widget._pull_delivery_active = True
        _set_mode(widget, "bubble")  # animated: present-revision advances

        for i in range(30):
            tick_pipeline._publish_logical_state(
                widget, time.time() + i * 0.011, changed=True, mode_reveal_ready=False
            )

        assert widget._thread_manager.calls == [], (
            "a steady logical publication marshalled a GUI callback while the "
            "compositor pull was active"
        )
        # State still advanced at authored cadence, and it is visually dirty.
        assert widget._logical_mailbox.revision >= 30
        assert widget._logical_mailbox.present_revision >= 30

    def test_negative_control_old_shape_posts_one_callback_per_publication(
        self, widget, monkeypatch
    ):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=True)
        widget._pull_delivery_active = False  # no pull registered: legacy marshal
        _set_mode(widget, "bubble")

        for i in range(30):
            tick_pipeline._publish_logical_state(
                widget, time.time() + i * 0.011, changed=True, mode_reveal_ready=False
            )

        assert len(widget._thread_manager.calls) == 30, (
            "the legacy per-publication marshal did not fire once per publication, "
            "so the callback-count bound proves nothing"
        )

    def test_no_replacement_gui_timer_is_created(self, widget):
        # The runtime owns cadence; no GUI QTimer paces publication.
        assert getattr(widget, "_bars_timer", None) is None

    def test_a_settled_idle_scene_stops_advancing_present_revision(
        self, widget, monkeypatch
    ):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=True)
        widget._pull_delivery_active = True
        _set_mode(widget, "spectrum")
        widget._spotify_playing = False
        widget._rainbow_enabled = False
        widget._mode_transition_phase = 0
        widget._present_force_until_ts = 0.0  # past any reveal force window

        base = time.time() + 100.0  # well past the force window
        start_present = widget._logical_mailbox.present_revision
        for i in range(20):
            tick_pipeline._publish_logical_state(
                widget, base + i * 0.011, changed=False, mode_reveal_ready=False
            )

        # Idle Spectrum: state slot still refreshes, but nothing visually changed,
        # so the compositor's freshness signal does not advance -> paints suppress.
        assert widget._logical_mailbox.revision >= 20
        assert widget._logical_mailbox.present_revision == start_present
        assert widget._thread_manager.calls == []


class TestGateB_LatestStateSampling:
    def test_a_slow_consumer_sees_only_the_newest_revision(self):
        mailbox = LatestStateMailbox()
        for r in range(1, 6):
            mailbox.publish({"r": r}, generation=5, activation_id=1, dirty=True)

        newest = mailbox.take_for_generation(5)
        assert newest is not None and newest.state["r"] == 5, "an intermediate revision replayed"
        assert mailbox.superseded_count == 4, "superseded states were queued, not dropped"
        assert mailbox.take() is None, "a backlog remained after taking the newest"

    def test_present_revision_counts_only_dirty_publications(self):
        mailbox = LatestStateMailbox()
        mailbox.publish({"n": 1}, generation=0, dirty=True)
        mailbox.publish({"n": 2}, generation=0, dirty=False)
        mailbox.publish({"n": 3}, generation=0, dirty=True)
        assert mailbox.revision == 3
        assert mailbox.present_revision == 2


class TestGateC_ModesRetainSemantics:
    @pytest.mark.parametrize("mode", ["bubble", "sine_wave", "oscilloscope", "devcurve"])
    def test_animated_modes_always_mark_a_present(self, widget, monkeypatch, mode):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=True)
        widget._pull_delivery_active = True
        _set_mode(widget, mode)
        widget._present_force_until_ts = 0.0

        base = time.time() + 100.0
        before = widget._logical_mailbox.present_revision
        tick_pipeline._publish_logical_state(widget, base, changed=False, mode_reveal_ready=False)
        assert widget._logical_mailbox.present_revision == before + 1, (
            f"{mode} did not advance the present-revision though it animates every tick"
        )

    def test_paused_spectrum_is_the_only_suppressible_mode(self, widget, monkeypatch):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=True)
        widget._pull_delivery_active = True
        _set_mode(widget, "spectrum")
        widget._spotify_playing = False
        widget._present_force_until_ts = 0.0

        base = time.time() + 100.0
        before = widget._logical_mailbox.present_revision
        tick_pipeline._publish_logical_state(widget, base, changed=False, mode_reveal_ready=False)
        assert widget._logical_mailbox.present_revision == before, (
            "settled paused Spectrum still advanced the present-revision"
        )


class TestGateD_TwoDisplayIndependence:
    def test_visualizer_producer_imposes_no_callbacks_on_a_second_display(
        self, widget, monkeypatch
    ):
        # The 60 Hz visualizer display's logical producer must not enqueue GUI
        # callbacks that would compete on the shared GUI thread with a second
        # (165 Hz) display's consumer. With the pull active, publishing many
        # revisions posts zero callbacks.
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=True)
        widget._pull_delivery_active = True
        _set_mode(widget, "bubble")

        for i in range(90):  # ~1s of 90 Hz logical steps
            tick_pipeline._publish_logical_state(
                widget, time.time() + i * 0.011, changed=True, mode_reveal_ready=False
            )

        assert widget._thread_manager.calls == [], (
            "the visualizer producer created a GUI callback backlog that would "
            "starve the other display"
        )

    def test_present_revision_is_a_thread_safe_plain_int(self, widget):
        # The compute-thread scheduler must be able to sample freshness without a
        # QWidget/GUI call.
        rev = tick_pipeline.logical_present_revision(widget)
        assert isinstance(rev, int)


class TestGateE_EdgeHandoffsStillWork:
    def test_a_reveal_frame_marshals_a_gui_callback(self, widget, monkeypatch):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=False)
        widget._pull_delivery_active = True
        _set_mode(widget, "spectrum")

        tick_pipeline._publish_logical_state(
            widget, time.time(), changed=False, mode_reveal_ready=True
        )
        assert len(widget._thread_manager.calls) == 1, (
            "a decided reveal did not marshal its bounded GUI callback"
        )

    def test_a_first_frame_marshals_a_gui_callback(self, widget, monkeypatch):
        monkeypatch.setattr(tick_pipeline, "present_tick", lambda w, **k: None)
        widget._thread_manager = _RecordingManager(run_inline=False)
        widget._pull_delivery_active = True
        widget._has_pushed_first_frame = False  # first frame not yet delivered
        _set_mode(widget, "spectrum")

        tick_pipeline._publish_logical_state(
            widget, time.time(), changed=False, mode_reveal_ready=False
        )
        assert len(widget._thread_manager.calls) == 1

    def test_the_pull_never_executes_a_reveal(self, widget, monkeypatch):
        # apply_latest_logical_present (the paint pull) must leave a reveal frame
        # for the edge callback rather than mutating layout/fade during paint.
        reveals: list = []
        monkeypatch.setattr(
            tick_pipeline.mode_transition, "execute_mode_reveal",
            lambda w, now: reveals.append(now),
        )
        widget._logical_mailbox.publish(
            {"now_ts": 1.0, "present_frame": True, "changed": False,
             "mode_reveal_ready": True},
            generation=tick_pipeline.coerce_identity(widget._runtime_generation),
            activation_id=1,
        )

        tick_pipeline.apply_latest_logical_present(widget)

        assert reveals == [], "the paint pull executed a reveal"
        # The reveal frame is left in the mailbox for the edge callback.
        assert widget._logical_mailbox.peek() is not None

    def test_stop_tick_source_detaches_the_pull_from_a_compositor(self, widget):
        cleared: list = []

        class _Comp:
            def set_visualizer_logical_source(self, s):
                pass

            def clear_visualizer_logical_source(self, s):
                cleared.append(s)

        widget._registered_pull_compositor = _Comp()
        widget._pull_delivery_active = True
        from widgets.spotify_visualizer.tick_helpers import stop_tick_source

        stop_tick_source(widget)

        assert cleared == [widget]
        assert widget._pull_delivery_active is False
        assert widget._registered_pull_compositor is None


class TestGateF_SlowTickDiagnosticsCannotThrow:
    def test_the_slow_tick_path_does_not_throw(self, widget, monkeypatch):
        # Force _tick_elapsed > 50 ms with an advancing clock and PERF enabled.
        monkeypatch.setattr(tick_pipeline, "is_perf_metrics_enabled", lambda: True)

        clock = {"t": 1000.0}

        def _advancing():
            clock["t"] += 0.05  # every time.time() call jumps 50 ms
            return clock["t"]

        monkeypatch.setattr(tick_pipeline.time, "time", _advancing)

        # Must not raise NameError (the stale is_transition_active reference) or
        # any other exception, and must still publish.
        payload = tick_pipeline.logical_tick(widget)
        assert payload is not None
        assert widget._logical_mailbox.revision >= 1
