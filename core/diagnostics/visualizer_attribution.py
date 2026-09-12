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


def enable_if_admitted() -> bool:
    """Allocate the counter block once, only when the experiment is admitted.

    Called deliberately at startup after the diagnostics resolver activates. Safe
    to call more than once. Returns whether attribution is now enabled.
    """
    global _ATTR
    if _ATTR is None:
        from core.diagnostics.experiment_flags import (
            visualizer_switch_telemetry_admitted,
        )

        if visualizer_switch_telemetry_admitted():
            _ATTR = _PresentationCounters()
    return _ATTR is not None


def is_enabled() -> bool:
    return _ATTR is not None


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
    """Clear the process-level counter block (tests only)."""
    global _ATTR
    _ATTR = None


__all__ = [
    "enable_if_admitted",
    "is_enabled",
    "note_pacer_opportunity",
    "note_publication",
    "note_present_request",
    "note_window_update_fallback",
    "note_frame_swap",
    "snapshot",
    "reset_for_testing",
]
