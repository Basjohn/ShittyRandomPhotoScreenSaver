from __future__ import annotations

from typing import List, Sequence

import numpy as np
import time
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger
from rendering.gl_format import apply_widget_surface_format
from OpenGL import GL as gl


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

        try:
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        except Exception:
            pass
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception:
            pass

        self._enabled: bool = False
        self._bars: List[float] = []
        self._bar_count: int = 0
        self._segments: int = 0
        self._fill_color: QColor = QColor(200, 200, 200, 230)
        self._border_color: QColor = QColor(255, 255, 255, 255)
        self._fade: float = 0.0
        self._playing: bool = False

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

        # Minimal GL state for a fullscreen quad shader. If initialisation
        # fails at any point we fall back to the legacy QPainter-on-GL path.
        self._gl_program = None
        self._gl_vao = None
        self._gl_vbo = None
        self._u_resolution = None
        self._u_bar_count = None
        self._u_segments = None
        self._u_bars = None
        self._u_peaks = None
        self._u_fill_color = None
        self._u_border_color = None
        self._u_fade = None
        self._u_playing = None
        self._u_ghost_alpha = None
        self._gl_disabled: bool = False
        self._debug_bars_logged: bool = False
        self._debug_paint_logged: bool = False

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
    ) -> None:
        """Update overlay bar state and geometry.

        ``rect`` is specified in the parent ``DisplayWidget`` coordinate space
        and should usually be the geometry of the associated
        ``SpotifyVisualizerWidget``.
        """

        if not visible:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        # Apply ghost configuration up-front so it is visible to both the
        # peak-envelope update and the shader path. When ghosting is
        # disabled, we keep bar rendering active but collapse ghost alpha to
        # zero so only the solid bars remain.
        try:
            self._ghosting_enabled = bool(ghosting_enabled)
        except Exception:
            self._ghosting_enabled = True

        try:
            ga = float(ghost_alpha)
        except Exception:
            ga = 0.4
        if ga < 0.0:
            ga = 0.0
        if ga > 1.0:
            ga = 1.0
        self._ghost_alpha = ga

        try:
            gd = float(ghost_decay)
        except Exception:
            gd = -1.0
        if gd >= 0.0:
            self._peak_decay_per_sec = max(0.0, gd)

        try:
            count = int(bar_count)
        except Exception:
            count = 0
        try:
            segs = int(segments)
        except Exception:
            segs = 0

        if count <= 0 or segs <= 0:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        try:
            bars_seq = list(bars)
        except Exception:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        if not bars_seq:
            self._enabled = False
            try:
                self.hide()
            except Exception:
                pass
            return

        if len(bars_seq) > count:
            bars_seq = bars_seq[:count]
        elif len(bars_seq) < count:
            bars_seq = bars_seq + [0.0] * (count - len(bars_seq))

        clamped: List[float] = []
        for v in bars_seq:
            try:
                f = float(v)
            except Exception:
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
            except Exception:
                pass
            return

        # Update per-bar peak state using the latest clamped values.
        try:
            now_ts = time.monotonic()
        except Exception:
            now_ts = 0.0
        dt = 0.0
        try:
            last_ts = self._last_peak_ts
        except Exception:
            last_ts = 0.0
        if last_ts > 0.0 and now_ts > last_ts:
            dt = now_ts - last_ts
        try:
            self._last_peak_ts = now_ts
        except Exception:
            pass

        try:
            peaks = list(self._peaks)
        except Exception:
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
                        except Exception:
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
        except Exception:
            self._fade = 1.0
        self._playing = bool(playing)

        try:
            cur_geom = None
            try:
                cur_geom = self.geometry()
            except Exception:
                cur_geom = None
            if cur_geom is None or cur_geom != rect:
                self.setGeometry(rect)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set overlay geometry", exc_info=True)

        try:
            if self._enabled:
                self.show()
                self.raise_()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to show/raise overlay", exc_info=True)

        self.update()

    # ------------------------------------------------------------------
    # QOpenGLWidget hooks
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:  # type: ignore[override]
        """Create the small shader pipeline used for bar rendering.

        Any failure here is treated as non-fatal – the widget will fall back
        to the QPainter implementation in paintGL.
        """

        try:
            self._init_gl_pipeline()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to initialise GL pipeline for SpotifyBarsGLOverlay", exc_info=True)

    def paintGL(self) -> None:  # type: ignore[override]
        if not self._enabled:
            return

        try:
            fade = float(self._fade)
        except Exception:
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
        except Exception:
            pass

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
            except Exception:
                pass
            try:
                self._debug_paint_logged = True
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal rendering helpers
    # ------------------------------------------------------------------

    def _init_gl_pipeline(self) -> None:
        if self._gl_disabled or self._gl_program is not None:
            return

        from OpenGL import GL as _gl  # local alias to avoid surprises during import

        vs_source = """#version 330 core
layout(location = 0) in vec2 a_pos;
out vec2 v_uv;
void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

        fs_source = """#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;   // logical size in QWidget coordinates
uniform float u_dpr;         // device pixel ratio of the backing FBO
uniform int u_bar_count;
uniform int u_segments;
uniform float u_bars[64];
uniform float u_peaks[64];
uniform vec4 u_fill_color;
uniform vec4 u_border_color;
uniform float u_fade;
uniform int u_playing;
uniform float u_ghost_alpha;

void main() {
    if (u_fade <= 0.0 || u_bar_count <= 0 || u_segments <= 0) {
        discard;
    }

    float width = u_resolution.x;
    float height = u_resolution.y;
    if (width <= 0.0 || height <= 0.0) {
        discard;
    }

    // Derive logical fragment coordinates from the physical framebuffer
    // position. QOpenGLWidget renders into a device-pixel-scaled FBO, so we
    // map gl_FragCoord (physical) back into QWidget logical space using the
    // current device pixel ratio.
    float dpr = (u_dpr <= 0.0) ? 1.0 : u_dpr;
    float fb_height = height * dpr;
    vec2 fragCoord = vec2(gl_FragCoord.x / dpr, (fb_height - gl_FragCoord.y) / dpr);

    float margin_x = 8.0;
    float margin_y = 6.0;
    float gap = 2.0;
    float seg_gap = 1.0;

    // Match QWidget geometry: inner rect is rect.adjusted(margin_x, margin_y,
    // -margin_x, -margin_y). For a logical rect starting at (0, 0) this
    // gives width = W - 2*margin_x and height = H - 2*margin_y.
    float inner_left = margin_x;
    float inner_top = margin_y;
    float inner_width = width - margin_x * 2.0;
    float inner_height = height - margin_y * 2.0;
    float inner_right = inner_left + inner_width;
    float inner_bottom = inner_top + inner_height;

    if (inner_width <= 0.0 || inner_height <= 0.0) {
        discard;
    }

    // Discard anything outside the bar field vertically so we don't fill
    // the entire card when active_segments is high.
    if (fragCoord.y < inner_top || fragCoord.y > inner_bottom) {
        discard;
    }

    float bars_left = inner_left + 5.0;
    float total_gap = gap * float(u_bar_count - 1);
    float bar_width = (inner_width - total_gap) / float(u_bar_count);
    bar_width = floor(bar_width);
    if (bar_width < 1.0) {
        discard;
    }

    float x_rel = fragCoord.x - bars_left;
    if (x_rel < 0.0) {
        discard;
    }
    float span = float(u_bar_count) * bar_width + total_gap;
    if (x_rel >= span) {
        discard;
    }

    float step_x = bar_width + gap;
    int bar_index = int(floor(x_rel / step_x));
    if (bar_index < 0 || bar_index >= u_bar_count) {
        discard;
    }

    // Local X coordinate within the bar; discard the explicit gap region.
    // Use a half-open range [0, bar_width) so that we never classify the
    // gap pixel as part of the bar due to floating-point rounding.
    float bar_local_x = x_rel - float(bar_index) * step_x;
    if (bar_local_x < 0.0 || bar_local_x >= bar_width) {
        discard;
    }

    float value = u_bars[bar_index];
    if (value < 0.0) {
        value = 0.0;
    }
    if (value > 1.0) {
        value = 1.0;
    }

    float peak = u_peaks[bar_index];
    if (peak < 0.0) {
        peak = 0.0;
    }
    if (peak > 1.0) {
        peak = 1.0;
    }

    float total_seg_gap = seg_gap * float(u_segments - 1);
    float seg_height = (inner_height - total_seg_gap) / float(u_segments);
    seg_height = floor(seg_height);
    if (seg_height < 1.0) {
        discard;
    }

    float base_bottom = inner_bottom;
    float step_y = seg_height + seg_gap;
    float y_rel = base_bottom - fragCoord.y;
    if (y_rel < 0.0) {
        discard;
    }

    int seg_index = int(floor(y_rel / step_y));
    if (seg_index < 0) {
        discard;
    }

    // Local Y coordinate within the segment; discard the vertical gap
    // region using a half-open range [0, seg_height).
    float seg_local_y = y_rel - float(seg_index) * step_y;
    if (seg_local_y < 0.0 || seg_local_y >= seg_height) {
        discard;
    }

    float boosted = value * 1.2;
    if (boosted > 1.0) {
        boosted = 1.0;
    }
    int active_segments = int(round(boosted * float(u_segments)));
    if (active_segments <= 0) {
        // Always keep at least one active segment so the visualiser has
        // a visible baseline even when audio energy is near zero or the
        // player is paused.
        active_segments = 1;
    }

    // Determine whether this fragment belongs to the main bar body
    // or to a trailing ghost segment derived from the decaying peak.
    int peak_segments = active_segments;
    bool is_ghost_frag = false;
    if (peak > value) {
        float delta = peak - value;
        if (delta < 0.0) {
            delta = 0.0;
        }

        // Map the peak/value difference into extra segments above the
        // current active height. Even a modest drop produces at least one
        // ghost segment when there is vertical room.
        float boosted_delta = delta * 1.2;
        if (boosted_delta > 1.0) {
            boosted_delta = 1.0;
        }
        int extra_segments = int(ceil(boosted_delta * float(u_segments)));
        if (extra_segments <= 0 && delta > 0.01 && active_segments < u_segments) {
            extra_segments = 1;
        }

        peak_segments = active_segments + extra_segments;
        if (peak_segments > u_segments) {
            peak_segments = u_segments;
        }
        if (peak_segments > active_segments && seg_index >= active_segments && seg_index < peak_segments) {
            is_ghost_frag = true;
        }
    }

    bool is_bar_frag = (active_segments > 0) && (seg_index < active_segments);
    if (!is_bar_frag && !is_ghost_frag) {
        discard;
    }

    // Draw a bar segment using the configured fill/border colours. Visual
    // segmentation between blocks/segments is still provided by the explicit
    // horizontal/vertical gaps; border detection operates in integer-like
    // local coordinates to remain stable across resolutions/DPI.

    float bw_px = floor(bar_width);
    float sh_px = floor(seg_height);
    float bx = floor(bar_local_x);
    float by = floor(seg_local_y);

    bool on_border = false;
    if (is_bar_frag) {
        if (bw_px <= 2.0 || sh_px <= 2.0) {
            on_border = true;
        } else {
            if (bx <= 0.0 || bx >= bw_px - 1.0 || by <= 0.0 || by >= sh_px - 1.0) {
                on_border = true;
            }
        }
    }

    vec4 fill = u_fill_color;
    vec4 border = u_border_color;
    fill.a *= u_fade;
    border.a *= u_fade;

    if (is_ghost_frag) {
        // Ghost bars use the bright border colour with an additional alpha
        // falloff along the trail so newer ghost segments just above the
        // live bar remain stronger while the oldest/highest segments fade
        // out more quickly.
        float ghost_alpha = clamp(u_ghost_alpha, 0.0, 1.0);
        if (ghost_alpha <= 0.0) {
            discard;
        }

        // Normalise the distance of this ghost segment above the active bar
        // into [0, 1], where 0.0 sits directly above the bar and 1.0 is the
        // top-most ghost segment.
        float ghost_factor = 1.0;
        if (peak_segments > active_segments) {
            float ghost_idx = float(seg_index - active_segments);
            float ghost_len = float(max(1, peak_segments - active_segments));
            float t = 0.0;
            if (ghost_len > 1.0) {
                t = clamp(ghost_idx / (ghost_len - 1.0), 0.0, 1.0);
            }
            // Fade from full strength near the bar to a softer outline at
            // the very top of the trail.
            float start = 1.0;
            float end = 0.25;
            ghost_factor = mix(start, end, t);
        }

        vec4 ghost = border;
        ghost.a *= ghost_alpha * ghost_factor;
        fragColor = ghost;
    } else {
        fragColor = on_border ? border : fill;
    }
}
"""

        prog = _gl.glCreateProgram()
        vs = _gl.glCreateShader(_gl.GL_VERTEX_SHADER)
        fs = _gl.glCreateShader(_gl.GL_FRAGMENT_SHADER)

        _gl.glShaderSource(vs, vs_source)
        _gl.glCompileShader(vs)
        status = _gl.glGetShaderiv(vs, _gl.GL_COMPILE_STATUS)
        if not status:
            raise RuntimeError("SpotifyBarsGLOverlay vertex shader compile failed")

        _gl.glShaderSource(fs, fs_source)
        _gl.glCompileShader(fs)
        status = _gl.glGetShaderiv(fs, _gl.GL_COMPILE_STATUS)
        if not status:
            raise RuntimeError("SpotifyBarsGLOverlay fragment shader compile failed")

        _gl.glAttachShader(prog, vs)
        _gl.glAttachShader(prog, fs)
        _gl.glLinkProgram(prog)
        link_ok = _gl.glGetProgramiv(prog, _gl.GL_LINK_STATUS)
        if not link_ok:
            raise RuntimeError("SpotifyBarsGLOverlay program link failed")

        _gl.glDeleteShader(vs)
        _gl.glDeleteShader(fs)

        vao = _gl.glGenVertexArrays(1)
        vbo = _gl.glGenBuffers(1)

        _gl.glBindVertexArray(vao)
        _gl.glBindBuffer(_gl.GL_ARRAY_BUFFER, vbo)
        vertices = np.array(
            [
                -1.0,
                -1.0,
                1.0,
                -1.0,
                -1.0,
                1.0,
                1.0,
                1.0,
            ],
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

        self._gl_program = prog
        self._gl_vao = vao
        self._gl_vbo = vbo
        self._u_resolution = _gl.glGetUniformLocation(prog, "u_resolution")
        self._u_bar_count = _gl.glGetUniformLocation(prog, "u_bar_count")
        self._u_segments = _gl.glGetUniformLocation(prog, "u_segments")
        self._u_bars = _gl.glGetUniformLocation(prog, "u_bars")
        self._u_peaks = _gl.glGetUniformLocation(prog, "u_peaks")
        self._u_fill_color = _gl.glGetUniformLocation(prog, "u_fill_color")
        self._u_border_color = _gl.glGetUniformLocation(prog, "u_border_color")
        self._u_fade = _gl.glGetUniformLocation(prog, "u_fade")
        self._u_playing = _gl.glGetUniformLocation(prog, "u_playing")
        self._u_ghost_alpha = _gl.glGetUniformLocation(prog, "u_ghost_alpha")
        self._u_dpr = _gl.glGetUniformLocation(prog, "u_dpr")

    def _render_with_shader(self, rect: QRect, fade: float) -> bool:
        if self._gl_disabled:
            return False

        try:
            if self._gl_program is None or self._gl_vao is None:
                self._init_gl_pipeline()
        except Exception:
            self._gl_disabled = True
            logger.debug("[SPOTIFY_VIS] GL pipeline unavailable, falling back to QPainter", exc_info=True)
            return False

        if self._gl_program is None or self._gl_vao is None:
            return False

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

            _gl.glUseProgram(self._gl_program)
            _gl.glBindVertexArray(self._gl_vao)

            if self._u_resolution is not None:
                _gl.glUniform2f(self._u_resolution, float(width), float(height))
            if self._u_bar_count is not None:
                _gl.glUniform1i(self._u_bar_count, min(count, 64))
            if self._u_segments is not None:
                _gl.glUniform1i(self._u_segments, segments)

            if getattr(self, "_u_dpr", None) is not None:
                try:
                    # Prefer the window's devicePixelRatio when available; fall
                    # back to the widget's own logical DPR. Clamp to a sane
                    # range so that bad values do not explode geometry.
                    dpr = 1.0
                    try:
                        win = self.windowHandle()  # type: ignore[attr-defined]
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
                    _gl.glUniform1f(self._u_dpr, dpr)
                except Exception:
                    _gl.glUniform1f(self._u_dpr, 1.0)

            bars = list(self._bars)
            if not bars:
                _gl.glBindVertexArray(0)
                return False
            if len(bars) < 64:
                bars = bars + [0.0] * (64 - len(bars))
            else:
                bars = bars[:64]

            if not getattr(self, "_debug_bars_logged", False):
                try:
                    if count > 0:
                        sample = bars[:count]
                        mn = min(sample)
                        mx = max(sample)
                    else:
                        mn = 0.0
                        mx = 0.0
                    logger.debug(
                        "[SPOTIFY_VIS] Shader bars snapshot: count=%d, min=%.4f, max=%.4f",
                        count,
                        mn,
                        mx,
                    )
                except Exception:
                    pass
                try:
                    self._debug_bars_logged = True
                except Exception:
                    pass

            if self._u_bars is not None:
                buf = np.asarray(bars, dtype="float32")
                _gl.glUniform1fv(self._u_bars, 64, buf)

            peaks = list(self._peaks)
            if len(peaks) < len(bars):
                peaks = peaks + [0.0] * (len(bars) - len(peaks))
            if len(peaks) < 64:
                peaks = peaks + [0.0] * (64 - len(peaks))
            else:
                peaks = peaks[:64]

            if self._u_peaks is not None:
                buf_peaks = np.asarray(peaks, dtype="float32")
                _gl.glUniform1fv(self._u_peaks, 64, buf_peaks)

            fill = QColor(self._fill_color)
            if self._u_fill_color is not None:
                _gl.glUniform4f(
                    self._u_fill_color,
                    float(fill.redF()),
                    float(fill.greenF()),
                    float(fill.blueF()),
                    float(fill.alphaF()),
                )

            border = QColor(self._border_color)
            if self._u_border_color is not None:
                _gl.glUniform4f(
                    self._u_border_color,
                    float(border.redF()),
                    float(border.greenF()),
                    float(border.blueF()),
                    float(border.alphaF()),
                )
            if self._u_fade is not None:
                _gl.glUniform1f(self._u_fade, float(max(0.0, min(1.0, fade))))

            if self._u_playing is not None:
                _gl.glUniform1i(self._u_playing, 1 if self._playing else 0)

            if self._u_ghost_alpha is not None:
                try:
                    ga = float(self._ghost_alpha if self._ghosting_enabled else 0.0)
                except Exception:
                    ga = 0.0
                if ga < 0.0:
                    ga = 0.0
                if ga > 1.0:
                    ga = 1.0
                _gl.glUniform1f(self._u_ghost_alpha, ga)

            _gl.glDrawArrays(_gl.GL_TRIANGLE_STRIP, 0, 4)
            _gl.glBindVertexArray(0)
            _gl.glUseProgram(0)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Shader-based bar rendering failed", exc_info=True)
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
        except Exception:
            pass

        painter = QPainter(self)
        try:
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            except Exception:
                pass

            painter.setBrush(fill)
            painter.setPen(border)

            max_segments = min(segments, len(seg_y))
            draw_count = min(count, len(bar_x), len(self._bars))

            for i in range(draw_count):
                x = bar_x[i]
                try:
                    value = float(self._bars[i])
                except Exception:
                    value = 0.0
                if value <= 0.0:
                    continue
                if value > 1.0:
                    value = 1.0
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
