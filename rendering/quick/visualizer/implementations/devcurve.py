"""Qt Quick DevCurve renderer consuming one immutable authored snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import DevCurveFrame
from widgets.spotify_visualizer.shaders import load_fragment_shader

from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QUICK_VISUALIZER_VERTEX_SOURCE,
    QuickVisualizerRenderFrame,
)


_LAYER_NAMES = ("bass", "vocals", "mids", "transients")
_LAYER_IDS = {name: index for index, name in enumerate(_LAYER_NAMES)}
_MAX_SAMPLES = 96
_LAYER_DEFAULTS = {
    "bass": ((82, 167, 255, 230), 0.55),
    "vocals": ((136, 190, 255, 220), 0.42),
    "mids": ((100, 145, 255, 220), 0.46),
    "transients": ((215, 240, 255, 240), 0.66),
}


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
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

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
        extra_inset = float(presentation.shell_style.get("content_inset", 0.0))
        authored_inset = (presentation.border_width + extra_inset) / scale
        baseline_width, baseline_height = presentation.baseline_viewport_size
        layout = compute_quick_devcurve_layout(
            local_content_rect=(
                content_x - outer_x,
                content_y - outer_y,
                content_width,
                content_height,
            ),
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
            parameter(parameters, "devcurve_sample_count", _MAX_SAMPLES),
        )
        order = _draw_order(mode_state.draw_order)
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
        gl.glUniform1f(uniforms["u_border_width"], presentation.border_width)
        gl.glUniform1f(uniforms["u_fade"], presentation.content_fade)
        gl.glUniform1i(uniforms["u_devcurve_sample_count"], sample_count)


        for name in _LAYER_NAMES:
            default_color, default_alpha = _LAYER_DEFAULTS[name]
            gl.glUniform4f(
                uniforms[f"u_devcurve_layer_{name}_color"],
                *rgba(
                    parameter(parameters, f"devcurve_layer_{name}_color", None),
                    default=default_color,
                ),
            )
            gl.glUniform4f(
                uniforms[f"u_devcurve_layer_{name}_outline_color"],
                *rgba(
                    parameter(
                        parameters,
                        f"devcurve_layer_{name}_outline_color",
                        None,
                    ),
                    default=(255, 255, 255, 255),
                ),
            )
            gl.glUniform1f(
                uniforms[f"u_devcurve_layer_{name}_outline_width"],
                max(
                    0.0004,
                    min(
                        0.015,
                        float(
                            parameter(
                                parameters,
                                f"devcurve_layer_{name}_outline_width",
                                0.006,
                            )
                        )
                        * layout.normalized_y_scale,
                    ),
                ),
            )
            gl.glUniform1i(
                uniforms[f"u_devcurve_layer_{name}_enabled"],
                1
                if bool(
                    parameter(
                        parameters,
                        f"devcurve_layer_{name}_enabled",
                        True,
                    )
                )
                else 0,
            )
            gl.glUniform1f(
                uniforms[f"u_devcurve_layer_{name}_alpha"],
                max(
                    0.0,
                    min(
                        1.0,
                        float(
                            parameter(
                                parameters,
                                f"devcurve_layer_{name}_alpha",
                                default_alpha,
                            )
                        ),
                    ),
                ),
            )
            gl.glUniform1fv(
                uniforms[f"u_devcurve_curve_{name}"],
                _MAX_SAMPLES,
                _padded_samples(curves[name], sample_count=sample_count),
            )

        for index, name in enumerate(order):
            gl.glUniform1i(
                uniforms[f"u_devcurve_order{index}"],
                _LAYER_IDS[name],
            )
        gl.glUniform1i(
            uniforms["u_devcurve_foreground_layer_id"],
            max(-1, min(3, int(mode_state.foreground_layer_id))),
        )
        gl.glUniform1i(
            uniforms["u_devcurve_foreground_shadow_enabled"],
            1
            if bool(
                parameter(
                    parameters,
                    "devcurve_foreground_shadow_enabled",
                    False,
                )
            )
            else 0,
        )
        for uniform_name, parameter_name, default, minimum, maximum in (
            (
                "u_devcurve_foreground_shadow_alpha",
                "devcurve_foreground_shadow_alpha",
                0.36,
                0.0,
                1.0,
            ),
            (
                "u_devcurve_foreground_shadow_darken",
                "devcurve_foreground_shadow_darken",
                0.42,
                0.0,
                1.0,
            ),
            (
                "u_devcurve_foreground_shadow_offset",
                "devcurve_foreground_shadow_offset",
                0.10,
                0.0,
                0.45,
            ),
        ):
            value = max(
                minimum,
                min(maximum, float(parameter(parameters, parameter_name, default))),
            )
            if parameter_name.endswith("offset"):
                value *= layout.normalized_y_scale
            gl.glUniform1f(uniforms[uniform_name], value)

        gl.glUniform1i(
            uniforms["u_devcurve_foreground_specular_enabled"],
            1
            if bool(
                parameter(
                    parameters,
                    "devcurve_foreground_specular_enabled",
                    False,
                )
            )
            else 0,
        )
        specular_activity = max(
            0.0,
            min(
                1.0,
                float(
                    parameter(
                        parameters,
                        "devcurve_specular_activity_alpha",
                        1.0,
                    )
                ),
            ),
        )
        gl.glUniform1f(
            uniforms["u_devcurve_foreground_specular_alpha"],
            max(
                0.0,
                min(
                    1.0,
                    float(
                        parameter(
                            parameters,
                            "devcurve_foreground_specular_alpha",
                            0.78,
                        )
                    ),
                ),
            )
            * specular_activity,
        )
        gl.glUniform1f(
            uniforms["u_devcurve_foreground_specular_width"],
            max(
                0.002,
                min(
                    0.120,
                    float(
                        parameter(
                            parameters,
                            "devcurve_foreground_specular_width",
                            0.022,
                        )
                    )
                    * layout.normalized_x_scale,
                ),
            ),
        )
        gl.glUniform1f(
            uniforms["u_devcurve_foreground_specular_offset"],
            max(
                -0.20,
                min(
                    0.20,
                    float(
                        parameter(
                            parameters,
                            "devcurve_foreground_specular_offset",
                            0.028,
                        )
                    )
                    * layout.normalized_y_scale,
                ),
            ),
        )
        gl.glUniform1f(
            uniforms["u_devcurve_foreground_specular_crest_bias"],
            max(
                0.0,
                min(
                    2.0,
                    float(
                        parameter(
                            parameters,
                            "devcurve_foreground_specular_crest_bias",
                            1.05,
                        )
                    ),
                ),
            ),
        )
        slots = list(mode_state.specular_slots)
        while len(slots) < 3:
            slots.append(())
        for index, values in enumerate(slots[:3]):
            gl.glUniform4f(
                uniforms[f"u_devcurve_specular_slot{index}"],
                *_slot(values),
            )

        hue = 0.0
        if bool(parameter(parameters, "rainbow_enabled", False)):
            speed = max(
                0.01,
                min(5.0, float(parameter(parameters, "rainbow_speed", 0.5))),
            )
            hue = safe_hue(snapshot.logical.logical_timestamp * speed * 0.1)
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
        fragment_source = load_fragment_shader("devcurve")
        if fragment_source is None:
            raise RuntimeError("canonical DevCurve shader is unavailable")
        program = compile_program(
            QUICK_VISUALIZER_VERTEX_SOURCE,
            fragment_source,
            label="Quick DevCurve",
        )
        self._program = program
        try:
            required = [
                "uMatrix",
                "uItemSize",
                "u_resolution",
                "u_dpr",
                "u_viewport_origin_px",
                "u_quick_item_coords",
                "u_content_rect",
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
                required.extend(
                    (
                        f"u_devcurve_layer_{name}_color",
                        f"u_devcurve_layer_{name}_outline_color",
                        f"u_devcurve_layer_{name}_outline_width",
                        f"u_devcurve_layer_{name}_enabled",
                        f"u_devcurve_layer_{name}_alpha",
                        f"u_devcurve_curve_{name}",
                    )
                )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick DevCurve uniforms are incomplete: "
                    + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_visualizer_renderer() -> QuickDevCurveRenderer:
    return QuickDevCurveRenderer()


__all__ = [
    "QuickDevCurveLayout",
    "QuickDevCurveRenderer",
    "compute_quick_devcurve_layout",
    "create_visualizer_renderer",
]
