"""The Visualizer's one authored clock (Architecture Checklist AC-12). Qt-free, import-light.

Every logical step, the beat engine's smoothing, play ramp, keepalive and event ages, the capture timestamps the engine
compares against, and the view-motion timestamps the GUI thread records read ``authored_now()``. It is monotonic
(``time.perf_counter``: QueryPerformanceCounter on Windows, system-wide), so a wall-clock step (time sync, a manual
change) can no longer inject a dt jump or a negative dt. The logical runtime exposes it
(``widgets.spotify_visualizer.logical_runtime.authored_now``); this module only keeps it importable without the
Visualizer package (the display manager and the Quick renderer read it too).

Offline replays (the recorded-clip driver, the Studios' recorded-input workers) pin it with ``pinned_authored_clock``
(through ``feature_replay.deterministic_clock``). Wall time stays only where a value is a human-facing date or is
compared with another process's wall stamp.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

authored_clock_source: Callable[[], float] = time.perf_counter


def authored_now() -> float:
    """Seconds on the Visualizer's monotonic authored clock."""
    return authored_clock_source()


class pinned_authored_clock:
    """Context manager: the authored clock reads ``source`` until exit (offline replays and tests only)."""

    def __init__(self, source: Callable[[], float]) -> None:
        self._source = source
        self._saved: Optional[Callable[[], float]] = None

    def __enter__(self) -> Callable[[], float]:
        global authored_clock_source
        self._saved = authored_clock_source
        authored_clock_source = self._source
        return self._source

    def __exit__(self, *exc: object) -> None:
        global authored_clock_source
        authored_clock_source = self._saved if self._saved is not None else time.perf_counter
