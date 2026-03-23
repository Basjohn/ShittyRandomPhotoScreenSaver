from __future__ import annotations

from typing import List, Sequence, Optional, Set

import numpy as np
import time
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import (
    get_logger,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
)
from rendering.gl_format import apply_widget_surface_format
from rendering.gl_state_manager import GLStateManager, GLContextState
from OpenGL import GL as gl
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands
from widgets.spotify_visualizer.blob_math import (
    compute_stage_progress,
)


logger = get_logger(__name__)


class SpotifyBarsGLOverlay(QOpenGLWidget):
    """Small GL surface that renders the Spotify bar field.

    This overlay is parented to ``DisplayWidget`` and positioned so that it
    exactly covers the Spotify visualiser card. The card itself (background,
    border, fade, shadow) continues to be drawn by ``SpotifyVisualizerWidget``;
    this class is responsible only for the bar geometry.
    """

    def __init__(self, parent=None) -> None:  # type: ignore[override]
        super().__init__(parent)

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
        
        # Active visualization mode
        self._vis_mode: str = 'spectrum'

        # Accumulated time for animated visualizers (seconds)
        self._accumulated_time: float = 0.0
        self._last_time_ts: float = 0.0
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

        # Energy bands for blob
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
        self._osc_line_amplitude: float = 3.0
        self._osc_smoothing: float = 0.7

        # Oscilloscope multi-line
        self._osc_line_count: int = 1
        self._osc_line2_color: QColor = QColor(255, 120, 50, 230)
        self._osc_line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._osc_line3_color: QColor = QColor(50, 255, 120, 230)
        self._osc_line3_glow_color: QColor = QColor(50, 255, 120, 180)
        self._osc_ghost_line2_enabled: bool = True
        self._osc_ghost_line3_enabled: bool = True


        # Blob settings
        self._blob_color: QColor = QColor(0, 180, 255, 230)
        self._blob_glow_color: QColor = QColor(0, 140, 255, 180)
        self._blob_edge_color: QColor = QColor(100, 220, 255, 230)
        self._blob_outline_color: QColor = QColor(0, 0, 0, 0)  # dark band between fill and glow
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
        self._blob_stretch_inner: float = 0.5
        self._blob_stretch_outer: float = 0.5
        self._blob_smoothed_energy: float = 0.0
        self._blob_raw_bass_energy: float = 0.0
        self._blob_raw_mid_energy: float = 0.0
        self._blob_raw_high_energy: float = 0.0
        self._blob_raw_overall_energy: float = 0.0
        self._blob_live_bass_energy: float = 0.0
        self._blob_live_mid_energy: float = 0.0
        self._blob_live_high_energy: float = 0.0
        self._blob_live_overall_energy: float = 0.0
        self._blob_peak_energy: float = 0.0
        self._blob_peak_bass: float = 0.0
        self._blob_peak_mid: float = 0.0
        self._blob_peak_high: float = 0.0
        self._blob_peak_overall: float = 0.0
        self._blob_seed_pending: bool = False
        self._osc_speed: float = 1.0
        self._osc_line_dim: bool = False  # optional half-strength dimming on lines 2/3
        self._osc_line_offset_bias: float = 0.0
        self._osc_vertical_shift: int = 0
        self._osc_sine_travel: int = 0  # 0=none, 1=left, 2=right (used by sine_wave mode)
        self._sine_card_adaptation: float = 0.30
        self._sine_travel_line2: int = 0  # per-line travel: 0=none, 1=left, 2=right
        self._sine_travel_line3: int = 0
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
        self._osc_smoothed_bass: float = 0.0  # CPU-side smoothed energy for osc glow
        self._osc_smoothed_mid: float = 0.0
        self._osc_smoothed_high: float = 0.0
        self._sine_wave_transient_width_mix: float = 0.4
        self._osc_transient_width_mix: float = 0.35
        self._blob_transient_mix_bass: float = 0.5
        self._blob_transient_mix_vocal: float = 0.35
        self._transient_clamp: float = 1.5
        self._blob_pulse_cap: float = 1.0
        self._blob_pulse_release_ms: float = 220.0
        # Sine wave ghost: peak-tracked energy per band (decays slowly)
        self._sine_peak_bass: float = 0.0
        self._sine_peak_mid: float = 0.0
        self._sine_peak_high: float = 0.0
        self._sine_peak_hold_remaining: float = 0.0
        self._glow_diag_last_ts: float = 0.0
        self._glow_diag_last_sig: tuple | None = None

        self._blob_stage_progress_raw: tuple[float, float, float] = (-1.0, -1.0, -1.0)
        self._blob_stage_progress_filtered: tuple[float, float, float] = (-1.0, -1.0, -1.0)
        self._blob_stage_progress_ready: bool = False
        self._blob_kick_event_strength: float = 0.0
        self._blob_snare_event_strength: float = 0.0
        self._blob_kick_event_envelope: float = 0.0
        self._blob_snare_event_envelope: float = 0.0
        self._blob_diag_last_ts: float = 0.0
        self._blob_diag_last_sig: tuple | None = None
        self._line_kick_event_strength: float = 0.0
        self._line_snare_event_strength: float = 0.0
        self._line_kick_event_envelope: float = 0.0
        self._line_snare_event_envelope: float = 0.0
        self._last_vis_mode: Optional[str] = None

        # Rainbow (Taste The Rainbow) mode
        self._rainbow_enabled: bool = False
        self._rainbow_speed: float = 0.5
        self._rainbow_per_bar: bool = False

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

        # Ghosting configuration – whether trailing segments are drawn and
        # how strong they appear relative to the main bar border colour. The
        # decay rate is controlled separately via _peak_decay_per_sec.
        self._ghosting_enabled: bool = True
        self._ghost_alpha: float = 0.4
        # Per-mode ghost fields (strict isolation, no cross-mode bleed)
        self._spectrum_ghosting_enabled: bool = True
        self._spectrum_ghost_alpha: float = 0.4
        self._spectrum_ghost_decay: float = 0.4
        self._blob_ghosting_enabled: bool = False
        self._blob_ghost_alpha: float = 0.4
        self._blob_ghost_decay: float = 0.3
        self._sine_ghosting_enabled: bool = True
        self._sine_ghost_alpha: float = 0.45
        self._sine_ghost_decay: float = 0.3
        self._sine_ghost_line2_enabled: bool = True
        self._sine_ghost_line3_enabled: bool = True
        self._bubble_ghosting_enabled: bool = False
        self._bubble_ghost_alpha: float = 0.0
        self._bubble_ghost_decay: float = 0.4

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
        self._gl_vao = None
        self._gl_vbo = None
        # ResourceManager resource IDs for GL handles (for cleanup tracking)
        self._gl_program_rids: _Dict[str, _Any] = {}
        self._gl_vao_rid = None
        self._gl_vbo: Optional[int] = None
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

        if not mode:
            return
        normalized = mode.lower()
        valid_modes = {
            'spectrum',
            'oscilloscope',
            'blob',
            'sine_wave',
            'bubble',
        }
        if normalized not in valid_modes:
            return
        self._pending_mode_resets.add(normalized)

    def _reset_mode_state(self, mode: str, *, reason: str) -> None:
        """Cold-reset per-mode accumulators so the next frame behaves like a fresh start."""

        mode_key = mode.lower() if mode else 'spectrum'
        self._accumulated_time = 0.0
        self._last_time_ts = 0.0

        if mode_key == 'blob':
            self.reset_blob_state()
        else:
            self._blob_stage_progress_ready = False
            self._blob_stage_progress_raw = (-1.0, -1.0, -1.0)
            self._blob_stage_progress_filtered = (-1.0, -1.0, -1.0)

        if mode_key in {'oscilloscope', 'sine_wave'}:
            self._waveform = []
            self._prev_waveform = []
            self._ghost_waveform_ring = []
            self._ghost_ring_idx = 0
            self._osc_smoothed_bass = 0.0
            self._osc_smoothed_mid = 0.0
            self._osc_smoothed_high = 0.0
            # Sine ghost peak state: clear to prevent stale peaks on mode re-entry
            self._sine_peak_bass = 0.0
            self._sine_peak_mid = 0.0
            self._sine_peak_high = 0.0
            self._sine_peak_hold_remaining = 0.0

        if mode_key == 'bubble':
            self._bubble_pos_data = []
            self._bubble_extra_data = []
            self._bubble_trail_data = []
            self._bubble_count = 0

        logger.info(
            "[SPOTIFY_VIS][OVERLAY][RESET] mode=%s reason=%s",
            mode_key,
            reason,
        )
        self._last_reset_mode = mode_key
        self._last_reset_reason = reason
        try:
            self._last_reset_ts = time.time()
        except Exception:
            self._last_reset_ts = 0.0

    def reset_blob_state(self) -> None:
        if not hasattr(self, "_blob_smoothed_energy"):
            self._blob_smoothed_energy = 0.0
        else:
            self._blob_smoothed_energy = 0.0
        self._blob_raw_bass_energy = 0.0
        self._blob_raw_mid_energy = 0.0
        self._blob_raw_high_energy = 0.0
        self._blob_raw_overall_energy = 0.0
        self._blob_live_bass_energy = 0.0
        self._blob_live_mid_energy = 0.0
        self._blob_live_high_energy = 0.0
        self._blob_live_overall_energy = 0.0
        self._blob_peak_energy = 0.0
        self._blob_peak_bass = 0.0
        self._blob_peak_mid = 0.0
        self._blob_peak_high = 0.0
        self._blob_peak_overall = 0.0
        self._blob_peak_hold_remaining = 0.0
        self._blob_stage_progress_raw = (-1.0, -1.0, -1.0)
        self._blob_stage_progress_filtered = (0.0, 0.0, 0.0)
        self._blob_stage_progress_ready = False
        self._blob_seed_pending = True
        self._blob_kick_event_strength = 0.0
        self._blob_snare_event_strength = 0.0
        self._blob_kick_event_envelope = 0.0
        self._blob_snare_event_envelope = 0.0
        self._blob_diag_last_ts = 0.0
        self._blob_diag_last_sig = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        osc_line_amplitude: float = 3.0,
        osc_sensitivity: float | None = None,
        osc_smoothing: float = 0.7,
        blob_color: QColor | None = None,
        blob_glow_color: QColor | None = None,
        blob_edge_color: QColor | None = None,
        blob_outline_color: QColor | None = None,
        blob_pulse: float = 1.0,
        blob_width: float = 1.0,
        blob_size: float = 1.0,
        blob_glow_intensity: float = 0.5,
        blob_reactive_glow: bool = True,
        blob_reactive_deformation: float = 1.0,
        blob_stage_gain: float = 1.0,
        blob_core_scale: float = 1.0,
        blob_core_floor_bias: float = 0.35,
        blob_stage_bias: float = 0.0,
        blob_stage2_release_ms: float = 900.0,
        blob_stage3_release_ms: float = 1200.0,
        blob_pulse_cap: float = 1.0,
        blob_pulse_release_ms: float = 220.0,
        blob_constant_wobble: float = 1.0,
        blob_reactive_wobble: float = 1.0,
        blob_stretch_tendency: float = 0.35,
        blob_stretch_inner: float = 0.5,
        blob_stretch_outer: float = 0.5,
        osc_speed: float = 1.0,
        osc_line_dim: bool = False,
        osc_line_offset_bias: float = 0.0,
        osc_vertical_shift: int = 0,
        osc_sine_travel: int = 0,
        sine_card_adaptation: float = 0.30,
        sine_travel_line2: int = 0,
        sine_travel_line3: int = 0,
        sine_wave_effect: float = 0.0,
        sine_micro_wobble: float = 0.0,
        sine_crawl_amount: float = 0.0,
        sine_vertical_shift: int = 0,
        sine_line1_shift: float = 0.0,
        sine_line2_shift: float = 0.0,
        sine_line3_shift: float = 0.0,
        sine_width_reaction: float = 0.0,
        sine_density: float = 1.0,
        sine_displacement: float = 0.0,
        line_color: QColor | None = None,
        osc_line_count: int = 1,
        osc_line2_color: QColor | None = None,
        osc_line2_glow_color: QColor | None = None,
        osc_line3_color: QColor | None = None,
        osc_line3_glow_color: QColor | None = None,
        osc_ghost_line2_enabled: bool = True,
        osc_ghost_line3_enabled: bool = True,
        single_piece: bool = False,
        slanted: bool = False,
        border_radius: float = 0.0,
        rainbow_enabled: bool = False,
        rainbow_speed: float = 0.5,
        rainbow_per_bar: bool = False,
        spectrum_glow_enabled: bool = False,
        spectrum_glow_intensity: float = 0.55,
        spectrum_glow_color: QColor | None = None,
        osc_ghosting_enabled: bool = False,
        osc_ghost_intensity: float = 0.4,
        spectrum_ghosting_enabled: bool = True,
        spectrum_ghost_alpha: float = 0.4,
        spectrum_ghost_decay: float = 0.4,
        blob_ghosting_enabled: bool = False,
        blob_ghost_alpha: float = 0.4,
        blob_ghost_decay: float = 0.3,
        sine_ghosting_enabled: bool = True,
        sine_ghost_alpha: float = 0.45,
        sine_ghost_decay: float = 0.3,
        sine_ghost_line2_enabled: bool = True,
        sine_ghost_line3_enabled: bool = True,
        bubble_ghosting_enabled: bool = False,
        bubble_ghost_alpha: float = 0.0,
        bubble_ghost_decay: float = 0.4,
        blob_glow_reactivity: float = 1.0,
        blob_glow_max_size: float = 1.0,
        sine_heartbeat: float = 0.0,
        heartbeat_intensity: float = 0.0,
        # Bubble mode
        bubble_count: int = 0,
        bubble_pos_data: list | None = None,
        bubble_extra_data: list | None = None,
        bubble_trail_data: list | None = None,
        bubble_trail_strength: float = 0.0,
        bubble_tail_opacity: float = 0.0,
        bubble_outline_color: QColor | None = None,
        bubble_specular_color: QColor | None = None,
        bubble_gradient_light: QColor | None = None,
        bubble_gradient_dark: QColor | None = None,
        bubble_pop_color: QColor | None = None,
        bubble_specular_direction: str = "top_left",
        bubble_gradient_direction: str = "top",
        border_width_px: float = 0.0,
        transient_energy: TransientEnergyBands | None = None,
        blob_kick_event_strength: float = 0.0,
        blob_snare_event_strength: float = 0.0,
        line_kick_event_strength: float = 0.0,
        line_snare_event_strength: float = 0.0,
    ) -> None:
        """Update overlay bar state and geometry.

        ``rect`` is specified in the parent ``DisplayWidget`` coordinate space
        and should usually be the geometry of the associated
        ``SpotifyVisualizerWidget``.
        """

        if not visible:
            self.clear_overlay_buffer()
            return

        # Set active visualizer mode
        prev_mode = self._vis_mode
        requested_mode = vis_mode if vis_mode in (
            'spectrum', 'oscilloscope', 'blob', 'sine_wave', 'bubble'
        ) else 'spectrum'
        self._vis_mode = requested_mode
        manual_reset = False
        if requested_mode in self._pending_mode_resets:
            manual_reset = True
            self._pending_mode_resets.discard(requested_mode)
        if prev_mode != self._vis_mode or manual_reset:
            reason = "mode_change" if prev_mode != self._vis_mode else "manual_reset"
            self._reset_mode_state(self._vis_mode, reason=reason)
            self._last_vis_mode = self._vis_mode
        try:
            self._border_width_px = max(0.0, float(border_width_px))
        except Exception:
            self._border_width_px = 0.0

        try:
            self._sine_density = float(sine_density)
        except Exception:
            self._sine_density = 1.0
        try:
            self._sine_displacement = float(sine_displacement)
        except Exception:
            self._sine_displacement = 0.0

        # Keep blob's live core, smoothed energy, peaks, and stage progress on
        # one coherent input snapshot per frame.
        if transient_energy is not None:
            self._transient_energy = transient_energy
        blob_kick_raw = max(0.0, min(1.0, float(blob_kick_event_strength)))
        blob_snare_raw = max(0.0, min(1.0, float(blob_snare_event_strength)))
        blob_live_bands: tuple[float, float, float, float] | None = None
        blob_live_bands_filtered: tuple[float, float, float, float] | None = None
        blob_prev_smoothed = self._blob_smoothed_energy
        blob_prev_stage_filtered = self._blob_stage_progress_filtered
        blob_dt_seconds = 0.0

        # Update accumulated time for animated modes
        dt_seconds = 0.0
        now_ts = time.time()
        if self._last_time_ts > 0.0:
            dt = now_ts - self._last_time_ts
            if 0.0 < dt < 1.0:  # sanity clamp
                dt_seconds = dt
                blob_dt = self._compute_blob_smoothing_dt(dt_seconds)
                blob_dt_seconds = blob_dt
                hitch_clamped = dt_seconds > (blob_dt + 0.020)
                kick_tau = 0.22 if blob_kick_raw < self._blob_kick_event_envelope else (0.08 if hitch_clamped else 0.05)
                snare_tau = 0.18 if blob_snare_raw < self._blob_snare_event_envelope else (0.07 if hitch_clamped else 0.05)
                kick_alpha = min(1.0, blob_dt / max(kick_tau, 0.01))
                snare_alpha = min(1.0, blob_dt / max(snare_tau, 0.01))
                self._blob_kick_event_envelope += (
                    blob_kick_raw - self._blob_kick_event_envelope
                ) * kick_alpha
                self._blob_snare_event_envelope += (
                    blob_snare_raw - self._blob_snare_event_envelope
                ) * snare_alpha
                self._blob_kick_event_strength = self._blob_kick_event_envelope
                self._blob_snare_event_strength = self._blob_snare_event_envelope
                if self._vis_mode == 'blob' and energy_bands is not None:
                    blob_live_bands = self._compute_blob_live_bands(energy_bands)
                # Gate rainbow hue rotation on playing state (issue 1.5)
                if playing:
                    self._accumulated_time += dt
                # Blob: smooth overall energy to reduce glow flickering
                if self._vis_mode == 'blob' and blob_live_bands is not None:
                    self._blob_raw_bass_energy = blob_live_bands[0]
                    self._blob_raw_mid_energy = blob_live_bands[1]
                    self._blob_raw_high_energy = blob_live_bands[2]
                    self._blob_raw_overall_energy = blob_live_bands[3]
                    live_bass, live_mid, live_high, live_overall = self._filter_blob_live_bands(
                        blob_live_bands,
                        blob_dt,
                    )
                    prev = self._blob_smoothed_energy
                    # Use a bass-weighted signal so vocal energy doesn't
                    # drive pulse/size.  Raw bands → single fast EMA.
                    raw_bass = self._blob_raw_bass_energy
                    raw_overall = self._blob_raw_overall_energy
                    se_input = raw_bass * 0.70 + raw_overall * 0.30
                    if se_input > prev:
                        # Magnitude-scaled rise: big jumps (kicks) snap fast,
                        # small wobbles (vocal flutter) get heavily damped.
                        _delta = se_input - prev
                        _mag = min(1.0, _delta / 0.12)
                        _rise_tau = 0.022 + (1.0 - _mag) * 0.10  # 22ms..122ms
                        alpha = min(1.0, blob_dt / _rise_tau)
                    else:
                        alpha = min(1.0, blob_dt / 0.35)
                    self._blob_smoothed_energy = prev + (se_input - prev) * alpha
                    self._blob_live_bass_energy = live_bass
                    self._blob_live_mid_energy = live_mid
                    self._blob_live_high_energy = live_high
                    self._blob_live_overall_energy = live_overall
                    blob_live_bands_filtered = (live_bass, live_mid, live_high, live_overall)
                    smoothed_e = self._blob_smoothed_energy
                    # Ghost peak: retain the same processed blob silhouette
                    # the live core is using, then hold/decay it separately.
                    any_peak_hit = False
                    if live_overall > self._blob_peak_energy:
                        self._blob_peak_energy = live_overall
                        any_peak_hit = True
                    if live_bass > self._blob_peak_bass:
                        self._blob_peak_bass = live_bass
                        any_peak_hit = True
                    if live_mid > self._blob_peak_mid:
                        self._blob_peak_mid = live_mid
                        any_peak_hit = True
                    if live_high > self._blob_peak_high:
                        self._blob_peak_high = live_high
                        any_peak_hit = True
                    if live_overall > self._blob_peak_overall:
                        self._blob_peak_overall = live_overall
                        any_peak_hit = True
                    if self._blob_ghosting_enabled:
                        if any_peak_hit:
                            self._blob_peak_hold_remaining = 0.15
                        hold = getattr(self, '_blob_peak_hold_remaining', 0.0)
                        if hold > 0.0:
                            self._blob_peak_hold_remaining = max(0.0, hold - blob_dt)
                        else:
                            decay_slider = max(0.1, min(1.0, self._peak_decay_per_sec / 2.0))
                            tau = 3.0 - decay_slider * 2.5
                            da = min(1.0, blob_dt / max(tau, 0.1))
                            self._blob_peak_energy += (smoothed_e - self._blob_peak_energy) * da
                            self._blob_peak_bass += (
                                smoothed_e * (live_bass / max(live_overall, 0.001)) - self._blob_peak_bass
                            ) * da
                            self._blob_peak_mid += (
                                smoothed_e * (live_mid / max(live_overall, 0.001)) - self._blob_peak_mid
                            ) * da
                            self._blob_peak_high += (
                                smoothed_e * (live_high / max(live_overall, 0.001)) - self._blob_peak_high
                            ) * da
                            self._blob_peak_overall += (smoothed_e - self._blob_peak_overall) * da
                        min_offset = max(0.06, smoothed_e * 0.12)
                        self._blob_peak_energy = max(self._blob_peak_energy, smoothed_e + min_offset)
                        self._blob_peak_bass = max(self._blob_peak_bass, live_bass + min_offset * 0.8)
                        self._blob_peak_mid = max(self._blob_peak_mid, live_mid + min_offset * 0.8)
                        self._blob_peak_high = max(self._blob_peak_high, live_high + min_offset * 0.8)
                        self._blob_peak_overall = max(self._blob_peak_overall, live_overall + min_offset)
                # Oscilloscope / Sine Wave: smooth per-band energy for glow anti-flicker
                if self._vis_mode in ('oscilloscope', 'sine_wave') and energy_bands is not None:
                    for attr, band in (
                        ('_osc_smoothed_bass', 'bass'),
                        ('_osc_smoothed_mid', 'mid'),
                        ('_osc_smoothed_high', 'high'),
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
                    min_off = max(0.40, self._osc_smoothed_bass * 0.50)
                    self._sine_peak_bass = max(self._sine_peak_bass, raw_bass + min_off)
                    self._sine_peak_mid = max(self._sine_peak_mid, raw_mid + min_off * 0.90)
                    self._sine_peak_high = max(self._sine_peak_high, raw_high + min_off * 0.80)
        else:
            self._blob_kick_event_envelope = blob_kick_raw
            self._blob_snare_event_envelope = blob_snare_raw
            self._blob_kick_event_strength = self._blob_kick_event_envelope
            self._blob_snare_event_strength = self._blob_snare_event_envelope
            if self._vis_mode == 'blob' and energy_bands is not None:
                blob_live_bands = self._compute_blob_live_bands(energy_bands)
                self._blob_raw_bass_energy = blob_live_bands[0]
                self._blob_raw_mid_energy = blob_live_bands[1]
                self._blob_raw_high_energy = blob_live_bands[2]
                self._blob_raw_overall_energy = blob_live_bands[3]
        self._last_time_ts = now_ts

        # Store waveform data (oscilloscope) with temporal smoothing via osc_speed
        if waveform is not None:
            # Push current waveform into ghost ring buffer before updating
            if self._waveform and self._osc_ghost_alpha > 0.001:
                ring = self._ghost_waveform_ring
                delay = self._ghost_delay_frames
                if len(ring) < delay:
                    ring.append(list(self._waveform))
                else:
                    ring[self._ghost_ring_idx % delay] = list(self._waveform)
                # Read the oldest entry as the ghost waveform
                oldest_idx = (self._ghost_ring_idx + 1) % max(1, len(ring))
                self._prev_waveform = ring[oldest_idx] if len(ring) > 0 else []
                self._ghost_ring_idx = (self._ghost_ring_idx + 1) % max(1, delay)
            new_wf = list(waveform)
            speed = self._osc_speed
            if speed < 0.99 and len(self._waveform) == len(new_wf) and len(new_wf) > 0:
                # Blend: low speed = slow change, high speed = instant update
                # alpha = speed^2 makes low values feel genuinely slow
                alpha = speed * speed
                self._waveform = [
                    old * (1.0 - alpha) + new * alpha
                    for old, new in zip(self._waveform, new_wf)
                ]
            else:
                self._waveform = new_wf
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
        self._blob_pulse_cap = max(0.0, min(2.0, float(blob_pulse_cap)))
        self._blob_pulse_release_ms = max(60.0, min(800.0, float(blob_pulse_release_ms)))

        # Store energy bands (all modes that need them)
        if energy_bands is not None:
            self._energy_bands = energy_bands
            # Blob stage progress is expensive — only compute when in blob mode
            if self._vis_mode == 'blob':
                bass_val, mid_val, high_val, overall_val = (
                    blob_live_bands_filtered
                    if blob_live_bands_filtered is not None
                    else blob_live_bands
                    if blob_live_bands is not None
                    else self._compute_blob_live_bands(energy_bands)
                )
                self._blob_live_bass_energy = bass_val
                self._blob_live_mid_energy = mid_val
                self._blob_live_high_energy = high_val
                self._blob_live_overall_energy = overall_val
                if self._blob_seed_pending:
                    seed_value = overall_val or bass_val or mid_val or high_val
                    if seed_value > 0.0:
                        self._blob_smoothed_energy = seed_value
                        self._blob_seed_pending = False
                stage_progress_bass = float(getattr(self, '_blob_stage_input_bass', bass_val) or bass_val)
                stage_progress_mid = float(getattr(self, '_blob_stage_input_mid', mid_val) or mid_val)
                stage_progress_high = float(getattr(self, '_blob_stage_input_high', high_val) or high_val)
                stage_progress_overall = float(getattr(self, '_blob_stage_input_overall', overall_val) or overall_val)
                stage_progress_raw = compute_stage_progress(
                    bass_energy=stage_progress_bass,
                    mid_energy=stage_progress_mid,
                    high_energy=stage_progress_high,
                    overall_energy=stage_progress_overall,
                    smoothed_energy=self._blob_smoothed_energy,
                    stage_bias=self._blob_stage_bias,
                )
                self._blob_stage_progress_raw = stage_progress_raw
                filtered = self._filter_stage_progress(
                    stage_progress_raw,
                    self._compute_blob_smoothing_dt(dt_seconds),
                )
                self._blob_stage_progress_filtered = filtered
                self._blob_stage_progress_ready = True
                self._maybe_log_blob_diagnostics(
                    dt_seconds=dt_seconds,
                    blob_dt=blob_dt_seconds,
                    kick_raw=blob_kick_raw,
                    snare_raw=blob_snare_raw,
                    raw_live=(
                        self._blob_raw_bass_energy,
                        self._blob_raw_mid_energy,
                        self._blob_raw_high_energy,
                        self._blob_raw_overall_energy,
                    ),
                    filtered_live=(
                        bass_val,
                        mid_val,
                        high_val,
                        overall_val,
                    ),
                    prev_smoothed=blob_prev_smoothed,
                    raw_e=overall_val,
                    smoothed_e=self._blob_smoothed_energy,
                    stage_raw=stage_progress_raw,
                    stage_filtered=filtered,
                    prev_stage_filtered=blob_prev_stage_filtered,
                )
                if not self._blob_ghosting_enabled:
                    self._blob_peak_energy = self._blob_smoothed_energy
                    self._blob_peak_bass = bass_val
                    self._blob_peak_mid = mid_val
                    self._blob_peak_high = high_val
                    self._blob_peak_overall = overall_val

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
        _amp_value = osc_line_amplitude if osc_sensitivity is None else osc_sensitivity
        self._osc_line_amplitude = max(0.5, min(10.0, float(_amp_value)))
        self._osc_smoothing = max(0.0, min(1.0, float(osc_smoothing)))

        # Multi-line oscilloscope
        self._osc_line_count = max(1, min(3, int(osc_line_count)))
        if osc_line2_color is not None:
            self._osc_line2_color = QColor(osc_line2_color)
        if osc_line2_glow_color is not None:
            self._osc_line2_glow_color = QColor(osc_line2_glow_color)
        if osc_line3_color is not None:
            self._osc_line3_color = QColor(osc_line3_color)
        if osc_line3_glow_color is not None:
            self._osc_line3_glow_color = QColor(osc_line3_glow_color)
        self._osc_ghost_line2_enabled = bool(osc_ghost_line2_enabled)
        self._osc_ghost_line3_enabled = bool(osc_ghost_line3_enabled)


        # Blob settings
        if blob_color is not None:
            self._blob_color = QColor(blob_color)
        if blob_glow_color is not None:
            self._blob_glow_color = QColor(blob_glow_color)
        if blob_edge_color is not None:
            self._blob_edge_color = QColor(blob_edge_color)
        if blob_outline_color is not None:
            self._blob_outline_color = QColor(blob_outline_color)
        self._blob_pulse = max(0.0, float(blob_pulse))
        self._blob_width = max(0.1, min(1.0, float(blob_width)))
        self._blob_size = max(0.3, min(2.0, float(blob_size)))
        self._blob_glow_intensity = max(0.0, min(1.0, float(blob_glow_intensity)))
        self._blob_glow_reactivity = max(0.0, min(2.0, float(blob_glow_reactivity)))
        self._blob_glow_max_size = max(0.1, min(3.0, float(blob_glow_max_size)))
        self._blob_reactive_glow = bool(blob_reactive_glow)
        self._blob_reactive_deformation = max(0.0, min(2.0, float(blob_reactive_deformation)))
        self._blob_stage_gain = max(0.0, min(2.0, float(blob_stage_gain)))
        self._blob_core_scale = max(0.25, min(2.5, float(blob_core_scale)))
        self._blob_core_floor_bias = max(0.0, min(0.6, float(blob_core_floor_bias)))
        self._blob_stage_bias = max(-0.60, min(0.60, float(blob_stage_bias)))
        self._blob_stage2_release_ms = max(50.0, min(5000.0, float(blob_stage2_release_ms)))
        self._blob_stage3_release_ms = max(50.0, min(5000.0, float(blob_stage3_release_ms)))
        self._blob_pulse_cap = max(0.0, min(2.0, float(blob_pulse_cap)))
        self._blob_pulse_release_ms = max(60.0, min(800.0, float(blob_pulse_release_ms)))
        self._blob_constant_wobble = max(0.0, min(2.0, float(blob_constant_wobble)))
        self._blob_reactive_wobble = max(0.0, min(2.0, float(blob_reactive_wobble)))
        self._blob_stretch_tendency = max(0.0, min(1.0, float(blob_stretch_tendency)))
        self._blob_stretch_inner = max(0.0, min(1.0, float(blob_stretch_inner)))
        self._blob_stretch_outer = max(0.0, min(1.0, float(blob_stretch_outer)))
        self._osc_speed = max(0.01, min(1.0, float(osc_speed)))
        self._osc_line_dim = bool(osc_line_dim)
        self._osc_line_offset_bias = max(0.0, min(1.0, float(osc_line_offset_bias)))
        self._osc_vertical_shift = max(-50, min(200, int(osc_vertical_shift)))
        self._osc_sine_travel = max(0, min(2, int(osc_sine_travel)))
        self._sine_card_adaptation = max(0.05, min(1.0, float(sine_card_adaptation)))
        self._sine_travel_line2 = max(0, min(2, int(sine_travel_line2)))
        self._sine_travel_line3 = max(0, min(2, int(sine_travel_line3)))
        self._sine_wave_effect = max(0.0, min(1.0, float(sine_wave_effect)))
        self._sine_micro_wobble = max(0.0, min(1.0, float(sine_micro_wobble)))
        self._sine_crawl_amount = max(0.0, min(1.0, float(sine_crawl_amount)))
        self._sine_vertical_shift = max(-50, min(200, int(sine_vertical_shift)))
        self._sine_line1_shift = max(-1.0, min(1.0, float(sine_line1_shift)))
        self._sine_line2_shift = max(-1.0, min(1.0, float(sine_line2_shift)))
        self._sine_line3_shift = max(-1.0, min(1.0, float(sine_line3_shift)))
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
        self._spectrum_glow_enabled = bool(spectrum_glow_enabled)
        self._spectrum_glow_intensity = max(0.0, min(1.5, float(spectrum_glow_intensity)))
        if spectrum_glow_color is not None:
            self._spectrum_glow_color = QColor(spectrum_glow_color)

        # Oscilloscope ghost trail
        self._osc_ghost_alpha = max(0.0, min(1.0, float(osc_ghost_intensity))) if osc_ghosting_enabled else 0.0

        # Sine Wave Heartbeat
        self._sine_heartbeat = max(0.0, min(1.0, float(sine_heartbeat)))
        self._heartbeat_intensity = max(0.0, min(1.0, float(heartbeat_intensity)))

        if is_viz_diagnostics_enabled() and self._vis_mode in ('oscilloscope', 'sine_wave', 'spectrum'):
            now_diag = time.time()
            if self._vis_mode == 'spectrum':
                diag_sig = (
                    self._vis_mode,
                    int(self._spectrum_glow_enabled),
                    round(float(self._spectrum_glow_intensity), 3),
                    tuple(int(c) for c in self._spectrum_glow_color.getRgb()),
                    int(self._bar_count),
                    round(float(getattr(self._energy_bands, 'bass', 0.0) or 0.0), 3),
                    round(float(getattr(self._energy_bands, 'mid', 0.0) or 0.0), 3),
                    round(float(getattr(self._energy_bands, 'high', 0.0) or 0.0), 3),
                    round(float(getattr(self._energy_bands, 'overall', 0.0) or 0.0), 3),
                )
            else:
                diag_sig = (
                    self._vis_mode,
                    int(self._glow_enabled),
                    round(float(self._glow_intensity), 3),
                    round(float(self._glow_reactivity), 3),
                    int(self._reactive_glow),
                    int(self._osc_line_count),
                    int(self._osc_ghost_line2_enabled),
                    int(self._osc_ghost_line3_enabled),
                    round(float(getattr(self._energy_bands, 'bass', 0.0) or 0.0), 3),
                    round(float(getattr(self._energy_bands, 'mid', 0.0) or 0.0), 3),
                    round(float(getattr(self._energy_bands, 'high', 0.0) or 0.0), 3),
                    round(float(getattr(self._energy_bands, 'overall', 0.0) or 0.0), 3),
                )
            if (
                (now_diag - self._glow_diag_last_ts) >= 0.5
                or diag_sig != self._glow_diag_last_sig
            ):
                if self._vis_mode == 'spectrum':
                    logger.info(
                        "[SPOTIFY_VIS][GLOW] mode=%s enabled=%s intensity=%.3f color=%s bar_count=%d energy(b=%.3f m=%.3f h=%.3f o=%.3f)",
                        self._vis_mode,
                        self._spectrum_glow_enabled,
                        self._spectrum_glow_intensity,
                        tuple(int(c) for c in self._spectrum_glow_color.getRgb()),
                        int(self._bar_count),
                        float(getattr(self._energy_bands, 'bass', 0.0) or 0.0),
                        float(getattr(self._energy_bands, 'mid', 0.0) or 0.0),
                        float(getattr(self._energy_bands, 'high', 0.0) or 0.0),
                        float(getattr(self._energy_bands, 'overall', 0.0) or 0.0),
                    )
                else:
                    logger.info(
                        "[SPOTIFY_VIS][GLOW] mode=%s enabled=%s intensity=%.3f reactivity=%.3f reactive=%s lines=%d ghost2=%s ghost3=%s energy(b=%.3f m=%.3f h=%.3f o=%.3f)",
                        self._vis_mode,
                        self._glow_enabled,
                        self._glow_intensity,
                        self._glow_reactivity,
                        self._reactive_glow,
                        int(self._osc_line_count),
                        self._osc_ghost_line2_enabled,
                        self._osc_ghost_line3_enabled,
                        float(getattr(self._energy_bands, 'bass', 0.0) or 0.0),
                        float(getattr(self._energy_bands, 'mid', 0.0) or 0.0),
                        float(getattr(self._energy_bands, 'high', 0.0) or 0.0),
                        float(getattr(self._energy_bands, 'overall', 0.0) or 0.0),
                    )
                self._glow_diag_last_ts = now_diag
                self._glow_diag_last_sig = diag_sig

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
        self._blob_ghosting_enabled = bool(blob_ghosting_enabled)
        self._blob_ghost_alpha = max(0.0, min(1.0, float(blob_ghost_alpha)))
        self._blob_ghost_decay = max(0.1, min(1.0, float(blob_ghost_decay)))
        self._sine_ghosting_enabled = bool(sine_ghosting_enabled)
        self._sine_ghost_alpha = max(0.0, min(1.0, float(sine_ghost_alpha)))
        self._sine_ghost_decay = max(0.1, min(1.0, float(sine_ghost_decay)))
        self._sine_ghost_line2_enabled = bool(sine_ghost_line2_enabled)
        self._sine_ghost_line3_enabled = bool(sine_ghost_line3_enabled)
        self._bubble_ghosting_enabled = bool(bubble_ghosting_enabled)
        self._bubble_ghost_alpha = max(0.0, min(1.0, float(bubble_ghost_alpha)))
        self._bubble_ghost_decay = max(0.1, min(1.0, float(bubble_ghost_decay)))

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
        # spectrum peak trails and blob peak energy use mode-local rates.
        if self._vis_mode == 'spectrum':
            self._peak_decay_per_sec = self._spectrum_ghost_decay * 2.0
        elif self._vis_mode == 'blob':
            self._peak_decay_per_sec = self._blob_ghost_decay * 2.0

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

        # Update per-bar peak state using the latest clamped values.
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
                    # New higher bar value becomes the next peak.
                    p = v
                else:
                    # Let the peak decay more slowly than the bar value so it
                    # stays above for a while and forms a visible trail, but
                    # bias the decay rate by the current peak/value gap so the
                    # highest (oldest) ghost segments shrink a little faster
                    # than the newer ones regardless of the global decay
                    # setting.
                    delta = p - v
                    if delta <= 0.0:
                        p = v
                    else:
                        # Scale the decay by a mild factor in [0.75, 1.5]
                        # based on how tall the trail currently is. Long
                        # trails (large delta) lose height a bit faster so
                        # their topmost segments disappear sooner, while small
                        # residual peaks decay more gently.
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

        _geom_start = time.time()
        if not clamped:
            self.clear_overlay_buffer()
            return
        try:
            cur_geom = None
            try:
                cur_geom = self.geometry()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                cur_geom = None
            if cur_geom is None or cur_geom != rect:
                self.setGeometry(rect)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set overlay geometry", exc_info=True)
        _geom_elapsed = (time.time() - _geom_start) * 1000.0

        _show_start = time.time()
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
                # Skip raise_() entirely - it's expensive and unnecessary
                # The overlay is created on top and stays there
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to show overlay", exc_info=True)
        _show_elapsed = (time.time() - _show_start) * 1000.0

        _update_start = time.time()
        self.update()
        _update_elapsed = (time.time() - _update_start) * 1000.0
        
        if is_perf_metrics_enabled() and (_geom_elapsed > 5.0 or _show_elapsed > 5.0 or _update_elapsed > 5.0):
            logger.warning("[PERF] [SPOTIFY_BARS_GL] set_state breakdown: geom=%.2fms, show=%.2fms, update=%.2fms",
                          _geom_elapsed, _show_elapsed, _update_elapsed)

    def clear_overlay_buffer(self) -> None:
        """Reset overlay state and clear the GL backing buffer."""

        self._enabled = False
        self._bars = []
        self._bar_count = 0
        self._segments = 0
        self._peaks = []
        self._fade = 0.0
        self._waveform = []
        self._prev_waveform = []
        self._bubble_pos_data = []
        self._bubble_extra_data = []
        self._bubble_trail_data = []

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

        Any failure here is treated as non-fatal – the widget will fall back
        to the QPainter implementation in paintGL.
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
        try:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        if not self._enabled:
            return

        try:
            fade = float(self._fade)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            fade = 0.0
        if fade <= 0.0:
            return

        # Prefer the shader path when available; fall back to QPainter when
        # the GL program or buffers are not ready or fail at runtime.
        used_shader = self._render_with_shader(rect, fade)
        if not used_shader:
            self._render_with_qpainter(rect, fade)

        self.update()

    def _filter_stage_progress(
        self,
        new_progress: tuple[float, float, float],
        dt: float,
    ) -> tuple[float, float, float]:
        new_clamped = tuple(max(0.0, min(1.0, v)) for v in new_progress)
        if not self._blob_stage_progress_ready or dt <= 0.0:
            return new_clamped

        prev = self._blob_stage_progress_filtered
        filtered: List[float] = []
        stage2_tau = max(0.05, self._blob_stage2_release_ms / 1000.0)
        stage3_tau = max(0.05, self._blob_stage3_release_ms / 1000.0)
        decay_taus = (0.40, stage2_tau, stage3_tau)
        rise_tau = 0.020
        for idx, (prev_val, new_val) in enumerate(zip(prev, new_clamped)):
            if new_val >= prev_val:
                alpha = min(1.0, dt / rise_tau)
            else:
                decay_tau = decay_taus[idx] if idx < len(decay_taus) else 0.65
                alpha = min(1.0, dt / decay_tau)
            filtered.append(prev_val + (new_val - prev_val) * alpha)
        return (filtered[0], filtered[1], filtered[2])

    def _compute_blob_smoothing_dt(self, dt_seconds: float) -> float:
        """Clamp Blob-local smoothing so frame hitches do not become visual punches."""
        if dt_seconds <= 0.0:
            return 0.0
        return min(dt_seconds, 1.0 / 20.0)

    def _filter_blob_live_bands(
        self,
        live_bands: tuple[float, float, float, float],
        dt: float,
    ) -> tuple[float, float, float, float]:
        """Smooth Blob's live deformation bands so the silhouette cannot snap back in one frame."""
        clamped = tuple(max(0.0, min(1.5, float(v))) for v in live_bands)
        if dt <= 0.0:
            return clamped

        prev = (
            float(getattr(self, '_blob_live_bass_energy', 0.0) or 0.0),
            float(getattr(self, '_blob_live_mid_energy', 0.0) or 0.0),
            float(getattr(self, '_blob_live_high_energy', 0.0) or 0.0),
            float(getattr(self, '_blob_live_overall_energy', 0.0) or 0.0),
        )
        if bool(getattr(self, '_blob_seed_pending', False)) or max(prev) <= 0.0001:
            return clamped
        taus = (
            (
                0.018,
                max(0.08, float(getattr(self, '_blob_pulse_release_ms', 220.0) or 220.0) / 1000.0 * 0.75),
            ),  # bass: fast rise, user-shaped release
            (
                0.028,
                max(0.10, float(getattr(self, '_blob_pulse_release_ms', 220.0) or 220.0) / 1000.0 * 1.00),
            ),  # mid: most visually obvious deformation path
            (
                0.025,
                max(0.08, float(getattr(self, '_blob_pulse_release_ms', 220.0) or 220.0) / 1000.0 * 0.85),
            ),  # high: sparkle without chatter
            (
                0.028,
                max(0.12, float(getattr(self, '_blob_pulse_release_ms', 220.0) or 220.0) / 1000.0 * 1.15),
            ),  # overall: stage/size support
        )
        filtered: List[float] = []
        for idx, (prev_val, cur_val, (rise_tau, decay_tau)) in enumerate(
            zip(prev, clamped, taus)
        ):
            if cur_val >= prev_val:
                # For bass(0) and overall(3): magnitude-scale the rise so
                # small wobbles get damped while kicks still snap fast.
                if idx == 0 or idx == 3:
                    _d = cur_val - prev_val
                    _m = min(1.0, _d / 0.10)
                    tau = rise_tau + (1.0 - _m) * rise_tau * 3.0
                else:
                    tau = rise_tau
            else:
                tau = decay_tau
            alpha = min(1.0, dt / max(tau, 0.01))
            filtered.append(prev_val + (cur_val - prev_val) * alpha)
        return (filtered[0], filtered[1], filtered[2], filtered[3])

    def _maybe_log_blob_diagnostics(
        self,
        *,
        dt_seconds: float,
        blob_dt: float,
        kick_raw: float,
        snare_raw: float,
        raw_live: tuple[float, float, float, float],
        filtered_live: tuple[float, float, float, float],
        prev_smoothed: float,
        raw_e: float,
        smoothed_e: float,
        stage_raw: tuple[float, float, float],
        stage_filtered: tuple[float, float, float],
        prev_stage_filtered: tuple[float, float, float],
    ) -> None:
        if not is_viz_diagnostics_enabled() or self._vis_mode != 'blob':
            return
        now_ts = time.time()
        hitch_clamped = dt_seconds > (blob_dt + 0.020)
        energy_jump = abs(raw_e - prev_smoothed) > 0.18 or abs(smoothed_e - prev_smoothed) > 0.14
        stage_jump = max(
            abs(cur - prev) for cur, prev in zip(stage_filtered, prev_stage_filtered)
        ) > 0.20
        hot_event = kick_raw > 0.55 or snare_raw > 0.55
        sig = (
            round(raw_e, 2),
            round(smoothed_e, 2),
            round(self._blob_kick_event_strength, 2),
            round(self._blob_snare_event_strength, 2),
            tuple(round(v, 2) for v in stage_filtered),
        )
        should_log = hitch_clamped or energy_jump or stage_jump or hot_event
        if not should_log and (now_ts - self._blob_diag_last_ts) < 0.75:
            return
        if not should_log and sig == self._blob_diag_last_sig:
            return
        logger.debug(
            (
                "[SPOTIFY_VIS][BLOB] dt=%.3f blob_dt=%.3f kick=%.2f/%.2f "
                "snare=%.2f/%.2f base=(%.3f,%.3f,%.3f,%.3f) "
                "trans=(%.3f,%.3f,%.3f) raw_live=(%.3f,%.3f,%.3f,%.3f) "
                "live=(%.3f,%.3f,%.3f,%.3f) smooth=%.3f->%.3f "
                "stage_raw=(%.2f,%.2f,%.2f) stage_filt=(%.2f,%.2f,%.2f) "
                "stage_prev=(%.2f,%.2f,%.2f) flags[hitch=%s energy=%s stage=%s hot=%s]"
            ),
            dt_seconds,
            blob_dt,
            kick_raw,
            self._blob_kick_event_strength,
            snare_raw,
            self._blob_snare_event_strength,
            float(getattr(self, '_blob_diag_base_bass', 0.0) or 0.0),
            float(getattr(self, '_blob_diag_base_mid', 0.0) or 0.0),
            float(getattr(self, '_blob_diag_base_high', 0.0) or 0.0),
            float(getattr(self, '_blob_diag_base_overall', 0.0) or 0.0),
            float(getattr(self, '_blob_diag_transient_bass', 0.0) or 0.0),
            float(getattr(self, '_blob_diag_transient_mid', 0.0) or 0.0),
            float(getattr(self, '_blob_diag_transient_high', 0.0) or 0.0),
            raw_live[0],
            raw_live[1],
            raw_live[2],
            raw_live[3],
            filtered_live[0],
            filtered_live[1],
            filtered_live[2],
            filtered_live[3],
            prev_smoothed,
            smoothed_e,
            stage_raw[0],
            stage_raw[1],
            stage_raw[2],
            stage_filtered[0],
            stage_filtered[1],
            stage_filtered[2],
            prev_stage_filtered[0],
            prev_stage_filtered[1],
            prev_stage_filtered[2],
            hitch_clamped,
            energy_jump,
            stage_jump,
            hot_event,
        )
        self._blob_diag_last_ts = now_ts
        self._blob_diag_last_sig = sig

    def _compute_blob_live_bands(self, energy_bands) -> tuple[float, float, float, float]:
        """Return Blob's live deformation bands after transient and scheduler help."""
        base_bass = float(getattr(energy_bands, 'bass', 0.0) or 0.0)
        base_mid = float(getattr(energy_bands, 'mid', 0.0) or 0.0)
        base_high = float(getattr(energy_bands, 'high', 0.0) or 0.0)
        base_overall = float(getattr(energy_bands, 'overall', 0.0) or 0.0)

        def _clamp01(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        clamp_raw = getattr(self, '_transient_clamp', 1.5)
        clamp_max = float(1.5 if clamp_raw is None else clamp_raw)
        transient_bass = 0.0
        transient_mid = 0.0
        transient_high = 0.0
        transient = getattr(self, '_transient_energy', None)
        if transient is not None:
            bass_mix_raw = getattr(self, '_blob_transient_mix_bass', 0.5)
            vocal_mix_raw = getattr(self, '_blob_transient_mix_vocal', 0.35)
            bass_mix = float(0.5 if bass_mix_raw is None else bass_mix_raw)
            vocal_mix = float(0.35 if vocal_mix_raw is None else vocal_mix_raw)
            bass_transient_raw = getattr(transient, 'bass_transient', 0.0)
            mid_transient_raw = getattr(transient, 'mid_transient', 0.0)
            high_transient_raw = getattr(transient, 'high_transient', 0.0)
            transient_bass = float(0.0 if bass_transient_raw is None else bass_transient_raw) * bass_mix
            transient_mid = float(0.0 if mid_transient_raw is None else mid_transient_raw) * vocal_mix
            transient_high = float(0.0 if high_transient_raw is None else high_transient_raw) * max(0.10, vocal_mix * 0.30)

        kick_gain_raw = getattr(self, '_kick_lane_gain', 1.0)
        kick_gain = max(0.0, min(2.0, float(1.0 if kick_gain_raw is None else kick_gain_raw)))
        kick_evt_raw = getattr(self, '_blob_kick_event_strength', 0.0)
        snare_evt_raw = getattr(self, '_blob_snare_event_strength', 0.0)
        kick_evt = max(0.0, float(0.0 if kick_evt_raw is None else kick_evt_raw)) * kick_gain
        snare_evt = max(0.0, float(0.0 if snare_evt_raw is None else snare_evt_raw))
        kick_drive = 0.0
        snare_drive = 0.0
        if kick_evt > 0.0 or snare_evt > 0.0:
            # Event assist should be earned by the underlying music, not by the
            # already-boosted live bands re-justifying themselves.
            kick_support_cont = _clamp01(
                base_bass * 1.35
                + base_overall * 0.45
                - base_mid * 0.45
                - base_high * 0.20
            )
            kick_support_trans = _clamp01(
                transient_bass * 1.15
                - transient_mid * 0.35
            )
            kick_support = max(kick_support_cont, kick_support_trans)
            kick_guard = _clamp01((kick_support - 0.08) / 0.42)

            snare_support_cont = _clamp01(
                base_mid * 0.95
                + base_high * 0.55
                + base_overall * 0.20
                - base_bass * 0.15
            )
            snare_support_trans = _clamp01(
                transient_mid * 1.00
                + transient_high * 0.55
                - transient_bass * 0.20
            )
            snare_support = max(snare_support_cont, snare_support_trans)
            snare_guard = _clamp01((snare_support - 0.06) / 0.40)

            kick_drive = kick_evt * kick_guard * (0.06 + kick_support * 0.28)
            snare_drive = snare_evt * snare_guard * (0.04 + snare_support * 0.18)
        else:
            kick_support = 0.0
            kick_guard = 0.0

        # Blob's main scalar size should stay rooted in continuous support.
        # Discrete events should primarily steer stretch/wobble/stage rather than
        # exploding the same bass/overall channels that the shader uses for core radius.
        self._blob_diag_base_bass = base_bass
        self._blob_diag_base_mid = base_mid
        self._blob_diag_base_high = base_high
        self._blob_diag_base_overall = base_overall
        self._blob_diag_transient_bass = transient_bass
        self._blob_diag_transient_mid = transient_mid
        self._blob_diag_transient_high = transient_high
        pulse_cap_raw = getattr(self, '_blob_pulse_cap', 1.0)
        pulse_cap_scale = max(0.0, min(2.0, float(1.0 if pulse_cap_raw is None else pulse_cap_raw)))
        support_bass = min(clamp_max, base_bass + transient_bass * 0.65)
        support_mid = min(clamp_max, base_mid + transient_mid * 0.55)
        support_high = min(clamp_max, base_high + transient_high * 0.45)
        support_overall = min(
            clamp_max,
            max(base_overall, support_bass * 0.55 + base_overall * 0.45),
        )
        cap_unit = (
            0.035
            + base_overall * 0.10
            + transient_bass * 0.12
            + transient_mid * 0.08
            + transient_high * 0.05
        ) * pulse_cap_scale

        # Live silhouette: keep bass/overall on the continuous path so whole-blob
        # pulse remains calm, while events mostly show up in the stretch/wobble bands.
        bass = support_bass
        mid = min(
            clamp_max,
            support_mid
            + snare_drive * 0.90
            + kick_drive * 0.16,
        )
        high = min(
            clamp_max,
            support_high
            + snare_drive * 0.58
            + kick_drive * 0.08,
        )
        overall = min(
            clamp_max,
            support_overall
            + kick_drive * 0.04
            + snare_drive * 0.02,
        )

        bass = min(bass, support_bass + cap_unit * 0.40)
        mid = min(mid, support_mid + cap_unit * 1.10)
        high = min(high, support_high + cap_unit * 0.85)
        overall = min(overall, support_overall + cap_unit * 0.35)

        stage_bass_support = min(clamp_max, base_bass + transient_bass * 0.35)
        stage_kick_boost = kick_evt * kick_guard * (0.05 + kick_support * 0.20)
        stage_overall = max(
            base_overall,
            support_overall,
            stage_bass_support * 0.82 + base_overall * 0.18 + stage_kick_boost,
        )
        stage_overall = min(
            clamp_max,
            max(base_overall, min(stage_overall, support_overall + cap_unit * 1.05)),
        )
        stage_bass = min(clamp_max, stage_bass_support + stage_kick_boost * 0.95)
        stage_bass = min(stage_bass, support_bass + cap_unit * 1.20)
        stage_mid = min(
            stage_overall,
            base_mid * 0.18 + transient_mid * 0.08 + snare_drive * 0.16 + kick_drive * 0.06,
        )
        stage_high = min(
            stage_overall * 0.70,
            base_high * 0.14 + transient_high * 0.05 + snare_drive * 0.12 + kick_drive * 0.04,
        )
        self._blob_stage_input_bass = stage_bass
        self._blob_stage_input_mid = stage_mid
        self._blob_stage_input_high = stage_high
        self._blob_stage_input_overall = stage_overall
        return bass, mid, high, overall

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

        # Compile each mode's fragment shader into its own program
        for mode, fs_source in frag_sources.items():
            try:
                fs = _gl.glCreateShader(_gl.GL_FRAGMENT_SHADER)
                _gl.glShaderSource(fs, fs_source)
                _gl.glCompileShader(fs)
                if not _gl.glGetShaderiv(fs, _gl.GL_COMPILE_STATUS):
                    info = _gl.glGetShaderInfoLog(fs)
                    logger.warning("[SPOTIFY_VIS] %s frag shader compile failed: %s", mode, info)
                    _gl.glDeleteShader(fs)
                    continue

                prog = _gl.glCreateProgram()
                _gl.glAttachShader(prog, vs)
                _gl.glAttachShader(prog, fs)
                _gl.glLinkProgram(prog)
                _gl.glDeleteShader(fs)

                if not _gl.glGetProgramiv(prog, _gl.GL_LINK_STATUS):
                    info = _gl.glGetProgramInfoLog(prog)
                    logger.warning("[SPOTIFY_VIS] %s program link failed: %s", mode, info)
                    _gl.glDeleteProgram(prog)
                    continue

                # Query all uniform locations for this program.
                # glGetUniformLocation returns -1 for uniforms not in the shader,
                # which is harmless — the set call is simply a no-op.
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
                    "u_blob_color", "u_blob_glow_color", "u_blob_edge_color", "u_blob_outline_color",
                    "u_blob_pulse", "u_blob_width", "u_blob_size", "u_blob_glow_intensity", "u_blob_glow_reactivity", "u_blob_glow_max_size",
                    "u_blob_reactive_glow", "u_blob_smoothed_energy", "u_blob_peak_energy",
                    "u_blob_peak_bass", "u_blob_peak_mid", "u_blob_peak_high", "u_blob_peak_overall",
                    "u_blob_reactive_deformation", "u_blob_stage_gain", "u_blob_core_scale", "u_blob_core_floor_bias", "u_blob_stage_bias", "u_blob_constant_wobble", "u_blob_reactive_wobble",
                    "u_blob_stretch_tendency", "u_blob_stretch_inner", "u_blob_stretch_outer",
                    "u_blob_stage_progress_override",
                    "u_osc_speed", "u_osc_line_dim",
                    "u_osc_line_offset_bias",
                    "u_osc_vertical_shift",
                    "u_osc_sine_travel",
                    "u_sine_speed", "u_sine_line_dim",
                    "u_sine_line_offset_bias",
                    "u_sine_vertical_shift",
                    "u_sine_travel",
                    "u_card_adaptation",
                    "u_sine_travel_line2", "u_sine_travel_line3",
                    "u_wave_effect", "u_micro_wobble", "u_crawl_amount", "u_width_reaction",
                    "u_sine_density", "u_sine_displacement",
                    "u_line_color", "u_line_count",
                    "u_line2_color", "u_line2_glow_color",
                    "u_line3_color", "u_line3_glow_color",
                    "u_slanted", "u_border_radius",
                    "u_spectrum_glow_enabled", "u_spectrum_glow_intensity", "u_spectrum_glow_color",
                    "u_rainbow_hue_offset", "u_rainbow_per_bar",
                    "u_prev_waveform", "u_osc_ghost_alpha",
                    "u_ghost_line2_enabled", "u_ghost_line3_enabled",
                    "u_heartbeat", "u_heartbeat_intensity",
                    # Bubble mode uniforms
                    "u_bubble_count", "u_bubbles_pos", "u_bubbles_extra",
                    "u_bubbles_trail", "u_trail_strength", "u_tail_opacity",
                    "u_specular_dir", "u_gradient_dir", "u_outline_color", "u_specular_color",
                    "u_gradient_light", "u_gradient_dark", "u_pop_color",
                    "u_sine_line1_shift", "u_sine_line2_shift", "u_sine_line3_shift",
                    "u_ghost_bass", "u_ghost_mid", "u_ghost_high",
                ):
                    uniforms[uname] = _gl.glGetUniformLocation(prog, uname)

                self._gl_programs[mode] = prog
                self._gl_uniforms[mode] = uniforms
                logger.debug("[SPOTIFY_VIS] Compiled shader program: %s", mode)

            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to compile %s shader", mode, exc_info=True)

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

        # Register GL handles with ResourceManager for VRAM leak prevention
        try:
            from core.resources.manager import ResourceManager
            from OpenGL import GL as _gl_mod
            rm = ResourceManager()
            for mode, prog in self._gl_programs.items():
                rid = rm.register_gl_handle(
                    prog, "program",
                    lambda h, _g=_gl_mod: _g.glDeleteProgram(h),
                    description=f"SpotifyBarsGLOverlay {mode} shader",
                    group="spotify_vis_gl",
                )
                self._gl_program_rids[mode] = rid
            self._gl_vao_rid = rm.register_gl_handle(
                vao, "vao",
                lambda h, _g=_gl_mod: _g.glDeleteVertexArrays(1, [h]),
                description="SpotifyBarsGLOverlay VAO",
                group="spotify_vis_gl",
            )
            self._gl_vbo_rid = rm.register_gl_handle(
                vbo, "vbo",
                lambda h, _g=_gl_mod: _g.glDeleteBuffers(1, [h]),
                description="SpotifyBarsGLOverlay VBO",
                group="spotify_vis_gl",
            )
            logger.debug("[SPOTIFY_VIS] GL handles registered with ResourceManager")
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to register GL handles: %s", e)
            self._gl_vao_rid = None
            self._gl_vbo_rid = None

        logger.info(
            "[SPOTIFY_VIS] Multi-shader pipeline ready: %s",
            ", ".join(sorted(self._gl_programs.keys())),
        )

    def cleanup_gl(self) -> None:
        """Delete all GL handles (programs, VAO, VBO) to prevent VRAM leaks."""

        try:
            from OpenGL import GL as _gl
        except ImportError:
            return

        ctx_acquired = False
        if self._gl_state.is_ready():
            try:
                self.makeCurrent()
                ctx_acquired = True
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Failed to make GL context current for cleanup: %s", e)

        try:
            for mode, prog in list(self._gl_programs.items()):
                try:
                    if ctx_acquired:
                        _gl.glDeleteProgram(prog)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Failed to delete %s program: %s", mode, e)
            self._gl_programs.clear()
            self._gl_uniforms.clear()
            self._gl_program = None

            if self._gl_vbo is not None:
                try:
                    if ctx_acquired:
                        _gl.glDeleteBuffers(1, [self._gl_vbo])
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Failed to delete VBO: %s", e)
                self._gl_vbo = None

            if self._gl_vao is not None:
                try:
                    if ctx_acquired:
                        _gl.glDeleteVertexArrays(1, [self._gl_vao])
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Failed to delete VAO: %s", e)
                self._gl_vao = None
        finally:
            if ctx_acquired:
                try:
                    self.doneCurrent()
                except Exception:
                    pass

        self._gl_program_rids.clear()
        self._gl_vao_rid = None
        self._gl_vbo_rid = None
        logger.debug("[SPOTIFY_VIS] GL handles cleaned up")

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
            logger.debug("[SPOTIFY_VIS] GL pipeline unavailable, falling back to QPainter", exc_info=True)
            return False

        if not self._gl_programs or self._gl_vao is None:
            return False

        mode = self._vis_mode
        prog = self._gl_programs.get(mode)
        if prog is None:
            # Fall back to spectrum if the requested mode wasn't compiled
            prog = self._gl_programs.get('spectrum')
            mode = 'spectrum'
        if prog is None:
            return False

        u = self._gl_uniforms.get(mode, {})

        width = rect.width()
        height = rect.height()
        if width <= 0 or height <= 0:
            return False

        # Store rect for renderer access (e.g. spectrum height scale)
        self._render_rect = rect

        try:
            from OpenGL import GL as _gl

            _gl.glUseProgram(prog)
            _gl.glBindVertexArray(self._gl_vao)

            # --- Common uniforms (all modes) ---
            loc = u.get("u_resolution", -1)
            if loc >= 0:
                _gl.glUniform2f(loc, float(width), float(height))

            loc = u.get("u_dpr", -1)
            if loc >= 0:
                _gl.glUniform1f(loc, self._get_dpr())

            loc = u.get("u_fade", -1)
            if loc >= 0:
                _gl.glUniform1f(loc, float(max(0.0, min(1.0, fade))))

            loc = u.get("u_time", -1)
            if loc >= 0:
                _gl.glUniform1f(loc, float(self._accumulated_time))

            loc = u.get("u_border_width", -1)
            if loc >= 0:
                _gl.glUniform1f(loc, float(max(0.0, self._border_width_px)))

            # --- Rainbow per-bar flag (spectrum only) ---
            loc_pb = u.get("u_rainbow_per_bar", -1)
            if loc_pb >= 0:
                _gl.glUniform1i(loc_pb, 1 if self._rainbow_per_bar else 0)

            # --- Rainbow hue offset (all modes) ---
            loc = u.get("u_rainbow_hue_offset", -1)
            # Log per-mode when rainbow is active so we can confirm loc is valid
            _rainbow_logged_mode = getattr(self, '_rainbow_logged_mode', None)
            if self._rainbow_enabled and _rainbow_logged_mode != mode:
                hue_val = (self._accumulated_time * self._rainbow_speed * 0.1) % 1.0
                logger.info(
                    "[SPOTIFY_VIS] Rainbow ACTIVE: enabled=%s per_bar=%s speed=%.2f loc=%d pb_loc=%d mode=%s "
                    "accum_time=%.2f hue=%.4f",
                    self._rainbow_enabled, self._rainbow_per_bar, self._rainbow_speed, loc, loc_pb, mode,
                    self._accumulated_time, hue_val,
                )
                self._rainbow_logged_mode = mode
            if not self._rainbow_enabled:
                self._rainbow_logged_mode = None
            if loc >= 0:
                if self._rainbow_enabled:
                    # Continuous hue rotation: fract() keeps it in 0..1.
                    # Remap 0..1 to 0.002..1.002 then fract() so hue_offset
                    # never hits the shader's <= 0.001 dead-zone guard, which
                    # would cause a single-frame white flash at the wrap point.
                    raw = (self._accumulated_time * self._rainbow_speed * 0.1) % 1.0
                    hue_offset = (raw + 0.002) % 1.0 if raw < 0.001 else raw
                    _gl.glUniform1f(loc, float(hue_offset))
                elif self._rainbow_per_bar and mode == 'spectrum':
                    # Per-bar unique colours: needs a non-zero hue offset to cycle
                    # even when global rainbow is off. Use a slow independent cycle.
                    raw = (self._accumulated_time * 0.05) % 1.0
                    hue_offset = (raw + 0.002) % 1.0 if raw < 0.001 else raw
                    _gl.glUniform1f(loc, float(hue_offset))
                else:
                    _gl.glUniform1f(loc, 0.0)
            elif self._rainbow_enabled:
                logger.warning(
                    "[SPOTIFY_VIS] Rainbow BROKEN: u_rainbow_hue_offset loc=-1 for mode=%s "
                    "(uniform missing or optimized out in shader)", mode,
                )

            # --- Per-mode uniforms (dispatched to renderer modules) ---
            from widgets.spotify_visualizer.renderers import upload_mode_uniforms
            if not upload_mode_uniforms(mode, _gl, u, self):
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

    def _render_with_qpainter(self, rect: QRect, fade: float) -> None:
        count = self._bar_count
        segments = self._segments
        if count <= 0 or segments <= 0:
            return

        margin_x = 8
        margin_y = 6
        inner = rect.adjusted(margin_x, margin_y, -margin_x, -margin_y)
        if inner.width() <= 0 or inner.height() <= 0:
            return

        gap = 2
        total_gap = gap * (count - 1) if count > 1 else 0
        bar_width = int((inner.width() - total_gap) / max(1, count))
        if bar_width <= 0:
            return

        x0 = inner.left() + 5
        bar_x = [x0 + i * (bar_width + gap) for i in range(count)]

        seg_gap = 1
        total_seg_gap = seg_gap * max(0, segments - 1)
        seg_height = int((inner.height() - total_seg_gap) / max(1, segments))
        if seg_height <= 0:
            return
        base_bottom = inner.bottom()
        seg_y = [base_bottom - s * (seg_height + seg_gap) - seg_height + 1 for s in range(segments)]

        fill = QColor(self._fill_color)
        border = QColor(self._border_color)

        try:
            fade_clamped = max(0.0, min(1.0, fade))
            fill.setAlpha(int(fill.alpha() * fade_clamped))
            border.setAlpha(int(border.alpha() * fade_clamped))
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        painter = QPainter(self)
        try:
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

            painter.setBrush(fill)
            painter.setPen(border)

            max_segments = min(segments, len(seg_y))
            draw_count = min(count, len(bar_x), len(self._bars))

            _BASE_H = 80.0
            h_scale = max(1.0, float(rect.height()) / _BASE_H)

            for i in range(draw_count):
                x = bar_x[i]
                try:
                    value = float(self._bars[i])
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    value = 0.0
                if value <= 0.0:
                    continue
                if value > 1.0:
                    value = 1.0
                # Height-aware visual boost (mirrors shader u_bar_height_scale)
                value = min(0.95, value * h_scale)

                if self._single_piece:
                    # Solid bar: one rectangle from bottom to active height
                    bar_h = max(1, int(round(value * inner.height())))
                    bar_y = base_bottom - bar_h + 1
                    painter.drawRect(QRect(x, bar_y, bar_width, bar_h))
                else:
                    active = int(round(value * segments))
                    if active <= 0:
                        if self._playing and value > 0.0:
                            active = 1
                        else:
                            continue
                    if active > max_segments:
                        active = max_segments
                    for s in range(active):
                        y = seg_y[s]
                        painter.drawRect(QRect(x, y, bar_width, seg_height))
        finally:
            painter.end()
