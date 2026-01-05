"""
Widget setup helpers for DisplayWidget.

Extracts widget creation logic from DisplayWidget._setup_widgets() to reduce
the monolithic method size and improve maintainability.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Set
from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from core.settings import SettingsManager

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget

logger = get_logger(__name__)


def parse_color_to_qcolor(color_data: Any, opacity_override: float = None) -> Optional[QColor]:
    """Parse color data [r,g,b,a] to QColor, with optional opacity override.
    
    Args:
        color_data: List/tuple of [r, g, b] or [r, g, b, a] values
        opacity_override: Optional opacity multiplier (0.0-1.0) to apply to alpha
        
    Returns:
        QColor or None if parsing fails
    """
    try:
        r, g, b = color_data[0], color_data[1], color_data[2]
        a = color_data[3] if len(color_data) > 3 else 255
        if opacity_override is not None:
            a = int(max(0.0, min(1.0, opacity_override)) * a)
        return QColor(r, g, b, a)
    except Exception as e:
        logger.debug("[MISC] Exception suppressed: %s", e)
        return None


def resolve_monitor_visibility(monitor_sel: str, screen_index: int) -> bool:
    """Determine if a widget should be visible on the given screen.
    
    Args:
        monitor_sel: Monitor selection string ('ALL' or monitor number as string)
        screen_index: 0-based screen index
        
    Returns:
        True if widget should be visible on this screen
    """
    try:
        return (monitor_sel == 'ALL') or (int(monitor_sel) == (screen_index + 1))
    except Exception as e:
        logger.debug("[MISC] Exception suppressed: %s", e)
        return True  # Default to visible on parse error


def setup_dimming(display: "DisplayWidget", widgets_config: Dict) -> None:
    """Configure dimming overlay via GL compositor.
    
    Args:
        display: The DisplayWidget instance
        widgets_config: Widget settings dictionary
    """
    settings = display.settings_manager
    if not settings:
        return
        
    dimming_enabled = SettingsManager.to_bool(
        settings.get('accessibility.dimming.enabled', False), False
    )
    try:
        dimming_opacity = int(settings.get('accessibility.dimming.opacity', 30))
        dimming_opacity = max(10, min(90, dimming_opacity))
    except (ValueError, TypeError):
        dimming_opacity = 30
    
    # Store dimming state
    display._dimming_enabled = dimming_enabled
    display._dimming_opacity = dimming_opacity / 100.0
    
    # Configure GL compositor dimming if available
    comp = getattr(display, "_gl_compositor", None)
    if comp is not None and hasattr(comp, "set_dimming"):
        comp.set_dimming(dimming_enabled, display._dimming_opacity)
        logger.debug("GL compositor dimming: enabled=%s, opacity=%d%%", 
                     dimming_enabled, dimming_opacity)


def get_widget_shadow_config(widgets_config: Dict) -> Dict:
    """Extract shadow configuration from widgets config.
    
    Args:
        widgets_config: Widget settings dictionary
        
    Returns:
        Shadow configuration dictionary
    """
    if isinstance(widgets_config, dict):
        return widgets_config.get('shadows', {})
    return {}


def compute_expected_overlays(
    display: "DisplayWidget",
    widgets_config: Dict,
) -> Set[str]:
    """Compute which overlays are expected on this display for fade coordination.
    
    Args:
        display: The DisplayWidget instance
        widgets_config: Widget settings dictionary
        
    Returns:
        Set of overlay names expected on this display
    """
    expected = set()
    screen_index = display.screen_index
    
    widgets_map = widgets_config if isinstance(widgets_config, dict) else {}
    
    # Weather
    weather_settings = widgets_map.get('weather', {})
    weather_enabled = SettingsManager.to_bool(weather_settings.get('enabled', False), False)
    weather_monitor = weather_settings.get('monitor', 'ALL')
    if weather_enabled and resolve_monitor_visibility(weather_monitor, screen_index):
        expected.add("weather")
    
    # Reddit
    reddit_settings = widgets_map.get('reddit', {})
    reddit_enabled = SettingsManager.to_bool(reddit_settings.get('enabled', False), False)
    reddit_monitor = reddit_settings.get('monitor', 'ALL')
    if reddit_enabled and resolve_monitor_visibility(reddit_monitor, screen_index):
        expected.add("reddit")
    
    # Media
    media_settings = widgets_map.get('media', {})
    media_enabled = SettingsManager.to_bool(media_settings.get('enabled', False), False)
    media_monitor = media_settings.get('monitor', 'ALL')
    if media_enabled and resolve_monitor_visibility(media_monitor, screen_index):
        expected.add("media")
        
        # Spotify visualizer (only if media is also enabled)
        spotify_vis_settings = widgets_map.get('spotify_visualizer', {})
        spotify_vis_enabled = SettingsManager.to_bool(
            spotify_vis_settings.get('enabled', False), False
        )
        if spotify_vis_enabled:
            expected.add("spotify_visualizer")
    
    return expected
