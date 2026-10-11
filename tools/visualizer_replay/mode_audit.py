"""Reactivity audit of the replayable modes on recorded music: python -m tools.visualizer_replay.mode_audit

    python -m tools.visualizer_replay.mode_audit --modes bubble --save logs/bubble_readings.json
    python -m tools.visualizer_replay.mode_audit --modes bubble --compare logs/bubble_readings.json

Replays every schema 2 clip in ``logs/visualizer_recordings`` (archived takes excluded) through
Spectrum (whose runtime Extruded Spectrum shares), Oscilloscope, Sine Wave, DevCurve and Shockwave
Grid (its live waves; clips recorded with musical onsets), and reports
the warning signs of ``Docs/Guides/Visualizer_Reactivity_Authoring.md`` per band of passage
intensity (<0.35 quiet, 0.35-0.75 usual, >0.75 loud): the output's mean level, how much it moves
frame to frame, and how often its values sit at the ceiling or at zero. A healthy mode grows from
quiet to loud and spends little time pinned. DevCurve's reaction is a zero-mean undulation around
its authored contour, so its level is the swing from the clip-long resting curve, not the mean.

Bubble reads its own vocabulary per band (``bubble_audit``): the live bubbles' mean drawn radius, how
much the radii move frame to frame, how fast the bubbles travel, the share that are big, and pops per
second. Every mode replays on its frozen settings (``tests/fixtures/visualizer_frozen_settings``), never
a curated preset: presets are authored and change often. ``--save`` writes the readings; ``--compare``
prints each reading's change against a saved run as a ratio, so a change to shared code shows how the
reaction moved rather than whether it matches a pinned number.
"""
from __future__ import annotations

import statistics

from .driver import mode_output, replay_clip

MODES = ("spectrum", "oscilloscope", "sine_wave", "devcurve", "shockwave_grid", "bubble")
BANDS = (("quiet", 0.0, 0.35), ("usual", 0.35, 0.75), ("loud", 0.75, 9.0))


def _frozen(mode: str) -> dict:
    from tools.freeze_visualizer_settings import load_frozen

    return load_frozen(mode)


def _bands(clip):
    """Each frame's passage band (None while silent), from the eased passage intensity."""
    from widgets.spotify_visualizer.transient_bus import PassageIntensity

    follower, last_us, bands = PassageIntensity(), None, []
    for feature in clip.frames:
        step = 0.0 if last_us is None else (feature.timestamp_us - last_us) / 1e6
        last_us = feature.timestamp_us
        loudness = feature.real.musical_level[0] if feature.real is not None else feature.energy.bubble.overall
        intensity = follower.update(loudness, step)
        bands.append(None if loudness <= 0.0 else
                     next(name for name, low, high in BANDS if low <= intensity < high))
    return bands


def bubble_audit(clip) -> dict:
    """Bubble's reaction per passage band: drawn radius, radius motion, travel speed (both per
    second), big-bubble share and pops per second."""
    from .bubble_fidelity import replay_bubbles

    _result, observations, _settings = replay_bubbles(clip, settings=_frozen)
    bands = _bands(clip)
    stats = {name: {"radius": [], "radius_motion": [], "speed": [], "big": [], "pops": 0, "seconds": 0.0}
             for name, *_ in BANDS}
    previous, last_us = {}, None
    for feature, band, samples in zip(clip.frames, bands, observations):
        step = 0.0 if last_us is None else (feature.timestamp_us - last_us) / 1e6
        last_us = feature.timestamp_us
        current = {sample["track"]: sample for sample in samples}
        if band is not None and samples and step > 0.0:
            entry = stats[band]
            entry["seconds"] += step
            live = [s for s in samples if not s["popping"] and not s["exiting"]]
            if live:
                entry["radius"].append(statistics.fmean(s["radius"] for s in live))
                entry["big"].append(sum(1 for s in live if s["big"]) / len(live))
            moved = [(s, previous[s["track"]]) for s in live if s["track"] in previous]
            if moved:
                entry["radius_motion"].append(statistics.fmean(abs(s["radius"] - p["radius"]) for s, p in moved) / step)
                entry["speed"].append(statistics.fmean(
                    ((s["x"] - p["x"]) ** 2 + (s["y"] - p["y"]) ** 2) ** 0.5 for s, p in moved) / step)
            entry["pops"] += sum(1 for s in samples if s["popping"] and not previous.get(s["track"], {}).get("popping"))
        previous = current
    mean = lambda values: statistics.fmean(values) if values else 0.0
    return {name: {"seconds": round(entry["seconds"], 2), "radius": mean(entry["radius"]),
                   "radius_motion": mean(entry["radius_motion"]), "speed": mean(entry["speed"]),
                   "big_share": mean(entry["big"]),
                   "pops_per_s": entry["pops"] / entry["seconds"] if entry["seconds"] else 0.0}
            for name, entry in stats.items()}


def audit(clip, mode: str) -> dict:
    from widgets.spotify_visualizer.transient_bus import PassageIntensity

    result = replay_clip(clip, mode, settings=_frozen)
    outputs = [mode_output(logical) for logical in result["logical_series"]]
    if mode == "devcurve":
        valid = [values for values in outputs if values]
        rest = [statistics.fmean(column) for column in zip(*valid)] if valid else []
        outputs = [tuple(v - r for v, r in zip(values, rest)) if values else values for values in outputs]
    follower, last_us = PassageIntensity(), None
    stats = {name: {"level": [], "motion": [], "ceiling": 0, "zero": 0, "values": 0} for name, *_ in BANDS}
    previous = None
    for feature, output in zip(clip.frames, outputs):
        step = 0.0 if last_us is None else (feature.timestamp_us - last_us) / 1e6
        last_us = feature.timestamp_us
        intensity = follower.update(feature.real.musical_level[0], step)
        values = [abs(float(v)) for v in output]
        if not values or feature.real.musical_level[0] <= 0.0:
            previous = values
            continue
        entry = stats[next(name for name, low, high in BANDS if low <= intensity < high)]
        peak = max(values)
        entry["level"].append(statistics.fmean(values))
        if previous is not None and len(previous) == len(values):
            entry["motion"].append(statistics.fmean(abs(a - b) for a, b in zip(values, previous)))
        entry["ceiling"] += sum(1 for v in values if v >= 0.98)
        entry["zero"] += sum(1 for v in values if v <= 0.005)
        entry["values"] += len(values)
        previous = values
    return stats


def _readings(clips, modes) -> dict:
    readings: dict = {}
    for mode in modes:
        for clip in clips:
            if mode == "shockwave_grid" and not any(frame.real.onsets for frame in clip.frames):
                continue
            if mode == "bubble":
                readings.setdefault(mode, {})[clip.name] = bubble_audit(clip)
                continue
            rows = {}
            for name, entry in audit(clip, mode).items():
                n = max(1, entry["values"])
                mean = lambda values: statistics.fmean(values) if values else 0.0
                rows[name] = {"level": mean(entry["level"]), "motion": mean(entry["motion"]),
                              "ceiling": entry["ceiling"] / n, "zero": entry["zero"] / n}
            readings.setdefault(mode, {})[clip.name] = rows
    return readings


def _print(readings, baseline=None) -> None:
    for mode, clips in readings.items():
        print(f"== {mode}")
        for clip, bands in clips.items():
            print(f" {clip}")
            for band, values in bands.items():
                cells = []
                for key, value in values.items():
                    if key == "seconds":
                        cells.append(f"{value:5.1f}s")
                        continue
                    text = f"{key} {value:.4f}" if key not in ("ceiling", "zero", "big_share") else f"{key} {value:5.1%}"
                    old = (baseline or {}).get(mode, {}).get(clip, {}).get(band, {}).get(key)
                    if old is not None:
                        text += f" (x{value / old:.2f})" if abs(old) > 1e-9 else " (was 0)"
                    cells.append(text)
                print(f"  {band:5s} " + "  ".join(cells))


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    from PySide6.QtCore import QCoreApplication

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--modes", nargs="*", default=list(MODES), choices=MODES)
    parser.add_argument("--save", type=Path, help="write the readings as JSON")
    parser.add_argument("--compare", type=Path, help="print each reading's ratio to a saved run")
    args = parser.parse_args()
    QCoreApplication.instance() or QCoreApplication([])
    from .record import recorded_clips

    readings = _readings(recorded_clips(), args.modes)
    baseline = json.loads(args.compare.read_text(encoding="utf-8")) if args.compare else None
    _print(readings, baseline)
    if args.save:
        args.save.write_text(json.dumps(readings, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
