from __future__ import annotations

from typing import List, Optional, Dict, Any, Callable
import time
import copy

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import (
    get_logger,
    is_verbose_logging,
    is_perf_metrics_enabled,
)
from core.threading.manager import ThreadManager
from core.process import ProcessSupervisor
from core.settings.models import SpotifyVisualizerSettings, PER_MODE_TECHNICAL_MODES
from widgets.shadow_utils import configure_overlay_widget_attributes
from widgets.base_overlay_widget import BaseOverlayWidget


from utils.profiler import profile


# Re-export package symbols for backward compatibility with external importers
from widgets.spotify_visualizer.audio_worker import (
    SpotifyVisualizerAudioWorker,  # noqa: F401 – re-export
    VisualizerMode,
    _AudioFrame,  # noqa: F401 – re-export
)
from widgets.spotify_visualizer.beat_engine import (
    get_shared_spotify_beat_engine,
    _SpotifyBeatEngine,
)

logger = get_logger(__name__)



class SpotifyVisualizerWidget(QWidget):
    """Thin bar visualizer card paired with the Spotify media widget.

    The widget draws a rounded-rect card that inherits Spotify/Media
    styling from DisplayWidget and renders a row of vertical bars whose
    heights are driven by audio magnitudes published by
    SpotifyVisualizerAudioWorker.
    """

    def __init__(self, parent: Optional[QWidget] = None, bar_count: int = 32) -> None:
        super().__init__(parent)

        self._bar_count = max(1, int(bar_count))
        self._display_bars: List[float] = [0.0] * self._bar_count
        self._target_bars: List[float] = [0.0] * self._bar_count
        self._per_bar_energy: List[float] = [0.0] * self._bar_count
        self._visual_bars: List[float] = [0.0] * self._bar_count
        self._visual_smoothing_tau: float = 0.055
        self._cached_vis_kwargs: Dict[str, Any] = {}

        self._last_visual_smooth_ts: float = 0.0
        # Base smoothing time constant in seconds; actual per-tick blend
        # factor is derived from this and the real dt between ticks so that
        # behaviour stays consistent even if tick rate changes. Slightly
        # reduced from earlier values to make bar attacks feel less "late"
        # without removing the pleasant decay tail.
        self._smoothing: float = 0.18

        self._thread_manager: Optional[ThreadManager] = None
        self._bars_timer = None
        self._shadow_config = None
        self._show_background: bool = True
        self._animation_manager = None
        self._anim_listener_id: Optional[int] = None

        # Card style (mirrors Spotify/Media widget)
        self._bg_color = QColor(16, 16, 16, 255)
        self._bg_opacity: float = 0.7
        self._card_border_color = QColor(255, 255, 255, 230)
        self._border_width: int = BaseOverlayWidget.get_global_border_width()

        # Bar styling
        self._bar_fill_color = QColor(200, 200, 200, 230)
        self._bar_border_color = QColor(255, 255, 255, 255)
        self._bar_segments_base: int = 18
        self._ghosting_enabled: bool = True
        self._ghost_alpha: float = 0.4
        self._ghost_decay_rate: float = 0.4
        self._blob_ghosting_enabled: bool = False
        self._blob_ghost_alpha: float = 0.4
        self._blob_ghost_decay: float = 0.3
        self._spectrum_single_piece: bool = False
        self._spectrum_bar_profile: str = 'legacy'
        self._spectrum_border_radius: float = 0.0

        # Visualization mode (Spectrum, Waveform, Abstract)
        self._vis_mode: VisualizerMode = VisualizerMode.SPECTRUM

        # Oscilloscope settings
        self._osc_glow_enabled: bool = True
        self._osc_glow_intensity: float = 0.5
        self._osc_glow_color: QColor = QColor(0, 200, 255, 230)
        self._osc_line_color: QColor = QColor(255, 255, 255, 255)
        self._osc_reactive_glow: bool = True
        self._osc_sensitivity: float = 3.0
        self._osc_smoothing: float = 0.7
        self._osc_line_count: int = 1
        self._osc_line2_color: QColor = QColor(255, 120, 50, 230)
        self._osc_line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._osc_line3_color: QColor = QColor(50, 255, 120, 230)
        self._osc_line3_glow_color: QColor = QColor(50, 255, 120, 180)

        # Starfield settings
        self._star_density: float = 1.0
        self._star_travel_speed: float = 0.5
        self._star_reactivity: float = 1.0
        self._nebula_tint1: QColor = QColor(20, 40, 120)
        self._nebula_tint2: QColor = QColor(80, 20, 100)
        self._nebula_cycle_speed: float = 0.3

        # Blob settings
        self._blob_color: QColor = QColor(0, 180, 255, 230)
        self._blob_glow_color: QColor = QColor(0, 140, 255, 180)
        self._blob_edge_color: QColor = QColor(100, 220, 255, 230)
        self._blob_outline_color: QColor = QColor(0, 0, 0, 0)
        self._blob_pulse: float = 1.0
        self._blob_width: float = 1.0
        self._blob_size: float = 1.0
        self._blob_glow_intensity: float = 0.5
        self._blob_glow_reactivity: float = 1.0
        self._blob_glow_max_size: float = 1.0
        self._blob_reactive_glow: bool = True
        self._blob_reactive_deformation: float = 1.0
        self._blob_stage_gain: float = 1.0
        self._blob_core_scale: float = 1.0
        self._blob_core_floor_bias: float = 0.35
        self._blob_stage_bias: float = 0.0
        self._blob_stage2_release_ms: float = 900.0
        self._blob_stage3_release_ms: float = 1200.0
        self._blob_constant_wobble: float = 1.0
        self._blob_reactive_wobble: float = 1.0
        self._blob_stretch_tendency: float = 0.35
        self._blob_stretch_inner: float = 0.5  # 0..1 how deep inward dents go
        self._blob_stretch_outer: float = 0.5  # 0..1 how far outward protrusions go

        # Helix settings
        self._helix_turns: int = 4
        self._helix_double: bool = True
        self._helix_speed: float = 1.0

        # Helix glow settings
        self._helix_glow_enabled: bool = True
        self._helix_glow_intensity: float = 0.5
        self._helix_glow_color: QColor = QColor(0, 200, 255, 180)
        self._helix_reactive_glow: bool = True

        # Card height expansion (per-mode growth factors, user-customizable)
        self._base_height: int = 80
        self._spectrum_growth: float = 2.0
        self._starfield_growth: float = 3.0
        self._blob_growth: float = 3.5
        self._helix_growth: float = 3.0
        self._osc_growth: float = 2.0
        self._bubble_growth: float = 3.0
        self._osc_speed: float = 1.0
        self._osc_line_dim: bool = False
        self._osc_line_offset_bias: float = 0.0
        self._osc_vertical_shift: int = 0
        self._sine_wave_growth: float = 2.0
        self._sine_wave_travel: int = 0  # 0=none, 1=left, 2=right
        self._sine_travel_line2: int = 0  # per-line travel for line 2
        self._sine_travel_line3: int = 0  # per-line travel for line 3
        self._sine_card_adaptation: float = 0.3  # 0.05-1.0, how much of card height waves use
        self._sine_wave_effect: float = 0.0  # 0.0-1.0, wave-like positional effect
        self._sine_micro_wobble: float = 0.0  # 0.0-1.0, energy-reactive micro distortions (legacy)
        self._sine_crawl_amount: float = 0.25  # 0.0-1.0, Crawl slider amount
        self._sine_vertical_shift: int = 0  # -50 to 200, line spread amount
        self._sine_width_reaction: float = 0.0  # 0.0-1.0, bass-driven line width stretching
        self._sine_density: float = 1.0
        self._sine_displacement: float = 0.0
        self._sine_glow_enabled: bool = True
        self._sine_glow_intensity: float = 0.5
        self._sine_glow_color: QColor = QColor(0, 200, 255, 230)
        self._sine_line_color: QColor = QColor(255, 255, 255, 255)
        self._sine_line2_color: QColor = QColor(255, 120, 50, 230)
        self._sine_line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._sine_line3_color: QColor = QColor(50, 255, 120, 230)
        self._sine_line3_glow_color: QColor = QColor(50, 255, 120, 180)
        self._sine_reactive_glow: bool = True
        self._sine_sensitivity: float = 1.0
        self._sine_speed: float = 1.0
        self._sine_line_count: int = 1
        self._sine_line_offset_bias: float = 0.0
        self._sine_line_dim: bool = False
        self._sine_line1_shift: float = 0.0
        self._sine_line2_shift: float = 0.0
        self._sine_line3_shift: float = 0.0

        # Rainbow (Taste The Rainbow) mode — global, applies to all visualizers
        self._rainbow_enabled: bool = False
        self._rainbow_speed: float = 0.5
        self._rainbow_per_bar: bool = False

        # Oscilloscope ghost trail
        self._osc_ghosting_enabled: bool = False
        self._osc_ghost_intensity: float = 0.4

        # Sine Wave Heartbeat
        self._sine_heartbeat: float = 0.0
        self._heartbeat_intensity: float = 0.0  # CPU-side decay envelope
        self._heartbeat_avg_bass: float = 0.0   # rolling average for transient detection
        self._heartbeat_fast_bass: float = 0.0  # short window peak tracker
        self._heartbeat_floor_bass: float = 0.0 # very slow baseline to re-prime transients
        self._heartbeat_fast_prev: float = 0.0  # last-frame fast value for slope checks
        self._heartbeat_last_ts: float = 0.0    # dedicated tick timestamp for dt_hb
        self._heartbeat_last_log_ts: float = 0.0
        self._heartbeat_last_trigger_ts: float = 0.0
        self._crawl_last_log_ts: float = 0.0

        # Audio latency instrumentation (viz debug)
        self._latency_last_log_ts: float = 0.0
        self._latency_log_interval: float = 10.0
        self._latency_warn_ms: float = 80.0
        self._latency_error_ms: float = 150.0
        self._latency_pending_probe: List[str] = []
        self._latency_last_signature: Optional[
            tuple[str, float, str, int, Optional[str], Optional[str]]
        ] = None
        self._last_transition_running: bool = False

        # Bubble visualizer
        self._bubble_big_bass_pulse: float = 0.5
        self._bubble_small_freq_pulse: float = 0.5
        self._bubble_stream_direction: str = "up"
        self._bubble_stream_constant_speed: float = 0.5
        self._bubble_stream_speed_cap: float = 2.0
        self._bubble_stream_reactivity: float = 0.5
        self._bubble_rotation_amount: float = 0.5
        self._bubble_drift_amount: float = 0.5
        self._bubble_drift_speed: float = 0.5
        self._bubble_drift_frequency: float = 0.5
        self._bubble_drift_direction: str = "random"
        self._bubble_big_count: int = 8
        self._bubble_small_count: int = 25
        self._bubble_surface_reach: float = 0.6
        self._bubble_outline_color: QColor = QColor(255, 255, 255, 230)
        self._bubble_specular_color: QColor = QColor(255, 255, 255, 255)
        self._bubble_gradient_light: QColor = QColor(210, 170, 120, 255)
        self._bubble_gradient_dark: QColor = QColor(80, 60, 50, 255)
        self._bubble_pop_color: QColor = QColor(255, 255, 255, 180)
        self._bubble_specular_direction: str = "top_left"
        self._bubble_gradient_direction: str = "top"
        self._bubble_big_size_max: float = 0.038
        self._bubble_small_size_max: float = 0.018
        self._bubble_simulation: Optional[object] = None  # lazy init (owned by compute thread)
        self._bubble_pos_data: list = []
        self._bubble_extra_data: list = []
        self._bubble_trail_data: list = []
        self._bubble_trail_strength: float = 0.0
        self._bubble_tail_opacity: float = 0.0
        self._bubble_count: int = 0
        self._bubble_compute_pending: bool = False  # coalescing flag
        self._bubble_last_tick_ts: float = 0.0

        # Behavioural gating
        self._spotify_playing: bool = False
        self._anchor_media: Optional[QWidget] = None
        self._has_seen_media: bool = False
        # Legacy Spotify gating state (still tracked for telemetry/UI toggles)
        self._last_media_state_ts: float = 0.0
        self._media_state_logged: bool = False

        # Shared beat engine (single audio worker per process). We keep
        # aliases for _audio_worker/_bars_buffer/_bars_result_buffer so
        # existing tests and diagnostics continue to function, but all
        # heavy work is centralised in the engine.
        self._engine: Optional[_SpotifyBeatEngine] = get_shared_spotify_beat_engine(self._bar_count)
        self._last_floor_config = (True, 2.1)
        self._last_sensitivity_config = (True, 1.0)
        self._last_energy_boost: float = 0.85
        self._last_audio_block_size: int = 0
        self._settings_model: Optional[SpotifyVisualizerSettings] = None
        self._technical_config_cache: Dict[str, Dict[str, Any]] = {}
        self._process_supervisor: Optional[ProcessSupervisor] = None
        try:
            engine = self._engine
            if engine is not None:
                # Canonical bar_count is driven by the shared engine.
                try:
                    engine_bar_count = int(getattr(engine, "_bar_count", self._bar_count))
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    engine_bar_count = self._bar_count
                if engine_bar_count > 0 and engine_bar_count != self._bar_count:
                    self._bar_count = engine_bar_count
                    self._display_bars = [0.0] * self._bar_count
                    self._target_bars = [0.0] * self._bar_count
                    self._per_bar_energy = [0.0] * self._bar_count
                    self._visual_bars = [0.0] * self._bar_count
                self._bind_engine_aliases(engine)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach shared beat engine", exc_info=True)

        self._enabled: bool = False
        self._paint_debug_logged: bool = False

        # Lightweight PERF profiling state for widget activity so we can
        # correlate Spotify playing state with Transition/FPS behaviour.
        self._perf_tick_start_ts: Optional[float] = None
        self._perf_tick_last_ts: Optional[float] = None
        self._perf_tick_frame_count: int = 0
        self._perf_tick_min_dt: float = 0.0
        self._perf_tick_max_dt: float = 0.0

        self._perf_paint_start_ts: Optional[float] = None
        self._perf_paint_last_ts: Optional[float] = None
        self._perf_paint_frame_count: int = 0
        self._perf_paint_min_dt: float = 0.0
        self._perf_paint_max_dt: float = 0.0

        # Lightweight view of capture→bars latency derived from the shared
        # beat engine's last-audio timestamp. Logged alongside Tick/Paint
        # metrics but kept in a separate line so existing schemas remain
        # stable for tools.
        self._perf_audio_lag_last_ms: float = 0.0
        self._perf_audio_lag_min_ms: float = 0.0
        self._perf_audio_lag_max_ms: float = 0.0
        self._fallback_mismatch_start: float = 0.0
        self._fallback_forced_until: float = 0.0

        # Last time we emitted a PERF snapshot while running. This allows us
        # to log Spotify visualiser activity periodically even if the widget
        # is never explicitly stopped/cleaned up (for example, if the
        # screensaver exits abruptly), so logs still capture its effective
        # update/paint rate alongside compositor and animation metrics.
        self._perf_last_log_ts: Optional[float] = None
        self._dt_spike_threshold_ms: float = 42.0
        self._dt_spike_log_cooldown: float = 0.75
        self._last_tick_spike_log_ts: float = 0.0

        # Geometry cache for paintEvent to avoid per-frame recomputation of
        # bar/segment layout. Rebuilt on resize or when bar_count/segments
        # change.
        self._geom_cache_rect: Optional[QRect] = None
        self._geom_cache_bar_count: int = self._bar_count
        self._geom_cache_segments: int = self._bar_segments_base
        self._geom_bar_x: List[int] = []
        self._geom_seg_y: List[int] = []
        self._geom_bar_width: int = 0
        self._geom_seg_height: int = 0

        # Last time a visual update (GPU frame push or QWidget repaint)
        # was issued. Initialised to a negative sentinel so the first
        # tick always triggers an update and subsequent ticks are
        # throttled purely by the configured FPS caps.
        self._last_update_ts: float = -1.0
        self._last_smooth_ts: float = 0.0
        self._has_pushed_first_frame: bool = False
        # Base paint FPS caps for the visualiser; slightly higher than
        # before now that compositor/GL transitions are cheaper, while
        # still low enough that the visualiser cannot dominate the UI
        # event loop.
        self._base_max_fps: float = 90.0
        self._transition_max_fps: float = 60.0
        self._transition_hot_start_fps: float = 50.0
        self._transition_spinup_window: float = 2.0
        self._idle_fps_boost_delay: float = 5.0
        self._idle_max_fps: float = 100.0
        self._current_timer_interval_ms: int = 16
        self._last_gpu_fade_sent: float = -1.0
        self._last_gpu_geom: Optional[QRect] = None

        # Mode transition driven by double-click (no timers, tick-driven)
        self._mode_transition_ts: float = 0.0   # 0 = no transition active
        self._mode_transition_phase: int = 0     # 0=idle, 1=fading out, 3=waiting, 2=fading in
        self._mode_transition_duration: float = 0.25  # seconds per half (out/in)
        self._mode_transition_pending: Optional[VisualizerMode] = None
        # When non-zero, indicates a transition resume timestamp captured just
        # before the visualizer state is cold-reset mid-cycle (double-click).
        self._mode_transition_resume_ts: float = 0.0
        self._mode_transition_apply_height_on_resume: bool = False
        self._pending_shadow_cache_invalidation: bool = False
        self._reset_teardown_bookkeeping()

        # When GPU overlay rendering is available, we disable the
        # widget's own bar drawing and instead push frames up to the
        # DisplayWidget, which owns a small QOpenGLWidget overlay.
        self._cpu_bars_enabled: bool = True
        # User-configurable switch controlling whether the legacy software
        # visualiser is allowed to draw bars when GPU rendering is
        # unavailable or disabled. Defaults to False so the GPU overlay
        # remains the primary path in OpenGL mode.
        self._software_visualizer_enabled: bool = False

        # Tick source coordination
        self._using_animation_ticks: bool = False

        self._setup_ui()

    def _replay_engine_config(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        """Ensure the shared engine reflects the last applied widget config."""
        if engine is None:
            return
        try:
            floor_dyn, floor_value = self._last_floor_config
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            floor_dyn, floor_value = True, 2.1
        try:
            sens_rec, sens_value = self._last_sensitivity_config
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            sens_rec, sens_value = True, 1.0

        try:
            engine.set_floor_config(floor_dyn, floor_value)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay floor config", exc_info=True)
        try:
            engine.set_sensitivity_config(sens_rec, sens_value)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay sensitivity config", exc_info=True)
        try:
            engine.set_curved_profile(self._spectrum_bar_profile != 'legacy')
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay curved profile config", exc_info=True)
        try:
            engine.set_energy_boost(self._last_energy_boost)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay energy boost config", exc_info=True)

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        self._thread_manager = thread_manager
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            engine.set_thread_manager(thread_manager)
            self._replay_engine_config(engine)
            self._bind_engine_aliases(engine)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate ThreadManager to shared beat engine", exc_info=True)

    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for worker integration."""
        self._process_supervisor = supervisor
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
            if engine is not None:
                engine.set_process_supervisor(supervisor)
                logger.debug("[SPOTIFY_VIS] ProcessSupervisor set on beat engine")
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set ProcessSupervisor on beat engine", exc_info=True)
        if self._enabled:
            self._ensure_tick_source()

    def apply_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        """Public hook for tests/UI to set floor config on the widget."""
        self._last_floor_config = (bool(dynamic_enabled), float(manual_floor))
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.set_floor_config(dynamic_enabled, manual_floor)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to push floor config via apply_floor_config", exc_info=True)

    # Backwards-compat alias for legacy callers/tests
    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        self.apply_floor_config(dynamic_enabled, manual_floor)

    def apply_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        """Public hook for tests/UI to set sensitivity config on the widget."""
        self._last_sensitivity_config = (bool(recommended), float(sensitivity))
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.set_sensitivity_config(recommended, sensitivity)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to push sensitivity config via apply_sensitivity_config", exc_info=True)

    def _apply_energy_boost(self, boost: float) -> None:
        try:
            value = float(boost)
        except Exception as exc:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
            value = 1.0
        if abs(value - self._last_energy_boost) <= 1e-4:
            return
        self._last_energy_boost = value
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as exc:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
            engine = None
        if engine is None:
            return
        try:
            engine.set_energy_boost(value)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to push energy boost config", exc_info=True)

    @staticmethod
    def _compute_energy_boost(enabled: bool) -> float:
        """Map dynamic range flag to a safe energy boost multiplier."""
        return 1.18 if enabled else 0.85

    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        self.apply_sensitivity_config(recommended, sensitivity)

    def apply_vis_mode_config(self, mode: str, **kwargs) -> None:
        """Apply visualization mode and per-mode settings.

        Called when the settings dialog saves a new visualizer type or
        per-mode parameter.  Delegates keyword→attribute mapping to
        :mod:`widgets.spotify_visualizer.config_applier`.
        """
        mode_map = {
            'spectrum': VisualizerMode.SPECTRUM,
            'oscilloscope': VisualizerMode.OSCILLOSCOPE,
            'starfield': VisualizerMode.STARFIELD,
            'blob': VisualizerMode.BLOB,
            'helix': VisualizerMode.HELIX,
            'sine_wave': VisualizerMode.SINE_WAVE,
            'bubble': VisualizerMode.BUBBLE,
        }
        vm = mode_map.get(str(mode).lower(), VisualizerMode.SPECTRUM)
        self.set_visualization_mode(vm)

        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        apply_vis_mode_kwargs(self, kwargs)

        try:
            self._cached_vis_kwargs = copy.deepcopy(kwargs)
        except Exception:
            self._cached_vis_kwargs = dict(kwargs)

        self._reset_visualizer_state(clear_overlay=False, replay_cached=False)
        self._mode_transition_apply_height_on_resume = True

        if self._mode_transition_phase == 0:
            self._apply_pending_mode_transition_layout()

        logger.debug("[SPOTIFY_VIS] Applied vis mode config: mode=%s", mode)

    @property
    def _vis_mode_str(self) -> str:
        return self._vis_mode.name.lower()

    def set_settings_model(self, model: SpotifyVisualizerSettings) -> None:
        if model is None:
            return
        try:
            snapshot = copy.deepcopy(model)
        except Exception:
            snapshot = model
        self._settings_model = snapshot
        self._technical_config_cache = self._build_technical_cache(snapshot)
        self._apply_technical_config_for_mode(self._vis_mode, reason="settings_model_update")

    def _build_technical_cache(self, model: SpotifyVisualizerSettings) -> Dict[str, Dict[str, Any]]:
        cache: Dict[str, Dict[str, Any]] = {}
        for mode_key in PER_MODE_TECHNICAL_MODES:
            try:
                cache[mode_key] = {
                    "bar_count": model.resolve_bar_count(mode_key),
                    "dynamic_floor": model.resolve_dynamic_floor(mode_key),
                    "manual_floor": model.resolve_manual_floor(mode_key),
                    "adaptive_sensitivity": model.resolve_adaptive_sensitivity(mode_key),
                    "sensitivity": model.resolve_sensitivity(mode_key),
                    "audio_block_size": model.resolve_audio_block_size(mode_key),
                    "dynamic_range_enabled": model.resolve_dynamic_range_enabled(mode_key),
                }
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to cache technical config for mode=%s", mode_key, exc_info=True)
        return cache

    def _get_mode_technical_config(self, mode: VisualizerMode) -> Optional[Dict[str, Any]]:
        if not self._technical_config_cache:
            return None
        mode_key = mode.name.lower()
        config = self._technical_config_cache.get(mode_key)
        if config is None:
            # Fallback to the first cached entry
            try:
                config = next(iter(self._technical_config_cache.values()))
            except StopIteration:
                return None
        return config

    def _apply_technical_config_for_mode(self, mode: VisualizerMode, *, reason: str) -> None:
        config = self._get_mode_technical_config(mode)
        if config is None:
            return
        try:
            target_bars = int(config.get("bar_count", self._bar_count))
        except Exception:
            target_bars = self._bar_count
        if target_bars != self._bar_count:
            self._resize_bar_buffers(target_bars)

        dynamic_floor = bool(config.get("dynamic_floor", True))
        manual_floor = float(config.get("manual_floor", 2.1))
        adaptive = bool(config.get("adaptive_sensitivity", True))
        sensitivity = float(config.get("sensitivity", 1.0))
        audio_block_size = int(config.get("audio_block_size", 0) or 0)
        dynamic_range_enabled = bool(config.get("dynamic_range_enabled", False))
        energy_boost = self._compute_energy_boost(dynamic_range_enabled)

        self.apply_floor_config(dynamic_floor, manual_floor)
        self.apply_sensitivity_config(adaptive, sensitivity)
        self._apply_audio_block_size(audio_block_size)
        self._apply_energy_boost(energy_boost)

        try:
            from os import getenv

            if getenv('SRPSS_VIZ_DIAGNOSTICS', 'false').lower() == 'true':
                logger.info(
                    "[SPOTIFY_VIS][TECHNICAL] mode=%s reason=%s bar_count=%d dyn_floor=%s manual_floor=%.2f adaptive=%s sensitivity=%.2f block=%d dyn_range=%s energy_boost=%.2f",
                    mode.name,
                    reason,
                    self._bar_count,
                    dynamic_floor,
                    manual_floor,
                    adaptive,
                    sensitivity,
                    audio_block_size,
                    dynamic_range_enabled,
                    energy_boost,
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to log technical config", exc_info=True)

    def _apply_audio_block_size(self, block_size: int) -> None:
        try:
            value = max(0, int(block_size))
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            value = 0
        if value == self._last_audio_block_size:
            return
        self._last_audio_block_size = value
        engine = self._engine
        if engine is None:
            try:
                engine = get_shared_spotify_beat_engine(self._bar_count)
                self._engine = engine
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to resolve beat engine for block size", exc_info=True)
                engine = None
        worker = getattr(engine, "_audio_worker", None) if engine is not None else None
        if worker is None or not hasattr(worker, "set_audio_block_size"):
            return
        try:
            worker.set_audio_block_size(value)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to push audio block size", exc_info=True)

    def _resize_bar_buffers(self, new_bar_count: int) -> None:
        new_count = max(1, int(new_bar_count))
        if new_count == self._bar_count:
            return
        was_enabled = self._enabled
        old_engine = self._engine
        if was_enabled and old_engine is not None:
            try:
                old_engine.release()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to release old beat engine during resize", exc_info=True)
        self._engine = None
        self._bar_count = new_count
        self._display_bars = [0.0] * new_count
        self._target_bars = [0.0] * new_count
        self._per_bar_energy = [0.0] * new_count
        self._visual_bars = [0.0] * new_count
        self._geom_cache_rect = None
        self._geom_cache_bar_count = new_count
        self._geom_bar_x = []
        self._geom_seg_y = []
        self._geom_bar_width = 0
        self._geom_seg_height = 0
        self._last_gpu_geom = None
        self._last_gpu_fade_sent = -1.0
        self._has_pushed_first_frame = False
        self._waiting_for_fresh_engine_frame = True
        self._waiting_for_fresh_frame = True
        try:
            engine = get_shared_spotify_beat_engine(new_count)
            self._engine = engine
            if self._thread_manager is not None:
                engine.set_thread_manager(self._thread_manager)
            if self._process_supervisor is not None:
                engine.set_process_supervisor(self._process_supervisor)
            self._bind_engine_aliases(engine)
            if was_enabled:
                engine.acquire()
                self._replay_engine_config(engine)
                engine.ensure_started()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to resize beat engine", exc_info=True)

    def _bind_engine_aliases(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        if engine is None:
            return
        try:
            self._bars_buffer = engine._audio_buffer  # type: ignore[attr-defined]
            self._audio_worker = engine._audio_worker  # type: ignore[attr-defined]
            self._bars_result_buffer = engine._bars_result_buffer  # type: ignore[attr-defined]
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to bind beat engine aliases", exc_info=True)

    def get_preferred_height(self) -> int:
        """Return the ideal card height for the current visualizer mode."""
        from widgets.spotify_visualizer.card_height import preferred_height
        mode = self._vis_mode_str
        growth = {
            'spectrum': self._spectrum_growth,
            'oscilloscope': self._osc_growth,
            'starfield': self._starfield_growth,
            'blob': self._blob_growth,
            'helix': self._helix_growth,
            'sine_wave': self._sine_wave_growth,
            'bubble': self._bubble_growth,
        }.get(mode)
        return preferred_height(mode, self._base_height, growth)

    def _request_reposition(self) -> None:
        """Ask the WidgetManager to reposition this widget for the new mode.

        This ensures the card height and position are correct after a mode
        switch (e.g. from Spectrum's 80px strip to Blob's taller card).
        """
        wm = getattr(self, '_widget_manager', None)
        if wm is None:
            return
        try:
            parent = self.parent()
            if parent is None:
                return
            pw, ph = parent.width(), parent.height()
            # Find the media widget sibling for relative positioning
            media = wm._widgets.get('media')
            if media is not None:
                wm.position_spotify_visualizer(self, media, pw, ph)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Reposition after mode switch failed", exc_info=True)

    def _apply_preferred_height(self) -> None:
        """Resize the widget to match the preferred height for the current mode.

        For spectrum/oscilloscope (growth=1.0), we explicitly shrink the
        widget back to base_height so the positioning system doesn't keep
        a stale tall height from an expanded mode (blob/helix/starfield).
        For expanded modes we set a minimum height from the growth factor.
        """
        mode = self._vis_mode_str
        growth = {
            'spectrum': self._spectrum_growth,
            'oscilloscope': self._osc_growth,
            'sine_wave': self._sine_wave_growth,
        }.get(mode)
        if growth is not None and growth <= 1.0:
            base = self._base_height
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            current = self.height()
            if current > base:
                self.resize(self.width(), base)
                logger.debug("[SPOTIFY_VIS] Card height shrunk: %d -> %d (mode=%s)", current, base, mode)
            return
        h = self.get_preferred_height()
        current = self.height()
        if current != h:
            self.setMinimumHeight(h)
            self.setMaximumHeight(16777215)  # allow positioning system to grow
            self.resize(self.width(), h)
            logger.debug("[SPOTIFY_VIS] Card height set: %d -> %d (mode=%s)", current, h, mode)

    def set_software_visualizer_enabled(self, enabled: bool) -> None:
        """Enable or disable the QWidget-based software visualiser path.

        When ``enabled`` is True, the widget is allowed to render bars via
        its own ``paintEvent`` when GPU rendering is unavailable (for
        example in software renderer mode). When False, the widget only
        exposes smoothed bar data to the GPU overlay and does not draw
        bars itself unless explicitly re-enabled.
        """

        try:
            self._software_visualizer_enabled = bool(enabled)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._software_visualizer_enabled = bool(enabled)

    def attach_to_animation_manager(self, animation_manager) -> None:
        # Detach from any previous manager first to avoid stacking listeners.
        if self._animation_manager is not None and self._anim_listener_id is not None:
            try:
                if hasattr(self._animation_manager, "remove_tick_listener"):
                    self._animation_manager.remove_tick_listener(self._anim_listener_id)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to remove previous AnimationManager listener", exc_info=True)

        self._animation_manager = animation_manager
        self._anim_listener_id = None

        # NOTE: We keep the dedicated _bars_timer running even when attached to
        # AnimationManager. The AnimationManager only ticks during active transitions,
        # so the dedicated timer ensures continuous visualizer updates between transitions.
        # The _on_tick method's FPS cap via _last_update_ts handles deduplication of
        # the actual GPU push, so double-ticking is not a performance issue.

        try:
            def _tick_listener(dt: float) -> None:
                if not self._enabled:
                    return
                self._on_tick()

            listener_id = animation_manager.add_tick_listener(_tick_listener)
            self._anim_listener_id = listener_id
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach to AnimationManager", exc_info=True)
        finally:
            self._ensure_tick_source()

    def detach_from_animation_manager(self) -> None:
        am = self._animation_manager
        listener_id = self._anim_listener_id
        if am is not None and listener_id is not None and hasattr(am, "remove_tick_listener"):
            try:
                am.remove_tick_listener(listener_id)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager", exc_info=True)
        self._animation_manager = None
        self._anim_listener_id = None
        self._ensure_tick_source()

    def _bubble_compute_worker(self, dt: float, eb_snap: dict,
                               sim_settings: dict, pulse_params: dict):
        """Run bubble simulation on COMPUTE thread pool. Returns snapshot data."""
        if self._bubble_simulation is None:
            from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
            self._bubble_simulation = BubbleSimulation()
            logger.debug("[SPOTIFY_VIS] Bubble simulation created on COMPUTE thread")
        self._bubble_simulation.tick(dt, eb_snap, sim_settings)
        pos_data, extra_data, trail_data = self._bubble_simulation.snapshot(
            bass=pulse_params['bass'],
            mid_high=pulse_params['mid_high'],
            big_bass_pulse=pulse_params['big_bass_pulse'],
            small_freq_pulse=pulse_params['small_freq_pulse'],
        )
        count = self._bubble_simulation.count
        if not getattr(self, '_bubble_worker_logged', False):
            logger.debug(
                "[SPOTIFY_VIS] Bubble worker: count=%d pos_len=%d extra_len=%d dt=%.3f",
                count, len(pos_data), len(extra_data), dt,
            )
            self._bubble_worker_logged = True
        return (pos_data, extra_data, trail_data, count)

    def _bubble_compute_done(self, task_result) -> None:
        """Callback from COMPUTE thread — post results to UI thread."""
        self._bubble_compute_pending = False
        if task_result.success and task_result.result is not None:
            pos_data, extra_data, trail_data, count = task_result.result
            if not getattr(self, '_bubble_done_logged', False):
                logger.debug(
                    "[SPOTIFY_VIS] Bubble compute done: success=%s count=%d",
                    task_result.success, count,
                )
                self._bubble_done_logged = True
            from core.threading.manager import ThreadManager
            ThreadManager.run_on_ui_thread(
                self._bubble_apply_result, pos_data, extra_data, trail_data, count
            )
        elif not task_result.success:
            logger.warning(
                "[SPOTIFY_VIS] Bubble compute FAILED: %s",
                task_result.error,
            )

    def _bubble_apply_result(self, pos_data: list, extra_data: list, trail_data: list, count: int) -> None:
        """Apply bubble simulation results on UI thread (atomic swap)."""
        self._bubble_pos_data = pos_data
        self._bubble_extra_data = extra_data
        self._bubble_trail_data = trail_data
        self._bubble_count = count

    def _ensure_tick_source(self) -> None:
        """Ensure the visualizer has a tick source for continuous updates.
        
        This method ensures the dedicated _bars_timer is running when the
        visualizer is enabled and no AnimationManager tick listener is active.
        The timer provides continuous 60Hz updates between transitions.
        """
        if not self._enabled:
            return
        
        # If we have an AnimationManager listener, we're covered during transitions
        # but still need the dedicated timer for between-transition updates
        if self._thread_manager is not None and self._bars_timer is None:
            try:
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
                self._current_timer_interval_ms = 16
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to create tick source timer", exc_info=True)
                self._bars_timer = None

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config

    def _update_card_style(self) -> None:
        if self._show_background:
            bg = QColor(self._bg_color)
            alpha = int(255 * max(0.0, min(1.0, self._bg_opacity)))
            bg.setAlpha(alpha)
            self.setStyleSheet(
                f"""
                QWidget {{
                    background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                    border: {self._border_width}px solid rgba({self._card_border_color.red()}, {self._card_border_color.green()}, {self._card_border_color.blue()}, {self._card_border_color.alpha()});
                    border-radius: 8px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget {
                    background-color: transparent;
                    border: 0px solid transparent;
                    border-radius: 8px;
                }
                """
            )

    def set_bar_style(self, *, bg_color: QColor, bg_opacity: float, border_color: QColor, border_width: Optional[int] = None,
                      show_background: bool = True) -> None:
        self._bg_color = QColor(bg_color)
        self._bg_opacity = max(0.0, min(1.0, float(bg_opacity)))
        self._card_border_color = QColor(border_color)
        resolved_width = BaseOverlayWidget.get_global_border_width() if border_width is None else int(border_width)
        self._border_width = max(0, resolved_width)
        self._show_background = bool(show_background)
        self._update_card_style()
        self.update()

    def set_bar_colors(self, fill_color: QColor, border_color: QColor) -> None:
        # Fill colour is applied per-bar; border colour controls the bar
        # outline tint. Card border remains driven by set_bar_style.
        self._bar_fill_color = QColor(fill_color)
        self._bar_border_color = QColor(border_color)
        self.update()

    def set_ghost_config(self, enabled: bool, alpha: float, decay: float) -> None:
        """Configure ghost trailing behaviour for the GPU bar overlay.

        ``enabled`` toggles whether ghost bars are drawn at all. ``alpha``
        controls their base opacity relative to the main bar border colour,
        and ``decay`` feeds into the overlay's peak-envelope decay so that
        higher values shorten the trail while lower values keep it visible
        for longer.
        """

        try:
            self._ghosting_enabled = bool(enabled)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._ghosting_enabled = True

        try:
            ga = float(alpha)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            ga = 0.4
        if ga < 0.0:
            ga = 0.0
        if ga > 1.0:
            ga = 1.0
        self._ghost_alpha = ga

        try:
            gd = float(decay)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            gd = 0.4
        if gd < 0.0:
            gd = 0.0
        self._ghost_decay_rate = gd

    def set_anchor_media_widget(self, widget: QWidget) -> None:
        self._anchor_media = widget
        if widget is not None:
            try:
                self.sync_visibility_with_anchor()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    def handle_media_update(self, payload: dict) -> None:
        """Receive Spotify media state from MediaWidget.

        Expects payload from MediaWidget.media_updated with a ``state``
        field of "playing"/"paused"/"stopped". When not playing, the
        visualizer decays to idle even if other apps are producing audio.
        """

        try:
            state = str(payload.get("state", "")).lower()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            state = ""
        prev = self._spotify_playing
        self._spotify_playing = state == "playing"
        self._last_media_state_ts = time.time()
        self._fallback_logged = False

        # WAKE TRIGGER: Play state transition from paused→playing
        if self._spotify_playing and not prev:
            self._trigger_wake()

        # WAKE TRIGGER: Artwork changed (indicates track change, possibly during pause)
        artwork_url = payload.get("artwork_url", "")
        artwork_hash = hash(artwork_url) if artwork_url else 0
        if artwork_hash != getattr(self, "_last_artwork_hash", 0):
            self._last_artwork_hash = artwork_hash
            if not self._spotify_playing:
                # Artwork changed while paused - likely a wake event
                self._trigger_wake()

        # CRITICAL: Pass playback state to beat engine for audio processing gating
        try:
            if self._engine is not None:
                self._engine.set_playback_state(self._spotify_playing)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set beat engine playback state", exc_info=True)

        first_media = not self._has_seen_media
        if first_media:
            # Track that we have seen at least one Spotify media state update
            # so later calls can focus purely on bar gating.
            self._has_seen_media = True

        if is_verbose_logging():
            try:
                logger.debug(
                    "[SPOTIFY_VIS] handle_media_update: state=%r (prev_playing=%s, now_playing=%s)",
                    state,
                    prev,
                    self._spotify_playing,
                )
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        
        self.sync_visibility_with_anchor()

    def sync_visibility_with_anchor(self) -> None:
        """Show/hide based on anchor media widget visibility."""
        anchor = self._anchor_media
        if anchor is not None:
            try:
                anchor_visible = anchor.isVisible()
                if anchor_visible and not self.isVisible():
                    # Media widget became visible - show visualizer
                    self._start_widget_fade_in(1500)
                elif not anchor_visible and self.isVisible():
                    # Media widget hidden - hide visualizer and clear GL overlay
                    self.hide()
                    self._clear_gl_overlay()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    
    def _destroy_parent_overlay(self, *, reason: str) -> None:
        parent = self.parent()
        if parent is None:
            logger.warning("[SPOTIFY_VIS] Overlay destroy requested without parent (reason=%s)", reason)
            return

        overlay = getattr(parent, "_spotify_bars_overlay", None)
        if overlay is None:
            logger.debug("[SPOTIFY_VIS] No overlay to destroy (reason=%s)", reason)
            return

        logger.debug(
            "[SPOTIFY_VIS] Destroying SpotifyBarsGLOverlay (reason=%s id=%s)",
            reason,
            hex(id(overlay)),
        )

        pixel_shift_manager = getattr(parent, "_pixel_shift_manager", None)
        if pixel_shift_manager is not None:
            try:
                pixel_shift_manager.unregister_widget(overlay)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to unregister overlay from PixelShiftManager", exc_info=True)

        try:
            overlay.hide()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to hide overlay before destroy", exc_info=True)

        try:
            if hasattr(overlay, "clear_overlay_buffer"):
                overlay.clear_overlay_buffer()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to blank overlay buffer before destroy", exc_info=True)

        try:
            overlay.update()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to schedule overlay update before destroy", exc_info=True)

        try:
            if hasattr(overlay, "cleanup_gl"):
                overlay.cleanup_gl()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to cleanup overlay GL state", exc_info=True)

        try:
            overlay.deleteLater()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to schedule overlay delete", exc_info=True)

        try:
            setattr(parent, "_spotify_bars_overlay", None)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to clear parent overlay reference", exc_info=True)

        # Fully detach drop shadows and cached pixmaps so other widgets don't inherit corruption.
        self._pending_shadow_cache_invalidation = True
        self._invalidate_shadow_cache_if_needed()
        self._shadow_config_missing = True
        self._waiting_for_fresh_frame = True

    def _request_overlay_mode_reset(self, *, mode: Optional[str] = None, reason: str = "widget_reset") -> None:
        """Ask the GL overlay (if present) to cold-reset its per-mode state."""

        parent = self.parent()
        if parent is None or not hasattr(parent, "push_spotify_visualizer_frame"):
            return
        overlay = getattr(parent, "_spotify_bars_overlay", None)
        if overlay is None or not hasattr(overlay, "request_mode_reset"):
            return
        try:
            target = mode or self._vis_mode_str
            overlay.request_mode_reset(target)
            logger.debug("[SPOTIFY_VIS] Requested overlay mode reset: mode=%s reason=%s", target, reason)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to request overlay mode reset", exc_info=True)

    def _reset_engine_state(self, *, reason: str) -> None:
        """Hard-reset beat engine + widget bar/energy state after crossover."""

        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None

        if engine is not None:
            try:
                engine.cancel_pending_compute_tasks()
                engine.reset_smoothing_state()
                engine.reset_floor_state()
                engine.set_smoothing(self._smoothing)
                self._replay_engine_config(engine)
                # Reapply the active mode's technical config so manual/dynamic floors
                # and sensitivity caches refresh whenever the engine is reset.
                self._apply_technical_config_for_mode(
                    self._vis_mode,
                    reason=f"engine_reset:{reason}" if reason else "engine_reset",
                )
                engine.ensure_started()
                self._track_engine_generation(engine)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to reset engine state", exc_info=True)

        zeros = [0.0] * self._bar_count
        self._display_bars = list(zeros)
        self._target_bars = list(zeros)
        self._visual_bars = list(zeros)
        self._per_bar_energy = list(zeros)
        self._waiting_for_fresh_engine_frame = True
        self._waiting_for_fresh_frame = True
        if reason:
            logger.debug("[SPOTIFY_VIS] Engine state reset reason=%s", reason)

    def _track_engine_generation(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        if engine is None:
            self._pending_engine_generation = -1
            return
        try:
            gen = int(engine.get_generation_id())
        except Exception:
            gen = -1
        self._pending_engine_generation = gen
        self._last_engine_generation_seen = -1

    def _handle_mode_cycle_state_reset(self) -> None:
        self._reset_teardown_bookkeeping()
        self._pending_shadow_cache_invalidation = True
        self._prepare_engine_for_mode_reset()

    def _clear_gl_overlay(self) -> None:
        """Destroy the GL bars overlay when visualizer hides."""
        self._request_overlay_mode_reset(reason="clear_gl_overlay")
        self._destroy_parent_overlay(reason="clear_gl_overlay")
        
    def _is_media_state_stale(self) -> bool:
        """Return True if Spotify state has not updated within fallback timeout."""
        last = getattr(self, "_last_media_state_ts", 0.0)
        if last <= 0.0:
            return True
        try:
            timeout = float(self._media_fallback_timeout)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            timeout = 8.0
        return (time.time() - last) >= max(1.0, timeout)

    def _has_audio_activity(
        self,
        bars: List[float],
        raw_bars: Optional[List[float]] = None,
    ) -> bool:
        """Heuristic to detect meaningful audio energy on the loopback feed."""
        candidates = raw_bars if isinstance(raw_bars, list) and raw_bars else bars
        if not isinstance(candidates, list) or not candidates:
            return False
        threshold = 0.01
        try:
            return max(candidates) >= threshold
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return any((b or 0.0) >= threshold for b in candidates)

    def _is_fallback_forced(self) -> bool:
        return time.time() <= getattr(self, "_fallback_forced_until", 0.0)

    def _update_fallback_force_state(self, audio_active: bool) -> None:
        now = time.time()
        if self._spotify_playing:
            self._fallback_mismatch_start = 0.0
            self._fallback_forced_until = 0.0
            return

        if audio_active:
            if self._fallback_mismatch_start <= 0.0:
                self._fallback_mismatch_start = now
            elif (now - self._fallback_mismatch_start) >= 3.0:
                if not self._is_fallback_forced():
                    self._fallback_forced_until = now + 20.0
                    logger.warning(
                        "[SPOTIFY_VIS] Forcing audio fallback for 20s (bridge reports paused but audio active)",
                    )
        else:
            self._fallback_mismatch_start = 0.0

    def _trigger_wake(self) -> None:
        """Trigger wake sequence for visualizer recovery after pause."""
        logger.debug("[SPOTIFY_VIS] Wake triggered")
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
            if engine and hasattr(engine, 'wake'):
                engine.wake()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Wake failed", exc_info=True)

    # ------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # ------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize visualizer resources (lifecycle hook)."""
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate visualizer - start audio capture (lifecycle hook)."""
        # Start audio capture via the shared beat engine
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            if self._thread_manager is not None:
                engine.set_thread_manager(self._thread_manager)
            engine.acquire()
            self._replay_engine_config(engine)
            engine.ensure_started()
            # Ensure the active mode's technical configuration is re-sent on every
            # activation so shared engine caches (floors, sensitivity, block size)
            # cannot bleed between runs.
            self._apply_technical_config_for_mode(self._vis_mode, reason="activate_impl")
        except Exception:
            logger.debug("[LIFECYCLE] Failed to start shared beat engine", exc_info=True)
        
        # Start dedicated timer for continuous visualizer updates
        if self._thread_manager is not None and self._bars_timer is None:
            try:
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
                self._current_timer_interval_ms = 16
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                self._bars_timer = None
        
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate visualizer - stop audio capture (lifecycle hook)."""
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.release()
            except Exception:
                logger.debug("[LIFECYCLE] Failed to release shared beat engine", exc_info=True)
        
        try:
            self.detach_from_animation_manager()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        
        if self._bars_timer is not None:
            try:
                self._bars_timer.stop()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._bars_timer = None
        self._using_animation_ticks = False
        
        self._log_perf_snapshot(reset=True)
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up visualizer resources (lifecycle hook)."""
        self._deactivate_impl()
        self._engine = None
        # Free GL handles on the bars overlay to prevent VRAM leaks
        self._destroy_parent_overlay(reason="cleanup_impl")
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget cleaned up")

    # ------------------------------------------------------------------
    # Legacy Lifecycle Methods (for backward compatibility)
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True

        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        # Start audio capture via the shared beat engine so the buffer can
        # begin filling. Each widget acquires a reference so the engine can
        # stop cleanly once the last visualiser stops.
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            if self._thread_manager is not None:
                engine.set_thread_manager(self._thread_manager)
            engine.acquire()
            self._replay_engine_config(engine)
            
            # CRITICAL: Initialize beat engine with current playback state
            # This ensures audio gating is active from startup
            engine.set_playback_state(self._spotify_playing)
            
            engine.ensure_started()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to start shared beat engine", exc_info=True)

        # Always start the dedicated timer for continuous visualizer updates.
        # AnimationManager only ticks during active transitions, so we need
        # the dedicated timer to keep the visualizer running between transitions.
        # The _on_tick method handles deduplication via _last_update_ts.
        if self._thread_manager is not None and self._bars_timer is None:
            try:
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
                self._current_timer_interval_ms = 16
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                self._bars_timer = None
        elif self._animation_manager is not None and self._anim_listener_id is not None:
            self._using_animation_ticks = True

        # Coordinate the visualiser card fade-in with the primary overlay
        # group so it joins the main wave on this display. Only show if the
        # anchor media widget is visible (Spotify is active).
        parent = self.parent()

        def _starter() -> None:
            # Guard against widget being deleted before deferred callback runs
            if not Shiboken.isValid(self):
                return
            # Only show if anchor media widget is visible (Spotify is playing)
            anchor = self._anchor_media
            if anchor is not None:
                try:
                    if not anchor.isVisible():
                        # Media widget not visible - don't show visualizer yet
                        return
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            
            try:
                self._start_widget_fade_in(1500)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                try:
                    self.show()
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("spotify_visualizer", _starter)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                _starter()
        else:
            _starter()

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False

        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.release()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to release shared beat engine", exc_info=True)

        try:
            self.detach_from_animation_manager()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager on stop", exc_info=True)

        try:
            if self._bars_timer is not None:
                self._bars_timer.stop()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        self._bars_timer = None
        self._using_animation_ticks = False

        # Emit a concise PERF summary for this widget's activity during the
        # last enabled period so we can see its effective update/paint rate
        # and dt jitter alongside compositor and animation metrics.
        self._log_perf_snapshot(reset=True)

        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    def cleanup(self) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # UI and painting
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Configure attributes to prevent flicker with GL compositor
        configure_overlay_widget_attributes(self)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        # Slightly taller default so bars and card border have breathing
        # room and match the visual weight of other widgets.
        self.setMinimumHeight(88)
        self._update_card_style()

    # ------------------------------------------------------------------
    # Mouse event handling for mode cycling
    # ------------------------------------------------------------------

    def set_widget_manager(self, wm) -> None:
        """Store WidgetManager reference for settings persistence."""
        self._widget_manager = wm

    def _cycle_mode(self) -> bool:
        """Cycle to the next visualizer mode with a crossfade."""
        from widgets.spotify_visualizer.mode_transition import cycle_mode

        result = cycle_mode(self)
        if result:
            try:
                self._on_mode_cycle_requested()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Mode cycle hook failed", exc_info=True)
            self._request_latency_probe("mode_cycle")
        return result

    def handle_double_click(self, local_pos) -> bool:
        """Called by WidgetManager dispatch. Cycles visualizer mode."""
        return self._cycle_mode()

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click cycles visualizer mode with a crossfade."""
        if self._cycle_mode():
            event.accept()
        else:
            event.ignore()

    def mousePressEvent(self, event) -> None:
        """Forward single clicks to parent (compositor/reddit)."""
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        """Forward releases to parent."""
        event.ignore()

    def _mode_transition_fade_factor(self, now_ts: float) -> float:
        """Return a 0..1 fade multiplier for the mode crossfade."""
        from widgets.spotify_visualizer.mode_transition import mode_transition_fade_factor
        return mode_transition_fade_factor(self, now_ts)

    def _persist_vis_mode(self) -> None:
        """Save the current visualizer mode to SettingsManager."""
        from widgets.spotify_visualizer.mode_transition import persist_vis_mode
        persist_vis_mode(self)

    def _reset_visualizer_state(self, *, clear_overlay: bool = False, replay_cached: bool = False) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import reset_visualizer_state
        reset_visualizer_state(self, clear_overlay=clear_overlay, replay_cached=replay_cached)

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import start_widget_fade_in
        start_widget_fade_in(self, duration_ms)

    def _start_widget_fade_out(self, duration_ms: int = 1200, on_complete: Optional[Callable[[], None]] = None) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import start_widget_fade_out
        start_widget_fade_out(self, duration_ms, on_complete)

    def _reset_teardown_bookkeeping(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import reset_teardown_bookkeeping
        reset_teardown_bookkeeping(self)

    def _on_mode_cycle_requested(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import on_mode_cycle_requested
        on_mode_cycle_requested(self)

    def _on_mode_fade_out_complete(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import on_mode_fade_out_complete
        on_mode_fade_out_complete(self)

    def _prepare_engine_for_mode_reset(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
        prepare_engine_for_mode_reset(self)

    def _begin_mode_fade_in(self, now_ts: float) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import begin_mode_fade_in
        begin_mode_fade_in(self, now_ts)

    def _check_mode_teardown_ready(self, engine: Optional[_SpotifyBeatEngine], now_ts: float) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import check_mode_teardown_ready
        check_mode_teardown_ready(self, engine, now_ts)

    def _apply_pending_mode_transition_layout(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import apply_pending_mode_transition_layout
        apply_pending_mode_transition_layout(self)

    def _invalidate_shadow_cache_if_needed(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import invalidate_shadow_cache_if_needed
        invalidate_shadow_cache_if_needed(self)

    def _on_first_frame_after_cold_start(self) -> None:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import on_first_frame_after_cold_start
        on_first_frame_after_cold_start(self)

    def _get_gpu_fade_factor(self, now_ts: float) -> float:
        """Delegates to widgets.spotify_visualizer.mode_transition."""
        from widgets.spotify_visualizer.mode_transition import get_gpu_fade_factor
        return get_gpu_fade_factor(self, now_ts)

    def _dynamic_bar_segments(self) -> int:
        """Compute segment count based on current widget height.

        Targets ~4px per segment + 1px gap so taller cards gain more segments
        (better gradient resolution) while shorter cards stay clean.  Clamps
        between 8 and 64 (GLSL uniform array limit).
        """
        try:
            h = self.height()
        except Exception:
            return max(8, self._bar_segments_base)
        if h <= 0:
            return max(8, self._bar_segments_base)
        margin_y = 6
        inner_h = h - margin_y * 2
        if inner_h <= 0:
            return 8
        seg_slot = 5  # 4px segment + 1px gap
        segs = max(8, min(64, inner_h // seg_slot))
        return segs

    def _rebuild_geometry_cache(self, rect: QRect) -> None:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import rebuild_geometry_cache
        rebuild_geometry_cache(self, rect)

    def _apply_visual_smoothing(self, target_bars: List[float], now_ts: float) -> bool:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import apply_visual_smoothing
        return apply_visual_smoothing(self, target_bars, now_ts)

    def _get_transition_context(self, parent: Optional[QWidget]) -> Dict[str, Any]:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import get_transition_context
        return get_transition_context(self, parent)

    def _resolve_max_fps(self, transition_ctx: Dict[str, Any]) -> float:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import resolve_max_fps
        return resolve_max_fps(self, transition_ctx)

    def _update_timer_interval(self, max_fps: float) -> None:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import update_timer_interval
        update_timer_interval(self, max_fps)

    def _pause_timer_during_transition(self, is_transition_active: bool) -> None:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import pause_timer_during_transition
        pause_timer_during_transition(self, is_transition_active)

    def _log_tick_spike(self, dt: float, transition_ctx: Dict[str, Any]) -> None:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import log_tick_spike
        log_tick_spike(self, dt, transition_ctx)

    def _request_latency_probe(self, reason: str) -> None:
        if reason not in self._latency_pending_probe:
            self._latency_pending_probe.append(reason)

    def _log_audio_latency_metrics(
        self,
        engine: _SpotifyBeatEngine | None,
        now_ts: float,
        force_reason: Optional[str] = None,
    ) -> None:
        """Delegates to widgets.spotify_visualizer.tick_pipeline."""
        from widgets.spotify_visualizer.tick_pipeline import log_audio_latency_metrics
        log_audio_latency_metrics(self, engine, now_ts, force_reason=force_reason)

    def _on_tick(self) -> None:
        """Delegates to widgets.spotify_visualizer.tick_pipeline."""
        from widgets.spotify_visualizer.tick_pipeline import on_tick
        on_tick(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        rect = self.rect()
        if is_verbose_logging() and not getattr(self, "_paint_debug_logged", False):
            try:
                anchor = self._anchor_media
                anchor_geom_ok = bool(anchor and anchor.width() > 0 and anchor.height() > 0)
                logger.debug(
                    "[SPOTIFY_VIS] paintEvent: geom=(%s,%s,%s,%s) rect=(%s,%s,%s,%s) enabled=%s visible=%s spotify_playing=%s show_bg=%s anchor_geom_ok=%s",
                    self.x(),
                    self.y(),
                    self.width(),
                    self.height(),
                    rect.x(),
                    rect.y(),
                    rect.width(),
                    rect.height(),
                    self._enabled,
                    self.isVisible(),
                    self._spotify_playing,
                    self._show_background,
                    anchor_geom_ok,
                )
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            try:
                self._paint_debug_logged = True
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        if rect.width() <= 0 or rect.height() <= 0:
            painter.end()
            return

        # When GPU overlay rendering is active for this widget instance, the
        # card/fade/shadow are still drawn via stylesheets and
        # ShadowFadeProfile, but the bar geometry itself is rendered by the
        # GL overlay. In that mode we skip the CPU bar drawing entirely.
        if not getattr(self, "_cpu_bars_enabled", True):
            painter.end()
            return

        if is_perf_metrics_enabled():
            try:
                now = time.time()
                if self._perf_paint_last_ts is not None:
                    dt = now - self._perf_paint_last_ts
                    # Skip metrics for gaps >1s (widget was likely occluded during GL transition).
                    # Also reset the measurement window to avoid polluting duration/avg_fps.
                    if dt > 1.0:
                        # Large gap detected - reset measurement window
                        self._perf_paint_start_ts = now
                        self._perf_paint_min_dt = 0.0
                        self._perf_paint_max_dt = 0.0
                        self._perf_paint_frame_count = 0
                    elif dt > 0.0:
                        # Normal frame - record metrics
                        if self._perf_paint_min_dt == 0.0 or dt < self._perf_paint_min_dt:
                            self._perf_paint_min_dt = dt
                        if dt > self._perf_paint_max_dt:
                            self._perf_paint_max_dt = dt
                        self._perf_paint_frame_count += 1
                else:
                    # First paint event
                    self._perf_paint_start_ts = now
                self._perf_paint_last_ts = now
            except Exception:
                logger.debug("[SPOTIFY_VIS] Paint PERF accounting failed", exc_info=True)

        # Note: paintEvent itself does not trigger PERF snapshots; these are
        # driven from the tick path so that tick/paint metrics share a common
        # time window and appear as a paired summary in logs.

        with profile("SPOTIFY_VIS_PAINT", threshold_ms=5.0, log_level="DEBUG"):
            # Card background is handled by the stylesheet; painting focuses on
            # the bar geometry only. Use a cached layout to avoid recomputing
            # per-frame integer geometry.

            segments = max(1, self._dynamic_bar_segments())
            if (
                self._geom_cache_rect is None
                or self._geom_cache_rect.width() != rect.width()
                or self._geom_cache_rect.height() != rect.height()
                or self._geom_cache_bar_count != self._bar_count
                or self._geom_cache_segments != segments
            ):
                self._rebuild_geometry_cache(rect)

            inner = self._geom_cache_rect
            bar_x = self._geom_bar_x
            seg_y = self._geom_seg_y
            bar_width = self._geom_bar_width
            seg_height = self._geom_seg_height
            if (
                inner is None
                or inner.width() <= 0
                or inner.height() <= 0
                or not bar_x
                or not seg_y
                or bar_width <= 0
                or seg_height <= 0
            ):
                painter.end()
                return

            count = self._bar_count
            count = min(count, len(bar_x))

            fill = QColor(self._bar_fill_color)
            border = QColor(self._bar_border_color)
            max_segments = min(segments, len(seg_y))

            painter.setBrush(fill)
            painter.setPen(border)

            # SPECTRUM mode - classic bar visualization
            _single = self._spectrum_single_piece
            for i in range(count):
                    x = bar_x[i]
                    value = max(0.0, min(1.0, self._display_bars[i]))
                    if value <= 0.0:
                        continue
                    boosted = value * 1.2
                    if boosted > 1.0:
                        boosted = 1.0

                    if _single:
                        bar_h = max(1, int(round(boosted * inner.height())))
                        bar_y = inner.bottom() - bar_h + 1
                        painter.drawRect(QRect(x, bar_y, bar_width, bar_h))
                    else:
                        active = int(round(boosted * segments))
                        if active <= 0:
                            if self._spotify_playing and value > 0.0:
                                active = 1
                            else:
                                continue
                        active = min(active, max_segments)
                        for s in range(active):
                            y = seg_y[s]
                            bar_rect = QRect(x, y, bar_width, seg_height)
                            painter.drawRect(bar_rect)

            painter.end()

    def set_visualization_mode(self, mode: VisualizerMode) -> None:
        """Set the visualization display mode."""
        if mode != self._vis_mode:
            self._vis_mode = mode
            self._apply_technical_config_for_mode(mode, reason="mode_switch")
            try:
                wm = getattr(self, '_widget_manager', None)
                sm = getattr(wm, '_settings_manager', None) if wm is not None else None
                if sm is not None:
                    from core.settings.visualizer_presets import apply_preset_to_config

                    cfg = sm.get('widgets', {}) or {}
                    vis_cfg = dict(cfg.get('spotify_visualizer', {}) or {})
                    mode_str = self._vis_mode_str
                    preset_idx = int(vis_cfg.get(f'preset_{mode_str}', 0) or 0)
                    vis_cfg = apply_preset_to_config(mode_str, preset_idx, vis_cfg)

                    pm_re = f'{mode_str}_rainbow_enabled'
                    pm_rs = f'{mode_str}_rainbow_speed'
                    self._rainbow_enabled = bool(vis_cfg.get(pm_re, vis_cfg.get('rainbow_enabled', False)))
                    self._rainbow_speed = max(
                        0.01,
                        min(5.0, float(vis_cfg.get(pm_rs, vis_cfg.get('rainbow_speed', 0.5))))
                    )
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to sync per-mode rainbow on mode switch", exc_info=True)
            # Reset display bars so returning modes start clean
            for i in range(len(self._display_bars)):
                self._display_bars[i] = 0.0
            # Invalidate cached GPU geometry so the next tick forces a push
            self._last_gpu_geom = None
            self._last_gpu_fade_sent = -1.0
            self._has_pushed_first_frame = False
            # Reset beat engine smoothing so the new mode starts fresh
            # (prevents stale smoothed bars/energy dampening reactivity)
            if self._engine is not None:
                try:
                    self._engine.reset_smoothing_state()
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            logger.debug("[SPOTIFY_VIS] Visualization mode changed to %s", mode.name)

    def get_visualization_mode(self) -> VisualizerMode:
        """Get the current visualization display mode."""
        return self._vis_mode

    def cycle_visualization_mode(self) -> VisualizerMode:
        """Cycle to the next visualization mode and return it.

        Cycles through Spectrum → Oscilloscope → Sine Wave → Blob → Bubble.
        Starfield and Helix are excluded from the quick-cycle.
        """
        _CYCLE_MODES = [
            VisualizerMode.SPECTRUM,
            VisualizerMode.OSCILLOSCOPE,
            VisualizerMode.SINE_WAVE,
            VisualizerMode.BLOB,
            VisualizerMode.BUBBLE,
        ]
        try:
            idx = _CYCLE_MODES.index(self._vis_mode)
        except ValueError:
            idx = -1
        next_mode = _CYCLE_MODES[(idx + 1) % len(_CYCLE_MODES)]
        self.set_visualization_mode(next_mode)
        self._apply_preferred_height()
        return self._vis_mode

    def _log_perf_snapshot(self, reset: bool = False) -> None:
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import log_perf_snapshot
        log_perf_snapshot(self, reset=reset)

