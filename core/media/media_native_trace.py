"""One-shot Media construction/activation stage breadcrumbs (H1 diagnostic).

Bounded instrumentation for the dual-display *replacement-generation* native
termination recorded in ``H_Post_Cutover_Runtime_Reality_Corrections.md`` §3:
the old two-display generation tears down cleanly, the replacement starts, screen
0 completes, and the process dies during screen 1's Media/native activation
(``Windows GSMTC controller initialized`` -> Media poll timer -> comtypes/Core
Audio release), with no clean Python return.

Because the failure is native, the decisive evidence is *which* Media component
reaches *which* stage last, on *which thread*, in *which runtime generation*.
This tracer emits at most one line per ``(generation, screen, component, stage)``
so a replacement generation re-emits its full timeline while steady-state
polling, reactivation and re-admission never spam. It performs **no** polling and
**no** per-frame logging, and it owns no lifecycle: it only records.

The tracer is intentionally free of Media/Qt imports so the native owners can
call it from any thread without dragging presentation state onto that thread.
"""
from __future__ import annotations

import threading
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)

_seen: set[tuple[str, str, str, str]] = set()
_lock = threading.Lock()


def reset_media_native_trace_for_tests() -> None:
    """Clear the one-shot de-dup set (test isolation only)."""

    with _lock:
        _seen.clear()


def trace_media_native_stage(
    *,
    component: str,
    stage: str,
    generation: Any = None,
    screen: Any = None,
    detail: str = "",
    once: bool = True,
) -> None:
    """Record one bounded Media-native construction/activation breadcrumb.

    ``component`` is the owner/lease under construction (e.g. ``media``,
    ``spotify_volume``, ``mute_button``, ``media_family``). ``stage`` is a short
    verb-phrase such as ``model_construct_begin`` / ``activate_complete``. The
    calling thread identity is always recorded because a cross-generation
    thread/apartment mismatch is the leading native hypothesis.

    ``once`` de-duplicates on ``(generation, screen, component, stage)``; pass
    ``once=False`` only for a stage that is genuinely expected to repeat and is
    not on a poll/frame cadence.
    """

    if once:
        key = (str(generation), str(screen), str(component), str(stage))
        with _lock:
            if key in _seen:
                return
            _seen.add(key)
    thread = threading.current_thread()
    logger.info(
        "[MEDIA_NATIVE][H1] gen=%s screen=%s component=%s stage=%s thread=%s(%s)%s",
        generation,
        screen,
        component,
        stage,
        thread.name,
        thread.ident,
        (" " + detail) if detail else "",
    )


__all__ = ["reset_media_native_trace_for_tests", "trace_media_native_stage"]
