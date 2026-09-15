"""Low-observer-effect frame trace admission and binary durability contracts."""

from __future__ import annotations

from pathlib import Path
import struct
import subprocess
import sys
import threading

from core.performance import frame_trace
from core.performance.frame_trace import FrameTraceEvent, FrameTraceSink


def test_frame_trace_requires_explicit_flag() -> None:
    assert frame_trace.frame_trace_requested(["--perf", "--usage"]) is False
    assert frame_trace.frame_trace_requested(["--frame-trace"]) is True


def test_binary_sink_writes_fixed_records_without_standard_logging(tmp_path: Path) -> None:
    path = tmp_path / "trace.bin"
    sink = FrameTraceSink(path, capacity=512)
    for revision in range(300):
        assert sink.record(
            FrameTraceEvent.LOGICAL_PUBLISH,
            screen_index=1,
            revision=revision,
            logical_timestamp_ns=revision * 100,
            auxiliary=7,
            timestamp_ns=1000 + revision,
        )
    metrics = sink.close()
    assert metrics["dropped_records"] == 0
    raw = path.read_bytes()
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    magic, version, record_size, capacity = header.unpack_from(raw, 0)
    assert magic == b"SRPSSFT1"
    assert version == 1
    assert record_size == record.size
    assert capacity == 512
    assert (len(raw) - header.size) // record.size == 300


def test_full_trace_ring_drops_diagnostics_instead_of_blocking() -> None:
    # Build only the producer-side ring state so no writer can race the test.
    # This deterministically proves a full ring rejects new diagnostics instead
    # of waiting for capacity/disk.
    sink = object.__new__(FrameTraceSink)
    sink._capacity = 512
    sink._storage = bytearray(sink._capacity * struct.Struct("<QHhqqq").size)
    sink._lock = threading.RLock()
    sink._wake = threading.Event()
    sink._closed = False
    sink._write_index = 0
    sink._read_index = 0
    sink._count = 0
    sink._dropped = 0

    accepted = 0
    for revision in range(700):
        if sink.record(FrameTraceEvent.RENDER_DRAW, revision=revision):
            accepted += 1

    assert accepted == 512
    assert sink._count == 512
    assert sink._dropped == 188


def test_absent_flag_creates_no_sink_or_writer(monkeypatch, tmp_path: Path) -> None:
    class _ForbiddenSink:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("frame trace sink must not exist without explicit flag")

    monkeypatch.setattr(frame_trace, "FrameTraceSink", _ForbiddenSink)
    monkeypatch.setattr(frame_trace, "_active_sink", None)
    assert frame_trace.start_frame_trace(tmp_path, ["--perf"]) is None
    assert frame_trace.current_frame_trace() is None


def test_record_drops_on_ring_lock_contention_instead_of_waiting(tmp_path: Path) -> None:
    sink = FrameTraceSink(tmp_path / "trace.bin", capacity=512)
    held = threading.Event()
    release = threading.Event()

    def _hold_lock() -> None:
        with sink._lock:
            held.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=_hold_lock)
    thread.start()
    assert held.wait(timeout=2)
    try:
        assert sink.record(FrameTraceEvent.RENDER_DRAW, revision=1) is False
        assert sink._dropped >= 1
    finally:
        release.set()
        thread.join(timeout=2)
        sink.close()
    assert not thread.is_alive()


def test_frame_swap_trace_drops_if_last_draw_telemetry_is_contended() -> None:
    root = Path(__file__).resolve().parents[1]
    telemetry = (root / "rendering" / "quick" / "visualizer" / "telemetry.py").read_text(encoding="utf-8")
    scene = (root / "rendering" / "quick" / "scene_controller.py").read_text(encoding="utf-8")
    trace_method = telemetry.split("def trace_last_draw", 1)[1].split("def note_sync", 1)[0]
    assert "acquire(blocking=False)" in trace_method
    assert "return None" in trace_method
    swap_method = scene.split("def _trace_frame_swapped", 1)[1].split("def _on_frame_swapped", 1)[0]
    assert "if draw_identity is None" in swap_method
    assert "return" in swap_method


def test_report_keeps_latency_per_screen_and_counts_repeat_draws(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        # Same generation+revision on two display windows. Each publication must
        # correlate only with its own QQuickWindow stages.
        (1_000_000, 1, 0, 7, 900_000, 3),
        (2_000_000, 3, 0, 7, 900_000, 3),
        (3_000_000, 5, 0, 7, 900_000, 3),
        (4_000_000, 5, 0, 7, 900_000, 3),  # repeated draw of same revision
        (5_000_000, 6, 0, 7, 900_000, 3),
        (6_000_000, 1, 1, 7, 900_000, 3),
        (7_000_000, 3, 1, 7, 900_000, 3),
        (14_000_000, 5, 1, 7, 900_000, 3),
        (15_000_000, 6, 1, 7, 900_000, 3),
    ]
    payload = bytearray(header.pack(b"SRPSSFT1", 1, record.size, 512))
    for row in rows:
        payload.extend(record.pack(*row))
    trace_path.write_bytes(payload)

    completed = subprocess.run(
        [sys.executable, "tools/frame_trace_report.py", str(trace_path)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )
    out = completed.stdout
    assert "screen=0 draws=2 unique_revisions=1 repeat_draws=1" in out
    assert "screen=1 draws=1 unique_revisions=1 repeat_draws=0" in out
    assert "screen=0 publish->draw_ms n=2 median=2.500" in out
    assert "screen=1 publish->draw_ms n=1 median=8.000" in out


def test_report_surfaces_missing_and_unmatched_stage_records(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        (1_000_000, 1, 0, 10, 900_000, 4),  # publication reaches draw
        (3_000_000, 5, 0, 10, 900_000, 4),
        (4_000_000, 1, 0, 11, 900_000, 4),  # publication missing draw
        (5_000_000, 5, 0, 99, 900_000, 4),  # draw missing publication
    ]
    payload = bytearray(header.pack(b"SRPSSFT1", 1, record.size, 512))
    for row in rows:
        payload.extend(record.pack(*row))
    trace_path.write_bytes(payload)

    completed = subprocess.run(
        [sys.executable, "tools/frame_trace_report.py", str(trace_path)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )
    out = completed.stdout
    assert (
        "screen=0 publish->draw_correlation publications=2 "
        "matched_occurrences=1 unmatched_downstream=1 missing_publications=1"
    ) in out
