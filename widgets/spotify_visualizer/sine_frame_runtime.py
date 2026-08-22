"""Authored Sine Wave state advanced by the sole logical clock."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from widgets.spotify_visualizer.frame_runtime_lifecycle import (
    RetirableFrameRuntime,
    retirement_fenced,
)
from widgets.spotify_visualizer.render_state import VisualizerEnergyState
from widgets.spotify_visualizer.sine_reactivity import (
    advance_sine_reactivity,
    compute_sine_reactivity_targets,
)


_SETTLED_EPSILON = 1.0e-5
_LINE_COUNT = 6


def _clamp(value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    if not math.isfinite(number):
        return minimum
    return max(minimum, min(maximum, number))


def _travel_values(values: Sequence[object]) -> list[int]:
    resolved = [max(0, min(2, int(value))) for value in values[:_LINE_COUNT]]
    resolved.extend([0] * (_LINE_COUNT - len(resolved)))
    return resolved


def _line_shift_values(values: Sequence[object]) -> list[float]:
    resolved = [_clamp(value, -1.0, 1.0) for value in values[:_LINE_COUNT]]
    resolved.extend([0.0] * (_LINE_COUNT - len(resolved)))
    return resolved


def _energy_changed(
    before: VisualizerEnergyState,
    after: VisualizerEnergyState,
) -> bool:
    return any(
        abs(float(getattr(before, name)) - float(getattr(after, name)))
        > _SETTLED_EPSILON
        for name in ("bass", "mid", "high", "overall")
    )


@dataclass(frozen=True, slots=True)
class SineResolvedFrame:
    energy: VisualizerEnergyState
    ghost_energy: VisualizerEnergyState
    heartbeat_intensity: float
    animation_time: float
    line_speed: float
    travels: tuple[int, ...]
    line_shifts: tuple[float, ...]
    sensitivity: float
    width_reaction: float
    wave_effect_gate: float
    changed: bool
    reactive_source_ready: bool


class SineFrameRuntime(RetirableFrameRuntime):
    """Small Sine-only state owner with no Qt/render authority."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()

    def reset(self) -> None:
        self._smoothed_energy = VisualizerEnergyState()
        self._kick_envelope = 0.0
        self._snare_envelope = 0.0
        self._reactivity: dict[str, float] = {}
        self._ghost_energy = VisualizerEnergyState()
        self._ghost_peak_hold_remaining = 0.0
        self._idle_shift_phase = 0.0
        self._animation_time = 0.0
        self._last_timestamp = 0.0
        self._last_playing: bool | None = None
        self._last_line_speed = 0.0
        self._last_travels = (0,) * _LINE_COUNT
        self._last_line_shifts = (0.0,) * _LINE_COUNT
        self._activation_identity: tuple[int, int, int] | None = None

    @retirement_fenced
    def resolve(
        self,
        *,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_generation: int,
        source_activation_id: int,
        playing: bool,
        energy: VisualizerEnergyState,
        kick_event: float,
        snare_event: float,
        ghosting_enabled: bool,
        ghost_decay: float,
        line_count: int,
        line_speed: float,
        travels: Sequence[object],
        line_shifts: Sequence[object],
        transient_width_mix: float,
        base_width_reaction: float,
        base_sensitivity: float,
        base_heartbeat: float,
        heartbeat_slider: float,
    ) -> SineResolvedFrame | None:
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
        previous_energy = self._smoothed_energy
        previous_ghost = self._ghost_energy
        previous_reactivity = dict(self._reactivity)
        previous_animation_time = self._animation_time

        dt = 0.0
        if self._last_timestamp > 0.0:
            candidate = timestamp - self._last_timestamp
            if 0.0 < candidate < 1.0:
                dt = candidate

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
        elif not self._reactivity:
            self._kick_envelope = kick_target
            self._snare_envelope = snare_target

        targets = compute_sine_reactivity_targets(
            smoothed_bass=self._smoothed_energy.bass,
            smoothed_mid=self._smoothed_energy.mid,
            smoothed_high=self._smoothed_energy.high,
            overall_energy=self._smoothed_energy.overall,
            kick_event=self._kick_envelope,
            snare_event=self._snare_envelope,
            transient_width_mix=transient_width_mix,
            base_width_reaction=base_width_reaction,
            base_sensitivity=base_sensitivity,
            base_heartbeat=base_heartbeat if source_ready else 0.0,
            heartbeat_slider=heartbeat_slider,
        )
        if not self._reactivity:
            self._reactivity = advance_sine_reactivity(None, targets, dt=1.0 / 60.0)
        elif dt > 0.0:
            self._reactivity = advance_sine_reactivity(
                self._reactivity,
                targets,
                dt=max(1.0 / 240.0, min(0.050, dt)),
            )

        ghost_active = bool(ghosting_enabled)
        if not ghost_active:
            self._ghost_energy = VisualizerEnergyState()
            self._ghost_peak_hold_remaining = 0.0
        elif dt > 0.0:
            peak_bass = self._ghost_energy.bass
            peak_mid = self._ghost_energy.mid
            peak_high = self._ghost_energy.high
            decay_tau = max(
                0.3,
                3.0 - _clamp(ghost_decay, 0.1, 1.0) * 2.5,
            )
            if source_ready:
                raw_bass = _clamp(target_energy.bass, 0.0, 1.0)
                raw_mid = _clamp(target_energy.mid, 0.0, 1.0)
                raw_high = _clamp(target_energy.high, 0.0, 1.0)
                any_peak = False
                if raw_bass > peak_bass:
                    peak_bass = raw_bass
                    any_peak = True
                if raw_mid > peak_mid:
                    peak_mid = raw_mid
                    any_peak = True
                if raw_high > peak_high:
                    peak_high = raw_high
                    any_peak = True
                if any_peak:
                    self._ghost_peak_hold_remaining = 0.12
                if self._ghost_peak_hold_remaining > 0.0:
                    self._ghost_peak_hold_remaining = max(
                        0.0,
                        self._ghost_peak_hold_remaining - dt,
                    )
                else:
                    alpha = min(1.0, dt / decay_tau)
                    peak_bass += (raw_bass - peak_bass) * alpha
                    peak_mid += (raw_mid - peak_mid) * alpha
                    peak_high += (raw_high - peak_high) * alpha
                minimum_offset = max(0.40, self._smoothed_energy.bass * 0.50)
                peak_bass = max(peak_bass, raw_bass + minimum_offset)
                peak_mid = max(peak_mid, raw_mid + minimum_offset * 0.90)
                peak_high = max(peak_high, raw_high + minimum_offset * 0.80)
            else:
                self._ghost_peak_hold_remaining = 0.0
                alpha = min(1.0, dt / decay_tau)
                peak_bass += (0.0 - peak_bass) * alpha
                peak_mid += (0.0 - peak_mid) * alpha
                peak_high += (0.0 - peak_high) * alpha
            self._ghost_energy = VisualizerEnergyState(
                bass=peak_bass,
                mid=peak_mid,
                high=peak_high,
                overall=0.0,
            )

        resolved_travels = _travel_values(travels)
        resolved_shifts = _line_shift_values(line_shifts)
        resolved_speed = _clamp(line_speed, 0.0, 3.0)
        is_playing = bool(playing)
        if not is_playing:
            resolved_speed = max(0.22, resolved_speed)
            active_lines = max(1, min(_LINE_COUNT, int(line_count)))
            preferred = next(
                (value for value in resolved_travels if value in (1, 2)),
                2,
            )
            for index in range(active_lines):
                if resolved_travels[index] == 0:
                    resolved_travels[index] = preferred
            idle_dt = 0.0
            if self._last_playing is None:
                idle_dt = 1.0 / 60.0
            elif dt > 0.0:
                idle_dt = max(1.0 / 240.0, min(0.100, dt))
            self._idle_shift_phase = math.fmod(
                self._idle_shift_phase + idle_dt * (0.12 * resolved_speed),
                1.0,
            )
            for index, travel in enumerate(resolved_travels):
                if travel == 1:
                    resolved_shifts[index] += self._idle_shift_phase
                elif travel == 2:
                    resolved_shifts[index] -= self._idle_shift_phase

        if dt > 0.0:
            self._animation_time += dt

        energy_out = VisualizerEnergyState(
            bass=self._reactivity["bass_energy"],
            mid=self._reactivity["mid_energy"],
            high=self._reactivity["high_energy"],
            overall=self._reactivity["overall_energy"],
        )
        travels_out = tuple(resolved_travels)
        shifts_out = tuple(resolved_shifts)
        changed = bool(
            _energy_changed(previous_energy, self._smoothed_energy)
            or _energy_changed(previous_ghost, self._ghost_energy)
            or previous_reactivity != self._reactivity
            or abs(previous_animation_time - self._animation_time)
            > _SETTLED_EPSILON
            or abs(self._last_line_speed - resolved_speed) > _SETTLED_EPSILON
            or self._last_travels != travels_out
            or any(
                abs(before - after) > _SETTLED_EPSILON
                for before, after in zip(self._last_line_shifts, shifts_out)
            )
            or self._last_playing is None
            or self._last_playing != is_playing
        )
        self._last_timestamp = timestamp
        self._last_playing = is_playing
        self._last_line_speed = resolved_speed
        self._last_travels = travels_out
        self._last_line_shifts = shifts_out
        return SineResolvedFrame(
            energy=energy_out,
            ghost_energy=self._ghost_energy,
            heartbeat_intensity=self._reactivity["heartbeat_intensity"],
            animation_time=self._animation_time,
            line_speed=resolved_speed,
            travels=travels_out,
            line_shifts=shifts_out,
            sensitivity=self._reactivity["sensitivity"],
            width_reaction=self._reactivity["width_reaction"],
            wave_effect_gate=self._reactivity["wave_effect_gate"],
            changed=changed,
            reactive_source_ready=source_ready,
        )


__all__ = ["SineFrameRuntime", "SineResolvedFrame"]
