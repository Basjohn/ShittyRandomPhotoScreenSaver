"""Paused idle waveform samples are synthesized only for Oscilloscope (VZ-01).

The paused BeatEngine used to synthesize 256 x 3 ``math.sin`` samples on every
authored tick for every mode (~150 us/tick), although only the Oscilloscope
renderer draws them. Line-mode readiness keys on the waveform *generation*,
which must keep advancing exactly as before.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from widgets.spotify_visualizer import beat_engine as beat_engine_module
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


def _reference_idle_waveform(now_ts: float) -> list[float]:
    """The authored R-03 idle synthesis, frozen here as the oracle."""
    count = 256
    phase = now_ts * 0.62
    out = []
    for i in range(count):
        x = float(i) / float(count - 1)
        slow = math.sin((x * 2.0 * math.pi * 1.2) + phase)
        mid = math.sin((x * 2.0 * math.pi * 2.7) - (phase * 0.8))
        fine = math.sin((x * 2.0 * math.pi * 5.1) + (phase * 1.4))
        out.append(float((slow * 0.035) + (mid * 0.022) + (fine * 0.010)))
    return out


@pytest.fixture
def paused_engine(monkeypatch):
    engine = _SpotifyBeatEngine(bar_count=32)
    engine.set_playback_state(False)
    engine._audio_buffer.consume_latest = Mock(return_value=None)
    clock = [1000.25]
    monkeypatch.setattr(beat_engine_module.time, "time", lambda: clock[0])
    engine._test_clock = clock
    return engine


def test_oscilloscope_demand_synthesizes_the_identical_idle_waveform(paused_engine) -> None:
    paused_engine.set_idle_waveform_demand(True)
    for step in range(3):
        paused_engine._test_clock[0] = 1000.25 + step * 0.011
        paused_engine.tick()
        assert paused_engine.get_waveform() == _reference_idle_waveform(paused_engine._test_clock[0])
        assert paused_engine.get_waveform_count() == 256
        assert (
            paused_engine.get_latest_generation_with_waveform()
            == paused_engine.get_generation_id()
        )


def test_non_line_modes_skip_synthesis_but_keep_readiness(paused_engine, monkeypatch) -> None:
    calls: list[float] = []
    monkeypatch.setattr(paused_engine, "_update_idle_waveform", lambda now_ts: calls.append(now_ts))
    # Live PCM captured before the pause must not linger in paused snapshots.
    paused_engine._waveform = [0.9] * 256
    paused_engine._waveform_count = 256
    paused_engine._latest_generation_with_waveform = -1

    paused_engine.set_idle_waveform_demand(False)
    for _ in range(5):
        paused_engine.tick()

    assert calls == []
    assert paused_engine.get_waveform_count() == 0
    assert max(abs(value) for value in paused_engine.get_waveform()) == 0.0
    assert paused_engine.get_latest_generation_with_waveform() == paused_engine.get_generation_id()
    # Idle bars/energy still animate for every paused mode.
    assert max(paused_engine._latest_bars) > 0.0


def test_undeclared_callers_keep_synthesizing(paused_engine) -> None:
    paused_engine.tick()
    assert paused_engine.get_waveform() == _reference_idle_waveform(paused_engine._test_clock[0])


@pytest.mark.parametrize(
    ("mode", "demanded"),
    [
        ("oscilloscope", True),
        ("sine_wave", False),
        ("spectrum", False),
        ("bubble", False),
        ("devcurve", False),
        ("sphere", False),
    ],
)
def test_logical_step_declares_demand_before_every_engine_tick(mode, demanded, monkeypatch) -> None:
    order: list[tuple[str, object]] = []
    engine = SimpleNamespace(
        set_idle_waveform_demand=lambda value: order.append(("demand", value)),
        tick=lambda: order.append(("tick", None)),
        get_smoothed_bars=lambda: [0.0] * 4,
        get_generation_id=lambda: 1,
        get_activation_id=lambda: 1,
        get_latest_generation_with_frame=lambda: 1,
    )
    widget = SimpleNamespace(
        _engine=engine,
        _bar_count=4,
        _vis_mode_str=mode,
        _waiting_for_fresh_engine_frame=True,
        _pending_engine_generation=-1,
        _spotify_playing=True,
        _latency_pending_probe=set(),
        _log_audio_latency_metrics=lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(tick_pipeline, "_ensure_fresh_generation_state", lambda _widget: None)
    # A reset generation is still unresolved, so no bars are consumed; only the
    # ordering at the engine boundary matters here.
    assert tick_pipeline.consume_engine_bars(widget, 1.0) == (False, False)
    assert order == [("demand", demanded), ("tick", None)]
