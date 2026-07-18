"""Low-pressure whole-process resource telemetry for ``--usage`` runs."""
from __future__ import annotations

import os
import re
import threading
import time
import weakref
from dataclasses import dataclass
from typing import Any, Iterable

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


def _fmt_hot_threads(values: tuple[tuple[str, float], ...]) -> str:
    if not values:
        return "na"
    return "|".join(f"{name}:{cpu_pct:.1f}" for name, cpu_pct in values)


@dataclass(frozen=True)
class ProcessUsageSnapshot:
    pids: tuple[int, ...]
    process_count: int
    child_count: int
    cpu_app_pct: float | None
    cpu_main_pct: float | None
    cpu_system_pct: float | None
    rss_app_mb: float
    rss_main_mb: float
    private_app_mb: float | None
    vms_app_mb: float
    threads_app: int
    handles_app: int | None
    io_read_mb: float | None
    io_write_mb: float | None
    cpu_primed: bool
    cpu_hot_threads: tuple[tuple[str, float], ...] = ()


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
        self._last_sample_at: float | None = None
        self._process_cpu_totals: dict[int, float] = {}
        self._thread_cpu_totals: dict[tuple[int, int], float] = {}
        self._system_cpu_total: float | None = None
        self._system_cpu_busy: float | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _process_cpu_total(process: psutil.Process) -> float | None:
        try:
            times = process.cpu_times()
            return max(
                0.0,
                float(getattr(times, "user", 0.0) or 0.0)
                + float(getattr(times, "system", 0.0) or 0.0),
            )
        except (psutil.Error, OSError, AttributeError):
            return None

    @staticmethod
    def _system_cpu_totals() -> tuple[float | None, float | None]:
        try:
            times = psutil.cpu_times()
            values = times._asdict() if hasattr(times, "_asdict") else {}
            if not values:
                return None, None
            total = sum(
                max(0.0, float(value or 0.0))
                for name, value in values.items()
                if name not in {"guest", "guest_nice"}
            )
            idle = max(0.0, float(values.get("idle", 0.0) or 0.0))
            idle += max(0.0, float(values.get("iowait", 0.0) or 0.0))
            return total, max(0.0, total - idle)
        except (psutil.Error, OSError, AttributeError, TypeError, ValueError):
            return None, None

    @staticmethod
    def _safe_thread_name(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "thread"))
        return normalized.strip("_")[:48] or "thread"

    def _thread_cpu_snapshot(
        self,
        processes: list[psutil.Process],
        *,
        elapsed: float | None,
    ) -> tuple[tuple[tuple[str, float], ...], dict[tuple[int, int], float]]:
        current: dict[tuple[int, int], float] = {}
        samples: list[tuple[str, float]] = []
        main_names: dict[int, str] = {}
        try:
            main_names = {
                int(thread.native_id): self._safe_thread_name(thread.name)
                for thread in threading.enumerate()
                if getattr(thread, "native_id", None) is not None
            }
        except Exception:
            main_names = {}

        for process in processes:
            try:
                thread_rows = process.threads()
            except (psutil.Error, OSError, AttributeError):
                continue
            for row in thread_rows:
                try:
                    tid = int(row.id)
                    total = max(
                        0.0,
                        float(getattr(row, "user_time", 0.0) or 0.0)
                        + float(getattr(row, "system_time", 0.0) or 0.0),
                    )
                except (AttributeError, TypeError, ValueError):
                    continue
                key = (int(process.pid), tid)
                current[key] = total
                previous = self._thread_cpu_totals.get(key)
                if previous is None or elapsed is None or elapsed <= 0.0:
                    continue
                cpu_pct = max(0.0, (total - previous) / elapsed * 100.0)
                if cpu_pct < 0.1:
                    continue
                if process.pid == self._main.pid:
                    name = main_names.get(tid, f"main_tid_{tid}")
                else:
                    name = f"child_{process.pid}_tid_{tid}"
                samples.append((name, cpu_pct))

        samples.sort(key=lambda item: item[1], reverse=True)
        return tuple(samples[:4]), current

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
            live.append(cached)
            live_pids.add(child.pid)

        self._processes = {
            pid: process for pid, process in self._processes.items() if pid in live_pids
        }
        return live

    def collect(self) -> ProcessUsageSnapshot:
        with self._lock:
            return self._collect_locked()

    def _collect_locked(self) -> ProcessUsageSnapshot:
        sample_at = time.monotonic()
        elapsed = (
            None
            if self._last_sample_at is None
            else max(0.0, sample_at - self._last_sample_at)
        )
        processes = self._live_processes()
        main_cpu: float | None = None
        app_cpu: float | None = None
        current_process_cpu: dict[int, float] = {}
        process_cpu_deltas: dict[int, float] = {}
        all_process_cpu_primed = elapsed is not None and elapsed > 0.0
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
                memory = process.memory_info()
                live_pids.append(process.pid)
            except (psutil.Error, OSError):
                continue

            cpu_total = self._process_cpu_total(process)
            if cpu_total is None:
                all_process_cpu_primed = False
            else:
                current_process_cpu[process.pid] = cpu_total
                previous_cpu = self._process_cpu_totals.get(process.pid)
                if previous_cpu is None or elapsed is None or elapsed <= 0.0:
                    all_process_cpu_primed = False
                else:
                    process_cpu_deltas[process.pid] = max(0.0, cpu_total - previous_cpu)

            rss = int(getattr(memory, "rss", 0) or 0)
            rss_app += rss
            vms_app += int(getattr(memory, "vms", 0) or 0)
            if process.pid == self._main.pid:
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

        system_total, system_busy = self._system_cpu_totals()
        system_cpu: float | None = None
        system_primed = (
            self._system_cpu_total is not None
            and self._system_cpu_busy is not None
            and system_total is not None
            and system_busy is not None
        )
        if system_primed:
            total_delta = max(0.0, system_total - self._system_cpu_total)
            busy_delta = max(0.0, system_busy - self._system_cpu_busy)
            if total_delta > 0.0:
                system_cpu = min(100.0, busy_delta / total_delta * 100.0)
            else:
                system_primed = False

        cpu_primed = bool(all_process_cpu_primed and system_primed)
        if cpu_primed and elapsed is not None and elapsed > 0.0:
            app_cpu = sum(process_cpu_deltas.values()) / elapsed * 100.0
            main_delta = process_cpu_deltas.get(self._main.pid)
            if main_delta is not None:
                main_cpu = main_delta / elapsed * 100.0

        hot_threads, current_thread_cpu = self._thread_cpu_snapshot(
            processes,
            elapsed=elapsed,
        )
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
            cpu_primed=cpu_primed,
            cpu_hot_threads=hot_threads,
        )
        self._last_sample_at = sample_at
        self._process_cpu_totals = current_process_cpu
        self._thread_cpu_totals = current_thread_cpu
        self._system_cpu_total = system_total
        self._system_cpu_busy = system_busy
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
        resource_manager: Any | None = None,
        image_cache: Any | None = None,
    ) -> None:
        self._thread_manager = thread_manager
        self._interval_ms = max(5_000, int(interval_ms))
        self._process_collector = process_collector or ProcessUsageCollector()
        self._gpu_collector = gpu_collector or WindowsGpuUsageCollector()
        self._resource_manager = resource_manager
        self._image_cache_ref = (
            weakref.ref(image_cache) if image_cache is not None else None
        )
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
            )
        except Exception:
            self._in_flight = False
            if not self._stopped:
                logger.warning("[USAGE] sample_submit_failed sequence=%d", sequence, exc_info=True)

    def _thread_snapshot(self) -> dict[str, int]:
        active_ids = self._thread_manager.get_active_tasks()
        non_usage_active = sum(
            1 for task_id in active_ids if not task_id.startswith("usage_sampler_")
        )
        stats = self._thread_manager.get_pool_stats()
        io_stats = stats.get("io", {})
        compute_stats = stats.get("compute", {})
        config = self._thread_manager.config
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
        }

    def _resource_snapshot(self) -> dict[str, int | None]:
        manager = self._resource_manager
        if manager is None:
            return {
                "rm_total": None,
                "rm_gl_total": None,
                "rm_gl_texture": None,
                "rm_gl_vbo": None,
                "rm_gl_vao": None,
                "rm_gl_program": None,
                "rm_gl_framebuffer": None,
                "rm_gl_renderbuffer": None,
                "rm_gl_texture_est_bytes": None,
                "rm_gl_pbo_est_bytes": None,
            }
        try:
            get_usage_counts = getattr(manager, "get_usage_counts", None)
            if callable(get_usage_counts):
                counts = get_usage_counts()
                return {
                    "rm_total": int(counts.get("total", 0) or 0),
                    "rm_gl_total": int(counts.get("gl_total", 0) or 0),
                    "rm_gl_texture": int(counts.get("gl_texture", 0) or 0),
                    "rm_gl_vbo": int(counts.get("gl_vbo", 0) or 0),
                    "rm_gl_vao": int(counts.get("gl_vao", 0) or 0),
                    "rm_gl_program": int(counts.get("gl_program", 0) or 0),
                    "rm_gl_framebuffer": int(counts.get("gl_framebuffer", 0) or 0),
                    "rm_gl_renderbuffer": int(counts.get("gl_renderbuffer", 0) or 0),
                    "rm_gl_texture_est_bytes": int(
                        counts.get("gl_texture_est_bytes", 0) or 0
                    ),
                    "rm_gl_pbo_est_bytes": int(
                        counts.get("gl_pbo_est_bytes", 0) or 0
                    ),
                }
            gl_stats = manager.get_gl_stats()
            return {
                "rm_total": len(manager.get_all_resources()),
                "rm_gl_total": int(gl_stats.get("total", 0) or 0),
                "rm_gl_texture": int(gl_stats.get("texture", 0) or 0),
                "rm_gl_vbo": int(gl_stats.get("vbo", 0) or 0),
                "rm_gl_vao": int(gl_stats.get("vao", 0) or 0),
                "rm_gl_program": int(gl_stats.get("program", 0) or 0),
                "rm_gl_framebuffer": int(gl_stats.get("framebuffer", 0) or 0),
                "rm_gl_renderbuffer": int(gl_stats.get("renderbuffer", 0) or 0),
                "rm_gl_texture_est_bytes": None,
                "rm_gl_pbo_est_bytes": None,
            }
        except Exception:
            return {
                "rm_total": None,
                "rm_gl_total": None,
                "rm_gl_texture": None,
                "rm_gl_vbo": None,
                "rm_gl_vao": None,
                "rm_gl_program": None,
                "rm_gl_framebuffer": None,
                "rm_gl_renderbuffer": None,
                "rm_gl_texture_est_bytes": None,
                "rm_gl_pbo_est_bytes": None,
            }

    def _image_cache_snapshot(self) -> dict[str, int | float | None]:
        empty = {
            "img_cache_items": None,
            "img_cache_max_items": None,
            "img_cache_est_mb": None,
            "img_cache_budget_mb": None,
            "img_cache_hits": None,
            "img_cache_misses": None,
            "img_cache_evictions": None,
        }
        cache_ref = self._image_cache_ref
        cache = cache_ref() if cache_ref is not None else None
        if cache is None:
            return empty
        try:
            stats = cache.get_stats()
            return {
                "img_cache_items": int(stats.get("item_count", 0) or 0),
                "img_cache_max_items": int(stats.get("max_items", 0) or 0),
                "img_cache_est_mb": max(
                    0.0,
                    float(stats.get("memory_usage_mb", 0.0) or 0.0),
                ),
                "img_cache_budget_mb": max(
                    0.0,
                    float(stats.get("max_memory_mb", 0.0) or 0.0),
                ),
                "img_cache_hits": int(stats.get("hits", 0) or 0),
                "img_cache_misses": int(stats.get("misses", 0) or 0),
                "img_cache_evictions": int(stats.get("evictions", 0) or 0),
            }
        except Exception:
            return empty

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
            image_cache = self._image_cache_snapshot()
            collect_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "[USAGE] sample seq=%d cadence_gap_ms=%s skipped=%d collect_ms=%s "
                "cpu_primed=%d cpu_app_pct=%s cpu_main_pct=%s cpu_system_pct=%s "
                "cpu_hot_threads=%s "
                "processes=%d children=%d rss_app_mb=%s rss_main_mb=%s "
                "private_app_mb=%s vms_app_mb=%s threads_app=%d handles_app=%s "
                "io_read_mb=%s io_write_mb=%s gpu_supported=%d gpu_active=%d "
                "gpu_status=%s gpu_busy_pct=%s gpu_engine_sum_pct=%s "
                "vram_supported=%d vram_dedicated_mb=%s vram_shared_mb=%s "
                "rm_total=%s rm_gl_total=%s rm_gl_texture=%s rm_gl_vbo=%s "
                "rm_gl_vao=%s rm_gl_program=%s rm_gl_framebuffer=%s "
                "rm_gl_renderbuffer=%s rm_gl_texture_est_mb=%s "
                "rm_gl_pbo_est_mb=%s img_cache_items=%s "
                "img_cache_max_items=%s img_cache_est_mb=%s "
                "img_cache_budget_mb=%s img_cache_hits=%s "
                "img_cache_misses=%s img_cache_evictions=%s "
                "tm_active=%d tm_io_max=%d tm_compute_max=%d "
                "tm_io_submitted=%d tm_io_completed=%d tm_io_failed=%d "
                "tm_compute_submitted=%d tm_compute_completed=%d tm_compute_failed=%d",
                sequence,
                _fmt(cadence_gap_ms),
                skipped,
                _fmt(collect_ms, 2),
                int(process.cpu_primed),
                _fmt(process.cpu_app_pct),
                _fmt(process.cpu_main_pct),
                _fmt(process.cpu_system_pct),
                _fmt_hot_threads(process.cpu_hot_threads),
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
                _fmt(resources["rm_total"]),
                _fmt(resources["rm_gl_total"]),
                _fmt(resources["rm_gl_texture"]),
                _fmt(resources["rm_gl_vbo"]),
                _fmt(resources["rm_gl_vao"]),
                _fmt(resources["rm_gl_program"]),
                _fmt(resources["rm_gl_framebuffer"]),
                _fmt(resources["rm_gl_renderbuffer"]),
                _fmt(
                    _mb(resources["rm_gl_texture_est_bytes"])
                    if resources["rm_gl_texture_est_bytes"] is not None
                    else None
                ),
                _fmt(
                    _mb(resources["rm_gl_pbo_est_bytes"])
                    if resources["rm_gl_pbo_est_bytes"] is not None
                    else None
                ),
                _fmt(image_cache["img_cache_items"]),
                _fmt(image_cache["img_cache_max_items"]),
                _fmt(image_cache["img_cache_est_mb"]),
                _fmt(image_cache["img_cache_budget_mb"]),
                _fmt(image_cache["img_cache_hits"]),
                _fmt(image_cache["img_cache_misses"]),
                _fmt(image_cache["img_cache_evictions"]),
                threads["tm_active"],
                threads["tm_io_max"],
                threads["tm_compute_max"],
                threads["tm_io_submitted"],
                threads["tm_io_completed"],
                threads["tm_io_failed"],
                threads["tm_compute_submitted"],
                threads["tm_compute_completed"],
                threads["tm_compute_failed"],
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
