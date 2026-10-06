"""Opt-in GUI-thread stall stacks for traced steady-state investigation.

The binary ``--frame-trace`` is intentionally low-observer-effect. Full Python
stack snapshots are much heavier: ``sys._current_frames()`` plus
``traceback.format_stack()`` allocates and linecache-walks every live Python
thread. Those snapshots therefore require the separate
``--gui-stall-stacks`` admission in addition to ``--frame-trace``.

Startup, Settings replacement and teardown are binding lifecycle windows, not
stall points. While that window is open this sampler disarms completely: no
stack capture, no stall count and no carry-over silence interval. The next GUI
wake after the window closes starts a fresh steady-state observation period.

Once admitted and outside a lifecycle window, every Visualizer GUI wake notes
itself here. If none arrives within ``threshold_s`` the sampler writes every
thread's Python stack once for that stall, then the stall's total length when
wakes resume. ``late_ms`` is how late the sampler itself woke: a large value
means some thread held the GIL (a long C call), not that the GUI thread ran
Python. It still does nothing before the first wake and returns to indefinite
wait after ``idle_s`` without wakes.
"""
from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable


class GuiStallSampler:
    def __init__(
        self,
        path: Path,
        *,
        threshold_s: float = 0.040,
        idle_s: float = 2.0,
        gui_thread_ident: int | None = None,
        suppress_predicate: Callable[[], bool] | None = None,
    ) -> None:
        self._path = Path(path)
        self._threshold_s = float(threshold_s)
        self._idle_s = float(idle_s)
        self._gui_ident = gui_thread_ident if gui_thread_ident is not None else threading.main_thread().ident
        if suppress_predicate is None:
            from core.diagnostics.lifecycle_window import is_open as lifecycle_window_is_open

            suppress_predicate = lifecycle_window_is_open
        self._suppress_predicate = suppress_predicate
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._closed = False
        self._last_wake = 0.0
        self._stalls = 0
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._loop, name="gui_stall_sampler", daemon=True)
        self._thread.start()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def stalls(self) -> int:
        return self._stalls

    def note_wake(self) -> None:
        """One Visualizer GUI wake (called on the GUI thread, admitted diagnostics only)."""
        if self._suppressed():
            # Wake the sampler so an already-active steady-state observation can
            # disarm immediately. Do not seed a post-lifecycle silence interval.
            self._last_wake = 0.0
            self._wake.set()
            return
        self._last_wake = time.perf_counter()
        self._wake.set()

    def _suppressed(self) -> bool:
        try:
            return bool(self._suppress_predicate())
        except Exception:
            # Diagnostics must fail closed rather than perturb product runtime.
            return True

    def close(self, timeout: float = 2.0) -> None:
        with self._lock:
            self._closed = True
        self._wake.set()
        self._thread.join(timeout)

    def _loop(self) -> None:
        active = False
        reported_at = None
        while True:
            waited_from = time.perf_counter()
            woke = self._wake.wait(self._threshold_s if active else None)
            with self._lock:
                if self._closed:
                    return
            now = time.perf_counter()
            if self._suppressed():
                # Lifecycle work is intentionally noisy and already has its own
                # deadline/trace markers. Never format all-thread stacks here,
                # and never carry its silence into the next steady-state sample.
                self._wake.clear()
                self._last_wake = 0.0
                active = False
                reported_at = None
                continue
            if woke:
                self._wake.clear()
                if reported_at is not None:
                    self._write(f"stall_end total_ms={(self._last_wake - reported_at[0]) * 1000.0:.1f}\n\n")
                    reported_at = None
                active = True
                continue
            silence = now - self._last_wake
            if silence >= self._idle_s:
                if reported_at is not None:
                    self._write(f"stall_end total_ms>={silence * 1000.0:.1f} (wakes stopped)\n\n")
                    reported_at = None
                active = False
                continue
            if silence >= self._threshold_s and reported_at is None:
                late_ms = max(0.0, (now - waited_from - self._threshold_s) * 1000.0)
                reported_at = (self._last_wake,)
                self._stalls += 1
                self._write(self._describe(silence, late_ms))

    def _describe(self, silence: float, late_ms: float) -> str:
        names = {thread.ident: thread.name for thread in threading.enumerate()}
        lines = [f"=== gui_stall wall={time.strftime('%Y-%m-%d %H:%M:%S')} perf={time.perf_counter():.6f} "
                 f"since_wake_ms={silence * 1000.0:.1f} sampler_late_ms={late_ms:.1f}\n"]
        frames = sys._current_frames()
        ordered = sorted(frames.items(), key=lambda item: item[0] != self._gui_ident)
        for ident, frame in ordered:
            if ident == threading.get_ident():
                continue
            label = "GUI" if ident == self._gui_ident else names.get(ident, str(ident))
            lines.append(f"--- thread {label}\n")
            lines.extend(traceback.format_stack(frame, limit=24))
        return "".join(lines)

    def _write(self, text: str) -> None:
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(text)
        except OSError:
            pass


__all__ = ["GuiStallSampler"]
