"""GUI-thread stall stacks for ``--frame-trace`` runs (Current_Plan N1e).

The frame trace shows Visualizer presentation stalling 45-200 ms while the logical clock keeps time: the GUI
thread delivered no Visualizer wake (``frame_trace_cadence.py`` "gui_starved"). The trace cannot say what the
GUI thread was doing. This sampler can: every Visualizer GUI wake notes itself here, and when none arrives within
``threshold_s`` the sampler writes every thread's Python stack once for that stall, then the stall's total length
when wakes resume. ``late_ms`` is how late the sampler itself woke: a large value means some thread held the GIL
(a long C call), not that the GUI thread ran Python.

It exists only under ``--frame-trace`` (created and closed with the trace sink), does nothing until the first
wake, and stops waiting with a timeout once wakes stop for ``idle_s`` (a paused or retired Visualizer): no
polling at rest. It only observes.
"""
from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path


class GuiStallSampler:
    def __init__(self, path: Path, *, threshold_s: float = 0.040, idle_s: float = 2.0,
                 gui_thread_ident: int | None = None) -> None:
        self._path = Path(path)
        self._threshold_s = float(threshold_s)
        self._idle_s = float(idle_s)
        self._gui_ident = gui_thread_ident if gui_thread_ident is not None else threading.main_thread().ident
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
        """One Visualizer GUI wake (called on the GUI thread, trace runs only)."""
        self._last_wake = time.perf_counter()
        self._wake.set()

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
