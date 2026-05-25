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
from core.settings.widget_capacity_policy import clamp_list_capacity
from widgets.spotify_visualizer.card_geometry import (
    build_growth_map_from_widget,
    resolve_card_metrics,
)
from rendering.widget_stacking import (
    StackObstacle,
    StackParticipant,
    build_stack_plan,
    get_stack_band,
    get_stack_lane,
)

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
            except Exception as e:
                logger.debug("[UI] Exception suppressed: %s", e)
                result.append((1920, 1080, 1.0))
        
        return result if result else [(1920, 1080, 1.0)]
    except Exception as e:
        logger.debug("[UI] Exception suppressed: %s", e)
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
    GMAIL = "gmail"
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
    except Exception as e:
        logger.debug("[UI] Exception suppressed: %s", e)
    
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
    except Exception as e:
        logger.debug("[UI] Exception suppressed: %s", e)
    
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


def estimate_gmail_size(font_size: int, item_count: int, width: int = 600) -> Tuple[int, int]:
    """Estimate Gmail widget size based on settings."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontMetrics

        app = QApplication.instance()
        if app is not None:
            header_font = QFont("Segoe UI", font_size, QFont.Weight.Bold)
            header_metrics = QFontMetrics(header_font)
            row_font = QFont("Segoe UI", font_size, QFont.Weight.Normal)
            row_metrics = QFontMetrics(row_font)
            header_height = header_metrics.height() + 28
            line_height = row_metrics.height() + 6
            row_spacing = 4
            card_padding = 26
            return (
                max(200, min(1200, int(width))),
                header_height
                + (item_count * line_height)
                + (max(0, item_count - 1) * row_spacing)
                + card_padding,
            )
    except Exception as e:
        logger.debug("[UI] Exception suppressed: %s", e)

    actual_font_height = int(font_size * 2.0)
    header_height = actual_font_height + 28
    line_height = actual_font_height + 6
    row_spacing = 4
    card_padding = 26
    return (
        max(200, min(1200, int(width))),
        header_height
        + (item_count * line_height)
        + (max(0, item_count - 1) * row_spacing)
        + card_padding,
    )


def estimate_spotify_vis_size(
    vis_settings: Dict,
    *,
    media_width: int,
) -> Tuple[int, int]:
    """Estimate Spotify visualizer authored card size."""
    mode_id = str(vis_settings.get("mode", "bubble") or "bubble").strip().lower()
    growth_holder = type(
        "_GrowthHolder",
        (),
        {
            "_spectrum_growth": float(vis_settings.get("spectrum_growth", 2.0)),
            "_osc_growth": float(vis_settings.get("osc_growth", 2.0)),
            "_blob_growth": float(vis_settings.get("blob_growth", 3.5)),
            "_sine_wave_growth": float(vis_settings.get("sine_wave_growth", 2.0)),
            "_bubble_growth": float(vis_settings.get("bubble_growth", 3.0)),
            "_devcurve_growth": float(vis_settings.get("devcurve_growth", 3.5)),
        },
    )()
    metrics = resolve_card_metrics(
        mode_id,
        int(vis_settings.get("base_height", 80)),
        build_growth_map_from_widget(growth_holder),
    )
    return (max(10, int(media_width)), int(metrics.preferred_height))


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
    if clock.get('enabled', False) and str(clock.get('position', '')).strip().lower() != "custom":
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
    if clock2.get('enabled', False) and str(clock.get('position', '')).strip().lower() != "custom":
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
    if clock3.get('enabled', False) and str(clock.get('position', '')).strip().lower() != "custom":
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
    if weather.get('enabled', False) and str(weather.get('position', '')).strip().lower() != "custom":
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
    if media.get('enabled', False) and str(media.get('position', '')).strip().lower() != "custom":
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
    if reddit.get('enabled', False) and str(reddit.get('position', '')).strip().lower() != "custom":
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
    if reddit2.get('enabled', False) and str(reddit2.get('position', '')).strip().lower() != "custom":
        # Reddit 2 inherits font from Reddit 1
        font_size = reddit.get('font_size', 18)
        item_count = clamp_list_capacity(reddit2.get('limit', 20), default=20)
        w, h = estimate_reddit_size(font_size, item_count)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.REDDIT2,
            position=reddit2.get('position', 'Top Left'),
            monitor=str(reddit2.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    # Gmail
    gmail = settings.get('gmail', {})
    if gmail.get('enabled', False) and str(gmail.get('position', '')).strip().lower() != "custom":
        font_size = gmail.get('font_size', 18)
        item_count = clamp_list_capacity(gmail.get('limit', 5), default=5)
        width = max(200, min(1200, int(gmail.get('width', gmail.get('min_width', gmail.get('max_width', 600))))))
        width, h = estimate_gmail_size(font_size, item_count, width)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.GMAIL,
            position=gmail.get('position', 'Top Left'),
            monitor=str(gmail.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=width,
            estimated_height=h,
        ))
    
    # Spotify visualizer reserves authored lane space relative to Media
    # even though it is not independently stackable.
    spotify_vis = settings.get('spotify_visualizer', {})
    if (
        media.get('enabled', False)
        and str(media.get('position', '')).strip().lower() != "custom"
        and spotify_vis.get('visualizers_enabled', True)
        and spotify_vis.get('enabled', True)
        and str(spotify_vis.get('position', '')).strip().lower() != "custom"
    ):
        media_font_size = media.get('font_size', 14)
        artwork_size = media.get('artwork_size', 80)
        media_width, media_height = estimate_media_size(media_font_size, artwork_size)
        vis_width, vis_height = estimate_spotify_vis_size(
            spotify_vis,
            media_width=media_width,
        )
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.SPOTIFY_VIS,
            position=media.get('position', 'Bottom Right'),
            monitor=str(media.get('monitor', 'ALL')),
            enabled=True,
            estimated_width=vis_width,
            estimated_height=vis_height,
        ))
    
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
        WidgetType.GMAIL: "Gmail",
        WidgetType.SPOTIFY_VIS: "Spotify Visualizer",
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
    target_pos_key = target_position.lower().replace(" ", "_")
    target_lane = get_stack_lane(target_pos_key)
    if target_lane is None:
        return (True, "", [])

    lane_members: List[WidgetEstimate] = []
    for est in estimates:
        if not est.enabled:
            continue
        monitors_overlap = (
            target_monitor == "ALL" or
            est.monitor == "ALL" or
            target_monitor == est.monitor
        )
        if not monitors_overlap:
            continue
        lane = get_stack_lane(est.position_key())
        if lane != target_lane:
            continue
        lane_members.append(est)

    target_est = None
    for est in estimates:
        if est.widget_type == target_widget:
            target_est = est
            break
    if target_est is None:
        target_est = WidgetEstimate(
            widget_type=target_widget,
            position=target_position,
            monitor=target_monitor,
            enabled=True,
            estimated_width=350,
            estimated_height=100,
        )
        lane_members.append(target_est)

    conflicting = [est for est in lane_members if est.widget_type != target_widget]
    if not conflicting:
        return (True, "", [])

    def _estimate_base_y(est: WidgetEstimate) -> int:
        pos_key = est.position_key()
        if "top" in pos_key:
            return 20
        if "bottom" in pos_key:
            return screen_height - est.estimated_height - 20
        return (screen_height - est.estimated_height) // 2

    sorted_members = sorted(lane_members, key=lambda item: item.widget_type.value)
    media_est = next((est for est in sorted_members if est.widget_type == WidgetType.MEDIA), None)
    vis_est = next((est for est in sorted_members if est.widget_type == WidgetType.SPOTIFY_VIS), None)

    obstacles: list[StackObstacle] = []
    excluded_types: set[WidgetType] = set()
    if media_est is not None and vis_est is not None:
        media_top = _estimate_base_y(media_est)
        vis_top = _estimate_base_y(vis_est)
        block_top = min(media_top, vis_top)
        block_bottom = max(
            media_top + media_est.estimated_height,
            vis_top + vis_est.estimated_height,
        )
        obstacles.append(
            StackObstacle(
                key="spotify_media_visualizer_block",
                lane=target_lane,
                top_y=block_top,
                height=max(0, block_bottom - block_top),
            )
        )
        excluded_types.update({WidgetType.MEDIA, WidgetType.SPOTIFY_VIS})

    participants = []
    for index, est in enumerate(sorted_members):
        if est.widget_type in excluded_types:
            continue
        participants.append(
            StackParticipant(
                key=est.widget_type.value,
                lane=target_lane,
                band=get_stack_band(est.position_key()) or "middle",
                base_y=_estimate_base_y(est),
                height=est.estimated_height,
                order=index,
            )
        )

    plan = build_stack_plan(
        participants,
        obstacles=obstacles or None,
        container_height=screen_height,
        spacing=10,
    )

    conflicting_types = [est.widget_type for est in conflicting]
    conflict_names = [_get_widget_display_name(est.widget_type) for est in conflicting]
    conflict_str = ", ".join(conflict_names)
    if plan.lane_fit.get(target_lane, True):
        return (True, f"Will stack with {conflict_str}!", conflicting_types)
    return (False, f"Conflicts with {conflict_str}!", conflicting_types)


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
    if str(position or "").strip().lower() == "custom":
        return (True, "")
    global_cfg = settings.get("global", {})
    if not isinstance(global_cfg, dict):
        global_cfg = {}
    if not bool(global_cfg.get("stacking_enabled", False)):
        return (True, "")

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
