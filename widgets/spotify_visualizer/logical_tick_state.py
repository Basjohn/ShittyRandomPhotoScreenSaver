"""Controller-owned presentation-neutral visualizer logical tick state (H).

The authored per-tick logical computation historically ran against a large set
of live ``SpotifyVisualizerWidget`` fields. This object is the destination owner
for that per-tick logical state so ``VisualizerLogicalRuntime`` can advance
without a ``QWidget``/legacy presenter argument, per the H visualizer runtime
ownership correction.

Design:

- The presentation-neutral ``VisualizerRuntimeController`` owns exactly one of
  these per generation; it does **not** duplicate the BeatEngine, source, logical
  runtime, mailbox or render bridge - those stay singular on the controller.
- Fields the controller already owns (engine/playback/mode identity, mailbox,
  engine generation/activation fencing, thread/process/settings seams) are
  exposed here as delegating properties to the controller, so this object is a
  single complete logical host.
- The remaining authored per-tick logical fields (heartbeat, perf-tick,
  devcurve, bubble, mode-transition-readiness, source freshness, smoothing) live
  here as plain attributes, populated by the existing initialization/tick code.
- The five logical hooks the tick pipeline invokes are thin delegators to the
  existing presentation-neutral module functions, passing this host.

No QML/QQuickItem/QScreen/render-thread object ever enters this state. This is an
ownership migration; authored algorithms, timing and semantics are unchanged.
"""

from __future__ import annotations

from typing import Any


# The controller-owned fields the logical host exposes by delegation. Mirrors the
# legacy widget adapter so a state-owned host and a widget host are interchangeable.
_CONTROLLER_DELEGATED: tuple[str, ...] = (
    "_engine",
    "_spotify_playing",
    "_enabled",
    "_bar_count",
    "_settings_model",
    "_technical_config_cache",
    "_thread_manager",
    "_process_supervisor",
    "_logical_mailbox",
    "_logical_present_pending",
    "_committed_activation_identity",
    "_mode_activation_committed_for",
    "_pending_engine_generation",
    "_last_engine_generation_seen",
    "_pending_engine_activation_id",
    "_last_engine_activation_seen",
)


class VisualizerLogicalTickState:
    """Single presentation-neutral host for one generation's logical tick state."""

    def __init__(self, controller: Any) -> None:
        object.__setattr__(self, "_controller", controller)

    # ------------------------------------------------------------------ #
    # Controller-delegated identity/lifecycle fields                      #
    # ------------------------------------------------------------------ #
    @property
    def runtime_controller(self) -> Any:
        return self._controller

    @property
    def presentation_config_host(self) -> Any:
        """Where the legacy adapter reads pure renderer/presentation-only config.

        Authored logical inputs live on this state; renderer/presentation-only
        config is owned by the controller-owned ``VisualizerPresentationState``.
        The capture routes its presentation reads here so this logical host never
        needs to carry presentation styling.
        """

        return self._controller.presentation_state

    @property
    def _runtime_generation(self) -> int:
        return self._controller.runtime_generation

    @_runtime_generation.setter
    def _runtime_generation(self, value: int | None) -> None:
        self._controller.runtime_generation = value

    @property
    def _engine(self) -> Any:
        return self._controller.engine

    @_engine.setter
    def _engine(self, value: Any) -> None:
        self._controller.engine = value

    @property
    def _spotify_playing(self) -> bool:
        return self._controller.playing

    @_spotify_playing.setter
    def _spotify_playing(self, value: bool) -> None:
        self._controller.playing = value

    @property
    def _enabled(self) -> bool:
        return self._controller.enabled

    @_enabled.setter
    def _enabled(self, value: bool) -> None:
        self._controller.enabled = value

    @property
    def _bar_count(self) -> int:
        return self._controller.bar_count

    @_bar_count.setter
    def _bar_count(self, value: int) -> None:
        self._controller.bar_count = value

    @property
    def _vis_mode_str(self) -> str:
        # Derived read-only mode string, identical to the legacy widget's
        # ``_vis_mode.name.lower()`` (the controller mode id is that canonical
        # lowercase token).
        return str(self._controller.mode_id)

    @property
    def _settings_model(self) -> Any:
        return self._controller.settings_model

    @_settings_model.setter
    def _settings_model(self, value: Any) -> None:
        self._controller.settings_model = value

    @property
    def _technical_config_cache(self) -> dict[str, dict[str, Any]]:
        return self._controller.technical_config_cache

    @_technical_config_cache.setter
    def _technical_config_cache(self, value: dict[str, dict[str, Any]]) -> None:
        self._controller.technical_config_cache = value

    @property
    def _thread_manager(self) -> Any:
        return self._controller.thread_manager

    @_thread_manager.setter
    def _thread_manager(self, value: Any) -> None:
        self._controller.thread_manager = value

    @property
    def _process_supervisor(self) -> Any:
        return self._controller.process_supervisor

    @_process_supervisor.setter
    def _process_supervisor(self, value: Any) -> None:
        self._controller.process_supervisor = value

    @property
    def _logical_mailbox(self) -> Any:
        return self._controller.logical_mailbox

    @_logical_mailbox.setter
    def _logical_mailbox(self, value: Any) -> None:
        self._controller.replace_logical_mailbox(value)

    @property
    def _logical_present_pending(self) -> bool:
        return self._controller.logical_present_pending

    @_logical_present_pending.setter
    def _logical_present_pending(self, value: bool) -> None:
        self._controller.logical_present_pending = value

    @property
    def _committed_activation_identity(self) -> tuple | None:
        return self._controller.committed_activation_identity

    @_committed_activation_identity.setter
    def _committed_activation_identity(self, value: tuple | None) -> None:
        self._controller.committed_activation_identity = value

    @property
    def _mode_activation_committed_for(self) -> Any:
        return self._controller.mode_activation_committed_for

    @_mode_activation_committed_for.setter
    def _mode_activation_committed_for(self, value: Any) -> None:
        self._controller.mode_activation_committed_for = value

    @property
    def _pending_engine_generation(self) -> int:
        return self._controller.pending_engine_generation

    @_pending_engine_generation.setter
    def _pending_engine_generation(self, value: int) -> None:
        self._controller.pending_engine_generation = value

    @property
    def _last_engine_generation_seen(self) -> int:
        return self._controller.last_engine_generation_seen

    @_last_engine_generation_seen.setter
    def _last_engine_generation_seen(self, value: int) -> None:
        self._controller.last_engine_generation_seen = value

    @property
    def _pending_engine_activation_id(self) -> int:
        return self._controller.pending_engine_activation_id

    @_pending_engine_activation_id.setter
    def _pending_engine_activation_id(self, value: int) -> None:
        self._controller.pending_engine_activation_id = value

    @property
    def _last_engine_activation_seen(self) -> int:
        return self._controller.last_engine_activation_seen

    @_last_engine_activation_seen.setter
    def _last_engine_activation_seen(self, value: int) -> None:
        self._controller.last_engine_activation_seen = value

    # ------------------------------------------------------------------ #
    # Logical hooks: thin delegators to existing neutral module functions #
    # ------------------------------------------------------------------ #
    def _check_mode_teardown_ready(self, engine: Any, now_ts: float) -> bool:
        from widgets.spotify_visualizer.mode_transition import (
            evaluate_mode_teardown_ready,
        )

        return evaluate_mode_teardown_ready(self, engine, now_ts)

    def _on_first_frame_after_cold_start(self) -> None:
        from widgets.spotify_visualizer.mode_transition import (
            on_first_frame_after_cold_start,
        )

        on_first_frame_after_cold_start(self)

    def _log_tick_spike(self, dt: float, transition_ctx: dict[str, Any]) -> None:
        from widgets.spotify_visualizer.tick_helpers import log_tick_spike

        log_tick_spike(self, dt, transition_ctx)

    def _log_perf_snapshot(self, reset: bool = False) -> None:
        from widgets.spotify_visualizer.tick_helpers import log_perf_snapshot

        log_perf_snapshot(self, reset=reset)

    def _log_audio_latency_metrics(
        self,
        engine: Any,
        now_ts: float,
        force_reason: str | None = None,
    ) -> None:
        from widgets.spotify_visualizer.tick_pipeline import log_audio_latency_metrics

        log_audio_latency_metrics(self, engine, now_ts, force_reason=force_reason)


def install_default_logical_tick_state(state: Any, *, bar_count: int) -> None:
    """Initialize a fresh controller-owned logical state's authored runtime fields.

    These are the authored per-tick runtime defaults the legacy widget setup
    installs; extracting them here lets the Quick visualizer ownership edge
    construct a usable logical state with no ``SpotifyVisualizerWidget``. Values
    mirror the widget's post-construction defaults exactly (an ownership move, not
    a retune). Authored logical *configuration* (Bubble physics) is applied
    separately from canonical settings via ``apply_logical_vis_mode_kwargs``;
    mode-specific runtime fields (devcurve) install when that mode activates.
    """

    from widgets.spotify_visualizer.bubble_cadence import BubbleCadenceState

    # Authored Bubble physics config defaults (canonical settings override these
    # through apply_logical_vis_mode_kwargs; kept here so an omitted key never
    # leaves the authored simulation config unset).
    state._bubble_big_count = 8
    state._bubble_small_count = 25
    state._bubble_big_size_max = 0.038
    state._bubble_small_size_max = 0.018
    state._bubble_big_size_clamp = 4.0
    state._bubble_big_contraction_bias = 1.0
    state._bubble_big_specular_max_size = 2.5
    state._bubble_big_bass_pulse = 0.5
    state._bubble_small_freq_pulse = 0.5
    state._bubble_surface_reach = 0.6
    state._bubble_rotation_amount = 0.5
    state._bubble_drift_amount = 0.5
    state._bubble_drift_speed = 0.5
    state._bubble_drift_frequency = 0.5
    state._bubble_drift_direction = "random"
    state._bubble_stream_direction = "up"
    state._bubble_stream_constant_speed = 0.5
    state._bubble_stream_speed_cap = 2.0
    state._bubble_stream_reactivity = 0.5
    state._bubble_bounce_big_pct = 70
    state._bubble_bounce_small_pct = 30
    state._bubble_bounce_big_speed = 0.8
    state._bubble_bounce_small_speed = 0.5
    state._bubble_bounce_same_only = False
    state._bubble_trail_strength = 0.0
    state._sine_heartbeat = 0.0

    # Authored per-mode logical config defaults (canonical settings override
    # these through apply_logical_vis_mode_kwargs). Mirrors the widget's
    # post-construction defaults exactly - an ownership move, not a retune.
    # DevCurve per-layer colour/shape inputs are omitted here: the DevCurve
    # parameter snapshot supplies their canonical defaults on read.
    state._spectrum_single_piece = False
    state._spectrum_visual_smoothing_enabled = True
    state._spectrum_visual_smoothing = 0.5
    state._spectrum_ghosting_enabled = True
    state._spectrum_ghost_decay = 0.4
    state._osc_speed = 1.0
    state._osc_line_amplitude = 3.0
    state._osc_ghosting_enabled = False
    state._osc_ghost_intensity = 0.4
    state._osc_ghost_decay = 0.4
    state._sine_speed = 1.0
    state._sine_line_count = 1
    state._sine_wave_travel = 0
    state._sine_travel_line2 = 0
    state._sine_travel_line3 = 0
    state._sine_travel_line4 = 0
    state._sine_travel_line5 = 0
    state._sine_travel_line6 = 0
    state._sine_line1_shift = 0.0
    state._sine_line2_shift = 0.0
    state._sine_line3_shift = 0.0
    state._sine_line4_shift = 0.0
    state._sine_line5_shift = 0.0
    state._sine_line6_shift = 0.0
    state._sine_width_reaction = 0.0
    state._sine_sensitivity = 1.0
    state._sine_ghosting_enabled = True
    state._sine_ghost_alpha = 0.45
    state._sine_ghost_decay = 0.3
    state._devcurve_active_layer = "bass"
    state._devcurve_base_level = 0.58
    state._devcurve_motion_power = 1.0
    state._devcurve_idle_motion = 0.20
    state._devcurve_idle_speed = 0.60
    state._devcurve_smoothness = 0.55
    state._devcurve_ghosting_enabled = False
    state._devcurve_ghost_alpha = 0.0
    state._devcurve_ghost_decay = 0.4
    state._devcurve_foreground_shadow_enabled = False
    state._devcurve_foreground_shadow_alpha = 0.36
    state._devcurve_foreground_shadow_darken = 0.42
    state._devcurve_foreground_shadow_offset = 0.10
    state._devcurve_foreground_specular_enabled = False
    state._devcurve_foreground_specular_alpha = 0.78
    state._devcurve_foreground_specular_width = 0.022
    state._devcurve_foreground_specular_offset = 0.028
    state._devcurve_foreground_specular_crest_bias = 1.05

    # Heartbeat / pulse tracking.
    state._heartbeat_intensity = 0.0
    state._heartbeat_avg_bass = 0.0
    state._heartbeat_fast_bass = 0.0
    state._heartbeat_fast_prev = 0.0
    state._heartbeat_last_ts = 0.0
    state._heartbeat_last_trigger_ts = 0.0
    state._heartbeat_last_log_ts = 0.0

    # Authored cadence + smoothing.
    state._smoothing = 0.18
    state._bubble_cadence_state = BubbleCadenceState()
    state._dt_spike_threshold_ms = 42.0
    state._last_update_ts = -1.0

    # Tick dt-spike diagnostic (read by the delegated tick path via
    # tick_helpers.log_tick_spike). Mirrors the legacy widget's post-construction
    # defaults exactly - an ownership move, not a retune. Without these the first
    # authored spike raised AttributeError on _last_tick_spike_log_ts.
    state._dt_spike_log_cooldown = 0.75
    state._last_tick_spike_log_ts = 0.0

    # Bubble runtime state (the simulation owns its own interior state).
    state._bubble_count = 0
    state._bubble_pos_data = []
    state._bubble_trail_data = []
    state._bubble_extra_data = []
    state._bubble_last_perf_diag = {}
    state._bubble_last_tick_ts = 0.0
    state._bubble_dispatch_energy_snapshot = {}
    state._bubble_dispatch_pulse_params = {}
    state._bubble_dispatch_settings = {}
    state._bubble_visible_render_state_ts = 0.0
    state._bubble_visible_simulation_ts = 0.0
    state._bubble_visible_source_ts = 0.0

    # Display bars mirror + source identity.
    state._display_bars = [0.0] * max(1, int(bar_count))
    state._display_bars_source_generation = -1
    state._display_bars_source_activation = -1

    # Source freshness / mode-teardown readiness.
    state._waiting_for_fresh_frame = False
    state._waiting_for_fresh_engine_frame = False
    state._has_pushed_first_frame = False
    state._fallback_logged = False
    state._mode_teardown_block_until_ready = False
    state._mode_teardown_state = "idle"
    state._mode_teardown_target_generation = -1
    state._mode_transition_phase = 0
    state._mode_transition_ready = False

    # Perf tick + paint diagnostics.
    state._perf_tick_frame_count = 0
    state._perf_tick_last_ts = None
    state._perf_tick_start_ts = None
    state._perf_tick_min_dt = 0.0
    state._perf_tick_max_dt = 0.0
    state._perf_last_log_ts = None
    state._perf_paint_frame_count = 0
    state._perf_paint_last_ts = None
    state._perf_paint_start_ts = None
    state._perf_paint_min_dt = 0.0
    state._perf_paint_max_dt = 0.0
    state._perf_audio_lag_last_ms = 0.0
    state._perf_audio_lag_min_ms = 0.0
    state._perf_audio_lag_max_ms = 0.0

    # Latency diagnostics.
    state._latency_pending_probe = []
    state._latency_last_signature = None
    state._latency_last_log_ts = 0.0
    state._latency_audio_ready = False
    state._latency_authority = None
    state._latency_log_interval = 10.0
    state._latency_warn_ms = 80.0
    state._latency_error_ms = 150.0


__all__ = [
    "VisualizerLogicalTickState",
    "_CONTROLLER_DELEGATED",
    "install_default_logical_tick_state",
]
