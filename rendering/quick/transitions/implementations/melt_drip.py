"""Bounded implicit-liquid renderer for Melt / Drip."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from OpenGL import GL as gl

from rendering.gl_programs.melt_drip_program import MELT_FRAGMENT_SOURCE
from ..mesh_support import MeshResources, bind_frame, direction_vector
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


@dataclass(frozen=True, slots=True)
class MeltDripParameters:
    seed: int
    detail: float
    depth: float
    gloss: float
    direction: tuple[float, float]


def melt_drip_parameters(
    parameters: Mapping[str, object], direction: object
) -> MeltDripParameters:
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Melt / Drip seed must be an integer between 1 and 65535")
    values: dict[str, float] = {}
    for name, lower, upper in (
        ("detail", 0.5, 2.0),
        ("depth", 0.0, 1.0),
        ("gloss", 0.0, 1.0),
    ):
        value = parameters.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"Melt / Drip {name} must be finite and numeric")
        numeric = float(value)
        if not lower <= numeric <= upper:
            raise ValueError(
                f"Melt / Drip {name} must be between {lower:g} and {upper:g}"
            )
        values[name] = numeric
    if str(direction).strip().lower() not in {"down", "up", "left", "right"}:
        raise ValueError(
            "Melt / Drip requires resolved direction down, up, left, or right"
        )
    return MeltDripParameters(
        seed,
        values["detail"],
        values["depth"],
        values["gloss"],
        direction_vector(direction),
    )


class QuickMeltDripRenderer:
    transition_id = "melt_drip"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Melt Drip")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        try:
            params = melt_drip_parameters(
                frame.run.request.parameter_dict(), frame.run.request.direction
            )
            program = self._resources.program(
                "liquid", QUICK_TRANSITION_VERTEX_SOURCE, MELT_FRAGMENT_SOURCE
            )
            u = self._resources.uniforms(
                "liquid",
                (
                    "uMatrix",
                    "uItemSize",
                    "uOldTex",
                    "uNewTex",
                    "uProgress",
                    "uSeed",
                    "uDetail",
                    "uDepth",
                    "uGloss",
                    "uDirection",
                ),
            )
            bind_frame(program, u, frame)
            for name, value in (
                ("uProgress", frame.sample.eased_progress),
                ("uSeed", params.seed),
                ("uDetail", params.detail),
                ("uDepth", params.depth),
                ("uGloss", params.gloss),
            ):
                gl.glUniform1f(u[name], float(value))
            gl.glUniform2f(u["uDirection"], *params.direction)
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        except Exception:
            self.release_resources()
            raise

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickMeltDripRenderer:
    return QuickMeltDripRenderer()
