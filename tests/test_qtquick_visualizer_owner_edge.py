"""Thin Quick visualizer ownership edge bars (H).

Prove the edge constructs/configures/starts the existing VisualizerRuntimeController
per display generation, binds its render source + viewport-config seam into the
QuickDisplayRuntime, and retires cleanly across a generation replacement - with no
SpotifyVisualizerWidget and no duplicate engine/logical owner.
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


class _Engine:
    """Production-shaped fake engine (energy/transient snapshots)."""

    def __init__(self) -> None:
        self.acquire_count = 0
        self.release_count = 0

    def get_bubble_energy_bands(self):
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

    def set_playback_state(self, _playing: bool) -> None:
        pass

    def acquire(self) -> None:
        self.acquire_count += 1

    def release(self) -> None:
        self.release_count += 1


_BUBBLE_CONFIG = {
    "bubble_big_count": 8,
    "bubble_small_count": 25,
    "bubble_drift_direction": "random",
    "bubble_stream_direction": "up",
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


def _quiet_tick(monkeypatch):
    # Isolate lifecycle from engine consumption; the real Bubble dispatch is
    # covered by the ownership/acceptance bars.
    monkeypatch.setattr(
        tick_pipeline, "consume_engine_bars", lambda owner, now: (True, True)
    )
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "dispatch_devcurve_field", lambda owner, now: None)


@pytest.mark.qt
def test_edge_constructs_configures_binds_starts_and_retires(qt_app, monkeypatch) -> None:
    _quiet_tick(monkeypatch)
    runtime, factory = _make_runtime(qt_app, 40)
    try:
        engine = _Engine()
        owner = QuickDisplayVisualizerOwner(
            runtime,
            bar_count=32,
            initial_mode="bubble",
            engine_factory=lambda _bc: engine,
        )
        # Exactly one controller for this generation, tagged with it.
        assert owner.controller.runtime_generation == 40

        owner.configure(logical_kwargs=_BUBBLE_CONFIG, playing=True)
        assert owner.controller.enabled is True
        assert owner.controller.engine is not None
        assert owner.controller.logical_tick_state._bubble_big_count == 8

        identity = owner.bind(engine_generation=6, activation_id=9)
        assert identity.runtime_generation == 40
        assert identity.engine_generation == 6
        assert identity.activation_id == 9
        assert identity.mode_id == "bubble"
        assert runtime.scene_controller.visualizer_render_identity == identity

        owner.start()
        logical = owner.controller.logical_runtime
        assert logical is not None
        assert logical.is_running() is True
        assert engine.acquire_count == 1

        assert owner.retire() is True
        # The sole logical runtime is joined/stopped and detached from the controller.
        assert logical.is_running() is False
        assert owner.controller.logical_runtime is None
        assert engine.release_count == 1
        # Idempotent.
        assert owner.retire() is False
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_generation_replacement_builds_fresh_owner_no_duplicate(qt_app, monkeypatch) -> None:
    _quiet_tick(monkeypatch)
    first_runtime, first_factory = _make_runtime(qt_app, 41)
    try:
        first = QuickDisplayVisualizerOwner(
            first_runtime, bar_count=32, initial_mode="bubble",
            engine_factory=lambda _bc: _Engine(),
        )
        first.configure(logical_kwargs=_BUBBLE_CONFIG, playing=True)
        first.bind(engine_generation=1, activation_id=1)
        first.start()
        first_logical = first.controller.logical_runtime
        assert first_logical.is_running() is True

        # Replacement retires the old owner's sole logical runtime first.
        assert first.retire() is True
        assert first_logical.is_running() is False
    finally:
        first_runtime.close_runtime()
        first_factory.deleteLater()
        qt_app.processEvents()

    second_runtime, second_factory = _make_runtime(qt_app, 42)
    try:
        second = QuickDisplayVisualizerOwner(
            second_runtime, bar_count=32, initial_mode="bubble",
            engine_factory=lambda _bc: _Engine(),
        )
        second.configure(logical_kwargs=_BUBBLE_CONFIG, playing=True)
        # A replacement generation owns its own distinct controller + logical runtime.
        assert second.controller is not first.controller
        assert second.controller.runtime_generation == 42
        second.bind(engine_generation=2, activation_id=2)
        second.start()
        assert second.controller.logical_runtime is not first_logical
        assert second.controller.logical_runtime.is_running() is True
        second.retire()
    finally:
        second_runtime.close_runtime()
        second_factory.deleteLater()
        qt_app.processEvents()
