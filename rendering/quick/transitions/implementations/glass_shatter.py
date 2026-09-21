"""Irregular glass shards, rendered inside the existing Quick transition host."""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.glass_shatter_program import (
    GLASS_FRAGMENT, GLASS_VERTEX, fracture_cells, fracture_vertices,
)
from ..mesh_support import MeshResources, bind_frame, direction_vector
from ..render_contract import QuickTransitionRenderFrame


class QuickGlassShatterRenderer:
    transition_id = "glass_shatter"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Glass Shatter")
        self._geometry_key = None
        self._vao = self._count = 0

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        resources = self._resources
        progress = float(frame.sample.eased_progress)
        try:
            resources.draw_image(frame, frame.source_texture_id if progress <= 0.0 else frame.destination_texture_id)
            if progress <= 0.0 or progress >= 1.0:
                return
            params = frame.run.request.parameter_dict()
            aspect = frame.logical_size[0] / frame.logical_size[1]
            key = (frame.run.run_id, params["seed"], params["shards"], aspect)
            if key != self._geometry_key:
                resources.drop_mesh("shards")
                vertices = fracture_vertices(fracture_cells(int(params["seed"]), int(params["shards"]), aspect), aspect)
                self._vao, self._count = resources.mesh("shards", vertices, (2, 2, 1, 1))
                self._geometry_key = key
            program = resources.program("glass", GLASS_VERTEX, GLASS_FRAGMENT)
            uniforms = resources.uniforms("glass", ("uMatrix", "uItemSize", "uOldTex", "uNewTex", "uProgress", "uDepth", "uDirection", "uRadial"))
            resources.begin_depth(frame)
            bind_frame(program, uniforms, frame)
            radial = frame.run.request.direction == "center_out"
            direction = (0.0, 0.0) if radial else direction_vector(frame.run.request.direction)
            gl.glUniform2f(uniforms["uDirection"], *direction)
            gl.glUniform1i(uniforms["uRadial"], int(radial))
            gl.glUniform1f(uniforms["uProgress"], progress)
            gl.glUniform1f(uniforms["uDepth"], float(params["depth"]))
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)
        except Exception:
            self.release_resources()
            raise

    def release_resources(self) -> None:
        self._resources.release_resources()
        self._geometry_key = None
        self._vao = self._count = 0


def create_transition_renderer() -> QuickGlassShatterRenderer:
    return QuickGlassShatterRenderer()
