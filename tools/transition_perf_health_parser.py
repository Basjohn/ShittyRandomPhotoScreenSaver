"""Transition/display performance health parser.

This tool turns the high-signal PERF/cache log shapes from mixed-refresh
transition investigations into a small automation bar.  It intentionally stays
read-only: parse logs, flag suspicious windows, and make regressions hard to
miss before we touch runtime/rendering code.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


_KV_RE = re.compile(r"([A-Za-z_]+)=([^,\s]+)")
_GL_ANIM_RE = re.compile(r"\[PERF\] \[GL ANIM\] (?P<name>.+?) metrics: (?P<payload>.*)")
_GL_PAINT_RE = re.compile(r"\[PERF\] \[GL PAINT\] (?P<name>.+?) metrics: (?P<payload>.*)")
_GL_RENDER_RE = re.compile(r"\[PERF\] \[GL RENDER\] Timer metrics: (?P<payload>.*)")
_ANIM_MANAGER_RE = re.compile(r"\[PERF\] \[ANIM\] AnimationManager metrics: (?P<payload>.*)")
_CACHE_FALLBACK_RE = re.compile(r"\[CACHE\] \[FALLBACK\] Worker fallback .*?(?P<payload>display=.*)")
_PREFETCH_STATE_RE = re.compile(
    r"prefetch_state=raw_inflight:(?P<raw_inflight>\d+),"
    r"raw_pending:(?P<raw_pending>\d+),"
    r"scaled_inflight:(?P<scaled_inflight>\d+),"
    r"scaled_pending:(?P<scaled_pending>\d+)"
)


@dataclass(frozen=True)
class MetricWindow:
    source: str
    name: str
    avg_fps: float
    target_fps: int | None = None
    dt_max_ms: float | None = None
    line: str = ""


@dataclass(frozen=True)
class CacheFallback:
    display: int | None
    reason: str
    raw_state: str
    raw_inflight: int
    raw_pending: int
    scaled_inflight: int
    scaled_pending: int
    line: str = ""

    @property
    def has_no_producer(self) -> bool:
        return (
            self.raw_inflight == 0
            and self.raw_pending == 0
            and self.scaled_inflight == 0
            and self.scaled_pending == 0
        )


@dataclass
class PerfHealthReport:
    windows: list[MetricWindow] = field(default_factory=list)
    cache_fallbacks: list[CacheFallback] = field(default_factory=list)
    shader_fallbacks: list[str] = field(default_factory=list)

    @property
    def high_target_near_sixty(self) -> list[MetricWindow]:
        return [
            window
            for window in self.windows
            if window.source == "gl_anim"
            and (window.target_fps or 0) >= 120
            and window.avg_fps <= 75.0
        ]

    @property
    def low_refresh_under_target(self) -> list[MetricWindow]:
        return [
            window
            for window in self.windows
            if window.source in {"gl_anim", "gl_render"}
            and (window.target_fps or 0) in range(55, 76)
            and window.avg_fps < 50.0
        ]

    @property
    def zero_producer_cache_fallbacks(self) -> list[CacheFallback]:
        return [fallback for fallback in self.cache_fallbacks if fallback.has_no_producer]

    @property
    def animation_manager_under_target(self) -> list[MetricWindow]:
        return [
            window
            for window in self.windows
            if window.source == "animation_manager"
            and (window.target_fps or 0) >= 55
            and window.avg_fps < max(50.0, (window.target_fps or 0) * 0.72)
        ]

    @property
    def anomalies(self) -> list[str]:
        messages: list[str] = []
        if self.high_target_near_sixty:
            messages.append(
                f"high-refresh transition windows delivered near-60fps: {len(self.high_target_near_sixty)}"
            )
        if self.low_refresh_under_target:
            messages.append(
                f"60Hz transition windows delivered far under target: {len(self.low_refresh_under_target)}"
            )
        if self.zero_producer_cache_fallbacks:
            messages.append(
                f"cache worker fallbacks had no registered producer: {len(self.zero_producer_cache_fallbacks)}"
            )
        if self.animation_manager_under_target:
            messages.append(
                f"animation manager windows delivered far under target: {len(self.animation_manager_under_target)}"
            )
        if self.shader_fallbacks:
            messages.append(f"shader fallbacks present: {len(self.shader_fallbacks)}")
        return messages


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.rstrip("ms").rstrip("Hz"))
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _parse_kv_payload(payload: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _KV_RE.finditer(payload)}


def _metric_window_from_payload(source: str, name: str, payload: str, line: str) -> MetricWindow | None:
    parts = _parse_kv_payload(payload)
    avg_fps = _parse_float(parts.get("avg_fps"))
    if avg_fps is None:
        return None
    target_fps = _parse_int(parts.get("target_fps") or parts.get("fps_target") or parts.get("target"))
    dt_max_ms = _parse_float(parts.get("dt_max"))
    return MetricWindow(
        source=source,
        name=name.strip(),
        avg_fps=avg_fps,
        target_fps=target_fps,
        dt_max_ms=dt_max_ms,
        line=line,
    )


def _cache_fallback_from_line(line: str) -> CacheFallback | None:
    match = _CACHE_FALLBACK_RE.search(line)
    if not match:
        return None
    payload = match.group("payload")
    parts = _parse_kv_payload(payload)
    state = _PREFETCH_STATE_RE.search(line)
    if state is None:
        return None
    return CacheFallback(
        display=_parse_int(parts.get("display")),
        reason=parts.get("reason", "unknown"),
        raw_state=parts.get("raw_state", "unknown"),
        raw_inflight=int(state.group("raw_inflight")),
        raw_pending=int(state.group("raw_pending")),
        scaled_inflight=int(state.group("scaled_inflight")),
        scaled_pending=int(state.group("scaled_pending")),
        line=line,
    )


def parse_perf_health_lines(lines: Iterable[str]) -> PerfHealthReport:
    report = PerfHealthReport()
    for raw in lines:
        line = raw.rstrip("\n")

        anim = _GL_ANIM_RE.search(line)
        if anim:
            window = _metric_window_from_payload(
                "gl_anim",
                anim.group("name"),
                anim.group("payload"),
                line,
            )
            if window is not None:
                report.windows.append(window)
            continue

        paint = _GL_PAINT_RE.search(line)
        if paint:
            window = _metric_window_from_payload(
                "gl_paint",
                paint.group("name"),
                paint.group("payload"),
                line,
            )
            if window is not None:
                report.windows.append(window)
            continue

        render_timer = _GL_RENDER_RE.search(line)
        if render_timer:
            window = _metric_window_from_payload(
                "gl_render",
                "render_timer",
                render_timer.group("payload"),
                line,
            )
            if window is not None:
                report.windows.append(window)
            continue

        anim_manager = _ANIM_MANAGER_RE.search(line)
        if anim_manager:
            window = _metric_window_from_payload(
                "animation_manager",
                "AnimationManager",
                anim_manager.group("payload"),
                line,
            )
            if window is not None:
                report.windows.append(window)
            continue

        cache_fallback = _cache_fallback_from_line(line)
        if cache_fallback is not None:
            report.cache_fallbacks.append(cache_fallback)
            continue

        if "[GL PAINT][FALLBACK]" in line:
            report.shader_fallbacks.append(line)

    return report


def parse_perf_health_log(path: Path) -> PerfHealthReport:
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_perf_health_lines(text.splitlines())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize transition/display perf anomalies and cache fallback producer gaps."
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs") / "screensaver_perf.log",
        help="Path to the perf/cache log file to analyze.",
    )
    parser.add_argument(
        "--fail-on-anomaly",
        action="store_true",
        help="Return exit code 2 when high-signal anomalies are present.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=4,
        help="Maximum sample lines per anomaly category.",
    )
    return parser


def _print_samples(title: str, samples: list[object], max_samples: int) -> None:
    print(f"\n{title}: {len(samples)}")
    for sample in samples[:max_samples]:
        line = getattr(sample, "line", str(sample))
        print(f"  {line}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    log_path: Path = args.log
    if not log_path.exists() or not log_path.is_file():
        print(f"Log file not found: {log_path}")
        return 1

    report = parse_perf_health_log(log_path)
    print(f"Transition perf health summary for {log_path}")
    print(f"Metric windows: {len(report.windows)}")
    print(f"Cache worker fallbacks: {len(report.cache_fallbacks)}")
    print(f"Shader fallbacks: {len(report.shader_fallbacks)}")

    _print_samples("High-refresh near-60 windows", report.high_target_near_sixty, args.max_samples)
    _print_samples("60Hz under-target windows", report.low_refresh_under_target, args.max_samples)
    _print_samples("AnimationManager under-target windows", report.animation_manager_under_target, args.max_samples)
    _print_samples("Zero-producer cache fallbacks", report.zero_producer_cache_fallbacks, args.max_samples)
    _print_samples("Shader fallbacks", report.shader_fallbacks, args.max_samples)

    if report.anomalies:
        print("\nAnomalies:")
        for anomaly in report.anomalies:
            print(f"  - {anomaly}")
        return 2 if args.fail_on_anomaly else 0

    print("\nNo high-signal transition/cache anomalies found.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI helper
    raise SystemExit(main())
