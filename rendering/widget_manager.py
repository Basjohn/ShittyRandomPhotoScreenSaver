"""
Widget Manager - Extracted from DisplayWidget for better separation of concerns.

Manages overlay widget lifecycle, positioning, visibility, and Z-order.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect

from core.logging.logger import get_logger, is_verbose_logging
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
from rendering.widget_setup import parse_color_to_qcolor, compute_expected_overlays
from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
from widgets.weather_widget import WeatherWidget, WeatherPosition
from widgets.media_widget import MediaWidget, MediaPosition
from widgets.reddit_widget import RedditWidget, RedditPosition
# Gmail widget archived - see archive/gmail_feature/RESTORE_GMAIL.md
# from widgets.gmail_widget import GmailWidget, GmailPosition
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_volume_widget import SpotifyVolumeWidget
from widgets.shadow_utils import apply_widget_shadow
from rendering.widget_positioner import WidgetPositioner, PositionAnchor
from rendering.widget_factories import WidgetFactoryRegistry

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


class WidgetManager:
    """
    Manages overlay widgets for a DisplayWidget.
    
    Responsibilities:
    - Widget creation and destruction
    - Widget positioning and sizing
    - Widget visibility and Z-order
    - Fade coordination via ShadowFadeProfile
    - Rate-limited raise operations
    - Effect invalidation (Phase E: cache corruption mitigation)
    
    Phase E Context:
        This class centralizes QGraphicsEffect lifecycle management to make
        ordering deterministic during context menu open/close and focus/activation
        cascades. By owning effect invalidation, we can prevent the cache corruption
        that occurs when effects are manipulated from multiple call sites with
        inconsistent ordering.
    """
    
    # Rate limit for raise operations (ms)
    RAISE_RATE_LIMIT_MS = 100
    
    def __init__(self, parent: "DisplayWidget", resource_manager: Optional[ResourceManager] = None):
        """
        Initialize the WidgetManager.
        
        Args:
            parent: The DisplayWidget that owns these widgets
            resource_manager: Optional ResourceManager for lifecycle tracking
        """
        self._parent = parent
        self._resource_manager = resource_manager
        
        # Widget references
        self._widgets: Dict[str, QWidget] = {}
        
        # Rate limiting for raise operations
        self._last_raise_time: float = 0.0
        self._pending_raise: bool = False
        self._raise_timer: Optional[QTimer] = None
        
        # Fade coordination
        self._fade_callbacks: Dict[str, Callable] = {}
        
        # Overlay fade synchronization state (Phase E: centralized coordination)
        self._overlay_fade_expected: Set[str] = set()
        self._overlay_fade_pending: Dict[str, Callable[[], None]] = {}
        self._overlay_fade_started: bool = False
        self._overlay_fade_timeout: Optional[QTimer] = None
        self._spotify_secondary_fade_starters: List[Callable[[], None]] = []
        
        # Widget positioning (Dec 2025)
        self._positioner = WidgetPositioner()
        
        # Widget factory registry (Dec 2025) - for simplified widget creation
        self._factory_registry: Optional[WidgetFactoryRegistry] = None
        
        logger.debug("[WIDGET_MANAGER] Initialized")
    
    def set_factory_registry(
        self, 
        settings: SettingsManager, 
        thread_manager: Optional["ThreadManager"] = None
    ) -> None:
        """
        Initialize the widget factory registry.
        
        Args:
            settings: SettingsManager for widget configuration
            thread_manager: Optional ThreadManager for background operations
        """
        self._factory_registry = WidgetFactoryRegistry(settings, thread_manager)
        logger.debug("[WIDGET_MANAGER] Factory registry initialized")
    
    def create_widget_from_factory(
        self,
        widget_type: str,
        config: Dict[str, Any],
    ) -> Optional[QWidget]:
        """
        Create a widget using the factory registry.
        
        This is a simplified creation method that delegates to the factory.
        For complex widget creation with full settings resolution, use the
        specific create_*_widget methods.
        
        Args:
            widget_type: Type of widget ('clock', 'weather', 'media', 'reddit', etc.)
            config: Widget configuration dict
            
        Returns:
            Created widget or None if creation failed
        """
        if self._factory_registry is None:
            logger.warning("[WIDGET_MANAGER] Factory registry not initialized")
            return None
        
        widget = self._factory_registry.create_widget(widget_type, self._parent, config)
        if widget:
            self.register_widget(widget_type, widget)
        return widget
    
    def register_widget(self, name: str, widget: QWidget) -> None:
        """
        Register a widget for management.
        
        Args:
            name: Unique name for the widget
            widget: The widget to manage
        """
        self._widgets[name] = widget
        if widget is not None and hasattr(widget, "set_widget_manager"):
            try:
                widget.set_widget_manager(self)
            except Exception:
                pass
        if self._resource_manager:
            try:
                self._resource_manager.register_qt(widget, description=f"Widget: {name}")
            except Exception:
                pass
        logger.debug(f"[WIDGET_MANAGER] Registered widget: {name}")

    def configure_expected_overlays(self, widgets_config: Dict[str, Any]) -> None:
        """Compute and store the overlays expected to participate in fade sync."""
        if widgets_config is None:
            widgets_config = {}
        try:
            expected = compute_expected_overlays(self._parent, widgets_config)
        except Exception:
            expected = set()
        self.set_expected_overlays(expected)
    
    def unregister_widget(self, name: str) -> Optional[QWidget]:
        """
        Unregister a widget.
        
        Args:
            name: Name of the widget to unregister
            
        Returns:
            The unregistered widget or None
        """
        widget = self._widgets.pop(name, None)
        if widget:
            logger.debug(f"[WIDGET_MANAGER] Unregistered widget: {name}")
        return widget
    
    def get_widget(self, name: str) -> Optional[QWidget]:
        """Get a widget by name."""
        return self._widgets.get(name)
    
    def get_all_widgets(self) -> List[QWidget]:
        """Get all managed widgets."""
        return list(self._widgets.values())
    
    def raise_all(self, force: bool = False) -> None:
        """
        Raise all widgets above the compositor.
        
        Rate-limited to avoid expensive operations on every frame.
        
        Args:
            force: If True, bypass rate limiting
        """
        now = time.time()
        elapsed_ms = (now - self._last_raise_time) * 1000.0
        
        if not force and elapsed_ms < self.RAISE_RATE_LIMIT_MS:
            # Schedule a deferred raise if not already pending
            if not self._pending_raise:
                self._pending_raise = True
                remaining_ms = int(self.RAISE_RATE_LIMIT_MS - elapsed_ms) + 1
                if self._raise_timer is None:
                    self._raise_timer = QTimer()
                    self._raise_timer.setSingleShot(True)
                    self._raise_timer.timeout.connect(self._do_deferred_raise)
                self._raise_timer.start(remaining_ms)
            return
        
        self._do_raise_all()
    
    def _do_deferred_raise(self) -> None:
        """Execute a deferred raise operation."""
        self._pending_raise = False
        self._do_raise_all()
    
    def _do_raise_all(self) -> None:
        """Actually raise all widgets."""
        self._last_raise_time = time.time()
        
        for name, widget in self._widgets.items():
            try:
                if widget is not None and widget.isVisible():
                    widget.raise_()
            except Exception:
                if is_verbose_logging():
                    logger.debug(f"[WIDGET_MANAGER] Failed to raise {name}", exc_info=True)
    
    def raise_widget(self, name: str) -> bool:
        """
        Raise a specific widget.
        
        Args:
            name: Name of the widget to raise
            
        Returns:
            True if widget was raised
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.raise_()
                return True
            except Exception:
                pass
        return False
    
    def show_widget(self, name: str) -> bool:
        """
        Show a specific widget.
        
        Args:
            name: Name of the widget to show
            
        Returns:
            True if widget was shown
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.show()
                return True
            except Exception:
                pass
        return False
    
    def hide_widget(self, name: str) -> bool:
        """
        Hide a specific widget.
        
        Args:
            name: Name of the widget to hide
            
        Returns:
            True if widget was hidden
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.hide()
                return True
            except Exception:
                pass
        return False
    
    def set_widget_geometry(self, name: str, x: int, y: int, width: int, height: int) -> bool:
        """
        Set widget geometry.
        
        Args:
            name: Widget name
            x, y: Position
            width, height: Size
            
        Returns:
            True if geometry was set
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.setGeometry(x, y, width, height)
                return True
            except Exception:
                pass
        return False
    
    def register_fade_callback(self, name: str, callback: Callable) -> None:
        """
        Register a fade callback for a widget.
        
        Args:
            name: Widget name
            callback: Callback to invoke during fade
        """
        self._fade_callbacks[name] = callback
    
    def invoke_fade_callbacks(self, progress: float) -> None:
        """
        Invoke all registered fade callbacks.
        
        Args:
            progress: Fade progress (0.0 to 1.0)
        """
        for name, callback in self._fade_callbacks.items():
            try:
                callback(progress)
            except Exception:
                if is_verbose_logging():
                    logger.debug(f"[WIDGET_MANAGER] Fade callback failed for {name}", exc_info=True)
    
    def raise_all_widgets(self) -> None:
        """Raise all registered widgets above the compositor.
        
        CRITICAL: Must be called SYNCHRONOUSLY after transition.start() returns,
        NOT via QTimer.singleShot(0, ...). Deferred raises allow the compositor
        to render frames before widgets are raised above it.
        """
        for name, widget in self._widgets.items():
            if widget is not None:
                try:
                    widget.raise_()
                    # Handle clock timezone labels
                    if hasattr(widget, '_tz_label') and widget._tz_label:
                        widget._tz_label.raise_()
                except Exception:
                    pass

    def position_spotify_visualizer(self, vis_widget, media_widget, parent_width: int, parent_height: int) -> None:
        """Position Spotify visualizer relative to media widget."""
        if vis_widget is None or media_widget is None:
            return
        try:
            media_geom = media_widget.geometry()
            if media_geom.width() <= 0 or media_geom.height() <= 0:
                return
            
            gap = 20
            height = max(vis_widget.height(), vis_widget.minimumHeight())
            width = media_geom.width()
            x = media_geom.left()
            
            position = getattr(media_widget, "_position", None)
            place_above = position not in ("TOP_LEFT", "TOP_RIGHT") if position else True
            
            if place_above:
                y = media_geom.top() - gap - height
            else:
                y = media_geom.bottom() + gap
            
            y = max(0, y)
            x = max(0, x)
            width = min(width, max(10, parent_width - x))
            
            vis_widget.setGeometry(x, y, width, height)
            vis_widget.raise_()
            
            # Keep pixel-shift drift baseline aligned with the media card so the
            # GL overlay inherits the same reference frame as the QWidget card.
            pixel_shift_manager = getattr(self._parent, "_pixel_shift_manager", None)
            if pixel_shift_manager is not None and hasattr(pixel_shift_manager, "update_original_position"):
                try:
                    pixel_shift_manager.update_original_position(vis_widget)
                except Exception:
                    pass
        except Exception:
            pass

    def position_spotify_volume(self, vol_widget, media_widget, parent_width: int, parent_height: int) -> None:
        """Position Spotify volume slider beside media widget."""
        if vol_widget is None or media_widget is None:
            return
        try:
            media_geom = media_widget.geometry()
            if media_geom.width() <= 0 or media_geom.height() <= 0:
                return
            
            gap = 16
            width = max(vol_widget.minimumWidth(), 32)
            card_height = media_geom.height()
            height = max(vol_widget.minimumHeight(), card_height - 8)
            height = min(height, card_height)
            
            space_left = max(0, media_geom.left())
            space_right = max(0, parent_width - media_geom.right())
            
            if space_right >= space_left:
                x = media_geom.right() + gap
                if x + width > parent_width:
                    x = max(0, parent_width - width)
            else:
                x = media_geom.left() - gap - width
                x = max(0, x)
            
            y = media_geom.top() + max(0, (card_height - height) // 2)
            y = max(0, min(y, max(0, parent_height - height)))
            
            vol_widget.setGeometry(x, y, width, height)
            if vol_widget.isVisible():
                vol_widget.raise_()
        except Exception:
            pass

    def apply_widget_stacking(self, widget_list: list) -> None:
        """Apply vertical stacking offsets to widgets sharing the same position."""
        from PySide6.QtCore import QPoint
        
        position_groups: dict = {}
        for i, (widget, attr_name) in enumerate(widget_list):
            if widget is None:
                continue
            pos_key = self._get_widget_position_key(widget)
            if not pos_key:
                continue
            if pos_key not in position_groups:
                position_groups[pos_key] = []
            position_groups[pos_key].append((widget, attr_name, i))
        
        spacing = 10
        for pos_key, widgets_at_pos in position_groups.items():
            if len(widgets_at_pos) <= 1:
                if widgets_at_pos and hasattr(widgets_at_pos[0][0], 'set_stack_offset'):
                    widgets_at_pos[0][0].set_stack_offset(QPoint(0, 0))
                continue
            
            stack_down = 'top' in pos_key
            widgets_at_pos.sort(key=lambda x: x[2], reverse=not stack_down)
            
            cumulative_offset = 0
            for i, (widget, attr_name, _) in enumerate(widgets_at_pos):
                if i == 0:
                    if hasattr(widget, 'set_stack_offset'):
                        widget.set_stack_offset(QPoint(0, 0))
                    continue
                
                prev_widget = widgets_at_pos[i - 1][0]
                prev_height = self._get_widget_stack_height(prev_widget)
                cumulative_offset += prev_height + spacing
                offset_y = cumulative_offset if stack_down else -cumulative_offset
                
                if hasattr(widget, 'set_stack_offset'):
                    widget.set_stack_offset(QPoint(0, offset_y))

    def _get_widget_position_key(self, widget) -> str:
        """Get normalized position key from widget."""
        try:
            if hasattr(widget, '_position'):
                pos = widget._position
                if hasattr(pos, 'name'):
                    return pos.name.lower()
                return str(pos).lower().replace(' ', '_')
            if hasattr(widget, 'get_position'):
                pos = widget.get_position()
                if hasattr(pos, 'name'):
                    return pos.name.lower()
                return str(pos).lower().replace(' ', '_')
        except Exception:
            pass
        return ""

    def _get_widget_stack_height(self, widget) -> int:
        """Get widget height for stacking calculations."""
        try:
            if hasattr(widget, 'get_bounding_size'):
                return widget.get_bounding_size().height()
            hint = widget.sizeHint()
            if hint.isValid() and hint.height() > 0:
                return hint.height()
            return widget.height() if widget.height() > 0 else 100
        except Exception:
            return 100
    
    def cleanup(self) -> None:
        """Clean up all managed widgets."""
        if self._raise_timer is not None:
            try:
                self._raise_timer.stop()
            except Exception:
                pass
            self._raise_timer = None
        
        # Use lifecycle cleanup for widgets that support it
        for name, widget in list(self._widgets.items()):
            if widget is not None:
                try:
                    if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                        widget.cleanup()
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to cleanup %s", name, exc_info=True)
        
        self._widgets.clear()
        self._fade_callbacks.clear()
        logger.debug("[WIDGET_MANAGER] Cleanup complete")

    # =========================================================================
    # Lifecycle Integration (Dec 2025)
    # =========================================================================

    def initialize_widget(self, name: str) -> bool:
        """Initialize a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to initialize
            
        Returns:
            True if widget was initialized successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'initialize') and callable(widget.initialize):
                widget.initialize()
                logger.debug("[LIFECYCLE] Widget %s initialized via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to initialize %s", name, exc_info=True)
        return False

    def activate_widget(self, name: str) -> bool:
        """Activate a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to activate
            
        Returns:
            True if widget was activated successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'activate') and callable(widget.activate):
                widget.activate()
                logger.debug("[LIFECYCLE] Widget %s activated via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to activate %s", name, exc_info=True)
        return False

    def deactivate_widget(self, name: str) -> bool:
        """Deactivate a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to deactivate
            
        Returns:
            True if widget was deactivated successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'deactivate') and callable(widget.deactivate):
                widget.deactivate()
                logger.debug("[LIFECYCLE] Widget %s deactivated via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to deactivate %s", name, exc_info=True)
        return False

    def cleanup_widget(self, name: str) -> bool:
        """Cleanup a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to cleanup
            
        Returns:
            True if widget was cleaned up successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                widget.cleanup()
                logger.debug("[LIFECYCLE] Widget %s cleaned up via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to cleanup %s", name, exc_info=True)
        return False

    def initialize_all_widgets(self) -> int:
        """Initialize all managed widgets using the new lifecycle system.
        
        Returns:
            Number of widgets successfully initialized
        """
        count = 0
        for name in list(self._widgets.keys()):
            if self.initialize_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Initialized %d widgets", count)
        return count

    def activate_all_widgets(self) -> int:
        """Activate all managed widgets using the new lifecycle system.
        
        Returns:
            Number of widgets successfully activated
        """
        count = 0
        for name in list(self._widgets.keys()):
            if self.activate_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Activated %d widgets", count)
        return count

    def deactivate_all_widgets(self) -> int:
        """Deactivate all managed widgets using the new lifecycle system.
        
        Returns:
            Number of widgets successfully deactivated
        """
        count = 0
        for name in list(self._widgets.keys()):
            if self.deactivate_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Deactivated %d widgets", count)
        return count

    def get_widget_lifecycle_state(self, name: str) -> Optional[str]:
        """Get the lifecycle state of a widget.
        
        Args:
            name: Name of the widget
            
        Returns:
            Lifecycle state name or None if widget not found or doesn't support lifecycle
        """
        widget = self._widgets.get(name)
        if widget is None:
            return None
        
        try:
            if hasattr(widget, '_lifecycle_state'):
                state = widget._lifecycle_state
                if hasattr(state, 'name'):
                    return state.name
                return str(state)
        except Exception:
            pass
        return None

    def get_all_lifecycle_states(self) -> Dict[str, str]:
        """Get lifecycle states of all managed widgets.
        
        Returns:
            Dict mapping widget name to lifecycle state name
        """
        states = {}
        for name in self._widgets.keys():
            state = self.get_widget_lifecycle_state(name)
            if state is not None:
                states[name] = state
        return states

    # =========================================================================
    # Widget Positioning (Dec 2025)
    # =========================================================================

    def set_container_size(self, width: int, height: int) -> None:
        """Set the container size for widget positioning.
        
        Args:
            width: Container width in pixels
            height: Container height in pixels
        """
        from PySide6.QtCore import QSize
        self._positioner.set_container_size(QSize(width, height))

    def get_positioner(self) -> WidgetPositioner:
        """Get the widget positioner for advanced positioning operations."""
        return self._positioner

    def position_widget_by_anchor(self, name: str, anchor: PositionAnchor, margin: int = 20) -> bool:
        """Position a widget using the centralized positioner.
        
        Args:
            name: Name of the widget to position
            anchor: Position anchor (e.g., TOP_LEFT, BOTTOM_RIGHT)
            margin: Margin from screen edge
            
        Returns:
            True if widget was positioned successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            self._positioner.position_widget(widget, anchor, margin_x=margin, margin_y=margin)
            return True
        except Exception:
            logger.debug("[POSITIONER] Failed to position %s", name, exc_info=True)
        return False

    # =========================================================================
    # Phase E: Effect Invalidation (Cache Corruption Mitigation)
    # =========================================================================

    def invalidate_overlay_effects(self, reason: str) -> None:
        """Invalidate and optionally recreate widget QGraphicsEffects.
        
        Phase E Context:
            This method centralizes effect cache-busting to prevent Qt's internal
            cached pixmap/texture backing from becoming corrupt during rapid
            focus/activation + popup menu sequencing across multi-monitor windows.
        
        Args:
            reason: Identifier for the trigger (e.g., "menu_about_to_show",
                    "menu_before_popup", "focus_in"). Menu-related reasons
                    trigger stronger invalidation with effect recreation.
        """
        screen_idx = "?"
        try:
            screen_idx = getattr(self._parent, "screen_index", "?")
        except Exception:
            pass
        
        if win_diag_logger.isEnabledFor(logging.DEBUG):
            # Phase E instrumentation: log effect state before invalidation
            effect_states = []
            for name, widget in self._widgets.items():
                if widget is None:
                    continue
                try:
                    eff = widget.graphicsEffect()
                    if eff is not None:
                        eff_type = type(eff).__name__
                        eff_id = id(eff)
                        enabled = eff.isEnabled() if hasattr(eff, 'isEnabled') else '?'
                        effect_states.append(f"{name}:{eff_type}@{eff_id:#x}(en={enabled})")
                except Exception:
                    pass
            
            win_diag_logger.debug(
                "[EFFECT_INVALIDATE] screen=%s reason=%s widgets=%d effects=[%s]",
                screen_idx, reason, len(self._widgets), ", ".join(effect_states) if effect_states else "none",
            )

        # Menu-related triggers warrant stronger invalidation (effect recreation)
        try:
            strong = "menu" in str(reason)
        except Exception:
            strong = False

        refresh_effects = False
        if strong:
            # Toggle-based refresh: recreate effects on every other menu
            # invalidation to bust Qt caches without excessive churn.
            try:
                flip = bool(getattr(self, "_effect_refresh_flip", False))
            except Exception:
                flip = False
            flip = not flip
            try:
                setattr(self, "_effect_refresh_flip", flip)
            except Exception:
                pass
            refresh_effects = flip

        seen: set[int] = set()
        for name, widget in self._widgets.items():
            if widget is None:
                continue
            try:
                seen.add(id(widget))
            except Exception:
                pass
            self._invalidate_widget_effect(widget, name, refresh_effects)

        for attr_name in (
            "clock_widget",
            "clock2_widget",
            "clock3_widget",
            "weather_widget",
            "media_widget",
            "spotify_visualizer_widget",
            "spotify_volume_widget",
            "reddit_widget",
            "reddit2_widget",
        ):
            try:
                widget = getattr(self._parent, attr_name, None)
            except Exception:
                widget = None
            if widget is None:
                continue
            try:
                if id(widget) in seen:
                    continue
            except Exception:
                pass
            self._invalidate_widget_effect(widget, attr_name, refresh_effects)

    def _invalidate_widget_effect(self, widget: QWidget, name: str, refresh: bool) -> None:
        """Invalidate a single widget's graphics effect.
        
        Args:
            widget: The widget to invalidate
            name: Widget name for logging
            refresh: If True, recreate the effect instead of just toggling
        """
        try:
            eff = widget.graphicsEffect()
        except Exception:
            eff = None

        if isinstance(eff, (QGraphicsDropShadowEffect, QGraphicsOpacityEffect)):
            if refresh:
                # Skip recreation if widget is mid-animation (has active fades)
                try:
                    anim = getattr(widget, "_shadowfade_anim", None)
                except Exception:
                    anim = None
                try:
                    shadow_anim = getattr(widget, "_shadowfade_shadow_anim", None)
                except Exception:
                    shadow_anim = None

                if anim is None and shadow_anim is None:
                    eff = self._recreate_effect(widget, eff)

            # Toggle enable state to force Qt repaint
            try:
                eff.setEnabled(False)
                eff.setEnabled(True)
            except Exception:
                pass

            # Force property refresh for drop shadows
            if isinstance(eff, QGraphicsDropShadowEffect):
                try:
                    eff.setBlurRadius(eff.blurRadius())
                    eff.setOffset(eff.offset())
                    eff.setColor(eff.color())
                except Exception:
                    pass

        # Request widget repaint
        try:
            if widget.isVisible():
                widget.update()
        except Exception:
            pass

    def _recreate_effect(self, widget: QWidget, old_eff: Any) -> Any:
        """Recreate a QGraphicsEffect to bust Qt's internal cache.
        
        Args:
            widget: The widget owning the effect
            old_eff: The existing effect to replace
            
        Returns:
            The new effect (or the old one if recreation failed)
        """
        if isinstance(old_eff, QGraphicsDropShadowEffect):
            try:
                blur = old_eff.blurRadius()
            except Exception:
                blur = None
            try:
                offset = old_eff.offset()
            except Exception:
                offset = None
            try:
                color = old_eff.color()
            except Exception:
                color = None

            try:
                widget.setGraphicsEffect(None)
            except Exception:
                pass

            try:
                new_eff = QGraphicsDropShadowEffect(widget)
                if blur is not None:
                    new_eff.setBlurRadius(blur)
                if offset is not None:
                    new_eff.setOffset(offset)
                if color is not None:
                    new_eff.setColor(color)
                widget.setGraphicsEffect(new_eff)
                return new_eff
            except Exception:
                try:
                    return widget.graphicsEffect()
                except Exception:
                    return old_eff

        elif isinstance(old_eff, QGraphicsOpacityEffect):
            try:
                opacity = old_eff.opacity()
            except Exception:
                opacity = None

            try:
                widget.setGraphicsEffect(None)
            except Exception:
                pass

            try:
                new_eff = QGraphicsOpacityEffect(widget)
                if opacity is not None:
                    new_eff.setOpacity(opacity)
                widget.setGraphicsEffect(new_eff)
                return new_eff
            except Exception:
                try:
                    return widget.graphicsEffect()
                except Exception:
                    return old_eff

        return old_eff

    def schedule_effect_invalidation(self, reason: str, delay_ms: int = 16) -> None:
        """Schedule a deferred effect invalidation.
        
        Useful when invalidation should happen after Qt event processing settles.
        
        Args:
            reason: The invalidation reason
            delay_ms: Delay in milliseconds before invalidation runs
        """
        try:
            pending = getattr(self, "_pending_effect_invalidation", False)
        except Exception:
            pending = False

        if pending:
            return

        try:
            setattr(self, "_pending_effect_invalidation", True)
        except Exception:
            pass

        def _run() -> None:
            try:
                self.invalidate_overlay_effects(reason)
            finally:
                try:
                    setattr(self, "_pending_effect_invalidation", False)
                except Exception:
                    pass

        try:
            QTimer.singleShot(max(0, delay_ms), _run)
        except Exception:
            _run()

    # =========================================================================
    # Overlay Fade Coordination
    # =========================================================================

    def reset_fade_coordination(self) -> None:
        """Reset fade coordination state for a new widget setup cycle."""
        self._overlay_fade_expected = set()
        self._overlay_fade_pending = {}
        self._overlay_fade_started = False
        if self._overlay_fade_timeout is not None:
            try:
                self._overlay_fade_timeout.stop()
                self._overlay_fade_timeout.deleteLater()
            except Exception:
                pass
            self._overlay_fade_timeout = None
        self._spotify_secondary_fade_starters = []

    def set_expected_overlays(self, expected: Set[str]) -> None:
        """Set the overlays expected to participate in coordinated fade.
        
        Args:
            expected: Set of overlay names (e.g., {"weather", "media", "reddit"})
        """
        self._overlay_fade_expected = set(expected)

    def add_expected_overlay(self, name: str) -> None:
        """Add an overlay to the expected set."""
        self._overlay_fade_expected.add(name)

    def request_overlay_fade_sync(self, overlay_name: str, starter: Callable[[], None]) -> None:
        """Register an overlay's initial fade so all widgets can fade together.

        Overlays call this when they are ready to start their first fade-in.
        We buffer the starter callbacks until either all expected overlays have
        registered or a short timeout elapses, then run them together.
        
        Args:
            overlay_name: Name of the overlay requesting fade
            starter: Callback to start the fade animation
        """
        expected = self._overlay_fade_expected
        started = self._overlay_fade_started

        if is_verbose_logging():
            screen_idx = getattr(self._parent, "screen_index", "?")
            logger.debug(
                "[OVERLAY_FADE] request_overlay_fade_sync: screen=%s overlay=%s expected=%s started=%s",
                screen_idx, overlay_name, sorted(expected) if expected else [], started,
            )

        # If coordination is not active or fades already kicked off, run now.
        if not expected or started:
            if is_verbose_logging():
                logger.debug(
                    "[OVERLAY_FADE] %s running starter immediately (expected=%s, started=%s)",
                    overlay_name, sorted(expected) if expected else [], started,
                )
            try:
                starter()
            except Exception:
                pass
            return

        self._overlay_fade_pending[overlay_name] = starter

        remaining = [name for name in expected if name not in self._overlay_fade_pending]
        if is_verbose_logging():
            logger.debug(
                "[OVERLAY_FADE] %s registered (pending=%s, remaining=%s)",
                overlay_name, sorted(self._overlay_fade_pending.keys()), sorted(remaining),
            )

        if not remaining:
            try:
                QTimer.singleShot(0, lambda: self._start_overlay_fades(force=False))
            except Exception:
                self._start_overlay_fades(force=False)
            return

        # Arm a timeout so a misbehaving overlay cannot block all fades.
        if self._overlay_fade_timeout is None:
            try:
                timeout = QTimer()
                timeout.setSingleShot(True)
                timeout.timeout.connect(lambda: self._start_overlay_fades(force=True))
                timeout.start(2500)
                self._overlay_fade_timeout = timeout
            except Exception:
                self._start_overlay_fades(force=True)

    def _start_overlay_fades(self, force: bool = False) -> None:
        """Kick off any pending overlay fade callbacks."""
        if self._overlay_fade_started:
            return
        self._overlay_fade_started = True

        if self._overlay_fade_timeout is not None:
            try:
                self._overlay_fade_timeout.stop()
                self._overlay_fade_timeout.deleteLater()
            except Exception:
                pass
            self._overlay_fade_timeout = None

        try:
            starters = list(self._overlay_fade_pending.values())
            names = list(self._overlay_fade_pending.keys())
        except Exception:
            starters = []
            names = []

        screen_idx = getattr(self._parent, "screen_index", "?")
        logger.debug(
            "[OVERLAY_FADE] starting overlay fades (screen=%s, force=%s, overlays=%s)",
            screen_idx, force, sorted(names),
        )
        self._overlay_fade_pending = {}

        # Warm-up delay to reduce pops on startup
        warmup_delay_ms = 0 if force else 250

        def _run_all_starters() -> None:
            """Run all starters synchronously so they fade together."""
            for starter in starters:
                try:
                    starter()
                except Exception:
                    pass
            try:
                # Delay secondary fades by 500ms so they start after primary overlays
                # are well into their 1500ms fade-in animation
                self._run_spotify_secondary_fades(base_delay_ms=500)
            except Exception:
                pass

        if warmup_delay_ms <= 0:
            _run_all_starters()
            return

        # Single timer to run ALL starters together after warmup
        try:
            QTimer.singleShot(warmup_delay_ms, _run_all_starters)
        except Exception:
            _run_all_starters()

    def _run_spotify_secondary_fades(self, *, base_delay_ms: int) -> None:
        """Start any queued Spotify second-wave fade callbacks."""
        starters = self._spotify_secondary_fade_starters
        if not starters:
            return

        try:
            queued = list(starters)
        except Exception:
            queued = []
        self._spotify_secondary_fade_starters = []

        delay_ms = max(0, int(base_delay_ms))
        for starter in queued:
            try:
                if delay_ms <= 0:
                    starter()
                else:
                    QTimer.singleShot(delay_ms, starter)
            except Exception:
                try:
                    starter()
                except Exception:
                    pass

    def register_spotify_secondary_fade(self, starter: Callable[[], None]) -> None:
        """Register a Spotify second-wave fade to run after primary overlays.

        When there is no primary overlay coordination active, or when the
        primary group has already started, the starter is run with a small
        delay so it still feels like a secondary pass without popping in
        ahead of other widgets.
        """
        expected = self._overlay_fade_expected

        # If no primary overlays are coordinated or already started, run with delay
        # Use 500ms delay to match the coordinated secondary fade timing
        if not expected or self._overlay_fade_started:
            try:
                QTimer.singleShot(500, starter)
            except Exception:
                try:
                    starter()
                except Exception:
                    pass
            return

        self._spotify_secondary_fade_starters.append(starter)

    # =========================================================================
    # Widget Factory Methods (Phase 1b)
    # =========================================================================

    def create_clock_widget(
        self,
        settings_key: str,
        attr_name: str,
        default_position: str,
        default_font_size: int,
        widgets_config: dict,
        shadows_config: dict,
        base_clock_settings: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
    ) -> Optional[ClockWidget]:
        """
        Create and configure a clock widget.
        
        Args:
            settings_key: Settings key ('clock', 'clock2', 'clock3')
            attr_name: Attribute name on parent widget
            default_position: Default position string
            default_font_size: Default font size
            widgets_config: Full widgets configuration dict
            shadows_config: Shadow configuration dict
            base_clock_settings: Base clock settings for inheritance
            screen_index: Screen index for monitor selection
            thread_manager: Optional ThreadManager for async operations
            
        Returns:
            Created ClockWidget or None if disabled
        """
        clock_settings = widgets_config.get(settings_key, {}) if isinstance(widgets_config, dict) else {}
        clock_enabled = SettingsManager.to_bool(clock_settings.get('enabled', False), False)
        clock_monitor_sel = clock_settings.get('monitor', 'ALL')
        
        try:
            show_on_this = (clock_monitor_sel == 'ALL') or (int(clock_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = True

        if not (clock_enabled and show_on_this):
            logger.debug("%s widget disabled in settings", settings_key)
            return None

        # Add to expected overlays for fade coordination (syncs to parent)
        self.add_expected_overlay(settings_key)

        def _resolve_style(key: str, default):
            """Resolve style with inheritance for secondary clocks."""
            if settings_key == 'clock':
                if isinstance(clock_settings, dict) and key in clock_settings:
                    return clock_settings[key]
                return default
            if isinstance(base_clock_settings, dict) and key in base_clock_settings:
                return base_clock_settings[key]
            return default

        position_map = {
            'Top Left': ClockPosition.TOP_LEFT,
            'Top Center': ClockPosition.TOP_CENTER,
            'Top Right': ClockPosition.TOP_RIGHT,
            'Middle Left': ClockPosition.MIDDLE_LEFT,
            'Center': ClockPosition.CENTER,
            'Middle Right': ClockPosition.MIDDLE_RIGHT,
            'Bottom Left': ClockPosition.BOTTOM_LEFT,
            'Bottom Center': ClockPosition.BOTTOM_CENTER,
            'Bottom Right': ClockPosition.BOTTOM_RIGHT,
        }

        raw_format = _resolve_style('format', '12h')
        time_format = TimeFormat.TWELVE_HOUR if raw_format == '12h' else TimeFormat.TWENTY_FOUR_HOUR
        position_str = _resolve_style('position', default_position)
        show_seconds = SettingsManager.to_bool(_resolve_style('show_seconds', False), False)
        timezone_str = clock_settings.get('timezone', 'local')
        show_timezone = SettingsManager.to_bool(_resolve_style('show_timezone', False), False)
        font_size = _resolve_style('font_size', default_font_size)
        margin = _resolve_style('margin', 20)
        color = _resolve_style('color', [255, 255, 255, 230])
        bg_color_data = _resolve_style('bg_color', [64, 64, 64, 255])
        border_color_data = _resolve_style('border_color', [128, 128, 128, 255])
        border_opacity_val = _resolve_style('border_opacity', 0.8)

        position = position_map.get(position_str, position_map.get(default_position, ClockPosition.TOP_RIGHT))

        try:
            clock = ClockWidget(self._parent, time_format, position, show_seconds, timezone_str, show_timezone)

            font_family = _resolve_style('font_family', 'Segoe UI')
            if hasattr(clock, 'set_font_family'):
                clock.set_font_family(font_family)

            clock.set_font_size(font_size)
            clock.set_margin(margin)

            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                clock.set_text_color(qcolor)

            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            if bg_qcolor and hasattr(clock, "set_background_color"):
                clock.set_background_color(bg_qcolor)

            try:
                bo = float(border_opacity_val)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            if border_qcolor and hasattr(clock, "set_background_border"):
                clock.set_background_border(2, border_qcolor)

            show_bg_val = _resolve_style('show_background', False)
            show_background = SettingsManager.to_bool(show_bg_val, False)
            clock.set_show_background(show_background)

            bg_opacity = _resolve_style('bg_opacity', 0.9)
            clock.set_background_opacity(bg_opacity)

            try:
                display_mode_val = _resolve_style('display_mode', 'digital')
                if hasattr(clock, 'set_display_mode'):
                    clock.set_display_mode(display_mode_val)
            except Exception:
                pass

            try:
                show_numerals_val = _resolve_style('show_numerals', True)
                show_numerals = SettingsManager.to_bool(show_numerals_val, True)
                if hasattr(clock, 'set_show_numerals'):
                    clock.set_show_numerals(show_numerals)
            except Exception:
                pass

            try:
                analog_shadow_val = _resolve_style('analog_face_shadow', True)
                analog_shadow = SettingsManager.to_bool(analog_shadow_val, True)
                if hasattr(clock, 'set_analog_face_shadow'):
                    clock.set_analog_face_shadow(analog_shadow)
            except Exception:
                pass

            try:
                intense_shadow_val = _resolve_style('analog_shadow_intense', False)
                intense_shadow = SettingsManager.to_bool(intense_shadow_val, False)
                if hasattr(clock, 'set_analog_shadow_intense'):
                    clock.set_analog_shadow_intense(intense_shadow)
            except Exception:
                pass

            try:
                digital_intense_val = _resolve_style('digital_shadow_intense', False)
                digital_intense = SettingsManager.to_bool(digital_intense_val, False)
                if hasattr(clock, 'set_digital_shadow_intense'):
                    clock.set_digital_shadow_intense(digital_intense)
            except Exception:
                pass

            try:
                if hasattr(clock, "set_shadow_config"):
                    clock.set_shadow_config(shadows_config)
                else:
                    apply_widget_shadow(clock, shadows_config, has_background_frame=show_background)
            except Exception:
                pass

            try:
                if hasattr(clock, "set_overlay_name"):
                    clock.set_overlay_name(settings_key)
            except Exception:
                pass

            # Register with WidgetManager (but DON'T start yet - defer until all widgets created)
            self.register_widget(settings_key, clock)

            clock.raise_()
            # NOTE: start() is deferred to setup_all_widgets after all widgets are created
            # This ensures fade sync has the complete expected overlay set
            logger.info(
                "✅ %s widget created: %s, %s, font=%spx, seconds=%s",
                settings_key, position_str, time_format.value, font_size, show_seconds,
            )
            return clock
        except Exception as e:
            logger.error("Failed to create/configure %s widget: %s", settings_key, e, exc_info=True)
            return None

    def create_weather_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
    ) -> Optional[WeatherWidget]:
        """
        Create and configure a weather widget.
        
        Args:
            widgets_config: Full widgets configuration dict
            shadows_config: Shadow configuration dict
            screen_index: Screen index for monitor selection
            thread_manager: Optional ThreadManager for async operations
            
        Returns:
            Created WeatherWidget or None if disabled
        """
        weather_settings = widgets_config.get('weather', {}) if isinstance(widgets_config, dict) else {}
        weather_enabled = SettingsManager.to_bool(weather_settings.get('enabled', False), False)
        weather_monitor_sel = weather_settings.get('monitor', 'ALL')
        
        try:
            show_on_this = (weather_monitor_sel == 'ALL') or (int(weather_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = False

        if not (weather_enabled and show_on_this):
            return None

        self.add_expected_overlay("weather")

        position_str = weather_settings.get('position', 'Top Left')
        location = weather_settings.get('location', 'New York')
        font_size = weather_settings.get('font_size', 24)
        color = weather_settings.get('color', [255, 255, 255, 230])

        weather_position_map = {
            'Top Left': WeatherPosition.TOP_LEFT,
            'Top Center': WeatherPosition.TOP_CENTER,
            'Top Right': WeatherPosition.TOP_RIGHT,
            'Middle Left': WeatherPosition.MIDDLE_LEFT,
            'Center': WeatherPosition.CENTER,
            'Middle Right': WeatherPosition.MIDDLE_RIGHT,
            'Bottom Left': WeatherPosition.BOTTOM_LEFT,
            'Bottom Center': WeatherPosition.BOTTOM_CENTER,
            'Bottom Right': WeatherPosition.BOTTOM_RIGHT,
        }
        position = weather_position_map.get(position_str, WeatherPosition.TOP_LEFT)

        try:
            widget = WeatherWidget(self._parent, location, position)
            
            if thread_manager is not None and hasattr(widget, "set_thread_manager"):
                try:
                    widget.set_thread_manager(thread_manager)
                except Exception:
                    pass

            font_family = weather_settings.get('font_family', 'Segoe UI')
            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(font_family)

            widget.set_font_size(font_size)

            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                widget.set_text_color(qcolor)

            show_background = SettingsManager.to_bool(weather_settings.get('show_background', True), True)
            widget.set_show_background(show_background)

            bg_color_data = weather_settings.get('bg_color', [35, 35, 35, 255])
            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            if bg_qcolor:
                widget.set_background_color(bg_qcolor)

            bg_opacity = weather_settings.get('bg_opacity', 0.7)
            widget.set_background_opacity(bg_opacity)

            border_color_data = weather_settings.get('border_color', [255, 255, 255, 255])
            border_opacity = weather_settings.get('border_opacity', 1.0)
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 1.0
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            if border_qcolor:
                widget.set_background_border(2, border_qcolor)

            show_forecast = SettingsManager.to_bool(weather_settings.get('show_forecast', False), False)
            widget.set_show_forecast(show_forecast)

            # Apply margin setting
            margin = weather_settings.get('margin', 20)
            try:
                widget.set_margin(int(margin))
            except Exception:
                pass

            try:
                intense_shadow = SettingsManager.to_bool(weather_settings.get('intense_shadow', False), False)
                if hasattr(widget, 'set_intense_shadow'):
                    widget.set_intense_shadow(intense_shadow)
            except Exception:
                pass

            try:
                if hasattr(widget, "set_shadow_config"):
                    widget.set_shadow_config(shadows_config)
                else:
                    apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
            except Exception:
                pass

            self.register_widget("weather", widget)
            widget.raise_()
            # NOTE: start() deferred to setup_all_widgets for fade sync
            logger.info("✅ Weather widget created: %s, %s, font=%spx", location, position_str, font_size)
            return widget
        except Exception as e:
            logger.error("Failed to create weather widget: %s", e, exc_info=True)
            return None

    def create_media_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
    ) -> Optional[MediaWidget]:
        """
        Create and configure a media widget.
        
        Args:
            widgets_config: Full widgets configuration dict
            shadows_config: Shadow configuration dict
            screen_index: Screen index for monitor selection
            thread_manager: Optional ThreadManager for async operations
            
        Returns:
            Created MediaWidget or None if disabled
        """
        media_settings = widgets_config.get('media', {}) if isinstance(widgets_config, dict) else {}
        media_enabled = SettingsManager.to_bool(media_settings.get('enabled', False), False)
        media_monitor_sel = media_settings.get('monitor', 'ALL')
        
        try:
            show_on_this = (media_monitor_sel == 'ALL') or (int(media_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = False

        if not (media_enabled and show_on_this):
            return None

        self.add_expected_overlay("media")

        position_str = media_settings.get('position', 'Bottom Left')
        font_size = media_settings.get('font_size', 20)
        margin = media_settings.get('margin', 20)
        color = media_settings.get('color', [255, 255, 255, 230])
        artwork_size = media_settings.get('artwork_size', 100)
        rounded_artwork = SettingsManager.to_bool(media_settings.get('rounded_artwork_border', True), True)
        show_controls = SettingsManager.to_bool(media_settings.get('show_controls', True), True)
        show_header_frame = SettingsManager.to_bool(media_settings.get('show_header_frame', True), True)

        media_position_map = {
            'Top Left': MediaPosition.TOP_LEFT,
            'Top Center': MediaPosition.TOP_CENTER,
            'Top Right': MediaPosition.TOP_RIGHT,
            'Middle Left': MediaPosition.MIDDLE_LEFT,
            'Center': MediaPosition.CENTER,
            'Middle Right': MediaPosition.MIDDLE_RIGHT,
            'Bottom Left': MediaPosition.BOTTOM_LEFT,
            'Bottom Center': MediaPosition.BOTTOM_CENTER,
            'Bottom Right': MediaPosition.BOTTOM_RIGHT,
        }
        position = media_position_map.get(position_str, MediaPosition.BOTTOM_LEFT)

        try:
            widget = MediaWidget(self._parent, position=position)

            if thread_manager is not None and hasattr(widget, "set_thread_manager"):
                try:
                    widget.set_thread_manager(thread_manager)
                except Exception:
                    pass

            font_family = media_settings.get('font_family', 'Segoe UI')
            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(font_family)

            try:
                widget.set_font_size(int(font_size))
            except Exception:
                widget.set_font_size(20)

            try:
                margin_val = int(margin)
            except Exception:
                margin_val = 20
            widget.set_margin(margin_val)

            # Artwork size, border shape, and controls visibility
            try:
                if hasattr(widget, 'set_artwork_size'):
                    widget.set_artwork_size(int(artwork_size))
            except Exception:
                pass
            try:
                if hasattr(widget, 'set_rounded_artwork_border'):
                    widget.set_rounded_artwork_border(rounded_artwork)
            except Exception:
                pass
            try:
                if hasattr(widget, 'set_show_controls'):
                    widget.set_show_controls(show_controls)
            except Exception:
                pass
            try:
                if hasattr(widget, 'set_show_header_frame'):
                    widget.set_show_header_frame(show_header_frame)
            except Exception:
                pass

            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                widget.set_text_color(qcolor)

            show_background = SettingsManager.to_bool(media_settings.get('show_background', True), True)
            widget.set_show_background(show_background)

            bg_color_data = media_settings.get('bg_color', [64, 64, 64, 255])
            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            if bg_qcolor:
                widget.set_background_color(bg_qcolor)

            try:
                bg_opacity = float(media_settings.get('bg_opacity', 0.9))
            except Exception:
                bg_opacity = 0.9
            widget.set_background_opacity(bg_opacity)

            # Border color and opacity
            border_color_data = media_settings.get('border_color', [128, 128, 128, 255])
            border_opacity = media_settings.get('border_opacity', 0.8)
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            if border_qcolor:
                widget.set_background_border(2, border_qcolor)

            try:
                intense_shadow = SettingsManager.to_bool(media_settings.get('intense_shadow', False), False)
                if hasattr(widget, 'set_intense_shadow'):
                    widget.set_intense_shadow(intense_shadow)
            except Exception:
                pass

            try:
                if hasattr(widget, "set_shadow_config"):
                    widget.set_shadow_config(shadows_config)
                else:
                    apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
            except Exception:
                pass

            self.register_widget("media", widget)
            widget.raise_()
            # NOTE: start() deferred to setup_all_widgets for fade sync
            logger.info("✅ Media widget created: %s, font=%spx, margin=%d", position_str, font_size, margin_val)
            return widget
        except Exception as e:
            logger.error("Failed to create media widget: %s", e, exc_info=True)
            return None

    def create_reddit_widget(
        self,
        settings_key: str,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        base_reddit_settings: Optional[dict] = None,
    ) -> Optional[RedditWidget]:
        """
        Create and configure a Reddit widget.
        
        Args:
            settings_key: Settings key ('reddit' or 'reddit2')
            widgets_config: Full widgets configuration dict
            shadows_config: Shadow configuration dict
            screen_index: Screen index for monitor selection
            thread_manager: Optional ThreadManager for async operations
            base_reddit_settings: For reddit2, inherit styling from reddit1
            
        Returns:
            Created RedditWidget or None if disabled
        """
        reddit_settings = widgets_config.get(settings_key, {}) if isinstance(widgets_config, dict) else {}
        reddit_enabled = SettingsManager.to_bool(reddit_settings.get('enabled', False), False)
        reddit_monitor_sel = reddit_settings.get('monitor', 'ALL')
        
        try:
            show_on_this = (reddit_monitor_sel == 'ALL') or (int(reddit_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = False

        if not (reddit_enabled and show_on_this):
            return None

        self.add_expected_overlay(settings_key)

        # For reddit2, inherit styling from reddit1 (base_reddit_settings)
        style_source = base_reddit_settings if (settings_key == 'reddit2' and base_reddit_settings) else reddit_settings

        position_str = reddit_settings.get('position', 'Bottom Right')
        subreddit = reddit_settings.get('subreddit', 'wallpapers') or 'wallpapers'
        
        # Styling from style_source (reddit1 for reddit2, own settings for reddit1)
        font_size = style_source.get('font_size', 14)
        margin = style_source.get('margin', 20)
        color = style_source.get('color', [255, 255, 255, 230])
        bg_color_data = style_source.get('bg_color', [35, 35, 35, 255])
        border_color_data = style_source.get('border_color', [255, 255, 255, 255])
        border_opacity = style_source.get('border_opacity', 1.0)
        show_background = SettingsManager.to_bool(style_source.get('show_background', True), True)
        show_separators = SettingsManager.to_bool(style_source.get('show_separators', True), True)
        bg_opacity = style_source.get('bg_opacity', 1.0)
        font_family = style_source.get('font_family', 'Segoe UI')
        
        # Limit comes from own settings
        try:
            limit_val = int(reddit_settings.get('limit', 10))
        except Exception:
            limit_val = 10
        limit_val = max(4, min(limit_val, 25))

        reddit_position_map = {
            'Top Left': RedditPosition.TOP_LEFT,
            'Top Center': RedditPosition.TOP_CENTER,
            'Top Right': RedditPosition.TOP_RIGHT,
            'Middle Left': RedditPosition.MIDDLE_LEFT,
            'Center': RedditPosition.CENTER,
            'Middle Right': RedditPosition.MIDDLE_RIGHT,
            'Bottom Left': RedditPosition.BOTTOM_LEFT,
            'Bottom Center': RedditPosition.BOTTOM_CENTER,
            'Bottom Right': RedditPosition.BOTTOM_RIGHT,
        }
        position = reddit_position_map.get(position_str, RedditPosition.BOTTOM_RIGHT)

        try:
            widget = RedditWidget(self._parent, subreddit=subreddit, position=position)

            if thread_manager is not None and hasattr(widget, "set_thread_manager"):
                try:
                    widget.set_thread_manager(thread_manager)
                except Exception:
                    pass

            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(font_family)

            try:
                widget.set_font_size(int(font_size))
            except Exception:
                widget.set_font_size(14)

            try:
                margin_val = int(margin)
            except Exception:
                margin_val = 20
            widget.set_margin(margin_val)

            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                widget.set_text_color(qcolor)

            widget.set_show_background(show_background)

            try:
                widget.set_show_separators(show_separators)
            except Exception:
                pass

            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            if bg_qcolor:
                widget.set_background_color(bg_qcolor)

            try:
                bg_opacity_f = float(bg_opacity)
            except Exception:
                bg_opacity_f = 0.9
            widget.set_background_opacity(bg_opacity_f)

            # Border color and opacity
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            if border_qcolor:
                widget.set_background_border(2, border_qcolor)

            # Item limit
            try:
                widget.set_item_limit(limit_val)
            except Exception:
                pass

            # Intense shadow
            try:
                intense_shadow = SettingsManager.to_bool(style_source.get('intense_shadow', False), False)
                if hasattr(widget, 'set_intense_shadow'):
                    widget.set_intense_shadow(intense_shadow)
            except Exception:
                pass

            # Shadow config
            try:
                if hasattr(widget, "set_shadow_config"):
                    widget.set_shadow_config(shadows_config)
                else:
                    apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
            except Exception:
                pass

            # Overlay name for fade coordination
            try:
                if hasattr(widget, 'set_overlay_name'):
                    widget.set_overlay_name(settings_key)
            except Exception:
                pass

            self.register_widget(settings_key, widget)
            widget.raise_()
            # NOTE: start() deferred to setup_all_widgets for fade sync
            logger.info("✅ %s widget created: r/%s, %s, font=%spx, limit=%d", settings_key, subreddit, position_str, font_size, limit_val)
            return widget
        except Exception as e:
            logger.error("Failed to create %s widget: %s", settings_key, e, exc_info=True)
            return None

    # Gmail widget creation method removed - archived in archive/gmail_feature/

    def setup_all_widgets(
        self,
        settings_manager: SettingsManager,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
    ) -> dict:
        """
        Set up all overlay widgets based on settings.
        
        This is the main entry point for widget creation, replacing the
        monolithic _setup_widgets method in DisplayWidget.
        
        Args:
            settings_manager: SettingsManager instance
            screen_index: Screen index for monitor selection
            thread_manager: Optional ThreadManager for async operations
            
        Returns:
            Dict of created widgets keyed by name
        """
        if not settings_manager:
            logger.warning("No settings_manager provided - widgets will not be created")
            return {}

        logger.debug("Setting up overlay widgets for screen %d", screen_index)

        widgets_config = settings_manager.get('widgets', {})
        if not isinstance(widgets_config, dict):
            widgets_config = {}

        base_clock_settings = widgets_config.get('clock', {}) if isinstance(widgets_config, dict) else {}
        shadows_config = widgets_config.get('shadows', {}) if isinstance(widgets_config, dict) else {}

        # Reset fade coordination
        self.reset_fade_coordination()

        created = {}

        # Create clock widgets
        for settings_key, attr_name, default_pos, default_size in [
            ('clock', 'clock_widget', 'Top Right', 48),
            ('clock2', 'clock2_widget', 'Bottom Right', 32),
            ('clock3', 'clock3_widget', 'Bottom Left', 32),
        ]:
            widget = self.create_clock_widget(
                settings_key, attr_name, default_pos, default_size,
                widgets_config, shadows_config, base_clock_settings,
                screen_index, thread_manager,
            )
            if widget:
                created[attr_name] = widget

        # Create weather widget
        widget = self.create_weather_widget(widgets_config, shadows_config, screen_index, thread_manager)
        if widget:
            created['weather_widget'] = widget

        # Create media widget
        widget = self.create_media_widget(widgets_config, shadows_config, screen_index, thread_manager)
        if widget:
            created['media_widget'] = widget

        # Create reddit widgets (reddit2 inherits styling from reddit1)
        base_reddit_settings = widgets_config.get('reddit', {}) if isinstance(widgets_config, dict) else {}
        for settings_key, attr_name in [('reddit', 'reddit_widget'), ('reddit2', 'reddit2_widget')]:
            widget = self.create_reddit_widget(
                settings_key, widgets_config, shadows_config, screen_index, thread_manager,
                base_reddit_settings=base_reddit_settings if settings_key == 'reddit2' else None,
            )
            if widget:
                created[attr_name] = widget

        # Gmail widget archived - see archive/gmail_feature/

        # Create Spotify widgets (require media widget)
        media_widget = created.get('media_widget')
        if media_widget:
            # Spotify volume widget
            vol_widget = self.create_spotify_volume_widget(
                widgets_config, shadows_config, screen_index, thread_manager, media_widget,
            )
            if vol_widget:
                created['spotify_volume_widget'] = vol_widget
            
            # Spotify visualizer widget
            vis_widget = self.create_spotify_visualizer_widget(
                widgets_config, shadows_config, screen_index, thread_manager, media_widget,
            )
            if vis_widget:
                created['spotify_visualizer_widget'] = vis_widget

        # NOW start all widgets - this ensures fade sync has complete expected overlay set
        # All widgets are created and their expected overlays are registered before any
        # widget calls request_overlay_fade_sync(), so they will all wait for each other.
        logger.debug("[FADE_SYNC] Starting %d widgets with expected overlays: %s",
                     len(created), sorted(self._overlay_fade_expected))
        
        for attr_name, widget in created.items():
            if widget is not None and hasattr(widget, 'start'):
                try:
                    widget.start()
                except Exception as e:
                    logger.debug("Failed to start %s: %s", attr_name, e)

        logger.info("Widget setup complete: %d widgets created and started", len(created))
        return created

    def create_spotify_volume_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ) -> Optional[SpotifyVolumeWidget]:
        """Create and configure a Spotify volume widget."""
        if media_widget is None:
            return None
        
        media_settings = widgets_config.get('media', {}) if isinstance(widgets_config, dict) else {}
        spotify_volume_enabled = SettingsManager.to_bool(media_settings.get('spotify_volume_enabled', True), True)
        
        media_monitor_sel = media_settings.get('monitor', 'ALL')
        try:
            show_on_this = (media_monitor_sel == 'ALL') or (int(media_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = False
        
        if not (spotify_volume_enabled and show_on_this):
            return None
        
        try:
            vol = SpotifyVolumeWidget(self._parent)
            
            if thread_manager is not None and hasattr(vol, "set_thread_manager"):
                try:
                    vol.set_thread_manager(thread_manager)
                except Exception:
                    pass
            
            try:
                vol.set_shadow_config(shadows_config)
            except Exception:
                pass
            
            # Set anchor to media widget for visibility gating
            try:
                if hasattr(vol, "set_anchor_media_widget"):
                    vol.set_anchor_media_widget(media_widget)
            except Exception:
                pass
            
            # Inherit media card background and border colours
            bg_color_data = media_settings.get('bg_color', [64, 64, 64, 255])
            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            border_color_data = media_settings.get('border_color', [128, 128, 128, 255])
            border_opacity = media_settings.get('border_opacity', 0.8)
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            
            try:
                from PySide6.QtGui import QColor as _QColor
                fill_color_data = media_settings.get('spotify_volume_fill_color', [255, 255, 255, 230])
                try:
                    fr, fg, fb = fill_color_data[0], fill_color_data[1], fill_color_data[2]
                    fa = fill_color_data[3] if len(fill_color_data) > 3 else 230
                    fill_color = _QColor(fr, fg, fb, fa)
                except Exception:
                    fill_color = _QColor(255, 255, 255, 230)
                
                if hasattr(vol, "set_colors"):
                    vol.set_colors(track_bg=bg_qcolor, track_border=border_qcolor, fill=fill_color)
            except Exception:
                pass
            
            self.register_widget("spotify_volume", vol)
            vol.raise_()
            # Add to expected overlays so it participates in coordinated fade
            self.add_expected_overlay("spotify_volume")
            # Call start() - the widget now uses request_overlay_fade_sync internally
            vol.start()
            logger.info("✅ Spotify volume widget started with coordinated fade sync")
            return vol
        except Exception as e:
            logger.error("Failed to create Spotify volume widget: %s", e, exc_info=True)
            return None

    def create_spotify_visualizer_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ) -> Optional[SpotifyVisualizerWidget]:
        """Create and configure a Spotify visualizer widget."""
        if media_widget is None:
            return None
        
        media_settings = widgets_config.get('media', {}) if isinstance(widgets_config, dict) else {}
        spotify_vis_settings = widgets_config.get('spotify_visualizer', {}) if isinstance(widgets_config, dict) else {}
        spotify_vis_enabled = SettingsManager.to_bool(spotify_vis_settings.get('enabled', False), False)
        
        media_monitor_sel = media_settings.get('monitor', 'ALL')
        try:
            show_on_this = (media_monitor_sel == 'ALL') or (int(media_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = False
        
        if not (spotify_vis_enabled and show_on_this):
            return None
        
        self.add_expected_overlay("spotify_visualizer")
        
        try:
            bar_count = int(spotify_vis_settings.get('bar_count', 32))
            vis = SpotifyVisualizerWidget(self._parent, bar_count=bar_count)
            
            # Preferred audio block size (0=auto)
            try:
                block_size = int(spotify_vis_settings.get('audio_block_size', 0) or 0)
                if hasattr(vis, 'set_audio_block_size'):
                    vis.set_audio_block_size(block_size)
            except Exception:
                pass
            
            # ThreadManager for animation tick scheduling
            if thread_manager is not None and hasattr(vis, 'set_thread_manager'):
                try:
                    vis.set_thread_manager(thread_manager)
                except Exception:
                    pass
            
            # Anchor geometry to media widget
            try:
                vis.set_anchor_media_widget(media_widget)
            except Exception:
                pass
            
            # Card style inheritance from media widget
            bg_color_data = media_settings.get('bg_color', [64, 64, 64, 255])
            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            try:
                bg_opacity = float(media_settings.get('bg_opacity', 0.9))
            except Exception:
                bg_opacity = 0.9
            border_color_data = media_settings.get('border_color', [128, 128, 128, 255])
            border_opacity = media_settings.get('border_opacity', 0.8)
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            show_background = SettingsManager.to_bool(media_settings.get('show_background', True), True)
            
            try:
                vis.set_bar_style(
                    bg_color=bg_qcolor,
                    bg_opacity=bg_opacity,
                    border_color=border_qcolor,
                    border_width=2,
                    show_background=show_background,
                )
            except Exception:
                pass
            
            # Per-bar colours
            from PySide6.QtGui import QColor as _QColor
            try:
                fill_color_data = spotify_vis_settings.get('bar_fill_color', [255, 255, 255, 230])
                fr, fg, fb = fill_color_data[0], fill_color_data[1], fill_color_data[2]
                fa = fill_color_data[3] if len(fill_color_data) > 3 else 230
                bar_fill_qcolor = _QColor(fr, fg, fb, fa)
            except Exception:
                bar_fill_qcolor = _QColor(255, 255, 255, 230)
            
            try:
                bar_border_color_data = spotify_vis_settings.get('bar_border_color', [255, 255, 255, 230])
                br_r, br_g, br_b = bar_border_color_data[0], bar_border_color_data[1], bar_border_color_data[2]
                base_alpha = bar_border_color_data[3] if len(bar_border_color_data) > 3 else 230
                try:
                    bar_bo = float(spotify_vis_settings.get('bar_border_opacity', 0.85))
                except Exception:
                    bar_bo = 0.85
                bar_bo = max(0.0, min(1.0, bar_bo))
                br_a = int(bar_bo * base_alpha)
                bar_border_qcolor = _QColor(br_r, br_g, br_b, br_a)
            except Exception:
                bar_border_qcolor = _QColor(255, 255, 255, 230)
            
            try:
                vis.set_bar_colors(bar_fill_qcolor, bar_border_qcolor)
            except Exception:
                pass
            
            # Ghosting configuration
            try:
                ghost_enabled = SettingsManager.to_bool(spotify_vis_settings.get('ghosting_enabled', True), True)
                ghost_alpha = float(spotify_vis_settings.get('ghost_alpha', 0.4))
                ghost_decay = max(0.0, float(spotify_vis_settings.get('ghost_decay', 0.4)))
                if hasattr(vis, 'set_ghost_config'):
                    vis.set_ghost_config(ghost_enabled, ghost_alpha, ghost_decay)
            except Exception:
                pass
            
            # Sensitivity configuration
            try:
                recommended = SettingsManager.to_bool(spotify_vis_settings.get('adaptive_sensitivity', True), True)
                sens = max(0.25, min(2.5, float(spotify_vis_settings.get('sensitivity', 1.0))))
                if hasattr(vis, 'set_sensitivity_config'):
                    vis.set_sensitivity_config(recommended, sens)
            except Exception:
                pass

            # Visualization mode (only spectrum supported)
            try:
                if hasattr(vis, 'set_visualization_mode'):
                    from widgets.spotify_visualizer_widget import VisualizerMode
                    vis.set_visualization_mode(VisualizerMode.SPECTRUM)
            except Exception:
                pass

            # Noise floor configuration
            try:
                dynamic_floor = SettingsManager.to_bool(
                    spotify_vis_settings.get('dynamic_floor', True),
                    True,
                )
                manual_floor = float(spotify_vis_settings.get('manual_floor', 2.1))
                if hasattr(vis, 'set_floor_config'):
                    vis.set_floor_config(dynamic_floor, manual_floor)
            except Exception:
                pass

            # Shadow config
            try:
                vis.set_shadow_config(shadows_config)
            except Exception:
                pass
            
            # Wire media state into visualizer
            try:
                if not getattr(vis, "_srpss_media_connected", False):
                    media_widget.media_updated.connect(vis.handle_media_update)
                    setattr(vis, "_srpss_media_connected", True)
            except Exception:
                pass
            
            self.register_widget("spotify_visualizer", vis)
            vis.raise_()
            vis.start()
            logger.info("✅ Spotify visualizer widget started: %d bars", bar_count)
            return vis
        except Exception as e:
            logger.error("Failed to create Spotify visualizer widget: %s", e, exc_info=True)
            return None
