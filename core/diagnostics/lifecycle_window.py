"""Startup and teardown are lifecycle windows, not stall points (operator rule 2026-09-29).

A display runtime starting up or tearing down is expected to spike: windows, scene
graphs, programs and images are all being built or dropped at once. Counting those
frames as stalls made every performance review rediscover the same non-problem.

A window opens at cold start, when Settings pauses the runtime and when any display
runtime starts tearing down (Settings, exit, monitor or layout replacement); it closes
when the next generation's coordinated reveal completes (that reveal has its own stall
deadline, so a window cannot stay open indefinitely). Stall and spike diagnostics neither
warn nor count inside it. The one lifecycle concern is poisoning: frames after the window
closes are ordinary steady-state frames, so startup cost that bleeds past the reveal
still counts.

Plain module state: reading it is a global lookup, so hot diagnostics may consult it on
every tick. Only ``--frame-trace`` adds work (one record per edge).
"""
from __future__ import annotations

from core.performance.frame_trace import FrameTraceEvent, current_frame_trace

_open = False
_reason = ""


def open_window(reason: str) -> None:
    """A runtime starts up or tears down: stop counting stalls until the next reveal."""
    global _open, _reason
    if _open:
        return
    _open, _reason = True, str(reason)
    _trace(FrameTraceEvent.LIFECYCLE_BEGIN)


def close_window() -> None:
    """The generation's coordinated reveal completed: frames count again from here."""
    global _open, _reason
    if not _open:
        return
    _open, _reason = False, ""
    _trace(FrameTraceEvent.LIFECYCLE_END)


def is_open() -> bool:
    return _open


def reason() -> str:
    return _reason


def _trace(event: FrameTraceEvent) -> None:
    sink = current_frame_trace()
    if sink is not None:
        sink.record(event)
