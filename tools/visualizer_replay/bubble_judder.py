"""Bubble judder on recorded music: python -m tools.visualizer_replay.bubble_judder [--px-per-unit 300]

Operator 2026-10-04: a bubble caught between breathing states sticks mid-way and vibrates 1-2 px. This counts,
per bubble (index-matched across frames with an unchanged bubble count), runs of alternating frame-to-frame
changes (up, down, up, ...) in the drawn radius and position whose steps are at least ``--min-px`` at the given
card scale, i.e. a visible back-and-forth rather than a monotonic swell or a fade.
"""
from __future__ import annotations

import argparse
from collections import Counter

from .driver import replay_clip
from .record import recorded_clips


def judder(series, min_step: float, min_run: int = 3):
    """Runs of >= ``min_run`` sign-alternating steps of at least ``min_step`` in ``series``."""
    runs, run, last_sign = [], 0, 0
    for a, b in zip(series, series[1:]):
        step = b - a
        sign = 0 if abs(step) < min_step else (1 if step > 0 else -1)
        if sign and last_sign and sign == -last_sign:
            run += 1
        else:
            if run >= min_run:
                runs.append(run)
            run = 1 if sign else 0
        last_sign = sign
    if run >= min_run:
        runs.append(run)
    return runs


def _tracks(frames, max_jump: float):
    """Chain each bubble across frames by nearest position (the payload's order is not stable)."""
    tracks, live = [], []                 # live: (track index, x, y)
    for state in frames:
        bubbles = [tuple(state.positions[i * 4:i * 4 + 4]) for i in range(state.bubble_count)]
        taken, next_live = set(), []
        for x, y, r, alpha in bubbles:
            best, best_d = None, max_jump
            for slot, (track, px, py) in enumerate(live):
                if slot in taken:
                    continue
                d = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                if d < best_d:
                    best, best_d = slot, d
            if best is None:
                tracks.append([])
                track = len(tracks) - 1
            else:
                taken.add(best)
                track = live[best][0]
            tracks[track].append((x, y, r, alpha))
            next_live.append((track, x, y))
        live = next_live
    return tracks


def analyse(clip, *, px_per_unit: float, min_px: float, settings=None):
    result = replay_clip(clip, "bubble", settings=settings)
    frames = [logical.mode_state for logical in result["logical_series"]]
    min_step = min_px / px_per_unit
    stats = Counter()
    for track in _tracks(frames, max_jump=12.0 / px_per_unit):
        if len(track) < 4:
            continue
        for name, offset in (("radius", 2), ("x", 0), ("y", 1)):
            for run in judder([sample[offset] for sample in track], min_step):
                stats[f"{name}_runs"] += 1
                stats[f"{name}_steps"] += run
    stats["frames"] = len(frames)
    return stats


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--px-per-unit", type=float, default=300.0, help="card content height in px")
    parser.add_argument("--min-px", type=float, default=0.5)
    parser.add_argument("--frozen", action="store_true", help="frozen settings instead of the live preset")
    args = parser.parse_args()
    QCoreApplication.instance() or QCoreApplication([])
    settings = None
    if args.frozen:
        from tools.freeze_visualizer_settings import load_frozen
        settings = load_frozen
    for clip in recorded_clips():
        stats = analyse(clip, px_per_unit=args.px_per_unit, min_px=args.min_px, settings=settings)
        minutes = stats["frames"] / 90.0 / 60.0
        print(f"{clip.name:14s} " + " ".join(
            f"{name}: {stats[name + '_runs'] / minutes:6.1f} runs/min ({stats[name + '_steps']} steps)"
            for name in ("radius", "x", "y")))


if __name__ == "__main__":
    main()
