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


class MediaWidgetFactory(WidgetFactory):
    """Factory for the temporary non-painting Media/Visualizer anchor."""
    
    def get_widget_name(self) -> str:
        return "media"
    
    def create(
        self,
        parent: QWidget,
        config: Dict[str, Any],
        *,
        shadows_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[QWidget]:
        """Create the runtime/geometry anchor; retained Quick owns styling."""
        from widgets.media_widget import MediaWidget, MediaPosition
        from core.settings.models import MediaWidgetSettings, WidgetPosition, coerce_widget_position
        
        model = MediaWidgetSettings.from_mapping(config if isinstance(config, dict) else {})
        if not SettingsManager.to_bool(model.enabled, False):
            return None
        
        del shadows_config

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
                WidgetPosition.CUSTOM: MediaPosition.BOTTOM_LEFT,
            }
            
            widget_pos = coerce_widget_position(model.position, WidgetPosition.BOTTOM_LEFT)
            position = position_map.get(widget_pos, MediaPosition.BOTTOM_LEFT)
            
            widget = MediaWidget(
                parent=parent,
                position=position,
                provider=model.provider,
                build_default_runtime=False,
            )
            
            # Thread manager
            if self._thread_manager and hasattr(widget, "set_thread_manager"):
                widget.set_thread_manager(self._thread_manager)
            
            widget.set_margin(model.margin)
            widget.set_artwork_size(int(model.artwork_size))
            
            logger.debug("[MEDIA_FACTORY] Created MediaWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[MEDIA_FACTORY] Failed to create MediaWidget: {e}", exc_info=True)
            return None


class SpotifyVisualizerFactory(WidgetFactory):
    """Factory for creating SpotifyVisualizerWidget instances."""
    
    def __init__(self, settings: SettingsManager, thread_manager: Optional["ThreadManager"] = None):
        super().__init__(settings, thread_manager)
        self._process_supervisor = None
    
    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor for worker integration."""
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
            
            # Set process supervisor for worker integration
            if self._process_supervisor:
                widget.set_process_supervisor(self._process_supervisor)
            
            logger.debug("[SPOTIFY_VIS_FACTORY] Created SpotifyVisualizerWidget")
            return widget
            
        except Exception as e:
            logger.error(f"[SPOTIFY_VIS_FACTORY] Failed to create SpotifyVisualizerWidget: {e}", exc_info=True)
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
        self.register(MediaWidgetFactory(self._settings, self._thread_manager))
        self.register(SpotifyVisualizerFactory(self._settings, self._thread_manager))

    def set_thread_manager(self, thread_manager: Optional["ThreadManager"]) -> None:
        """Update thread manager on the registry and all factories."""
        self._thread_manager = thread_manager
        for factory in self._factories.values():
            if hasattr(factory, "_thread_manager"):
                factory._thread_manager = thread_manager

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
        
        Currently only SpotifyVisualizerFactory uses this for worker integration.
        """
        spotify_factory = self._factories.get("spotify_visualizer")
        if spotify_factory and hasattr(spotify_factory, "set_process_supervisor"):
            spotify_factory.set_process_supervisor(supervisor)
            logger.debug("[FACTORY_REGISTRY] ProcessSupervisor set on spotify_visualizer factory")
