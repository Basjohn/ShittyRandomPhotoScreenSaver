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
    # Per (label, generation) so a line cannot report unrelated buckets' counts.
    per_key_matched: dict[tuple[str, int], int] = {}
    per_key_unmatched: dict[tuple[str, int], int] = {}

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
        key = (label, generation)
        if found_any:
            matched += 1
            per_key_matched[key] = per_key_matched.get(key, 0) + 1
        else:
            unmatched += 1
            per_key_unmatched[key] = per_key_unmatched.get(key, 0) + 1

    report: dict = {
        "matched_gpu_samples": matched,
        "unmatched_gpu_samples": unmatched,
        "by_delta": {},
        "per_key_matched": per_key_matched,
        "per_key_unmatched": per_key_unmatched,
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
                        sum(
                            v for (lab, _gen), v in report.get("per_key_matched", {}).items()
                            if lab == label
                        ),
                        sum(
                            v for (lab, _gen), v in report.get("per_key_unmatched", {}).items()
                            if lab == label
                        ),
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


# ---------------------------------------------------------------------------
# PART D: Qt top-level composition / swap boundary observation.
#
# QOpenGLWidget renders into an internal FBO; Qt later composes and swaps on the
# GUI thread, after paintGL and therefore outside the existing GL_TIME_ELAPSED
# scope. aboutToCompose and frameSwapped bracket that stage.
#
# Direct GUI-thread handling only: no timer, thread, queued callback,
# invokeMethod, singleShot, update() or repaint(). No one-paint : one-compose :
# one-swap relationship is assumed - the counters record what Qt actually does.
# ---------------------------------------------------------------------------


class QtCompositionObserver:
    """Bounded record of paint -> compose -> swap timing on the GUI thread."""

    def __init__(self, *, capacity: int = 256) -> None:
        from collections import deque

        self._paints = deque(maxlen=capacity)
        self._records = deque(maxlen=capacity)
        self._active = None
        self.paints_without_compose = 0
        self.compose_without_paint = 0
        self.multiple_paints_before_compose = 0
        self.swap_without_compose = 0
        self.compose_replaced = 0
        self._pending_paints_since_compose = 0

    def record_paint_end(self, *, scene_generation, frame_index, transition, paint_end_ts):
        if self._pending_paints_since_compose >= 1:
            self.multiple_paints_before_compose += 1
        self._pending_paints_since_compose += 1
        self._paints.append(
            {
                "scene_generation": int(scene_generation),
                "frame_index": int(frame_index),
                "transition": str(transition),
                "paint_end_ts": float(paint_end_ts),
            }
        )

    def on_about_to_compose(self, now_ts: float) -> None:
        """Consume the newest UNCONSUMED sampled paint exactly once.

        `_paints` holds only unconsumed eligible sampled paint completions.
        Stage paint records exist solely for sampled frames, so after one is
        composed and swapped the many subsequent unsampled Qt compositions must
        NOT re-attach to it - doing so manufactures enormous
        paint_end_to_compose/swap ages out of an old identity.
        """
        if self._active is not None:
            self.compose_replaced += 1
            self._active = None
        if not self._paints:
            # No eligible sampled paint: record the composition, associate nothing.
            self.compose_without_paint += 1
            return
        # Newest eligible paint is consumed; older uncomposed sampled paints are
        # counted and discarded rather than matched to this composition.
        paint = self._paints.pop()
        if self._paints:
            self.paints_without_compose += len(self._paints)
            self._paints.clear()
        self._pending_paints_since_compose = 0
        self._active = {"paint": paint, "compose_ts": float(now_ts)}

    def on_frame_swapped(self, now_ts: float) -> None:
        active = self._active
        self._active = None
        if active is None:
            self.swap_without_compose += 1
            return
        paint = active["paint"]
        compose_ts = active["compose_ts"]
        paint_end = paint["paint_end_ts"]
        self._records.append(
            {
                "scene_generation": paint["scene_generation"],
                "frame_index": paint["frame_index"],
                "transition": paint["transition"],
                "paint_end_to_compose_ms": max(0.0, (compose_ts - paint_end) * 1000.0),
                "compose_to_swap_ms": max(0.0, (now_ts - compose_ts) * 1000.0),
                "paint_end_to_swap_ms": max(0.0, (now_ts - paint_end) * 1000.0),
            }
        )

    def take_records(self) -> list[dict]:
        drained = list(self._records)
        self._records.clear()
        return drained

    def counters(self) -> dict:
        return {
            "paints_without_compose": self.paints_without_compose,
            "compose_without_paint": self.compose_without_paint,
            "multiple_paints_before_compose": self.multiple_paints_before_compose,
            "swap_without_compose": self.swap_without_compose,
            "compose_replaced": self.compose_replaced,
        }


# ---------------------------------------------------------------------------
# PART E: unified stage association report.
# ---------------------------------------------------------------------------

_STAGE_FIELDS = (
    "outer_gpu_ms",
    "prep_gpu_ms",
    "core_draw_gpu_ms",
    "dimming_gpu_ms",
    "overlay_gpu_ms",
    "unpartitioned_gpu_ms",
    "prep_cpu_ms",
    "core_draw_cpu_ms",
    "dimming_cpu_ms",
    "overlay_cpu_ms",
    "hud_build_cpu_ms",
    "paint_end_to_compose_ms",
    "compose_to_swap_ms",
    "paint_end_to_swap_ms",
)


def associate_stages(stage_packets, paint_samples, composition_records=()):
    """Join stage/HUD/composition data to the gap entering the successor frame.

    Same causal convention as `associate()`: data for frame N is compared
    against the delivery gap entering frame N+1. Deltas are not pooled.
    """
    by_identity = {}
    for sample in paint_samples:
        by_identity[(int(sample.scene_generation), int(sample.frame_index))] = sample

    compose_by_identity = {}
    for record in composition_records:
        compose_by_identity[
            (int(record["scene_generation"]), int(record["frame_index"]))
        ] = record

    buckets = {}
    matched = {field: 0 for field in _STAGE_FIELDS}
    unmatched = {field: 0 for field in _STAGE_FIELDS}
    delta = 1  # primary causal comparison only

    for packet in stage_packets:
        generation = int(packet.scene_generation)
        frame = int(packet.frame_index)
        successor = by_identity.get((generation, frame + delta))
        if successor is None:
            for field in _STAGE_FIELDS:
                unmatched[field] += 1
            continue
        gap = getattr(successor, "paint_interval_ms", None)
        classification = _classify(None if gap is None else float(gap))
        if classification is None:
            continue

        values = dict(packet.spans_ms())
        values.update(
            {k: v for k, v in packet.cpu_ms.items() if str(k).endswith("_cpu_ms")}
        )
        hud = getattr(packet, "hud", {}) or {}
        if "hud_build_cpu_ms" in hud:
            values["hud_build_cpu_ms"] = hud["hud_build_cpu_ms"]
        outer = getattr(packet, "outer_gpu_ms", None)
        if outer is not None:
            values["outer_gpu_ms"] = float(outer)
            marked = values.get("marked_gpu_ms")
            if marked is not None:
                # Not assumed zero: query command overhead and boundary
                # placement both exist.
                values["unpartitioned_gpu_ms"] = float(outer) - float(marked)
        compose = compose_by_identity.get((generation, frame))
        if compose is not None:
            for key in (
                "paint_end_to_compose_ms",
                "compose_to_swap_ms",
                "paint_end_to_swap_ms",
            ):
                values[key] = compose[key]

        bucket_key = f"{packet.transition}|{getattr(packet, 'render_path', 'unknown')}"
        per_label = buckets.setdefault(bucket_key, {})
        per_class = per_label.setdefault(classification, {})
        for field in _STAGE_FIELDS:
            if field in values:
                per_class.setdefault(field, []).append(float(values[field]))
                matched[field] += 1
            else:
                unmatched[field] += 1

    report = {
        "frame_delta": delta,
        "matched": matched,
        "unmatched": unmatched,
        "by_label": {},
    }
    for label, per_class in buckets.items():
        out_class = {}
        for classification, fields in per_class.items():
            out_fields = {}
            for field, values_list in fields.items():
                out_fields[field] = {
                    "n": len(values_list),
                    "p50": _percentile(values_list, 0.50),
                    "p95": _percentile(values_list, 0.95),
                    "max": max(values_list) if values_list else None,
                }
            out_class[classification] = out_fields
        report["by_label"][label] = out_class
    return report


def format_stage_report_lines(
    report: dict, *, screen: object, counters: dict, dropped: int
) -> list[tuple[str, tuple]]:
    """Render the unified stage attribution as compact records.

    One line per transition label and successor class. Matched/unmatched are
    reported per field so a missing Qt signal or dropped timestamp packet
    cannot silently bias the result.
    """
    lines: list[tuple[str, tuple]] = []
    matched = report.get("matched", {})
    unmatched = report.get("unmatched", {})
    for bucket_key, per_class in sorted(report.get("by_label", {}).items()):
        label, _, render_path = bucket_key.partition("|")
        for classification, fields in sorted(per_class.items()):
            parts = []
            args: list = [
                screen if screen is not None else "<unknown>",
                label,
                render_path or "unknown",
                report.get("frame_delta", 1),
                classification,
            ]
            for name in _STAGE_FIELDS:
                entry = fields.get(name)
                parts.append(f"{name}_n=%d {name}_p50=%s {name}_p95=%s {name}_max=%s")
                if entry is None:
                    args.extend([0, "na", "na", "na"])
                else:
                    args.extend(
                        [
                            entry["n"],
                            _text(entry["p50"]),
                            _text(entry["p95"]),
                            _text(entry["max"]),
                        ]
                    )
            parts.append("matched=%s unmatched=%s dropped_packets=%d")
            args.extend(
                [
                    ",".join(f"{k}:{v}" for k, v in sorted(matched.items()) if v),
                    ",".join(f"{k}:{v}" for k, v in sorted(unmatched.items()) if v),
                    int(dropped),
                ]
            )
            parts.append(
                "qt_paints_no_compose=%d qt_compose_no_paint=%d "
                "qt_multi_paint_before_compose=%d qt_swap_no_compose=%d "
                "qt_compose_replaced=%d"
            )
            args.extend(
                [
                    int(counters.get("paints_without_compose", 0)),
                    int(counters.get("compose_without_paint", 0)),
                    int(counters.get("multiple_paints_before_compose", 0)),
                    int(counters.get("swap_without_compose", 0)),
                    int(counters.get("compose_replaced", 0)),
                ]
            )
            message = (
                "[PERF][P4_STAGES] screen=%s transition=%s render_path=%s frame_delta=+%d successor=%s "
                + " ".join(parts)
            )
            lines.append((message, tuple(args)))
    return lines
