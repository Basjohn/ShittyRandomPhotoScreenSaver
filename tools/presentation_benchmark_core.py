"""Common timeline, source, metrics, pacing, and CLI benchmark contracts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import threading
from typing import Any, Sequence


DEFAULT_TARGET_HZ = (165.0, 60.0)
MAX_BOUNDED_SECONDS = 120.0
BENCHMARK_SCHEMA_VERSION = 1
NANOSECONDS_PER_SECOND = 1_000_000_000
COMMON_LOGICAL_HZ = 90
GAP_THRESHOLDS_MS = (12.0, 16.0, 25.0, 33.0, 50.0, 100.0)
SLOW_LOGICAL_STEP_MS = 25.0
MAX_OBSERVED_PHASE_OVERRUN_NS = 2 * NANOSECONDS_PER_SECOND
COMMON_SLIDE_SOURCE_SPEC = {
    "schema": 1,
    "direction": "left",
    "duration_ms": 5000,
    "easing": "linear",
    "old": {
        "background": "#14243a",
        "bands": ("#1d3557", "#24496c", "#2b5c7b", "#326f88"),
        "accent": "#7dd3fc",
    },
    "new": {
        "background": "#3a1824",
        "bands": ("#54243a", "#6b2d46", "#813750", "#98415a"),
        "accent": "#f9a8d4",
    },
    "band_count": 12,
    "accent_width_fraction": 0.035,
}
COMMON_BUBBLE_RECT_FRACTIONS = (0.10, 0.62, 0.80, 0.28)
OBSERVED_PHASE_NAMES = (
    "first_intentional_visible_frame",
    "slide_start",
    "bubble_first_logical_frame",
    "bubble_first_physical_frame",
    "slide_end",
    "synthetic_pause",
    "synthetic_resume",
    "stop_report",
)
COMPLETION_SIGNAL_SEMANTICS = {
    "qquickwindow.frameSwapped": {
        "stage": "swap_completed",
        "physical_presentation_evidence": True,
    },
    "external.presentmon.displayed": {
        "stage": "displayed",
        "physical_presentation_evidence": True,
    },
    "qrhiwidget.frameSubmitted": {
        "stage": "graphics_submission",
        "physical_presentation_evidence": False,
    },
}
RESOURCE_METRIC_UNITS = {
    "system_cpu_pct": "percent",
    "process_cpu_pct": "percent",
    "gpu_busy_pct": "percent",
    "gpu_frame_ms": "milliseconds",
    "memory_mb": "megabytes",
    "vram_mb": "megabytes",
}


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def common_workload_identity(
    timeline: "CommonBenchmarkTimeline" | None = None,
) -> dict[str, Any]:
    """Return the candidate-neutral identity of the complete Stage-1 workload."""

    resolved_timeline = timeline or COMMON_TIMELINE
    bubble_sha256 = build_common_bubble_feature_clip(resolved_timeline).sha256()
    slide_sha256 = _canonical_digest(COMMON_SLIDE_SOURCE_SPEC)
    components = {
        "timeline_sha256": resolved_timeline.sha256(),
        "slide_source_sha256": slide_sha256,
        "bubble_source_sha256": bubble_sha256,
        "bubble_rect_fractions": COMMON_BUBBLE_RECT_FRACTIONS,
    }
    return {
        **components,
        "workload_sha256": _canonical_digest(components),
    }


@dataclass(frozen=True, slots=True)
class TimelineMarker:
    name: str
    elapsed_ns: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("timeline marker name must not be empty")
        if type(self.elapsed_ns) is not int or self.elapsed_ns < 0:
            raise ValueError("timeline marker elapsed_ns must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class TimelineState:
    elapsed_ns: int
    phase: str
    slide_active: bool
    slide_progress: float
    bubble_active: bool
    playing: bool
    stopped: bool


@dataclass(frozen=True, slots=True)
class CommonBenchmarkTimeline:
    """The immutable 15-second Stage-1 Slide + Bubble workload schedule."""

    markers: tuple[TimelineMarker, ...]
    logical_hz: int = COMMON_LOGICAL_HZ

    def __post_init__(self) -> None:
        if type(self.logical_hz) is not int or self.logical_hz <= 0:
            raise ValueError("logical_hz must be a positive integer")
        names = tuple(marker.name for marker in self.markers)
        expected = (
            "first_intentional_visible_frame",
            "slide_bubble_start",
            "slide_end",
            "synthetic_pause",
            "synthetic_resume",
            "stop_report",
        )
        if names != expected:
            raise ValueError(f"timeline markers must be exactly {expected!r}")
        timestamps = tuple(marker.elapsed_ns for marker in self.markers)
        if timestamps[0] != 0:
            raise ValueError("first intentional frame must be scheduled at zero")
        if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
            raise ValueError("timeline markers must be strictly monotonic")

    @property
    def duration_ns(self) -> int:
        return self.marker_ns("stop_report")

    def marker_ns(self, name: str) -> int:
        for marker in self.markers:
            if marker.name == name:
                return marker.elapsed_ns
        raise KeyError(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_hz": self.logical_hz,
            "markers": [
                {"name": marker.name, "elapsed_ns": marker.elapsed_ns}
                for marker in self.markers
            ],
        }

    def sha256(self) -> str:
        return _canonical_digest(self.to_dict())

    def state_at(self, elapsed_ns: int) -> TimelineState:
        elapsed_ns = int(elapsed_ns)
        if elapsed_ns < 0:
            raise ValueError("elapsed_ns must be non-negative")
        start_ns = self.marker_ns("slide_bubble_start")
        slide_end_ns = self.marker_ns("slide_end")
        pause_ns = self.marker_ns("synthetic_pause")
        resume_ns = self.marker_ns("synthetic_resume")
        stop_ns = self.marker_ns("stop_report")

        if elapsed_ns < start_ns:
            phase = "startup"
        elif elapsed_ns < slide_end_ns:
            phase = "slide_bubble"
        elif elapsed_ns < pause_ns:
            phase = "settled_bubble"
        elif elapsed_ns < resume_ns:
            phase = "paused_hold"
        elif elapsed_ns < stop_ns:
            phase = "resumed_bubble"
        else:
            phase = "stopped"

        slide_span_ns = max(1, slide_end_ns - start_ns)
        slide_progress = min(
            1.0,
            max(0.0, (elapsed_ns - start_ns) / float(slide_span_ns)),
        )
        return TimelineState(
            elapsed_ns=elapsed_ns,
            phase=phase,
            slide_active=start_ns <= elapsed_ns < slide_end_ns,
            slide_progress=slide_progress,
            bubble_active=start_ns <= elapsed_ns < stop_ns,
            playing=not (pause_ns <= elapsed_ns < resume_ns),
            stopped=elapsed_ns >= stop_ns,
        )


COMMON_TIMELINE = CommonBenchmarkTimeline(
    markers=(
        TimelineMarker("first_intentional_visible_frame", 0),
        TimelineMarker("slide_bubble_start", 1 * NANOSECONDS_PER_SECOND),
        TimelineMarker("slide_end", 6 * NANOSECONDS_PER_SECOND),
        TimelineMarker("synthetic_pause", 11 * NANOSECONDS_PER_SECOND),
        TimelineMarker("synthetic_resume", 13 * NANOSECONDS_PER_SECOND),
        TimelineMarker("stop_report", 15 * NANOSECONDS_PER_SECOND),
    )
)


def common_logical_deadlines_ns(
    timeline: CommonBenchmarkTimeline = COMMON_TIMELINE,
) -> tuple[int, ...]:
    """Return drift-free logical deadlines while Bubble is active."""

    start_ns = timeline.marker_ns("slide_bubble_start")
    stop_ns = timeline.marker_ns("stop_report")
    deadlines: list[int] = []
    index = 0
    while True:
        offset_ns = (
            index * NANOSECONDS_PER_SECOND + timeline.logical_hz // 2
        ) // timeline.logical_hz
        deadline_ns = start_ns + offset_ns
        if deadline_ns >= stop_ns:
            break
        deadlines.append(deadline_ns)
        index += 1
    return tuple(deadlines)


def _unit(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 7)


def build_common_bubble_feature_clip(
    timeline: CommonBenchmarkTimeline = COMMON_TIMELINE,
):
    """Build the deterministic feature-only Bubble source shared by candidates."""

    from widgets.spotify_visualizer.feature_frame import (
        BandEnergy,
        EnergyLanes,
        FeatureClip,
        FeatureFrame,
        RAW_BAR_COUNT,
        TransientEnergy,
        WAVEFORM_COUNT,
    )

    frames = []
    beat_period = max(1, timeline.logical_hz // 2)
    for index, timestamp_ns in enumerate(common_logical_deadlines_ns(timeline)):
        state = timeline.state_at(timestamp_ns)
        if state.playing:
            beat_offset = index % beat_period
            beat_envelope = math.exp(-beat_offset / 8.0)
            bass = _unit(0.16 + 0.68 * beat_envelope)
            mid = _unit(0.14 + 0.28 * (0.5 + 0.5 * math.sin(index * 0.071)))
            high = _unit(0.10 + 0.22 * (0.5 + 0.5 * math.sin(index * 0.113 + 1.2)))
            onset_detected = beat_offset == 0
        else:
            bass = mid = high = 0.0
            onset_detected = False

        overall = _unit((bass + mid + high) / 3.0)

        def _lane(scale: float) -> BandEnergy:
            values = tuple(_unit(value * scale) for value in (bass, mid, high))
            return BandEnergy(*values, _unit(sum(values) / 3.0))

        continuous = _lane(1.0)
        pre_agc = _lane(0.86)
        bubble = BandEnergy(
            bass,
            _unit(mid * 0.82),
            _unit(high * 0.68),
            _unit((bass + mid * 0.82 + high * 0.68) / 3.0),
        )
        transient = TransientEnergy(
            bass if onset_detected else 0.0,
            _unit(mid * 0.5) if onset_detected else 0.0,
            _unit(high * 0.35) if onset_detected else 0.0,
            _unit((bass + mid * 0.5 + high * 0.35) / 3.0)
            if onset_detected
            else 0.0,
            onset_detected,
            "bass" if onset_detected else "",
            1.0 if onset_detected else 0.0,
        )
        if not state.playing:
            raw_bars = (0.0,) * RAW_BAR_COUNT
            waveform = (0.0,) * WAVEFORM_COUNT
        else:
            raw_bars = tuple(
                _unit(
                    (
                        bass * (1.0 - bar_index / 14.0)
                        if bar_index < 10
                        else mid
                        if bar_index < 22
                        else high
                    )
                    * (0.96 + 0.04 * math.sin((index + bar_index) * 0.37))
                )
                for bar_index in range(RAW_BAR_COUNT)
            )
            waveform = tuple(
                round(
                    overall
                    * math.sin(
                        sample_index * math.tau * 3.0 / WAVEFORM_COUNT
                        + index * 0.19
                    ),
                    7,
                )
                for sample_index in range(WAVEFORM_COUNT)
            )
        frames.append(
            FeatureFrame(
                timestamp_us=timestamp_ns // 1_000,
                energy=EnergyLanes(continuous, pre_agc, bubble, transient),
                raw_bars=raw_bars,
                waveform=waveform,
                playing=state.playing,
                visible=state.bubble_active,
                mode="bubble",
            )
        )
    return FeatureClip("presentation_benchmark_bubble", tuple(frames))


def _numeric_summary(
    values: Sequence[float],
    *,
    include_gap_counts: bool = False,
) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values)
    result: dict[str, Any] = {
        "count": len(ordered),
        "p50": percentile(ordered, 0.50),
        "p90": percentile(ordered, 0.90),
        "p95": percentile(ordered, 0.95),
        "p99": percentile(ordered, 0.99),
        "max": ordered[-1] if ordered else 0.0,
    }
    if include_gap_counts:
        result["counts_gte_ms"] = {
            f"{threshold:g}": sum(value >= threshold for value in ordered)
            for threshold in GAP_THRESHOLDS_MS
        }
    return result


@dataclass
class BenchmarkMetricsRecorder:
    """Candidate-neutral event recorder for the common evidence schema."""

    candidate: str
    population: str
    display: str
    target_hz: float
    completion_signal: str
    source_sha256: str
    timeline: CommonBenchmarkTimeline = COMMON_TIMELINE
    source_components: dict[str, Any] = field(default_factory=dict)
    requested_opportunities: int = 0
    accepted_requests: int = 0
    logical_steps: int = 0
    skipped_deadlines: int = 0
    slow_steps: int = 0
    failures: int = 0
    gui_callback_count: int = 0
    _frame_timestamps_ns: list[int] = field(default_factory=list, repr=False)
    _paint_ms: list[float] = field(default_factory=list, repr=False)
    _request_age_ms: list[float] = field(default_factory=list, repr=False)
    _source_age_ms: list[float] = field(default_factory=list, repr=False)
    _logical_timestamps_ns: list[int] = field(default_factory=list, repr=False)
    _observed_phases_ns: dict[str, int] = field(default_factory=dict, repr=False)
    _large_gaps: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _resource_samples: dict[str, list[float]] = field(default_factory=dict, repr=False)
    _gui_thread_id: int | None = field(default=None, repr=False)
    _render_thread_id: int | None = field(default=None, repr=False)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not self.candidate or not self.population or not self.display:
            raise ValueError("candidate, population, and display are required")
        if not self.completion_signal:
            raise ValueError("completion_signal is required")
        if self.completion_signal not in COMPLETION_SIGNAL_SEMANTICS:
            allowed = ", ".join(sorted(COMPLETION_SIGNAL_SEMANTICS))
            raise ValueError(f"unsupported completion signal; expected one of: {allowed}")
        if not self.source_sha256:
            raise ValueError("source_sha256 is required")
        rate = float(self.target_hz)
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError("target_hz must be finite and greater than zero")
        self.target_hz = rate

    def mark_phase(self, name: str, elapsed_ns: int) -> None:
        with self._lock:
            if name not in OBSERVED_PHASE_NAMES:
                raise ValueError(f"unsupported observed phase: {name}")
            if name in self._observed_phases_ns:
                raise ValueError(f"phase already marked: {name}")
            elapsed_ns = int(elapsed_ns)
            latest_allowed_ns = (
                self.timeline.duration_ns + MAX_OBSERVED_PHASE_OVERRUN_NS
            )
            if not 0 <= elapsed_ns <= latest_allowed_ns:
                raise ValueError("phase elapsed_ns must be within the bounded observation window")
            if self._observed_phases_ns:
                previous_name = next(reversed(self._observed_phases_ns))
                previous_ns = self._observed_phases_ns[previous_name]
                if OBSERVED_PHASE_NAMES.index(name) <= OBSERVED_PHASE_NAMES.index(previous_name):
                    raise ValueError("observed phases must follow the canonical order")
                if elapsed_ns <= previous_ns:
                    raise ValueError("observed phase timestamps must be strictly monotonic")
            self._observed_phases_ns[str(name)] = elapsed_ns

    def record_request(self, *, accepted: bool) -> None:
        with self._lock:
            self.requested_opportunities += 1
            if accepted:
                self.accepted_requests += 1

    def record_logical_step(
        self,
        *,
        completed_ns: int,
        scheduled_ns: int | None = None,
        skipped_deadlines: int = 0,
        failed: bool = False,
    ) -> None:
        with self._lock:
            completed_ns = int(completed_ns)
            if self._logical_timestamps_ns and completed_ns < self._logical_timestamps_ns[-1]:
                raise ValueError("logical step timestamps must be monotonic")
            self._logical_timestamps_ns.append(completed_ns)
            self.logical_steps += 1
            self.skipped_deadlines += max(0, int(skipped_deadlines))
            if failed:
                self.failures += 1
            if scheduled_ns is not None:
                duration_ms = max(0.0, (completed_ns - int(scheduled_ns)) / 1_000_000.0)
                if duration_ms >= SLOW_LOGICAL_STEP_MS:
                    self.slow_steps += 1

    def record_gui_callback(self) -> None:
        with self._lock:
            self.gui_callback_count += 1

    def set_logical_runtime_totals(
        self,
        *,
        steps: int,
        skipped_deadlines: int,
        slow_steps: int,
        failures: int,
    ) -> None:
        """Install the authoritative totals reported by VisualizerLogicalRuntime."""

        values = (steps, skipped_deadlines, slow_steps, failures)
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("logical runtime totals must be non-negative integers")
        with self._lock:
            self.logical_steps = steps
            self.skipped_deadlines = skipped_deadlines
            self.slow_steps = slow_steps
            self.failures = failures

    def record_completed_frame(
        self,
        *,
        consumed_ns: int,
        completed_ns: int,
        paint_ms: float | None = None,
        requested_ns: int | None = None,
        logical_published_ns: int | None = None,
    ) -> None:
        with self._lock:
            consumed_ns = int(consumed_ns)
            completed_ns = int(completed_ns)
            if consumed_ns > completed_ns:
                raise ValueError("consume timestamp cannot follow completion")
            if self._frame_timestamps_ns and completed_ns <= self._frame_timestamps_ns[-1]:
                raise ValueError("completion timestamps must be strictly monotonic")
            previous_ns = self._frame_timestamps_ns[-1] if self._frame_timestamps_ns else None
            request_age_ms = None
            source_age_ms = None
            if requested_ns is not None:
                if int(requested_ns) > consumed_ns:
                    raise ValueError("request timestamp cannot follow consume")
                request_age_ms = max(0.0, (consumed_ns - int(requested_ns)) / 1_000_000.0)
            if logical_published_ns is not None:
                if int(logical_published_ns) > consumed_ns:
                    raise ValueError("logical publication timestamp cannot follow consume")
                source_age_ms = max(
                    0.0,
                    (consumed_ns - int(logical_published_ns)) / 1_000_000.0,
                )
            self._frame_timestamps_ns.append(completed_ns)
            if paint_ms is not None:
                self._paint_ms.append(max(0.0, float(paint_ms)))
            if request_age_ms is not None:
                self._request_age_ms.append(request_age_ms)
            if source_age_ms is not None:
                self._source_age_ms.append(source_age_ms)
            if previous_ns is not None:
                gap_ms = (completed_ns - previous_ns) / 1_000_000.0
                if gap_ms >= 25.0:
                    state = self.timeline.state_at(completed_ns)
                    nearest = min(
                        self.timeline.markers,
                        key=lambda marker: abs(marker.elapsed_ns - completed_ns),
                    )
                    self._large_gaps.append(
                        {
                            "completed_ns": completed_ns,
                            "gap_ms": gap_ms,
                            "phase": state.phase,
                            "nearest_marker": nearest.name,
                            "request_age_ms": request_age_ms,
                            "source_age_ms": source_age_ms,
                        }
                    )

    def record_resource_sample(self, **values: float | int | None) -> None:
        with self._lock:
            unknown = sorted(set(values) - set(RESOURCE_METRIC_UNITS))
            if unknown:
                raise ValueError(f"unsupported resource metrics: {', '.join(unknown)}")
            for name, value in values.items():
                if value is None:
                    continue
                sample = float(value)
                if not math.isfinite(sample):
                    raise ValueError(f"resource sample {name} must be finite")
                self._resource_samples.setdefault(str(name), []).append(sample)

    def set_thread_identity(self, *, gui_thread_id: int, render_thread_id: int) -> None:
        with self._lock:
            self._gui_thread_id = int(gui_thread_id)
            self._render_thread_id = int(render_thread_id)

    def report(self, *, elapsed_ns: int | None = None) -> dict[str, Any]:
        with self._lock:
            return self._report_unlocked(elapsed_ns=elapsed_ns)

    def _report_unlocked(self, *, elapsed_ns: int | None = None) -> dict[str, Any]:
        duration_ns = self.timeline.duration_ns if elapsed_ns is None else int(elapsed_ns)
        duration_s = max(0.0, duration_ns / NANOSECONDS_PER_SECOND)
        frame_intervals_ms = [
            (right - left) / 1_000_000.0
            for left, right in zip(self._frame_timestamps_ns, self._frame_timestamps_ns[1:])
        ]
        logical_holes_ms = [
            (right - left) / 1_000_000.0
            for left, right in zip(
                self._logical_timestamps_ns,
                self._logical_timestamps_ns[1:],
            )
        ]
        resource_summary = {}
        missing_resources = []
        for name, unit in RESOURCE_METRIC_UNITS.items():
            samples = self._resource_samples.get(name, [])
            if not samples:
                missing_resources.append(name)
            resource_summary[name] = {
                "unit": unit,
                "status": "recorded" if samples else "missing",
                **_numeric_summary(samples),
            }
        if self._render_thread_id is None or self._gui_thread_id is None:
            thread_relationship = "not_recorded"
        elif self._render_thread_id == self._gui_thread_id:
            thread_relationship = "same"
        else:
            thread_relationship = "distinct"
        completion_semantics = COMPLETION_SIGNAL_SEMANTICS[
            self.completion_signal
        ]
        physical_evidence = bool(
            completion_semantics["physical_presentation_evidence"]
        )
        return {
            "schema_version": BENCHMARK_SCHEMA_VERSION,
            "candidate": self.candidate,
            "population": self.population,
            "display": self.display,
            "target_hz": self.target_hz,
            "completion_signal": self.completion_signal,
            "completion_semantics": dict(completion_semantics),
            "timeline_sha256": self.timeline.sha256(),
            "source_sha256": self.source_sha256,
            "source_components": dict(self.source_components),
            "planned_phase_timestamps_ns": {
                marker.name: marker.elapsed_ns for marker in self.timeline.markers
            },
            "observed_phase_timestamps_ns": dict(sorted(self._observed_phases_ns.items())),
            "missing_observed_phases": [
                name for name in OBSERVED_PHASE_NAMES if name not in self._observed_phases_ns
            ],
            "counts": {
                "requested_opportunities": self.requested_opportunities,
                "accepted_requests": self.accepted_requests,
                "completion_signal_frames": len(self._frame_timestamps_ns),
                "completed_physical_frames": (
                    len(self._frame_timestamps_ns) if physical_evidence else None
                ),
                "logical_steps": self.logical_steps,
                "skipped_deadlines": self.skipped_deadlines,
                "slow_steps": self.slow_steps,
                "failures": self.failures,
                "gui_callbacks": self.gui_callback_count,
            },
            "rates": {
                "request_acceptance_pct": (
                    self.accepted_requests / self.requested_opportunities * 100.0
                    if self.requested_opportunities
                    else 0.0
                ),
                "completion_signal_fps": (
                    len(self._frame_timestamps_ns) / duration_s if duration_s else 0.0
                ),
                "completed_physical_fps": (
                    len(self._frame_timestamps_ns) / duration_s
                    if duration_s and physical_evidence
                    else None
                ),
            },
            "timing_ms": {
                "completion_dt": _numeric_summary(
                    frame_intervals_ms,
                    include_gap_counts=True,
                ),
                "paint": _numeric_summary(self._paint_ms),
                "request_age": _numeric_summary(self._request_age_ms),
                "logical_publication_to_render_consume_age": _numeric_summary(
                    self._source_age_ms
                ),
                "longest_logical_hole": max(logical_holes_ms, default=0.0),
            },
            "large_completion_gaps": list(self._large_gaps),
            "resources": resource_summary,
            "missing_required_resource_metrics": missing_resources,
            "physical_evidence_valid": physical_evidence,
            "thread_identity": {
                "gui_thread_id": self._gui_thread_id,
                "render_thread_id": self._render_thread_id,
                "relationship": thread_relationship,
            },
        }


def _bounded_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("seconds must be a number") from exc
    if not math.isfinite(seconds) or seconds <= 0.0:
        raise argparse.ArgumentTypeError("seconds must be finite and greater than zero")
    if seconds > MAX_BOUNDED_SECONDS:
        raise argparse.ArgumentTypeError(
            f"seconds must not exceed {MAX_BOUNDED_SECONDS:g} for this bounded harness"
        )
    return seconds


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _target_hz_list(value: str) -> tuple[float, ...]:
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("target-hz requires one or more comma-separated rates")
    rates: list[float] = []
    for part in parts:
        try:
            rate = float(part)
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError(f"invalid target rate: {part!r}") from exc
        if not math.isfinite(rate) or not 1.0 <= rate <= 1000.0:
            raise argparse.ArgumentTypeError(
                "target rates must be finite and between 1 and 1000 Hz"
            )
        rates.append(rate)
    return tuple(rates)


def build_spike_parser(*, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--seconds", type=_bounded_seconds, default=15.0)
    parser.add_argument("--windows", type=_positive_int, default=2)
    parser.add_argument(
        "--target-hz",
        type=_target_hz_list,
        default=DEFAULT_TARGET_HZ,
        metavar="HZ[,HZ...]",
        help="target pace per window; one value applies to every window",
    )
    parser.add_argument(
        "--load-label",
        default="light",
        help="operator-provided environment label only; this harness creates no load",
    )
    parser.add_argument(
        "--throughput-probe",
        action="store_true",
        help="explicit unpaced afterFrameEnd throughput control; invalid as architecture evidence",
    )
    parser.add_argument(
        "--basic",
        action="store_true",
        help="force the GUI-thread render-loop negative control; invalid as architecture evidence",
    )
    return parser


def parse_spike_args(
    argv: Sequence[str] | None,
    *,
    description: str,
) -> argparse.Namespace:
    parser = build_spike_parser(description=description)
    args = parser.parse_args(argv)
    rates = tuple(float(rate) for rate in args.target_hz)
    if len(rates) == 1:
        rates = rates * int(args.windows)
    elif len(rates) != int(args.windows):
        parser.error("--target-hz must provide one rate or exactly one rate per window")
    args.target_hz = rates
    args.load_label = str(args.load_label).strip() or "unlabelled"
    return args


def build_candidate_parser(*, description: str) -> argparse.ArgumentParser:
    """Build the strict parser shared by production-shaped benchmark candidates."""

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--population",
        choices=("P0", "P1"),
        default="P0",
        help="P0 is the minimal discriminator; P1 adds the static production population",
    )
    parser.add_argument(
        "--target-hz",
        type=_target_hz_list,
        default=DEFAULT_TARGET_HZ,
        metavar="HZ[,HZ]",
        help="one rate for both displays or exactly two display rates",
    )
    parser.add_argument(
        "--load-label",
        default="light",
        help="operator-provided environment label only; the harness creates no load",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new JSON result path; existing files are never overwritten",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="stable unique label for this one bounded 15-second run",
    )
    return parser


def parse_candidate_args(
    argv: Sequence[str] | None,
    *,
    description: str,
) -> argparse.Namespace:
    parser = build_candidate_parser(description=description)
    args = parser.parse_args(argv)
    rates = tuple(float(rate) for rate in args.target_hz)
    if len(rates) == 1:
        rates = rates * 2
    elif len(rates) != 2:
        parser.error("--target-hz must provide one rate or exactly two rates")
    args.target_hz = rates
    args.load_label = str(args.load_label).strip() or "unlabelled"
    args.run_id = str(args.run_id).strip()
    if not args.run_id:
        parser.error("--run-id must not be empty")
    args.output = Path(args.output).expanduser().resolve()
    if args.output.exists():
        parser.error(f"--output already exists: {args.output}")
    return args


@dataclass(frozen=True)
class PacingDecision:
    due_opportunities: int
    next_delay_ms: int


@dataclass
class TargetPacerState:
    """Monotonic latest-opportunity pacing with no catch-up request burst."""

    target_hz: float
    requested_opportunities: int = 0
    paced_requests: int = 0
    skipped_deadlines: int = 0
    next_deadline_ns: int | None = None

    def __post_init__(self) -> None:
        rate = float(self.target_hz)
        if not math.isfinite(rate) or rate <= 0.0:
            raise ValueError("target_hz must be finite and greater than zero")
        self.target_hz = rate
        self.interval_ns = max(1, int(round(1_000_000_000.0 / rate)))

    def start(self, now_ns: int) -> None:
        self.next_deadline_ns = int(now_ns)

    def consume(self, now_ns: int) -> PacingDecision:
        now_ns = int(now_ns)
        if self.next_deadline_ns is None:
            self.start(now_ns)

        deadline = int(self.next_deadline_ns)
        if now_ns < deadline:
            return PacingDecision(
                due_opportunities=0,
                next_delay_ms=max(1, math.ceil((deadline - now_ns) / 1_000_000.0)),
            )

        due = 1 + ((now_ns - deadline) // self.interval_ns)
        self.requested_opportunities += int(due)
        self.paced_requests += 1
        self.skipped_deadlines += max(0, int(due) - 1)
        self.next_deadline_ns = deadline + int(due) * self.interval_ns
        delay_ns = max(0, int(self.next_deadline_ns) - now_ns)
        return PacingDecision(
            due_opportunities=int(due),
            next_delay_ms=max(1, math.ceil(delay_ns / 1_000_000.0)),
        )


def validate_window_screen_count(window_count: int, screen_count: int) -> None:
    """Reject silent multi-window aliasing when physical screens are absent."""

    if int(screen_count) <= 0:
        raise ValueError("Qt reported no screens")
    if int(window_count) > int(screen_count):
        raise ValueError(
            f"requested {int(window_count)} windows but Qt reported only "
            f"{int(screen_count)} physical screens"
        )


def percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(
        len(sorted_values) - 1,
        max(0, int(round((len(sorted_values) - 1) * float(fraction)))),
    )
    return float(sorted_values[index])
