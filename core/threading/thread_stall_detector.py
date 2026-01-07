"""
Thread stall detection for performance monitoring.

Detects when threads or workers are blocked/stalled beyond acceptable thresholds.
All profiling is gated behind SRPSS_PERF_METRICS environment variable.
"""
import threading
import time
from typing import Dict, Optional
from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)


class ThreadStallDetector:
    """Detects thread stalls and reports them for debugging.
    
    Thread-safe detector that tracks thread execution times and reports
    when threads are blocked beyond acceptable thresholds.
    
    Usage:
        detector = ThreadStallDetector()
        
        # Mark thread entry
        detector.enter_section("texture_upload", thread_id)
        
        # ... do work ...
        
        # Mark thread exit (auto-detects stalls)
        detector.exit_section("texture_upload", thread_id)
    """
    
    def __init__(self, stall_threshold_ms: float = 100.0):
        """Initialize stall detector.
        
        Args:
            stall_threshold_ms: Threshold in milliseconds for stall detection
        """
        self._threshold_ms = stall_threshold_ms
        self._lock = threading.Lock()
        self._active_sections: Dict[str, Dict[int, float]] = {}
        
    def enter_section(self, section_name: str, thread_id: Optional[int] = None) -> None:
        """Mark entry into a monitored section.
        
        Args:
            section_name: Name of the section (e.g., "texture_upload")
            thread_id: Optional thread ID (uses current thread if None)
        """
        if not is_perf_metrics_enabled():
            return
        
        if thread_id is None:
            thread_id = threading.get_ident()
        
        with self._lock:
            if section_name not in self._active_sections:
                self._active_sections[section_name] = {}
            self._active_sections[section_name][thread_id] = time.time()
    
    def exit_section(self, section_name: str, thread_id: Optional[int] = None) -> None:
        """Mark exit from a monitored section and check for stalls.
        
        Args:
            section_name: Name of the section
            thread_id: Optional thread ID (uses current thread if None)
        """
        if not is_perf_metrics_enabled():
            return
        
        if thread_id is None:
            thread_id = threading.get_ident()
        
        with self._lock:
            if section_name not in self._active_sections:
                return
            
            if thread_id not in self._active_sections[section_name]:
                return
            
            start_time = self._active_sections[section_name].pop(thread_id)
            elapsed_ms = (time.time() - start_time) * 1000.0
            
            if elapsed_ms > self._threshold_ms:
                # Report to debug log (ungated - user wants to know about stalls)
                logger.debug("[THREAD STALL] %s blocked for %.2fms (thread=%d, threshold=%.2fms)",
                           section_name, elapsed_ms, thread_id, self._threshold_ms)
                
                # Also report to perf log with [PERF] tag
                logger.warning("[PERF] [THREAD STALL] %s: %.2fms (thread=%d)",
                             section_name, elapsed_ms, thread_id)
    
    def check_active_sections(self) -> None:
        """Check all active sections for stalls (call periodically).
        
        This is useful for detecting threads that never exit (deadlocks).
        """
        if not is_perf_metrics_enabled():
            return
        
        current_time = time.time()
        
        with self._lock:
            for section_name, threads in self._active_sections.items():
                for thread_id, start_time in list(threads.items()):
                    elapsed_ms = (current_time - start_time) * 1000.0
                    
                    if elapsed_ms > self._threshold_ms * 2:  # 2x threshold for active checks
                        logger.warning("[PERF] [THREAD STALL] %s still active after %.2fms (thread=%d)",
                                     section_name, elapsed_ms, thread_id)


# Global singleton instance
_global_detector: Optional[ThreadStallDetector] = None
_detector_lock = threading.Lock()


def get_stall_detector() -> ThreadStallDetector:
    """Get global stall detector instance (singleton)."""
    global _global_detector
    
    if _global_detector is None:
        with _detector_lock:
            if _global_detector is None:
                _global_detector = ThreadStallDetector(stall_threshold_ms=100.0)
    
    return _global_detector
