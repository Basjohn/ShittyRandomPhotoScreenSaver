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
    assert metrics["writer_alive"] is False
    assert sink._file.closed is True
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


def test_frame_swap_trace_uses_new_draw_sequence_not_last_ever_identity() -> None:
    root = Path(__file__).resolve().parents[1]
    telemetry = (root / "rendering" / "quick" / "visualizer" / "telemetry.py").read_text(encoding="utf-8")
    scene = (root / "rendering" / "quick" / "scene_controller.py").read_text(encoding="utf-8")

    trace_method = telemetry.split("def trace_last_draw", 1)[1].split("def note_sync", 1)[0]
    # The swap observer runs directly on the same Quick render thread as
    # note_draw(); it must never contend with GUI snapshot telemetry.
    assert "self._trace_draw_sequence" in trace_method
    assert "acquire(" not in trace_method

    swap_method = scene.split("def _trace_frame_swapped", 1)[1].split("def _on_frame_swapped", 1)[0]
    assert "draw_sequence <= self._frame_trace_last_swapped_draw_sequence" in swap_method
    assert swap_method.index("self._frame_trace_last_swapped_draw_sequence = draw_sequence") < swap_method.index("trace.record(")
    assert "FrameTraceEvent.FRAME_SWAP" in swap_method


def test_visualizer_trace_draw_sequence_advances_once_per_draw() -> None:
    # telemetry.py itself is deliberately PySide/OpenGL-free. Load that exact
    # module without importing the visualizer package, whose public __init__
    # legitimately exposes render hosts that require the installed runtime.
    import importlib.util

    telemetry_path = (
        Path(__file__).resolve().parents[1]
        / "rendering"
        / "quick"
        / "visualizer"
        / "telemetry.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_srpss_visualizer_telemetry_contract", telemetry_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        VisualizerRenderNodeTelemetry = module.VisualizerRenderNodeTelemetry
    finally:
        sys.modules.pop(spec.name, None)

    telemetry = VisualizerRenderNodeTelemetry()
    assert telemetry.trace_last_draw() == (0, 0, 0.0)

    telemetry.note_draw("bubble", logical_revision=41, logical_timestamp=1.25)
    assert telemetry.trace_last_draw() == (1, 41, 1.25)
    # Reading the latch does not manufacture a new presentation boundary.
    assert telemetry.trace_last_draw() == (1, 41, 1.25)

    telemetry.note_draw("bubble", logical_revision=41, logical_timestamp=1.25)
    assert telemetry.trace_last_draw() == (2, 41, 1.25)


def test_report_keeps_latency_per_screen_and_counts_repeat_draws(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        # Same generation+revision on two display windows. Each publication must
        # correlate only with its own QQuickWindow stages.
        (1_000_000, 1, 0, 7, 900_000, 3),
        (1_200_000, 3, 0, 7, 900_000, 3),
        (1_500_000, 4, 0, 7, 900_000, 3),
        (1_600_000, 7, 0, 7, 900_000, 3),
        (2_500_000, 8, 0, 7, 900_000, 3),
        (3_000_000, 5, 0, 7, 900_000, 3),
        (3_500_000, 8, 0, 7, 900_000, 3),
        (4_000_000, 5, 0, 7, 900_000, 3),  # repeated draw of same revision
        (5_000_000, 6, 0, 7, 900_000, 3),
        (6_000_000, 1, 1, 7, 900_000, 3),
        (7_000_000, 3, 1, 7, 900_000, 3),
        (7_500_000, 4, 1, 7, 900_000, 3),
        (7_600_000, 7, 1, 7, 900_000, 3),
        (13_000_000, 8, 1, 7, 900_000, 3),
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
    assert "screen=0 quick_sync->quick_sync_ready_ms n=1 median=0.100" in out
    assert "screen=0 render_begin->draw_ms n=2 median=0.500" in out
    assert "screen=1 render_begin->draw_ms n=1 median=1.000" in out


def test_render_trace_splits_sync_wait_from_python_gl_work() -> None:
    root = Path(__file__).resolve().parents[1]
    item = (root / "rendering" / "quick" / "visualizer" / "item.py").read_text(
        encoding="utf-8"
    )
    node = (root / "rendering" / "quick" / "visualizer" / "node.py").read_text(
        encoding="utf-8"
    )
    sync_tail = item.split("node.synchronize(", 1)[1].split("self._retirement.set_node", 1)[0]
    assert "FrameTraceEvent.QUICK_SYNC_READY" in sync_tail
    render_body = node.split("def render(", 1)[1].split("def releaseResources", 1)[0]
    assert "FrameTraceEvent.RENDER_BEGIN" in render_body
    assert render_body.index("FrameTraceEvent.RENDER_BEGIN") < render_body.index(
        "self._render_host.render("
    )
    assert render_body.index("self._render_host.render(") < render_body.index(
        "FrameTraceEvent.RENDER_DRAW"
    )


def test_report_timeline_exposes_load_windows_without_runtime_overhead(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        (1_000_000_000, 1, 0, 1, 900_000_000, 1),
        (1_001_000_000, 4, 0, 1, 900_000_000, 1),
        (1_002_000_000, 7, 0, 1, 900_000_000, 1),
        (1_004_000_000, 8, 0, 1, 900_000_000, 1),
        (1_006_000_000, 5, 0, 1, 900_000_000, 1),
        (2_100_000_000, 1, 0, 2, 2_000_000_000, 1),
        (2_110_000_000, 4, 0, 2, 2_000_000_000, 1),
        (2_112_000_000, 7, 0, 2, 2_000_000_000, 1),
        (2_130_000_000, 8, 0, 2, 2_000_000_000, 1),
        (2_150_000_000, 5, 0, 2, 2_000_000_000, 1),
    ]
    payload = bytearray(header.pack(b"SRPSSFT1", 1, record.size, 512))
    for row in rows:
        payload.extend(record.pack(*row))
    trace_path.write_bytes(payload)

    completed = subprocess.run(
        [
            sys.executable,
            "tools/frame_trace_report.py",
            str(trace_path),
            "--timeline-seconds",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )
    out = completed.stdout
    assert "timeline_window_seconds=1" in out
    assert "screen=0 timeline t=0-1s publications=1" in out
    assert "screen=0 timeline t=1-2s publications=1" in out
    assert "sync_ready_render_begin_p95_ms=2.000" in out
    assert "render_begin_draw_p95_ms=2.000" in out
    assert "sync_ready_render_begin_p95_ms=18.000" in out
    assert "render_begin_draw_p95_ms=20.000" in out


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


def test_report_warns_and_keeps_complete_records_with_truncated_tail(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    payload = bytearray(header.pack(b"SRPSSFT1", 1, record.size, 512))
    payload.extend(record.pack(1_000_000, 1, 0, 1, 900_000, 2))
    payload.extend(b"\x01\x02\x03")
    trace_path.write_bytes(payload)

    completed = subprocess.run(
        [sys.executable, "tools/frame_trace_report.py", str(trace_path)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )
    out = completed.stdout
    assert "warning: trailing_bytes=3; incomplete final record ignored" in out
    assert "records=1 capacity=512" in out
    assert "logical_publish: 1" in out
