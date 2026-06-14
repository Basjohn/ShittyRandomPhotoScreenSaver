from __future__ import annotations

from typing import List, Optional, Dict, Any, Callable, Mapping
import copy
import time

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget
from core.logging.logger import (
    get_logger,
    is_verbose_logging,
)
from core.threading.manager import ThreadManager
from core.process import ProcessSupervisor
from core.settings.models import SpotifyVisualizerSettings, PER_MODE_TECHNICAL_MODES
from core.settings.visualizer_presets import (
    VisualizerActivationPayload,
    resolve_visualizer_activation_payload,
)
from core.settings.visualizer_mode_registry import coerce_visualizer_mode_id
from widgets.shadow_utils import ShadowFadeProfile, configure_overlay_widget_attributes, shadow_config_enabled
from widgets.base_overlay_widget import BaseOverlayWidget


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
from widgets.spotify_visualizer.startup_contract import VisualizerStartupState

logger = get_logger(__name__)



class SpotifyVisualizerWidget(QWidget):
    """Thin bar visualizer card paired with the Spotify media widget.

    The widget draws a rounded-rect card that inherits Spotify/Media
    styling from DisplayWidget and renders a row of vertical bars whose
    heights are driven by audio magnitudes published by
    SpotifyVisualizerAudioWorker.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        bar_count: int = 32,
        initial_mode: VisualizerMode | str | None = None,
    ) -> None:
        super().__init__(parent)

        self._bar_count = max(1, int(bar_count))
        self._display_bars: List[float] = [0.0] * self._bar_count
        self._target_bars: List[float] = [0.0] * self._bar_count
        self._per_bar_energy: List[float] = [0.0] * self._bar_count
        self._visual_bars: List[float] = [0.0] * self._bar_count

        # Source tracking for bar arrays to prevent stale compute/frame commits
        self._display_bars_source_generation: int = -1
        self._display_bars_source_activation: int = -1
        self._target_bars_source_generation: int = -1
        self._target_bars_source_activation: int = -1
        self._visual_bars_source_generation: int = -1
        self._visual_bars_source_activation: int = -1
        self._per_bar_energy_source_generation: int = -1
        self._per_bar_energy_source_activation: int = -1

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
        self._painted_frame_shadow_enabled: bool = True
        self._custom_layout_constraint_restore: Optional[tuple[int, int, int, int]] = None
        self._painted_frame_shadow_pixmap: Optional[QPixmap] = None
        self._painted_frame_shadow_cache_key: Optional[tuple] = None
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
        self._spectrum_ghosting_enabled: bool = True
        self._spectrum_ghost_alpha: float = 0.4
        self._spectrum_ghost_decay: float = 0.4
        self._sine_ghosting_enabled: bool = True
        self._sine_ghost_alpha: float = 0.45
        self._sine_ghost_decay: float = 0.3
        self._sine_ghost_line2_enabled: bool = True
        self._sine_ghost_line3_enabled: bool = True
        self._sine_ghost_line4_enabled: bool = True
        self._sine_ghost_line5_enabled: bool = True
        self._sine_ghost_line6_enabled: bool = True
        self._bubble_ghosting_enabled: bool = False
        self._bubble_ghost_alpha: float = 0.0
        self._bubble_ghost_decay: float = 0.4
        self._spectrum_single_piece: bool = False
        self._spectrum_border_radius: float = 0.0
        self._spectrum_glow_enabled: bool = False
        self._spectrum_glow_intensity: float = 0.55
        self._spectrum_glow_color: QColor = QColor(110, 220, 255, 235)
        self._spectrum_mirrored: bool = True
        self._spectrum_shape_nodes: list = [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]]
        self._spectrum_notch_positions_mirrored: list = [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]]
        self._spectrum_notch_positions_linear: list = [[0.0, "Bass"], [0.24, "Low-Mid"], [0.46, "Vocal"], [0.72, "Hi-Mid"], [1.0, "Treble"]]
        self._spectrum_lane_strengths_mirrored: dict = {
            "Mid": 0.60,
            "Vocal": 0.64,
            "Low-Mid": 0.70,
            "Bass": 0.80,
        }
        self._spectrum_lane_strengths_linear: dict = {
            "Bass": 0.80,
            "Low-Mid": 0.70,
            "Vocal": 0.64,
            "Hi-Mid": 0.80,
            "Treble": 1.00,
        }
        # Spectrum shaping config (pushed to audio worker DSP pipeline)
        self._spectrum_wave_amplitude: float = 0.50
        self._spectrum_profile_floor: float = 0.12
        self._spectrum_drop_speed: float = 1.0

        # Visualization mode (Spectrum, Waveform, Abstract)
        _initial_mode_id = coerce_visualizer_mode_id(
            initial_mode.name.lower() if isinstance(initial_mode, VisualizerMode) else initial_mode
        )
        self._vis_mode: VisualizerMode = {
            "spectrum": VisualizerMode.SPECTRUM,
            "oscilloscope": VisualizerMode.OSCILLOSCOPE,
            "sine_wave": VisualizerMode.SINE_WAVE,
            "blob": VisualizerMode.BLOB,
            "bubble": VisualizerMode.BUBBLE,
            "devcurve": VisualizerMode.DEVCURVE,
        }.get(_initial_mode_id, VisualizerMode.BUBBLE)

        # Oscilloscope settings
        self._osc_glow_enabled: bool = True
        self._osc_glow_intensity: float = 0.5
        self._osc_glow_size: float = 1.0
        self._osc_glow_reactivity: float = 1.0
        self._osc_glow_color: QColor = QColor(0, 200, 255, 230)
        self._osc_line_color: QColor = QColor(255, 255, 255, 255)
        self._osc_reactive_glow: bool = True
        self._osc_line_amplitude: float = 3.0
        self._osc_smoothing: float = 0.7
        self._osc_line_count: int = 1
        self._osc_line2_color: QColor = QColor(255, 120, 50, 230)
        self._osc_line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._osc_line3_color: QColor = QColor(50, 255, 120, 230)
        self._osc_line3_glow_color: QColor = QColor(50, 255, 120, 180)
        self._osc_line4_color: QColor = QColor(255, 0, 150, 230)
        self._osc_line4_glow_color: QColor = QColor(255, 0, 150, 180)
        self._osc_line5_color: QColor = QColor(0, 255, 200, 230)
        self._osc_line5_glow_color: QColor = QColor(0, 255, 200, 180)
        self._osc_line6_color: QColor = QColor(200, 100, 255, 230)
        self._osc_line6_glow_color: QColor = QColor(200, 100, 255, 180)


        # Blob settings
        self._blob_color: QColor = QColor(0, 180, 255, 230)
        self._blob_glow_color: QColor = QColor(0, 140, 255, 180)
        self._blob_edge_color: QColor = QColor(100, 220, 255, 230)
        self._blob_outline_color: QColor = QColor(0, 0, 0, 0)
        self._blob_inward_liquid_color: QColor = QColor(170, 225, 255, 190)
        self._blob_pulse: float = 1.0
        self._blob_width: float = 1.0
        self._blob_size: float = 1.0
        self._blob_glow_intensity: float = 0.5
        self._blob_glow_reactivity: float = 1.0
        self._blob_glow_max_size: float = 1.0
        self._blob_reactive_glow: bool = True
        self._blob_inward_liquid_enabled: bool = False
        self._blob_inward_liquid_reactivity: float = 1.0
        self._blob_inward_liquid_max_size: float = 0.28
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
        self._blob_stretch_inner: float = 0.0  # default modern path: no authored inward dents
        self._blob_stretch_outer: float = 0.35  # 0..1 how far outward protrusions go


        # Card height expansion (per-mode growth factors, user-customizable)
        self._base_height: int = 80
        self._spectrum_growth: float = 2.0
        self._blob_growth: float = 3.5
        self._osc_growth: float = 2.0
        self._bubble_growth: float = 3.0
        self._devcurve_growth: float = 3.0
        self._osc_speed: float = 1.0
        self._osc_line_dim: bool = False
        self._osc_line_offset_bias: float = 0.0
        self._osc_vertical_shift: int = 0
        self._sine_wave_growth: float = 2.0
        self._sine_wave_travel: int = 0  # 0=none, 1=left, 2=right
        self._sine_travel_line2: int = 0  # per-line travel for line 2
        self._sine_travel_line3: int = 0  # per-line travel for line 3
        self._sine_travel_line4: int = 0  # per-line travel for line 4
        self._sine_travel_line5: int = 0  # per-line travel for line 5
        self._sine_travel_line6: int = 0  # per-line travel for line 6
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
        self._sine_glow_size: float = 1.0
        self._sine_glow_reactivity: float = 1.0
        self._sine_glow_color: QColor = QColor(0, 200, 255, 230)
        self._sine_line_color: QColor = QColor(255, 255, 255, 255)
        self._sine_line2_color: QColor = QColor(255, 120, 50, 230)
        self._sine_line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._sine_line3_color: QColor = QColor(50, 255, 120, 230)
        self._sine_line3_glow_color: QColor = QColor(50, 255, 120, 180)
        self._sine_line4_color: QColor = QColor(255, 120, 50, 230)
        self._sine_line4_glow_color: QColor = QColor(255, 120, 50, 180)
        self._sine_line5_color: QColor = QColor(50, 255, 120, 230)
        self._sine_line5_glow_color: QColor = QColor(50, 255, 120, 180)
        self._sine_line6_color: QColor = QColor(255, 0, 150, 230)
        self._sine_line6_glow_color: QColor = QColor(255, 0, 150, 180)
        self._sine_reactive_glow: bool = True
        self._sine_sensitivity: float = 1.0
        self._sine_smoothing: float = 0.7
        self._sine_speed: float = 1.0
        self._sine_line_count: int = 1
        self._sine_line_offset_bias: float = 0.0
        self._sine_line_dim: bool = False
        self._sine_line1_shift: float = 0.0
        self._sine_line2_shift: float = 0.0
        self._sine_line3_shift: float = 0.0
        self._sine_line4_shift: float = 0.0
        self._sine_line5_shift: float = 0.0
        self._sine_line6_shift: float = 0.0

        # Rainbow (Taste The Rainbow) mode — global, applies to all visualizers
        self._rainbow_enabled: bool = False
        self._rainbow_speed: float = 0.5
        self._rainbow_per_bar: bool = False
        self._spectrum_rainbow_border: bool = False

        # Oscilloscope ghost trail
        self._osc_ghosting_enabled: bool = False
        self._osc_ghost_intensity: float = 0.4
        self._osc_ghost_line2_enabled: bool = True
        self._osc_ghost_line3_enabled: bool = True
        self._osc_ghost_line4_enabled: bool = True
        self._osc_ghost_line5_enabled: bool = True
        self._osc_ghost_line6_enabled: bool = True

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
        self._latency_audio_ready: bool = False
        self._latency_activation_started_ts: float = time.time()
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
        self._bubble_bounce_big_pct: int = 70
        self._bubble_bounce_small_pct: int = 30
        self._bubble_bounce_big_speed: float = 0.8
        self._bubble_bounce_small_speed: float = 0.5
        self._bubble_bounce_same_only: bool = False
        self._bubble_collision_pop_mode: str = "off"
        self._bubble_outline_color: QColor = QColor(255, 255, 255, 230)
        self._bubble_specular_color: QColor = QColor(255, 255, 255, 255)
        self._bubble_gradient_light: QColor = QColor(210, 170, 120, 255)
        self._bubble_gradient_dark: QColor = QColor(80, 60, 50, 255)
        self._bubble_pop_color: QColor = QColor(255, 255, 255, 180)
        self._bubble_specular_direction: str = "top_left"
        self._bubble_gradient_direction: str = "top"
        self._bubble_big_size_max: float = 0.038
        self._bubble_small_size_max: float = 0.018
        # Transient bus controls (Approach A dual-path)
        self._transient_pulse_gain: float = 1.0   # Bubble: transient bass pulse gain (0-3)
        self._transient_clamp: float = 1.5         # Global: max transient energy per channel (0-3)
        self._kick_lane_gain: float = 1.0          # Spectrum: kick express lane gain (0-2)
        self._spectrum_lane_transient_mix: float = 0.65   # Spectrum: transient bleed into kick lane
        self._bubble_transient_mix_bass: float = 0.75     # Bubble: bass transient mix weight
        self._bubble_transient_mix_vocal: float = 0.25    # Bubble: vocal/mid transient mix weight
        self._blob_transient_mix_bass: float = 0.5        # Blob: bass transient mix weight
        self._blob_transient_mix_vocal: float = 0.35      # Blob: vocal/mid transient mix weight
        self._sine_wave_transient_width_mix: float = 0.4  # Sine: transient→width reaction mix
        self._osc_transient_width_mix: float = 0.35       # Osc: transient→width reaction mix
        self._bubble_big_contraction_bias: float = 1.0
        self._bubble_big_size_clamp: float = 4.0
        self._bubble_big_specular_max_size: float = 2.5
        self._bubble_simulation: Optional[object] = None  # lazy init (owned by compute thread)
        self._bubble_pos_data: list = []
        self._bubble_extra_data: list = []
        self._bubble_trail_data: list = []
        self._bubble_trail_strength: float = 0.0
        self._bubble_tail_opacity: float = 0.0
        self._bubble_count: int = 0
        self._bubble_compute_pending: bool = False  # coalescing flag
        self._bubble_last_tick_ts: float = 0.0
        self._bubble_dispatch_energy_snapshot: Dict[str, float] = {
            "bass": 0.0,
            "mid": 0.0,
            "high": 0.0,
            "overall": 0.0,
            "smooth_mid": 0.0,
            "smooth_high": 0.0,
        }
        self._bubble_dispatch_settings: Dict[str, Any] = {
            "bubble_big_count": self._bubble_big_count,
            "bubble_small_count": self._bubble_small_count,
            "bubble_surface_reach": self._bubble_surface_reach,
            "bubble_stream_direction": self._bubble_stream_direction,
            "bubble_stream_constant_speed": self._bubble_stream_constant_speed,
            "bubble_stream_speed_cap": self._bubble_stream_speed_cap,
            "bubble_stream_reactivity": self._bubble_stream_reactivity,
            "bubble_rotation_amount": self._bubble_rotation_amount,
            "bubble_drift_amount": self._bubble_drift_amount,
            "bubble_drift_speed": self._bubble_drift_speed,
            "bubble_drift_frequency": self._bubble_drift_frequency,
            "bubble_drift_direction": self._bubble_drift_direction,
            "bubble_big_size_max": self._bubble_big_size_max,
            "bubble_small_size_max": self._bubble_small_size_max,
            "bubble_trail_strength": self._bubble_trail_strength,
            "bubble_bounce_big_pct": self._bubble_bounce_big_pct,
            "bubble_bounce_small_pct": self._bubble_bounce_small_pct,
            "bubble_bounce_big_speed": self._bubble_bounce_big_speed,
            "bubble_bounce_small_speed": self._bubble_bounce_small_speed,
            "bubble_bounce_same_only": self._bubble_bounce_same_only,
            "bubble_collision_pop_mode": self._bubble_collision_pop_mode,
            "_event_scheduler": None,
        }
        self._bubble_dispatch_pulse_params: Dict[str, float] = {
            "bass": 0.0,
            "mid_high": 0.0,
            "big_bass_pulse": self._bubble_big_bass_pulse,
            "small_freq_pulse": self._bubble_small_freq_pulse,
            "big_specular_max_size": self._bubble_big_specular_max_size,
            "big_contraction_bias": self._bubble_big_contraction_bias,
            "big_size_clamp": self._bubble_big_size_clamp,
        }
        self._bubble_sim_task_id: str = f"bubble_sim_{id(self)}"

        # Behavioural gating
        self._spotify_playing: bool = False
        self._pending_playback_pause_timer = None
        self._pending_playback_pause_state: Optional[str] = None
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
        self._last_floor_config = (True, 0.12)
        self._last_sensitivity_config = (True, 1.0)
        self._last_energy_boost: float = 0.85
        self._last_input_gain: float = 1.0
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
        self._target_timer_interval_ms: int = 16
        self._current_timer_interval_ms: int = 16
        self._spectrum_gpu_push_extras: Dict[str, Any] = {}
        self._last_gpu_fade_sent: float = -1.0
        self._last_gpu_geom: Optional[QRect] = None
        # Reset/fresh-frame handoff tracking must exist from construction so
        # the recurring UI tick cannot crash before any mode-reset helpers run.
        self._waiting_for_fresh_frame: bool = False
        self._waiting_for_fresh_engine_frame: bool = False
        self._pending_engine_generation: int = -1
        self._last_engine_generation_seen: int = -1
        self._pending_engine_activation_id: int = -1
        self._last_engine_activation_seen: int = -1
        self._first_overlay_push_probe_key: Optional[tuple] = None

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

        # Visualizer content is GL-only; this widget owns the card surface
        # while DisplayWidget's QOpenGLWidget overlay owns mode rendering.

        # Tick source coordination
        self._using_animation_ticks: bool = False
        try:
            shared_fade_ms = ShadowFadeProfile.default_duration_ms()
        except Exception:
            shared_fade_ms = max(0, int(getattr(ShadowFadeProfile, "DURATION_MS", 1800)))
        self._startup_phase = VisualizerStartupState.from_shared_fade_duration(shared_fade_ms)

        self._setup_ui()

    def _get_startup_phase_attr(self, attr_name: str):
        return getattr(self._startup_phase, attr_name)

    def _set_startup_phase_attr(self, attr_name: str, value) -> None:
        setattr(self._startup_phase, attr_name, value)

    @property
    def _spotify_secondary_stage_registered(self) -> bool:
        return bool(self._get_startup_phase_attr("secondary_stage_registered"))

    @_spotify_secondary_stage_registered.setter
    def _spotify_secondary_stage_registered(self, value: bool) -> None:
        self._set_startup_phase_attr("secondary_stage_registered", bool(value))

    @property
    def _startup_secondary_stage_pending(self) -> bool:
        return bool(self._get_startup_phase_attr("secondary_stage_pending"))

    @_startup_secondary_stage_pending.setter
    def _startup_secondary_stage_pending(self, value: bool) -> None:
        self._set_startup_phase_attr("secondary_stage_pending", bool(value))

    @property
    def _startup_hot_start_started(self) -> bool:
        return bool(self._get_startup_phase_attr("hot_start_started"))

    @_startup_hot_start_started.setter
    def _startup_hot_start_started(self, value: bool) -> None:
        self._set_startup_phase_attr("hot_start_started", bool(value))

    @property
    def _startup_reveal_pending(self) -> bool:
        return bool(self._get_startup_phase_attr("reveal_pending"))

    @_startup_reveal_pending.setter
    def _startup_reveal_pending(self, value: bool) -> None:
        self._set_startup_phase_attr("reveal_pending", bool(value))

    @property
    def _startup_reveal_token(self) -> int:
        return int(self._get_startup_phase_attr("reveal_token"))

    @_startup_reveal_token.setter
    def _startup_reveal_token(self, value: int) -> None:
        self._set_startup_phase_attr("reveal_token", int(value))

    @property
    def _startup_reveal_ready_token(self) -> int:
        return int(self._get_startup_phase_attr("reveal_ready_token"))

    @_startup_reveal_ready_token.setter
    def _startup_reveal_ready_token(self, value: int) -> None:
        self._set_startup_phase_attr("reveal_ready_token", int(value))

    @property
    def _startup_wake_deferred(self) -> bool:
        return bool(self._get_startup_phase_attr("wake_deferred"))

    @_startup_wake_deferred.setter
    def _startup_wake_deferred(self, value: bool) -> None:
        self._set_startup_phase_attr("wake_deferred", bool(value))

    @property
    def _startup_wake_deferred_reason(self) -> str:
        return str(self._get_startup_phase_attr("wake_deferred_reason") or "")

    @_startup_wake_deferred_reason.setter
    def _startup_wake_deferred_reason(self, value: str) -> None:
        self._set_startup_phase_attr("wake_deferred_reason", str(value or ""))

    @property
    def _startup_require_playing_before_reveal(self) -> bool:
        return bool(self._get_startup_phase_attr("require_playing_before_reveal"))

    @_startup_require_playing_before_reveal.setter
    def _startup_require_playing_before_reveal(self, value: bool) -> None:
        self._set_startup_phase_attr("require_playing_before_reveal", bool(value))

    @property
    def _startup_idle_reveal_requires_authoritative_media(self) -> bool:
        return bool(self._get_startup_phase_attr("idle_reveal_requires_authoritative_media"))

    @_startup_idle_reveal_requires_authoritative_media.setter
    def _startup_idle_reveal_requires_authoritative_media(self, value: bool) -> None:
        self._set_startup_phase_attr("idle_reveal_requires_authoritative_media", bool(value))

    @property
    def _startup_has_authoritative_media_update(self) -> bool:
        return bool(self._get_startup_phase_attr("has_authoritative_media_update"))

    @_startup_has_authoritative_media_update.setter
    def _startup_has_authoritative_media_update(self, value: bool) -> None:
        self._set_startup_phase_attr("has_authoritative_media_update", bool(value))

    @property
    def _startup_min_reveal_delay_ms(self) -> int:
        return int(self._get_startup_phase_attr("min_reveal_delay_ms"))

    @_startup_min_reveal_delay_ms.setter
    def _startup_min_reveal_delay_ms(self, value: int) -> None:
        self._set_startup_phase_attr("min_reveal_delay_ms", int(value))

    @property
    def _startup_reveal_watchdog_ms(self) -> int:
        return int(self._get_startup_phase_attr("reveal_watchdog_ms"))

    @_startup_reveal_watchdog_ms.setter
    def _startup_reveal_watchdog_ms(self, value: int) -> None:
        self._set_startup_phase_attr("reveal_watchdog_ms", int(value))

    @property
    def _startup_reveal_not_before_ts(self) -> float:
        return float(self._get_startup_phase_attr("reveal_not_before_ts"))

    @_startup_reveal_not_before_ts.setter
    def _startup_reveal_not_before_ts(self, value: float) -> None:
        self._set_startup_phase_attr("reveal_not_before_ts", float(value))

    def _replay_engine_config(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        from widgets.spotify_visualizer.config_applier import replay_engine_config
        replay_engine_config(self, engine)

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        from widgets.spotify_visualizer.runtime_config import set_thread_manager

        set_thread_manager(self, thread_manager)

    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        from widgets.spotify_visualizer.runtime_config import set_process_supervisor

        set_process_supervisor(self, supervisor)

    def apply_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        from widgets.spotify_visualizer.runtime_config import apply_floor_config

        apply_floor_config(self, dynamic_enabled, manual_floor)

    # Backwards-compat alias for legacy callers/tests
    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        self.apply_floor_config(dynamic_enabled, manual_floor)

    def apply_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        from widgets.spotify_visualizer.runtime_config import apply_sensitivity_config

        apply_sensitivity_config(self, recommended, sensitivity)

    def _apply_energy_boost(self, boost: float) -> None:
        from widgets.spotify_visualizer.runtime_config import apply_energy_boost

        apply_energy_boost(self, boost)

    def _apply_input_gain(self, gain: float) -> None:
        from widgets.spotify_visualizer.runtime_config import apply_input_gain

        apply_input_gain(self, gain)

    def _apply_agc_strength(self, value: float) -> None:
        from widgets.spotify_visualizer.runtime_config import apply_agc_strength

        apply_agc_strength(self, value)

    @staticmethod
    def _compute_energy_boost(enabled: bool) -> float:
        from widgets.spotify_visualizer.runtime_config import compute_energy_boost

        return compute_energy_boost(enabled)

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
            'blob': VisualizerMode.BLOB,
            'sine_wave': VisualizerMode.SINE_WAVE,
            'bubble': VisualizerMode.BUBBLE,
            'devcurve': VisualizerMode.DEVCURVE,
        }
        vm = mode_map.get(str(mode).lower(), VisualizerMode.SPECTRUM)
        mode_changed = vm != self._vis_mode
        if mode_changed:
            self._vis_mode = vm

        from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
        apply_vis_mode_kwargs(self, kwargs)
        mode_key = vm.name.lower()
        replaced_runtime_technical = self._replace_runtime_technical_overrides(mode_key, kwargs)

        try:
            self._cached_vis_kwargs = copy.deepcopy(kwargs)
        except Exception:
            self._cached_vis_kwargs = dict(kwargs)

        # Settings refreshes and runtime switches both apply the target
        # mode before resetting engine/overlay state. That keeps the settings
        # round-trip path and direct switch path from diverging.
        self._last_gpu_geom = None
        self._last_gpu_fade_sent = -1.0
        self._has_pushed_first_frame = False
        self._mode_transition_apply_height_on_resume = True

        if self._mode_transition_phase == 0:
            self._apply_pending_mode_transition_layout()

        if replaced_runtime_technical:
            self._apply_technical_config_for_mode(vm, reason="vis_mode_config")

        if mode_changed:
            self._waiting_for_fresh_engine_frame = True
            self._waiting_for_fresh_frame = True
            self._reset_mode_owned_runtime_state(reason="vis_mode_config")
            self._clear_gl_overlay()
            self._prepare_engine_for_mode_reset()
            self._clear_runtime_bar_state()

        logger.debug("[SPOTIFY_VIS] Applied vis mode config: mode=%s", mode)

    @property
    def _vis_mode_str(self) -> str:
        return self._vis_mode.name.lower()

    def set_settings_model(self, model: SpotifyVisualizerSettings, *, apply_now: bool = True) -> None:
        from widgets.spotify_visualizer.activation_runtime import set_settings_model

        set_settings_model(self, model, apply_now=apply_now)

    def _extract_technical_config_from_kwargs(
        self,
        mode_key: str,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        from widgets.spotify_visualizer.technical_config import extract_technical_config_from_kwargs

        return extract_technical_config_from_kwargs(self, mode_key, kwargs)

    def _replace_runtime_technical_overrides(
        self,
        mode_key: str,
        kwargs: Dict[str, Any],
    ) -> bool:
        from widgets.spotify_visualizer.technical_config import replace_runtime_technical_overrides

        return replace_runtime_technical_overrides(self, mode_key, kwargs)

    def _map_mode_key_to_enum(self, mode_key: str) -> VisualizerMode:
        from widgets.spotify_visualizer.technical_config import map_mode_key_to_enum

        return map_mode_key_to_enum(mode_key)

    def _sync_active_mode_legacy_ghost_bridge(self, mode: VisualizerMode) -> None:
        from widgets.spotify_visualizer.technical_config import sync_active_mode_legacy_ghost_bridge

        sync_active_mode_legacy_ghost_bridge(self, mode)

    def _log_live_activation_state(
        self,
        mode: VisualizerMode,
        payload: VisualizerActivationPayload,
        *,
        reason: str,
    ) -> None:
        from widgets.spotify_visualizer.activation_runtime import log_live_activation_state

        log_live_activation_state(self, mode, payload, reason=reason)

    def _log_active_render_state_snapshot(self, *, reason: str) -> None:
        """Log active-mode render state snapshot for bleed diagnosis."""
        try:
            mode = self._vis_mode
            mode_str = mode.name.lower()
            
            # Preset info from settings model
            sm = getattr(self, "_settings_model", None)
            preset_index = getattr(sm, "preset_index", -1) if sm else -1
            preset_kind = "custom" if (sm and getattr(sm, "is_custom", False)) else "curated" if sm else "unknown"
            
            # Bar/energy array summaries
            display_bars = getattr(self, "_display_bars", [])
            target_bars = getattr(self, "_target_bars", [])
            visual_bars = getattr(self, "_visual_bars", [])
            per_bar_energy = getattr(self, "_per_bar_energy", [])
            
            display_max = max(display_bars) if display_bars else 0.0
            display_avg = sum(display_bars) / len(display_bars) if display_bars else 0.0
            target_max = max(target_bars) if target_bars else 0.0
            target_avg = sum(target_bars) / len(target_bars) if target_bars else 0.0
            visual_max = max(visual_bars) if visual_bars else 0.0
            visual_avg = sum(visual_bars) / len(visual_bars) if visual_bars else 0.0
            energy_max = max(per_bar_energy) if per_bar_energy else 0.0
            energy_avg = sum(per_bar_energy) / len(per_bar_energy) if per_bar_energy else 0.0
            
            # Source tracking fields
            display_source_gen = getattr(self, "_display_bars_source_generation", -1)
            display_source_act = getattr(self, "_display_bars_source_activation", -1)
            target_source_gen = getattr(self, "_target_bars_source_generation", -1)
            target_source_act = getattr(self, "_target_bars_source_activation", -1)
            visual_source_gen = getattr(self, "_visual_bars_source_generation", -1)
            visual_source_act = getattr(self, "_visual_bars_source_activation", -1)
            energy_source_gen = getattr(self, "_per_bar_energy_source_generation", -1)
            energy_source_act = getattr(self, "_per_bar_energy_source_activation", -1)
            
            # Engine generation/activation
            engine = getattr(self, "_engine", None)
            engine_generation = getattr(engine, "get_generation_id", lambda: -1)() if engine else -1
            engine_activation = getattr(engine, "get_activation_id", lambda: -1)() if engine else -1
            
            # Overlay activation/generation ids
            overlay = getattr(self.parent(), "_spotify_bars_overlay", None) if self.parent() is not None else None
            overlay_activation = getattr(overlay, "_activation_id", None) if overlay else None
            overlay_generation = getattr(overlay, "_engine_generation", None) if overlay else None
            
            # Mode-specific fields
            if mode_str == "spectrum":
                spectrum_glow = getattr(self, "_spectrum_glow_enabled", False)
                spectrum_glow_intensity = getattr(self, "_spectrum_glow_intensity", 0.0)
                spectrum_mirrored = getattr(self, "_spectrum_mirrored", False)
                spectrum_growth = getattr(self, "_spectrum_growth", 1.0)
                
                # Hash for shape nodes
                shape_nodes = getattr(self, "_spectrum_shape_nodes", [])
                shape_hash = hash(str(shape_nodes)) if shape_nodes else 0
                
                logger.info(
                    "[SPOTIFY_VIS][RENDER_STATE] reason=%s mode=%s preset=%s:%d bars=%d "
                    "display_max=%.3f display_avg=%.3f target_max=%.3f target_avg=%.3f "
                    "visual_max=%.3f visual_avg=%.3f energy_max=%.3f energy_avg=%.3f "
                    "spectrum_glow=%s spectrum_glow_intensity=%.3f spectrum_mirrored=%s "
                    "spectrum_growth=%.3f shape_hash=%s "
                    "engine_generation=%s engine_activation=%s "
                    "display_source_generation=%s display_source_activation=%s "
                    "target_source_generation=%s target_source_activation=%s "
                    "visual_source_generation=%s visual_source_activation=%s "
                    "energy_source_generation=%s energy_source_activation=%s "
                    "overlay_activation=%s overlay_generation=%s",
                    reason, mode_str, preset_kind, preset_index, len(display_bars),
                    display_max, display_avg, target_max, target_avg,
                    visual_max, visual_avg, energy_max, energy_avg,
                    spectrum_glow, spectrum_glow_intensity, spectrum_mirrored,
                    spectrum_growth, shape_hash,
                    engine_generation, engine_activation,
                    display_source_gen, display_source_act,
                    target_source_gen, target_source_act,
                    visual_source_gen, visual_source_act,
                    energy_source_gen, energy_source_act,
                    overlay_activation, overlay_generation,
                )
            elif mode_str == "devcurve":
                devcurve_growth = getattr(self, "_devcurve_growth", 1.0)
                devcurve_base_level = getattr(self, "_devcurve_base_level", 0.58)
                devcurve_smoothness = getattr(self, "_devcurve_smoothness", 0.5)
                
                logger.info(
                    "[SPOTIFY_VIS][RENDER_STATE] reason=%s mode=%s preset=%s:%d bars=%d "
                    "display_max=%.3f display_avg=%.3f target_max=%.3f target_avg=%.3f "
                    "visual_max=%.3f visual_avg=%.3f energy_max=%.3f energy_avg=%.3f "
                    "devcurve_growth=%.3f devcurve_base_level=%.3f devcurve_smoothness=%.3f "
                    "engine_generation=%s engine_activation=%s "
                    "display_source_generation=%s display_source_activation=%s "
                    "target_source_generation=%s target_source_activation=%s "
                    "visual_source_generation=%s visual_source_activation=%s "
                    "energy_source_generation=%s energy_source_activation=%s "
                    "overlay_activation=%s overlay_generation=%s",
                    reason, mode_str, preset_kind, preset_index, len(display_bars),
                    display_max, display_avg, target_max, target_avg,
                    visual_max, visual_avg, energy_max, energy_avg,
                    devcurve_growth, devcurve_base_level, devcurve_smoothness,
                    engine_generation, engine_activation,
                    display_source_gen, display_source_act,
                    target_source_gen, target_source_act,
                    visual_source_gen, visual_source_act,
                    energy_source_gen, energy_source_act,
                    overlay_activation, overlay_generation,
                )
            else:
                logger.info(
                    "[SPOTIFY_VIS][RENDER_STATE] reason=%s mode=%s preset=%s:%d bars=%d "
                    "display_max=%.3f display_avg=%.3f target_max=%.3f target_avg=%.3f "
                    "visual_max=%.3f visual_avg=%.3f energy_max=%.3f energy_avg=%.3f "
                    "engine_generation=%s engine_activation=%s "
                    "display_source_generation=%s display_source_activation=%s "
                    "target_source_generation=%s target_source_activation=%s "
                    "visual_source_generation=%s visual_source_activation=%s "
                    "energy_source_generation=%s energy_source_activation=%s "
                    "overlay_activation=%s overlay_generation=%s",
                    reason, mode_str, preset_kind, preset_index, len(display_bars),
                    display_max, display_avg, target_max, target_avg,
                    visual_max, visual_avg, energy_max, energy_avg,
                    engine_generation, engine_activation,
                    display_source_gen, display_source_act,
                    target_source_gen, target_source_act,
                    visual_source_gen, visual_source_act,
                    energy_source_gen, energy_source_act,
                    overlay_activation, overlay_generation,
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to log render state snapshot", exc_info=True)

    def apply_resolved_activation_payload(
        self,
        model: SpotifyVisualizerSettings,
        payload: VisualizerActivationPayload,
        *,
        reason: str,
        force_runtime_reset: bool = False,
    ) -> None:
        """Apply one canonical resolved activation payload to the live widget."""
        from widgets.spotify_visualizer.activation_runtime import apply_resolved_activation_payload

        apply_resolved_activation_payload(
            self,
            model,
            payload,
            reason=reason,
            force_runtime_reset=force_runtime_reset,
        )

    def _build_technical_cache(self, model: SpotifyVisualizerSettings) -> Dict[str, Dict[str, Any]]:
        from widgets.spotify_visualizer.technical_config import build_technical_cache

        return build_technical_cache(self, model)

    def _get_mode_technical_config(self, mode: VisualizerMode) -> Optional[Dict[str, Any]]:
        from widgets.spotify_visualizer.technical_config import get_mode_technical_config

        return get_mode_technical_config(self, mode)

    def _apply_technical_config_for_mode(self, mode: VisualizerMode, *, reason: str) -> None:
        from widgets.spotify_visualizer.technical_config import apply_technical_config_for_mode

        apply_technical_config_for_mode(self, mode, reason=reason)

    def _apply_full_runtime_config_for_mode(self, mode: VisualizerMode, *, reason: str) -> None:
        """Replay the same target-mode config used by a settings refresh."""
        from widgets.spotify_visualizer.activation_runtime import apply_full_runtime_config_for_mode

        apply_full_runtime_config_for_mode(self, mode, reason=reason)

    def _clear_runtime_bar_state(self) -> None:
        from widgets.spotify_visualizer.runtime_config import clear_runtime_bar_state

        clear_runtime_bar_state(self)

    def _apply_audio_block_size(self, block_size: int) -> None:
        from widgets.spotify_visualizer.runtime_config import apply_audio_block_size

        apply_audio_block_size(self, block_size)

    def _resize_bar_buffers(self, new_bar_count: int) -> None:
        from widgets.spotify_visualizer.runtime_config import resize_bar_buffers

        resize_bar_buffers(self, new_bar_count)

    def _bind_engine_aliases(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        from widgets.spotify_visualizer.runtime_config import bind_engine_aliases

        bind_engine_aliases(self, engine)

    def get_preferred_height(self) -> int:
        """Return the ideal card height for the current visualizer mode."""
        from widgets.spotify_visualizer.card_geometry import (
            build_growth_map_from_widget,
            resolve_card_metrics,
        )

        metrics = resolve_card_metrics(
            self._vis_mode_str,
            self._base_height,
            build_growth_map_from_widget(self),
        )
        return metrics.preferred_height

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
            custom_active = self._is_custom_layout_active()
            if media is None and custom_active:
                media = getattr(self, "_anchor_media", None)
            if media is not None or custom_active:
                wm.position_spotify_visualizer(self, media, pw, ph)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Reposition after mode switch failed", exc_info=True)

    def _active_custom_layout_rect(self) -> Optional[QRect]:
        if bool(getattr(self, "_custom_layout_shell_active", False)):
            return None
        custom_rect = getattr(self, "_custom_layout_local_rect", None)
        if not isinstance(custom_rect, QRect):
            return None
        if custom_rect.width() <= 0 or custom_rect.height() <= 0:
            return None
        return QRect(custom_rect)

    def _resolve_gpu_target_rect(self) -> Optional[QRect]:
        """Return the authoritative outer rect for GPU/overlay geometry work."""

        custom_rect = self._resolve_runtime_custom_layout_rect()
        if custom_rect is not None:
            return custom_rect
        try:
            return QRect(self.geometry())
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to resolve GPU target rect", exc_info=True)
            return None

    def _resolve_runtime_custom_layout_rect(self) -> Optional[QRect]:
        """Resolve the committed CUSTOM rect against the current parent bounds."""

        custom_rect = self._active_custom_layout_rect()
        if custom_rect is None:
            return None
        try:
            parent = self.parent()
            if parent is None:
                return QRect(custom_rect)
            from widgets.spotify_visualizer.card_geometry import resolve_custom_card_rect

            resolved = resolve_custom_card_rect(
                custom_rect,
                parent_width=int(parent.width()),
                parent_height=int(parent.height()),
                size=custom_rect.size(),
            )
            if resolved.width() > 0 and resolved.height() > 0:
                return resolved
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to resolve runtime CUSTOM visualizer rect", exc_info=True)
        return QRect(custom_rect)

    def _apply_custom_layout_size_constraints_if_active(self) -> bool:
        """Lock the visualizer's QWidget min/max size to the committed CUSTOM rect."""

        custom_rect = self._active_custom_layout_rect()
        if custom_rect is None:
            return False
        try:
            if self._custom_layout_constraint_restore is None:
                self._custom_layout_constraint_restore = (
                    int(self.minimumWidth()),
                    int(self.maximumWidth()),
                    int(self.minimumHeight()),
                    int(self.maximumHeight()),
                )
            QWidget.setMinimumWidth(self, int(custom_rect.width()))
            QWidget.setMaximumWidth(self, int(custom_rect.width()))
            QWidget.setMinimumHeight(self, int(custom_rect.height()))
            QWidget.setMaximumHeight(self, int(custom_rect.height()))
            return True
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to lock CUSTOM size constraints", exc_info=True)
            return False

    def _restore_custom_layout_size_constraints(self) -> None:
        """Restore authored min/max size constraints after CUSTOM authority ends."""

        restore = self._custom_layout_constraint_restore
        self._custom_layout_constraint_restore = None
        if restore is None:
            return
        try:
            min_w, max_w, min_h, max_h = restore
            QWidget.setMinimumWidth(self, int(min_w))
            QWidget.setMaximumWidth(self, int(max_w))
            QWidget.setMinimumHeight(self, int(min_h))
            QWidget.setMaximumHeight(self, int(max_h))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to restore authored size constraints", exc_info=True)

    def _is_custom_layout_active(self) -> bool:
        """Return whether a committed CUSTOM layout currently owns geometry."""

        try:
            return self._active_custom_layout_rect() is not None
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to evaluate CUSTOM layout ownership", exc_info=True)
            return False

    def _is_custom_layout_route_selected(self) -> bool:
        """Return whether the visualizer is currently routed through the CUSTOM slot."""

        try:
            wm = getattr(self, "_widget_manager", None)
            sm = getattr(wm, "_settings_manager", None) if wm is not None else None
            if sm is None:
                return False
            widgets_config = sm.get_widgets_map()
            if not isinstance(widgets_config, Mapping):
                return False
            from rendering.widget_descriptors import is_custom_position_selected_for_widget

            return bool(is_custom_position_selected_for_widget("spotify_visualizer", widgets_config))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to evaluate CUSTOM routing selection", exc_info=True)
            return False

    def _resolve_custom_locked_width(self, width: int) -> int:
        custom_rect = self._active_custom_layout_rect()
        if custom_rect is None:
            return int(width)
        return int(custom_rect.width())

    def _resolve_custom_locked_height(self, height: int) -> int:
        custom_rect = self._active_custom_layout_rect()
        if custom_rect is None:
            return int(height)
        return int(custom_rect.height())

    def setGeometry(self, *args) -> None:  # type: ignore[override]
        runtime_custom_rect = self._resolve_runtime_custom_layout_rect()
        if runtime_custom_rect is not None:
            QWidget.setGeometry(self, runtime_custom_rect)
            return
        super().setGeometry(*args)

    def setMinimumWidth(self, minw: int) -> None:  # type: ignore[override]
        if self._apply_custom_layout_size_constraints_if_active():
            return
        super().setMinimumWidth(self._resolve_custom_locked_width(minw))

    def setMaximumWidth(self, maxw: int) -> None:  # type: ignore[override]
        if self._apply_custom_layout_size_constraints_if_active():
            return
        super().setMaximumWidth(self._resolve_custom_locked_width(maxw))

    def setMinimumHeight(self, minh: int) -> None:  # type: ignore[override]
        if self._apply_custom_layout_size_constraints_if_active():
            return
        super().setMinimumHeight(self._resolve_custom_locked_height(minh))

    def setMaximumHeight(self, maxh: int) -> None:  # type: ignore[override]
        if self._apply_custom_layout_size_constraints_if_active():
            return
        super().setMaximumHeight(self._resolve_custom_locked_height(maxh))

    def _apply_preferred_height(self) -> None:
        """Resize the widget to match the preferred height for the current mode.

        For spectrum/oscilloscope (growth=1.0), we explicitly shrink the
        widget back to base_height so the positioning system doesn't keep
        a stale tall height from an expanded mode (blob/bubble).
        For expanded modes we set a minimum height from the growth factor.
        """
        from widgets.spotify_visualizer.card_geometry import (
            build_growth_map_from_widget,
            resolve_card_metrics,
        )

        if self._is_custom_layout_active() or self._is_custom_layout_route_selected():
            logger.debug(
                "[SPOTIFY_VIS] Deferring preferred-height resize to WidgetManager while CUSTOM layout is active"
            )
            return

        mode = self._vis_mode_str
        metrics = resolve_card_metrics(
            mode,
            self._base_height,
            build_growth_map_from_widget(self),
        )
        if metrics.force_base_height:
            base = self._base_height
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            current = self.height()
            if current > base:
                self.resize(self.width(), base)
                logger.debug("[SPOTIFY_VIS] Card height shrunk: %d -> %d (mode=%s)", current, base, mode)
            return
        h = metrics.preferred_height
        current = self.height()
        if current != h:
            self.setMinimumHeight(h)
            self.setMaximumHeight(16777215)  # allow positioning system to grow
            self.resize(self.width(), h)
            logger.debug("[SPOTIFY_VIS] Card height set: %d -> %d (mode=%s)", current, h, mode)

    def attach_to_animation_manager(self, animation_manager) -> None:
        from widgets.spotify_visualizer.tick_helpers import attach_to_animation_manager

        attach_to_animation_manager(self, animation_manager)

    def _enable_animation_tick_listener(self) -> None:
        from widgets.spotify_visualizer.tick_helpers import enable_animation_tick_listener

        enable_animation_tick_listener(self)

    def _disable_animation_tick_listener(self) -> None:
        from widgets.spotify_visualizer.tick_helpers import disable_animation_tick_listener

        disable_animation_tick_listener(self)

    def detach_from_animation_manager(self) -> None:
        from widgets.spotify_visualizer.tick_helpers import detach_from_animation_manager

        detach_from_animation_manager(self)

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
            big_specular_max_size=pulse_params.get('big_specular_max_size', 2.5),
            big_contraction_bias=pulse_params.get('big_contraction_bias', 1.0),
            big_size_clamp=pulse_params.get('big_size_clamp', 4.0),
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
        """Delegates to widgets.spotify_visualizer.tick_helpers."""
        from widgets.spotify_visualizer.tick_helpers import ensure_tick_source

        ensure_tick_source(self)

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config
        self._painted_frame_shadow_enabled = shadow_config_enabled(config, "enabled", True)
        self._invalidate_painted_frame_shadow_cache()
        self._update_card_style()
        self.update()

    def _update_card_style(self) -> None:
        from widgets.spotify_visualizer.card_paint import update_card_style
        update_card_style(self)

    def set_bar_style(self, *, bg_color: QColor, bg_opacity: float, border_color: QColor, border_width: Optional[int] = None,
                      show_background: bool = True) -> None:
        self._bg_color = QColor(bg_color)
        self._bg_opacity = max(0.0, min(1.0, float(bg_opacity)))
        self._card_border_color = QColor(border_color)
        resolved_width = BaseOverlayWidget.get_global_border_width() if border_width is None else int(border_width)
        self._border_width = max(0, resolved_width)
        self._show_background = bool(show_background)
        self._invalidate_painted_frame_shadow_cache()
        self._update_card_style()
        self.update()

    def uses_painted_frame_shadow(self) -> bool:
        return bool(self._painted_frame_shadow_enabled and self._show_background)

    def _invalidate_painted_frame_shadow_cache(self) -> None:
        self._painted_frame_shadow_pixmap = None
        self._painted_frame_shadow_cache_key = None

    def _painted_frame_shadow_card_rect(self) -> QRectF:
        from widgets.spotify_visualizer.card_paint import painted_frame_shadow_card_rect
        return painted_frame_shadow_card_rect(self)

    def _ensure_painted_frame_shadow_pixmap(self) -> Optional[QPixmap]:
        from widgets.spotify_visualizer.card_paint import ensure_painted_frame_shadow_pixmap
        return ensure_painted_frame_shadow_pixmap(self)

    def _paint_painted_frame_shadow(self) -> None:
        from widgets.spotify_visualizer.card_paint import paint_painted_frame_shadow
        paint_painted_frame_shadow(self)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._invalidate_painted_frame_shadow_cache()
        super().resizeEvent(event)

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

    @staticmethod
    def _media_info_to_payload(info: object) -> Optional[dict]:
        from widgets.spotify_visualizer.media_bridge import media_info_to_payload
        return media_info_to_payload(info)

    def _seed_playback_state_from_anchor(self, *, reason: str, request_refresh_if_missing: bool) -> bool:
        from widgets.spotify_visualizer.media_bridge import seed_playback_state_from_anchor
        return seed_playback_state_from_anchor(self, reason=reason, request_refresh_if_missing=request_refresh_if_missing)

    def handle_media_update(self, payload: dict, **kwargs) -> None:
        from widgets.spotify_visualizer.media_bridge import handle_media_update
        handle_media_update(self, payload, **kwargs)

    def sync_visibility_with_anchor(self) -> None:
        from widgets.spotify_visualizer.media_bridge import sync_visibility_with_anchor
        sync_visibility_with_anchor(self)

    def _destroy_parent_overlay(self, *, reason: str) -> None:
        from widgets.spotify_visualizer.media_bridge import destroy_parent_overlay
        destroy_parent_overlay(self, reason=reason)

    def _request_overlay_mode_reset(self, *, mode: Optional[str] = None, reason: str = "widget_reset") -> None:
        from widgets.spotify_visualizer.media_bridge import request_overlay_mode_reset
        request_overlay_mode_reset(self, mode=mode, reason=reason)

    def _reset_engine_state(self, *, reason: str) -> None:
        from widgets.spotify_visualizer.engine_lifecycle import reset_engine_state
        reset_engine_state(self, reason=reason)

    def reset_runtime_activation_state(self, *, reason: str = "activation") -> None:
        from widgets.spotify_visualizer.engine_lifecycle import reset_runtime_activation_state
        reset_runtime_activation_state(self, reason=reason)

    def _reset_mode_owned_runtime_state(self, *, reason: str = "activation") -> None:
        from widgets.spotify_visualizer.mode_transition import reset_mode_owned_runtime_state
        reset_mode_owned_runtime_state(self, reason=reason)

    def _should_capture_audio_now(self) -> bool:
        from widgets.spotify_visualizer.engine_lifecycle import should_capture_audio_now
        return should_capture_audio_now(self)

    def _track_engine_generation(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        from widgets.spotify_visualizer.engine_lifecycle import track_engine_generation
        track_engine_generation(self, engine)

    def _handle_mode_cycle_state_reset(self) -> None:
        from widgets.spotify_visualizer.engine_lifecycle import handle_mode_cycle_state_reset
        handle_mode_cycle_state_reset(self)

    def _clear_gl_overlay(self) -> None:
        from widgets.spotify_visualizer.engine_lifecycle import clear_gl_overlay
        clear_gl_overlay(self)

    def _is_media_state_stale(self) -> bool:
        from widgets.spotify_visualizer.engine_lifecycle import is_media_state_stale
        return is_media_state_stale(self)

    def _has_audio_activity(self, bars: List[float], raw_bars: Optional[List[float]] = None) -> bool:
        from widgets.spotify_visualizer.engine_lifecycle import has_audio_activity
        return has_audio_activity(self, bars, raw_bars)

    def _is_fallback_forced(self) -> bool:
        from widgets.spotify_visualizer.engine_lifecycle import is_fallback_forced
        return is_fallback_forced(self)

    def _update_fallback_force_state(self, audio_active: bool) -> None:
        from widgets.spotify_visualizer.engine_lifecycle import update_fallback_force_state
        update_fallback_force_state(self, audio_active)

    def _trigger_wake(self, *, reason: str = "unspecified", allow_defer: bool = True) -> None:
        from widgets.spotify_visualizer.engine_lifecycle import trigger_wake
        trigger_wake(self, reason=reason, allow_defer=allow_defer)

    # ------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # ------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize visualizer resources (lifecycle hook)."""
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget initialized")

    def _is_anchor_visible(self) -> bool:
        from widgets.spotify_visualizer.startup_staging import is_anchor_visible
        return is_anchor_visible(self)

    def _cancel_pending_startup_reveal(self) -> None:
        from widgets.spotify_visualizer.startup_staging import cancel_pending_startup_reveal
        cancel_pending_startup_reveal(self)

    def _ensure_spotify_secondary_stage_registration(self) -> None:
        from widgets.spotify_visualizer.startup_staging import ensure_spotify_secondary_stage_registration
        ensure_spotify_secondary_stage_registration(self)

    def _is_parent_secondary_stage_ready(self) -> bool:
        from widgets.spotify_visualizer.startup_staging import is_parent_secondary_stage_ready
        return is_parent_secondary_stage_ready(self)

    def _prewarm_parent_overlay(self) -> None:
        from widgets.spotify_visualizer.startup_staging import prewarm_parent_overlay
        prewarm_parent_overlay(self)

    def _finish_staged_startup_reveal(self, *, reason: str) -> None:
        from widgets.spotify_visualizer.startup_staging import finish_staged_startup_reveal
        finish_staged_startup_reveal(self, reason=reason)

    def _schedule_ready_driven_startup_reveal(self, *, delay_ms: int) -> None:
        from widgets.spotify_visualizer.startup_staging import schedule_ready_driven_startup_reveal
        schedule_ready_driven_startup_reveal(self, delay_ms=delay_ms)

    def _schedule_startup_reveal_watchdog(self) -> None:
        from widgets.spotify_visualizer.startup_staging import schedule_startup_reveal_watchdog
        schedule_startup_reveal_watchdog(self)

    def _mode_allows_idle_reveal(self) -> bool:
        from widgets.spotify_visualizer.startup_staging import mode_allows_idle_reveal
        return mode_allows_idle_reveal(self)

    def _arm_staged_startup(self, *, reason: str) -> None:
        from widgets.spotify_visualizer.startup_staging import arm_staged_startup
        arm_staged_startup(self, reason=reason)

    def _begin_hot_start(self, *, reason: str, reset_reason: str) -> None:
        from widgets.spotify_visualizer.startup_staging import begin_hot_start
        begin_hot_start(self, reason=reason, reset_reason=reset_reason)

    def begin_spotify_secondary_stage(self) -> None:
        from widgets.spotify_visualizer.startup_staging import begin_spotify_secondary_stage
        begin_spotify_secondary_stage(self)

    def _activate_impl(self) -> None:
        from widgets.spotify_visualizer.startup_staging import activate_impl
        activate_impl(self)

    def _deactivate_impl(self) -> None:
        from widgets.spotify_visualizer.startup_staging import deactivate_impl
        deactivate_impl(self)

    def _cleanup_impl(self) -> None:
        from widgets.spotify_visualizer.startup_staging import cleanup_impl
        cleanup_impl(self)

    # ------------------------------------------------------------------
    # Legacy Lifecycle Methods (for backward compatibility)
    # ------------------------------------------------------------------

    def start(self) -> None:
        from widgets.spotify_visualizer.startup_staging import start_legacy
        start_legacy(self)

    def stop(self) -> None:
        from widgets.spotify_visualizer.startup_staging import stop_legacy
        stop_legacy(self)

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

    def switch_to_mode(self, mode_id: str) -> bool:
        """Switch to a specific visualizer mode with a crossfade.

        Same transition path as _cycle_mode / double-click but targets
        a specific mode by registry mode_id (e.g. ``"spectrum"``).
        """
        from widgets.spotify_visualizer.mode_transition import switch_to_mode

        result = switch_to_mode(self, mode_id)
        if result:
            try:
                self._on_mode_cycle_requested()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Mode switch hook failed", exc_info=True)
            self._request_latency_probe("mode_switch")
        return result

    def handle_double_click(self, local_pos) -> bool:
        """Called by WidgetManager dispatch. Cycles visualizer mode."""
        return self._cycle_mode()

    def handle_mouse_button(self, button: Qt.MouseButton) -> bool:
        """Handle runtime preset cycling shortcuts from routed mouse clicks."""
        if button == Qt.MouseButton.MiddleButton:
            direction = 1
        elif button in (Qt.MouseButton.XButton1, Qt.MouseButton.BackButton):
            direction = -1
        else:
            return False

        wm = getattr(self, '_widget_manager', None)
        if wm is None or not hasattr(wm, 'cycle_visualizer_preset'):
            return False

        mode_key = str(getattr(self, '_vis_mode_str', 'spectrum') or 'spectrum')
        try:
            cycled = bool(wm.cycle_visualizer_preset(mode_key, direction))
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to cycle preset via WidgetManager", exc_info=True)
            return False
        if not cycled:
            return False

        self._reset_visualizer_state(clear_overlay=False, replay_cached=False)
        self._request_latency_probe("preset_cycle")
        return True

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click cycles visualizer mode with a crossfade."""
        if self._cycle_mode():
            event.accept()
        else:
            event.ignore()

    def mousePressEvent(self, event) -> None:
        """Handle preset-cycle shortcuts, otherwise forward to parent routing."""
        if self.handle_mouse_button(event.button()):
            event.accept()
            return
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

    def _start_widget_fade_in(self, duration_ms: Optional[int] = None) -> None:
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

    def _reset_latency_diagnostics(self) -> None:
        self._latency_pending_probe.clear()
        self._latency_last_signature = None
        self._latency_last_log_ts = 0.0
        self._latency_audio_ready = False
        self._latency_activation_started_ts = time.time()

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
        if self.uses_painted_frame_shadow():
            self._paint_painted_frame_shadow()
        else:
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

        # Visualizer content is GL-only. This QWidget paint path owns only the
        # card/background/shadow surface; bars and mode visuals are pushed to
        # the SpotifyBarsGLOverlay.
        painter.end()

    def set_visualization_mode(self, mode: VisualizerMode, *, reset_runtime: bool = True) -> None:
        """Set the visualization display mode."""
        from widgets.spotify_visualizer.mode_transition import activate_visualization_mode

        activate_visualization_mode(self, mode, reset_runtime=reset_runtime)

    def get_visualization_mode(self) -> VisualizerMode:
        """Get the current visualization display mode."""
        return self._vis_mode

    def cycle_visualization_mode(self) -> VisualizerMode:
        """Cycle to the next visualization mode and return it.

        Only cycles through modes whose dev gates are active.
        """
        from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

        _CYCLE_MODES = []
        for desc in iter_visualizer_mode_descriptors():
            member = getattr(VisualizerMode, desc.mode_id.upper(), None)
            if member is not None:
                _CYCLE_MODES.append(member)
        if not _CYCLE_MODES:
            return self._vis_mode
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



