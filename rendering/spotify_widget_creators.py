"""Spotify widget creation routines for WidgetManager.

Extracted from widget_manager.py (M-7 refactor) to reduce monolith size.
Contains create_spotify_volume_widget and create_spotify_visualizer_widget.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Mapping

from PySide6.QtGui import QColor

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.settings_manager import SettingsManager
from core.settings.models import SpotifyVisualizerSettings, MediaWidgetSettings
from rendering.widget_setup import parse_color_to_qcolor
from widgets.media_widget import MediaWidget
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_volume_widget import SpotifyVolumeWidget

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


def create_spotify_volume_widget(
    mgr: "WidgetManager",
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
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        show_on_this = False

    if not (spotify_volume_enabled and show_on_this):
        return None

    try:
        vol = SpotifyVolumeWidget(mgr._parent)

        if thread_manager is not None and hasattr(vol, "set_thread_manager"):
            try:
                vol.set_thread_manager(thread_manager)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        try:
            vol.set_shadow_config(shadows_config)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Set anchor to media widget for visibility gating
        try:
            if hasattr(vol, "set_anchor_media_widget"):
                vol.set_anchor_media_widget(media_widget)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Inherit media card background and border colours
        bg_color_data = media_model.bg_color
        bg_qcolor = parse_color_to_qcolor(bg_color_data)
        border_color_data = media_model.border_color
        border_opacity = media_model.border_opacity
        try:
            bo = float(border_opacity)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bo = 0.8
        border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)

        try:
            fill_color_data = media_model.spotify_volume_fill_color or [255, 255, 255, 230]
            try:
                fr, fg, fb = fill_color_data[0], fill_color_data[1], fill_color_data[2]
                fa = fill_color_data[3] if len(fill_color_data) > 3 else 230
                fill_color = QColor(fr, fg, fb, fa)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                fill_color = QColor(255, 255, 255, 230)

            if hasattr(vol, "set_colors"):
                vol.set_colors(track_bg=bg_qcolor, track_border=border_qcolor, fill=fill_color)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        mgr.register_widget("spotify_volume", vol)
        # Add to expected overlays so it participates in coordinated fade
        mgr.add_expected_overlay("spotify_volume")
        mgr._bind_parent_attribute("spotify_volume_widget", vol)
        if is_perf_metrics_enabled():
            logger.info(
                "[SPOTIFY_VOL] Created volume widget (screen=%s, monitor=%s)",
                screen_index,
                media_monitor_sel,
            )
        logger.debug("Spotify volume widget created, will start with coordinated fade")
        return vol
    except Exception as e:
        logger.error("Failed to create Spotify volume widget: %s", e, exc_info=True)
        return None


def create_spotify_visualizer_widget(
    mgr: "WidgetManager",
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
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        show_on_this = False

    if not (spotify_vis_enabled and show_on_this):
        return None

    mgr.add_expected_overlay("spotify_visualizer")

    try:
        bar_count = int(model.bar_count)
        vis = SpotifyVisualizerWidget(mgr._parent, bar_count=bar_count)

        mgr._log_spotify_vis_config("create", spotify_vis_settings)
        if is_perf_metrics_enabled():
            logger.info(
                "[SPOTIFY_VIS] Created visualizer widget (screen=%s, bar_count=%s, monitor=%s)",
                screen_index,
                bar_count,
                media_monitor_sel,
            )

        # Preferred audio block size (0=auto)
        try:
            block_size = int(model.audio_block_size or 0)
            if hasattr(vis, 'set_audio_block_size'):
                vis.set_audio_block_size(block_size)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # ThreadManager for animation tick scheduling
        if thread_manager is not None and hasattr(vis, 'set_thread_manager'):
            try:
                vis.set_thread_manager(thread_manager)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Anchor geometry to media widget
        try:
            vis.set_anchor_media_widget(media_widget)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Card style inheritance from media widget
        bg_color_data = media_settings.get('bg_color', [64, 64, 64, 255])
        bg_qcolor = parse_color_to_qcolor(bg_color_data)
        try:
            bg_opacity = float(media_settings.get('bg_opacity', 0.9))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bg_opacity = 0.9
        border_color_data = media_settings.get('border_color', [128, 128, 128, 255])
        border_opacity = media_settings.get('border_opacity', 0.8)
        try:
            bo = float(border_opacity)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Per-bar colours
        try:
            fill_color_data = spotify_vis_settings.get('bar_fill_color', [255, 255, 255, 230])
            fr, fg, fb = fill_color_data[0], fill_color_data[1], fill_color_data[2]
            fa = fill_color_data[3] if len(fill_color_data) > 3 else 230
            bar_fill_qcolor = QColor(fr, fg, fb, fa)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bar_fill_qcolor = QColor(255, 255, 255, 230)

        try:
            bar_border_color_data = spotify_vis_settings.get('bar_border_color', [255, 255, 255, 230])
            br_r, br_g, br_b = bar_border_color_data[0], bar_border_color_data[1], bar_border_color_data[2]
            base_alpha = bar_border_color_data[3] if len(bar_border_color_data) > 3 else 230
            try:
                bar_bo = float(spotify_vis_settings.get('bar_border_opacity', 0.85))
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                bar_bo = 0.85
            bar_bo = max(0.0, min(1.0, bar_bo))
            br_a = int(bar_bo * base_alpha)
            bar_border_qcolor = QColor(br_r, br_g, br_b, br_a)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bar_border_qcolor = QColor(255, 255, 255, 230)

        try:
            vis.set_bar_colors(bar_fill_qcolor, bar_border_qcolor)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Ghosting configuration
        try:
            ghost_enabled = SettingsManager.to_bool(model.ghosting_enabled, True)
            ghost_alpha = float(model.ghost_alpha)
            ghost_decay = max(0.0, float(model.ghost_decay))
            if hasattr(vis, 'set_ghost_config'):
                vis.set_ghost_config(ghost_enabled, ghost_alpha, ghost_decay)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Sensitivity configuration
        try:
            recommended = SettingsManager.to_bool(model.adaptive_sensitivity, True)
            sens = max(0.25, min(2.5, float(model.sensitivity)))
            if hasattr(vis, 'set_sensitivity_config'):
                vis.set_sensitivity_config(recommended, sens)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Visualization mode (only spectrum supported)
        try:
            if hasattr(vis, 'set_visualization_mode'):
                from widgets.spotify_visualizer_widget import VisualizerMode
                vis.set_visualization_mode(VisualizerMode.SPECTRUM)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Noise floor configuration
        try:
            dynamic_floor = SettingsManager.to_bool(model.dynamic_floor, True)
            manual_floor = float(model.manual_floor)
            if hasattr(vis, 'set_floor_config'):
                vis.set_floor_config(dynamic_floor, manual_floor)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Shadow config
        try:
            vis.set_shadow_config(shadows_config)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Wire media state into visualizer
        try:
            if not getattr(vis, "_srpss_media_connected", False):
                media_widget.media_updated.connect(vis.handle_media_update)
                setattr(vis, "_srpss_media_connected", True)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        mgr.register_widget("spotify_visualizer", vis)
        logger.debug("Spotify visualizer widget created: %d bars, will start with coordinated fade", bar_count)
        mgr._bind_parent_attribute("spotify_visualizer_widget", vis)
        return vis
    except Exception as e:
        logger.error("Failed to create Spotify visualizer widget: %s", e, exc_info=True)
        return None
