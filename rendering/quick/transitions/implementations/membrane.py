"""Lazy Quick renderer for Membrane Turnover: the old picture's membrane twists over and away."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.membrane_options import MEMBRANE_SWEEP_VECTORS
from rendering.gl_programs.membrane_program import MEMBRANE_DONE, MEMBRANE_FRAGMENT_SOURCE, MEMBRANE_VERTEX_SOURCE
from rendering.gl_programs.scene3d import (
    scene3d_detail,
    scene3d_grid_size,
    scene3d_grid_vertices,
    scene3d_request_samples,
)
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM
from rendering.quick.scene3d.resources import pack_floats
from ..native_scene import (NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass, native_clip_depth)

# N5.2e (N4.l's bendable grid): the native scene's passes, the texts this renderer compiles (the sheet's vertex stage
# with its native clip depth): the new picture under the sheet, then the sheet over the run's grid, blended straight.
_GRID_INPUTS = (("aGrid", 2),)
_SCENE_PASSES = (
    item_quad_pass("underlay", UNDERLAY_PROGRAM[1], UNDERLAY_PROGRAM[2], (("uImage", "new"),)),
    NativeScenePass("sheet", native_clip_depth(MEMBRANE_VERTEX_SOURCE), MEMBRANE_FRAGMENT_SOURCE, mesh="grid",
                    samplers=(("uOldTex", "old"), ("uNewTex", "new"), ("uEnvironment", "environment")), depth=True,
                    blend=(("add", "src_alpha", "one_minus_src_alpha"), ("add", "one", "one_minus_src_alpha"))),
)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def membrane_parameters(parameters: Mapping[str, object]) -> tuple[float, int, str]:
    """The resolved gloss, seed and 3D Detail tier, validated before any GL state changes."""
    gloss, seed, detail = parameters.get("gloss"), parameters.get("seed"), parameters.get("detail")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Membrane Turnover needs a resolved gloss between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Membrane Turnover needs a resolved seed")
    if not isinstance(detail, str):
        raise ValueError("Membrane Turnover needs a resolved 3D Detail tier")
    return float(gloss), seed, detail


class QuickMembraneRenderer(NativeScenePasses):
    transition_id = "membrane"

    # ------------------------------------------------------------------------------- N5.2e: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        _gloss, _seed, detail = membrane_parameters(parameters)
        columns, rows = scene3d_grid_size(scene3d_detail(detail), logical_size[0] / logical_size[1])
        grid = NativeSceneMesh("grid", pack_floats(scene3d_grid_vertices(columns, rows)), _GRID_INPUTS)
        return NativeScene(_SCENE_PASSES, (grid,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample), MEMBRANE_DONE)

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        """The sheet's values for the frame (the underlay's are the core's)."""
        sweep = MEMBRANE_SWEEP_VECTORS.get(str(run.request.direction))
        if sweep is None:
            raise ValueError(f"unknown resolved Membrane Turnover sweep: {run.request.direction!r}")
        return self._sheet_values(_progress(sample), sweep, *membrane_parameters(run.request.parameter_dict()),
                                  logical_size)

    @staticmethod
    def _sheet_values(progress: float, sweep, gloss: float, seed: int, detail: str,
                      logical_size: tuple[float, float]) -> dict[str, object]:
        """The sheet's values (the one owner: ``_draw``'s and the native scene's)."""
        columns, rows = scene3d_grid_size(scene3d_detail(detail), logical_size[0] / logical_size[1])
        return {"uGridCells": (float(columns), float(rows)), "uSweep": sweep, "uProgress": progress,
                "uSpin": 1.0 if seed % 2 else -1.0, "uSeed": float(seed % 997), "uGloss": gloss}

    # The photographs bind_frame binds (units 0 and 1); every other value is in MEMBRANE_BLOCK.
    _SAMPLERS = ("uOldTex", "uNewTex")


def create_transition_renderer() -> QuickMembraneRenderer:
    return QuickMembraneRenderer()
