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
_TIME_RE = re.compile(r"(?P<ts>(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2})")
_GL_ANIM_RE = re.compile(r"\[PERF\] \[GL ANIM\] (?P<name>.+?) metrics: (?P<payload>.*)")
_GL_PAINT_RE = re.compile(r"\[PERF\] \[GL PAINT\] (?P<name>.+?) metrics: (?P<payload>.*)")
_GL_RENDER_RE = re.compile(r"\[PERF\] \[GL RENDER\] Timer metrics: (?P<payload>.*)")
_ANIM_MANAGER_RE = re.compile(r"\[PERF\] \[ANIM\] AnimationManager metrics: (?P<payload>.*)")
_TIMER_GAP_RE = re.compile(
    r"\[PERF\] \[TIMER\] Large gap for (?P<owner>[^:]+): (?P<gap_ms>[0-9.]+)ms"
)
_SPOTIFY_LATENCY_RE = re.compile(r"\[SPOTIFY_VIS\]\[LATENCY\] lag_ms=(?P<lag_ms>[0-9.]+)")
_SPOTIFY_SEVERE_LATENCY_RE = re.compile(r"\[!!!!\]\[SPOTIFY_VIS\]\[LATENCY\] lag_ms=(?P<lag_ms>[0-9.]+)")
_SPOTIFY_TICK_SPIKE_RE = re.compile(r"\[PERF\] \[SPOTIFY_VIS\] Tick dt spike_ms=(?P<dt_ms>[0-9.]+)")
_FRAME_BUDGET_SPIKE_RE = re.compile(r"\[PERF\] \[FRAME\] (?P<detail>.*)")
_SETTINGS_PERF_RE = re.compile(r"\[PERF\]\[SETTINGS\](?P<detail>.*)")
_SETTINGS_DURATION_RE = re.compile(
    r"(?P<name>.+?)\s+(?:in|took)\s+(?P<duration_ms>[0-9.]+)\s*ms"
)
_DISPLAY_PERF_RE = re.compile(r"\[PERF\]\[DISPLAY\](?P<detail>.*)")
_DISPLAY_SHOW_RE = re.compile(r"Showing on screen (?P<screen>\d+):")
_STARTUP_FIRST_FRAME_RE = re.compile(
    r"\[STARTUP\] First frame committed on screen=(?P<screen>\d+).*?elapsed_ms=(?P<elapsed_ms>[0-9.]+|N/A)"
)
_GEO_SAVE_RE = re.compile(r"\[GEO_AUDIT\].*phase=save_scene")
_SLOW_TEXTURE_UPLOAD_RE = re.compile(
    r"\[PERF\] \[GL TEXTURE\] Slow upload: (?P<duration_ms>[0-9.]+)ms "
    r"\((?P<width>\d+)x(?P<height>\d+), pbo=(?P<pbo>True|False)\)"
)
_PENDING_PAINT_REQUEUE_RE = re.compile(r"\[PERF\] \[GL RENDER\] Pending paint update exceeded coalescing window")
_PENDING_PAINT_STALL_RE = re.compile(r"\[PERF\] \[GL RENDER\] Paint update still pending without delivery")
_GL_SWAP_INTERVAL_WARNING_RE = re.compile(r"\[PERF\]\[GL COMPOSITOR\]\[WARNING\] GL context may still be swap-interval constrained")
_CACHE_FALLBACK_RE = re.compile(r"\[CACHE\] \[FALLBACK\] Worker fallback .*?(?P<payload>display=.*)")
_VISUALIZER_CUSTOM_SUPPRESSION_RE = re.compile(
    r"\[SPOTIFY_VIS\]\[FALLBACK\] Suppressing CUSTOM visualizer creation because no exact local custom rect is available"
)
_VISUALIZER_CUSTOM_BUCKET_REPAIR_RE = re.compile(
    r"\[SPOTIFY_VIS\]\[FALLBACK\] Repaired spotify_visualizer CUSTOM rect bucket from single foreign saved rect"
)
_PREFETCH_STATE_RE = re.compile(
    r"prefetch_state=raw_inflight:(?P<raw_inflight>\d+),"
    r"raw_pending:(?P<raw_pending>\d+),"
    r"scaled_inflight:(?P<scaled_inflight>\d+),"
    r"scaled_pending:(?P<scaled_pending>\d+)"
)


@dataclass(frozen=True)
class MetricWindow:
    timestamp: str | None
    source: str
    name: str
    avg_fps: float
    target_fps: int | None = None
    screen: int | None = None
    dt_max_ms: float | None = None
    active_count: int | None = None
    listener_count: int | None = None
    max_active_count: int | None = None
    max_listener_count: int | None = None
    pending_skip_count: int | None = None
    wakeup_count: int | None = None
    duration_ms: float | None = None
    owner: str | None = None
    line: str = ""

    @property
    def is_high_refresh(self) -> bool:
        return (self.target_fps or 0) >= 120

    @property
    def target_ratio(self) -> float | None:
        if not self.target_fps:
            return None
        return self.avg_fps / float(self.target_fps)


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


@dataclass(frozen=True)
class TimerGap:
    owner: str
    gap_ms: float
    line: str = ""


@dataclass(frozen=True)
class VisualizerTimingWarning:
    kind: str
    value_ms: float
    line: str = ""


@dataclass(frozen=True)
class TextureUploadWarning:
    duration_ms: float
    width: int
    height: int
    pbo: bool
    line: str = ""


@dataclass(frozen=True)
class SettingsStall:
    name: str
    duration_ms: float
    line: str = ""


@dataclass(frozen=True)
class PaintDeliveryStarvation:
    render: MetricWindow
    paint: MetricWindow

    @property
    def line(self) -> str:
        return (
            f"{self.paint.timestamp or '<no-ts>'} screen={self.paint.screen} "
            f"target={self.paint.target_fps}Hz render_avg={self.render.avg_fps:.1f} "
            f"paint_avg={self.paint.avg_fps:.1f} transition={self.paint.name}"
        )


@dataclass(frozen=True)
class TimelineMarker:
    timestamp: str | None
    kind: str
    detail: str
    line: str = ""


@dataclass(frozen=True)
class StartupFirstFrameExposure:
    screen: int
    show_timestamp: str | None
    first_frame_timestamp: str | None
    exposure_ms: float
    first_frame_elapsed_ms: float | None
    line: str = ""


@dataclass
class PerfHealthReport:
    windows: list[MetricWindow] = field(default_factory=list)
    cache_fallbacks: list[CacheFallback] = field(default_factory=list)
    shader_fallbacks: list[str] = field(default_factory=list)
    gl_swap_interval_warnings: list[str] = field(default_factory=list)
    pending_paint_requeues: list[str] = field(default_factory=list)
    pending_paint_stalls: list[str] = field(default_factory=list)
    timer_gaps: list[TimerGap] = field(default_factory=list)
    visualizer_timing_warnings: list[VisualizerTimingWarning] = field(default_factory=list)
    texture_upload_warnings: list[TextureUploadWarning] = field(default_factory=list)
    settings_stalls: list[SettingsStall] = field(default_factory=list)
    visualizer_custom_suppressions: list[str] = field(default_factory=list)
    visualizer_custom_bucket_repairs: list[str] = field(default_factory=list)
    startup_first_frame_exposures: list[StartupFirstFrameExposure] = field(default_factory=list)
    timeline_markers: list[TimelineMarker] = field(default_factory=list)

    @property
    def high_target_near_sixty(self) -> list[MetricWindow]:
        return [
            window
            for window in self.windows
            if window.source in {"gl_paint", "gl_render"}
            and (window.target_fps or 0) >= 120
            and window.avg_fps <= 75.0
        ]

    @property
    def high_target_stable_divisor_windows(self) -> list[MetricWindow]:
        """High-refresh visual windows that look locked to a stable lower cadence.

        This is intentionally not a generic "below target" check.  It catches
        suspicious divisor-like cadence such as a 165Hz display painting around
        82.5Hz or 55Hz, and a 144Hz display painting around 72Hz or 48Hz.
        """
        suspicious: list[MetricWindow] = []
        for window in self.windows:
            if window.source not in {"gl_paint", "gl_anim"} or not window.is_high_refresh:
                continue
            target = float(window.target_fps or 0)
            if target <= 0.0:
                continue
            for divisor in (2, 3):
                expected = target / divisor
                tolerance = max(3.0, expected * 0.08)
                if abs(window.avg_fps - expected) <= tolerance:
                    suspicious.append(window)
                    break
        return suspicious

    @property
    def high_target_under_delivered(self) -> list[MetricWindow]:
        return [
            window
            for window in self.windows
            if window.source in {"gl_paint", "gl_render"}
            and (window.target_fps or 0) >= 120
            and window.avg_fps < float(window.target_fps or 0) * 0.75
        ]

    @property
    def high_target_render_paint_split_windows(self) -> list[MetricWindow]:
        """Paint windows where the target is high but visible cadence is not.

        Render-timer logs can stay healthy while QWidget paint delivery falls
        behind.  This property names that seam directly so the next pass does
        not conflate a good timer with good visible frame delivery.
        """
        return [
            window
            for window in self.windows
            if window.source == "gl_paint"
            and window.is_high_refresh
            and window.avg_fps < float(window.target_fps or 0) * 0.70
        ]

    @property
    def render_timer_pending_skip_windows(self) -> list[MetricWindow]:
        """Render windows where the timer woke but paint updates were coalesced."""
        return [
            window
            for window in self.windows
            if window.source == "gl_render"
            and (window.pending_skip_count or 0) > 0
        ]

    @property
    def paint_delivery_starvation_windows(self) -> list[PaintDeliveryStarvation]:
        """Paired windows where the render timer is healthy but paint delivery is not."""
        render_by_key: dict[tuple[str | None, int | None, int | None], MetricWindow] = {}
        for window in self.windows:
            if window.source != "gl_render":
                continue
            render_by_key[(window.timestamp, window.screen, window.target_fps)] = window

        starved: list[PaintDeliveryStarvation] = []
        for paint in self.windows:
            if paint.source != "gl_paint" or not paint.target_fps:
                continue
            render = render_by_key.get((paint.timestamp, paint.screen, paint.target_fps))
            if render is None:
                continue
            render_ratio = render.target_ratio or 0.0
            paint_ratio = paint.target_ratio or 0.0
            if render_ratio < 0.90:
                continue
            if paint.target_fps >= 120 and paint_ratio < 0.75:
                starved.append(PaintDeliveryStarvation(render=render, paint=paint))
            elif 55 <= paint.target_fps <= 75 and paint_ratio < 0.85:
                starved.append(PaintDeliveryStarvation(render=render, paint=paint))
        return starved

    @property
    def low_refresh_under_target(self) -> list[MetricWindow]:
        return [
            window
            for window in self.windows
            if window.source in {"gl_anim", "gl_paint", "gl_render"}
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
            and (
                window.active_count is None
                or window.active_count > 0
                or (window.max_active_count is not None and window.max_active_count > 0)
                or (window.duration_ms is not None and window.duration_ms >= 1000.0)
                or (window.listener_count is not None and window.listener_count > 0)
                or (window.max_listener_count is not None and window.max_listener_count > 0)
            )
            and (window.target_fps or 0) >= 55
            and window.avg_fps < max(50.0, (window.target_fps or 0) * 0.72)
        ]

    @property
    def animation_manager_under_target_unknown_owner(self) -> list[MetricWindow]:
        return [
            window
            for window in self.animation_manager_under_target
            if window.owner in {None, "", "<unknown>"}
        ]

    @property
    def idle_animation_manager_under_target(self) -> list[MetricWindow]:
        return [
            window
            for window in self.animation_manager_under_target
            if window.active_count == 0
            and window.listener_count == 0
            and window.max_active_count == 0
            and window.max_listener_count == 0
        ]

    @property
    def high_target_animation_callback_collapse(self) -> list[MetricWindow]:
        """High-refresh transition control callbacks that fell near 60Hz.

        `GL ANIM` is the AnimationManager/control cadence, not necessarily the
        final visible shader cadence now that paint-time interpolation exists.
        Keep it separate so diagnostics do not conflate control starvation with
        paint delivery starvation.
        """
        return [
            window
            for window in self.windows
            if window.source == "gl_anim"
            and window.is_high_refresh
            and window.avg_fps < max(75.0, float(window.target_fps or 0) * 0.50)
        ]

    @property
    def media_timer_starvation_gaps(self) -> list[TimerGap]:
        return [
            gap
            for gap in self.timer_gaps
            if "MediaWidget" in gap.owner and gap.gap_ms >= 1800.0
        ]

    @property
    def significant_visualizer_timing_warnings(self) -> list[VisualizerTimingWarning]:
        return [
            warning
            for warning in self.visualizer_timing_warnings
            if warning.value_ms >= 40.0
        ]

    @property
    def severe_visualizer_latency_warnings(self) -> list[VisualizerTimingWarning]:
        return [
            warning
            for warning in self.visualizer_timing_warnings
            if warning.kind == "severe_latency" or warning.value_ms >= 500.0
        ]

    @property
    def slow_texture_uploads(self) -> list[TextureUploadWarning]:
        return [
            warning
            for warning in self.texture_upload_warnings
            if warning.duration_ms >= 16.0
        ]

    @property
    def significant_settings_stalls(self) -> list[SettingsStall]:
        return [
            stall
            for stall in self.settings_stalls
            if stall.duration_ms >= 1000.0
        ]

    @property
    def risky_startup_first_frame_exposures(self) -> list[StartupFirstFrameExposure]:
        return [
            exposure
            for exposure in self.startup_first_frame_exposures
            if exposure.exposure_ms >= 750.0
        ]

    @property
    def anomalies(self) -> list[str]:
        messages: list[str] = []
        if self.paint_delivery_starvation_windows:
            messages.append(
                "paint delivery starvation with healthy render timer: "
                f"{len(self.paint_delivery_starvation_windows)}"
            )
        if self.high_target_near_sixty:
            messages.append(
                f"high-refresh transition windows delivered near-60fps: {len(self.high_target_near_sixty)}"
            )
        divisor_locked = [
            window
            for window in self.high_target_stable_divisor_windows
            if window not in self.high_target_near_sixty
        ]
        if divisor_locked:
            messages.append(
                "high-refresh transition windows look divisor/cadence locked: "
                f"{len(divisor_locked)}"
            )
        split_windows = [
            window
            for window in self.high_target_render_paint_split_windows
            if window not in self.high_target_near_sixty
            and window not in divisor_locked
        ]
        if split_windows:
            messages.append(
                "high-refresh render/paint cadence split windows: "
                f"{len(split_windows)}"
            )
        under_delivered = [
            window
            for window in self.high_target_under_delivered
            if window not in self.high_target_near_sixty
        ]
        if under_delivered:
            messages.append(
                "high-refresh transition windows delivered far under target: "
                f"{len(under_delivered)}"
            )
        if self.low_refresh_under_target:
            messages.append(
                f"60Hz transition windows delivered far under target: {len(self.low_refresh_under_target)}"
            )
        if self.high_target_animation_callback_collapse:
            messages.append(
                "high-refresh animation/control callback cadence collapsed near 60Hz: "
                f"{len(self.high_target_animation_callback_collapse)}"
            )
        if self.zero_producer_cache_fallbacks:
            messages.append(
                f"cache worker fallbacks had no registered producer: {len(self.zero_producer_cache_fallbacks)}"
            )
        if self.animation_manager_under_target:
            messages.append(
                f"animation manager windows delivered far under target: {len(self.animation_manager_under_target)}"
            )
        if self.animation_manager_under_target_unknown_owner:
            messages.append(
                "animation manager under-target windows lack concrete owner: "
                f"{len(self.animation_manager_under_target_unknown_owner)}"
            )
        if self.idle_animation_manager_under_target:
            messages.append(
                "animation manager timer ran under target with no active work: "
                f"{len(self.idle_animation_manager_under_target)}"
            )
        if self.shader_fallbacks:
            messages.append(f"shader fallbacks present: {len(self.shader_fallbacks)}")
        if self.gl_swap_interval_warnings:
            messages.append(
                "GL contexts may still be swap-interval constrained despite timer-only policy: "
                f"{len(self.gl_swap_interval_warnings)}"
            )
        if self.pending_paint_requeues:
            messages.append(
                "transition paint request coalescing rescues fired: "
                f"{len(self.pending_paint_requeues)}"
            )
        if self.pending_paint_stalls:
            messages.append(
                "paint update delivery stalls observed without requeue: "
                f"{len(self.pending_paint_stalls)}"
            )
        if self.render_timer_pending_skip_windows:
            messages.append(
                "render timer wakeups skipped because paint was already pending: "
                f"{len(self.render_timer_pending_skip_windows)}"
            )
        if self.media_timer_starvation_gaps:
            messages.append(
                f"media widget timer gaps suggest cadence starvation: {len(self.media_timer_starvation_gaps)}"
            )
        if self.significant_visualizer_timing_warnings:
            messages.append(
                "spotify visualizer timing warnings present: "
                f"{len(self.significant_visualizer_timing_warnings)}"
            )
        if self.severe_visualizer_latency_warnings:
            messages.append(
                "spotify visualizer severe latency warnings present: "
                f"{len(self.severe_visualizer_latency_warnings)}"
            )
        if self.slow_texture_uploads:
            messages.append(
                f"slow GL texture uploads present: {len(self.slow_texture_uploads)}"
            )
        if self.significant_settings_stalls:
            messages.append(
                "settings UI stalls above 1s present: "
                f"{len(self.significant_settings_stalls)}"
            )
        if self.risky_startup_first_frame_exposures:
            messages.append(
                "startup first-frame exposure windows risk visible placeholder flicker: "
                f"{len(self.risky_startup_first_frame_exposures)}"
            )
        if self.visualizer_custom_suppressions:
            messages.append(
                "spotify visualizer CUSTOM creation suppressions present: "
                f"{len(self.visualizer_custom_suppressions)}"
            )
        if self.visualizer_custom_bucket_repairs:
            messages.append(
                "spotify visualizer CUSTOM rect bucket repairs present: "
                f"{len(self.visualizer_custom_bucket_repairs)}"
            )
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


def _timestamp_from_line(line: str) -> str | None:
    match = _TIME_RE.search(line)
    return match.group("ts") if match else None


def _timestamp_seconds(timestamp: str | None) -> int | None:
    if not timestamp:
        return None
    time_part = timestamp.rsplit(" ", 1)[-1]
    parts = time_part.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _metric_window_from_payload(source: str, name: str, payload: str, line: str) -> MetricWindow | None:
    parts = _parse_kv_payload(payload)
    avg_fps = _parse_float(parts.get("avg_fps"))
    if avg_fps is None:
        return None
    target_fps = _parse_int(parts.get("target_fps") or parts.get("fps_target") or parts.get("target"))
    screen = _parse_int(parts.get("screen"))
    dt_max_ms = _parse_float(parts.get("dt_max"))
    active_count = _parse_int(parts.get("active_count"))
    listener_count = _parse_int(parts.get("listeners"))
    max_active_count = _parse_int(parts.get("max_active"))
    max_listener_count = _parse_int(parts.get("max_listeners"))
    pending_skip_count = _parse_int(parts.get("pending_skips"))
    wakeup_count = _parse_int(parts.get("wakeups"))
    duration_ms = _parse_float(parts.get("duration"))
    owner = parts.get("owner")
    return MetricWindow(
        timestamp=_timestamp_from_line(line),
        source=source,
        name=name.strip(),
        avg_fps=avg_fps,
        target_fps=target_fps,
        screen=screen,
        dt_max_ms=dt_max_ms,
        active_count=active_count,
        listener_count=listener_count,
        max_active_count=max_active_count,
        max_listener_count=max_listener_count,
        pending_skip_count=pending_skip_count,
        wakeup_count=wakeup_count,
        duration_ms=duration_ms,
        owner=owner,
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
    display_show_by_screen: dict[int, tuple[str | None, str]] = {}
    for raw in lines:
        line = raw.rstrip("\n")
        timestamp = _timestamp_from_line(line)

        display_show = _DISPLAY_SHOW_RE.search(line)
        if display_show:
            screen = int(display_show.group("screen"))
            display_show_by_screen[screen] = (timestamp, line)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "display_show", f"screen={screen}", line)
            )
            continue

        startup_first_frame = _STARTUP_FIRST_FRAME_RE.search(line)
        if startup_first_frame:
            screen = int(startup_first_frame.group("screen"))
            show_timestamp, _show_line = display_show_by_screen.get(screen, (None, ""))
            show_seconds = _timestamp_seconds(show_timestamp)
            frame_seconds = _timestamp_seconds(timestamp)
            exposure_ms = 0.0
            if show_seconds is not None and frame_seconds is not None:
                delta_seconds = frame_seconds - show_seconds
                if delta_seconds < 0:
                    delta_seconds += 24 * 60 * 60
                exposure_ms = float(delta_seconds * 1000)
            elapsed_ms = _parse_float(startup_first_frame.group("elapsed_ms"))
            report.startup_first_frame_exposures.append(
                StartupFirstFrameExposure(
                    screen=screen,
                    show_timestamp=show_timestamp,
                    first_frame_timestamp=timestamp,
                    exposure_ms=exposure_ms,
                    first_frame_elapsed_ms=elapsed_ms,
                    line=(
                        f"{timestamp or '<no-ts>'} screen={screen} exposure_ms={exposure_ms:.1f} "
                        f"first_frame_elapsed_ms={elapsed_ms if elapsed_ms is not None else 'N/A'}"
                    ),
                )
            )
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "startup_first_frame",
                    f"screen={screen} exposure_ms={exposure_ms:.1f}",
                    line,
                )
            )
            continue

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

        timer_gap = _TIMER_GAP_RE.search(line)
        if timer_gap:
            gap_ms = _parse_float(timer_gap.group("gap_ms"))
            if gap_ms is not None:
                report.timer_gaps.append(
                    TimerGap(
                        owner=timer_gap.group("owner").strip(),
                        gap_ms=gap_ms,
                        line=line,
                    )
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "timer_gap", timer_gap.group("owner").strip(), line)
                )
            continue

        severe_spotify_latency = _SPOTIFY_SEVERE_LATENCY_RE.search(line)
        if severe_spotify_latency:
            lag_ms = _parse_float(severe_spotify_latency.group("lag_ms"))
            if lag_ms is not None:
                report.visualizer_timing_warnings.append(
                    VisualizerTimingWarning("severe_latency", lag_ms, line)
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "spotify_severe_latency", f"lag_ms={lag_ms:.1f}", line)
                )
            continue

        spotify_latency = _SPOTIFY_LATENCY_RE.search(line)
        if spotify_latency:
            lag_ms = _parse_float(spotify_latency.group("lag_ms"))
            if lag_ms is not None:
                report.visualizer_timing_warnings.append(
                    VisualizerTimingWarning("latency", lag_ms, line)
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "spotify_latency", f"lag_ms={lag_ms:.1f}", line)
                )
            continue

        spotify_tick_spike = _SPOTIFY_TICK_SPIKE_RE.search(line)
        if spotify_tick_spike:
            dt_ms = _parse_float(spotify_tick_spike.group("dt_ms"))
            if dt_ms is not None:
                report.visualizer_timing_warnings.append(
                    VisualizerTimingWarning("tick_spike", dt_ms, line)
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "spotify_tick_spike", f"dt_ms={dt_ms:.1f}", line)
                )
            continue

        texture_upload = _SLOW_TEXTURE_UPLOAD_RE.search(line)
        if texture_upload:
            duration_ms = _parse_float(texture_upload.group("duration_ms"))
            if duration_ms is not None:
                report.texture_upload_warnings.append(
                    TextureUploadWarning(
                        duration_ms=duration_ms,
                        width=int(texture_upload.group("width")),
                        height=int(texture_upload.group("height")),
                        pbo=texture_upload.group("pbo") == "True",
                        line=line,
                    )
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "slow_texture_upload", f"duration_ms={duration_ms:.1f}", line)
                )
            continue

        if _PENDING_PAINT_REQUEUE_RE.search(line):
            report.pending_paint_requeues.append(line)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "pending_paint_requeue", "ui-pressure rescue fired", line)
            )
            continue

        if _PENDING_PAINT_STALL_RE.search(line):
            report.pending_paint_stalls.append(line)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "pending_paint_stall", "no_requeue=True", line)
            )
            continue

        if _VISUALIZER_CUSTOM_SUPPRESSION_RE.search(line):
            report.visualizer_custom_suppressions.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "visualizer_custom_suppression",
                    "no exact local custom rect",
                    line,
                )
            )
            continue

        if _VISUALIZER_CUSTOM_BUCKET_REPAIR_RE.search(line):
            report.visualizer_custom_bucket_repairs.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "visualizer_custom_bucket_repair",
                    "single foreign rect promoted",
                    line,
                )
            )
            continue

        cache_fallback = _cache_fallback_from_line(line)
        if cache_fallback is not None:
            report.cache_fallbacks.append(cache_fallback)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "cache_fallback", cache_fallback.reason, line)
            )
            continue

        if "[GL PAINT][FALLBACK]" in line:
            report.shader_fallbacks.append(line)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "shader_fallback", "GL paint fallback", line)
            )
            continue

        if _GL_SWAP_INTERVAL_WARNING_RE.search(line):
            report.gl_swap_interval_warnings.append(line)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "gl_swap_interval_warning", "swap interval constrained", line)
            )
            continue

        frame_spike = _FRAME_BUDGET_SPIKE_RE.search(line)
        if frame_spike:
            report.timeline_markers.append(
                TimelineMarker(timestamp, "frame_budget_spike", frame_spike.group("detail"), line)
            )
            continue

        settings_perf = _SETTINGS_PERF_RE.search(line)
        if settings_perf:
            detail = settings_perf.group("detail").strip()
            duration_match = _SETTINGS_DURATION_RE.search(detail)
            if duration_match:
                duration_ms = _parse_float(duration_match.group("duration_ms"))
                if duration_ms is not None:
                    report.settings_stalls.append(
                        SettingsStall(
                            name=duration_match.group("name").strip(),
                            duration_ms=duration_ms,
                            line=line,
                        )
                    )
            report.timeline_markers.append(TimelineMarker(timestamp, "settings_stall", detail, line))
            continue

        display_perf = _DISPLAY_PERF_RE.search(line)
        if display_perf:
            report.timeline_markers.append(
                TimelineMarker(timestamp, "display_lifecycle", display_perf.group("detail").strip(), line)
            )
            continue

        if _GEO_SAVE_RE.search(line):
            report.timeline_markers.append(
                TimelineMarker(timestamp, "geometry_save", "save_scene", line)
            )

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
    parser.add_argument(
        "--timeline",
        action="store_true",
        help="Print timeline markers that can explain cadence collapse.",
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
    print(f"GL swap-interval warnings: {len(report.gl_swap_interval_warnings)}")
    print(f"Pending paint requeues: {len(report.pending_paint_requeues)}")
    print(f"Pending paint stalls: {len(report.pending_paint_stalls)}")
    print(f"Render pending skips: {len(report.render_timer_pending_skip_windows)}")
    print(f"Timer gaps: {len(report.timer_gaps)}")
    print(f"Spotify visualizer timing warnings: {len(report.visualizer_timing_warnings)}")
    print(f"Slow GL texture uploads: {len(report.texture_upload_warnings)}")
    print(f"Settings stalls: {len(report.settings_stalls)}")
    print(f"Startup first-frame exposures: {len(report.startup_first_frame_exposures)}")
    print(f"Spotify visualizer CUSTOM suppressions: {len(report.visualizer_custom_suppressions)}")
    print(f"Spotify visualizer CUSTOM bucket repairs: {len(report.visualizer_custom_bucket_repairs)}")
    print(f"Timeline markers: {len(report.timeline_markers)}")

    _print_samples(
        "Paint delivery starvation windows",
        report.paint_delivery_starvation_windows,
        args.max_samples,
    )
    _print_samples("High-refresh near-60 windows", report.high_target_near_sixty, args.max_samples)
    _print_samples(
        "High-refresh stable-divisor windows",
        report.high_target_stable_divisor_windows,
        args.max_samples,
    )
    _print_samples(
        "High-refresh render/paint split windows",
        report.high_target_render_paint_split_windows,
        args.max_samples,
    )
    _print_samples("High-refresh under-target windows", report.high_target_under_delivered, args.max_samples)
    _print_samples("60Hz under-target windows", report.low_refresh_under_target, args.max_samples)
    _print_samples(
        "High-refresh animation/control callback collapse windows",
        report.high_target_animation_callback_collapse,
        args.max_samples,
    )
    _print_samples("AnimationManager under-target windows", report.animation_manager_under_target, args.max_samples)
    _print_samples("MediaWidget timer starvation gaps", report.media_timer_starvation_gaps, args.max_samples)
    _print_samples(
        "Spotify visualizer timing warnings",
        report.significant_visualizer_timing_warnings,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer severe latency warnings",
        report.severe_visualizer_latency_warnings,
        args.max_samples,
    )
    _print_samples("Slow GL texture uploads", report.slow_texture_uploads, args.max_samples)
    _print_samples("Significant settings stalls", report.significant_settings_stalls, args.max_samples)
    _print_samples(
        "Risky startup first-frame exposures",
        report.risky_startup_first_frame_exposures,
        args.max_samples,
    )
    _print_samples("Zero-producer cache fallbacks", report.zero_producer_cache_fallbacks, args.max_samples)
    _print_samples("Spotify visualizer CUSTOM suppressions", report.visualizer_custom_suppressions, args.max_samples)
    _print_samples("Spotify visualizer CUSTOM bucket repairs", report.visualizer_custom_bucket_repairs, args.max_samples)
    _print_samples("Shader fallbacks", report.shader_fallbacks, args.max_samples)
    _print_samples("GL swap-interval warnings", report.gl_swap_interval_warnings, args.max_samples)
    _print_samples("Pending paint requeues", report.pending_paint_requeues, args.max_samples)
    _print_samples("Pending paint stalls", report.pending_paint_stalls, args.max_samples)
    _print_samples("Render pending skips", report.render_timer_pending_skip_windows, args.max_samples)
    if args.timeline:
        _print_samples("Timeline markers", report.timeline_markers, args.max_samples)

    if report.anomalies:
        print("\nAnomalies:")
        for anomaly in report.anomalies:
            print(f"  - {anomaly}")
        return 2 if args.fail_on_anomaly else 0

    print("\nNo high-signal transition/cache anomalies found.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI helper
    raise SystemExit(main())
