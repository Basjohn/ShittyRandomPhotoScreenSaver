"""GLTransitionRenderer - Centralized transition rendering for GL compositor.

Handles shader-based transition rendering (GL-only, no QPainter fallbacks).
Provides clean boundary between base image rendering and overlay visuals.
"""

from __future__ import annotations

import math
import time
import logging
from typing import TYPE_CHECKING, Optional, Callable, Tuple, Any

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QPixmap

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None

from transitions.base_transition import SlideDirection

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget, _GLPipelineState
    from rendering.gl_programs.texture_manager import GLTextureManager
    from rendering.gl_profiler import TransitionProfiler

logger = logging.getLogger(__name__)


def _blockspin_spin_from_progress(p: float) -> float:
    """Convert linear progress to spin amount with ease-in-out."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    # Ease-in-out cubic
    if p < 0.5:
        return 4.0 * p * p * p
    return 1.0 - pow(-2.0 * p + 2.0, 3) / 2.0


class GLTransitionRenderer:
    """Renders transition effects via shader or QPainter paths.
    
    Centralizes all transition rendering logic, providing:
    - Shader path dispatch for Group A transitions
    - QPainter fallback for Group B transitions
    - Clean interface for overlay rendering (dimming, visualizer, debug)
    
    Thread Safety:
    - All methods must be called from UI thread with valid GL context
    """
    
    def __init__(
        self,
        compositor: "GLCompositorWidget",
        get_pipeline: Callable[[], Optional["_GLPipelineState"]],
        get_texture_manager: Callable[[], "GLTextureManager"],
        get_profiler: Callable[[], "TransitionProfiler"],
        get_viewport_size: Callable[[], Tuple[int, int]],
        get_render_progress: Callable[[float], float],
    ):
        """Initialize renderer with compositor callbacks.
        
        Args:
            compositor: Parent GLCompositorWidget for state access
            get_pipeline: Callback to get current pipeline state
            get_texture_manager: Callback to get texture manager
            get_profiler: Callback to get transition profiler
            get_viewport_size: Callback to get viewport dimensions
            get_render_progress: Callback to get interpolated progress
        """
        self._compositor = compositor
        self._get_pipeline = get_pipeline
        self._get_texture_manager = get_texture_manager
        self._get_profiler = get_profiler
        self._get_viewport_size = get_viewport_size
        self._get_render_progress = get_render_progress
        
        # Program helper getters (set by compositor after init)
        self._program_getters: dict = {}
    
    def set_program_getters(self, getters: dict) -> None:
        """Set program helper getter functions.
        
        Args:
            getters: Dict mapping program names to getter functions
        """
        self._program_getters = getters
    
    # -------------------------------------------------------------------------
    # Shader Path Rendering
    # -------------------------------------------------------------------------
    
    def render_simple_shader(
        self,
        can_use_fn: Callable[[], bool],
        state: Any,
        prep_fn: Callable[[], bool],
        program_attr: str,
        uniforms_attr: str,
        helper_name: str,
    ) -> None:
        """Generic shader render for simple fullscreen quad transitions."""
        pipeline = self._get_pipeline()
        if not can_use_fn() or pipeline is None or state is None:
            return
        if not state.old_pixmap or state.old_pixmap.isNull() or not state.new_pixmap or state.new_pixmap.isNull():
            return
        if not prep_fn():
            return
        
        vp_w, vp_h = self._get_viewport_size()
        tex_mgr = self._get_texture_manager()
        helper_fn = self._program_getters.get(helper_name)
        if helper_fn is None:
            return
        
        helper_fn().render(
            program=getattr(pipeline, program_attr),
            uniforms=getattr(pipeline, uniforms_attr),
            viewport=(vp_w, vp_h),
            old_tex=tex_mgr.old_tex_id,
            new_tex=tex_mgr.new_tex_id,
            state=state,
            quad_vao=pipeline.quad_vao,
        )
    
    def render_blockspin_shader(self, target: QRect, state: Any) -> None:
        """Render BlockSpin transition using 3D card-flip shader.

        Rendering contract: the slab is rendered over a black void.
        """
        pipeline = self._get_pipeline()
        if gl is None or pipeline is None or state is None:
            return
        if not state.old_pixmap or state.old_pixmap.isNull() or not state.new_pixmap or state.new_pixmap.isNull():
            return
        
        vp_w, vp_h = self._get_viewport_size()
        tex_mgr = self._get_texture_manager()
        
        w = max(1, target.width())
        h = max(1, target.height())
        base_p = state.progress
        aspect = w / h
        
        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)

        # Ensure the depth buffer is actually cleared before rendering the slab.
        try:
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        except Exception as e:
            logger.debug("[GL TRANSITION] Exception suppressed: %s", e)
        
        gl.glUseProgram(pipeline.basic_program)
        try:
            if pipeline.u_aspect_loc != -1:
                gl.glUniform1f(pipeline.u_aspect_loc, float(aspect))
            
            axis_mode = 0
            if state.direction in (SlideDirection.UP, SlideDirection.DOWN):
                axis_mode = 1
            elif state.direction == SlideDirection.DIAG_TL_BR:
                axis_mode = 2
            elif state.direction == SlideDirection.DIAG_TR_BL:
                axis_mode = 3
            if pipeline.u_axis_mode_loc != -1:
                gl.glUniform1i(pipeline.u_axis_mode_loc, int(axis_mode))
            
            spin_dir = 1.0
            if state.direction in (SlideDirection.RIGHT, SlideDirection.DOWN):
                spin_dir = -1.0
            elif state.direction == SlideDirection.DIAG_TR_BL:
                spin_dir = -1.0
            if pipeline.u_spec_dir_loc != -1:
                gl.glUniform1f(pipeline.u_spec_dir_loc, float(spin_dir))
            
            # Bind textures
            if pipeline.u_old_tex_loc != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, tex_mgr.old_tex_id)
                gl.glUniform1i(pipeline.u_old_tex_loc, 0)
            if pipeline.u_new_tex_loc != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, tex_mgr.new_tex_id)
                gl.glUniform1i(pipeline.u_new_tex_loc, 1)
            
            spin = _blockspin_spin_from_progress(base_p)
            angle = math.pi * spin * spin_dir
            
            if pipeline.u_angle_loc != -1:
                gl.glUniform1f(pipeline.u_angle_loc, angle)
            if pipeline.u_block_rect_loc != -1:
                gl.glUniform4f(pipeline.u_block_rect_loc, -1.0, -1.0, 1.0, 1.0)
            if pipeline.u_block_uv_rect_loc != -1:
                gl.glUniform4f(pipeline.u_block_uv_rect_loc, 0.0, 0.0, 1.0, 1.0)
            
            box_vao = getattr(pipeline, "box_vao", 0)
            box_count = getattr(pipeline, "box_vertex_count", 0)
            if box_vao and box_count > 0:
                gl.glBindVertexArray(box_vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, box_count)
                gl.glBindVertexArray(0)
            else:
                gl.glBindVertexArray(pipeline.quad_vao)
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_FALSE)
    
    def render_slide_shader(self, target: QRect, state: Any) -> None:
        """Render Slide transition with pre-computed coordinates."""
        pipeline = self._get_pipeline()
        if pipeline is None or state is None:
            return
        if not state.old_pixmap or state.old_pixmap.isNull() or not state.new_pixmap or state.new_pixmap.isNull():
            return
        
        profiler = self._get_profiler()
        profiler.tick_paint("slide")
        
        w = max(1, target.width())
        h = max(1, target.height())
        inv_w = 1.0 / w
        inv_h = 1.0 / h
        
        t = self._get_render_progress(state.progress)
        
        old_x = (state._old_start_x + state._old_delta_x * t) * inv_w
        old_y = (state._old_start_y + state._old_delta_y * t) * inv_h
        new_x = (state._new_start_x + state._new_delta_x * t) * inv_w
        new_y = (state._new_start_y + state._new_delta_y * t) * inv_h
        
        start_gpu = time.perf_counter()
        vp_w, vp_h = self._get_viewport_size()
        tex_mgr = self._get_texture_manager()
        
        slide_helper = self._program_getters.get("slide")
        if slide_helper is None:
            return
        
        slide_helper().render(
            program=pipeline.slide_program,
            uniforms=pipeline.slide_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=tex_mgr.old_tex_id,
            new_tex=tex_mgr.new_tex_id,
            state=state,
            quad_vao=pipeline.quad_vao,
            old_rect=(old_x, old_y, 1.0, 1.0),
            new_rect=(new_x, new_y, 1.0, 1.0),
        )
        
        try:
            gpu_ms = max(0.0, float((time.perf_counter() - start_gpu) * 1000.0))
            profiler.tick_gpu("slide", gpu_ms)
        except Exception as e:
            logger.debug("[GL TRANSITION] Exception suppressed: %s", e)
    
    def render_base_image(self, painter: QPainter, target: QRect, pixmap: Optional[QPixmap]) -> None:
        """Render base image when no transition is active."""
        if pixmap is not None and not pixmap.isNull():
            painter.setOpacity(1.0)
            painter.drawPixmap(target, pixmap)
        else:
            painter.fillRect(target, Qt.GlobalColor.black)
