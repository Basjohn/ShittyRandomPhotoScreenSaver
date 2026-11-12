"""Irregular glass shards, rendered inside the existing Quick transition host."""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.glass_shatter_program import (
    GLASS_BLOCK, GLASS_FRAGMENT, GLASS_GHOST_FRAGMENT, GLASS_MOTION_BLOCK, GLASS_MOTION_FRAGMENT, GLASS_MOTION_VERTEX,
    GLASS_VERTEX,
)
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import (
    SCENE3D_TRAIL_GHOSTS,
    scene3d_request_samples,
    scene3d_shutter_progress,
    scene3d_trail_ghosts,
)
from rendering.quick.scene3d.environment import PHOTO_ENVIRONMENT_PROGRAM, PhotoEnvironment
from rendering.quick.scene3d.motion import motion_program, set_motion_values
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, draw_ghosts, trail_program
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
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
        # A ghost pass gives each of its draws its own pass block copy.
        self._resources = MeshResources("Quick Glass Shatter", copies=SCENE3D_TRAIL_GHOSTS)
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
        if not warm_pass_blocks(self._resources, size):
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

    # The photographs bind_frame binds (units 0 and 1); every other value is in the program's pass block.
    _SHARD_SAMPLERS = ("uOldTex", "uNewTex")

    @staticmethod
    def _shard_values(values: dict, frame, params, environment: int) -> None:
        """The shards' invariant values into the pass-block ``values``, and the environment on unit 2."""
        radial = frame.run.request.direction == "center_out"
        values["uDirection"] = (0.0, 0.0) if radial else direction_vector(frame.run.request.direction)
        values["uRadial"] = int(radial)
        values["uDepth"] = float(params["depth"])
        for name in ("thickness", "transparency", "refraction", "dispersion", "sheen"):
            values["u" + name.capitalize()] = float(params[name])
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, environment)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def _draw_shards(self, frame, progress: float, params, motion: bool, environment: int) -> None:
        resources = self._resources
        program, uniforms, values, block = motion_program(
            resources, "glass", (GLASS_VERTEX, GLASS_FRAGMENT, GLASS_BLOCK),
            (GLASS_MOTION_VERTEX, GLASS_MOTION_FRAGMENT, GLASS_MOTION_BLOCK), self._SHARD_SAMPLERS, motion)
        bind_frame(program, uniforms, frame, values)
        self._shard_values(values, frame, params, environment)
        values["uProgress"] = progress
        if motion:
            set_motion_values(values, frame,
                              max(progress - scene3d_shutter_progress(frame.run.request.duration_ms), 0.0))
        gl.glBindVertexArray(self._vao)
        with self._target.velocity_writes(), resources.pass_blocks.bound(pack_block(block, values)):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count)

    def _draw_shard_ghosts(self, frame, ghosts, params, environment: int, now: float) -> None:
        """Bind invariant glass ghost state once; the ghost loop changes only progress and fade."""
        resources = self._resources
        program, uniforms = trail_program(resources, "glass", GLASS_MOTION_VERTEX, GLASS_GHOST_FRAGMENT,
                                          self._SHARD_SAMPLERS)
        values = resources.values("glass_ghost")
        bind_frame(program, uniforms, frame, values)
        self._shard_values(values, frame, params, environment)
        set_motion_values(values, frame, now)
        gl.glBindVertexArray(self._vao)
        with self._target.velocity_writes():
            draw_ghosts(resources.pass_blocks, GLASS_MOTION_BLOCK, values, ghosts, lambda time: {"uProgress": time},
                        lambda: gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._count))

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
