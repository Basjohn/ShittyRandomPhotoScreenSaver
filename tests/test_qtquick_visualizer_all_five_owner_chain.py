"""Owner-shaped all-five destination-chain proof (H Finding F).

From resolved canonical settings, prove every visualizer mode can:
  configure (logical + presentation, via the neutral authorities)
  -> bind the render source
  -> advance the authored logical step against controller-owned state
  -> the GUI/Quick synchronization owner composes + publishes one complete
     VisualizerRenderSnapshot into the controller's existing bridge
  -> the retained Quick consumer takes it for the correct
     runtime/engine-generation/activation/mode identity
  -> stale identity is rejected
  -> retirement is a hard join barrier
all WITHOUT constructing SpotifyVisualizerWidget.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)

_ENGINE_GEN = 5
_ACT_ID = 7


class _Engine:
    """Production-shaped fake engine covering every mode's capture reads."""

    def get_activation_id(self):
        return _ACT_ID

    def get_generation_id(self):
        return _ENGINE_GEN

    def get_latest_generation_with_frame(self):
        return _ENGINE_GEN

    def get_latest_generation_with_waveform(self):
        return _ENGINE_GEN

    def get_latest_authoritative_frame(self):
        return (0.0, _ENGINE_GEN, _ACT_ID)

    def get_waveform(self):
        return (0.0, 0.1, -0.1, 0.05)

    def get_waveform_count(self):
        return 4

    def get_energy_bands(self):
        return SimpleNamespace(bass=0.2, mid=0.1, high=0.05, overall=0.15)

    def get_bubble_energy_bands(self):
        return SimpleNamespace(bass=0.2, mid=0.1, high=0.05, overall=0.15)

    def get_transient_energy_bands(self):
        return SimpleNamespace(
            bass_transient=0.0, mid_transient=0.0, high_transient=0.0,
            onset_detected=False, onset_type="", onset_strength=0.0,
        )

    def get_event_scheduler(self):
        return None

    def get_floor_snapshot(self):
        return None

    def get_perf_diagnostics(self):
        return {}


# Resolved canonical settings per mode: authored-logical + presentation styling.
_MODE_CASES = {
    "spectrum": (
        {"spectrum_visual_smoothing": 0.3, "spectrum_ghost_decay": 0.5},
        {"spectrum_glow_color": [0, 120, 255, 255], "bar_fill_color": [10, 20, 30, 255]},
    ),
    "oscilloscope": (
        {"osc_speed": 0.5, "osc_line_amplitude": 4.0, "osc_ghost_decay": 0.6},
        {"osc_glow_color": [200, 50, 50, 255], "osc_line_color": [1, 2, 3, 255]},
    ),
    "sine_wave": (
        {"sine_speed": 0.6, "sine_width_reaction": 0.4, "sine_wave_travel": 1},
        {"sine_glow_color": [50, 220, 120, 255], "sine_line_color": [9, 8, 7, 255]},
    ),
    "bubble": (
        {"bubble_big_count": 10, "bubble_stream_direction": "up"},
        {"bubble_gradient_light": [210, 170, 120, 255], "bubble_outline_color": [255, 255, 255, 230]},
    ),
    "devcurve": (
        {"devcurve_base_level": 0.62, "devcurve_motion_power": 1.3},
        {},
    ),
}


def _make_runtime(qt_app, generation: int):
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=generation,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    return runtime, factory


def _prime_state(state) -> None:
    state._mode_teardown_block_until_ready = False
    state._mode_transition_ready = True
    state._waiting_for_fresh_engine_frame = False
    state._display_bars_source_generation = _ENGINE_GEN
    state._display_bars_source_activation = _ACT_ID


def _quiet(monkeypatch) -> None:
    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda o, n: (True, True))
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda o, n: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda o, n: None)


@pytest.mark.qt
@pytest.mark.parametrize("mode", list(_MODE_CASES.keys()))
def test_owner_publishes_complete_snapshot_for_every_mode(qt_app, monkeypatch, mode) -> None:
    _quiet(monkeypatch)
    logical_kwargs, presentation_kwargs = _MODE_CASES[mode]
    runtime, factory = _make_runtime(qt_app, 50)
    try:
        owner = QuickDisplayVisualizerOwner(
            runtime, bar_count=32, initial_mode=mode,
            engine_factory=lambda _bc: _Engine(),
        )
        owner.configure(
            logical_kwargs=logical_kwargs,
            presentation_kwargs=presentation_kwargs,
            playing=True,
        )
        identity = owner.bind(engine_generation=_ENGINE_GEN, activation_id=_ACT_ID)
        assert identity.mode_id == mode
        state = owner.controller.logical_tick_state
        _prime_state(state)

        # Advance the authored logical step widget-free until it publishes.
        published_frame = None
        for _ in range(6):
            published_frame = tick_pipeline.logical_tick(state)
            if published_frame is not None:
                break
        assert published_frame is not None, f"{mode} produced no logical frame"

        # The GUI/Quick synchronization owner composes + publishes one snapshot.
        assert owner.sync_present() is True, f"{mode} sync did not publish"

        consumed = owner.controller.render_bridge.take_for_render(
            runtime_generation=identity.runtime_generation,
            engine_generation=_ENGINE_GEN,
            activation_id=_ACT_ID,
            mode_id=mode,
        )
        assert consumed is not None, f"{mode} snapshot did not reach the bridge"
        assert consumed.logical.mode_id == mode
        assert consumed.presentation is not None
        # No widget was constructed for any of this.
        assert type(owner.controller).__name__ == "VisualizerRuntimeController"

        assert owner.retire() is True
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_sync_rejects_stale_identity(qt_app, monkeypatch) -> None:
    _quiet(monkeypatch)
    runtime, factory = _make_runtime(qt_app, 51)
    try:
        owner = QuickDisplayVisualizerOwner(
            runtime, bar_count=32, initial_mode="bubble",
            engine_factory=lambda _bc: _Engine(),
        )
        owner.configure(logical_kwargs={"bubble_big_count": 8}, playing=True)
        owner.bind(engine_generation=_ENGINE_GEN, activation_id=_ACT_ID)
        state = owner.controller.logical_tick_state
        _prime_state(state)
        for _ in range(6):
            if tick_pipeline.logical_tick(state) is not None:
                break

        # Close render admission -> render identity is gone -> a stale pending
        # publication must not be admitted.
        owner.controller.close_render_admission()
        assert owner.controller.render_identity is None
        assert owner.sync_present() is False
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
