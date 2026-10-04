"""Reactivity audit of the replayable modes on recorded music: python -m tools.visualizer_replay.mode_audit

Replays every schema 2 clip in ``logs/visualizer_recordings`` (``*_noevents`` excluded) through
Spectrum (whose runtime Extruded Spectrum shares), Oscilloscope, Sine Wave, DevCurve and Shockwave
Grid (its live waves; clips recorded with musical onsets), and reports
the warning signs of ``Docs/Guides/Visualizer_Reactivity_Authoring.md`` per band of passage
intensity (<0.35 quiet, 0.35-0.75 usual, >0.75 loud): the output's mean level, how much it moves
frame to frame, and how often its values sit at the ceiling or at zero. A healthy mode grows from
quiet to loud and spends little time pinned.
"""
from __future__ import annotations

from pathlib import Path
import statistics

from .driver import mode_output, replay_clip

RECORDINGS = Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"
MODES = ("spectrum", "oscilloscope", "sine_wave", "devcurve", "shockwave_grid")
BANDS = (("quiet", 0.0, 0.35), ("usual", 0.35, 0.75), ("loud", 0.75, 9.0))


def audit(clip, mode: str) -> dict:
    from widgets.spotify_visualizer.transient_bus import PassageIntensity

    result = replay_clip(clip, mode)
    follower, last_us = PassageIntensity(), None
    stats = {name: {"level": [], "motion": [], "ceiling": 0, "zero": 0, "values": 0} for name, *_ in BANDS}
    previous = None
    for feature, logical in zip(clip.frames, result["logical_series"]):
        step = 0.0 if last_us is None else (feature.timestamp_us - last_us) / 1e6
        last_us = feature.timestamp_us
        intensity = follower.update(feature.real.musical_level[0], step)
        values = [abs(float(v)) for v in mode_output(logical)]
        if not values or feature.real.musical_level[0] <= 0.0:
            previous = values
            continue
        entry = stats[next(name for name, low, high in BANDS if low <= intensity < high)]
        peak = max(values)
        entry["level"].append(statistics.fmean(values))
        if previous is not None and len(previous) == len(values):
            entry["motion"].append(statistics.fmean(abs(a - b) for a, b in zip(values, previous)))
        entry["ceiling"] += sum(1 for v in values if v >= 0.98 * max(1.0, peak if mode == "devcurve" else 1.0))
        entry["zero"] += sum(1 for v in values if v <= 0.005)
        entry["values"] += len(values)
        previous = values
    return stats


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    from widgets.spotify_visualizer.feature_frame import load_jsonl

    QCoreApplication.instance() or QCoreApplication([])
    clips = [load_jsonl(path) for path in sorted(RECORDINGS.glob("*.jsonl")) if not path.stem.endswith("_noevents")]
    for mode in MODES:
        print(f"== {mode}")
        for clip in clips:
            if mode == "shockwave_grid" and not any(frame.real.onsets for frame in clip.frames):
                print(f" {clip.name}: recorded without musical onsets (re-record to audit)")
                continue
            print(f" {clip.name}")
            for name, entry in audit(clip, mode).items():
                n = max(1, entry["values"])
                mean = lambda values: statistics.fmean(values) if values else 0.0
                print(f"  {name:5s} level {mean(entry['level']):.3f}  motion {mean(entry['motion']):.4f}"
                      f"  at ceiling {entry['ceiling'] / n:5.1%}  at zero {entry['zero'] / n:5.1%}")


if __name__ == "__main__":
    main()
