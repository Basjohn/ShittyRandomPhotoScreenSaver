"""Low-pressure whole-process resource telemetry for ``--usage`` runs."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

import psutil

from core.logging.logger import get_logger
from core.threading.manager import TaskPriority, ThreadManager, ThreadPoolType


logger = get_logger(__name__)

DEFAULT_USAGE_INTERVAL_MS = 15_000
_MB = 1024.0 * 1024.0


def _mb(value: int | float) -> float:
    return max(0.0, float(value)) / _MB


def _fmt(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "na"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{decimals}f}"


@dataclass(frozen=True)
class ProcessUsageSnapshot:
    pids: tuple[int, ...]
    process_count: int
    child_count: int
    cpu_app_pct: float
    cpu_main_pct: float
    cpu_system_pct: float
    rss_app_mb: float
    rss_main_mb: float
    private_app_mb: float | None
    vms_app_mb: float
    threads_app: int
    handles_app: int | None
    io_read_mb: float | None
    io_write_mb: float | None
    cpu_primed: bool


@dataclass(frozen=True)
class GpuUsageSnapshot:
    supported: bool
    active: bool
    status: str
    busy_pct: float | None = None
    engine_sum_pct: float | None = None
    vram_supported: bool = False
    vram_dedicated_mb: float | None = None
    vram_shared_mb: float | None = None


class ProcessUsageCollector:
    """Collect main-process and recursive child totals without blocking intervals."""

    def __init__(self, process: psutil.Process | None = None) -> None:
        self._main = process or psutil.Process(os.getpid())
        self._processes: dict[int, psutil.Process] = {self._main.pid: self._main}
        self._sample_count = 0
        self._prime_cpu(self._main)
        psutil.cpu_percent(interval=None)

    @staticmethod
    def _prime_cpu(process: psutil.Process) -> None:
        try:
            process.cpu_percent(interval=None)
        except (psutil.Error, OSError):
            pass

    def _live_processes(self) -> list[psutil.Process]:
        try:
            children = self._main.children(recursive=True)
        except (psutil.Error, OSError):
            children = []

        live: list[psutil.Process] = [self._main]
        live_pids = {self._main.pid}
        for child in children:
            if child.pid in live_pids:
                continue
            cached = self._processes.get(child.pid)
            if cached is None:
                cached = child
                self._processes[child.pid] = cached
                self._prime_cpu(cached)
            live.append(cached)
            live_pids.add(child.pid)

        self._processes = {
            pid: process for pid, process in self._processes.items() if pid in live_pids
        }
        return live

    def collect(self) -> ProcessUsageSnapshot:
        processes = self._live_processes()
        main_cpu = 0.0
        app_cpu = 0.0
        rss_main = 0
        rss_app = 0
        private_app = 0
        private_available = True
        vms_app = 0
        threads_app = 0
        handles_app = 0
        handles_available = True
        io_read = 0
        io_write = 0
        io_available = True
        live_pids: list[int] = []

        for process in processes:
            try:
                cpu = max(0.0, float(process.cpu_percent(interval=None)))
                memory = process.memory_info()
                live_pids.append(process.pid)
            except (psutil.Error, OSError):
                continue

            app_cpu += cpu
            rss = int(getattr(memory, "rss", 0) or 0)
            rss_app += rss
            vms_app += int(getattr(memory, "vms", 0) or 0)
            if process.pid == self._main.pid:
                main_cpu = cpu
                rss_main = rss

            private_value = getattr(memory, "private", None)
            if private_value is None:
                private_available = False
            else:
                private_app += int(private_value)

            try:
                threads_app += int(process.num_threads())
            except (psutil.Error, OSError, AttributeError):
                pass

            try:
                handles_app += int(process.num_handles())
            except (psutil.Error, OSError, AttributeError):
                handles_available = False

            try:
                io = process.io_counters()
                io_read += int(getattr(io, "read_bytes", 0) or 0)
                io_write += int(getattr(io, "write_bytes", 0) or 0)
            except (psutil.Error, OSError, AttributeError):
                io_available = False

        system_cpu = max(0.0, float(psutil.cpu_percent(interval=None)))
        snapshot = ProcessUsageSnapshot(
            pids=tuple(sorted(live_pids)),
            process_count=len(live_pids),
            child_count=max(0, len(live_pids) - 1),
            cpu_app_pct=app_cpu,
            cpu_main_pct=main_cpu,
            cpu_system_pct=system_cpu,
            rss_app_mb=_mb(rss_app),
            rss_main_mb=_mb(rss_main),
            private_app_mb=_mb(private_app) if private_available else None,
            vms_app_mb=_mb(vms_app),
            threads_app=threads_app,
            handles_app=handles_app if handles_available else None,
            io_read_mb=_mb(io_read) if io_available else None,
            io_write_mb=_mb(io_write) if io_available else None,
            cpu_primed=self._sample_count > 0,
        )
        self._sample_count += 1
        return snapshot


class WindowsGpuUsageCollector:
    """Read process-scoped Windows GPU Engine and GPU Process Memory counters."""

    def __init__(self, refresh_seconds: float = 300.0) -> None:
        self._refresh_seconds = max(15.0, float(refresh_seconds))
        self._pdh: Any | None = None
        self._query: Any | None = None
        self._engine_counters: list[Any] = []
        self._dedicated_counters: list[Any] = []
        self._shared_counters: list[Any] = []
        self._pids: tuple[int, ...] = ()
        self._last_rebuild = 0.0
        try:
            import win32pdh

            self._pdh = win32pdh
        except (ImportError, OSError):
            self._pdh = None

    @staticmethod
    def _matches_pid(instance: str, pids: Iterable[int]) -> bool:
        lowered = instance.lower()
        return any(f"pid_{pid}_" in lowered for pid in pids)

    def _close_query(self) -> None:
        if self._pdh is not None and self._query is not None:
            try:
                self._pdh.CloseQuery(self._query)
            except Exception:
                pass
        self._query = None
        self._engine_counters = []
        self._dedicated_counters = []
        self._shared_counters = []

    def close(self) -> None:
        self._close_query()

    def _add_counter(self, object_name: str, instance: str, counter_name: str) -> Any | None:
        if self._pdh is None or self._query is None:
            return None
        try:
            path = self._pdh.MakeCounterPath(
                (None, object_name, instance, None, -1, counter_name)
            )
            return self._pdh.AddCounter(self._query, path)
        except Exception:
            return None

    def _rebuild(self, pids: tuple[int, ...], now: float) -> None:
        self._close_query()
        self._pids = pids
        self._last_rebuild = now
        if self._pdh is None or not pids:
            return

        try:
            self._query = self._pdh.OpenQuery()
            _counters, engine_instances = self._pdh.EnumObjectItems(
                None,
                None,
                "GPU Engine",
                self._pdh.PERF_DETAIL_WIZARD,
            )
            for instance in dict.fromkeys(engine_instances):
                if not self._matches_pid(instance, pids):
                    continue
                counter = self._add_counter(
                    "GPU Engine", instance, "Utilization Percentage"
                )
                if counter is not None:
                    self._engine_counters.append(counter)

            _counters, memory_instances = self._pdh.EnumObjectItems(
                None,
                None,
                "GPU Process Memory",
                self._pdh.PERF_DETAIL_WIZARD,
            )
            for instance in dict.fromkeys(memory_instances):
                if not self._matches_pid(instance, pids):
                    continue
                dedicated = self._add_counter(
                    "GPU Process Memory", instance, "Dedicated Usage"
                )
                shared = self._add_counter(
                    "GPU Process Memory", instance, "Shared Usage"
                )
                if dedicated is not None:
                    self._dedicated_counters.append(dedicated)
                if shared is not None:
                    self._shared_counters.append(shared)

            if not (
                self._engine_counters
                or self._dedicated_counters
                or self._shared_counters
            ):
                self._close_query()
                return
            self._pdh.CollectQueryData(self._query)
        except Exception:
            self._close_query()

    def _values(self, counters: Iterable[Any], fmt: int) -> list[float]:
        if self._pdh is None:
            return []
        values: list[float] = []
        for counter in counters:
            try:
                _counter_type, value = self._pdh.GetFormattedCounterValue(counter, fmt)
                values.append(max(0.0, float(value)))
            except Exception:
                continue
        return values

    def collect(self, pids: Iterable[int]) -> GpuUsageSnapshot:
        normalized_pids = tuple(sorted({int(pid) for pid in pids if int(pid) > 0}))
        if self._pdh is None:
            return GpuUsageSnapshot(False, False, "unsupported")

        now = time.monotonic()
        if (
            normalized_pids != self._pids
            or self._last_rebuild <= 0.0
            or now - self._last_rebuild >= self._refresh_seconds
        ):
            self._rebuild(normalized_pids, now)
            if self._query is None:
                return GpuUsageSnapshot(True, False, "idle_no_counters", vram_supported=True)
            return GpuUsageSnapshot(
                True,
                True,
                "warming",
                vram_supported=bool(self._dedicated_counters or self._shared_counters),
            )

        if self._query is None:
            return GpuUsageSnapshot(True, False, "idle_no_counters", vram_supported=True)

        try:
            self._pdh.CollectQueryData(self._query)
            engine_values = self._values(
                self._engine_counters, self._pdh.PDH_FMT_DOUBLE
            )
            dedicated_values = self._values(
                self._dedicated_counters, self._pdh.PDH_FMT_LARGE
            )
            shared_values = self._values(
                self._shared_counters, self._pdh.PDH_FMT_LARGE
            )
            return GpuUsageSnapshot(
                supported=True,
                active=bool(engine_values or dedicated_values or shared_values),
                status="ok",
                busy_pct=max(engine_values) if engine_values else None,
                engine_sum_pct=sum(engine_values) if engine_values else None,
                vram_supported=bool(self._dedicated_counters or self._shared_counters),
                vram_dedicated_mb=(
                    _mb(sum(dedicated_values)) if dedicated_values else None
                ),
                vram_shared_mb=_mb(sum(shared_values)) if shared_values else None,
            )
        except Exception:
            self._close_query()
            return GpuUsageSnapshot(True, False, "query_error", vram_supported=True)


class UsageTelemetryService:
    """Schedule passive resource samples without doing work on the UI thread."""

    def __init__(
        self,
        thread_manager: ThreadManager,
        *,
        interval_ms: int = DEFAULT_USAGE_INTERVAL_MS,
        process_collector: ProcessUsageCollector | None = None,
        gpu_collector: WindowsGpuUsageCollector | None = None,
        resource_snapshot_provider: Callable[[], Mapping[str, Any] | Any] | None = None,
    ) -> None:
        self._thread_manager = thread_manager
        self._interval_ms = max(5_000, int(interval_ms))
        self._process_collector = process_collector or ProcessUsageCollector()
        self._gpu_collector = gpu_collector or WindowsGpuUsageCollector()
        self._resource_snapshot_provider = resource_snapshot_provider
        self._timer: Any | None = None
        self._stopped = True
        self._in_flight = False
        self._last_request_at: float | None = None
        self._skipped_samples = 0
        self._sequence = 0

    def start(self) -> bool:
        if not self._stopped:
            return True
        if getattr(self._thread_manager, "_shutdown", False):
            return False
        self._stopped = False
        self._timer = self._thread_manager.schedule_recurring(
            self._interval_ms,
            self._request_sample,
            description="Whole-process usage telemetry submit",
        )
        logger.info(
            "[USAGE] session_start interval_ms=%d ui_collection=0 auto_quality_changes=0",
            self._interval_ms,
        )
        self._request_sample()
        return True

    def stop(self) -> None:
        self._stopped = True
        timer = self._timer
        self._timer = None
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        if not self._in_flight:
            self._gpu_collector.close()
        logger.info("[USAGE] session_stop sequence=%d", self._sequence)

    def _request_sample(self) -> None:
        if self._stopped or getattr(self._thread_manager, "_shutdown", False):
            return

        now = time.monotonic()
        cadence_gap_ms = (
            0.0
            if self._last_request_at is None
            else max(0.0, (now - self._last_request_at) * 1000.0)
        )
        self._last_request_at = now
        if self._in_flight:
            self._skipped_samples += 1
            return

        self._in_flight = True
        self._sequence += 1
        sequence = self._sequence
        skipped = self._skipped_samples
        self._skipped_samples = 0
        try:
            self._thread_manager.submit_io_task(
                self._collect_and_log,
                sequence,
                cadence_gap_ms,
                skipped,
                task_id=f"usage_sampler_{sequence}",
                priority=TaskPriority.LOW,
                category="diagnostics.usage",
            )
        except Exception:
            self._in_flight = False
            if not self._stopped:
                logger.warning("[USAGE] sample_submit_failed sequence=%d", sequence, exc_info=True)

    def _thread_snapshot(self) -> dict[str, Any]:
        active_ids = self._thread_manager.get_active_tasks()
        non_usage_active = sum(
            1 for task_id in active_ids if not task_id.startswith("usage_sampler_")
        )
        stats = self._thread_manager.get_pool_stats()
        io_stats = stats.get("io", {})
        compute_stats = stats.get("compute", {})
        config = self._thread_manager.config
        category_getter = getattr(self._thread_manager, "get_task_category_stats", None)
        categories = category_getter() if callable(category_getter) else {}
        return {
            "tm_active": non_usage_active,
            "tm_io_max": int(config.get(ThreadPoolType.IO, 0) or 0),
            "tm_compute_max": int(config.get(ThreadPoolType.COMPUTE, 0) or 0),
            "tm_io_submitted": int(io_stats.get("submitted", 0) or 0),
            "tm_io_completed": int(io_stats.get("completed", 0) or 0),
            "tm_io_failed": int(io_stats.get("failed", 0) or 0),
            "tm_compute_submitted": int(compute_stats.get("submitted", 0) or 0),
            "tm_compute_completed": int(compute_stats.get("completed", 0) or 0),
            "tm_compute_failed": int(compute_stats.get("failed", 0) or 0),
            "tm_categories": json.dumps(
                categories,
                separators=(",", ":"),
                sort_keys=True,
            ),
        }

    def _resource_snapshot(self) -> dict[str, Any]:
        """Read one immutable owner-maintained accounting snapshot."""
        provider = self._resource_snapshot_provider
        if provider is None:
            return {}
        try:
            snapshot = provider()
            aggregate = getattr(snapshot, "aggregate_fields", None)
            if callable(aggregate):
                snapshot = aggregate()
            return dict(snapshot) if isinstance(snapshot, Mapping) else {}
        except Exception:
            logger.debug("[USAGE] Resource accounting snapshot failed", exc_info=True)
            return {}

    def _collect_and_log(
        self,
        sequence: int,
        cadence_gap_ms: float,
        skipped: int,
    ) -> None:
        started = time.perf_counter()
        try:
            process = self._process_collector.collect()
            gpu = self._gpu_collector.collect(process.pids)
            threads = self._thread_snapshot()
            resources = self._resource_snapshot()
            collect_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "[USAGE] sample seq=%d cadence_gap_ms=%s skipped=%d collect_ms=%s "
                "cpu_primed=%d cpu_app_pct=%s cpu_main_pct=%s cpu_system_pct=%s "
                "processes=%d children=%d rss_app_mb=%s rss_main_mb=%s "
                "private_app_mb=%s vms_app_mb=%s threads_app=%d handles_app=%s "
                "io_read_mb=%s io_write_mb=%s gpu_supported=%d gpu_active=%d "
                "gpu_status=%s gpu_busy_pct=%s gpu_engine_sum_pct=%s "
                "vram_supported=%d vram_dedicated_mb=%s vram_shared_mb=%s "
                "tracked_resources=%s tracked_known_bytes=%s "
                "cpu_cache_resources=%s cpu_cache_bytes=%s "
                "cpu_display_resources=%s cpu_display_bytes=%s "
                "rm_resources=%s rm_known_bytes=%s rm_unknown_resources=%s "
                "gl_resources=%s gl_known_bytes=%s gl_unknown_resources=%s "
                "gl_texture_resources=%s gl_texture_bytes=%s "
                "gl_framebuffer_resources=%s gl_framebuffer_bytes=%s "
                "gl_renderbuffer_resources=%s gl_renderbuffer_bytes=%s "
                "gl_pbo_resources=%s gl_pbo_bytes=%s qt_default_fbo=%s "
                "tm_active=%d tm_io_max=%d tm_compute_max=%d "
                "tm_io_submitted=%d tm_io_completed=%d tm_io_failed=%d "
                "tm_compute_submitted=%d tm_compute_completed=%d tm_compute_failed=%d "
                "tm_categories=%s",
                sequence,
                _fmt(cadence_gap_ms),
                skipped,
                _fmt(collect_ms, 2),
                int(process.cpu_primed),
                _fmt(process.cpu_app_pct),
                _fmt(process.cpu_main_pct),
                _fmt(process.cpu_system_pct),
                process.process_count,
                process.child_count,
                _fmt(process.rss_app_mb),
                _fmt(process.rss_main_mb),
                _fmt(process.private_app_mb),
                _fmt(process.vms_app_mb),
                process.threads_app,
                _fmt(process.handles_app),
                _fmt(process.io_read_mb),
                _fmt(process.io_write_mb),
                int(gpu.supported),
                int(gpu.active),
                gpu.status,
                _fmt(gpu.busy_pct),
                _fmt(gpu.engine_sum_pct),
                int(gpu.vram_supported),
                _fmt(gpu.vram_dedicated_mb),
                _fmt(gpu.vram_shared_mb),
                _fmt(resources.get("tracked_resources")),
                _fmt(resources.get("tracked_known_bytes")),
                _fmt(resources.get("cpu_cache_resources")),
                _fmt(resources.get("cpu_cache_bytes")),
                _fmt(resources.get("cpu_display_resources")),
                _fmt(resources.get("cpu_display_bytes")),
                _fmt(resources.get("rm_resources")),
                _fmt(resources.get("rm_known_bytes")),
                _fmt(resources.get("rm_unknown_resources")),
                _fmt(resources.get("gl_resources")),
                _fmt(resources.get("gl_known_bytes")),
                _fmt(resources.get("gl_unknown_resources")),
                _fmt(resources.get("gl_texture_resources")),
                _fmt(resources.get("gl_texture_bytes")),
                _fmt(resources.get("gl_framebuffer_resources")),
                _fmt(resources.get("gl_framebuffer_bytes")),
                _fmt(resources.get("gl_renderbuffer_resources")),
                _fmt(resources.get("gl_renderbuffer_bytes")),
                _fmt(resources.get("gl_pbo_resources")),
                _fmt(resources.get("gl_pbo_bytes")),
                resources.get("qt_default_fbo", "na"),
                threads["tm_active"],
                threads["tm_io_max"],
                threads["tm_compute_max"],
                threads["tm_io_submitted"],
                threads["tm_io_completed"],
                threads["tm_io_failed"],
                threads["tm_compute_submitted"],
                threads["tm_compute_completed"],
                threads["tm_compute_failed"],
                threads["tm_categories"],
            )
        except Exception:
            collect_ms = (time.perf_counter() - started) * 1000.0
            logger.warning(
                "[USAGE] sample_failed seq=%d collect_ms=%.2f",
                sequence,
                collect_ms,
                exc_info=True,
            )
        finally:
            self._in_flight = False
            if self._stopped:
                self._gpu_collector.close()
