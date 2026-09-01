"""Current ImageWorker shared-memory lifecycle/plateau harness.

The default scenario performs 50 sequential 4K prescales through the real
spawned ImageWorker and the production parent QImage consumption path, then
checks shared-memory disposal and optional shutdown while a transfer is in flight.
It is a current R-52 regression harness, not Phase-4 migration authority. Each run
writes a plain evidence subfolder; no archive is created.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from datetime import datetime
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import psutil
from PIL import Image

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.process.workers.image_worker import image_worker_main
from engine.image_pipeline import load_image_via_worker


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
    denominator = sum(
        (index - x_mean) ** 2
        for index in range(len(values))
    )
    return numerator / denominator if denominator else 0.0


def _worker_memory(supervisor: ProcessSupervisor) -> dict[str, float | int | None]:
    snapshot = supervisor.get_image_worker_usage_snapshot()
    pid = snapshot.get("image_worker_pid")
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
        "rss_mb": snapshot.get("image_worker_rss_mb"),
        "vms_mb": snapshot.get("image_worker_vms_mb"),
        "private_mb": private_mb,
    }


def _mapping_exists(name: str) -> bool:
    try:
        mapping = SharedMemory(name=name, create=False)
    except FileNotFoundError:
        return False
    else:
        mapping.close()
        return True


def run_harness(
    *,
    cycles: int = 50,
    width: int = 3840,
    height: int = 2160,
    warmup_cycles: int = 10,
    timeout_ms: int = 15_000,
    exercise_shutdown_transfer: bool = True,
) -> dict[str, Any]:
    cycles = max(1, int(cycles))
    width = max(1, int(width))
    height = max(1, int(height))
    warmup_cycles = min(max(0, int(warmup_cycles)), max(0, cycles - 1))

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.IMAGE, image_worker_main)
    errors: list[str] = []
    shared_memory_names: list[str] = []
    samples: list[dict[str, Any]] = []
    orphans_before_shutdown: list[str] = []
    started_at = time.time()

    with tempfile.TemporaryDirectory(prefix="srpss_image_worker_shm_") as temp_dir:
        source_path = Path(temp_dir) / "synthetic_4k.png"
        # A deterministic pattern avoids file/network variability while still
        # forcing the full RGBA output allocation in the worker.
        image = Image.new("RGB", (width, height), (31, 97, 173))
        image.save(source_path, "PNG")
        image.close()

        if not supervisor.start(WorkerType.IMAGE):
            raise RuntimeError("ImageWorker failed to start")

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
            name = response.payload.get("shared_memory_name")
            if name:
                shared_memory_names.append(str(name))
            return consume(response, consumer)

        def _recording_dispose(response, *, reason):
            name = response.payload.get("shared_memory_name")
            if name:
                shared_memory_names.append(str(name))
            return dispose(response, reason=reason)

        supervisor.consume_shared_memory_response = _recording_consume
        supervisor.dispose_response = _recording_dispose

        try:
            for cycle in range(1, cycles + 1):
                qimage = load_image_via_worker(
                    engine,
                    str(source_path),
                    width,
                    height,
                    display_mode="fill",
                    sharpen=False,
                    timeout_ms=timeout_ms,
                )
                if qimage is None:
                    errors.append(f"cycle {cycle}: ImageWorker returned no QImage")
                    break
                if qimage.width() != width or qimage.height() != height:
                    errors.append(
                        f"cycle {cycle}: unexpected size "
                        f"{qimage.width()}x{qimage.height()}"
                    )
                pixel = qimage.pixelColor(width // 2, height // 2)
                if (pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()) != (
                    31,
                    97,
                    173,
                    255,
                ):
                    errors.append(f"cycle {cycle}: copied pixel data changed")
                del qimage

                accounting = supervisor.get_shared_memory_accounting_snapshot()
                memory = _worker_memory(supervisor)
                samples.append(
                    {
                        "cycle": cycle,
                        **memory,
                        **accounting,
                    }
                )
                if accounting["segments_live"] != 0:
                    errors.append(
                        f"cycle {cycle}: {accounting['segments_live']} live segments"
                    )
                if accounting["live_bytes"] != 0:
                    errors.append(
                        f"cycle {cycle}: {accounting['live_bytes']} live bytes"
                    )

            # This no-payload request proves the worker has left the final
            # attachment wait before orphan probing.
            barrier = supervisor.send_request_and_await_response(
                WorkerType.IMAGE,
                MessageType.CONFIG_UPDATE,
                payload={},
                timeout_ms=timeout_ms,
            )
            if barrier is None or not barrier.success:
                errors.append("post-transfer worker barrier failed")

            if exercise_shutdown_transfer:
                correlation_id = supervisor.send_message(
                    WorkerType.IMAGE,
                    MessageType.IMAGE_PRESCALE,
                    payload={
                        "path": str(source_path),
                        "target_width": width,
                        "target_height": height,
                        "mode": "fill",
                        "use_lanczos": True,
                        "sharpen": False,
                    },
                )
                if correlation_id is None:
                    errors.append("worker-shutdown transfer was not submitted")
                elif not supervisor.stop(
                    WorkerType.IMAGE,
                    timeout=max(1.0, timeout_ms / 1000.0),
                ):
                    errors.append("worker shutdown during transfer failed")

            orphans_before_shutdown = [
                name for name in shared_memory_names if _mapping_exists(name)
            ]
        finally:
            supervisor.shutdown()

    orphans_after_shutdown = [
        name for name in shared_memory_names if _mapping_exists(name)
    ]
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
        max(end_window) - max(head_window)
        if head_window and end_window
        else 0.0
    )

    accounting = supervisor.get_shared_memory_accounting_snapshot()
    pass_criteria = {
        "all_cycles_completed": len(samples) == cycles and not errors,
        "zero_live_segments": accounting["segments_live"] == 0,
        "zero_live_bytes": accounting["live_bytes"] == 0,
        "all_segments_finalized": (
            accounting["segments_created"]
            == accounting["segments_consumed"]
            + accounting["segments_reclaimed_late"]
        ),
        "no_unlink_failures": accounting["unlink_failures"] == 0,
        "no_orphans_before_shutdown": not orphans_before_shutdown,
        "no_orphans_after_shutdown": not orphans_after_shutdown,
        "worker_shutdown_transfer_reclaimed": (
            not exercise_shutdown_transfer
            or accounting["segments_reclaimed_late"] >= 1
        ),
        # The broken path grew about 31.6 MiB per image.  These bounds allow
        # ordinary allocator noise while rejecting that staircase decisively.
        "worker_rss_tail_slope_bounded": tail_slope <= 2.0,
        "worker_rss_tail_high_water_bounded": tail_high_water_growth <= 64.0,
    }
    return {
        "scenario": "image_worker_shared_memory_lifecycle",
        "cycles_requested": cycles,
        "cycles_completed": len(samples),
        "width": width,
        "height": height,
        "rgba_bytes_per_image": width * height * 4,
        "warmup_cycles": warmup_cycles,
        "exercise_shutdown_transfer": exercise_shutdown_transfer,
        "duration_s": time.time() - started_at,
        "accounting": accounting,
        "worker_rss_tail_slope_mb_per_cycle": tail_slope,
        "worker_rss_tail_high_water_growth_mb": tail_high_water_growth,
        "worker_rss_min_mb": min(rss_values) if rss_values else None,
        "worker_rss_max_mb": max(rss_values) if rss_values else None,
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
    args = parser.parse_args()

    report = run_harness(
        cycles=args.cycles,
        width=args.width,
        height=args.height,
        warmup_cycles=args.warmup_cycles,
        timeout_ms=args.timeout_ms,
    )
    output_dir = args.output_dir or _default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "image_worker_shm_lifecycle_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({
        "passed": report["passed"],
        "cycles_completed": report["cycles_completed"],
        "worker_rss_tail_slope_mb_per_cycle": (
            report["worker_rss_tail_slope_mb_per_cycle"]
        ),
        "worker_rss_tail_high_water_growth_mb": (
            report["worker_rss_tail_high_water_growth_mb"]
        ),
        "accounting": report["accounting"],
        "report": str(report_path.resolve()),
    }, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
