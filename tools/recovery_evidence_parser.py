"""Read-only forensic parser for SRPSS architecture-recovery evidence.

Plain evidence subfolders are the current format.  Legacy ZIP archives remain
readable for old frozen comparisons.  Derived artifacts are written only to
the caller-selected output directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PARSER_VERSION = "1.8"

_TIMESTAMP_RE = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_LOG_FILE_RE = re.compile(r"^(?P<base>.+\.log)(?:\.(?P<rotation>\d+))?$")
_KV_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^,\s]+)")
_FRAME_RE = re.compile(
    r"\[GL (?P<kind>RENDER|PAINT|ANIM)\](?P<label>.*?)"
    r"(?:Timer )?metrics:\s*(?P<payload>.*)",
    re.IGNORECASE,
)
_MICROGAP_RE = re.compile(r"\[SPOTIFY_VIS\]\[MICROGAP\]\s*(?P<payload>.*)")
_TICK_SPIKE_RE = re.compile(
    r"\[SPOTIFY_VIS\]\s+Tick dt spike_ms=(?P<dt_ms>[0-9.]+)(?P<payload>.*)"
)
_LATENCY_RE = re.compile(
    r"\[SPOTIFY_VIS\]\[LATENCY\]\s+lag_ms=(?P<lag_ms>[0-9.]+)(?P<payload>.*)"
)
_EVENT_LOOP_RE = re.compile(r"\[EVENT LOOP\] summary\s+(?P<payload>.*)")
_RESOURCE_RE = re.compile(r"\[RESOURCE\] snapshot\s+(?P<payload>.*)")
_RESOURCE_DETAILS_RE = re.compile(r"\bresources_json=(?P<payload>\[.*\])\s*$")
_MODE_RE = re.compile(r"\bmode=(?P<mode>[A-Za-z0-9_-]+)")
_DISPLAY_RE = re.compile(
    r"Showing on screen (?P<screen>\d+): "
    r"(?P<width>\d+)x(?P<height>\d+) at "
    r"\((?P<x>-?\d+), (?P<y>-?\d+)\) DPR=(?P<dpr>[0-9.]+)"
)
_REFRESH_RE = re.compile(
    r"\[REFRESH_DIAG\].*?screen=(?P<screen>\d+).*?"
    r"detected_hz=(?P<detected_hz>[0-9.]+).*?"
    r"target_fps=(?P<target_fps>[0-9.]+)"
)
_LEVEL_RE = re.compile(r"\s-\s(?P<level>WARNING|ERROR|CRITICAL)\s+-\s")
_LIFECYCLE_TERMS = re.compile(
    r"settings|edit|shutdown|cleanup|destroy|context|generation|"
    r"recreate|stop|start|quies|makecurrent|donecurrent|error|warning",
    re.IGNORECASE,
)
_FRAME_GAP_OWNER_RE = re.compile(r"\[PERF\]\[FRAME_GAP_OWNER\]\s+(?P<payload>.*)")
_ADAPTIVE_TIMER_METRICS_RE = re.compile(
    r"\[ADAPTIVE_TIMER\]\s+Metrics:\s*(?P<payload>.*)", re.IGNORECASE
)
_VISUALIZER_LANE_RE = re.compile(
    r"\[PERF\]\s*\[SPOTIFY_VIS\]\[(?P<lane>BUBBLE_LANE|AUDIO_LANE)\]\s+(?P<payload>.*)"
)
_MEDIA_PRESENTATION_RE = re.compile(
    r"\[PERF\]\[MEDIA_PRESENTATION\]\s+(?P<payload>.*)"
)
_CACHE_REPRESENTATIONS_RE = re.compile(
    r"\[PERF\]\s*\[CACHE\]\s+ImageCacheRepresentations:\s*(?P<payload>.*)"
)
_CACHE_FLOW_RE = re.compile(
    r"\[PERF\]\s*\[CACHE\]\s+ImageCacheFlow:\s*(?P<payload>.*)"
)
_LIFECYCLE_BARRIER_RE = re.compile(
    r"\[LIFECYCLE_BARRIER\]\s+(?P<event>armed|complete)\s+(?P<payload>.*)"
)
_IMAGE_UI_DELAY_RE = re.compile(
    r"\[PERF\]\s*\[IMAGE_UI_DELAY\]\s+(?P<payload>.*)"
)
_IMAGE_UI_SEGMENT_RE = re.compile(
    r"\[PERF\]\s*\[IMAGE_UI_SEGMENT\]\s+(?P<payload>.*)"
)
_GL_RETENTION_RE = re.compile(
    r"\[PERF\]\s*\[GL RETENTION\]\s+(?P<payload>.*)"
)


@dataclass(frozen=True)
class ArchiveAnalysis:
    summary: dict[str, object]
    frame_rows: list[dict[str, object]]
    task_rows: list[dict[str, object]]
    memory_rows: list[dict[str, object]]
    gpu_rows: list[dict[str, object]]
    event_loop_rows: list[dict[str, object]]
    resource_rows: list[dict[str, object]]
    lifecycle_rows: list[dict[str, object]]
    visualizer_rows: list[dict[str, object]]
    phase5_rows: list[dict[str, object]]
    errors_and_warnings: list[str]
    unknown_lines: list[str]


def _timestamp(line: str) -> str:
    match = _TIMESTAMP_RE.match(line)
    return match.group("timestamp") if match else ""


def _timestamp_value(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _kv(payload: str) -> dict[str, str]:
    return {
        match.group("key"): match.group("value")
        for match in _KV_RE.finditer(payload)
    }


def _json_object_after_marker(line: str, marker: str) -> dict[str, object]:
    """Decode one nested JSON object without assuming it ends the log line."""

    marker_index = line.find(marker)
    if marker_index < 0:
        return {}
    payload = line[marker_index + len(marker):].lstrip()
    try:
        decoded, _end = json.JSONDecoder().raw_decode(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _number(value: str | None) -> float | None:
    if value is None or value.lower() in {"na", "none", "<none>", "n/a"}:
        return None
    cleaned = value.rstrip("%").removesuffix("ms").removesuffix("Hz").removesuffix("s")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _integer(value: str | None) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _log_file_identity(path: Path) -> tuple[str, int] | None:
    match = _LOG_FILE_RE.match(path.name)
    if match is None:
        return None
    return match.group("base"), int(match.group("rotation") or 0)


def _directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for log_path in sorted(
        (
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file() and _log_file_identity(candidate) is not None
        ),
        key=lambda item: item.relative_to(path).as_posix().lower(),
    ):
        relative = log_path.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with log_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest().upper()


def _source_hash(path: Path) -> str:
    return _directory_hash(path) if path.is_dir() else _file_hash(path)


def _read_source(path: Path) -> tuple[dict[str, list[str]], dict[str, int]]:
    rotated_logs: dict[str, dict[int, list[str]]] = {}
    sizes: dict[str, int] = {}

    def add_log(name: str, text: str, size: int) -> None:
        identity = _log_file_identity(Path(name))
        if identity is None:
            return
        base, rotation = identity
        versions = rotated_logs.setdefault(base, {})
        if rotation in versions:
            raise ValueError(f"Duplicate log rotation in evidence source: {name}")
        versions[rotation] = text.splitlines()
        sizes[Path(name).name] = size

    if path.is_dir():
        for log_path in sorted(
            (
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file()
                and _log_file_identity(candidate) is not None
            ),
            key=lambda item: item.relative_to(path).as_posix().lower(),
        ):
            text = log_path.read_text(encoding="utf-8", errors="replace")
            add_log(log_path.name, text, log_path.stat().st_size)
        return {
            base: [
                line
                for rotation in sorted(versions, reverse=True)
                for line in versions[rotation]
            ]
            for base, versions in rotated_logs.items()
        }, sizes

    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir() or _log_file_identity(Path(info.filename)) is None:
                continue
            text = archive.read(info).decode("utf-8", errors="replace")
            add_log(Path(info.filename).name, text, info.file_size)
    return {
        base: [
            line
            for rotation in sorted(versions, reverse=True)
            for line in versions[rotation]
        ]
        for base, versions in rotated_logs.items()
    }, sizes


def _parse_usage(
    lines: Sequence[str],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    memory_rows: list[dict[str, object]] = []
    gpu_rows: list[dict[str, object]] = []
    counters: list[dict[str, object]] = []

    for line_number, line in enumerate(lines, 1):
        if "[USAGE] sample " not in line:
            continue
        values = _kv(line.split("[USAGE] sample ", 1)[1])
        common = {
            "timestamp": _timestamp(line),
            "line": line_number,
            "sequence": _integer(values.get("seq")),
        }
        memory_rows.append(
            {
                **common,
                "rss_app_mb": _number(values.get("rss_app_mb")),
                "rss_main_mb": _number(values.get("rss_main_mb")),
                "rss_children_mb": _number(values.get("rss_children_mb")),
                "image_worker_pid": _integer(values.get("image_worker_pid")),
                "image_worker_rss_mb": _number(
                    values.get("image_worker_rss_mb")
                ),
                "image_worker_vms_mb": _number(
                    values.get("image_worker_vms_mb")
                ),
                "shm_segments_created": _integer(
                    values.get("shm_segments_created")
                ),
                "shm_segments_live": _integer(
                    values.get("shm_segments_live")
                ),
                "shm_live_bytes": _integer(values.get("shm_live_bytes")),
                "shm_segments_consumed": _integer(
                    values.get("shm_segments_consumed")
                ),
                "shm_segments_reclaimed_late": _integer(
                    values.get("shm_segments_reclaimed_late")
                ),
                "shm_unlink_failures": _integer(
                    values.get("shm_unlink_failures")
                ),
                "private_app_mb": _number(values.get("private_app_mb")),
                "private_main_mb": _number(values.get("private_main_mb")),
                "private_children_mb": _number(
                    values.get("private_children_mb")
                ),
                "uss_app_mb": _number(values.get("uss_app_mb")),
                "uss_main_mb": _number(values.get("uss_main_mb")),
                "uss_children_mb": _number(values.get("uss_children_mb")),
                "vms_app_mb": _number(values.get("vms_app_mb")),
                "threads_app": _integer(values.get("threads_app")),
                "handles_app": _integer(values.get("handles_app")),
                "image_cache_items": _integer(
                    values.get("cpu_cache_resources") or values.get("img_cache_items")
                ),
                "image_cache_est_mb": _number(values.get("img_cache_est_mb")),
                "image_cache_budget_mb": _number(values.get("img_cache_budget_mb")),
                "image_cache_tracked_bytes": _integer(
                    values.get("cpu_cache_bytes") or values.get("img_cache_tracked_bytes")
                ),
                "display_image_resources": _integer(values.get("cpu_display_resources")),
                "display_image_tracked_bytes": _integer(values.get("cpu_display_bytes")),
                "tracked_resources": _integer(values.get("tracked_resources")),
                "tracked_known_bytes": _integer(values.get("tracked_known_bytes")),
                "resource_total": _integer(
                    values.get("rm_resources") or values.get("rm_total")
                ),
                "resource_known_bytes": _integer(values.get("rm_known_bytes")),
                "resource_unknown_count": _integer(values.get("rm_unknown_resources")),
                "resource_gl_total": _integer(
                    values.get("gl_resources") or values.get("rm_gl_total")
                ),
                "resource_gl_known_bytes": _integer(values.get("gl_known_bytes")),
                "resource_gl_unknown_count": _integer(values.get("gl_unknown_resources")),
                "resource_gl_texture": _integer(
                    values.get("gl_texture_resources") or values.get("rm_gl_texture")
                ),
                "resource_gl_texture_bytes": _integer(values.get("gl_texture_bytes")),
                "resource_gl_framebuffer": _integer(
                    values.get("gl_framebuffer_resources") or values.get("rm_gl_framebuffer")
                ),
                "resource_gl_framebuffer_bytes": _integer(values.get("gl_framebuffer_bytes")),
                "resource_gl_renderbuffer": _integer(
                    values.get("gl_renderbuffer_resources") or values.get("rm_gl_renderbuffer")
                ),
                "resource_gl_renderbuffer_bytes": _integer(values.get("gl_renderbuffer_bytes")),
                "resource_gl_pbo": _integer(values.get("gl_pbo_resources")),
                "resource_gl_pbo_bytes": _integer(values.get("gl_pbo_bytes")),
                "qt_default_fbo": values.get("qt_default_fbo"),
                "resource_gl_texture_est_mb": _number(
                    values.get("rm_gl_texture_est_mb")
                ),
                "resource_gl_pbo_est_mb": _number(values.get("rm_gl_pbo_est_mb")),
            }
        )
        gpu_rows.append(
            {
                **common,
                "gpu_supported": values.get("gpu_supported"),
                "gpu_active": values.get("gpu_active"),
                "gpu_status": values.get("gpu_status"),
                "gpu_busy_pct": _number(values.get("gpu_busy_pct")),
                "gpu_engine_sum_pct": _number(values.get("gpu_engine_sum_pct")),
                "vram_supported": values.get("vram_supported"),
                "vram_dedicated_mb": _number(values.get("vram_dedicated_mb")),
                "vram_shared_mb": _number(values.get("vram_shared_mb")),
            }
        )
        category_payload = _json_object_after_marker(line, "tm_categories=")
        category_submitted = {
            str(category): int(counts.get("submitted", 0) or 0)
            for category, counts in category_payload.items()
            if isinstance(counts, dict)
        }
        counters.append(
            {
                **common,
                "cpu_app_pct": _number(values.get("cpu_app_pct")),
                "cpu_main_pct": _number(values.get("cpu_main_pct")),
                "cpu_system_pct": _number(values.get("cpu_system_pct")),
                "compute_submitted": _integer(values.get("tm_compute_submitted")),
                "compute_completed": _integer(values.get("tm_compute_completed")),
                "io_submitted": _integer(values.get("tm_io_submitted")),
                "io_completed": _integer(values.get("tm_io_completed")),
                "active_tasks": _integer(values.get("tm_active")),
                "category_submitted": category_submitted,
            }
        )

    task_rows: list[dict[str, object]] = []
    for previous, current in zip(counters, counters[1:]):
        previous_time = _timestamp_value(str(previous["timestamp"]))
        current_time = _timestamp_value(str(current["timestamp"]))
        if previous_time is None or current_time is None:
            continue
        elapsed = (current_time - previous_time).total_seconds()
        if elapsed <= 0:
            continue
        compute_delta = _counter_delta(
            previous.get("compute_submitted"), current.get("compute_submitted")
        )
        io_delta = _counter_delta(previous.get("io_submitted"), current.get("io_submitted"))
        previous_categories = previous.get("category_submitted", {})
        current_categories = current.get("category_submitted", {})
        category_deltas: dict[str, int] = {}
        if isinstance(previous_categories, dict) and isinstance(current_categories, dict):
            for category in sorted(set(previous_categories) | set(current_categories)):
                before = int(previous_categories.get(category, 0) or 0)
                after = int(current_categories.get(category, 0) or 0)
                if after >= before:
                    category_deltas[str(category)] = after - before
        category_rates = {
            category: delta / elapsed
            for category, delta in category_deltas.items()
        }
        category_total_delta = sum(category_deltas.values())
        explicit_category_delta = sum(
            delta
            for category, delta in category_deltas.items()
            if category not in {"uncategorized", "other"}
        )
        task_rows.append(
            {
                "timestamp": current["timestamp"],
                "line": current["line"],
                "sequence": current["sequence"],
                "interval_seconds": elapsed,
                "compute_submitted_delta": compute_delta,
                "compute_submitted_per_sec": (
                    compute_delta / elapsed if compute_delta is not None else None
                ),
                "io_submitted_delta": io_delta,
                "io_submitted_per_sec": (
                    io_delta / elapsed if io_delta is not None else None
                ),
                "total_submitted_per_sec": (
                    (compute_delta + io_delta) / elapsed
                    if compute_delta is not None and io_delta is not None
                    else None
                ),
                "category_submitted_delta": json.dumps(
                    category_deltas, separators=(",", ":"), sort_keys=True
                ),
                "category_submitted_per_sec": json.dumps(
                    category_rates, separators=(",", ":"), sort_keys=True
                ),
                "category_coverage_pct": (
                    explicit_category_delta / category_total_delta * 100.0
                    if category_total_delta > 0
                    else None
                ),
                "active_tasks": current.get("active_tasks"),
                "cpu_app_pct": current.get("cpu_app_pct"),
                "cpu_main_pct": current.get("cpu_main_pct"),
                "cpu_system_pct": current.get("cpu_system_pct"),
            }
        )
    return task_rows, memory_rows, gpu_rows


def _counter_delta(previous: object, current: object) -> int | None:
    if not isinstance(previous, int) or not isinstance(current, int) or current < previous:
        return None
    return current - previous


def _parse_frames(lines: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        match = _FRAME_RE.search(line)
        if not match:
            continue
        values = _kv(match.group("payload"))
        target = values.get("target_fps") or values.get("target")
        rows.append(
            {
                "timestamp": _timestamp(line),
                "line": line_number,
                "kind": match.group("kind").upper(),
                "label": match.group("label").strip(),
                "screen": _integer(values.get("screen")),
                "frames": _integer(values.get("frames")),
                "wakeups": _integer(values.get("wakeups")),
                "average_fps": _number(values.get("avg_fps")),
                "dt_min_ms": _number(values.get("dt_min")),
                "dt_p50_ms": _number(values.get("dt_p50_ms")),
                "dt_p90_ms": _number(values.get("dt_p90_ms")),
                "dt_p95_ms": _number(values.get("dt_p95_ms")),
                "dt_p99_ms": _number(values.get("dt_p99_ms")),
                "dt_max_ms": _number(values.get("dt_max_ms") or values.get("dt_max")),
                "dt_over_25_ms": _integer(values.get("dt_over_25_ms")),
                "dt_over_33_ms": _integer(values.get("dt_over_33_ms")),
                "dt_over_50_ms": _integer(values.get("dt_over_50_ms")),
                "dt_over_100_ms": _integer(values.get("dt_over_100_ms")),
                "paint_p50_ms": _number(values.get("paint_p50_ms")),
                "paint_p90_ms": _number(values.get("paint_p90_ms")),
                "paint_p95_ms": _number(values.get("paint_p95_ms")),
                "paint_p99_ms": _number(values.get("paint_p99_ms")),
                "paint_max_ms": _number(values.get("paint_max_ms")),
                "request_age_p50_ms": _number(values.get("request_age_p50_ms")),
                "request_age_p90_ms": _number(values.get("request_age_p90_ms")),
                "request_age_p95_ms": _number(values.get("request_age_p95_ms")),
                "request_age_p99_ms": _number(values.get("request_age_p99_ms")),
                "request_age_max_ms": _number(values.get("request_age_max_ms")),
                "window_frames": _integer(values.get("window_frames")),
                "render_requests": _integer(values.get("render_requests")),
                "skipped_requests": _integer(values.get("skipped_requests")),
                "request_acceptance_pct": _number(values.get("request_acceptance_pct")),
                "last_presented_frame": _integer(values.get("last_presented_frame")),
                "scene_generation": _integer(values.get("scene_generation")),
                "target_fps": _number(target),
                "pending_skips": _integer(values.get("pending_skips")),
                "slow_frames": _integer(values.get("slow_frames")),
                "outcome": values.get("outcome", ""),
            }
        )
    return rows


def _parse_event_loop(lines: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        match = _EVENT_LOOP_RE.search(line)
        if not match:
            continue
        values = _kv(match.group("payload"))
        rows.append(
            {
                "timestamp": _timestamp(line),
                "line": line_number,
                "samples": _integer(values.get("samples")),
                "retained": _integer(values.get("retained")),
                "interval_ms": _number(values.get("interval_ms")),
                "late_p50_ms": _number(values.get("late_p50_ms")),
                "late_p90_ms": _number(values.get("late_p90_ms")),
                "late_p95_ms": _number(values.get("late_p95_ms")),
                "late_p99_ms": _number(values.get("late_p99_ms")),
                "late_max_ms": _number(values.get("late_max_ms")),
                "over_25_ms": _integer(values.get("over_25_ms")),
                "over_50_ms": _integer(values.get("over_50_ms")),
                "over_100_ms": _integer(values.get("over_100_ms")),
                "outcome": values.get("outcome", ""),
            }
        )
    return rows


def _parse_resources(lines: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        match = _RESOURCE_RE.search(line)
        if not match:
            continue
        values = _kv(match.group("payload"))
        details: list[object] = []
        details_match = _RESOURCE_DETAILS_RE.search(line)
        if details_match:
            try:
                decoded = json.loads(details_match.group("payload"))
                if isinstance(decoded, list):
                    details = decoded
            except (TypeError, ValueError, json.JSONDecodeError):
                details = []
        rows.append(
            {
                "timestamp": _timestamp(line),
                "line": line_number,
                "event": values.get("event", ""),
                "stage": values.get("stage", ""),
                "tracked_resources": _integer(values.get("tracked_resources")),
                "tracked_known_bytes": _integer(values.get("tracked_known_bytes")),
                "cpu_cache_resources": _integer(values.get("cpu_cache_resources")),
                "cpu_cache_bytes": _integer(values.get("cpu_cache_bytes")),
                "cpu_display_resources": _integer(values.get("cpu_display_resources")),
                "cpu_display_bytes": _integer(values.get("cpu_display_bytes")),
                "rm_resources": _integer(values.get("rm_resources")),
                "rm_known_bytes": _integer(values.get("rm_known_bytes")),
                "rm_unknown_resources": _integer(values.get("rm_unknown_resources")),
                "gl_resources": _integer(values.get("gl_resources")),
                "gl_known_bytes": _integer(values.get("gl_known_bytes")),
                "gl_unknown_resources": _integer(values.get("gl_unknown_resources")),
                "gl_texture_resources": _integer(values.get("gl_texture_resources")),
                "gl_texture_bytes": _integer(values.get("gl_texture_bytes")),
                "gl_framebuffer_resources": _integer(values.get("gl_framebuffer_resources")),
                "gl_framebuffer_bytes": _integer(values.get("gl_framebuffer_bytes")),
                "gl_renderbuffer_resources": _integer(values.get("gl_renderbuffer_resources")),
                "gl_renderbuffer_bytes": _integer(values.get("gl_renderbuffer_bytes")),
                "gl_pbo_resources": _integer(values.get("gl_pbo_resources")),
                "gl_pbo_bytes": _integer(values.get("gl_pbo_bytes")),
                "qt_default_fbo": values.get("qt_default_fbo", ""),
                "resource_detail_count": len(details),
                "resources_json": json.dumps(
                    details,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            }
        )
    return rows


def _parse_visualizer(lines: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        microgap = _MICROGAP_RE.search(line)
        spike = _TICK_SPIKE_RE.search(line)
        latency = _LATENCY_RE.search(line)
        if microgap:
            values = _kv(microgap.group("payload"))
            rows.append(
                {
                    "timestamp": _timestamp(line),
                    "line": line_number,
                    "event": "microgap",
                    "mode": values.get("mode", ""),
                    "screen": _integer(values.get("screen")),
                    "context": values.get("context", ""),
                    "transition_active": values.get("transition_active", ""),
                    "samples": _integer(values.get("gap_samples")),
                    "p95_ms": _number(values.get("gap_p95_ms")),
                    "max_ms": _number(values.get("gap_max_ms")),
                    "wait_p95_ms": _number(values.get("wait_p95_ms")),
                    "wait_max_ms": _number(values.get("wait_max_ms")),
                }
            )
        elif spike:
            values = _kv(spike.group("payload"))
            rows.append(
                {
                    "timestamp": _timestamp(line),
                    "line": line_number,
                    "event": "tick_spike",
                    "mode": values.get("mode", ""),
                    "screen": None,
                    "context": "",
                    "transition_active": values.get("transition_running", ""),
                    "samples": None,
                    "p95_ms": None,
                    "max_ms": _number(spike.group("dt_ms")),
                    "wait_p95_ms": None,
                    "wait_max_ms": None,
                }
            )
        elif latency:
            values = _kv(latency.group("payload"))
            rows.append(
                {
                    "timestamp": _timestamp(line),
                    "line": line_number,
                    "event": "latency",
                    "mode": values.get("mode", ""),
                    "screen": None,
                    "context": "",
                    "transition_active": "",
                    "samples": None,
                    "p95_ms": None,
                    "max_ms": _number(latency.group("lag_ms")),
                    "wait_p95_ms": None,
                    "wait_max_ms": None,
                }
            )
    return rows


def _parse_lifecycle(lines: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, 1):
        if not _LIFECYCLE_TERMS.search(line):
            continue
        rows.append(
            {
                "timestamp": _timestamp(line),
                "line": line_number,
                "event": line,
            }
        )
    return rows


def _parse_phase5_telemetry(
    logs: Mapping[str, Sequence[str]],
) -> list[dict[str, object]]:
    """Parse current compact Phase 5 records without assuming a log sidecar."""
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for source, lines in sorted(logs.items()):
        for line_number, line in enumerate(lines, 1):
            normalized = line.strip()
            if normalized in seen:
                continue
            match = _FRAME_GAP_OWNER_RE.search(line)
            kind = "frame_gap_owner"
            extra: dict[str, object] = {}
            if match:
                extra["severity"] = _kv(match.group("payload")).get("severity", "")
            else:
                match = _ADAPTIVE_TIMER_METRICS_RE.search(line)
                kind = "adaptive_timer_metrics"
            if not match:
                match = _VISUALIZER_LANE_RE.search(line)
                kind = "visualizer_lane"
                if match:
                    extra["lane"] = match.group("lane").lower()
            if not match:
                match = _MEDIA_PRESENTATION_RE.search(line)
                kind = "media_presentation"
            if not match:
                match = _CACHE_REPRESENTATIONS_RE.search(line)
                kind = "cache_representations"
            if not match:
                match = _CACHE_FLOW_RE.search(line)
                kind = "cache_flow"
            if not match:
                match = _LIFECYCLE_BARRIER_RE.search(line)
                kind = "lifecycle_barrier"
                if match:
                    extra["barrier_event"] = match.group("event")
            if not match:
                match = _IMAGE_UI_DELAY_RE.search(line)
                kind = "image_ui_delay"
            if not match:
                match = _IMAGE_UI_SEGMENT_RE.search(line)
                kind = "image_ui_segment"
            if not match:
                match = _GL_RETENTION_RE.search(line)
                kind = "gl_retention"
            if not match:
                continue
            seen.add(normalized)
            values = _kv(match.group("payload"))
            rows.append(
                {
                    "timestamp": _timestamp(line),
                    "source": source,
                    "line": line_number,
                    "kind": kind,
                    "severity": extra.get("severity", ""),
                    "lane": extra.get("lane", ""),
                    "barrier_event": extra.get("barrier_event", ""),
                    "event": values.get("event", ""),
                    "display": values.get("display", ""),
                    "callable": values.get("callable", ""),
                    "stage": values.get("stage", ""),
                    "generation": _integer(values.get("generation")),
                    "outcome": values.get("outcome", ""),
                    "update_requested": values.get("update_requested", ""),
                    "reason": values.get("reason", ""),
                    "transition": values.get("transition", ""),
                    "owner": values.get("owner", values.get("last_ui", "")),
                    "gap_ms": _number(values.get("gap_ms")),
                    "paint_ms": _number(values.get("paint_ms")),
                    "request_age_ms": _number(values.get("request_age_ms")),
                    "source_age_ms": _number(values.get("source_age_ms")),
                    "simulation_age_ms": _number(values.get("simulation_age_ms")),
                    "render_state_age_ms": _number(values.get("render_state_age_ms")),
                    "owner_age_ms": _number(values.get("last_ui_age_ms")),
                    "elapsed_ms": _number(values.get("elapsed_ms")),
                    "delay_ms": _number(values.get("delay_ms")),
                    "queue_late_ms": _number(values.get("queue_late_ms")),
                    "guard_ms": _number(values.get("guard_ms")),
                    "callback_ms": _number(values.get("callback_ms")),
                    "total_age_ms": _number(values.get("total_age_ms")),
                    "scheduled_mono_ms": _number(values.get("scheduled_mono_ms")),
                    "due_mono_ms": _number(values.get("due_mono_ms")),
                    "start_mono_ms": _number(values.get("start_mono_ms")),
                    "end_mono_ms": _number(values.get("end_mono_ms")),
                    "duration_ms": _number(values.get("duration_ms")),
                    "size": values.get("size", ""),
                    "cold_compositor": values.get("cold_compositor", ""),
                    "manager_before": values.get("manager_before", ""),
                    "manager_after": values.get("manager_after", ""),
                    "cache_size_before": _integer(values.get("cache_size_before")),
                    "cache_size_after": _integer(values.get("cache_size_after")),
                    "retained_key_before": _integer(values.get("retained_key_before")),
                    "old_key": _integer(values.get("old_key")),
                    "new_key": _integer(values.get("new_key")),
                    "old_cached_before": values.get("old_cached_before", ""),
                    "new_cached_before": values.get("new_cached_before", ""),
                    "old_texture_before": _integer(values.get("old_texture_before")),
                    "new_texture_before": _integer(values.get("new_texture_before")),
                    "cache_hits_delta": _integer(values.get("cache_hits_delta")),
                    "texture_allocations_delta": _integer(values.get("texture_allocations_delta")),
                    "texture_uploads_delta": _integer(values.get("texture_uploads_delta")),
                    "terminal": _integer(values.get("terminal")),
                    "retain_active": values.get("retain_active", ""),
                    "retained_texture": _integer(values.get("retained_texture")),
                    "retained_cache_key": _integer(values.get("retained_cache_key")),
                    "texture_count": _integer(values.get("texture_count")),
                    "texture_cache_hits": _integer(values.get("texture_cache_hits")),
                    "texture_allocations": _integer(values.get("texture_allocations")),
                    "texture_uploads": _integer(values.get("texture_uploads")),
                    "texture_deletions": _integer(values.get("texture_deletions")),
                    "pbo_count": _integer(values.get("pbo_count")),
                    "pbo_creations": _integer(values.get("pbo_creations")),
                    "pbo_reuses": _integer(values.get("pbo_reuses")),
                    "upload_total_ms": _number(values.get("upload_total_ms")),
                    "interval_scope": values.get("interval_scope", ""),
                    "interval_texture_uploads": _integer(values.get("interval_texture_uploads")),
                    "interval_texture_allocations": _integer(values.get("interval_texture_allocations")),
                    "interval_pbo_creations": _integer(values.get("interval_pbo_creations")),
                    "interval_pbo_reuses": _integer(values.get("interval_pbo_reuses")),
                    "interval_upload_total_ms": _number(values.get("interval_upload_total_ms")),
                    "frames": _integer(values.get("frames")),
                    "transitions": _integer(values.get("transitions")),
                    "time_idle_ms": _number(values.get("time_idle")),
                    "time_paused_ms": _number(values.get("time_paused")),
                    "time_running_ms": _number(values.get("time_running")),
                    "total_runtime_seconds": _number(values.get("total_runtime")),
                    "logical_steps": _integer(values.get("logical_steps")),
                    "published": _integer(values.get("published")),
                    "executor_tasks": _integer(values.get("executor_tasks")),
                    "handoff_ms_max": _number(values.get("handoff_ms_max")),
                    "execution_ms_max": _number(values.get("execution_ms_max")),
                    "callback_ms_max": _number(values.get("callback_ms_max")),
                    "raw_items": _integer(values.get("raw_items")),
                    "scaled_items": _integer(values.get("scaled_items")),
                    "raw_mb": _number(values.get("raw_mb")),
                    "scaled_mb": _number(values.get("scaled_mb")),
                    "raw_hits": _integer(values.get("raw_hits")),
                    "raw_misses": _integer(values.get("raw_misses")),
                    "scaled_hits": _integer(values.get("scaled_hits")),
                    "scaled_misses": _integer(values.get("scaled_misses")),
                    "worker_requests": _integer(values.get("worker_requests")),
                    "worker_fallbacks": _integer(values.get("worker_fallbacks")),
                    "qobjects": _integer(values.get("qobjects")),
                    "python_owners": _integer(values.get("python_owners")),
                    "values_json": json.dumps(values, separators=(",", ":"), sort_keys=True),
                }
            )
    return rows


def _collect_errors(logs: Mapping[str, Sequence[str]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for source, lines in sorted(logs.items()):
        for line_number, line in enumerate(lines, 1):
            if not (
                _LEVEL_RE.search(line)
                or "Traceback (most recent call last)" in line
                or "QOpenGLContext" in line
            ):
                continue
            normalized = line.strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            found.append(f"{source}:{line_number}: {line}")
    return found


def _collect_modes(logs: Mapping[str, Sequence[str]]) -> list[str]:
    visualizer_markers = (
        "[SPOTIFY_VIS][CFG]",
        "[SPOTIFY_VIS][OVERLAY]",
        "[SPOTIFY_VIS][MICROGAP]",
        "[SPOTIFY_VIS][LATENCY]",
        "[SPOTIFY_VIS] Tick dt spike",
        "[SPOTIFY_VIS][MODE]",
    )
    return sorted(
        {
            match.group("mode").lower()
            for lines in logs.values()
            for line in lines
            if any(marker in line for marker in visualizer_markers)
            for match in _MODE_RE.finditer(line)
        }
    )


def _collect_displays(logs: Mapping[str, Sequence[str]]) -> list[dict[str, object]]:
    by_screen: dict[int, dict[str, object]] = {}
    for lines in logs.values():
        for line in lines:
            display = _DISPLAY_RE.search(line)
            if display:
                screen = int(display.group("screen"))
                by_screen[screen] = {
                    "screen": screen,
                    "logical_width": int(display.group("width")),
                    "logical_height": int(display.group("height")),
                    "x": int(display.group("x")),
                    "y": int(display.group("y")),
                    "dpr": float(display.group("dpr")),
                }
            refresh = _REFRESH_RE.search(line)
            if refresh:
                screen = int(refresh.group("screen"))
                target = by_screen.setdefault(screen, {"screen": screen})
                target["detected_hz"] = float(refresh.group("detected_hz"))
                target["target_fps"] = float(refresh.group("target_fps"))
    return [by_screen[key] for key in sorted(by_screen)]


def _metric_summary(values: Iterable[object]) -> dict[str, float] | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return {
        "minimum": min(numeric),
        "median": statistics.median(numeric),
        "maximum": max(numeric),
    }


def analyze_evidence_source(path: Path) -> ArchiveAnalysis:
    path = path.resolve()
    logs, sizes = _read_source(path)
    usage_lines = logs.get("screensaver_usage.log", [])
    perf_lines = logs.get("screensaver_perf.log", [])
    visualizer_lines = logs.get("screensaver_spotify_vis.log", [])
    lifecycle_lines = logs.get("screensaver_lifecycle.log", [])

    task_rows, memory_rows, gpu_rows = _parse_usage(usage_lines)
    frame_rows = _parse_frames(perf_lines)
    event_loop_rows = _parse_event_loop(perf_lines)
    resource_rows = _parse_resources(perf_lines)
    visualizer_rows = _parse_visualizer(visualizer_lines)
    lifecycle_rows = _parse_lifecycle(lifecycle_lines)
    phase5_rows = _parse_phase5_telemetry(logs)
    errors = _collect_errors(logs)

    recognized = {
        ("screensaver_usage.log", row["line"]) for row in memory_rows
    } | {
        ("screensaver_perf.log", row["line"]) for row in frame_rows
    } | {
        ("screensaver_perf.log", row["line"]) for row in event_loop_rows
    } | {
        ("screensaver_perf.log", row["line"]) for row in resource_rows
    } | {
        ("screensaver_spotify_vis.log", row["line"]) for row in visualizer_rows
    } | {
        ("screensaver_lifecycle.log", row["line"]) for row in lifecycle_rows
    } | {
        (str(row["source"]), row["line"]) for row in phase5_rows
    }
    unknown = [
        f"{source}:{line_number}: {line}"
        for source, lines in sorted(logs.items())
        for line_number, line in enumerate(lines, 1)
        if line.strip() and (source, line_number) not in recognized
    ]

    timestamps = [
        value
        for lines in logs.values()
        for line in lines
        if (value := _timestamp(line))
    ]
    usage_cpu = [row.get("cpu_app_pct") for row in task_rows]
    summary: dict[str, object] = {
        "parser_version": PARSER_VERSION,
        "source_kind": "folder" if path.is_dir() else "zip",
        "source_path": str(path),
        "source_sha256": _source_hash(path),
        # Compatibility fields retained for existing downstream reports.
        "source_archive": str(path),
        "source_archive_sha256": _source_hash(path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_files": sizes,
        "time_range": {
            "first": min(timestamps) if timestamps else None,
            "last": max(timestamps) if timestamps else None,
        },
        "assumptions": [
            "Canonical sidecar logs are parsed by category to avoid double-counting verbose-log duplicates.",
            "Rotated sidecars are joined oldest rotation first, followed by the active .log file.",
            "Task rates are deltas between cumulative usage-sampler counters.",
            "Frame rows are aggregate metric windows; the archives do not contain every raw frame interval.",
            "Unknown non-empty lines are retained verbatim in unknown_lines.txt.",
        ],
        "visualizer_modes_observed": _collect_modes(logs),
        "displays_observed": _collect_displays(logs),
        "counts": {
            "frame_windows": len(frame_rows),
            "task_rate_intervals": len(task_rows),
            "usage_samples": len(memory_rows),
            "event_loop_windows": len(event_loop_rows),
            "resource_snapshots": len(resource_rows),
            "visualizer_events": len(visualizer_rows),
            "lifecycle_events": len(lifecycle_rows),
            "phase5_telemetry_records": len(phase5_rows),
            "deduplicated_errors_and_warnings": len(errors),
            "unknown_lines": len(unknown),
        },
        "usage": {
            "cpu_app_pct": _metric_summary(usage_cpu),
            "rss_app_mb": _metric_summary(
                row.get("rss_app_mb") for row in memory_rows
            ),
            "rss_main_mb": _metric_summary(
                row.get("rss_main_mb") for row in memory_rows
            ),
            "rss_children_mb": _metric_summary(
                row.get("rss_children_mb") for row in memory_rows
            ),
            "image_worker_rss_mb": _metric_summary(
                row.get("image_worker_rss_mb") for row in memory_rows
            ),
            "shm_segments_live": _metric_summary(
                row.get("shm_segments_live") for row in memory_rows
            ),
            "shm_live_bytes": _metric_summary(
                row.get("shm_live_bytes") for row in memory_rows
            ),
            "shm_unlink_failures": _metric_summary(
                row.get("shm_unlink_failures") for row in memory_rows
            ),
            "private_app_mb": _metric_summary(
                row.get("private_app_mb") for row in memory_rows
            ),
            "private_main_mb": _metric_summary(
                row.get("private_main_mb") for row in memory_rows
            ),
            "private_children_mb": _metric_summary(
                row.get("private_children_mb") for row in memory_rows
            ),
            "uss_app_mb": _metric_summary(
                row.get("uss_app_mb") for row in memory_rows
            ),
            "uss_main_mb": _metric_summary(
                row.get("uss_main_mb") for row in memory_rows
            ),
            "uss_children_mb": _metric_summary(
                row.get("uss_children_mb") for row in memory_rows
            ),
            "vram_dedicated_mb": _metric_summary(
                row.get("vram_dedicated_mb") for row in gpu_rows
            ),
            "gpu_busy_pct": _metric_summary(
                row.get("gpu_busy_pct") for row in gpu_rows
            ),
            "compute_submitted_per_sec": _metric_summary(
                row.get("compute_submitted_per_sec") for row in task_rows
            ),
            "total_submitted_per_sec": _metric_summary(
                row.get("total_submitted_per_sec") for row in task_rows
            ),
        },
        "frame_windows": {
            kind: {
                "count": len(rows),
                "average_fps": _metric_summary(
                    row.get("average_fps") for row in rows
                ),
                "dt_p95_ms": _metric_summary(row.get("dt_p95_ms") for row in rows),
                "dt_p99_ms": _metric_summary(row.get("dt_p99_ms") for row in rows),
                "dt_max_ms": _metric_summary(row.get("dt_max_ms") for row in rows),
                "paint_p99_ms": _metric_summary(row.get("paint_p99_ms") for row in rows),
                "request_age_p99_ms": _metric_summary(
                    row.get("request_age_p99_ms") for row in rows
                ),
            }
            for kind in sorted({str(row["kind"]) for row in frame_rows})
            if (rows := [row for row in frame_rows if row["kind"] == kind])
        },
        "event_loop": {
            "late_p99_ms": _metric_summary(
                row.get("late_p99_ms") for row in event_loop_rows
            ),
            "late_max_ms": _metric_summary(
                row.get("late_max_ms") for row in event_loop_rows
            ),
        },
        "resources": {
            "tracked_known_bytes": _metric_summary(
                row.get("tracked_known_bytes") for row in resource_rows
            ),
            "cpu_cache_bytes": _metric_summary(
                row.get("cpu_cache_bytes") for row in resource_rows
            ),
            "gl_known_bytes": _metric_summary(
                row.get("gl_known_bytes") for row in resource_rows
            ),
            "gl_unknown_resources": _metric_summary(
                row.get("gl_unknown_resources") for row in resource_rows
            ),
        },
        "visualizer": {
            "microgap_p95_ms": _metric_summary(
                row.get("p95_ms")
                for row in visualizer_rows
                if row["event"] == "microgap"
            ),
            "microgap_max_ms": _metric_summary(
                row.get("max_ms")
                for row in visualizer_rows
                if row["event"] == "microgap"
            ),
            "tick_spike_ms": _metric_summary(
                row.get("max_ms")
                for row in visualizer_rows
                if row["event"] == "tick_spike"
            ),
            "latency_ms": _metric_summary(
                row.get("max_ms")
                for row in visualizer_rows
                if row["event"] == "latency"
            ),
        },
        "phase5": {
            "frame_gap_owner": {
                "count": sum(row["kind"] == "frame_gap_owner" for row in phase5_rows),
                "gap_ms": _metric_summary(
                    row.get("gap_ms") for row in phase5_rows
                    if row["kind"] == "frame_gap_owner"
                ),
                "request_age_ms": _metric_summary(
                    row.get("request_age_ms") for row in phase5_rows
                    if row["kind"] == "frame_gap_owner"
                ),
                "source_age_ms": _metric_summary(
                    row.get("source_age_ms") for row in phase5_rows
                    if row["kind"] == "frame_gap_owner"
                ),
                "simulation_age_ms": _metric_summary(
                    row.get("simulation_age_ms") for row in phase5_rows
                    if row["kind"] == "frame_gap_owner"
                ),
                "render_state_age_ms": _metric_summary(
                    row.get("render_state_age_ms") for row in phase5_rows
                    if row["kind"] == "frame_gap_owner"
                ),
                "owner_age_ms": _metric_summary(
                    row.get("owner_age_ms") for row in phase5_rows
                    if row["kind"] == "frame_gap_owner"
                ),
                "severity_counts": {
                    severity: sum(
                        row["kind"] == "frame_gap_owner" and row["severity"] == severity
                        for row in phase5_rows
                    )
                    for severity in sorted({str(row["severity"]) for row in phase5_rows if row["kind"] == "frame_gap_owner"})
                },
            },
            "adaptive_timer": {
                "count": sum(row["kind"] == "adaptive_timer_metrics" for row in phase5_rows),
                "frames": _metric_summary(row.get("frames") for row in phase5_rows if row["kind"] == "adaptive_timer_metrics"),
                "transitions": _metric_summary(row.get("transitions") for row in phase5_rows if row["kind"] == "adaptive_timer_metrics"),
                "time_running_ms": _metric_summary(row.get("time_running_ms") for row in phase5_rows if row["kind"] == "adaptive_timer_metrics"),
                "total_runtime_seconds": _metric_summary(row.get("total_runtime_seconds") for row in phase5_rows if row["kind"] == "adaptive_timer_metrics"),
            },
            "visualizer_lanes": {
                lane: {
                    "count": sum(row["kind"] == "visualizer_lane" and row["lane"] == lane for row in phase5_rows),
                    "logical_steps": _metric_summary(row.get("logical_steps") for row in phase5_rows if row["kind"] == "visualizer_lane" and row["lane"] == lane),
                    "published": _metric_summary(row.get("published") for row in phase5_rows if row["kind"] == "visualizer_lane" and row["lane"] == lane),
                    "execution_ms_max": _metric_summary(row.get("execution_ms_max") for row in phase5_rows if row["kind"] == "visualizer_lane" and row["lane"] == lane),
                }
                for lane in sorted({str(row["lane"]) for row in phase5_rows if row["kind"] == "visualizer_lane"})
            },
            "media_presentation": {
                "applied": sum(row["kind"] == "media_presentation" and row["update_requested"].lower() == "true" for row in phase5_rows),
                "unchanged_refresh_suppressed": sum(row["kind"] == "media_presentation" and row["event"] == "unchanged_refresh_suppressed" for row in phase5_rows),
            },
            "cache": {
                "representation_records": sum(row["kind"] == "cache_representations" for row in phase5_rows),
                "flow_records": sum(row["kind"] == "cache_flow" for row in phase5_rows),
                "raw_items": _metric_summary(row.get("raw_items") for row in phase5_rows if row["kind"] == "cache_representations"),
                "scaled_items": _metric_summary(row.get("scaled_items") for row in phase5_rows if row["kind"] == "cache_representations"),
                "raw_hits": _metric_summary(row.get("raw_hits") for row in phase5_rows if row["kind"] == "cache_flow"),
                "scaled_hits": _metric_summary(row.get("scaled_hits") for row in phase5_rows if row["kind"] == "cache_flow"),
                "worker_requests": _metric_summary(row.get("worker_requests") for row in phase5_rows if row["kind"] == "cache_flow"),
                "worker_fallbacks": _metric_summary(row.get("worker_fallbacks") for row in phase5_rows if row["kind"] == "cache_flow"),
            },
            "lifecycle_barrier": {
                "armed": sum(row["kind"] == "lifecycle_barrier" and row["barrier_event"] == "armed" for row in phase5_rows),
                "complete": sum(row["kind"] == "lifecycle_barrier" and row["barrier_event"] == "complete" for row in phase5_rows),
                "elapsed_ms": _metric_summary(row.get("elapsed_ms") for row in phase5_rows if row["kind"] == "lifecycle_barrier" and row["barrier_event"] == "complete"),
            },
            "image_ui": {
                "delay_records": sum(row["kind"] == "image_ui_delay" for row in phase5_rows),
                "segment_records": sum(row["kind"] == "image_ui_segment" for row in phase5_rows),
                "queue_late_ms": _metric_summary(
                    row.get("queue_late_ms") for row in phase5_rows
                    if row["kind"] == "image_ui_delay"
                ),
                "guard_ms": _metric_summary(
                    row.get("guard_ms") for row in phase5_rows
                    if row["kind"] == "image_ui_delay"
                ),
                "callback_ms": _metric_summary(
                    row.get("callback_ms") for row in phase5_rows
                    if row["kind"] == "image_ui_delay"
                ),
                "total_age_ms": _metric_summary(
                    row.get("total_age_ms") for row in phase5_rows
                    if row["kind"] == "image_ui_delay"
                ),
                "segment_duration_ms": _metric_summary(
                    row.get("duration_ms") for row in phase5_rows
                    if row["kind"] == "image_ui_segment"
                ),
                "segments_by_stage": {
                    stage: {
                        "count": sum(
                            row["kind"] == "image_ui_segment" and row["stage"] == stage
                            for row in phase5_rows
                        ),
                        "duration_ms": _metric_summary(
                            row.get("duration_ms") for row in phase5_rows
                            if row["kind"] == "image_ui_segment" and row["stage"] == stage
                        ),
                        "texture_allocations_delta": _metric_summary(
                            row.get("texture_allocations_delta") for row in phase5_rows
                            if row["kind"] == "image_ui_segment" and row["stage"] == stage
                        ),
                        "texture_uploads_delta": _metric_summary(
                            row.get("texture_uploads_delta") for row in phase5_rows
                            if row["kind"] == "image_ui_segment" and row["stage"] == stage
                        ),
                    }
                    for stage in sorted({
                        str(row["stage"])
                        for row in phase5_rows
                        if row["kind"] == "image_ui_segment" and row["stage"]
                    })
                },
                "outcomes": {
                    outcome: sum(
                        row["kind"] == "image_ui_delay" and row["outcome"] == outcome
                        for row in phase5_rows
                    )
                    for outcome in sorted({
                        str(row["outcome"])
                        for row in phase5_rows
                        if row["kind"] == "image_ui_delay" and row["outcome"]
                    })
                },
            },
            "gl_retention": {
                "records": sum(row["kind"] == "gl_retention" for row in phase5_rows),
                "retained_cache_keys": sorted({
                    int(row["retained_cache_key"])
                    for row in phase5_rows
                    if row["kind"] == "gl_retention" and row.get("retained_cache_key")
                }),
                "texture_uploads": _metric_summary(
                    row.get("texture_uploads") for row in phase5_rows
                    if row["kind"] == "gl_retention"
                ),
                "interval_texture_uploads": _metric_summary(
                    row.get("interval_texture_uploads") for row in phase5_rows
                    if row["kind"] == "gl_retention"
                ),
                "interval_pbo_creations": _metric_summary(
                    row.get("interval_pbo_creations") for row in phase5_rows
                    if row["kind"] == "gl_retention"
                ),
                "interval_pbo_reuses": _metric_summary(
                    row.get("interval_pbo_reuses") for row in phase5_rows
                    if row["kind"] == "gl_retention"
                ),
                "interval_upload_total_ms": _metric_summary(
                    row.get("interval_upload_total_ms") for row in phase5_rows
                    if row["kind"] == "gl_retention"
                ),
            },
        },
    }
    return ArchiveAnalysis(
        summary=summary,
        frame_rows=frame_rows,
        task_rows=task_rows,
        memory_rows=memory_rows,
        gpu_rows=gpu_rows,
        event_loop_rows=event_loop_rows,
        resource_rows=resource_rows,
        lifecycle_rows=lifecycle_rows,
        visualizer_rows=visualizer_rows,
        phase5_rows=phase5_rows,
        errors_and_warnings=errors,
        unknown_lines=unknown,
    )


def analyze_archive(path: Path) -> ArchiveAnalysis:
    """Backward-compatible alias for callers that still pass legacy ZIPs."""
    return analyze_evidence_source(path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_analysis(analysis: ArchiveAnalysis, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(analysis.summary, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_dir / "frame_intervals.csv", analysis.frame_rows)
    _write_csv(output_dir / "task_rates.csv", analysis.task_rows)
    _write_csv(output_dir / "memory_usage.csv", analysis.memory_rows)
    _write_csv(output_dir / "gpu_usage.csv", analysis.gpu_rows)
    _write_csv(output_dir / "event_loop_stalls.csv", analysis.event_loop_rows)
    _write_csv(output_dir / "resource_snapshots.csv", analysis.resource_rows)
    _write_csv(output_dir / "lifecycle_events.csv", analysis.lifecycle_rows)
    _write_csv(output_dir / "visualizer_gaps.csv", analysis.visualizer_rows)
    _write_csv(output_dir / "phase5_telemetry.csv", analysis.phase5_rows)
    (output_dir / "errors_and_warnings.txt").write_text(
        "\n".join(analysis.errors_and_warnings) + "\n",
        encoding="utf-8",
    )
    (output_dir / "unknown_lines.txt").write_text(
        "\n".join(analysis.unknown_lines) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse an SRPSS evidence subfolder or legacy ZIP archive."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--source",
        type=Path,
        help="Evidence subfolder (preferred) or legacy ZIP archive.",
    )
    source.add_argument(
        "--archive",
        type=Path,
        help="Legacy alias for a ZIP evidence source.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    source = args.source or args.archive
    if source is None or not source.exists():
        print(f"Evidence source not found: {source}")
        return 1
    try:
        analysis = analyze_evidence_source(source)
        write_analysis(analysis, args.output_dir)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Failed to parse evidence source: {exc}")
        return 1
    print(
        f"Wrote recovery evidence artifacts to {args.output_dir} "
        f"(sha256={analysis.summary['source_sha256']})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
