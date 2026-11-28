"""Irregular glass shards, rendered inside the existing Quick transition host."""
from __future__ import annotations


from rendering.gl_programs.glass_shatter_program import (
    GLASS_FRAGMENT,
    GLASS_GHOST_FRAGMENT,
    GLASS_MOTION_FRAGMENT,
    GLASS_MOTION_VERTEX,
    GLASS_VERTEX,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM
from ..directions import direction_vector
from ..native_scene import (TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses,
                            eased_show, ghost_values, item_quad_pass, native_clip_depth)
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

    # The photographs bind_frame binds (units 0 and 1); every other value is in the program's pass block.
    _SHARD_SAMPLERS = ("uOldTex", "uNewTex")


def create_transition_renderer() -> QuickGlassShatterRenderer:
    return QuickGlassShatterRenderer()
