"""Focused Oscilloscope frame-runtime and Qt Quick renderer regressions."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
from rendering.quick.visualizer.implementations.oscilloscope import (
    QuickOscilloscopeRenderer,
    oscilloscope_layout,
)
from widgets.spotify_visualizer.oscilloscope_frame_runtime import OscilloscopeFrameRuntime


_IDENTITY = dict(runtime_generation=2, engine_generation=5, activation_id=7)


def _resolve(
    runtime: OscilloscopeFrameRuntime,
    waveform,
    *,
    now_ts: float,
    playing: bool = True,
    source_generation: int = 5,
    source_activation_id: int = 7,
    source_timestamp: float | None = None,
    display: str = "Trace",
    span_ms: float = 22.0,
    gain: float = 2.0,
    delay_ms: float = 1.2,
    afterglow: float = 0.4,
    detail: float = 0.7,
    onsets=(),
    loudness: float = 0.6,
    presence: float = 0.4,
    intensity: float = 0.8,
    spectrum=(),
):
    values = tuple(waveform)
    return runtime.resolve(
        history=None,
        waveform=values,
        waveform_count=len(values),
        now_ts=now_ts,
        **_IDENTITY,
        source_generation=source_generation,
        source_activation_id=source_activation_id,
        source_timestamp=(now_ts if playing and source_timestamp is None else source_timestamp),
        playing=playing,
        display=display,
        span_ms=span_ms,
        gain=gain,
        delay_ms=delay_ms,
        afterglow=afterglow,
        detail=detail,
        onsets=onsets,
        loudness=loudness,
        presence=presence,
        intensity=intensity,
        spectrum=spectrum,
    )


def test_paused_idle_frame_is_ready_and_contains_packed_trace() -> None:
    runtime = OscilloscopeFrameRuntime()
    idle = tuple(0.2 * math.sin(index * math.tau / 32.0) for index in range(64))
    resolved = _resolve(runtime, idle, now_ts=1.0, playing=False)

    assert resolved is not None
    assert resolved.reactive_source_ready is True
    assert resolved.trace_alphas == (1.0,)
    assert len(resolved.points) > 0
    assert len(resolved.points) % 8 == 0
    assert resolved.animation_time == 0.0


def test_playing_frame_without_authoritative_timestamp_is_not_reactive() -> None:
    runtime = OscilloscopeFrameRuntime()
    unresolved = _resolve(runtime, (0.8,) * 64, now_ts=1.0, source_timestamp=0.0)

    assert unresolved is not None
    assert unresolved.reactive_source_ready is False
    assert unresolved.flare == 0.0
    assert unresolved.drive == 0.0


def test_stale_source_cannot_replace_current_trace() -> None:
    runtime = OscilloscopeFrameRuntime()
    live = _resolve(runtime, [0.8 * math.sin(i * math.tau / 32.0) for i in range(64)], now_ts=1.0)
    stale = _resolve(runtime, [-0.8] * 64, now_ts=1.016, source_generation=4)

    assert live is not None and stale is not None
    assert stale.reactive_source_ready is False
    assert stale.points == live.points


def test_afterglow_keeps_prior_packed_trace_and_fades_oldest() -> None:
    runtime = OscilloscopeFrameRuntime()
    first = _resolve(runtime, [math.sin(i * math.tau / 32.0) for i in range(256)], now_ts=1.0)
    second = _resolve(runtime, [math.cos(i * math.tau / 32.0) for i in range(256)], now_ts=1.1)

    assert first is not None and second is not None
    assert len(first.trace_alphas) == 1
    assert len(second.trace_alphas) == 2
    assert second.trace_alphas[0] < 1.0
    assert second.points[: len(first.points)] == first.points
    assert len(second.points) == len(first.points) * 2

    expired = _resolve(runtime, [0.3] * 256, now_ts=2.0)
    assert expired is not None
    assert expired.trace_alphas == (1.0,)
    assert expired.points != second.points[: len(expired.points)]


def test_onset_drive_tone_and_logical_time_are_runtime_owned() -> None:
    runtime = OscilloscopeFrameRuntime()
    first = _resolve(runtime, [math.sin(i * math.tau / 32.0) for i in range(256)], now_ts=1.0)
    onset = SimpleNamespace(serial=1, timestamp=1.03, magnitude=3.0, loudness=1.0, presence=1.0)
    second = _resolve(
        runtime,
        [math.sin(i * math.tau / 28.0) for i in range(256)],
        now_ts=1.03,
        onsets=(onset,),
        spectrum=(0.0, 0.1, 0.8, 1.0),
    )

    assert first is not None and second is not None
    assert second.animation_time == pytest.approx(0.03)
    assert second.changed is True
    assert second.flare > 0.0
    assert second.drive > first.drive
    assert second.tone > first.tone

    # The flare rises toward the hit over a few tens of ms, then decays; the serial is taken once.
    rising = _resolve(runtime, [math.sin(i * math.tau / 28.0) for i in range(256)], now_ts=1.06,
                      onsets=(onset,))
    later = _resolve(runtime, [math.sin(i * math.tau / 28.0) for i in range(256)], now_ts=1.6,
                     onsets=(onset,))
    assert rising is not None and later is not None
    assert runtime.onset_serial == onset.serial
    assert rising.flare > second.flare
    assert 0.0 < later.flare < rising.flare


def test_oscilloscope_layout_reflows_by_display_shape() -> None:
    trace_scale, trace_length = oscilloscope_layout((0.0, 0.0, 420.0, 280.0), "Trace")
    ring_scale, ring_length = oscilloscope_layout((0.0, 0.0, 420.0, 280.0), "Ring")
    phase_scale, phase_length = oscilloscope_layout((0.0, 0.0, 560.0, 280.0), "Phase")

    assert trace_scale[0] > trace_scale[1]
    assert ring_scale[0] == pytest.approx(ring_scale[1])
    assert phase_scale[0] == pytest.approx(phase_scale[1])
    assert trace_length > 0.0
    assert ring_length > trace_length
    assert phase_length > 0.0


def test_quick_oscilloscope_registry_is_static_lazy_and_resource_dormant(monkeypatch) -> None:
    from rendering.quick.visualizer import implementation_registry

    descriptors = implementation_registry.iter_quick_visualizer_implementations()
    assert tuple(descriptor.mode_id for descriptor in descriptors) == VISUALIZER_MODE_IDS

    imported: list[str] = []
    real_import = implementation_registry.import_module
    monkeypatch.setattr(implementation_registry, "import_module", lambda name: (imported.append(name), real_import(name))[1])
    implementation_registry.iter_quick_visualizer_implementations()
    assert imported == []

    renderer = implementation_registry.resolve_quick_visualizer_renderer("oscilloscope")
    assert renderer is not None
    assert renderer.mode_id == "oscilloscope"
    assert renderer.has_resources is False
    assert imported == ["rendering.quick.visualizer.implementations.oscilloscope"]


def test_quick_oscilloscope_renderer_has_no_legacy_presentation_dependency() -> None:
    source = QuickOscilloscopeRenderer.__module__
    import importlib

    module_source = importlib.import_module(source).__loader__.get_source(source)
    assert module_source is not None
    assert "spotify_bars_gl_overlay" not in module_source
    assert "QWidget" not in module_source
    assert "DisplayWidget" not in module_source
    assert "gl_FragCoord" not in module_source
    assert "glDrawArraysInstanced" in module_source

