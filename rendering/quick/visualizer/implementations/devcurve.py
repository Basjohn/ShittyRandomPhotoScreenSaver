"""Qt Quick Spline Curve renderer consuming one immutable authored snapshot.

Spline Curve is mode id ``devcurve`` (code name DevCurve); its sibling owners are mapped in
``Docs/Reference/Naming.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from OpenGL import GL as gl

from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.uniforms import PassBlocks
from widgets.spotify_visualizer.render_state import DevCurveFrame
from widgets.spotify_visualizer.shaders import load_fragment_shader

from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QuickVisualizerRenderFrame,
    quick_visualizer_vertex_source,
)


_LAYER_NAMES = ("bass", "vocals", "mids", "transients")
_LAYER_IDS = {name: index for index, name in enumerate(_LAYER_NAMES)}
_MAX_SAMPLES = 96


def _devcurve_program_parts():
    """(the quad's vertex stage, the block layout) from ``devcurve.frag``'s own ``DevCurveDraw`` declaration (N1.6):
    one declaration for both stages and for the packing. (None, None) when the shader file is unavailable."""
    fragment = load_fragment_shader("devcurve")
    if fragment is None:
        return None, None
    declaration = block_declaration(fragment, "DevCurveDraw")
    return quick_visualizer_vertex_source(declaration), block_layout_from_glsl(declaration)


DEVCURVE_VERTEX_SOURCE, DEVCURVE_BLOCK = _devcurve_program_parts()

@dataclass(frozen=True, slots=True)
class QuickDevCurveLayout:
    content_rect: tuple[float, float, float, float]
    visual_scale: float
    normalized_x_scale: float
    normalized_y_scale: float


def compute_quick_devcurve_layout(
    *,
    local_content_rect: Sequence[object],
    visual_scale: float,
    baseline_content_extent: Sequence[object],
) -> QuickDevCurveLayout:
    if len(local_content_rect) != 4:
        raise ValueError("DevCurve content geometry is incomplete")
    if len(baseline_content_extent) != 2:
        raise ValueError("DevCurve baseline content extent is incomplete")
    content = tuple(float(value) for value in local_content_rect)
    baseline = tuple(float(value) for value in baseline_content_extent)
    scale = float(visual_scale)
    if min(content[2], content[3], baseline[0], baseline[1], scale) <= 0.0:
        raise ValueError("DevCurve content geometry must be positive")
    return QuickDevCurveLayout(
        content_rect=content,  # type: ignore[arg-type]
        visual_scale=scale,
        normalized_x_scale=(baseline[0] * scale) / content[2],
        normalized_y_scale=(baseline[1] * scale) / content[3],
    )




def _smoothstep01(value: float) -> float:
    x = max(0.0, min(1.0, float(value)))
    return x * x * (3.0 - 2.0 * x)


def devcurve_outline_extra_total_px(layout: QuickDevCurveLayout) -> float:
    """Return the bounded viewport-derived *total* line-width addition.

    DevCurve's persisted outline widths remain authored normalized values.  The
    Quick migration had left them visually a little light, and pure CUSTOM
    viewport expansion intentionally preserves authored pixel scale.  Add one
    logical pixel at every size, then ease in at most two more pixels as either
    viewport axis grows from canonical to 3x.  Uniform whole-card scaling is
    already handled by the authored width and does not enter this viewport ramp.
    """

    x_extent = 1.0 / max(float(layout.normalized_x_scale), 1e-6)
    y_extent = 1.0 / max(float(layout.normalized_y_scale), 1e-6)
    viewport_extent = max(x_extent, y_extent)
    ramp = _smoothstep01((viewport_extent - 1.0) / 2.0)
    return 1.0 + 2.0 * ramp


def devcurve_outline_half_width(
    authored_width: float,
    layout: QuickDevCurveLayout,
) -> float:
    """Resolve authored outline half-width plus the small Quick pixel boost."""

    base = max(0.0004, min(0.015, float(authored_width))) * float(
        layout.normalized_y_scale
    )
    content_height = max(1.0, float(layout.content_rect[3]))
    extra_half_normalized = (devcurve_outline_extra_total_px(layout) * 0.5) / (
        content_height
    )
    return base + extra_half_normalized


def _curve_mapping(
    values: Sequence[tuple[str, Sequence[object]]],
) -> dict[str, tuple[float, ...]]:
    result: dict[str, tuple[float, ...]] = {}
    for name, samples in values:
        canonical = str(name or "").strip().lower()
        if canonical not in _LAYER_IDS or canonical in result:
            raise ValueError(f"invalid DevCurve layer identity: {name!r}")
        result[canonical] = tuple(float(value) for value in samples)
    return result


def _sample_count(
    curves: Mapping[str, Sequence[object]],
    requested: object,
) -> int:
    if set(curves) != set(_LAYER_NAMES):
        raise ValueError("DevCurve immutable frame must contain all four layers")
    available = min(len(curves[name]) for name in _LAYER_NAMES)
    count = min(_MAX_SAMPLES, available, max(2, int(requested)))
    if count < 2:
        raise ValueError("DevCurve immutable curves require at least two samples")
    return count


def _padded_samples(
    values: Sequence[object],
    *,
    sample_count: int,
) -> tuple[float, ...]:
    active = tuple(float(value) for value in values[:sample_count])
    if len(active) < sample_count:
        raise ValueError("DevCurve immutable curve is shorter than sample_count")
    tail = active[-1]
    return active + (tail,) * (_MAX_SAMPLES - len(active))


def _draw_order(values: Sequence[object]) -> tuple[str, ...]:
    resolved = tuple(str(value or "").strip().lower() for value in values)
    if len(resolved) == 4 and set(resolved) == set(_LAYER_NAMES):
        return resolved
    return _LAYER_NAMES


def _slot(values: Sequence[object]) -> tuple[float, float, float, float]:
    padded = tuple(float(value) for value in values[:4]) + (0.0,) * 4
    return padded[:4]  # type: ignore[return-value]


class QuickDevCurveRenderer:
    mode_id = "devcurve"

    def __init__(self) -> None:
        self._program = 0
        # The block's values as the program's uniforms held them: zero at link, kept between frames (N1.6).
        self._values: dict[str, object] = {}
        self._blocks = PassBlocks("Quick DevCurve", block_bytes=DEVCURVE_BLOCK.size if DEVCURVE_BLOCK else 256)
        self._last_content_rotation_quarters: int | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._program) or self._blocks.has_resources

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        mode_state = snapshot.logical.mode_state
        if not isinstance(mode_state, DevCurveFrame):
            raise TypeError("DevCurve renderer received another mode frame")
        presentation = snapshot.presentation
        outer_x, outer_y, _outer_width, _outer_height = (
            presentation.outer_rect
        )
        content_x, content_y, content_width, content_height = (
            presentation.content_rect
        )
        scale = presentation.uniform_visual_scale
        extra_inset = float(presentation.shell_style["content_inset"])
        # The shell border now follows the shared bounded visible-stroke contract,
        # so it is intentionally non-linear with visual scale. DevCurve's authored
        # baseline content extent must recover the original authored border source
        # rather than reverse-scaling the visible/clamped frame thickness.
        authored_border = float(
            presentation.shell_style["authored_border_width"]
        )
        authored_inset = authored_border + extra_inset / scale
        baseline_width, baseline_height = presentation.baseline_viewport_size
        layout = compute_quick_devcurve_layout(
            local_content_rect=frame.logical_content_rect,
            visual_scale=scale,
            baseline_content_extent=(
                max(1.0, baseline_width - 2.0 * authored_inset),
                max(1.0, baseline_height - 2.0 * authored_inset),
            ),
        )
        if not self._program:
            self._initialize()

        parameters = mode_state.parameters
        curves = _curve_mapping(mode_state.curves)
        sample_count = _sample_count(
            curves,
            parameter(parameters, "devcurve_sample_count"),
        )
        order = _draw_order(mode_state.draw_order)
        # The program's values persist between frames as its uniforms did; the whole block is bound for the draw
        # (N1.6).
        values = self._values

        gl.glUseProgram(self._program)
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
        values["u_content_rect"] = tuple(layout.content_rect)
        values["u_devcurve_normalized_scale"] = (layout.normalized_x_scale, layout.normalized_y_scale)
        values["u_devcurve_x_to_y_scale"] = layout.normalized_y_scale / layout.normalized_x_scale
        values["u_border_width"] = presentation.border_width
        values["u_fade"] = presentation.content_fade
        values["u_devcurve_sample_count"] = sample_count

        for name in _LAYER_NAMES:
            values[f"u_devcurve_layer_{name}_color"] = tuple(
                rgba(parameter(parameters, f"devcurve_layer_{name}_color")))
            values[f"u_devcurve_layer_{name}_outline_color"] = tuple(
                rgba(parameter(parameters, f"devcurve_layer_{name}_outline_color")))
            values[f"u_devcurve_layer_{name}_outline_width"] = devcurve_outline_half_width(
                float(parameter(parameters, f"devcurve_layer_{name}_outline_width")), layout)
            values[f"u_devcurve_layer_{name}_enabled"] = (
                1 if bool(parameter(parameters, f"devcurve_layer_{name}_enabled")) else 0)
            values[f"u_devcurve_layer_{name}_alpha"] = max(
                0.0, min(1.0, float(parameter(parameters, f"devcurve_layer_{name}_alpha"))))
            values[f"u_devcurve_curve_{name}"] = _padded_samples(curves[name], sample_count=sample_count)

        for index, name in enumerate(order):
            values[f"u_devcurve_order{index}"] = _LAYER_IDS[name]
        values["u_devcurve_foreground_layer_id"] = max(-1, min(3, int(mode_state.foreground_layer_id)))
        values["u_devcurve_foreground_shadow_enabled"] = (
            1 if bool(parameter(parameters, "devcurve_foreground_shadow_enabled")) else 0)
        for uniform_name, parameter_name, minimum, maximum in (
            (
                "u_devcurve_foreground_shadow_alpha",
                "devcurve_foreground_shadow_alpha",
                0.0,
                1.0,
            ),
            (
                "u_devcurve_foreground_shadow_darken",
                "devcurve_foreground_shadow_darken",
                0.0,
                1.0,
            ),
            (
                "u_devcurve_foreground_shadow_offset",
                "devcurve_foreground_shadow_offset",
                0.0,
                0.45,
            ),
        ):
            value = max(
                minimum,
                min(maximum, float(parameter(parameters, parameter_name))),
            )
            if parameter_name.endswith("offset"):
                value *= layout.normalized_y_scale
            values[uniform_name] = value

        values["u_devcurve_foreground_specular_enabled"] = (
            1 if bool(parameter(parameters, "devcurve_foreground_specular_enabled")) else 0)
        specular_activity = max(
            0.0,
            min(
                1.0,
                float(
                    parameter(
                        parameters,
                        "devcurve_specular_activity_alpha",
                    )
                ),
            ),
        )
        values["u_devcurve_foreground_specular_alpha"] = max(
            0.0, min(1.0, float(parameter(parameters, "devcurve_foreground_specular_alpha")))
        ) * specular_activity
        # Each projected width and offset is the clamped authored value times its axis scale.
        values.update(
            u_devcurve_foreground_specular_width=max(
                0.002,
                min(0.120, float(parameter(parameters, "devcurve_foreground_specular_width"))),
            )
            * layout.normalized_x_scale,
            u_devcurve_foreground_specular_offset=max(
                -0.20,
                min(0.20, float(parameter(parameters, "devcurve_foreground_specular_offset"))),
            )
            * layout.normalized_y_scale,
            u_devcurve_foreground_specular_crest_bias=max(
                0.0, min(2.0, float(parameter(parameters, "devcurve_foreground_specular_crest_bias")))),
        )
        slots = list(mode_state.specular_slots)
        while len(slots) < 3:
            slots.append(())
        for index, slot in enumerate(slots[:3]):
            values[f"u_devcurve_specular_slot{index}"] = _slot(slot)

        hue = 0.0
        if bool(parameter(parameters, "rainbow_enabled")):
            speed = max(
                0.01,
                min(5.0, float(parameter(parameters, "rainbow_speed"))),
            )
            hue = safe_hue(snapshot.logical.logical_timestamp * speed * 0.1)
        values["u_rainbow_hue_offset"] = hue
        with self._blocks.bound(pack_block(DEVCURVE_BLOCK, values)):
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program and not self._blocks.has_resources:
            return
        if self._program:
            delete_program(self._program)
        self._program = 0
        self._blocks.release()
        self._last_content_rotation_quarters = None
        self._values = {}    # a new program's values start at zero, as its uniforms did

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("devcurve")
        if fragment_source is None or DEVCURVE_VERTEX_SOURCE is None:
            raise RuntimeError("canonical DevCurve shader is unavailable")
        written = [
            "uMatrix",
            "uItemSize",
            "uContentRotationQuarters",
            "u_resolution",
            "u_dpr",
            "u_viewport_origin_px",
            "u_quick_item_coords",
            "u_content_rect",
            "u_devcurve_normalized_scale",
            "u_devcurve_x_to_y_scale",
            "u_border_width",
            "u_fade",
            "u_rainbow_hue_offset",
            "u_devcurve_sample_count",
            "u_devcurve_order0",
            "u_devcurve_order1",
            "u_devcurve_order2",
            "u_devcurve_order3",
            "u_devcurve_foreground_layer_id",
            "u_devcurve_foreground_shadow_enabled",
            "u_devcurve_foreground_shadow_alpha",
            "u_devcurve_foreground_shadow_darken",
            "u_devcurve_foreground_shadow_offset",
            "u_devcurve_foreground_specular_enabled",
            "u_devcurve_foreground_specular_alpha",
            "u_devcurve_foreground_specular_width",
            "u_devcurve_foreground_specular_offset",
            "u_devcurve_foreground_specular_crest_bias",
            "u_devcurve_specular_slot0",
            "u_devcurve_specular_slot1",
            "u_devcurve_specular_slot2",
        ]
        for name in _LAYER_NAMES:
            written.extend(
                (
                    f"u_devcurve_layer_{name}_color",
                    f"u_devcurve_layer_{name}_outline_color",
                    f"u_devcurve_layer_{name}_outline_width",
                    f"u_devcurve_layer_{name}_enabled",
                    f"u_devcurve_layer_{name}_alpha",
                    f"u_devcurve_curve_{name}",
                )
            )
        held = {name for name, _kind in DEVCURVE_BLOCK.fields}
        missing = [name for name in written if name not in held]
        if missing:
            raise RuntimeError("Quick DevCurve's block is incomplete: " + ", ".join(missing))
        self._program = compile_program(DEVCURVE_VERTEX_SOURCE, fragment_source, label="Quick DevCurve")
        self._values = {}
        # The block's ring, allocated with the program (the first frame compiles it anyway).
        self._blocks.warm()


def create_visualizer_renderer() -> QuickDevCurveRenderer:
    return QuickDevCurveRenderer()


__all__ = [
    "QuickDevCurveLayout",
    "QuickDevCurveRenderer",
    "compute_quick_devcurve_layout",
    "create_visualizer_renderer",
]
