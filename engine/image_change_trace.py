"""Passive performance tracing for one image-change admission.

The tracer is intentionally timer-free and presentation-neutral.  Callers mark
already-existing boundaries (timer/manual request, queue selection, worker
submission/completion, GUI publication, transition admission) and the tracer
emits one compact ``--perf`` record per boundary.  It never sleeps, polls, or
owns a render/update cadence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import threading
import time
from typing import Any

from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)

_TRACE_IDS = itertools.count(1)


def _format_field(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.3f}"
    text = str(value).replace("\n", " ").replace("\r", " ")
    # Paths can be enormous; retain enough identity for correlation without
    # turning every timing boundary into a multi-kilobyte log line.
    if len(text) > 180:
        text = "…" + text[-179:]
    return text.replace(" ", "_")


@dataclass(slots=True)
class ImageChangePerfTrace:
    """One accepted/requested image-change trace.

    Instances are cheap enough to create for every image-change request.  When
    ``--perf`` is disabled ``mark`` is effectively a no-op apart from updating
    local timestamps, so the same call sites can remain in production code.
    """

    origin: str
    trace_id: int = field(default_factory=lambda: next(_TRACE_IDS))
    requested_ns: int = field(default_factory=time.perf_counter_ns)
    last_stage_ns: int = field(init=False)
    last_stage: str = field(default="request", init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _enabled: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.origin = str(self.origin or "unknown")
        self.last_stage_ns = self.requested_ns
        self._enabled = bool(is_perf_metrics_enabled())
        self.mark("request")

    def mark(self, stage: str, **fields: Any) -> None:
        # One trace crosses the UI and image-compute threads.  Serialize only
        # the tiny timestamp/stage mutation so a worker that starts immediately
        # after submission cannot corrupt the previous-stage chain.
        if not self._enabled:
            return
        now_ns = time.perf_counter_ns()
        with self._lock:
            elapsed_ms = max(0.0, (now_ns - self.requested_ns) / 1_000_000.0)
            delta_ms = max(0.0, (now_ns - self.last_stage_ns) / 1_000_000.0)
            previous_stage = self.last_stage
            self.last_stage_ns = now_ns
            self.last_stage = str(stage or "unknown")
            current_stage = self.last_stage
        suffix = " ".join(
            f"{key}={_format_field(value)}"
            for key, value in fields.items()
            if value is not None
        )
        logger.info(
            "[PERF][IMAGE_CHANGE] id=%d origin=%s stage=%s elapsed_ms=%.2f "
            "delta_ms=%.2f previous=%s%s%s",
            self.trace_id,
            _format_field(self.origin),
            _format_field(current_stage),
            elapsed_ms,
            delta_ms,
            _format_field(previous_stage),
            " " if suffix else "",
            suffix,
        )

    def finish(self, outcome: str, **fields: Any) -> None:
        self.mark("finished", outcome=outcome, **fields)


__all__ = ["ImageChangePerfTrace"]
