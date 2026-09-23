"""Gravity melt renderer for Melt / Drip: the image melts from a chosen origin."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from OpenGL import GL as gl

from rendering.gl_programs.melt_drip_program import MELT_FRAGMENT_SOURCE
from ..mesh_support import MeshResources, bind_frame
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame

# Resolved melt origins: (screen origin with y down, mode 0 = spread from the
# point, 1 = melt from every edge toward the centre).
MELT_ORIGINS: dict[str, tuple[tuple[float, float], float]] = {
    "top_left": ((0.0, 0.0), 0.0),
    "top_center": ((0.5, 0.0), 0.0),
    "top_right": ((1.0, 0.0), 0.0),
    "center_out": ((0.5, 0.5), 0.0),
    "center_in": ((0.5, 0.5), 1.0),
}


@dataclass(frozen=True, slots=True)
class MeltDripParameters:
    seed: int
    detail: float
    depth: float
    gloss: float
    origin: tuple[float, float]
    origin_mode: float


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
    origin = MELT_ORIGINS.get(str(direction).strip().lower())
    if origin is None:
        raise ValueError(
            "Melt / Drip requires a resolved origin: " + ", ".join(MELT_ORIGINS)
        )
    return MeltDripParameters(
        seed,
        values["detail"],
        values["depth"],
        values["gloss"],
        origin[0],
        origin[1],
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
                    "uOrigin",
                    "uOriginMode",
                ),
            )
            bind_frame(program, u, frame)
            for name, value in (
                ("uProgress", frame.sample.eased_progress),
                ("uSeed", params.seed),
                ("uDetail", params.detail),
                ("uDepth", params.depth),
                ("uGloss", params.gloss),
                ("uOriginMode", params.origin_mode),
            ):
                gl.glUniform1f(u[name], float(value))
            gl.glUniform2f(u["uOrigin"], *params.origin)
            gl.glBindVertexArray(frame.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        except Exception:
            self.release_resources()
            raise

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickMeltDripRenderer:
    return QuickMeltDripRenderer()
