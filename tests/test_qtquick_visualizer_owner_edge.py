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
        assert owner._sync is None
        assert owner._pending_mode_activation is None
        assert owner._presentation_resolver is None
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


def test_display_transfer_moves_pacer_and_retirement_edge_without_recreating_controller() -> None:
    class _Pacer:
        def __init__(self) -> None:
            self.active_calls = []
            self.sync_calls = []

        def set_visualizer_active(self, value):
            self.active_calls.append(bool(value))

        def set_visualizer_sync(self, callback):
            self.sync_calls.append(callback)

    class _Scene:
        def __init__(self) -> None:
            self.sinks = []
            self.double = []
            self.middle = []

        def set_visualizer_viewport_config_sink(self, sink):
            self.sinks.append(sink)

        def set_visualizer_double_click_admission(self, value):
            self.double.append(value)

        def set_visualizer_middle_click_admission(self, value):
            self.middle.append(value)

    def _runtime():
        scene = _Scene()
        runtime = SimpleNamespace(
            runtime_generation=17,
            frame_pacer=_Pacer(),
            scene_controller=scene,
        )
        runtime.bind_visualizer_viewport_config = scene.set_visualizer_viewport_config_sink
        return runtime

    source, target = _runtime(), _runtime()
    owner = QuickDisplayVisualizerOwner(source, bar_count=8, initial_mode="bubble")
    controller = owner.controller
    owner._bound = True
    owner._started = True

    assert owner.set_presentation_runtime(target) is True
    assert owner.controller is controller
    assert owner.presentation_runtime is target
    assert owner._runtime is target
    assert source.frame_pacer.active_calls[-1] is False
    assert source.frame_pacer.sync_calls[-1] is None
    assert target.frame_pacer.sync_calls[-1] == owner.sync_present
    assert target.frame_pacer.active_calls[-1] is True
    assert source.scene_controller.sinks[-1] is None
    assert target.scene_controller.sinks[-1] == controller.set_custom_viewport_override

    assert owner.retire() is True
    assert target.frame_pacer.active_calls[-1] is False
    assert target.frame_pacer.sync_calls[-1] is None
    assert target.scene_controller.sinks[-1] is None


def test_fresh_visualizer_sync_requires_a_retained_item_update_request() -> None:
    class _Scene:
        @staticmethod
        def request_visualizer_present() -> bool:
            return False

    owner = object.__new__(QuickDisplayVisualizerOwner)
    owner._retired = False
    owner._presentation_runtime = SimpleNamespace(scene_controller=_Scene())

    with pytest.raises(
        RuntimeError,
        match="fresh visualizer publication has no retained presentation item",
    ):
        owner._request_retained_present()


def test_frame_pacer_coalesces_visualizer_item_update_with_window_request() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "rendering" / "quick" / "frame_pacer.py").read_text(
        encoding="utf-8"
    )
    assert "visualizer_requested_present = bool(synchronize())" in source
    assert "if not visualizer_requested_present:" in source
    assert "self._window.update()" in source
