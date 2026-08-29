"""Widget-free visualizer logical-step ownership bars (H).

These prove the authored per-tick logical step advances against the controller-
owned VisualizerLogicalTickState as its host - no QWidget/legacy presenter is
passed. During this transitional slice the widget still performs setup (its
fields delegate to the controller-owned state), but the *step* runs against the
state directly, which is the destination the Quick visualizer ownership edge
will drive.
"""

from __future__ import annotations

import pytest

from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime


class _Bars:
    def get_bars(self):
        return [0.2, 0.4, 0.6, 0.8], [0.0] * 4, []

    def get_perf_diagnostics(self):
        return {}


class _Engine:
    def __init__(self):
        self._bars = _Bars()

    def get_visualization_data(self):
        return self._bars.get_bars()

    def get_perf_diagnostics(self):
        return {}


@pytest.mark.qt
def test_logical_step_advances_against_controller_state_without_widget(
    qt_app, monkeypatch
) -> None:
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    # The widget performs setup only; its fields delegate to the controller-owned
    # logical state. We then drive the step against that state, not the widget.
    widget = SpotifyVisualizerWidget(parent=None, bar_count=4, initial_mode="bubble")
    try:
        widget._runtime_generation = 0
        widget._enabled = True
        widget._spotify_playing = True
        widget._engine = _Engine()
        controller = widget.runtime_controller
        assert (
            controller.resolve_logical_mode_state("bubble", BubbleFrameRuntime)
            is not None
        )
        controller.begin_render_activation(engine_generation=5, activation_id=7)
        widget._mode_teardown_block_until_ready = False
        widget._mode_transition_ready = True
        widget._waiting_for_fresh_engine_frame = False

        # Engine consumption / heartbeat / perf / devcurve are exercised by the
        # golden suites; here we isolate that the authored bubble logical dispatch
        # and publication advance when the *host is the controller-owned state*.
        monkeypatch.setattr(
            tick_pipeline, "consume_engine_bars", lambda owner, now: (True, True)
        )
        monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda owner, now: None)
        monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda owner, now: None)
        monkeypatch.setattr(
            tick_pipeline, "dispatch_devcurve_field", lambda owner, now: None
        )

        state = controller.logical_tick_state
        # The host is the controller-owned state; no widget crosses the seam.
        assert state.runtime_controller is controller

        produced = 0
        for _ in range(6):
            frame = tick_pipeline.logical_tick(state)
            if frame is not None:
                produced += 1
                publication = controller.logical_mailbox.take()
                assert publication is not None
                assert (
                    publication.state.logical_timestamp == frame.logical_timestamp
                )

        # The authored step advanced and published frames driven purely by the
        # controller-owned state.
        assert produced >= 1
    finally:
        widget.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_state_host_and_widget_host_are_interchangeable(qt_app) -> None:
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    widget = SpotifyVisualizerWidget(parent=None, bar_count=4, initial_mode="bubble")
    try:
        widget._runtime_generation = 0
        widget._enabled = True
        widget._spotify_playing = True
        widget._engine = _Engine()
        controller = widget.runtime_controller
        controller.resolve_logical_mode_state("bubble", BubbleFrameRuntime)
        controller.begin_render_activation(engine_generation=1, activation_id=1)
        widget._mode_teardown_block_until_ready = False
        widget._mode_transition_ready = True
        widget._waiting_for_fresh_engine_frame = False

        # A field written through the widget is visible on the state host and
        # vice versa - they are one and the same logical host.
        widget._heartbeat_intensity = 0.42
        assert controller.logical_tick_state._heartbeat_intensity == pytest.approx(0.42)
        controller.logical_tick_state._smoothing = 0.25
        assert widget._smoothing == pytest.approx(0.25)
    finally:
        widget.deleteLater()
        qt_app.processEvents()
