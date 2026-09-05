"""Qt Quick Bubble renderer consuming one immutable authored snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from OpenGL import GL as gl

from core.settings.bubble_gradient_semantics import (
    get_bubble_gradient_shader_mode,
    get_bubble_gradient_shader_vector,
    get_bubble_specular_shader_vector,
)
from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.bubble_viewport_profile import (
    resolve_bubble_viewport_profile,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerRenderSnapshot,
)
from widgets.spotify_visualizer.shaders import load_fragment_shader

from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QUICK_VISUALIZER_VERTEX_SOURCE,
    QuickVisualizerRenderFrame,
)


_MAX_BUBBLES = 110
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
    trail_axis_scale: tuple[float, float]
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
    protected: bool = False


def compute_quick_bubble_layout(
    *,
    local_content_rect: Sequence[object],
    visual_scale: float,
    viewport_extent: Sequence[object],
    baseline_viewport_size: Sequence[object],
) -> QuickBubbleLayout:
    if len(local_content_rect) != 4:
        raise ValueError("Bubble content geometry is incomplete")
    content = tuple(float(value) for value in local_content_rect)
    scale = float(visual_scale)
    if len(viewport_extent) != 2 or len(baseline_viewport_size) != 2:
        raise ValueError("Bubble viewport geometry is incomplete")
    extent = tuple(float(value) for value in viewport_extent)
    baseline = tuple(float(value) for value in baseline_viewport_size)
    if min(content[2], content[3], scale, *extent, *baseline) <= 0.0:
        raise ValueError("Bubble content geometry must be positive")
    # Bubble history remains renderer-normalized content geometry.  The wake is
    # an authored presentation effect, however: allowing the same normalized
    # history separation to expand with a CUSTOM axis made its three samples
    # read as three extra bubbles at tall/wide extents.  Compress only the
    # rendered sample offset back to baseline-pixel authority.
    trail_axis_scale = (
        min(1.0, baseline[0] / extent[0]),
        min(1.0, baseline[1] / extent[1]),
    )
    # Ripple distance is aspect-corrected in units of content height.  Its
    # radius/ring spacing therefore need the vertical baseline/current ratio
    # as well; otherwise R4's compact source centres still emit enormous wake
    # fields on a tall edge-resized viewport.  Uniform whole-card scale is
    # intentionally independent and continues to scale the finished effect.
    trail_radial_scale = min(1.0, baseline[1] / extent[1])

    # The operator rejected the height-only projection: reshaping the same
    # area into a wide card weakened every visible reaction, and a tall card
    # amplified it. Project the entire authored waveform through an equal-area
    # canonical rectangle, independent of how extent/scale encode that area.
    # This is not the retired baseline/current cap: large views still grow and
    # temporal attack/overshoot/settling remain fully intact.
    response_height = math.sqrt(content[2] * content[3] / (baseline[0] / baseline[1]))
    effect_scale = response_height / baseline[1]

    # Resolve the same continuous geometry profile used by the simulation.  The
    # result is physical half-stroke pixels, independent of effect scale, so
    # extreme shapes firm up gradually without the old late accelerating ramp.
    viewport_profile = resolve_bubble_viewport_profile(
        extent,
        baseline_viewport_size=baseline,
    )
    # Specular mutation and ellipse orientation were authored at canonical
    # content aspect. Recover that content size at the current uniform scale
    # and resolved inset, so an edge resize cannot stretch a bubble-local light.
    # The shader uses a one-pixel height floor in its aspect metric as well.
    excluded_width = max(0.0, extent[0] * scale - content[2])
    excluded_height = max(0.0, extent[1] * scale - content[3])
    reference_width = max(1e-6, baseline[0] * scale - excluded_width)
    reference_height = max(1.0, baseline[1] * scale - excluded_height)
    return QuickBubbleLayout(
        content_rect=content,  # type: ignore[arg-type]
        aspect_ratio=content[2] / content[3],
        visual_scale=scale,
        trail_axis_scale=trail_axis_scale,
        trail_radial_scale=trail_radial_scale,
        viewport_stroke_extra_half_px=viewport_profile.stroke_extra_half_px,
        specular_reference_aspect=reference_width / reference_height,
        response_radius_scale=response_height / content[3],
        effect_scale=effect_scale,
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
    )



class QuickBubbleRenderer:
    mode_id = "bubble"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}
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

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        mode_state = snapshot.logical.mode_state
        if not isinstance(mode_state, BubbleFrame):
            raise TypeError("Bubble renderer received another mode frame")
        presentation = snapshot.presentation
        outer_x, outer_y, _outer_width, _outer_height = presentation.outer_rect
        content_x, content_y, content_width, content_height = (
            presentation.content_rect
        )
        local_content_rect = (
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        )
        layout_key = (
            local_content_rect,
            presentation.uniform_visual_scale,
            presentation.viewport_extent,
            presentation.baseline_viewport_size,
        )
        if self._layout_cache_key != layout_key or self._layout_cache is None:
            self._layout_cache = compute_quick_bubble_layout(
                local_content_rect=local_content_rect,
                visual_scale=presentation.uniform_visual_scale,
                viewport_extent=presentation.viewport_extent,
                baseline_viewport_size=presentation.baseline_viewport_size,
            )
            self._layout_cache_key = layout_key
        layout = self._layout_cache
        payload = resolve_quick_bubble_payload(snapshot)
        if not self._program:
            self._initialize()

        parameters = mode_state.parameters
        uniforms = self._uniforms
        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2f(uniforms["u_resolution"], *frame.logical_size)
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
                float(parameter(parameters, "bubble_trail_strength", 0.0)),
            ),
        )
        tail_opacity = max(
            0.0,
            min(
                0.85,
                float(parameter(parameters, "bubble_tail_opacity", 0.0)),
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
        gl.glUniform2f(uniforms["u_trail_axis_scale"], *layout.trail_axis_scale)
        gl.glUniform1f(uniforms["u_trail_radial_scale"], layout.trail_radial_scale)
        gl.glUniform1f(
            uniforms["u_viewport_stroke_extra_half_px"],
            layout.viewport_stroke_extra_half_px,
        )

        specular_direction = get_bubble_specular_shader_vector(
            str(parameter(parameters, "bubble_specular_direction", "top_left"))
        )
        gradient_name = str(
            parameter(parameters, "bubble_gradient_direction", "top")
        )
        gradient_direction = get_bubble_gradient_shader_vector(gradient_name)
        gl.glUniform2f(uniforms["u_specular_dir"], *specular_direction)
        gl.glUniform2f(uniforms["u_gradient_dir"], *gradient_direction)
        gl.glUniform1i(
            uniforms["u_gradient_mode"],
            get_bubble_gradient_shader_mode(gradient_name),
        )

        color_values = (
            (
                "u_outline_color",
                "bubble_outline_color",
                (255, 255, 255, 230),
            ),
            (
                "u_specular_color",
                "bubble_specular_color",
                (255, 255, 255, 255),
            ),
            (
                "u_gradient_light",
                "bubble_gradient_light",
                (210, 170, 120, 255),
            ),
            (
                "u_gradient_dark",
                "bubble_gradient_dark",
                (80, 60, 50, 255),
            ),
            (
                "u_pop_color",
                "bubble_pop_color",
                (255, 255, 255, 180),
            ),
        )
        for uniform_name, parameter_name, default in color_values:
            gl.glUniform4f(
                uniforms[uniform_name],
                *rgba(parameter(parameters, parameter_name, None), default=default),
            )

        ghost_alpha = 0.0
        if bool(parameter(parameters, "bubble_ghosting_enabled", False)):
            ghost_alpha = max(
                0.0,
                min(
                    1.0,
                    float(parameter(parameters, "bubble_ghost_alpha", 0.0)),
                ),
            )
        gl.glUniform1f(uniforms["u_ghost_alpha"], ghost_alpha)
        ghost_decay = max(
            0.1,
            min(
                1.0,
                float(parameter(parameters, "bubble_ghost_decay", 0.4)),
            ),
        )
        gl.glUniform1f(uniforms["u_ghost_decay"], ghost_decay)
        hue = 0.0
        if bool(parameter(parameters, "rainbow_enabled", False)):
            speed = max(
                0.01,
                min(
                    5.0,
                    float(parameter(parameters, "rainbow_speed", 0.5)),
                ),
            )
            hue = safe_hue(mode_state.simulation_timestamp * speed * 0.1)
        gl.glUniform1f(uniforms["u_rainbow_hue_offset"], hue)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
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
                "u_bubbles_pos",
                "u_bubbles_extra",
                "u_bubbles_trail",
                "u_trail_strength",
                "u_tail_opacity",
                "u_trail_axis_scale",
                "u_trail_radial_scale",
                "u_viewport_stroke_extra_half_px",
                "u_specular_dir",
                "u_gradient_dir",
                "u_gradient_mode",
                "u_outline_color",
                "u_specular_color",
                "u_gradient_light",
                "u_gradient_dark",
                "u_pop_color",
                "u_rainbow_hue_offset",
                "u_ghost_alpha",
                "u_ghost_decay",
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
