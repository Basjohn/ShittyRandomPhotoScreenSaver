"""VZ-03: the logical tick's phase breakdown is diagnostic work, opt-in via --perf.

With perf off a tick must build no phase recorder at all (no closure, dict or
``perf_counter`` samples); with perf on a slow tick still logs the identical
phase breakdown.
"""

from __future__ import annotations

import time

from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from tests.test_qtquick_visualizer_logical_ownership import (
    _CANONICAL_BUBBLE_CONFIG,
    _Engine,
)

_PHASES = (
    "fresh_state",
    "validity",
    "context",
    "perf_accounting",
    "engine_consume",
    "teardown_check",
    "heartbeat",
    "bubble_step",
    "devcurve_dispatch",
    "publish",
)


def _bubble_tick_state():
    from core.settings.default_contract import get_raw_default_settings
    from core.settings.models import SpotifyVisualizerSettings
    from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.presentation_state import (
        install_default_presentation_state,
    )
    from widgets.spotify_visualizer.quick_technical_config import (
        apply_controller_technical_config,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.technical_config import build_technical_cache

    controller = VisualizerRuntimeController(
        runtime_generation=0, bar_count=32, initial_mode="bubble"
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    install_default_presentation_state(controller.presentation_state)
    apply_logical_vis_mode_kwargs(state, _CANONICAL_BUBBLE_CONFIG)
    controller.enabled = True
    controller.playing = True
    controller.engine = _Engine()
    model = SpotifyVisualizerSettings.from_mapping(
        dict(get_raw_default_settings()["widgets"]["spotify_visualizer"])
    )
    technical = dict(build_technical_cache(None, model)["bubble"])
    apply_controller_technical_config(controller, technical, reason="vz03_test")
    assert controller.resolve_logical_mode_state("bubble", BubbleFrameRuntime) is not None
    controller.begin_render_activation(engine_generation=3, activation_id=4)
    state._mode_teardown_block_until_ready = False
    state._mode_transition_ready = True
    state._waiting_for_fresh_engine_frame = False
    return controller, state


def _slow_tick(monkeypatch, *, perf: bool) -> tuple[list[str], int]:
    controller, state = _bubble_tick_state()

    def _slow_consume(_owner, _now):
        time.sleep(0.06)  # exceed the 50 ms slow-tick threshold
        return True, True

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", _slow_consume)
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "dispatch_devcurve_field", lambda owner, now: None)
    monkeypatch.setattr(tick_pipeline, "is_perf_metrics_enabled", lambda: perf)
    recorders = []
    real_recorder = tick_pipeline._new_tick_phase_recorder

    def _counting_recorder():
        recorders.append(True)
        return real_recorder()

    monkeypatch.setattr(tick_pipeline, "_new_tick_phase_recorder", _counting_recorder)
    warnings: list[str] = []
    monkeypatch.setattr(
        tick_pipeline.logger,
        "warning",
        lambda message, *args: warnings.append(message % args),
    )

    frame = tick_pipeline.logical_tick(state)

    assert frame is not None
    assert controller.logical_mailbox.take() is not None
    return warnings, len(recorders)


def test_perf_off_tick_builds_no_phase_record_and_logs_nothing(monkeypatch) -> None:
    warnings, recorders = _slow_tick(monkeypatch, perf=False)

    assert recorders == 0
    assert not [w for w in warnings if "[SPOTIFY_VIS]" in w]


def test_perf_on_slow_tick_keeps_the_phase_breakdown(monkeypatch) -> None:
    warnings, recorders = _slow_tick(monkeypatch, perf=True)

    assert recorders == 1
    slow = [w for w in warnings if w.startswith("[PERF] [SPOTIFY_VIS] Slow _on_tick: ")]
    assert len(slow) == 1
    breakdown = [
        w for w in warnings if w.startswith("[PERF] [SPOTIFY_VIS] Tick phase breakdown ")
    ]
    assert len(breakdown) == 1
    line = breakdown[0]
    assert "mode=bubble changed=True first_frame=" in line
    assert "used_gpu=False" in line
    tail = line.split("used_gpu=False ", 1)[1]
    assert [part.split("_ms=")[0] for part in tail.split(" ")] == list(_PHASES)
    consume_ms = float(tail.split("engine_consume_ms=")[1].split(" ")[0])
    assert consume_ms >= 50.0
