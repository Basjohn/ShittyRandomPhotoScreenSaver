"""The bendable grid surface: a subdivided photograph an effect bends in its vertex shader.

The mesh is static (``scene3d_grid_vertices``), built once per size and reused; its
density comes from the 3D Detail tier (``scene3d_grid_size``), the main cost lever of
any bending effect. The effect's program is ``scene3d_grid_vertex_source`` around its
own ``sceneDisplace`` plus its own fragment shader (``vUv``, ``vWorld``, ``vNormal``).
"""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import scene3d_grid_vertices


def draw_grid(resources, columns: int, rows: int) -> None:
    """Draw the grid with the program already in use (its ``uGridCells`` set by the caller)."""
    vao, count = resources.mesh(f"scene_grid_{columns}x{rows}", scene3d_grid_vertices(columns, rows), (2,))
    gl.glBindVertexArray(vao)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
