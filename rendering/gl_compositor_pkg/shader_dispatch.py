"""Shader capability checks, texture preparation, and paint dispatch.

Extracted from gl_compositor.py to reduce monolith size.
All functions take the compositor widget (``comp``) as their first argument.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtGui import QPixmap, QPainter

from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget

try:
    from OpenGL import GL as gl  # type: ignore[import]
except Exception:
    gl = None

logger = get_logger(__name__)


# ======================================================================
# Shader capability checks
# ======================================================================

def can_use_blockspin_shader(comp: "GLCompositorWidget") -> bool:
    if comp._gl_disabled_for_session or gl is None:
        return False
    if comp._gl_pipeline is None or not comp._gl_pipeline.initialized:
        return False
    if comp._blockspin is None:
        return False
    return True


def can_use_simple_shader(comp: "GLCompositorWidget", state: object, program_id: int) -> bool:
    """Shared capability check for simple fullscreen quad shaders.

    Used by Ripple (raindrops), Warp Dissolve and Shooting Stars, which
    all draw a single quad over the full compositor surface.
    """
    if comp._gl_disabled_for_session or gl is None:
        return False
    if comp._gl_pipeline is None or not comp._gl_pipeline.initialized:
        return False
    if state is None:
        return False
    if not program_id:
        return False
    return True


def can_use_warp_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._warp, getattr(comp._gl_pipeline, "warp_program", 0))


def can_use_raindrops_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._raindrops, comp._gl_pipeline.raindrops_program)


def can_use_grid_shader(comp: "GLCompositorWidget", state, program_attr: str) -> bool:
    """Check if a grid-based shader (diffuse, blockflip, blinds) can be used."""
    if state is None:
        return False
    if getattr(state, "cols", 0) <= 0 or getattr(state, "rows", 0) <= 0:
        return False
    return can_use_simple_shader(comp, state, getattr(comp._gl_pipeline, program_attr, 0))


def can_use_diffuse_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_grid_shader(comp, comp._diffuse, "diffuse_program")


def can_use_blockflip_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_grid_shader(comp, comp._blockflip, "blockflip_program")


def can_use_peel_shader(comp: "GLCompositorWidget") -> bool:
    st = comp._peel
    if st is None or getattr(st, "strips", 0) <= 0:
        return False
    return can_use_simple_shader(comp, st, getattr(comp._gl_pipeline, "peel_program", 0))


def can_use_blinds_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_grid_shader(comp, comp._blinds, "blinds_program")


def can_use_crumble_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._crumble, getattr(comp._gl_pipeline, "crumble_program", 0))


def can_use_particle_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._particle, getattr(comp._gl_pipeline, "particle_program", 0))


def can_use_crossfade_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._crossfade, getattr(comp._gl_pipeline, "crossfade_program", 0))


def can_use_burn_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._burn, getattr(comp._gl_pipeline, "burn_program", 0))


def can_use_slide_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._slide, getattr(comp._gl_pipeline, "slide_program", 0))


def can_use_wipe_shader(comp: "GLCompositorWidget") -> bool:
    return can_use_simple_shader(comp, comp._wipe, getattr(comp._gl_pipeline, "wipe_program", 0))


# ======================================================================
# Texture preparation
# ======================================================================

def release_transition_textures(comp: "GLCompositorWidget") -> None:
    """Release current transition texture references via texture manager."""
    if comp._texture_manager is not None:
        comp._texture_manager.release_transition_textures()


def prepare_pair_textures(comp: "GLCompositorWidget", old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
    """Prepare texture pair via texture manager."""
    if comp._gl_pipeline is None:
        return False
    try:
        result = comp._texture_manager.prepare_transition_textures(old_pixmap, new_pixmap)
        if not result:
            comp._gl_disabled_for_session = True
            comp._use_shaders = False
        return result
    except Exception:
        logger.debug("[GL SHADER] Failed to upload transition textures", exc_info=True)
        release_transition_textures(comp)
        comp._gl_disabled_for_session = True
        comp._use_shaders = False
        return False


def prepare_transition_textures(comp: "GLCompositorWidget", can_use_fn, state) -> bool:
    """Generic texture preparation for any transition type."""
    if not can_use_fn():
        return False
    if comp._gl_pipeline is None:
        return False
    if comp._texture_manager is None:
        return False
    if comp._texture_manager.has_transition_textures():
        return True
    if state is None:
        return False
    return prepare_pair_textures(comp, state.old_pixmap, state.new_pixmap)


def prepare_blockspin_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_blockspin_shader(comp), comp._blockspin)

def prepare_warp_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_warp_shader(comp), comp._warp)

def prepare_raindrops_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_raindrops_shader(comp), comp._raindrops)

def prepare_diffuse_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_diffuse_shader(comp), comp._diffuse)

def prepare_blockflip_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_blockflip_shader(comp), comp._blockflip)

def prepare_peel_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_peel_shader(comp), comp._peel)

def prepare_blinds_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_blinds_shader(comp), comp._blinds)

def prepare_crumble_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_crumble_shader(comp), comp._crumble)

def prepare_particle_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_particle_shader(comp), comp._particle)

def prepare_crossfade_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_crossfade_shader(comp), comp._crossfade)

def prepare_burn_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_burn_shader(comp), comp._burn)

def prepare_slide_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_slide_shader(comp), comp._slide)

def prepare_wipe_textures(comp: "GLCompositorWidget") -> bool:
    return prepare_transition_textures(comp, lambda: can_use_wipe_shader(comp), comp._wipe)


# ======================================================================
# Shader compilation
# ======================================================================

def compile_shader(source: str, shader_type: int) -> int:
    """Compile a single GLSL shader and return its id."""
    if gl is None:
        raise RuntimeError("OpenGL context not available for shader compilation")

    shader = gl.glCreateShader(shader_type)
    gl.glShaderSource(shader, source)
    gl.glCompileShader(shader)
    status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
    if status != gl.GL_TRUE:
        log = gl.glGetShaderInfoLog(shader)
        logger.debug("[GL SHADER] Failed to compile shader: %r", log)
        gl.glDeleteShader(shader)
        raise RuntimeError(f"Failed to compile shader: {log!r}")
    return int(shader)


# ======================================================================
# Viewport
# ======================================================================

def get_viewport_size(comp: "GLCompositorWidget") -> tuple[int, int]:
    """Return the framebuffer viewport size in physical pixels.

    PERFORMANCE OPTIMIZED: Caches the result and only recalculates when
    widget size changes. This eliminates per-frame DPR lookups and float
    conversions in the hot render path.
    """
    current_size = (comp.width(), comp.height())

    if comp._cached_viewport is not None and comp._cached_widget_size == current_size:
        return comp._cached_viewport

    try:
        dpr = float(comp.devicePixelRatioF())
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        dpr = 1.0
    w = max(1, int(round(current_size[0] * dpr)))
    h = max(1, int(round(current_size[1] * dpr)))
    h = max(1, h + 1)

    comp._cached_viewport = (w, h)
    comp._cached_widget_size = current_size
    return comp._cached_viewport


# ======================================================================
# Paint shader dispatch
# ======================================================================

def paint_blockspin_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    """Render BlockSpin transition - delegates to GLTransitionRenderer."""
    if gl is None:
        return
    if not can_use_blockspin_shader(comp) or comp._gl_pipeline is None or comp._blockspin is None:
        return
    if not comp._blockspin.old_pixmap or comp._blockspin.old_pixmap.isNull() or not comp._blockspin.new_pixmap or comp._blockspin.new_pixmap.isNull():
        return
    if not prepare_blockspin_textures(comp):
        return
    comp._transition_renderer.render_blockspin_shader(target, comp._blockspin)


def render_simple_shader(
    comp: "GLCompositorWidget", can_use_fn, state, prep_fn,
    program_attr: str, uniforms_attr: str, helper_name: str
) -> None:
    """Generic shader render - delegates to GLTransitionRenderer."""
    comp._transition_renderer.render_simple_shader(
        can_use_fn, state, prep_fn, program_attr, uniforms_attr, helper_name
    )


def paint_peel_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_peel_shader(comp), comp._peel,
        lambda: prepare_peel_textures(comp),
        "peel_program", "peel_uniforms", "peel"
    )

def paint_crumble_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_crumble_shader(comp), comp._crumble,
        lambda: prepare_crumble_textures(comp),
        "crumble_program", "crumble_uniforms", "crumble"
    )

def paint_particle_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_particle_shader(comp), comp._particle,
        lambda: prepare_particle_textures(comp),
        "particle_program", "particle_uniforms", "particle"
    )

def paint_blinds_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_blinds_shader(comp), comp._blinds,
        lambda: prepare_blinds_textures(comp),
        "blinds_program", "blinds_uniforms", "blinds"
    )

def paint_wipe_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_wipe_shader(comp), comp._wipe,
        lambda: prepare_wipe_textures(comp),
        "wipe_program", "wipe_uniforms", "wipe"
    )

def paint_slide_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    """Render Slide transition - delegates to GLTransitionRenderer."""
    if not can_use_slide_shader(comp) or comp._gl_pipeline is None or comp._slide is None:
        return
    if not comp._slide.old_pixmap or comp._slide.old_pixmap.isNull() or not comp._slide.new_pixmap or comp._slide.new_pixmap.isNull():
        return
    if not prepare_slide_textures(comp):
        return
    comp._transition_renderer.render_slide_shader(target, comp._slide)

def paint_crossfade_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_crossfade_shader(comp), comp._crossfade,
        lambda: prepare_crossfade_textures(comp),
        "crossfade_program", "crossfade_uniforms", "crossfade"
    )

def paint_diffuse_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_diffuse_shader(comp), comp._diffuse,
        lambda: prepare_diffuse_textures(comp),
        "diffuse_program", "diffuse_uniforms", "diffuse"
    )

def paint_blockflip_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_blockflip_shader(comp), comp._blockflip,
        lambda: prepare_blockflip_textures(comp),
        "blockflip_program", "blockflip_uniforms", "blockflip"
    )

def paint_warp_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_warp_shader(comp), comp._warp,
        lambda: prepare_warp_textures(comp),
        "warp_program", "warp_uniforms", "warp"
    )

def paint_raindrops_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_raindrops_shader(comp), comp._raindrops,
        lambda: prepare_raindrops_textures(comp),
        "raindrops_program", "raindrops_uniforms", "raindrops"
    )

def paint_burn_shader(comp: "GLCompositorWidget", target: QRect) -> None:
    render_simple_shader(
        comp, lambda: can_use_burn_shader(comp), comp._burn,
        lambda: prepare_burn_textures(comp),
        "burn_program", "burn_uniforms", "burn"
    )


def paint_debug_overlay_gl(comp: "GLCompositorWidget") -> None:
    if not is_perf_metrics_enabled():
        return

    from rendering.gl_compositor_pkg.overlays import render_debug_overlay_image
    image = render_debug_overlay_image(comp)
    if image is None:
        return

    gl.glUseProgram(0)

    painter = QPainter(comp)
    try:
        painter.drawImage(0, 0, image)
    finally:
        painter.end()


def paint_spotify_visualizer_gl(comp: "GLCompositorWidget") -> None:
    if not comp._spotify_vis_enabled:
        return
    from rendering.gl_compositor_pkg.overlays import paint_spotify_visualizer
    painter = QPainter(comp)
    try:
        paint_spotify_visualizer(comp, painter)
    finally:
        painter.end()


def try_shader_path(comp: "GLCompositorWidget", name: str, state, can_use_fn, paint_fn, target, prep_fn=None) -> bool:
    """Try to render a transition via shader path. Returns True if successful."""
    if state is None or not can_use_fn():
        return False
    try:
        if prep_fn is not None and not prep_fn():
            return False
        paint_fn(target)
        from rendering.gl_compositor_pkg.overlays import paint_dimming_gl
        paint_dimming_gl(comp)
        paint_spotify_visualizer_gl(comp)
        if is_perf_metrics_enabled():
            paint_debug_overlay_gl(comp)
        return True
    except Exception:
        logger.debug("[GL SHADER] Shader %s path failed; disabling shader pipeline", name, exc_info=True)
        comp._gl_disabled_for_session = True
        comp._use_shaders = False
        return False
