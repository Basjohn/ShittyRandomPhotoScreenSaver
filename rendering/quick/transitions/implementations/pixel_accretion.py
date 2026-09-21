"""Lazy instanced micro-quad renderer for Directional Pixel Accretion."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.pixel_accretion_program import (
    PIXEL_ACCRETION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_QUAD_VERTICES,
    PIXEL_ACCRETION_VERTEX_SOURCE,
    pixel_accretion_grid,
    pixel_accretion_parameters,
)
from ..mesh_support import MeshResources, bind_frame, direction_vector
from ..render_contract import QuickTransitionRenderFrame


class QuickPixelAccretionRenderer:
    transition_id = "pixel_accretion"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Directional Pixel Accretion")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            self._initialize()
            seed, tile_size, travel = pixel_accretion_parameters(
                frame.run.request.parameter_dict()
            )
            columns, rows, _actual_size = pixel_accretion_grid(
                frame.viewport[2], frame.viewport[3], tile_size
            )
            self._resources.draw_image(frame, frame.source_texture_id)
            self._resources.begin_depth(frame)
            program = self._resources.program(
                "microquads", PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE
            )
            uniforms = self._resources.uniforms(
                "microquads", ("uMatrix", "uItemSize", "uNewTex", "uGrid", "uDirection", "uProgress", "uTravel", "uSeed")
            )
            bind_frame(program, uniforms, frame)
            gl.glUniform2f(uniforms["uGrid"], float(columns), float(rows))
            gl.glUniform2f(uniforms["uDirection"], *direction_vector(frame.run.request.direction))
            gl.glUniform1f(uniforms["uProgress"], progress)
            gl.glUniform1f(uniforms["uTravel"], travel)
            gl.glUniform1f(uniforms["uSeed"], float(seed))
            vao, count = self._resources.mesh("microquad", PIXEL_ACCRETION_QUAD_VERTICES, (2, 2))
            gl.glBindVertexArray(vao)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, columns * rows)
        except Exception:
            self.release_resources()
            raise

    def _initialize(self) -> None:
        self._resources.program(
            "microquads", PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE
        )

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickPixelAccretionRenderer:
    return QuickPixelAccretionRenderer()
