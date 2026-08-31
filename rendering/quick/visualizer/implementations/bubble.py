"""Qt Quick Bubble renderer consuming one immutable authored snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from OpenGL import GL as gl

from core.settings.bubble_gradient_semantics import (
    get_bubble_gradient_shader_mode,
    get_bubble_gradient_shader_vector,
    get_bubble_specular_shader_vector,
)
from rendering.quick.render.gl_resources import compile_program
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


@dataclass(frozen=True, slots=True)
class QuickBubbleLayout:
    content_rect: tuple[float, float, float, float]
    aspect_ratio: float
    visual_scale: float


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
) -> QuickBubbleLayout:
    if len(local_content_rect) != 4:
        raise ValueError("Bubble content geometry is incomplete")
    content = tuple(float(value) for value in local_content_rect)
    scale = float(visual_scale)
    if min(content[2], content[3], scale) <= 0.0:
        raise ValueError("Bubble content geometry must be positive")
    return QuickBubbleLayout(
        content_rect=content,  # type: ignore[arg-type]
        aspect_ratio=content[2] / content[3],
        visual_scale=scale,
    )


def _payload(
    positions: Sequence[object],
    extras: Sequence[object],
    trails: Sequence[object],
    count: object,
    *,
    protected: bool,
) -> QuickBubblePayload | None:
    bubble_count = max(0, min(_MAX_BUBBLES, int(count)))
    required = bubble_count * 4
    if len(positions) < required or len(extras) < required:
        return None
    required_trails = bubble_count * 9
    trail_values = tuple(float(value) for value in trails[:required_trails])
    if trail_values and len(trail_values) < required_trails:
        return None
    return QuickBubblePayload(
        positions=tuple(float(value) for value in positions[:required]),
        extras=tuple(float(value) for value in extras[:required]),
        trails=trail_values,
        bubble_count=bubble_count,
        protected=protected,
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
    current = _payload(
        mode_state.positions,
        mode_state.extras,
        mode_state.trails,
        mode_state.bubble_count,
        protected=False,
    )
    if current is None:
        raise ValueError("Bubble immutable arrays do not match bubble_count")
    return current



class QuickBubbleRenderer:
    mode_id = "bubble"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

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
        layout = compute_quick_bubble_layout(
            local_content_rect=(
                content_x - outer_x,
                content_y - outer_y,
                content_width,
                content_height,
            ),
            visual_scale=presentation.uniform_visual_scale,
        )
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
        gl.glUniform1f(uniforms["u_visual_scale"], layout.visual_scale)
        gl.glUniform1f(uniforms["u_border_width"], presentation.border_width)
        gl.glUniform1f(uniforms["u_fade"], presentation.content_fade)
        gl.glUniform1i(uniforms["u_bubble_count"], payload.bubble_count)
        if payload.bubble_count:
            gl.glUniform4fv(
                uniforms["u_bubbles_pos"],
                payload.bubble_count,
                payload.positions,
            )
            gl.glUniform4fv(
                uniforms["u_bubbles_extra"],
                payload.bubble_count,
                payload.extras,
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
            gl.glUniform3fv(
                uniforms["u_bubbles_trail"],
                payload.bubble_count * 3,
                payload.trails,
            )
        else:
            trail_strength = 0.0
            tail_opacity = 0.0
        gl.glUniform1f(uniforms["u_trail_strength"], trail_strength)
        gl.glUniform1f(uniforms["u_tail_opacity"], tail_opacity)

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
                "u_border_width",
                "u_fade",
                "u_bubble_count",
                "u_bubbles_pos",
                "u_bubbles_extra",
                "u_bubbles_trail",
                "u_trail_strength",
                "u_tail_opacity",
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
