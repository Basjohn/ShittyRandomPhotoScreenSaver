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
from rendering.quick.scene3d.environment import (PHOTO_ENVIRONMENT_MIPS_PROGRAM, PHOTO_ENVIRONMENT_PROGRAM,
                                                 PhotoEnvironment)
from rendering.quick.scene3d.motion import motion_program, set_motion_values
from rendering.quick.scene3d.trails import TRAIL_EDGES_PROGRAM, MotionTrails, draw_ghosts, trail_program
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, MeshResources, bind_frame, warm_programs, warm_pass_blocks
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..directions import direction_vector
from ..native_scene import (TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses,
                            eased_show, ghost_values, item_quad_pass, native_clip_depth)
from ..render_contract import QuickTransitionRenderFrame
from ..run_geometry import (
    GLASS_ATTRIBUTES,
    PREPARED_GEOMETRY,
    build_glass_geometry,
    glass_geometry_key,
)


# N5.2d: the native scene's passes (their texts the ones this renderer compiles, each vertex stage with its native clip
# depth); the shards' mesh by name.
_SHARD_INPUTS = tuple(zip(("aUv", "aCenter", "aZ", "aNormal", "aInset", "aFace", "aVariation", "aRadius", "aLife",
                           "aKick", "aSpin", "aPivot", "aKick2", "aSpin2", "aPivot2", "aLayer"), GLASS_ATTRIBUTES))
_NATIVE_SHARD_SAMPLERS = (("uOldTex", "old"), ("uNewTex", "new"), ("uEnvironment", "environment"))
_SCENE_PASSES = (
    item_quad_pass("underlay", UNDERLAY_PROGRAM[1], UNDERLAY_PROGRAM[2], (("uImage", "new"),)),
    NativeScenePass("glass_ghost", native_clip_depth(GLASS_MOTION_VERTEX), GLASS_GHOST_FRAGMENT, mesh="shards",
                    samplers=_NATIVE_SHARD_SAMPLERS, target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("glass", native_clip_depth(GLASS_VERTEX), GLASS_FRAGMENT, mesh="shards",
                    samplers=_NATIVE_SHARD_SAMPLERS, depth=True),
    NativeScenePass("glass_motion", native_clip_depth(GLASS_MOTION_VERTEX), GLASS_MOTION_FRAGMENT, mesh="shards",
                    samplers=_NATIVE_SHARD_SAMPLERS, depth=True, moves=True),
)


def _scene_pass(name: str, environment: bool) -> NativeScenePass:
    """A pass by name; without sheen (no environment: Python binds none) its environment sampler reads the new picture,
    which the shader then weighs by a zero sheen."""
    from dataclasses import replace

    found = next(p for p in _SCENE_PASSES if p.name == name)
    if environment:
        return found
    return replace(found, samplers=tuple((sampler, "new" if kind == "environment" else kind)
                                         for sampler, kind in found.samplers))


def _sheen(parameters) -> bool:
    return float(parameters["sheen"]) > 0.0


class QuickGlassShatterRenderer(NativeScenePasses):
    transition_id = "glass_shatter"
    scene_pixels = True                  # N5.2d: its motion reads the item's device pixels (uViewport)

    # ------------------------------------------------------------------------------- N5.2d: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        key = glass_geometry_key(parameters, logical_size[0] / logical_size[1], run.request.direction)
        geometry = PREPARED_GEOMETRY.get_or_build(key, build_glass_geometry)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        environment = _sheen(parameters)
        names = ["underlay"] + (["glass_ghost", TRAIL_EDGES_PASS.name] if trails else []) + [
            "glass_motion" if motion else "glass"]
        passes = tuple(_scene_pass(name, environment) for name in names)
        shards = NativeSceneMesh("shards", bytes(geometry.vertices), _SHARD_INPUTS)
        return NativeScene(passes, (shards,), samples, environment, motion=motion, trails=trails)

    def scene_show(self, run, sample) -> int:
        return eased_show(float(sample.eased_progress))

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The shards' values for the frame (``_shard_values`` and ``render``'s, one owner): their time, and with motion
        blur their time one shutter ago; with trails each ghost's time and fade (``<member>@glass_ghost_<k>``)."""
        parameters = run.request.parameter_dict()
        progress = float(sample.eased_progress)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        values: dict[str, object] = {"uProgress": progress}
        self._shard_parameters(values, run.request.direction, parameters)
        if motion or trails:
            width, height = pixels if pixels is not None else logical_size
            values["uViewport"] = (float(width), float(height))
        if motion:
            values["uProgressBefore"] = max(progress - scene3d_shutter_progress(run.request.duration_ms), 0.0)
            values["uGhostFade@glass_motion"] = 0.0     # the shared motion block's ghost member, read by no stage here
        if trails:
            values.update(ghost_values("glass_ghost", scene3d_trail_ghosts(progress, run.request.duration_ms),
                                       "uProgress", lambda time: {"uProgress": time}, progress))
        return values

    @staticmethod
    def _shard_parameters(values: dict, direction, params) -> None:
        """The shards' invariant values (the one owner: ``_shard_values`` and the native scene's)."""
        radial = direction == "center_out"
        values["uDirection"] = (0.0, 0.0) if radial else direction_vector(direction)
        values["uRadial"] = int(radial)
        values["uDepth"] = float(params["depth"])
        for name in ("thickness", "transparency", "refraction", "dispersion", "sheen"):
            values["u" + name.capitalize()] = float(params[name])

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
            entries += [(r, *PHOTO_ENVIRONMENT_PROGRAM), (r, *PHOTO_ENVIRONMENT_MIPS_PROGRAM)]
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
        QuickGlassShatterRenderer._shard_parameters(values, frame.run.request.direction, params)
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
