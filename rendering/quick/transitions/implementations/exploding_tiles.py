"""Lazy, instanced renderer for Exploding Tiles.

Four passes per frame, all analytic from the run's progress: the new photograph
lit by the blast, soft tile shadows on it (MIN-blended, 3D Detail permitting),
the beveled slabs (depth-tested), then additive sparks. Their shared per-frame
values travel in one uniform block. With anti-aliasing, bloom or motion blur the
passes render into a scene target that the host's park drops after the run; with
motion blur the slabs also write their screen motion over the shutter.
"""

from __future__ import annotations

from OpenGL import GL as gl
from rendering.gl_programs.exploding_tiles_program import (
    EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
    EXPLODING_TILES_BOX_VERTICES,
    EXPLODING_TILES_FRAGMENT_SOURCE,
    EXPLODING_TILES_FRAME_BLOCK,
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
from rendering.gl_programs.scene3d import scene3d_detail, scene3d_shutter_progress
from rendering.quick.scene3d.particles import draw_particles, particle_budget
from rendering.quick.scene3d.resources import MeshResources, bind_frame
from rendering.quick.scene3d.shadows import draw_planar_shadows
from rendering.quick.scene3d.target import SceneTarget
from rendering.quick.scene3d.uniforms import UniformBlock
from ..directions import direction_vector
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


class QuickExplodingTilesRenderer:
    transition_id = "exploding_tiles"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Exploding Tiles")
        self._target = SceneTarget("Quick Exploding Tiles")
        self._frame_block = UniformBlock(EXPLODING_TILES_FRAME_BLOCK, "Quick Exploding Tiles")
        self._body_key: tuple[int, str] | None = None
        self._body = (0.15, 0.15, 0.15)

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._frame_block.has_resources

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        try:
            if progress <= 0.0:
                self._resources.draw_image(frame, frame.source_texture_id)
                return
            if progress >= 1.0:
                self._resources.draw_image(frame, frame.destination_texture_id)
                return
            (seed, columns, depth, thickness, force, detail_name, samples, bloom,
             motion_blur) = exploding_tiles_parameters(frame.run.request.parameter_dict())
            # Multisampling, bloom and motion blur arrive resolved (this transition's settings
            # over the 3D Detail tier); the tier itself still sets shadows and the spark budget.
            detail = scene3d_detail(detail_name)
            samples = samples or (1 if bloom > 0.0 or motion_blur else 0)
            grid = exploding_tiles_grid(columns, frame.viewport[2], frame.viewport[3])
            direction = frame.run.request.direction
            center_out = str(direction) == "center_out"
            width, height = frame.logical_size
            epicentre = exploding_tiles_epicentre(
                None if center_out else direction_vector(direction), seed, width / height
            )
            values = {
                "uGrid": grid, "uProgress": progress, "uSeed": float(seed), "uDepth": depth,
                "uThickness": thickness, "uForce": force, "uCenterOut": 1 if center_out else 0,
                "uEpicentre": epicentre, "uSeconds": frame.run.request.duration_ms / 1000.0,
                "uBlast": exploding_tiles_blast(progress), "uBody": self._body_colour(frame),
                "uEmissive": 1.0 if samples and bloom > 0.0 else 0.0,
                "uShutter": scene3d_shutter_progress(frame.run.request.duration_ms) if motion_blur else 0.0,
                "uViewport": (float(frame.viewport[2]), float(frame.viewport[3])),
            }
            with self._frame_block.bound(values):
                if samples:
                    with self._target.scope(frame, samples, self._resources, bloom=bloom, motion_blur=motion_blur):
                        self._draw_scene(frame, grid, detail, progress, force, center_out)
                else:
                    self._draw_scene(frame, grid, detail, progress, force, center_out)
        except Exception:
            self.release_resources()
            raise

    def _draw_scene(self, frame, grid, detail, progress: float, force: float, center_out: bool) -> None:
        tiles = grid[0] * grid[1]
        self._draw_backdrop(frame)
        if detail.shadows:
            self._draw_shadows(frame, tiles)
        self._resources.begin_depth(frame)
        self._draw_tiles(frame, tiles)
        sparks = particle_budget(EXPLODING_TILES_SPARKS, detail)
        if sparks and exploding_tiles_sparks_live(progress, force, center_out):
            self._draw_sparks(frame, sparks)

    def _use(self, key: str, vertex: str, fragment: str, names: tuple[str, ...], frame) -> None:
        program = self._resources.program(key, vertex, fragment)
        self._frame_block.attach(program)
        bind_frame(program, self._resources.uniforms(key, names), frame)

    def _draw_backdrop(self, frame) -> None:
        self._use("backdrop", QUICK_TRANSITION_VERTEX_SOURCE, EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE,
                  ("uMatrix", "uItemSize", "uNewTex"), frame)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def _draw_shadows(self, frame, tiles: int) -> None:
        self._use("shadows", EXPLODING_TILES_SHADOW_VERTEX_SOURCE, EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE,
                  ("uMatrix", "uItemSize", "uNewTex"), frame)
        draw_planar_shadows(frame, tiles)

    def _draw_tiles(self, frame, tiles: int) -> None:
        self._use("tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE,
                  ("uMatrix", "uItemSize", "uOldTex"), frame)
        vao, count = self._resources.mesh("beveled_slab", EXPLODING_TILES_BOX_VERTICES, (3, 3, 2))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes():
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, tiles)

    def _draw_sparks(self, frame, count: int) -> None:
        self._use("sparks", EXPLODING_TILES_SPARK_VERTEX_SOURCE, EXPLODING_TILES_SPARK_FRAGMENT_SOURCE,
                  ("uMatrix", "uItemSize"), frame)
        draw_particles(frame, count)

    def _body_colour(self, frame) -> tuple[float, float, float]:
        """The source's most used colour, found once per run."""
        image = frame.run.request.source_image
        key = (frame.run.run_id, image.identity)
        if key != self._body_key:
            self._body = exploding_tiles_dominant_colour(image.rgba8, image.pixel_size, image.row_stride)
            self._body_key = key
        return self._body

    def park(self) -> None:
        """Drop the per-run scene target; programs, the slab mesh and the block stay warm."""
        self._target.release()

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._frame_block.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickExplodingTilesRenderer:
    return QuickExplodingTilesRenderer()
