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
    """Factory for creating ClockWidget instances."""
    
    def get_widget_name(self) -> str:
        return "clock"
    
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """Create and configure a ClockWidget."""
        from widgets.clock_widget import ClockWidget, TimeFormat, ClockPosition
        
        if not config.get("enabled", False):
            return None
        
        try:
            # Parse configuration
            time_format = TimeFormat.TWELVE_HOUR
            if config.get("format", "12h") == "24h":
                time_format = TimeFormat.TWENTY_FOUR_HOUR
            
            position_str = config.get("position", "top_right")
            try:
                position = ClockPosition(position_str)
            except ValueError:
                position = ClockPosition.TOP_RIGHT
            
            show_seconds = config.get("show_seconds", True)
            timezone_str = config.get("timezone", "local")
            show_timezone = config.get("show_timezone", False)
            
            # Create widget
            widget = ClockWidget(
                parent=parent,
                time_format=time_format,
                position=position,
                show_seconds=show_seconds,
                timezone_str=timezone_str,
                show_timezone=show_timezone,
            )
            
            # Configure styling
            self._configure_styling(widget, config)
            
            # Configure shadow
            shadow_config = self._get_shadow_config(config)
            if shadow_config:
                widget.set_shadow_config(shadow_config)
            
            # Set thread manager
            if self._thread_manager:
                widget.set_thread_manager(self._thread_manager)
            
            logger.debug("[CLOCK_FACTORY] Created ClockWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[CLOCK_FACTORY] Failed to create ClockWidget: {e}", exc_info=True)
            return None
    
    def _configure_styling(self, widget: QWidget, config: Dict[str, Any]) -> None:
        """Apply styling configuration to widget."""
        from widgets.clock_widget import ClockWidget
        if not isinstance(widget, ClockWidget):
            return
        
        # Font
        font_family = config.get("font_family", "Segoe UI")
        font_size = config.get("font_size", 48)
        widget.set_font_family(font_family)
        widget.set_font_size(font_size)
        
        # Color
        color_str = config.get("color", "#FFFFFF")
        color = parse_color_to_qcolor(color_str)
        if color:
            widget.set_text_color(color)
        
        # Display mode
        display_mode = config.get("display_mode", "digital")
        widget.set_display_mode(display_mode)
        
        # Analog options
        if display_mode == "analog":
            widget.set_show_numerals(config.get("show_numerals", True))
            widget.set_analog_face_shadow(config.get("analog_face_shadow", True))
            widget.set_analog_shadow_intense(config.get("analog_shadow_intense", False))


class WeatherWidgetFactory(WidgetFactory):
    """Factory for creating WeatherWidget instances."""
    
    def get_widget_name(self) -> str:
        return "weather"
    
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """Create and configure a WeatherWidget."""
        from widgets.weather_widget import WeatherWidget, WeatherPosition
        
        if not config.get("enabled", False):
            return None
        
        try:
            # Parse position
            position_str = config.get("position", "bottom_left")
            try:
                position = WeatherPosition(position_str)
            except ValueError:
                position = WeatherPosition.BOTTOM_LEFT
            
            # Create widget - WeatherWidget takes location and position
            widget = WeatherWidget(
                parent=parent,
                location=config.get("location", "London"),
                position=position,
            )
            
            # Configure styling
            self._configure_styling(widget, config)
            
            # Configure shadow
            shadow_config = self._get_shadow_config(config)
            if shadow_config:
                widget.set_shadow_config(shadow_config)
            
            # Set thread manager
            if self._thread_manager:
                widget.set_thread_manager(self._thread_manager)
            
            logger.debug("[WEATHER_FACTORY] Created WeatherWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[WEATHER_FACTORY] Failed to create WeatherWidget: {e}", exc_info=True)
            return None
    
    def _configure_styling(self, widget: QWidget, config: Dict[str, Any]) -> None:
        """Apply styling configuration to widget."""
        from widgets.weather_widget import WeatherWidget
        if not isinstance(widget, WeatherWidget):
            return
        
        # Font
        font_family = config.get("font_family", "Segoe UI")
        font_size = config.get("font_size", 18)
        widget.set_font_family(font_family)
        widget.set_font_size(font_size)
        
        # Color
        color_str = config.get("color", "#FFFFFF")
        color = parse_color_to_qcolor(color_str)
        if color:
            widget.set_text_color(color)


class MediaWidgetFactory(WidgetFactory):
    """Factory for creating MediaWidget instances."""
    
    def get_widget_name(self) -> str:
        return "media"
    
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """Create and configure a MediaWidget."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        if not config.get("enabled", False):
            return None
        
        try:
            # Parse position
            position_str = config.get("position", "bottom_center")
            try:
                position = MediaPosition(position_str)
            except ValueError:
                position = MediaPosition.BOTTOM_CENTER
            
            # Create widget
            widget = MediaWidget(
                parent=parent,
                position=position,
            )
            
            # Configure styling
            self._configure_styling(widget, config)
            
            # Configure shadow
            shadow_config = self._get_shadow_config(config)
            if shadow_config:
                widget.set_shadow_config(shadow_config)
            
            # Set thread manager
            if self._thread_manager:
                widget.set_thread_manager(self._thread_manager)
            
            logger.debug("[MEDIA_FACTORY] Created MediaWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[MEDIA_FACTORY] Failed to create MediaWidget: {e}", exc_info=True)
            return None
    
    def _configure_styling(self, widget: QWidget, config: Dict[str, Any]) -> None:
        """Apply styling configuration to widget."""
        from widgets.media_widget import MediaWidget
        if not isinstance(widget, MediaWidget):
            return
        
        # Font
        font_family = config.get("font_family", "Segoe UI")
        font_size = config.get("font_size", 14)
        widget.set_font_family(font_family)
        widget.set_font_size(font_size)
        
        # Color
        color_str = config.get("color", "#FFFFFF")
        color = parse_color_to_qcolor(color_str)
        if color:
            widget.set_text_color(color)


class RedditWidgetFactory(WidgetFactory):
    """Factory for creating RedditWidget instances."""
    
    def get_widget_name(self) -> str:
        return "reddit"
    
    def create(self, parent: QWidget, config: Dict[str, Any]) -> Optional[QWidget]:
        """Create and configure a RedditWidget."""
        from widgets.reddit_widget import RedditWidget, RedditPosition
        
        if not config.get("enabled", False):
            return None
        
        try:
            # Parse position
            position_str = config.get("position", "bottom_left")
            try:
                position = RedditPosition(position_str)
            except ValueError:
                position = RedditPosition.BOTTOM_LEFT
            
            # Create widget
            widget = RedditWidget(
                parent=parent,
                position=position,
            )
            
            # Configure styling
            self._configure_styling(widget, config)
            
            # Configure shadow
            shadow_config = self._get_shadow_config(config)
            if shadow_config:
                widget.set_shadow_config(shadow_config)
            
            # Set thread manager
            if self._thread_manager:
                widget.set_thread_manager(self._thread_manager)
            
            # Configure Reddit-specific settings
            widget.set_subreddits(config.get("subreddits", ["pics", "earthporn"]))
            widget.set_rotation_interval(config.get("rotation_interval", 30))
            
            logger.debug("[REDDIT_FACTORY] Created RedditWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[REDDIT_FACTORY] Failed to create RedditWidget: {e}", exc_info=True)
            return None
    
    def _configure_styling(self, widget: QWidget, config: Dict[str, Any]) -> None:
        """Apply styling configuration to widget."""
        from widgets.reddit_widget import RedditWidget
        if not isinstance(widget, RedditWidget):
            return
        
        # Font
        font_family = config.get("font_family", "Segoe UI")
        font_size = config.get("font_size", 12)
        widget.set_font_family(font_family)
        widget.set_font_size(font_size)
        
        # Color
        color_str = config.get("color", "#FFFFFF")
        color = parse_color_to_qcolor(color_str)
        if color:
            widget.set_text_color(color)


class SpotifyVisualizerFactory(WidgetFactory):
    """Factory for creating SpotifyVisualizerWidget instances."""
    
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
