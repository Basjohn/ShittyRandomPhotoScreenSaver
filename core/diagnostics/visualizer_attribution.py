"""Opt-in GUI-side presentation attribution counters (P4 H1/H2 attribution).

Authority: ``Docs/Future_Work/Visualizer_Post_Switch_Performance.md`` (attribution).
Guardrail: ``Docs/Guardrails/Performance_Optimization_Contract.md``.

The P4 matrix established a swap-sensitive presentation/event-loop tail. To
distinguish H1 (stale render-host/GL/scene ownership accumulating across switches)
from H2 (ownership clean but GUI/Quick presentation/update work amplified or
duplicated after switching), we count the distinct presentation-request edges
**separately** — never collapsed into one generic "invalidation" metric.

These are GUI-thread primitive counters on already-existing execution edges. They
are strictly opt-in: the process-level counter block is allocated only when the
experiment admission is active (``--viz-switch-telemetry`` / ``--abc-drive``); until
then every ``note_*`` is a single ``is None`` check and ordinary Standard/MC runtime
pays nothing new — no allocation, no lock, no timer, no logging, no ``glGet*``.

All edges here run on the GUI thread (the presentation pump, the retained-present
request, the window-update fallback, and Qt's ``frameSwapped``, which is delivered
on the GUI thread), so no lock is required. The render-thread sync/render/draw
counts are read separately from the existing per-node telemetry, not incremented
here.
"""

from __future__ import annotations

from bisect import bisect_right
from threading import get_ident

# Fixed latency buckets (nanosecond upper bounds), 0.5 us .. 100 ms. Bucketing is
# one bisect + one increment per sample: no per-draw allocation, no lock. The final
# bucket (index == len) captures anything above the top bound.
_FENCE_BUCKET_NS: tuple[int, ...] = (
    500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000,
    200_000, 500_000, 1_000_000, 2_000_000, 5_000_000,
    10_000_000, 20_000_000, 50_000_000, 100_000_000,
)


class _EdgeTiming:
    """Bounded CPU-time distribution for one synchronous fence edge.

    Written only from the Quick render thread (the sole caller of the fence), read
    only at experiment/scored-window boundaries, so it needs no lock: there is a
    single writer, and a boundary read that races one in-flight sample is harmless
    for bounded statistics.
    """

    __slots__ = ("count", "total_ns", "max_ns", "buckets", "thread_id")

    def __init__(self) -> None:
        self.count = 0
        self.total_ns = 0
        self.max_ns = 0
        self.buckets = [0] * (len(_FENCE_BUCKET_NS) + 1)
        self.thread_id: int | None = None

    def note(self, elapsed_ns: int) -> None:
        self.count += 1
        self.total_ns += elapsed_ns
        if elapsed_ns > self.max_ns:
            self.max_ns = elapsed_ns
        self.buckets[bisect_right(_FENCE_BUCKET_NS, elapsed_ns)] += 1
        self.thread_id = get_ident()

    def snapshot(self) -> dict[str, object]:
        return {
            "count": self.count,
            "total_ns": self.total_ns,
            "max_ns": self.max_ns,
            "mean_ns": (self.total_ns / self.count) if self.count else 0.0,
            "buckets": list(self.buckets),
            "thread_id": self.thread_id,
        }


class _FenceTiming:
    """Per-draw ``_InheritedGlState.capture()`` / ``restore()`` CPU-time cost."""

    __slots__ = ("capture", "restore")

    def __init__(self) -> None:
        self.capture = _EdgeTiming()
        self.restore = _EdgeTiming()

    def note_capture(self, elapsed_ns: int) -> None:
        self.capture.note(elapsed_ns)

    def note_restore(self, elapsed_ns: int) -> None:
        self.restore.note(elapsed_ns)

    def snapshot(self) -> dict[str, object]:
        return {
            "capture": self.capture.snapshot(),
            "restore": self.restore.snapshot(),
            "bucket_upper_ns": list(_FENCE_BUCKET_NS),
        }


class _PresentationCounters:
    __slots__ = (
        "pacer_opportunities",
        "publications",
        "present_requests",
        "window_update_fallbacks",
        "frame_swaps",
    )

    def __init__(self) -> None:
        self.pacer_opportunities = 0
        self.publications = 0
        self.present_requests = 0
        self.window_update_fallbacks = 0
        self.frame_swaps = 0


# Process-level, allocated only when admitted. None => disabled => zero cost.
_ATTR: _PresentationCounters | None = None
_FENCE: _FenceTiming | None = None


def enable_if_admitted() -> bool:
    """Allocate the counter blocks once, only when the experiment is admitted.

    Called deliberately at startup after the diagnostics resolver activates. Safe
    to call more than once. Returns whether attribution is now enabled.
    """
    global _ATTR, _FENCE
    if _ATTR is None:
        from core.diagnostics.experiment_flags import (
            visualizer_switch_telemetry_admitted,
        )

        if visualizer_switch_telemetry_admitted():
            _ATTR = _PresentationCounters()
            _FENCE = _FenceTiming()
    return _ATTR is not None


def is_enabled() -> bool:
    return _ATTR is not None


def fence_timing() -> _FenceTiming | None:
    """Return the per-draw fence-timing accumulator, or None when disabled.

    The render host reads this once per ``render()`` (once per draw) and, only when
    non-None, times the existing ``_InheritedGlState.capture()``/``restore()`` with
    ``time.perf_counter_ns()``. Disabled == None == no timing calls at all.
    """
    return _FENCE


def note_pacer_opportunity() -> None:
    """One presentation-pump opportunity (``owner.sync_present()`` entry)."""
    counters = _ATTR
    if counters is not None:
        counters.pacer_opportunities += 1


def note_publication() -> None:
    """One successful snapshot publication (``sync_latest()`` returned True)."""
    counters = _ATTR
    if counters is not None:
        counters.publications += 1


def note_present_request() -> None:
    """One retained item present request caused by a publication.

    ``scene_controller.request_visualizer_present()`` -> ``item.update()``.
    """
    counters = _ATTR
    if counters is not None:
        counters.present_requests += 1


def note_window_update_fallback() -> None:
    """One fallback ``QQuickWindow.update()`` request (retirement/invalidation path)."""
    counters = _ATTR
    if counters is not None:
        counters.window_update_fallbacks += 1


def note_frame_swap() -> None:
    """One actual presented frame (Qt ``frameSwapped``, GUI thread)."""
    counters = _ATTR
    if counters is not None:
        counters.frame_swaps += 1


def snapshot() -> dict[str, int] | None:
    """Return the current counter values, or ``None`` when disabled."""
    counters = _ATTR
    if counters is None:
        return None
    return {
        "pacer_opportunities": counters.pacer_opportunities,
        "publications": counters.publications,
        "present_requests": counters.present_requests,
        "window_update_fallbacks": counters.window_update_fallbacks,
        "frame_swaps": counters.frame_swaps,
    }


def reset_for_testing() -> None:
    """Clear the process-level counter blocks (tests only)."""
    global _ATTR, _FENCE
    _ATTR = None
    _FENCE = None


__all__ = [
    "enable_if_admitted",
    "is_enabled",
    "fence_timing",
    "note_pacer_opportunity",
    "note_publication",
    "note_present_request",
    "note_window_update_fallback",
    "note_frame_swap",
    "snapshot",
    "reset_for_testing",
]
