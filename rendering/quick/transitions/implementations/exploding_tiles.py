"""Lazy, instanced renderer for Exploding Tiles.

Four passes per frame, all analytic from the run's progress: the new photograph
lit by the blast, soft tile shadows on it (MIN-blended, 3D Detail permitting),
the beveled slabs (depth-tested), then additive sparks. On High the passes
render into a multisampled scene target that the host's park drops after the run.
"""

from __future__ import annotations

from OpenGL import GL as gl
from rendering.gl_programs.exploding_tiles_program import (
    EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
    EXPLODING_TILES_BOX_VERTICES,
    EXPLODING_TILES_FRAGMENT_SOURCE,
    EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE,
    EXPLODING_TILES_SHADOW_VERTEX_SOURCE,
    EXPLODING_TILES_SPARK_FRAGMENT_SOURCE,
    EXPLODING_TILES_SPARK_VERTEX_SOURCE,
    EXPLODING_TILES_SPARKS,
    EXPLODING_TILES_VERTEX_SOURCE,
    exploding_tiles_blast,
    exploding_tiles_dominant_colour,
    exploding_tiles_epicentre,
    exploding_tiles_grid,
    exploding_tiles_parameters,
    exploding_tiles_sparks_live,
)
from rendering.gl_programs.scene3d import scene3d_detail
from rendering.quick.scene3d.passes import blend_scope
from rendering.quick.scene3d.resources import MeshResources, bind_frame
from rendering.quick.scene3d.target import SceneTarget
from ..directions import direction_vector
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame

_MOTION_UNIFORMS = (
    "uMatrix", "uItemSize", "uGrid", "uProgress", "uSeed",
    "uDepth", "uThickness", "uForce", "uCenterOut", "uEpicentre", "uSeconds",
)


class QuickExplodingTilesRenderer:
    transition_id = "exploding_tiles"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Exploding Tiles")
        self._target = SceneTarget("Quick Exploding Tiles")
        self._body_key: tuple[int, str] | None = None
        self._body = (0.15, 0.15, 0.15)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            seed, columns, depth, thickness, force, detail_name = exploding_tiles_parameters(
                frame.run.request.parameter_dict()
            )
            detail = scene3d_detail(detail_name)
            grid = exploding_tiles_grid(columns, frame.viewport[2], frame.viewport[3])
            direction = frame.run.request.direction
            center_out = str(direction) == "center_out"
            width, height = frame.logical_size
            epicentre = exploding_tiles_epicentre(
                None if center_out else direction_vector(direction), seed, width / height
            )
            blast = exploding_tiles_blast(progress)
            seconds = frame.run.request.duration_ms / 1000.0
            motion = (grid, progress, seed, depth, thickness, force, center_out, epicentre, seconds)
            if detail.samples:
                with self._target.scope(frame, detail.samples, self._resources):
                    self._draw_scene(frame, motion, blast, detail)
            else:
                self._draw_scene(frame, motion, blast, detail)
        except Exception:
            self.release_resources()
            raise

    def _draw_scene(self, frame, motion, blast, detail) -> None:
        _grid, progress, _seed, _depth, _thickness, force, center_out, epicentre, _seconds = motion
        self._draw_backdrop(frame, epicentre, blast)
        if detail.shadows:
            self._draw_shadows(frame, motion, blast)
        self._resources.begin_depth(frame)
        self._draw_tiles(frame, motion, blast)
        sparks = round(EXPLODING_TILES_SPARKS * detail.particles)
        if sparks and exploding_tiles_sparks_live(progress, force, center_out):
            self._draw_sparks(frame, motion, sparks)

    def _program(self, key: str, vertex: str, fragment: str, names: tuple[str, ...]):
        program = self._resources.program(key, vertex, fragment)
        return program, self._resources.uniforms(key, names)

    @staticmethod
    def _set_motion(uniforms: dict[str, int], motion) -> None:
        grid, progress, seed, depth, thickness, force, center_out, epicentre, seconds = motion
        gl.glUniform2f(uniforms["uGrid"], *grid)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uSeed"], float(seed))
        gl.glUniform1f(uniforms["uDepth"], depth)
        gl.glUniform1f(uniforms["uThickness"], thickness)
        gl.glUniform1f(uniforms["uForce"], force)
        gl.glUniform1i(uniforms["uCenterOut"], 1 if center_out else 0)
        gl.glUniform3f(uniforms["uEpicentre"], *epicentre)
        gl.glUniform1f(uniforms["uSeconds"], seconds)

    def _draw_backdrop(self, frame, epicentre, blast) -> None:
        program, uniforms = self._program(
            "backdrop", QUICK_TRANSITION_VERTEX_SOURCE, EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
            ("uMatrix", "uItemSize", "uNewTex", "uEpicentre", "uBlast"),
        )
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        bind_frame(program, uniforms, frame)
        gl.glUniform3f(uniforms["uEpicentre"], *epicentre)
        gl.glUniform2f(uniforms["uBlast"], *blast)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def _draw_shadows(self, frame, motion, blast) -> None:
        program, uniforms = self._program(
            "shadows", EXPLODING_TILES_SHADOW_VERTEX_SOURCE, EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE,
            _MOTION_UNIFORMS + ("uNewTex", "uBlast"),
        )
        bind_frame(program, uniforms, frame)
        self._set_motion(uniforms, motion)
        gl.glUniform2f(uniforms["uBlast"], *blast)
        gl.glBindVertexArray(frame.quad_vao)
        grid = motion[0]
        with blend_scope(gl.GL_MIN):
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, grid[0] * grid[1])

    def _draw_tiles(self, frame, motion, blast) -> None:
        program, uniforms = self._program(
            "tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE,
            _MOTION_UNIFORMS + ("uOldTex", "uBlast", "uBody"),
        )
        bind_frame(program, uniforms, frame)
        self._set_motion(uniforms, motion)
        gl.glUniform2f(uniforms["uBlast"], *blast)
        gl.glUniform3f(uniforms["uBody"], *self._body_colour(frame))
        vao, count = self._resources.mesh("beveled_slab", EXPLODING_TILES_BOX_VERTICES, (3, 3, 2))
        gl.glBindVertexArray(vao)
        grid = motion[0]
        gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, grid[0] * grid[1])

    def _body_colour(self, frame) -> tuple[float, float, float]:
        """The source's most used colour, found once per run."""
        image = frame.run.request.source_image
        key = (frame.run.run_id, image.identity)
        if key != self._body_key:
            self._body = exploding_tiles_dominant_colour(image.rgba8, image.pixel_size, image.row_stride)
            self._body_key = key
        return self._body

    def _draw_sparks(self, frame, motion, count: int) -> None:
        program, uniforms = self._program(
            "sparks", EXPLODING_TILES_SPARK_VERTEX_SOURCE, EXPLODING_TILES_SPARK_FRAGMENT_SOURCE,
            ("uMatrix", "uItemSize", "uProgress", "uSeed", "uForce", "uCenterOut", "uEpicentre"),
        )
        _grid, progress, seed, _depth, _thickness, force, center_out, epicentre, _seconds = motion
        bind_frame(program, uniforms, frame)
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uSeed"], float(seed))
        gl.glUniform1f(uniforms["uForce"], force)
        gl.glUniform1i(uniforms["uCenterOut"], 1 if center_out else 0)
        gl.glUniform3f(uniforms["uEpicentre"], *epicentre)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBindVertexArray(frame.quad_vao)
        with blend_scope(gl.GL_FUNC_ADD):
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, count)

    def park(self) -> None:
        """Drop the per-run scene target; programs and the slab mesh stay warm."""
        self._target.release()

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickExplodingTilesRenderer:
    return QuickExplodingTilesRenderer()
