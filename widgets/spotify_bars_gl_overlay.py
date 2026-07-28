from __future__ import annotations

from typing import List, Sequence, Optional, Set

import logging
import numpy as np
import time
from PySide6.QtCore import Qt, QRect, QTimer, QCoreApplication, QThread
from PySide6.QtGui import QColor, QOpenGLContext
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import (
    get_logger,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
)
from core.settings.visualizer_mode_registry import coerce_visualizer_mode_id
from rendering.gl_format import apply_widget_surface_format
from rendering.gl_state_manager import GLStateManager, GLContextState
from OpenGL import GL as gl
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
from widgets.spotify_visualizer.overlay_state import (
    apply_state_handoff,
    request_mode_reset as request_overlay_mode_reset,
    reset_mode_state as reset_overlay_mode_state,
)
from widgets.spotify_visualizer.overlay_mask import (
    compute_painted_card_mask_uniforms,
)
from widgets.spotify_visualizer.overlay_diagnostics import (
    maybe_log_glow_diagnostics,
    maybe_log_oscilloscope_diagnostics,
    maybe_log_sine_idle_state,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    apply_overlay_spectrum_solid_hysteresis,
    reset_overlay_spectrum_solid_hysteresis_state,
)
from widgets.spotify_visualizer.overlay_uniforms import (
    upload_common_uniforms,
)
from widgets.spotify_visualizer.overlay_render_dispatch import (
    dispatch_mode_uniforms,
    resolve_mode_program,
    resolve_render_program_key,
)
from widgets.spotify_visualizer.oscilloscope_contract import (
    advance_ghost_ring,
    blend_waveform,
    condition_live_waveform,
    resolve_transient_sensitivity_modulation,
    resolve_waveform_blend_alpha,
)
from widgets.spotify_visualizer.overlay_frame_shell import (
    clear_overlay_backbuffer,
    render_overlay_frame,
    resolve_frame_fade,
)
from widgets.spotify_visualizer.signal_contract import soft_ceiling
from widgets.base_overlay_widget import (
    PAINTED_FRAME_SHADOW_TUNING,
)

logger = get_logger(__name__)

_ARRAY_UNIFORM_NAMES = {
    "u_bars",
    "u_peaks",
    "u_waveform",
    "u_prev_waveform",
    "u_bubbles_pos",
    "u_bubbles_extra",
    "u_bubbles_trail",
    "u_devcurve_curve_bass",
    "u_devcurve_curve_vocals",
    "u_devcurve_curve_mids",
    "u_devcurve_curve_transients",
}


def _uniform_lookup_name(uniform_name: str) -> str:
    """Return the GL lookup token for a uniform name.

    Array uniforms must be queried by their first element on real drivers.
    Querying the bare array name often works in mocks/tests but returns -1 in
    live GL, which silently drops uploads and can collapse authored shapes back
    to fallback circles.
    """
    if uniform_name in _ARRAY_UNIFORM_NAMES:
        return f"{uniform_name}[0]"
    return uniform_name


def prioritized_visualizer_compile_order(active_mode: str, available_modes: Sequence[str]) -> List[str]:
    ordered: List[str] = []
    seen: Set[str] = set()
    active = str(active_mode or "").strip()
    if active and active in available_modes:
        ordered.append(active)
        seen.add(active)
    for mode in available_modes:
        if mode in seen:
            continue
        ordered.append(mode)
        seen.add(mode)
    return ordered


class SpotifyBarsGLOverlay(QOpenGLWidget):
    """Small GL surface that renders the Spotify bar field.

    This overlay is parented to ``DisplayWidget`` and positioned so that it
    exactly covers the Spotify visualiser card. The card itself (background,
    border, fade, shadow) continues to be drawn by ``SpotifyVisualizerWidget``;
    this class is responsible only for the bar geometry.
    """

    def __init__(self, parent=None, initial_mode: str | None = None) -> None:  # type: ignore[override]
        super().__init__(parent)
        self._painted_frame_shadow_enabled: bool = True

        apply_widget_surface_format(self, reason="spotify_bars_overlay")

        # CRITICAL: Hide immediately at construction to prevent startup flash.
        # The widget will be shown later when set_state() is called with fade > 0.
        # This must happen BEFORE any other setup to avoid a visible frame.
        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        try:
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        self._enabled: bool = False
        self._bars: List[float] = []
        self._bar_count: int = 0
        self._segments: int = 0
        self._fill_color: QColor = QColor(200, 200, 200, 230)
        self._border_color: QColor = QColor(255, 255, 255, 255)
        self._fade: float = 0.0
        self._playing: bool = False
        self._perf_set_state_count: int = 0
        self._perf_paint_count: int = 0
        self._perf_update_request_count: int = 0
        self._perf_geometry_change_count: int = 0
        self._perf_last_log_ts: float = time.monotonic()
        
        # Active visualization mode
        self._vis_mode: str = coerce_visualizer_mode_id(initial_mode)
        self._activation_id: int | None = None
        self._engine_generation: int | None = None
        self._latest_frame_generation: int | None = None
        self._latest_waveform_generation: int | None = None

        # Accumulated time for animated visualizers (seconds)
        self._accumulated_time: float = 0.0
        self._last_time_ts: float = 0.0
        self._last_sine_idle_diag_ts: float = 0.0
        self._pending_mode_resets: Set[str] = set()
        self._last_reset_mode: Optional[str] = None
        self._last_reset_reason: Optional[str] = None
        self._last_reset_ts: float = 0.0

        # Waveform data for oscilloscope (256 samples, -1..1)
        self._waveform: List[float] = []
        self._prev_waveform: List[float] = []  # delayed ghost trail waveform
        self._ghost_waveform_ring: List[List[float]] = []  # ring buffer for delay
        self._ghost_ring_idx: int = 0
        _GHOST_DELAY_FRAMES = 6  # ~100ms at 60fps — enough spatial separation
        self._ghost_delay_frames: int = _GHOST_DELAY_FRAMES
        self._waveform_count: int = 0
        self._osc_ghost_alpha: float = 0.0  # 0 = disabled

        self._energy_bands: EnergyBands = EnergyBands()
        # Transient energy (Approach A dual-path)
        self._transient_energy: TransientEnergyBands = TransientEnergyBands()

        # Oscilloscope glow settings
        self._glow_enabled: bool = True
        self._glow_intensity: float = 0.5
        self._glow_size: float = 1.0
        self._glow_reactivity: float = 1.0
        self._glow_color: QColor = QColor(0, 200, 255, 230)
        self._line_color: QColor = QColor(255, 255, 255, 255)
        self._reactive_glow: bool = True
        self._line_sensitivity: float = 3.0
        self._line_smoothing: float = 0.7

        # Oscilloscope / Sine multi-line
        self._line_count: int = 1
        self._line2_color: QColor = QColor(255, 120, 50, 230)
        self._line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._line3_color: QColor = QColor(50, 255, 120, 230)
        self._line3_glow_color: QColor = QColor(50, 255, 120, 180)
        self._line4_color: QColor = QColor(255, 0, 150, 230)
        self._line4_glow_color: QColor = QColor(255, 0, 150, 180)
        self._line5_color: QColor = QColor(0, 255, 200, 230)
        self._line5_glow_color: QColor = QColor(0, 255, 200, 180)
        self._line6_color: QColor = QColor(200, 100, 255, 230)
        self._line6_glow_color: QColor = QColor(200, 100, 255, 180)
        self._osc_ghost_line2_enabled: bool = True
        self._osc_ghost_line3_enabled: bool = True
        self._osc_ghost_line4_enabled: bool = True
        self._osc_ghost_line5_enabled: bool = True
        self._osc_ghost_line6_enabled: bool = True


        # Compatibility mirror for legacy callers only; renderer authority is
        self._continuous_floor_dynamic_enabled: bool = False
        self._continuous_floor_manual: float = 0.12
        self._continuous_floor_applied: float = 0.12
        self._continuous_floor_pressure: float = 0.0
        self._line_speed: float = 1.0
        self._line_dim: bool = False  # optional half-strength dimming on lines 2/3
        self._line_offset_bias: float = 0.0
        self._osc_vertical_shift: int = 0
        self._sine_wave_travel: int = 0  # 0=none, 1=left, 2=right
        self._sine_card_adaptation: float = 0.30
        self._sine_travel_line2: int = 0  # per-line travel: 0=none, 1=left, 2=right
        self._sine_travel_line3: int = 0
        self._sine_travel_line4: int = 0
        self._sine_travel_line5: int = 0
        self._sine_travel_line6: int = 0
        self._sine_wave_effect: float = 0.0  # 0.0-1.0, wave-like positional effect
        self._sine_micro_wobble: float = 0.0  # 0.0-1.0, energy-reactive micro distortions
        self._sine_crawl_amount: float = 0.0  # 0.0-1.0, Crawl slider amount
        self._sine_vertical_shift: int = 0  # -50 to 200, line spread amount
        self._sine_width_reaction: float = 0.0  # 0.0-1.0, bass-driven line width stretching
        self._sine_density: float = 1.0  # cycles per card multiplier
        self._sine_displacement: float = 0.0  # multi-line transient offset
        self._sine_line1_shift: float = 0.0
        self._sine_line2_shift: float = 0.0
        self._sine_line3_shift: float = 0.0
        self._sine_line4_shift: float = 0.0
        self._sine_line5_shift: float = 0.0
        self._sine_line6_shift: float = 0.0
        self._line_smoothed_bass: float = 0.0  # CPU-side smoothed energy shared by line modes
        self._line_smoothed_mid: float = 0.0
        self._line_smoothed_high: float = 0.0
        self._sine_wave_transient_width_mix: float = 0.4
        self._osc_transient_width_mix: float = 0.35
        self._transient_pulse_gain: float = 1.0
        self._transient_clamp: float = 1.5
        # Sine wave ghost: peak-tracked energy per band (decays slowly)
        self._sine_peak_bass: float = 0.0
        self._sine_peak_mid: float = 0.0
        self._sine_peak_high: float = 0.0
        self._sine_peak_hold_remaining: float = 0.0
        self._glow_diag_last_ts: float = 0.0
        self._glow_diag_last_sig: tuple | None = None
        self._osc_diag_last_ts: float = 0.0
        self._osc_diag_last_sig: tuple | None = None
        self._osc_last_waveform_delta: float = 0.0
        self._osc_last_waveform_blend_alpha: float = 1.0

        self._line_kick_event_strength: float = 0.0
        self._line_snare_event_strength: float = 0.0
        self._line_kick_event_envelope: float = 0.0
        self._line_snare_event_envelope: float = 0.0
        self._last_vis_mode: Optional[str] = None

        # Rainbow (Taste The Rainbow) mode
        self._rainbow_enabled: bool = False
        self._rainbow_speed: float = 0.5
        self._rainbow_per_bar: bool = False
        self._spectrum_rainbow_border: bool = False

        # Bubble settings
        self._bubble_count: int = 0
        self._bubble_pos_data: list = []
        self._bubble_extra_data: list = []
        self._bubble_trail_data: list = []
        self._bubble_trail_strength: float = 0.0
        self._bubble_tail_opacity: float = 0.0
        self._bubble_outline_color: QColor = QColor(255, 255, 255, 230)


        # Spectrum: single piece mode (solid bars, no segment gaps)
        self._single_piece: bool = False
        self._spectrum_glow_enabled: bool = False
        self._spectrum_glow_intensity: float = 0.55
        self._spectrum_glow_color: QColor = QColor(110, 220, 255, 235)
        self._spectrum_solid_display_segments: list[int] = []
        self._spectrum_solid_display_segment_values: list[float] = []
        self._spectrum_solid_last_update_ts: list[float] = []
        self._spectrum_solid_hysteresis_segments: int = 0
        self._spectrum_solid_hysteresis_bar_count: int = 0
        self._spectrum_solid_last_signal_ts: float = 0.0

        # Ghosting configuration – whether trailing segments are drawn and
        # how strong they appear relative to the main bar border colour. The
        # decay rate is controlled separately via _peak_decay_per_sec.
        self._ghosting_enabled: bool = True
        self._ghost_alpha: float = 0.4
        # Per-mode ghost fields (strict isolation, no cross-mode bleed)
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

        # Dev Curve mode defaults (safe no-op values so upload_uniforms always works)
        self._devcurve_base_level: float = 0.58
        self._devcurve_sample_count: int = 96
        self._devcurve_curve_bass: list = []
        self._devcurve_curve_vocals: list = []
        self._devcurve_curve_mids: list = []
        self._devcurve_curve_transients: list = []
        self._devcurve_layer_bass_color: QColor = QColor(82, 167, 255, 230)
        self._devcurve_layer_vocals_color: QColor = QColor(136, 190, 255, 210)
        self._devcurve_layer_mids_color: QColor = QColor(100, 145, 255, 210)
        self._devcurve_layer_transients_color: QColor = QColor(215, 240, 255, 240)
        self._devcurve_layer_bass_outline_color: QColor = QColor(255, 255, 255, 255)
        self._devcurve_layer_vocals_outline_color: QColor = QColor(255, 255, 255, 255)
        self._devcurve_layer_mids_outline_color: QColor = QColor(255, 255, 255, 255)
        self._devcurve_layer_transients_outline_color: QColor = QColor(255, 255, 255, 255)
        self._devcurve_layer_bass_outline_width: float = 0.006
        self._devcurve_layer_vocals_outline_width: float = 0.006
        self._devcurve_layer_mids_outline_width: float = 0.006
        self._devcurve_layer_transients_outline_width: float = 0.006
        self._devcurve_layer_bass_alpha: float = 0.55
        self._devcurve_layer_vocals_alpha: float = 0.42
        self._devcurve_layer_mids_alpha: float = 0.46
        self._devcurve_layer_transients_alpha: float = 0.66
        self._devcurve_layer_bass_enabled: bool = True
        self._devcurve_layer_vocals_enabled: bool = True
        self._devcurve_layer_mids_enabled: bool = True
        self._devcurve_layer_transients_enabled: bool = True
        self._devcurve_layer_bass_order: int = 1
        self._devcurve_layer_vocals_order: int = 2
        self._devcurve_layer_mids_order: int = 3
        self._devcurve_layer_transients_order: int = 4
        self._devcurve_foreground_layer_id: int = -1
        self._devcurve_foreground_shadow_enabled: bool = False
        self._devcurve_foreground_shadow_alpha: float = 0.36
        self._devcurve_foreground_shadow_darken: float = 0.42
        self._devcurve_foreground_shadow_offset: float = 0.10
        self._devcurve_foreground_specular_enabled: bool = False
        self._devcurve_foreground_specular_alpha: float = 0.78
        self._devcurve_foreground_specular_width: float = 0.022
        self._devcurve_foreground_specular_offset: float = 0.028
        self._devcurve_foreground_specular_crest_bias: float = 1.05
        self._devcurve_specular_slot0: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._devcurve_specular_slot1: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._devcurve_specular_slot2: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._devcurve_ghosting_enabled: bool = False
        self._devcurve_ghost_alpha: float = 0.0
        self._devcurve_ghost_decay: float = 0.4

        # Per-bar peak values used to draw trailing "ghost" segments above
        # the current bar height. Peaks are updated whenever new bar data
        # arrives and decay over time.
        self._peaks: List[float] = []
        self._last_peak_ts: float = 0.0
        # Decay rate for the peak envelope; kept low enough that the
        # peak/value gap – and thus the ghost trail – remains visible for
        # roughly a second after a strong drop.
        self._peak_decay_per_sec: float = 0.4

        # Multi-shader GL state. Each vis_mode has its own compiled program
        # stored in _gl_programs[mode]. The shared VAO/VBO is reused across
        # all modes (they all render a single fullscreen quad).
        from typing import Dict as _Dict, Any as _Any
        self._gl_programs: _Dict[str, _Any] = {}  # mode -> program id
        self._gl_uniforms: _Dict[str, _Dict[str, _Any]] = {}  # mode -> {name: loc}
        self._gl_program_warm_queue: List[str] = []
        self._gl_program_warm_timer: Optional[QTimer] = None
        self._gl_vao = None
        self._gl_vbo = None
        # ResourceManager resource IDs for GL handles (for cleanup tracking)
        self._gl_program_rids: _Dict[str, _Any] = {}
        self._gl_vao_rid = None
        self._gl_vbo: Optional[int] = None
        # Rounded-rect stencil mask program for painted-card corner clipping
        self._gl_mask_program: Optional[int] = None
        # Legacy single-program aliases for backward compat with ResourceManager
        self._gl_program = None
        self._gl_program_rid = None
        self._gl_disabled: bool = False
        self._debug_bars_logged: bool = False
        self._debug_paint_logged: bool = False
        self._border_width_px: float = 0.0
        
        # Pre-allocated uniform buffers to reduce GC pressure (avoid per-frame allocation)
        self._bars_buffer: np.ndarray = np.zeros(64, dtype="float32")
        self._peaks_buffer: np.ndarray = np.zeros(64, dtype="float32")
        
        # Centralized GL state manager for robust state tracking
        self._gl_state = GLStateManager(f"spotify_bars_{id(self)}")

    def request_mode_reset(self, mode: str) -> None:
        """Schedule a manual reset for ``mode`` prior to the next frame push."""
        request_overlay_mode_reset(self, mode)

    def _reset_mode_state(self, mode: str, *, reason: str) -> None:
        """Cold-reset per-mode accumulators so the next frame behaves like a fresh start."""
        reset_overlay_mode_state(self, mode, reason=reason)

    def _perf_screen_index(self) -> int | None:
        parent = self.parent()
        for attr in ("_screen_index", "screen_index"):
            value = getattr(parent, attr, None)
            if value is None:
                continue
            try:
                return int(value)
            except Exception:
                return None
        return None

    def _maybe_log_perf_counters(self, *, reason: str) -> None:
        if not is_perf_metrics_enabled():
            return
        now = time.monotonic()
        elapsed = now - self._perf_last_log_ts
        if elapsed < 10.0:
            return
        screen = self._perf_screen_index()
        logger.info(
            "[PERF][SPOTIFY_VIS][OVERLAY] reason=%s screen=%s mode=%s elapsed_ms=%.1f "
            "set_state=%d paint=%d update_requests=%d geometry_changes=%d "
            "visible=%s enabled=%s playing=%s",
            reason,
            screen if screen is not None else "<unknown>",
            self._vis_mode,
            elapsed * 1000.0,
            self._perf_set_state_count,
            self._perf_paint_count,
            self._perf_update_request_count,
            self._perf_geometry_change_count,
            self.isVisible(),
            self._enabled,
            self._playing,
        )
        self._perf_set_state_count = 0
        self._perf_paint_count = 0
        self._perf_update_request_count = 0
        self._perf_geometry_change_count = 0
        self._perf_last_log_ts = now

    def _request_frame_update(self, *, force: bool = False) -> None:
        del force
        self._perf_update_request_count += 1
        self.update()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_painted_frame_shadow_enabled(self, enabled: bool) -> None:
        self._painted_frame_shadow_enabled = bool(enabled)

    def set_state(
        self,
        rect: QRect,
        bars: Sequence[float],
        bar_count: int,
        segments: int,
        fill_color: QColor,
        border_color: QColor,
        fade: float,
        playing: bool,
        visible: bool,
        ghosting_enabled: bool = True,
        ghost_alpha: float = 0.4,
        ghost_decay: float = -1.0,
        ghost_line2_enabled: bool = True,
        ghost_line3_enabled: bool = True,
        ghost_line4_enabled: bool = True,
        ghost_line5_enabled: bool = True,
        ghost_line6_enabled: bool = True,
        vis_mode: str = "spectrum",
        waveform: Sequence[float] | None = None,
        waveform_count: int | None = None,
        energy_bands: EnergyBands | None = None,
        glow_enabled: bool = True,
        glow_intensity: float = 0.5,
        glow_size: float = 1.0,
        glow_reactivity: float = 1.0,
        glow_color: QColor | None = None,
        reactive_glow: bool = True,
        line_sensitivity: float = 3.0,
        line_smoothing: float = 0.7,
        line_speed: float = 1.0,
        line_dim: bool = False,
        line_offset_bias: float = 0.0,
        osc_vertical_shift: int = 0,
        sine_wave_travel: int = 0,
        sine_card_adaptation: float = 0.30,
        sine_travel_line2: int = 0,
        sine_travel_line3: int = 0,
        sine_travel_line4: int = 0,
        sine_travel_line5: int = 0,
        sine_travel_line6: int = 0,
        sine_wave_effect: float = 0.0,
        sine_micro_wobble: float = 0.0,
        sine_crawl_amount: float = 0.0,
        sine_vertical_shift: int = 0,
        sine_line1_shift: float = 0.0,
        sine_line2_shift: float = 0.0,
        sine_line3_shift: float = 0.0,
        sine_line4_shift: float = 0.0,
        sine_line5_shift: float = 0.0,
        sine_line6_shift: float = 0.0,
        sine_width_reaction: float = 0.0,
        sine_density: float = 1.0,
        sine_displacement: float = 0.0,
        line_color: QColor | None = None,
        line_count: int = 1,
        line2_color: QColor | None = None,
        line2_glow_color: QColor | None = None,
        line3_color: QColor | None = None,
        line3_glow_color: QColor | None = None,
        line4_color: QColor | None = None,
        line4_glow_color: QColor | None = None,
        line5_color: QColor | None = None,
        line5_glow_color: QColor | None = None,
        line6_color: QColor | None = None,
        line6_glow_color: QColor | None = None,
        osc_ghost_line2_enabled: bool = True,
        osc_ghost_line3_enabled: bool = True,
        osc_ghost_line4_enabled: bool = True,
        osc_ghost_line5_enabled: bool = True,
        osc_ghost_line6_enabled: bool = True,
        single_piece: bool = False,
        slanted: bool = False,
        border_radius: float = 0.0,
        rainbow_enabled: bool = False,
        rainbow_speed: float = 0.5,
        rainbow_per_bar: bool = False,
        spectrum_rainbow_border: bool = False,
        spectrum_glow_enabled: bool = False,
        spectrum_glow_intensity: float = 0.55,
        spectrum_glow_color: QColor | None = None,
        osc_ghosting_enabled: bool = False,
        osc_ghost_intensity: float = 0.4,
        osc_ghost_decay: float = 0.4,
        spectrum_ghosting_enabled: bool = True,
        spectrum_ghost_alpha: float = 0.4,
        spectrum_ghost_decay: float = 0.4,
        sine_ghosting_enabled: bool = True,
        sine_ghost_alpha: float = 0.45,
        sine_ghost_decay: float = 0.3,
        sine_ghost_line2_enabled: bool = True,
        sine_ghost_line3_enabled: bool = True,
        sine_ghost_line4_enabled: bool = True,
        sine_ghost_line5_enabled: bool = True,
        sine_ghost_line6_enabled: bool = True,
        bubble_ghosting_enabled: bool = False,
        bubble_ghost_alpha: float = 0.0,
        bubble_ghost_decay: float = 0.4,
        sine_heartbeat: float = 0.0,
        heartbeat_intensity: float = 0.0,
        # Bubble mode
        bubble_count: int = 0,
        bubble_pos_data: list | None = None,
        bubble_extra_data: list | None = None,
        bubble_trail_data: list | None = None,
        bubble_trail_strength: float = 0.0,
        bubble_tail_opacity: float = 0.0,
        # Dev Curve mode
        devcurve_base_level: float = 0.58,
        devcurve_sample_count: int = 96,
        devcurve_curve_bass: list | None = None,
        devcurve_curve_vocals: list | None = None,
        devcurve_curve_mids: list | None = None,
        devcurve_curve_transients: list | None = None,
        devcurve_layer_bass_color: QColor | list | None = None,
        devcurve_layer_vocals_color: QColor | list | None = None,
        devcurve_layer_mids_color: QColor | list | None = None,
        devcurve_layer_transients_color: QColor | list | None = None,
        devcurve_layer_bass_outline_color: QColor | list | None = None,
        devcurve_layer_vocals_outline_color: QColor | list | None = None,
        devcurve_layer_mids_outline_color: QColor | list | None = None,
        devcurve_layer_transients_outline_color: QColor | list | None = None,
        devcurve_layer_bass_outline_width: float = 0.006,
        devcurve_layer_vocals_outline_width: float = 0.006,
        devcurve_layer_mids_outline_width: float = 0.006,
        devcurve_layer_transients_outline_width: float = 0.006,
        devcurve_layer_bass_alpha: float = 0.55,
        devcurve_layer_vocals_alpha: float = 0.42,
        devcurve_layer_mids_alpha: float = 0.46,
        devcurve_layer_transients_alpha: float = 0.66,
        devcurve_layer_bass_enabled: bool = True,
        devcurve_layer_vocals_enabled: bool = True,
        devcurve_layer_mids_enabled: bool = True,
        devcurve_layer_transients_enabled: bool = True,
        devcurve_layer_bass_order: int = 1,
        devcurve_layer_vocals_order: int = 2,
        devcurve_layer_mids_order: int = 3,
        devcurve_layer_transients_order: int = 4,
        devcurve_foreground_layer_id: int = -1,
        devcurve_foreground_shadow_enabled: bool = False,
        devcurve_foreground_shadow_alpha: float = 0.36,
        devcurve_foreground_shadow_darken: float = 0.42,
        devcurve_foreground_shadow_offset: float = 0.10,
        devcurve_foreground_specular_enabled: bool = False,
        devcurve_foreground_specular_alpha: float = 0.78,
        devcurve_foreground_specular_width: float = 0.022,
        devcurve_foreground_specular_offset: float = 0.028,
        devcurve_foreground_specular_crest_bias: float = 1.05,
        devcurve_specular_slot0: list | tuple | None = None,
        devcurve_specular_slot1: list | tuple | None = None,
        devcurve_specular_slot2: list | tuple | None = None,
        devcurve_ghosting_enabled: bool = False,
        devcurve_ghost_alpha: float = 0.0,
        devcurve_ghost_decay: float = 0.4,
        bubble_outline_color: QColor | None = None,
        bubble_specular_color: QColor | None = None,
        bubble_gradient_light: QColor | None = None,
        bubble_gradient_dark: QColor | None = None,
        bubble_pop_color: QColor | None = None,
        bubble_specular_direction: str = "top_left",
        bubble_gradient_direction: str = "top",
        border_width_px: float = 0.0,
        transient_energy: TransientEnergyBands | None = None,
        transient_pulse_gain: float = 1.0,
        transient_clamp: float = 1.5,
        line_kick_event_strength: float = 0.0,
        line_snare_event_strength: float = 0.0,
        floor_snapshot: dict | None = None,
        activation_id: int | None = None,
        engine_generation: int | None = None,
        latest_frame_generation: int | None = None,
        latest_waveform_generation: int | None = None,
    ) -> None:
        """Update overlay bar state and geometry.

        ``rect`` is specified in the parent ``DisplayWidget`` coordinate space
        and should usually be the geometry of the associated
        ``SpotifyVisualizerWidget``.
        """

        was_playing = bool(getattr(self, "_playing", False))
        if not apply_state_handoff(
            self,
            visible=visible,
            vis_mode=vis_mode,
            activation_id=activation_id,
            engine_generation=engine_generation,
            latest_frame_generation=latest_frame_generation,
            latest_waveform_generation=latest_waveform_generation,
            floor_snapshot=floor_snapshot,
            border_width_px=border_width_px,
        ):
            return
        self._perf_set_state_count += 1
        osc_entering_idle = self._vis_mode == "oscilloscope" and was_playing and not bool(playing)
        osc_entering_live = self._vis_mode == "oscilloscope" and (not was_playing) and bool(playing)

        try:
            self._sine_density = float(sine_density)
        except Exception:
            self._sine_density = 1.0
        try:
            self._sine_displacement = float(sine_displacement)
        except Exception:
            self._sine_displacement = 0.0

        # one coherent input snapshot per frame.
        if transient_energy is not None:
            self._transient_energy = transient_energy

        # Update accumulated time for animated modes
        dt_seconds = 0.0
        now_ts = time.time()
        if self._last_time_ts > 0.0:
            dt = now_ts - self._last_time_ts
            if 0.0 < dt < 1.0:  # sanity clamp
                dt_seconds = dt
                # Keep inherently animated modes moving while paused, but
                # preserve Spectrum's established no-paused-drift behavior.
                if playing or self._vis_mode in ('sine_wave', 'oscilloscope', 'bubble'):
                    self._accumulated_time += dt
                # Oscilloscope / Sine Wave: smooth per-band energy for glow anti-flicker
                if self._vis_mode in ('oscilloscope', 'sine_wave') and energy_bands is not None:
                    for attr, band in (
                        ('_line_smoothed_bass', 'bass'),
                        ('_line_smoothed_mid', 'mid'),
                        ('_line_smoothed_high', 'high'),
                    ):
                        raw_e = getattr(energy_bands, band, 0.0)
                        prev = getattr(self, attr)
                        a = min(1.0, dt / 0.06) if raw_e > prev else min(1.0, dt / 0.12)
                        setattr(self, attr, prev + (raw_e - prev) * a)
                # Sine Wave ghost: peak-tracked per-band energy envelope
                if self._vis_mode == 'sine_wave' and energy_bands is not None and self._sine_ghosting_enabled:
                    raw_bass = getattr(energy_bands, 'bass', 0.0)
                    raw_mid = getattr(energy_bands, 'mid', 0.0)
                    raw_high = getattr(energy_bands, 'high', 0.0)
                    any_sine_peak = False
                    if raw_bass > self._sine_peak_bass:
                        self._sine_peak_bass = raw_bass
                        any_sine_peak = True
                    if raw_mid > self._sine_peak_mid:
                        self._sine_peak_mid = raw_mid
                        any_sine_peak = True
                    if raw_high > self._sine_peak_high:
                        self._sine_peak_high = raw_high
                        any_sine_peak = True
                    if any_sine_peak:
                        self._sine_peak_hold_remaining = 0.12
                    hold = self._sine_peak_hold_remaining
                    if hold > 0.0:
                        self._sine_peak_hold_remaining = max(0.0, hold - dt)
                    else:
                        decay_tau = max(0.3, 3.0 - max(0.1, min(1.0, self._sine_ghost_decay)) * 2.5)
                        da = min(1.0, dt / decay_tau)
                        self._sine_peak_bass += (raw_bass - self._sine_peak_bass) * da
                        self._sine_peak_mid += (raw_mid - self._sine_peak_mid) * da
                        self._sine_peak_high += (raw_high - self._sine_peak_high) * da
                    min_off = max(0.40, self._line_smoothed_bass * 0.50)
                    self._sine_peak_bass = max(self._sine_peak_bass, raw_bass + min_off)
                    self._sine_peak_mid = max(self._sine_peak_mid, raw_mid + min_off * 0.90)
                    self._sine_peak_high = max(self._sine_peak_high, raw_high + min_off * 0.80)
        self._last_time_ts = now_ts
        self._line_speed = max(0.01, min(1.0, float(line_speed)))
        self._osc_ghost_alpha = max(0.0, min(1.0, float(osc_ghost_intensity))) if osc_ghosting_enabled else 0.0
        osc_decay = max(0.1, min(1.0, float(osc_ghost_decay)))
        self._ghost_delay_frames = max(2, min(18, int(round(2 + osc_decay * 16))))

        # Store waveform data (line modes) with temporal smoothing via line_speed
        if waveform is not None:
            if osc_entering_idle or osc_entering_live:
                previous_waveform = list(self._waveform)
                self._waveform = []
                if osc_entering_idle and previous_waveform and self._osc_ghost_alpha > 0.001:
                    # A pause is a content-state boundary, not a mode reset.
                    # Keep one delayed live outline so the first idle frame
                    # crossfades visually instead of flashing through empty GL
                    # state, while the body accepts idle data immediately below.
                    self._prev_waveform = previous_waveform
                    self._ghost_waveform_ring = [previous_waveform]
                    self._ghost_ring_idx = 0
                else:
                    self._prev_waveform = []
                    self._ghost_waveform_ring = []
                    self._ghost_ring_idx = 0
                self._line_kick_event_envelope = 0.0
                self._line_snare_event_envelope = 0.0
                self._line_kick_event_strength = 0.0
                self._line_snare_event_strength = 0.0
            if self._waveform and self._osc_ghost_alpha > 0.001:
                self._prev_waveform, self._ghost_ring_idx = advance_ghost_ring(
                    self._ghost_waveform_ring,
                    self._ghost_ring_idx,
                    self._waveform,
                    self._ghost_delay_frames,
                )
            new_wf = (
                condition_live_waveform(self._waveform, waveform)
                if self._vis_mode == "oscilloscope" and bool(playing)
                else list(waveform)
            )
            speed = self._line_speed
            old_wf = list(self._waveform)
            self._osc_last_waveform_blend_alpha = resolve_waveform_blend_alpha(speed)
            self._waveform = blend_waveform(self._waveform, new_wf, speed)
            if old_wf and len(old_wf) == len(self._waveform):
                self._osc_last_waveform_delta = max(
                    abs(float(new) - float(old))
                    for old, new in zip(old_wf, self._waveform)
                )
            else:
                self._osc_last_waveform_delta = max((abs(float(v)) for v in self._waveform), default=0.0)
            if waveform_count is None:
                resolved_waveform_count = len(self._waveform)
            else:
                resolved_waveform_count = waveform_count
            self._waveform_count = max(0, min(256, int(resolved_waveform_count)))

        line_kick_raw = max(0.0, min(1.0, float(line_kick_event_strength)))
        line_snare_raw = max(0.0, min(1.0, float(line_snare_event_strength)))
        if dt_seconds > 0.0:
            kick_tau = 0.14 if line_kick_raw < self._line_kick_event_envelope else 0.04
            snare_tau = 0.16 if line_snare_raw < self._line_snare_event_envelope else 0.05
            kick_alpha = min(1.0, dt_seconds / max(kick_tau, 0.01))
            snare_alpha = min(1.0, dt_seconds / max(snare_tau, 0.01))
            self._line_kick_event_envelope += (
                line_kick_raw - self._line_kick_event_envelope
            ) * kick_alpha
            self._line_snare_event_envelope += (
                line_snare_raw - self._line_snare_event_envelope
            ) * snare_alpha
        else:
            self._line_kick_event_envelope = line_kick_raw
            self._line_snare_event_envelope = line_snare_raw
        self._line_kick_event_strength = self._line_kick_event_envelope
        self._line_snare_event_strength = self._line_snare_event_envelope

        # Store energy bands (all modes that need them)
        if energy_bands is not None:
            self._energy_bands = energy_bands

        # Oscilloscope glow settings
        self._glow_enabled = bool(glow_enabled)
        self._glow_intensity = max(0.0, float(glow_intensity))
        self._glow_size = max(0.1, min(3.0, float(glow_size)))
        self._glow_reactivity = max(0.0, min(2.0, float(glow_reactivity)))
        if glow_color is not None:
            self._glow_color = QColor(glow_color)
        if line_color is not None:
            self._line_color = QColor(line_color)
        self._reactive_glow = bool(reactive_glow)
        self._line_sensitivity = max(0.5, min(10.0, float(line_sensitivity)))
        self._line_smoothing = max(0.0, min(1.0, float(line_smoothing)))

        # Multi-line oscilloscope / sine
        self._line_count = max(1, min(6, int(line_count)))
        if line2_color is not None:
            self._line2_color = QColor(line2_color)
        if line2_glow_color is not None:
            self._line2_glow_color = QColor(line2_glow_color)
        if line3_color is not None:
            self._line3_color = QColor(line3_color)
        if line3_glow_color is not None:
            self._line3_glow_color = QColor(line3_glow_color)
        if line4_color is not None:
            self._line4_color = QColor(line4_color)
        if line4_glow_color is not None:
            self._line4_glow_color = QColor(line4_glow_color)
        if line5_color is not None:
            self._line5_color = QColor(line5_color)
        if line5_glow_color is not None:
            self._line5_glow_color = QColor(line5_glow_color)
        if line6_color is not None:
            self._line6_color = QColor(line6_color)
        if line6_glow_color is not None:
            self._line6_glow_color = QColor(line6_glow_color)
        self._osc_ghost_line2_enabled = bool(osc_ghost_line2_enabled)
        self._osc_ghost_line3_enabled = bool(osc_ghost_line3_enabled)
        self._osc_ghost_line4_enabled = bool(osc_ghost_line4_enabled)
        self._osc_ghost_line5_enabled = bool(osc_ghost_line5_enabled)
        self._osc_ghost_line6_enabled = bool(osc_ghost_line6_enabled)


        self._transient_pulse_gain = max(0.0, min(3.0, float(transient_pulse_gain)))
        self._transient_clamp = max(0.0, min(3.0, float(transient_clamp)))
        # pockets/solvers cannot spend a frame under stale subtype authority.
        self._line_dim = bool(line_dim)
        self._line_offset_bias = max(0.0, min(1.0, float(line_offset_bias)))
        self._osc_vertical_shift = max(-50, min(200, int(osc_vertical_shift)))
        if self._vis_mode == "oscilloscope":
            _osc_sens_mod, _osc_drive = resolve_transient_sensitivity_modulation(
                base_sensitivity=self._line_sensitivity,
                smoothed_bass=self._line_smoothed_bass,
                kick_event=self._line_kick_event_strength,
                snare_event=self._line_snare_event_strength,
                width_mix=self._osc_transient_width_mix,
            )
            self._osc_last_transient_width_drive = _osc_drive
            self._osc_last_sensitivity_mod = _osc_sens_mod
        self._sine_wave_travel = max(0, min(2, int(sine_wave_travel)))
        self._sine_card_adaptation = max(0.05, min(1.0, float(sine_card_adaptation)))
        self._sine_travel_line2 = max(0, min(2, int(sine_travel_line2)))
        self._sine_travel_line3 = max(0, min(2, int(sine_travel_line3)))
        self._sine_travel_line4 = max(0, min(2, int(sine_travel_line4)))
        self._sine_travel_line5 = max(0, min(2, int(sine_travel_line5)))
        self._sine_travel_line6 = max(0, min(2, int(sine_travel_line6)))
        self._sine_wave_effect = max(0.0, min(1.0, float(sine_wave_effect)))
        self._sine_micro_wobble = max(0.0, min(1.0, float(sine_micro_wobble)))
        self._sine_crawl_amount = max(0.0, min(1.0, float(sine_crawl_amount)))
        self._sine_vertical_shift = max(-50, min(200, int(sine_vertical_shift)))
        self._sine_line1_shift = max(-1.0, min(1.0, float(sine_line1_shift)))
        self._sine_line2_shift = max(-1.0, min(1.0, float(sine_line2_shift)))
        self._sine_line3_shift = max(-1.0, min(1.0, float(sine_line3_shift)))
        self._sine_line4_shift = max(-1.0, min(1.0, float(sine_line4_shift)))
        self._sine_line5_shift = max(-1.0, min(1.0, float(sine_line5_shift)))
        self._sine_line6_shift = max(-1.0, min(1.0, float(sine_line6_shift)))
        self._sine_width_reaction = max(0.0, min(1.0, float(sine_width_reaction)))


        # Spectrum: single piece (solid bars, no segments)
        self._single_piece = bool(single_piece)
        # Spectrum: slanted bar edges and border radius
        self._slanted = bool(slanted)
        self._border_radius = max(0.0, float(border_radius))

        # Rainbow (Taste The Rainbow) mode
        self._rainbow_enabled = bool(rainbow_enabled)
        self._rainbow_speed = max(0.01, min(5.0, float(rainbow_speed)))
        self._rainbow_per_bar = bool(rainbow_per_bar)
        self._spectrum_rainbow_border = bool(spectrum_rainbow_border)
        self._spectrum_glow_enabled = bool(spectrum_glow_enabled)
        self._spectrum_glow_intensity = max(0.0, min(1.5, float(spectrum_glow_intensity)))
        if spectrum_glow_color is not None:
            self._spectrum_glow_color = QColor(spectrum_glow_color)

        # Sine Wave Heartbeat
        self._sine_heartbeat = max(0.0, min(1.0, float(sine_heartbeat)))
        self._heartbeat_intensity = max(0.0, min(1.0, float(heartbeat_intensity)))

        maybe_log_glow_diagnostics(self, logger)
        maybe_log_oscilloscope_diagnostics(self, logger)

        # Bubble settings
        self._bubble_count = max(0, min(110, int(bubble_count)))
        self._bubble_pos_data = bubble_pos_data or []
        self._bubble_extra_data = bubble_extra_data or []
        self._bubble_trail_data = bubble_trail_data or []
        self._bubble_trail_strength = max(0.0, min(1.5, float(bubble_trail_strength)))
        self._bubble_tail_opacity = max(0.0, min(0.85, float(bubble_tail_opacity)))
        if bubble_outline_color is not None:
            self._bubble_outline_color = QColor(bubble_outline_color) if not isinstance(bubble_outline_color, QColor) else bubble_outline_color
        if bubble_specular_color is not None:
            self._bubble_specular_color = QColor(bubble_specular_color) if not isinstance(bubble_specular_color, QColor) else bubble_specular_color
        if bubble_gradient_light is not None:
            self._bubble_gradient_light = QColor(bubble_gradient_light) if not isinstance(bubble_gradient_light, QColor) else bubble_gradient_light
        if bubble_gradient_dark is not None:
            self._bubble_gradient_dark = QColor(bubble_gradient_dark) if not isinstance(bubble_gradient_dark, QColor) else bubble_gradient_dark
        if bubble_pop_color is not None:
            self._bubble_pop_color = QColor(bubble_pop_color) if not isinstance(bubble_pop_color, QColor) else bubble_pop_color
        self._bubble_specular_direction = str(bubble_specular_direction)
        self._bubble_gradient_direction = str(bubble_gradient_direction)

        # --- Per-mode ghost configuration -----------------------------------
        # Each mode stores its own ghosting_enabled / ghost_alpha / ghost_decay
        # so no mode can contaminate another.  The old global ghost params
        # (ghosting_enabled, ghost_alpha, ghost_decay named args) are kept for
        # backward compat and used to seed the legacy _ghosting_enabled /
        # _ghost_alpha fields, but mode-specific fields always take priority
        # for rendering decisions.
        self._spectrum_ghosting_enabled = bool(spectrum_ghosting_enabled)
        self._spectrum_ghost_alpha = max(0.0, min(1.0, float(spectrum_ghost_alpha)))
        self._spectrum_ghost_decay = max(0.1, min(1.0, float(spectrum_ghost_decay)))
        self._sine_ghosting_enabled = bool(sine_ghosting_enabled)
        self._sine_ghost_alpha = max(0.0, min(1.0, float(sine_ghost_alpha)))
        self._sine_ghost_decay = max(0.1, min(1.0, float(sine_ghost_decay)))
        self._sine_ghost_line2_enabled = bool(sine_ghost_line2_enabled)
        self._sine_ghost_line3_enabled = bool(sine_ghost_line3_enabled)
        self._sine_ghost_line4_enabled = bool(sine_ghost_line4_enabled)
        self._sine_ghost_line5_enabled = bool(sine_ghost_line5_enabled)
        self._sine_ghost_line6_enabled = bool(sine_ghost_line6_enabled)
        self._bubble_ghosting_enabled = bool(bubble_ghosting_enabled)
        self._bubble_ghost_alpha = max(0.0, min(1.0, float(bubble_ghost_alpha)))
        self._bubble_ghost_decay = max(0.1, min(1.0, float(bubble_ghost_decay)))

        # Dev Curve mode state -----------------------------------------------------
        self._devcurve_base_level = max(0.10, min(0.90, float(devcurve_base_level)))
        self._devcurve_sample_count = max(2, min(96, int(devcurve_sample_count)))
        if devcurve_curve_bass is not None:
            self._devcurve_curve_bass = list(devcurve_curve_bass)
        if devcurve_curve_vocals is not None:
            self._devcurve_curve_vocals = list(devcurve_curve_vocals)
        if devcurve_curve_mids is not None:
            self._devcurve_curve_mids = list(devcurve_curve_mids)
        if devcurve_curve_transients is not None:
            self._devcurve_curve_transients = list(devcurve_curve_transients)
        if devcurve_layer_bass_color is not None:
            self._devcurve_layer_bass_color = QColor(*devcurve_layer_bass_color) if not isinstance(devcurve_layer_bass_color, QColor) else QColor(devcurve_layer_bass_color)
        if devcurve_layer_vocals_color is not None:
            self._devcurve_layer_vocals_color = QColor(*devcurve_layer_vocals_color) if not isinstance(devcurve_layer_vocals_color, QColor) else QColor(devcurve_layer_vocals_color)
        if devcurve_layer_mids_color is not None:
            self._devcurve_layer_mids_color = QColor(*devcurve_layer_mids_color) if not isinstance(devcurve_layer_mids_color, QColor) else QColor(devcurve_layer_mids_color)
        if devcurve_layer_transients_color is not None:
            self._devcurve_layer_transients_color = QColor(*devcurve_layer_transients_color) if not isinstance(devcurve_layer_transients_color, QColor) else QColor(devcurve_layer_transients_color)
        if devcurve_layer_bass_outline_color is not None:
            self._devcurve_layer_bass_outline_color = QColor(*devcurve_layer_bass_outline_color) if not isinstance(devcurve_layer_bass_outline_color, QColor) else QColor(devcurve_layer_bass_outline_color)
            self._devcurve_layer_bass_outline_color.setAlpha(255)
        if devcurve_layer_vocals_outline_color is not None:
            self._devcurve_layer_vocals_outline_color = QColor(*devcurve_layer_vocals_outline_color) if not isinstance(devcurve_layer_vocals_outline_color, QColor) else QColor(devcurve_layer_vocals_outline_color)
            self._devcurve_layer_vocals_outline_color.setAlpha(255)
        if devcurve_layer_mids_outline_color is not None:
            self._devcurve_layer_mids_outline_color = QColor(*devcurve_layer_mids_outline_color) if not isinstance(devcurve_layer_mids_outline_color, QColor) else QColor(devcurve_layer_mids_outline_color)
            self._devcurve_layer_mids_outline_color.setAlpha(255)
        if devcurve_layer_transients_outline_color is not None:
            self._devcurve_layer_transients_outline_color = QColor(*devcurve_layer_transients_outline_color) if not isinstance(devcurve_layer_transients_outline_color, QColor) else QColor(devcurve_layer_transients_outline_color)
            self._devcurve_layer_transients_outline_color.setAlpha(255)
        self._devcurve_layer_bass_outline_width = max(0.001, min(0.020, float(devcurve_layer_bass_outline_width)))
        self._devcurve_layer_vocals_outline_width = max(0.001, min(0.020, float(devcurve_layer_vocals_outline_width)))
        self._devcurve_layer_mids_outline_width = max(0.001, min(0.020, float(devcurve_layer_mids_outline_width)))
        self._devcurve_layer_transients_outline_width = max(0.001, min(0.020, float(devcurve_layer_transients_outline_width)))
        self._devcurve_layer_bass_alpha = max(0.0, min(1.0, float(devcurve_layer_bass_alpha)))
        self._devcurve_layer_vocals_alpha = max(0.0, min(1.0, float(devcurve_layer_vocals_alpha)))
        self._devcurve_layer_mids_alpha = max(0.0, min(1.0, float(devcurve_layer_mids_alpha)))
        self._devcurve_layer_transients_alpha = max(0.0, min(1.0, float(devcurve_layer_transients_alpha)))
        self._devcurve_layer_bass_enabled = bool(devcurve_layer_bass_enabled)
        self._devcurve_layer_vocals_enabled = bool(devcurve_layer_vocals_enabled)
        self._devcurve_layer_mids_enabled = bool(devcurve_layer_mids_enabled)
        self._devcurve_layer_transients_enabled = bool(devcurve_layer_transients_enabled)
        self._devcurve_layer_bass_order = max(1, min(4, int(devcurve_layer_bass_order)))
        self._devcurve_layer_vocals_order = max(1, min(4, int(devcurve_layer_vocals_order)))
        self._devcurve_layer_mids_order = max(1, min(4, int(devcurve_layer_mids_order)))
        self._devcurve_layer_transients_order = max(1, min(4, int(devcurve_layer_transients_order)))
        self._devcurve_foreground_layer_id = max(-1, min(3, int(devcurve_foreground_layer_id)))
        self._devcurve_foreground_shadow_enabled = bool(devcurve_foreground_shadow_enabled)
        self._devcurve_foreground_shadow_alpha = max(0.0, min(1.0, float(devcurve_foreground_shadow_alpha)))
        self._devcurve_foreground_shadow_darken = max(0.0, min(1.0, float(devcurve_foreground_shadow_darken)))
        self._devcurve_foreground_shadow_offset = max(0.0, min(0.45, float(devcurve_foreground_shadow_offset)))
        self._devcurve_foreground_specular_enabled = bool(devcurve_foreground_specular_enabled)
        self._devcurve_foreground_specular_alpha = max(0.0, min(1.0, float(devcurve_foreground_specular_alpha)))
        self._devcurve_foreground_specular_width = max(0.002, min(0.120, float(devcurve_foreground_specular_width)))
        self._devcurve_foreground_specular_offset = max(-0.20, min(0.20, float(devcurve_foreground_specular_offset)))
        self._devcurve_foreground_specular_crest_bias = max(0.0, min(2.0, float(devcurve_foreground_specular_crest_bias)))
        _slot0 = devcurve_specular_slot0 if isinstance(devcurve_specular_slot0, (list, tuple)) else (0.0, 0.0, 0.0)
        _slot1 = devcurve_specular_slot1 if isinstance(devcurve_specular_slot1, (list, tuple)) else (0.0, 0.0, 0.0)
        _slot2 = devcurve_specular_slot2 if isinstance(devcurve_specular_slot2, (list, tuple)) else (0.0, 0.0, 0.0)
        self._devcurve_specular_slot0 = [
            max(-1.5, min(2.5, float(_slot0[0] if len(_slot0) > 0 else 0.0))),
            max(0.0, min(1.0, float(_slot0[1] if len(_slot0) > 1 else 0.0))),
            max(0.0, min(1.0, float(_slot0[2] if len(_slot0) > 2 else 0.0))),
            max(0.0, min(1.0, float(_slot0[3] if len(_slot0) > 3 else 0.0))),
        ]
        self._devcurve_specular_slot1 = [
            max(-1.5, min(2.5, float(_slot1[0] if len(_slot1) > 0 else 0.0))),
            max(0.0, min(1.0, float(_slot1[1] if len(_slot1) > 1 else 0.0))),
            max(0.0, min(1.0, float(_slot1[2] if len(_slot1) > 2 else 0.0))),
            max(0.0, min(1.0, float(_slot1[3] if len(_slot1) > 3 else 0.0))),
        ]
        self._devcurve_specular_slot2 = [
            max(-1.5, min(2.5, float(_slot2[0] if len(_slot2) > 0 else 0.0))),
            max(0.0, min(1.0, float(_slot2[1] if len(_slot2) > 1 else 0.0))),
            max(0.0, min(1.0, float(_slot2[2] if len(_slot2) > 2 else 0.0))),
            max(0.0, min(1.0, float(_slot2[3] if len(_slot2) > 3 else 0.0))),
        ]
        self._devcurve_ghosting_enabled = bool(devcurve_ghosting_enabled)
        self._devcurve_ghost_alpha = max(0.0, min(1.0, float(devcurve_ghost_alpha)))
        self._devcurve_ghost_decay = max(0.1, min(1.0, float(devcurve_ghost_decay)))

        # Legacy global ghost fields — still written for backward compat but
        # renderers MUST read mode-specific fields above.
        try:
            self._ghosting_enabled = bool(ghosting_enabled)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._ghosting_enabled = True

        try:
            ga = float(ghost_alpha)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            ga = 0.4
        if ga < 0.0:
            ga = 0.0
        if ga > 1.0:
            ga = 1.0
        self._ghost_alpha = ga

        try:
            gd = float(ghost_decay)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            gd = -1.0
        if gd >= 0.0:
            self._peak_decay_per_sec = max(0.0, gd)

        # Route peak_decay_per_sec from current mode's decay setting so
        if self._vis_mode == 'spectrum':
            self._peak_decay_per_sec = self._spectrum_ghost_decay * 2.0

        try:
            count = int(bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            count = 0
        try:
            segs = int(segments)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            segs = 0

        if count <= 0 or segs <= 0:
            self.clear_overlay_buffer()
            return

        try:
            bars_seq = list(bars)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self.clear_overlay_buffer()
            return

        if not bars_seq:
            self.clear_overlay_buffer()
            return

        if len(bars_seq) > count:
            bars_seq = bars_seq[:count]
        elif len(bars_seq) < count:
            bars_seq = bars_seq + [0.0] * (count - len(bars_seq))

        clamped: List[float] = []
        for v in bars_seq:
            try:
                f = float(v)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                f = 0.0
            if f < 0.0:
                f = 0.0
            if f > 1.0:
                f = 1.0
            clamped.append(f)

        if not clamped:
            self.clear_overlay_buffer()
            return

        if self._vis_mode == 'spectrum' and self._single_piece:
            try:
                now_ts = time.monotonic()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                now_ts = 0.0
            clamped = apply_overlay_spectrum_solid_hysteresis(
                self,
                clamped,
                segments=max(1, segs),
                render_height=float(rect.height()),
                now_ts=now_ts,
            )
        else:
            reset_overlay_spectrum_solid_hysteresis_state(self)

        # Update per-bar peak state only for Spectrum. Other modes may still
        # pass bar arrays through the shared overlay, but they must not mutate
        # Spectrum ghost memory behind the scenes.
        if self._vis_mode == 'spectrum':
            try:
                now_ts = time.monotonic()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                now_ts = 0.0
            dt = 0.0
            try:
                last_ts = self._last_peak_ts
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                last_ts = 0.0
            if last_ts > 0.0 and now_ts > last_ts:
                dt = now_ts - last_ts
            try:
                self._last_peak_ts = now_ts
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

            try:
                peaks = list(self._peaks)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                peaks = []

            if not peaks or len(peaks) != len(clamped):
                peaks = list(clamped)

            decay_rate = self._peak_decay_per_sec
            if decay_rate < 0.0:
                decay_rate = 0.0

            if dt > 0.0 and decay_rate > 0.0:
                decay = decay_rate * dt
                max_len = len(clamped)
                if len(peaks) < max_len:
                    peaks.extend([0.0] * (max_len - len(peaks)))
                for i in range(max_len):
                    v = clamped[i]
                    p = peaks[i]
                    if v > p:
                        p = v
                    else:
                        delta = p - v
                        if delta <= 0.0:
                            p = v
                        else:
                            try:
                                gap_factor = 0.75 + min(1.0, float(delta)) * 0.75
                            except Exception as e:
                                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                                gap_factor = 1.0
                            p = max(v, p - decay * gap_factor)
                    if p < 0.0:
                        p = 0.0
                    if p > 1.0:
                        p = 1.0
                    peaks[i] = p
            else:
                for i, v in enumerate(clamped):
                    if i < len(peaks):
                        if v > peaks[i]:
                            peaks[i] = v
                    else:
                        peaks.append(v)

            self._peaks = peaks

        self._enabled = True
        self._bars = clamped
        self._bar_count = len(clamped)
        self._segments = max(1, segs)
        self._fill_color = QColor(fill_color)
        self._border_color = QColor(border_color)
        try:
            self._fade = max(0.0, min(1.0, float(fade)))
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._fade = 1.0
        self._playing = bool(playing)
        maybe_log_sine_idle_state(self, logger, dt_seconds=dt_seconds)

        _geom_start = time.time()
        if not clamped:
            self.clear_overlay_buffer()
            return
        geometry_changed = False
        try:
            cur_geom = None
            try:
                cur_geom = self.geometry()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                cur_geom = None
            if cur_geom is None or cur_geom != rect:
                self.setGeometry(rect)
                self._perf_geometry_change_count += 1
                geometry_changed = True
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set overlay geometry", exc_info=True)
        _geom_elapsed = (time.time() - _geom_start) * 1000.0

        _show_start = time.time()
        became_visible = False
        try:
            if self._enabled:
                # PERF: show()/raise_() take 25ms+ each - avoid calling them
                # Instead of hiding/showing, we control visibility via _enabled flag
                # and let paintGL skip rendering when disabled
                #
                # IMPORTANT: Only show() when fade > 0 to prevent startup flash.
                # The bars should fade in smoothly, not appear instantly on first
                # set_state call. This defers the expensive show() until the fade
                # animation actually starts.
                if not self.isVisible() and self._fade > 0.0:
                    # Only show once when first becoming visible AND fading in
                    self.show()
                    became_visible = True
                # Skip raise_() entirely - it's expensive and unnecessary
                # The overlay is created on top and stays there
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to show overlay", exc_info=True)
        _show_elapsed = (time.time() - _show_start) * 1000.0

        _update_start = time.time()
        self._request_frame_update(force=geometry_changed or became_visible)
        _update_elapsed = (time.time() - _update_start) * 1000.0
        self._maybe_log_perf_counters(reason="set_state")
        
        if is_perf_metrics_enabled() and (_geom_elapsed > 5.0 or _show_elapsed > 5.0 or _update_elapsed > 5.0):
            logger.warning("[PERF] [SPOTIFY_BARS_GL] set_state breakdown: geom=%.2fms, show=%.2fms, update=%.2fms",
                          _geom_elapsed, _show_elapsed, _update_elapsed)

    def prewarm_context(self, rect: QRect) -> None:
        """Pre-create the GL context and shader pipeline off the visible hot path."""

        try:
            self.setGeometry(rect)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set overlay geometry during prewarm", exc_info=True)

        self._enabled = False
        self._fade = 0.0

        try:
            if not self.isVisible():
                self.show()
            self.update()
            # Force the QOpenGLWidget to realise its GL surface now instead
            # of waiting until the visualizer's staged reveal window. This
            # shifts context creation + shader compilation into the shared
            # startup prewarm phase.
            if not self._gl_state.is_ready() and not self._gl_state.is_error():
                try:
                    self.grabFramebuffer()
                except Exception:
                    logger.warning(
                        "[SPOTIFY_VIS][FALLBACK] grabFramebuffer prewarm fallback triggered",
                        exc_info=True,
                    )
                    self.repaint()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to prewarm SpotifyBarsGLOverlay", exc_info=True)

    def clear_overlay_buffer(self) -> None:
        """Reset overlay state and clear the GL backing buffer."""

        self._enabled = False
        self._bars = []
        self._bar_count = 0
        self._segments = 0
        self._peaks = []
        self._last_peak_ts = 0.0
        self._fade = 0.0
        self._waveform = []
        self._prev_waveform = []
        self._waveform_count = 0
        self._bubble_pos_data = []
        self._bubble_extra_data = []
        self._bubble_trail_data = []
        self._bubble_count = 0
        reset_overlay_spectrum_solid_hysteresis_state(self)

        if self._gl_state.is_ready():
            try:
                self.makeCurrent()
                gl.glDisable(gl.GL_SCISSOR_TEST)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to clear overlay buffer", exc_info=True)
            finally:
                try:
                    self.doneCurrent()
                except Exception:
                    pass

        self.update()

    # ------------------------------------------------------------------
    # GL State Management Helpers
    # ------------------------------------------------------------------
    
    def is_gl_ready(self) -> bool:
        """Check if GL context is ready for rendering."""
        return self._gl_state.is_ready()
    
    def get_gl_state(self) -> GLContextState:
        """Get current GL context state."""
        return self._gl_state.get_state()

    # ------------------------------------------------------------------
    # QOpenGLWidget hooks
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:  # type: ignore[override]
        """Create the small shader pipeline used for bar rendering.

        Any failure here is treated as non-fatal – the widget will skip
        rendering until the GL pipeline recovers.
        """
        # Transition to INITIALIZING state
        if not self._gl_state.transition(GLContextState.INITIALIZING):
            logger.warning("[SPOTIFY_VIS] Failed to transition to INITIALIZING state")
            return

        try:
            self._init_gl_pipeline()
            # Transition to READY state on success
            self._gl_state.transition(GLContextState.READY)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to initialise GL pipeline for SpotifyBarsGLOverlay", exc_info=True)
            self._gl_state.transition(GLContextState.ERROR, str(e))
        
        # GLStateManager now tracks initialization state - no separate flag needed

    def paintGL(self) -> None:  # type: ignore[override]
        self._perf_paint_count += 1
        # Skip rendering until initializeGL has completed to avoid
        # uninitialized buffer artifacts (green dots on first frame)
        # Use GLStateManager for proper state tracking
        if not self._gl_state.is_ready() and not self._gl_state.is_error():
            return

        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Always clear the backing buffer so stale frames do not linger when
        # the overlay is disabled between mode switches.
        clear_overlay_backbuffer(gl, logger)

        fade = resolve_frame_fade(self, logger)
        if fade is None:
            return

        render_overlay_frame(self, rect, fade, self._render_with_shader)

        # set_state() is the repaint authority.  Scheduling from paintGL()
        # creates a child-GL self-loop that can overdrive the owning display.
        self._maybe_log_perf_counters(reason="paintGL")

    def _begin_painted_card_stencil_clip(self, rect: QRect) -> bool:
        if not self._painted_frame_shadow_enabled:
            return False
        try:
            gl.glEnable(gl.GL_STENCIL_TEST)
            gl.glStencilMask(0xFF)
            gl.glClear(gl.GL_STENCIL_BUFFER_BIT)
            gl.glColorMask(False, False, False, False)
            gl.glStencilFunc(gl.GL_ALWAYS, 1, 0xFF)
            gl.glStencilOp(gl.GL_KEEP, gl.GL_KEEP, gl.GL_REPLACE)

            if self._gl_mask_program and self._gl_vao:
                self._draw_painted_card_stencil_mask(rect)

            gl.glColorMask(True, True, True, True)
            gl.glStencilFunc(gl.GL_EQUAL, 1, 0xFF)
            gl.glStencilOp(gl.GL_KEEP, gl.GL_KEEP, gl.GL_KEEP)
            return True
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Stencil mask setup failed: %s", e)
            return False

    def _draw_painted_card_stencil_mask(self, rect: QRect) -> None:
        dpr = self._get_dpr()
        uniforms = compute_painted_card_mask_uniforms(
            rect,
            dpr=dpr,
            border_width_px=self._border_width_px,
            shrink_right=int(PAINTED_FRAME_SHADOW_TUNING["card_shrink_right"]),
            shrink_bottom=int(PAINTED_FRAME_SHADOW_TUNING["card_shrink_bottom"]),
            radius_extra=int(PAINTED_FRAME_SHADOW_TUNING.get("radius_extra", 0)),
        )

        gl.glUseProgram(self._gl_mask_program)
        loc_rect = gl.glGetUniformLocation(self._gl_mask_program, "u_card_rect")
        loc_radius = gl.glGetUniformLocation(self._gl_mask_program, "u_radius")
        gl.glUniform4f(
            loc_rect,
            uniforms.rect_x_px,
            uniforms.rect_y_px,
            uniforms.rect_w_px,
            uniforms.rect_h_px,
        )
        gl.glUniform1f(loc_radius, uniforms.radius_px)
        gl.glBindVertexArray(self._gl_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)
        gl.glUseProgram(0)

    def _end_painted_card_stencil_clip(self, stencil_active: bool) -> None:
        if not stencil_active:
            return
        gl.glDisable(gl.GL_STENCIL_TEST)
        gl.glStencilMask(0x00)

    def _filter_stage_progress(
        self,
        new_progress: tuple[float, float, float],
        dt: float,
    ) -> tuple[float, float, float]:
        new_clamped = tuple(max(0.0, min(1.0, v)) for v in new_progress)

        filtered: List[float] = []
        # Keep the first stage breathing. Stage 1 is the main size-support rung,
        # higher-order motion is left to twitch on top.
        decay_taus = (0.24, stage2_tau, stage3_tau)
        rise_tau = 0.020
        for idx, (prev_val, new_val) in enumerate(zip(prev, new_clamped)):
            if new_val >= prev_val:
                alpha = min(1.0, dt / rise_tau)
            else:
                decay_tau = decay_taus[idx] if idx < len(decay_taus) else 0.65
                if new_val <= 0.02:
                    decay_tau *= (0.55, 0.72, 0.72)[idx]
                if new_val <= 0.02 and prev_val >= 0.80:
                    hot_excess = min(1.0, (prev_val - 0.80) / 0.40)
                    decay_tau *= 1.0 - hot_excess * (0.48, 0.34, 0.34)[idx]
                alpha = min(1.0, dt / decay_tau)
            filtered.append(prev_val + (new_val - prev_val) * alpha)
        filtered[1] = min(filtered[1], filtered[0])
        filtered[2] = min(filtered[2], filtered[1])
        return (filtered[0], filtered[1], filtered[2])



    def _apply_floor_snapshot(self, floor_snapshot: dict | None) -> None:
        if not isinstance(floor_snapshot, dict):
            self._continuous_floor_dynamic_enabled = False
            self._continuous_floor_manual = 0.12
            self._continuous_floor_applied = 0.12
            self._continuous_floor_pressure = 0.0
            return

        try:
            dynamic_enabled = bool(floor_snapshot.get('dynamic_enabled', False))
        except Exception:
            dynamic_enabled = False
        try:
            manual_floor = float(floor_snapshot.get('manual_floor', 0.12) or 0.12)
        except Exception:
            manual_floor = 0.12
        try:
            gate_floor = float(floor_snapshot.get('gate_floor', manual_floor) or manual_floor)
        except Exception:
            gate_floor = manual_floor
        try:
            support_pressure = float(floor_snapshot.get('support_pressure', 0.0) or 0.0)
        except Exception:
            support_pressure = 0.0

        self._continuous_floor_dynamic_enabled = dynamic_enabled
        self._continuous_floor_manual = max(0.0, min(1.0, manual_floor))
        self._continuous_floor_applied = max(0.0, min(1.0, gate_floor))
        self._continuous_floor_pressure = max(
            0.0,
            min(1.0, support_pressure if dynamic_enabled else 0.0),
        )





    # ------------------------------------------------------------------
    # Internal rendering helpers
    # ------------------------------------------------------------------

    def _init_gl_pipeline(self) -> None:
        if self._gl_disabled or self._gl_programs:
            return

        from OpenGL import GL as _gl
        from widgets.spotify_visualizer.shaders import (
            SHARED_VERTEX_SHADER,
            load_all_fragment_shaders,
        )

        # Load all fragment shader sources from external files
        frag_sources = load_all_fragment_shaders()
        if not frag_sources:
            raise RuntimeError("No visualizer shaders could be loaded")

        vs_source = SHARED_VERTEX_SHADER

        # Compile the shared vertex shader once
        vs = _gl.glCreateShader(_gl.GL_VERTEX_SHADER)
        _gl.glShaderSource(vs, vs_source)
        _gl.glCompileShader(vs)
        if not _gl.glGetShaderiv(vs, _gl.GL_COMPILE_STATUS):
            info = _gl.glGetShaderInfoLog(vs)
            raise RuntimeError(f"Vertex shader compile failed: {info}")

        startup_program_key = resolve_render_program_key(self, self._vis_mode)
        compile_order = prioritized_visualizer_compile_order(startup_program_key, list(frag_sources.keys()))
        active_mode = compile_order[0] if compile_order else startup_program_key
        if active_mode and active_mode in frag_sources:
            self._compile_gl_mode_program(active_mode, frag_sources[active_mode], vs, _gl)

        _gl.glDeleteShader(vs)

        if not self._gl_programs:
            raise RuntimeError("No visualizer shader programs compiled successfully")

        # Legacy alias for backward compat checks
        self._gl_program = next(iter(self._gl_programs.values()))

        # Create shared VAO/VBO (fullscreen quad, reused by all modes)
        vao = _gl.glGenVertexArrays(1)
        vbo = _gl.glGenBuffers(1)

        _gl.glBindVertexArray(vao)
        _gl.glBindBuffer(_gl.GL_ARRAY_BUFFER, vbo)
        vertices = np.array(
            [-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0],
            dtype="float32",
        )
        _gl.glBufferData(
            _gl.GL_ARRAY_BUFFER,
            int(vertices.nbytes),
            vertices,
            _gl.GL_STATIC_DRAW,
        )
        _gl.glEnableVertexAttribArray(0)
        _gl.glVertexAttribPointer(0, 2, _gl.GL_FLOAT, False, 0, None)
        _gl.glBindVertexArray(0)

        self._gl_vao = vao
        self._gl_vbo = vbo

        # --- Compile rounded-rect stencil mask shader (reuses shared vertex shader) ---
        _MASK_FRAGMENT_SHADER = """#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform vec4 u_card_rect;
uniform float u_radius;
float roundedRectSDF(vec2 p, vec2 halfSize, float radius) {
    vec2 d = abs(p) - halfSize + radius;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - radius;
}
void main() {
    vec2 center = u_card_rect.xy + u_card_rect.zw * 0.5;
    vec2 halfSize = u_card_rect.zw * 0.5;
    float dist = roundedRectSDF(gl_FragCoord.xy - center, halfSize, u_radius);
    if (dist > 0.0) {
        discard;
    }
    fragColor = vec4(1.0);
}
"""
        try:
            fs_mask = _gl.glCreateShader(_gl.GL_FRAGMENT_SHADER)
            _gl.glShaderSource(fs_mask, _MASK_FRAGMENT_SHADER)
            _gl.glCompileShader(fs_mask)
            if not _gl.glGetShaderiv(fs_mask, _gl.GL_COMPILE_STATUS):
                info = _gl.glGetShaderInfoLog(fs_mask)
                logger.warning("[SPOTIFY_VIS] Mask fragment shader compile failed: %s", info)
                _gl.glDeleteShader(fs_mask)
            else:
                prog_mask = _gl.glCreateProgram()
                _gl.glAttachShader(prog_mask, vs)
                _gl.glAttachShader(prog_mask, fs_mask)
                _gl.glLinkProgram(prog_mask)
                _gl.glDeleteShader(fs_mask)
                if _gl.glGetProgramiv(prog_mask, _gl.GL_LINK_STATUS):
                    self._gl_mask_program = prog_mask
                else:
                    info = _gl.glGetProgramInfoLog(prog_mask)
                    logger.warning("[SPOTIFY_VIS] Mask program link failed: %s", info)
                    _gl.glDeleteProgram(prog_mask)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Mask shader setup failed", exc_info=True)

        # Register GL handles with ResourceManager for passive accounting.
        try:
            from core.resources.manager import ResourceManager
            rm = ResourceManager.get_or_create_app_shared()
            self._gl_vao_rid = rm.register_gl_handle(
                vao, "vao",
                description="SpotifyBarsGLOverlay VAO",
                group="spotify_vis_gl",
                owner=f"{type(self).__name__}:{id(self)}",
                generation=id(self),
                dimensions=None,
                format="VERTEX_ARRAY",
                tracked_bytes=None,
            )
            self._gl_vbo_rid = rm.register_gl_handle(
                vbo, "vbo",
                description="SpotifyBarsGLOverlay VBO",
                group="spotify_vis_gl",
                owner=f"{type(self).__name__}:{id(self)}",
                generation=id(self),
                dimensions=(4, 2),
                format="float32[x,y]",
                tracked_bytes=int(vertices.nbytes),
            )
            logger.debug("[SPOTIFY_VIS] GL handles registered with ResourceManager")
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to register GL handles: %s", e)
            self._gl_vao_rid = None
            self._gl_vbo_rid = None

        logger.info(
            "[SPOTIFY_VIS] Startup shader ready: active_mode=%s program=%s compiled=%s pending=%s",
            self._vis_mode,
            startup_program_key,
            ", ".join(sorted(self._gl_programs.keys())),
            ", ".join(mode for mode in compile_order[1:] if mode not in self._gl_programs),
        )
        self._schedule_gl_program_warmup_queue([mode for mode in compile_order[1:] if mode in frag_sources])

    def _compile_gl_mode_program(self, mode: str, fs_source: str, vs: int, _gl) -> bool:
        if mode in self._gl_programs:
            return True
        try:
            fs = _gl.glCreateShader(_gl.GL_FRAGMENT_SHADER)
            _gl.glShaderSource(fs, fs_source)
            _gl.glCompileShader(fs)
            if not _gl.glGetShaderiv(fs, _gl.GL_COMPILE_STATUS):
                info = _gl.glGetShaderInfoLog(fs)
                logger.warning("[SPOTIFY_VIS] %s frag shader compile failed: %s", mode, info)
                _gl.glDeleteShader(fs)
                return False

            prog = _gl.glCreateProgram()
            _gl.glAttachShader(prog, vs)
            _gl.glAttachShader(prog, fs)
            _gl.glLinkProgram(prog)
            _gl.glDeleteShader(fs)

            if not _gl.glGetProgramiv(prog, _gl.GL_LINK_STATUS):
                info = _gl.glGetProgramInfoLog(prog)
                logger.warning("[SPOTIFY_VIS] %s program link failed: %s", mode, info)
                _gl.glDeleteProgram(prog)
                return False

            uniforms = {}
            for uname in (
                "u_resolution", "u_dpr", "u_fade", "u_time",
                "u_border_width",
                "u_bar_count", "u_segments", "u_bar_height_scale", "u_single_piece",
                "u_bars", "u_peaks",
                "u_fill_color", "u_border_color", "u_playing", "u_ghost_alpha",
                "u_waveform", "u_waveform_count",
                "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
                "u_glow_enabled", "u_glow_intensity", "u_glow_size", "u_glow_reactivity",
                "u_glow_color", "u_reactive_glow",
                "u_sensitivity", "u_smoothing",
                "u_osc_speed", "u_osc_line_dim",
                "u_osc_line_offset_bias",
                "u_osc_vertical_shift",
                "u_sine_speed", "u_sine_line_dim",
                "u_sine_line_offset_bias",
                "u_sine_vertical_shift",
                "u_sine_travel",
                "u_card_adaptation",
                "u_sine_travel_line2", "u_sine_travel_line3",
                "u_sine_travel_line4", "u_sine_travel_line5", "u_sine_travel_line6",
                "u_wave_effect", "u_micro_wobble", "u_crawl_amount", "u_width_reaction",
                "u_sine_density", "u_sine_displacement",
                "u_line_color", "u_line_count",
                "u_line2_color", "u_line2_glow_color",
                "u_line3_color", "u_line3_glow_color",
                "u_line4_color", "u_line4_glow_color",
                "u_line5_color", "u_line5_glow_color",
                "u_line6_color", "u_line6_glow_color",
                "u_slanted", "u_border_radius",
                "u_spectrum_glow_enabled", "u_spectrum_glow_intensity", "u_spectrum_glow_color",
                "u_rainbow_hue_offset", "u_rainbow_per_bar", "u_rainbow_border",
                "u_prev_waveform", "u_osc_ghost_alpha",
                "u_ghost_line2_enabled", "u_ghost_line3_enabled",
                "u_ghost_line4_enabled", "u_ghost_line5_enabled", "u_ghost_line6_enabled",
                "u_heartbeat", "u_heartbeat_intensity",
                "u_bubble_count", "u_bubbles_pos", "u_bubbles_extra",
                "u_bubbles_trail", "u_trail_strength", "u_tail_opacity",
                "u_specular_dir", "u_gradient_dir", "u_gradient_mode", "u_outline_color", "u_specular_color",
                "u_gradient_light", "u_gradient_dark", "u_pop_color",
                "u_sine_line1_shift", "u_sine_line2_shift", "u_sine_line3_shift",
                "u_sine_line4_shift", "u_sine_line5_shift", "u_sine_line6_shift",
                "u_ghost_bass", "u_ghost_mid", "u_ghost_high",
            ):
                uniforms[uname] = _gl.glGetUniformLocation(prog, _uniform_lookup_name(uname))

            try:
                from widgets.spotify_visualizer.renderers import get_all_uniform_names
                for uname in get_all_uniform_names(mode):
                    if not uname or uname in uniforms:
                        continue
                    uniforms[uname] = _gl.glGetUniformLocation(prog, _uniform_lookup_name(uname))
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to query renderer uniform names for %s", mode, exc_info=True)

            self._gl_programs[mode] = prog
            self._gl_uniforms[mode] = uniforms
            if self._gl_program is None:
                self._gl_program = prog
            self._register_gl_program_handle(mode, prog)
            return True
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to compile %s shader", mode, exc_info=True)
            return False

    def _register_gl_program_handle(self, mode: str, prog: int) -> None:
        try:
            from core.resources.manager import ResourceManager
            rm = ResourceManager.get_or_create_app_shared()
            rid = rm.register_gl_handle(
                prog, "program",
                description=f"SpotifyBarsGLOverlay {mode} shader",
                group="spotify_vis_gl",
                owner=f"{type(self).__name__}:{id(self)}",
                generation=id(self),
                dimensions=None,
                format="GL_PROGRAM",
                tracked_bytes=None,
            )
            self._gl_program_rids[mode] = rid
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to register %s GL handle: %s", mode, e)

    def _warm_next_gl_program(self) -> None:
        if self._gl_disabled or not self._gl_program_warm_queue:
            return
        if not self._gl_state.is_ready():
            self._schedule_gl_program_warmup_queue(self._gl_program_warm_queue)
            return
        from OpenGL import GL as _gl
        from widgets.spotify_visualizer.shaders import SHARED_VERTEX_SHADER, load_fragment_shader
        try:
            self.makeCurrent()
            vs = _gl.glCreateShader(_gl.GL_VERTEX_SHADER)
            _gl.glShaderSource(vs, SHARED_VERTEX_SHADER)
            _gl.glCompileShader(vs)
            if not _gl.glGetShaderiv(vs, _gl.GL_COMPILE_STATUS):
                info = _gl.glGetShaderInfoLog(vs)
                raise RuntimeError(f"Vertex shader compile failed: {info}")
            mode = self._gl_program_warm_queue.pop(0)
            fs_source = load_fragment_shader(mode)
            if fs_source:
                self._compile_gl_mode_program(mode, fs_source, vs, _gl)
            _gl.glDeleteShader(vs)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Deferred program warmup failed", exc_info=True)
        finally:
            try:
                self.doneCurrent()
            except Exception:
                logger.debug("[SPOTIFY_VIS] doneCurrent failed after deferred shader warmup", exc_info=True)
        if self._gl_program_warm_queue:
            self._schedule_gl_program_warmup_queue(self._gl_program_warm_queue)

    def _schedule_gl_program_warmup_queue(self, modes: Sequence[str]) -> None:
        queue = [mode for mode in modes if mode not in self._gl_programs]
        self._gl_program_warm_queue = queue
        if not queue:
            return
        if self._gl_program_warm_timer is None:
            self._gl_program_warm_timer = QTimer(self)
            self._gl_program_warm_timer.setSingleShot(True)
            self._gl_program_warm_timer.timeout.connect(self._warm_next_gl_program)
        self._gl_program_warm_timer.start(140)

    def cleanup_gl(self) -> None:
        """Strictly delete every overlay-owned GL handle on its owner context."""
        if self._gl_program_warm_timer is not None:
            try:
                self._gl_program_warm_timer.stop()
            except Exception as exc:
                logger.debug("[SPOTIFY_VIS] Failed to stop deferred warm timer: %s", exc)
        self._gl_program_warm_queue = []

        live_resources = bool(
            self._gl_programs
            or self._gl_program is not None
            or self._gl_mask_program is not None
            or self._gl_vbo is not None
            or self._gl_vao is not None
        )
        state = self._gl_state.get_state()
        if state == GLContextState.DESTROYED:
            if live_resources:
                raise RuntimeError("Visualizer overlay is DESTROYED with live GL resources")
            return

        if not live_resources:
            if state == GLContextState.DESTROYING:
                try:
                    self.doneCurrent()
                except Exception as exc:
                    raise RuntimeError(
                        "Visualizer overlay context release remains incomplete"
                    ) from exc
            if state in {
                GLContextState.READY,
                GLContextState.ERROR,
                GLContextState.CONTEXT_LOST,
            }:
                if not self._gl_state.transition(GLContextState.DESTROYING):
                    raise RuntimeError("Visualizer overlay could not enter DESTROYING")
            if self._gl_state.get_state() != GLContextState.DESTROYED:
                if not self._gl_state.transition(GLContextState.DESTROYED):
                    raise RuntimeError("Visualizer overlay could not enter DESTROYED")
            return

        application = QCoreApplication.instance()
        if application is not None and QThread.currentThread() is not application.thread():
            raise RuntimeError("Visualizer overlay GL teardown must run on the GUI thread")
        if not self.isValid():
            raise RuntimeError("Cannot delete live visualizer GL resources: context is invalid")
        if state != GLContextState.DESTROYING:
            if not self._gl_state.transition(GLContextState.DESTROYING):
                raise RuntimeError("Visualizer overlay could not enter DESTROYING")

        try:
            self.makeCurrent()
        except Exception as exc:
            raise RuntimeError(
                "Cannot delete live visualizer GL resources: makeCurrent() failed"
            ) from exc

        expected_context = self.context()
        if expected_context is not None and QOpenGLContext.currentContext() != expected_context:
            try:
                self.doneCurrent()
            finally:
                raise RuntimeError(
                    "Cannot delete live visualizer GL resources: owner context is not current"
                )

        errors: list[str] = []
        if (
            self._gl_program is not None
            and int(self._gl_program) not in {int(value) for value in self._gl_programs.values()}
        ):
            errors.append(f"untracked_program:{int(self._gl_program)}")
        try:
            for mode, program_id in list(self._gl_programs.items()):
                try:
                    gl.glDeleteProgram(int(program_id))
                except Exception as exc:
                    errors.append(f"program:{mode}:{type(exc).__name__}:{exc}")
                    continue
                self._gl_programs.pop(mode, None)
                self._gl_uniforms.pop(mode, None)
                self._release_resource_tracking(self._gl_program_rids.pop(mode, None))

            if self._gl_mask_program is not None:
                try:
                    gl.glDeleteProgram(int(self._gl_mask_program))
                except Exception as exc:
                    errors.append(f"mask_program:{type(exc).__name__}:{exc}")
                else:
                    self._gl_mask_program = None

            if self._gl_vbo is not None:
                try:
                    gl.glDeleteBuffers(1, [int(self._gl_vbo)])
                except Exception as exc:
                    errors.append(f"vbo:{type(exc).__name__}:{exc}")
                else:
                    self._gl_vbo = None
                    self._release_resource_tracking(self._gl_vbo_rid)
                    self._gl_vbo_rid = None

            if self._gl_vao is not None:
                try:
                    gl.glDeleteVertexArrays(1, [int(self._gl_vao)])
                except Exception as exc:
                    errors.append(f"vao:{type(exc).__name__}:{exc}")
                else:
                    self._gl_vao = None
                    self._release_resource_tracking(self._gl_vao_rid)
                    self._gl_vao_rid = None
        finally:
            try:
                self.doneCurrent()
            except Exception as exc:
                errors.append(f"doneCurrent:{type(exc).__name__}:{exc}")

        self._gl_program = next(iter(self._gl_programs.values()), None)
        if errors:
            raise RuntimeError(
                "Visualizer overlay GL resource deletion incomplete: " + " | ".join(errors)
            )

        self._gl_uniforms.clear()
        self._gl_program_rids.clear()
        if not self._gl_state.transition(GLContextState.DESTROYED):
            raise RuntimeError("Visualizer overlay could not enter DESTROYED")
        logger.debug("[SPOTIFY_VIS] GL handles cleaned up")

    @staticmethod
    def _release_resource_tracking(resource_id: str | None) -> None:
        if not resource_id:
            return
        try:
            from core.resources.manager import ResourceManager
            manager = ResourceManager.get_app_shared()
            if manager is not None:
                manager.release_tracking(resource_id)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to release GL resource tracking", exc_info=True)

    def _get_dpr(self) -> float:
        """Resolve device pixel ratio for the backing FBO."""
        dpr = 1.0
        try:
            win = self.windowHandle()
        except Exception:
            win = None
        if win is not None:
            try:
                dpr = float(win.devicePixelRatio())
            except Exception:
                dpr = 1.0
        else:
            try:
                dpr = float(self.devicePixelRatioF())
            except Exception:
                dpr = 1.0
        if dpr <= 0.0:
            dpr = 1.0
        if dpr > 4.0:
            dpr = 4.0
        return dpr

    def _render_with_shader(self, rect: QRect, fade: float) -> bool:
        if self._gl_disabled:
            return False

        try:
            if not self._gl_programs or self._gl_vao is None:
                self._init_gl_pipeline()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._gl_disabled = True
            logger.debug("[SPOTIFY_VIS] GL pipeline unavailable, skipping render", exc_info=True)
            return False

        if not self._gl_programs or self._gl_vao is None:
            return False

        mode = self._vis_mode
        width = rect.width()
        height = rect.height()
        if width <= 0 or height <= 0:
            return False

        # Store rect for renderer access (e.g. spectrum height scale)
        self._render_rect = rect

        try:
            from OpenGL import GL as _gl

            prog = resolve_mode_program(self, _gl, mode, logger)
            if prog is None:
                return False

            u = self._gl_uniforms.get(resolve_render_program_key(self, mode), {})

            _gl.glUseProgram(prog)
            _gl.glBindVertexArray(self._gl_vao)

            upload_common_uniforms(_gl, u, self, mode, width, height, fade, logger)

            if not dispatch_mode_uniforms(_gl, mode, u, self):
                _gl.glBindVertexArray(0)
                _gl.glUseProgram(0)
                return False

            # --- Draw ---
            _gl.glDrawArrays(_gl.GL_TRIANGLE_STRIP, 0, 4)
            _gl.glBindVertexArray(0)
            _gl.glUseProgram(0)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Shader-based rendering failed (mode=%s)", mode, exc_info=True)
            return False

        return True


