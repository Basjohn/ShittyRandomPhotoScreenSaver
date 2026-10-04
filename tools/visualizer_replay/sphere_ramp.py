"""Sphere reaction ramp on recorded music: python -m tools.visualizer_replay.sphere_ramp [--preset N]

Replays every schema 2 clip in ``logs/visualizer_recordings`` (archived takes excluded) through
Voxel Sphere's production capture and reports, per band of passage intensity (where the music sits
in the track's own dynamic range, ``PassageIntensity``: <0.35 quiet, 0.35-0.75 usual, >0.75 loud),
how often and how strongly each reaction fires: fragment bursts (the fragmentation starting to
rise), particle cohort launches, tracer, spin and body growth. A healthy ramp grows from quiet to loud in both
rate and size.
"""
from __future__ import annotations

import argparse
import statistics

from .driver import replay_clip

BANDS = (("quiet <0.35", 0.0, 0.35), ("usual .35-.75", 0.35, 0.75), ("loud >0.75", 0.75, 9.0))
FRAME_S = 0.011111


def measure(clip, preset: int) -> dict:
    from widgets.spotify_visualizer.transient_bus import PassageIntensity

    result = replay_clip(clip, "sphere", preset=preset)
    rows = result["frames"]
    follower, last_us, intensities = PassageIntensity(), None, []
    for feature in clip.frames:
        step = 0.0 if last_us is None else (feature.timestamp_us - last_us) / 1e6
        last_us = feature.timestamp_us
        intensities.append(follower.update(feature.real.musical_level[0], step))
    stats = {name: {"frames": 0, "bursts": [], "launches": [], "tracer": [], "spin": [], "body": []} for name, *_ in BANDS}
    previous_drives = None
    previous_cohorts = 0
    rising = False
    for feature, row, intensity in zip(clip.frames, rows, intensities):
        if feature.real.musical_level[0] <= 0.0:
            continue
        band = next(name for name, low, high in BANDS if low <= intensity < high)
        entry = stats[band]
        entry["frames"] += 1
        sphere = row["sphere"]
        drives = sphere["section_drives"]
        if previous_drives is not None:
            jump = max(now - before for now, before in zip(drives, previous_drives))
            if jump > 0.05 and not rising:
                entry["bursts"].append(max(drives))
            rising = jump > 0.05
        launched = [c for c in sphere["cohorts"] if c["progress"] < 0.02]
        if launched and len(sphere["cohorts"]) >= previous_cohorts:
            entry["launches"].extend(c["strength"] for c in launched)
        entry["tracer"].append(sphere["tracer_drive"])
        entry["spin"].append(sphere["rotation_drive"])
        entry["body"].append(sphere["size_pulse"])
        previous_drives = drives
        previous_cohorts = len(sphere["cohorts"])
    return stats


def _line(name, entry) -> str:
    seconds = max(1e-9, entry["frames"] * FRAME_S)
    mean = lambda values: statistics.fmean(values) if values else 0.0
    return (f"  {name:14s} {seconds:5.1f}s  bursts/s {len(entry['bursts']) / seconds:4.2f} size {mean(entry['bursts']):.2f}"
            f"  launches/s {len(entry['launches']) / seconds:4.2f} strength {mean(entry['launches']):.2f}"
            f"  tracer {mean(entry['tracer']):.2f}  spin {mean(entry['spin']):.2f}  body {mean(entry['body']):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preset", type=int, nargs="*", default=[0, 1])
    args = parser.parse_args()
    from PySide6.QtCore import QCoreApplication

    QCoreApplication.instance() or QCoreApplication([])
    from .record import recorded_clips

    clips = recorded_clips()
    for preset in args.preset:
        print(f"== Sphere preset {preset}")
        for clip in clips:
            print(f" {clip.name}")
            for name, entry in measure(clip, preset).items():
                print(_line(name, entry))


if __name__ == "__main__":
    main()
