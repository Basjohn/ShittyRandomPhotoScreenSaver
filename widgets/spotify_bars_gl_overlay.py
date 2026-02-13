from __future__ import annotations

from typing import List, Sequence

import numpy as np
import time
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger, get_throttled_logger, is_perf_metrics_enabled
from rendering.gl_format import apply_widget_surface_format
from rendering.gl_state_manager import GLStateManager, GLContextState
from OpenGL import GL as gl
from widgets.spotify_visualizer.energy_bands import EnergyBands


logger = get_logger(__name__)
# Throttled logger for high-frequency debug messages (max 1/second)
_throttled_logger = get_throttled_logger(__name__, max_per_second=1.0)


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

        # Waveform data for oscilloscope (256 samples, -1..1)
        self._waveform: List[float] = []
        self._waveform_count: int = 0

        # Energy bands for starfield / blob / helix
        self._energy_bands: EnergyBands = EnergyBands()

        # Oscilloscope glow settings
        self._glow_enabled: bool = True
        self._glow_intensity: float = 0.5
        self._glow_color: QColor = QColor(0, 200, 255, 230)
        self._line_color: QColor = QColor(255, 255, 255, 255)
        self._reactive_glow: bool = True
        self._osc_sensitivity: float = 3.0
        self._osc_smoothing: float = 0.7

        # Oscilloscope multi-line
        self._osc_line_count: int = 1
        self._osc_line2_color: QColor = QColor(255, 120, 50, 230)
        self._osc_line2_glow_color: QColor = QColor(255, 120, 50, 180)
        self._osc_line3_color: QColor = QColor(50, 255, 120, 230)
        self._osc_line3_glow_color: QColor = QColor(50, 255, 120, 180)

        # Starfield settings
        self._star_density: float = 1.0
        self._travel_speed: float = 0.5
        self._star_reactivity: float = 1.0
        self._starfield_travel_time: float = 0.0  # CPU-accumulated travel (monotonic, never reverses)
        self._nebula_tint1: QColor = QColor(20, 40, 120)   # first nebula colour
        self._nebula_tint2: QColor = QColor(80, 20, 100)    # second nebula colour
        self._nebula_cycle_speed: float = 0.3               # colour cycle speed (0..1)

        # Blob settings
        self._blob_color: QColor = QColor(0, 180, 255, 230)
        self._blob_glow_color: QColor = QColor(0, 140, 255, 180)
        self._blob_edge_color: QColor = QColor(100, 220, 255, 230)
        self._blob_outline_color: QColor = QColor(0, 0, 0, 0)  # dark band between fill and glow
        self._blob_pulse: float = 1.0
        self._blob_width: float = 1.0
        self._blob_size: float = 1.0
        self._blob_glow_intensity: float = 0.5
        self._blob_reactive_glow: bool = True
        self._blob_smoothed_energy: float = 0.0  # CPU-side smoothed energy for glow decay
        self._blob_reactive_deformation: float = 1.0
        self._blob_constant_wobble: float = 1.0
        self._blob_reactive_wobble: float = 1.0
        self._blob_stretch_tendency: float = 0.0
        self._osc_speed: float = 1.0
        self._osc_line_dim: bool = False  # optional half-strength dimming on lines 2/3
        self._osc_line_offset_bias: float = 0.0
        self._osc_vertical_shift: int = 0
        self._osc_sine_travel: int = 0  # 0=none, 1=left, 2=right (used by sine_wave mode)
        self._sine_card_adaptation: float = 0.3  # 0.0-1.0, how much of card height wave uses
        self._sine_travel_line2: int = 0  # per-line travel: 0=none, 1=left, 2=right
        self._sine_travel_line3: int = 0
        self._sine_wave_effect: float = 0.0  # 0.0-1.0, wave-like positional effect
        self._sine_micro_wobble: float = 0.0  # 0.0-1.0, energy-reactive micro distortions
        self._sine_vertical_shift: int = 0  # -50 to 200, line spread amount
        self._osc_smoothed_bass: float = 0.0  # CPU-side smoothed energy for osc glow
        self._osc_smoothed_mid: float = 0.0
        self._osc_smoothed_high: float = 0.0

        # Helix settings
        self._helix_turns: int = 4
        self._helix_double: bool = True
        self._helix_speed: float = 1.0
        self._helix_glow_enabled: bool = True
        self._helix_glow_intensity: float = 0.5
        self._helix_glow_color: QColor = QColor(0, 200, 255, 180)
        self._helix_reactive_glow: bool = True

        # Spectrum: single piece mode (solid bars, no segment gaps)
        self._single_piece: bool = False

        # Ghosting configuration – whether trailing segments are drawn and
        # how strong they appear relative to the main bar border colour. The
        # decay rate is controlled separately via _peak_decay_per_sec.
        self._ghosting_enabled: bool = True
        self._ghost_alpha: float = 0.4

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
        self._gl_vbo_rid = None
        # Legacy single-program aliases for backward compat with ResourceManager
        self._gl_program = None
        self._gl_program_rid = None
        self._gl_disabled: bool = False
        self._debug_bars_logged: bool = False
        self._debug_paint_logged: bool = False
        
        # Pre-allocated uniform buffers to reduce GC pressure (avoid per-frame allocation)
        self._bars_buffer: np.ndarray = np.zeros(64, dtype="float32")
        self._peaks_buffer: np.ndarray = np.zeros(64, dtype="float32")
        
        # Centralized GL state manager for robust state tracking
        self._gl_state = GLStateManager(f"spotify_bars_{id(self)}")

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
        energy_bands: EnergyBands | None = None,
        glow_enabled: bool = True,
        glow_intensity: float = 0.5,
        glow_color: QColor | None = None,
        reactive_glow: bool = True,
        osc_sensitivity: float = 3.0,
        osc_smoothing: float = 0.7,
        star_density: float = 1.0,
        travel_speed: float = 0.5,
        star_reactivity: float = 1.0,
        nebula_tint1: QColor | None = None,
        nebula_tint2: QColor | None = None,
        nebula_cycle_speed: float = 0.3,
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
        blob_constant_wobble: float = 1.0,
        blob_reactive_wobble: float = 1.0,
        blob_stretch_tendency: float = 0.0,
        osc_speed: float = 1.0,
        osc_line_dim: bool = False,
        osc_line_offset_bias: float = 0.0,
        osc_vertical_shift: int = 0,
        osc_sine_travel: int = 0,
        sine_card_adaptation: float = 0.3,
        sine_travel_line2: int = 0,
        sine_travel_line3: int = 0,
        sine_wave_effect: float = 0.0,
        sine_micro_wobble: float = 0.0,
        sine_vertical_shift: int = 0,
        helix_turns: int = 4,
        helix_double: bool = True,
        helix_speed: float = 1.0,
        helix_glow_enabled: bool = True,
        helix_glow_intensity: float = 0.5,
        helix_glow_color: QColor | None = None,
        helix_reactive_glow: bool = True,
        line_color: QColor | None = None,
        osc_line_count: int = 1,
        osc_line2_color: QColor | None = None,
        osc_line2_glow_color: QColor | None = None,
        osc_line3_color: QColor | None = None,
        osc_line3_glow_color: QColor | None = None,
        single_piece: bool = False,
        slanted: bool = False,
        border_radius: float = 0.0,
    ) -> None:
        """Update overlay bar state and geometry.

        ``rect`` is specified in the parent ``DisplayWidget`` coordinate space
        and should usually be the geometry of the associated
        ``SpotifyVisualizerWidget``.
        """

        if not visible:
            self._enabled = False
            # PERF: Don't call hide() - it's expensive (25ms+) and causes show() to be
            # called again on next visible frame. Instead, paintGL checks _enabled flag
            # and skips rendering when disabled. The overlay stays "visible" to Qt but
            # renders nothing.
            self.update()  # Trigger repaint to clear the bars
            return

        # Set active visualizer mode
        self._vis_mode = vis_mode if vis_mode in (
            'spectrum', 'oscilloscope', 'starfield', 'blob', 'helix', 'sine_wave'
        ) else 'spectrum'

        # Update accumulated time for animated modes
        now_ts = time.time()
        if self._last_time_ts > 0.0:
            dt = now_ts - self._last_time_ts
            if 0.0 < dt < 1.0:  # sanity clamp
                self._accumulated_time += dt
                # Starfield: integrate speed*dt so travel is monotonic (never reverses)
                # Gate on overall energy so travel stops when music is paused
                if self._vis_mode == 'starfield' and energy_bands is not None:
                    overall = getattr(energy_bands, 'overall', 0.0)
                    bass = getattr(energy_bands, 'bass', 0.0)
                    # Fade base speed to 0 when silent (overall < 0.02)
                    activity = min(1.0, overall * 10.0)  # 0→1 over energy 0→0.1
                    base_spd = self._travel_speed * activity
                    spd = base_spd + bass * self._star_reactivity * 0.4
                    self._starfield_travel_time += dt * spd
                # Blob: smooth overall energy to reduce glow flickering
                if self._vis_mode == 'blob' and energy_bands is not None:
                    raw_e = getattr(energy_bands, 'overall', 0.0)
                    prev = self._blob_smoothed_energy
                    # Fast rise (~50ms tau), slow decay (~300ms tau)
                    alpha = min(1.0, dt / 0.05) if raw_e > prev else min(1.0, dt / 0.30)
                    self._blob_smoothed_energy = prev + (raw_e - prev) * alpha
                # Oscilloscope / Sine Wave: smooth per-band energy for glow anti-flicker
                if self._vis_mode in ('oscilloscope', 'sine_wave') and energy_bands is not None:
                    for attr, band in (
                        ('_osc_smoothed_bass', 'bass'),
                        ('_osc_smoothed_mid', 'mid'),
                        ('_osc_smoothed_high', 'high'),
                    ):
                        raw_e = getattr(energy_bands, band, 0.0)
                        prev = getattr(self, attr)
                        a = min(1.0, dt / 0.06) if raw_e > prev else min(1.0, dt / 0.25)
                        setattr(self, attr, prev + (raw_e - prev) * a)
        self._last_time_ts = now_ts

        # Store waveform data (oscilloscope) with temporal smoothing via osc_speed
        if waveform is not None:
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
            self._waveform_count = len(self._waveform)

        # Store energy bands (starfield / blob / helix)
        if energy_bands is not None:
            self._energy_bands = energy_bands

        # Oscilloscope glow settings
        self._glow_enabled = bool(glow_enabled)
        self._glow_intensity = max(0.0, float(glow_intensity))
        if glow_color is not None:
            self._glow_color = QColor(glow_color)
        if line_color is not None:
            self._line_color = QColor(line_color)
        self._reactive_glow = bool(reactive_glow)
        self._osc_sensitivity = max(0.5, min(10.0, float(osc_sensitivity)))
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

        # Starfield settings
        self._star_density = max(0.1, float(star_density))
        self._travel_speed = max(0.0, float(travel_speed))
        self._star_reactivity = max(0.0, float(star_reactivity))
        if nebula_tint1 is not None:
            self._nebula_tint1 = QColor(nebula_tint1) if not isinstance(nebula_tint1, QColor) else nebula_tint1
        if nebula_tint2 is not None:
            self._nebula_tint2 = QColor(nebula_tint2) if not isinstance(nebula_tint2, QColor) else nebula_tint2
        self._nebula_cycle_speed = max(0.0, min(1.0, float(nebula_cycle_speed)))

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
        self._blob_reactive_glow = bool(blob_reactive_glow)
        self._blob_reactive_deformation = max(0.0, min(2.0, float(blob_reactive_deformation)))
        self._blob_constant_wobble = max(0.0, min(2.0, float(blob_constant_wobble)))
        self._blob_reactive_wobble = max(0.0, min(2.0, float(blob_reactive_wobble)))
        self._blob_stretch_tendency = max(0.0, min(1.0, float(blob_stretch_tendency)))
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
        self._sine_vertical_shift = max(-50, min(200, int(sine_vertical_shift)))

        # Helix settings
        self._helix_turns = max(2, int(helix_turns))
        self._helix_double = bool(helix_double)
        self._helix_speed = max(0.0, float(helix_speed))
        self._helix_glow_enabled = bool(helix_glow_enabled)
        self._helix_glow_intensity = max(0.0, float(helix_glow_intensity))
        if helix_glow_color is not None:
            self._helix_glow_color = QColor(helix_glow_color)
        self._helix_reactive_glow = bool(helix_reactive_glow)

        # Spectrum: single piece (solid bars, no segments)
        self._single_piece = bool(single_piece)
        # Spectrum: slanted bar edges and border radius
        self._slanted = bool(slanted)
        self._border_radius = max(0.0, float(border_radius))

        # Apply ghost configuration up-front so it is visible to both the
        # peak-envelope update and the shader path. When ghosting is
        # disabled, we keep bar rendering active but collapse ghost alpha to
        # zero so only the solid bars remain.
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
            self._enabled = False
            try:
                self.hide()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return

        try:
            bars_seq = list(bars)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._enabled = False
            try:
                self.hide()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return

        if not bars_seq:
            self._enabled = False
            try:
                self.hide()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
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
            self._enabled = False
            try:
                self.hide()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
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
        
        if not self._enabled:
            return

        try:
            fade = float(self._fade)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            fade = 0.0
        if fade <= 0.0:
            return

        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Start from a clean transparent buffer each frame so that decaying
        # bars do not leave ghost outlines or coloured speckles behind.
        try:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        # Prefer the shader path when available; fall back to QPainter when
        # the GL program or buffers are not ready or fail at runtime.
        used_shader = self._render_with_shader(rect, fade)
        if not used_shader:
            self._render_with_qpainter(rect, fade)

        if not getattr(self, "_debug_paint_logged", False):
            try:
                logger.debug(
                    "[SPOTIFY_VIS] paintGL path: %s",
                    "shader" if used_shader else "qpainter",
                )
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            try:
                self._debug_paint_logged = True
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

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
                    "u_bar_count", "u_segments", "u_bar_height_scale", "u_single_piece",
                    "u_bars", "u_peaks",
                    "u_fill_color", "u_border_color", "u_playing", "u_ghost_alpha",
                    "u_waveform", "u_waveform_count",
                    "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
                    "u_glow_enabled", "u_glow_intensity", "u_glow_color", "u_reactive_glow",
                    "u_sensitivity", "u_smoothing",
                    "u_star_density", "u_travel_speed", "u_star_reactivity",
                    "u_travel_time", "u_nebula_tint1", "u_nebula_tint2", "u_nebula_cycle_speed",
                    "u_blob_color", "u_blob_glow_color", "u_blob_edge_color", "u_blob_outline_color",
                    "u_blob_pulse", "u_blob_width", "u_blob_size", "u_blob_glow_intensity",
                    "u_blob_reactive_glow", "u_blob_smoothed_energy",
                    "u_blob_reactive_deformation", "u_blob_constant_wobble", "u_blob_reactive_wobble",
                    "u_blob_stretch_tendency",
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
                    "u_wave_effect", "u_micro_wobble",
                    "u_helix_turns", "u_helix_double", "u_helix_speed",
                    "u_helix_glow_enabled", "u_helix_glow_intensity",
                    "u_helix_glow_color", "u_helix_reactive_glow",
                    "u_line_color", "u_line_count",
                    "u_line2_color", "u_line2_glow_color",
                    "u_line3_color", "u_line3_glow_color",
                    "u_slanted", "u_border_radius",
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
        """Delete all GL handles (programs, VAO, VBO) to prevent VRAM leaks.

        Must be called with a valid GL context (e.g. from the widget's
        destroy path while the context is still current).
        """
        try:
            from OpenGL import GL as _gl
        except ImportError:
            return

        for mode, prog in list(self._gl_programs.items()):
            try:
                _gl.glDeleteProgram(prog)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Failed to delete %s program: %s", mode, e)
        self._gl_programs.clear()
        self._gl_uniforms.clear()
        self._gl_program = None

        if self._gl_vbo is not None:
            try:
                _gl.glDeleteBuffers(1, [self._gl_vbo])
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Failed to delete VBO: %s", e)
            self._gl_vbo = None

        if self._gl_vao is not None:
            try:
                _gl.glDeleteVertexArrays(1, [self._gl_vao])
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Failed to delete VAO: %s", e)
            self._gl_vao = None

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

        # For spectrum mode, bar data is required
        if mode == 'spectrum':
            try:
                count = int(self._bar_count)
                segments = int(self._segments)
            except Exception:
                return False
            if count <= 0 or segments <= 0:
                return False

        width = rect.width()
        height = rect.height()
        if width <= 0 or height <= 0:
            return False

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

            # --- Spectrum-specific uniforms ---
            if mode == 'spectrum':
                count = int(self._bar_count)
                segments = int(self._segments)

                loc = u.get("u_bar_count", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, min(count, 64))
                loc = u.get("u_segments", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, segments)

                # Visual height boost: when the card is taller than the default
                # 80px spectrum height, scale bar values so they fill more of
                # the card.  The 0.55 audio scaling is preserved on the CPU
                # side; this only affects the shader's visual mapping.
                loc = u.get("u_bar_height_scale", -1)
                if loc >= 0:
                    _SPECTRUM_BASE_HEIGHT = 80.0
                    cur_h = max(1.0, float(rect.height()))
                    height_scale = max(1.0, cur_h / _SPECTRUM_BASE_HEIGHT)
                    _gl.glUniform1f(loc, float(height_scale))

                loc = u.get("u_single_piece", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._single_piece else 0)

                loc = u.get("u_slanted", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if getattr(self, '_slanted', False) else 0)

                loc = u.get("u_border_radius", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(getattr(self, '_border_radius', 0.0)))

                bars = list(self._bars)
                if not bars:
                    _gl.glBindVertexArray(0)
                    _gl.glUseProgram(0)
                    return False
                if len(bars) < 64:
                    bars = bars + [0.0] * (64 - len(bars))
                else:
                    bars = bars[:64]

                if not self._debug_bars_logged:
                    try:
                        sample = bars[:count] if count > 0 else [0.0]
                        logger.debug(
                            "[SPOTIFY_VIS] Shader bars snapshot: count=%d, min=%.4f, max=%.4f",
                            count, min(sample), max(sample),
                        )
                    except Exception:
                        pass
                    self._debug_bars_logged = True

                loc = u.get("u_bars", -1)
                if loc >= 0:
                    buf = self._bars_buffer
                    buf.fill(0.0)
                    # Scale bars ~55% so vocals/drums (bars 1/2) don't pin at top
                    # at normal volume. Calibrated to match ideal state at ~55% mixer.
                    for i in range(min(len(bars), 64)):
                        buf[i] = float(bars[i]) * 0.55
                    _gl.glUniform1fv(loc, 64, buf)

                loc = u.get("u_peaks", -1)
                if loc >= 0:
                    buf_peaks = self._peaks_buffer
                    buf_peaks.fill(0.0)
                    peaks = self._peaks
                    for i in range(min(len(peaks), 64)):
                        buf_peaks[i] = float(peaks[i]) * 0.55
                    _gl.glUniform1fv(loc, 64, buf_peaks)

                loc = u.get("u_playing", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._playing else 0)

                loc = u.get("u_ghost_alpha", -1)
                if loc >= 0:
                    try:
                        ga = float(self._ghost_alpha if self._ghosting_enabled else 0.0)
                    except Exception:
                        ga = 0.0
                    _gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

            # --- Fill / border colours (spectrum + helix) ---
            if mode in ('spectrum', 'helix'):
                fill = QColor(self._fill_color)
                loc = u.get("u_fill_color", -1)
                if loc >= 0:
                    _gl.glUniform4f(loc, float(fill.redF()), float(fill.greenF()),
                                    float(fill.blueF()), float(fill.alphaF()))
                border = QColor(self._border_color)
                loc = u.get("u_border_color", -1)
                if loc >= 0:
                    _gl.glUniform4f(loc, float(border.redF()), float(border.greenF()),
                                    float(border.blueF()), float(border.alphaF()))

            # --- Oscilloscope uniforms (waveform data only) ---
            if mode == 'oscilloscope':
                wf = self._waveform
                wf_count = min(len(wf), 256) if wf else 0
                loc = u.get("u_waveform_count", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, max(wf_count, 2))
                loc = u.get("u_waveform", -1)
                if loc >= 0 and wf_count > 0:
                    wf_buf = np.zeros(256, dtype="float32")
                    for i in range(wf_count):
                        wf_buf[i] = float(wf[i])
                    _gl.glUniform1fv(loc, 256, wf_buf)

            # --- Shared line/glow uniforms (oscilloscope + sine_wave) ---
            if mode in ('oscilloscope', 'sine_wave'):
                loc = u.get("u_glow_enabled", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._glow_enabled else 0)
                loc = u.get("u_glow_intensity", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._glow_intensity))
                loc = u.get("u_glow_color", -1)
                if loc >= 0:
                    gc = self._glow_color
                    _gl.glUniform4f(loc, float(gc.redF()), float(gc.greenF()),
                                    float(gc.blueF()), float(gc.alphaF()))
                loc = u.get("u_reactive_glow", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._reactive_glow else 0)
                loc = u.get("u_sensitivity", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._osc_sensitivity))
                loc = u.get("u_smoothing", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._osc_smoothing))

                # Line colour (separate from glow)
                loc = u.get("u_line_color", -1)
                if loc >= 0:
                    lc = self._line_color
                    _gl.glUniform4f(loc, float(lc.redF()), float(lc.greenF()),
                                    float(lc.blueF()), float(lc.alphaF()))

                # Multi-line uniforms
                loc = u.get("u_line_count", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, self._osc_line_count)
                for uname, qc in (
                    ("u_line2_color", self._osc_line2_color),
                    ("u_line2_glow_color", self._osc_line2_glow_color),
                    ("u_line3_color", self._osc_line3_color),
                    ("u_line3_glow_color", self._osc_line3_glow_color),
                ):
                    loc = u.get(uname, -1)
                    if loc >= 0:
                        _gl.glUniform4f(loc, float(qc.redF()), float(qc.greenF()),
                                        float(qc.blueF()), float(qc.alphaF()))

            # --- Energy band uniforms (oscilloscope, sine_wave, starfield, blob, helix) ---
            if mode in ('oscilloscope', 'sine_wave', 'starfield', 'blob', 'helix'):
                eb = self._energy_bands
                loc = u.get("u_overall_energy", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(eb.overall))
                # Oscilloscope/sine_wave use CPU-smoothed bands for glow anti-flicker
                if mode in ('oscilloscope', 'sine_wave'):
                    bass_val = self._osc_smoothed_bass
                    mid_val = self._osc_smoothed_mid
                    high_val = self._osc_smoothed_high
                else:
                    bass_val = eb.bass
                    mid_val = eb.mid
                    high_val = eb.high
                loc = u.get("u_bass_energy", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(bass_val))
                loc = u.get("u_mid_energy", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(mid_val))
                loc = u.get("u_high_energy", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(high_val))

            # --- Starfield uniforms ---
            if mode == 'starfield':
                loc = u.get("u_star_density", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._star_density))
                loc = u.get("u_travel_speed", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._travel_speed))
                loc = u.get("u_star_reactivity", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._star_reactivity))
                loc = u.get("u_travel_time", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._starfield_travel_time))
                loc = u.get("u_nebula_tint1", -1)
                if loc >= 0:
                    nt1 = self._nebula_tint1
                    _gl.glUniform3f(loc, float(nt1.redF()), float(nt1.greenF()), float(nt1.blueF()))
                loc = u.get("u_nebula_tint2", -1)
                if loc >= 0:
                    nt2 = self._nebula_tint2
                    _gl.glUniform3f(loc, float(nt2.redF()), float(nt2.greenF()), float(nt2.blueF()))
                loc = u.get("u_nebula_cycle_speed", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._nebula_cycle_speed))

            # --- Blob uniforms ---
            if mode == 'blob':
                loc = u.get("u_blob_color", -1)
                if loc >= 0:
                    bc = self._blob_color
                    _gl.glUniform4f(loc, float(bc.redF()), float(bc.greenF()),
                                    float(bc.blueF()), float(bc.alphaF()))
                loc = u.get("u_blob_glow_color", -1)
                if loc >= 0:
                    bgc = self._blob_glow_color
                    _gl.glUniform4f(loc, float(bgc.redF()), float(bgc.greenF()),
                                    float(bgc.blueF()), float(bgc.alphaF()))
                loc = u.get("u_blob_edge_color", -1)
                if loc >= 0:
                    bec = self._blob_edge_color
                    _gl.glUniform4f(loc, float(bec.redF()), float(bec.greenF()),
                                    float(bec.blueF()), float(bec.alphaF()))
                loc = u.get("u_blob_pulse", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_pulse))
                loc = u.get("u_blob_width", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_width))
                loc = u.get("u_blob_size", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_size))
                loc = u.get("u_blob_glow_intensity", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_glow_intensity))
                loc = u.get("u_blob_reactive_glow", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._blob_reactive_glow else 0)
                loc = u.get("u_blob_outline_color", -1)
                if loc >= 0:
                    boc = self._blob_outline_color
                    _gl.glUniform4f(loc, float(boc.redF()), float(boc.greenF()),
                                    float(boc.blueF()), float(boc.alphaF()))
                loc = u.get("u_blob_smoothed_energy", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_smoothed_energy))
                loc = u.get("u_blob_reactive_deformation", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_reactive_deformation))
                loc = u.get("u_blob_constant_wobble", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_constant_wobble))
                loc = u.get("u_blob_reactive_wobble", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_reactive_wobble))
                loc = u.get("u_blob_stretch_tendency", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._blob_stretch_tendency))

            # --- Oscilloscope uniforms ---
            if mode == 'oscilloscope':
                loc = u.get("u_osc_speed", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._osc_speed))
                loc = u.get("u_osc_line_dim", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._osc_line_dim else 0)
                loc = u.get("u_osc_line_offset_bias", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._osc_line_offset_bias))
                loc = u.get("u_osc_vertical_shift", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, int(self._osc_vertical_shift))

            # --- Sine Wave uniforms (shares osc speed/dim/offset/travel) ---
            if mode == 'sine_wave':
                loc = u.get("u_playing", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._playing else 0)
                loc = u.get("u_sine_speed", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._osc_speed))
                loc = u.get("u_sine_line_dim", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._osc_line_dim else 0)
                loc = u.get("u_sine_line_offset_bias", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._osc_line_offset_bias))
                loc = u.get("u_sine_travel", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, int(self._osc_sine_travel))
                loc = u.get("u_card_adaptation", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._sine_card_adaptation))
                loc = u.get("u_sine_travel_line2", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, int(self._sine_travel_line2))
                loc = u.get("u_sine_travel_line3", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, int(self._sine_travel_line3))
                loc = u.get("u_wave_effect", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._sine_wave_effect))
                loc = u.get("u_micro_wobble", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._sine_micro_wobble))
                loc = u.get("u_sine_vertical_shift", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, int(self._sine_vertical_shift))

            # --- Helix uniforms ---
            if mode == 'helix':
                loc = u.get("u_helix_turns", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, int(self._helix_turns))
                loc = u.get("u_helix_double", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._helix_double else 0)
                loc = u.get("u_helix_speed", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._helix_speed))
                loc = u.get("u_helix_glow_enabled", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._helix_glow_enabled else 0)
                loc = u.get("u_helix_glow_intensity", -1)
                if loc >= 0:
                    _gl.glUniform1f(loc, float(self._helix_glow_intensity))
                loc = u.get("u_helix_glow_color", -1)
                if loc >= 0:
                    hgc = self._helix_glow_color
                    _gl.glUniform4f(loc, float(hgc.redF()), float(hgc.greenF()),
                                    float(hgc.blueF()), float(hgc.alphaF()))
                loc = u.get("u_helix_reactive_glow", -1)
                if loc >= 0:
                    _gl.glUniform1i(loc, 1 if self._helix_reactive_glow else 0)

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
