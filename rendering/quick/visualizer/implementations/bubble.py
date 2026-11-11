"""Qt Quick Bubble renderer consuming one immutable authored snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from OpenGL import GL as gl

from core.performance.frame_trace import FrameTraceEvent
from core.gradient_geometry import project_linear_gradient
from core.settings.bubble_gradient_semantics import (
    project_bubble_gradient,
    get_bubble_specular_shader_vector,
)
from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.bubble_viewport_profile import (
    BUBBLE_RENDER_CAPACITY,
    bubble_stroke_extra_half_px,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerRenderSnapshot,
)
from widgets.spotify_visualizer.shaders import load_fragment_shader
from widgets.spotify_visualizer.bubble_ambient_geometry import ambient_sprite_scale

from rendering.quick import gl_query
from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QUICK_VISUALIZER_VERTEX_SOURCE,
    QuickVisualizerRenderFrame,
)


_MAX_BUBBLES = BUBBLE_RENDER_CAPACITY
_BUBBLE_POS_SIZE = _MAX_BUBBLES * 4
_BUBBLE_EXTRA_SIZE = _MAX_BUBBLES * 4
_BUBBLE_TRAIL_SIZE = _MAX_BUBBLES * 3 * 3


def _copy_uniform_float_buffer(
    buffer: np.ndarray,
    source: Sequence[object],
    *,
    active_size: int,
) -> np.ndarray:
    """Copy immutable Bubble payload values into one persistent float32 buffer.

    PyOpenGL recursively converts Python tuple/list inputs in ``arrays.lists`` on
    every uniform upload.  The old Bubble compositor already avoids that hot-path
    converter with persistent NumPy transport buffers; Quick keeps immutable tuple
    snapshots as its ownership contract and performs the same transport-only copy
    here on the render thread.
    """
    active = max(0, min(int(active_size), int(buffer.size)))
    if len(source) < active:
        raise ValueError("Bubble uniform payload is shorter than its active size")
    if active:
        # Quick payload tuples are already exact-length for the active Bubble count,
        # so avoid slicing/allocating another tuple in the normal render path.
        if len(source) == active:
            buffer[:active] = source
        else:
            buffer[:active] = source[:active]
    return buffer



@dataclass(frozen=True, slots=True)
class QuickBubbleLayout:
    content_rect: tuple[float, float, float, float]
    aspect_ratio: float
    visual_scale: float
    # Content-height fractions of the canonical card's wake ring geometry (1 on the canonical card).
    trail_radial_scale: float
    viewport_stroke_extra_half_px: float
    specular_reference_aspect: float
    response_radius_scale: float
    effect_scale: float


@dataclass(frozen=True, slots=True)
class QuickBubblePayload:
    positions: tuple[float, ...]
    extras: tuple[float, ...]
    trails: tuple[float, ...]
    bubble_count: int
    big_class_bits: tuple[int, int, int, int] = (0, 0, 0, 0)
    ambient_points: tuple[float, ...] = ()
    ambient_occluders: tuple[float, ...] = ()
    protected: bool = False


def compute_quick_bubble_layout(
    *,
    local_content_rect: Sequence[object],
    visual_scale: float,
    viewport_extent: Sequence[object],
    baseline_viewport_size: Sequence[object],
    world_scale: float = 1.0,
) -> QuickBubbleLayout:
    """Project Bubble's canonical-card units onto this card.

    The simulation works in canonical-card units on every card shape and
    publishes radius in them (``BubbleWorld``). One radius unit therefore covers
    the canonical card's response height at the current uniform scale and inset,
    times the world's capacity zoom ``world_scale`` - never the current card's
    height or area. That keeps every shape's bubbles, wakes and outlines the
    canonical card's size at equal uniform scale.
    """
    if len(local_content_rect) != 4:
        raise ValueError("Bubble content geometry is incomplete")
    content = tuple(float(value) for value in local_content_rect)
    scale = float(visual_scale)
    zoom = float(world_scale)
    if len(viewport_extent) != 2 or len(baseline_viewport_size) != 2:
        raise ValueError("Bubble viewport geometry is incomplete")
    extent = tuple(float(value) for value in viewport_extent)
    baseline = tuple(float(value) for value in baseline_viewport_size)
    if min(content[2], content[3], scale, *extent, *baseline) <= 0.0:
        raise ValueError("Bubble content geometry must be positive")
    if not math.isfinite(zoom) or zoom <= 0.0:
        raise ValueError("Bubble world scale must be finite and positive")
    # The canonical card's content at this uniform scale and inset. Specular
    # mutation and ellipse orientation keep that card's aspect, so an edge
    # resize cannot stretch a bubble-local light. The shader uses a one-pixel
    # height floor in its aspect metric as well.
    excluded_width = max(0.0, extent[0] * scale - content[2])
    excluded_height = max(0.0, extent[1] * scale - content[3])
    reference_width = max(1e-6, baseline[0] * scale - excluded_width)
    reference_height = max(1.0, baseline[1] * scale - excluded_height)
    # On a canonical axis the reference is the content itself, exactly.
    canonical_width = content[2] if extent[0] == baseline[0] else reference_width
    canonical_height = content[3] if extent[1] == baseline[1] else reference_height
    # One radius unit: the canonical card's equal-area response height (the
    # operator's 2026-09-05 response contract on that card), times the zoom.
    response_height = math.sqrt(
        canonical_width * canonical_height / (baseline[0] / baseline[1])
    ) * zoom
    return QuickBubbleLayout(
        content_rect=content,  # type: ignore[arg-type]
        aspect_ratio=content[2] / content[3],
        visual_scale=scale,
        # Wake rings are authored in canonical content heights.
        trail_radial_scale=zoom * canonical_height / content[3],
        viewport_stroke_extra_half_px=bubble_stroke_extra_half_px(zoom),
        specular_reference_aspect=reference_width / reference_height,
        response_radius_scale=response_height / content[3],
        effect_scale=response_height / baseline[1],
    )


def resolve_quick_bubble_payload(
    snapshot: VisualizerRenderSnapshot,
) -> QuickBubblePayload:
    """Resolve Bubble geometry from the newest authored mode frame only.

    Protected Bubble edges carry consume-once event metadata across latest-state
    coalescing, but event consequences are already forward-carried by the
    continuously integrated simulation.  They must never replace newer geometry
    with an older full-frame payload at the retained Quick boundary.
    """

    mode_state = snapshot.logical.mode_state
    if not isinstance(mode_state, BubbleFrame):
        raise TypeError("Bubble payload resolver received another mode frame")
    bubble_count = min(_MAX_BUBBLES, mode_state.bubble_count)
    required = bubble_count * 4
    required_trails = bubble_count * 9
    positions, extras, trails = mode_state.positions, mode_state.extras, mode_state.trails
    if (
        len(positions) < required
        or len(extras) < required
        or (trails and len(trails) < required_trails)
    ):
        raise ValueError("Bubble immutable arrays do not match bubble_count")
    # BubbleFrame already freezes and validates finite float tuples at publication.
    # Retain those immutable objects instead of recasting every element every draw.
    # Only the bounded active prefix of an oversized frame needs a new tuple; the
    # native upload still copies into renderer-owned persistent float32 buffers.
    return QuickBubblePayload(
        positions=positions if len(positions) == required else positions[:required],
        extras=extras if len(extras) == required else extras[:required],
        trails=trails if len(trails) <= required_trails else trails[:required_trails],
        bubble_count=bubble_count,
        big_class_bits=mode_state.big_class_bits,
        ambient_points=mode_state.ambient_points,
        ambient_occluders=mode_state.ambient_occluders,
    )



class QuickBubbleRenderer:
    mode_id = "bubble"

    def __init__(self) -> None:
        self._program = 0
        self._ambient_renderer = None  # lazily allocated, never if both layers are disabled
        self._uniforms: dict[str, int] = {}
        self._last_content_rotation_quarters: int | None = None
        # Persistent render-thread transport. Immutable authored snapshots remain
        # tuples; only the OpenGL upload representation is mutable/reused.
        self._position_uniform_buffer = np.zeros(_BUBBLE_POS_SIZE, dtype=np.float32)
        self._extra_uniform_buffer = np.zeros(_BUBBLE_EXTRA_SIZE, dtype=np.float32)
        self._trail_uniform_buffer = np.zeros(_BUBBLE_TRAIL_SIZE, dtype=np.float32)
        self._layout_cache_key: tuple[object, ...] | None = None
        self._layout_cache: QuickBubbleLayout | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def _gradient_parameters(self, parameters, layout: QuickBubbleLayout):
        """Named recipes retain their vectors; custom nodes use the shared physical projection."""
        direction = str(parameter(parameters, "bubble_gradient_direction"))
        if direction == 'custom':
            return (*project_linear_gradient(parameter(parameters, 'bubble_gradient_endpoints'), layout.aspect_ratio), 0.)
        return project_bubble_gradient(direction)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        trace = frame.trace_context
        snapshot = frame.snapshot
        mode_state = snapshot.logical.mode_state
        if not isinstance(mode_state, BubbleFrame):
            raise TypeError("Bubble renderer received another mode frame")
        presentation = snapshot.presentation
        local_content_rect = frame.logical_content_rect
        layout_key = (
            local_content_rect,
            presentation.uniform_visual_scale,
            presentation.logical_viewport_extent,
            presentation.baseline_viewport_size,
            mode_state.world_scale,
        )
        if self._layout_cache_key != layout_key or self._layout_cache is None:
            self._layout_cache = compute_quick_bubble_layout(
                local_content_rect=local_content_rect,
                visual_scale=presentation.uniform_visual_scale,
                viewport_extent=presentation.logical_viewport_extent,
                baseline_viewport_size=presentation.baseline_viewport_size,
                world_scale=mode_state.world_scale,
            )
            self._layout_cache_key = layout_key
        layout = self._layout_cache
        payload = resolve_quick_bubble_payload(snapshot)
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_LAYOUT_PAYLOAD_READY)
        if not self._program:
            self._initialize()
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_PROGRAM_READY)

        parameters = mode_state.parameters
        uniforms = self._uniforms
        # Draw a small, content-local ambient texture BEFORE the Bubble draw.
        # The canonical Bubble shader then inserts it between the background
        # gradient and all existing wake, ghost and 110-body contributions.
        # No texture, framebuffer or extra GL calls on the opt-out path.
        ambient_texture = ambient_light = 0
        if payload.ambient_points:
            if self._ambient_renderer is None:
                # Loaded on this edge only: the opt-out path never imports the ambient GL module.
                from .bubble_ambient_gl import QuickBubbleAmbientPoints
                self._ambient_renderer = QuickBubbleAmbientPoints()
            ambient_texture, ambient_light = self._ambient_renderer.render_texture(
                layout.content_rect, presentation.dpr, payload.ambient_points,
                sprite_scale=ambient_sprite_scale(layout.effect_scale),
                glow_spread=float(parameter(parameters, "bubble_particle_glow_spread")),
                micro_color=rgba(parameter(parameters, "bubble_outline_color")),
                particle_color=rgba(parameter(parameters, "bubble_particle_color")),
                occluders=payload.ambient_occluders,
                response_radius_scale=layout.response_radius_scale,
            )
        elif self._ambient_renderer is not None:
            # Returning to an ordinary preset releases the opt-in GPU target
            # exactly once; the original Bubble path then remains allocation-free.
            self._ambient_renderer.release_resources()
            self._ambient_renderer = None
        gl.glUseProgram(self._program)
        gl.glUniform1i(uniforms["u_ambient_enabled"], int(bool(ambient_texture)))
        gl.glUniform1i(uniforms["u_ambient_light_enabled"], int(bool(ambient_light)))
        if ambient_texture:
            gl.glUniform1i(uniforms["u_ambient_texture"], 0)
        if ambient_light:
            gl.glUniform1i(uniforms["u_ambient_light"], 1)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        content_rotation_quarters = frame.content_rotation_quarters
        if content_rotation_quarters != self._last_content_rotation_quarters:
            gl.glUniform1i(
                uniforms["uContentRotationQuarters"],
                content_rotation_quarters,
            )
            self._last_content_rotation_quarters = content_rotation_quarters
        gl.glUniform2f(uniforms["u_resolution"], *frame.oriented_logical_size)
        gl.glUniform1f(uniforms["u_dpr"], presentation.dpr)
        gl.glUniform2f(uniforms["u_viewport_origin_px"], 0.0, 0.0)
        gl.glUniform1i(uniforms["u_quick_item_coords"], 1)
        gl.glUniform4f(uniforms["u_content_rect"], *layout.content_rect)
        gl.glUniform1f(uniforms["u_visual_scale"], layout.effect_scale)
        gl.glUniform1f(uniforms["u_response_radius_scale"], layout.response_radius_scale)
        gl.glUniform1f(
            uniforms["u_specular_reference_aspect"], layout.specular_reference_aspect,
        )
        gl.glUniform1f(uniforms["u_border_width"], presentation.border_width)
        gl.glUniform1f(uniforms["u_fade"], presentation.content_fade)
        gl.glUniform1i(uniforms["u_bubble_count"], payload.bubble_count)
        # Four uint32 words (16 bytes), not a per-hero uniform array or
        # additional pass. Uses true is_big classes from the same snapshot.
        gl.glUniform4ui(uniforms["u_big_class_bits"], *payload.big_class_bits)
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_COMMON_UNIFORMS_READY)
        if payload.bubble_count:
            position_buffer = _copy_uniform_float_buffer(
                self._position_uniform_buffer,
                payload.positions,
                active_size=payload.bubble_count * 4,
            )
            extra_buffer = _copy_uniform_float_buffer(
                self._extra_uniform_buffer,
                payload.extras,
                active_size=payload.bubble_count * 4,
            )
            gl.glUniform4fv(
                uniforms["u_bubbles_pos"],
                payload.bubble_count,
                position_buffer,
            )
            gl.glUniform4fv(
                uniforms["u_bubbles_extra"],
                payload.bubble_count,
                extra_buffer,
            )

        trail_strength = max(
            0.0,
            min(
                1.5,
                float(parameter(parameters, "bubble_trail_strength")),
            ),
        )
        tail_opacity = max(
            0.0,
            min(
                0.85,
                float(parameter(parameters, "bubble_tail_opacity")),
            ),
        )
        if payload.trails and payload.bubble_count:
            trail_buffer = _copy_uniform_float_buffer(
                self._trail_uniform_buffer,
                payload.trails,
                active_size=payload.bubble_count * 9,
            )
            gl.glUniform3fv(
                uniforms["u_bubbles_trail"],
                payload.bubble_count * 3,
                trail_buffer,
            )
        else:
            trail_strength = 0.0
            tail_opacity = 0.0
        gl.glUniform1f(uniforms["u_trail_strength"], trail_strength)
        gl.glUniform1f(uniforms["u_tail_opacity"], tail_opacity)
        gl.glUniform1f(uniforms["u_trail_radial_scale"], layout.trail_radial_scale)
        gl.glUniform1f(
            uniforms["u_viewport_stroke_extra_half_px"],
            layout.viewport_stroke_extra_half_px,
        )
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_REACTIVE_UNIFORMS_READY)

        specular_direction = get_bubble_specular_shader_vector(
            str(parameter(parameters, "bubble_specular_direction"))
        )
        gl.glUniform2f(uniforms["u_specular_dir"], *specular_direction)
        gl.glUniform4f(uniforms["u_gradient"], *self._gradient_parameters(parameters, layout))

        color_parameters = (
            ("u_outline_color", "bubble_outline_color"),
            ("u_specular_color", "bubble_specular_color"),
            ("u_gradient_light", "bubble_gradient_light"),
            ("u_gradient_dark", "bubble_gradient_dark"),
            ("u_pop_color", "bubble_pop_color"),
        )
        for uniform_name, parameter_name in color_parameters:
            gl.glUniform4f(
                uniforms[uniform_name],
                *rgba(parameter(parameters, parameter_name)),
            )

        ghost_alpha = 0.0
        if bool(parameter(parameters, "bubble_ghosting_enabled")):
            ghost_alpha = max(
                0.0,
                min(
                    1.0,
                    float(parameter(parameters, "bubble_ghost_alpha")),
                ),
            )
        gl.glUniform1f(uniforms["u_ghost_alpha"], ghost_alpha)
        ghost_decay = max(
            0.1,
            min(
                1.0,
                float(parameter(parameters, "bubble_ghost_decay")),
            ),
        )
        gl.glUniform1f(uniforms["u_ghost_decay"], ghost_decay)
        hue = 0.0
        if bool(parameter(parameters, "rainbow_enabled")):
            speed = max(
                0.01,
                min(
                    5.0,
                    float(parameter(parameters, "rainbow_speed")),
                ),
            )
            hue = safe_hue(mode_state.simulation_timestamp * speed * 0.1)
        gl.glUniform1f(uniforms["u_rainbow_hue_offset"], hue)
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_STYLE_UNIFORMS_READY)
        gl.glBindVertexArray(frame.quad_vao)
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_VAO_READY)
        if ambient_texture:
            prior_active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            prior_bound = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
            prior_light = 0
            try:
                gl.glBindTexture(gl.GL_TEXTURE_2D, ambient_texture)
                if ambient_light:
                    # Glowing particles' linear light on unit 1, for this draw only.
                    gl.glActiveTexture(gl.GL_TEXTURE1)
                    prior_light = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, ambient_light)
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            finally:
                if ambient_light:
                    gl.glActiveTexture(gl.GL_TEXTURE1)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, prior_light)
                    gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, prior_bound)
                gl.glActiveTexture(prior_active)
        else:
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_DRAW_READY)

    def release_resources(self) -> None:
        if self._ambient_renderer is not None:
            self._ambient_renderer.release_resources()
            self._ambient_renderer = None
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._last_content_rotation_quarters = None
        self._uniforms.clear()

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("bubble")
        if fragment_source is None:
            raise RuntimeError("canonical Bubble shader is unavailable")
        program = compile_program(
            QUICK_VISUALIZER_VERTEX_SOURCE,
            fragment_source,
            label="Quick Bubble",
        )
        self._program = program
        try:
            required = (
                "uMatrix",
                "uItemSize",
                "uContentRotationQuarters",
                "u_resolution",
                "u_dpr",
                "u_viewport_origin_px",
                "u_quick_item_coords",
                "u_content_rect",
                "u_visual_scale",
                "u_response_radius_scale",
                "u_specular_reference_aspect",
                "u_border_width",
                "u_fade",
                "u_bubble_count",
                "u_big_class_bits",
                "u_bubbles_pos",
                "u_bubbles_extra",
                "u_bubbles_trail",
                "u_trail_strength",
                "u_tail_opacity",
                "u_trail_radial_scale",
                "u_viewport_stroke_extra_half_px",
                "u_specular_dir",
                "u_gradient",
                "u_outline_color",
                "u_specular_color",
                "u_gradient_light",
                "u_gradient_dark",
                "u_pop_color",
                "u_rainbow_hue_offset",
                "u_ghost_alpha",
                "u_ghost_decay",
                "u_ambient_enabled",
                "u_ambient_texture",
                "u_ambient_light_enabled",
                "u_ambient_light",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Bubble uniforms are incomplete: "
                    + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_visualizer_renderer() -> QuickBubbleRenderer:
    return QuickBubbleRenderer()


__all__ = [
    "QuickBubbleLayout",
    "QuickBubblePayload",
    "QuickBubbleRenderer",
    "compute_quick_bubble_layout",
    "create_visualizer_renderer",
    "resolve_quick_bubble_payload",
]
