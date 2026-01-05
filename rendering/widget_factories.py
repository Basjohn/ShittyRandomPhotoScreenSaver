"""
Widget Factory Classes for Overlay Widgets.

Extracts widget creation logic from WidgetManager into dedicated factory classes.
Each factory is responsible for creating and configuring a specific widget type.

This decomposition improves:
- Single Responsibility Principle (each factory handles one widget type)
- Testability (factories can be tested independently)
- Maintainability (widget-specific logic is isolated)
- Extensibility (new widgets just need a new factory)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from rendering.widget_setup import parse_color_to_qcolor

if TYPE_CHECKING:
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


class WidgetFactory(ABC):
    """Abstract base class for widget factories."""
    
    def __init__(self, settings: SettingsManager, thread_manager: Optional["ThreadManager"] = None):
        """
        Initialize the factory.
        
        Args:
            settings: SettingsManager for widget configuration
            thread_manager: Optional ThreadManager for background operations
        """
        self._settings = settings
        self._thread_manager = thread_manager
    
    @abstractmethod
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """
        Create and configure a widget.
        
        Args:
            parent: Parent widget (usually DisplayWidget)
            config: Widget-specific configuration
            
        Returns:
            Configured widget or None if creation failed
        """
        pass
    
    @abstractmethod
    def get_widget_name(self) -> str:
        """Get the canonical name for this widget type."""
        pass
    
    def _get_shadow_config(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract shadow configuration from widget config."""
        shadow_cfg = config.get("shadow", {})
        if not shadow_cfg.get("enabled", True):
            return None
        return {
            "blur_radius": shadow_cfg.get("blur_radius", 15),
            "offset_x": shadow_cfg.get("offset_x", 3),
            "offset_y": shadow_cfg.get("offset_y", 3),
            "color": shadow_cfg.get("color", "#000000"),
            "opacity": shadow_cfg.get("opacity", 0.6),
        }


class ClockWidgetFactory(WidgetFactory):
    """Factory for creating ClockWidget instances.
    
    Handles full settings inheritance for clock2/clock3 from base clock settings.
    """
    
    def get_widget_name(self) -> str:
        return "clock"
    
    def create(
        self,
        parent: QWidget,
        config: Dict[str, Any],
        *,
        settings_key: str = "clock",
        base_clock_settings: Optional[Dict[str, Any]] = None,
        shadows_config: Optional[Dict[str, Any]] = None,
        overlay_name: Optional[str] = None,
    ) -> Optional[QWidget]:
        """Create and configure a ClockWidget with full settings inheritance.
        
        Args:
            parent: Parent widget
            config: Widget-specific configuration from settings
            settings_key: Settings key ('clock', 'clock2', 'clock3')
            base_clock_settings: Base clock settings for inheritance (for clock2/clock3)
            shadows_config: Shadow configuration dict
            overlay_name: Overlay name for fade coordination
        """
        from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
        from core.settings.models import WidgetPosition, coerce_widget_position
        
        if not SettingsManager.to_bool(config.get("enabled", False), False):
            return None
        
        try:
            # Style inheritance helper for secondary clocks
            def _resolve_style(key: str, default):
                if settings_key == 'clock':
                    return config.get(key, default)
                if isinstance(base_clock_settings, dict) and key in base_clock_settings:
                    return base_clock_settings.get(key, default)
                return config.get(key, default)
            
            # Position mapping
            position_map = {
                WidgetPosition.TOP_LEFT: ClockPosition.TOP_LEFT,
                WidgetPosition.TOP_CENTER: ClockPosition.TOP_CENTER,
                WidgetPosition.TOP_RIGHT: ClockPosition.TOP_RIGHT,
                WidgetPosition.MIDDLE_LEFT: ClockPosition.MIDDLE_LEFT,
                WidgetPosition.CENTER: ClockPosition.CENTER,
                WidgetPosition.MIDDLE_RIGHT: ClockPosition.MIDDLE_RIGHT,
                WidgetPosition.BOTTOM_LEFT: ClockPosition.BOTTOM_LEFT,
                WidgetPosition.BOTTOM_CENTER: ClockPosition.BOTTOM_CENTER,
                WidgetPosition.BOTTOM_RIGHT: ClockPosition.BOTTOM_RIGHT,
            }
            
            default_pos = config.get("_default_position", "Top Right")
            resolved_widget_pos = coerce_widget_position(
                _resolve_style('position', default_pos),
                coerce_widget_position(default_pos, WidgetPosition.TOP_RIGHT),
            )
            position = position_map.get(resolved_widget_pos, ClockPosition.TOP_RIGHT)
            
            # Time format
            raw_format = _resolve_style('format', '12h')
            time_format = TimeFormat.TWELVE_HOUR if raw_format == '12h' else TimeFormat.TWENTY_FOUR_HOUR
            
            show_seconds = SettingsManager.to_bool(_resolve_style('show_seconds', False), False)
            timezone_str = config.get('timezone', 'local')
            show_timezone = SettingsManager.to_bool(_resolve_style('show_timezone', False), False)
            
            # Create widget
            widget = ClockWidget(
                parent=parent,
                time_format=time_format,
                position=position,
                show_seconds=show_seconds,
                timezone_str=timezone_str,
                show_timezone=show_timezone,
            )
            
            # Configure styling with inheritance
            font_family = _resolve_style('font_family', 'Segoe UI')
            default_font_size = config.get("_default_font_size", 48)
            font_size = _resolve_style('font_size', default_font_size)
            margin = _resolve_style('margin', 20)
            color = _resolve_style('color', [255, 255, 255, 230])
            bg_color = _resolve_style('bg_color', [64, 64, 64, 255])
            border_color = _resolve_style('border_color', [128, 128, 128, 255])
            border_opacity = _resolve_style('border_opacity', 0.8)
            show_background = SettingsManager.to_bool(_resolve_style('show_background', False), False)
            bg_opacity = _resolve_style('bg_opacity', 0.9)
            
            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(font_family)
            widget.set_font_size(font_size)
            widget.set_margin(margin)
            
            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                widget.set_text_color(qcolor)
            
            bg_qcolor = parse_color_to_qcolor(bg_color)
            if bg_qcolor and hasattr(widget, "set_background_color"):
                widget.set_background_color(bg_qcolor)
            
            try:
                bo = float(border_opacity)
            except Exception as e:
                logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color, opacity_override=bo)
            if border_qcolor and hasattr(widget, "set_background_border"):
                widget.set_background_border(2, border_qcolor)
            
            widget.set_show_background(show_background)
            widget.set_background_opacity(bg_opacity)
            
            # Display mode
            display_mode = _resolve_style('display_mode', 'digital')
            if hasattr(widget, 'set_display_mode'):
                widget.set_display_mode(display_mode)
            
            # Analog options
            show_numerals = SettingsManager.to_bool(_resolve_style('show_numerals', True), True)
            if hasattr(widget, 'set_show_numerals'):
                widget.set_show_numerals(show_numerals)
            
            analog_shadow = SettingsManager.to_bool(_resolve_style('analog_face_shadow', True), True)
            if hasattr(widget, 'set_analog_face_shadow'):
                widget.set_analog_face_shadow(analog_shadow)
            
            intense_shadow = SettingsManager.to_bool(_resolve_style('analog_shadow_intense', False), False)
            if hasattr(widget, 'set_analog_shadow_intense'):
                widget.set_analog_shadow_intense(intense_shadow)
            
            digital_intense = SettingsManager.to_bool(_resolve_style('digital_shadow_intense', False), False)
            if hasattr(widget, 'set_digital_shadow_intense'):
                widget.set_digital_shadow_intense(digital_intense)
            
            # Shadow config
            if shadows_config:
                from widgets.shadow_utils import apply_widget_shadow
                try:
                    if hasattr(widget, "set_shadow_config"):
                        widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
                except Exception as e:
                    logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
            
            # Overlay name for fade coordination
            if overlay_name and hasattr(widget, "set_overlay_name"):
                try:
                    widget.set_overlay_name(overlay_name)
                except Exception as e:
                    logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
            
            # Thread manager
            if self._thread_manager and hasattr(widget, 'set_thread_manager'):
                widget.set_thread_manager(self._thread_manager)
            
            logger.debug("[CLOCK_FACTORY] Created ClockWidget: %s", settings_key)
            return widget
            
        except Exception as e:
            logger.error(f"[CLOCK_FACTORY] Failed to create ClockWidget: {e}", exc_info=True)
            return None


class WeatherWidgetFactory(WidgetFactory):
    """Factory for creating WeatherWidget instances with full settings support."""
    
    def get_widget_name(self) -> str:
        return "weather"
    
    def create(
        self,
        parent: QWidget,
        config: Dict[str, Any],
        *,
        shadows_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[QWidget]:
        """Create and configure a WeatherWidget."""
        from widgets.weather_widget import WeatherWidget, WeatherPosition
        from core.settings.models import WidgetPosition, coerce_widget_position
        from widgets.shadow_utils import apply_widget_shadow
        
        if not SettingsManager.to_bool(config.get("enabled", False), False):
            return None
        
        try:
            # Position mapping
            position_map = {
                WidgetPosition.TOP_LEFT: WeatherPosition.TOP_LEFT,
                WidgetPosition.TOP_CENTER: WeatherPosition.TOP_CENTER,
                WidgetPosition.TOP_RIGHT: WeatherPosition.TOP_RIGHT,
                WidgetPosition.MIDDLE_LEFT: WeatherPosition.MIDDLE_LEFT,
                WidgetPosition.CENTER: WeatherPosition.CENTER,
                WidgetPosition.MIDDLE_RIGHT: WeatherPosition.MIDDLE_RIGHT,
                WidgetPosition.BOTTOM_LEFT: WeatherPosition.BOTTOM_LEFT,
                WidgetPosition.BOTTOM_CENTER: WeatherPosition.BOTTOM_CENTER,
                WidgetPosition.BOTTOM_RIGHT: WeatherPosition.BOTTOM_RIGHT,
            }
            
            widget_pos = coerce_widget_position(config.get('position', 'Top Left'), WidgetPosition.TOP_LEFT)
            position = position_map.get(widget_pos, WeatherPosition.TOP_LEFT)
            location = config.get('location', 'New York')
            
            widget = WeatherWidget(parent=parent, location=location, position=position)
            
            # Thread manager
            if self._thread_manager and hasattr(widget, "set_thread_manager"):
                widget.set_thread_manager(self._thread_manager)
            
            # Font
            font_family = config.get('font_family', 'Segoe UI')
            font_size = config.get('font_size', 24)
            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(font_family)
            widget.set_font_size(font_size)
            
            # Color
            color = config.get('color', [255, 255, 255, 230])
            qcolor = parse_color_to_qcolor(color)
            if qcolor:
                widget.set_text_color(qcolor)
            
            # Background
            show_background = SettingsManager.to_bool(config.get('show_background', True), True)
            widget.set_show_background(show_background)
            
            bg_color = config.get('bg_color', [35, 35, 35, 255])
            bg_qcolor = parse_color_to_qcolor(bg_color)
            if bg_qcolor:
                widget.set_background_color(bg_qcolor)
            
            bg_opacity = config.get('bg_opacity', 0.7)
            widget.set_background_opacity(bg_opacity)
            
            # Border
            border_color = config.get('border_color', [255, 255, 255, 255])
            border_opacity = config.get('border_opacity', 1.0)
            try:
                bo = float(border_opacity)
            except Exception as e:
                logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
                bo = 1.0
            border_qcolor = parse_color_to_qcolor(border_color, opacity_override=bo)
            if border_qcolor:
                widget.set_background_border(2, border_qcolor)
            
            # Forecast
            show_forecast = SettingsManager.to_bool(config.get('show_forecast', False), False)
            widget.set_show_forecast(show_forecast)
            
            # Margin
            margin = config.get('margin', 20)
            try:
                widget.set_margin(int(margin))
            except Exception as e:
                logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
            
            # Intense shadow
            intense_shadow = SettingsManager.to_bool(config.get('intense_shadow', False), False)
            if hasattr(widget, 'set_intense_shadow'):
                widget.set_intense_shadow(intense_shadow)
            
            # Shadow config
            if shadows_config:
                try:
                    if hasattr(widget, "set_shadow_config"):
                        widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
                except Exception as e:
                    logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
            
            logger.debug("[WEATHER_FACTORY] Created WeatherWidget: %s", location)
            return widget
            
        except Exception as e:
            logger.error(f"[WEATHER_FACTORY] Failed to create WeatherWidget: {e}", exc_info=True)
            return None


class MediaWidgetFactory(WidgetFactory):
    """Factory for creating MediaWidget instances with full settings support."""
    
    def get_widget_name(self) -> str:
        return "media"
    
    def create(
        self,
        parent: QWidget,
        config: Dict[str, Any],
        *,
        shadows_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[QWidget]:
        """Create and configure a MediaWidget with full settings."""
        from widgets.media_widget import MediaWidget, MediaPosition
        from core.settings.models import MediaWidgetSettings, WidgetPosition, coerce_widget_position
        from widgets.shadow_utils import apply_widget_shadow
        
        model = MediaWidgetSettings.from_mapping(config if isinstance(config, dict) else {})
        if not SettingsManager.to_bool(model.enabled, False):
            return None
        
        try:
            # Position mapping
            position_map = {
                WidgetPosition.TOP_LEFT: MediaPosition.TOP_LEFT,
                WidgetPosition.TOP_CENTER: MediaPosition.TOP_CENTER,
                WidgetPosition.TOP_RIGHT: MediaPosition.TOP_RIGHT,
                WidgetPosition.MIDDLE_LEFT: MediaPosition.MIDDLE_LEFT,
                WidgetPosition.CENTER: MediaPosition.CENTER,
                WidgetPosition.MIDDLE_RIGHT: MediaPosition.MIDDLE_RIGHT,
                WidgetPosition.BOTTOM_LEFT: MediaPosition.BOTTOM_LEFT,
                WidgetPosition.BOTTOM_CENTER: MediaPosition.BOTTOM_CENTER,
                WidgetPosition.BOTTOM_RIGHT: MediaPosition.BOTTOM_RIGHT,
            }
            
            widget_pos = coerce_widget_position(model.position, WidgetPosition.BOTTOM_LEFT)
            position = position_map.get(widget_pos, MediaPosition.BOTTOM_LEFT)
            
            widget = MediaWidget(parent=parent, position=position)
            
            # Thread manager
            if self._thread_manager and hasattr(widget, "set_thread_manager"):
                widget.set_thread_manager(self._thread_manager)
            
            # Font
            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(model.font_family)
            widget.set_font_size(model.font_size)
            
            # Margin
            widget.set_margin(model.margin)
            
            # Color
            qcolor = parse_color_to_qcolor(model.color)
            if qcolor:
                widget.set_text_color(qcolor)
            
            # Background
            show_background = SettingsManager.to_bool(model.show_background, True)
            widget.set_show_background(show_background)
            
            bg_qcolor = parse_color_to_qcolor(model.bg_color)
            if bg_qcolor:
                widget.set_background_color(bg_qcolor)
            widget.set_background_opacity(model.background_opacity)
            
            # Border
            try:
                bo = float(model.border_opacity)
            except Exception as e:
                logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(model.border_color, opacity_override=bo)
            if border_qcolor:
                widget.set_background_border(2, border_qcolor)
            
            # Controls and header
            show_controls = SettingsManager.to_bool(model.show_controls, True)
            if hasattr(widget, 'set_show_controls'):
                widget.set_show_controls(show_controls)
            
            show_header = SettingsManager.to_bool(model.show_header_frame, True)
            if hasattr(widget, 'set_show_header_frame'):
                widget.set_show_header_frame(show_header)
            
            # Shadow config
            if shadows_config:
                try:
                    if hasattr(widget, "set_shadow_config"):
                        widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
                except Exception as e:
                    logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
            
            logger.debug("[MEDIA_FACTORY] Created MediaWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[MEDIA_FACTORY] Failed to create MediaWidget: {e}", exc_info=True)
            return None


class RedditWidgetFactory(WidgetFactory):
    """Factory for creating RedditWidget instances with full settings support."""
    
    def get_widget_name(self) -> str:
        return "reddit"
    
    def create(
        self,
        parent: QWidget,
        config: Dict[str, Any],
        *,
        settings_key: str = "reddit",
        base_reddit_settings: Optional[Dict[str, Any]] = None,
        shadows_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[QWidget]:
        """Create and configure a RedditWidget with full settings inheritance."""
        from widgets.reddit_widget import RedditWidget, RedditPosition
        from core.settings.models import RedditWidgetSettings, WidgetPosition, coerce_widget_position
        from widgets.shadow_utils import apply_widget_shadow
        
        model = RedditWidgetSettings.from_mapping(config if isinstance(config, dict) else {}, prefix=f"widgets.{settings_key}")
        if not SettingsManager.to_bool(model.enabled, False):
            return None
        
        try:
            # Style inheritance helper for reddit2
            style_fallback = base_reddit_settings if (settings_key == 'reddit2' and isinstance(base_reddit_settings, dict)) else None
            
            def inherit_style(field: str, default):
                if field in config:
                    return config.get(field)
                if isinstance(style_fallback, dict) and field in style_fallback:
                    return style_fallback.get(field)
                return default
            
            # Position mapping
            position_map = {
                WidgetPosition.TOP_LEFT: RedditPosition.TOP_LEFT,
                WidgetPosition.TOP_CENTER: RedditPosition.TOP_CENTER,
                WidgetPosition.TOP_RIGHT: RedditPosition.TOP_RIGHT,
                WidgetPosition.MIDDLE_LEFT: RedditPosition.MIDDLE_LEFT,
                WidgetPosition.CENTER: RedditPosition.CENTER,
                WidgetPosition.MIDDLE_RIGHT: RedditPosition.MIDDLE_RIGHT,
                WidgetPosition.BOTTOM_LEFT: RedditPosition.BOTTOM_LEFT,
                WidgetPosition.BOTTOM_CENTER: RedditPosition.BOTTOM_CENTER,
                WidgetPosition.BOTTOM_RIGHT: RedditPosition.BOTTOM_RIGHT,
            }
            
            widget_pos = coerce_widget_position(model.position, WidgetPosition.TOP_RIGHT)
            position = position_map.get(widget_pos, RedditPosition.TOP_RIGHT)
            
            widget = RedditWidget(parent=parent, position=position)
            
            # Thread manager
            if self._thread_manager and hasattr(widget, "set_thread_manager"):
                widget.set_thread_manager(self._thread_manager)
            
            # Font with inheritance
            font_family = inherit_style('font_family', model.font_family)
            font_size = inherit_style('font_size', model.font_size)
            if hasattr(widget, 'set_font_family'):
                widget.set_font_family(font_family)
            if hasattr(widget, 'set_font_size'):
                widget.set_font_size(int(font_size))
            
            # Margin
            margin = inherit_style('margin', model.margin)
            if hasattr(widget, 'set_margin'):
                widget.set_margin(int(margin))
            
            # Color
            text_color = inherit_style('color', [255, 255, 255, 230])
            qcolor = parse_color_to_qcolor(text_color)
            if qcolor and hasattr(widget, 'set_text_color'):
                widget.set_text_color(qcolor)
            
            # Background
            show_background = SettingsManager.to_bool(inherit_style('show_background', model.show_background), True)
            if hasattr(widget, 'set_show_background'):
                widget.set_show_background(show_background)
            
            # Separators
            show_separators = SettingsManager.to_bool(inherit_style('show_separators', model.show_separators), True)
            if hasattr(widget, 'set_show_separators'):
                widget.set_show_separators(show_separators)
            
            # Background color
            bg_color = inherit_style('bg_color', inherit_style('background_color', [35, 35, 35, 255]))
            bg_qcolor = parse_color_to_qcolor(bg_color)
            if bg_qcolor and hasattr(widget, 'set_background_color'):
                widget.set_background_color(bg_qcolor)
            
            # Background opacity
            bg_opacity = inherit_style('bg_opacity', model.background_opacity)
            if hasattr(widget, 'set_background_opacity'):
                widget.set_background_opacity(float(bg_opacity))
            
            # Border
            border_color = inherit_style('border_color', [255, 255, 255, 255])
            border_opacity = inherit_style('border_opacity', model.border_opacity)
            try:
                bo = float(border_opacity)
            except Exception as e:
                logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
                bo = 0.8
            border_qcolor = parse_color_to_qcolor(border_color, opacity_override=bo)
            if border_qcolor and hasattr(widget, 'set_background_border'):
                widget.set_background_border(2, border_qcolor)
            
            # Reddit-specific settings
            subreddit = model.subreddit or 'pics'
            if hasattr(widget, 'set_subreddit'):
                widget.set_subreddit(subreddit)
            
            item_limit = model.item_limit
            if hasattr(widget, 'set_item_limit'):
                widget.set_item_limit(int(item_limit))
            
            # Intense shadow
            intense_shadow = SettingsManager.to_bool(model.intense_shadow, False)
            if hasattr(widget, 'set_intense_shadow'):
                widget.set_intense_shadow(intense_shadow)
            
            # Overlay name for fade coordination
            if hasattr(widget, 'set_overlay_name'):
                widget.set_overlay_name(settings_key)
            
            # Shadow config
            if shadows_config:
                try:
                    if hasattr(widget, "set_shadow_config"):
                        widget.set_shadow_config(shadows_config)
                    else:
                        apply_widget_shadow(widget, shadows_config, has_background_frame=show_background)
                except Exception as e:
                    logger.debug("[WIDGET_FACTORY] Exception suppressed: %s", e)
            
            logger.debug("[REDDIT_FACTORY] Created RedditWidget: %s", settings_key)
            return widget
            
        except Exception as e:
            logger.error(f"[REDDIT_FACTORY] Failed to create RedditWidget: {e}", exc_info=True)
            return None


class SpotifyVisualizerFactory(WidgetFactory):
    """Factory for creating SpotifyVisualizerWidget instances."""
    
    def __init__(self, settings: SettingsManager, thread_manager: Optional["ThreadManager"] = None):
        super().__init__(settings, thread_manager)
        self._process_supervisor = None
    
    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor for FFTWorker integration."""
        self._process_supervisor = supervisor
    
    def get_widget_name(self) -> str:
        return "spotify_visualizer"
    
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """Create and configure a SpotifyVisualizerWidget."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        
        if not config.get("enabled", False):
            return None
        
        try:
            # Create widget
            widget = SpotifyVisualizerWidget(parent=parent)
            
            # Configure visualizer settings
            widget.set_bar_count(config.get("bar_count", 10))
            widget.set_segments(config.get("segments", 5))
            
            # Configure colors
            fill_color = config.get("fill_color", "#1DB954")
            border_color = config.get("border_color", "#FFFFFF")
            fill_qcolor = parse_color_to_qcolor(fill_color)
            border_qcolor = parse_color_to_qcolor(border_color)
            if fill_qcolor and border_qcolor:
                widget.set_colors(fill_qcolor, border_qcolor)
            
            # Set thread manager
            if self._thread_manager:
                widget.set_thread_manager(self._thread_manager)
            
            # Set process supervisor for FFTWorker integration
            if self._process_supervisor:
                widget.set_process_supervisor(self._process_supervisor)
            
            logger.debug("[SPOTIFY_VIS_FACTORY] Created SpotifyVisualizerWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[SPOTIFY_VIS_FACTORY] Failed to create SpotifyVisualizerWidget: {e}", exc_info=True)
            return None


class SpotifyVolumeFactory(WidgetFactory):
    """Factory for creating SpotifyVolumeWidget instances."""
    
    def get_widget_name(self) -> str:
        return "spotify_volume"
    
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """Create and configure a SpotifyVolumeWidget."""
        from widgets.spotify_volume_widget import SpotifyVolumeWidget
        
        # Volume widget is typically created alongside media widget
        # and doesn't have its own enabled flag
        
        try:
            # Create widget
            widget = SpotifyVolumeWidget(parent=parent)
            
            # Configure colors
            fill_color = config.get("fill_color", "#1DB954")
            border_color = config.get("border_color", "#FFFFFF")
            bg_color = config.get("bg_color", "#333333")
            fill_qcolor = parse_color_to_qcolor(fill_color)
            border_qcolor = parse_color_to_qcolor(border_color)
            bg_qcolor = parse_color_to_qcolor(bg_color)
            if fill_qcolor and border_qcolor and bg_qcolor:
                widget.set_colors(fill_qcolor, border_qcolor, bg_qcolor)
            
            logger.debug("[SPOTIFY_VOL_FACTORY] Created SpotifyVolumeWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[SPOTIFY_VOL_FACTORY] Failed to create SpotifyVolumeWidget: {e}", exc_info=True)
            return None


# ---------------------------------------------------------------------------
# Factory Registry
# ---------------------------------------------------------------------------

class WidgetFactoryRegistry:
    """
    Registry for widget factories.
    
    Provides a central point for registering and retrieving widget factories.
    """
    
    def __init__(self, settings: SettingsManager, thread_manager: Optional["ThreadManager"] = None):
        """
        Initialize the registry with default factories.
        
        Args:
            settings: SettingsManager for widget configuration
            thread_manager: Optional ThreadManager for background operations
        """
        self._settings = settings
        self._thread_manager = thread_manager
        self._factories: Dict[str, WidgetFactory] = {}
        
        # Register default factories
        self._register_default_factories()
    
    def _register_default_factories(self) -> None:
        """Register all default widget factories."""
        self.register(ClockWidgetFactory(self._settings, self._thread_manager))
        self.register(WeatherWidgetFactory(self._settings, self._thread_manager))
        self.register(MediaWidgetFactory(self._settings, self._thread_manager))
        self.register(RedditWidgetFactory(self._settings, self._thread_manager))
        self.register(SpotifyVisualizerFactory(self._settings, self._thread_manager))
        self.register(SpotifyVolumeFactory(self._settings, self._thread_manager))
    
    def register(self, factory: WidgetFactory) -> None:
        """
        Register a widget factory.
        
        Args:
            factory: Factory to register
        """
        name = factory.get_widget_name()
        self._factories[name] = factory
        logger.debug(f"[FACTORY_REGISTRY] Registered factory: {name}")
    
    def get_factory(self, name: str) -> Optional[WidgetFactory]:
        """
        Get a factory by widget name.
        
        Args:
            name: Widget name
            
        Returns:
            Factory or None if not found
        """
        return self._factories.get(name)
    
    def create_widget(self, name: str, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """
        Create a widget using the appropriate factory.
        
        Args:
            name: Widget name
            parent: Parent widget
            config: Widget configuration
            
        Returns:
            Created widget or None
        """
        factory = self.get_factory(name)
        if factory is None:
            logger.warning(f"[FACTORY_REGISTRY] No factory for widget: {name}")
            return None
        return factory.create(parent, config)
    
    def get_all_factory_names(self) -> list:
        """Get names of all registered factories."""
        return list(self._factories.keys())
    
    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor on factories that support it.
        
        Currently only SpotifyVisualizerFactory uses this for FFTWorker integration.
        """
        spotify_factory = self._factories.get("spotify_visualizer")
        if spotify_factory and hasattr(spotify_factory, "set_process_supervisor"):
            spotify_factory.set_process_supervisor(supervisor)
            logger.debug("[FACTORY_REGISTRY] ProcessSupervisor set on spotify_visualizer factory")
