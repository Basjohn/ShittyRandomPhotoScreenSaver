"""
Widget stacking prediction for settings UI.

Provides estimated size calculations and collision detection for overlay widgets
WITHOUT instantiating actual widget objects. This is purely for settings UI
feedback to help users understand position conflicts.

This module is ONLY used by the settings dialog and does not affect runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)


def get_screen_info() -> List[Tuple[int, int, float]]:
    """Get available screen resolutions with DPI scaling.
    
    Returns:
        List of (width, height, device_pixel_ratio) tuples for each screen.
        Falls back to [(1920, 1080, 1.0)] if Qt is unavailable.
    """
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QGuiApplication
        
        app = QApplication.instance()
        if app is None:
            return [(1920, 1080, 1.0)]
        
        screens = QGuiApplication.screens()
        if not screens:
            return [(1920, 1080, 1.0)]
        
        result = []
        for screen in screens:
            try:
                geom = screen.geometry()
                dpr = screen.devicePixelRatio()
                # Use logical size (what widgets see)
                result.append((geom.width(), geom.height(), dpr))
            except Exception:
                result.append((1920, 1080, 1.0))
        
        return result if result else [(1920, 1080, 1.0)]
    except Exception:
        return [(1920, 1080, 1.0)]


def get_screen_height_for_monitor(monitor: str) -> int:
    """Get the screen height for a specific monitor selection.
    
    Args:
        monitor: "ALL", "1", "2", "3", etc.
        
    Returns:
        Screen height in logical pixels. For "ALL", returns minimum height
        across all screens to be conservative.
    """
    screens = get_screen_info()
    
    if not screens:
        return 1080
    
    if monitor == "ALL":
        # Use minimum height across all screens (conservative)
        return min(h for _, h, _ in screens)
    
    try:
        idx = int(monitor) - 1  # Convert 1-based to 0-based
        if 0 <= idx < len(screens):
            return screens[idx][1]
    except (ValueError, IndexError):
        pass
    
    # Fallback to first screen or minimum
    return screens[0][1] if screens else 1080


class WidgetType(Enum):
    """Widget types for prediction."""
    CLOCK = "clock"
    CLOCK2 = "clock2"
    CLOCK3 = "clock3"
    WEATHER = "weather"
    MEDIA = "media"
    REDDIT = "reddit"
    REDDIT2 = "reddit2"
    SPOTIFY_VIS = "spotify_visualizer"


@dataclass
class WidgetEstimate:
    """Estimated widget dimensions for stacking prediction."""
    widget_type: WidgetType
    position: str  # "Top Left", "Top Right", etc.
    monitor: str   # "ALL", "1", "2", "3"
    enabled: bool
    estimated_width: int
    estimated_height: int
    
    def position_key(self) -> str:
        """Get normalized position key for grouping."""
        return self.position.lower().replace(" ", "_")


def estimate_clock_size(
    font_size: int,
    show_seconds: bool = True,
    show_tz: bool = False,
    display_mode: str = "digital",
) -> Tuple[int, int]:
    """Estimate clock widget size based on settings.
    
    Uses actual QFontMetrics when Qt is available for accurate height calculation.
    
    Args:
        font_size: Font size in pixels
        show_seconds: Whether seconds are shown (digital only)
        show_tz: Whether timezone label is shown
        display_mode: "digital" or "analogue" - analogue clocks are square and larger
    """
    # Try to use actual font metrics
    actual_font_height = None
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontMetrics
        
        app = QApplication.instance()
        if app is not None:
            font = QFont('Segoe UI', font_size)
            metrics = QFontMetrics(font)
            actual_font_height = metrics.height()
    except Exception:
        pass
    
    if actual_font_height is None:
        # Fallback formula
        actual_font_height = int(font_size * 1.8)
    
    if display_mode == "analogue" or display_mode == "analog":
        # Analogue clocks are square, sized based on font_size as a scaling factor
        # Matches clock_widget.py: base_side = max(160, int(self._font_size * 4.5))
        clock_diameter = max(160, int(font_size * 4.5))
        width = clock_diameter + 20
        height = clock_diameter + 20
        
        if show_tz:
            height += actual_font_height + 10
        
        return (width, height)
    
    # Digital clock sizing
    char_width = font_size * 0.6
    base_width = int(char_width * 5)  # "HH:MM"
    
    if show_seconds:
        base_width += int(char_width * 3)  # ":SS"
    
    width = base_width + 40
    height = actual_font_height + 30
    
    if show_tz:
        height += actual_font_height + 10
    
    return (width, height)


def estimate_weather_size(font_size: int, show_forecast: bool = False) -> Tuple[int, int]:
    """Estimate weather widget size based on settings."""
    # QFontMetrics.height() is typically ~1.8x the point size on Windows
    font_height_multiplier = 1.8
    actual_font_height = int(font_size * font_height_multiplier)
    
    # Weather shows: icon + temp + condition
    width = 200 + font_size * 2  # Icon + text
    height = actual_font_height * 2 + 40  # Two lines + padding
    
    if show_forecast:
        height += actual_font_height + 10  # Forecast line
    
    return (width, height)


def estimate_media_size(font_size: int, artwork_size: int = 80) -> Tuple[int, int]:
    """Estimate media widget size based on settings."""
    # Media card: artwork + text area + controls
    width = artwork_size + 200  # Artwork + text width
    height = max(artwork_size, font_size * 3) + 50  # Artwork or 3 lines + controls
    return (width, height)


def estimate_reddit_size(font_size: int, item_count: int) -> Tuple[int, int]:
    """Estimate reddit widget size based on settings.
    
    Uses actual QFontMetrics when Qt is available for accurate height calculation.
    Falls back to formula-based estimation otherwise.
    
    Measured at runtime with DPR=1.5:
    - 10-post widget: 468px actual (from stacking offset log)
    - 4-post widget: ~250px actual
    """
    try:
        # Use actual Qt font metrics for accuracy
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontMetrics
        
        app = QApplication.instance()
        if app is not None:
            font_family = 'Segoe UI'
            
            # Header font
            header_font = QFont(font_family, font_size, QFont.Weight.Bold)
            header_metrics = QFontMetrics(header_font)
            header_height = header_metrics.height() + 8
            
            # Title font (determines line height)
            title_font = QFont(font_family, font_size, QFont.Weight.Bold)
            title_metrics = QFontMetrics(title_font)
            line_height = title_metrics.height() + 4
            
            row_spacing = 4
            card_padding = 22
            margins_safety = 4
            shadow_buffer = 30  # Buffer for shadows and stacking gap
            
            width = 350
            height = (
                header_height
                + (item_count * line_height)
                + (max(0, item_count - 1) * row_spacing)
                + card_padding
                + margins_safety
                + shadow_buffer
            )
            return (width, height)
    except Exception:
        pass
    
    # Fallback: formula-based estimation
    # Use conservative multiplier to account for DPI variance
    font_height_multiplier = 2.0
    header_font_height = int(font_size * font_height_multiplier) + 8
    line_height = int(font_size * font_height_multiplier) + 4
    row_spacing = 4
    card_padding = 22
    margins_safety = 4
    shadow_buffer = 30
    
    width = 350
    height = (
        header_font_height
        + (item_count * line_height)
        + (max(0, item_count - 1) * row_spacing)
        + card_padding
        + margins_safety
        + shadow_buffer
    )
    return (width, height)


def estimate_spotify_vis_size(bar_count: int = 16) -> Tuple[int, int]:
    """Estimate Spotify visualizer size."""
    # Visualizer is positioned relative to media widget
    # but for collision purposes, estimate its footprint
    width = bar_count * 8 + 20
    height = 60
    return (width, height)


def build_widget_estimates(settings: Dict) -> List[WidgetEstimate]:
    """Build list of enabled widget estimates from settings.
    
    Args:
        settings: Full settings dict (from SettingsManager.get('widgets'))
        
    Returns:
        List of WidgetEstimate for all enabled widgets
    """
    estimates = []
    
    # Clock 1
    clock = settings.get('clock', {})
    if clock.get('enabled', False):
        font_size = clock.get('font_size', 48)
        show_seconds = clock.get('show_seconds', False)
        show_tz = clock.get('show_timezone_label', False)
        display_mode = clock.get('display_mode', 'digital')
        w, h = estimate_clock_size(font_size, show_seconds, show_tz, display_mode)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.CLOCK,
            position=clock.get('position', 'Top Right'),
            monitor=str(clock.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # Clock 2
    clock2 = settings.get('clock2', {})
    if clock2.get('enabled', False):
        # Clock 2/3 inherit font and display_mode from Clock 1
        font_size = clock.get('font_size', 48)
        display_mode = clock.get('display_mode', 'digital')
        w, h = estimate_clock_size(font_size, display_mode=display_mode)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.CLOCK2,
            position=clock.get('position', 'Top Right'),  # Same position as Clock 1
            monitor=str(clock2.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # Clock 3
    clock3 = settings.get('clock3', {})
    if clock3.get('enabled', False):
        font_size = clock.get('font_size', 48)
        display_mode = clock.get('display_mode', 'digital')
        w, h = estimate_clock_size(font_size, display_mode=display_mode)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.CLOCK3,
            position=clock.get('position', 'Top Right'),  # Same position as Clock 1
            monitor=str(clock3.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # Weather
    weather = settings.get('weather', {})
    if weather.get('enabled', False):
        font_size = weather.get('font_size', 18)
        show_forecast = weather.get('show_forecast', False)
        w, h = estimate_weather_size(font_size, show_forecast)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.WEATHER,
            position=weather.get('position', 'Top Left'),
            monitor=str(weather.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # Media
    media = settings.get('media', {})
    if media.get('enabled', False):
        font_size = media.get('font_size', 14)
        artwork_size = media.get('artwork_size', 80)
        w, h = estimate_media_size(font_size, artwork_size)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.MEDIA,
            position=media.get('position', 'Bottom Right'),
            monitor=str(media.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # Reddit
    reddit = settings.get('reddit', {})
    if reddit.get('enabled', False):
        font_size = reddit.get('font_size', 18)
        item_count = reddit.get('limit', 10)
        w, h = estimate_reddit_size(font_size, item_count)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.REDDIT,
            position=reddit.get('position', 'Bottom Right'),
            monitor=str(reddit.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # Reddit 2
    reddit2 = settings.get('reddit2', {})
    if reddit2.get('enabled', False):
        # Reddit 2 inherits font from Reddit 1
        font_size = reddit.get('font_size', 18)
        item_count = reddit2.get('limit', 4)
        w, h = estimate_reddit_size(font_size, item_count)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.REDDIT2,
            position=reddit2.get('position', 'Top Left'),
            monitor=str(reddit2.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))
    
    # NOTE: Spotify Visualizer is NOT included in stacking estimates.
    # It's a companion widget that floats above Media, not a separate
    # stackable widget. Including it would cause false "Will stack!"
    # messages for Media widget.
    
    return estimates


def _get_widget_display_name(widget_type: WidgetType) -> str:
    """Get human-readable display name for a widget type."""
    names = {
        WidgetType.CLOCK: "Clock",
        WidgetType.CLOCK2: "Clock 2",
        WidgetType.CLOCK3: "Clock 3",
        WidgetType.WEATHER: "Weather",
        WidgetType.MEDIA: "Media",
        WidgetType.REDDIT: "Reddit",
        WidgetType.REDDIT2: "Reddit 2",
    }
    return names.get(widget_type, widget_type.value)


def predict_stacking_status(
    estimates: List[WidgetEstimate],
    target_widget: WidgetType,
    target_position: str,
    target_monitor: str,
    screen_height: int = 1080,
) -> Tuple[bool, str, List[WidgetType]]:
    """Predict if a widget can stack at the given position.
    
    Args:
        estimates: List of all widget estimates
        target_widget: The widget type being configured
        target_position: Position being set ("Top Left", etc.)
        target_monitor: Monitor selection ("ALL", "1", "2", "3")
        screen_height: Assumed screen height for calculations
        
    Returns:
        Tuple of (can_stack: bool, message: str, conflicting_widgets: List[WidgetType])
        - (True, "", []) if no conflict (widget alone at position)
        - (True, "Will stack with X!", [X]) if stacking is possible
        - (False, "Conflicts with X!", [X]) if cannot stack
    """
    # Normalize position for comparison
    target_pos_key = target_position.lower().replace(" ", "_")
    
    # Find other widgets at the same position that would be visible on same monitor
    conflicting: List[WidgetEstimate] = []
    for est in estimates:
        if est.widget_type == target_widget:
            continue  # Skip self
        if not est.enabled:
            continue
        if est.position_key() != target_pos_key:
            continue
        
        # Check monitor overlap
        # "ALL" conflicts with everything, specific numbers only conflict with same or "ALL"
        monitors_overlap = (
            target_monitor == "ALL" or
            est.monitor == "ALL" or
            target_monitor == est.monitor
        )
        if not monitors_overlap:
            continue
        
        conflicting.append(est)
    
    if not conflicting:
        return (True, "", [])  # No conflict, no message needed
    
    # Build list of conflicting widget types for return
    conflicting_types = [est.widget_type for est in conflicting]
    
    # Build human-readable names for message
    conflict_names = [_get_widget_display_name(est.widget_type) for est in conflicting]
    conflict_str = ", ".join(conflict_names)
    
    # Calculate if stacking is possible
    # Get the target widget's estimated size
    target_est = None
    for est in estimates:
        if est.widget_type == target_widget:
            target_est = est
            break
    
    if target_est is None:
        # Widget not in estimates yet (being configured), use default size
        target_height = 100
    else:
        target_height = target_est.estimated_height
    
    # Calculate total height needed for widgets at this position
    total_height = target_height
    spacing = 10
    for est in conflicting:
        total_height += est.estimated_height + spacing
    
    # Also check for widgets on the opposite vertical edge of the same horizontal edge
    # e.g., bottom_right widgets can conflict with top_right widgets if combined height
    # exceeds screen height
    opposite_height = 0
    is_bottom = 'bottom' in target_pos_key
    is_top = 'top' in target_pos_key
    is_right = 'right' in target_pos_key
    is_left = 'left' in target_pos_key
    
    for est in estimates:
        if not est.enabled:
            continue
        est_pos = est.position_key()
        
        # Check monitor overlap
        monitors_overlap = (
            target_monitor == "ALL" or
            est.monitor == "ALL" or
            target_monitor == est.monitor
        )
        if not monitors_overlap:
            continue
        
        # Check if on opposite vertical edge of same horizontal edge
        est_is_bottom = 'bottom' in est_pos
        est_is_top = 'top' in est_pos
        est_is_right = 'right' in est_pos
        est_is_left = 'left' in est_pos
        
        same_horizontal_edge = (is_right and est_is_right) or (is_left and est_is_left)
        opposite_vertical = (is_bottom and est_is_top) or (is_top and est_is_bottom)
        
        if same_horizontal_edge and opposite_vertical:
            opposite_height += est.estimated_height + spacing
    
    # Check against available space (screen height minus margins)
    margin = 40  # Top + bottom margins
    available = screen_height - margin
    
    # Total space needed is our stack + opposite edge widgets
    combined_height = total_height + opposite_height
    
    if combined_height <= available:
        return (True, f"Will stack with {conflict_str}!", conflicting_types)
    else:
        # Determine if it's a same-position conflict or cross-edge conflict
        if total_height > available:
            return (False, f"Conflicts with {conflict_str}!", conflicting_types)
        else:
            # Cross-edge conflict - mention the opposite edge widgets
            return (False, f"Conflicts with {conflict_str} (screen too small)!", conflicting_types)


def get_position_status_for_widget(
    settings: Dict,
    widget_type: WidgetType,
    position: str,
    monitor: str,
) -> Tuple[bool, str]:
    """Get stacking status for a specific widget configuration.
    
    This is the main entry point for the settings UI.
    Automatically detects screen height based on monitor selection.
    
    Args:
        settings: Full widgets settings dict
        widget_type: Widget being configured
        position: Position being set
        monitor: Monitor selection ("ALL", "1", "2", "3")
        
    Returns:
        Tuple of (can_stack: bool, status_message: str)
    """
    estimates = build_widget_estimates(settings)
    
    # Determine the effective screen height for prediction
    # If this widget or any conflicting widget is on "ALL", use minimum height
    # to be conservative about the worst-case scenario
    target_pos_key = position.lower().replace(" ", "_")
    
    any_on_all = (monitor == "ALL")
    if not any_on_all:
        for est in estimates:
            if est.widget_type == widget_type:
                continue
            if not est.enabled:
                continue
            if est.position_key() != target_pos_key:
                continue
            # Check if this conflicting widget overlaps with our monitor
            if est.monitor == "ALL" or est.monitor == monitor:
                if est.monitor == "ALL":
                    any_on_all = True
                    break
    
    if any_on_all:
        # Use minimum screen height (conservative for ALL displays)
        screen_height = get_screen_height_for_monitor("ALL")
    else:
        # Use specific monitor height
        screen_height = get_screen_height_for_monitor(monitor)
    
    can_stack, message, _conflicting = predict_stacking_status(
        estimates, widget_type, position, monitor, screen_height
    )
    return (can_stack, message)
