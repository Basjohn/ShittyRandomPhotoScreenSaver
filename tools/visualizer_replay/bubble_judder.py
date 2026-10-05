"""Bubble judder on recorded music or committed fixtures.

Examples::

    python -m tools.visualizer_replay.bubble_judder --px-per-unit 300
    python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-tiny-assist

Operator 2026-10-04: a bubble caught between breathing states sticks mid-way and vibrates 1-2 px. This counts,
per bubble (nearest-position tracked across frames), runs of alternating frame-to-frame changes (up, down, up,
...) in the drawn radius and position whose steps are at least ``--min-px`` at the given card scale. Tiny-radius
stats classify only the samples inside ``--tiny-max-px``. ``--compare-tiny-assist`` runs the same clip twice,
with ``TINY_BREATH_ASSIST_PX`` forced to zero and then restored, so the local operator can prove that the new
render seam is both present and materially changing the remaining tiny-radius chatter.
"""
from __future__ import annotations

import argparse
from collections import Counter

from .driver import replay_clip
from .record import recorded_clips


def judder_spans(series, min_step: float, min_run: int = 3):
    """Return ``(sample_start, sample_end, steps)`` for sign-alternating runs."""
    spans, run, run_start, last_sign = [], 0, None, 0
    for index, (a, b) in enumerate(zip(series, series[1:])):
        step = b - a
        sign = 0 if abs(step) < min_step else (1 if step > 0 else -1)
        if sign and last_sign and sign == -last_sign:
            run += 1
        else:
            if run >= min_run and run_start is not None:
                spans.append((run_start, index, run))
            run = 1 if sign else 0
            run_start = index if sign else None
        last_sign = sign
    if run >= min_run and run_start is not None:
        spans.append((run_start, len(series) - 1, run))
    return spans


def judder(series, min_step: float, min_run: int = 3):
    """Run lengths retained for existing tests/callers."""
    return [steps for _start, _end, steps in judder_spans(series, min_step, min_run)]


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


def analyse(clip, *, px_per_unit: float, min_px: float, settings=None, tiny_max_px: float = 8.0):
    result = replay_clip(clip, "bubble", settings=settings)
    frames = [logical.mode_state for logical in result["logical_series"]]
    min_step = min_px / px_per_unit
    stats = Counter()
    for track in _tracks(frames, max_jump=12.0 / px_per_unit):
        if len(track) < 4:
            continue
        for name, offset in (("radius", 2), ("x", 0), ("y", 1)):
            series = [sample[offset] for sample in track]
            for start, end, run in judder_spans(series, min_step):
                stats[f"{name}_runs"] += 1
                stats[f"{name}_steps"] += run
                if name == "radius":
                    radius_px = [value * px_per_unit for value in series[start:end + 1]]
                    if radius_px and max(radius_px) <= tiny_max_px:
                        stats["tiny_radius_runs"] += 1
                        stats["tiny_radius_steps"] += run
                        if min(radius_px) < 4.0 <= max(radius_px):
                            stats["tiny_dot_outline_runs"] += 1
                            stats["tiny_dot_outline_steps"] += run
    stats["frames"] = len(frames)
    return stats


def _selected_clips(*, fixtures: bool, names: list[str]):
    if fixtures:
        from .driver import load_clips

        clips = list(load_clips().values())
    else:
        clips = list(recorded_clips())
    if names:
        wanted = set(names)
        clips = [clip for clip in clips if clip.name in wanted]
        missing = wanted.difference(clip.name for clip in clips)
        if missing:
            raise SystemExit(f"unknown clip(s): {', '.join(sorted(missing))}")
    return clips


def _print_stats(clip, stats, *, tiny: bool = True) -> None:
    minutes = stats["frames"] / 90.0 / 60.0
    fields = [
        f"{name}: {stats[name + '_runs'] / minutes:6.1f} runs/min ({stats[name + '_steps']} steps)"
        for name in ("radius", "x", "y")
    ]
    if tiny:
        fields.append(
            f"tiny-radius: {stats['tiny_radius_runs'] / minutes:6.1f} runs/min "
            f"({stats['tiny_radius_steps']} steps; dot/outline {stats['tiny_dot_outline_steps']})"
        )
    print(f"{clip.name:14s} " + " ".join(fields))


def main() -> None:
    from PySide6.QtCore import QCoreApplication

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--px-per-unit", type=float, default=300.0, help="card content height in physical px")
    parser.add_argument("--min-px", type=float, default=0.5)
    parser.add_argument("--tiny-max-px", type=float, default=8.0, help="largest radius counted as tiny")
    parser.add_argument("--frozen", action="store_true", help="frozen settings instead of the live preset")
    parser.add_argument(
        "--fixtures",
        action="store_true",
        help="use committed replay fixtures instead of logs/visualizer_recordings",
    )
    parser.add_argument("--clip", action="append", default=[], help="run only this clip name (repeatable)")
    parser.add_argument(
        "--compare-tiny-assist",
        action="store_true",
        help="replay each clip with TINY_BREATH_ASSIST_PX=0 then with the product value",
    )
    args = parser.parse_args()
    QCoreApplication.instance() or QCoreApplication([])
    settings = None
    if args.frozen:
        from tools.freeze_visualizer_settings import load_frozen
        settings = load_frozen
    clips = _selected_clips(fixtures=args.fixtures, names=args.clip)
    if not clips:
        parser.error("no replay clips found")

    if args.compare_tiny_assist:
        import widgets.spotify_visualizer.bubble_simulation as simulation

        product_assist = float(simulation.TINY_BREATH_ASSIST_PX)
        if product_assist <= 0.0:
            parser.error("product TINY_BREATH_ASSIST_PX is disabled; comparison has no positive control")
        try:
            for clip in clips:
                simulation.TINY_BREATH_ASSIST_PX = 0.0
                raw = analyse(
                    clip,
                    px_per_unit=args.px_per_unit,
                    min_px=args.min_px,
                    settings=settings,
                    tiny_max_px=args.tiny_max_px,
                )
                simulation.TINY_BREATH_ASSIST_PX = product_assist
                assisted = analyse(
                    clip,
                    px_per_unit=args.px_per_unit,
                    min_px=args.min_px,
                    settings=settings,
                    tiny_max_px=args.tiny_max_px,
                )
                before = raw["tiny_radius_steps"]
                after = assisted["tiny_radius_steps"]
                reduction = 0.0 if before <= 0 else 100.0 * (before - after) / before
                print(
                    f"{clip.name:14s} tiny-radius assist OFF {before:5d} steps -> "
                    f"ON {after:5d} steps ({reduction:+6.1f}% reduction); "
                    f"all-radius {raw['radius_steps']} -> {assisted['radius_steps']}"
                )
        finally:
            simulation.TINY_BREATH_ASSIST_PX = product_assist
        return

    for clip in clips:
        stats = analyse(
            clip,
            px_per_unit=args.px_per_unit,
            min_px=args.min_px,
            settings=settings,
            tiny_max_px=args.tiny_max_px,
        )
        _print_stats(clip, stats)


if __name__ == "__main__":
    main()
