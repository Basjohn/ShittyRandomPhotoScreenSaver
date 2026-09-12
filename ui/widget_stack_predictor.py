"""
Widget stacking prediction for settings UI.

Provides estimated size calculations and collision detection for overlay widgets
WITHOUT instantiating actual widget objects. This is purely for settings UI
feedback to help users understand position conflicts.

This module is ONLY used by the settings dialog and does not affect runtime.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Tuple

from core.logging.logger import get_logger
from core.settings.widget_capacity_policy import clamp_list_capacity
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO,
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
    STEAM_PROGRESS = "steam_progress"
    ACHIEVEMENT_PULSE = "achievement_pulse"
    ABANDONMENT_ISSUES = "abandonment_issues"
    FRIEND_PULSE = "friend_pulse"
    SYSTEM_STATS = "system_stats"


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
    show_day_of_week: bool = False,
    show_date: bool = False,
    calendar_layout: str = "shared_line",
    calendar_font_size: int = 20,
) -> Tuple[int, int]:
    """Estimate clock widget size based on settings.
    
    Uses actual QFontMetrics when Qt is available for accurate height calculation.
    
    Args:
        font_size: Font size in pixels
        show_seconds: Whether seconds are shown (digital only)
        show_tz: Whether timezone label is shown
        display_mode: "digital" or "analogue" - analogue clocks are square and larger
        show_day_of_week: Whether the weekday footer is shown
        show_date: Whether the DD/MM/YYYY footer is shown
        calendar_layout: Shared line or two-line weekday/date layout
        calendar_font_size: Weekday/date font size
    """
    # Try to use actual font metrics
    actual_font_height = None
    calendar_height = 0
    calendar_width = 0
    calendar_lines = 0
    if show_day_of_week or show_date:
        calendar_lines = (
            2
            if show_day_of_week and show_date and calendar_layout == "two_lines"
            else 1
        )
        if show_day_of_week and show_date and calendar_layout != "two_lines":
            calendar_sample = "WEDNESDAY - 31/12/2026"
        elif show_day_of_week:
            calendar_sample = "WEDNESDAY"
        else:
            calendar_sample = "31/12/2026"
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontMetrics
        
        app = QApplication.instance()
        if app is not None:
            font = QFont('Segoe UI', font_size)
            metrics = QFontMetrics(font)
            actual_font_height = metrics.height()
            if calendar_lines:
                calendar_metrics = QFontMetrics(QFont('Segoe UI', calendar_font_size))
                calendar_height = calendar_metrics.height() * calendar_lines
                calendar_width = calendar_metrics.horizontalAdvance(calendar_sample)
    except Exception as e:
        logger.debug("[UI] Exception suppressed: %s", e)
    
    if actual_font_height is None:
        # Fallback formula
        actual_font_height = int(font_size * 1.8)
    if calendar_lines and calendar_height <= 0:
        calendar_height = int(calendar_font_size * 1.8) * calendar_lines
        calendar_width = int(len(calendar_sample) * calendar_font_size * 0.6)
    
    if display_mode == "analogue" or display_mode == "analog":
        # Analogue clocks are square, sized based on font_size as a scaling factor
        # Clock analogue preview contract: scale the square face from font size.
        clock_diameter = max(160, int(font_size * 4.5))
        width = clock_diameter + 20
        height = clock_diameter + 20
        
        if show_tz:
            height += actual_font_height + 10
        if calendar_lines:
            height += calendar_height + 10
            width = max(width, calendar_width + 40)
        
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
    if calendar_lines:
        height += calendar_height + 10
        width = max(width, calendar_width + 40)
    
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


def estimate_steam_card_size(font_size: int, width: int = 420, height: int = 180) -> Tuple[int, int]:
    """Estimate a Steam card scaffold size for settings stack prediction."""
    scaled_height = max(int(height), int(font_size * 7.5))
    return (max(260, int(width)), max(120, scaled_height))


def estimate_friend_pulse_size(
    *,
    width: int = 560,
    view_mode: str = "grid",
    capacity: int = 4,
) -> Tuple[int, int]:
    """Estimate Friend Pulse geometry from its retained presentation contract.

    Friend Pulse reserves geometry from configured capacity, not source row
    count. Keep this calculation presentation-neutral so the settings stack
    predictor follows the same rows/grid contract without importing Qt Quick.
    """
    normalized_width = max(420, min(900, int(width)))
    normalized_capacity = max(1, min(6, int(capacity)))
    normalized_mode = str(view_mode or "grid").strip().lower()
    if normalized_mode not in {"rows", "grid"}:
        normalized_mode = "grid"
    if normalized_mode == "grid":
        columns = (
            2
            if normalized_capacity <= 4 or normalized_width < 540
            else 3
        )
        rows = (normalized_capacity + columns - 1) // columns
        height = 120 + rows * 102 + max(0, rows - 1) * 10
    else:
        height = 102 + normalized_capacity * 58
    return normalized_width, height


def estimate_spotify_vis_size(
    vis_settings: Mapping[str, Any],
    *,
    media_width: int,
) -> Tuple[int, int]:
    """Estimate ordinary Visualizer geometry from the active aspect contract.

    Mode-specific ``*_growth`` card-height tuning was retired by the Qt Quick
    geometry migration. Normal layout uses one 1.5 presentation aspect; CUSTOM
    viewport extent is owned by live layout state and is deliberately not
    predicted here.
    """
    _ = vis_settings  # admission/routing is resolved by the caller
    width = max(10, int(media_width))
    height = max(1, int(round(width / CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO)))
    return (width, height)


def _merge_section_defaults(
    defaults: Mapping[str, Any],
    current: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Overlay current section state onto its canonical product baseline."""
    merged = deepcopy(dict(defaults))
    if not isinstance(current, Mapping):
        return merged
    for key, value in current.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_section_defaults(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _resolved_widget_section(
    settings: Mapping[str, Any],
    defaults: Mapping[str, Any],
    section: str,
) -> dict[str, Any]:
    canonical = defaults.get(section)
    if not isinstance(canonical, Mapping):
        raise KeyError(f"Canonical Widget defaults are missing widgets.{section}")
    current = settings.get(section) if isinstance(settings, Mapping) else None
    return _merge_section_defaults(canonical, current if isinstance(current, Mapping) else None)


def build_widget_estimates(
    settings: Mapping[str, Any],
    *,
    defaults: Mapping[str, Any],
) -> List[WidgetEstimate]:
    """Build enabled-widget estimates from current state over canonical defaults."""
    estimates: List[WidgetEstimate] = []

    clock = _resolved_widget_section(settings, defaults, "clock")
    if bool(clock["enabled"]) and str(clock["position"]).strip().lower() != "custom":
        w, h = estimate_clock_size(
            int(clock["font_size"]),
            bool(clock["show_seconds"]),
            bool(clock["show_timezone"]),
            str(clock["display_mode"]),
            bool(clock["show_day_of_week"]),
            bool(clock["show_date"]),
            str(clock["calendar_layout"]),
            int(clock["calendar_font_size"]),
        )
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.CLOCK,
            position=str(clock["position"]),
            monitor=str(clock["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    # Clock 2/3 have their own persisted appearance/position state. They do not
    # expose Clock 1's calendar extensions, so those capability-only arguments
    # remain disabled rather than borrowing another widget's product defaults.
    for section, widget_type in (("clock2", WidgetType.CLOCK2), ("clock3", WidgetType.CLOCK3)):
        extra_clock = _resolved_widget_section(settings, defaults, section)
        if not bool(extra_clock["enabled"]):
            continue
        if str(extra_clock["position"]).strip().lower() == "custom":
            continue
        w, h = estimate_clock_size(
            int(extra_clock["font_size"]),
            bool(extra_clock["show_seconds"]),
            bool(extra_clock["show_timezone"]),
            str(extra_clock["display_mode"]),
            False,
            False,
            "shared_line",
            0,
        )
        estimates.append(WidgetEstimate(
            widget_type=widget_type,
            position=str(extra_clock["position"]),
            monitor=str(extra_clock["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    weather = _resolved_widget_section(settings, defaults, "weather")
    if bool(weather["enabled"]) and str(weather["position"]).strip().lower() != "custom":
        w, h = estimate_weather_size(int(weather["font_size"]), bool(weather["show_forecast"]))
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.WEATHER,
            position=str(weather["position"]),
            monitor=str(weather["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    media = _resolved_widget_section(settings, defaults, "media")
    if bool(media["enabled"]) and str(media["position"]).strip().lower() != "custom":
        w, h = estimate_media_size(int(media["font_size"]), int(media["artwork_size"]))
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.MEDIA,
            position=str(media["position"]),
            monitor=str(media["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    reddit = _resolved_widget_section(settings, defaults, "reddit")
    if bool(reddit["enabled"]) and str(reddit["position"]).strip().lower() != "custom":
        w, h = estimate_reddit_size(int(reddit["font_size"]), int(reddit["limit"]))
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.REDDIT,
            position=str(reddit["position"]),
            monitor=str(reddit["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    reddit2 = _resolved_widget_section(settings, defaults, "reddit2")
    if bool(reddit2["enabled"]) and str(reddit2["position"]).strip().lower() != "custom":
        item_count = clamp_list_capacity(
            reddit2["limit"], default=int(defaults["reddit2"]["limit"])
        )
        w, h = estimate_reddit_size(int(reddit["font_size"]), item_count)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.REDDIT2,
            position=str(reddit2["position"]),
            monitor=str(reddit2["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    gmail = _resolved_widget_section(settings, defaults, "gmail")
    if bool(gmail["enabled"]) and str(gmail["position"]).strip().lower() != "custom":
        item_count = clamp_list_capacity(
            gmail["limit"], default=int(defaults["gmail"]["limit"])
        )
        width = max(200, min(1200, int(gmail["width"])))
        width, h = estimate_gmail_size(int(gmail["font_size"]), item_count, width)
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.GMAIL,
            position=str(gmail["position"]),
            monitor=str(gmail["monitor"]),
            enabled=True,
            estimated_width=width,
            estimated_height=h,
        ))

    steam_type_map = {
        "steam_progress": WidgetType.STEAM_PROGRESS,
        "achievement_pulse": WidgetType.ACHIEVEMENT_PULSE,
        "abandonment_issues": WidgetType.ABANDONMENT_ISSUES,
        "friend_pulse": WidgetType.FRIEND_PULSE,
    }
    for section, widget_type in steam_type_map.items():
        steam_card = _resolved_widget_section(settings, defaults, section)
        if not bool(steam_card["enabled"]):
            continue
        if str(steam_card["position"]).strip().lower() == "custom":
            continue
        if section == "friend_pulse":
            w, h = estimate_friend_pulse_size(
                width=int(steam_card["preferred_width"]),
                view_mode=str(steam_card.get("view_mode", "grid")),
                capacity=int(steam_card.get("visible_row_capacity", 4)),
            )
        else:
            w, h = estimate_steam_card_size(
                int(steam_card["font_size"]),
                int(steam_card["preferred_width"]),
                int(steam_card["preferred_height"]),
            )
        estimates.append(WidgetEstimate(
            widget_type=widget_type,
            position=str(steam_card["position"]),
            monitor=str(steam_card["monitor"]),
            enabled=True,
            estimated_width=w,
            estimated_height=h,
        ))

    system_stats = _resolved_widget_section(settings, defaults, "system_stats")
    if (
        bool(system_stats["enabled"])
        and str(system_stats["position"]).strip().lower() != "custom"
    ):
        w, h = estimate_steam_card_size(
            int(system_stats["font_size"]),
            int(system_stats["preferred_width"]),
            int(system_stats["preferred_height"]),
        )
        estimates.append(
            WidgetEstimate(
                widget_type=WidgetType.SYSTEM_STATS,
                position=str(system_stats["position"]),
                monitor=str(system_stats["monitor"]),
                enabled=True,
                estimated_width=w,
                estimated_height=h,
            )
        )

    spotify_vis = _resolved_widget_section(settings, defaults, "spotify_visualizer")
    if (
        bool(media["enabled"])
        and str(media["position"]).strip().lower() != "custom"
        and bool(spotify_vis["visualizers_enabled"])
        and bool(spotify_vis["enabled"])
        and str(spotify_vis["position"]).strip().lower() != "custom"
    ):
        media_width, _media_height = estimate_media_size(
            int(media["font_size"]), int(media["artwork_size"])
        )
        vis_width, vis_height = estimate_spotify_vis_size(
            spotify_vis, media_width=media_width
        )
        estimates.append(WidgetEstimate(
            widget_type=WidgetType.SPOTIFY_VIS,
            position=str(media["position"]),
            monitor=str(media["monitor"]),
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
        WidgetType.STEAM_PROGRESS: "Steam Journey",
        WidgetType.ACHIEVEMENT_PULSE: "Achievement Pulse",
        WidgetType.ABANDONMENT_ISSUES: "Abandonment Issues",
        WidgetType.FRIEND_PULSE: "Friend Pulse",
        WidgetType.SYSTEM_STATS: "System Stats",
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
    settings: Mapping[str, Any],
    widget_type: WidgetType,
    position: str,
    monitor: str,
    *,
    defaults: Mapping[str, Any],
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
    global_cfg = _resolved_widget_section(settings, defaults, "global")
    if not bool(global_cfg["stacking_enabled"]):
        return (True, "")

    estimates = build_widget_estimates(settings, defaults=defaults)
    
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
