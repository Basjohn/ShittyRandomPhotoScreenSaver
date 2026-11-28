"""Lazy instanced micro-quad renderer for Directional Pixel Accretion."""

from __future__ import annotations


from rendering.gl_programs.pixel_accretion_program import (
    PIXEL_ACCRETION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_GHOST_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_MOTION_FRAGMENT_SOURCE,
    PIXEL_ACCRETION_MOTION_VERTEX_SOURCE,
    PIXEL_ACCRETION_QUAD_VERTICES,
    PIXEL_ACCRETION_VERTEX_SOURCE,
    pixel_accretion_grid,
    pixel_accretion_parameters,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, pack_floats
from ..directions import direction_vector
from ..native_scene import (TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses,
                            eased_show, ghost_values, item_quad_pass, native_clip_depth)


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

    # The photograph bind_frame binds (unit 1); every other value is in the program's pass block.
    _TILE_SAMPLERS = ("uNewTex",)


def create_transition_renderer() -> QuickPixelAccretionRenderer:
    return QuickPixelAccretionRenderer()
