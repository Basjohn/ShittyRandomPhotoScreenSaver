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
from datetime import date
from pathlib import Path
from typing import Iterable


_KV_RE = re.compile(r"([A-Za-z_]+)=([^,\s]+)")
_TIME_RE = re.compile(r"(?P<ts>(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2})")
_GL_ANIM_RE = re.compile(r"\[PERF\] \[GL ANIM\] (?P<name>.+?) metrics: (?P<payload>.*)")
_GL_PAINT_RE = re.compile(r"\[PERF\] \[GL PAINT\] (?P<name>.+?) metrics: (?P<payload>.*)")
_GL_PAINT_PATH_RE = re.compile(r"\[PERF\] \[GL PAINT PATH\] (?P<payload>.*)")
_GL_RENDER_RE = re.compile(r"\[PERF\] \[GL RENDER\] Timer metrics: (?P<payload>.*)")
_ANIM_MANAGER_RE = re.compile(r"\[PERF\] \[ANIM\] AnimationManager metrics: (?P<payload>.*)")
_TIMER_GAP_RE = re.compile(
    r"\[PERF\] \[TIMER\] Large gap for (?P<owner>[^:]+): (?P<gap_ms>[0-9.]+)ms"
)
_SPOTIFY_LATENCY_RE = re.compile(r"\[SPOTIFY_VIS\]\[LATENCY\] lag_ms=(?P<lag_ms>[0-9.]+)")
_SPOTIFY_SEVERE_LATENCY_RE = re.compile(r"\[!!!!\]\[SPOTIFY_VIS\]\[LATENCY\] lag_ms=(?P<lag_ms>[0-9.]+)")
_SPOTIFY_TICK_SPIKE_RE = re.compile(r"\[PERF\] \[SPOTIFY_VIS\] Tick dt spike_ms=(?P<dt_ms>[0-9.]+)")
_SPOTIFY_TICK_PHASE_RE = re.compile(r"\[PERF\] \[SPOTIFY_VIS\] Tick phase breakdown (?P<detail>.*)")
_SPOTIFY_GPU_PUSH_RE = re.compile(r"\[PERF\] \[SPOTIFY_VIS\] GPU push breakdown (?P<detail>.*)")
_SPOTIFY_DEVCURVE_WORKER_RE = re.compile(
    r"\[PERF\] \[SPOTIFY_VIS\]\[DEVCURVE\] worker_ms=(?P<worker_ms>[0-9.]+) "
    r"pending=(?P<pending>True|False)"
)
_SPOTIFY_OVERLAY_PERF_RE = re.compile(r"\[PERF\]\[SPOTIFY_VIS\]\[OVERLAY\](?P<detail>.*)")
_SPOTIFY_OVERLAY_MICROGAP_RE = re.compile(r"\[PERF\]\[SPOTIFY_VIS\]\[MICROGAP\](?P<detail>.*)")
_SPOTIFY_SURFACE_RE = re.compile(
    r"\[SPOTIFY_VIS\]\[SURFACE\] Renderer target=(?P<target>\S+) "
    r"reason=(?P<reason>\S+) screen=(?P<screen>\S+)"
)
_SPOTIFY_VIS_SYNC_PERF_RE = re.compile(r"\[PERF\]\[SPOTIFY_VIS\]\[VIS_SYNC\](?P<detail>.*)")
_MEDIA_EMIT_PERF_RE = re.compile(r"\[PERF\]\[MEDIA_WIDGET\] emit_media_update(?P<detail>.*)")
_MEDIA_REFRESH_PERF_RE = re.compile(r"\[PERF\]\[MEDIA_WIDGET\]\[REFRESH\](?P<detail>.*)")
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
    r"\((?P<width>\d+)x(?P<height>\d+), pbo=(?P<pbo>True|False)"
    r"(?:, convert=(?P<convert_ms>[0-9.]+)ms, copy=(?P<copy_ms>[0-9.]+)ms, "
    r"pbo_stage=(?P<pbo_stage_ms>[0-9.]+)ms, "
    r"tex_upload=(?P<tex_upload_ms>[0-9.]+)ms"
    r"(?:, direct=(?P<direct>True|False))?)?\)"
)
_GL_TEXTURE_CACHE_RE = re.compile(
    r"\[PERF\] \[GL TEXTURE CACHE\] cleanup (?P<payload>.*)"
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
_SPOTIFY_VIS_CREATED_RE = re.compile(
    r"\[SPOTIFY_VIS\] Created visualizer widget \(screen=(?P<screen>\d+),.*?monitor=(?P<monitor>[^,\)]+)"
)
_MEDIA_CONTROLLER_RE = re.compile(r"\[MEDIA_WIDGET\] Using controller: (?P<controller>\S+)")
_PREFETCH_STATE_RE = re.compile(
    r"prefetch_state=raw_inflight:(?P<raw_inflight>\d+),"
    r"raw_pending:(?P<raw_pending>\d+),"
    r"scaled_inflight:(?P<scaled_inflight>\d+),"
    r"scaled_pending:(?P<scaled_pending>\d+)"
)
_USAGE_SAMPLE_RE = re.compile(r"\[USAGE\] sample (?P<payload>.*)")
_VISUALIZER_SAFEGUARD_FAILURE_RE = re.compile(
    r"(?P<detail>Reveal watchdog expired|Failed to push frame|"
    r"\[FIRST_FRAME_GUARD\].*(?:failed|expired|timeout|stale)|"
    r"\[PARITY\].*(?:failed|mismatch))",
    re.IGNORECASE,
)
_TRANSITION_START_REFUSAL_RE = re.compile(
    r"(?:Transition failed to start|Transition refused/failed to start)"
)
_TRANSITION_INSTANT_COMMIT_RE = re.compile(r"displaying final image immediately")
_TRANSITION_REQUEST_DROP_RE = re.compile(
    r"Transition in progress - skipping (?:image )?request"
)
_GL_PROGRAM_LIFECYCLE_ERROR_RE = re.compile(
    r"(?:Failed to delete (?:shader program|private card-flip program)|"
    r"glDeleteProgram\(\d+\).*GL_INVALID_VALUE|"
    r"Transition program admission failed|"
    r"glUniform\w*\(\d+.*GL_INVALID_OPERATION|"
    r"baseOperation\s*=\s*gl(?:DeleteProgram|Uniform\w*))"
)
_GL_AFFINITY_ERROR_RE = re.compile(
    r"(?:Cannot make QOpenGLContext current in a different thread|"
    r"\[GL COMPOSITOR\]\[AFFINITY\]\[ERROR\]|Qt GL affinity violation)"
)
_ADAPTIVE_STOP_ACK_RE = re.compile(
    r"\[PERF\]\[ADAPTIVE_TIMER\] asynchronous_stop_ack "
    r"screen=(?P<screen>\S+) latency_ms=(?P<latency_ms>[0-9.]+) "
    r"immediate=(?P<immediate>True|False)"
)
_GL_TERMINAL_TRANSACTION_ERROR_RE = re.compile(
    r"(?:\[GL COMPOSITOR\]\[TERMINAL\]\[ERROR\]|"
    r"Terminal transition completion failed)"
)
_STALE_IMAGE_PUBLICATION_RE = re.compile(r"\[ASYNC(?:-PREV)?\]\[STALE\]")


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
    presentation_dirty_generation: int | None = None
    presentation_ack_generation: int | None = None
    presentation_generation_lag: int | None = None
    visualizer_request_count: int | None = None
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

    @property
    def pending_skip_ratio(self) -> float | None:
        if not self.wakeup_count:
            return None
        return float(self.pending_skip_count or 0) / float(self.wakeup_count)


@dataclass(frozen=True)
class PaintPathWindow:
    timestamp: str | None
    screen: int | None
    elapsed_ms: float
    total: int
    idle_gl: int
    transition_gl: int
    idle_qpainter_fallback: int
    transition_qpainter_fallback: int
    idle_gl_avg_ms: float
    idle_gl_max_ms: float
    transition_gl_avg_ms: float
    transition_gl_max_ms: float
    idle_qpainter_avg_ms: float
    idle_qpainter_max_ms: float
    transition_qpainter_avg_ms: float
    transition_qpainter_max_ms: float
    line: str = ""

    @property
    def fallback_count(self) -> int:
        return self.idle_qpainter_fallback + self.transition_qpainter_fallback

    @property
    def fallback_ratio(self) -> float:
        return self.fallback_count / max(1, self.total)


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
    timestamp: str | None = None
    mode: str | None = None
    trigger: str | None = None


@dataclass(frozen=True)
class UsageSample:
    timestamp: str | None
    sequence: int
    cadence_gap_ms: float
    skipped: int
    collect_ms: float
    cpu_primed: bool
    cpu_app_pct: float | None
    cpu_main_pct: float | None
    cpu_system_pct: float | None
    rss_app_mb: float
    private_app_mb: float | None
    vms_app_mb: float | None
    threads_app: int
    handles_app: int | None
    gpu_supported: bool
    gpu_active: bool
    gpu_busy_pct: float | None
    vram_supported: bool
    vram_dedicated_mb: float | None
    tm_active: int
    rm_total: int | None = None
    rm_gl_total: int | None = None
    rm_gl_texture: int | None = None
    rm_gl_vbo: int | None = None
    rm_gl_vao: int | None = None
    rm_gl_program: int | None = None
    rm_gl_framebuffer: int | None = None
    rm_gl_renderbuffer: int | None = None
    rm_gl_texture_est_mb: float | None = None
    rm_gl_pbo_est_mb: float | None = None
    img_cache_items: int | None = None
    img_cache_max_items: int | None = None
    img_cache_est_mb: float | None = None
    img_cache_budget_mb: float | None = None
    img_cache_hits: int | None = None
    img_cache_misses: int | None = None
    img_cache_evictions: int | None = None
    tm_io_submitted: int | None = None
    tm_io_completed: int | None = None
    tm_io_failed: int | None = None
    tm_compute_submitted: int | None = None
    tm_compute_completed: int | None = None
    tm_compute_failed: int | None = None
    cpu_hot_threads: tuple[tuple[str, float], ...] = ()
    line: str = ""


def _usage_growth_anomalies_for_samples(samples: list[UsageSample]) -> list[str]:
    baseline = samples[1]
    latest = samples[-1]
    anomalies: list[str] = []
    rss_growth = latest.rss_app_mb - baseline.rss_app_mb
    rss_growth_flagged = (
        rss_growth >= 128.0
        and latest.rss_app_mb >= baseline.rss_app_mb * 1.20
    )
    if rss_growth_flagged:
        anomalies.append(f"app RSS grew {rss_growth:.1f}MB across usage samples")
        if baseline.img_cache_est_mb is not None and latest.img_cache_est_mb is not None:
            image_cache_growth = latest.img_cache_est_mb - baseline.img_cache_est_mb
            if image_cache_growth >= 16.0:
                anomalies.append(
                    "ImageCache estimate grew "
                    f"{image_cache_growth:.1f}MB alongside RSS; decoded-image cache "
                    "warm-up is a plausible contributor"
                )
            else:
                anomalies.append(
                    "ImageCache estimate remained effectively flat during RSS growth; "
                    "current telemetry does not attribute that growth to the decoded-image cache"
                )
    if baseline.private_app_mb is not None and latest.private_app_mb is not None:
        private_growth = latest.private_app_mb - baseline.private_app_mb
        if private_growth >= 128.0 and latest.private_app_mb >= baseline.private_app_mb * 1.20:
            anomalies.append(
                f"app private memory grew {private_growth:.1f}MB across usage samples"
            )
    if baseline.vms_app_mb is not None and latest.vms_app_mb is not None:
        vms_growth = latest.vms_app_mb - baseline.vms_app_mb
        if vms_growth >= 256.0 and latest.vms_app_mb >= baseline.vms_app_mb * 1.15:
            anomalies.append(
                f"app virtual memory grew {vms_growth:.1f}MB across usage samples"
            )
    thread_growth = latest.threads_app - baseline.threads_app
    if thread_growth >= 8:
        anomalies.append(f"app thread count grew by {thread_growth} across usage samples")
    if baseline.handles_app is not None and latest.handles_app is not None:
        handle_growth = latest.handles_app - baseline.handles_app
        if handle_growth >= 128:
            anomalies.append(f"app handle count grew by {handle_growth} across usage samples")
    if baseline.vram_dedicated_mb is not None and latest.vram_dedicated_mb is not None:
        vram_growth = latest.vram_dedicated_mb - baseline.vram_dedicated_mb
        vram_growth_flagged = (
            vram_growth >= 256.0
            and latest.vram_dedicated_mb >= baseline.vram_dedicated_mb * 1.25
        )
        if vram_growth_flagged:
            anomalies.append(f"dedicated VRAM grew {vram_growth:.1f}MB across usage samples")
            if (
                baseline.rm_gl_texture_est_mb is not None
                and latest.rm_gl_texture_est_mb is not None
                and baseline.rm_gl_pbo_est_mb is not None
                and latest.rm_gl_pbo_est_mb is not None
            ):
                registered_growth = (
                    latest.rm_gl_texture_est_mb
                    + latest.rm_gl_pbo_est_mb
                    - baseline.rm_gl_texture_est_mb
                    - baseline.rm_gl_pbo_est_mb
                )
                if registered_growth >= 16.0:
                    anomalies.append(
                        "registered compositor texture/PBO estimate grew "
                        f"{registered_growth:.1f}MB alongside dedicated VRAM"
                    )
                else:
                    anomalies.append(
                        "registered compositor texture/PBO estimate remained effectively flat "
                        "during dedicated VRAM growth; current telemetry does not attribute it "
                        "to GLTextureManager cache/PBO ownership"
                    )
    if baseline.rm_gl_total is not None and latest.rm_gl_total is not None:
        gl_growth = latest.rm_gl_total - baseline.rm_gl_total
        if gl_growth >= 8:
            anomalies.append(
                f"ResourceManager GL registrations grew by {gl_growth} across usage samples"
            )
    if baseline.rm_gl_texture is not None and latest.rm_gl_texture is not None:
        texture_growth = latest.rm_gl_texture - baseline.rm_gl_texture
        if texture_growth >= 8:
            anomalies.append(
                "ResourceManager texture registrations grew by "
                f"{texture_growth} across usage samples"
            )
    if baseline.rm_total is not None and latest.rm_total is not None:
        resource_growth = latest.rm_total - baseline.rm_total
        if resource_growth >= 32:
            anomalies.append(
                f"ResourceManager total registrations grew by {resource_growth} "
                "across usage samples"
            )
    if (
        baseline.tm_compute_submitted is not None
        and baseline.tm_compute_completed is not None
        and latest.tm_compute_submitted is not None
        and latest.tm_compute_completed is not None
    ):
        baseline_backlog = baseline.tm_compute_submitted - baseline.tm_compute_completed
        latest_backlog = latest.tm_compute_submitted - latest.tm_compute_completed
        backlog_growth = latest_backlog - baseline_backlog
        if latest_backlog >= 8 and backlog_growth >= 8:
            anomalies.append(
                "ThreadManager compute backlog grew by "
                f"{backlog_growth} to {latest_backlog} tasks"
            )
    return anomalies


@dataclass(frozen=True)
class UsageVisualizerCorrelation:
    usage: UsageSample
    warning: VisualizerTimingWarning

    @property
    def line(self) -> str:
        cpu_app = (
            f"{self.usage.cpu_app_pct:.1f}%"
            if self.usage.cpu_app_pct is not None
            else "na"
        )
        return (
            f"{self.usage.timestamp or '<no-ts>'} cpu_app={cpu_app} "
            f"rss={self.usage.rss_app_mb:.1f}MB gpu={self.usage.gpu_busy_pct if self.usage.gpu_busy_pct is not None else 'na'} "
            f"visualizer={self.warning.kind}:{self.warning.value_ms:.1f}ms"
        )


@dataclass(frozen=True)
class VisualizerSafeguardFailure:
    timestamp: str | None
    detail: str
    line: str = ""


@dataclass(frozen=True)
class VisualizerTickPhaseBreakdown:
    timestamp: str | None
    total_ms: float
    mode: str
    transition_active: bool
    changed: bool
    first_frame: bool
    used_gpu: bool
    phases_ms: dict[str, float]
    line: str = ""

    @property
    def dominant_phase(self) -> tuple[str, float] | None:
        if not self.phases_ms:
            return None
        return max(self.phases_ms.items(), key=lambda item: item[1])

    @property
    def summary(self) -> str:
        dominant = self.dominant_phase
        if dominant is None:
            dominant_text = "dominant=<unknown>"
        else:
            dominant_text = f"dominant={dominant[0]}:{dominant[1]:.2f}ms"
        return (
            f"{self.timestamp or '<no-ts>'} total_ms={self.total_ms:.2f} "
            f"mode={self.mode} transition_active={self.transition_active} "
            f"{dominant_text}"
        )


@dataclass(frozen=True)
class VisualizerGpuPushBreakdown:
    """A slow GPU-push event with its synchronous preparation subphases."""

    timestamp: str | None
    total_ms: float
    mode: str
    extra_build_ms: float
    primer_ms: float
    packet_build_ms: float
    parent_publish_ms: float
    line: str = ""

    @property
    def dominant_phase(self) -> tuple[str, float]:
        phases = {
            "extra_build": self.extra_build_ms,
            "primer": self.primer_ms,
            "packet_build": self.packet_build_ms,
            "parent_publish": self.parent_publish_ms,
        }
        return max(phases.items(), key=lambda item: item[1])

    @property
    def summary(self) -> str:
        dominant_name, dominant_ms = self.dominant_phase
        return (
            f"{self.timestamp or '<no-ts>'} total_ms={self.total_ms:.2f} "
            f"mode={self.mode} dominant={dominant_name}:{dominant_ms:.2f}ms"
        )


@dataclass(frozen=True)
class VisualizerDevCurveWorkerSample:
    timestamp: str | None
    worker_ms: float
    pending: bool
    line: str = ""


@dataclass(frozen=True)
class AdaptiveRenderOwnerStopAck:
    timestamp: str | None
    screen: int | None
    latency_ms: float
    immediate: bool
    line: str = ""


@dataclass(frozen=True)
class MediaRefreshWarning:
    timestamp: str | None
    total_ms: float
    worker_ms: float
    callback_ms: float
    ui_delay_ms: float
    state: str
    line: str = ""

    @property
    def dominant_phase(self) -> tuple[str, float]:
        phases = {
            "worker": self.worker_ms,
            "callback": self.callback_ms,
            "ui_delay": self.ui_delay_ms,
        }
        return max(phases.items(), key=lambda item: item[1])


@dataclass(frozen=True)
class TextureUploadWarning:
    duration_ms: float
    width: int
    height: int
    pbo: bool
    convert_ms: float | None = None
    copy_ms: float | None = None
    pbo_stage_ms: float | None = None
    tex_upload_ms: float | None = None
    direct: bool | None = None
    line: str = ""

    @property
    def dominant_phase(self) -> tuple[str, float] | None:
        phases = {
            "convert": self.convert_ms,
            "copy": self.copy_ms,
            "pbo_stage": self.pbo_stage_ms,
            "tex_upload": self.tex_upload_ms,
        }
        measured = {
            name: value for name, value in phases.items() if value is not None
        }
        if not measured:
            return None
        return max(measured.items(), key=lambda item: item[1])


@dataclass(frozen=True)
class TextureCacheCleanup:
    textures: int
    texture_mb: float
    pbo_count: int
    pbo_mb: float
    hits: int
    misses: int
    uploads: int
    evictions: int
    managed_releases: int
    pbo_replacements: int
    registrations: int
    shared_leases: int = 0
    shared_group_textures: int = 0
    shared_group_texture_mb: float = 0.0
    shared_group_managers: int = 0
    shared_acquisitions: int = 0
    shared_reuses: int = 0
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
class SpotifyTopologyEvent:
    timestamp: str | None
    kind: str
    screen: int | None = None
    monitor: str | None = None
    detail: str = ""
    line: str = ""


@dataclass(frozen=True)
class SpotifySurfaceSelection:
    timestamp: str | None
    target: str
    reason: str
    screen: int | None
    line: str = ""


@dataclass(frozen=True)
class SpotifyTopologyStarvation:
    starvation: PaintDeliveryStarvation
    visualizer: SpotifyTopologyEvent
    media_seen: bool

    @property
    def line(self) -> str:
        media = "media_seen" if self.media_seen else "media_unknown"
        return (
            f"{self.starvation.line} spotify_visualizer_screen={self.visualizer.screen} "
            f"monitor={self.visualizer.monitor or '<unknown>'} {media}"
        )


@dataclass(frozen=True)
class SpotifyOverlayPerfWindow:
    timestamp: str | None
    reason: str
    screen: int | None
    mode: str
    surface: str
    elapsed_ms: float
    set_state_count: int
    paint_count: int
    update_request_count: int
    geometry_change_count: int
    fbo_resize_count: int
    fbo_render_count: int
    texture_reuse_count: int
    render_failure_count: int
    retained_last_good_count: int
    visible: bool
    enabled: bool
    playing: bool | None = None
    line: str = ""

    @property
    def elapsed_seconds(self) -> float:
        return max(self.elapsed_ms / 1000.0, 0.001)

    @property
    def set_state_fps(self) -> float:
        return self.set_state_count / self.elapsed_seconds

    @property
    def paint_fps(self) -> float:
        return self.paint_count / self.elapsed_seconds

    @property
    def update_request_fps(self) -> float:
        return self.update_request_count / self.elapsed_seconds


@dataclass(frozen=True)
class SpotifyOverlayMicrogapWindow:
    timestamp: str | None
    reason: str
    screen: int | None
    mode: str
    surface: str
    context: str
    gap_samples: int
    gap_p95_ms: float
    gap_max_ms: float
    wait_samples: int
    wait_p95_ms: float
    wait_max_ms: float
    pending_wait_ms: float
    visible: bool
    enabled: bool
    playing: bool | None = None
    line: str = ""


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
    paint_path_windows: list[PaintPathWindow] = field(default_factory=list)
    cache_fallbacks: list[CacheFallback] = field(default_factory=list)
    shader_fallbacks: list[str] = field(default_factory=list)
    transition_start_refusals: list[str] = field(default_factory=list)
    transition_instant_commits: list[str] = field(default_factory=list)
    transition_request_drops: list[str] = field(default_factory=list)
    gl_program_lifecycle_errors: list[str] = field(default_factory=list)
    gl_affinity_errors: list[str] = field(default_factory=list)
    adaptive_render_owner_stop_acks: list[AdaptiveRenderOwnerStopAck] = field(default_factory=list)
    gl_terminal_transaction_errors: list[str] = field(default_factory=list)
    stale_image_publications: list[str] = field(default_factory=list)
    gl_swap_interval_warnings: list[str] = field(default_factory=list)
    pending_paint_requeues: list[str] = field(default_factory=list)
    pending_paint_stalls: list[str] = field(default_factory=list)
    timer_gaps: list[TimerGap] = field(default_factory=list)
    visualizer_timing_warnings: list[VisualizerTimingWarning] = field(default_factory=list)
    visualizer_safeguard_failures: list[VisualizerSafeguardFailure] = field(default_factory=list)
    usage_samples: list[UsageSample] = field(default_factory=list)
    visualizer_tick_phase_breakdowns: list[VisualizerTickPhaseBreakdown] = field(default_factory=list)
    visualizer_gpu_push_breakdowns: list[VisualizerGpuPushBreakdown] = field(default_factory=list)
    visualizer_devcurve_worker_samples: list[VisualizerDevCurveWorkerSample] = field(default_factory=list)
    media_refresh_warnings: list[MediaRefreshWarning] = field(default_factory=list)
    texture_upload_warnings: list[TextureUploadWarning] = field(default_factory=list)
    texture_cache_cleanups: list[TextureCacheCleanup] = field(default_factory=list)
    settings_stalls: list[SettingsStall] = field(default_factory=list)
    visualizer_custom_suppressions: list[str] = field(default_factory=list)
    visualizer_custom_bucket_repairs: list[str] = field(default_factory=list)
    spotify_topology_events: list[SpotifyTopologyEvent] = field(default_factory=list)
    spotify_surface_selections: list[SpotifySurfaceSelection] = field(default_factory=list)
    spotify_overlay_perf_windows: list[SpotifyOverlayPerfWindow] = field(default_factory=list)
    spotify_overlay_microgap_windows: list[SpotifyOverlayMicrogapWindow] = field(default_factory=list)
    startup_first_frame_exposures: list[StartupFirstFrameExposure] = field(default_factory=list)
    timeline_markers: list[TimelineMarker] = field(default_factory=list)

    @property
    def usage_lifetimes(self) -> list[list[UsageSample]]:
        """Partition samples whenever the per-process sequence restarts."""
        lifetimes: list[list[UsageSample]] = []
        current: list[UsageSample] = []
        previous_sequence: int | None = None
        for sample in self.usage_samples:
            if current and previous_sequence is not None and sample.sequence <= previous_sequence:
                lifetimes.append(current)
                current = []
            current.append(sample)
            previous_sequence = sample.sequence
        if current:
            lifetimes.append(current)
        return lifetimes

    @property
    def intrusive_usage_samples(self) -> list[UsageSample]:
        """Samples where diagnostics were slow, late, or unable to keep cadence."""
        return [
            sample
            for sample in self.usage_samples
            if (sample.sequence > 1 and sample.collect_ms >= 100.0)
            or sample.skipped > 0
            or sample.cadence_gap_ms >= 30_000.0
        ]

    @property
    def sustained_high_cpu_samples(self) -> list[UsageSample]:
        sustained: list[UsageSample] = []
        for lifetime in self.usage_lifetimes:
            high = [
                sample
                for sample in lifetime
                if sample.cpu_primed
                and sample.cpu_app_pct is not None
                and sample.cpu_app_pct >= 100.0
            ]
            if len(high) >= 3:
                sustained.extend(high)
        return sustained

    @property
    def usage_hot_thread_stats(self) -> list[tuple[str, float, float, int]]:
        buckets: dict[str, list[float]] = {}
        for sample in self.usage_samples:
            for name, cpu_pct in sample.cpu_hot_threads:
                buckets.setdefault(name, []).append(cpu_pct)
        return sorted(
            (
                (name, sum(values) / len(values), max(values), len(values))
                for name, values in buckets.items()
            ),
            key=lambda item: (item[2], item[1]),
            reverse=True,
        )

    @property
    def sustained_gpu_saturation_samples(self) -> list[UsageSample]:
        sustained: list[UsageSample] = []
        for lifetime in self.usage_lifetimes:
            high = [
                sample
                for sample in lifetime
                if sample.gpu_supported
                and sample.gpu_active
                and (sample.gpu_busy_pct or 0.0) >= 90.0
            ]
            if len(high) >= 3:
                sustained.extend(high)
        return sustained

    @property
    def usage_growth_anomalies(self) -> list[str]:
        anomalies: list[str] = []
        lifetimes = self.usage_lifetimes
        for index, lifetime in enumerate(lifetimes, start=1):
            if len(lifetime) < 3:
                continue
            prefix = f"usage lifetime {index}/{len(lifetimes)}: " if len(lifetimes) > 1 else ""
            anomalies.extend(
                prefix + message
                for message in _usage_growth_anomalies_for_samples(lifetime)
            )
        return anomalies

    @property
    def excessive_texture_cache_cleanups(self) -> list[TextureCacheCleanup]:
        return [
            cleanup
            for cleanup in self.texture_cache_cleanups
            if cleanup.textures > 4
            or cleanup.pbo_count > 1
            or cleanup.registrations > 5
        ]

    @property
    def excessive_shared_texture_groups(self) -> list[TextureCacheCleanup]:
        return [
            cleanup
            for cleanup in self.texture_cache_cleanups
            if cleanup.shared_group_managers > 0
            and cleanup.shared_group_textures
            > 4 * cleanup.shared_group_managers
        ]

    @property
    def unexpected_paint_path_fallback_windows(self) -> list[PaintPathWindow]:
        """Fallback that persisted beyond a first-image safety paint."""

        return [
            window
            for window in self.paint_path_windows
            if window.transition_qpainter_fallback > 0
            or (
                window.idle_qpainter_fallback >= 3
                and window.fallback_ratio >= 0.05
            )
        ]

    @property
    def usage_visualizer_correlations(self) -> list[UsageVisualizerCorrelation]:
        correlated: list[UsageVisualizerCorrelation] = []
        for warning in self.significant_visualizer_timing_warnings:
            warning_seconds = _timestamp_seconds(warning.timestamp)
            if warning_seconds is None:
                continue
            nearest: tuple[float, UsageSample] | None = None
            for sample in self.usage_samples:
                sample_seconds = _timestamp_seconds(sample.timestamp)
                if sample_seconds is None:
                    continue
                distance = abs(sample_seconds - warning_seconds)
                if distance > 20.0:
                    continue
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, sample)
            if nearest is not None:
                correlated.append(
                    UsageVisualizerCorrelation(usage=nearest[1], warning=warning)
                )
        return correlated

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
        """Render windows where timer wakeups are materially lost to paint coalescing.

        A few pending skips are normal when paint is already in flight, especially
        on high-refresh displays. Keep the bar red for the old collapse shape:
        high skip ratio and/or under-delivery, not healthy near-target cadence.
        """
        problematic: list[MetricWindow] = []
        for window in self.windows:
            if window.source != "gl_render" or (window.pending_skip_count or 0) <= 0:
                continue
            skip_ratio = window.pending_skip_ratio or 0.0
            target_ratio = window.target_ratio or 0.0
            if skip_ratio >= 0.10 or target_ratio < 0.90:
                problematic.append(window)
        return problematic

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
    def cross_display_spotify_paint_starvation(self) -> list[SpotifyTopologyStarvation]:
        """Paint starvation where the latest visualizer owner is another display.

        This names the Spotify-stack topology without claiming the shader,
        Bubble worker, or transition identity is the root cause.
        """
        visualizers = [
            event for event in self.spotify_topology_events if event.kind == "visualizer_created"
        ]
        media_events = [
            event for event in self.spotify_topology_events if event.kind == "media_controller"
        ]
        correlated: list[SpotifyTopologyStarvation] = []
        for starvation in self.paint_delivery_starvation_windows:
            paint_seconds = _timestamp_seconds(starvation.paint.timestamp)
            latest_vis: SpotifyTopologyEvent | None = None
            for event in visualizers:
                if event.screen is None:
                    continue
                event_seconds = _timestamp_seconds(event.timestamp)
                if (
                    paint_seconds is not None
                    and event_seconds is not None
                    and event_seconds > paint_seconds
                ):
                    continue
                latest_vis = event
            if latest_vis is None or latest_vis.screen == starvation.paint.screen:
                continue
            media_seen = False
            for event in media_events:
                event_seconds = _timestamp_seconds(event.timestamp)
                if (
                    paint_seconds is not None
                    and event_seconds is not None
                    and event_seconds > paint_seconds
                ):
                    continue
                media_seen = True
            correlated.append(
                SpotifyTopologyStarvation(
                    starvation=starvation,
                    visualizer=latest_vis,
                    media_seen=media_seen,
                )
            )
        return correlated

    def _target_fps_for_screen(self, screen: int | None) -> int:
        targets = [
            window.target_fps
            for window in self.windows
            if window.screen == screen and window.target_fps
        ]
        if not targets:
            return 60
        return max(targets)

    @property
    def spotify_overlay_overpaint_windows(self) -> list[SpotifyOverlayPerfWindow]:
        """Visualizer child-GL windows that self-drive faster than the owner display.

        A Spotify overlay should be repainted by the visualizer frame handoff,
        not by a paint-owned recursive update loop.  This bar intentionally
        looks at the overlay's own passive counters rather than blaming any
        visualizer mode or transition shader.
        """
        overpaint: list[SpotifyOverlayPerfWindow] = []
        for window in self.spotify_overlay_perf_windows:
            if not window.visible or not window.enabled:
                continue
            target = float(self._target_fps_for_screen(window.screen))
            paint_limit = max(target * 3.0, target + 120.0)
            update_limit = max(target * 3.0, target + 120.0)
            if window.paint_fps > paint_limit or window.update_request_fps > update_limit:
                overpaint.append(window)
        return overpaint

    @property
    def spotify_overlay_under_delivery_windows(self) -> list[SpotifyOverlayPerfWindow]:
        """Visualizer overlay windows where the feed is healthy but display cadence is choppy."""
        under_delivered: list[SpotifyOverlayPerfWindow] = []
        for window in self.spotify_overlay_perf_windows:
            if not window.visible or not window.enabled:
                continue
            target = float(self._target_fps_for_screen(window.screen))
            if window.set_state_fps < max(target * 1.05, target + 5.0):
                continue
            if window.paint_fps < target * 0.85 or window.update_request_fps < target * 0.85:
                under_delivered.append(window)
        return under_delivered

    @property
    def spotify_overlay_microgap_anomalies(self) -> list[SpotifyOverlayMicrogapWindow]:
        """Short delivery gaps hidden by otherwise healthy ten-second averages."""
        anomalous: list[SpotifyOverlayMicrogapWindow] = []
        for window in self.spotify_overlay_microgap_windows:
            if not window.visible or not window.enabled:
                continue
            target = max(1.0, float(self._target_fps_for_screen(window.screen)))
            frame_ms = 1000.0 / target
            repeated_gap_limit = max(24.0, frame_ms * 2.0)
            repeated_wait_limit = max(16.0, frame_ms * 1.5)
            if (
                window.gap_max_ms >= 100.0
                or window.wait_max_ms >= 50.0
                or window.pending_wait_ms >= 100.0
                or (
                    window.gap_samples >= 5
                    and window.gap_p95_ms > repeated_gap_limit
                )
                or (
                    window.wait_samples >= 5
                    and window.wait_p95_ms > repeated_wait_limit
                )
            ):
                anomalous.append(window)
        return anomalous

    @property
    def unexpected_spotify_legacy_surfaces(self) -> list[SpotifySurfaceSelection]:
        expected_reasons = {"explicit_rollback", "software_backend"}
        return [
            selection
            for selection in self.spotify_surface_selections
            if selection.target == "legacy_child"
            and selection.reason not in expected_reasons
        ]

    @property
    def spotify_compositor_render_failure_windows(self) -> list[SpotifyOverlayPerfWindow]:
        """Single-surface windows where a visualizer render failed.

        Last-good retention protects fidelity from a visible blank or sudden
        disappearance, but it must not turn renderer failures into silent
        success.
        """
        return [
            window
            for window in self.spotify_overlay_perf_windows
            if window.surface == "compositor" and window.render_failure_count > 0
        ]

    @property
    def spotify_compositor_fbo_churn_windows(self) -> list[SpotifyOverlayPerfWindow]:
        """Compositor windows that rebuilt card buffers more than lifecycle needs."""
        return [
            window
            for window in self.spotify_overlay_perf_windows
            if window.surface == "compositor" and window.fbo_resize_count > 1
        ]

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
        paused_forced_ids = {
            id(warning)
            for warning in self.paused_forced_visualizer_latency_warnings
        }
        return [
            warning
            for warning in self.visualizer_timing_warnings
            if warning.value_ms >= 40.0 and id(warning) not in paused_forced_ids
        ]

    @property
    def severe_visualizer_latency_warnings(self) -> list[VisualizerTimingWarning]:
        paused_forced_ids = {
            id(warning)
            for warning in self.paused_forced_visualizer_latency_warnings
        }
        return [
            warning
            for warning in self.visualizer_timing_warnings
            if warning.kind == "severe_latency" or warning.value_ms >= 500.0
            if id(warning) not in paused_forced_ids
        ]

    @property
    def slow_devcurve_worker_samples(self) -> list[VisualizerDevCurveWorkerSample]:
        """Worker solves that cannot independently sustain a 60 Hz feed."""

        return [
            sample
            for sample in self.visualizer_devcurve_worker_samples
            if sample.worker_ms > 16.67
        ]

    @property
    def slow_adaptive_render_owner_stop_acks(self) -> list[AdaptiveRenderOwnerStopAck]:
        """Retirements that remained alive well beyond a normal wake cycle."""

        return [
            sample
            for sample in self.adaptive_render_owner_stop_acks
            if sample.latency_ms > 250.0
        ]

    @property
    def paused_forced_visualizer_latency_warnings(self) -> list[VisualizerTimingWarning]:
        """Transition probes that sampled intentionally paused audio authority."""
        paused: list[VisualizerTimingWarning] = []
        for warning in self.visualizer_timing_warnings:
            if warning.kind not in {"latency", "severe_latency"}:
                continue
            if not str(warning.trigger or "").startswith("transition_"):
                continue
            warning_seconds = _timestamp_seconds(warning.timestamp)
            if warning_seconds is None:
                continue
            nearest: tuple[float, SpotifyOverlayPerfWindow] | None = None
            for window in self.spotify_overlay_perf_windows:
                if window.playing is None:
                    continue
                if warning.mode and window.mode != warning.mode:
                    continue
                window_seconds = _timestamp_seconds(window.timestamp)
                if window_seconds is None:
                    continue
                distance = abs(window_seconds - warning_seconds)
                if distance > 12.0:
                    continue
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, window)
            if nearest is not None and nearest[1].playing is False:
                paused.append(warning)
        return paused

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
        if self.cross_display_spotify_paint_starvation:
            messages.append(
                "paint starvation correlated with cross-display Spotify visualizer topology: "
                f"{len(self.cross_display_spotify_paint_starvation)}"
            )
        if self.spotify_overlay_overpaint_windows:
            messages.append(
                "spotify visualizer overlay overpainted beyond owner display target: "
                f"{len(self.spotify_overlay_overpaint_windows)}"
            )
        if self.spotify_overlay_under_delivery_windows:
            messages.append(
                "spotify visualizer overlay under-delivered despite healthy feed: "
                f"{len(self.spotify_overlay_under_delivery_windows)}"
            )
        if self.spotify_overlay_microgap_anomalies:
            messages.append(
                "spotify visualizer overlay delivery microgaps exceeded the owner cadence: "
                f"{len(self.spotify_overlay_microgap_anomalies)}"
            )
        if self.spotify_compositor_render_failure_windows:
            messages.append(
                "spotify compositor visualizer renderer failures retained or dropped frames: "
                f"{len(self.spotify_compositor_render_failure_windows)}"
            )
        if self.spotify_compositor_fbo_churn_windows:
            messages.append(
                "spotify compositor visualizer framebuffer churn exceeded lifecycle needs: "
                f"{len(self.spotify_compositor_fbo_churn_windows)}"
            )
        if self.unexpected_spotify_legacy_surfaces:
            messages.append(
                "unexpected spotify legacy visualizer surfaces were activated: "
                f"{len(self.unexpected_spotify_legacy_surfaces)}"
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
        if self.unexpected_paint_path_fallback_windows:
            messages.append(
                "persistent compositor QPainter fallback windows present: "
                f"{len(self.unexpected_paint_path_fallback_windows)}"
            )
        if self.transition_start_refusals:
            messages.append(
                "transition starts were refused after image preparation: "
                f"{len(self.transition_start_refusals)}"
            )
        if self.transition_instant_commits:
            messages.append(
                "refused transitions committed the final image without animation: "
                f"{len(self.transition_instant_commits)}"
            )
        if self.transition_request_drops:
            messages.append(
                "image requests were dropped while transitions were active: "
                f"{len(self.transition_request_drops)}"
            )
        if self.gl_program_lifecycle_errors:
            messages.append(
                "GL program ownership/binding lifecycle errors present: "
                f"{len(self.gl_program_lifecycle_errors)}"
            )
        if self.gl_affinity_errors:
            messages.append(
                "Qt/OpenGL affinity violations present: "
                f"{len(self.gl_affinity_errors)}"
            )
        if self.slow_adaptive_render_owner_stop_acks:
            messages.append(
                "adaptive render-owner retirement acknowledgement exceeded 250ms: "
                f"{len(self.slow_adaptive_render_owner_stop_acks)}"
            )
        if self.gl_terminal_transaction_errors:
            messages.append(
                "compositor terminal transaction errors present: "
                f"{len(self.gl_terminal_transaction_errors)}"
            )
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
        if self.media_refresh_warnings:
            messages.append(
                f"media widget async refresh slow paths present: {len(self.media_refresh_warnings)}"
            )
        if self.visualizer_gpu_push_breakdowns:
            messages.append(
                "spotify visualizer slow GPU push paths present: "
                f"{len(self.visualizer_gpu_push_breakdowns)}"
            )
        if self.slow_devcurve_worker_samples:
            messages.append(
                "spotify Dev Curve worker exceeded one 60 Hz frame: "
                f"{len(self.slow_devcurve_worker_samples)}"
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
        if self.excessive_texture_cache_cleanups:
            messages.append(
                "GL texture cache cleanup exceeded the four-texture/one-PBO bound: "
                f"{len(self.excessive_texture_cache_cleanups)}"
            )
        if self.excessive_shared_texture_groups:
            messages.append(
                "GL shared texture residency exceeded the four-textures-per-manager bound: "
                f"{len(self.excessive_shared_texture_groups)}"
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
        if self.intrusive_usage_samples:
            messages.append(
                "usage telemetry was slow, late, or skipped samples: "
                f"{len(self.intrusive_usage_samples)}"
            )
        if self.sustained_high_cpu_samples:
            messages.append(
                f"app CPU remained above one logical core: {len(self.sustained_high_cpu_samples)}"
            )
        if self.sustained_gpu_saturation_samples:
            messages.append(
                "app GPU engine usage remained near saturation: "
                f"{len(self.sustained_gpu_saturation_samples)}"
            )
        messages.extend(self.usage_growth_anomalies)
        if self.visualizer_safeguard_failures:
            messages.append(
                "visualizer first-frame/reactivity safeguard failures present: "
                f"{len(self.visualizer_safeguard_failures)}"
            )
        return messages


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.rstrip("ms").rstrip("Hz"))
    except ValueError:
        return None


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, percentile)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def _parse_int(value: str | None) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _parse_kv_payload(payload: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _KV_RE.finditer(payload)}


def _parse_bool(value: str | None) -> bool:
    return str(value).strip().lower() == "true"


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return _parse_bool(value)


def _parse_flag(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_hot_threads(value: str | None) -> tuple[tuple[str, float], ...]:
    if not value or value.strip().lower() == "na":
        return ()
    parsed: list[tuple[str, float]] = []
    for entry in value.split("|"):
        name, separator, raw_cpu = entry.rpartition(":")
        cpu_pct = _parse_float(raw_cpu) if separator else None
        if not name or cpu_pct is None:
            continue
        parsed.append((name, cpu_pct))
    return tuple(parsed)


def _usage_sample_from_line(line: str, payload: str) -> UsageSample | None:
    parts = _parse_kv_payload(payload)
    sequence = _parse_int(parts.get("seq"))
    cadence_gap_ms = _parse_float(parts.get("cadence_gap_ms"))
    skipped = _parse_int(parts.get("skipped"))
    collect_ms = _parse_float(parts.get("collect_ms"))
    cpu_app_pct = _parse_float(parts.get("cpu_app_pct"))
    cpu_main_pct = _parse_float(parts.get("cpu_main_pct"))
    cpu_system_pct = _parse_float(parts.get("cpu_system_pct"))
    rss_app_mb = _parse_float(parts.get("rss_app_mb"))
    threads_app = _parse_int(parts.get("threads_app"))
    tm_active = _parse_int(parts.get("tm_active"))
    required = (
        sequence,
        cadence_gap_ms,
        skipped,
        collect_ms,
        rss_app_mb,
        threads_app,
        tm_active,
    )
    if any(value is None for value in required):
        return None
    return UsageSample(
        timestamp=_timestamp_from_line(line),
        sequence=sequence,
        cadence_gap_ms=cadence_gap_ms,
        skipped=skipped,
        collect_ms=collect_ms,
        cpu_primed=_parse_flag(parts.get("cpu_primed")),
        cpu_app_pct=cpu_app_pct,
        cpu_main_pct=cpu_main_pct,
        cpu_system_pct=cpu_system_pct,
        rss_app_mb=rss_app_mb,
        private_app_mb=_parse_float(parts.get("private_app_mb")),
        vms_app_mb=_parse_float(parts.get("vms_app_mb")),
        threads_app=threads_app,
        handles_app=_parse_int(parts.get("handles_app")),
        gpu_supported=_parse_flag(parts.get("gpu_supported")),
        gpu_active=_parse_flag(parts.get("gpu_active")),
        gpu_busy_pct=_parse_float(parts.get("gpu_busy_pct")),
        vram_supported=_parse_flag(parts.get("vram_supported")),
        vram_dedicated_mb=_parse_float(parts.get("vram_dedicated_mb")),
        tm_active=tm_active,
        rm_total=_parse_int(parts.get("rm_total")),
        rm_gl_total=_parse_int(parts.get("rm_gl_total")),
        rm_gl_texture=_parse_int(parts.get("rm_gl_texture")),
        rm_gl_vbo=_parse_int(parts.get("rm_gl_vbo")),
        rm_gl_vao=_parse_int(parts.get("rm_gl_vao")),
        rm_gl_program=_parse_int(parts.get("rm_gl_program")),
        rm_gl_framebuffer=_parse_int(parts.get("rm_gl_framebuffer")),
        rm_gl_renderbuffer=_parse_int(parts.get("rm_gl_renderbuffer")),
        rm_gl_texture_est_mb=_parse_float(parts.get("rm_gl_texture_est_mb")),
        rm_gl_pbo_est_mb=_parse_float(parts.get("rm_gl_pbo_est_mb")),
        img_cache_items=_parse_int(parts.get("img_cache_items")),
        img_cache_max_items=_parse_int(parts.get("img_cache_max_items")),
        img_cache_est_mb=_parse_float(parts.get("img_cache_est_mb")),
        img_cache_budget_mb=_parse_float(parts.get("img_cache_budget_mb")),
        img_cache_hits=_parse_int(parts.get("img_cache_hits")),
        img_cache_misses=_parse_int(parts.get("img_cache_misses")),
        img_cache_evictions=_parse_int(parts.get("img_cache_evictions")),
        tm_io_submitted=_parse_int(parts.get("tm_io_submitted")),
        tm_io_completed=_parse_int(parts.get("tm_io_completed")),
        tm_io_failed=_parse_int(parts.get("tm_io_failed")),
        tm_compute_submitted=_parse_int(parts.get("tm_compute_submitted")),
        tm_compute_completed=_parse_int(parts.get("tm_compute_completed")),
        tm_compute_failed=_parse_int(parts.get("tm_compute_failed")),
        cpu_hot_threads=_parse_hot_threads(parts.get("cpu_hot_threads")),
        line=line,
    )


def _texture_cache_cleanup_from_line(
    line: str,
    payload: str,
) -> TextureCacheCleanup | None:
    parts = _parse_kv_payload(payload)
    required = {
        "textures": _parse_int(parts.get("textures")),
        "texture_mb": _parse_float(parts.get("texture_mb")),
        "pbo_count": _parse_int(parts.get("pbo_count")),
        "pbo_mb": _parse_float(parts.get("pbo_mb")),
        "hits": _parse_int(parts.get("hits")),
        "misses": _parse_int(parts.get("misses")),
        "uploads": _parse_int(parts.get("uploads")),
        "evictions": _parse_int(parts.get("evictions")),
        "managed_releases": _parse_int(parts.get("managed_releases")),
        "pbo_replacements": _parse_int(parts.get("pbo_replacements")),
        "registrations": _parse_int(parts.get("registrations")),
    }
    if any(value is None for value in required.values()):
        return None
    return TextureCacheCleanup(
        textures=int(required["textures"]),
        texture_mb=float(required["texture_mb"]),
        pbo_count=int(required["pbo_count"]),
        pbo_mb=float(required["pbo_mb"]),
        hits=int(required["hits"]),
        misses=int(required["misses"]),
        uploads=int(required["uploads"]),
        evictions=int(required["evictions"]),
        managed_releases=int(required["managed_releases"]),
        pbo_replacements=int(required["pbo_replacements"]),
        registrations=int(required["registrations"]),
        shared_leases=int(_parse_int(parts.get("shared_leases")) or 0),
        shared_group_textures=int(
            _parse_int(parts.get("shared_group_textures")) or 0
        ),
        shared_group_texture_mb=float(
            _parse_float(parts.get("shared_group_texture_mb")) or 0.0
        ),
        shared_group_managers=int(
            _parse_int(parts.get("shared_group_managers")) or 0
        ),
        shared_acquisitions=int(
            _parse_int(parts.get("shared_acquisitions")) or 0
        ),
        shared_reuses=int(_parse_int(parts.get("shared_reuses")) or 0),
        line=line,
    )


def _timestamp_from_line(line: str) -> str | None:
    match = _TIME_RE.search(line)
    return match.group("ts") if match else None


def _timestamp_seconds(timestamp: str | None) -> int | None:
    if not timestamp:
        return None
    timestamp_parts = timestamp.rsplit(" ", 1)
    time_part = timestamp_parts[-1]
    parts = time_part.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return None
    day_offset = 0
    if len(timestamp_parts) == 2:
        try:
            day_offset = date.fromisoformat(timestamp_parts[0]).toordinal() * 86_400
        except ValueError:
            return None
    return day_offset + hours * 3600 + minutes * 60 + seconds


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
    presentation_dirty_generation = _parse_int(parts.get("dirty_generation"))
    presentation_ack_generation = _parse_int(parts.get("ack_generation"))
    presentation_generation_lag = _parse_int(parts.get("generation_lag"))
    visualizer_request_count = _parse_int(parts.get("visualizer_requests"))
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
        presentation_dirty_generation=presentation_dirty_generation,
        presentation_ack_generation=presentation_ack_generation,
        presentation_generation_lag=presentation_generation_lag,
        visualizer_request_count=visualizer_request_count,
        duration_ms=duration_ms,
        owner=owner,
        line=line,
    )


def _paint_path_window_from_line(line: str, payload: str) -> PaintPathWindow | None:
    parts = _parse_kv_payload(payload)
    elapsed_ms = _parse_float(parts.get("elapsed_ms"))
    total = _parse_int(parts.get("total"))
    if elapsed_ms is None or total is None:
        return None
    return PaintPathWindow(
        timestamp=_timestamp_from_line(line),
        screen=_parse_int(parts.get("screen")),
        elapsed_ms=elapsed_ms,
        total=total,
        idle_gl=_parse_int(parts.get("idle_gl")) or 0,
        transition_gl=_parse_int(parts.get("transition_gl")) or 0,
        idle_qpainter_fallback=(
            _parse_int(parts.get("idle_qpainter_fallback")) or 0
        ),
        transition_qpainter_fallback=(
            _parse_int(parts.get("transition_qpainter_fallback")) or 0
        ),
        idle_gl_avg_ms=_parse_float(parts.get("idle_gl_avg_ms")) or 0.0,
        idle_gl_max_ms=_parse_float(parts.get("idle_gl_max_ms")) or 0.0,
        transition_gl_avg_ms=(
            _parse_float(parts.get("transition_gl_avg_ms")) or 0.0
        ),
        transition_gl_max_ms=(
            _parse_float(parts.get("transition_gl_max_ms")) or 0.0
        ),
        idle_qpainter_avg_ms=(
            _parse_float(parts.get("idle_qpainter_avg_ms")) or 0.0
        ),
        idle_qpainter_max_ms=(
            _parse_float(parts.get("idle_qpainter_max_ms")) or 0.0
        ),
        transition_qpainter_avg_ms=(
            _parse_float(parts.get("transition_qpainter_avg_ms")) or 0.0
        ),
        transition_qpainter_max_ms=(
            _parse_float(parts.get("transition_qpainter_max_ms")) or 0.0
        ),
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


def _spotify_overlay_perf_from_line(line: str, detail: str) -> SpotifyOverlayPerfWindow | None:
    parts = _parse_kv_payload(detail)
    elapsed_ms = _parse_float(parts.get("elapsed_ms"))
    if elapsed_ms is None or elapsed_ms <= 0.0:
        return None
    return SpotifyOverlayPerfWindow(
        timestamp=_timestamp_from_line(line),
        reason=parts.get("reason", "unknown"),
        screen=_parse_int(parts.get("screen")),
        mode=parts.get("mode", "unknown"),
        surface=parts.get("surface", "legacy_child"),
        elapsed_ms=elapsed_ms,
        set_state_count=_parse_int(parts.get("set_state")) or 0,
        paint_count=_parse_int(parts.get("paint")) or 0,
        update_request_count=_parse_int(parts.get("update_requests")) or 0,
        geometry_change_count=_parse_int(parts.get("geometry_changes")) or 0,
        fbo_resize_count=_parse_int(parts.get("fbo_resizes")) or 0,
        fbo_render_count=_parse_int(parts.get("fbo_renders")) or 0,
        texture_reuse_count=_parse_int(parts.get("texture_reuses")) or 0,
        render_failure_count=_parse_int(parts.get("render_failures")) or 0,
        retained_last_good_count=_parse_int(parts.get("retained_last_good")) or 0,
        visible=_parse_bool(parts.get("visible")),
        enabled=_parse_bool(parts.get("enabled")),
        playing=_parse_optional_bool(parts.get("playing")),
        line=line,
    )


def _spotify_overlay_microgap_from_line(
    line: str,
    detail: str,
) -> SpotifyOverlayMicrogapWindow | None:
    parts = _parse_kv_payload(detail)
    context = parts.get("context")
    if not context:
        return None
    return SpotifyOverlayMicrogapWindow(
        timestamp=_timestamp_from_line(line),
        reason=parts.get("reason", "unknown"),
        screen=_parse_int(parts.get("screen")),
        mode=parts.get("mode", "unknown"),
        surface=parts.get("surface", "legacy_child"),
        context=context,
        gap_samples=_parse_int(parts.get("gap_samples")) or 0,
        gap_p95_ms=_parse_float(parts.get("gap_p95_ms")) or 0.0,
        gap_max_ms=_parse_float(parts.get("gap_max_ms")) or 0.0,
        wait_samples=_parse_int(parts.get("wait_samples")) or 0,
        wait_p95_ms=_parse_float(parts.get("wait_p95_ms")) or 0.0,
        wait_max_ms=_parse_float(parts.get("wait_max_ms")) or 0.0,
        pending_wait_ms=_parse_float(parts.get("pending_wait_ms")) or 0.0,
        visible=_parse_bool(parts.get("visible")),
        enabled=_parse_bool(parts.get("enabled")),
        playing=_parse_optional_bool(parts.get("playing")),
        line=line,
    )


def _spotify_tick_phase_from_line(line: str, detail: str) -> VisualizerTickPhaseBreakdown | None:
    parts = _parse_kv_payload(detail)
    total_ms = _parse_float(parts.get("total_ms"))
    if total_ms is None:
        return None
    phases_ms: dict[str, float] = {}
    for key, value in parts.items():
        if not key.endswith("_ms") or key == "total_ms":
            continue
        phase_name = key[:-3]
        parsed = _parse_float(value)
        if parsed is not None:
            phases_ms[phase_name] = parsed
    return VisualizerTickPhaseBreakdown(
        timestamp=_timestamp_from_line(line),
        total_ms=total_ms,
        mode=parts.get("mode", "unknown"),
        transition_active=_parse_bool(parts.get("transition_active")),
        changed=_parse_bool(parts.get("changed")),
        first_frame=_parse_bool(parts.get("first_frame")),
        used_gpu=_parse_bool(parts.get("used_gpu")),
        phases_ms=phases_ms,
        line=line,
    )


def _spotify_gpu_push_from_line(line: str, detail: str) -> VisualizerGpuPushBreakdown | None:
    parts = _parse_kv_payload(detail)
    total_ms = _parse_float(parts.get("total_ms"))
    if total_ms is None:
        return None
    return VisualizerGpuPushBreakdown(
        timestamp=_timestamp_from_line(line),
        total_ms=total_ms,
        mode=parts.get("mode", "unknown"),
        extra_build_ms=_parse_float(parts.get("extra_build_ms")) or 0.0,
        primer_ms=_parse_float(parts.get("primer_ms")) or 0.0,
        packet_build_ms=_parse_float(parts.get("packet_build_ms")) or 0.0,
        parent_publish_ms=_parse_float(parts.get("parent_publish_ms")) or 0.0,
        line=line,
    )


def _media_refresh_from_line(line: str, detail: str) -> MediaRefreshWarning | None:
    parts = _parse_kv_payload(detail)
    total_ms = _parse_float(parts.get("total_ms"))
    if total_ms is None:
        return None
    return MediaRefreshWarning(
        timestamp=_timestamp_from_line(line),
        total_ms=total_ms,
        worker_ms=_parse_float(parts.get("worker_ms")) or 0.0,
        callback_ms=_parse_float(parts.get("callback_ms")) or 0.0,
        ui_delay_ms=_parse_float(parts.get("ui_delay_ms")) or 0.0,
        state=parts.get("state", "unknown"),
        line=line,
    )


def parse_perf_health_lines(lines: Iterable[str]) -> PerfHealthReport:
    report = PerfHealthReport()
    display_show_by_screen: dict[int, tuple[str | None, str]] = {}
    for raw in lines:
        line = raw.rstrip("\n")
        timestamp = _timestamp_from_line(line)

        spotify_surface = _SPOTIFY_SURFACE_RE.search(line)
        if spotify_surface:
            selection = SpotifySurfaceSelection(
                timestamp=timestamp,
                target=spotify_surface.group("target"),
                reason=spotify_surface.group("reason"),
                screen=_parse_int(spotify_surface.group("screen")),
                line=line,
            )
            report.spotify_surface_selections.append(selection)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "spotify_visualizer_surface",
                    f"target={selection.target} reason={selection.reason} screen={selection.screen}",
                    line,
                )
            )

        if _TRANSITION_START_REFUSAL_RE.search(line):
            report.transition_start_refusals.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "transition_start_refusal",
                    "prepared transition did not start",
                    line,
                )
            )
        if _TRANSITION_INSTANT_COMMIT_RE.search(line):
            report.transition_instant_commits.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "transition_instant_commit",
                    "final image committed without transition",
                    line,
                )
            )
        if _TRANSITION_REQUEST_DROP_RE.search(line):
            report.transition_request_drops.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "transition_request_drop",
                    "active transition dropped image request",
                    line,
                )
            )
        if _GL_PROGRAM_LIFECYCLE_ERROR_RE.search(line):
            report.gl_program_lifecycle_errors.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "gl_program_lifecycle_error",
                    "program delete/bind/uniform ownership failure",
                    line,
                )
            )
        if _GL_AFFINITY_ERROR_RE.search(line):
            report.gl_affinity_errors.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "gl_affinity_error",
                    "Qt GL operation crossed its affinity boundary",
                    line,
                )
            )
        adaptive_stop_ack = _ADAPTIVE_STOP_ACK_RE.search(line)
        if adaptive_stop_ack:
            latency_ms = _parse_float(adaptive_stop_ack.group("latency_ms"))
            if latency_ms is not None:
                sample = AdaptiveRenderOwnerStopAck(
                    timestamp=timestamp,
                    screen=_parse_int(adaptive_stop_ack.group("screen")),
                    latency_ms=latency_ms,
                    immediate=adaptive_stop_ack.group("immediate") == "True",
                    line=line,
                )
                report.adaptive_render_owner_stop_acks.append(sample)
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "adaptive_render_owner_stop_ack",
                        f"screen={sample.screen} latency_ms={latency_ms:.2f} "
                        f"immediate={sample.immediate}",
                        line,
                    )
                )
        if _GL_TERMINAL_TRANSACTION_ERROR_RE.search(line):
            report.gl_terminal_transaction_errors.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "gl_terminal_transaction_error",
                    "terminal transaction failed to reach owner-thread commit",
                    line,
                )
            )
        if _STALE_IMAGE_PUBLICATION_RE.search(line):
            report.stale_image_publications.append(line)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "stale_image_publication_suppressed",
                    "old display generation was prevented from publishing",
                    line,
                )
            )

        texture_cache_match = _GL_TEXTURE_CACHE_RE.search(line)
        if texture_cache_match:
            cleanup = _texture_cache_cleanup_from_line(
                line,
                texture_cache_match.group("payload"),
            )
            if cleanup is not None:
                report.texture_cache_cleanups.append(cleanup)
            continue

        usage_match = _USAGE_SAMPLE_RE.search(line)
        if usage_match:
            sample = _usage_sample_from_line(line, usage_match.group("payload"))
            if sample is not None:
                report.usage_samples.append(sample)
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "usage_sample",
                        (
                            f"cpu_app={f'{sample.cpu_app_pct:.1f}%' if sample.cpu_app_pct is not None else 'na'} "
                            f"rss={sample.rss_app_mb:.1f}MB "
                            f"gpu={sample.gpu_busy_pct if sample.gpu_busy_pct is not None else 'na'} "
                            f"rm_gl={sample.rm_gl_total if sample.rm_gl_total is not None else 'na'}"
                        ),
                        line,
                    )
                )
            continue

        safeguard_failure = _VISUALIZER_SAFEGUARD_FAILURE_RE.search(line)
        if safeguard_failure:
            report.visualizer_safeguard_failures.append(
                VisualizerSafeguardFailure(
                    timestamp=timestamp,
                    detail=safeguard_failure.group("detail"),
                    line=line,
                )
            )
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "visualizer_safeguard_failure",
                    safeguard_failure.group("detail"),
                    line,
                )
            )

        spotify_vis_created = _SPOTIFY_VIS_CREATED_RE.search(line)
        if spotify_vis_created:
            screen = int(spotify_vis_created.group("screen"))
            monitor = spotify_vis_created.group("monitor").strip()
            event = SpotifyTopologyEvent(
                timestamp=timestamp,
                kind="visualizer_created",
                screen=screen,
                monitor=monitor,
                detail=f"screen={screen} monitor={monitor}",
                line=line,
            )
            report.spotify_topology_events.append(event)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "spotify_visualizer_created", event.detail, line)
            )
            continue

        media_controller = _MEDIA_CONTROLLER_RE.search(line)
        if media_controller:
            controller = media_controller.group("controller")
            event = SpotifyTopologyEvent(
                timestamp=timestamp,
                kind="media_controller",
                detail=f"controller={controller}",
                line=line,
            )
            report.spotify_topology_events.append(event)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "media_controller", event.detail, line)
            )
            continue

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

        paint_path = _GL_PAINT_PATH_RE.search(line)
        if paint_path:
            path_window = _paint_path_window_from_line(
                line,
                paint_path.group("payload"),
            )
            if path_window is not None:
                report.paint_path_windows.append(path_window)
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "gl_paint_path",
                        (
                            f"screen={path_window.screen} total={path_window.total} "
                            f"fallbacks={path_window.fallback_count}"
                        ),
                        line,
                    )
                )
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
                latency_parts = _parse_kv_payload(line)
                report.visualizer_timing_warnings.append(
                    VisualizerTimingWarning(
                        "severe_latency",
                        lag_ms,
                        line,
                        timestamp,
                        latency_parts.get("mode"),
                        latency_parts.get("trigger"),
                    )
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "spotify_severe_latency", f"lag_ms={lag_ms:.1f}", line)
                )
            continue

        spotify_latency = _SPOTIFY_LATENCY_RE.search(line)
        if spotify_latency:
            lag_ms = _parse_float(spotify_latency.group("lag_ms"))
            if lag_ms is not None:
                latency_parts = _parse_kv_payload(line)
                report.visualizer_timing_warnings.append(
                    VisualizerTimingWarning(
                        "latency",
                        lag_ms,
                        line,
                        timestamp,
                        latency_parts.get("mode"),
                        latency_parts.get("trigger"),
                    )
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
                    VisualizerTimingWarning("tick_spike", dt_ms, line, timestamp)
                )
                report.timeline_markers.append(
                    TimelineMarker(timestamp, "spotify_tick_spike", f"dt_ms={dt_ms:.1f}", line)
                )
            continue

        spotify_tick_phase = _SPOTIFY_TICK_PHASE_RE.search(line)
        if spotify_tick_phase:
            breakdown = _spotify_tick_phase_from_line(
                line,
                spotify_tick_phase.group("detail"),
            )
            if breakdown is not None:
                report.visualizer_tick_phase_breakdowns.append(breakdown)
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "spotify_tick_phase_breakdown",
                        breakdown.summary,
                        line,
                    )
                )
            continue

        spotify_gpu_push = _SPOTIFY_GPU_PUSH_RE.search(line)
        if spotify_gpu_push:
            breakdown = _spotify_gpu_push_from_line(line, spotify_gpu_push.group("detail"))
            if breakdown is not None:
                report.visualizer_gpu_push_breakdowns.append(breakdown)
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "spotify_gpu_push_breakdown",
                        breakdown.summary,
                        line,
                    )
                )
            continue

        spotify_devcurve_worker = _SPOTIFY_DEVCURVE_WORKER_RE.search(line)
        if spotify_devcurve_worker:
            worker_ms = _parse_float(spotify_devcurve_worker.group("worker_ms"))
            if worker_ms is not None:
                sample = VisualizerDevCurveWorkerSample(
                    timestamp=timestamp,
                    worker_ms=worker_ms,
                    pending=spotify_devcurve_worker.group("pending") == "True",
                    line=line,
                )
                report.visualizer_devcurve_worker_samples.append(sample)
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "spotify_devcurve_worker",
                        f"worker_ms={worker_ms:.2f} pending={sample.pending}",
                        line,
                    )
                )
            continue

        spotify_overlay_perf = _SPOTIFY_OVERLAY_PERF_RE.search(line)
        if spotify_overlay_perf:
            overlay_window = _spotify_overlay_perf_from_line(
                line,
                spotify_overlay_perf.group("detail"),
            )
            if overlay_window is not None:
                report.spotify_overlay_perf_windows.append(overlay_window)
            report.timeline_markers.append(
                TimelineMarker(timestamp, "spotify_overlay_perf", spotify_overlay_perf.group("detail").strip(), line)
            )
            continue

        spotify_overlay_microgap = _SPOTIFY_OVERLAY_MICROGAP_RE.search(line)
        if spotify_overlay_microgap:
            microgap_window = _spotify_overlay_microgap_from_line(
                line,
                spotify_overlay_microgap.group("detail"),
            )
            if microgap_window is not None:
                report.spotify_overlay_microgap_windows.append(microgap_window)
            report.timeline_markers.append(
                TimelineMarker(
                    timestamp,
                    "spotify_overlay_microgap",
                    spotify_overlay_microgap.group("detail").strip(),
                    line,
                )
            )
            continue

        spotify_vis_sync_perf = _SPOTIFY_VIS_SYNC_PERF_RE.search(line)
        if spotify_vis_sync_perf:
            report.timeline_markers.append(
                TimelineMarker(timestamp, "spotify_visibility_sync_perf", spotify_vis_sync_perf.group("detail").strip(), line)
            )
            continue

        media_emit_perf = _MEDIA_EMIT_PERF_RE.search(line)
        if media_emit_perf:
            report.timeline_markers.append(
                TimelineMarker(timestamp, "media_emit_perf", media_emit_perf.group("detail").strip(), line)
            )
            continue

        media_refresh_perf = _MEDIA_REFRESH_PERF_RE.search(line)
        if media_refresh_perf:
            warning = _media_refresh_from_line(line, media_refresh_perf.group("detail"))
            if warning is not None:
                report.media_refresh_warnings.append(warning)
                dominant_name, dominant_ms = warning.dominant_phase
                report.timeline_markers.append(
                    TimelineMarker(
                        timestamp,
                        "media_refresh_slow",
                        (
                            f"total_ms={warning.total_ms:.1f} "
                            f"dominant={dominant_name}:{dominant_ms:.1f}ms"
                        ),
                        line,
                    )
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
                        convert_ms=_parse_float(texture_upload.group("convert_ms")),
                        copy_ms=_parse_float(texture_upload.group("copy_ms")),
                        pbo_stage_ms=_parse_float(
                            texture_upload.group("pbo_stage_ms")
                        ),
                        tex_upload_ms=_parse_float(
                            texture_upload.group("tex_upload_ms")
                        ),
                        direct=_parse_optional_bool(texture_upload.group("direct")),
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


def parse_perf_health_logs(paths: Iterable[Path]) -> PerfHealthReport:
    lines: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines.extend(text.splitlines())
    ordered_unique_lines = list(dict.fromkeys(lines))
    return parse_perf_health_lines(
        sorted(
            ordered_unique_lines,
            key=lambda line: _timestamp_seconds(_timestamp_from_line(line)) or 0.0,
        )
    )


def _resolve_log_paths(
    primary: Path,
    extra_logs: Iterable[Path],
    usage_log: Path | None,
) -> list[Path]:
    """Merge high-signal companion logs without requiring manual sidecar flags."""

    paths = [primary, *extra_logs]
    main_log = primary.with_name("screensaver.log")
    if main_log.exists() and main_log not in paths:
        paths.append(main_log)
    verbose_log = primary.with_name("screensaver_verbose.log")
    if verbose_log.exists() and verbose_log not in paths:
        paths.append(verbose_log)

    resolved_usage = usage_log or primary.with_name("screensaver_usage.log")
    if resolved_usage.exists() and resolved_usage not in paths:
        paths.append(resolved_usage)
    return paths


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
        "--extra-log",
        type=Path,
        action="append",
        default=[],
        help="Additional sidecar log to merge into the timeline, e.g. --viz for Spotify topology.",
    )
    parser.add_argument(
        "--usage-log",
        type=Path,
        default=None,
        help=(
            "Whole-process usage sidecar. When omitted, screensaver_usage.log "
            "beside the primary perf log is merged automatically if present."
        ),
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
    usage_log = args.usage_log or args.log.with_name("screensaver_usage.log")
    if args.usage_log is not None and not usage_log.exists():
        print(f"Log file not found: {usage_log}")
        return 1
    log_paths = _resolve_log_paths(args.log, args.extra_log, args.usage_log)
    for log_path in log_paths:
        if not log_path.exists() or not log_path.is_file():
            print(f"Log file not found: {log_path}")
            return 1

    report = parse_perf_health_logs(log_paths)
    if len(log_paths) == 1:
        print(f"Transition perf health summary for {log_paths[0]}")
    else:
        joined = ", ".join(str(path) for path in log_paths)
        print(f"Transition perf health summary for {joined}")
    print(f"Metric windows: {len(report.windows)}")
    print(f"GL paint-path windows: {len(report.paint_path_windows)}")
    print(
        "Persistent GL QPainter fallback windows: "
        f"{len(report.unexpected_paint_path_fallback_windows)}"
    )
    print(f"Cache worker fallbacks: {len(report.cache_fallbacks)}")
    print(f"Shader fallbacks: {len(report.shader_fallbacks)}")
    print(f"Transition start refusals: {len(report.transition_start_refusals)}")
    print(f"Transition instant commits: {len(report.transition_instant_commits)}")
    print(f"Transition request drops: {len(report.transition_request_drops)}")
    print(f"GL program lifecycle errors: {len(report.gl_program_lifecycle_errors)}")
    print(f"Qt/OpenGL affinity errors: {len(report.gl_affinity_errors)}")
    print(f"GL terminal transaction errors: {len(report.gl_terminal_transaction_errors)}")
    print(f"Stale image publications suppressed: {len(report.stale_image_publications)}")
    print(f"Adaptive render-owner stop acknowledgements: {len(report.adaptive_render_owner_stop_acks)}")
    print(
        "Slow adaptive render-owner stop acknowledgements: "
        f"{len(report.slow_adaptive_render_owner_stop_acks)}"
    )
    print(f"GL swap-interval warnings: {len(report.gl_swap_interval_warnings)}")
    print(f"Pending paint requeues: {len(report.pending_paint_requeues)}")
    print(f"Pending paint stalls: {len(report.pending_paint_stalls)}")
    print(f"Render pending skips: {len(report.render_timer_pending_skip_windows)}")
    print(f"Timer gaps: {len(report.timer_gaps)}")
    print(f"MediaWidget slow refreshes: {len(report.media_refresh_warnings)}")
    print(f"Spotify visualizer timing warnings: {len(report.visualizer_timing_warnings)}")
    print(
        "Paused forced-probe latency diagnostics: "
        f"{len(report.paused_forced_visualizer_latency_warnings)}"
    )
    print(f"Visualizer safeguard failures: {len(report.visualizer_safeguard_failures)}")
    print(f"Whole-process usage samples: {len(report.usage_samples)}")
    print(f"Whole-process usage lifetimes: {len(report.usage_lifetimes)}")
    print(f"Spotify visualizer tick phase breakdowns: {len(report.visualizer_tick_phase_breakdowns)}")
    print(f"Spotify visualizer slow GPU pushes: {len(report.visualizer_gpu_push_breakdowns)}")
    print(f"Spotify Dev Curve worker samples: {len(report.visualizer_devcurve_worker_samples)}")
    print(f"Spotify Dev Curve slow worker samples: {len(report.slow_devcurve_worker_samples)}")
    print(f"Slow GL texture uploads: {len(report.texture_upload_warnings)}")
    print(f"GL texture cache cleanups: {len(report.texture_cache_cleanups)}")
    print(f"Settings stalls: {len(report.settings_stalls)}")
    print(f"Startup first-frame exposures: {len(report.startup_first_frame_exposures)}")
    print(f"Spotify visualizer CUSTOM suppressions: {len(report.visualizer_custom_suppressions)}")
    print(f"Spotify visualizer CUSTOM bucket repairs: {len(report.visualizer_custom_bucket_repairs)}")
    print(f"Spotify topology events: {len(report.spotify_topology_events)}")
    print(f"Spotify visualizer surface selections: {len(report.spotify_surface_selections)}")
    print(f"Unexpected Spotify legacy surfaces: {len(report.unexpected_spotify_legacy_surfaces)}")
    print(f"Spotify overlay perf windows: {len(report.spotify_overlay_perf_windows)}")
    print(
        "Spotify compositor perf windows: "
        f"{sum(window.surface == 'compositor' for window in report.spotify_overlay_perf_windows)}"
    )
    print(
        "Spotify legacy-child perf windows: "
        f"{sum(window.surface == 'legacy_child' for window in report.spotify_overlay_perf_windows)}"
    )
    print(f"Spotify overlay under-delivery windows: {len(report.spotify_overlay_under_delivery_windows)}")
    print(f"Spotify overlay microgap windows: {len(report.spotify_overlay_microgap_windows)}")
    print(f"Spotify overlay microgap anomalies: {len(report.spotify_overlay_microgap_anomalies)}")
    print(
        "Spotify compositor render-failure windows: "
        f"{len(report.spotify_compositor_render_failure_windows)}"
    )
    print(
        "Spotify compositor FBO-churn windows: "
        f"{len(report.spotify_compositor_fbo_churn_windows)}"
    )
    print(f"Timeline markers: {len(report.timeline_markers)}")
    if report.usage_samples:
        usage_samples = report.usage_lifetimes[-1]
        growth_baseline_index = 1 if len(usage_samples) >= 3 else 0
        growth_baseline = usage_samples[growth_baseline_index]
        last_usage = usage_samples[-1]
        primed_cpu = [
            sample.cpu_app_pct
            for sample in usage_samples
            if sample.cpu_primed and sample.cpu_app_pct is not None
        ]
        peak_cpu = max(primed_cpu) if primed_cpu else None
        average_cpu = (
            sum(primed_cpu) / len(primed_cpu)
            if primed_cpu
            else None
        )
        p95_cpu = _percentile(primed_cpu, 0.95)
        peak_rss = max(sample.rss_app_mb for sample in usage_samples)
        gpu_values = [
            sample.gpu_busy_pct
            for sample in usage_samples
            if sample.gpu_busy_pct is not None
        ]
        peak_gpu = max(gpu_values) if gpu_values else None
        gl_registration_values = [
            sample.rm_gl_total
            for sample in usage_samples
            if sample.rm_gl_total is not None
        ]
        peak_gl_registrations = (
            max(gl_registration_values) if gl_registration_values else None
        )
        gl_registration_delta = (
            last_usage.rm_gl_total - growth_baseline.rm_gl_total
            if (
                last_usage.rm_gl_total is not None
                and growth_baseline.rm_gl_total is not None
            )
            else None
        )
        elapsed_seconds = sum(
            max(0.0, sample.cadence_gap_ms)
            for sample in usage_samples[growth_baseline_index + 1 :]
        ) / 1000.0
        compute_rate = None
        compute_backlog = None
        if (
            elapsed_seconds > 0.0
            and growth_baseline.tm_compute_submitted is not None
            and last_usage.tm_compute_submitted is not None
        ):
            compute_rate = (
                last_usage.tm_compute_submitted
                - growth_baseline.tm_compute_submitted
            ) / elapsed_seconds
        if (
            last_usage.tm_compute_submitted is not None
            and last_usage.tm_compute_completed is not None
        ):
            compute_backlog = (
                last_usage.tm_compute_submitted
                - last_usage.tm_compute_completed
            )
        private_delta = (
            last_usage.private_app_mb - growth_baseline.private_app_mb
            if (
                last_usage.private_app_mb is not None
                and growth_baseline.private_app_mb is not None
            )
            else None
        )
        vms_delta = (
            last_usage.vms_app_mb - growth_baseline.vms_app_mb
            if (
                last_usage.vms_app_mb is not None
                and growth_baseline.vms_app_mb is not None
            )
            else None
        )
        image_cache_delta = (
            last_usage.img_cache_est_mb - growth_baseline.img_cache_est_mb
            if (
                last_usage.img_cache_est_mb is not None
                and growth_baseline.img_cache_est_mb is not None
            )
            else None
        )
        texture_estimate_delta = (
            last_usage.rm_gl_texture_est_mb
            - growth_baseline.rm_gl_texture_est_mb
            if (
                last_usage.rm_gl_texture_est_mb is not None
                and growth_baseline.rm_gl_texture_est_mb is not None
            )
            else None
        )
        pbo_estimate_delta = (
            last_usage.rm_gl_pbo_est_mb - growth_baseline.rm_gl_pbo_est_mb
            if (
                last_usage.rm_gl_pbo_est_mb is not None
                and growth_baseline.rm_gl_pbo_est_mb is not None
            )
            else None
        )
        print(
            f"Usage summary (latest lifetime {len(report.usage_lifetimes)}/{len(report.usage_lifetimes)}): "
            f"avg_cpu={f'{average_cpu:.1f}%' if average_cpu is not None else 'na'} "
            f"p95_cpu={f'{p95_cpu:.1f}%' if p95_cpu is not None else 'na'} "
            f"peak_cpu={f'{peak_cpu:.1f}%' if peak_cpu is not None else 'na'} "
            f"peak_rss={peak_rss:.1f}MB "
            f"growth_baseline_seq={growth_baseline.sequence} "
            f"rss_delta={last_usage.rss_app_mb - growth_baseline.rss_app_mb:.1f}MB "
            f"private_delta={f'{private_delta:.1f}MB' if private_delta is not None else 'na'} "
            f"vms_delta={f'{vms_delta:.1f}MB' if vms_delta is not None else 'na'} "
            f"threads_delta={last_usage.threads_app - growth_baseline.threads_app} "
            f"peak_gpu={f'{peak_gpu:.1f}%' if peak_gpu is not None else 'na'} "
            f"peak_rm_gl={peak_gl_registrations if peak_gl_registrations is not None else 'na'} "
            f"rm_gl_delta={gl_registration_delta if gl_registration_delta is not None else 'na'} "
            f"img_cache={f'{last_usage.img_cache_est_mb:.1f}MB' if last_usage.img_cache_est_mb is not None else 'na'} "
            f"img_cache_delta={f'{image_cache_delta:.1f}MB' if image_cache_delta is not None else 'na'} "
            f"img_cache_items={last_usage.img_cache_items if last_usage.img_cache_items is not None else 'na'} "
            f"rm_texture_est_delta={f'{texture_estimate_delta:.1f}MB' if texture_estimate_delta is not None else 'na'} "
            f"rm_pbo_est_delta={f'{pbo_estimate_delta:.1f}MB' if pbo_estimate_delta is not None else 'na'} "
            f"compute_submit_rate={f'{compute_rate:.1f}/s' if compute_rate is not None else 'na'} "
            f"compute_backlog={compute_backlog if compute_backlog is not None else 'na'}"
        )
        if report.usage_hot_thread_stats:
            print(
                "Hot thread CPU (all parsed lifetimes): "
                + "; ".join(
                    f"{name} avg={average:.1f}% peak={peak:.1f}% samples={count}"
                    for name, average, peak, count in report.usage_hot_thread_stats[:8]
                )
            )

    _print_samples(
        "Paint delivery starvation windows",
        report.paint_delivery_starvation_windows,
        args.max_samples,
    )
    _print_samples(
        "Cross-display Spotify topology starvation windows",
        report.cross_display_spotify_paint_starvation,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer overlay overpaint windows",
        report.spotify_overlay_overpaint_windows,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer overlay under-delivery windows",
        report.spotify_overlay_under_delivery_windows,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer overlay delivery microgaps",
        report.spotify_overlay_microgap_anomalies,
        args.max_samples,
    )
    _print_samples(
        "Spotify compositor visualizer render failures",
        report.spotify_compositor_render_failure_windows,
        args.max_samples,
    )
    _print_samples(
        "Spotify compositor visualizer framebuffer churn",
        report.spotify_compositor_fbo_churn_windows,
        args.max_samples,
    )
    _print_samples(
        "Unexpected Spotify legacy visualizer surfaces",
        report.unexpected_spotify_legacy_surfaces,
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
    _print_samples("MediaWidget slow async refreshes", report.media_refresh_warnings, args.max_samples)
    _print_samples(
        "Spotify visualizer timing warnings",
        report.significant_visualizer_timing_warnings,
        args.max_samples,
    )
    _print_samples(
        "Visualizer first-frame/reactivity safeguard failures",
        report.visualizer_safeguard_failures,
        args.max_samples,
    )
    _print_samples(
        "Usage telemetry slow/late/skipped samples",
        report.intrusive_usage_samples,
        args.max_samples,
    )
    _print_samples(
        "Usage samples near visualizer timing warnings",
        report.usage_visualizer_correlations,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer tick phase breakdowns",
        report.visualizer_tick_phase_breakdowns,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer slow GPU push breakdowns",
        report.visualizer_gpu_push_breakdowns,
        args.max_samples,
    )
    _print_samples(
        "Spotify visualizer severe latency warnings",
        report.severe_visualizer_latency_warnings,
        args.max_samples,
    )
    _print_samples(
        "Paused forced-probe latency diagnostics",
        report.paused_forced_visualizer_latency_warnings,
        args.max_samples,
    )
    _print_samples("Slow GL texture uploads", report.slow_texture_uploads, args.max_samples)
    _print_samples(
        "Excessive GL texture cache cleanups",
        report.excessive_texture_cache_cleanups,
        args.max_samples,
    )
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
    _print_samples(
        "Persistent compositor QPainter fallback windows",
        report.unexpected_paint_path_fallback_windows,
        args.max_samples,
    )
    _print_samples(
        "Transition start refusals",
        report.transition_start_refusals,
        args.max_samples,
    )
    _print_samples(
        "Transition instant commits",
        report.transition_instant_commits,
        args.max_samples,
    )
    _print_samples(
        "Transition request drops",
        report.transition_request_drops,
        args.max_samples,
    )
    _print_samples(
        "GL program lifecycle errors",
        report.gl_program_lifecycle_errors,
        args.max_samples,
    )
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
