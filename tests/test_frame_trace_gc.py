"""Garbage collections on the opt-in frame trace: recorded only when ``--frame-trace`` is admitted (zero work otherwise)."""
from __future__ import annotations

import gc
import struct

from core.performance import frame_trace
from core.performance.frame_trace import FrameTraceEvent

_RECORD = struct.Struct("<QHhqqq")
_HEADER = struct.Struct("<8sHHI")


def test_without_the_trace_no_gc_callback_exists():
    assert frame_trace.start_frame_trace(".", [], native_argv=()) is None
    assert frame_trace._gc_trace_callback not in gc.callbacks


def test_an_admitted_trace_records_every_collection_edge_and_unhooks_on_close(tmp_path):
    sink = frame_trace.start_frame_trace(tmp_path, ["--frame-trace"], native_argv=())
    try:
        assert sink is not None and frame_trace._gc_trace_callback in gc.callbacks
        gc.collect(1)
        gc.collect(2)
    finally:
        frame_trace.close_frame_trace()
    assert frame_trace._gc_trace_callback not in gc.callbacks
    raw = (tmp_path / "screensaver_frame_trace.bin").read_bytes()
    records = [_RECORD.unpack_from(raw, _HEADER.size + i * _RECORD.size)
               for i in range((len(raw) - _HEADER.size) // _RECORD.size)]
    edges = [(event, aux) for _ts, event, _screen, _revision, _logical, aux in records
             if event in (FrameTraceEvent.GC_BEGIN, FrameTraceEvent.GC_END)]
    assert (FrameTraceEvent.GC_BEGIN, 2) in edges and (FrameTraceEvent.GC_END, 2) in edges
    assert (FrameTraceEvent.GC_BEGIN, 1) in edges and (FrameTraceEvent.GC_END, 1) in edges
