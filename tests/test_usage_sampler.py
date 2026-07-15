from __future__ import annotations

import logging
import time

from core.performance.usage_sampler import (
    GpuUsageSnapshot,
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


def test_usage_service_logs_complete_sample_off_submitted_task(caplog):
    manager = _Manager()
    gpu = _GpuCollector()
    service = UsageTelemetryService(
        manager,
        process_collector=_ProcessCollector(),
        gpu_collector=gpu,
    )

    with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
        assert service.start() is True

    sample = next(record.message for record in caplog.records if "[USAGE] sample " in record.message)
    assert "cpu_app_pct=42.5" in sample
    assert "rss_app_mb=420.0" in sample
    assert "gpu_busy_pct=67.0" in sample
    assert "vram_dedicated_mb=512.0" in sample
    assert "tm_active=1" in sample

    service.stop()
    assert manager.timer.stopped is True
    assert gpu.closed is True


def test_usage_service_never_overlaps_collection_and_reports_skips(caplog):
    manager = _Manager(deferred=True)
    service = UsageTelemetryService(
        manager,
        process_collector=_ProcessCollector(),
        gpu_collector=_GpuCollector(),
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
