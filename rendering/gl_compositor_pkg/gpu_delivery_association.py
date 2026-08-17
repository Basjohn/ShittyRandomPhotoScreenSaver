"""Post-hoc association of sampled GPU results with paint-delivery gaps.

`GL_TIME_ELAPSED` results are asynchronous: the query relevant to a delivery gap
is usually not available when that gap is observed, so the association cannot be
made at gap-emission time. Instead, completed GPU results carry their owning
frame identity and are joined afterwards against the bounded paint-sample
history that the compositor already retains.

Causal ordering, which this module enforces rather than assumes:

    a gap recorded for paint frame N is the interval *before* paint N begins,
    so GPU execution measured for frame N cannot have caused it.

The primary comparison is therefore ``GPU duration frame N`` against the
delivery gap entering frame ``N+1``. Deeper pipeline effects are reported at
``+2`` and ``+3`` separately, never pooled into a "within K frames" window,
because pooling makes accidental matches steadily more likely. Same-frame
(``+0``) association is recorded descriptively only and is explicitly not
causal for the preceding gap.

Purely observational: no timer, queue, hop, event interception, admission or
repaint logic, no waiting on a GPU result, and no change to sample stride. It
does not consume or alter the aggregate GPU window statistics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

_GAP_MS = 33.0
_SEVERE_GAP_MS = 50.0
# Frame deltas reported separately. +0 is descriptive only.
_DELTAS = (0, 1, 2, 3)


@dataclass(frozen=True)
class _Bucket:
    """GPU durations grouped by what the following frame's delivery looked like."""

    ordinary: list[float]
    over_33: list[float]
    over_50: list[float]

    @classmethod
    def empty(cls) -> "_Bucket":
        return cls(ordinary=[], over_33=[], over_50=[])


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * quantile))))
    return ordered[index]


def _classify(gap_ms: float | None) -> str | None:
    if gap_ms is None:
        return None
    if gap_ms > _SEVERE_GAP_MS:
        return "over_50"
    if gap_ms > _GAP_MS:
        return "over_33"
    return "ordinary"


def associate(
    gpu_samples: Iterable,
    paint_samples: Iterable,
) -> dict:
    """Join GPU results to the delivery gap entering later frames.

    `gpu_samples` are `GPUFrameSample`-shaped (scene_generation, frame_index,
    label, elapsed_ms). `paint_samples` are `_PaintTimingSample`-shaped
    (frame_index, scene_generation, paint_interval_ms, ...).

    Frames are matched on `(scene_generation, frame_index)`. Generation is part
    of the key so repeated transition labels - several Blockspin runs, say -
    cannot cross-associate.
    """
    by_identity: dict[tuple[int, int], object] = {}
    for sample in paint_samples:
        by_identity[(int(sample.scene_generation), int(sample.frame_index))] = sample

    buckets: dict[int, dict[str, _Bucket]] = {}
    matched = 0
    unmatched = 0

    for gpu in gpu_samples:
        generation = int(gpu.scene_generation)
        frame = int(gpu.frame_index)
        label = str(gpu.label)
        found_any = False
        for delta in _DELTAS:
            target = by_identity.get((generation, frame + delta))
            if target is None:
                continue
            gap = getattr(target, "paint_interval_ms", None)
            classification = _classify(None if gap is None else float(gap))
            if classification is None:
                continue
            found_any = True
            per_label = buckets.setdefault(delta, {})
            bucket = per_label.setdefault(label, _Bucket.empty())
            getattr(bucket, classification).append(float(gpu.elapsed_ms))
        if found_any:
            matched += 1
        else:
            unmatched += 1

    report: dict = {
        "matched_gpu_samples": matched,
        "unmatched_gpu_samples": unmatched,
        "by_delta": {},
    }
    for delta, per_label in sorted(buckets.items()):
        label_report: dict = {}
        for label, bucket in per_label.items():
            entry = {}
            for name in ("ordinary", "over_33", "over_50"):
                values = getattr(bucket, name)
                entry[name] = {
                    "n": len(values),
                    "p50_ms": _percentile(values, 0.50),
                    "p95_ms": _percentile(values, 0.95),
                    "max_ms": max(values) if values else None,
                }
            label_report[label] = entry
        report["by_delta"][delta] = label_report
    return report


def format_report_lines(report: dict, *, screen: object) -> list[tuple[str, tuple]]:
    """Render the association as compact log records; caller does the logging."""
    lines: list[tuple[str, tuple]] = []
    for delta, per_label in sorted(report.get("by_delta", {}).items()):
        for label, entry in per_label.items():
            ordinary = entry["ordinary"]
            over_33 = entry["over_33"]
            over_50 = entry["over_50"]
            if not (ordinary["n"] or over_33["n"] or over_50["n"]):
                continue
            lines.append(
                (
                    "[PERF][GPU_DELIVERY_ASSOC] screen=%s transition=%s frame_delta=+%d "
                    "causal=%s matched=%d unmatched=%d "
                    "ordinary_n=%d ordinary_p50=%s ordinary_p95=%s ordinary_max=%s "
                    "gap33_n=%d gap33_p50=%s gap33_p95=%s gap33_max=%s "
                    "gap50_n=%d gap50_p50=%s gap50_p95=%s gap50_max=%s",
                    (
                        screen if screen is not None else "<unknown>",
                        label,
                        delta,
                        "no_same_frame" if delta == 0 else "yes",
                        report.get("matched_gpu_samples", 0),
                        report.get("unmatched_gpu_samples", 0),
                        ordinary["n"],
                        _text(ordinary["p50_ms"]),
                        _text(ordinary["p95_ms"]),
                        _text(ordinary["max_ms"]),
                        over_33["n"],
                        _text(over_33["p50_ms"]),
                        _text(over_33["p95_ms"]),
                        _text(over_33["max_ms"]),
                        over_50["n"],
                        _text(over_50["p50_ms"]),
                        _text(over_50["p95_ms"]),
                        _text(over_50["max_ms"]),
                    ),
                )
            )
    return lines


def _text(value: float | None) -> str:
    return "na" if value is None else f"{value:.2f}"
