"""Lazy finite tube renderer for the sculptural Tendril Reveal transition."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
import ctypes
import math
from OpenGL import GL as gl
from rendering.gl_programs.tendril_reveal_program import (
    TENDRIL_CANOPY_FRAGMENT,
    TENDRIL_FRAGMENT,
    TENDRIL_VERTEX,
    tendril_branches,
    tendril_canopy_segments,
    tendril_tube_vertices,
)
from ..mesh_support import MeshResources, bind_frame
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


@dataclass(frozen=True, slots=True)
class TendrilRevealParameters:
    seed: int
    detail: float
    depth: float
    gloss: float


def tendril_reveal_parameters(
    parameters: Mapping[str, object],
) -> TendrilRevealParameters:
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Tendril Reveal seed must be an integer between 1 and 65535")
    values = []
    for name, low, high in (
        ("detail", 0.5, 2.0),
        ("depth", 0.0, 1.0),
        ("gloss", 0.0, 1.0),
    ):
        value = parameters.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or not low <= float(value) <= high
        ):
            raise ValueError(
                f"Tendril Reveal {name} must be finite and between {low:g} and {high:g}"
            )
        values.append(float(value))
    return TendrilRevealParameters(seed, *values)


class QuickTendrilRevealRenderer:
    transition_id = "tendril_reveal"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Tendril Reveal")
        self._geometry_key = None
        self._canopy_key = None
        self._vao = self._count = 0

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = float(frame.sample.eased_progress)
        resources = self._resources
        try:
            if progress >= 1.0:
                resources.draw_image(frame, frame.destination_texture_id)
                return
            resources.draw_image(frame, frame.source_texture_id)
            if progress <= 0.0:
                return
            p = tendril_reveal_parameters(frame.run.request.parameter_dict())
            aspect = frame.logical_size[0] / frame.logical_size[1]
            key = (frame.run.run_id, p.seed, p.detail, aspect)
            if key != self._geometry_key:
                resources.drop_mesh("tubes")
                branches = tendril_branches(p.seed, p.detail)
                vertices = tendril_tube_vertices(branches, aspect=aspect)
                self._vao, self._count = resources.mesh(
                    "tubes", vertices, (3, 2, 3, 3, 1)
                )
                self._geometry_key = key
                self._canopy_segments = tendril_canopy_segments(branches)
                self._canopy_key = None
            self._draw_canopy(frame, p, progress, key)
            program = resources.program("tubes", TENDRIL_VERTEX, TENDRIL_FRAGMENT)
            uniforms = resources.uniforms(
                "tubes",
                ("uMatrix", "uItemSize", "uNewTex", "uProgress", "uDepth", "uGloss"),
            )
            resources.begin_depth(frame)
            bind_frame(program, uniforms, frame)
            gl.glUniform1f(uniforms["uProgress"], progress)
            gl.glUniform1f(uniforms["uDepth"], p.depth)
            gl.glUniform1f(uniforms["uGloss"], p.gloss)
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)
        except Exception:
            self.release_resources()
            raise

    def release_resources(self) -> None:
        self._resources.release_resources()
        self._geometry_key = None
        self._canopy_key = None
        self._vao = self._count = 0

    def _draw_canopy(
        self,
        frame: QuickTransitionRenderFrame,
        params: TendrilRevealParameters,
        progress: float,
        geometry_key: tuple[object, ...],
    ) -> None:
        resources = self._resources
        program = resources.program(
            "canopy", QUICK_TRANSITION_VERTEX_SOURCE, TENDRIL_CANOPY_FRAGMENT
        )
        uniforms = resources.uniforms(
            "canopy",
            (
                "uMatrix",
                "uItemSize",
                "uOldTex",
                "uNewTex",
                "uProgress",
                "uDetail",
                "uDepth",
                "uGloss",
                "uAspect",
                "uSegmentCount",
                "uSegmentsA[0]",
                "uSegmentsB[0]",
            ),
        )
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uDetail"], params.detail)
        gl.glUniform1f(uniforms["uDepth"], params.depth)
        gl.glUniform1f(uniforms["uGloss"], params.gloss)
        gl.glUniform1f(
            uniforms["uAspect"], frame.logical_size[0] / frame.logical_size[1]
        )
        if self._canopy_key != geometry_key:
            starts, ends = self._canopy_segments
            segment_count = len(starts) // 4
            gl.glUniform1i(uniforms["uSegmentCount"], segment_count)
            gl.glUniform4fv(
                uniforms["uSegmentsA[0]"],
                segment_count,
                (ctypes.c_float * len(starts))(*starts),
            )
            gl.glUniform4fv(
                uniforms["uSegmentsB[0]"],
                segment_count,
                (ctypes.c_float * len(ends))(*ends),
            )
            self._canopy_key = geometry_key
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)


def create_transition_renderer() -> QuickTendrilRevealRenderer:
    return QuickTendrilRevealRenderer()
