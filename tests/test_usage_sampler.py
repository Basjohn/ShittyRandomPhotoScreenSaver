from __future__ import annotations

import logging
import time
from types import SimpleNamespace

from core.performance.usage_sampler import (
    GpuUsageSnapshot,
    ProcessUsageCollector,
    ProcessUsageSnapshot,
    UsageTelemetryService,
    WindowsGpuUsageCollector,
)


class _CountingProc:
    """A psutil.Process-like double for the fallback topology/thread path.

    The preferred Windows path now injects Toolhelp topology data; these counters
    pin that psutil enumeration remains slow-cadence fallback behavior only.
    """

    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.children_calls = 0
        self.num_threads_calls = 0
        self.threads = 17
        self.rss = 100 * 1024 * 1024

    def cpu_percent(self, interval=None):  # noqa: D401 - test double
        return 5.0

    def children(self, recursive=False):
        self.children_calls += 1
        return []

    def memory_info(self):
        return SimpleNamespace(rss=self.rss, vms=200 * 1024 * 1024, private=90 * 1024 * 1024)

    def memory_full_info(self):
        return SimpleNamespace(uss=80 * 1024 * 1024)

    def num_threads(self):
        self.num_threads_calls += 1
        return self.threads

    def num_handles(self):
        return 500

    def io_counters(self):
        return SimpleNamespace(read_bytes=10, write_bytes=5)


def test_collector_partitions_system_wide_enumerations_to_heavy_cadence():
    proc = _CountingProc()
    collector = ProcessUsageCollector(proc, heavy_refresh_samples=4)

    # Sample 0 is always heavy: it discovers topology and measures threads.
    first = collector.collect()
    assert proc.children_calls == 1
    assert proc.num_threads_calls == 1
    assert first.threads_app == 17
    assert first.rss_app_mb > 0.0
    # With only the main process, the per-process handle split equals the total.
    assert first.handles_app == 500
    assert first.handles_main == 500

    # Samples 1..3 are light: no children()/num_threads() calls, and the thread
    # count carries forward even though the underlying value changed.
    proc.threads = 99
    proc.rss = 150 * 1024 * 1024
    for _ in range(3):
        light = collector.collect()
        assert light.threads_app == 17  # carried forward, not re-measured
        # Cheap per-process memory metrics are still refreshed every sample.
        assert light.rss_app_mb > first.rss_app_mb
    assert proc.children_calls == 1
    assert proc.num_threads_calls == 1

    # Sample 4 refreshes the heavy metrics again and picks up the new count.
    heavy = collector.collect()
    assert proc.children_calls == 2
    assert proc.num_threads_calls == 2
    assert heavy.threads_app == 99




def test_collector_injected_topology_snapshot_avoids_gil_held_psutil_enumerations():
    proc = _CountingProc()
    snapshots = []

    def topology(pid: int):
        snapshots.append(pid)
        return {pid: 23}

    collector = ProcessUsageCollector(
        proc,
        heavy_refresh_samples=4,
        topology_snapshot_provider=topology,
    )

    first = collector.collect()
    assert snapshots == [proc.pid]
    assert proc.children_calls == 0
    assert proc.num_threads_calls == 0
    assert first.threads_app == 23
    assert collector.last_sample_was_heavy is True
    assert collector.last_topology_source == "toolhelp"

    second = collector.collect()
    assert second.threads_app == 23
    assert proc.children_calls == 0
    assert proc.num_threads_calls == 0
    assert collector.last_sample_was_heavy is False
    assert collector.last_topology_source == "cached"


def test_collector_heavy_refresh_one_measures_every_sample():
    proc = _CountingProc()
    collector = ProcessUsageCollector(proc, heavy_refresh_samples=1)
    for _ in range(3):
        collector.collect()
    assert proc.children_calls == 3
    assert proc.num_threads_calls == 3


def test_collector_excludes_handle_sidecar_from_toolhelp_tree_and_thread_total():
    proc = _CountingProc()

    def topology(pid: int):
        return {pid: 23, 7777: 4}

    collector = ProcessUsageCollector(
        proc,
        heavy_refresh_samples=1,
        topology_snapshot_provider=topology,
    )
    collector.exclude_pid(7777)

    snapshot = collector.collect()
    assert snapshot.pids == (proc.pid,)
    assert snapshot.process_count == 1
    assert snapshot.child_count == 0
    assert snapshot.threads_app == 23
    assert snapshot.handles_app == 500


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

    def get_task_category_stats(self):
        return {
            "diagnostics.usage": {
                "submitted": 1,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "rejected": 0,
                "active": 1,
            },
            "visualizer.audio_analysis": {
                "submitted": 23,
                "completed": 22,
                "failed": 0,
                "cancelled": 0,
                "rejected": 0,
                "active": 1,
            },
        }


class _ProcessCollector:
    last_sample_was_heavy = True
    last_topology_source = "toolhelp"

    def __init__(self) -> None:
        self.excluded_pids = []

    def exclude_pid(self, pid):
        self.excluded_pids.append(pid)

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
            rss_children_mb=70.0,
            private_app_mb=380.0,
            private_main_mb=320.0,
            private_children_mb=60.0,
            uss_app_mb=360.0,
            uss_main_mb=300.0,
            uss_children_mb=60.0,
            vms_app_mb=800.0,
            threads_app=17,
            handles_app=640,
            handles_main=560,
            io_read_mb=12.0,
            io_write_mb=3.0,
            cpu_primed=True,
        )


class _HandleSidecar:
    def __init__(self) -> None:
        self.started_with = None
        self.stopped = False

    def start(self, target_pid):
        self.started_with = target_pid
        return 7777

    def stop(self):
        self.stopped = True


def test_usage_service_excludes_out_of_process_handle_sidecar_from_app_totals():
    manager = _Manager()
    process = _ProcessCollector()
    sidecar = _HandleSidecar()
    service = UsageTelemetryService(
        manager,
        process_collector=process,
        gpu_collector=_GpuCollector(),
        handle_attribution_sidecar=sidecar,
    )

    assert service.start() is True
    assert sidecar.started_with is not None
    assert process.excluded_pids == [7777]
    service.stop()
    assert sidecar.stopped is True


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
            query_generation=7,
            engine_counter_count=12,
            dedicated_counter_count=2,
            shared_counter_count=2,
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
        resource_snapshot_provider=lambda: {
            "tracked_resources": 5,
            "tracked_known_bytes": 4096,
            "cpu_cache_resources": 2,
            "cpu_cache_bytes": 2048,
            "cpu_display_resources": 1,
            "cpu_display_bytes": 512,
            "rm_resources": 3,
            "rm_known_bytes": 2048,
            "rm_unknown_resources": 1,
            "gl_resources": 3,
            "gl_known_bytes": 2048,
            "gl_unknown_resources": 1,
            "gl_texture_resources": 1,
            "gl_texture_bytes": 1024,
            "gl_framebuffer_resources": 0,
            "gl_framebuffer_bytes": 0,
            "gl_renderbuffer_resources": 0,
            "gl_renderbuffer_bytes": 0,
            "gl_pbo_resources": 1,
            "gl_pbo_bytes": 1024,
            "qt_default_fbo": "qt_owned_untracked",
            "image_worker_pid": 101,
            "image_worker_rss_mb": 70.0,
            "image_worker_vms_mb": 140.0,
            "image_prefetch_worker_pid": 202,
            "image_prefetch_worker_rss_mb": 55.0,
            "image_prefetch_worker_vms_mb": 110.0,
            "segments_created": 4,
            "segments_live": 0,
            "live_bytes": 0,
            "segments_consumed": 3,
            "segments_reclaimed_late": 1,
            "unlink_failures": 0,
        },
    )

    with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
        assert service.start() is True

    sample = next(record.message for record in caplog.records if "[USAGE] sample " in record.message)
    assert "topology_refresh=1" in sample
    assert "topology_source=toolhelp" in sample
    assert "cpu_app_pct=42.5" in sample
    assert "handles_app=640" in sample
    assert "handles_main=560" in sample
    assert "rss_app_mb=420.0" in sample
    assert "rss_children_mb=70.0" in sample
    assert "private_main_mb=320.0" in sample
    assert "private_children_mb=60.0" in sample
    assert "uss_app_mb=360.0" in sample
    assert "uss_main_mb=300.0" in sample
    assert "uss_children_mb=60.0" in sample
    assert "gpu_busy_pct=67.0" in sample
    assert "gpu_query_generation=7" in sample
    assert "gpu_engine_counters=12" in sample
    assert "gpu_dedicated_counters=2" in sample
    assert "gpu_shared_counters=2" in sample
    assert "gpu_pdh_counters_total=16" in sample
    assert "vram_dedicated_mb=512.0" in sample
    assert "tracked_known_bytes=4096" in sample
    assert "cpu_cache_bytes=2048" in sample
    assert "cpu_display_resources=1" in sample
    assert "cpu_display_bytes=512" in sample
    assert "gl_texture_bytes=1024" in sample
    assert "gl_framebuffer_bytes=0" in sample
    assert "gl_pbo_bytes=1024" in sample
    assert "qt_default_fbo=qt_owned_untracked" in sample
    assert "image_worker_pid=101" in sample
    assert "image_worker_rss_mb=70.0" in sample
    assert "image_prefetch_worker_pid=202" in sample
    assert "image_prefetch_worker_rss_mb=55.0" in sample
    assert "image_prefetch_worker_vms_mb=110.0" in sample
    assert "shm_segments_created=4" in sample
    assert "shm_segments_live=0" in sample
    assert "shm_live_bytes=0" in sample
    assert "shm_segments_reclaimed_late=1" in sample
    assert "tm_active=1" in sample
    assert '"visualizer.audio_analysis":{"active":1' in sample
    assert "tm_delivery={}" in sample
    assert manager.tasks[0][2]["category"] == "diagnostics.usage"
    lifecycle = service.get_latest_lifecycle_snapshot()
    assert lifecycle["sequence"] == 1
    assert lifecycle["rss_app_mb"] == 420.0
    assert lifecycle["private_app_mb"] == 380.0
    assert lifecycle["private_main_mb"] == 320.0
    assert lifecycle["uss_app_mb"] == 360.0
    assert lifecycle["handles_main"] == 560
    assert lifecycle["vram_dedicated_mb"] == 512.0
    assert lifecycle["gpu_query_generation"] == 7
    assert lifecycle["gpu_engine_counter_count"] == 12
    assert lifecycle["gpu_dedicated_counter_count"] == 2
    assert lifecycle["gpu_shared_counter_count"] == 2
    assert lifecycle["sample_age_ms"] >= 0.0

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


class _FakePdh:
    PERF_DETAIL_WIZARD = 400
    PDH_FMT_DOUBLE = 1
    PDH_FMT_LARGE = 2

    def __init__(self) -> None:
        self.opened: list[str] = []
        self.closed: list[str] = []
        self.events: list[tuple[str, str]] = []
        self._generation = 0

    def OpenQuery(self):
        self._generation += 1
        query = f"query-{self._generation}"
        self.opened.append(query)
        self.events.append(("open", query))
        return query

    def CloseQuery(self, query):
        self.closed.append(query)
        self.events.append(("close", query))

    def EnumObjectItems(self, _machine, _data_source, object_name, _detail):
        if self._generation == 1:
            instances = {
                "GPU Engine": [
                    "pid_100_luid_0x1_engtype_3D",
                    "pid_100_luid_0x1_engtype_Copy",
                    "pid_999_luid_0x2_engtype_3D",
                ],
                "GPU Process Memory": ["pid_100_luid_0x1_phys_0"],
            }
        else:
            instances = {
                "GPU Engine": ["pid_100_luid_0x1_engtype_3D"],
                "GPU Process Memory": [
                    "pid_100_luid_0x1_phys_0",
                    "pid_100_luid_0x1_phys_1",
                ],
            }
        return [], instances[object_name]

    def MakeCounterPath(self, parts):
        _machine, object_name, instance, _parent, _index, counter_name = parts
        return object_name, instance, counter_name

    def AddCounter(self, query, path):
        return query, path

    def CollectQueryData(self, _query):
        return None

    def GetFormattedCounterValue(self, _counter, _fmt):
        return 0, 1.0


def test_gpu_collector_refresh_closes_old_query_and_replaces_counter_ownership(monkeypatch):
    """Periodic rediscovery may change cardinality but must not retain prior PDH handles."""

    import core.performance.usage_sampler as usage_module

    now = iter((100.0, 401.0))
    monkeypatch.setattr(usage_module.time, "monotonic", lambda: next(now))
    pdh = _FakePdh()
    collector = WindowsGpuUsageCollector(refresh_seconds=300.0)
    collector._pdh = pdh

    first = collector.collect((100,))
    assert first.status == "warming"
    assert first.query_generation == 1
    assert first.engine_counter_count == 2
    assert first.dedicated_counter_count == 1
    assert first.shared_counter_count == 1
    assert collector._query == "query-1"
    assert len(collector._engine_counters) == 2
    assert len(collector._dedicated_counters) == 1
    assert len(collector._shared_counters) == 1
    assert pdh.closed == []

    second = collector.collect((100,))
    assert second.status == "warming"
    assert second.query_generation == 2
    assert second.engine_counter_count == 1
    assert second.dedicated_counter_count == 2
    assert second.shared_counter_count == 2
    assert collector._query == "query-2"
    # Generation two has a smaller engine set and a larger memory-instance set.
    # Exact lengths prove refresh replaced the lists instead of appending owners.
    assert len(collector._engine_counters) == 1
    assert len(collector._dedicated_counters) == 2
    assert len(collector._shared_counters) == 2
    assert pdh.closed == ["query-1"]
    assert pdh.events.index(("close", "query-1")) < pdh.events.index(("open", "query-2"))

    collector.close()
    assert pdh.closed == ["query-1", "query-2"]
    assert collector._query is None
    assert collector._engine_counters == []
    assert collector._dedicated_counters == []
    assert collector._shared_counters == []


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


def test_handle_attribution_summary_groups_resolved_and_unresolved_types():
    from core.performance.windows_handle_attribution import summarize_handle_types

    counts, indices = summarize_handle_types(
        [(7, 100), (7, 101), (11, 200), (13, 300)],
        {7: "Event", 11: "File"},
    )

    assert counts == {"Event": 2, "File": 1, "type_13": 1}
    assert indices == {"7": "Event", "11": "File", "13": "type_13"}
