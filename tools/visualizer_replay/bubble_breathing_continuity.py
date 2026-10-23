"""Per-identity breathing continuity from a ``bubble_response_comparison`` output directory.

Reads ``bubble.jsonl`` and ``extruded_bubble.jsonl`` (same recorded samples/cadence)
and measures, per stable identity and contiguous mature segment, how the displayed
radius ratio moves from sample to sample:

* ``range``: (max - min) / median ratio, the segment's breathing excursion;
* ``step_p50/p95``: |step| as a fraction of that segment's own range;
* ``jumps``: share of steps larger than 15% of the range in one sample (snapping);
* ``flat``: share of steps below 0.5% of the range (sitting between states);
* ``reversals``: share of steps that reverse direction after a non-flat step (jitter);
* ``top_reversals`` / ``top_step_p50``: the same inside the top 15% of the range
  (judder at maximum size);
* ``swings_per_s``: turning points whose swing from the previous turning point
  exceeds 25% of the segment range, per second (phrase breathing is slow; beat
  pumping is fast).

Logical ratios only: not segmented pixels, display cadence or listening acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load_series(path: Path):
    series: dict[int, list[tuple[float, float, bool, bool]]] = {}
    times = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            times.append(row["time_s"])
            for obj in row["objects"]:
                series.setdefault(obj["id"], []).append(
                    (row["time_s"], obj["ratio"], bool(obj["large"]), bool(obj["mature"]))
                )
    return series, np.asarray(times)


def mature_segments(samples, min_seconds: float, cadence: float):
    segment = []
    for time_s, ratio, large, mature in samples:
        contiguous = segment and time_s - segment[-1][0] <= cadence * 1.6
        if mature and (not segment or contiguous):
            segment.append((time_s, ratio, large))
            continue
        if segment and segment[-1][0] - segment[0][0] >= min_seconds:
            yield segment
        segment = [(time_s, ratio, large)] if mature else []
    if segment and segment[-1][0] - segment[0][0] >= min_seconds:
        yield segment


def segment_metrics(segment):
    ratios = np.asarray([r for _, r, _ in segment])
    span = float(ratios.max() - ratios.min())
    median = float(np.median(ratios))
    steps = np.diff(ratios)
    if span <= 1e-9 or not len(steps):
        return None
    scaled = np.abs(steps) / span
    flat = scaled < 0.005
    moving = ~flat
    signs = np.sign(steps)
    reversal = moving[1:] & moving[:-1] & (signs[1:] != signs[:-1])
    top = ratios[1:] >= ratios.min() + 0.85 * span
    swings = 0
    anchor = ratios[0]
    direction = 0
    for value in ratios[1:]:
        move = value - anchor
        if direction >= 0 and move <= -0.25 * span:
            swings += direction > 0
            direction, anchor = -1, value
        elif direction <= 0 and move >= 0.25 * span:
            swings += direction < 0
            direction, anchor = 1, value
        elif (direction > 0 and value > anchor) or (direction < 0 and value < anchor):
            anchor = value
    top_moving = moving[1:] & moving[:-1] & top[1:]
    return dict(
        start_s=segment[0][0], seconds=segment[-1][0] - segment[0][0], samples=len(ratios),
        large=segment[0][2], range=span / median,
        step_p50=float(np.median(scaled)), step_p95=float(np.percentile(scaled, 95)),
        jumps=float(np.mean(scaled > 0.15)), flat=float(np.mean(flat)),
        reversals=float(np.mean(reversal)) if len(reversal) else 0.0,
        top_samples=int(top.sum()),
        top_reversals=float(reversal[top[1:]].mean()) if top_moving.any() else 0.0,
        top_step_p50=float(np.median(scaled[1:][top[1:]])) if top[1:].any() else 0.0,
        swings_per_s=swings / max(1e-6, segment[-1][0] - segment[0][0]),
    )


def summarize(rows):
    keys = ("range", "step_p50", "step_p95", "jumps", "flat", "reversals", "top_reversals", "top_step_p50",
            "swings_per_s")
    out = {}
    for large, label in ((True, "large"), (False, "small")):
        chosen = [r for r in rows if r["large"] is large]
        out[label] = dict(segments=len(chosen), seconds=round(sum(r["seconds"] for r in chosen), 2))
        for key in keys:
            values = [r[key] for r in chosen]
            out[label][key] = round(float(np.median(values)), 4) if values else None
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--min-seconds", type=float, default=2.0)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = {}
    for mode in ("bubble", "extruded_bubble"):
        series, times = load_series(args.directory / f"{mode}.jsonl")
        cadence = float(np.median(np.diff(times)))
        rows = [m for samples in series.values()
                for segment in mature_segments(samples, args.min_seconds, cadence)
                if (m := segment_metrics(segment)) is not None]
        report[mode] = dict(cadence_s=cadence, samples=len(times), identities=len(series),
                            summary=summarize(rows), segments=rows)
        print(mode, f"cadence={cadence*1000:.1f}ms ids={len(series)}")
        for label, values in report[mode]["summary"].items():
            print(f"  {label}: {values}")
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
