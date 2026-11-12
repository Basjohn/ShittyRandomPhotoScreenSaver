"""Lazy instanced micro-quad renderer for Directional Pixel Accretion."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.pixel_accretion_program import (
    PIXEL_ACCRETION_BLOCK,
    PIXEL_ACCRETION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_GHOST_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_MOTION_BLOCK,
    PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_MOTION_VERTEX_SOURCE,
    PIXEL_ACCRETION_QUAD_VERTICES,
    PIXEL_ACCRETION_VERTEX_SOURCE,
    pixel_accretion_grid,
    pixel_accretion_parameters,
)
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import (
    SCENE3D_TRAIL_GHOSTS,
    scene3d_request_samples,
    scene3d_shutter_progress,
    scene3d_trail_ghosts,
)
from rendering.quick.scene3d.motion import motion_program, set_motion_values
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, draw_ghosts, trail_program
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..directions import direction_vector
from ..render_contract import QuickTransitionRenderFrame


class QuickPixelAccretionRenderer:
    transition_id = "pixel_accretion"

    def __init__(self) -> None:
        # A ghost pass gives each of its draws its own pass block copy.
        self._resources = MeshResources("Quick Directional Pixel Accretion", copies=SCENE3D_TRAIL_GHOSTS)
        self._target = SceneTarget("Quick Directional Pixel Accretion")
        self._trails = MotionTrails("Quick Directional Pixel Accretion")

    @property
    def has_resources(self) -> bool:
        return self._resources.has_resources or self._target.has_resources or self._trails.has_resources

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
            parameters = frame.run.request.parameter_dict()
            seed, tile_size, travel = pixel_accretion_parameters(parameters)
            motion = bool(parameters.get("motion_blur", False))
            trails = bool(parameters.get("motion_trails", False))
            samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
            if samples:
                with self._target.scope(frame, samples, self._resources, motion_blur=motion):
                    self._draw_scene(frame, progress, seed, tile_size, travel, motion, trails)
            else:
                self._draw_scene(frame, progress, seed, tile_size, travel, False)
        except Exception:
            self.release_resources()
            raise

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        r = self._resources
        # render() always prepares the plain program (``_initialize``), motion blur or not.
        entries = [(r, *UNDERLAY_PROGRAM),
                   (r, "microquads", PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE)]
        if motion:
            entries.append((r, "microquads_motion", PIXEL_ACCRETION_MOTION_VERTEX_SOURCE,
                            PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE))
        if trails:
            entries += [(r, "microquads_ghost", PIXEL_ACCRETION_MOTION_VERTEX_SOURCE, PIXEL_ACCRETION_GHOST_FRAGMENT_SOURCE),
                        (r, *TRAIL_EDGES_PROGRAM)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, motion)]
        if not warm_programs(entries):
            return False
        if not warm_pass_blocks(self._resources, size):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion,
                                  bloom=False, with_trails=trails)

    def _draw_scene(self, frame, progress: float, seed: int, tile_size: int, travel: float, motion: bool,
                    trails: bool = False) -> None:
        self._resources.draw_image(frame, frame.source_texture_id)
        if trails:
            self._trails.draw(self._target, frame, self._resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms),
                              lambda ghosts: self._draw_tile_ghosts(frame, ghosts, seed, tile_size, travel, progress))
        self._resources.begin_depth(frame)
        self._draw_tiles(frame, progress, seed, tile_size, travel, motion)

    # The photograph bind_frame binds (unit 1); every other value is in the program's pass block.
    _TILE_SAMPLERS = ("uNewTex",)

    @staticmethod
    def _tile_values(values: dict, frame, columns: int, rows: int, seed: int, travel: float) -> None:
        values["uGrid"] = (float(columns), float(rows))
        values["uDirection"] = direction_vector(frame.run.request.direction)
        values["uTravel"] = travel
        values["uSeed"] = float(seed)

    def _draw_tiles(self, frame, progress: float, seed: int, tile_size: int, travel: float, motion: bool) -> None:
        columns, rows, _actual_size = pixel_accretion_grid(
            frame.viewport[2], frame.viewport[3], tile_size
        )
        program, uniforms, values, block = motion_program(
            self._resources, "microquads",
            (PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE, PIXEL_ACCRETION_BLOCK),
            (PIXEL_ACCRETION_MOTION_VERTEX_SOURCE, PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE, PIXEL_ACCRETION_MOTION_BLOCK),
            self._TILE_SAMPLERS, motion,
        )
        bind_frame(program, uniforms, frame, values)
        self._tile_values(values, frame, columns, rows, seed, travel)
        values["uProgress"] = progress
        if motion:
            set_motion_values(values, frame,
                              max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0))
        vao, count = self._resources.mesh("microquad", PIXEL_ACCRETION_QUAD_VERTICES, (2, 2))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes(), self._resources.pass_blocks.bound(pack_block(block, values)):
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, columns * rows)

    def _draw_tile_ghosts(self, frame, ghosts, seed: int, tile_size: int, travel: float, now: float) -> None:
        """Bind the micro-tile ghost pass once; only ghost time and fade vary."""
        columns, rows, _actual_size = pixel_accretion_grid(frame.viewport[2], frame.viewport[3], tile_size)
        program, uniforms = trail_program(
            self._resources, "microquads", PIXEL_ACCRETION_MOTION_VERTEX_SOURCE,
            PIXEL_ACCRETION_GHOST_FRAGMENT_SOURCE, self._TILE_SAMPLERS,
        )
        values = self._resources.values("microquads_ghost")
        bind_frame(program, uniforms, frame, values)
        self._tile_values(values, frame, columns, rows, seed, travel)
        set_motion_values(values, frame, now)
        vao, count = self._resources.mesh("microquad", PIXEL_ACCRETION_QUAD_VERTICES, (2, 2))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes():
            draw_ghosts(self._resources.pass_blocks, PIXEL_ACCRETION_MOTION_BLOCK, values, ghosts,
                        lambda time: {"uProgress": time},
                        lambda: gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, columns * rows))

    def park(self) -> None:
        """Drop the per-run scene target and trails; the program and mesh stay warm."""
        self._target.release()
        self._trails.release()

    def _initialize(self) -> None:
        self._resources.program(
            "microquads", PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE
        )

    def release_resources(self) -> None:
        self._target.release()
        self._trails.release()
        self._resources.release_resources()


def create_transition_renderer() -> QuickPixelAccretionRenderer:
    return QuickPixelAccretionRenderer()
