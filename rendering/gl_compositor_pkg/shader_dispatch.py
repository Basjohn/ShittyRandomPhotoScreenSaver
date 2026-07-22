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


class _IdleBaseState:
    __slots__ = ()
    progress = 0.0


_IDLE_BASE_STATE = _IdleBaseState()


def _record_shader_path_failure(comp: "GLCompositorWidget", name: str, reason: str) -> None:
    """Store the most recent active shader failure for the paint fallback log."""
    try:
        comp._last_shader_path_failure = f"{name}:{reason}"
        comp._shader_path_failure_streak = int(
            getattr(comp, "_shader_path_failure_streak", 0) or 0
        ) + 1
    except Exception:
        pass


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


def prepare_pair_textures(
    comp: "GLCompositorWidget",
    old_pixmap: QPixmap,
    new_pixmap: QPixmap,
    *,
    old_payload=None,
    new_payload=None,
) -> bool:
    """Prepare texture pair via texture manager."""
    if comp._gl_pipeline is None:
        return False
    try:
        if old_payload is not None or new_payload is not None:
            prepared = bool(
                comp._texture_manager.prepare_transition_textures(
                    old_pixmap,
                    new_pixmap,
                    old_payload=old_payload,
                    new_payload=new_payload,
                )
            )
        else:
            prepared = bool(
                comp._texture_manager.prepare_transition_textures(old_pixmap, new_pixmap)
            )
        if prepared:
            comp._texture_prep_exception_logged = False
        return prepared
    except Exception:
        if not bool(getattr(comp, "_texture_prep_exception_logged", False)):
            logger.debug(
                "[GL SHADER] Failed to upload transition textures; retaining retry authority",
                exc_info=True,
            )
            comp._texture_prep_exception_logged = True
        release_transition_textures(comp)
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
    return prepare_pair_textures(
        comp,
        state.old_pixmap,
        state.new_pixmap,
        old_payload=getattr(state, "old_upload_payload", None),
        new_payload=getattr(state, "new_upload_payload", None),
    )


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


def paint_idle_base_shader(comp: "GLCompositorWidget") -> bool:
    """Draw the resident base image with one fullscreen GL quad.

    This path is deliberately cache-only. A first image that has not completed
    hidden GL warmup still uses the established QPainter presentation rather
    than performing conversion or texture upload inside a visible paint.
    """

    if gl is None or getattr(comp, "_gl_disabled_for_session", False):
        return False
    pipeline = getattr(comp, "_gl_pipeline", None)
    manager = getattr(comp, "_texture_manager", None)
    pixmap = getattr(comp, "_base_pixmap", None)
    if (
        pipeline is None
        or not getattr(pipeline, "initialized", False)
        or not getattr(pipeline, "crossfade_program", 0)
        or not getattr(pipeline, "quad_vao", 0)
        or manager is None
        or pixmap is None
        or pixmap.isNull()
    ):
        return False

    texture_id = manager.get_committed_texture()
    if texture_id <= 0:
        return False

    viewport = get_viewport_size(comp)
    source_width = max(1, int(pixmap.width()))
    source_height = max(1, int(pixmap.height()))
    source_aspect = source_width / float(source_height)
    viewport_aspect = viewport[0] / float(max(1, viewport[1]))
    if abs(source_aspect - viewport_aspect) > max(0.0005, viewport_aspect * 0.001):
        # Crossfade samples the whole texture. Preserve QPainter's aspect-fill
        # crop authority for an unusual non-display-ready base image.
        return False

    try:
        from rendering.gl_programs.program_cache import GLProgramCache, get_program_cache

        helper = get_program_cache().get_program_instance(GLProgramCache.CROSSFADE)
        helper.render(
            program=int(pipeline.crossfade_program),
            uniforms=pipeline.crossfade_uniforms,
            viewport=viewport,
            old_tex=texture_id,
            new_tex=texture_id,
            state=_IDLE_BASE_STATE,
            quad_vao=int(pipeline.quad_vao),
        )
        return True
    except Exception:
        logger.debug("[GL COMPOSITOR] Idle base shader paint failed", exc_info=True)
        return False


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


def paint_qpainter_overlays_gl(comp: "GLCompositorWidget") -> None:
    """Paint the complete QPainter scene overlay in one post-shader session.

    Dimming, the Spotify visualizer card/layer, and the debug HUD retain their
    established order without opening separate painter/native-state cycles.
    """
    debug_image = None
    if is_perf_metrics_enabled():
        from rendering.gl_compositor_pkg.overlays import render_debug_overlay_image

        debug_image = render_debug_overlay_image(comp)

    try:
        dimming_opacity = float(getattr(comp, "_dimming_opacity", 0.0) or 0.0)
    except (TypeError, ValueError):
        dimming_opacity = 0.0
    has_dimming = bool(
        getattr(comp, "_dimming_enabled", False) and dimming_opacity > 0.0
    )
    visualizer_layer = getattr(comp, "_spotify_visualizer_layer", None)
    has_visualizer = visualizer_layer is not None
    if has_visualizer:
        should_paint = getattr(visualizer_layer, "should_paint_scene", None)
        if callable(should_paint):
            try:
                has_visualizer = bool(should_paint())
            except Exception:
                # Preserve the established paint path if diagnostics cannot
                # prove that the layer is inactive.
                has_visualizer = True
    if not has_dimming and not has_visualizer and debug_image is None:
        return

    if has_visualizer and not has_dimming and debug_image is None:
        native_paint = getattr(visualizer_layer, "paint_native", None)
        if callable(native_paint):
            try:
                if bool(native_paint()):
                    comp._native_visualizer_fallback_logged = False
                    comp._native_visualizer_partial_logged = False
                    return
            except Exception:
                logger.error(
                    "[SPOTIFY_VIS][COMPOSITOR] Native visualizer dispatch raised; "
                    "retaining QPainter path",
                    exc_info=True,
                )
            fallback_safe = getattr(
                visualizer_layer,
                "native_fallback_is_safe",
                None,
            )
            if callable(fallback_safe) and not bool(fallback_safe()):
                if not bool(
                    getattr(comp, "_native_visualizer_partial_logged", False)
                ):
                    logger.error(
                        "[SPOTIFY_VIS][COMPOSITOR] Native visualizer frame was "
                        "partially presented; suppressing double-blend QPainter fallback"
                    )
                    comp._native_visualizer_partial_logged = True
                return
            if not bool(
                getattr(comp, "_native_visualizer_fallback_logged", False)
            ):
                logger.error(
                    "[SPOTIFY_VIS][COMPOSITOR] Native visualizer dispatch was not "
                    "presentable; retaining QPainter path"
                )
                comp._native_visualizer_fallback_logged = True

    gl.glUseProgram(0)

    painter = QPainter(comp)
    try:
        if has_dimming:
            comp._paint_dimming(painter)
        if has_visualizer:
            from rendering.gl_compositor_pkg.overlays import paint_visualizer_scene

            paint_visualizer_scene(comp, painter)
        if debug_image is not None:
            painter.drawImage(0, 0, debug_image)
    finally:
        painter.end()


def try_shader_path(comp: "GLCompositorWidget", name: str, state, can_use_fn, paint_fn, target, prep_fn=None) -> bool:
    """Try to render a transition via shader path. Returns True if successful."""
    if state is None:
        return False
    if not can_use_fn():
        _record_shader_path_failure(comp, name, "capability_unavailable")
        return False
    try:
        if prep_fn is not None and not prep_fn():
            _record_shader_path_failure(comp, name, "texture_prep_failed")
            return False
        paint_fn(target)
        paint_qpainter_overlays_gl(comp)
        try:
            comp._last_shader_path_failure = ""
            comp._shader_path_failure_streak = 0
        except Exception:
            pass
        return True
    except Exception as exc:
        _record_shader_path_failure(comp, name, f"exception:{type(exc).__name__}")
        streak = int(getattr(comp, "_shader_path_failure_streak", 1) or 1)
        if streak == 1 or (streak & (streak - 1)) == 0:
            logger.warning(
                "[GL SHADER][RECOVERY] Shader %s paint failed; retaining committed "
                "frame and retrying on the compositor streak=%d error=%s",
                name,
                streak,
                type(exc).__name__,
                exc_info=True,
            )
        return False
