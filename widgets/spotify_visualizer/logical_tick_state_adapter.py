"""Legacy widget delegation for controller-owned logical tick state (H).

While ``SpotifyVisualizerWidget`` remains the pre-cutover production presenter,
its authored per-tick logical fields are owned by the controller's
``VisualizerLogicalTickState`` (see the H visualizer runtime ownership
correction). This mixin makes each such widget field a delegating property to
``self._runtime_controller.logical_tick_state`` so the existing widget setup/tick
code keeps working unchanged while the state's single owner is the controller.

This is an explicit, enumerated delegation of named old-presenter seams - not a
generic ``__getattr__`` facade. When the atomic production cutover deletes the
legacy widget, this mixin is deleted with it and only the controller-owned state
remains.
"""

from __future__ import annotations

from typing import Any


# The authored per-tick logical fields that now live on the controller-owned
# VisualizerLogicalTickState. Enumerated explicitly; the widget delegates each.
LOCAL_LOGICAL_TICK_FIELDS: tuple[str, ...] = (
    "_bubble_big_bass_pulse",
    "_bubble_big_contraction_bias",
    "_bubble_big_count",
    "_bubble_big_size_clamp",
    "_bubble_big_size_max",
    "_bubble_big_specular_max_size",
    "_bubble_bounce_big_pct",
    "_bubble_bounce_big_speed",
    "_bubble_bounce_same_only",
    "_bubble_bounce_small_pct",
    "_bubble_bounce_small_speed",
    "_bubble_cadence_state",
    "_bubble_count",
    "_bubble_dispatch_energy_snapshot",
    "_bubble_dispatch_pulse_params",
    "_bubble_dispatch_settings",
    "_bubble_drift_amount",
    "_bubble_drift_direction",
    "_bubble_drift_frequency",
    "_bubble_drift_speed",
    "_bubble_extra_data",
    "_bubble_last_perf_diag",
    "_bubble_last_tick_ts",
    "_bubble_pos_data",
    "_bubble_rotation_amount",
    "_bubble_small_count",
    "_bubble_small_freq_pulse",
    "_bubble_small_size_max",
    "_bubble_stream_constant_speed",
    "_bubble_stream_direction",
    "_bubble_stream_reactivity",
    "_bubble_stream_speed_cap",
    "_bubble_surface_reach",
    "_bubble_trail_data",
    "_bubble_trail_strength",
    "_bubble_visible_render_state_ts",
    "_bubble_visible_simulation_ts",
    "_bubble_visible_source_ts",
    "_devcurve_active_amplitude",
    "_devcurve_diag_last_log_ts",
    "_devcurve_draw_order",
    "_devcurve_foreground_layer",
    "_devcurve_foreground_layer_id",
    "_devcurve_foreground_travel_pos",
    "_devcurve_foreground_travel_rate",
    "_devcurve_idle_amplitude",
    "_devcurve_sample_count",
    "_devcurve_smoothness_max_step",
    "_devcurve_specular_activity_alpha",
    "_devcurve_specular_travel_rate",
    "_display_bars",
    "_display_bars_source_activation",
    "_display_bars_source_generation",
    "_dt_spike_threshold_ms",
    "_fallback_logged",
    "_has_pushed_first_frame",
    "_heartbeat_avg_bass",
    "_heartbeat_fast_bass",
    "_heartbeat_fast_prev",
    "_heartbeat_intensity",
    "_heartbeat_last_log_ts",
    "_heartbeat_last_trigger_ts",
    "_heartbeat_last_ts",
    "_last_update_ts",
    "_latency_audio_ready",
    "_latency_authority",
    "_latency_error_ms",
    "_latency_last_log_ts",
    "_latency_last_signature",
    "_latency_log_interval",
    "_latency_pending_probe",
    "_latency_warn_ms",
    "_mode_teardown_block_until_ready",
    "_mode_teardown_state",
    "_mode_teardown_target_generation",
    "_mode_transition_phase",
    "_mode_transition_ready",
    "_perf_audio_lag_last_ms",
    "_perf_audio_lag_max_ms",
    "_perf_audio_lag_min_ms",
    "_perf_last_log_ts",
    "_perf_paint_frame_count",
    "_perf_paint_last_ts",
    "_perf_paint_max_dt",
    "_perf_paint_min_dt",
    "_perf_paint_start_ts",
    "_perf_tick_frame_count",
    "_perf_tick_last_ts",
    "_perf_tick_max_dt",
    "_perf_tick_min_dt",
    "_perf_tick_start_ts",
    "_sine_heartbeat",
    "_smoothing",
    "_waiting_for_fresh_engine_frame",
    "_waiting_for_fresh_frame",
    # --- Authored-logical per-mode configuration (H pre-cutover Finding B) ----
    # Consumed by each mode's *FrameRuntime.resolve / DevCurve logical field
    # solve. Owned by the controller-owned logical state; the widget delegates so
    # one storage serves both the authored logical step and legacy readers.
    # Spectrum.
    "_spectrum_single_piece",
    "_spectrum_visual_smoothing_enabled",
    "_spectrum_visual_smoothing",
    "_spectrum_ghosting_enabled",
    "_spectrum_ghost_decay",
    # Oscilloscope.
    "_osc_speed",
    "_osc_line_amplitude",
    "_osc_ghosting_enabled",
    "_osc_ghost_intensity",
    "_osc_ghost_decay",
    # Sine.
    "_sine_speed",
    "_sine_line_count",
    "_sine_wave_travel",
    "_sine_travel_line2",
    "_sine_travel_line3",
    "_sine_travel_line4",
    "_sine_travel_line5",
    "_sine_travel_line6",
    "_sine_line1_shift",
    "_sine_line2_shift",
    "_sine_line3_shift",
    "_sine_line4_shift",
    "_sine_line5_shift",
    "_sine_line6_shift",
    "_sine_width_reaction",
    "_sine_sensitivity",
    "_sine_ghosting_enabled",
    "_sine_ghost_alpha",
    "_sine_ghost_decay",
    # DevCurve (the field solve consumes its full parameter snapshot).
    "_devcurve_active_layer",
    "_devcurve_base_level",
    "_devcurve_motion_power",
    "_devcurve_idle_motion",
    "_devcurve_idle_speed",
    "_devcurve_smoothness",
    "_devcurve_ghosting_enabled",
    "_devcurve_ghost_alpha",
    "_devcurve_ghost_decay",
    "_devcurve_foreground_shadow_enabled",
    "_devcurve_foreground_shadow_alpha",
    "_devcurve_foreground_shadow_darken",
    "_devcurve_foreground_shadow_offset",
    "_devcurve_foreground_specular_enabled",
    "_devcurve_foreground_specular_alpha",
    "_devcurve_foreground_specular_width",
    "_devcurve_foreground_specular_offset",
    "_devcurve_foreground_specular_crest_bias",
    "_devcurve_layer_bass_enabled",
    "_devcurve_layer_bass_color",
    "_devcurve_layer_bass_alpha",
    "_devcurve_layer_bass_power",
    "_devcurve_layer_bass_offset",
    "_devcurve_layer_bass_order",
    "_devcurve_layer_bass_outline_color",
    "_devcurve_layer_bass_outline_width",
    "_devcurve_layer_bass_shape_nodes",
    "_devcurve_layer_vocals_enabled",
    "_devcurve_layer_vocals_color",
    "_devcurve_layer_vocals_alpha",
    "_devcurve_layer_vocals_power",
    "_devcurve_layer_vocals_offset",
    "_devcurve_layer_vocals_order",
    "_devcurve_layer_vocals_outline_color",
    "_devcurve_layer_vocals_outline_width",
    "_devcurve_layer_vocals_shape_nodes",
    "_devcurve_layer_mids_enabled",
    "_devcurve_layer_mids_color",
    "_devcurve_layer_mids_alpha",
    "_devcurve_layer_mids_power",
    "_devcurve_layer_mids_offset",
    "_devcurve_layer_mids_order",
    "_devcurve_layer_mids_outline_color",
    "_devcurve_layer_mids_outline_width",
    "_devcurve_layer_mids_shape_nodes",
    "_devcurve_layer_transients_enabled",
    "_devcurve_layer_transients_color",
    "_devcurve_layer_transients_alpha",
    "_devcurve_layer_transients_power",
    "_devcurve_layer_transients_offset",
    "_devcurve_layer_transients_order",
    "_devcurve_layer_transients_outline_color",
    "_devcurve_layer_transients_outline_width",
    "_devcurve_layer_transients_shape_nodes",
)


def _make_delegated_property(field_name: str) -> property:
    def getter(self: Any) -> Any:
        return getattr(self._runtime_controller.logical_tick_state, field_name)

    def setter(self: Any, value: Any) -> None:
        setattr(self._runtime_controller.logical_tick_state, field_name, value)

    getter.__name__ = field_name
    setter.__name__ = field_name
    return property(getter, setter)


class LegacyVisualizerLogicalTickStateAdapterMixin:
    """Named delegating properties for controller-owned logical tick fields."""


for _field in LOCAL_LOGICAL_TICK_FIELDS:
    setattr(
        LegacyVisualizerLogicalTickStateAdapterMixin,
        _field,
        _make_delegated_property(_field),
    )


__all__ = [
    "LegacyVisualizerLogicalTickStateAdapterMixin",
    "LOCAL_LOGICAL_TICK_FIELDS",
]
