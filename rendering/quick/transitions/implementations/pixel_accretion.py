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
from rendering.quick.scene3d.resources import (UNDERLAY_PROGRAM, MeshResources, bind_frame, pack_floats, warm_programs,
                                               warm_pass_blocks)
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs, warm_run_resources
from ..directions import direction_vector
from ..native_scene import (TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses,
                            eased_show, ghost_values, item_quad_pass, native_clip_depth)
from ..render_contract import QuickTransitionRenderFrame


# N5.2d: the native scene's passes (their texts the ones this renderer compiles, each vertex stage with its native clip
# depth): the micro-quad drawn once a tile of the grid, whose count (the item's device pixels over the tile size,
# ``pixel_accretion_grid``) is the setting TILE_INSTANCES.
TILE_INSTANCES = "tile_instances"
_QUAD_INPUTS = (("aPosition", 2), ("aUv", 2))
_NATIVE_TILE_SAMPLERS = (("uOldTex", "old"), ("uNewTex", "new"))
_SCENE_PASSES = (
    item_quad_pass("underlay", UNDERLAY_PROGRAM[1], UNDERLAY_PROGRAM[2], (("uImage", "old"),)),
    NativeScenePass("microquads_ghost", native_clip_depth(PIXEL_ACCRETION_MOTION_VERTEX_SOURCE),
                    PIXEL_ACCRETION_GHOST_FRAGMENT_SOURCE, mesh="microquad", instances=TILE_INSTANCES,
                    samplers=_NATIVE_TILE_SAMPLERS, target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("microquads", native_clip_depth(PIXEL_ACCRETION_VERTEX_SOURCE), PIXEL_ACCRETION_FRAGMENT_SOURCE,
                    mesh="microquad", instances=TILE_INSTANCES, samplers=_NATIVE_TILE_SAMPLERS, depth=True),
    NativeScenePass("microquads_motion", native_clip_depth(PIXEL_ACCRETION_MOTION_VERTEX_SOURCE),
                    PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE, mesh="microquad", instances=TILE_INSTANCES,
                    samplers=_NATIVE_TILE_SAMPLERS, depth=True, moves=True),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


class QuickPixelAccretionRenderer(NativeScenePasses):
    transition_id = "pixel_accretion"
    scene_pixels = True                  # N5.2d: its grid and motion read the item's device pixels

    # ------------------------------------------------------------------------------- N5.2d: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        pixel_accretion_parameters(parameters)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        names = ["underlay"] + (["microquads_ghost", TRAIL_EDGES_PASS.name] if trails else []) + [
            "microquads_motion" if motion else "microquads"]
        passes = tuple(next(p for p in _SCENE_PASSES if p.name == name) for name in names)
        quad = NativeSceneMesh("microquad", pack_floats(PIXEL_ACCRETION_QUAD_VERTICES), _QUAD_INPUTS)
        return NativeScene(passes, (quad,), samples, False, motion=motion, trails=trails)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The tiles' values for the frame (``_tile_values`` and ``render``'s, one owner): the grid of the item's device
        pixels and its tile count, their time, and with motion blur their time one shutter ago; with trails each
        ghost's time and fade (``<member>@microquads_ghost_<k>``)."""
        parameters = run.request.parameter_dict()
        seed, tile_size, travel = pixel_accretion_parameters(parameters)
        width, height = pixels if pixels is not None else (round(logical_size[0]), round(logical_size[1]))
        columns, rows, _size = pixel_accretion_grid(int(width), int(height), tile_size)
        progress = _progress(sample)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        values: dict[str, object] = {"uProgress": progress, TILE_INSTANCES: columns * rows}
        self._grid_values(values, run.request.direction, columns, rows, seed, travel)
        if motion or trails:
            values["uViewport"] = (float(width), float(height))
        if motion:
            values["uProgressBefore"] = max(progress - scene3d_shutter_progress(run.request.duration_ms), 0.0)
            values["uGhostFade@microquads_motion"] = 0.0  # the shared motion block's ghost member, read by no stage
        if trails:
            values.update(ghost_values("microquads_ghost", scene3d_trail_ghosts(progress, run.request.duration_ms),
                                       "uProgress", lambda time: {"uProgress": time}, progress))
        return values

    @staticmethod
    def _grid_values(values: dict, direction, columns: int, rows: int, seed: int, travel: float) -> None:
        """The tiles' invariant values (the one owner: ``_tile_values`` and the native scene's)."""
        values["uGrid"] = (float(columns), float(rows))
        values["uDirection"] = direction_vector(direction)
        values["uTravel"] = travel
        values["uSeed"] = float(seed)

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
        QuickPixelAccretionRenderer._grid_values(values, frame.run.request.direction, columns, rows, seed, travel)

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
