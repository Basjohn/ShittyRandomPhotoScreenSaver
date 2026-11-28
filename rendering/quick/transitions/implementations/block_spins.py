"""Lazy Quick renderer for the authored single-slab 3D BlockSpin effect."""

from __future__ import annotations

import math


from rendering.gl_programs.blockspin_program import (
    BLOCK_SPIN_BOX_VERTICES,
    BLOCK_SPIN_FRAGMENT_SOURCE,
    BLOCK_SPIN_GHOST_FRAGMENT_SOURCE,
    BLOCK_SPIN_MOTION_FRAGMENT_SOURCE,
    BLOCK_SPIN_MOTION_VERTEX_SOURCE,
    BLOCK_SPIN_QUICK_VERTEX_SOURCE,
    block_spin_edge_glass_mode,
    block_spin_progress,
)
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.gl_programs.item_quad import item_quad_program
from rendering.quick.scene3d.resources import pack_floats
from ..native_scene import (SHOW_EFFECT, TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass,
                            NativeScenePasses, ghost_values, item_quad_pass, native_clip_depth)


_DIRECTION_STATES = {
    "left": (0, 1.0),
    "right": (0, -1.0),
    "up": (1, 1.0),
    "down": (1, -1.0),
    "diag_tl_br": (3, 1.0),
    "diag_tr_bl": (2, 1.0),
}


_VOID_FRAGMENT_SOURCE = """#version 460 core
out vec4 FragColor;

void main() {
    FragColor = vec4(0.0, 0.0, 0.0, 1.0);
}
"""
# N1.6: the void is drawn over the item quad, its values (the quad's) one std140 pass block.
_VOID_VERTEX_SOURCE, _VOID_FRAGMENT_SOURCE, _VOID_BLOCK = item_quad_program(
    _VOID_FRAGMENT_SOURCE, block="BlockSpinsVoid", samplers={})


def _block_spin_direction_state(direction: object) -> tuple[int, float]:
    value = str(direction).strip().lower()
    state = _DIRECTION_STATES.get(value)
    if state is None:
        raise ValueError(f"unknown resolved 3D Block Spins direction: {direction!r}")
    return state


# N5.2d: the native scene's passes (their texts the ones this renderer compiles); the slab's mesh by name.
_SLAB_INPUTS = (("aPosition", 3), ("aNormal", 3), ("aUv", 2))
_SLAB_SAMPLERS = (("uOldTexture", "old"), ("uNewTexture", "new"), ("uEnvironment", "environment"))
# The slab's stages write their own clip depth (``native_clip_depth``).
_SLAB_VERTEX = native_clip_depth(BLOCK_SPIN_QUICK_VERTEX_SOURCE)
_SLAB_MOTION_VERTEX = native_clip_depth(BLOCK_SPIN_MOTION_VERTEX_SOURCE)
_SCENE_PASSES = (
    item_quad_pass("void", _VOID_VERTEX_SOURCE, _VOID_FRAGMENT_SOURCE),
    NativeScenePass("slab_ghost", _SLAB_MOTION_VERTEX, BLOCK_SPIN_GHOST_FRAGMENT_SOURCE, mesh="slab",
                    samplers=_SLAB_SAMPLERS, target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("slab", _SLAB_VERTEX, BLOCK_SPIN_FRAGMENT_SOURCE, mesh="slab", samplers=_SLAB_SAMPLERS,
                    depth=True),
    NativeScenePass("slab_motion", _SLAB_MOTION_VERTEX, BLOCK_SPIN_MOTION_FRAGMENT_SOURCE, mesh="slab",
                    samplers=_SLAB_SAMPLERS, depth=True, moves=True),
)


def _scene_pass(name: str) -> NativeScenePass:
    return next(p for p in _SCENE_PASSES if p.name == name)


def _without_environment(scene_pass: NativeScenePass) -> NativeScenePass:
    """Edge Glass Off or Refraction reads no environment (Python binds none): its sampler bound to the new picture,
    which the shader then never reads (``uEdgeGlass`` 0 or 2)."""
    from dataclasses import replace

    return replace(scene_pass, samplers=tuple((name, "new" if kind == "environment" else kind)
                                              for name, kind in scene_pass.samplers))


class QuickBlockSpinsRenderer(NativeScenePasses):
    transition_id = "block_spins"
    scene_pixels = True                  # N5.2d: its motion reads the item's device pixels (uViewport)

    # ------------------------------------------------------------------------------- N5.2d: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        _block_spin_direction_state(run.request.direction)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        reflections = block_spin_edge_glass_mode(parameters.get("edge_glass", "Off")) in (1, 3)
        names = ["void"] + (["slab_ghost", TRAIL_EDGES_PASS.name] if trails else []) + [
            "slab_motion" if motion else "slab"]
        passes = tuple(p if reflections or p.core_triangle else _without_environment(p)
                       for p in map(_scene_pass, names))
        slab = NativeSceneMesh("slab", pack_floats(BLOCK_SPIN_BOX_VERTICES), _SLAB_INPUTS)
        return NativeScene(passes, (slab,), samples, reflections, motion=motion, trails=trails)

    def scene_show(self, run, sample) -> int:
        return SHOW_EFFECT                   # the slab is drawn at every progress (its faces are the photographs)

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The slab's values for the frame (``render``'s, one owner): its turn, and with motion blur its turn one
        shutter ago; with trails each ghost's turn and fade (``<member>@slab_ghost_<k>``)."""
        parameters = run.request.parameter_dict()
        axis_mode, spin_direction = _block_spin_direction_state(run.request.direction)
        progress = float(sample.eased_progress)
        angle = lambda time: math.pi * block_spin_progress(time) * spin_direction  # noqa: E731
        values: dict[str, object] = {
            "uSpecDirection": spin_direction, "uAxisMode": axis_mode,
            "uEdgeGlass": block_spin_edge_glass_mode(parameters.get("edge_glass", "Off")), "uAngle": angle(progress)}
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        if motion or trails:
            width, height = pixels if pixels is not None else logical_size
            values["uViewport"] = (float(width), float(height))
        if motion:
            before = max(progress - scene3d_shutter_progress(run.request.duration_ms), 0.0)
            values["uAngleBefore"] = angle(before)
            values["uGhostFade@slab_motion"] = 0.0      # the shared motion block's ghost member, read by no stage here
        if trails:
            values.update(ghost_values("slab_ghost", scene3d_trail_ghosts(progress, run.request.duration_ms), "uAngle",
                                       lambda time: {"uAngle": angle(time)}, progress))
        return values


def create_transition_renderer() -> QuickBlockSpinsRenderer:
    return QuickBlockSpinsRenderer()
