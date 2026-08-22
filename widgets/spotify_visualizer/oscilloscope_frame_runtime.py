"""Authored Oscilloscope state advanced by the sole logical clock."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from widgets.spotify_visualizer.frame_runtime_lifecycle import (
    RetirableFrameRuntime,
    retirement_fenced,
)
from widgets.spotify_visualizer.oscilloscope_contract import (
    advance_ghost_ring,
    blend_waveform,
    condition_live_waveform,
    resolve_transient_sensitivity_modulation,
)
from widgets.spotify_visualizer.render_state import VisualizerEnergyState


_MAX_WAVEFORM_SAMPLES = 256
_SETTLED_EPSILON = 1.0e-5


def _clamp(value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    if not math.isfinite(number):
        return minimum
    return max(minimum, min(maximum, number))


def _waveform(values: Sequence[object]) -> list[float]:
    return [
        _clamp(value, -1.0, 1.0)
        for value in values[:_MAX_WAVEFORM_SAMPLES]
    ]


def _sequence_changed(
    previous: Sequence[float],
    current: Sequence[float],
) -> bool:
    return len(previous) != len(current) or any(
        abs(float(before) - float(after)) > _SETTLED_EPSILON
        for before, after in zip(previous, current)
    )


@dataclass(frozen=True, slots=True)
class OscilloscopeResolvedFrame:
    waveform: tuple[float, ...]
    waveform_count: int
    previous_waveform: tuple[float, ...]
    energy: VisualizerEnergyState
    resolved_sensitivity: float
    animation_time: float
    changed: bool
    reactive_source_ready: bool


class OscilloscopeFrameRuntime(RetirableFrameRuntime):
    """Small Oscilloscope-only state owner with no Qt/render authority."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()

    def reset(self) -> None:
        self._waveform: list[float] = []
        self._waveform_count = 0
        self._previous_waveform: list[float] = []
        self._ghost_waveform_ring: list[list[float]] = []
        self._ghost_ring_index = 0
        self._smoothed_energy = VisualizerEnergyState()
        self._kick_envelope = 0.0
        self._snare_envelope = 0.0
        self._resolved_sensitivity = 0.0
        self._animation_time = 0.0
        self._last_timestamp = 0.0
        self._last_playing: bool | None = None
        self._activation_identity: tuple[int, int, int] | None = None

    @retirement_fenced
    def resolve(
        self,
        source_waveform: Sequence[object],
        *,
        waveform_count: int,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_generation: int,
        source_activation_id: int,
        playing: bool,
        line_speed: float,
        ghosting_enabled: bool,
        ghost_decay: float,
        energy: VisualizerEnergyState,
        kick_event: float,
        snare_event: float,
        transient_width_mix: float,
        base_sensitivity: float,
        animation_enabled: bool,
    ) -> OscilloscopeResolvedFrame | None:
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
        previous_body = list(self._waveform)
        previous_ghost = list(self._previous_waveform)
        previous_energy = self._smoothed_energy
        previous_sensitivity = self._resolved_sensitivity

        dt = 0.0
        if self._last_timestamp > 0.0:
            candidate = timestamp - self._last_timestamp
            if 0.0 < candidate < 1.0:
                dt = candidate

        is_playing = bool(playing)
        playback_changed = (
            self._last_playing is not None
            and is_playing != self._last_playing
        )
        ghost_enabled = bool(ghosting_enabled)
        if playback_changed:
            old_body = list(self._waveform)
            self._waveform = []
            self._waveform_count = 0
            if not is_playing and old_body and ghost_enabled:
                self._previous_waveform = old_body
                self._ghost_waveform_ring = [old_body]
            else:
                self._previous_waveform = []
                self._ghost_waveform_ring = []
            self._ghost_ring_index = 0
            self._kick_envelope = 0.0
            self._snare_envelope = 0.0

        if not ghost_enabled:
            self._previous_waveform = []
            self._ghost_waveform_ring = []
            self._ghost_ring_index = 0

        incoming = _waveform(source_waveform)
        requested_count = max(0, int(waveform_count))
        if source_ready:
            delay_frames = max(
                2,
                min(18, int(round(2.0 + _clamp(ghost_decay, 0.1, 1.0) * 16.0))),
            )
            if self._waveform and ghost_enabled:
                (
                    self._previous_waveform,
                    self._ghost_ring_index,
                ) = advance_ghost_ring(
                    self._ghost_waveform_ring,
                    self._ghost_ring_index,
                    self._waveform,
                    delay_frames,
                )
            conditioned = (
                condition_live_waveform(self._waveform, incoming)
                if is_playing
                else incoming
            )
            self._waveform = blend_waveform(
                self._waveform,
                conditioned,
                _clamp(line_speed, 0.01, 1.0),
            )
            self._waveform_count = min(
                requested_count,
                len(self._waveform),
                _MAX_WAVEFORM_SAMPLES,
            )

        target_energy = energy if source_ready else VisualizerEnergyState()
        smoothed: dict[str, float] = {}
        for name in ("bass", "mid", "high"):
            prior = _clamp(getattr(self._smoothed_energy, name), 0.0, 1.0)
            target = _clamp(getattr(target_energy, name), 0.0, 1.0)
            if dt > 0.0:
                time_constant = 0.06 if target > prior else 0.12
                alpha = min(1.0, dt / time_constant)
                prior += (target - prior) * alpha
            smoothed[name] = prior
        smoothed["overall"] = _clamp(target_energy.overall, 0.0, 1.0)
        self._smoothed_energy = VisualizerEnergyState(**smoothed)

        kick_target = _clamp(kick_event, 0.0, 1.0) if source_ready else 0.0
        snare_target = _clamp(snare_event, 0.0, 1.0) if source_ready else 0.0
        if dt > 0.0:
            kick_tau = 0.14 if kick_target < self._kick_envelope else 0.04
            snare_tau = 0.16 if snare_target < self._snare_envelope else 0.05
            self._kick_envelope += (
                kick_target - self._kick_envelope
            ) * min(1.0, dt / kick_tau)
            self._snare_envelope += (
                snare_target - self._snare_envelope
            ) * min(1.0, dt / snare_tau)
        else:
            self._kick_envelope = kick_target
            self._snare_envelope = snare_target

        sensitivity, _drive = resolve_transient_sensitivity_modulation(
            base_sensitivity=base_sensitivity,
            smoothed_bass=self._smoothed_energy.bass,
            kick_event=self._kick_envelope,
            snare_event=self._snare_envelope,
            width_mix=transient_width_mix,
        )
        self._resolved_sensitivity = float(sensitivity)
        if dt > 0.0:
            self._animation_time += dt

        body = tuple(self._waveform)
        ghost = tuple(self._previous_waveform) if ghost_enabled else ()
        changed = bool(
            _sequence_changed(previous_body, body)
            or _sequence_changed(previous_ghost, ghost)
            or previous_energy != self._smoothed_energy
            or abs(previous_sensitivity - sensitivity) > _SETTLED_EPSILON
            or (animation_enabled and dt > 0.0)
        )
        self._last_timestamp = timestamp
        self._last_playing = is_playing
        return OscilloscopeResolvedFrame(
            waveform=body,
            waveform_count=self._waveform_count,
            previous_waveform=ghost,
            energy=self._smoothed_energy,
            resolved_sensitivity=float(sensitivity),
            animation_time=float(self._animation_time),
            changed=changed,
            reactive_source_ready=source_ready,
        )


__all__ = ["OscilloscopeFrameRuntime", "OscilloscopeResolvedFrame"]
