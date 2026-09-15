"""Reduce one SRPSS WPR scheduler ETL to a tiny attribution report.

This is deliberately an *offline* tool.  The raw WPR ETL is high-volume and is
not a handoff artifact.  Keep it local, run this reducer after SRPSS has exited
(so lifecycle telemetry contains the Quick render-thread TID), and hand off the
small JSON/text report plus the ordinary SRPSS logs/frame trace if needed.

The reducer uses only the Python standard library.  It reads the kernel
CSwitch/ReadyThread records that are already present in WPR's
``GeneralProfile.Light`` and correlates them to SRPSS's existing binary frame
trace.  No observer is added to the runtime/render hot path.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import mmap
from pathlib import Path
import re
import statistics
import struct
from typing import Iterable, Iterator, Mapping, Sequence

TOOL_VERSION = 1
ETL_BUFFER_BYTES = 1024 * 1024
ETL_BUFFER_HEADER_BYTES = 72

# SRPSS frame trace v1.
_FRAME_MAGIC = b"SRPSSFT1"
_FRAME_HEADER = struct.Struct("<8sHHI")
_FRAME_RECORD = struct.Struct("<QHhqqq")

# NT kernel Thread provider opcodes used here.
_THREAD_GROUP = 0x05
_CSWITCH = 36
_READY_THREAD = 50
_THREAD_START_END = {1, 2, 3, 4}
_SYSTEM_MARKERS = {0x01, 0x02, 0x03, 0x04}
_PERF_MARKERS = {0x10, 0x11}
_SYSTEM_OR_PERF_MARKERS = _SYSTEM_MARKERS | _PERF_MARKERS

_STATE_NAMES = {
    0: "initialized",
    1: "ready",
    2: "running_state",
    3: "standby",
    4: "terminated",
    5: "waiting",
    6: "transition",
    7: "deferred_ready",
}
_WAIT_REASON_NAMES = {
    0: "Executive",
    1: "FreePage",
    2: "PageIn",
    3: "PoolAllocation",
    4: "DelayExecution",
    5: "Suspended",
    6: "UserRequest",
    7: "WrExecutive",
    8: "WrFreePage",
    9: "WrPageIn",
    10: "WrPoolAllocation",
    11: "WrDelayExecution",
    12: "WrSuspended",
    13: "WrUserRequest",
    14: "WrEventPair",
    15: "WrQueue",
    16: "WrLpcReceive",
    17: "WrLpcReply",
    18: "WrVirtualMemory",
    19: "WrPageOut",
    20: "WrRendezvous",
    21: "WrKeyedEvent",
    22: "WrTerminated",
    23: "WrProcessInSwap",
    24: "WrCpuRateControl",
    25: "WrCalloutStack",
    26: "WrKernel",
    27: "WrResource",
    28: "WrPushLock",
    29: "WrMutex",
    30: "WrQuantumEnd",
    31: "WrDispatchInt",
    32: "WrPreempted",
    33: "WrYieldExecution",
    34: "WrFastMutex",
    35: "WrGuardedMutex",
    36: "WrRundown",
    37: "MaximumWaitReason",
}


@dataclass(frozen=True, slots=True)
class ThreadInfo:
    pid: int
    tid: int
    start_address: int | None = None
    base_priority: int | None = None
    affinity_mask: int | None = None


@dataclass(frozen=True, slots=True)
class SchedulerEvent:
    timestamp_ns: int
    kind: str
    cpu: int
    new_tid: int | None = None
    old_tid: int | None = None
    new_priority: int | None = None
    old_priority: int | None = None
    old_wait_reason: int | None = None
    old_state: int | None = None
    readier_tid: int | None = None


@dataclass(frozen=True, slots=True)
class StateInterval:
    start_ns: int
    end_ns: int
    state: str
    wait_reason: int | None = None
    readier_tid: int | None = None


@dataclass(frozen=True, slots=True)
class FrameGap:
    start_ns: int
    end_ns: int
    duration_ms: float
    screen_index: int
    runtime_generation: int
    revision: int


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * float(q)
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    fraction = index - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def _stats_ms(values: Sequence[float]) -> dict[str, float | int | None]:
    values = [float(value) for value in values]
    return {
        "n": len(values),
        "median_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "max_ms": max(values) if values else None,
    }


def _anchor_ns(manifest: Mapping[str, object], label: str) -> int:
    anchors = manifest.get("anchors")
    if not isinstance(anchors, list):
        raise ValueError("capture manifest has no anchors list")
    for anchor in anchors:
        if isinstance(anchor, dict) and anchor.get("label") == label:
            return int(anchor["perf_counter_ns"])
    raise ValueError(f"capture manifest has no {label!r} anchor")


def capture_bounds(manifest: Mapping[str, object]) -> tuple[int, int]:
    start = _anchor_ns(manifest, "after_wpr_start")
    try:
        end = _anchor_ns(manifest, "before_wpr_status")
    except ValueError:
        end = _anchor_ns(manifest, "before_wpr_stop")
    if end <= start:
        raise ValueError("capture manifest has invalid monotonic bounds")
    return start, end


def discover_runtime_ids(log_dir: Path) -> dict[str, int | None]:
    """Find already-recorded SRPSS PID/render/main/known-Python-worker TIDs."""

    root = Path(log_dir)
    lifecycle = root / "screensaver_lifecycle.log"
    verbose = root / "screensaver_verbose.log"
    perf = root / "screensaver_perf.log"
    texts: list[str] = []
    for path in (lifecycle, perf, verbose):
        if path.is_file():
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
    merged = "\n".join(texts)

    def last_int(pattern: str) -> int | None:
        matches = re.findall(pattern, merged)
        return int(matches[-1]) if matches else None

    return {
        "render_tid": last_int(r"['\"]render_thread_id['\"]\s*:\s*(\d+)"),
        "main_pid": last_int(r"['\"]main_pid['\"]\s*:\s*(\d+)"),
        "main_tid": last_int(r"MainThread\((\d+)\)"),
        # This is only an anchor for the common CPython-created worker start
        # routine.  Classification remains unknown if it is unavailable.
        "known_python_worker_tid": last_int(r"thread=io_pool_[^\s(]*\((\d+)\)"),
    }


def _record_size(buffer: mmap.mmap, pos: int, limit: int) -> int:
    if pos + 8 > limit:
        return 0
    marker = buffer[pos + 2]
    size_offset = pos + 4 if marker in _SYSTEM_OR_PERF_MARKERS else pos
    size = struct.unpack_from("<H", buffer, size_offset)[0]
    if size < 8 or pos + size > limit:
        return 0
    return int(size)


def _system_header_size(marker: int) -> int:
    # Full 32/64-bit SystemTrace headers include kernel/user time; compact
    # variants do not.  GeneralProfile.Light currently emits the full form.
    return 32 if marker in (0x01, 0x02) else 24


def scan_scheduler_etl(
    etl_path: Path,
    *,
    render_tid: int,
    start_ns: int,
    end_ns: int,
) -> tuple[list[SchedulerEvent], dict[int, ThreadInfo], dict[str, int]]:
    """Stream only the scheduler/thread metadata needed for attribution."""

    path = Path(etl_path)
    size = path.stat().st_size
    if size < ETL_BUFFER_BYTES or size % ETL_BUFFER_BYTES:
        raise ValueError(
            "unsupported ETL layout: expected WPR 1 MiB fixed buffers "
            f"(size={size})"
        )

    current_tid_by_cpu: dict[int, int] = {}
    events: list[SchedulerEvent] = []
    thread_info: dict[int, ThreadInfo] = {}
    counters = Counter()
    last_timestamp_by_cpu: dict[int, int] = defaultdict(int)

    with path.open("rb") as handle:
        raw = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            for buffer_index in range(size // ETL_BUFFER_BYTES):
                base = buffer_index * ETL_BUFFER_BYTES
                buffer_size = struct.unpack_from("<I", raw, base)[0]
                saved_offset = struct.unpack_from("<I", raw, base + 4)[0]
                cpu = struct.unpack_from("<H", raw, base + 40)[0]
                if buffer_size != ETL_BUFFER_BYTES:
                    raise ValueError(
                        f"unexpected ETL buffer size {buffer_size} at index {buffer_index}"
                    )
                if not (ETL_BUFFER_HEADER_BYTES <= saved_offset <= ETL_BUFFER_BYTES):
                    raise ValueError(
                        f"invalid ETL saved_offset={saved_offset} at index {buffer_index}"
                    )
                pos = base + ETL_BUFFER_HEADER_BYTES
                limit = base + saved_offset
                while pos + 8 <= limit:
                    record_size = _record_size(raw, pos, limit)
                    if not record_size:
                        counters["malformed_records"] += 1
                        break
                    marker = raw[pos + 2]
                    if marker in _PERF_MARKERS:
                        event_type = raw[pos + 6]
                        group = raw[pos + 7]
                        if group == _THREAD_GROUP:
                            timestamp_ns = struct.unpack_from("<Q", raw, pos + 8)[0] * 100
                            if timestamp_ns < last_timestamp_by_cpu[cpu]:
                                counters["per_cpu_timestamp_regressions"] += 1
                            last_timestamp_by_cpu[cpu] = timestamp_ns
                            if event_type == _CSWITCH and record_size >= 44:
                                counters["cswitch_records"] += 1
                                new_tid, old_tid = struct.unpack_from("<II", raw, pos + 16)
                                new_priority = raw[pos + 24]
                                old_priority = raw[pos + 25]
                                old_wait_reason = raw[pos + 28]
                                old_state = raw[pos + 30]
                                if (
                                    start_ns <= timestamp_ns <= end_ns
                                    and (new_tid == render_tid or old_tid == render_tid)
                                ):
                                    events.append(
                                        SchedulerEvent(
                                            timestamp_ns=timestamp_ns,
                                            kind="cswitch",
                                            cpu=cpu,
                                            new_tid=new_tid,
                                            old_tid=old_tid,
                                            new_priority=new_priority,
                                            old_priority=old_priority,
                                            old_wait_reason=old_wait_reason,
                                            old_state=old_state,
                                        )
                                    )
                                # A CSwitch event describes the transition; after
                                # it, the new thread owns this logical processor.
                                current_tid_by_cpu[cpu] = new_tid
                            elif event_type == _READY_THREAD and record_size >= 24:
                                counters["ready_thread_records"] += 1
                                target_tid = struct.unpack_from("<I", raw, pos + 16)[0]
                                if target_tid == render_tid and start_ns <= timestamp_ns <= end_ns:
                                    events.append(
                                        SchedulerEvent(
                                            timestamp_ns=timestamp_ns,
                                            kind="ready",
                                            cpu=cpu,
                                            readier_tid=current_tid_by_cpu.get(cpu),
                                        )
                                    )
                    elif marker in _SYSTEM_MARKERS:
                        event_type = raw[pos + 6]
                        group = raw[pos + 7]
                        if group == _THREAD_GROUP and event_type in _THREAD_START_END:
                            version = struct.unpack_from("<H", raw, pos)[0]
                            header_size = _system_header_size(marker)
                            payload_size = record_size - header_size
                            if payload_size >= 8:
                                pid, tid = struct.unpack_from("<II", raw, pos + header_size)
                                start_address = None
                                affinity_mask = None
                                base_priority = None
                                # Thread v3 layout: seven 64-bit pointer/size
                                # fields before SubProcessTag/priorities.  The
                                # Win32 start routine is at payload +48.
                                if version >= 3 and payload_size >= 72:
                                    affinity_mask = struct.unpack_from(
                                        "<Q", raw, pos + header_size + 40
                                    )[0]
                                    start_address = struct.unpack_from(
                                        "<Q", raw, pos + header_size + 48
                                    )[0]
                                    base_priority = raw[pos + header_size + 68]
                                thread_info[tid] = ThreadInfo(
                                    pid=pid,
                                    tid=tid,
                                    start_address=start_address,
                                    base_priority=base_priority,
                                    affinity_mask=affinity_mask,
                                )
                    pos += (record_size + 7) & ~7
        finally:
            raw.close()

    events.sort(key=lambda event: event.timestamp_ns)
    counters["target_events"] = len(events)
    counters["etl_buffers"] = size // ETL_BUFFER_BYTES
    return events, thread_info, dict(counters)


def build_state_intervals(
    events: Sequence[SchedulerEvent],
    *,
    render_tid: int,
    start_ns: int,
    end_ns: int,
) -> list[StateInterval]:
    intervals: list[StateInterval] = []
    current_state = "unknown"
    current_start = start_ns
    current_wait_reason: int | None = None
    current_readier: int | None = None

    def close(at_ns: int, *, readier_tid: int | None = None) -> None:
        nonlocal current_start, current_readier
        at_ns = max(current_start, min(at_ns, end_ns))
        if at_ns > current_start:
            intervals.append(
                StateInterval(
                    start_ns=current_start,
                    end_ns=at_ns,
                    state=current_state,
                    wait_reason=current_wait_reason,
                    readier_tid=(readier_tid if current_state == "waiting" else current_readier),
                )
            )
        current_start = at_ns
        current_readier = None

    for event in events:
        timestamp = event.timestamp_ns
        if timestamp < start_ns or timestamp > end_ns:
            continue
        next_state: str | None = None
        next_reason: int | None = None
        if event.kind == "ready":
            if current_state != "running":
                # Attribute the wait that just ended to the thread which made
                # the render thread runnable.
                close(timestamp, readier_tid=event.readier_tid)
                current_state = "ready"
                current_wait_reason = None
                current_start = timestamp
            continue
        if event.kind == "cswitch":
            if event.old_tid == render_tid:
                next_state = _STATE_NAMES.get(int(event.old_state or -1), f"state_{event.old_state}")
                next_reason = event.old_wait_reason if next_state == "waiting" else None
            if event.new_tid == render_tid:
                next_state = "running"
                next_reason = None
        if next_state is not None:
            close(timestamp)
            current_state = next_state
            current_wait_reason = next_reason
            current_start = timestamp

    close(end_ns)
    return intervals


def _thread_class(
    tid: int | None,
    *,
    thread_info: Mapping[int, ThreadInfo],
    main_pid: int | None,
    main_tid: int | None,
    python_worker_start: int | None,
) -> str:
    if tid is None:
        return "unknown"
    if main_tid is not None and tid == main_tid:
        return "python_main"
    info = thread_info.get(tid)
    if info is None:
        return "unknown"
    if main_pid is not None and info.pid == main_pid:
        if python_worker_start is not None and info.start_address == python_worker_start:
            return "cpython_thread_bootstrap"
        return "srpss_other"
    return "external"


def state_totals(intervals: Sequence[StateInterval]) -> dict[str, object]:
    totals = Counter()
    waits = Counter()
    for interval in intervals:
        duration = interval.end_ns - interval.start_ns
        totals[interval.state] += duration
        if interval.state == "waiting":
            waits[interval.wait_reason] += duration
    total = sum(totals.values())
    return {
        "capture_s": total / 1e9,
        "states": {
            state: {
                "seconds": duration / 1e9,
                "pct": (100.0 * duration / total if total else 0.0),
            }
            for state, duration in totals.most_common()
        },
        "waiting_by_reason": {
            f"{reason}:{_WAIT_REASON_NAMES.get(reason, 'Unknown')}": {
                "seconds": duration / 1e9,
                "pct_of_wait": (100.0 * duration / sum(waits.values()) if waits else 0.0),
            }
            for reason, duration in waits.most_common()
        },
    }


def ready_to_run_stats(
    events: Sequence[SchedulerEvent], *, render_tid: int
) -> dict[str, object]:
    pending_ready: SchedulerEvent | None = None
    delays: list[float] = []
    by_readier: Counter[int | None] = Counter()
    for event in events:
        if event.kind == "ready":
            pending_ready = event
        elif event.kind == "cswitch" and event.new_tid == render_tid and pending_ready is not None:
            if event.timestamp_ns >= pending_ready.timestamp_ns:
                delays.append((event.timestamp_ns - pending_ready.timestamp_ns) / 1e6)
                by_readier[pending_ready.readier_tid] += 1
            pending_ready = None
    result = _stats_ms(delays)
    result["readier_event_counts"] = {
        str(tid): count for tid, count in by_readier.most_common(20)
    }
    return result


def priority_stats(events: Sequence[SchedulerEvent], *, render_tid: int) -> dict[str, object]:
    switch_in = Counter()
    switch_out = Counter()
    cpus = Counter()
    for event in events:
        if event.kind != "cswitch":
            continue
        if event.new_tid == render_tid:
            switch_in[event.new_priority] += 1
            cpus[event.cpu] += 1
        if event.old_tid == render_tid:
            switch_out[event.old_priority] += 1
    return {
        "switch_in_priority_counts": {str(k): v for k, v in sorted(switch_in.items())},
        "switch_out_priority_counts": {str(k): v for k, v in sorted(switch_out.items())},
        "switch_in_cpu_counts": {str(k): v for k, v in sorted(cpus.items())},
    }


def read_frame_gaps(
    frame_trace_path: Path,
    *,
    start_ns: int,
    end_ns: int,
) -> dict[str, list[FrameGap]]:
    raw = Path(frame_trace_path).read_bytes()
    if len(raw) < _FRAME_HEADER.size:
        raise ValueError("frame trace is too short")
    magic, version, record_size, _capacity = _FRAME_HEADER.unpack_from(raw, 0)
    if magic != _FRAME_MAGIC or version != 1 or record_size != _FRAME_RECORD.size:
        raise ValueError("unsupported SRPSS frame trace format")

    by_key: dict[tuple[int, int, int], dict[int, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    payload = len(raw) - _FRAME_HEADER.size
    count = payload // _FRAME_RECORD.size
    for index in range(count):
        offset = _FRAME_HEADER.size + index * _FRAME_RECORD.size
        ts_ns, event, screen, revision, _logical_ns, generation = _FRAME_RECORD.unpack_from(
            raw, offset
        )
        if not (start_ns <= ts_ns <= end_ns) or screen < 0 or revision < 0:
            continue
        if event in (3, 4, 7, 8):
            by_key[(int(screen), int(generation), int(revision))][int(event)].append(
                int(ts_ns)
            )

    def gaps(event_a: int, event_b: int) -> list[FrameGap]:
        result: list[FrameGap] = []
        for (screen, generation, revision), events in by_key.items():
            if event_a not in events or event_b not in events:
                continue
            for start in events[event_a]:
                finish = next((value for value in events[event_b] if value >= start), None)
                if finish is not None:
                    result.append(
                        FrameGap(
                            start_ns=start,
                            end_ns=finish,
                            duration_ms=(finish - start) / 1e6,
                            screen_index=screen,
                            runtime_generation=generation,
                            revision=revision,
                        )
                    )
                    break
        result.sort(key=lambda gap: gap.start_ns)
        return result

    return {
        "gui_snapshot_to_quick_sync": gaps(3, 4),
        "quick_sync_ready_to_render_begin": gaps(7, 8),
    }


def _overlap_breakdown(
    gaps: Sequence[FrameGap],
    intervals: Sequence[StateInterval],
    *,
    thread_info: Mapping[int, ThreadInfo],
    main_pid: int | None,
    main_tid: int | None,
    python_worker_start: int | None,
) -> dict[str, object]:
    starts = [interval.start_ns for interval in intervals]

    def overlap_one(gap: FrameGap) -> tuple[Counter[str], Counter[str]]:
        import bisect

        states: Counter[str] = Counter()
        readiers: Counter[str] = Counter()
        index = max(0, bisect.bisect_right(starts, gap.start_ns) - 1)
        while index < len(intervals):
            interval = intervals[index]
            if interval.start_ns >= gap.end_ns:
                break
            left = max(gap.start_ns, interval.start_ns)
            right = min(gap.end_ns, interval.end_ns)
            if right > left:
                duration = right - left
                states[interval.state] += duration
                if interval.state == "waiting":
                    readiers[
                        _thread_class(
                            interval.readier_tid,
                            thread_info=thread_info,
                            main_pid=main_pid,
                            main_tid=main_tid,
                            python_worker_start=python_worker_start,
                        )
                    ] += duration
            index += 1
        return states, readiers

    p95 = _percentile([gap.duration_ms for gap in gaps], 0.95)
    groups = {
        "all": list(gaps),
        "p95_tail": [gap for gap in gaps if p95 is not None and gap.duration_ms >= p95],
    }
    output: dict[str, object] = {
        "latency": _stats_ms([gap.duration_ms for gap in gaps]),
    }
    for name, selected in groups.items():
        states = Counter()
        readiers = Counter()
        for gap in selected:
            state_part, readier_part = overlap_one(gap)
            states.update(state_part)
            readiers.update(readier_part)
        total = sum(states.values())
        wait_total = sum(readiers.values())
        output[name] = {
            "n_gaps": len(selected),
            "state_overlap_pct": {
                state: (100.0 * duration / total if total else 0.0)
                for state, duration in states.most_common()
            },
            "waiting_wake_class_pct": {
                role: (100.0 * duration / wait_total if wait_total else 0.0)
                for role, duration in readiers.most_common()
            },
        }
    return output


def build_report(
    *,
    manifest: Mapping[str, object],
    events: Sequence[SchedulerEvent],
    thread_info: Mapping[int, ThreadInfo],
    etl_counters: Mapping[str, int],
    intervals: Sequence[StateInterval],
    frame_gaps: Mapping[str, Sequence[FrameGap]],
    render_tid: int,
    ids: Mapping[str, int | None],
    start_ns: int,
    end_ns: int,
) -> dict[str, object]:
    main_pid = ids.get("main_pid")
    main_tid = ids.get("main_tid")
    known_worker_tid = ids.get("known_python_worker_tid")
    known_worker = thread_info.get(int(known_worker_tid)) if known_worker_tid is not None else None
    python_worker_start = known_worker.start_address if known_worker is not None else None

    render_info = thread_info.get(render_tid)
    state = state_totals(intervals)
    ready = ready_to_run_stats(events, render_tid=render_tid)
    priorities = priority_stats(events, render_tid=render_tid)

    readier_counts: Counter[str] = Counter()
    readier_tid_counts: Counter[int | None] = Counter()
    for event in events:
        if event.kind == "ready":
            readier_tid_counts[event.readier_tid] += 1
            readier_counts[
                _thread_class(
                    event.readier_tid,
                    thread_info=thread_info,
                    main_pid=main_pid,
                    main_tid=main_tid,
                    python_worker_start=python_worker_start,
                )
            ] += 1
    total_readies = sum(readier_counts.values())

    stage_report = {
        name: _overlap_breakdown(
            gaps,
            intervals,
            thread_info=thread_info,
            main_pid=main_pid,
            main_tid=main_tid,
            python_worker_start=python_worker_start,
        )
        for name, gaps in frame_gaps.items()
    }

    ready_pct = float(state["states"].get("ready", {}).get("pct", 0.0))  # type: ignore[index]
    ready_p95 = ready.get("p95_ms")
    runnable_starvation = (
        "not_supported_by_trace"
        if ready_p95 is not None and float(ready_p95) < 0.1 and ready_pct < 5.0
        else "not_ruled_out"
    )

    return {
        "tool": "scheduler_trace_reduce",
        "tool_version": TOOL_VERSION,
        "capture": {
            "start_perf_counter_ns": start_ns,
            "end_perf_counter_ns": end_ns,
            "duration_s": (end_ns - start_ns) / 1e9,
            "source_profile": manifest.get("profile"),
            "trace_health": manifest.get("trace_health"),
            "wpr_lost_event_any": manifest.get("wpr_lost_event_any"),
        },
        "runtime": {
            "render_tid": render_tid,
            "main_pid": main_pid,
            "main_tid": main_tid,
            "known_python_worker_tid": known_worker_tid,
            "known_cpython_thread_bootstrap_start_address": (
                None if python_worker_start is None else hex(python_worker_start)
            ),
            "render_thread": (
                None
                if render_info is None
                else {
                    "pid": render_info.pid,
                    "base_priority": render_info.base_priority,
                    "affinity_mask": render_info.affinity_mask,
                    "start_address": (
                        None if render_info.start_address is None else hex(render_info.start_address)
                    ),
                }
            ),
        },
        "etl": dict(etl_counters),
        "scheduler": {
            "state_totals": state,
            "ready_to_run": ready,
            "priorities": priorities,
            "ready_event_wake_class_pct": {
                role: (100.0 * count / total_readies if total_readies else 0.0)
                for role, count in readier_counts.most_common()
            },
            "top_readier_tids": [
                {
                    "tid": tid,
                    "pid": (thread_info.get(tid).pid if tid in thread_info else None),
                    "count": count,
                    "class": _thread_class(
                        tid,
                        thread_info=thread_info,
                        main_pid=main_pid,
                        main_tid=main_tid,
                        python_worker_start=python_worker_start,
                    ),
                }
                for tid, count in readier_tid_counts.most_common(20)
            ],
        },
        "frame_stages": stage_report,
        "assessment": {
            "ordinary_os_runnable_starvation": runnable_starvation,
            "note": (
                "Ready means runnable but not executing. Waiting means blocked/not runnable. "
                "Frame-stage intervals also include Qt/scenegraph/callback-boundary work; "
                "they are not pure scheduler-delay markers. A cpython_thread_bootstrap "
                "classification means only that the readier shares a CPython-created thread "
                "start routine with a known SRPSS worker; it does not identify a specific pool."
            ),
        },
    }


def _human_report(report: Mapping[str, object]) -> str:
    scheduler = report["scheduler"]  # type: ignore[index]
    state_totals_map = scheduler["state_totals"]["states"]  # type: ignore[index]
    ready = scheduler["ready_to_run"]  # type: ignore[index]
    lines = [
        "SRPSS R-87 scheduler attribution",
        "================================",
        f"render TID: {report['runtime']['render_tid']}",  # type: ignore[index]
        f"capture: {report['capture']['duration_s']:.3f} s",  # type: ignore[index]
        f"trace health: {report['capture']['trace_health']}",  # type: ignore[index]
        "",
        "Render-thread scheduler state:",
    ]
    for state, values in state_totals_map.items():  # type: ignore[union-attr]
        lines.append(
            f"  {state:16s} {values['seconds']:.6f} s  {values['pct']:.3f}%"
        )
    lines.extend(
        [
            "",
            "Ready -> running latency:",
            f"  n={ready['n']} median={ready['median_ms']:.6f} ms "
            f"p95={ready['p95_ms']:.6f} ms p99={ready['p99_ms']:.6f} ms "
            f"max={ready['max_ms']:.6f} ms",
            "",
            f"Ordinary OS runnable-starvation assessment: "
            f"{report['assessment']['ordinary_os_runnable_starvation']}",  # type: ignore[index]
            "",
            "Frame-stage correlation:",
        ]
    )
    for stage_name, stage in report["frame_stages"].items():  # type: ignore[union-attr]
        latency = stage["latency"]
        lines.append(
            f"  {stage_name}: n={latency['n']} median={latency['median_ms']:.4f} ms "
            f"p95={latency['p95_ms']:.4f} ms"
        )
        for group in ("all", "p95_tail"):
            data = stage[group]
            states = ", ".join(
                f"{name}={pct:.1f}%" for name, pct in data["state_overlap_pct"].items()
            )
            wakes = ", ".join(
                f"{name}={pct:.1f}%" for name, pct in data["waiting_wake_class_pct"].items()
            )
            lines.append(f"    {group}: states[{states}] waiting-wake[{wakes}]")
    lines.extend(
        [
            "",
            "Raw ETL is intentionally local-only. Preserve this report, not the ETL, for handoff.",
        ]
    )
    return "\n".join(lines) + "\n"


def reduce_capture(
    capture_dir: Path,
    *,
    srpss_log_dir: Path,
    render_tid: int | None = None,
    output_json: Path | None = None,
    output_text: Path | None = None,
) -> dict[str, object]:
    capture_dir = Path(capture_dir).resolve()
    log_dir = Path(srpss_log_dir).resolve()
    manifest_path = capture_dir / "scheduler_capture_manifest.json"
    etl_path = capture_dir / "srpss_scheduler.etl"
    frame_trace_path = log_dir / "screensaver_frame_trace.bin"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    if not etl_path.is_file():
        raise FileNotFoundError(etl_path)
    if not frame_trace_path.is_file():
        raise FileNotFoundError(frame_trace_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    start_ns, end_ns = capture_bounds(manifest)
    ids = discover_runtime_ids(log_dir)
    actual_render_tid = int(render_tid or ids.get("render_tid") or 0)
    if actual_render_tid <= 0:
        raise ValueError(
            "render thread TID was not found; exit SRPSS normally so lifecycle telemetry "
            "is complete, or pass --render-tid"
        )
    ids = dict(ids)
    ids["render_tid"] = actual_render_tid

    events, thread_info, counters = scan_scheduler_etl(
        etl_path,
        render_tid=actual_render_tid,
        start_ns=start_ns,
        end_ns=end_ns,
    )
    intervals = build_state_intervals(
        events,
        render_tid=actual_render_tid,
        start_ns=start_ns,
        end_ns=end_ns,
    )
    frame_gaps = read_frame_gaps(frame_trace_path, start_ns=start_ns, end_ns=end_ns)
    report = build_report(
        manifest=manifest,
        events=events,
        thread_info=thread_info,
        etl_counters=counters,
        intervals=intervals,
        frame_gaps=frame_gaps,
        render_tid=actual_render_tid,
        ids=ids,
        start_ns=start_ns,
        end_ns=end_ns,
    )

    json_path = output_json or capture_dir / "scheduler_attribution.json"
    text_path = output_text or capture_dir / "scheduler_attribution.txt"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    text_path.write_text(_human_report(report), encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reduce a local SRPSS WPR scheduler ETL to a small attribution report"
    )
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument(
        "--srpss-log-dir",
        type=Path,
        required=True,
        help="SRPSS log directory containing lifecycle telemetry and screensaver_frame_trace.bin",
    )
    parser.add_argument("--render-tid", type=int, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-text", type=Path, default=None)
    parser.add_argument(
        "--delete-etl",
        action="store_true",
        help="delete the raw ETL after a successful reduction; recommended because raw ETLs are local-only",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = reduce_capture(
        args.capture_dir,
        srpss_log_dir=args.srpss_log_dir,
        render_tid=args.render_tid,
        output_json=args.output_json,
        output_text=args.output_text,
    )
    print(_human_report(report), end="")
    if args.delete_etl:
        etl_path = Path(args.capture_dir).resolve() / "srpss_scheduler.etl"
        etl_path.unlink()
        print(f"Deleted local raw ETL after successful reduction: {etl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
