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
from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.uniforms import PassBlocks
from widgets.spotify_visualizer.bubble_viewport_profile import (
    BUBBLE_RENDER_CAPACITY,
    bubble_stroke_extra_half_px,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerRenderSnapshot,
)
from widgets.spotify_visualizer.shaders import load_fragment_shader
from widgets.spotify_visualizer.bubble_ambient import RECORD_STRIDE as BUBBLE_AMBIENT_RECORD_STRIDE
from widgets.spotify_visualizer.bubble_ambient_geometry import ambient_sprite_scale, ambient_target_size

from rendering.quick import gl_query
from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QuickVisualizerRenderFrame,
    quick_visualizer_vertex_source,
)


_MAX_BUBBLES = BUBBLE_RENDER_CAPACITY
_BUBBLE_POS_SIZE = _MAX_BUBBLES * 4
_BUBBLE_EXTRA_SIZE = _MAX_BUBBLES * 4
_BUBBLE_TRAIL_SIZE = _MAX_BUBBLES * 3 * 3


def _bubble_program_parts():
    """(the quad's vertex stage, the block layout) from ``bubble.frag``'s own ``BubbleDraw`` declaration (N1.6):
    one declaration for both stages and for the packing. (None, None) when the shader file is unavailable."""
    fragment = load_fragment_shader("bubble")
    if fragment is None:
        return None, None
    declaration = block_declaration(fragment, "BubbleDraw")
    return quick_visualizer_vertex_source(declaration), block_layout_from_glsl(declaration)


BUBBLE_VERTEX_SOURCE, BUBBLE_BLOCK = _bubble_program_parts()


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
    big_class_bits: tuple[int, ...] = (0,) * 8
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
    return _payload_of(mode_state)


def _payload_of(mode_state: BubbleFrame) -> QuickBubblePayload:
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



def bubble_presentation_layout(presentation, logical_content_rect: Sequence[object],
                               world_scale: float) -> QuickBubbleLayout:
    """The layout of a drawn card: ``presentation`` with its content rect in the oriented item (the Python renderer's
    ``frame.logical_content_rect``; the native card's ``content_rect``) and the frame's capacity zoom."""
    return compute_quick_bubble_layout(
        local_content_rect=logical_content_rect,
        visual_scale=presentation.uniform_visual_scale,
        viewport_extent=presentation.logical_viewport_extent,
        baseline_viewport_size=presentation.baseline_viewport_size,
        world_scale=world_scale,
    )


def _bubble_frame(logical) -> BubbleFrame:
    mode_state = logical.mode_state
    if not isinstance(mode_state, BubbleFrame):
        raise TypeError("Bubble renderer received another mode frame")
    return mode_state


def _gradient_values(parameters, layout: QuickBubbleLayout) -> tuple[float, float, float, float]:
    """Named recipes retain their vectors; custom nodes use the shared physical projection."""
    direction = str(parameter(parameters, "bubble_gradient_direction"))
    if direction == 'custom':
        return (*project_linear_gradient(parameter(parameters, 'bubble_gradient_endpoints'), layout.aspect_ratio), 0.)
    return tuple(project_bubble_gradient(direction))


#: BubbleDraw's members the Python renderer never writes (declared by the shader, read by none of its Quick paths):
#: zero, as its uniforms were at link. The native core takes them as settings, since it fills no member silently (D12).
BUBBLE_UNWRITTEN_MEMBERS = ("u_time", "u_playing", "u_overall_energy", "u_bass_energy", "u_mid_energy",
                            "u_high_energy")

#: BubbleDraw's per-frame members (``bubble_frame_values``): the native record's block fields
#: (``core.visualizer_engine.bubble_native_schema``). The ambient points and occluders are the record's two streams.
BUBBLE_FRAME_MEMBERS = ("u_bubbles_pos", "u_bubbles_extra", "u_bubbles_trail", "u_bubble_count", "u_big_class_bits",
                        "u_big_class_bits_hi", "u_trail_strength", "u_tail_opacity", "u_rainbow_hue_offset", "u_ambient_enabled",
                        "u_ambient_light_enabled")


def _points_glow(points: Sequence[float]) -> bool:
    """True when any ambient particle emits light (glow is the record's fifth field)."""
    return max(points[4::BUBBLE_AMBIENT_RECORD_STRIDE], default=0.0) > 0.0


def bubble_ambient_settings_values(logical, layout: QuickBubbleLayout, dpr: float) -> dict[str, object]:
    """The ambient points' block (``BubbleAmbientPoints``) from Settings and the card, as the Python renderer passes it
    to its ambient pass (read only while the layer draws: a frame of the ambience's Settings carries these)."""
    parameters = _bubble_frame(logical).parameters
    return {
        "uTexelScale": ambient_target_size(layout.content_rect, dpr)[2],
        "uSpriteScale": ambient_sprite_scale(layout.effect_scale),
        "uGlowSpread": float(parameter(parameters, "bubble_particle_glow_spread")),
        "uMicroColor": tuple(rgba(parameter(parameters, "bubble_outline_color"))),
        "uParticleColor": tuple(rgba(parameter(parameters, "bubble_particle_color"))),
    }


def bubble_settings_values(logical, layout: QuickBubbleLayout, dpr: float) -> dict[str, object]:
    """Every BubbleDraw member that comes from Settings or the card, by name, as the Python renderer writes it
    (``QuickBubbleRenderer.render`` calls this): its layout and style and the ambient target's content size.
    ``layout``: ``bubble_presentation_layout`` of the drawn card; ``dpr``: the drawn card's. The core members
    (``MODE_CORE_MEMBERS``) are not here; the ambient pass's are ``bubble_ambient_settings_values``."""
    mode_state = _bubble_frame(logical)
    parameters = mode_state.parameters
    ghost_alpha = 0.0
    if bool(parameter(parameters, "bubble_ghosting_enabled")):
        ghost_alpha = max(0.0, min(1.0, float(parameter(parameters, "bubble_ghost_alpha"))))
    width, height, _texel_scale = ambient_target_size(layout.content_rect, dpr)
    values: dict[str, object] = {
        "u_content_rect": tuple(layout.content_rect),
        "u_visual_scale": layout.effect_scale,
        "u_response_radius_scale": layout.response_radius_scale,
        "u_specular_reference_aspect": layout.specular_reference_aspect,
        "u_trail_radial_scale": layout.trail_radial_scale,
        "u_viewport_stroke_extra_half_px": layout.viewport_stroke_extra_half_px,
        "u_specular_dir": tuple(get_bubble_specular_shader_vector(
            str(parameter(parameters, "bubble_specular_direction")))),
        "u_gradient": _gradient_values(parameters, layout),
        "u_ghost_alpha": ghost_alpha,
        "u_ghost_decay": max(0.1, min(1.0, float(parameter(parameters, "bubble_ghost_decay")))),
        # The ambient target's content size (ambient_target_size): where its content lies in the texture sampled.
        "u_ambient_px": (float(width), float(height)),
    }
    for uniform_name, parameter_name in (
        ("u_outline_color", "bubble_outline_color"),
        ("u_specular_color", "bubble_specular_color"),
        ("u_gradient_light", "bubble_gradient_light"),
        ("u_gradient_dark", "bubble_gradient_dark"),
        ("u_pop_color", "bubble_pop_color"),
    ):
        values[uniform_name] = tuple(rgba(parameter(parameters, parameter_name)))
    for name in BUBBLE_UNWRITTEN_MEMBERS:
        values[name] = 0
    return values


def bubble_frame_scalars(mode_state: BubbleFrame, payload: QuickBubblePayload) -> dict[str, object]:
    """BubbleDraw's per-frame scalars, as the Python renderer writes them and the native record carries them: the
    count, the big-class words, the wake's strength and opacity (0 on a frame with no trail samples), the rainbow's
    hue (the simulation clock times the speed) and the ambient layer's two switches."""
    parameters = mode_state.parameters
    trail_strength = tail_opacity = 0.0
    if payload.trails and payload.bubble_count:
        trail_strength = max(0.0, min(1.5, float(parameter(parameters, "bubble_trail_strength"))))
        tail_opacity = max(0.0, min(0.85, float(parameter(parameters, "bubble_tail_opacity"))))
    hue = 0.0
    if bool(parameter(parameters, "rainbow_enabled")):
        speed = max(0.01, min(5.0, float(parameter(parameters, "rainbow_speed"))))
        hue = safe_hue(mode_state.simulation_timestamp * speed * 0.1)
    return {
        "u_bubble_count": payload.bubble_count,
        # Eight class words in two uvec4 members: heroes 0-127, then 128-191 (bubble.frag).
        "u_big_class_bits": tuple(payload.big_class_bits[:4]),
        "u_big_class_bits_hi": tuple(payload.big_class_bits[4:8]),
        "u_trail_strength": trail_strength,
        "u_tail_opacity": tail_opacity,
        "u_rainbow_hue_offset": hue,
        "u_ambient_enabled": int(bool(payload.ambient_points)),
        "u_ambient_light_enabled": int(_points_glow(payload.ambient_points)),
    }


def bubble_frame_values(logical) -> dict[str, object]:
    """Every per-frame value of Bubble's native record (``BUBBLE_FRAME_MEMBERS`` and the ambient streams), by name, in
    double precision (the core rounds each to float as the Python block packer does): the arrays padded with zeros past
    the count (the shader reads only the first count), the trail samples zero on a frame without them (R-225), the
    ambient points and hero occluders as the float32 bytes the Python renderer uploads, with their used lengths."""
    mode_state = _bubble_frame(logical)
    payload = _payload_of(mode_state)
    values = bubble_frame_scalars(mode_state, payload)
    count = payload.bubble_count

    def rows(flat: Sequence[float], used: int, total: int, width: int) -> tuple[tuple[float, ...], ...]:
        out = [tuple(float(v) for v in flat[i * width:(i + 1) * width]) + (0.0,) * (4 - width) for i in range(used)]
        return tuple(out) + ((0.0, 0.0, 0.0, 0.0),) * (total - used)

    values["u_bubbles_pos"] = rows(payload.positions, count, _MAX_BUBBLES, 4)
    values["u_bubbles_extra"] = rows(payload.extras, count, _MAX_BUBBLES, 4)
    samples = count * 3 if payload.trails else 0
    values["u_bubbles_trail"] = rows(payload.trails, samples, _MAX_BUBBLES * 3, 3)
    values["ambient_points"] = np.asarray(payload.ambient_points, dtype=np.float32).tobytes()
    values["ambient_point_floats"] = len(payload.ambient_points)
    values["ambient_occluders"] = np.asarray(payload.ambient_occluders, dtype=np.float32).tobytes()
    values["ambient_occluder_floats"] = len(payload.ambient_occluders)
    return values


class QuickBubbleRenderer:
    mode_id = "bubble"

    def __init__(self) -> None:
        self._program = 0
        self._ambient_renderer = None  # lazily allocated, never if both layers are disabled
        # The block's values as the program's uniforms held them: zero at link, kept between frames (N1.6).
        self._values: dict[str, object] = {}
        self._blocks = PassBlocks("Quick Bubble", block_bytes=BUBBLE_BLOCK.size if BUBBLE_BLOCK else 256)
        self._last_content_rotation_quarters: int | None = None
        # Persistent render-thread transport. Immutable authored snapshots remain
        # tuples; only the OpenGL upload representation is mutable/reused.
        self._position_uniform_buffer = np.zeros(_BUBBLE_POS_SIZE, dtype=np.float32)
        self._extra_uniform_buffer = np.zeros(_BUBBLE_EXTRA_SIZE, dtype=np.float32)
        self._trail_uniform_buffer = np.zeros(_BUBBLE_TRAIL_SIZE, dtype=np.float32)
        # The trail samples in the block's std140 form (a vec3 element takes 16 bytes): the samples a frame uploads
        # are copied in, the rest keep what they held, as the uniform array's elements did.
        self._trail_block = np.zeros((_BUBBLE_TRAIL_SIZE // 3, 4), dtype=np.float32)
        self._trail_samples_held = False      # the block's trail samples are a frame's (cleared on a frame without)
        self._layout_cache_key: tuple[object, ...] | None = None
        self._layout_cache: QuickBubbleLayout | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._program) or self._blocks.has_resources

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
            self._layout_cache = bubble_presentation_layout(presentation, local_content_rect, mode_state.world_scale)
            self._layout_cache_key = layout_key
        layout = self._layout_cache
        payload = resolve_quick_bubble_payload(snapshot)
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_LAYOUT_PAYLOAD_READY)
        if not self._program:
            self._initialize()
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_PROGRAM_READY)

        # The program's values persist between frames as its uniforms did; the whole block is bound for the draw
        # (N1.6). Settings and per-frame scalars come from the functions the native route and record share (N5.1).
        values = self._values
        settings = bubble_settings_values(snapshot.logical, layout, presentation.dpr)
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
            ambient = bubble_ambient_settings_values(snapshot.logical, layout, presentation.dpr)
            ambient_texture, ambient_light = self._ambient_renderer.render_texture(
                layout.content_rect, presentation.dpr, payload.ambient_points,
                sprite_scale=ambient["uSpriteScale"],
                glow_spread=ambient["uGlowSpread"],
                micro_color=ambient["uMicroColor"],
                particle_color=ambient["uParticleColor"],
                occluders=payload.ambient_occluders,
                response_radius_scale=layout.response_radius_scale,
            )
        elif self._ambient_renderer is not None:
            # Returning to an ordinary preset releases the opt-in GPU target
            # exactly once; the original Bubble path then remains allocation-free.
            self._ambient_renderer.release_resources()
            self._ambient_renderer = None
        gl.glUseProgram(self._program)
        # The ambient samplers are bound at units 0 and 1 by the shader (layout bindings).
        values.update(settings)
        values.update(bubble_frame_scalars(mode_state, payload))
        values["uMatrix"] = frame.matrix_values
        values["uItemSize"] = tuple(frame.logical_size)
        content_rotation_quarters = frame.content_rotation_quarters
        if content_rotation_quarters != self._last_content_rotation_quarters:
            values["uContentRotationQuarters"] = content_rotation_quarters
            self._last_content_rotation_quarters = content_rotation_quarters
        values["u_resolution"] = tuple(frame.oriented_logical_size)
        values["u_dpr"] = presentation.dpr
        values["u_viewport_origin_px"] = (0.0, 0.0)
        values["u_quick_item_coords"] = 1
        # fragPixel's target (the window's framebuffer here; its row flip is 0 in this renderer, N1.4).
        values["u_target_px"] = (float(frame.viewport[2]), float(frame.viewport[3]))
        values["u_border_width"] = presentation.border_width
        values["u_fade"] = presentation.content_fade
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
            # vec4 arrays: the float32 buffers are already in std140 form. Elements past the count keep what an
            # earlier frame gave them, as the uniform arrays' did (the shader reads only the first count).
            values["u_bubbles_pos"] = position_buffer.tobytes()
            values["u_bubbles_extra"] = extra_buffer.tobytes()

        if payload.trails and payload.bubble_count:
            trail_buffer = _copy_uniform_float_buffer(
                self._trail_uniform_buffer,
                payload.trails,
                active_size=payload.bubble_count * 9,
            )
            samples = payload.bubble_count * 3
            self._trail_block[:samples, :3] = trail_buffer[:samples * 3].reshape(samples, 3)
            values["u_bubbles_trail"] = self._trail_block.tobytes()
            self._trail_samples_held = True
        elif self._trail_samples_held:
            # No trail samples this frame: the ghost pass reads the oldest sample whatever the wake does, so an
            # earlier frame's samples would draw a ghost frozen where that frame left it (R-225). Cleared once at
            # this edge; nothing is written again while the trails stay inactive.
            self._trail_block.fill(0.0)
            values["u_bubbles_trail"] = self._trail_block.tobytes()
            self._trail_samples_held = False
        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_REACTIVE_UNIFORMS_READY)

        if trace is not None:
            trace.mark(FrameTraceEvent.BUBBLE_STYLE_UNIFORMS_READY)
        with self._blocks.bound(pack_block(BUBBLE_BLOCK, values)):
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
        if not self._program and not self._blocks.has_resources:
            return
        if self._program:
            delete_program(self._program)
        self._program = 0
        self._blocks.release()
        self._last_content_rotation_quarters = None
        self._values = {}    # a new program's values start at zero, as its uniforms did

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("bubble")
        if fragment_source is None or BUBBLE_VERTEX_SOURCE is None:
            raise RuntimeError("canonical Bubble shader is unavailable")
        written = (
            "uMatrix",
            "uItemSize",
            "uContentRotationQuarters",
            "u_resolution",
            "u_dpr",
            "u_viewport_origin_px",
            "u_quick_item_coords",
            "u_target_px",
            "u_content_rect",
            "u_visual_scale",
            "u_response_radius_scale",
            "u_specular_reference_aspect",
            "u_border_width",
            "u_fade",
            "u_bubble_count",
            "u_big_class_bits",
            "u_big_class_bits_hi",
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
            "u_ambient_light_enabled",
            "u_ambient_px",
        )
        held = {name for name, _kind in BUBBLE_BLOCK.fields}
        missing = [name for name in written if name not in held]
        if missing:
            raise RuntimeError("Quick Bubble's block is incomplete: " + ", ".join(missing))
        self._program = compile_program(BUBBLE_VERTEX_SOURCE, fragment_source, label="Quick Bubble")
        self._values = {}
        # The block's ring, allocated with the program (the first frame compiles it anyway).
        self._blocks.warm()


def create_visualizer_renderer() -> QuickBubbleRenderer:
    return QuickBubbleRenderer()


__all__ = [
    "BUBBLE_FRAME_MEMBERS",
    "BUBBLE_UNWRITTEN_MEMBERS",
    "bubble_ambient_settings_values",
    "bubble_frame_scalars",
    "bubble_frame_values",
    "bubble_presentation_layout",
    "bubble_settings_values",
    "QuickBubbleLayout",
    "QuickBubblePayload",
    "QuickBubbleRenderer",
    "compute_quick_bubble_layout",
    "create_visualizer_renderer",
    "resolve_quick_bubble_payload",
]
