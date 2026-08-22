"""Authored Spectrum presentation state advanced by the sole logical clock."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from widgets.spotify_visualizer.frame_runtime_lifecycle import (
    RetirableFrameRuntime,
    retirement_fenced,
)
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)
from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
    idle_spectrum_baseline,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    apply_spectrum_solid_hysteresis,
    reset_spectrum_solid_hysteresis_state,
)


_MIN_TIME_CONSTANT_SECONDS = 0.002
_MAX_TIME_CONSTANT_SECONDS = 0.014
_STALL_SNAP_SECONDS = 0.100
_SETTLED_EPSILON = 1.0e-4


def _clamp01(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(0.0, min(1.0, number))


def _normalise_bars(values: Sequence[object], count: int) -> list[float]:
    resolved = [_clamp01(value) for value in values[:count]]
    if len(resolved) < count:
        resolved.extend([0.0] * (count - len(resolved)))
    return resolved


def _changed(previous: Sequence[float], current: Sequence[float]) -> bool:
    return len(previous) != len(current) or any(
        abs(float(before) - float(after)) > _SETTLED_EPSILON
        for before, after in zip(previous, current)
    )


@dataclass(frozen=True, slots=True)
class SpectrumResolvedFrame:
    bars: tuple[float, ...]
    peaks: tuple[float, ...]
    ghost_bars: tuple[float, ...]
    animation_time: float
    changed: bool
    reactive_source_ready: bool


class SpectrumFrameRuntime(RetirableFrameRuntime):
    """Small Spectrum-only state owner with no Qt or render-loop authority."""

    def __init__(self) -> None:
        super().__init__()
        self._presentation_bars: list[float] = []
        self._presentation_last_ts = 0.0
        self._presentation_identity: tuple[object, ...] | None = None
        self._peaks: list[float] = []
        self._last_peak_ts = 0.0
        self._animation_time = 0.0
        self._last_animation_ts = 0.0
        self._activation_identity: tuple[int, int, int] | None = None
        reset_spectrum_solid_hysteresis_state(self)

    def reset(self) -> None:
        self._presentation_bars = []
        self._presentation_last_ts = 0.0
        self._presentation_identity = None
        self._peaks = []
        self._last_peak_ts = 0.0
        self._animation_time = 0.0
        self._last_animation_ts = 0.0
        self._activation_identity = None
        reset_spectrum_solid_hysteresis_state(self)

    @retirement_fenced
    def resolve(
        self,
        source_bars: Sequence[object],
        *,
        bar_count: int,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_generation: int,
        source_activation_id: int,
        playing: bool,
        first_frame: bool,
        smoothing_enabled: bool,
        smoothing_strength: float,
        single_piece: bool,
        segments: int,
        viewport_height: float = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1],
        ghosting_enabled: bool,
        ghost_decay: float,
        animation_enabled: bool,
    ) -> SpectrumResolvedFrame | None:
        count = max(0, int(bar_count))
        timestamp = float(now_ts)
        activation_identity = (
            int(runtime_generation),
            int(engine_generation),
            int(activation_id),
        )
        if activation_identity != self._activation_identity:
            self.reset()
            self._activation_identity = activation_identity

        source_ready = bool(
            int(source_generation) >= 0
            and int(source_activation_id) >= 0
            and int(source_generation) == int(engine_generation)
            and int(source_activation_id) == int(activation_id)
        )
        values = _normalise_bars(source_bars, count)
        strength = _clamp01(smoothing_strength)
        presentation_identity = (
            activation_identity,
            int(source_generation),
            int(source_activation_id),
            count,
            bool(single_piece),
            round(strength, 4),
        )

        previous_bars = list(self._presentation_bars)
        if not playing:
            baseline = idle_spectrum_baseline(count)
            values = [max(value, floor) for value, floor in zip(values, baseline)]
            resolved_bars = values
        elif not source_ready:
            # Keep the presentation-owned resting scene while Play waits for a
            # real current-activation frame.  The source identity remains
            # absent/stale and the render admission guard will not treat these
            # bars as reactive data.
            resolved_bars = (
                list(previous_bars)
                if len(previous_bars) == count
                else idle_spectrum_baseline(count)
            )
        elif not smoothing_enabled or strength <= 0.0:
            resolved_bars = values
        else:
            last_ts = self._presentation_last_ts
            dt = timestamp - last_ts
            reset_boundary = bool(
                first_frame
                or self._presentation_identity != presentation_identity
                or len(previous_bars) != len(values)
                or dt <= 0.0
                or dt >= _STALL_SNAP_SECONDS
            )
            if reset_boundary:
                resolved_bars = values
            else:
                time_constant = _MIN_TIME_CONSTANT_SECONDS + (
                    _MAX_TIME_CONSTANT_SECONDS - _MIN_TIME_CONSTANT_SECONDS
                ) * strength
                alpha = 1.0 - math.exp(-dt / max(time_constant, 1.0e-6))
                resolved_bars = []
                for prior, target in zip(previous_bars, values):
                    next_value = prior + (target - prior) * alpha
                    if abs(target - next_value) <= _SETTLED_EPSILON:
                        next_value = target
                    resolved_bars.append(next_value)

        self._presentation_bars = list(resolved_bars)
        self._presentation_last_ts = timestamp
        self._presentation_identity = presentation_identity

        if single_piece and resolved_bars:
            resolved_bars = apply_spectrum_solid_hysteresis(
                self,
                resolved_bars,
                segments=max(1, int(segments)),
                render_height=max(1.0, float(viewport_height)),
                now_ts=timestamp,
            )
        else:
            reset_spectrum_solid_hysteresis_state(self)

        peaks_before = list(self._peaks)
        peak_dt = (
            timestamp - self._last_peak_ts
            if self._last_peak_ts > 0.0 and timestamp > self._last_peak_ts
            else 0.0
        )
        peaks = list(peaks_before)
        if len(peaks) != count:
            peaks = list(resolved_bars)
        decay_rate = max(0.0, float(ghost_decay)) * 2.0
        decay = decay_rate * peak_dt
        for index, value in enumerate(resolved_bars):
            peak = peaks[index]
            if value > peak:
                peak = value
            elif decay > 0.0:
                gap = max(0.0, peak - value)
                gap_factor = 0.75 + min(1.0, gap) * 0.75
                peak = max(value, peak - decay * gap_factor)
            peaks[index] = _clamp01(peak)
        self._peaks = peaks
        self._last_peak_ts = timestamp

        animation_dt = (
            timestamp - self._last_animation_ts
            if self._last_animation_ts > 0.0
            and 0.0 < timestamp - self._last_animation_ts < 1.0
            else 0.0
        )
        if playing and animation_enabled:
            self._animation_time += animation_dt
        self._last_animation_ts = timestamp

        frame_changed = (
            _changed(previous_bars, resolved_bars)
            or _changed(peaks_before, peaks)
            or bool(animation_dt > 0.0 and playing and animation_enabled)
        )
        ghost_bars = tuple(peaks) if ghosting_enabled else ()
        return SpectrumResolvedFrame(
            bars=tuple(resolved_bars),
            peaks=tuple(peaks),
            ghost_bars=ghost_bars,
            animation_time=float(self._animation_time),
            changed=frame_changed,
            reactive_source_ready=source_ready,
        )


__all__ = ["SpectrumFrameRuntime", "SpectrumResolvedFrame"]
