"""Lead E1 — warm re-entry freshness admission.

The shared beat engine is persistent: it keeps its last committed smoothed bars
(with real energy) across owner recreation and across a pause. On a same-mode /
same-bar-count re-entry nothing bumps the engine generation, so that retained
frame satisfies the *generation-only* fresh-frame fence and would be admitted as
the first reactive result — a flash of seconds-old audio energy.

These tests pin the commit-seq watermark fix:

- a warm re-entry holds the fence until the engine commits a frame *after*
  re-entry (the retained stale bars never reach the display mirror);
- a cold engine (no prior committed frame) is left unfenced, so cold start is
  unchanged;
- with no watermark armed (mode-change / steady-state) the fence keeps its exact
  generation-only clear semantics;
- the real engine's commit sequence is monotonic and advances on every commit.
"""
from __future__ import annotations

from typing import List

from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.logical_tick_state import (
    VisualizerLogicalTickState,
    install_default_logical_tick_state,
)


class _FakeController:
    """Minimal controller exposing the fields the logical state delegates to."""

    def __init__(self, bar_count: int, mode_id: str) -> None:
        self.bar_count = bar_count
        self.mode_id = mode_id
        self.runtime_generation = 1
        self.engine = None
        self.playing = True
        self.enabled = True
        self.thread_manager = None
        self.process_supervisor = None
        self.settings_model = None
        self.technical_config_cache = {}
        self.presentation_state = None
        self.pending_engine_generation = -1
        self.last_engine_generation_seen = -1
        self.pending_engine_activation_id = -1
        self.last_engine_activation_seen = -1


class _FakeEngine:
    """Persistent engine that already holds a retained (stale) committed frame."""

    def __init__(self, bar_count: int, *, warm: bool) -> None:
        self._bar_count = bar_count
        self._generation = 6
        self._activation = 6
        # A warm engine's retained frame carries real old energy.
        self._smoothed = [0.6] * bar_count if warm else [0.0] * bar_count
        self._commit_seq = 10 if warm else 0
        self._frame_ts = 1000.0 if warm else 0.0

    # --- committed-frame provenance ------------------------------------- #
    def get_latest_authoritative_frame(self):
        return (self._frame_ts, self._generation, self._activation)

    def get_authoritative_frame_commit_seq(self) -> int:
        return self._commit_seq

    def get_latest_generation_with_frame(self) -> int:
        return self._generation

    def get_latest_generation_with_waveform(self) -> int:
        return self._generation

    def get_generation_id(self) -> int:
        return self._generation

    def get_activation_id(self) -> int:
        return self._activation

    def get_smoothed_bars(self) -> List[float]:
        return list(self._smoothed)

    # --- lifecycle no-ops ----------------------------------------------- #
    def tick(self):
        return None

    def set_smoothing(self, *_a, **_k):
        return None

    # --- test helper ----------------------------------------------------- #
    def commit_fresh(self, bars: List[float]) -> None:
        """Simulate the engine committing a genuinely fresh frame after re-entry."""
        self._smoothed = list(bars)
        self._commit_seq += 1
        self._frame_ts += 1.0


def _make_state(engine, *, mode_id: str = "bubble", bar_count: int = 32):
    controller = _FakeController(bar_count, mode_id)
    state = VisualizerLogicalTickState(controller)
    install_default_logical_tick_state(state, bar_count=bar_count)
    controller.engine = engine
    controller.playing = True
    return controller, state


def test_warm_reentry_holds_until_post_reentry_commit():
    engine = _FakeEngine(32, warm=True)
    _controller, state = _make_state(engine)

    armed = tick_pipeline.arm_reentry_fresh_frame_fence(state, engine)
    assert armed is True
    assert state._waiting_for_fresh_engine_frame is True
    assert state._pending_engine_frame_epoch == 10

    # First reactive tick while playing: no frame committed since re-entry.
    changed, any_nonzero = tick_pipeline.consume_engine_bars(state, 2000.0)
    assert changed is False and any_nonzero is False
    assert state._waiting_for_fresh_engine_frame is True
    # The retained stale energy never reached the display mirror.
    assert all(v == 0.0 for v in state._display_bars)

    # A genuinely fresh frame commits after re-entry -> the fence releases it.
    engine.commit_fresh([0.4] * 32)
    changed, any_nonzero = tick_pipeline.consume_engine_bars(state, 2000.05)
    assert state._waiting_for_fresh_engine_frame is False
    assert state._pending_engine_frame_epoch == -1
    assert changed is True and any_nonzero is True
    assert state._display_bars[0] == 0.4


def test_warm_reentry_spectrum_also_holds():
    # Spectrum is not idle-self-animating, so the paused-clear path never fires;
    # while playing the watermark must still hold the retained frame.
    engine = _FakeEngine(48, warm=True)
    _controller, state = _make_state(engine, mode_id="spectrum", bar_count=48)

    assert tick_pipeline.arm_reentry_fresh_frame_fence(state, engine) is True
    changed, any_nonzero = tick_pipeline.consume_engine_bars(state, 5.0)
    assert changed is False and any_nonzero is False
    assert state._waiting_for_fresh_engine_frame is True
    assert all(v == 0.0 for v in state._display_bars)

    engine.commit_fresh([0.3] * 48)
    tick_pipeline.consume_engine_bars(state, 5.01)
    assert state._waiting_for_fresh_engine_frame is False
    assert state._display_bars[0] == 0.3


def test_cold_engine_is_left_unfenced():
    engine = _FakeEngine(32, warm=False)
    _controller, state = _make_state(engine)

    armed = tick_pipeline.arm_reentry_fresh_frame_fence(state, engine)
    assert armed is False
    assert state._waiting_for_fresh_engine_frame is False
    assert state._pending_engine_frame_epoch == -1

    # A cold engine presents whatever it has (zeros) with no hold.
    tick_pipeline.consume_engine_bars(state, 1.0)
    assert state._waiting_for_fresh_engine_frame is False


def test_unarmed_fence_keeps_generation_only_semantics():
    # No watermark armed (epoch < 0): a same-generation frame clears the fence
    # immediately, exactly as before Lead E1 (mode-change / steady-state path).
    engine = _FakeEngine(32, warm=True)
    _controller, state = _make_state(engine)
    state._waiting_for_fresh_engine_frame = True
    state._pending_engine_generation = engine.get_generation_id()
    state._pending_engine_activation_id = engine.get_activation_id()
    assert state._pending_engine_frame_epoch == -1

    tick_pipeline.consume_engine_bars(state, 1.0)
    assert state._waiting_for_fresh_engine_frame is False


def test_engine_commit_seq_is_monotonic_and_advances():
    from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine

    engine = get_shared_spotify_beat_engine(32)
    before = engine.get_authoritative_frame_commit_seq()
    assert isinstance(before, int)

    ok = engine._commit_analysis_frame(
        raw_bars=[0.2] * 32,
        smoothed_bars=[0.2] * 32,
        timestamp=123.0,
        activation_id=engine.get_activation_id(),
    )
    assert ok is True
    assert engine.get_authoritative_frame_commit_seq() == before + 1
    assert engine.get_latest_authoritative_frame()[0] == 123.0
