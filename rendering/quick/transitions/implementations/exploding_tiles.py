"""Lazy, instanced beveled-slab renderer for Exploding Tiles."""

from __future__ import annotations

from OpenGL import GL as gl
from rendering.gl_programs.exploding_tiles_program import (
    EXPLODING_TILES_BOX_VERTICES,
    EXPLODING_TILES_FRAGMENT_SOURCE,
    EXPLODING_TILES_VERTEX_SOURCE,
    exploding_tiles_grid,
    exploding_tiles_parameters,
)
from ..mesh_support import MeshResources, bind_frame, direction_vector
from ..render_contract import QuickTransitionRenderFrame


class QuickExplodingTilesRenderer:
    transition_id = "exploding_tiles"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Exploding Tiles")

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
            seed, columns, depth, thickness, force = exploding_tiles_parameters(
                frame.run.request.parameter_dict()
            )
            grid = exploding_tiles_grid(columns, frame.viewport[2], frame.viewport[3])
            direction = frame.run.request.direction
            center_out = str(direction) == "center_out"
            vector = (0.0, 0.0) if center_out else direction_vector(direction)
            self._resources.draw_image(frame, frame.destination_texture_id)
            self._resources.begin_depth(frame)
            program = self._resources.program(
                "tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE
            )
            uniforms = self._resources.uniforms(
                "tiles",
                (
                    "uMatrix",
                    "uItemSize",
                    "uOldTex",
                    "uGrid",
                    "uDirection",
                    "uProgress",
                    "uSeed",
                    "uDepth",
                    "uThickness",
                    "uForce",
                    "uCenterOut",
                ),
            )
            bind_frame(program, uniforms, frame)
            gl.glUniform2f(uniforms["uGrid"], *grid)
            gl.glUniform2f(uniforms["uDirection"], *vector)
            gl.glUniform1f(uniforms["uProgress"], progress)
            gl.glUniform1f(uniforms["uSeed"], float(seed))
            gl.glUniform1f(uniforms["uDepth"], depth)
            gl.glUniform1f(uniforms["uThickness"], thickness)
            gl.glUniform1f(uniforms["uForce"], force)
            gl.glUniform1i(uniforms["uCenterOut"], 1 if center_out else 0)
            vao, count = self._resources.mesh(
                "beveled_slab", EXPLODING_TILES_BOX_VERTICES, (3, 3, 2)
            )
            gl.glBindVertexArray(vao)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, grid[0] * grid[1])
        except Exception:
            self.release_resources()
            raise

    def _initialize(self) -> None:
        self._resources.program(
            "tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE
        )

    def release_resources(self) -> None:
        self._resources.release_resources()


def create_transition_renderer() -> QuickExplodingTilesRenderer:
    return QuickExplodingTilesRenderer()
