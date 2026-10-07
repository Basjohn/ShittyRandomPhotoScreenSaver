"""Bubble judder on recorded music or committed fixtures.

Examples::

    python -m tools.visualizer_replay.bubble_judder --px-per-unit 300
    python -m tools.visualizer_replay.bubble_judder --fixtures --clip broadband_noise --frozen --compare-release

Operator 2026-10-04: a bubble caught between breathing states sticks mid-way and vibrates 1-2 px. This counts,
per bubble (production object identity tracked across frames), runs of alternating frame-to-frame changes (up, down, up,
...) in the drawn radius and position whose steps are at least ``--min-px`` at the given card scale. Tiny-radius
stats classify only the samples inside ``--tiny-max-px``. ``--compare-release`` runs the same clip twice,
with an instant release and then the accepted product render-release envelope. ``--report`` retains
frame-aligned radius, extrema and first-change evidence. Its projection is supplied by the caller;
offline replay does not measure a physical display or establish live audio-to-screen latency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import subprocess

from .bubble_fidelity import compare_observations, replay_bubbles, settings_digest, tracks
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


def analyse(clip, *, px_per_unit: float, min_px: float, settings=None, tiny_max_px: float = 8.0):
    _result, observations, _settings = replay_bubbles(clip, settings=settings)
    return analyse_observations(observations, px_per_unit=px_per_unit, min_px=min_px, tiny_max_px=tiny_max_px)


def analyse_observations(observations, *, px_per_unit: float, min_px: float, tiny_max_px: float = 8.0):
    min_step = min_px / px_per_unit
    stats = Counter()
    for samples in tracks(observations).values():
        track = [sample for _frame, sample in samples]
        if len(track) < 4:
            continue
        radii = [sample["radius"] * px_per_unit for sample in track]
        stats["dot_outline_crossings"] += sum((a < 4.0) != (b < 4.0) for a, b in zip(radii, radii[1:]))
        for name in ("radius", "x", "y"):
            series = [sample[name] for sample in track]
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
    stats["frames"] = len(observations)
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
    minutes = max(1e-9, (clip.frames[-1].timestamp_us - clip.frames[0].timestamp_us) / 60_000_000.0)
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
    parser.add_argument("--px-per-unit", type=float, default=300.0, help="drawn response-height projection in pixels (not a display measurement)")
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
        "--compare-release",
        action="store_true",
        help="replay each clip with instant render release then with the accepted product envelope",
    )
    parser.add_argument("--report", type=Path, help="write reproducible per-clip OFF/ON fidelity evidence as JSON")
    args = parser.parse_args()
    if not all(math.isfinite(value) and value > 0 for value in (args.px_per_unit, args.min_px, args.tiny_max_px)):
        parser.error("pixel scales and thresholds must be positive")
    if args.report and not args.compare_release:
        parser.error("--report requires --compare-release")
    QCoreApplication.instance() or QCoreApplication([])
    settings = None
    if args.frozen:
        from tools.freeze_visualizer_settings import load_frozen
        settings = load_frozen
    clips = _selected_clips(fixtures=args.fixtures, names=args.clip)
    if not clips:
        parser.error("no replay clips found")

    if args.compare_release:
        import widgets.spotify_visualizer.bubble_simulation as simulation

        product_release = float(simulation.RENDER_SIZE_RELEASE_S)
        if product_release <= 1e-6:
            parser.error("product render release has no positive control")
        report = {"schema": 2, "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True).strip(),
            "px_per_unit": args.px_per_unit, "min_px": args.min_px, "tiny_max_px": args.tiny_max_px,
            "comparison": "instant_release_vs_product", "release_s": product_release, "clips": []}
        report["diagnostic_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path(__file__).with_name("bubble_fidelity.py"),
                         Path(__file__).with_name("driver.py"))}
        try:
            for clip in clips:
                simulation.RENDER_SIZE_RELEASE_S = 1e-6
                raw_result, raw_observations, raw_settings = replay_bubbles(clip, settings=settings)
                raw = analyse_observations(
                    raw_observations,
                    px_per_unit=args.px_per_unit,
                    min_px=args.min_px,
                    tiny_max_px=args.tiny_max_px,
                )
                simulation.RENDER_SIZE_RELEASE_S = product_release
                on_result, on_observations, on_settings = replay_bubbles(clip, settings=settings)
                if raw_settings != on_settings:
                    raise RuntimeError("OFF/ON replay resolved different authored settings")
                assisted = analyse_observations(
                    on_observations,
                    px_per_unit=args.px_per_unit,
                    min_px=args.min_px,
                    tiny_max_px=args.tiny_max_px,
                )
                fidelity = compare_observations(clip, raw_observations, on_observations,
                                               px_per_unit=args.px_per_unit, tiny_max_px=args.tiny_max_px)
                before = raw["tiny_radius_steps"]
                after = assisted["tiny_radius_steps"]
                reduction = 0.0 if before <= 0 else 100.0 * (before - after) / before
                print(
                    f"{clip.name:14s} render release OFF {before:5d} tiny steps -> "
                    f"ON {after:5d} steps ({reduction:+6.1f}% reduction); "
                    f"all-radius {raw['radius_steps']} -> {assisted['radius_steps']}; "
                    f"boundary crossings {raw['dot_outline_crossings']} -> {assisted['dot_outline_crossings']}; "
                    f"max deviation {fidelity['max_radius_error_px']:.6f}px; "
                    f"first-change/peak shifts {fidelity['counts'].get('first_radius_change_frame_changed_windows', 0)}/"
                    f"{fidelity['counts'].get('peak_frame_changed_windows', 0)}",
                    flush=True,
                )
                report["clips"].append({"name": clip.name, "frames": len(clip.frames),
                    "input_sha256": hashlib.sha256(clip.to_jsonl_bytes()).hexdigest(),
                    "resolved_settings": raw_settings, "settings_sha256": settings_digest(raw_settings),
                    "off": dict(raw), "on": dict(assisted), "fidelity": fidelity,
                    "off_metrics": raw_result["metrics"], "on_metrics": on_result["metrics"]})
                if args.report:
                    args.report.parent.mkdir(parents=True, exist_ok=True)
                    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        finally:
            simulation.RENDER_SIZE_RELEASE_S = product_release
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
