"""Lazy instanced micro-quad renderer for Directional Pixel Accretion."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.pixel_accretion_program import (
    PIXEL_ACCRETION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_MOTION_VERTEX_SOURCE,
    PIXEL_ACCRETION_QUAD_VERTICES,
    PIXEL_ACCRETION_VERTEX_SOURCE,
    pixel_accretion_grid,
    pixel_accretion_parameters,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress
from rendering.quick.scene3d.motion import motion_program, set_motion_uniforms
from rendering.quick.scene3d.resources import MeshResources, bind_frame
from rendering.quick.scene3d.target import SceneTarget
from ..directions import direction_vector
from ..render_contract import QuickTransitionRenderFrame


class QuickPixelAccretionRenderer:
    transition_id = "pixel_accretion"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Directional Pixel Accretion")
        self._target = SceneTarget("Quick Directional Pixel Accretion")

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
            self._initialize()
            parameters = frame.run.request.parameter_dict()
            seed, tile_size, travel = pixel_accretion_parameters(parameters)
            motion = bool(parameters.get("motion_blur", False))
            samples = scene3d_request_samples(parameters) or (1 if motion else 0)
            if samples:
                with self._target.scope(frame, samples, self._resources, motion_blur=motion):
                    self._draw_scene(frame, progress, seed, tile_size, travel, motion)
            else:
                self._draw_scene(frame, progress, seed, tile_size, travel, False)
        except Exception:
            self.release_resources()
            raise

    def _draw_scene(self, frame, progress: float, seed: int, tile_size: int, travel: float, motion: bool) -> None:
        columns, rows, _actual_size = pixel_accretion_grid(
            frame.viewport[2], frame.viewport[3], tile_size
        )
        self._resources.draw_image(frame, frame.source_texture_id)
        self._resources.begin_depth(frame)
        program, uniforms = motion_program(
            self._resources, "microquads", (PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE),
            (PIXEL_ACCRETION_MOTION_VERTEX_SOURCE, PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE),
            ("uMatrix", "uItemSize", "uNewTex", "uGrid", "uDirection", "uProgress", "uTravel", "uSeed"), motion,
        )
        bind_frame(program, uniforms, frame)
        gl.glUniform2f(uniforms["uGrid"], float(columns), float(rows))
        gl.glUniform2f(uniforms["uDirection"], *direction_vector(frame.run.request.direction))
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uTravel"], travel)
        gl.glUniform1f(uniforms["uSeed"], float(seed))
        if motion:
            set_motion_uniforms(uniforms, frame,
                                max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0))
        vao, count = self._resources.mesh("microquad", PIXEL_ACCRETION_QUAD_VERTICES, (2, 2))
        gl.glBindVertexArray(vao)
        with self._target.velocity_writes():
            gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, count, columns * rows)

    def park(self) -> None:
        """Drop the per-run scene target; the program and mesh stay warm."""
        self._target.release()

    def _initialize(self) -> None:
        self._resources.program(
            "microquads", PIXEL_ACCRETION_VERTEX_SOURCE, PIXEL_ACCRETION_FRAGMENT_SOURCE
        )

    def release_resources(self) -> None:
        self._target.release()
        self._resources.release_resources()


def create_transition_renderer() -> QuickPixelAccretionRenderer:
    return QuickPixelAccretionRenderer()
