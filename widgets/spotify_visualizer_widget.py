from __future__ import annotations

from typing import List, Optional, Dict, Any
import os
import time
import logging
import copy

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
from core.process import ProcessSupervisor
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile, configure_overlay_widget_attributes
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

try:
    _DEBUG_CONST_BARS = float(os.environ.get("SRPSS_SPOTIFY_VIS_DEBUG_CONST", "0.0"))
except Exception as e:
    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    _DEBUG_CONST_BARS = 0.0



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
        self._blob_reactive_glow: bool = True
        self._blob_reactive_deformation: float = 1.0
        self._blob_constant_wobble: float = 1.0
        self._blob_reactive_wobble: float = 1.0
        self._blob_stretch_tendency: float = 0.0

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
        self._sine_card_adaptation: float = 0.3  # 0.0-1.0, how much of card height wave uses
        self._sine_wave_effect: float = 0.0  # 0.0-1.0, wave-like positional effect
        self._sine_micro_wobble: float = 0.0  # 0.0-1.0, energy-reactive micro distortions
        self._sine_vertical_shift: int = 0  # -50 to 200, line spread amount
        self._sine_width_reaction: float = 0.0  # 0.0-1.0, bass-driven line width stretching
        self._sine_glow_enabled: bool = True
        self._sine_glow_intensity: float = 0.5
        self._sine_glow_color: QColor = QColor(0, 200, 255, 230)
        self._sine_line_color: QColor = QColor(255, 255, 255, 255)
        self._sine_reactive_glow: bool = True
        self._sine_sensitivity: float = 1.0
        self._sine_speed: float = 1.0
        self._sine_line_count: int = 1
        self._sine_line_offset_bias: float = 0.0
        self._sine_line_dim: bool = False
        self._sine_line2_color: QColor = QColor(255, 255, 255, 230)
        self._sine_line2_glow_color: QColor = QColor(7, 114, 255, 180)
        self._sine_line3_color: QColor = QColor(255, 255, 255, 230)
        self._sine_line3_glow_color: QColor = QColor(14, 159, 255, 180)

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
        self._heartbeat_last_ts: float = 0.0    # dedicated tick timestamp for dt_hb

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
        self._bubble_big_size_max: float = 0.038
        self._bubble_small_size_max: float = 0.018
        self._bubble_simulation: Optional[object] = None  # lazy init (owned by compute thread)
        self._bubble_pos_data: list = []
        self._bubble_extra_data: list = []
        self._bubble_trail_data: list = []
        self._bubble_trail_strength: float = 0.0
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
                # Test/diagnostic aliases – these reference shared state.
                self._bars_buffer = engine._audio_buffer  # type: ignore[attr-defined]
                self._audio_worker = engine._audio_worker  # type: ignore[attr-defined]
                self._bars_result_buffer = engine._bars_result_buffer  # type: ignore[attr-defined]
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
        self._mode_transition_phase: int = 0     # 0=idle, 1=fading out, 2=fading in
        self._mode_transition_duration: float = 0.25  # seconds per half (out/in)
        self._mode_transition_pending: Optional[VisualizerMode] = None

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
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate ThreadManager to shared beat engine", exc_info=True)

    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for worker integration."""
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
        self._apply_preferred_height()

        logger.debug("[SPOTIFY_VIS] Applied vis mode config: mode=%s", mode)

    @property
    def _vis_mode_str(self) -> str:
        return self._vis_mode.name.lower()

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

        if logger.isEnabledFor(logging.INFO):
            try:
                track = payload.get("track_name") or payload.get("title") or ""
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                track = ""
            logger.info(
                "[SPOTIFY_VIS] media_update state=%s -> playing=%s (prev=%s) track=%s",
                state or "<unset>",
                self._spotify_playing,
                prev,
                track,
            )

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
    
    def _clear_gl_overlay(self) -> None:
        """Clear the GL bars overlay when visualizer hides."""
        parent = self.parent()
        if parent is not None:
            # Clear the SpotifyBarsGLOverlay by pushing an invisible state
            overlay = getattr(parent, "_spotify_bars_overlay", None)
            if overlay is not None and hasattr(overlay, "set_state"):
                try:
                    from PySide6.QtCore import QRect
                    from PySide6.QtGui import QColor
                    overlay.set_state(
                        QRect(0, 0, 0, 0),
                        [],
                        0,
                        0,
                        QColor(0, 0, 0, 0),
                        QColor(0, 0, 0, 0),
                        0.0,
                        False,
                        visible=False,
                    )
                    # Force overlay to repaint to clear any artifacts
                    if hasattr(overlay, 'update'):
                        overlay.update()
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            
            # Request parent repaint to ensure artifacts are cleared
            if hasattr(parent, 'update'):
                parent.update()
        
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
                    logger.info(
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
        try:
            parent = self.parent()
            overlay = getattr(parent, "_spotify_bars_overlay", None) if parent else None
            if overlay is not None and hasattr(overlay, "cleanup_gl"):
                overlay.cleanup_gl()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed during GL cleanup: %s", e)
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
        return cycle_mode(self)

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
        """Clear runtime visualizer state so the next mode behaves like a cold start."""
        zeros = [0.0] * self._bar_count
        self._display_bars = list(zeros)
        self._target_bars = list(zeros)
        self._visual_bars = list(zeros)
        self._per_bar_energy = list(zeros)
        self._geom_cache_rect = None
        self._geom_cache_bar_count = self._bar_count
        self._geom_cache_segments = self._bar_segments_base
        self._geom_bar_x = []
        self._geom_seg_y = []
        self._geom_bar_width = 0
        self._geom_seg_height = 0
        self._last_update_ts = -1.0
        self._last_smooth_ts = 0.0
        self._has_pushed_first_frame = False
        self._last_gpu_geom = None
        self._last_gpu_fade_sent = -1.0
        self._mode_transition_ts = 0.0
        self._perf_tick_start_ts = None
        self._perf_tick_last_ts = None
        self._perf_tick_frame_count = 0
        self._perf_tick_min_dt = 0.0
        self._perf_tick_max_dt = 0.0
        self._perf_paint_start_ts = None
        self._perf_paint_last_ts = None
        self._perf_paint_frame_count = 0
        self._perf_paint_min_dt = 0.0
        self._perf_paint_max_dt = 0.0
        self._perf_audio_lag_last_ms = 0.0
        self._perf_audio_lag_min_ms = 0.0
        self._perf_audio_lag_max_ms = 0.0
        self._perf_last_log_ts = None
        self._last_tick_spike_log_ts = 0.0
        self._fallback_mismatch_start = 0.0
        self._fallback_forced_until = 0.0
        self._bubble_pos_data = []
        self._bubble_extra_data = []
        self._bubble_trail_data = []
        self._bubble_count = 0
        self._bubble_compute_pending = False
        self._bubble_last_tick_ts = 0.0
        self._heartbeat_intensity = 0.0
        self._heartbeat_avg_bass = 0.0
        self._heartbeat_last_ts = 0.0
        if clear_overlay:
            self._clear_gl_overlay()
        if replay_cached and self._cached_vis_kwargs:
            from widgets.spotify_visualizer.config_applier import apply_vis_mode_kwargs
            try:
                apply_vis_mode_kwargs(self, copy.deepcopy(self._cached_vis_kwargs))
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to replay cached settings during reset", exc_info=True)

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        if duration_ms <= 0:
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            try:
                ShadowFadeProfile.attach_shadow(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to attach shadow in no-fade path",
                    exc_info=True,
                )
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] _start_widget_fade_in fallback path triggered",
                exc_info=True,
            )
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception:
                    logger.debug(
                        "[SPOTIFY_VIS] Failed to apply widget shadow in fallback path",
                        exc_info=True,
                    )

    def _get_gpu_fade_factor(self, now_ts: float) -> float:
        """Return fade factor for GPU bars based on ShadowFadeProfile.

        We prefer the shared ShadowFadeProfile progress when available so that
        the GL overlay tracks the exact same curve. When no progress is
        present we fall back to 1.0 while the widget is visible.
        """

        try:
            prog = getattr(self, "_shadowfade_progress", None)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            prog = None

        if isinstance(prog, (float, int)):
            p = float(prog)
            if p <= 0.0:
                return 0.0
            if p >= 1.0:
                return 1.0

            # Clamp first, then apply a stronger delay so bars fade in well
            # after the card/shadow begin fading. This keeps practical sync
            # with ShadowFadeProfile while ensuring the bars clearly read as a
            # second wave rather than appearing fully formed too early.
            p = max(0.0, min(1.0, p))
            delay = 0.65
            if p <= delay:
                return 0.0
            t = (p - delay) / (1.0 - delay)
            # Slower cubic ease-in so the bar opacity builds gradually and
            # avoids a sudden pop once the delay has elapsed.
            t = t * t * t
            return max(0.0, min(1.0, t))

        # Fallback: when ShadowFadeProfile progress is unavailable, check if
        # the fade animation has completed (progress reached 1.0 at some point).
        # We track this via _shadowfade_completed flag to avoid returning 1.0
        # prematurely at startup before the fade animation begins.
        try:
            completed = getattr(self, "_shadowfade_completed", False)
            if completed and self.isVisible():
                return 1.0
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return 0.0

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

    def _on_tick(self) -> None:
        """Periodic UI tick - PERFORMANCE OPTIMIZED.

        Consumes the latest bar frame from the TripleBuffer and smoothly
        interpolates towards it for visual stability.
        
        FPS CAP: This method is called by both _bars_timer (60Hz) and
        AnimationManager tick listener (60-165Hz). We apply the FPS cap
        at the START to avoid doing any work when rate-limited.
        """
        _tick_entry_ts = time.time()
        
        # PERFORMANCE: Fast validity check without nested try/except
        if not Shiboken.isValid(self):
            if self._bars_timer is not None:
                self._bars_timer.stop()
                self._bars_timer = None
            self._enabled = False
            return

        if not self._enabled:
            return

        now_ts = time.time()
        parent = self.parent()
        transition_ctx = self._get_transition_context(parent)
        is_transition_active = transition_ctx.get("running", False)
        
        # PERFORMANCE: Pause dedicated timer during transitions when AnimationManager is active
        # This prevents timer contention that causes 50-100ms dt spikes
        self._pause_timer_during_transition(is_transition_active)
        
        max_fps = self._resolve_max_fps(transition_ctx)
        self._update_timer_interval(max_fps)

        min_dt = 1.0 / max_fps if max_fps > 0.0 else 0.0
        last = self._last_update_ts
        dt_since_last = 0.0
        if last >= 0.0:
            dt_since_last = now_ts - last
        if last >= 0.0 and dt_since_last < min_dt:
            # Rate limited - skip this tick entirely
            return
        
        self._last_update_ts = now_ts
        # Cap dt to avoid logging spikes after system sleep/resume
        # dt > 1s indicates system sleep, not a performance issue
        _dt_spike_max_reasonable_ms: float = 1000.0  # 1 second
        dt_for_spike_check = min(dt_since_last * 1000.0, _dt_spike_max_reasonable_ms)
        if dt_since_last * 1000.0 >= self._dt_spike_threshold_ms and dt_for_spike_check < _dt_spike_max_reasonable_ms:
            self._log_tick_spike(dt_since_last, transition_ctx)

        # PERFORMANCE: Inline PERF metrics with gap filtering
        if is_perf_metrics_enabled():
            if self._perf_tick_last_ts is not None:
                dt = now_ts - self._perf_tick_last_ts
                # Skip metrics for gaps >100ms (startup, widget paused/hidden).
                # Reset measurement window to avoid polluting duration/avg_fps
                # with startup spikes that aren't representative of runtime perf.
                if dt > 0.1:
                    self._perf_tick_start_ts = now_ts
                    self._perf_tick_min_dt = 0.0
                    self._perf_tick_max_dt = 0.0
                    self._perf_tick_frame_count = 0
                elif dt > 0.0:
                    if self._perf_tick_min_dt == 0.0 or dt < self._perf_tick_min_dt:
                        self._perf_tick_min_dt = dt
                    if dt > self._perf_tick_max_dt:
                        self._perf_tick_max_dt = dt
                    self._perf_tick_frame_count += 1
            else:
                self._perf_tick_start_ts = now_ts
            self._perf_tick_last_ts = now_ts

            # Periodic PERF snapshot
            if self._perf_last_log_ts is None or (now_ts - self._perf_last_log_ts) >= 5.0:
                self._log_perf_snapshot(reset=False)
                self._perf_last_log_ts = now_ts

        # PERFORMANCE: Get pre-smoothed bars from engine
        # Smoothing is now done on COMPUTE pool, not UI thread
        engine = self._engine
        if engine is None:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            # Sync smoothing settings to engine
            engine.set_smoothing(self._smoothing)
        
        changed = False
        if engine is not None:
            # Trigger engine tick (schedules audio processing + smoothing on COMPUTE pool)
            _engine_tick_start = time.time()
            engine.tick()
            _engine_tick_elapsed = (time.time() - _engine_tick_start) * 1000.0
            if _engine_tick_elapsed > 20.0 and is_perf_metrics_enabled():
                logger.warning("[PERF] [SPOTIFY_VIS] Slow engine.tick(): %.2fms", _engine_tick_elapsed)
            
            # Track audio lag for PERF logs
            if is_perf_metrics_enabled():
                last_audio_ts = getattr(engine, "_last_audio_ts", 0.0)
                if last_audio_ts > 0.0:
                    lag_ms = (now_ts - last_audio_ts) * 1000.0
                    self._perf_audio_lag_last_ms = lag_ms
                    if self._perf_audio_lag_min_ms == 0.0 or lag_ms < self._perf_audio_lag_min_ms:
                        self._perf_audio_lag_min_ms = lag_ms
                    if lag_ms > self._perf_audio_lag_max_ms:
                        self._perf_audio_lag_max_ms = lag_ms
            
            # Get pre-smoothed bars from engine (smoothing done on COMPUTE pool)
            smoothed = engine.get_smoothed_bars()

            # Always drive the bars from audio to avoid Spotify bridge flakiness.
            self._fallback_logged = False

            # Debug constant-bar mode
            if _DEBUG_CONST_BARS > 0.0:
                const_val = max(0.0, min(1.0, _DEBUG_CONST_BARS))
                smoothed = [const_val] * self._bar_count
            
            # Check if bars changed
            bar_count = self._bar_count
            display_bars = self._display_bars
            any_nonzero = False
            for i in range(bar_count):
                new_val = smoothed[i] if i < len(smoothed) else 0.0
                old_val = display_bars[i] if i < len(display_bars) else 0.0
                if abs(new_val - old_val) > 1e-4:
                    changed = True
                if new_val > 0.0:
                    any_nonzero = True
                display_bars[i] = new_val
            
            # Force update during decay (when bars are non-zero but Spotify stopped)
            if any_nonzero and not self._spotify_playing:
                changed = True

        # --- Heartbeat transient detection (CPU-side) ---
        # Compare current bass to rolling average; spike triggers heartbeat.
        # Decay envelope: ~250ms full decay (4.0/s).
        if self._sine_heartbeat > 0.001 and self._engine is not None:
            eb = self._engine.get_energy_bands()
            bass_now = getattr(eb, 'bass', 0.0) if eb else 0.0
            # Use dedicated heartbeat timestamp so dt_hb is always the real tick interval
            prev_hb_ts = self._heartbeat_last_ts
            self._heartbeat_last_ts = now_ts
            dt_hb = max(0.001, min(0.05, now_ts - prev_hb_ts)) if prev_hb_ts > 0.0 else 0.016
            # Rolling average with ~0.5s window (slower average = easier to trigger)
            alpha_avg = min(1.0, dt_hb / 0.5)
            self._heartbeat_avg_bass += (bass_now - self._heartbeat_avg_bass) * alpha_avg
            # Transient: current bass exceeds average by threshold scaled by slider
            threshold = 0.12 * (1.1 - self._sine_heartbeat)  # lower threshold at higher slider
            if bass_now - self._heartbeat_avg_bass > threshold:
                self._heartbeat_intensity = 1.0
            # Decay: ~300ms full decay (3.3/s) — slower so effect is visible
            self._heartbeat_intensity = max(0.0, self._heartbeat_intensity - dt_hb * 3.3)

        # --- Bubble simulation tick (dispatched to COMPUTE thread pool) ---
        if self._vis_mode_str == 'bubble' and not self._bubble_compute_pending:
            if self._thread_manager is not None:
                self._bubble_compute_pending = True
                # Snapshot energy bands and settings on UI thread (cheap reads)
                # Use raw (unsmoothed) energy for pulse so kicks/drums produce
                # sharp transients. Travel speed uses smoothed bands (smooth feel).
                eb_raw = self._engine.get_raw_energy_bands() if self._engine else None
                eb_smooth = self._engine.get_energy_bands() if self._engine else None
                prev_ts = self._bubble_last_tick_ts
                self._bubble_last_tick_ts = now_ts
                dt_bubble = max(0.001, min(0.1, now_ts - prev_ts)) if prev_ts > 0 else 0.016
                if not self._spotify_playing:
                    dt_bubble = 0.0
                eb_snap = {
                    'bass': getattr(eb_raw, 'bass', 0.0) if eb_raw else 0.0,
                    'mid': getattr(eb_raw, 'mid', 0.0) if eb_raw else 0.0,
                    'high': getattr(eb_raw, 'high', 0.0) if eb_raw else 0.0,
                    'overall': getattr(eb_smooth, 'overall', 0.0) if eb_smooth else 0.0,
                    'smooth_mid': getattr(eb_smooth, 'mid', 0.0) if eb_smooth else 0.0,
                    'smooth_high': getattr(eb_smooth, 'high', 0.0) if eb_smooth else 0.0,
                }
                sim_settings = {
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
                }
                pulse_params = {
                    'bass': eb_snap['bass'],
                    'mid_high': (eb_snap['mid'] + eb_snap['high']) * 0.5,
                    'big_bass_pulse': self._bubble_big_bass_pulse,
                    'small_freq_pulse': self._bubble_small_freq_pulse,
                }
                self._thread_manager.submit_compute_task(
                    self._bubble_compute_worker,
                    dt_bubble, eb_snap, sim_settings, pulse_params,
                    callback=self._bubble_compute_done,
                    task_id=f"bubble_sim_{id(self)}",
                )

        # Always push at least one frame so the visualiser baseline is
        # visible as soon as the widget fades in, even before audio arrives.
        first_frame = not self._has_pushed_first_frame

        used_gpu = False
        need_card_update = False
        fade_changed = False
        fade = 1.0
        # When DisplayWidget exposes a GPU overlay path, prefer
        # that and disable CPU bar drawing once it succeeds.
        if parent is not None and hasattr(parent, "push_spotify_visualizer_frame"):
            try:
                current_geom = self.geometry()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                current_geom = None
            last_geom = self._last_gpu_geom
            geom_changed = last_geom is None or (current_geom is not None and current_geom != last_geom)

            fade = self._get_gpu_fade_factor(now_ts)
            # Apply mode-transition crossfade (1.0 when idle, 0→1 during switch)
            transition_fade = self._mode_transition_fade_factor(now_ts)
            fade *= transition_fade
            prev_fade = self._last_gpu_fade_sent
            self._last_gpu_fade_sent = fade
            if prev_fade < 0.0 or abs(fade - prev_fade) >= 0.01:
                fade_changed = True
                need_card_update = True

            transitioning = self._mode_transition_phase != 0
            # Animated modes must push every tick because their visuals change
            # continuously (bubble sim, waveform, starfield travel, blob pulse,
            # rainbow hue rotation, etc.) independent of bar data.
            # Spectrum only needs pushes when bars change, UNLESS rainbow is on.
            animated_mode = (self._vis_mode_str != 'spectrum') or getattr(self, '_rainbow_enabled', False)
            should_push = changed or fade_changed or first_frame or geom_changed or transitioning or animated_mode
            if should_push:
                _gpu_push_start = time.time()
                mode_str = self._vis_mode_str

                from widgets.spotify_visualizer.config_applier import build_gpu_push_extra_kwargs
                extra = build_gpu_push_extra_kwargs(self, mode_str, self._engine)

                used_gpu = parent.push_spotify_visualizer_frame(
                    bars=list(self._display_bars),
                    bar_count=self._bar_count,
                    segments=self._dynamic_bar_segments(),
                    fill_color=self._bar_fill_color,
                    border_color=self._bar_border_color,
                    fade=fade,
                    playing=self._spotify_playing,
                    ghosting_enabled=self._ghosting_enabled,
                    ghost_alpha=self._ghost_alpha,
                    ghost_decay=self._ghost_decay_rate,
                    vis_mode=mode_str,
                    single_piece=self._spectrum_single_piece,
                    slanted=(self._spectrum_bar_profile == 'slanted'),
                    border_radius=self._spectrum_border_radius if self._spectrum_bar_profile == 'curved' else 0.0,
                    **extra,
                )
                _gpu_push_elapsed = (time.time() - _gpu_push_start) * 1000.0
                if _gpu_push_elapsed > 20.0 and is_perf_metrics_enabled():
                    logger.warning("[PERF] [SPOTIFY_VIS] Slow GPU push: %.2fms", _gpu_push_elapsed)

            if used_gpu:
                self._has_pushed_first_frame = True
                self._cpu_bars_enabled = False
                try:
                    if current_geom is None:
                        current_geom = self.geometry()
                    self._last_gpu_geom = QRect(current_geom)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    self._last_gpu_geom = None
                # Card/background/shadow still repaint via stylesheet
                # Only request QWidget repaint when fade changes
                if need_card_update:
                    self.update()
            else:
                # Fallback: when there is no DisplayWidget/GPU bridge
                has_gpu_parent = parent is not None and hasattr(parent, "push_spotify_visualizer_frame")
                if not has_gpu_parent or self._software_visualizer_enabled:
                    self._cpu_bars_enabled = True
                    self.update()
                    self._has_pushed_first_frame = True

        # PERF: Log slow ticks to identify blocking operations
        _tick_elapsed = (time.time() - _tick_entry_ts) * 1000.0
        if _tick_elapsed > 50.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [SPOTIFY_VIS] Slow _on_tick: %.2fms", _tick_elapsed)

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
            logger.info("[SPOTIFY_VIS] Visualization mode changed to %s", mode.name)

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

