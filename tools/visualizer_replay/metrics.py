"""Quantitative v1 metric definitions, independent of any presenter.

Recovered from the pre-cutover replay metric calculator; no exact-frame oracle.
"""
from __future__ import annotations
from dataclasses import asdict
import math
from typing import Any, Mapping, Sequence

def _round_float(value: Any, digits: int = 7) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite replay metric")
    if abs(number) < 0.5 * (10.0 ** -digits):
        return 0.0
    return round(number, digits)

def _normalise(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return _round_float(value)
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return _normalise(asdict(value))
    return str(value)

def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0

def calculate_metrics(frames: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Calculate deterministic response, decay, continuity, and mode metrics."""
    timestamps = [int(frame.get("timestamp_us", 0)) for frame in frames]
    bar_means: list[float] = []
    bar_peaks: list[float] = []
    input_energy: list[float] = []
    centroids: list[float] = []
    waveform_values: list[float] = []
    state_derivatives: list[float] = []
    total_flux = 0.0
    integrated_energy = 0.0
    zero_crossings = 0
    beat_count = 0
    onset_count = 0
    previous_bars: list[float] | None = None
    mode_summary: dict[str, dict[str, float]] = {}
    bubble_speed_peak = 0.0
    bubble_radius_peak = 0.0
    bubble_particle_peak = 0
    bubble_mean_radii: list[float] = []
    bubble_centroids: list[tuple[float, float]] = []
    bubble_counts: list[int] = []

    for index, frame in enumerate(frames):
        bars = [float(value) for value in frame.get("display_bars", [])]
        bar_mean = _mean(bars)
        bar_peak = max(bars, default=0.0)
        bar_means.append(bar_mean)
        bar_peaks.append(bar_peak)

        continuous = frame.get("energy_lanes", {}).get("continuous", {})
        input_energy.append(float(continuous.get("overall", 0.0)))

        if previous_bars is not None:
            absolute_delta = sum(
                abs(current - previous)
                for current, previous in zip(bars, previous_bars)
            )
            total_flux += absolute_delta
            rms_delta = math.sqrt(
                _mean(
                    [
                        (current - previous) ** 2
                        for current, previous in zip(bars, previous_bars)
                    ]
                )
            )
            delta_seconds = max(
                1e-6,
                (timestamps[index] - timestamps[index - 1]) / 1_000_000.0,
            )
            state_derivatives.append(rms_delta / delta_seconds)
            integrated_energy += (
                bar_means[index - 1] + bar_mean
            ) * 0.5 * delta_seconds
        previous_bars = bars

        denominator = sum(bars)
        centroids.append(
            sum(position * value for position, value in enumerate(bars))
            / denominator
            if denominator > 0.0
            else 0.0
        )

        waveform = [float(value) for value in frame.get("waveform", [])]
        waveform_values.extend(waveform)
        zero_crossings += sum(
            1
            for left, right in zip(waveform, waveform[1:])
            if (left < 0.0 <= right) or (left > 0.0 >= right)
        )

        transient = frame.get("energy_lanes", {}).get("transient", {})
        if transient.get("onset_detected"):
            onset_count += 1
            if transient.get("onset_type") == "bass":
                beat_count += 1

        mode = str(frame.get("overlay", {}).get("mode", "unknown"))
        summary = mode_summary.setdefault(
            mode,
            {"frames": 0.0, "activity": 0.0},
        )
        summary["frames"] += 1.0
        summary["activity"] += bar_mean

        particles = frame.get("bubble_simulation", {}).get("particles", [])
        bubble_particle_peak = max(bubble_particle_peak, len(particles))
        bubble_counts.append(len(particles))
        frame_radii: list[float] = []
        frame_x: list[float] = []
        frame_y: list[float] = []
        for particle in particles:
            vx = float(particle.get("vx", 0.0)) + float(
                particle.get("impulse_vx", 0.0)
            )
            vy = float(particle.get("vy", 0.0)) + float(
                particle.get("impulse_vy", 0.0)
            )
            bubble_speed_peak = max(
                bubble_speed_peak,
                math.hypot(vx, vy),
            )
            radius = max(
                float(particle.get("display_radius", 0.0)),
                float(particle.get("radius", 0.0)),
            )
            bubble_radius_peak = max(bubble_radius_peak, radius)
            frame_radii.append(radius)
            frame_x.append(float(particle.get("x", 0.0)))
            frame_y.append(float(particle.get("y", 0.0)))
        bubble_mean_radii.append(_mean(frame_radii))
        bubble_centroids.append((_mean(frame_x), _mean(frame_y)))

    global_peak = max(bar_peaks, default=0.0)
    peak_index = bar_peaks.index(global_peak) if bar_peaks else 0
    input_peak = max(input_energy, default=0.0)
    input_start_index = next(
        (index for index, value in enumerate(input_energy) if value > 0.02),
        None,
    )
    response_index = None
    if input_start_index is not None:
        response_index = next(
            (
                index
                for index in range(input_start_index, len(bar_peaks))
                if bar_peaks[index] > 0.02
            ),
            None,
        )

    response_latency_ms = -1.0
    time_to_peak_ms = -1.0
    attack_slope_per_s = 0.0
    if input_start_index is not None and timestamps:
        if response_index is not None:
            response_latency_ms = (
                timestamps[response_index] - timestamps[input_start_index]
            ) / 1_000.0
        if peak_index >= input_start_index:
            time_to_peak_ms = (
                timestamps[peak_index] - timestamps[input_start_index]
            ) / 1_000.0
            if time_to_peak_ms > 0.0:
                attack_seconds = time_to_peak_ms / 1_000.0
            elif input_start_index + 1 < len(timestamps):
                attack_seconds = max(
                    1e-6,
                    (
                        timestamps[input_start_index + 1]
                        - timestamps[input_start_index]
                    )
                    / 1_000_000.0,
                )
            else:
                attack_seconds = 1e-6
            attack_slope_per_s = global_peak / attack_seconds

    half_peak = global_peak * 0.5
    decay_frames = 0
    decay_to_half_ms = -1.0
    if global_peak > 0.0:
        for offset, value in enumerate(bar_peaks[peak_index + 1 :], start=1):
            if value <= half_peak:
                decay_frames = offset
                decay_to_half_ms = (
                    timestamps[peak_index + offset] - timestamps[peak_index]
                ) / 1_000.0
                break

    settling_time_ms = -1.0
    settling_threshold = max(0.01, global_peak * 0.05)
    for index in range(peak_index, len(bar_peaks)):
        if all(value <= settling_threshold for value in bar_peaks[index:]):
            settling_time_ms = (
                timestamps[index] - timestamps[peak_index]
            ) / 1_000.0
            break

    for summary in mode_summary.values():
        summary["activity"] = _round_float(
            summary["activity"] / max(1.0, summary["frames"])
        )
        summary["frames"] = int(summary["frames"])

    bubble_centroid_speed_peak = 0.0
    bubble_radius_change_peak_per_s = 0.0
    bubble_count_change_peak = 0
    for index in range(1, len(frames)):
        delta_seconds = max(
            1e-6,
            (timestamps[index] - timestamps[index - 1]) / 1_000_000.0,
        )
        bubble_count_change_peak = max(
            bubble_count_change_peak,
            abs(bubble_counts[index] - bubble_counts[index - 1]),
        )
        if bubble_counts[index] and bubble_counts[index - 1]:
            previous_centroid = bubble_centroids[index - 1]
            current_centroid = bubble_centroids[index]
            bubble_centroid_speed_peak = max(
                bubble_centroid_speed_peak,
                math.hypot(
                    current_centroid[0] - previous_centroid[0],
                    current_centroid[1] - previous_centroid[1],
                )
                / delta_seconds,
            )
            bubble_radius_change_peak_per_s = max(
                bubble_radius_change_peak_per_s,
                abs(
                    bubble_mean_radii[index]
                    - bubble_mean_radii[index - 1]
                )
                / delta_seconds,
            )

    bubble_radius_excursion = 0.0
    bubble_radius_overshoot_ratio = 0.0
    bubble_radius_settling_time_ms = -1.0
    bubble_radius_rebound_count = 0
    if bubble_particle_peak > 0 and bubble_mean_radii:
        radius_min = min(bubble_mean_radii)
        radius_peak = max(bubble_mean_radii)
        radius_peak_index = bubble_mean_radii.index(radius_peak)
        radius_final = bubble_mean_radii[-1]
        bubble_radius_excursion = radius_peak - radius_min
        if radius_final > 0.0:
            bubble_radius_overshoot_ratio = max(
                0.0,
                (radius_peak - radius_final) / radius_final,
            )
        settle_threshold = max(1e-5, bubble_radius_excursion * 0.05)
        for index in range(radius_peak_index, len(bubble_mean_radii)):
            if all(
                abs(value - radius_final) <= settle_threshold
                for value in bubble_mean_radii[index:]
            ):
                bubble_radius_settling_time_ms = (
                    timestamps[index] - timestamps[radius_peak_index]
                ) / 1_000.0
                break
        derivative_signs = []
        derivative_floor = max(1e-6, settle_threshold * 0.1)
        for left, right in zip(
            bubble_mean_radii[radius_peak_index:],
            bubble_mean_radii[radius_peak_index + 1 :],
        ):
            delta = right - left
            if abs(delta) > derivative_floor:
                derivative_signs.append(1 if delta > 0.0 else -1)
        bubble_radius_rebound_count = sum(
            left != right
            for left, right in zip(derivative_signs, derivative_signs[1:])
        )

    waveform_rms = math.sqrt(
        _mean([value * value for value in waveform_values])
    )
    derivative_max = max(state_derivatives, default=0.0)
    discontinuity_threshold = max(12.0, derivative_max * 0.75)
    discontinuity_count = sum(
        value >= discontinuity_threshold for value in state_derivatives
    )

    return _normalise(
        {
            "bar_mean": _mean(bar_means),
            "bar_peak": global_peak,
            "bar_flux": total_flux,
            "bar_centroid": _mean(centroids),
            "integrated_bar_energy": integrated_energy,
            "input_peak": input_peak,
            "response_frame": -1 if response_index is None else response_index,
            "response_latency_ms": response_latency_ms,
            "time_to_peak_ms": time_to_peak_ms,
            "attack_slope_per_s": attack_slope_per_s,
            "overshoot_ratio": global_peak / input_peak if input_peak > 0.0 else 0.0,
            "decay_to_half_frames": decay_frames,
            "decay_to_half_ms": decay_to_half_ms,
            "settling_time_ms": settling_time_ms,
            "state_derivative_max_per_s": derivative_max,
            "discontinuity_count": discontinuity_count,
            "waveform_rms": waveform_rms,
            "waveform_peak": max(
                (abs(value) for value in waveform_values),
                default=0.0,
            ),
            "waveform_zero_crossings": zero_crossings,
            "beat_count": beat_count,
            "onset_count": onset_count,
            "bubble_particle_peak": bubble_particle_peak,
            "bubble_speed_peak": bubble_speed_peak,
            "bubble_radius_peak": bubble_radius_peak,
            "bubble_centroid_speed_peak": bubble_centroid_speed_peak,
            "bubble_radius_change_peak_per_s": bubble_radius_change_peak_per_s,
            "bubble_count_change_peak": bubble_count_change_peak,
            "bubble_radius_excursion": bubble_radius_excursion,
            "bubble_radius_overshoot_ratio": bubble_radius_overshoot_ratio,
            "bubble_radius_settling_time_ms": bubble_radius_settling_time_ms,
            "bubble_radius_rebound_count": bubble_radius_rebound_count,
            "mode_summary": mode_summary,
        }
    )
