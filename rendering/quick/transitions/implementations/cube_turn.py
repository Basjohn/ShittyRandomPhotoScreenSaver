"""Lazy Quick renderer for Cube Turn: the picture is a box that turns to show the next one."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.cube_turn_program import (
    CUBE_TURN_BACKDROP_FRAGMENT_SOURCE,
    CUBE_TURN_BACKDROP_VERTEX_SOURCE,
    CUBE_TURN_FRAGMENT_SOURCE,
    CUBE_TURN_VERTEX_SOURCE,
    cube_turn_axis,
    cube_turn_lift,
    cube_turn_state,
)
from rendering.gl_programs.scene3d import SCENE3D_BOX_VERTICES, scene3d_request_samples
from rendering.quick.scene3d.resources import pack_floats
from ..native_scene import (native_clip_depth, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass)

#: N5.2c: the box's attributes by name (``SCENE3D_BOX_ATTRIBUTES``' order: position, outward normal).
_BOX_INPUTS = (("aPosition", 3), ("aNormal", 3))
_SCENE_PASSES = (
    item_quad_pass("backdrop", CUBE_TURN_BACKDROP_VERTEX_SOURCE, CUBE_TURN_BACKDROP_FRAGMENT_SOURCE,
                   (("uEnvironment", "environment"),)),
    NativeScenePass("box", native_clip_depth(CUBE_TURN_VERTEX_SOURCE), CUBE_TURN_FRAGMENT_SOURCE, mesh="box",
                    samplers=(("uOldTex", "old"), ("uNewTex", "new"), ("uEnvironment", "environment")), depth=True),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def cube_turn_parameters(parameters: Mapping[str, object]) -> float:
    """The resolved gloss, validated before any GL state changes."""
    gloss = parameters.get("gloss")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Cube Turn needs a resolved gloss between 0 and 1")
    return float(gloss)


class QuickCubeTurnRenderer(NativeScenePasses):
    transition_id = "cube_turn"

    _BOX_SAMPLERS = ("uOldTex", "uNewTex")   # every other value is in the programs' pass blocks

    # ------------------------------------------------------------------------------- N5.2c: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        cube_turn_parameters(parameters)
        box = NativeSceneMesh("box", pack_floats(SCENE3D_BOX_VERTICES), _BOX_INPUTS)
        return NativeScene(_SCENE_PASSES, (box,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        """The box's values for the frame (the backdrop's are the core's: the matrix and the item size)."""
        axis, sign = cube_turn_axis(str(run.request.direction))
        gloss = cube_turn_parameters(run.request.parameter_dict())
        angle, zoom = cube_turn_state(_progress(sample), sign)
        return {"uAngle": angle, "uFinal": sign * 1.5707963267948966, "uAxis": axis, "uZoom": zoom, "uGloss": gloss,
                "uLift": cube_turn_lift(angle)}


def create_transition_renderer() -> QuickCubeTurnRenderer:
    return QuickCubeTurnRenderer()
