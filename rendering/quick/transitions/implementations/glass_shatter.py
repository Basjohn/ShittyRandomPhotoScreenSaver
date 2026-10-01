"""Irregular glass shards, rendered inside the existing Quick transition host."""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.glass_shatter_program import (
    GLASS_FRAGMENT, GLASS_GHOST_FRAGMENT, GLASS_MOTION_FRAGMENT, GLASS_MOTION_VERTEX, GLASS_VERTEX,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.motion import motion_program, motion_uniform_names, set_motion_uniforms
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, trail_program
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
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

    def warm(self, parameters, size: tuple[int, int] | None = None) -> bool:
        """One bounded step of the gradual warm-up for a run with ``parameters`` (render thread,
        between runs): True once that run's first frame will compile nothing and, given the
        render ``size`` in device pixels, allocate nothing."""
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        r = self._resources
        entries = [(r, *UNDERLAY_PROGRAM)]
        if float(parameters.get("sheen", 0.0)) > 0.0:
            entries.append((r, *PHOTO_ENVIRONMENT_PROGRAM))
        entries.append((r, "glass_motion", GLASS_MOTION_VERTEX, GLASS_MOTION_FRAGMENT) if motion
                       else (r, "glass", GLASS_VERTEX, GLASS_FRAGMENT))
        if trails:
            entries += [(r, "glass_ghost", GLASS_MOTION_VERTEX, GLASS_GHOST_FRAGMENT), (r, *TRAIL_EDGES_PROGRAM)]
        if samples:
            entries += [(r, *program) for program in scene_target_programs(samples, False, motion)]
        if not warm_programs(entries):
            return False
        return warm_run_resources(self._target, self._trails, size, samples, motion_blur=motion,
                                  bloom=False, with_trails=trails)

    def _draw_scene(self, frame, progress: float, params, motion: bool, environment: int,
                    trails: bool = False) -> None:
        resources = self._resources
        resources.draw_image(frame, frame.destination_texture_id)
        if trails:
            self._trails.draw(self._target, frame, resources,
                              scene3d_trail_ghosts(progress, frame.run.request.duration_ms),
                              lambda ghosts: self._draw_shard_ghosts(frame, ghosts, params, environment, progress))
        resources.begin_depth(frame)
        self._draw_shards(frame, progress, params, motion, environment)

    _SHARD_UNIFORMS = (
        "uMatrix", "uItemSize", "uOldTex", "uNewTex", "uProgress", "uDepth", "uDirection", "uRadial",
        "uThickness", "uTransparency", "uRefraction", "uDispersion", "uSheen", "uEnvironment",
    )

    def _draw_shards(self, frame, progress: float, params, motion: bool, environment: int) -> None:
        resources = self._resources
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
        if motion:
            set_motion_uniforms(uniforms, frame,
                                max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0))
        gl.glBindVertexArray(self._vao)
        with self._target.velocity_writes():
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)

    def _draw_shard_ghosts(self, frame, ghosts, params, environment: int, now: float) -> None:
        """Bind invariant glass ghost state once; the ghost loop changes only progress and fade."""
        program, uniforms = trail_program(
            self._resources, "glass", GLASS_MOTION_VERTEX, GLASS_GHOST_FRAGMENT,
            self._SHARD_UNIFORMS + motion_uniform_names(),
        )
        bind_frame(program, uniforms, frame)
        radial = frame.run.request.direction == "center_out"
        direction = (0.0, 0.0) if radial else direction_vector(frame.run.request.direction)
        gl.glUniform2f(uniforms["uDirection"], *direction)
        gl.glUniform1i(uniforms["uRadial"], int(radial))
        gl.glUniform1f(uniforms["uDepth"], float(params["depth"]))
        for name in ("thickness", "transparency", "refraction", "dispersion", "sheen"):
            gl.glUniform1f(uniforms["u" + name.capitalize()], float(params[name]))
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glUniform1i(uniforms["uEnvironment"], 2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        set_motion_uniforms(uniforms, frame, now)
        gl.glBindVertexArray(self._vao)
        with self._target.velocity_writes():
            for time, fade in ghosts:
                gl.glUniform1f(uniforms["uProgress"], time)
                gl.glUniform1f(uniforms["uGhostFade"], fade)
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
