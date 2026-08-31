"""Widget-free visualizer logical-step ownership bars (H).

These prove the authored per-tick logical step advances against the controller-
owned VisualizerLogicalTickState as its host - no QWidget/legacy presenter is
passed. During this transitional slice the widget still performs setup (its
fields delegate to the controller-owned state), but the *step* runs against the
state directly, which is the destination the Quick visualizer ownership edge
will drive.
"""

from __future__ import annotations

from types import SimpleNamespace

from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime


class _Engine:
    """Production-shaped fake engine: real energy/transient band snapshots so the
    authored Bubble dispatch and publication path runs unmodified."""

    def get_bubble_energy_bands(self):
        return SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    def get_energy_bands(self):
        return SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    def get_transient_energy_bands(self):
        return SimpleNamespace(
            bass_transient=0.0,
            mid_transient=0.0,
            high_transient=0.0,
            onset_detected=False,
            onset_type="",
            onset_strength=0.0,
        )

    def get_event_scheduler(self):
        return None

    def get_perf_diagnostics(self):
        return {}


_CANONICAL_BUBBLE_CONFIG = {
    "bubble_big_count": 8,
    "bubble_small_count": 25,
    "bubble_big_size_max": 0.038,
    "bubble_small_size_max": 0.018,
    "bubble_drift_amount": 0.5,
    "bubble_drift_speed": 0.5,
    "bubble_drift_direction": "random",
    "bubble_stream_direction": "up",
    "bubble_stream_constant_speed": 0.5,
    "bubble_surface_reach": 0.6,
    "bubble_bounce_big_pct": 70,
    "bubble_bounce_small_pct": 30,
    "bubble_trail_strength": 0.0,
}


def test_fresh_controller_configured_started_advanced_without_widget(
    monkeypatch,
) -> None:
    # Acceptance: a fresh visualizer destination owner is constructed, configured
    # from canonical settings, started and logically advanced WITHOUT constructing
    # SpotifyVisualizerWidget.
    from widgets.spotify_visualizer.config_applier import (
        apply_logical_vis_mode_kwargs,
    )
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0, bar_count=32, initial_mode="bubble"
    )
    state = controller.logical_tick_state

    # Construct: install the authored runtime defaults on the controller-owned
    # state (no widget).
    install_default_logical_tick_state(state, bar_count=32)
    # Configure: apply the authored logical (Bubble physics) config from canonical
    # settings through the single neutral authority.
    apply_logical_vis_mode_kwargs(state, _CANONICAL_BUBBLE_CONFIG)
    assert state._bubble_big_count == 8
    assert state._bubble_small_count == 25

    # Configure runtime identity + engine/source.
    controller.enabled = True
    controller.playing = True
    controller.engine = _Engine()
    assert controller.resolve_logical_mode_state("bubble", BubbleFrameRuntime) is not None
    controller.begin_render_activation(engine_generation=3, activation_id=4)
    state._mode_teardown_block_until_ready = False
    state._mode_transition_ready = True
    state._waiting_for_fresh_engine_frame = False

    monkeypatch.setattr(
        tick_pipeline, "consume_engine_bars", lambda owner, now: (True, True)
    )
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda owner, now: None)
    monkeypatch.setattr(
        tick_pipeline, "dispatch_devcurve_field", lambda owner, now: None
    )
    diagnostic_messages: list[str] = []
    monkeypatch.setattr(tick_pipeline, "is_viz_diagnostics_enabled", lambda: True)
    monkeypatch.setattr(
        tick_pipeline,
        "maybe_log_reactivity_boundary",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        tick_pipeline.logger,
        "debug",
        lambda message, *args: diagnostic_messages.append(message % args),
    )

    # Advance: the authored logical step runs against the controller-owned state
    # and publishes - no SpotifyVisualizerWidget was ever constructed.
    produced = 0
    for _ in range(6):
        frame = tick_pipeline.logical_tick(state)
        if frame is not None:
            produced += 1
            publication = controller.logical_mailbox.take()
            assert publication is not None
    assert produced >= 1
    bubble_geometry = next(
        message
        for message in diagnostic_messages
        if "stage=B6_B7" in message
    )
    assert "final_big_max_r=" in bubble_geometry
    assert "target_big_max_r=" in bubble_geometry
    assert "smooth_lag_max_r=" in bubble_geometry
    assert "frozen_big_max_r=" in bubble_geometry
    assert "track(token=" in bubble_geometry
    assert "rate_hz=" in bubble_geometry
    assert "mix=" in bubble_geometry
    assert "motion(event=" in bubble_geometry
    assert "stream_step=" in bubble_geometry
    assert "drift_step=" in bubble_geometry


def test_devcurve_diagnostics_do_not_cross_into_bubble_geometry(monkeypatch) -> None:
    from widgets.spotify_visualizer.devcurve_frame_runtime import (
        DevCurveFrameRuntime,
    )
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0,
        bar_count=32,
        initial_mode="devcurve",
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    controller.enabled = True
    controller.playing = True
    controller.engine = _Engine()
    controller.begin_render_activation(engine_generation=3, activation_id=4)
    monkeypatch.setattr(tick_pipeline, "is_viz_diagnostics_enabled", lambda: True)
    monkeypatch.setattr(
        tick_pipeline,
        "maybe_log_reactivity_boundary",
        lambda *_args, **_kwargs: None,
    )

    tick_pipeline.dispatch_devcurve_field(state, 10.0)

    runtime = controller.peek_logical_mode_state("devcurve")
    assert isinstance(runtime, DevCurveFrameRuntime)
    assert runtime.latest.curves
