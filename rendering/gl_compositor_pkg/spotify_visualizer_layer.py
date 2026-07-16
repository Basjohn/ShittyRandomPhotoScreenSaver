"""Display-owned Spotify visualizer layer for the single GL compositor."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Optional

from OpenGL import GL as gl
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QImage, QOpenGLContext, QPainter

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.resources.manager import ResourceManager
from widgets.spotify_bars_gl_overlay import SpotifyVisualizerGLRenderer
from widgets.spotify_visualizer.card_paint import paint_compositor_card

logger = get_logger(__name__)

_FALSE_VALUES = {"0", "false", "no", "off", "legacy", "disabled"}

_COMPOSITE_VERTEX_SHADER = """
#version 410 core
layout(location = 0) in vec2 a_pos;

uniform vec4 u_target_rect;
out vec2 v_uv;

void main() {
    vec2 uv = a_pos * 0.5 + 0.5;
    vec2 pos = mix(u_target_rect.xy, u_target_rect.zw, uv);
    gl_Position = vec4(pos, 0.0, 1.0);
    v_uv = uv;
}
"""

_COMPOSITE_FRAGMENT_SHADER = """
#version 410 core
in vec2 v_uv;
out vec4 frag_color;

uniform sampler2D u_visualizer_texture;

void main() {
    frag_color = texture(u_visualizer_texture, v_uv);
}
"""


def single_surface_visualizer_enabled() -> bool:
    """Return whether the compositor-owned visualizer path is requested."""

    raw = str(os.environ.get("SRPSS_SINGLE_SURFACE_VISUALIZER", "1") or "1")
    return raw.strip().lower() not in _FALSE_VALUES


def _compile_shader(shader_type: int, source: str) -> int:
    shader = int(gl.glCreateShader(shader_type))
    gl.glShaderSource(shader, source)
    gl.glCompileShader(shader)
    if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
        info = gl.glGetShaderInfoLog(shader)
        gl.glDeleteShader(shader)
        raise RuntimeError(f"Visualizer composite shader compile failed: {info}")
    return shader


@dataclass
class _FramebufferSlot:
    framebuffer: int
    texture: int
    stencil: int
    width_px: int
    height_px: int
    dpr: float
    framebuffer_rid: Optional[str] = None
    texture_rid: Optional[str] = None
    stencil_rid: Optional[str] = None


class CompositorSpotifyVisualizerLayer:
    """Renderer target and overlay-compatible facade owned by one compositor."""

    render_surface_kind = "compositor"

    _LOCAL_ATTRS = {
        "_compositor",
        "_renderer",
        "_geometry",
        "_visible",
        "_object_name",
        "_front",
        "_back",
        "_retained_front",
        "_buffer_size_px",
        "_buffer_logical_size",
        "_buffer_dpr",
        "_composite_program",
        "_composite_program_rid",
        "_composite_target_loc",
        "_composite_sampler_loc",
        "_resource_manager",
        "_has_last_good_frame",
        "_last_good_frame_ts",
        "_render_failure_count",
        "_render_failure_log_ts",
        "_last_failure_signature",
        "_retired",
        "_paint_count",
        "_fbo_resize_count",
        "_last_snapshot",
        "_perf_fbo_resize_window",
        "_perf_render_failure_window",
        "_perf_retained_last_good_window",
        "_prepare_failure_domain",
        "_prepare_failure_reason",
        "_prepare_attempted_this_paint",
        "_prepare_retry_not_before_ts",
        "_prepare_retry_delay_s",
        "_last_render_attempt_generation",
        "_last_rendered_state_generation",
        "_fbo_render_count",
        "_texture_reuse_count",
        "_perf_fbo_render_window",
        "_perf_texture_reuse_window",
    }

    def __init__(self, compositor: Any, *, initial_mode: str | None = None) -> None:
        object.__setattr__(self, "_compositor", compositor)
        object.__setattr__(self, "_geometry", QRect())
        object.__setattr__(self, "_visible", False)
        object.__setattr__(self, "_object_name", "spotify_visualizer_compositor_layer")
        object.__setattr__(self, "_front", None)
        object.__setattr__(self, "_back", None)
        object.__setattr__(self, "_retained_front", None)
        object.__setattr__(self, "_buffer_size_px", QSize())
        object.__setattr__(self, "_buffer_logical_size", QSize())
        object.__setattr__(self, "_buffer_dpr", 1.0)
        object.__setattr__(self, "_composite_program", 0)
        object.__setattr__(self, "_composite_program_rid", None)
        object.__setattr__(self, "_composite_target_loc", -1)
        object.__setattr__(self, "_composite_sampler_loc", -1)
        object.__setattr__(self, "_resource_manager", ResourceManager.get_or_create_app_shared())
        object.__setattr__(self, "_has_last_good_frame", False)
        object.__setattr__(self, "_last_good_frame_ts", 0.0)
        object.__setattr__(self, "_render_failure_count", 0)
        object.__setattr__(self, "_render_failure_log_ts", 0.0)
        object.__setattr__(self, "_last_failure_signature", None)
        object.__setattr__(self, "_retired", False)
        object.__setattr__(self, "_paint_count", 0)
        object.__setattr__(self, "_fbo_resize_count", 0)
        object.__setattr__(self, "_last_snapshot", None)
        object.__setattr__(self, "_perf_fbo_resize_window", 0)
        object.__setattr__(self, "_perf_render_failure_window", 0)
        object.__setattr__(self, "_perf_retained_last_good_window", 0)
        object.__setattr__(self, "_prepare_failure_domain", "")
        object.__setattr__(self, "_prepare_failure_reason", "")
        object.__setattr__(self, "_prepare_attempted_this_paint", False)
        object.__setattr__(self, "_prepare_retry_not_before_ts", 0.0)
        object.__setattr__(self, "_prepare_retry_delay_s", 0.0)
        object.__setattr__(self, "_last_render_attempt_generation", -1)
        object.__setattr__(self, "_last_rendered_state_generation", -1)
        object.__setattr__(self, "_fbo_render_count", 0)
        object.__setattr__(self, "_texture_reuse_count", 0)
        object.__setattr__(self, "_perf_fbo_render_window", 0)
        object.__setattr__(self, "_perf_texture_reuse_window", 0)
        object.__setattr__(
            self,
            "_renderer",
            SpotifyVisualizerGLRenderer(self, initial_mode=initial_mode),
        )

    def __getattr__(self, name: str):
        renderer = object.__getattribute__(self, "_renderer")
        return getattr(renderer, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._LOCAL_ATTRS or name.startswith("_layer_"):
            object.__setattr__(self, name, value)
            return
        renderer = self.__dict__.get("_renderer")
        if renderer is not None and hasattr(renderer, name):
            setattr(renderer, name, value)
            return
        object.__setattr__(self, name, value)

    # ------------------------------------------------------------------
    # Overlay-compatible surface protocol
    # ------------------------------------------------------------------

    def parent(self):
        return self._compositor.parent()

    def geometry(self) -> QRect:
        return QRect(self._geometry)

    def setGeometry(self, rect: QRect) -> None:
        normalized = QRect(rect)
        if normalized == self._geometry:
            return
        size_changed = normalized.size() != self._geometry.size()
        self._geometry = normalized
        if size_changed:
            self._buffer_logical_size = QSize()
            self._prepare_retry_not_before_ts = 0.0
            self._prepare_retry_delay_s = 0.0
        self.update()

    def rect(self) -> QRect:
        return QRect(0, 0, self._geometry.width(), self._geometry.height())

    def show(self) -> None:
        if self._retired:
            return
        if not self._visible:
            self._visible = True
            self.update()

    def hide(self) -> None:
        if self._visible:
            self._visible = False
            self.update()

    def isVisible(self) -> bool:
        return bool(self._visible and not self._retired)

    def update(self) -> None:
        if self._retired:
            return
        try:
            requester = getattr(self._compositor, "request_scene_update", None)
            if callable(requester):
                requester()
            else:
                self._compositor.update()
        except RuntimeError:
            return

    def invalidate_surface_metrics(self, *, reason: str) -> None:
        """Force a safe FBO refresh after logical-size, screen, or DPR changes."""

        if self._retired:
            return
        self._buffer_logical_size = QSize()
        self._last_render_attempt_generation = -1
        self._prepare_retry_not_before_ts = 0.0
        self._prepare_retry_delay_s = 0.0
        logger.debug(
            "[SPOTIFY_VIS] Invalidated compositor visualizer surface metrics reason=%s",
            reason,
        )
        self.update()

    def raise_(self) -> None:
        # The layer is part of the compositor scene; Qt sibling ordering is
        # handled by DisplayWidget/WidgetManager above that surface.
        return

    def setObjectName(self, name: str) -> None:
        self._object_name = str(name or "")

    def objectName(self) -> str:
        return self._object_name

    def timer_parent(self):
        return self._compositor

    def windowHandle(self):
        return self._compositor.windowHandle()

    def devicePixelRatioF(self) -> float:
        return float(self._compositor.devicePixelRatioF())

    def makeCurrent(self) -> None:
        self._compositor.makeCurrent()

    def doneCurrent(self) -> None:
        self._compositor.doneCurrent()

    def deleteLater(self) -> None:
        self._retired = True
        self._visible = False
        try:
            requester = getattr(self._compositor, "request_scene_update", None)
            if callable(requester):
                requester()
            else:
                self._compositor.update()
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # GL lifecycle
    # ------------------------------------------------------------------

    def _context_is_current(self) -> bool:
        try:
            return QOpenGLContext.currentContext() is self._compositor.context()
        except Exception:
            return False

    def _acquire_context(self) -> bool:
        if self._context_is_current():
            return False
        self._compositor.makeCurrent()
        return True

    def _release_context(self, acquired: bool) -> None:
        if acquired:
            self._compositor.doneCurrent()

    def force_renderer_initialize(self) -> None:
        acquired = False
        try:
            acquired = self._acquire_context()
            if not self._renderer.is_gl_ready() and not self._renderer._gl_state.is_error():
                self._renderer.initialize_renderer_gl()
            if not self._renderer.is_gl_ready():
                self._prepare_failure_domain = "shared_renderer"
                self._prepare_failure_reason = "renderer_not_ready"
                raise RuntimeError("Visualizer renderer did not reach READY")
            if not self._ensure_composite_program():
                raise RuntimeError("Visualizer composite program unavailable")
            if self._geometry.width() > 0 and self._geometry.height() > 0:
                if not self._ensure_framebuffers():
                    raise RuntimeError("Visualizer framebuffers unavailable")
            self._prepare_failure_domain = ""
            self._prepare_failure_reason = ""
            self._prepare_retry_not_before_ts = 0.0
            self._prepare_retry_delay_s = 0.0
        finally:
            self._release_context(acquired)

    def is_render_ready(self) -> bool:
        if not self._renderer.is_gl_ready() or not self._composite_program:
            return False
        if self._geometry.width() <= 0 or self._geometry.height() <= 0:
            return True
        return bool(self._front is not None and self._back is not None)

    def hard_legacy_fallback_reason(self) -> str | None:
        """Return a legacy-worthy hard failure, never a transient readiness miss.

        The legacy adapter shares this layer's renderer implementation, so a
        renderer/shader failure is not a reason to create a second GL surface.
        Only failures owned by the compositor layer itself can justify that
        pre-reveal escape hatch.
        """

        try:
            state = self._compositor.get_gl_state()
            state_name = str(getattr(state, "name", state)).upper()
        except Exception:
            state_name = ""
        if state_name in {"ERROR", "CONTEXT_LOST"}:
            return f"compositor_state_{state_name.lower()}"
        if self._prepare_failure_domain in {"composite_program", "framebuffer"}:
            return self._prepare_failure_reason or self._prepare_failure_domain
        return None

    def startup_retry_allowed(self) -> bool:
        """Return whether a short hidden startup retry can still make progress."""

        if self._retired:
            return False
        terminal_states = {"ERROR", "CONTEXT_LOST", "DESTROYING", "DESTROYED"}
        try:
            compositor_state = self._compositor.get_gl_state()
            compositor_name = str(
                getattr(compositor_state, "name", compositor_state)
            ).upper()
        except Exception:
            compositor_name = ""
        if compositor_name in terminal_states:
            return False
        try:
            renderer_state = self._renderer.get_gl_state()
            renderer_name = str(
                getattr(renderer_state, "name", renderer_state)
            ).upper()
        except Exception:
            renderer_name = ""
        if renderer_name in terminal_states:
            return False
        if self._prepare_failure_domain in {
            "shared_renderer",
            "composite_program",
            "framebuffer",
            "native_paint",
        }:
            return False
        return True

    def clear_renderer_backbuffer(self) -> None:
        acquired = False
        try:
            acquired = self._acquire_context()
            for slot in (self._front, self._back):
                if slot is None:
                    continue
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, slot.framebuffer)
                gl.glViewport(0, 0, self._buffer_size_px.width(), self._buffer_size_px.height())
                gl.glDisable(gl.GL_SCISSOR_TEST)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT)
            gl.glBindFramebuffer(
                gl.GL_FRAMEBUFFER,
                int(self._compositor.defaultFramebufferObject()),
            )
            # A retained pre-resize frame is presentation state, not an active
            # backbuffer. Explicit clear must retire it so stopped/reset
            # visualizers cannot resurrect stale pixels.
            self._release_retained_front()
            self._has_last_good_frame = False
            self._last_render_attempt_generation = -1
            self._last_rendered_state_generation = -1
        finally:
            self._release_context(acquired)
        self.update()

    def _register_handle(
        self,
        handle: int,
        handle_type: str,
        cleanup,
        description: str,
    ) -> Optional[str]:
        try:
            return self._resource_manager.register_gl_handle(
                int(handle),
                handle_type,
                cleanup,
                description=description,
                group="spotify_vis_compositor",
            )
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to register compositor visualizer %s",
                description,
                exc_info=True,
            )
            return None

    def _release_handle(
        self,
        handle: int,
        resource_id: Optional[str],
        direct_cleanup,
        *,
        context_valid: bool,
    ) -> None:
        if not handle:
            return
        if resource_id:
            try:
                self._resource_manager.unregister(
                    resource_id,
                    force=True,
                    cleanup=context_valid,
                )
                return
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Managed compositor visualizer release failed",
                    exc_info=True,
                )
                try:
                    self._resource_manager.unregister(
                        resource_id,
                        force=True,
                        cleanup=False,
                    )
                except Exception:
                    pass
        if context_valid:
            direct_cleanup(int(handle))

    def _ensure_composite_program(self) -> bool:
        if self._composite_program:
            return True
        vertex = 0
        fragment = 0
        program = 0
        try:
            vertex = _compile_shader(gl.GL_VERTEX_SHADER, _COMPOSITE_VERTEX_SHADER)
            fragment = _compile_shader(gl.GL_FRAGMENT_SHADER, _COMPOSITE_FRAGMENT_SHADER)
            program = int(gl.glCreateProgram())
            gl.glAttachShader(program, vertex)
            gl.glAttachShader(program, fragment)
            gl.glLinkProgram(program)
            if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
                info = gl.glGetProgramInfoLog(program)
                raise RuntimeError(f"Visualizer composite program link failed: {info}")
            target_loc = int(gl.glGetUniformLocation(program, "u_target_rect"))
            sampler_loc = int(
                gl.glGetUniformLocation(program, "u_visualizer_texture")
            )
            if target_loc < 0 or sampler_loc < 0:
                raise RuntimeError(
                    "Visualizer composite program required uniforms unavailable"
                )
            program_rid = self._register_handle(
                program,
                "program",
                gl.glDeleteProgram,
                "Compositor visualizer texture composite program",
            )
            self._composite_program = program
            self._composite_target_loc = target_loc
            self._composite_sampler_loc = sampler_loc
            self._composite_program_rid = program_rid
            program = 0
            return True
        except Exception:
            if program:
                try:
                    gl.glDeleteProgram(program)
                except Exception:
                    logger.debug(
                        "[SPOTIFY_VIS] Failed to delete partial composite program",
                        exc_info=True,
                    )
            self._composite_program = 0
            self._composite_program_rid = None
            self._composite_target_loc = -1
            self._composite_sampler_loc = -1
            self._prepare_failure_domain = "composite_program"
            self._prepare_failure_reason = "composite_program_init_failed"
            logger.error(
                "[SPOTIFY_VIS][COMPOSITOR] Failed to initialize visualizer composite program",
                exc_info=True,
            )
            return False
        finally:
            if vertex:
                gl.glDeleteShader(vertex)
            if fragment:
                gl.glDeleteShader(fragment)

    def _create_framebuffer_slot(
        self,
        width_px: int,
        height_px: int,
        *,
        dpr: float = 1.0,
    ) -> _FramebufferSlot:
        framebuffer = 0
        texture = 0
        stencil = 0
        try:
            framebuffer = int(gl.glGenFramebuffers(1))
            texture = int(gl.glGenTextures(1))
            stencil = int(gl.glGenRenderbuffers(1))

            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                getattr(gl, "GL_RGBA8", gl.GL_RGBA),
                width_px,
                height_px,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                None,
            )

            # The visualizer mask uses stencil only. Avoid allocating an
            # unused depth plane twice per active display.
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, stencil)
            gl.glRenderbufferStorage(
                gl.GL_RENDERBUFFER,
                gl.GL_STENCIL_INDEX8,
                width_px,
                height_px,
            )

            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer)
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER,
                gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D,
                texture,
                0,
            )
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER,
                gl.GL_STENCIL_ATTACHMENT,
                gl.GL_RENDERBUFFER,
                stencil,
            )
            status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
            if status != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(
                    f"Visualizer framebuffer incomplete: 0x{int(status):x}"
                )
        except Exception:
            # Registration happens only after a complete FBO exists, so
            # partially created handles remain directly owned by this scope.
            if framebuffer:
                gl.glDeleteFramebuffers(1, [framebuffer])
            if stencil:
                gl.glDeleteRenderbuffers(1, [stencil])
            if texture:
                gl.glDeleteTextures(1, [texture])
            raise

        return _FramebufferSlot(
            framebuffer=framebuffer,
            texture=texture,
            stencil=stencil,
            width_px=width_px,
            height_px=height_px,
            dpr=dpr,
            framebuffer_rid=self._register_handle(
                framebuffer,
                "framebuffer",
                lambda handle: gl.glDeleteFramebuffers(1, [handle]),
                "Compositor visualizer framebuffer",
            ),
            texture_rid=self._register_handle(
                texture,
                "texture",
                lambda handle: gl.glDeleteTextures(1, [handle]),
                "Compositor visualizer color texture",
            ),
            stencil_rid=self._register_handle(
                stencil,
                "renderbuffer",
                lambda handle: gl.glDeleteRenderbuffers(1, [handle]),
                "Compositor visualizer stencil buffer",
            ),
        )

    def _release_framebuffer_slot(
        self,
        slot: Optional[_FramebufferSlot],
        *,
        context_valid: bool,
    ) -> None:
        if slot is None:
            return
        self._release_handle(
            slot.framebuffer,
            slot.framebuffer_rid,
            lambda handle: gl.glDeleteFramebuffers(1, [handle]),
            context_valid=context_valid,
        )
        self._release_handle(
            slot.stencil,
            slot.stencil_rid,
            lambda handle: gl.glDeleteRenderbuffers(1, [handle]),
            context_valid=context_valid,
        )
        self._release_handle(
            slot.texture,
            slot.texture_rid,
            lambda handle: gl.glDeleteTextures(1, [handle]),
            context_valid=context_valid,
        )

    def _ensure_framebuffers(self) -> bool:
        logical_size = self._geometry.size()
        if logical_size.width() <= 0 or logical_size.height() <= 0:
            return False
        dpr = max(1.0, min(4.0, float(self.devicePixelRatioF())))
        width_px = max(1, int(round(logical_size.width() * dpr)))
        height_px = max(1, int(round(logical_size.height() * dpr)))
        physical_size = QSize(width_px, height_px)
        if (
            self._front is not None
            and self._back is not None
            and self._buffer_size_px == physical_size
            and self._buffer_logical_size == logical_size
            and abs(self._buffer_dpr - dpr) < 0.001
        ):
            return True

        old_front = self._front
        old_back = self._back
        new_front = None
        new_back = None
        try:
            new_front = self._create_framebuffer_slot(
                width_px,
                height_px,
                dpr=dpr,
            )
            new_back = self._create_framebuffer_slot(
                width_px,
                height_px,
                dpr=dpr,
            )
        except Exception:
            self._release_framebuffer_slot(new_front, context_valid=True)
            self._release_framebuffer_slot(new_back, context_valid=True)
            logger.error(
                "[SPOTIFY_VIS][COMPOSITOR] Failed to allocate visualizer buffers "
                "logical=%sx%s physical=%sx%s dpr=%.3f",
                logical_size.width(),
                logical_size.height(),
                width_px,
                height_px,
                dpr,
                exc_info=True,
            )
            self._prepare_failure_domain = "framebuffer"
            self._prepare_failure_reason = "framebuffer_allocation_failed"
            return False
        finally:
            try:
                gl.glBindFramebuffer(
                    gl.GL_FRAMEBUFFER,
                    int(self._compositor.defaultFramebufferObject()),
                )
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to restore compositor framebuffer after visualizer allocation",
                    exc_info=True,
                )

        if self._has_last_good_frame and old_front is not None:
            self._release_framebuffer_slot(
                self._retained_front,
                context_valid=True,
            )
            self._retained_front = old_front
        else:
            self._release_framebuffer_slot(old_front, context_valid=True)

        self._front = new_front
        self._back = new_back
        self._buffer_size_px = physical_size
        self._buffer_logical_size = QSize(logical_size)
        self._buffer_dpr = dpr
        self._has_last_good_frame = False
        self._last_render_attempt_generation = -1
        self._last_rendered_state_generation = -1
        self._fbo_resize_count += 1
        self._perf_fbo_resize_window += 1
        self._prepare_failure_domain = ""
        self._prepare_failure_reason = ""
        self._prepare_retry_not_before_ts = 0.0
        self._prepare_retry_delay_s = 0.0
        self._release_framebuffer_slot(old_back, context_valid=True)
        return True

    def initialize_gl(self) -> bool:
        if self._retired:
            return False
        if not self._renderer.is_gl_ready():
            if self._renderer._gl_state.is_error():
                self._prepare_failure_domain = "shared_renderer"
                self._prepare_failure_reason = "renderer_error"
                return False
            self._renderer.initialize_renderer_gl()
        if not self._renderer.is_gl_ready():
            self._prepare_failure_domain = "shared_renderer"
            self._prepare_failure_reason = "renderer_not_ready"
            return False
        return self._ensure_composite_program()

    def cleanup_gl(self) -> None:
        if self._retired and not any(
            (
                self._front,
                self._back,
                self._retained_front,
                self._composite_program,
                self._renderer._gl_programs,
            )
        ):
            return
        acquired = False
        context_valid = False
        try:
            try:
                acquired = self._acquire_context()
                context_valid = True
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Compositor visualizer cleanup has no valid context",
                    exc_info=True,
                )
            self._release_framebuffer_slot(self._front, context_valid=context_valid)
            self._release_framebuffer_slot(self._back, context_valid=context_valid)
            self._release_framebuffer_slot(
                self._retained_front,
                context_valid=context_valid,
            )
            self._front = None
            self._back = None
            self._retained_front = None
            self._buffer_size_px = QSize()
            self._buffer_logical_size = QSize()
            self._has_last_good_frame = False
            self._last_render_attempt_generation = -1
            self._last_rendered_state_generation = -1
            self._prepare_attempted_this_paint = False
            self._prepare_retry_not_before_ts = 0.0
            self._prepare_retry_delay_s = 0.0
            self._release_handle(
                self._composite_program,
                self._composite_program_rid,
                gl.glDeleteProgram,
                context_valid=context_valid,
            )
            self._composite_program = 0
            self._composite_program_rid = None
            self._renderer.cleanup_gl(context_current=context_valid)
        finally:
            self._release_context(acquired)
        logger.debug("[SPOTIFY_VIS] Compositor visualizer GL handles cleaned up")

    # ------------------------------------------------------------------
    # Compositor paint
    # ------------------------------------------------------------------

    def _needs_prepare(self) -> bool:
        if not self._renderer.is_gl_ready() or not self._composite_program:
            return True
        logical_size = self._geometry.size()
        dpr = max(1.0, min(4.0, float(self.devicePixelRatioF())))
        physical_size = QSize(
            max(1, int(round(logical_size.width() * dpr))),
            max(1, int(round(logical_size.height() * dpr))),
        )
        return (
            self._front is None
            or self._back is None
            or self._buffer_size_px != physical_size
            or self._buffer_logical_size != logical_size
            or abs(self._buffer_dpr - dpr) >= 0.001
        )

    def _prepare_inside_painter(self, painter: QPainter) -> bool:
        if not self._needs_prepare():
            self._prepare_attempted_this_paint = False
            self._prepare_retry_not_before_ts = 0.0
            self._prepare_retry_delay_s = 0.0
            return True
        now = time.monotonic()
        if (
            self._prepare_failure_domain
            and now < self._prepare_retry_not_before_ts
        ):
            self._prepare_attempted_this_paint = False
            return False
        self._prepare_attempted_this_paint = True
        native_started = False
        try:
            painter.beginNativePainting()
            native_started = True
            prepared = bool(self.initialize_gl() and self._ensure_framebuffers())
        except Exception:
            self._prepare_failure_domain = (
                self._prepare_failure_domain or "native_paint"
            )
            self._prepare_failure_reason = (
                self._prepare_failure_reason or "native_prepare_failed"
            )
            logger.debug(
                "[SPOTIFY_VIS] Visualizer native preparation failed",
                exc_info=True,
            )
            prepared = False
        finally:
            if native_started:
                try:
                    painter.endNativePainting()
                except Exception:
                    self._prepare_failure_domain = "native_paint"
                    self._prepare_failure_reason = "native_prepare_end_failed"
                    logger.debug(
                        "[SPOTIFY_VIS] Visualizer native preparation teardown failed",
                        exc_info=True,
                    )
                    prepared = False
        if prepared:
            self._prepare_retry_not_before_ts = 0.0
            self._prepare_retry_delay_s = 0.0
            return True
        delay_s = (
            0.10
            if self._prepare_retry_delay_s <= 0.0
            else min(2.0, self._prepare_retry_delay_s * 2.0)
        )
        self._prepare_retry_delay_s = delay_s
        self._prepare_retry_not_before_ts = now + delay_s
        return False

    def _record_render_failure(self, reason: str) -> None:
        self._render_failure_count += 1
        self._perf_render_failure_window += 1
        if self._has_presentable_frame():
            self._perf_retained_last_good_window += 1
        now = time.monotonic()
        signature = (reason, self._renderer._vis_mode, self._geometry.size())
        if signature == self._last_failure_signature and now - self._render_failure_log_ts < 10.0:
            return
        self._last_failure_signature = signature
        self._render_failure_log_ts = now
        logger.error(
            "[SPOTIFY_VIS][COMPOSITOR] Visualizer render failed "
            "reason=%s mode=%s rect=%s retained_last_good=%s failures=%d",
            reason,
            self._renderer._vis_mode,
            self._geometry,
            self._has_presentable_frame(),
            self._render_failure_count,
        )

    def _has_presentable_frame(self) -> bool:
        return bool(
            (self._has_last_good_frame and self._front is not None)
            or self._retained_front is not None
        )

    def _presentable_front_slot(self) -> Optional[_FramebufferSlot]:
        if self._has_last_good_frame and self._front is not None:
            return self._front
        return self._retained_front

    def _release_retained_front(self) -> None:
        retained = self._retained_front
        self._retained_front = None
        self._release_framebuffer_slot(retained, context_valid=True)

    def _render_to_back_buffer(self) -> tuple[bool, bool]:
        if self._back is None:
            return self._has_presentable_frame(), True
        generation = int(getattr(self._renderer, "_state_generation", 0) or 0)
        if generation == self._last_render_attempt_generation:
            if self._has_presentable_frame():
                self._texture_reuse_count += 1
                self._perf_texture_reuse_window += 1
            return self._has_presentable_frame(), False
        self._last_render_attempt_generation = generation
        self._fbo_render_count += 1
        self._perf_fbo_render_window += 1
        width_px = self._buffer_size_px.width()
        height_px = self._buffer_size_px.height()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._back.framebuffer)
        gl.glViewport(0, 0, width_px, height_px)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glColorMask(True, True, True, True)
        # The renderer owns both the color clear and any stencil clear needed
        # by the rounded-card mask. Do not clear either attachment twice.
        try:
            rendered = self._renderer.render_current_framebuffer(self.rect())
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Compositor visualizer mode render raised",
                exc_info=True,
            )
            return self._has_presentable_frame(), True
        published = bool(
            rendered or self._renderer.is_intentionally_transparent_frame()
        )
        if published:
            self._front, self._back = self._back, self._front
            self._has_last_good_frame = True
            self._last_good_frame_ts = time.monotonic()
            self._last_rendered_state_generation = generation
            self._release_retained_front()
            return True, False
        return self._has_presentable_frame(), True

    def _composite_front_buffer(self) -> bool:
        slot = self._presentable_front_slot()
        if slot is None:
            return False
        comp_width = max(1, self._compositor.width())
        comp_height = max(1, self._compositor.height())
        rect = self._geometry
        left = -1.0 + (2.0 * rect.left() / comp_width)
        right = -1.0 + (2.0 * (rect.left() + rect.width()) / comp_width)
        top = 1.0 - (2.0 * rect.top() / comp_height)
        bottom = 1.0 - (2.0 * (rect.top() + rect.height()) / comp_height)

        default_fbo = int(self._compositor.defaultFramebufferObject())
        dpr = max(1.0, min(4.0, float(self.devicePixelRatioF())))
        viewport_width = max(1, int(round(comp_width * dpr)))
        viewport_height = max(1, int(round(comp_height * dpr)))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, default_fbo)
        gl.glViewport(0, 0, viewport_width, viewport_height)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glDisable(gl.GL_STENCIL_TEST)
        gl.glStencilMask(0x00)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquation(gl.GL_FUNC_ADD)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glUseProgram(self._composite_program)
        gl.glUniform4f(self._composite_target_loc, left, bottom, right, top)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, slot.texture)
        gl.glUniform1i(self._composite_sampler_loc, 0)
        gl.glBindVertexArray(self._renderer._gl_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glUseProgram(0)
        gl.glDisable(gl.GL_BLEND)
        return True

    def paint(self, painter: QPainter) -> bool:
        if self._retired or not self.isVisible():
            return False
        if not bool(getattr(self._renderer, "_enabled", False)):
            return False
        if self._geometry.width() <= 0 or self._geometry.height() <= 0:
            return False

        visualizer = getattr(self.parent(), "spotify_visualizer_widget", None)
        if visualizer is None or not bool(
            getattr(visualizer, "_compositor_visualizer_active", False)
        ):
            return False
        try:
            if not visualizer.isVisible():
                return False
        except Exception:
            return False

        try:
            prepared = self._prepare_inside_painter(painter)
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Compositor visualizer preparation raised",
                exc_info=True,
            )
            prepared = False
        if not prepared:
            if bool(getattr(self, "_prepare_attempted_this_paint", True)):
                self._record_render_failure("prepare")
            if (
                not self._has_presentable_frame()
                or not self._composite_program
                or self._prepare_failure_domain == "native_paint"
            ):
                return False

        # A resize/DPR allocation failure keeps and scales the prior complete
        # frame instead of revealing a card with abruptly missing content.
        paint_compositor_card(visualizer, painter, self._geometry)

        painter.beginNativePainting()
        try:
            if prepared:
                frame_available, render_failed = self._render_to_back_buffer()
                if render_failed:
                    self._record_render_failure("mode_render")
            else:
                frame_available = self._has_presentable_frame()
            composited = False
            if frame_available:
                try:
                    composited = bool(self._composite_front_buffer())
                except Exception:
                    self._record_render_failure("texture_composite")
                    logger.debug(
                        "[SPOTIFY_VIS] Compositor visualizer texture blend raised",
                        exc_info=True,
                    )
            self._paint_count += 1
            return composited
        finally:
            try:
                gl.glBindFramebuffer(
                    gl.GL_FRAMEBUFFER,
                    int(self._compositor.defaultFramebufferObject()),
                )
                dpr = max(1.0, min(4.0, float(self.devicePixelRatioF())))
                gl.glViewport(
                    0,
                    0,
                    max(1, int(round(self._compositor.width() * dpr))),
                    max(1, int(round(self._compositor.height() * dpr))),
                )
                gl.glDisable(gl.GL_SCISSOR_TEST)
                gl.glDisable(gl.GL_STENCIL_TEST)
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glDisable(gl.GL_CULL_FACE)
                gl.glDisable(gl.GL_BLEND)
                gl.glColorMask(True, True, True, True)
                gl.glStencilMask(0x00)
                gl.glBindVertexArray(0)
                gl.glUseProgram(0)
            finally:
                painter.endNativePainting()

    # ------------------------------------------------------------------
    # Explicit edit-mode snapshot
    # ------------------------------------------------------------------

    def _read_front_buffer_image(self) -> QImage:
        slot = self._presentable_front_slot()
        if slot is None:
            return QImage()
        acquired = False
        try:
            acquired = self._acquire_context()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, slot.framebuffer)
            width_px = slot.width_px
            height_px = slot.height_px
            raw = gl.glReadPixels(
                0,
                0,
                width_px,
                height_px,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
            )
            image = QImage(
                bytes(raw),
                width_px,
                height_px,
                width_px * 4,
                QImage.Format.Format_RGBA8888,
            ).copy()
            image = image.mirrored(False, True)
            image.setDevicePixelRatio(slot.dpr)
            return image
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to read compositor visualizer edit snapshot",
                exc_info=True,
            )
            return QImage()
        finally:
            try:
                gl.glBindFramebuffer(
                    gl.GL_FRAMEBUFFER,
                    int(self._compositor.defaultFramebufferObject()),
                )
            except Exception:
                pass
            self._release_context(acquired)

    def grabFramebuffer(self) -> QImage:
        return self._read_front_buffer_image()

    def grab_composited_snapshot(self) -> QImage:
        visualizer = getattr(self.parent(), "spotify_visualizer_widget", None)
        if visualizer is None or self._geometry.width() <= 0 or self._geometry.height() <= 0:
            return QImage()
        dpr = max(1.0, min(4.0, float(self.devicePixelRatioF())))
        image = QImage(
            max(1, int(round(self._geometry.width() * dpr))),
            max(1, int(round(self._geometry.height() * dpr))),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.setDevicePixelRatio(dpr)
        image.fill(0)
        painter = QPainter(image)
        try:
            paint_compositor_card(
                visualizer,
                painter,
                QRect(0, 0, self._geometry.width(), self._geometry.height()),
            )
            bars = self._read_front_buffer_image()
            if not bars.isNull():
                painter.drawImage(
                    QRect(0, 0, self._geometry.width(), self._geometry.height()),
                    bars,
                )
        finally:
            painter.end()
        self._last_snapshot = image
        return image

    def describe_state(self) -> dict[str, Any]:
        return {
            "kind": "compositor",
            "visible": self.isVisible(),
            "geometry": QRect(self._geometry),
            "gl_ready": self._renderer.is_gl_ready(),
            "has_last_good_frame": self._has_last_good_frame,
            "has_retained_resize_frame": self._retained_front is not None,
            "buffer_size_px": QSize(self._buffer_size_px),
            "buffer_dpr": self._buffer_dpr,
            "paint_count": self._paint_count,
            "fbo_resize_count": self._fbo_resize_count,
            "fbo_render_count": self._fbo_render_count,
            "texture_reuse_count": self._texture_reuse_count,
            "last_rendered_state_generation": self._last_rendered_state_generation,
            "render_failures": self._render_failure_count,
            "prepare_failure_domain": self._prepare_failure_domain,
            "prepare_failure_reason": self._prepare_failure_reason,
            "perf_enabled": is_perf_metrics_enabled(),
        }

    def take_perf_window_counters(self) -> tuple[int, int, int, int, int]:
        counters = (
            int(self._perf_fbo_resize_window),
            int(self._perf_render_failure_window),
            int(self._perf_retained_last_good_window),
            int(self._perf_fbo_render_window),
            int(self._perf_texture_reuse_window),
        )
        self._perf_fbo_resize_window = 0
        self._perf_render_failure_window = 0
        self._perf_retained_last_good_window = 0
        self._perf_fbo_render_window = 0
        self._perf_texture_reuse_window = 0
        return counters
