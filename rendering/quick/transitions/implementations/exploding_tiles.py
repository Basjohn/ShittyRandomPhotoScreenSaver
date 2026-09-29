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
    EXPLODING_TILES_GHOST_FRAGMENT_SOURCE,
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
from rendering.gl_programs.scene3d import scene3d_detail, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.particles import draw_particles, particle_budget
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.shadows import draw_planar_shadows
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, trail_program
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from rendering.quick.scene3d.uniforms import UniformBlock
from ..directions import direction_vector
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


class QuickExplodingTilesRenderer:
    transition_id = "exploding_tiles"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Exploding Tiles")
        self._target = SceneTarget("Quick Exploding Tiles")
        self._environment = PhotoEnvironment("Quick Exploding Tiles")   # photo reflections
        self._trails = MotionTrails("Quick Exploding Tiles")
        # The ghosts' frame values (their own buffer, so the real tiles keep theirs).
        self._ghost_block = UniformBlock(EXPLODING_TILES_FRAME_BLOCK, "Quick Exploding Tiles ghosts")
        self._frame_block = UniformBlock(EXPLODING_TILES_FRAME_BLOCK, "Quick Exploding Tiles")
        self._body_key: tuple[int, str] | None = None
        self._body = (0.15, 0.15, 0.15)

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._frame_block.has_resources
                or self._environment.has_resources or self._trails.has_resources or self._ghost_block.has_resources)

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
             motion_blur, trails) = exploding_tiles_parameters(frame.run.request.parameter_dict())
            # Multisampling, bloom and motion blur arrive resolved (this transition's settings
            # over the 3D Detail tier); the tier itself still sets shadows and the spark budget.
            detail = scene3d_detail(detail_name)
            samples = samples or (1 if bloom > 0.0 or motion_blur or trails else 0)
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
            environment = self._environment.texture(frame, self._resources)
            with self._frame_block.bound(values):
                if samples:
                    with self._target.scope(frame, samples, self._resources, bloom=bloom, motion_blur=motion_blur):
                        self._draw_scene(frame, grid, detail, progress, force, center_out, environment,
                                         values if trails else None)
                else:
                    self._draw_scene(frame, grid, detail, progress, force, center_out, environment)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        (_seed, _columns, _depth, _thickness, _force, detail_name, samples, bloom,
         motion_blur, trails) = exploding_tiles_parameters(parameters)
        detail = scene3d_detail(detail_name)
        samples = samples or (1 if bloom > 0.0 or motion_blur or trails else 0)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM), (r, *PHOTO_ENVIRONMENT_PROGRAM),
                   (r, "backdrop", QUICK_TRANSITION_VERTEX_SOURCE, EXPLODING_TILES_BACKDROP_FRAGMENT_SOURCE)]
        if detail.shadows:
            entries.append((r, "shadows", EXPLODING_TILES_SHADOW_VERTEX_SOURCE, EXPLODING_TILES_SHADOW_FRAGMENT_SOURCE))
        entries.append((r, "tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE))
        if particle_budget(EXPLODING_TILES_SPARKS, detail):
            entries.append((r, "sparks", EXPLODING_TILES_SPARK_VERTEX_SOURCE, EXPLODING_TILES_SPARK_FRAGMENT_SOURCE))
        if trails:
            entries += [(r, "tiles_ghost", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_GHOST_FRAGMENT_SOURCE),
                        (r, *TRAIL_EDGES_PROGRAM)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, bloom > 0.0, motion_blur)]
        if not warm_programs(entries):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion_blur,
                                  bloom=bloom > 0.0, with_trails=trails)

    def _draw_scene(self, frame, grid, detail, progress: float, force: float, center_out: bool,
                    environment: int, trail_values=None) -> None:
        tiles = grid[0] * grid[1]
        self._draw_backdrop(frame)
        if detail.shadows:
            self._draw_shadows(frame, tiles)
        if trail_values is not None:
            def ghost(time, fade):
                # A negative shutter: the ghost's vertex stage also finds where each tile is now.
                values = {**trail_values, "uProgress": time, "uBlast": exploding_tiles_blast(time),
                          "uShutter": time - progress}
                with self._ghost_block.bound(values):
                    self._draw_tiles(frame, tiles, environment, fade)
            self._trails.draw(self._target, frame, self._resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms), ghost)
        self._resources.begin_depth(frame)
        self._draw_tiles(frame, tiles, environment)
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

    _TILE_UNIFORMS = ("uMatrix", "uItemSize", "uOldTex", "uEnvironment")

    def _draw_tiles(self, frame, tiles: int, environment: int, ghost: float | None = None) -> None:
        if ghost is not None:
            program, uniforms = trail_program(self._resources, "tiles", EXPLODING_TILES_VERTEX_SOURCE,
                                              EXPLODING_TILES_GHOST_FRAGMENT_SOURCE, self._TILE_UNIFORMS)
            self._frame_block.attach(program)
            bind_frame(program, uniforms, frame)
            gl.glUniform1f(uniforms["uGhostFade"], ghost)
        else:
            self._use("tiles", EXPLODING_TILES_VERTEX_SOURCE, EXPLODING_TILES_FRAGMENT_SOURCE,
                      self._TILE_UNIFORMS, frame)
            uniforms = self._resources.uniforms("tiles", self._TILE_UNIFORMS)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
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
        """Drop the per-run target, environment and trails; programs, the slab mesh and the block stay warm."""
        self._target.release()
        self._environment.release()
        self._trails.release()

    def release_resources(self) -> None:
        errors: list[str] = []
        for release in (self._target.release, self._environment.release, self._trails.release,
                        self._frame_block.release, self._ghost_block.release, self._resources.release_resources):
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(" | ".join(errors))


def create_transition_renderer() -> QuickExplodingTilesRenderer:
    return QuickExplodingTilesRenderer()
