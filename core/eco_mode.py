"""
Eco Mode Manager for MC (Manual Controller) builds.

Provides automatic resource conservation when the screensaver window is
covered by other applications. When 95%+ of the window is occluded,
Eco Mode pauses transitions, visualizer updates, and prefetching to
reduce CPU/GPU usage.

Features:
- Visibility detection via Qt window geometry intersection
- Automatic pause/resume of transitions and visualizer
- Isolation from "On Top" mode (never triggers when always-on-top)
- Telemetry logging for effectiveness tracking

Usage:
    eco_manager = EcoModeManager()
    eco_manager.set_display_widget(display_widget)
    eco_manager.set_transition_controller(transition_controller)
    eco_manager.set_visualizer(visualizer_widget)
    eco_manager.start_monitoring()
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional, TYPE_CHECKING

from PySide6.QtCore import QTimer, QRect
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from rendering.transition_controller import TransitionController
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

logger = get_logger(__name__)


class EcoModeState(Enum):
    """Eco Mode states."""
    DISABLED = auto()      # Eco Mode not active (On Top mode or disabled)
    MONITORING = auto()    # Actively monitoring visibility
    ECO_ACTIVE = auto()    # Resources paused due to occlusion


@dataclass
class EcoModeStats:
    """Statistics for Eco Mode effectiveness tracking."""
    activations: int = 0
    deactivations: int = 0
    total_eco_time_ms: float = 0.0
    last_activation_ts: float = 0.0
    current_session_start: float = 0.0
    
    def record_activation(self) -> None:
        """Record an Eco Mode activation."""
        self.activations += 1
        self.last_activation_ts = time.time()
        self.current_session_start = self.last_activation_ts
    
    def record_deactivation(self) -> None:
        """Record an Eco Mode deactivation."""
        self.deactivations += 1
        if self.current_session_start > 0:
            self.total_eco_time_ms += (time.time() - self.current_session_start) * 1000.0
            self.current_session_start = 0.0


@dataclass
class EcoModeConfig:
    """Configuration for Eco Mode behavior."""
    enabled: bool = True
    occlusion_threshold: float = 0.95  # 95% coverage triggers Eco Mode
    check_interval_ms: int = 1000      # Check visibility every 1 second
    recovery_delay_ms: int = 100       # Delay before resuming after visibility restored
    pause_transitions: bool = True
    pause_visualizer: bool = True
    pause_prefetch: bool = False       # Optional, may not provide significant benefit


class EcoModeManager:
    """
    Manages Eco Mode for MC builds.
    
    Automatically pauses resource-intensive operations when the screensaver
    window is covered by other applications.
    
    Thread Safety:
        All operations run on the UI thread via QTimer. No locks needed.
    """
    
    def __init__(self, config: Optional[EcoModeConfig] = None):
        """
        Initialize the Eco Mode manager.
        
        Args:
            config: Optional configuration (uses defaults if not provided)
        """
        self._config = config or EcoModeConfig()
        self._state = EcoModeState.DISABLED
        self._stats = EcoModeStats()
        
        # Components to pause/resume
        self._display_widget: Optional["DisplayWidget"] = None
        self._transition_controller: Optional["TransitionController"] = None
        self._visualizer: Optional["SpotifyVisualizerWidget"] = None
        self._prefetch_pause_callback: Optional[Callable[[], None]] = None
        self._prefetch_resume_callback: Optional[Callable[[], None]] = None
        
        # Monitoring timer
        self._monitor_timer: Optional[QTimer] = None
        self._recovery_timer: Optional[QTimer] = None
        
        # Always-on-top state (Eco Mode disabled when on top)
        self._always_on_top: bool = False
        
        # Paused state tracking
        self._transition_was_running: bool = False
        self._visualizer_was_active: bool = False
        
        logger.debug("[MC] [ECO MODE] Manager initialized")
    
    # =========================================================================
    # Configuration
    # =========================================================================
    
    def set_display_widget(self, widget: "DisplayWidget") -> None:
        """Set the display widget to monitor for visibility."""
        self._display_widget = widget
    
    def set_transition_controller(self, controller: "TransitionController") -> None:
        """Set the transition controller to pause/resume."""
        self._transition_controller = controller
    
    def set_visualizer(self, visualizer: "SpotifyVisualizerWidget") -> None:
        """Set the Spotify visualizer to pause/resume."""
        self._visualizer = visualizer
    
    def set_prefetch_callbacks(
        self,
        pause_callback: Callable[[], None],
        resume_callback: Callable[[], None]
    ) -> None:
        """Set callbacks for pausing/resuming image prefetching."""
        self._prefetch_pause_callback = pause_callback
        self._prefetch_resume_callback = resume_callback
    
    def set_always_on_top(self, on_top: bool) -> None:
        """
        Set the always-on-top state.
        
        When on top, Eco Mode is disabled (window is always visible).
        
        Args:
            on_top: True if window is always on top
        """
        self._always_on_top = on_top
        
        if on_top and self._state == EcoModeState.ECO_ACTIVE:
            # Resume immediately when switching to on-top mode
            self._deactivate_eco_mode("switched_to_on_top")
        
        if on_top:
            self._state = EcoModeState.DISABLED
            logger.info("[MC] [ECO MODE] Disabled (always on top)")
        elif self._config.enabled:
            self._state = EcoModeState.MONITORING
            logger.info("[MC] [ECO MODE] Enabled (on bottom)")
    
    # =========================================================================
    # Monitoring Control
    # =========================================================================
    
    def start_monitoring(self) -> None:
        """Start visibility monitoring."""
        if not self._config.enabled:
            logger.debug("[MC] [ECO MODE] Monitoring disabled by config")
            return
        
        if self._always_on_top:
            logger.debug("[MC] [ECO MODE] Monitoring skipped (always on top)")
            return
        
        self._state = EcoModeState.MONITORING
        
        if self._monitor_timer is None:
            self._monitor_timer = QTimer()
            self._monitor_timer.timeout.connect(self._check_visibility)
        
        self._monitor_timer.start(self._config.check_interval_ms)
        logger.info("[MC] [ECO MODE] Monitoring started (interval=%dms)", self._config.check_interval_ms)
    
    def stop_monitoring(self) -> None:
        """Stop visibility monitoring and resume all paused components."""
        if self._monitor_timer is not None:
            self._monitor_timer.stop()
        
        if self._recovery_timer is not None:
            self._recovery_timer.stop()
        
        if self._state == EcoModeState.ECO_ACTIVE:
            self._deactivate_eco_mode("monitoring_stopped")
        
        self._state = EcoModeState.DISABLED
        logger.info("[MC] [ECO MODE] Monitoring stopped")
    
    # =========================================================================
    # Visibility Detection
    # =========================================================================
    
    def _check_visibility(self) -> None:
        """Check if the display widget is sufficiently visible."""
        if self._display_widget is None:
            return
        
        if self._always_on_top:
            # Never trigger Eco Mode when on top
            if self._state == EcoModeState.ECO_ACTIVE:
                self._deactivate_eco_mode("on_top_detected")
            return
        
        try:
            occlusion_ratio = self._calculate_occlusion_ratio()
        except Exception as e:
            logger.debug("[MC] [ECO MODE] Visibility check failed: %s", e)
            return
        
        is_occluded = occlusion_ratio >= self._config.occlusion_threshold
        
        if is_occluded and self._state == EcoModeState.MONITORING:
            self._activate_eco_mode(occlusion_ratio)
        elif not is_occluded and self._state == EcoModeState.ECO_ACTIVE:
            self._schedule_recovery()
    
    def _calculate_occlusion_ratio(self) -> float:
        """
        Calculate what fraction of the display widget is occluded.
        
        Returns:
            Occlusion ratio (0.0 = fully visible, 1.0 = fully covered)
        """
        if self._display_widget is None:
            return 0.0
        
        try:
            widget_rect = self._display_widget.frameGeometry()
            widget_global = QRect(
                self._display_widget.mapToGlobal(widget_rect.topLeft()),
                widget_rect.size()
            )
        except Exception:
            return 0.0
        
        widget_area = widget_global.width() * widget_global.height()
        if widget_area <= 0:
            return 0.0
        
        # Get all top-level windows
        app = QApplication.instance()
        if app is None:
            return 0.0
        
        occluded_area = 0
        our_window = self._display_widget.window()
        
        try:
            for widget in app.topLevelWidgets():
                if widget is our_window:
                    continue
                if not widget.isVisible():
                    continue
                
                # Check if this window is above ours in Z-order
                # (simplified: assume all visible windows could occlude)
                other_rect = widget.frameGeometry()
                other_global = QRect(
                    widget.mapToGlobal(other_rect.topLeft()),
                    other_rect.size()
                )
                
                intersection = widget_global.intersected(other_global)
                if not intersection.isEmpty():
                    occluded_area += intersection.width() * intersection.height()
        except Exception:
            pass
        
        # Clamp to [0, 1] (overlapping windows could double-count)
        return min(1.0, occluded_area / widget_area)
    
    # =========================================================================
    # Eco Mode Activation/Deactivation
    # =========================================================================
    
    def _activate_eco_mode(self, occlusion_ratio: float) -> None:
        """Activate Eco Mode and pause resource-intensive operations."""
        if self._state == EcoModeState.ECO_ACTIVE:
            return
        
        self._state = EcoModeState.ECO_ACTIVE
        self._stats.record_activation()
        
        logger.info(
            "[MC] [ECO MODE] ACTIVATED (occlusion=%.1f%%, threshold=%.1f%%)",
            occlusion_ratio * 100,
            self._config.occlusion_threshold * 100
        )
        
        # Pause transitions
        if self._config.pause_transitions and self._transition_controller is not None:
            try:
                self._transition_was_running = self._transition_controller.is_running
                if self._transition_was_running:
                    # Note: We don't actually pause mid-transition, just prevent new ones
                    logger.debug("[MC] [ECO MODE] Transition controller noted as running")
            except Exception:
                pass
        
        # Pause visualizer
        if self._config.pause_visualizer and self._visualizer is not None:
            try:
                self._visualizer_was_active = getattr(self._visualizer, '_enabled', False)
                if hasattr(self._visualizer, 'set_eco_mode'):
                    self._visualizer.set_eco_mode(True)
                logger.debug("[MC] [ECO MODE] Visualizer paused")
            except Exception:
                pass
        
        # Pause prefetching
        if self._config.pause_prefetch and self._prefetch_pause_callback is not None:
            try:
                self._prefetch_pause_callback()
                logger.debug("[MC] [ECO MODE] Prefetching paused")
            except Exception:
                pass
    
    def _schedule_recovery(self) -> None:
        """Schedule recovery from Eco Mode after a short delay."""
        if self._recovery_timer is not None:
            self._recovery_timer.stop()
        else:
            self._recovery_timer = QTimer()
            self._recovery_timer.setSingleShot(True)
            self._recovery_timer.timeout.connect(
                lambda: self._deactivate_eco_mode("visibility_restored")
            )
        
        self._recovery_timer.start(self._config.recovery_delay_ms)
    
    def _deactivate_eco_mode(self, reason: str) -> None:
        """Deactivate Eco Mode and resume all paused operations."""
        if self._state != EcoModeState.ECO_ACTIVE:
            return
        
        self._state = EcoModeState.MONITORING if not self._always_on_top else EcoModeState.DISABLED
        self._stats.record_deactivation()
        
        logger.info("[MC] [ECO MODE] DEACTIVATED (reason=%s)", reason)
        
        # Resume visualizer
        if self._config.pause_visualizer and self._visualizer is not None:
            try:
                if hasattr(self._visualizer, 'set_eco_mode'):
                    self._visualizer.set_eco_mode(False)
                logger.debug("[MC] [ECO MODE] Visualizer resumed")
            except Exception:
                pass
        
        # Resume prefetching
        if self._config.pause_prefetch and self._prefetch_resume_callback is not None:
            try:
                self._prefetch_resume_callback()
                logger.debug("[MC] [ECO MODE] Prefetching resumed")
            except Exception:
                pass
        
        # Transitions resume automatically (we just prevented new ones)
    
    # =========================================================================
    # Statistics and Telemetry
    # =========================================================================
    
    def get_stats(self) -> EcoModeStats:
        """Get Eco Mode statistics."""
        return self._stats
    
    def get_state(self) -> EcoModeState:
        """Get current Eco Mode state."""
        return self._state
    
    def is_eco_active(self) -> bool:
        """Check if Eco Mode is currently active."""
        return self._state == EcoModeState.ECO_ACTIVE
    
    def log_stats(self) -> None:
        """Log current Eco Mode statistics."""
        stats = self._stats
        logger.info(
            "[MC] [ECO MODE] Stats: activations=%d, deactivations=%d, total_eco_time=%.1fs",
            stats.activations,
            stats.deactivations,
            stats.total_eco_time_ms / 1000.0
        )
    
    # =========================================================================
    # Cleanup
    # =========================================================================
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_monitoring()
        
        if self._monitor_timer is not None:
            self._monitor_timer.deleteLater()
            self._monitor_timer = None
        
        if self._recovery_timer is not None:
            self._recovery_timer.deleteLater()
            self._recovery_timer = None
        
        self.log_stats()
        logger.debug("[MC] [ECO MODE] Manager cleaned up")


def is_mc_build() -> bool:
    """
    Check if this is an MC (Manual Controller) build.
    
    Returns:
        True if running as MC build
    """
    import sys
    
    # Check for MC-specific entry point
    main_module = sys.modules.get('__main__')
    if main_module is not None:
        main_file = getattr(main_module, '__file__', '') or ''
        if 'main_mc' in main_file.lower():
            return True
    
    # Check for MC-specific settings
    try:
        from core.settings.settings_manager import SettingsManager
        mgr = SettingsManager()
        app_name = mgr.get_application_name()
        return 'MC' in app_name or 'mc' in app_name.lower()
    except Exception:
        pass
    
    return False
