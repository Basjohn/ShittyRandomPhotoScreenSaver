"""Fade Coordinator - Centralized overlay fade synchronization.

Replaces scattered fade logic across WidgetManager, DisplayWidget, BaseOverlayWidget.
Uses lock-free atomic operations and SPSC queues for state management.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from core.logging.logger import get_logger
from utils.lockfree.spsc_queue import SPSCQueue

logger = get_logger(__name__)


class FadeState(Enum):
    """Fade coordination states."""
    IDLE = auto()      # Waiting for participants
    READY = auto()     # Compositor ready, waiting for all participants
    FADING = auto()    # Fades in progress
    COMPLETE = auto()  # All fades complete


@dataclass
class FadeRequest:
    """Request for fade coordination."""
    overlay_name: str
    starter: Callable[[], None]
    timestamp: float = field(default_factory=time.time)


class FadeCoordinator:
    """Centralized fade coordination using lock-free atomic operations.
    
    All operations are thread-safe without locks:
    - State stored in simple attributes (atomic under GIL)
    - No threading.Lock() used - compliant with threading policies
    - UI thread owns all state mutations
    """
    
    def __init__(self, screen_index: int = 0):
        self._screen_index = screen_index
        
        # Atomic state - simple attributes (atomic under GIL, no locks needed)
        self._state: FadeState = FadeState.IDLE
        self._compositor_ready: bool = False
        
        # Participants tracking (UI thread only)
        self._participants: set[str] = set()
        self._pending: dict[str, Callable[[], None]] = {}
        self._completed: set[str] = set()
        self._active_fades: set[str] = set()
        self._startup_holds: set[str] = set()
        self._completion_callbacks: list[Callable[[], None]] = []
        self._generation: int = 0
        self._fade_started: bool = False
        self._last_sequence_log: tuple | None = None
        
        # Lock-free queue for cross-thread fade requests
        self._request_queue: SPSCQueue[FadeRequest] = SPSCQueue(64)
        
        logger.debug("[FADE_COORD] Initialized for screen=%s", screen_index)
    
    def register_participant(self, name: str) -> None:
        """Register a widget as fade participant."""
        self._participants.add(name)
        logger.debug("[FADE_COORD] screen=%s registered: %s", self._screen_index, name)

    def add_startup_hold(self, name: str) -> None:
        """Prevent startup fades until a named critical prerequisite is terminal."""

        name = str(name or "").strip()
        if not name:
            return
        self._startup_holds.add(name)
        self._log_startup_sequence()

    def release_startup_hold(self, name: str) -> None:
        """Release a named prerequisite and start queued fades when unblocked."""

        self._startup_holds.discard(str(name or "").strip())
        self._log_startup_sequence()
        self._try_start_fades()

    def add_completion_callback(self, callback: Callable[[], None]) -> None:
        """Run ``callback`` once all coordinated fade animations truly finish."""

        if self._state == FadeState.COMPLETE:
            try:
                callback()
            except Exception:
                logger.debug(
                    "[FADE_COORD] Completion callback failed after completion",
                    exc_info=True,
                )
            return
        self._completion_callbacks.append(callback)

    def get_generation(self) -> int:
        """Return the reset generation used to reject stale animation signals."""

        return self._generation
    
    def request_fade(self, name: str, starter: Callable[[], None]) -> bool:
        """Request fade coordination for a widget.
        
        Before compositor-ready, requests queue so startup participants can
        reveal together once the first frame is real. After compositor-ready,
        any widget that becomes genuinely ready for display should be allowed
        to fade in immediately instead of waiting for unrelated participants.
        """
        # Auto-register if not already registered
        if name not in self._participants:
            logger.warning("[FADE_COORD] %s not registered, auto-registering", name)
            self._participants.add(name)
        
        # Store locally for immediate check
        self._pending[name] = starter
        
        # After compositor-ready, a widget requesting fade is declaring itself
        # ready for visible reveal. Start queued reveals as soon as critical
        # startup holds have all been released.
        self._try_start_fades()
        if name in self._active_fades or name in self._completed:
            return True
        
        logger.debug("[FADE_COORD] screen=%s %s queued (pending=%d, expected=%d)",
                    self._screen_index, name, len(self._pending), len(self._participants))
        return False
    
    def signal_compositor_ready(self) -> None:
        """Signal that compositor is ready to display (first frame rendered)."""
        if self._compositor_ready:
            return
        
        self._compositor_ready = True
        old_state = self._state
        self._state = FadeState.READY
        
        logger.info("[FADE_COORD] screen=%s compositor ready (state=%s->READY)",
                   self._screen_index, old_state.name)
        
        self._log_startup_sequence()
        self._try_start_fades()

    def _try_start_fades(self) -> None:
        """Start pending fades only after first-frame and critical hold readiness."""

        if not self._compositor_ready:
            return
        if self._startup_holds:
            return
        if self._pending:
            self._start_all_fades()

    def _start_all_fades(self) -> None:
        """Start all pending fades."""
        if not self._pending:
            return
        
        self._state = FadeState.FADING
        pending = dict(self._pending)
        self._pending.clear()
        self._fade_started = True
        
        logger.info("[FADE_COORD] screen=%s starting %d fades: %s",
                   self._screen_index, len(pending), sorted(pending.keys()))
        self._log_startup_sequence()
        
        # Execute all starters (no locks held - lock-free)
        for name, starter in pending.items():
            self._active_fades.add(name)
            try:
                starter()
                logger.debug("[FADE_COORD] screen=%s %s fade started", self._screen_index, name)
            except Exception as e:
                logger.error("[FADE_COORD] screen=%s %s fade failed: %s", self._screen_index, name, e)
                self.mark_fade_complete(name, generation=self._generation)

        self._finish_if_complete()

    def mark_fade_complete(self, name: str, *, generation: int | None = None) -> None:
        """Record the real end of one overlay fade animation."""

        if generation is not None and int(generation) != self._generation:
            return
        if name not in self._participants:
            return
        self._active_fades.discard(name)
        self._completed.add(name)
        logger.debug(
            "[FADE_COORD] screen=%s %s fade completed",
            self._screen_index,
            name,
        )
        self._finish_if_complete()

    def _finish_if_complete(self) -> None:
        if not self._compositor_ready or self._startup_holds:
            return
        if self._pending or self._active_fades:
            return
        # Completion describes the fades that actually started. Enabled
        # overlays may remain data-unavailable indefinitely; they must not
        # strand optional GL warmup. A later request re-enters FADING and is
        # tracked normally before subsequent warmup slices may run.
        if not self._fade_started or not self._completed:
            return
        if self._state == FadeState.COMPLETE:
            return

        self._state = FadeState.COMPLETE
        logger.info("[FADE_COORD] screen=%s all fades complete", self._screen_index)
        self._log_startup_sequence()
        callbacks = list(self._completion_callbacks)
        self._completion_callbacks.clear()
        for callback in callbacks:
            try:
                callback()
            except Exception:
                logger.debug(
                    "[FADE_COORD] Completion callback failed",
                    exc_info=True,
                )

    def _log_startup_sequence(self) -> None:
        snapshot = (
            bool(self._compositor_ready),
            bool(
                self._compositor_ready
                and "critical_gl_startup" not in self._startup_holds
            ),
            tuple(sorted(self._startup_holds)),
            bool(self._fade_started),
            self._state == FadeState.COMPLETE,
        )
        if snapshot == self._last_sequence_log:
            return
        self._last_sequence_log = snapshot
        logger.info(
            "[STARTUP_SEQUENCE] screen=%s first_frame_ready=%s "
            "critical_gl_ready=%s fade_holds=%s fade_started=%s "
            "fade_completed=%s deferred_gl_warmup_started=%s",
            self._screen_index,
            snapshot[0],
            snapshot[1],
            list(snapshot[2]),
            snapshot[3],
            snapshot[4],
            False,
        )
    
    def reset(self, *, clear_participants: bool = False) -> None:
        """Reset coordination state for a new cycle.

        Args:
            clear_participants: When True, forget the previously registered
                overlay participants as well. Widget rebuild/setup cycles need
                this so stale participant names do not block immediate fade
                starts after the compositor is already ready.
        """
        self._state = FadeState.IDLE
        self._compositor_ready = False
        self._pending.clear()
        self._completed.clear()
        self._active_fades.clear()
        self._startup_holds.clear()
        self._completion_callbacks.clear()
        self._generation += 1
        self._fade_started = False
        self._last_sequence_log = None
        if clear_participants:
            self._participants.clear()
        logger.debug("[FADE_COORD] screen=%s reset", self._screen_index)

    def cleanup(self) -> None:
        """Release terminal callback and queued-starter ownership.

        A ``FadeCoordinator`` belongs to one ``WidgetManager`` runtime.  Its
        completion callbacks and pending starter wrappers can retain that
        manager, so terminal teardown must not leave the coordinator as a
        diagnostic Python root waiting for cyclic collection.
        """

        self.reset(clear_participants=True)
        self._request_queue.clear()
    
    def get_state(self) -> FadeState:
        return self._state
    
    def describe(self) -> dict:
        return {
            "screen": self._screen_index,
            "state": self._state.name,
            "compositor_ready": self._compositor_ready,
            "participants": sorted(self._participants),
            "pending": sorted(self._pending.keys()),
            "completed": sorted(self._completed),
            "active": sorted(self._active_fades),
            "startup_holds": sorted(self._startup_holds),
            "generation": self._generation,
            "fade_started": self._fade_started,
            "fade_completed": self._state == FadeState.COMPLETE,
        }
