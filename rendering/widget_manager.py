"""
Widget Manager - Extracted from DisplayWidget for better separation of concerns.

Manages overlay widget lifecycle, positioning, visibility, and Z-order.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING, Mapping

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect

from core.logging.logger import get_logger, is_verbose_logging
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
from rendering.widget_setup import parse_color_to_qcolor, compute_expected_overlays
from widgets.media_widget import MediaWidget
# Gmail widget archived - see archive/gmail_feature/RESTORE_GMAIL.md
# from widgets.gmail_widget import GmailWidget, GmailPosition
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from core.settings.models import SpotifyVisualizerSettings, MediaWidgetSettings, RedditWidgetSettings
from widgets.spotify_volume_widget import SpotifyVolumeWidget
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

        # Settings manager wiring for live updates (Spotify VIS etc.)
        self._settings_manager: Optional[SettingsManager] = None
        
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

    # =========================================================================
    # Settings integration
    # =========================================================================

    def _attach_settings_manager(self, settings_manager: SettingsManager) -> None:
        """Subscribe to settings changes for live widget updates."""
        if settings_manager is None:
            return
        if self._settings_manager is settings_manager:
            return
        self._detach_settings_manager()
        self._settings_manager = settings_manager
        try:
            settings_manager.settings_changed.connect(self._handle_settings_changed)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to connect settings_changed signal", exc_info=True)

    def _detach_settings_manager(self) -> None:
        """Disconnect previously attached settings manager, if any."""
        if self._settings_manager is None:
            return
        try:
            self._settings_manager.settings_changed.disconnect(self._handle_settings_changed)
        except Exception:
            pass
        finally:
            self._settings_manager = None

    def _handle_settings_changed(self, key: str, value: object) -> None:
        """React to settings changes for live widget updates."""
        try:
            setting_key = str(key) if key is not None else ""
        except Exception:
            setting_key = ""
        if not setting_key:
            return

        try:
            logger.debug("[WIDGET_MANAGER][SETTINGS] key=%s payload_type=%s", setting_key, type(value).__name__)
        except Exception:
            pass

        if setting_key == 'widgets':
            widgets_payload: Optional[Mapping[str, Any]] = value if isinstance(value, Mapping) else None
            self._refresh_spotify_visualizer_config(widgets_payload)
            self._refresh_media_config(widgets_payload)
            self._refresh_reddit_configs(widgets_payload)
            return

        if setting_key.startswith('widgets.spotify_visualizer'):
            self._refresh_spotify_visualizer_config()
            return

        if setting_key.startswith('widgets.media'):
            self._refresh_media_config()
            return

        if setting_key.startswith('widgets.reddit'):
            self._refresh_reddit_configs()
            return

    def _log_spotify_vis_config(self, context: str, cfg: Mapping[str, Any]) -> None:
        """Emit a single structured log line for Spotify VIS config rewires."""
        try:
            logger.info(
                "[SPOTIFY_VIS][CFG] %s adaptive=%s sensitivity=%.3f dynamic=%s manual=%.3f",
                context,
                cfg.get('adaptive_sensitivity'),
                float(cfg.get('sensitivity', 0.0)),
                cfg.get('dynamic_floor'),
                float(cfg.get('manual_floor', 0.0)),
            )
        except Exception:
            logger.debug("[SPOTIFY_VIS][CFG] %s %s", context, cfg, exc_info=True)

    def _apply_media_card_style_to_visualizer(
        self,
        vis_widget: Optional["SpotifyVisualizerWidget"],
        media_settings: Optional[Mapping[str, Any]],
    ) -> None:
        """Apply media widget card styling to the Spotify visualizer card."""
        if vis_widget is None:
            return

        settings_map = media_settings if isinstance(media_settings, Mapping) else {}

        bg_color_data = settings_map.get("bg_color") or settings_map.get("background_color") or [64, 64, 64, 255]
        bg_qcolor = parse_color_to_qcolor(bg_color_data)

        try:
            bg_opacity = float(settings_map.get("bg_opacity", settings_map.get("background_opacity", 0.9)))
        except Exception:
            bg_opacity = 0.9

        border_color_data = settings_map.get("border_color", [128, 128, 128, 255])
        try:
            border_opacity = float(settings_map.get("border_opacity", 0.8))
        except Exception:
            border_opacity = 0.8
        border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=border_opacity)

        show_background = SettingsManager.to_bool(settings_map.get("show_background", True), True)
        try:
            border_width = int(settings_map.get("border_width", 2) or 2)
        except Exception:
            border_width = 2

        try:
            vis_widget.set_bar_style(
                bg_color=bg_qcolor or parse_color_to_qcolor([64, 64, 64, 255]),
                bg_opacity=bg_opacity,
                border_color=border_qcolor or parse_color_to_qcolor([128, 128, 128, 255]),
                border_width=max(0, border_width),
                show_background=show_background,
            )
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to apply media card style to visualizer", exc_info=True)

    def _refresh_spotify_visualizer_config(self, widgets_config: Optional[Mapping[str, Any]] = None) -> None:
        """Apply latest Spotify VIS sensitivity / floor settings to the live widget."""
        vis = self._widgets.get('spotify_visualizer') or self._widgets.get('spotify_visualizer_widget')
        if vis is None or not hasattr(vis, 'set_sensitivity_config'):
            return

        cfg = widgets_config
        if cfg is None:
            if self._settings_manager is None:
                return
            cfg = self._settings_manager.get('widgets', {}) or {}
        if not isinstance(cfg, Mapping):
            return

        spotify_cfg = cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_cfg, Mapping):
            return

        model = SpotifyVisualizerSettings.from_mapping(spotify_cfg)
        self._log_spotify_vis_config("refresh", spotify_cfg)

        # Sensitivity (adaptive or manual multiplier)
        try:
            recommended = SettingsManager.to_bool(model.adaptive_sensitivity, True)
            sens_raw = float(model.sensitivity)
            sensitivity = max(0.25, min(2.5, sens_raw))
            vis.set_sensitivity_config(recommended, sensitivity)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply Spotify sensitivity config", exc_info=True)

        # Noise floor (dynamic/manual)
        try:
            dynamic_floor = SettingsManager.to_bool(model.dynamic_floor, True)
            manual_floor = float(model.manual_floor)
            vis.set_floor_config(dynamic_floor, manual_floor)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply Spotify floor config", exc_info=True)

        media_cfg = cfg.get('media', {}) if isinstance(cfg, Mapping) else {}
        self._apply_media_card_style_to_visualizer(vis, media_cfg)

    def _refresh_media_config(self, widgets_config: Optional[Mapping[str, Any]] = None) -> None:
        """Apply latest media settings to the live media widget (colors/volume flag)."""
        media_widget = self._widgets.get('media_widget') or self._widgets.get('media')
        if media_widget is None:
            return

        cfg = widgets_config
        if cfg is None:
            if self._settings_manager is None:
                return
            cfg = self._settings_manager.get('widgets', {}) or {}
        if not isinstance(cfg, Mapping):
            return

        media_cfg = cfg.get('media', {})
        if not isinstance(media_cfg, Mapping):
            return

        model = MediaWidgetSettings.from_mapping(media_cfg)

        try:
            if hasattr(media_widget, 'set_text_color'):
                media_widget.set_text_color(parse_color_to_qcolor(model.color))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media text color", exc_info=True)

        try:
            if hasattr(media_widget, 'set_background_color'):
                media_widget.set_background_color(parse_color_to_qcolor(model.bg_color))
            if hasattr(media_widget, 'set_background_opacity'):
                media_widget.set_background_opacity(float(model.background_opacity))
            if hasattr(media_widget, 'set_background_border'):
                border_qcolor = parse_color_to_qcolor(model.border_color, opacity_override=model.border_opacity)
                if border_qcolor:
                    media_widget.set_background_border(2, border_qcolor)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media background/border", exc_info=True)

        try:
            if hasattr(media_widget, 'set_show_controls'):
                media_widget.set_show_controls(SettingsManager.to_bool(model.show_controls, True))
            if hasattr(media_widget, 'set_show_header_frame'):
                media_widget.set_show_header_frame(SettingsManager.to_bool(model.show_header_frame, True))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media controls/header", exc_info=True)

        vis_widget = self._widgets.get('spotify_visualizer') or self._widgets.get('spotify_visualizer_widget')
        if vis_widget is not None:
            self._apply_media_card_style_to_visualizer(vis_widget, media_cfg)

    def _refresh_reddit_configs(self, widgets_config: Optional[Mapping[str, Any]] = None) -> None:
        """Apply latest reddit settings to live reddit widgets (reddit, reddit2)."""
        targets = [('reddit', self._widgets.get('reddit_widget')), ('reddit2', self._widgets.get('reddit2_widget'))]
        if all(w is None for _, w in targets):
            return

        cfg = widgets_config
        if cfg is None:
            if self._settings_manager is None:
                return
            cfg = self._settings_manager.get('widgets', {}) or {}
        if not isinstance(cfg, Mapping):
            return

        base_reddit_cfg = cfg.get('reddit', {}) if isinstance(cfg.get('reddit', {}), Mapping) else cfg.get('reddit', {})

        for key, widget in targets:
            if widget is None:
                continue
            reddit_cfg = cfg.get(key, {})
            if not isinstance(reddit_cfg, Mapping):
                continue
            model = RedditWidgetSettings.from_mapping(reddit_cfg, prefix=f"widgets.{key}")

            style_fallback = base_reddit_cfg if (key == 'reddit2' and isinstance(base_reddit_cfg, Mapping)) else None

            def inherit_style(field: str, default: Any) -> Any:
                if field in reddit_cfg:
                    return reddit_cfg.get(field)
                if isinstance(style_fallback, Mapping) and field in style_fallback:
                    return style_fallback.get(field)
                return default

            try:
                font_family = inherit_style('font_family', model.font_family)
                font_size = inherit_style('font_size', model.font_size)
                margin = inherit_style('margin', model.margin)
                text_color = inherit_style('color', [255, 255, 255, 230])
                show_background = SettingsManager.to_bool(inherit_style('show_background', model.show_background), True)
                show_separators = SettingsManager.to_bool(inherit_style('show_separators', model.show_separators), True)
                bg_color_value = inherit_style('bg_color', inherit_style('background_color', [35, 35, 35, 255]))
                bg_opacity_value = inherit_style('bg_opacity', model.background_opacity)
                border_color_value = inherit_style('border_color', [255, 255, 255, 255])
                border_opacity_value = inherit_style('border_opacity', model.border_opacity)

                if hasattr(widget, 'set_font_family'):
                    widget.set_font_family(font_family)
                if hasattr(widget, 'set_font_size'):
                    widget.set_font_size(int(font_size))
                if hasattr(widget, 'set_text_color'):
                    widget.set_text_color(parse_color_to_qcolor(text_color))
                if hasattr(widget, 'set_show_background'):
                    widget.set_show_background(show_background)
                if hasattr(widget, 'set_show_separators'):
                    widget.set_show_separators(show_separators)
                if hasattr(widget, 'set_background_color'):
                    widget.set_background_color(parse_color_to_qcolor(bg_color_value))
                if hasattr(widget, 'set_background_opacity'):
                    widget.set_background_opacity(float(bg_opacity_value))
                if hasattr(widget, 'set_background_border'):
                    border_qcolor = parse_color_to_qcolor(border_color_value, opacity_override=border_opacity_value)
                    if border_qcolor:
                        widget.set_background_border(2, border_qcolor)
                if hasattr(widget, 'set_margin'):
                    widget.set_margin(int(margin))
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to reapply reddit config for %s", key, exc_info=True)
    
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
            
            # Determine if we should place the visualizer BELOW or ABOVE the media widget.
            # If media is at the TOP of the screen, visualizer should be BELOW.
            # If media is at the BOTTOM (or center/middle), visualizer generally goes ABOVE.
            
            # Robustly check position name
            position_name = ""
            if hasattr(media_widget, "_position"):
                pos = media_widget._position
                if hasattr(pos, "name"):
                    position_name = pos.name.upper()
                else:
                    position_name = str(pos).upper()
            
            # List of anchors where visualizer should be BELOW the media card
            top_anchors = ("TOP_LEFT", "TOP_CENTER", "TOP_RIGHT")
            
            # Default to placing ABOVE, unless we are definitely at a TOP anchor
            place_below = any(anchor in position_name for anchor in top_anchors)
            
            if place_below:
                 # usage of top() + height() avoids QRect.bottom() off-by-one (bottom is y+h-1)
                 y = media_geom.top() + media_geom.height() + gap
            else:
                 y = media_geom.top() - gap - height
            
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
        self._detach_settings_manager()
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
    # Widget Factory Methods (Phase 2 - Jan 2026)
    # Legacy create_*_widget methods removed - now using WidgetFactoryRegistry
    # See rendering/widget_factories.py for ClockWidgetFactory, WeatherWidgetFactory,
    # MediaWidgetFactory, RedditWidgetFactory implementations
    # =========================================================================

    # NOTE: create_clock_widget, create_weather_widget, create_media_widget,
    # create_reddit_widget have been removed. setup_all_widgets() now uses
    # the WidgetFactoryRegistry for these widgets. Spotify widgets still use
    # direct methods below due to complex media widget anchoring logic.

    def setup_all_widgets(
        self,
        settings_manager: SettingsManager,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
    ) -> dict:
        """
        Set up all overlay widgets based on settings using the factory registry.
        
        This is the main entry point for widget creation, replacing the
        monolithic _setup_widgets method in DisplayWidget.
        
        Phase 2 Refactor (Jan 2026): Now delegates to WidgetFactoryRegistry
        for widget creation instead of inline create_*_widget methods.
        
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

        self._attach_settings_manager(settings_manager)
        
        # Initialize factory registry if not already done
        if self._factory_registry is None:
            self.set_factory_registry(settings_manager, thread_manager)

        logger.debug("Setting up overlay widgets for screen %d via factory registry", screen_index)

        widgets_config = settings_manager.get('widgets', {})
        if not isinstance(widgets_config, dict):
            widgets_config = {}

        base_clock_settings = widgets_config.get('clock', {}) if isinstance(widgets_config, dict) else {}
        base_reddit_settings = widgets_config.get('reddit', {}) if isinstance(widgets_config, dict) else {}
        shadows_config = widgets_config.get('shadows', {}) if isinstance(widgets_config, dict) else {}

        # Reset fade coordination
        self.reset_fade_coordination()

        created = {}

        # Helper to check monitor selection
        def _show_on_this_monitor(monitor_sel) -> bool:
            try:
                return (monitor_sel == 'ALL') or (int(monitor_sel) == (screen_index + 1))
            except Exception:
                return True

        # Get factory instances
        clock_factory = self._factory_registry.get_factory("clock")
        weather_factory = self._factory_registry.get_factory("weather")
        media_factory = self._factory_registry.get_factory("media")
        reddit_factory = self._factory_registry.get_factory("reddit")

        # Create clock widgets via factory
        for settings_key, attr_name, default_pos, default_size in [
            ('clock', 'clock_widget', 'Top Right', 48),
            ('clock2', 'clock2_widget', 'Bottom Right', 32),
            ('clock3', 'clock3_widget', 'Bottom Left', 32),
        ]:
            clock_settings = widgets_config.get(settings_key, {})
            monitor_sel = clock_settings.get('monitor', 'ALL')
            if not _show_on_this_monitor(monitor_sel):
                continue
            
            # Add expected overlay for fade coordination
            if SettingsManager.to_bool(clock_settings.get('enabled', False), False):
                self.add_expected_overlay(settings_key)
            
            # Inject defaults for factory
            clock_settings['_default_position'] = default_pos
            clock_settings['_default_font_size'] = default_size
            
            if clock_factory:
                widget = clock_factory.create(
                    self._parent, clock_settings,
                    settings_key=settings_key,
                    base_clock_settings=base_clock_settings if settings_key != 'clock' else None,
                    shadows_config=shadows_config,
                    overlay_name=settings_key,
                )
                if widget:
                    self.register_widget(settings_key, widget)
                    widget.raise_()
                    created[attr_name] = widget

        # Create weather widget via factory
        weather_settings = widgets_config.get('weather', {})
        monitor_sel = weather_settings.get('monitor', 'ALL')
        if _show_on_this_monitor(monitor_sel):
            if SettingsManager.to_bool(weather_settings.get('enabled', False), False):
                self.add_expected_overlay("weather")
            
            if weather_factory:
                widget = weather_factory.create(
                    self._parent, weather_settings,
                    shadows_config=shadows_config,
                )
                if widget:
                    self.register_widget("weather", widget)
                    widget.raise_()
                    created['weather_widget'] = widget

        # Create media widget via factory
        media_settings = widgets_config.get('media', {})
        monitor_sel = media_settings.get('monitor', 'ALL')
        if _show_on_this_monitor(monitor_sel):
            if SettingsManager.to_bool(media_settings.get('enabled', False), False):
                self.add_expected_overlay("media")
            
            if media_factory:
                media_widget = media_factory.create(
                    self._parent, media_settings,
                    shadows_config=shadows_config,
                )
                if media_widget:
                    self.register_widget("media", media_widget)
                    media_widget.raise_()
                    created['media_widget'] = media_widget

        # Create reddit widgets via factory (reddit2 inherits styling from reddit1)
        for settings_key, attr_name in [('reddit', 'reddit_widget'), ('reddit2', 'reddit2_widget')]:
            reddit_settings = widgets_config.get(settings_key, {})
            monitor_sel = reddit_settings.get('monitor', 'ALL')
            if not _show_on_this_monitor(monitor_sel):
                continue
            
            if SettingsManager.to_bool(reddit_settings.get('enabled', False), False):
                self.add_expected_overlay(settings_key)
            
            if reddit_factory:
                widget = reddit_factory.create(
                    self._parent, reddit_settings,
                    settings_key=settings_key,
                    base_reddit_settings=base_reddit_settings if settings_key == 'reddit2' else None,
                    shadows_config=shadows_config,
                )
                if widget:
                    self.register_widget(settings_key, widget)
                    widget.raise_()
                    created[attr_name] = widget

        # Gmail widget archived - see archive/gmail_feature/

        # Create Spotify widgets (require media widget) - still use direct methods
        # as they have complex media widget anchoring logic
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

        logger.info("Widget setup complete: %d widgets created and started via factories", len(created))
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
        media_model = MediaWidgetSettings.from_mapping(media_settings if isinstance(media_settings, Mapping) else {})
        spotify_volume_enabled = SettingsManager.to_bool(media_model.spotify_volume_enabled, True)
        
        media_monitor_sel = media_model.monitor
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
            bg_color_data = media_model.bg_color
            bg_qcolor = parse_color_to_qcolor(bg_color_data)
            border_color_data = media_model.border_color
            border_opacity = media_model.border_opacity
            try:
                bo = float(border_opacity)
            except Exception:
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
            
            try:
                from PySide6.QtGui import QColor as _QColor
                fill_color_data = media_model.spotify_volume_fill_color or [255, 255, 255, 230]
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
        model = SpotifyVisualizerSettings.from_mapping(spotify_vis_settings if isinstance(spotify_vis_settings, Mapping) else {})
        spotify_vis_enabled = SettingsManager.to_bool(model.enabled, False)
        
        media_monitor_sel = media_settings.get('monitor', 'ALL')
        try:
            show_on_this = (media_monitor_sel == 'ALL') or (int(media_monitor_sel) == (screen_index + 1))
        except Exception:
            show_on_this = False
        
        if not (spotify_vis_enabled and show_on_this):
            return None
        
        self.add_expected_overlay("spotify_visualizer")

        try:
            bar_count = int(model.bar_count)
            vis = SpotifyVisualizerWidget(self._parent, bar_count=bar_count)

            self._log_spotify_vis_config("create", spotify_vis_settings)
            
            # Preferred audio block size (0=auto)
            try:
                block_size = int(model.audio_block_size or 0)
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
                ghost_enabled = SettingsManager.to_bool(model.ghosting_enabled, True)
                ghost_alpha = float(model.ghost_alpha)
                ghost_decay = max(0.0, float(model.ghost_decay))
                if hasattr(vis, 'set_ghost_config'):
                    vis.set_ghost_config(ghost_enabled, ghost_alpha, ghost_decay)
            except Exception:
                pass
            
            # Sensitivity configuration
            try:
                recommended = SettingsManager.to_bool(model.adaptive_sensitivity, True)
                sens = max(0.25, min(2.5, float(model.sensitivity)))
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
                dynamic_floor = SettingsManager.to_bool(model.dynamic_floor, True)
                manual_floor = float(model.manual_floor)
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
