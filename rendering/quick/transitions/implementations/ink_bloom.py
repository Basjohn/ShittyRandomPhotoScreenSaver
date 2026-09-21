"""Lazy renderer for the finite marbled Ink Bloom transition."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
import math
from OpenGL import GL as gl
from rendering.gl_programs.ink_bloom_program import (
    INK_BLOOM_FRAGMENT_SOURCE,
    INK_BLOOM_VERTEX_SOURCE,
    ink_surface_vertices,
)
from ..mesh_support import MeshResources, bind_frame
from ..render_contract import QuickTransitionRenderFrame


@dataclass(frozen=True, slots=True)
class InkBloomParameters:
    seed: int
    detail: float
    depth: float
    gloss: float


def ink_bloom_parameters(parameters: Mapping[str, object]) -> InkBloomParameters:
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Ink Bloom seed must be an integer between 1 and 65535")
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
                f"Ink Bloom {name} must be finite and between {low:g} and {high:g}"
            )
        values.append(float(value))
    return InkBloomParameters(seed, *values)


class QuickInkBloomRenderer:
    transition_id = "ink_bloom"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Ink Bloom")
        self._aspect = None
        self._vao = self._count = 0

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        resources = self._resources
        progress = float(frame.sample.eased_progress)
        try:
            if progress <= 0.0 or progress >= 1.0:
                resources.draw_image(
                    frame,
                    frame.source_texture_id
                    if progress <= 0.0
                    else frame.destination_texture_id,
                )
                return
            params = ink_bloom_parameters(frame.run.request.parameter_dict())
            aspect = frame.logical_size[0] / frame.logical_size[1]
            if aspect != self._aspect:
                resources.drop_mesh("volume")
                self._vao, self._count = resources.mesh(
                    "volume", ink_surface_vertices(aspect), (2,)
                )
                self._aspect = aspect
            resources.draw_image(frame, frame.destination_texture_id)
            resources.begin_depth(frame)
            program = resources.program(
                "ink", INK_BLOOM_VERTEX_SOURCE, INK_BLOOM_FRAGMENT_SOURCE
            )
            uniforms = resources.uniforms(
                "ink",
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
                ),
            )
            bind_frame(program, uniforms, frame)
            for name, value in (
                ("uProgress", progress),
                ("uSeed", params.seed),
                ("uDetail", params.detail),
                ("uDepth", params.depth),
                ("uGloss", params.gloss),
            ):
                gl.glUniform1f(uniforms[name], float(value))
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)
        except Exception:
            self.release_resources()
            raise

    def release_resources(self) -> None:
        self._resources.release_resources()
        self._aspect = None
        self._vao = self._count = 0


def create_transition_renderer() -> QuickInkBloomRenderer:
    return QuickInkBloomRenderer()
