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
from widgets.spotify_visualizer.spectrum_temporal_contract import (
    SPECTRUM_PAUSE_TO_IDLE_SECONDS,
    SPECTRUM_SETTLED_EPSILON,
    SPECTRUM_STALL_SNAP_SECONDS,
    advance_idle_spectrum_travel_position,
    idle_spectrum_baseline,
    idle_spectrum_travel_scene,
    spectrum_visual_alpha,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    apply_spectrum_solid_hysteresis,
    canonical_spectrum_solid_hysteresis_segments,
    reset_spectrum_solid_hysteresis_state,
)



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
        abs(float(before) - float(after)) > SPECTRUM_SETTLED_EPSILON
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
        self._last_playing: bool | None = None
        self._pause_transition_started_ts = 0.0
        self._pause_transition_origin: list[float] = []
        self._idle_travel_position = -1.0
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
        self._last_playing = None
        self._pause_transition_started_ts = 0.0
        self._pause_transition_origin = []
        self._idle_travel_position = -1.0
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
        is_playing = bool(playing)
        pause_edge = self._last_playing is True and not is_playing
        idle_dt = (
            timestamp - self._presentation_last_ts
            if self._presentation_last_ts > 0.0
            and 0.0 < timestamp - self._presentation_last_ts < 1.0
            else 0.0
        )

        if not is_playing:
            # Spectrum's idle scene is presentation-owned. On a real playback
            # pause edge only, preserve the last live bars and ease them slowly
            # into that scene. Natural low-energy drops while `playing` remains
            # true stay on the existing source/smoothing path below.
            if pause_edge and len(previous_bars) == count:
                self._pause_transition_started_ts = timestamp
                self._pause_transition_origin = list(previous_bars)
                self._idle_travel_position = -1.0
            elif self._last_playing is None:
                # Cold/initial paused presentation is already idle; do not fake
                # a pause transition from an absent source.
                self._pause_transition_started_ts = 0.0
                self._pause_transition_origin = []
                self._idle_travel_position = -1.0

            self._idle_travel_position = advance_idle_spectrum_travel_position(
                self._idle_travel_position,
                bar_count=count,
                dt_seconds=idle_dt,
            )
            idle_scene = idle_spectrum_travel_scene(
                count,
                self._idle_travel_position,
            )
            if (
                self._pause_transition_started_ts > 0.0
                and len(self._pause_transition_origin) == count
            ):
                elapsed = max(0.0, timestamp - self._pause_transition_started_ts)
                progress = min(
                    1.0,
                    elapsed / max(SPECTRUM_PAUSE_TO_IDLE_SECONDS, 1.0e-6),
                )
                # Smoothstep gives the pause edge a deliberately soft initial
                # release without changing the steady-state/natural drop law.
                eased = progress * progress * (3.0 - 2.0 * progress)
                resolved_bars = [
                    origin + (target - origin) * eased
                    for origin, target in zip(
                        self._pause_transition_origin, idle_scene
                    )
                ]
                if progress >= 1.0:
                    self._pause_transition_started_ts = 0.0
                    self._pause_transition_origin = []
            else:
                resolved_bars = idle_scene
        elif not source_ready:
            self._pause_transition_started_ts = 0.0
            self._pause_transition_origin = []
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
            self._pause_transition_started_ts = 0.0
            self._pause_transition_origin = []
            resolved_bars = values
        else:
            self._pause_transition_started_ts = 0.0
            self._pause_transition_origin = []
            last_ts = self._presentation_last_ts
            dt = timestamp - last_ts
            reset_boundary = bool(
                first_frame
                or self._presentation_identity != presentation_identity
                or len(previous_bars) != len(values)
                or dt <= 0.0
                or dt >= SPECTRUM_STALL_SNAP_SECONDS
            )
            if reset_boundary:
                resolved_bars = values
            else:
                # Spectrum motion is vertical.  Preserve canonical/wide
                # temporal behaviour exactly, but lengthen the existing
                # presentation-only one-pole on tall viewport extents so the
                # same normalized source step does not become a proportionally
                # larger screen-pixel jump.  This is not source/DSP smoothing.
                alpha = spectrum_visual_alpha(
                    dt,
                    strength,
                    viewport_height=viewport_height,
                )
                resolved_bars = []
                for prior, target in zip(previous_bars, values):
                    next_value = prior + (target - prior) * alpha
                    if abs(target - next_value) <= SPECTRUM_SETTLED_EPSILON:
                        next_value = target
                    resolved_bars.append(next_value)

        self._presentation_bars = list(resolved_bars)
        self._presentation_last_ts = timestamp
        self._presentation_identity = presentation_identity

        if single_piece and resolved_bars:
            # Solid-bar hysteresis is authored temporal state, not renderer
            # geometry.  Its old segment domain tracked viewport height, so a
            # tall resize changed rate zones/reset state even though the source
            # signal was identical.  Keep that internal domain canonical; the
            # Quick renderer remains free to choose its own height-derived
            # segment count for segmented presentation.
            resolved_bars = apply_spectrum_solid_hysteresis(
                self,
                resolved_bars,
                segments=canonical_spectrum_solid_hysteresis_segments(),
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
        self._last_playing = is_playing
        return SpectrumResolvedFrame(
            bars=tuple(resolved_bars),
            peaks=tuple(peaks),
            ghost_bars=ghost_bars,
            animation_time=float(self._animation_time),
            changed=frame_changed,
            reactive_source_ready=source_ready,
        )


__all__ = ["SpectrumFrameRuntime", "SpectrumResolvedFrame"]
