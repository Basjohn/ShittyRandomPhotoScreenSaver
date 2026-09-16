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
    host = (root / "rendering" / "quick" / "visualizer" / "render_host.py").read_text(
        encoding="utf-8"
    )
    sync_tail = item.split("node.synchronize(", 1)[1].split("self._retirement.set_node", 1)[0]
    assert "FrameTraceEvent.QUICK_SYNC_READY" in sync_tail
    render_body = node.split("def render(", 1)[1].split("def releaseResources", 1)[0]
    assert "FrameTraceEvent.RENDER_BEGIN" in render_body
    assert render_body.index("FrameTraceEvent.RENDER_BEGIN") < render_body.index(
        "FrameTraceEvent.RENDER_PREP_READY"
    )
    assert render_body.index("FrameTraceEvent.RENDER_PREP_READY") < render_body.index(
        "FrameTraceEvent.RENDER_HOST_BEGIN"
    )
    assert render_body.index("FrameTraceEvent.RENDER_HOST_BEGIN") < render_body.index(
        "self._render_host.render("
    )
    assert render_body.index("self._render_host.render(") < render_body.index(
        "FrameTraceEvent.RENDER_HOST_READY"
    )
    assert render_body.index("FrameTraceEvent.RENDER_HOST_READY") < render_body.index(
        "FrameTraceEvent.RENDER_DRAW"
    )

    host_body = host.split("def render(", 1)[1].split(
        "def release_inactive_implementations", 1
    )[0]
    assert host_body.index("InheritedGlState.capture_render_host()") < host_body.index(
        "FrameTraceEvent.RENDER_GL_STATE_READY"
    )
    assert host_body.index("inherited_gl_state is not None") < host_body.index(
        "FrameTraceEvent.RENDER_GL_STATE_READY"
    )
    assert host_body.index("FrameTraceEvent.RENDER_GL_STATE_READY") < host_body.index(
        "FrameTraceEvent.RENDER_MODE_BEGIN"
    )
    assert host_body.index("FrameTraceEvent.RENDER_MODE_BEGIN") < host_body.index(
        "implementation.render(frame)"
    )
    assert host_body.index("implementation.render(frame)") < host_body.index(
        "FrameTraceEvent.RENDER_MODE_READY"
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
    assert "sync_work_n=1 sync_work_median_ms=1.000 sync_work_p95_ms=1.000" in out
    assert (
        "sync_ready_render_begin_n=1 sync_ready_render_begin_median_ms=2.000 "
        "sync_ready_render_begin_p95_ms=2.000"
    ) in out
    assert (
        "render_begin_draw_n=1 render_begin_draw_median_ms=2.000 "
        "render_begin_draw_p95_ms=2.000"
    ) in out
    assert "sync_work_n=1 sync_work_median_ms=2.000 sync_work_p95_ms=2.000" in out
    assert (
        "sync_ready_render_begin_n=1 sync_ready_render_begin_median_ms=18.000 "
        "sync_ready_render_begin_p95_ms=18.000"
    ) in out
    assert (
        "render_begin_draw_n=1 render_begin_draw_median_ms=20.000 "
        "render_begin_draw_p95_ms=20.000"
    ) in out


def test_report_splits_render_body_subphases(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        (1_000_000_000, 1, 0, 1, 900_000_000, 1),
        (1_001_000_000, 8, 0, 1, 900_000_000, 1),
        (1_002_000_000, 9, 0, 1, 900_000_000, 1),
        (1_003_000_000, 10, 0, 1, 900_000_000, 1),
        (1_005_000_000, 11, 0, 1, 900_000_000, 1),
        (1_006_000_000, 12, 0, 1, 900_000_000, 1),
        (1_010_000_000, 13, 0, 1, 900_000_000, 1),
        (1_012_000_000, 14, 0, 1, 900_000_000, 1),
        (1_013_000_000, 5, 0, 1, 900_000_000, 1),
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
    assert "render_begin->render_prep_ready_ms n=1 median=1.000" in out
    assert "render_prep_ready->render_host_begin_ms n=1 median=1.000" in out
    assert "render_host_begin->render_gl_state_ready_ms n=1 median=2.000" in out
    assert "render_gl_state_ready->render_mode_begin_ms n=1 median=1.000" in out
    assert "render_mode_begin->render_mode_ready_ms n=1 median=4.000" in out
    assert "render_mode_ready->render_host_ready_ms n=1 median=2.000" in out
    assert "render_host_ready->draw_ms n=1 median=1.000" in out
    assert "render_prep_n=1 render_prep_median_ms=1.000 render_prep_p95_ms=1.000" in out
    assert "render_host_n=1 render_host_median_ms=9.000 render_host_p95_ms=9.000" in out
    assert "render_mode_n=1 render_mode_median_ms=4.000 render_mode_p95_ms=4.000" in out
    assert "render_post_n=1 render_post_median_ms=1.000 render_post_p95_ms=1.000" in out


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


def test_audio_analysis_trace_can_be_correlated_with_render_entry_gap(tmp_path: Path) -> None:
    trace_path = tmp_path / "audio_overlap.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        # One ordinary visualizer revision on screen 0.
        (1_000_000, 1, 0, 1, 0, 0),
        (2_000_000, 7, 0, 1, 0, 0),
        # One analysis slot is deliberately unscoped from a display.
        (3_000_000, 15, -1, 101, 0, 1),
        (4_000_000, 17, -1, 101, 0, 1),
        (5_000_000, 18, -1, 101, 0, 1),
        (6_000_000, 16, -1, 101, 0, 1),
        (7_000_000, 8, 0, 1, 0, 0),
        (8_000_000, 5, 0, 1, 0, 0),
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
    assert "audio_analysis_ms n=1 median=3.000" in out
    assert "audio_smooth_ms n=1 median=1.000" in out
    assert (
        "screen=0 sync_ready_render_begin_audio_analysis_overlap "
        "scope=all gaps=1 overlap_gaps=1 overlap_gap_pct=100.00 "
        "overlap_time_pct=60.00"
    ) in out
    assert (
        "screen=0 sync_ready_render_begin_audio_smooth_overlap "
        "scope=all gaps=1 overlap_gaps=1 overlap_gap_pct=100.00 "
        "overlap_time_pct=20.00"
    ) in out


def test_audio_analysis_trace_brackets_compute_and_python_smoothing() -> None:
    root = Path(__file__).resolve().parents[1]
    beat_engine = (
        root / "widgets" / "spotify_visualizer" / "beat_engine.py"
    ).read_text(encoding="utf-8")
    body = beat_engine.split("def _run_analysis_request", 1)[1].split(
        "def _accept_analysis_lane_result", 1
    )[0]
    assert body.index("FrameTraceEvent.AUDIO_ANALYSIS_BEGIN") < body.index(
        "compute_bars_from_samples(worker_state, request.samples)"
    )
    assert body.index("compute_bars_from_samples(worker_state, request.samples)") < body.index(
        "FrameTraceEvent.AUDIO_ANALYSIS_READY"
    )
    assert body.index("FrameTraceEvent.AUDIO_SMOOTH_BEGIN") < body.index(
        "_smooth_analysis_bars("
    )
    assert body.index("_smooth_analysis_bars(") < body.index(
        "FrameTraceEvent.AUDIO_SMOOTH_READY"
    )


def test_background_render_trace_is_explicit_and_pre_visualizer_attribution_ready() -> None:
    root = Path(__file__).resolve().parents[1]
    item = (root / "rendering" / "quick" / "render" / "background_item.py").read_text(
        encoding="utf-8"
    )
    node = (root / "rendering" / "quick" / "render" / "background_node.py").read_text(
        encoding="utf-8"
    )
    scene = (root / "rendering" / "quick" / "scene_controller.py").read_text(
        encoding="utf-8"
    )

    assert "self._frame_trace = current_frame_trace()" in item
    assert "screen_index=self._window.screen_index" in scene
    render_body = node.split("def render(", 1)[1].split("def releaseResources", 1)[0]
    assert "if trace is not None:" in render_body
    assert "FrameTraceEvent.BACKGROUND_RENDER_BEGIN" in render_body
    assert "FrameTraceEvent.BACKGROUND_RENDER_READY" in render_body
    draw_body = node.split("def _draw(", 1)[1].split("def _draw_base", 1)[0]
    assert "FrameTraceEvent.BACKGROUND_TEXTURE_READY" in draw_body
    assert "FrameTraceEvent.BACKGROUND_DRAW_BEGIN" in draw_body
    assert "FrameTraceEvent.BACKGROUND_DRAW_READY" in draw_body


def test_report_splits_background_idle_transition_and_render_entry_overlap(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        # Visualizer render-entry gap 1: 1 -> 10 ms.
        (1_000_000, 7, 1, 100, 0, 0),
        # Steady background render occupies 2 -> 7 ms inside that gap.
        (2_000_000, 19, 1, 1, 0, 0),
        (3_000_000, 20, 1, 1, 0, 0),
        (4_000_000, 21, 1, 1, 0, 0),
        (6_000_000, 22, 1, 1, 0, 0),
        (7_000_000, 23, 1, 1, 0, 0),
        (10_000_000, 8, 1, 100, 0, 0),
        # Visualizer gap 2: 11 -> 21 ms; transition run 7 occupies 12 -> 18 ms.
        (11_000_000, 7, 1, 101, 0, 0),
        (12_000_000, 19, 1, 2, 0, 7),
        (13_000_000, 20, 1, 2, 0, 7),
        (14_000_000, 21, 1, 2, 0, 7),
        (17_000_000, 22, 1, 2, 0, 7),
        (18_000_000, 23, 1, 2, 0, 7),
        (21_000_000, 8, 1, 101, 0, 0),
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
    assert "background_render_begin: 2" in out
    assert "screen=1 background_render_begin->render_ready_ms n=2 median=5.500" in out
    assert "idle_n=1 idle_median=5.000" in out
    assert "transition_n=1 transition_median=6.000" in out
    assert "sync_ready_render_begin_background_render_overlap scope=all gaps=2 overlap_gaps=2" in out


def test_clip_trace_is_explicit_deferred_and_absent_from_untraced_clip_calls() -> None:
    root = Path(__file__).resolve().parents[1]
    node = (root / "rendering" / "quick" / "visualizer" / "node.py").read_text(
        encoding="utf-8"
    )
    clip = (root / "rendering" / "quick" / "visualizer" / "clip_host.py").read_text(
        encoding="utf-8"
    )

    assert "current_frame_trace" not in clip
    assert "if trace is None:" in node
    assert "self._clip_host.begin(clip_frame, state)" in node
    assert "trace_context=clip_trace" in node
    assert node.index("FrameTraceEvent.RENDER_DRAW") < node.index("clip_trace.flush()")

    begin_body = clip.split("def begin(", 1)[1].split("def end(", 1)[0]
    assert begin_body.index("CLIP_BEGIN_RESOURCES_READY") < begin_body.index(
        "CLIP_BEGIN_INHERITED_READY"
    )
    assert begin_body.index("CLIP_BEGIN_INHERITED_READY") < begin_body.index(
        "CLIP_BEGIN_SETUP_READY"
    )
    capture_body = clip.split("def capture(", 1)[1].split("def restore(", 1)[0]
    assert capture_body.index("CLIP_BEGIN_INHERITED_SCISSOR_READY") < capture_body.index(
        "CLIP_BEGIN_INHERITED_FRONT_READY"
    )
    draw_body = clip.split("def _draw_mask(", 1)[1].split("__all__", 1)[0]
    assert draw_body.index("CLIP_BEGIN_MASK_BINDINGS_READY") < draw_body.index(
        "CLIP_BEGIN_MASK_STATE_READY"
    )
    assert draw_body.index("CLIP_BEGIN_MASK_STATE_READY") < draw_body.index(
        "CLIP_BEGIN_MASK_GL_STATE_APPLIED"
    )
    assert draw_body.index("CLIP_BEGIN_MASK_GL_STATE_APPLIED") < draw_body.index(
        "CLIP_BEGIN_MASK_UNIFORMS_READY"
    )
    assert draw_body.index("CLIP_BEGIN_MASK_UNIFORMS_READY") < draw_body.index(
        "CLIP_BEGIN_MASK_DRAW_READY"
    )
    assert draw_body.index("CLIP_BEGIN_MASK_DRAW_READY") < draw_body.index(
        "CLIP_BEGIN_MASK_RESTORE_READY"
    )
    end_body = clip.split("def end(", 1)[1].split("def release_resources", 1)[0]
    assert end_body.index("CLIP_END_SETUP_READY") < end_body.index(
        "CLIP_END_INHERITED_READY"
    )


def test_report_splits_clip_stages_and_reports_parent_contribution(tmp_path: Path) -> None:
    trace_path = tmp_path / "clip_trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        # Clip begin parent: render_prep_ready 1 ms -> render_host_begin 12 ms.
        (1_000_000, 9, 1, 7, 0, 3),
        (2_000_000, 24, 1, 7, 0, 3),
        (4_000_000, 25, 1, 7, 0, 3),
        (5_000_000, 26, 1, 7, 0, 3),
        (7_000_000, 27, 1, 7, 0, 3),
        (10_000_000, 28, 1, 7, 0, 3),
        (11_000_000, 29, 1, 7, 0, 3),
        (12_000_000, 10, 1, 7, 0, 3),
        # Clip end parent: render_host_ready 20 ms -> render_draw 30 ms.
        (20_000_000, 14, 1, 7, 0, 3),
        (21_000_000, 30, 1, 7, 0, 3),
        (23_000_000, 31, 1, 7, 0, 3),
        (26_000_000, 32, 1, 7, 0, 3),
        (27_000_000, 33, 1, 7, 0, 3),
        (29_000_000, 34, 1, 7, 0, 3),
        (30_000_000, 5, 1, 7, 0, 3),
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
    assert "clip_begin_mask_state_ready: 1" in out
    assert "clip_end_inherited_ready: 1" in out
    assert (
        "screen=1 clip_begin_coverage "
        "parent_interval=render_prep_ready->render_host_begin parent_n=1 fully_attributed_n=1"
    ) in out
    assert (
        "screen=1 clip_begin_stage=inherited_state_capture "
        "parent_interval=render_prep_ready->render_host_begin n=1 "
        "median_ms=2.000 p95_ms=2.000 p99_ms=2.000 parent_total_share_pct=18.18"
    ) in out
    assert (
        "screen=1 clip_begin_stage=mask_draw "
        "parent_interval=render_prep_ready->render_host_begin n=1 "
        "median_ms=3.000 p95_ms=3.000 p99_ms=3.000 parent_total_share_pct=27.27"
    ) in out
    assert (
        "screen=1 clip_end_stage=inherited_state_restore "
        "parent_interval=render_host_ready->draw n=1 "
        "median_ms=2.000 p95_ms=2.000 p99_ms=2.000 parent_total_share_pct=20.00"
    ) in out
    assert "clip_begin_refined_coverage" not in out


def test_report_refines_clip_state_and_actual_draw_call_when_chk25_events_exist(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "clip_trace_refined.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        # Clip begin parent: 1 -> 15 ms. Existing CHK24 aggregate markers stay
        # present while CHK25 markers split inherited state and mask draw.
        (1_000_000, 9, 1, 7, 0, 3),
        (2_000_000, 24, 1, 7, 0, 3),
        (3_000_000, 35, 1, 7, 0, 3),
        (5_000_000, 36, 1, 7, 0, 3),
        (6_000_000, 25, 1, 7, 0, 3),
        (7_000_000, 26, 1, 7, 0, 3),
        (8_000_000, 37, 1, 7, 0, 3),
        (9_000_000, 27, 1, 7, 0, 3),
        (10_000_000, 38, 1, 7, 0, 3),
        (11_000_000, 39, 1, 7, 0, 3),
        (13_000_000, 28, 1, 7, 0, 3),
        (14_000_000, 29, 1, 7, 0, 3),
        (15_000_000, 10, 1, 7, 0, 3),
        # Clip end parent: 20 -> 30 ms with the same refined mask split.
        (20_000_000, 14, 1, 7, 0, 3),
        (21_000_000, 30, 1, 7, 0, 3),
        (22_000_000, 40, 1, 7, 0, 3),
        (23_000_000, 31, 1, 7, 0, 3),
        (24_000_000, 41, 1, 7, 0, 3),
        (25_000_000, 42, 1, 7, 0, 3),
        (27_000_000, 32, 1, 7, 0, 3),
        (28_000_000, 33, 1, 7, 0, 3),
        (29_000_000, 34, 1, 7, 0, 3),
        (30_000_000, 5, 1, 7, 0, 3),
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
    assert "clip_begin_inherited_scissor_ready: 1" in out
    assert "clip_begin_mask_uniforms_ready: 1" in out
    assert (
        "screen=1 clip_begin_refined_coverage "
        "parent_interval=render_prep_ready->render_host_begin "
        "parent_n=1 fully_attributed_n=1"
    ) in out
    assert (
        "screen=1 clip_begin_refined_stage=inherited_front_stencil_capture "
        "parent_interval=render_prep_ready->render_host_begin n=1 "
        "median_ms=2.000 p95_ms=2.000 p99_ms=2.000 "
        "parent_total_share_pct=14.29"
    ) in out
    assert (
        "screen=1 clip_begin_refined_stage=mask_draw_call "
        "parent_interval=render_prep_ready->render_host_begin n=1 "
        "median_ms=2.000 p95_ms=2.000 p99_ms=2.000 "
        "parent_total_share_pct=14.29"
    ) in out
    assert (
        "screen=1 clip_end_refined_stage=mask_draw_call "
        "parent_interval=render_host_ready->draw n=1 "
        "median_ms=2.000 p95_ms=2.000 p99_ms=2.000 "
        "parent_total_share_pct=20.00"
    ) in out


def test_chk26_clipped_gl_state_is_captured_once_and_carried_through_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    clip = (root / "rendering" / "quick" / "visualizer" / "clip_host.py").read_text(
        encoding="utf-8"
    )
    node = (root / "rendering" / "quick" / "visualizer" / "node.py").read_text(
        encoding="utf-8"
    )
    host = (root / "rendering" / "quick" / "visualizer" / "render_host.py").read_text(
        encoding="utf-8"
    )
    shared = (root / "rendering" / "quick" / "visualizer" / "gl_state.py").read_text(
        encoding="utf-8"
    )

    assert "InheritedGlState.capture_clipped_shared" in clip
    assert "run.inherited_gl_state =" in clip
    assert clip.count("inherited_gl_state=run.inherited_gl_state") >= 3
    assert "inherited_gl_state=clip_run.inherited_gl_state" in node
    assert "if inherited_gl_state is not None" in host
    assert "InheritedGlState.capture_render_host()" in host
    assert "CLIP_BEGIN_SHARED_GL_STATE_READY" in shared

    # The shared snapshot is safe to reuse through the mode because color-mask
    # ownership remains exclusive to the clip host. A future mode that starts
    # changing color writes must extend the common fence instead of silently
    # invalidating the carried-state contract.
    implementation_root = root / "rendering" / "quick" / "visualizer" / "implementations"
    implementation_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(implementation_root.glob("*.py"))
    )
    assert "glColorMask" not in implementation_source
    assert "glColorMask" not in host


def test_report_splits_chk26_shared_capture_and_tail_without_rewriting_old_stages(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "chk26_clip_trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    # One fully attributed clipped frame. Values are intentionally simple so the
    # CHK26-only shared-capture split and p95-tail summary are deterministic.
    rows = [
        (1_000_000, 9, 1, 7, 0, 3),
        (2_000_000, 24, 1, 7, 0, 3),
        (3_000_000, 35, 1, 7, 0, 3),
        (4_000_000, 36, 1, 7, 0, 3),
        (5_000_000, 25, 1, 7, 0, 3),
        (6_000_000, 26, 1, 7, 0, 3),
        (7_000_000, 37, 1, 7, 0, 3),
        (8_000_000, 27, 1, 7, 0, 3),
        (10_000_000, 43, 1, 7, 0, 3),
        (13_000_000, 38, 1, 7, 0, 3),
        (14_000_000, 39, 1, 7, 0, 3),
        (15_000_000, 28, 1, 7, 0, 3),
        (16_000_000, 29, 1, 7, 0, 3),
        (17_000_000, 10, 1, 7, 0, 3),
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
    assert "clip_begin_shared_gl_state_ready: 1" in out
    assert "clip_begin_refined_stage=shared_render_state_extra_capture" in out
    assert "median_ms=2.000" in out
    assert "clip_begin_refined_stage=mask_state_programming" in out
    assert "median_ms=3.000" in out
    assert "clip_begin_refined_p95_tail" in out
    assert "clip_begin_refined_p95_tail_stage=mask_state_programming" in out


def test_frame_trace_rolls_disk_segments_instead_of_growing_without_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "screensaver_frame_trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    segment_bytes = header.size + (10 * record.size)
    sink = FrameTraceSink(
        path,
        capacity=512,
        segment_bytes=segment_bytes,
        retained_segments=3,
    )
    payload = b"".join(
        record.pack(1_000 + revision, 1, 1, revision, 0, 7)
        for revision in range(40)
    )
    assert sink._write_trace_data(payload) == 40
    metrics = sink.close()

    retained = [path.with_name("screensaver_frame_trace.2.bin"),
                path.with_name("screensaver_frame_trace.1.bin"), path]
    assert all(candidate.is_file() for candidate in retained)
    assert all(candidate.stat().st_size <= segment_bytes for candidate in retained)
    assert metrics["retained_bytes_limit"] == segment_bytes * 3
    assert metrics["rotations"] == 3

    timestamps: list[int] = []
    for candidate in retained:
        raw = candidate.read_bytes()
        magic, version, record_size, _capacity = header.unpack_from(raw, 0)
        assert magic == b"SRPSSFT1"
        assert version == 1
        assert record_size == record.size
        for offset in range(header.size, len(raw), record.size):
            timestamps.append(record.unpack_from(raw, offset)[0])
    # Four ten-record segments were produced; only the newest three survive.
    assert timestamps == list(range(1_010, 1_040))


def test_frame_trace_report_reads_rolling_segments_oldest_to_newest(
    tmp_path: Path,
) -> None:
    path = tmp_path / "screensaver_frame_trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    segment_bytes = header.size + (10 * record.size)
    sink = FrameTraceSink(
        path,
        capacity=512,
        segment_bytes=segment_bytes,
        retained_segments=3,
    )
    payload = b"".join(
        record.pack(1_000_000 + revision, 1, 1, revision, 0, 7)
        for revision in range(40)
    )
    sink._write_trace_data(payload)
    sink.close()

    completed = subprocess.run(
        [sys.executable, "tools/frame_trace_report.py", str(path)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )
    assert "records=30 capacity=512" in completed.stdout
    assert "trace_segments=3 retention=rolling_oldest_to_newest" in completed.stdout
    assert "logical_publish: 30" in completed.stdout


def test_render_host_retains_lazy_quad_integer_state_helper() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "rendering" / "quick" / "visualizer" / "render_host.py"
    ).read_text(encoding="utf-8")
    assert "def _int_state(name: int) -> int:" in source
    ensure_quad = source.split("def _ensure_quad(self)", 1)[1]
    assert "_int_state(gl.GL_VERTEX_ARRAY_BINDING)" in ensure_quad
    assert "_int_state(gl.GL_ARRAY_BUFFER_BINDING)" in ensure_quad


def test_chk27_sync_attribution_is_explicit_trace_only_and_preserves_legacy_markers() -> None:
    root = Path(__file__).resolve().parents[1]
    frame_trace_source = (root / "core" / "performance" / "frame_trace.py").read_text(
        encoding="utf-8"
    )
    publication_sync = (
        root / "widgets" / "spotify_visualizer" / "quick_presentation_sync.py"
    ).read_text(encoding="utf-8")
    item = (root / "rendering" / "quick" / "visualizer" / "item.py").read_text(
        encoding="utf-8"
    )
    reporter = (root / "tools" / "frame_trace_report.py").read_text(encoding="utf-8")

    for event_name in (
        "GUI_PRESENTATION_COMMIT_READY",
        "GUI_PRESENT_REQUEST_READY",
        "QUICK_SYNC_ITEM_ENTRY",
        "QUICK_SYNC_SNAPSHOT_ACQUIRED",
    ):
        assert event_name in frame_trace_source
        assert event_name in publication_sync + item

    # Existing authority markers remain intact so CHK23-26 traces and reports
    # retain the same aggregate publication -> Quick synchronization seam.
    assert "FrameTraceEvent.GUI_SNAPSHOT_PUBLISH" in publication_sync
    assert "FrameTraceEvent.QUICK_SYNC_CONSUME" in item
    assert '(3, 4, "gui_snapshot->quick_sync")' in reporter

    # No untraced timestamping: updatePaintNode only asks perf_counter for the
    # entry timestamp when an explicit --frame-trace sink has been injected.
    update_body = item.split("def updatePaintNode(", 1)[1].split("__all__", 1)[0]
    assert "time.perf_counter_ns() if trace is not None else None" in update_body
    assert update_body.index("QUICK_SYNC_ITEM_ENTRY") < update_body.index(
        "QUICK_SYNC_CONSUME"
    )
    assert update_body.index("QUICK_SYNC_SNAPSHOT_ACQUIRED") < update_body.index(
        "QUICK_SYNC_CONSUME"
    )

    sync_body = publication_sync.split("def sync_latest(self)", 1)[1].split(
        "__all__", 1
    )[0]
    assert sync_body.index("GUI_SNAPSHOT_PUBLISH") < sync_body.index(
        "GUI_PRESENTATION_COMMIT_READY"
    )
    assert sync_body.index("GUI_PRESENTATION_COMMIT_READY") < sync_body.index(
        "GUI_PRESENT_REQUEST_READY"
    )


def test_report_splits_chk27_gui_snapshot_to_quick_sync_attribution(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "chk27_sync_trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    rows = [
        (1_000_000, 3, 1, 7, 900_000, 3),
        (1_200_000, 44, 1, 7, 900_000, 3),
        (1_400_000, 45, 1, 7, 900_000, 3),
        (5_400_000, 46, 1, 7, 900_000, 3),
        (5_600_000, 47, 1, 7, 900_000, 3),
        (6_000_000, 4, 1, 7, 900_000, 3),
        (6_500_000, 7, 1, 7, 900_000, 3),
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
    assert "gui_presentation_commit_ready: 1" in out
    assert "gui_present_request_ready: 1" in out
    assert "quick_sync_item_entry: 1" in out
    assert "quick_sync_snapshot_acquired: 1" in out
    assert "screen=1 gui_snapshot->quick_sync_ms n=1 median=5.000" in out
    assert "screen=1 gui_snapshot->presentation_commit_ready_ms n=1 median=0.200" in out
    assert "screen=1 presentation_commit_ready->present_request_ready_ms n=1 median=0.200" in out
    assert "screen=1 present_request_ready->quick_sync_item_entry_ms n=1 median=4.000" in out
    assert "screen=1 quick_sync_item_entry->snapshot_acquired_ms n=1 median=0.200" in out
    assert "screen=1 quick_sync_snapshot_acquired->quick_sync_consume_ms n=1 median=0.400" in out


def test_chk28_qquickwindow_phase_trace_is_explicit_sidecar_only() -> None:
    root = Path(__file__).resolve().parents[1]
    frame_trace_source = (root / "core" / "performance" / "frame_trace.py").read_text(
        encoding="utf-8"
    )
    scene_controller = (root / "rendering" / "quick" / "scene_controller.py").read_text(
        encoding="utf-8"
    )
    reporter = (root / "tools" / "frame_trace_report.py").read_text(
        encoding="utf-8"
    )

    events = (
        "QUICK_BEFORE_FRAME_BEGIN",
        "QUICK_BEFORE_SYNCHRONIZING",
        "QUICK_AFTER_SYNCHRONIZING",
        "QUICK_BEFORE_RENDERING",
        "QUICK_BEFORE_RENDER_PASS_RECORDING",
        "QUICK_AFTER_RENDER_PASS_RECORDING",
        "QUICK_AFTER_RENDERING",
    )
    for event_name in events:
        assert event_name in frame_trace_source
        assert event_name in scene_controller

    # All native render-loop hooks are installed only behind the existing
    # explicit --frame-trace sink and use direct render-thread connections.
    connection_block = scene_controller.split("if self._frame_trace is not None:", 1)[1].split(
        "window.frameSwapped.connect(\n            self._on_frame_swapped", 1
    )[0]
    for signal_name in (
        "beforeFrameBegin",
        "beforeSynchronizing",
        "afterSynchronizing",
        "beforeRendering",
        "beforeRenderPassRecording",
        "afterRenderPassRecording",
        "afterRendering",
    ):
        assert f"window.{signal_name}.connect(" in connection_block
    assert connection_block.count("Qt.ConnectionType.DirectConnection") >= 8
    assert "RENDER_CYCLE_EVENT_IDS = frozenset(range(48, 55))" in reporter


def test_report_splits_chk28_qt_native_admission_and_render_phases(
    tmp_path: Path,
) -> None:
    trace_path = tmp_path / "chk28_qt_phase_trace.bin"
    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    # Visualizer revision 7 (aux/runtime generation 3) is admitted into Qt render
    # cycle 101. Render-cycle revisions live in a separate reporter namespace.
    rows = [
        (1_000_000, 3, 1, 7, 900_000, 3),
        (1_200_000, 44, 1, 7, 900_000, 3),
        (1_400_000, 45, 1, 7, 900_000, 3),
        (3_000_000, 48, 1, 101, 0, 3),
        (5_000_000, 49, 1, 101, 0, 3),
        (5_400_000, 46, 1, 7, 900_000, 3),
        (5_600_000, 47, 1, 7, 900_000, 3),
        (6_000_000, 4, 1, 7, 900_000, 3),
        (6_500_000, 7, 1, 7, 900_000, 3),
        (6_700_000, 50, 1, 101, 0, 3),
        (7_000_000, 51, 1, 101, 0, 3),
        (7_400_000, 52, 1, 101, 0, 3),
        (9_000_000, 8, 1, 7, 900_000, 3),
        (10_000_000, 53, 1, 101, 0, 3),
        (10_200_000, 54, 1, 101, 0, 3),
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
    assert "quick_before_frame_begin: 1" in out
    assert "screen=1 quick_render_cycles=1" in out
    assert (
        "screen=1 quick_phase=before_frame_begin->before_synchronizing n=1 "
        "median_ms=2.000"
    ) in out
    assert (
        "screen=1 quick_phase=before_synchronizing->after_synchronizing n=1 "
        "median_ms=1.700"
    ) in out
    assert (
        "screen=1 quick_admission_stage=present_request->before_frame_begin n=1 "
        "median_ms=1.600"
    ) in out
    assert (
        "screen=1 quick_admission_stage=before_synchronizing->item_entry n=1 "
        "median_ms=0.400"
    ) in out
    assert (
        "screen=1 quick_post_sync_stage=sync_ready->after_synchronizing n=1 "
        "median_ms=0.200"
    ) in out
    assert (
        "screen=1 quick_post_sync_stage=after_synchronizing->before_rendering n=1 "
        "median_ms=0.300"
    ) in out
    assert (
        "screen=1 quick_post_sync_stage=before_rendering->before_render_pass n=1 "
        "median_ms=0.400"
    ) in out
    assert (
        "screen=1 quick_post_sync_stage=before_render_pass->visualizer_render_begin n=1 "
        "median_ms=1.600"
    ) in out
