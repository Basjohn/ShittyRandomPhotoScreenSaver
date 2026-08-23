"""
Multi-Monitor Coordinator - Centralized coordination for multi-display screensaver.

This module extracts the class-level shared state from DisplayWidget into a
proper singleton coordinator, providing cleaner APIs and better testability
while maintaining the required cross-display synchronization.

Phase 5 Enhancement: Replaces scattered class-level variables with a proper
coordination layer that can be unit tested and extended.
"""
from __future__ import annotations

import threading
import weakref
from typing import Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QScreen

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget

logger = get_logger(__name__)


class MultiMonitorCoordinator(QObject):
    """
    Singleton coordinator for multi-display screensaver synchronization.
    
    Responsibilities:
    - Ctrl-held interaction mode across all displays
    - Cursor halo ownership tracking
    - Focus ownership for single-focus-window policy
    - Event filter management
    - Display instance registry
    
    Thread Safety:
        All state access is protected by a lock for safe cross-thread queries.
        However, Qt widget operations must still happen on the UI thread.
    """
    
    # Singleton instance
    _instance: Optional["MultiMonitorCoordinator"] = None
    _instance_lock = threading.Lock()
    
    # Signals for state changes
    ctrl_held_changed = Signal(bool)  # Emitted when global Ctrl state changes
    halo_owner_changed = Signal(object)  # Emitted when halo ownership changes
    
    @classmethod
    def instance(cls) -> "MultiMonitorCoordinator":
        """Get or create the singleton coordinator instance."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.cleanup()
                except Exception as e:
                    logger.debug("[COORDINATOR] Exception suppressed: %s", e)
            cls._instance = None
    
    def __init__(self):
        """Initialize the coordinator. Use instance() to get the singleton."""
        super().__init__()
        
        # State lock for thread-safe access
        self._state_lock = threading.Lock()
        
        # Ctrl-held interaction mode
        self._global_ctrl_held: bool = False
        
        # Cursor halo ownership - weak reference to avoid preventing GC
        self._halo_owner_ref: Optional[weakref.ref] = None
        
        # Focus ownership - only one DisplayWidget accepts focus
        self._focus_owner_ref: Optional[weakref.ref] = None
        
        # Event filter state
        self._event_filter_installed: bool = False
        self._event_filter_owner_ref: Optional[weakref.ref] = None
        
        # Display instance registry - weak references keyed by screen signature
        self._instances: Dict[str, weakref.ref] = {}  # screen signature -> weak ref
        
        # Settings dialog active flag - prevents halo from showing
        self._settings_dialog_active: bool = False

        # E2.7 Visualizer CUSTOM failover: runtime-only record of the current
        # failover state — either a pending 30 s grace (no temporary owner yet) or
        # a live temporary fallback owner. Never persisted (a fallback must not
        # become configuration authority); cleared on runtime teardown. Holds the
        # configured/intended screen index, a weakref to the temporary host (if
        # any), a weakref to the origin WidgetManager (to read live settings and
        # fence its pending delayed callback), and the pending flag.
        self._visualizer_failover_intended: Optional[int] = None
        self._visualizer_failover_host_ref: Optional[weakref.ref] = None
        self._visualizer_failover_origin_ref: Optional[weakref.ref] = None
        self._visualizer_failover_pending: bool = False

        logger.debug("[MULTI_MONITOR] Coordinator initialized")
    
    # =========================================================================
    # Ctrl-Held State
    # =========================================================================
    
    @property
    def ctrl_held(self) -> bool:
        """Check if Ctrl is held globally across all displays."""
        with self._state_lock:
            return self._global_ctrl_held
    
    def set_ctrl_held(self, held: bool) -> None:
        """Set the global Ctrl-held state."""
        changed = False
        with self._state_lock:
            # Don't allow Ctrl held when settings dialog is active
            if self._settings_dialog_active:
                held = False
            if self._global_ctrl_held != held:
                self._global_ctrl_held = held
                changed = True
        
        if changed:
            logger.debug("[MULTI_MONITOR] Ctrl held: %s", held)
            try:
                self.ctrl_held_changed.emit(held)
            except Exception as e:
                logger.debug("[COORDINATOR] Exception suppressed: %s", e)
    
    @property
    def settings_dialog_active(self) -> bool:
        """Check if settings dialog is currently active."""
        with self._state_lock:
            return self._settings_dialog_active
    
    def set_settings_dialog_active(self, active: bool) -> None:
        """Set whether settings dialog is active. When active, halo is suppressed."""
        with self._state_lock:
            self._settings_dialog_active = active
            if active:
                # Force Ctrl held to false when settings opens
                self._global_ctrl_held = False
        logger.debug("[MULTI_MONITOR] Settings dialog active: %s", active)
    
    # =========================================================================
    # Halo Ownership
    # =========================================================================
    
    @property
    def halo_owner(self) -> Optional["DisplayWidget"]:
        """Get the current halo owner DisplayWidget."""
        with self._state_lock:
            if self._halo_owner_ref is None:
                return None
            return self._halo_owner_ref()
    
    def set_halo_owner(self, widget: Optional["DisplayWidget"]) -> None:
        """Set the halo owner DisplayWidget."""
        with self._state_lock:
            if widget is None:
                self._halo_owner_ref = None
            else:
                self._halo_owner_ref = weakref.ref(widget)
        
        logger.debug("[MULTI_MONITOR] Halo owner: %s", 
                     widget.screen_index if widget else None)
        try:
            self.halo_owner_changed.emit(widget)
        except Exception as e:
            logger.debug("[COORDINATOR] Exception suppressed: %s", e)
    
    def clear_halo_owner(self) -> Optional["DisplayWidget"]:
        """Clear and return the previous halo owner."""
        with self._state_lock:
            prev = self._halo_owner_ref() if self._halo_owner_ref else None
            self._halo_owner_ref = None
        return prev
    
    # =========================================================================
    # Focus Ownership
    # =========================================================================
    
    @property
    def focus_owner(self) -> Optional["DisplayWidget"]:
        """Get the DisplayWidget that owns focus."""
        with self._state_lock:
            if self._focus_owner_ref is None:
                return None
            return self._focus_owner_ref()
    
    def claim_focus(self, widget: "DisplayWidget") -> bool:
        """
        Attempt to claim focus ownership for a DisplayWidget.
        
        Returns:
            True if focus was claimed (first caller wins, but can be re-claimed
            if current owner is not visible or has an unavailable screen)
        """
        with self._state_lock:
            current = self._focus_owner_ref() if self._focus_owner_ref else None
            if current is None:
                self._focus_owner_ref = weakref.ref(widget)
                logger.debug("[MULTI_MONITOR] Focus claimed by screen %s", 
                             widget.screen_index)
                return True
            
            # Already the owner
            if current is widget:
                return True
            
            # Check if current owner should yield focus
            should_yield = False
            try:
                # Yield if current owner is not visible
                if not getattr(current, "isVisible", lambda: True)():
                    should_yield = True
                    logger.debug(
                        "[MULTI_MONITOR] Focus owner screen %s not visible",
                        getattr(current, "screen_index", "?"),
                    )
            except Exception as e:
                logger.debug("[COORDINATOR] Exception suppressed: %s", e)
                should_yield = True
            
            if not should_yield:
                try:
                    # Yield if current owner's screen is not available
                    current_screen = getattr(current, "_screen", None)
                    if current_screen is None:
                        should_yield = True
                        logger.debug(
                            "[MULTI_MONITOR] Focus owner screen %s has no screen object",
                            getattr(current, "screen_index", "?"),
                        )
                    elif hasattr(current_screen, "geometry"):
                        geom = current_screen.geometry()
                        if geom is None or not geom.isValid() or geom.width() <= 0:
                            should_yield = True
                            logger.debug(
                                "[MULTI_MONITOR] Focus owner screen %s has invalid geometry",
                                getattr(current, "screen_index", "?"),
                            )
                except Exception as e:
                    logger.debug("[COORDINATOR] Exception suppressed: %s", e)
            
            if should_yield:
                self._focus_owner_ref = weakref.ref(widget)
                logger.debug(
                    "[MULTI_MONITOR] Focus re-claimed by screen %s",
                    widget.screen_index,
                )
                return True
            
            return False
    
    def release_focus(self, widget: "DisplayWidget") -> None:
        """Release focus ownership if held by the given widget."""
        with self._state_lock:
            current = self._focus_owner_ref() if self._focus_owner_ref else None
            if current is widget:
                self._focus_owner_ref = None
                logger.debug("[MULTI_MONITOR] Focus released by screen %s",
                             widget.screen_index)
    
    def is_focus_owner(self, widget: "DisplayWidget") -> bool:
        """Check if the given widget is the focus owner."""
        with self._state_lock:
            current = self._focus_owner_ref() if self._focus_owner_ref else None
            return current is widget
    
    # =========================================================================
    # Event Filter Management
    # =========================================================================
    
    @property
    def event_filter_installed(self) -> bool:
        """Check if the global event filter is installed."""
        with self._state_lock:
            return self._event_filter_installed
    
    @property
    def event_filter_owner(self) -> Optional["DisplayWidget"]:
        """Get the DisplayWidget that owns the event filter."""
        with self._state_lock:
            if self._event_filter_owner_ref is None:
                return None
            return self._event_filter_owner_ref()
    
    def install_event_filter(self, widget: "DisplayWidget") -> bool:
        """
        Install the global event filter on the given widget.
        
        Returns:
            True if filter was installed (first caller wins)
        """
        with self._state_lock:
            if self._event_filter_installed:
                current = self._event_filter_owner_ref() if self._event_filter_owner_ref else None
                if current is widget:
                    return True
                try:
                    if current is None or not getattr(current, "isVisible", lambda: True)():
                        self._event_filter_owner_ref = weakref.ref(widget)
                        logger.debug(
                            "[MULTI_MONITOR] Event filter migrated to screen %s (previous owner not visible)",
                            widget.screen_index,
                        )
                        return True
                except Exception as e:
                    logger.debug("[COORDINATOR] Exception suppressed: %s", e)
                    self._event_filter_owner_ref = weakref.ref(widget)
                    return True
                return False
            self._event_filter_installed = True
            self._event_filter_owner_ref = weakref.ref(widget)
        
        logger.debug("[MULTI_MONITOR] Event filter installed on screen %s",
                     widget.screen_index)
        return True
    
    def uninstall_event_filter(self, widget: "DisplayWidget") -> None:
        """Uninstall the event filter if owned by the given widget."""
        with self._state_lock:
            current = self._event_filter_owner_ref() if self._event_filter_owner_ref else None
            if current is widget:
                self._event_filter_installed = False
                self._event_filter_owner_ref = None
                logger.debug("[MULTI_MONITOR] Event filter uninstalled")
    
    # =========================================================================
    # Instance Registry
    # =========================================================================
    
    @staticmethod
    def _screen_signature(screen: QScreen) -> str:
        """Build a stable signature for a screen across QScreen instances."""
        if screen is None:
            return "screen:none"

        identity_parts: List[str] = []
        serial_present = False
        for label, getter in (
            ("serial", getattr(screen, "serialNumber", None)),
            ("manufacturer", getattr(screen, "manufacturer", None)),
            ("model", getattr(screen, "model", None)),
            ("name", getattr(screen, "name", None)),
        ):
            try:
                if callable(getter):
                    value = getter()
                    if value:
                        text = f"{label}:{value}"
                        identity_parts.append(text)
                        if label == "serial":
                            serial_present = True
            except Exception as e:
                logger.debug("[COORDINATOR] Exception suppressed: %s", e)
                continue

        geom_part = ""
        try:
            geom = screen.geometry()
            geom_part = f"geom:{geom.x()}_{geom.y()}_{geom.width()}x{geom.height()}"
        except Exception as e:
            logger.debug("[COORDINATOR] Exception suppressed: %s", e)

        if serial_present and identity_parts:
            return "|".join(identity_parts)
        if identity_parts:
            if geom_part:
                return "|".join(identity_parts + [geom_part])
            return "|".join(identity_parts)
        if geom_part:
            return geom_part
        return f"id:{id(screen)}"

    def register_instance(self, widget: "DisplayWidget", screen: Optional[QScreen]) -> None:
        """Register a DisplayWidget instance for a screen."""
        screen_key = self._screen_signature(screen)
        with self._state_lock:
            self._instances[screen_key] = weakref.ref(widget)
        logger.debug("[MULTI_MONITOR] Registered screen %s (key=%s)",
                     widget.screen_index, screen_key)
    
    def unregister_instance(self, widget: "DisplayWidget", screen: QScreen) -> None:
        """Unregister a DisplayWidget instance."""
        screen_key = self._screen_signature(screen)
        with self._state_lock:
            current_ref = self._instances.get(screen_key)
            if current_ref is not None and current_ref() is widget:
                del self._instances[screen_key]
                logger.debug("[MULTI_MONITOR] Unregistered screen %s",
                             widget.screen_index)
    
    def get_all_instances(self) -> List["DisplayWidget"]:
        """Get all registered DisplayWidget instances."""
        with self._state_lock:
            result = []
            dead_keys = []
            for key, ref in self._instances.items():
                widget = ref()
                if widget is not None:
                    result.append(widget)
                else:
                    dead_keys.append(key)
            # Clean up dead references
            for key in dead_keys:
                del self._instances[key]
            return result
    
    def get_instance_for_screen(self, screen: QScreen) -> Optional["DisplayWidget"]:
        """Get the DisplayWidget for a specific screen."""
        screen_key = self._screen_signature(screen)
        with self._state_lock:
            ref = self._instances.get(screen_key)
            if ref is not None:
                return ref()
        return None
    
    def get_instance_count(self) -> int:
        """Get the number of registered instances."""
        with self._state_lock:
            return len(self._instances)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def reset_all_ctrl_state(self) -> None:
        """Reset Ctrl-held state on all displays."""
        self.set_ctrl_held(False)
        for widget in self.get_all_instances():
            try:
                widget._ctrl_held = False
            except Exception as e:
                logger.debug("[COORDINATOR] Exception suppressed: %s", e)
    
    def hide_all_halos(self) -> None:
        """Hide cursor halos on all displays."""
        for widget in self.get_all_instances():
            try:
                hint = getattr(widget, "_ctrl_cursor_hint", None)
                if hint is not None:
                    hint.cancel_animation()
                    hint.hide()
            except Exception as e:
                logger.debug("[COORDINATOR] Exception suppressed: %s", e)

    # =========================================================================
    # Visualizer CUSTOM failover record (E2.7) — runtime-only, never persisted
    # =========================================================================

    @staticmethod
    def _weak_or_none(obj: object) -> Optional[weakref.ref]:
        if obj is None:
            return None
        try:
            return weakref.ref(obj)
        except TypeError:
            return None

    def set_visualizer_failover(
        self,
        *,
        intended_index: int,
        host: object = None,
        origin_manager: object = None,
        pending: bool,
    ) -> None:
        """Record the current visualizer CUSTOM failover state (runtime-only).

        Two states share one record so topology reconciliation can see *both*:

        - ``pending=True`` (grace armed): a configured CUSTOM monitor is temporarily
          unavailable and a one-shot 30 s deadline is scheduled; no temporary owner
          exists yet (``host`` is ``None``). A configured display returning before
          the deadline can then be restored immediately and the stale callback
          fenced.
        - ``pending=False`` (fallback active): a temporary owner is live on
          ``host`` (a non-configured display) until the configured display returns.

        ``intended_index`` is the configured CUSTOM monitor index resolved at
        record time; reclaim always re-resolves the CURRENT configured monitor
        from live settings, so a later Settings change supersedes this. Never
        persisted; cleared on runtime teardown.
        """
        with self._state_lock:
            try:
                self._visualizer_failover_intended = int(intended_index)
            except Exception:
                self._visualizer_failover_intended = None
                self._visualizer_failover_host_ref = None
                self._visualizer_failover_origin_ref = None
                self._visualizer_failover_pending = False
                return
            self._visualizer_failover_host_ref = self._weak_or_none(host)
            self._visualizer_failover_origin_ref = self._weak_or_none(origin_manager)
            self._visualizer_failover_pending = bool(pending)
        logger.debug(
            "[MULTI_MONITOR] Visualizer failover recorded intended_index=%s pending=%s host=%s",
            intended_index,
            pending,
            getattr(host, "screen_index", None),
        )

    def update_visualizer_failover_intended(self, intended_index: int) -> None:
        """Update the recorded intended index (a live Settings monitor change)."""
        with self._state_lock:
            if self._visualizer_failover_intended is None:
                return
            try:
                self._visualizer_failover_intended = int(intended_index)
            except Exception:
                pass

    def clear_visualizer_failover(self) -> None:
        """Clear any recorded visualizer failover (grace or fallback) state."""
        with self._state_lock:
            had = self._visualizer_failover_intended is not None
            self._visualizer_failover_intended = None
            self._visualizer_failover_host_ref = None
            self._visualizer_failover_origin_ref = None
            self._visualizer_failover_pending = False
        if had:
            logger.debug("[MULTI_MONITOR] Visualizer failover record cleared")

    def get_visualizer_failover(self) -> Optional[dict]:
        """Return the current failover record, or None if there is none.

        Shape: ``{"intended_index": int, "host": obj|None,
        "origin_manager": obj|None, "pending": bool}``. A collected host weakref
        yields ``host=None`` (treated as pending grace by reclaim).
        """
        with self._state_lock:
            if self._visualizer_failover_intended is None:
                return None
            host = self._visualizer_failover_host_ref() if self._visualizer_failover_host_ref else None
            origin = self._visualizer_failover_origin_ref() if self._visualizer_failover_origin_ref else None
            return {
                "intended_index": self._visualizer_failover_intended,
                "host": host,
                "origin_manager": origin,
                "pending": self._visualizer_failover_pending,
            }

    def cleanup(self) -> None:
        """Clean up all coordinator state."""
        with self._state_lock:
            self._global_ctrl_held = False
            self._halo_owner_ref = None
            self._focus_owner_ref = None
            self._event_filter_installed = False
            self._event_filter_owner_ref = None
            self._instances.clear()
            self._visualizer_failover_intended = None
            self._visualizer_failover_host_ref = None
            self._visualizer_failover_origin_ref = None
            self._visualizer_failover_pending = False
        logger.debug("[MULTI_MONITOR] Coordinator cleanup complete")


# Convenience function for getting the coordinator
def get_coordinator() -> MultiMonitorCoordinator:
    """Get the global MultiMonitorCoordinator instance."""
    return MultiMonitorCoordinator.instance()
