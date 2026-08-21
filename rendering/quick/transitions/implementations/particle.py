"""Lazy Quick renderer for the full authored Particle transition shader."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from OpenGL import GL as gl

from rendering.gl_programs.particle_program import particle_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


@dataclass(frozen=True, slots=True)
class _ParticleParameters:
    seed: float
    mode: int
    direction: int
    particle_radius: float
    overlap: float
    trail_length: float
    trail_strength: float
    swirl_strength: float
    swirl_turns: float
    use_3d_shading: bool
    texture_mapping: bool
    wobble: bool
    gloss_size: float
    light_direction: int
    swirl_order: int


def _number(parameters: Mapping[str, object], name: str) -> float:
    raw = parameters.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"Particle requires resolved numeric parameter {name!r}")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"Particle {name} must be finite")
    return value


def _integer(parameters: Mapping[str, object], name: str) -> int:
    raw = parameters.get(name)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"Particle requires resolved integer parameter {name!r}")
    return raw


def _boolean(parameters: Mapping[str, object], name: str) -> bool:
    raw = parameters.get(name)
    if not isinstance(raw, bool):
        raise ValueError(f"Particle requires resolved boolean parameter {name!r}")
    return raw


def _particle_parameters(parameters: Mapping[str, object]) -> _ParticleParameters:
    seed = _number(parameters, "seed")
    mode = _integer(parameters, "mode")
    if mode not in {0, 1, 2}:
        raise ValueError("Particle mode must already be resolved to 0, 1, or 2")
    direction = _integer(parameters, "direction")
    if not 0 <= direction <= 9:
        raise ValueError("Particle direction must be between 0 and 9")

    radius = _number(parameters, "particle_radius")
    if radius < 8.0:
        raise ValueError("Particle particle_radius must be at least 8")
    overlap = _number(parameters, "overlap")
    if overlap < 0.0 or overlap >= radius * 2.0:
        raise ValueError("Particle overlap must be non-negative and smaller than particle diameter")

    trail_length = _number(parameters, "trail_length")
    trail_strength = _number(parameters, "trail_strength")
    if not 0.0 <= trail_length <= 1.0:
        raise ValueError("Particle trail_length must be between 0 and 1")
    if not 0.0 <= trail_strength <= 1.0:
        raise ValueError("Particle trail_strength must be between 0 and 1")

    swirl_strength = _number(parameters, "swirl_strength")
    if swirl_strength < 0.0:
        raise ValueError("Particle swirl_strength must be non-negative")
    swirl_turns = _number(parameters, "swirl_turns")
    if swirl_turns < 0.5:
        raise ValueError("Particle swirl_turns must be at least 0.5")

    gloss_size = _number(parameters, "gloss_size")
    if not 16.0 <= gloss_size <= 128.0:
        raise ValueError("Particle gloss_size must be between 16 and 128")
    light_direction = _integer(parameters, "light_direction")
    if not 0 <= light_direction <= 4:
        raise ValueError("Particle light_direction must be between 0 and 4")
    swirl_order = _integer(parameters, "swirl_order")
    if not 0 <= swirl_order <= 2:
        raise ValueError("Particle swirl_order must be between 0 and 2")

    return _ParticleParameters(
        seed=seed,
        mode=mode,
        direction=direction,
        particle_radius=radius,
        overlap=overlap,
        trail_length=trail_length,
        trail_strength=trail_strength,
        swirl_strength=swirl_strength,
        swirl_turns=swirl_turns,
        use_3d_shading=_boolean(parameters, "use_3d_shading"),
        texture_mapping=_boolean(parameters, "texture_mapping"),
        wobble=_boolean(parameters, "wobble"),
        gloss_size=gloss_size,
        light_direction=light_direction,
        swirl_order=swirl_order,
    )


class QuickParticleRenderer:
    transition_id = "particle"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        params = _particle_parameters(frame.run.request.parameter_dict())
        uniforms = self._uniforms

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], float(frame.sample.eased_progress))
        gl.glUniform2f(
            uniforms["u_resolution"],
            float(frame.viewport[2]),
            float(frame.viewport[3]),
        )
        gl.glUniform1f(uniforms["u_seed"], params.seed)
        gl.glUniform1f(uniforms["u_mode"], float(params.mode))
        gl.glUniform1f(uniforms["u_direction"], float(params.direction))
        gl.glUniform1f(uniforms["u_particle_radius"], params.particle_radius)
        gl.glUniform1f(uniforms["u_overlap"], params.overlap)
        gl.glUniform1f(uniforms["u_trail_length"], params.trail_length)
        gl.glUniform1f(uniforms["u_trail_strength"], params.trail_strength)
        gl.glUniform1f(uniforms["u_swirl_strength"], params.swirl_strength)
        gl.glUniform1f(uniforms["u_swirl_turns"], params.swirl_turns)
        gl.glUniform1f(uniforms["u_use_3d"], 1.0 if params.use_3d_shading else 0.0)
        gl.glUniform1f(uniforms["u_texture_map"], 1.0 if params.texture_mapping else 0.0)
        gl.glUniform1f(uniforms["u_wobble"], 1.0 if params.wobble else 0.0)
        gl.glUniform1f(uniforms["u_gloss_size"], params.gloss_size)
        gl.glUniform1f(uniforms["u_light_dir"], float(params.light_direction))
        gl.glUniform1f(uniforms["u_swirl_order"], float(params.swirl_order))

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        program = compile_program(
            QUICK_TRANSITION_VERTEX_SOURCE,
            particle_program.fragment_source,
            label="Quick Particle",
        )
        self._program = program
        try:
            required = (
                "uMatrix", "uItemSize", "uOldTex", "uNewTex", "u_progress",
                "u_resolution", "u_seed", "u_mode", "u_direction",
                "u_particle_radius", "u_overlap", "u_trail_length",
                "u_trail_strength", "u_swirl_strength", "u_swirl_turns",
                "u_use_3d", "u_texture_map", "u_wobble", "u_gloss_size",
                "u_light_dir", "u_swirl_order",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Particle uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickParticleRenderer:
    return QuickParticleRenderer()
