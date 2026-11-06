"""Spectrum visual-only smoothing through the production logical tick (operator, 6 Nov: "still broken").

The retired GL overlay push was the only writer that cleared ``_has_pushed_first_frame``. With it gone the capture
reported ``first_frame=True`` on every tick, so ``SpectrumFrameRuntime`` took its snap-to-source reset branch every
frame and every strength drew exactly the unsmoothed bars. These cases replay a fixture through ``logical_tick`` ->
``capture_visualizer_logical_frame`` (also the Spectrum Studio's step) -> ``SpectrumFrameRuntime`` and fail on that
behaviour (the negative control re-creates it). Strengths are compared with each other, never against authored values.
"""
from __future__ import annotations

import math

import pytest

import widgets.spotify_visualizer.tick_pipeline as tick_pipeline
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tools.visualizer_replay.driver import load_clips, replay_clip
from widgets.spotify_visualizer import spectrum_frame_runtime
from widgets.spotify_visualizer.spectrum_frame_runtime import SpectrumFrameRuntime

pytestmark = pytest.mark.usefixtures("qt_app")

STRENGTHS = (0.3, 0.7, 1.0)


@pytest.fixture(scope="module")
def clip():
    return load_clips()["representative_music_features"]


def _replay(clip, enabled: bool, strength: float):
    """Drawn bars and the source bars Spectrum's runtime received, per tick."""
    sources = []
    real = SpectrumFrameRuntime.resolve

    def spy(self, source_bars, **kwargs):
        sources.append(tuple(float(value) for value in source_bars))
        return real(self, source_bars, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(spectrum_frame_runtime.SpectrumFrameRuntime, "resolve", spy)
        result = replay_clip(clip, "spectrum", settings=frozen_visualizer_settings, overrides={
            "spectrum_visual_smoothing_enabled": enabled, "spectrum_visual_smoothing": strength})
    drawn = [tuple(frame.common.bars) for frame in result["logical_series"]]
    return drawn, sources


def _residual(reference, drawn) -> float:
    return sum(abs(a - b) for left, right in zip(reference, drawn) for a, b in zip(left, right))


def _jerk(drawn) -> float:
    return sum(abs(c - 2.0 * b + a) for x, y, z in zip(drawn, drawn[1:], drawn[2:]) for a, b, c in zip(x, y, z))


def _assert_smoothing_is_live(clip) -> None:
    off, off_sources = _replay(clip, False, 0.0)
    residuals, jerks = [], [_jerk(off)]
    for strength in STRENGTHS:
        drawn, sources = _replay(clip, True, strength)
        # Visual only: the analysis Spectrum draws from is identical whatever the smoothing does.
        assert sources == off_sources
        residuals.append(_residual(off, drawn))
        jerks.append(_jerk(drawn))
    assert residuals[0] > 0.0, "visual smoothing drew the unsmoothed bars"
    assert residuals == sorted(residuals) and len(set(residuals)) == len(residuals), residuals
    assert jerks == sorted(jerks, reverse=True) and len(set(jerks)) == len(jerks), jerks


def test_visual_smoothing_changes_drawn_bars_monotonically_on_the_production_tick(clip):
    _assert_smoothing_is_live(clip)


def test_negative_control_a_first_frame_flag_that_never_clears_kills_smoothing(clip, monkeypatch):
    original = tick_pipeline._publish_logical_state

    def never_clears(widget, *args, **kwargs):
        payload = original(widget, *args, **kwargs)
        widget._has_pushed_first_frame = False      # the pre-fix state: nothing ever cleared it
        return payload

    monkeypatch.setattr(tick_pipeline, "_publish_logical_state", never_clears)
    with pytest.raises(AssertionError, match="unsmoothed"):
        _assert_smoothing_is_live(clip)


def test_first_capture_ends_the_first_frame_edge(clip):
    from widgets.spotify_visualizer import logical_frame_capture

    flags = []
    real = logical_frame_capture.capture_visualizer_logical_frame

    def spy(widget, **kwargs):
        flags.append(bool(widget._has_pushed_first_frame))
        return real(widget, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(logical_frame_capture, "capture_visualizer_logical_frame", spy)
        replay_clip(clip, "spectrum", settings=frozen_visualizer_settings)
    assert flags[0] is False and all(flags[1:]), flags[:5]


def _step_response(strength: float, hz: float, seconds: float) -> float:
    runtime = SpectrumFrameRuntime()
    common = dict(bar_count=1, runtime_generation=1, engine_generation=1, activation_id=1, source_generation=1,
                  source_activation_id=1, playing=True, smoothing_enabled=True, smoothing_strength=strength,
                  single_piece=False, segments=40, ghosting_enabled=False, ghost_decay=0.0, animation_enabled=False)
    runtime.resolve([0.0], now_ts=10.0, first_frame=True, **common)
    steps = int(round(seconds * hz))
    value = 0.0
    for index in range(1, steps + 1):
        value = runtime.resolve([1.0], now_ts=10.0 + index / hz, first_frame=False, **common).bars[0]
    return value


@pytest.mark.parametrize("strength", STRENGTHS)
def test_smoothing_is_time_based_not_tick_based(strength):
    # The same elapsed time reaches the same height at 60, 120 and 240 Hz ticks.
    values = [_step_response(strength, hz, 1.0 / 20.0) for hz in (60.0, 120.0, 240.0)]
    assert 0.0 < min(values) < 1.0
    assert max(values) - min(values) < 1.0e-6, values


def test_stronger_smoothing_is_slower_at_every_rate():
    for hz in (60.0, 120.0, 240.0):
        values = [_step_response(strength, hz, 1.0 / hz) for strength in STRENGTHS]
        assert all(math.isfinite(v) for v in values)
        assert values == sorted(values, reverse=True) and len(set(values)) == len(values), (hz, values)
