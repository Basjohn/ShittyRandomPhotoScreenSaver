"""
Widget Manager - Extracted from DisplayWidget for better separation of concerns.

Manages overlay widget lifecycle, positioning, visibility, and Z-order.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING, Mapping

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
from rendering.widget_setup import parse_color_to_qcolor, compute_expected_overlays
from rendering.fade_coordinator import FadeCoordinator
from widgets.shadow_utils import apply_widget_shadow as _apply_widget_shadow
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

# Re-export for tests that monkeypatch rendering.widget_manager.apply_widget_shadow.
apply_widget_shadow = _apply_widget_shadow

logger = get_logger(__name__)


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
        
        # Fade callbacks
        self._fade_callbacks: Dict[str, Callable] = {}
        
        # Fade coordination - centralized via FadeCoordinator
        self._fade_coordinator: FadeCoordinator = FadeCoordinator(
            screen_index=getattr(parent, "screen_index", 0)
        )
        
        # Wait for compositor first frame before starting widget fades
        self._compositor_ready: bool = False
        self._connect_compositor_ready_signal()
        
        # Widget positioning (Dec 2025)
        self._positioner = WidgetPositioner()
        
        # Widget factory registry (Dec 2025) - for simplified widget creation
        self._factory_registry: Optional[WidgetFactoryRegistry] = None

        # Settings manager wiring for live updates (Spotify VIS etc.)
        self._settings_manager: Optional[SettingsManager] = None
        
        # Spotify visibility sync state
        self._pending_spotify_visibility_sync: bool = False
        
        logger.debug("[WIDGET_MANAGER] Initialized")

    def _bind_parent_attribute(self, attr_name: str, widget: Optional[QWidget]) -> None:
        """Expose newly created widgets on the parent DisplayWidget immediately."""
        parent = self._parent
        logger.debug("[WIDGET_MANAGER] Binding %s to parent=%s widget=%s", attr_name, parent, widget)
        if parent is None:
            logger.debug("[WIDGET_MANAGER] Cannot bind %s - parent is None", attr_name)
            return
        try:
            setattr(parent, attr_name, widget)
            logger.debug("[WIDGET_MANAGER] Successfully bound %s to parent", attr_name)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Failed to bind %s on parent: %s", attr_name, e)
    
    def _connect_compositor_ready_signal(self) -> None:
        """Connect to parent's image_displayed signal to know when compositor is ready."""
        if self._parent is None:
            self._compositor_ready = True  # No parent, assume ready
            return
        
        try:
            # Check if parent already has rendered first frame
            if getattr(self._parent, "_has_rendered_first_frame", False):
                self._compositor_ready = True
                return
            
            # Connect to image_displayed signal
            if hasattr(self._parent, "image_displayed"):
                self._parent.image_displayed.connect(self._on_compositor_ready)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Failed to connect compositor ready signal: %s", e)
            self._compositor_ready = True  # Assume ready on failure
    
    def _on_compositor_ready(self, image_path: str) -> None:
        """Called when compositor displays first image."""
        screen_idx = getattr(self._parent, "screen_index", "?")
        if self._compositor_ready:
            logger.debug("[FADE_SYNC] Compositor already ready on screen=%s, ignoring duplicate signal", screen_idx)
            return  # Already marked ready
        
        self._compositor_ready = True
        # Signal FadeCoordinator that compositor is ready
        self._fade_coordinator.signal_compositor_ready()
        
        logger.info("[FADE_SYNC] Compositor ready on screen=%s (first image: %s)", screen_idx, image_path)
        
        # Disconnect signal to avoid repeated calls
        try:
            if self._parent is not None and hasattr(self._parent, "image_displayed"):
                self._parent.image_displayed.disconnect(self._on_compositor_ready)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
    
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
    
    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor on the factory registry.
        
        This enables FFTWorker integration for the Spotify visualizer.
        """
        if self._factory_registry is not None:
            self._factory_registry.set_process_supervisor(supervisor)
            logger.debug("[WIDGET_MANAGER] ProcessSupervisor set on factory registry")
    
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
        if widget is not None:
            if hasattr(widget, "set_widget_manager"):
                try:
                    widget.set_widget_manager(self)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

            # Ensure widgets inherit the ThreadManager from the display if they expose a setter
            parent_tm = getattr(self._parent, "_thread_manager", None)
            if parent_tm is not None and hasattr(widget, "set_thread_manager"):
                try:
                    current_tm = getattr(widget, "_thread_manager", None)
                except Exception:
                    current_tm = None
                if current_tm is None:
                    try:
                        widget.set_thread_manager(parent_tm)
                    except Exception as e:
                        logger.debug("[WIDGET_MANAGER] Failed to inject ThreadManager into %s: %s", name, e)
        if self._resource_manager:
            try:
                self._resource_manager.register_qt(widget, description=f"Widget: {name}")
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        logger.debug(f"[WIDGET_MANAGER] Registered widget: {name}")

    def configure_expected_overlays(self, widgets_config: Dict[str, Any]) -> None:
        """Compute and store the overlays expected to participate in fade sync."""
        if widgets_config is None:
            widgets_config = {}
        try:
            expected = compute_expected_overlays(self._parent, widgets_config)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
                    if self._resource_manager:
                        try:
                            self._resource_manager.register_qt(
                                self._raise_timer,
                                description="WidgetManager raise rate-limit timer",
                            )
                        except Exception:
                            pass
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
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        finally:
            self._settings_manager = None

    def _handle_settings_changed(self, key: str, value: object) -> None:
        """React to settings changes for live widget updates."""
        try:
            setting_key = str(key) if key is not None else ""
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            setting_key = ""
        if not setting_key:
            return

        try:
            logger.debug("[WIDGET_MANAGER][SETTINGS] key=%s payload_type=%s", setting_key, type(value).__name__)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bg_opacity = 0.9

        border_color_data = settings_map.get("border_color", [128, 128, 128, 255])
        try:
            border_opacity = float(settings_map.get("border_opacity", 0.8))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            border_opacity = 0.8
        border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=border_opacity)

        show_background = SettingsManager.to_bool(settings_map.get("show_background", True), True)
        try:
            border_width = int(settings_map.get("border_width", 2) or 2)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

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
            full_width = media_geom.width()
            width = full_width
            x = media_geom.left()

            # Blob mode: apply card width factor and centre the narrower card
            vis_mode = getattr(vis_widget, '_vis_mode_str', 'spectrum')
            if vis_mode == 'blob':
                blob_w = getattr(vis_widget, '_blob_width', 1.0)
                blob_w = max(0.1, min(1.0, float(blob_w)))
                if blob_w < 1.0:
                    width = max(40, int(full_width * blob_w))
                    x = media_geom.left() + (full_width - width) // 2
            
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
            if is_perf_metrics_enabled():
                logger.info(
                    "[SPOTIFY_VIS] Positioned visualizer widget geom=(%d,%d,%d,%d)",
                    x,
                    y,
                    width,
                    height,
                )
            
            # Keep pixel-shift drift baseline aligned with the media card so the
            # GL overlay inherits the same reference frame as the QWidget card.
            pixel_shift_manager = getattr(self._parent, "_pixel_shift_manager", None)
            if pixel_shift_manager is not None and hasattr(pixel_shift_manager, "update_original_position"):
                try:
                    pixel_shift_manager.update_original_position(vis_widget)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

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
            if is_perf_metrics_enabled():
                logger.info(
                    "[SPOTIFY_VOL] Positioned volume widget geom=(%d,%d,%d,%d)",
                    x,
                    y,
                    width,
                    height,
                )
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            return 100
    
    def cleanup(self) -> None:
        """Clean up all managed widgets."""
        self._detach_settings_manager()
        if self._raise_timer is not None:
            try:
                self._raise_timer.stop()
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
        
        NOTE: This method is DORMANT as of Jan 2026. The legacy start() system
        is used instead (see setup_all_widgets). Lifecycle methods exist in all
        widgets but are not called. This is intentional - the lifecycle system
        is complete but kept dormant to reduce regression risk. Migration to
        lifecycle activation is planned for v1.3 after stabilization.
        
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
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
        """Delegates to rendering.widget_effects."""
        from rendering.widget_effects import invalidate_overlay_effects
        invalidate_overlay_effects(self, reason)

    def _invalidate_widget_effect(self, widget: QWidget, name: str, refresh: bool) -> None:
        """Delegates to rendering.widget_effects."""
        from rendering.widget_effects import _invalidate_widget_effect
        _invalidate_widget_effect(widget, name, refresh)

    def _recreate_effect(self, widget: QWidget, old_eff: Any) -> Any:
        """Delegates to rendering.widget_effects."""
        from rendering.widget_effects import _recreate_effect
        return _recreate_effect(widget, old_eff)

    def schedule_effect_invalidation(self, reason: str, delay_ms: int = 16) -> None:
        """Delegates to rendering.widget_effects."""
        from rendering.widget_effects import schedule_effect_invalidation
        schedule_effect_invalidation(self, reason, delay_ms)

    # =========================================================================
    # Overlay Fade Coordination
    # =========================================================================

    def reset_fade_coordination(self) -> None:
        """Reset fade coordination state for a new widget setup cycle."""
        if hasattr(self, '_fade_coordinator') and self._fade_coordinator is not None:
            self._fade_coordinator.reset()

    def set_expected_overlays(self, expected: Set[str]) -> None:
        """Set the overlays expected to participate in coordinated fade.
        
        Args:
            expected: Set of overlay names (e.g., {"weather", "media", "reddit"})
        """
        for name in expected:
            self._fade_coordinator.register_participant(name)

    def add_expected_overlay(self, name: str) -> None:
        """Add an overlay to the expected set."""
        self._fade_coordinator.register_participant(name)

    def request_overlay_fade_sync(self, overlay_name: str, starter: Callable[[], None]) -> None:
        """Register an overlay's initial fade so all widgets can fade together.

        Args:
            overlay_name: Name of the overlay requesting fade
            starter: Callback to start the fade animation
        """
        self._fade_coordinator.request_fade(overlay_name, starter)
        logger.debug("[FADE_COORD] %s fade request registered", overlay_name)

    def register_spotify_secondary_fade(self, starter: Callable[[], None]) -> None:
        """Register a Spotify second-wave fade to run after primary overlays."""
        # Check if fade coordination is active
        state = self._fade_coordinator.get_state()
        if not state['participants'] or state['started']:
            # Run with delay if coordination already started or no participants
            try:
                QTimer.singleShot(500, starter)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                try:
                    starter()
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            return
        # Add to secondary fade list for later execution
        self._spotify_secondary_fade_starters.append(starter)

    def _queue_spotify_visibility_sync(self, media_widget: Optional[MediaWidget]) -> None:
        if not media_widget or self._pending_spotify_visibility_sync:
            return

        notify = getattr(media_widget, "_notify_spotify_widgets_visibility", None)
        if not callable(notify):
            return

        self._pending_spotify_visibility_sync = True

        def _run() -> None:
            try:
                logger.debug(
                    "[SPOTIFY_DIAG] running media visibility sync (visible=%s)",
                    media_widget.isVisible(),
                )
                notify()
            except Exception as exc:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)
            finally:
                self._pending_spotify_visibility_sync = False

        try:
            QTimer.singleShot(0, _run)
        except Exception:
            _run()

    def _register_spotify_secondary_fade(self, widget: Optional[QWidget]) -> None:
        if widget is None:
            return
        parent = self._parent
        if parent is None:
            return
        register = getattr(parent, "register_spotify_secondary_fade", None)
        if not callable(register):
            return

        anchor = getattr(widget, "_anchor_media", None)
        max_deferrals = 20

        def _run_sync() -> None:
            try:
                sync = getattr(widget, "sync_visibility_with_anchor", None)
                if callable(sync):
                    sync()
            except Exception as exc:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)

        def _starter(attempt: int = 0) -> None:
            try:
                anchor_visible = True
                if anchor is not None and hasattr(anchor, "isVisible"):
                    anchor_visible = bool(anchor.isVisible())
            except Exception as exc:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)
                anchor_visible = True

            if not anchor_visible and attempt < max_deferrals:
                delay_ms = min(1000, 200 + attempt * 100)
                if is_perf_metrics_enabled():
                    logger.debug(
                        "[SPOTIFY_DIAG] deferring secondary fade for %s (anchor hidden, attempt=%s, delay=%sms)",
                        widget.objectName() or type(widget).__name__,
                        attempt + 1,
                        delay_ms,
                    )
                QTimer.singleShot(delay_ms, lambda: _starter(attempt + 1))
                return

            if not anchor_visible and is_perf_metrics_enabled():
                logger.debug(
                    "[SPOTIFY_DIAG] anchor still hidden after deferrals, forcing fade for %s",
                    widget.objectName() or type(widget).__name__,
                )

            if is_perf_metrics_enabled():
                logger.debug(
                    "[SPOTIFY_DIAG] secondary fade starter running for %s",
                    widget.objectName() or type(widget).__name__,
                )
            _run_sync()

        if is_perf_metrics_enabled():
            logger.debug(
                "[SPOTIFY_DIAG] registering secondary fade for %s (screen=%s)",
                widget.objectName() or type(widget).__name__,
                getattr(self._parent, "screen_index", "?"),
            )
        try:
            register(_starter)
        except Exception as exc:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)

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
        """Delegates to rendering.widget_setup_all."""
        from rendering.widget_setup_all import setup_all_widgets
        return setup_all_widgets(self, settings_manager, screen_index, thread_manager)

    def create_spotify_volume_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ) -> Optional[SpotifyVolumeWidget]:
        """Delegates to rendering.spotify_widget_creators."""
        from rendering.spotify_widget_creators import create_spotify_volume_widget
        return create_spotify_volume_widget(
            self, widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )

    def create_spotify_visualizer_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ) -> Optional[SpotifyVisualizerWidget]:
        """Delegates to rendering.spotify_widget_creators."""
        from rendering.spotify_widget_creators import create_spotify_visualizer_widget
        return create_spotify_visualizer_widget(
            self, widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )
