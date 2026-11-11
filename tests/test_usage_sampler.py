from __future__ import annotations

import logging
import os
import sys
import time
from types import SimpleNamespace

import pytest

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
            "close_failures": 0,
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
    assert "shm_close_failures=0" in sample
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


def test_collector_names_processes_entering_and_leaving_the_tree(caplog):
    # A sample's cost scales with the tree; a grown tree hitched every thread (2026-10-31) and counts alone could
    # not say which processes had joined. Changes are named once, never per sample.
    import os
    proc = _CountingProc()
    tree = {proc.pid: 23, os.getpid(): 40}
    collector = ProcessUsageCollector(proc, heavy_refresh_samples=1, topology_snapshot_provider=lambda pid: dict(tree))
    with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
        collector.collect()
        collector.collect()
        added = [r.getMessage() for r in caplog.records if "topology added" in r.getMessage()]
        assert len(added) == 1 and f"pid={os.getpid()}" in added[0] and "threads=40" in added[0] and "name=" in added[0]
        del tree[os.getpid()]
        collector.collect()
    removed = [r.getMessage() for r in caplog.records if "topology removed" in r.getMessage()]
    assert len(removed) == 1 and f"pid={os.getpid()}" in removed[0]


def test_collector_labels_a_named_child_from_its_own_per_process_pass_and_refreshes_only_for_a_new_one():
    # Native core P2b slice 5.7: the engine worker's CPU/RSS/threads come from the sample's existing per-process pass
    # (no extra OS call). A named child the cached tree does not know yet makes the next sample a topology refresh;
    # with no child named (at rest) or a known one, the slow refresh cadence is unchanged.
    import os
    proc = _CountingProc()
    tree = {proc.pid: 23}
    refreshes = []

    def topology(pid):
        refreshes.append(pid)
        return dict(tree)

    collector = ProcessUsageCollector(proc, heavy_refresh_samples=8, topology_snapshot_provider=topology)
    collector.collect()
    collector.expect_pids((None,))
    collector.collect()
    assert len(refreshes) == 1                                   # at rest: nothing named, no refresh
    child = os.getpid()                                          # a real process stands in for the spawned worker
    tree[child] = 31
    collector.expect_pids((child,))
    collector.collect()
    assert len(refreshes) == 2 and collector.last_sample_was_heavy
    labelled = collector.last_process_breakdown[child]
    # Its first CPU read is primed by this same refresh: no measurement, so ``na`` (A10-L2), its memory measured.
    assert labelled["threads"] == 31 and labelled["rss_mb"] > 0.0 and labelled["cpu_pct"] is None
    collector.expect_pids((child,))
    collector.collect()
    assert len(refreshes) == 2                                   # known: the cadence is unchanged
    assert collector.last_process_breakdown[child]["threads"] == 31          # carried forward like threads_app
    assert collector.last_process_breakdown[child]["cpu_pct"] >= 0.0         # measured over a whole interval now


def test_a_named_pid_the_refresh_cannot_find_forces_one_refresh_not_one_per_sample():
    # Checkpoint audit 10, A10-L2: the engine worker died while its supervisor still names it (until the heartbeat
    # reaps it). A dead process is never in the topology snapshot, so before the fix every sample paid a refresh
    # (~10 ms of mostly GIL-held enumeration each). Now: one refresh per distinct named PID; forgotten once no longer
    # named, so a later worker reusing the PID is refreshed for again. At rest nothing is named and nothing changes.
    proc = _CountingProc()
    tree = {proc.pid: 23}
    refreshes = []

    def topology(pid):
        refreshes.append(pid)
        return dict(tree)

    collector = ProcessUsageCollector(proc, heavy_refresh_samples=8, topology_snapshot_provider=topology)
    collector.collect()
    dead = 987_654_321                                           # never in the tree
    for _ in range(5):
        collector.expect_pids((dead,))
        collector.collect()
    assert len(refreshes) == 2                                   # the first sample, then once for the dead PID
    collector.expect_pids(())                                    # no longer named: forgotten
    collector.collect()
    collector.expect_pids((dead,))                               # named again (a later worker on the same PID)
    collector.collect()
    assert len(refreshes) == 3


def test_a_process_added_by_this_samples_refresh_is_left_out_of_the_cpu_total():
    # A10-L2: the refresh that discovers a child primes its CPU counter and the same sample read it over
    # microseconds (0, or a huge figure when a scheduler tick landed in between): left out of cpu_app_pct.
    class _Child(_CountingProc):
        def __init__(self, pid):
            super().__init__(pid)
            self.reads = 0

        def cpu_percent(self, interval=None):
            self.reads += 1
            return 0.0 if self.reads == 1 else (5000.0 if self.reads == 2 else 7.0)

    proc = _CountingProc()
    child = _Child(31337)
    # The psutil fallback path (no injected topology, a test double main process), as on a host without Toolhelp.
    collector = ProcessUsageCollector(proc, heavy_refresh_samples=8)
    collector.collect()
    proc.children = lambda recursive=False: [child]
    collector.expect_pids((child.pid,))
    first = collector.collect()
    assert child.reads == 2 and first.cpu_app_pct == 5.0      # the main process only; the child's 5000 % left out
    assert collector.last_process_breakdown[child.pid]["cpu_pct"] is None
    second = collector.collect()
    assert second.cpu_app_pct == 12.0 and collector.last_process_breakdown[child.pid]["cpu_pct"] == 7.0


def test_usage_service_forgets_the_engine_workers_pid_once_after_it_is_no_longer_named():
    # A10-L2: the service names the worker's PID while the supervisor reports one, and tells the collector once when
    # it stops (so a later worker reusing the PID is refreshed for); at rest it never calls the collector.
    class _Expecting(_ProcessCollector):
        def __init__(self):
            super().__init__()
            self.expected = []
            self.last_process_breakdown = {}

        def expect_pids(self, pids):
            self.expected.append(tuple(pids))

    named = [None, 101, 101, None, None, None]
    process = _Expecting()
    manager = _Manager()
    service = UsageTelemetryService(manager, process_collector=process, gpu_collector=_GpuCollector(),
                                    resource_snapshot_provider=lambda: {"visualizer_worker_pid": named.pop(0)})
    assert service.start() is True
    while named:
        manager.callback()
    assert process.expected == [(101,), (101,), ()]
    service.stop()


def test_usage_service_logs_the_engine_workers_labelled_breakdown(caplog):
    class _Labelled(_ProcessCollector):
        def __init__(self):
            super().__init__()
            self.expected = []
            self.last_process_breakdown = {101: {"cpu_pct": 12.5, "rss_mb": 84.0, "threads": 21}}

        def expect_pids(self, pids):
            self.expected.append(tuple(pids))

    for pid, expected in ((101, ("visualizer_worker_pid=101", "visualizer_worker_cpu_pct=12.5",
                                 "visualizer_worker_rss_mb=84.0", "visualizer_worker_threads=21")),
                          (None, ("visualizer_worker_pid=na", "visualizer_worker_cpu_pct=na"))):
        caplog.clear()
        process = _Labelled()
        service = UsageTelemetryService(_Manager(), process_collector=process, gpu_collector=_GpuCollector(),
                                        resource_snapshot_provider=lambda pid=pid: {"visualizer_worker_pid": pid})
        with caplog.at_level(logging.INFO, logger="core.performance.usage_sampler"):
            assert service.start() is True
        sample = next(record.message for record in caplog.records if "[USAGE] sample " in record.message)
        assert all(field in sample for field in expected), sample
        assert process.expected == ([(pid,)] if pid is not None else [])
        service.stop()


# -- per-process USS without the GIL-held working-set walk (native core P2, phase-boundary audit L3) ------------------


def test_an_injected_unique_set_size_provider_replaces_psutils_walk_and_fails_over_per_process(caplog):
    calls = []

    class _Proc(_CountingProc):
        full_info_calls = 0

        def memory_full_info(self):
            type(self).full_info_calls += 1
            return super().memory_full_info()

    proc = _Proc()
    collector = ProcessUsageCollector(proc, unique_set_size_provider=lambda pid: calls.append(pid) or 64 * 1024 * 1024)
    snapshot = collector.collect()
    assert calls == [proc.pid] and _Proc.full_info_calls == 0
    assert snapshot.uss_main_mb == snapshot.uss_app_mb == 64.0

    # This process only (it went between the refresh and the read): psutil's read answers for it, the provider stays.
    def gone(pid):
        raise ProcessLookupError(pid)

    collector = ProcessUsageCollector(proc, unique_set_size_provider=gone)
    assert collector.collect().uss_main_mb == 80.0 and _Proc.full_info_calls == 1
    assert collector.collect().uss_main_mb == 80.0 and _Proc.full_info_calls == 2
    assert collector._unique_set_size_provider is gone

    # Anything else is a broken reader: said once, then psutil's walk for the rest of the run.
    def broken(pid):
        raise ValueError("bad buffer")

    collector = ProcessUsageCollector(proc, unique_set_size_provider=broken)
    with caplog.at_level(logging.WARNING, logger="core.performance.usage_sampler"):
        assert collector.collect().uss_main_mb == 80.0
        assert collector.collect().uss_main_mb == 80.0
    assert collector._unique_set_size_provider is None
    assert sum("Native unique-set-size read failed" in record.message for record in caplog.records) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="the working-set reader is Windows-only")
def test_the_real_collector_never_runs_psutils_gil_held_working_set_walk(monkeypatch):
    """The regression bar: every sample used to call ``memory_full_info()`` for every process of the tree, a walk of
    the whole working set with the GIL held (3-4 ms for a 670 MB process on an idle machine; the engine worker's own
    added ~13 ms a sample under load)."""
    import psutil

    expected = psutil.Process().memory_full_info().uss

    def gil_held_walk(self):
        raise AssertionError("psutil's GIL-held working-set walk ran in a usage sample")

    monkeypatch.setattr(psutil.Process, "memory_full_info", gil_held_walk)
    collector = ProcessUsageCollector()
    try:
        for _ in range(2):
            snapshot = collector.collect()
            assert snapshot.uss_main_mb is not None and snapshot.uss_app_mb >= snapshot.uss_main_mb
            # The same definition as psutil's (a page is unique unless shared and mapped elsewhere); the set moves
            # a little between the two reads.
            assert abs(snapshot.uss_main_mb * 1024 * 1024 - expected) < 0.1 * expected
    finally:
        collector.close()


@pytest.mark.skipif(sys.platform != "win32", reason="the working-set reader is Windows-only")
def test_the_working_set_reader_keeps_one_handle_per_process_and_gives_them_back():
    import subprocess

    import psutil

    from core.performance.windows_working_set import WorkingSetReader

    reader = WorkingSetReader()
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    process = psutil.Process()
    try:
        before = process.num_handles()
        own, other = reader.unique_set_size(os.getpid()), reader.unique_set_size(child.pid)
        assert own > 0 and other > 0 and reader.open_handles == 2
        for _ in range(5):                                  # later samples reuse them: one foreign call a process
            reader.unique_set_size(os.getpid())
            reader.unique_set_size(child.pid)
        assert reader.open_handles == 2 and process.num_handles() - before <= 3
        reader.retain([os.getpid()])                        # the child left the sampled tree
        assert reader.open_handles == 1
        reader.unique_set_size(child.pid)
        child.stdin.close()
        child.wait(10)
        with pytest.raises(OSError):                        # gone: its handle is dropped, not kept for a reused PID
            reader.unique_set_size(child.pid)
        assert reader.open_handles == 1
    finally:
        if child.poll() is None:
            child.kill()
        reader.close()
    assert reader.open_handles == 0
    with pytest.raises(OSError):
        reader.unique_set_size(0x7FFFFFF0)                  # no such process


@pytest.mark.skipif(sys.platform != "win32", reason="the working-set reader is Windows-only")
def test_a_python_thread_keeps_running_while_the_working_set_is_walked():
    """What the fix is for: during psutil's walk no other Python thread runs; during the reader's, one does."""
    import threading

    import psutil

    from core.performance.windows_working_set import WorkingSetReader

    ballast = bytearray(b"x") * (256 * 1024 * 1024)          # a working set large enough to take milliseconds
    counter, stop = [0], threading.Event()

    def spin():
        while not stop.is_set():
            counter[0] += 1

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    process, reader = psutil.Process(), WorkingSetReader()
    try:
        reader.unique_set_size(os.getpid())                 # sizes the buffer and opens the handle once
        time.sleep(0.05)
        before, started = counter[0], time.perf_counter()
        time.sleep(0.3)                                     # this thread asleep: what the spinner makes unopposed
        free_rate = (counter[0] - before) / (time.perf_counter() - started)

        def share(call, repeats=9):
            """The spinner's progress during ``call`` against its unopposed rate, the median of ``repeats``: about 0
            when the call held the GIL throughout, towards 1 when it gave it up (a switch interval may fall inside
            one call's Python wrapper: the median is not moved by it)."""
            shares = []
            for _ in range(repeats):
                before, started = counter[0], time.perf_counter()
                call()
                shares.append((counter[0] - before) / max(free_rate * (time.perf_counter() - started), 1e-9))
            return sorted(shares)[len(shares) // 2]

        held = share(process.memory_full_info)
        released = share(lambda: reader.unique_set_size(os.getpid()))
    finally:
        stop.set()
        thread.join(5)
        reader.close()
        del ballast
    assert held < 0.15 and released > 0.3, (held, released)
