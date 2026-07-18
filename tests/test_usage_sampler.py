from __future__ import annotations

import gc
import logging
import threading
import time
from collections import namedtuple
from types import SimpleNamespace

from core.performance.usage_sampler import (
    GpuUsageSnapshot,
    ProcessUsageCollector,
    ProcessUsageSnapshot,
    UsageTelemetryService,
    WindowsGpuUsageCollector,
)


class _Timer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _Manager:
    _shutdown = False

    def __init__(self, *, deferred: bool = False) -> None:
        self.deferred = deferred
        from core.threading.manager import ThreadPoolType

        self.config = {ThreadPoolType.IO: 4, ThreadPoolType.COMPUTE: 3}
        self.timer = _Timer()
        self.callback = None
        self.tasks = []

    def schedule_recurring(self, _interval, callback, *, description):
        assert description == "Whole-process usage telemetry submit"
        self.callback = callback
        return self.timer

    def submit_io_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))
        if not self.deferred:
            func(*args)
        return kwargs["task_id"]

    def run_next(self) -> None:
        func, args, _kwargs = self.tasks.pop(0)
        func(*args)

    def get_active_tasks(self):
        return ["usage_sampler_1", "steam_refresh_2"]

    def get_pool_stats(self):
        return {
            "io": {"submitted": 7, "completed": 6, "failed": 0},
            "compute": {"submitted": 4, "completed": 4, "failed": 0},
        }


class _ProcessCollector:
    def collect(self):
        return ProcessUsageSnapshot(
            pids=(100, 101),
            process_count=2,
            child_count=1,
            cpu_app_pct=42.5,
            cpu_main_pct=32.0,
            cpu_system_pct=51.0,
            rss_app_mb=420.0,
            rss_main_mb=350.0,
            private_app_mb=380.0,
            vms_app_mb=800.0,
            threads_app=17,
            handles_app=640,
            io_read_mb=12.0,
            io_write_mb=3.0,
            cpu_primed=True,
            cpu_hot_threads=(("compute_pool_0", 18.4), ("MainThread", 12.1)),
        )


class _GpuCollector:
    def __init__(self) -> None:
        self.closed = False

    def collect(self, pids):
        assert tuple(pids) == (100, 101)
        return GpuUsageSnapshot(
            supported=True,
            active=True,
            status="ok",
            busy_pct=67.0,
            engine_sum_pct=71.0,
            vram_supported=True,
            vram_dedicated_mb=512.0,
            vram_shared_mb=64.0,
        )

    def close(self) -> None:
        self.closed = True


class _ResourceManager:
    def __init__(self) -> None:
        self.snapshot_calls = 0

    def get_usage_counts(self):
        self.snapshot_calls += 1
        return {
            "total": 24,
            "gl_total": 14,
            "gl_texture": 6,
            "gl_vbo": 2,
            "gl_vao": 2,
            "gl_program": 2,
            "gl_framebuffer": 1,
            "gl_renderbuffer": 1,
            "gl_texture_est_bytes": 32 * 1024 * 1024,
            "gl_pbo_est_bytes": 8 * 1024 * 1024,
        }


class _ImageCache:
    def __init__(self) -> None:
        self.snapshot_calls = 0

    def get_stats(self):
        self.snapshot_calls += 1
        return {
            "item_count": 5,
            "max_items": 24,
            "memory_usage_mb": 128.5,
            "max_memory_mb": 1024.0,
            "hits": 17,
            "misses": 4,
            "evictions": 2,
        }


def test_usage_service_logs_complete_sample_off_submitted_task(caplog):
    manager = _Manager()
    gpu = _GpuCollector()
    resources = _ResourceManager()
    image_cache = _ImageCache()
    service = UsageTelemetryService(
        manager,
        process_collector=_ProcessCollector(),
        gpu_collector=gpu,
        resource_manager=resources,
        image_cache=image_cache,
    )

    with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
        assert service.start() is True

    sample = next(record.message for record in caplog.records if "[USAGE] sample " in record.message)
    assert "cpu_app_pct=42.5" in sample
    assert "cpu_hot_threads=compute_pool_0:18.4|MainThread:12.1" in sample
    assert "rss_app_mb=420.0" in sample
    assert "gpu_busy_pct=67.0" in sample
    assert "vram_dedicated_mb=512.0" in sample
    assert "rm_total=24" in sample
    assert "rm_gl_total=14" in sample
    assert "rm_gl_texture=6" in sample
    assert "rm_gl_framebuffer=1" in sample
    assert "rm_gl_renderbuffer=1" in sample
    assert "rm_gl_texture_est_mb=32.0" in sample
    assert "rm_gl_pbo_est_mb=8.0" in sample
    assert "img_cache_items=5" in sample
    assert "img_cache_max_items=24" in sample
    assert "img_cache_est_mb=128.5" in sample
    assert "img_cache_budget_mb=1024.0" in sample
    assert "img_cache_hits=17" in sample
    assert "img_cache_misses=4" in sample
    assert "img_cache_evictions=2" in sample
    assert "tm_active=1" in sample
    assert resources.snapshot_calls == 1
    assert image_cache.snapshot_calls == 1

    service.stop()
    assert manager.timer.stopped is True
    assert gpu.closed is True


def test_usage_service_never_overlaps_collection_and_reports_skips(caplog):
    manager = _Manager(deferred=True)
    image_cache = _ImageCache()
    service = UsageTelemetryService(
        manager,
        process_collector=_ProcessCollector(),
        gpu_collector=_GpuCollector(),
        image_cache=image_cache,
    )

    with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
        service.start()
        assert len(manager.tasks) == 1
        manager.callback()
        assert len(manager.tasks) == 1
        manager.run_next()
        manager.callback()
        assert len(manager.tasks) == 1
        manager.run_next()

    samples = [record.message for record in caplog.records if "[USAGE] sample " in record.message]
    assert len(samples) == 2
    assert "skipped=1" in samples[1]
    assert image_cache.snapshot_calls == 2


def test_usage_service_does_not_retain_image_cache(caplog):
    manager = _Manager()
    image_cache = _ImageCache()
    service = UsageTelemetryService(
        manager,
        process_collector=_ProcessCollector(),
        gpu_collector=_GpuCollector(),
        image_cache=image_cache,
    )
    del image_cache
    gc.collect()

    with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
        service.start()

    sample = next(record.message for record in caplog.records if "[USAGE] sample " in record.message)
    assert "img_cache_items=na" in sample
    assert "img_cache_est_mb=na" in sample


def test_gpu_collector_negative_cache_does_not_rediscover_every_sample(monkeypatch):
    collector = WindowsGpuUsageCollector(refresh_seconds=300.0)
    collector._pdh = object()
    collector._pids = (100,)
    collector._last_rebuild = time.monotonic()
    collector._query = None
    rebuilds = []
    monkeypatch.setattr(
        collector,
        "_rebuild",
        lambda pids, now: rebuilds.append((pids, now)),
    )

    snapshot = collector.collect((100,))

    assert snapshot.status == "idle_no_counters"
    assert rebuilds == []


def test_process_cpu_deltas_remain_valid_when_collection_changes_threads(monkeypatch):
    cpu_times_type = namedtuple("CpuTimes", "user system idle")
    clock = [100.0]
    system_times = [cpu_times_type(100.0, 50.0, 850.0)]

    class FakeProcess:
        pid = 100

        def __init__(self) -> None:
            self.cpu_total = 10.0
            self.thread_cpu = 4.0

        def children(self, *, recursive):
            assert recursive is True
            return []

        def cpu_times(self):
            return SimpleNamespace(user=self.cpu_total, system=0.0)

        def memory_info(self):
            return SimpleNamespace(rss=100 * 1024**2, vms=200 * 1024**2, private=90 * 1024**2)

        def num_threads(self):
            return 1

        def num_handles(self):
            return 5

        def io_counters(self):
            return SimpleNamespace(read_bytes=0, write_bytes=0)

        def threads(self):
            return [SimpleNamespace(id=777, user_time=self.thread_cpu, system_time=0.0)]

    process = FakeProcess()
    monkeypatch.setattr(
        "core.performance.usage_sampler.time.monotonic",
        lambda: clock[0],
    )
    monkeypatch.setattr(
        "core.performance.usage_sampler.psutil.cpu_times",
        lambda: system_times[0],
    )
    collector = ProcessUsageCollector(process=process)

    first = collector.collect()
    assert first.cpu_primed is False
    assert first.cpu_app_pct is None
    assert first.cpu_system_pct is None

    clock[0] += 10.0
    process.cpu_total += 2.0
    process.thread_cpu += 1.2
    system_times[0] = cpu_times_type(110.0, 55.0, 895.0)
    result = []
    thread = threading.Thread(target=lambda: result.append(collector.collect()))
    thread.start()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    second = result[0]
    assert second.cpu_primed is True
    assert second.cpu_app_pct == 20.0
    assert second.cpu_main_pct == 20.0
    assert second.cpu_system_pct == 25.0
    assert second.cpu_hot_threads[0][0] == "main_tid_777"
    assert round(second.cpu_hot_threads[0][1], 1) == 12.0
