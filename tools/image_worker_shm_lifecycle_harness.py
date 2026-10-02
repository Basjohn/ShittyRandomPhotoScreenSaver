"""Bounded ImageWorker lifecycle and P0 parent-handoff evidence harness.

The default run retains the R-52 foreground ImageWorker shared-memory plateau
check. ``--parent-baseline`` measures parent Qt scale/RGBA-format work with
QImage decode deliberately outside the timed window, and
``--prefetch`` exercises one persistent speculative ImageWorker through the
production asynchronous batch derivative/response path. None of the modes
creates a QGuiApplication or visible surface.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import tempfile
import threading
import time
from datetime import datetime
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psutil
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.process.workers.image_worker import (
    image_worker_main,
    speculative_image_worker_main,
)
from engine.image_pipeline import derive_prefetch_via_worker, load_image_via_worker
from rendering.display_modes import DisplayMode
from rendering.image_processor_async import AsyncImageProcessor
from rendering.image_quality import RESAMPLE_FILTERS, decode_image, process_image


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    count = float(len(values))
    x_mean = (count - 1.0) / 2.0
    y_mean = sum(values) / count
    numerator = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(values)
    )
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    return numerator / denominator if denominator else 0.0


def _timing_summary(values_ns: list[int], *, warmup_cycles: int) -> dict[str, float | int | None]:
    tail = values_ns[warmup_cycles:]
    values_ms = [value / 1_000_000.0 for value in tail]
    return {
        "samples": len(values_ms),
        "median_ms": statistics.median(values_ms) if values_ms else None,
        "p95_ms": _percentile(values_ms, 0.95) if values_ms else None,
        "p99_ms": _percentile(values_ms, 0.99) if values_ms else None,
        "max_ms": max(values_ms) if values_ms else None,
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * quantile)))]


def _worker_memory(
    supervisor: ProcessSupervisor,
    worker_type: WorkerType,
) -> dict[str, float | int | None]:
    snapshot = supervisor.get_image_worker_usage_snapshot()
    if worker_type is WorkerType.IMAGE_PREFETCH:
        prefix = "image_prefetch_worker"
    else:
        prefix = "image_worker"
    pid = snapshot.get(f"{prefix}_pid")
    private_mb: float | None = None
    if isinstance(pid, int) and pid > 0:
        try:
            memory = psutil.Process(pid).memory_info()
            private = getattr(memory, "private", None)
            if private is not None:
                private_mb = float(private) / (1024.0 * 1024.0)
        except (psutil.Error, OSError):
            private_mb = None
    return {
        "pid": pid,
        "rss_mb": snapshot.get(f"{prefix}_rss_mb"),
        "vms_mb": snapshot.get(f"{prefix}_vms_mb"),
        "private_mb": private_mb,
    }


def _parent_handle_count() -> int | None:
    """Return this harness process's Windows handle count when available."""
    try:
        process = psutil.Process(os.getpid())
        getter = getattr(process, "num_handles", None)
        if callable(getter):
            return int(getter())
    except (psutil.Error, OSError, ValueError):
        pass
    return None


def _mapping_exists(name: str) -> bool:
    try:
        mapping = SharedMemory(name=name, create=False)
    except FileNotFoundError:
        return False
    else:
        mapping.close()
        return True


def _packed_rgba8888(image: QImage) -> bytes:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    try:
        width, height = int(rgba.width()), int(rgba.height())
        packed_stride = width * 4
        stride = int(rgba.bytesPerLine())
        raw = rgba.constBits().tobytes()
        if stride == packed_stride:
            return raw[: packed_stride * height]
        return b"".join(
            raw[row * stride: row * stride + packed_stride]
            for row in range(height)
        )
    finally:
        del rgba


def _build_prefetch_requests(
    width: int,
    height: int,
    *,
    resample_filter: str,
    sharpen: bool,
) -> list[dict[str, Any]]:
    half_width = max(1, (int(width) * 2) // 3)
    half_height = max(1, (int(height) * 2) // 3)
    quality_label = f"{resample_filter}-sharpen{int(sharpen)}"
    return [
        {
            "cache_key": f"p0-primary-{width}x{height}-{quality_label}",
            "width": int(width),
            "height": int(height),
            "display_mode": DisplayMode.FILL,
            "resample_filter": resample_filter,
            "sharpen": sharpen,
        },
        {
            "cache_key": f"p0-secondary-{half_width}x{half_height}-{quality_label}",
            "width": half_width,
            "height": half_height,
            "display_mode": DisplayMode.FILL,
            "resample_filter": resample_filter,
            "sharpen": sharpen,
        },
    ]


def _expected_prefetch_bytes(
    source_path: Path,
    requests: list[dict[str, Any]],
) -> dict[str, bytes]:
    """One untimed parity reference through the worker's selected quality branch."""

    if not requests:
        return {}
    signatures = {
        (str(request["resample_filter"]), bool(request["sharpen"]))
        for request in requests
    }
    if len(signatures) != 1:
        raise ValueError("prefetch parity requires one resolved quality signature")
    resample_filter, sharpen = next(iter(signatures))
    if resample_filter != "smooth" or sharpen:
        source = decode_image(str(source_path))
        expected: dict[str, bytes] = {}
        for request in requests:
            result = process_image(
                source,
                (int(request["width"]), int(request["height"])),
                request["display_mode"].value,
                resample_filter,
                sharpen,
            )
            expected[str(request["cache_key"])] = result.convert("RGBA").tobytes("raw", "RGBA")
        return expected

    source = QImage(str(source_path))
    if source.isNull():
        raise RuntimeError(f"Qt could not decode parity source {source_path}")
    try:
        expected: dict[str, bytes] = {}
        for request in requests:
            result = AsyncImageProcessor.process_qimage(
                source,
                QSize(int(request["width"]), int(request["height"])),
                request["display_mode"],
                resample_filter=resample_filter,
                sharpen=sharpen,
            )
            try:
                expected[str(request["cache_key"])] = _packed_rgba8888(result)
            finally:
                del result
        return expected
    finally:
        del source


def _parent_baseline_sample(
    source_path: Path,
    requests: list[dict[str, Any]],
) -> tuple[int, QImage]:
    """Measure only former parent GIL-holding Qt scale/RGBA-format work."""

    # Current P0 evidence establishes that QImage(path) decode releases the
    # GIL. The before measurement intentionally excludes that decode boundary.
    source = QImage(str(source_path))
    try:
        if source.isNull():
            raise RuntimeError(f"Qt could not decode {source_path}")
        started_ns = time.perf_counter_ns()
        primary: QImage | None = None
        try:
            for index, request in enumerate(requests):
                scaled = AsyncImageProcessor.process_qimage(
                    source,
                    QSize(int(request["width"]), int(request["height"])),
                    request["display_mode"],
                    resample_filter="smooth",
                    sharpen=False,
                )
                try:
                    rgba = scaled.convertToFormat(QImage.Format.Format_RGBA8888)
                finally:
                    del scaled
                if rgba.isNull() or (
                    rgba.width() != request["width"] or rgba.height() != request["height"]
                ):
                    del rgba
                    raise RuntimeError(
                        f"parent Qt derivative geometry changed for {request['cache_key']}"
                    )
                if index == 0:
                    primary = rgba
                else:
                    del rgba
            if primary is None:
                raise RuntimeError("parent baseline requires at least one derivative")
            return time.perf_counter_ns() - started_ns, primary
        except Exception:
            if primary is not None:
                del primary
            raise
    finally:
        del source


def _await_prefetch_batch(
    engine: Any,
    source_path: Path,
    requests: list[dict[str, Any]],
    generation: int,
    timeout_ms: int,
) -> dict[str, QImage]:
    done = threading.Event()
    outcome: dict[str, object] = {}

    def _complete(images: dict[str, QImage], error: BaseException | None) -> None:
        outcome["images"] = images
        outcome["error"] = error
        done.set()

    cancel = derive_prefetch_via_worker(
        engine,
        str(source_path),
        requests,
        generation,
        _complete,
    )
    if not done.wait(max(0.001, timeout_ms / 1000.0)):
        cancel()
        raise TimeoutError("prefetch worker response timed out")
    error = outcome.get("error")
    if error is not None:
        raise error
    images = outcome.get("images")
    if not isinstance(images, dict):
        raise RuntimeError("prefetch completion did not return an image mapping")
    return images


def run_harness(
    *,
    cycles: int = 50,
    width: int = 3840,
    height: int = 2160,
    warmup_cycles: int = 10,
    timeout_ms: int = 15_000,
    exercise_shutdown_transfer: bool = True,
    prefetch: bool = False,
    parent_baseline: bool = False,
    resample_filter: str | None = None,
    sharpen: bool = False,
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Run one bounded foreground, parent-baseline, or production-prefetch lane."""

    if prefetch and parent_baseline:
        raise ValueError("--prefetch and --parent-baseline are mutually exclusive")
    if (
        resample_filter is not None
        and (
            not isinstance(resample_filter, str)
            or resample_filter not in RESAMPLE_FILTERS
        )
    ):
        raise ValueError(f"Unknown resample filter: {resample_filter!r}")
    if not isinstance(sharpen, bool):
        raise TypeError("sharpen must be a boolean")
    default_filter = "smooth" if (prefetch or parent_baseline) else "lanczos"
    effective_filter = resample_filter or default_filter
    if parent_baseline and (effective_filter != "smooth" or sharpen):
        raise ValueError(
            "--parent-baseline measures only historical smooth Qt scaling; "
            "use --resample-filter smooth without --sharpen"
        )
    supplied_source = Path(source_path) if source_path is not None else None
    if supplied_source is not None and not supplied_source.is_file():
        raise FileNotFoundError(f"Source image does not exist: {supplied_source}")
    cycles = max(1, int(cycles))
    width = max(1, int(width))
    height = max(1, int(height))
    warmup_cycles = min(max(0, int(warmup_cycles)), max(0, cycles - 1))
    worker_type = WorkerType.IMAGE_PREFETCH if prefetch else WorkerType.IMAGE
    worker_required = not parent_baseline
    effective_shutdown_transfer = bool(exercise_shutdown_transfer and worker_required)
    source_width = width * 2 if (prefetch or parent_baseline) else width
    source_height = height * 2 if (prefetch or parent_baseline) else height
    scenario = (
        "p0_parent_qt_scale_format_baseline"
        if parent_baseline
        else "p0_prefetch_worker_batch"
        if prefetch
        else "image_worker_shared_memory_lifecycle"
    )

    supervisor = ProcessSupervisor()
    if worker_type is WorkerType.IMAGE_PREFETCH:
        supervisor.register_worker_factory(
            WorkerType.IMAGE_PREFETCH,
            speculative_image_worker_main,
        )
    else:
        supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)

    errors: list[str] = []
    shared_memory_names: list[str] = []
    samples: list[dict[str, Any]] = []
    parent_handoffs: list[dict[str, int]] = []
    parent_baseline_durations_ns: list[int] = []
    worker_scale_durations_ns: list[int] = []
    worker_pids: list[int] = []
    orphans_before_shutdown: list[str] = []
    started_at = time.monotonic()
    expected_prefetch: dict[str, bytes] = {}
    prefetch_requests = (
        _build_prefetch_requests(
            width,
            height,
            resample_filter=effective_filter,
            sharpen=sharpen,
        )
        if (prefetch or parent_baseline)
        else []
    )

    with tempfile.TemporaryDirectory(prefix="srpss_image_worker_shm_") as temp_dir:
        synthetic_source = supplied_source is None
        if supplied_source is None:
            resolved_source_path = Path(temp_dir) / "synthetic_source.png"
            # A deterministic opaque source avoids network/file variability. P0
            # baseline/prefetch sources are twice target size so Qt actually scales.
            image = Image.new("RGB", (source_width, source_height), (31, 97, 173))
            image.save(resolved_source_path, "PNG")
            image.close()
        else:
            resolved_source_path = supplied_source
            with Image.open(resolved_source_path) as source_image:
                source_width, source_height = source_image.size

        if prefetch:
            expected_prefetch = _expected_prefetch_bytes(resolved_source_path, prefetch_requests)

        if worker_required and not supervisor.start(worker_type):
            raise RuntimeError(f"{worker_type.value} worker failed to start")

        display_manager = object()
        engine = SimpleNamespace(
            _process_supervisor=supervisor,
            _runtime_generation=1,
            _shutting_down=False,
            display_manager=display_manager,
            settings_manager=None,
        )

        consume = supervisor.consume_shared_memory_response
        dispose = supervisor.dispose_response

        def _recording_consume(response, consumer):
            payload = getattr(response, "payload", {})
            name = payload.get("shared_memory_name") if isinstance(payload, dict) else None
            if name:
                shared_memory_names.append(str(name))
            started_ns = time.perf_counter_ns()
            try:
                return consume(response, consumer)
            finally:
                if prefetch and isinstance(payload, dict) and "derivatives" in payload:
                    parent_handoffs.append(
                        {
                            "duration_ns": time.perf_counter_ns() - started_ns,
                            "worker_pid": int(payload.get("worker_pid", 0)),
                            "decode_count": int(payload.get("decode_count", 0)),
                            "derivative_count": len(payload.get("derivatives", ())),
                            "scale_started_ns": int(payload.get("scale_started_ns", 0)),
                            "scale_finished_ns": int(payload.get("scale_finished_ns", 0)),
                        }
                    )

        def _recording_dispose(response, *, reason):
            payload = getattr(response, "payload", {})
            name = payload.get("shared_memory_name") if isinstance(payload, dict) else None
            if name:
                shared_memory_names.append(str(name))
            return dispose(response, reason=reason)

        supervisor.consume_shared_memory_response = _recording_consume
        supervisor.dispose_response = _recording_dispose

        try:
            for cycle in range(1, cycles + 1):
                if parent_baseline:
                    duration_ns, qimage = _parent_baseline_sample(
                        resolved_source_path,
                        prefetch_requests,
                    )
                    parent_baseline_durations_ns.append(duration_ns)
                    if qimage.width() != width or qimage.height() != height:
                        errors.append(f"cycle {cycle}: parent baseline output size changed")
                    pixel = qimage.pixelColor(width // 2, height // 2)
                    if synthetic_source and (pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()) != (31, 97, 173, 255):
                        errors.append(f"cycle {cycle}: parent baseline pixel data changed")
                    if pixel.alpha() != 255:
                        errors.append(f"cycle {cycle}: parent baseline output was not opaque")
                    del qimage
                    samples.append({"cycle": cycle, "parent_qt_scale_format_ns": duration_ns})
                    continue

                if prefetch:
                    handoff_count_before = len(parent_handoffs)
                    images = _await_prefetch_batch(
                        engine,
                        resolved_source_path,
                        prefetch_requests,
                        generation=1,
                        timeout_ms=timeout_ms,
                    )
                    if set(images) != set(expected_prefetch):
                        errors.append(f"cycle {cycle}: derivative cache-key set changed")
                    for request in prefetch_requests:
                        key = str(request["cache_key"])
                        image = images.get(key)
                        if not isinstance(image, QImage) or image.isNull():
                            errors.append(f"cycle {cycle}: missing derivative {key}")
                            continue
                        if image.width() != request["width"] or image.height() != request["height"]:
                            errors.append(f"cycle {cycle}: derivative geometry changed for {key}")
                        if _packed_rgba8888(image) != expected_prefetch[key]:
                            errors.append(f"cycle {cycle}: derivative bytes changed for {key}")
                        del image
                    images.clear()
                    new_handoffs = parent_handoffs[handoff_count_before:]
                    if len(new_handoffs) != 1:
                        errors.append(
                            f"cycle {cycle}: expected one parent handoff, got {len(new_handoffs)}"
                        )
                    else:
                        handoff = new_handoffs[0]
                        handoff["cycle"] = cycle
                        parent_handoffs[-1] = handoff
                        worker_pids.append(handoff["worker_pid"])
                        scale_started = handoff["scale_started_ns"]
                        scale_finished = handoff["scale_finished_ns"]
                        if scale_finished < scale_started or scale_started <= 0:
                            errors.append(f"cycle {cycle}: worker scale timing was invalid")
                        else:
                            worker_scale_durations_ns.append(scale_finished - scale_started)
                        if handoff["decode_count"] != 1:
                            errors.append(f"cycle {cycle}: speculative source decoded {handoff['decode_count']} times")
                        if handoff["derivative_count"] != len(prefetch_requests):
                            errors.append(f"cycle {cycle}: worker derivative count changed")
                else:
                    qimage = load_image_via_worker(
                        engine,
                        str(resolved_source_path),
                        width,
                        height,
                        display_mode="fill",
                        resample_filter=effective_filter,
                        sharpen=sharpen,
                        timeout_ms=timeout_ms,
                    )
                    if qimage is None:
                        errors.append(f"cycle {cycle}: ImageWorker returned no QImage")
                        break
                    if qimage.width() != width or qimage.height() != height:
                        errors.append(
                            f"cycle {cycle}: unexpected size {qimage.width()}x{qimage.height()}"
                        )
                    pixel = qimage.pixelColor(width // 2, height // 2)
                    if synthetic_source and (pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()) != (31, 97, 173, 255):
                        errors.append(f"cycle {cycle}: copied pixel data changed")
                    if pixel.alpha() != 255:
                        errors.append(f"cycle {cycle}: copied image was not opaque")
                    del qimage

                accounting = supervisor.get_shared_memory_accounting_snapshot()
                memory = _worker_memory(supervisor, worker_type)
                sample: dict[str, Any] = {
                    "cycle": cycle,
                    "parent_handles": _parent_handle_count(),
                    **memory,
                    **accounting,
                }
                if prefetch and parent_handoffs:
                    handoff = parent_handoffs[-1]
                    sample.update(
                        {
                            "parent_handoff_ns": handoff["duration_ns"],
                            "worker_pid": handoff["worker_pid"],
                            "worker_decode_count": handoff["decode_count"],
                            "worker_derivative_count": handoff["derivative_count"],
                            "worker_scale_started_ns": handoff["scale_started_ns"],
                            "worker_scale_finished_ns": handoff["scale_finished_ns"],
                            "worker_scale_ns": worker_scale_durations_ns[-1]
                            if worker_scale_durations_ns
                            else None,
                        }
                    )
                samples.append(sample)
                if accounting["segments_live"] != 0:
                    errors.append(f"cycle {cycle}: {accounting['segments_live']} live segments")
                if accounting["live_bytes"] != 0:
                    errors.append(f"cycle {cycle}: {accounting['live_bytes']} live bytes")

            if worker_required:
                barrier = supervisor.send_request_and_await_response(
                    worker_type,
                    MessageType.CONFIG_UPDATE,
                    payload={},
                    timeout_ms=timeout_ms,
                )
                if barrier is None or not barrier.success:
                    errors.append("post-transfer worker barrier failed")

            if effective_shutdown_transfer:
                if prefetch:
                    shutdown_payload = {
                        "path": str(resolved_source_path),
                        "generation": 1,
                        "derivatives": [
                            {
                                "cache_key": str(request["cache_key"]),
                                "width": int(request["width"]),
                                "height": int(request["height"]),
                                "mode": request["display_mode"].value,
                                "resample_filter": request["resample_filter"],
                                "sharpen": request["sharpen"],
                            }
                            for request in prefetch_requests
                        ],
                    }
                    message_type = MessageType.IMAGE_PREFETCH_BATCH
                else:
                    shutdown_payload = {
                        "path": str(resolved_source_path),
                        "target_width": width,
                        "target_height": height,
                        "mode": "fill",
                        "resample_filter": effective_filter,
                        "sharpen": sharpen,
                    }
                    message_type = MessageType.IMAGE_PRESCALE
                correlation_id = supervisor.send_message(
                    worker_type,
                    message_type,
                    payload=shutdown_payload,
                )
                if correlation_id is None:
                    errors.append("worker-shutdown transfer was not submitted")
                elif not supervisor.stop(
                    worker_type,
                    timeout=max(1.0, timeout_ms / 1000.0),
                ):
                    errors.append("worker shutdown during transfer failed")

            orphans_before_shutdown = [
                name for name in shared_memory_names if _mapping_exists(name)
            ]
        finally:
            supervisor.shutdown()

    orphans_after_shutdown = [name for name in shared_memory_names if _mapping_exists(name)]
    rss_values = [
        float(sample["rss_mb"])
        for sample in samples
        if isinstance(sample.get("rss_mb"), (int, float))
        and math.isfinite(float(sample["rss_mb"]))
    ]
    tail = rss_values[warmup_cycles:]
    tail_slope = _linear_slope(tail)
    head_window = tail[: min(5, len(tail))]
    end_window = tail[-min(5, len(tail)):] if tail else []
    tail_high_water_growth = (
        max(end_window) - max(head_window) if head_window and end_window else 0.0
    )
    accounting = supervisor.get_shared_memory_accounting_snapshot()
    parent_handle_values = [
        float(sample["parent_handles"])
        for sample in samples[warmup_cycles:]
        if isinstance(sample.get("parent_handles"), (int, float))
    ]
    parent_handle_slope = _linear_slope(parent_handle_values)
    parent_handle_growth = (
        parent_handle_values[-1] - parent_handle_values[0]
        if len(parent_handle_values) >= 2 else 0.0
    )
    parent_handoff_durations_ns = [record["duration_ns"] for record in parent_handoffs]
    isolated_worker = all(pid > 0 and pid != os.getpid() for pid in worker_pids)
    one_persistent_worker_pid = len(set(worker_pids)) == 1 if worker_pids else False

    pass_criteria = {
        "all_cycles_completed": len(samples) == cycles and not errors,
        "zero_live_segments": accounting["segments_live"] == 0,
        "zero_live_bytes": accounting["live_bytes"] == 0,
        "all_segments_finalized": (
            accounting["segments_created"]
            == accounting["segments_consumed"] + accounting["segments_reclaimed_late"]
        ),
        "no_close_failures": accounting["close_failures"] == 0,
        "no_unlink_failures": accounting["unlink_failures"] == 0,
        "parent_handle_slope_bounded": (
            not parent_handle_values or parent_handle_slope <= 0.25
        ),
        "no_orphans_before_shutdown": not orphans_before_shutdown,
        "no_orphans_after_shutdown": not orphans_after_shutdown,
        "worker_shutdown_transfer_reclaimed": (
            not effective_shutdown_transfer
            or accounting["segments_reclaimed_late"] >= 1
        ),
        "worker_rss_tail_slope_bounded": (
            not worker_required or tail_slope <= 2.0
        ),
        "worker_rss_tail_high_water_bounded": (
            not worker_required or tail_high_water_growth <= 64.0
        ),
    }
    if prefetch:
        pass_criteria.update(
            {
                "one_parent_handoff_per_batch": len(parent_handoffs) == cycles,
                "isolated_worker_pid": isolated_worker,
                "one_persistent_worker_pid": one_persistent_worker_pid,
                "worker_scale_timings_recorded": len(worker_scale_durations_ns) == cycles,
            }
        )
    if parent_baseline:
        pass_criteria["parent_qt_scale_format_timings_recorded"] = (
            len(parent_baseline_durations_ns) == cycles
        )

    return {
        "scenario": scenario,
        "cycles_requested": cycles,
        "cycles_completed": len(samples),
        "source_path": str(resolved_source_path),
        "synthetic_source": synthetic_source,
        "source_width": source_width,
        "source_height": source_height,
        "width": width,
        "height": height,
        "resample_filter": effective_filter,
        "sharpen": sharpen,
        "rgba_bytes_per_image": width * height * 4,
        "warmup_cycles": warmup_cycles,
        "worker_type": worker_type.value if worker_required else None,
        "prefetch_derivative_count": len(prefetch_requests),
        "exercise_shutdown_transfer": effective_shutdown_transfer,
        "duration_s": time.monotonic() - started_at,
        "accounting": accounting,
        "parent_handle_samples": len(parent_handle_values),
        "parent_handle_tail_slope_per_cycle": parent_handle_slope,
        "parent_handle_tail_growth": parent_handle_growth,
        "worker_rss_tail_slope_mb_per_cycle": tail_slope,
        "worker_rss_tail_high_water_growth_mb": tail_high_water_growth,
        "worker_rss_min_mb": min(rss_values) if rss_values else None,
        "worker_rss_max_mb": max(rss_values) if rss_values else None,
        "parent_qt_scale_format": _timing_summary(
            parent_baseline_durations_ns,
            warmup_cycles=warmup_cycles,
        ),
        "parent_handoff": _timing_summary(
            parent_handoff_durations_ns,
            warmup_cycles=warmup_cycles,
        ),
        "worker_scale": _timing_summary(
            worker_scale_durations_ns,
            warmup_cycles=warmup_cycles,
        ),
        "worker_pids": sorted(set(worker_pids)),
        "worker_pid_isolated_from_parent": isolated_worker if prefetch else None,
        "one_persistent_worker_pid": one_persistent_worker_pid if prefetch else None,
        "prefetch_handoffs": parent_handoffs,
        "orphan_names_before_shutdown": orphans_before_shutdown,
        "orphan_names_after_shutdown": orphans_after_shutdown,
        "pass_criteria": pass_criteria,
        "passed": all(pass_criteria.values()),
        "errors": errors,
        "samples": samples,
    }


def _default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("logs") / "evidence_chest" / f"image_worker_shm_{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--width", type=int, default=3840)
    parser.add_argument("--height", type=int, default=2160)
    parser.add_argument("--warmup-cycles", type=int, default=10)
    parser.add_argument("--timeout-ms", type=int, default=15_000)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--source",
        type=Path,
        help="read this image without modifying it instead of creating the synthetic source",
    )
    parser.add_argument(
        "--resample-filter",
        choices=sorted(RESAMPLE_FILTERS),
        help=(
            "resolved filter; defaults to smooth for --prefetch/--parent-baseline "
            "and lanczos for the foreground lifecycle lane"
        ),
    )
    parser.add_argument(
        "--sharpen",
        action="store_true",
        help="apply the resolved downscale sharpening in foreground or speculative worker lanes",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--prefetch",
        action="store_true",
        help="exercise one persistent speculative batch worker through production derive",
    )
    mode.add_argument(
        "--parent-baseline",
        action="store_true",
        help="measure the retired parent Qt scale/RGBA-format operation",
    )
    parser.add_argument(
        "--no-shutdown-transfer",
        action="store_true",
        help="skip the final in-flight transfer retirement edge",
    )
    args = parser.parse_args()
    if args.parent_baseline and (
        args.resample_filter not in (None, "smooth") or args.sharpen
    ):
        parser.error(
            "--parent-baseline measures only historical smooth Qt scaling; "
            "use --resample-filter smooth without --sharpen"
        )

    report = run_harness(
        cycles=args.cycles,
        width=args.width,
        height=args.height,
        warmup_cycles=args.warmup_cycles,
        timeout_ms=args.timeout_ms,
        exercise_shutdown_transfer=not args.no_shutdown_transfer,
        prefetch=args.prefetch,
        parent_baseline=args.parent_baseline,
        resample_filter=args.resample_filter,
        sharpen=args.sharpen,
        source_path=args.source,
    )
    output_dir = args.output_dir or _default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "image_worker_shm_lifecycle_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "scenario": report["scenario"],
                "cycles_completed": report["cycles_completed"],
                "parent_qt_scale_format": report["parent_qt_scale_format"],
                "parent_handoff": report["parent_handoff"],
                "worker_scale": report["worker_scale"],
                "worker_pid_isolated_from_parent": report["worker_pid_isolated_from_parent"],
                "accounting": report["accounting"],
                "report": str(report_path.resolve()),
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
