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
from core.settings.visualizer_presets import resolve_visualizer_activation_payload
from rendering.custom_layout_contract import get_screen_signature_aliases, load_custom_layout_map
from rendering.multi_monitor_coordinator import get_coordinator
from rendering.widget_setup import parse_color_to_qcolor
from rendering.widget_descriptors import (
    get_effective_monitor_value_for_widget,
    is_custom_position_selected_for_widget,
)
from widgets.spotify_visualizer.config_applier import normalize_blob_mode_contract_values
from widgets.media_widget import MediaWidget
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from widgets.spotify_volume_widget import SpotifyVolumeWidget
from widgets.mute_button_widget import MuteButtonWidget

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


def _resolve_display_screen(display) -> object | None:
    screen = getattr(display, "_screen", None)
    if screen is not None:
        return screen
    getter = getattr(display, "screen", None)
    if callable(getter):
        try:
            return getter()
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to resolve display.screen() during visualizer routing guard", exc_info=True)
    return None


def _resolve_invalid_custom_all_visualizer_target_screen_index(
    widgets_config: Mapping[str, object] | None,
) -> int | None:
    custom_layout_map = load_custom_layout_map(widgets_config)
    displays = custom_layout_map.get("displays", {})
    if not isinstance(displays, Mapping):
        return None

    owner_signatures = [
        str(signature)
        for signature, layouts in displays.items()
        if isinstance(layouts, Mapping) and isinstance(layouts.get("spotify_visualizer"), Mapping)
    ]
    if len(owner_signatures) != 1:
        return None

    target_signature = owner_signatures[0]
    try:
        instances = get_coordinator().get_all_instances()
    except Exception:
        logger.debug("[WIDGET_MANAGER] Failed to enumerate displays for invalid visualizer Custom+ALL guard", exc_info=True)
        return None

    for instance in instances:
        screen = _resolve_display_screen(instance)
        if screen is None:
            continue
        if target_signature in get_screen_signature_aliases(screen):
            try:
                return int(getattr(instance, "screen_index", -1))
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to read target screen index for invalid visualizer Custom+ALL guard", exc_info=True)
                return None
    return None


def _resolve_visualizer_anchor_media_widget(
    mgr: "WidgetManager",
    widgets_config: Mapping[str, object],
    screen_index: int,
    local_media_widget: Optional[MediaWidget],
) -> Optional[MediaWidget]:
    media_settings = widgets_config.get("media", {}) if isinstance(widgets_config, Mapping) else {}
    media_model = MediaWidgetSettings.from_mapping(media_settings if isinstance(media_settings, Mapping) else {})
    media_monitor_sel = str(media_model.monitor or "ALL")

    if media_monitor_sel == "ALL":
        if local_media_widget is not None:
            return local_media_widget
        try:
            instances = get_coordinator().get_all_instances()
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to enumerate displays for visualizer anchor resolution", exc_info=True)
            instances = []
        for instance in instances:
            candidate = getattr(instance, "media_widget", None)
            if candidate is not None:
                return candidate
        return None

    try:
        target_screen_index = max(0, int(media_monitor_sel) - 1)
    except Exception:
        logger.debug("[WIDGET_MANAGER] Invalid media monitor for visualizer anchor: %s", media_monitor_sel)
        return local_media_widget

    if local_media_widget is not None and screen_index == target_screen_index:
        return local_media_widget

    try:
        instances = get_coordinator().get_all_instances()
    except Exception:
        logger.debug("[WIDGET_MANAGER] Failed to enumerate displays for visualizer anchor resolution", exc_info=True)
        instances = []

    for instance in instances:
        if int(getattr(instance, "screen_index", -1)) != target_screen_index:
            continue
        candidate = getattr(instance, "media_widget", None)
        if candidate is not None:
            return candidate

    return local_media_widget


def apply_spotify_vis_model_config(vis, model: SpotifyVisualizerSettings, *, apply_mode: bool = True) -> None:
    """Apply full vis mode config from model to a live SpotifyVisualizerWidget.
    
    Reusable helper called from both initial setup and live settings refresh.
    """
    if not hasattr(vis, 'apply_vis_mode_config'):
        return
    spectrum_render_mode = str(getattr(model, "spectrum_render_mode", "bars") or "bars").lower()
    spectrum_single_piece = spectrum_render_mode != "segment"
    spectrum_unique_colors = bool(getattr(model, "spectrum_unique_colors", True))
    blob_shaper_enabled = bool(getattr(model, "blob_shaper_enabled", False))
    blob_motion_contract = normalize_blob_mode_contract_values(
        blob_shaper_enabled=blob_shaper_enabled,
        blob_reactive_deformation=model.blob_reactive_deformation,
        blob_constant_wobble=model.blob_constant_wobble,
        blob_reactive_wobble=model.blob_reactive_wobble,
        blob_stretch_tendency=model.blob_stretch_tendency,
        blob_stretch_inner=model.blob_stretch_inner,
        blob_stretch_outer=model.blob_stretch_outer,
    )
    kwargs = dict(
        mode=str(model.mode),
        bar_fill_color=model.bar_fill_color,
        bar_border_color=model.bar_border_color,
        bar_border_opacity=model.bar_border_opacity,
        osc_glow_enabled=model.osc_glow_enabled,
        osc_glow_intensity=model.osc_glow_intensity,
        osc_glow_color=model.osc_glow_color,
        osc_reactive_glow=model.osc_reactive_glow,
        osc_line_amplitude=model.osc_line_amplitude,
        osc_smoothing=model.osc_smoothing,
        blob_color=model.blob_color,
        blob_glow_color=model.blob_glow_color,
        blob_edge_color=model.blob_edge_color,
        blob_outline_color=model.blob_outline_color,
        blob_inward_liquid_color=model.blob_inward_liquid_color,
        blob_pulse=model.blob_pulse,
        blob_pulse_release_ms=model.blob_pulse_release_ms,
        blob_width=model.blob_width,
        blob_size=model.blob_size,
        blob_glow_intensity=model.blob_glow_intensity,
        blob_reactive_glow=model.blob_reactive_glow,
        blob_inward_liquid_enabled=model.blob_inward_liquid_enabled,
        blob_inward_liquid_reactivity=model.blob_inward_liquid_reactivity,
        blob_inward_liquid_max_size=model.blob_inward_liquid_max_size,
        osc_line_color=model.osc_line_color,
        osc_line_count=model.osc_line_count,
        osc_line2_color=model.osc_line2_color,
        osc_line2_glow_color=model.osc_line2_glow_color,
        osc_line3_color=model.osc_line3_color,
        osc_line3_glow_color=model.osc_line3_glow_color,
        osc_line4_color=model.osc_line4_color,
        osc_line4_glow_color=model.osc_line4_glow_color,
        osc_line5_color=model.osc_line5_color,
        osc_line5_glow_color=model.osc_line5_glow_color,
        osc_line6_color=model.osc_line6_color,
        osc_line6_glow_color=model.osc_line6_glow_color,
        osc_ghost_line2_enabled=model.osc_ghost_line2_enabled,
        osc_ghost_line3_enabled=model.osc_ghost_line3_enabled,
        osc_ghost_line4_enabled=model.osc_ghost_line4_enabled,
        osc_ghost_line5_enabled=model.osc_ghost_line5_enabled,
        osc_ghost_line6_enabled=model.osc_ghost_line6_enabled,
        osc_glow_reactivity=model.osc_glow_reactivity,
        spectrum_growth=model.spectrum_growth,
        spectrum_single_piece=spectrum_single_piece,
        spectrum_glow_enabled=model.spectrum_glow_enabled,
        spectrum_glow_intensity=model.spectrum_glow_intensity,
        spectrum_glow_color=model.spectrum_glow_color,
        spectrum_rainbow_per_bar=spectrum_unique_colors,
        spectrum_rainbow_border=bool(getattr(model, "spectrum_rainbow_border", False)),
        blob_growth=model.blob_growth,
        osc_speed=model.osc_speed,
        osc_line_dim=model.osc_line_dim,
        osc_line_offset_bias=model.osc_line_offset_bias,
        osc_vertical_shift=int(model.osc_vertical_shift),
        osc_growth=model.osc_growth,
        blob_reactive_deformation=blob_motion_contract['blob_reactive_deformation'],
        blob_pulse_cap=model.blob_pulse,
        blob_stage_gain=model.blob_stage_gain,
        blob_core_scale=model.blob_core_scale,
        blob_core_floor_bias=model.blob_core_floor_bias,
        blob_stage_bias=model.blob_stage_bias,
        blob_stage2_release_ms=max(400, int(round(model.blob_pulse_release_ms * 4.1))),
        blob_stage3_release_ms=max(500, int(round(model.blob_pulse_release_ms * 5.45))),
        blob_constant_wobble=blob_motion_contract['blob_constant_wobble'],
        blob_reactive_wobble=blob_motion_contract['blob_reactive_wobble'],
        blob_stretch=blob_motion_contract['blob_stretch_outer'],
        blob_stretch_tendency=blob_motion_contract['blob_stretch_tendency'],
        blob_stretch_inner=blob_motion_contract['blob_stretch_inner'],
        blob_stretch_outer=blob_motion_contract['blob_stretch_outer'],
        # Blob Shaper
        blob_shaper_enabled=blob_shaper_enabled,
        blob_shaper_base_strength=model.blob_shaper_base_strength,
        blob_shaper_react_strength=model.blob_shaper_react_strength,
        blob_shaper_idle_motion=model.blob_shaper_idle_motion,
        blob_shaper_audio_motion=model.blob_shaper_audio_motion,
        blob_topology=model.blob_topology,
        blob_ring_thickness=model.blob_ring_thickness,
        blob_shape_base_nodes=model.blob_shape_base_nodes,
        blob_shape_reaction_nodes=model.blob_shape_reaction_nodes,
        blob_shape_energy_nodes=model.blob_shape_energy_nodes,
        spectrum_border_radius=model.spectrum_border_radius,
        spectrum_mirrored=model.spectrum_mirrored,
        spectrum_shape_nodes=model.spectrum_shape_nodes,
        spectrum_lane_strengths_mirrored=model.spectrum_lane_strengths_mirrored,
        spectrum_lane_strengths_linear=model.spectrum_lane_strengths_linear,
        spectrum_wave_amplitude=model.spectrum_wave_amplitude,
        spectrum_profile_floor=model.spectrum_profile_floor,
        spectrum_drop_speed=model.spectrum_drop_speed,
        spectrum_notch_positions_mirrored=model.spectrum_notch_positions_mirrored,
        spectrum_notch_positions_linear=model.spectrum_notch_positions_linear,
        sine_wave_growth=model.sine_wave_growth,
        sine_wave_travel=model.sine_wave_travel,
        sine_glow_enabled=model.sine_glow_enabled,
        sine_glow_intensity=model.sine_glow_intensity,
        sine_glow_color=model.sine_glow_color,
        sine_line_color=model.sine_line_color,
        sine_reactive_glow=model.sine_reactive_glow,
        sine_sensitivity=model.sine_sensitivity,
        sine_speed=model.sine_speed,
        sine_line_count=model.sine_line_count,
        sine_line_offset_bias=model.sine_line_offset_bias,
        sine_smoothing=model.sine_smoothing,
        sine_glow_reactivity=model.sine_glow_reactivity,
        sine_line2_color=model.sine_line2_color,
        sine_line2_glow_color=model.sine_line2_glow_color,
        sine_line3_color=model.sine_line3_color,
        sine_line3_glow_color=model.sine_line3_glow_color,
        sine_line4_color=model.sine_line4_color,
        sine_line4_glow_color=model.sine_line4_glow_color,
        sine_line5_color=model.sine_line5_color,
        sine_line5_glow_color=model.sine_line5_glow_color,
        sine_line6_color=model.sine_line6_color,
        sine_line6_glow_color=model.sine_line6_glow_color,
        sine_ghost_line2_enabled=model.sine_ghost_line2_enabled,
        sine_ghost_line3_enabled=model.sine_ghost_line3_enabled,
        sine_ghost_line4_enabled=model.sine_ghost_line4_enabled,
        sine_ghost_line5_enabled=model.sine_ghost_line5_enabled,
        sine_ghost_line6_enabled=model.sine_ghost_line6_enabled,
        sine_travel_line2=model.sine_travel_line2,
        sine_travel_line3=model.sine_travel_line3,
        sine_travel_line4=model.sine_travel_line4,
        sine_travel_line5=model.sine_travel_line5,
        sine_travel_line6=model.sine_travel_line6,
        sine_line1_shift=model.sine_line1_shift,
        sine_line2_shift=model.sine_line2_shift,
        sine_line3_shift=model.sine_line3_shift,
        sine_line4_shift=model.sine_line4_shift,
        sine_line5_shift=model.sine_line5_shift,
        sine_line6_shift=model.sine_line6_shift,
        sine_wave_effect=model.sine_wave_effect,
        sine_micro_wobble=model.sine_micro_wobble,
        sine_width_reaction=model.sine_width_reaction,
        sine_vertical_shift=model.sine_vertical_shift,
        sine_card_adaptation=model.sine_card_adaptation,
        rainbow_enabled=model.rainbow_enabled,
        rainbow_speed=model.rainbow_speed,
        spectrum_ghosting_enabled=model.spectrum_ghosting_enabled,
        spectrum_ghost_alpha=model.spectrum_ghost_alpha,
        spectrum_ghost_decay=model.spectrum_ghost_decay,
        osc_ghosting_enabled=model.osc_ghosting_enabled,
        osc_ghost_intensity=model.osc_ghost_intensity,
        blob_ghosting_enabled=model.blob_ghosting_enabled,
        blob_ghost_alpha=model.blob_ghost_alpha,
        blob_ghost_decay=model.blob_ghost_decay,
        sine_ghosting_enabled=model.sine_ghosting_enabled,
        sine_ghost_alpha=model.sine_ghost_alpha,
        sine_ghost_decay=model.sine_ghost_decay,
        bubble_ghosting_enabled=model.bubble_ghosting_enabled,
        bubble_ghost_alpha=model.bubble_ghost_alpha,
        bubble_ghost_decay=model.bubble_ghost_decay,
        blob_glow_reactivity=model.blob_glow_reactivity,
        blob_glow_max_size=model.blob_glow_max_size,
        sine_heartbeat=model.sine_heartbeat,
        sine_density=model.sine_density,
        sine_displacement=model.sine_displacement,
        sine_crawl_amount=model.sine_crawl_amount,
        # Bubble
        bubble_big_bass_pulse=model.bubble_big_bass_pulse,
        bubble_small_freq_pulse=model.bubble_small_freq_pulse,
        bubble_stream_direction=model.bubble_stream_direction,
        bubble_stream_constant_speed=model.bubble_stream_constant_speed,
        bubble_stream_speed_cap=model.bubble_stream_speed_cap,
        bubble_stream_reactivity=model.bubble_stream_reactivity,
        bubble_rotation_amount=model.bubble_rotation_amount,
        bubble_drift_amount=model.bubble_drift_amount,
        bubble_drift_speed=model.bubble_drift_speed,
        bubble_drift_frequency=model.bubble_drift_frequency,
        bubble_drift_direction=model.bubble_drift_direction,
        bubble_big_count=model.bubble_big_count,
        bubble_small_count=model.bubble_small_count,
        bubble_surface_reach=model.bubble_surface_reach,
        bubble_bounce_big_pct=model.bubble_bounce_big_pct,
        bubble_bounce_small_pct=model.bubble_bounce_small_pct,
        bubble_bounce_big_speed=model.bubble_bounce_big_speed,
        bubble_bounce_small_speed=model.bubble_bounce_small_speed,
        bubble_bounce_same_only=model.bubble_bounce_same_only,
        bubble_collision_pop_mode=model.bubble_collision_pop_mode,
        bubble_outline_color=model.bubble_outline_color,
        bubble_specular_color=model.bubble_specular_color,
        bubble_gradient_light=model.bubble_gradient_light,
        bubble_gradient_dark=model.bubble_gradient_dark,
        bubble_pop_color=model.bubble_pop_color,
        bubble_specular_direction=model.bubble_specular_direction,
        bubble_gradient_direction=model.bubble_gradient_direction,
        bubble_big_size_max=model.bubble_big_size_max,
        bubble_small_size_max=model.bubble_small_size_max,
        bubble_big_contraction_bias=model.bubble_big_contraction_bias,
        bubble_big_size_clamp=model.bubble_big_size_clamp,
        bubble_big_specular_max_size=model.bubble_big_specular_max_size,
        bubble_growth=model.bubble_growth,
        devcurve_growth=model.devcurve_growth,
        bubble_trail_strength=model.bubble_trail_strength,
        bubble_tail_opacity=model.bubble_tail_opacity,
        # Dev Curve
        devcurve_active_layer=model.devcurve_active_layer,
        devcurve_layer_bass_shape_nodes=model.devcurve_layer_bass_shape_nodes,
        devcurve_layer_vocals_shape_nodes=model.devcurve_layer_vocals_shape_nodes,
        devcurve_layer_mids_shape_nodes=model.devcurve_layer_mids_shape_nodes,
        devcurve_layer_transients_shape_nodes=model.devcurve_layer_transients_shape_nodes,
        devcurve_base_level=model.devcurve_base_level,
        devcurve_motion_power=model.devcurve_motion_power,
        devcurve_idle_motion=model.devcurve_idle_motion,
        devcurve_idle_speed=model.devcurve_idle_speed,
        devcurve_smoothness=model.devcurve_smoothness,
        devcurve_layer_bass_enabled=model.devcurve_layer_bass_enabled,
        devcurve_layer_bass_color=model.devcurve_layer_bass_color,
        devcurve_layer_bass_alpha=model.devcurve_layer_bass_alpha,
        devcurve_layer_bass_power=model.devcurve_layer_bass_power,
        devcurve_layer_bass_offset=model.devcurve_layer_bass_offset,
        devcurve_layer_bass_outline_color=model.devcurve_layer_bass_outline_color,
        devcurve_layer_bass_outline_width=model.devcurve_layer_bass_outline_width,
        devcurve_layer_bass_order=model.devcurve_layer_bass_order,
        devcurve_layer_vocals_enabled=model.devcurve_layer_vocals_enabled,
        devcurve_layer_vocals_color=model.devcurve_layer_vocals_color,
        devcurve_layer_vocals_alpha=model.devcurve_layer_vocals_alpha,
        devcurve_layer_vocals_power=model.devcurve_layer_vocals_power,
        devcurve_layer_vocals_offset=model.devcurve_layer_vocals_offset,
        devcurve_layer_vocals_outline_color=model.devcurve_layer_vocals_outline_color,
        devcurve_layer_vocals_outline_width=model.devcurve_layer_vocals_outline_width,
        devcurve_layer_vocals_order=model.devcurve_layer_vocals_order,
        devcurve_layer_mids_enabled=model.devcurve_layer_mids_enabled,
        devcurve_layer_mids_color=model.devcurve_layer_mids_color,
        devcurve_layer_mids_alpha=model.devcurve_layer_mids_alpha,
        devcurve_layer_mids_power=model.devcurve_layer_mids_power,
        devcurve_layer_mids_offset=model.devcurve_layer_mids_offset,
        devcurve_layer_mids_outline_color=model.devcurve_layer_mids_outline_color,
        devcurve_layer_mids_outline_width=model.devcurve_layer_mids_outline_width,
        devcurve_layer_mids_order=model.devcurve_layer_mids_order,
        devcurve_layer_transients_enabled=model.devcurve_layer_transients_enabled,
        devcurve_layer_transients_color=model.devcurve_layer_transients_color,
        devcurve_layer_transients_alpha=model.devcurve_layer_transients_alpha,
        devcurve_layer_transients_power=model.devcurve_layer_transients_power,
        devcurve_layer_transients_offset=model.devcurve_layer_transients_offset,
        devcurve_layer_transients_outline_color=model.devcurve_layer_transients_outline_color,
        devcurve_layer_transients_outline_width=model.devcurve_layer_transients_outline_width,
        devcurve_layer_transients_order=model.devcurve_layer_transients_order,
        devcurve_foreground_shadow_enabled=model.devcurve_foreground_shadow_enabled,
        devcurve_foreground_shadow_alpha=model.devcurve_foreground_shadow_alpha,
        devcurve_foreground_shadow_darken=model.devcurve_foreground_shadow_darken,
        devcurve_foreground_shadow_offset=model.devcurve_foreground_shadow_offset,
        devcurve_foreground_specular_enabled=model.devcurve_foreground_specular_enabled,
        devcurve_foreground_specular_alpha=model.devcurve_foreground_specular_alpha,
        devcurve_foreground_specular_width=model.devcurve_foreground_specular_width,
        devcurve_foreground_specular_offset=model.devcurve_foreground_specular_offset,
        devcurve_foreground_specular_crest_bias=model.devcurve_foreground_specular_crest_bias,
        devcurve_ghosting_enabled=model.devcurve_ghosting_enabled,
        devcurve_ghost_alpha=model.devcurve_ghost_alpha,
        devcurve_ghost_decay=model.devcurve_ghost_decay,
        sine_line_dim=model.sine_line_dim,
    )

    if apply_mode:
        vis.apply_vis_mode_config(**kwargs)
        return

    from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs

    apply_vis_mode_kwargs(vis, kwargs)
    try:
        vis._cached_vis_kwargs = dict(kwargs)
    except Exception:
        pass


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
        provider = str(getattr(media_model, 'provider', 'spotify') or 'spotify')
        vol = SpotifyVolumeWidget(mgr._parent, provider=provider)

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
            fill_color_data = media_model.spotify_volume_fill_color or [255, 255, 255, 140]
            try:
                fr, fg, fb = fill_color_data[0], fill_color_data[1], fill_color_data[2]
                fa = fill_color_data[3] if len(fill_color_data) > 3 else 140
                # Migrate old default: set_colors() used to force alpha=140,
                # so saved alpha=230 was never visible — convert to 140.
                if fa == 230 and fr == 255 and fg == 255 and fb == 255:
                    fa = 140
                fill_color = QColor(fr, fg, fb, fa)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                fill_color = QColor(255, 255, 255, 140)

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
    media_settings = widgets_config.get('media', {}) if isinstance(widgets_config, dict) else {}
    media_model = MediaWidgetSettings.from_mapping(media_settings if isinstance(media_settings, Mapping) else {})
    spotify_vis_settings = widgets_config.get('spotify_visualizer', {}) if isinstance(widgets_config, dict) else {}
    activation_payload = resolve_visualizer_activation_payload(
        spotify_vis_settings if isinstance(spotify_vis_settings, Mapping) else {}
    )
    model = SpotifyVisualizerSettings.from_mapping(
        activation_payload.resolved_config,
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )
    spotify_vis_enabled = SettingsManager.to_bool(model.enabled, False)

    effective_monitor_sel = get_effective_monitor_value_for_widget(
        "spotify_visualizer",
        widgets_config if isinstance(widgets_config, Mapping) else None,
        default=str(media_model.monitor or "ALL"),
    )
    custom_routing_active = is_custom_position_selected_for_widget(
        "spotify_visualizer",
        widgets_config if isinstance(widgets_config, Mapping) else None,
    )
    invalid_custom_all_target_screen_index = None
    if custom_routing_active and str(effective_monitor_sel or "ALL").strip().upper() == "ALL":
        invalid_custom_all_target_screen_index = _resolve_invalid_custom_all_visualizer_target_screen_index(
            widgets_config if isinstance(widgets_config, Mapping) else None,
        )
        if invalid_custom_all_target_screen_index is not None:
            effective_monitor_sel = str(invalid_custom_all_target_screen_index + 1)
            logger.warning(
                "[SPOTIFY_VIS] Recovered invalid Custom+ALL monitor route by inferring screen=%s from saved CUSTOM layout",
                invalid_custom_all_target_screen_index,
            )
        else:
            logger.warning(
                "[SPOTIFY_VIS] Suppressing invalid Custom+ALL visualizer creation; unable to infer a single owning display"
            )
            return None
    try:
        show_on_this = (effective_monitor_sel == 'ALL') or (int(effective_monitor_sel) == (screen_index + 1))
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        show_on_this = False

    anchor_media_widget = _resolve_visualizer_anchor_media_widget(
        mgr,
        widgets_config if isinstance(widgets_config, Mapping) else {},
        screen_index,
        media_widget,
    )

    if not (spotify_vis_enabled and show_on_this and anchor_media_widget is not None):
        return None

    try:
        try:
            bar_count = int(model.resolve_bar_count(str(model.mode)))
        except Exception:
            bar_count = int(model.bar_count)
        vis = SpotifyVisualizerWidget(
            mgr._parent,
            bar_count=bar_count,
            initial_mode=activation_payload.mode,
        )

        mgr._log_spotify_vis_config(
            "create",
            activation_payload.resolved_config,
            model=model,
            activation_payload=activation_payload,
        )
        if is_perf_metrics_enabled():
            logger.info(
                "[SPOTIFY_VIS] Created visualizer widget (screen=%s, bar_count=%s, monitor=%s, custom_routing=%s)",
                screen_index,
                bar_count,
                effective_monitor_sel,
                custom_routing_active,
            )

        # Anchor geometry to media widget
        try:
            vis.set_anchor_media_widget(anchor_media_widget)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Card style inheritance from media model (canonical defaults)
        bg_color_data = media_model.bg_color
        bg_qcolor = parse_color_to_qcolor(bg_color_data)
        try:
            bg_opacity = float(media_model.background_opacity)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bg_opacity = 0.5
        border_color_data = media_model.border_color
        try:
            bo = float(media_model.border_opacity)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bo = 0.8
        border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
        show_background = media_model.show_background

        try:
            vis.set_bar_style(
                bg_color=bg_qcolor,
                bg_opacity=bg_opacity,
                border_color=border_qcolor,
                show_background=show_background,
            )
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Visualization mode + per-mode settings
        if hasattr(vis, "apply_resolved_activation_payload"):
            try:
                vis.apply_resolved_activation_payload(
                    model,
                    activation_payload,
                    reason="startup_create",
                    force_runtime_reset=False,
                )
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        else:
            if hasattr(vis, 'set_settings_model'):
                try:
                    vis.set_settings_model(model)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            try:
                apply_spotify_vis_model_config(vis, model)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # ThreadManager propagation may need to replay authoritative technical
        # config into the shared engine, so wire it only after the startup
        # activation payload/settings model have been applied.
        if thread_manager is not None and hasattr(vis, 'set_thread_manager'):
            try:
                vis.set_thread_manager(thread_manager)
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
                anchor_media_widget.media_updated.connect(vis.handle_media_update)
                setattr(vis, "_srpss_media_connected", True)
                # Fast path for already-warm media widgets: if metadata is
                # already cached, seed the visualizer immediately. The
                # authoritative cold-start seed still happens inside the
                # visualizer lifecycle once startup ordering has settled.
                try:
                    vis._seed_playback_state_from_anchor(
                        reason="creator_fast_path",
                        request_refresh_if_missing=False,
                    )
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed during playback state seed: %s", e)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        mgr.register_widget("spotify_visualizer", vis)
        logger.debug("Spotify visualizer widget created: %d bars, will start with coordinated fade", bar_count)
        mgr._bind_parent_attribute("spotify_visualizer_widget", vis)
        try:
            if hasattr(mgr, '_refresh_spotify_visualizer_config'):
                # Keep launch-time visualizer state on the same canonical path
                # that settings re-entry uses so startup cannot drift.
                mgr._refresh_spotify_visualizer_config(widgets_config)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return vis
    except Exception as e:
        logger.error("Failed to create Spotify visualizer widget: %s", e, exc_info=True)
        return None


def create_mute_button_widget(
    mgr: "WidgetManager",
    widgets_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"] = None,
    media_widget: Optional[MediaWidget] = None,
) -> Optional[MuteButtonWidget]:
    """Create and configure a system mute button widget."""
    if media_widget is None:
        return None

    media_settings = widgets_config.get('media', {}) if isinstance(widgets_config, dict) else {}
    media_model = MediaWidgetSettings.from_mapping(media_settings if isinstance(media_settings, Mapping) else {})
    mute_enabled = SettingsManager.to_bool(media_settings.get('mute_button_enabled', False), False)
    if not mute_enabled:
        return None

    media_monitor_sel = media_model.monitor
    try:
        show_on_this = (media_monitor_sel == 'ALL') or (int(media_monitor_sel) == (screen_index + 1))
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        show_on_this = False

    if not show_on_this:
        return None

    try:
        btn = MuteButtonWidget(mgr._parent)
        btn.set_enabled(True)

        if thread_manager is not None:
            btn.set_thread_manager(thread_manager)

        btn.set_anchor(media_widget)

        # Inherit media card background and border colours from model
        bg_color_data = media_model.bg_color
        bg_qcolor = parse_color_to_qcolor(bg_color_data)
        border_color_data = media_model.border_color
        try:
            bo = float(media_model.border_opacity)
        except Exception:
            bo = 0.8
        border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=bo)
        text_color_data = media_model.color
        icon_qcolor = parse_color_to_qcolor(text_color_data)

        if bg_qcolor and border_qcolor and icon_qcolor:
            btn.set_colors(bg_qcolor, border_qcolor, icon_qcolor)

        mgr.register_widget("mute_button", btn)
        mgr.add_expected_overlay("mute_button")
        mgr._bind_parent_attribute("mute_button_widget", btn)
        logger.debug("[MUTE_BTN] Created mute button widget (screen=%s)", screen_index)
        return btn
    except Exception as e:
        logger.error("Failed to create mute button widget: %s", e, exc_info=True)
        return None

