"""Behaviour at other logical cadences: python -m tools.visualizer_replay.cadence_parity [--modes bubble ...]

Current_Plan N1b option A matches the logical cadence to the presenting display (165 Hz on a 165 Hz display,
120 Hz on a 60 Hz one) instead of the authored 90 Hz. That is acceptable only if reaction, smoothness and
elasticity are unchanged. This replays each v1 fixture (and the local recordings, for the real-scale modes)
resampled to 90 / 120 / 165 Hz by holding each recorded frame (its onsets and control events stay on the first
copy) through frozen settings, and reports the protected metrics per rate with their change against 90 Hz.
"""
from __future__ import annotations

import argparse
import dataclasses

from .driver import load_clips, replay_clip
from .metrics import calculate_metrics

RATES = (90.0, 120.0, 165.0)
KEYS = {
    "bubble": ("response_latency_ms", "attack_slope_per_s", "decay_to_half_ms", "overshoot_ratio",
               "bubble_centroid_speed_peak", "bubble_radius_change_peak_per_s", "bubble_radius_excursion",
               "bubble_radius_overshoot_ratio", "bubble_radius_settling_time_ms", "bubble_radius_peak",
               "bubble_particle_peak"),
    "default": ("response_latency_ms", "attack_slope_per_s", "decay_to_half_ms", "overshoot_ratio",
                "settling_time_ms", "bar_mean", "bar_peak", "state_derivative_max_per_s"),
}


def resample(clip, rate_hz: float):
    """``clip`` ticked at ``rate_hz``: each tick holds the latest recorded frame."""
    frames = clip.frames
    step_us = int(round(1_000_000 / rate_hz))
    start, end = frames[0].timestamp_us, frames[-1].timestamp_us
    out, index, last_used = [], 0, -1
    t = start
    while t <= end:
        while index + 1 < len(frames) and frames[index + 1].timestamp_us <= t:
            index += 1
        frame = frames[index]
        held = index == last_used
        changes = {"timestamp_us": t}
        if held:
            changes["control_event"] = "none"
            if frame.real is not None and frame.real.onsets:
                changes["real"] = dataclasses.replace(frame.real, onsets=())
        out.append(dataclasses.replace(frame, **changes))
        last_used = index
        t += step_us
    return dataclasses.replace(clip, frames=tuple(out))


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    from tools.freeze_visualizer_settings import load_frozen

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modes", nargs="*", default=["bubble"])
    parser.add_argument("--clips", nargs="*", default=None)
    args = parser.parse_args()
    QCoreApplication.instance() or QCoreApplication([])
    clips = load_clips()
    for mode in args.modes:
        keys = KEYS.get(mode, KEYS["default"])
        for name, clip in clips.items():
            if args.clips and name not in args.clips:
                continue
            if name == "mode_visibility_switch":
                continue
            by_rate = {}
            for rate in RATES:
                result = replay_clip(resample(clip, rate), mode, settings=load_frozen)
                by_rate[rate] = calculate_metrics(result["frames"])
            base = by_rate[RATES[0]]
            print(f"== {mode} {name}")
            for key in keys:
                values = [float(by_rate[rate].get(key, 0.0)) for rate in RATES]
                ref = values[0]
                deltas = " ".join(
                    f"{(v - ref) / abs(ref):+6.1%}" if abs(ref) > 1e-9 else ("  same" if abs(v) < 1e-9 else "   n/a")
                    for v in values[1:])
                print(f"  {key:34s} " + " ".join(f"{v:10.4f}" for v in values) + f"   {deltas}")


if __name__ == "__main__":
    main()
