"""All-thread stack dump on a stalled runtime (re)construction (H1 diagnostic).

The dual-display replacement generation intermittently **hangs** — it does not
crash — during screen-1 Media/native family construction (see
``H_Post_Cutover_Runtime_Reality_Corrections.md`` §3, ledger O-001/O-002/O-004).
The main thread simply stops emitting log records; the process lingers and must
be killed manually.

The existing ``[MEDIA_NATIVE][H1]`` breadcrumbs proved the async log queue drops
nothing at the failure boundary (a full 498-object teardown was written intact),
so the truncation is real: the main thread genuinely stops between two trivial
breadcrumbs, with no live COM call and no blocking log. INFO/DEBUG staging cannot
name a blocking call that emits nothing, so this arms a ``faulthandler`` watchdog
around a bounded construction window. If the window does not complete within
``timeout_s``, faulthandler dumps **every** thread's Python stack (main + io_pool
+ render/Qt) to a dedicated file, naming the exact frame each thread is wedged
on. It is one-shot per arm and always disarmed on success, so it never fires
during steady-state running.

This owns no lifecycle and changes no product behaviour: it only observes.
"""
from __future__ import annotations

import faulthandler
import sys
import threading
import time
from pathlib import Path
from typing import Optional, TextIO

from core.logging.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_armed_label: Optional[str] = None
_dump_file: Optional[TextIO] = None


def dump_path() -> Path:
    """Return the dedicated stack-dump file path (best-effort ``logs/``)."""

    base = Path("logs")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        base = Path.cwd()
    return base / "hang_stacks.log"


def arm(label: str, *, timeout_s: float = 20.0) -> None:
    """Arm a one-shot all-thread stack dump if the caller does not disarm in time.

    ``timeout_s`` must comfortably exceed a healthy (re)construction (the barrier
    completes in a few hundred ms), so a fired dump means a genuine stall.
    """

    global _armed_label, _dump_file
    with _lock:
        try:
            # Native crash dumps (access violations) also print a C-level stack.
            faulthandler.enable(file=sys.stderr, all_threads=True)
        except Exception:
            pass
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        if _dump_file is not None:
            try:
                _dump_file.close()
            except Exception:
                pass
            _dump_file = None

        target: TextIO
        try:
            handle = open(dump_path(), "a", encoding="utf-8")
            handle.write(
                "\n===== HANG WATCHDOG ARMED label=%s timeout_s=%.1f ts=%s =====\n"
                % (label, timeout_s, time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            handle.flush()
            _dump_file = handle
            target = handle
        except Exception:
            logger.debug("[HANG_WATCHDOG] Could not open dump file", exc_info=True)
            _dump_file = None
            target = sys.stderr

        _armed_label = label
        try:
            faulthandler.dump_traceback_later(
                max(1.0, float(timeout_s)),
                repeat=False,
                file=target,
                exit=False,
            )
            logger.info(
                "[HANG_WATCHDOG] Armed for '%s' (timeout=%.1fs, dump=%s)",
                label,
                timeout_s,
                dump_path(),
            )
        except Exception:
            logger.debug("[HANG_WATCHDOG] Failed to arm faulthandler", exc_info=True)


def disarm(label: str = "") -> None:
    """Cancel the pending stack dump after a healthy construction completes."""

    global _armed_label, _dump_file
    with _lock:
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        handle = _dump_file
        _dump_file = None
        previous = _armed_label
        _armed_label = None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        if previous is not None:
            logger.debug("[HANG_WATCHDOG] Disarmed '%s'", previous or label)


__all__ = ["arm", "disarm", "dump_path"]
