"""Irregular glass shards, rendered inside the existing Quick transition host."""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.glass_shatter_program import (
    GLASS_FRAGMENT, GLASS_GHOST_FRAGMENT, GLASS_MOTION_FRAGMENT, GLASS_MOTION_VERTEX, GLASS_VERTEX,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.environment import PhotoEnvironment
from rendering.quick.scene3d.motion import motion_program, motion_uniform_names, set_motion_uniforms
from rendering.quick.scene3d.trails import MotionTrails, trail_program
from rendering.quick.scene3d.resources import MeshResources, bind_frame
from rendering.quick.scene3d.target import SceneTarget
from ..directions import direction_vector
from ..render_contract import QuickTransitionRenderFrame
from ..run_geometry import (
    GLASS_ATTRIBUTES,
    PREPARED_GEOMETRY,
    build_glass_geometry,
    glass_geometry_key,
)


class QuickGlassShatterRenderer:
    transition_id = "glass_shatter"

    def __init__(self) -> None:
        self._resources = MeshResources("Quick Glass Shatter")
        self._target = SceneTarget("Quick Glass Shatter")
        self._environment = PhotoEnvironment("Quick Glass Shatter")   # photo reflections
        self._trails = MotionTrails("Quick Glass Shatter")
        self._geometry_key = None
        self._vao = self._count = 0

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._environment.has_resources
                or self._trails.has_resources)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        resources = self._resources
        progress = float(frame.sample.eased_progress)
        try:
            if progress <= 0.0 or progress >= 1.0:
                resources.draw_image(frame, frame.source_texture_id if progress <= 0.0 else frame.destination_texture_id)
                return
            params = frame.run.request.parameter_dict()
            aspect = frame.logical_size[0] / frame.logical_size[1]
            geometry_key = glass_geometry_key(params, aspect, frame.run.request.direction)
            key = (frame.run.run_id, geometry_key)
            if key != self._geometry_key:
                resources.drop_mesh("shards")
                geometry = PREPARED_GEOMETRY.get_or_build(geometry_key, build_glass_geometry)
                self._vao, self._count = resources.mesh("shards", geometry.vertices, GLASS_ATTRIBUTES)
                self._geometry_key = key
            motion = bool(params.get("motion_blur", False))
            trails = bool(params.get("motion_trails", False))
            samples = scene3d_request_samples(params) or (1 if motion or trails else 0)
            # Sheen zero removes all reflection, so no environment is needed then.
            environment = self._environment.texture(frame, resources) if float(params["sheen"]) > 0.0 else 0
            if samples:
                with self._target.scope(frame, samples, resources, motion_blur=motion):
                    self._draw_scene(frame, progress, params, motion, environment, trails)
            else:
                self._draw_scene(frame, progress, params, False, environment)
        except Exception:
            self.release_resources()
            raise

    def _draw_scene(self, frame, progress: float, params, motion: bool, environment: int,
                    trails: bool = False) -> None:
        resources = self._resources
        resources.draw_image(frame, frame.destination_texture_id)
        if trails:
            self._trails.draw(self._target, frame, resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms),
                              lambda time, fade: self._draw_shards(frame, time, params, False, environment,
                                                                   (fade, progress)))
        resources.begin_depth(frame)
        self._draw_shards(frame, progress, params, motion, environment)

    _SHARD_UNIFORMS = (
        "uMatrix", "uItemSize", "uOldTex", "uNewTex", "uProgress", "uDepth", "uDirection", "uRadial",
        "uThickness", "uTransparency", "uRefraction", "uDispersion", "uSheen", "uEnvironment",
    )

    def _draw_shards(self, frame, progress: float, params, motion: bool, environment: int,
                     ghost: tuple[float, float] | None = None) -> None:
        """``ghost``: (fade, the moment now) to draw the shards as a motion-trail ghost."""
        resources = self._resources
        if ghost is not None:
            program, uniforms = trail_program(resources, "glass", GLASS_MOTION_VERTEX, GLASS_GHOST_FRAGMENT,
                                              self._SHARD_UNIFORMS + motion_uniform_names())
        else:
            program, uniforms = motion_program(resources, "glass", (GLASS_VERTEX, GLASS_FRAGMENT),
                                               (GLASS_MOTION_VERTEX, GLASS_MOTION_FRAGMENT), self._SHARD_UNIFORMS,
                                               motion)
        bind_frame(program, uniforms, frame)
        radial = frame.run.request.direction == "center_out"
        direction = (0.0, 0.0) if radial else direction_vector(frame.run.request.direction)
        gl.glUniform2f(uniforms["uDirection"], *direction)
        gl.glUniform1i(uniforms["uRadial"], int(radial))
        gl.glUniform1f(uniforms["uProgress"], progress)
        gl.glUniform1f(uniforms["uDepth"], float(params["depth"]))
        for name in ("thickness", "transparency", "refraction", "dispersion", "sheen"):
            gl.glUniform1f(uniforms["u" + name.capitalize()], float(params[name]))
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        if ghost is not None:
            gl.glUniform1f(uniforms["uGhostFade"], ghost[0])
            set_motion_uniforms(uniforms, frame, ghost[1])
        if motion:
            set_motion_uniforms(uniforms, frame,
                                max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0))
        gl.glBindVertexArray(self._vao)
        with self._target.velocity_writes():
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)

    def park(self) -> None:
        """Drop the per-run target, environment and trails; programs and shard geometry stay warm."""
        self._target.release()
        self._environment.release()
        self._trails.release()

    def release_resources(self) -> None:
        self._target.release()
        self._environment.release()
        self._trails.release()
        self._resources.release_resources()
        self._geometry_key = None
        self._vao = self._count = 0


def create_transition_renderer() -> QuickGlassShatterRenderer:
    return QuickGlassShatterRenderer()
