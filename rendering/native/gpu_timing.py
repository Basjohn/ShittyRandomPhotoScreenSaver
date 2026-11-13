"""The per-pass GPU timer's Python face (D5.3's first service, D8 plus 2; Current_Plan.md item 8b, N2.6).

The timer lives in the native core's frame driver (``native/core/src/gpu_timer.h``): while a host's timer is on, every
pass the core records is bracketed whole (raw timestamps on Vulkan, ``GL_TIME_ELAPSED`` on OpenGL), and QRhi's own
whole-frame figure is read where the host's QRhi was created with timestamps (the only figure QRhi gives on D3D11 and
D3D12). Results are read latched, frames later, never waited for, and queued in the core; ``Host.gpu_samples()`` drains
the queue on the GUI thread. While the timer is off the core holds no timer and no query object.

This module turns drained samples into frame-trace records (``core.performance.frame_trace``), in the form the frame
trace's other durations take and ``tools/frame_trace_report.py`` reads: one record per figure, its duration in
nanoseconds (the unit ``GL_TIME_ELAPSED`` reports), summarised there as median, p95 and p99 milliseconds per pass kind.

Admission: ``--gpu-pass-timing`` (``core.diagnostics.experiment_flags``), and only with a frame trace to write into
(``gpu_pass_timing_wanted``). Nothing in the product attaches a host yet (N2.7 adds the backend owner, which switches the
timer on when this admits it and drains it at a GUI-thread frame edge it already has).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

#: The figure kinds (``GpuPassKind`` in ``gpu_timer.h``); the frame trace's ``logical_timestamp_ns`` field carries them.
GPU_PASS_KINDS = {0: "frame", 1: "probe", 2: "surface", 3: "load"}
#: The timer's options (``GpuTimerConfig``): ``keep_when_off`` and ``wait_for_results`` are negative controls.
TIMER_OPTIONS = ("enabled", "keep_when_off", "wait_for_results")
#: The known-cost pass's options (``LoadConfig`` in ``load_pass.h``); ``timing="before"`` is a negative control.
LOAD_OPTIONS = ("width", "height", "draws", "iterations", "timing")
LOAD_TIMINGS = ("pass", "before")


@dataclass(frozen=True)
class GpuSample:
    """One figure: ``kind`` (``GPU_PASS_KINDS``), the frame edge the pass was recorded at (-1 for QRhi's frame figure,
    whose frame Qt does not name), the edge its result was read at, and the GPU time in nanoseconds."""

    kind: int
    frame: int
    read_at: int
    nanoseconds: int

    @property
    def kind_name(self) -> str:
        return GPU_PASS_KINDS.get(self.kind, str(self.kind))

    @property
    def milliseconds(self) -> float:
        return self.nanoseconds / 1_000_000.0

    @property
    def latency(self) -> int | None:
        """Frames between the pass's recording and the read of its result (None for a frame figure)."""
        return None if self.frame < 0 else self.read_at - self.frame


def samples_from(raw: Iterable[Any]) -> tuple[GpuSample, ...]:
    """The module's rows (``host_gpu_samples``: kind, frame, read_at, nanoseconds) as samples."""
    return tuple(GpuSample(int(kind), int(frame), int(read_at), int(ns)) for kind, frame, read_at, ns in raw)


def gpu_pass_timing_wanted(flags: Any, sink: Any) -> bool:
    """Whether a host's timer is switched on: admitted by ``--gpu-pass-timing`` and a frame trace exists to write into.
    Either missing, the timer stays off and the core holds no query object."""
    return bool(getattr(flags, "gpu_pass_timing", False)) and sink is not None


def write_to_frame_trace(sink: Any, samples: Iterable[GpuSample], *, screen_index: int = -1) -> int:
    """Each sample as one frame-trace record (``FrameTraceEvent.GPU_PASS_TIME``, or ``GPU_FRAME_TIME`` for QRhi's
    whole-frame figure): ``auxiliary`` the GPU time in nanoseconds, ``revision`` the frame edge the pass was recorded at
    (for a frame figure, the edge it was read at), ``logical_timestamp_ns`` the kind (``GPU_PASS_KINDS``). The record's
    own time is when it was written (the drain), not when the GPU ran. Returns the records the sink took (a full ring
    drops, as for every trace producer)."""
    from core.performance.frame_trace import FrameTraceEvent

    written = 0
    for sample in samples:
        frame_figure = sample.kind == 0
        event = FrameTraceEvent.GPU_FRAME_TIME if frame_figure else FrameTraceEvent.GPU_PASS_TIME
        revision = sample.read_at if frame_figure else sample.frame
        if sink.record(event, screen_index=int(screen_index), revision=int(revision),
                       logical_timestamp_ns=int(sample.kind), auxiliary=int(sample.nanoseconds)):
            written += 1
    return written


__all__ = ["GPU_PASS_KINDS", "GpuSample", "LOAD_OPTIONS", "LOAD_TIMINGS", "TIMER_OPTIONS", "gpu_pass_timing_wanted",
           "samples_from", "write_to_frame_trace"]
