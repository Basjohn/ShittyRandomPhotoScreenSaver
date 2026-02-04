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
        
        # Lock-free queue for cross-thread fade requests
        self._request_queue: SPSCQueue[FadeRequest] = SPSCQueue(64)
        
        logger.debug("[FADE_COORD] Initialized for screen=%s", screen_index)
    
    def register_participant(self, name: str) -> None:
        """Register a widget as fade participant."""
        self._participants.add(name)
        logger.debug("[FADE_COORD] screen=%s registered: %s", self._screen_index, name)
    
    def request_fade(self, name: str, starter: Callable[[], None]) -> bool:
        """Request fade coordination for a widget.
        
        If compositor ready and all participants registered, starts fade immediately.
        Otherwise queues for later batch start.
        """
        # Auto-register if not already registered
        if name not in self._participants:
            logger.warning("[FADE_COORD] %s not registered, auto-registering", name)
            self._participants.add(name)
        
        # Store locally for immediate check
        self._pending[name] = starter
        
        # Check if we can start immediately (compositor ready + all participants)
        if self._compositor_ready and len(self._pending) >= len(self._participants):
            self._start_all_fades()
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
        
        # Start any pending fades
        if self._pending:
            self._start_all_fades()
    
    def _start_all_fades(self) -> None:
        """Start all pending fades."""
        if not self._pending:
            return
        
        self._state = FadeState.FADING
        pending = dict(self._pending)
        self._pending.clear()
        
        logger.info("[FADE_COORD] screen=%s starting %d fades: %s",
                   self._screen_index, len(pending), sorted(pending.keys()))
        
        # Execute all starters (no locks held - lock-free)
        for name, starter in pending.items():
            try:
                starter()
                self._completed.add(name)
                logger.debug("[FADE_COORD] screen=%s %s fade started", self._screen_index, name)
            except Exception as e:
                logger.error("[FADE_COORD] screen=%s %s fade failed: %s", self._screen_index, name, e)
        
        if len(self._completed) >= len(self._participants):
            self._state = FadeState.COMPLETE
            logger.info("[FADE_COORD] screen=%s all fades complete", self._screen_index)
    
    def reset(self) -> None:
        """Reset for next image transition."""
        self._state = FadeState.IDLE
        self._compositor_ready = False
        self._pending.clear()
        self._completed.clear()
        logger.debug("[FADE_COORD] screen=%s reset", self._screen_index)
    
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
        }
