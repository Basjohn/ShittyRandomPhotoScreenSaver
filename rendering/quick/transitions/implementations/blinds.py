"""Lazy Quick renderer for Blinds: the canonical authored flat shader, or 3D Slats."""

from __future__ import annotations

from collections.abc import Mapping
import math


from rendering.gl_programs.blinds_program import blinds_program
from rendering.gl_programs.scene3d import scene3d_request_samples
from rendering.quick.scene3d.resources import pack_floats
from ..fullscreen_pass import SHOW_EFFECT, fullscreen_pass_parts
from ..native_scene import (native_clip_depth, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses, eased_show,
                            item_quad_pass)

# The flat style: the authored fragment over the item quad, its values one pass block (N1.6).
_FLAT_VERTEX_SOURCE, _FLAT_BLOCK = fullscreen_pass_parts(blinds_program.fragment_source, "BlindsPass")
#: N5.2c: the flat style's one pass (the core's item quad; the matrix, item size and resolution are the core's).
_FLAT_PASS = item_quad_pass("flat", _FLAT_VERTEX_SOURCE, blinds_program.fragment_source,
                            (("uOldTex", "old"), ("uNewTex", "new")))
_BOX_INPUTS = (("aPosition", 3), ("aNormal", 3))   # the slat box's attributes by name (position, outward normal)


_BLINDS_DIRECTION_MODES = {
    "horizontal": 0,
    "vertical": 1,
    "diagonal": 2,
}
_AUTHORED_SLAT_COLS = 7
_MIN_FEATHER = 0.001
_MAX_FEATHER = 0.5


def _blinds_direction_mode(direction: object) -> int:
    """Map one fully resolved authored direction to the shader mode."""

    value = str(direction).strip().lower()
    mode = _BLINDS_DIRECTION_MODES.get(value)
    if mode is None:
        raise ValueError(f"unknown resolved Blinds direction: {direction!r}")
    return mode


def _blinds_feather(parameters: Mapping[str, object]) -> float:
    """Read the resolved shader feather without a renderer-side UI fallback."""

    raw = parameters.get("feather")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Blinds requires resolved numeric parameter 'feather'")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Blinds feather must be finite")
    if not _MIN_FEATHER <= value <= _MAX_FEATHER:
        raise ValueError(
            f"Blinds feather must be between {_MIN_FEATHER} and {_MAX_FEATHER}"
        )
    return value


def _blinds_grid(logical_size: tuple[float, float]) -> tuple[int, int]:
    """Preserve the compositor Blinds grid derived from display aspect ratio."""

    if len(logical_size) != 2:
        raise ValueError("Blinds logical size must contain width and height")
    width, height = (float(value) for value in logical_size)
    if not math.isfinite(width) or not math.isfinite(height):
        raise ValueError("Blinds logical size must be finite")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Blinds logical size must be positive")

    # GLCompositorBlindsTransition historically used its default slat_cols=7,
    # doubled it, then derived row count from the target aspect ratio.  Its
    # slat_rows constructor value never participated in the effective grid.
    cols = max(2, _AUTHORED_SLAT_COLS * 2)
    aspect = height / max(1.0, width)
    rows = max(2, int(round(cols * aspect)))
    return cols, rows


def _slats_parameters(parameters: Mapping[str, object]) -> tuple[int, float]:
    """The resolved 3D Slats count and gloss, validated before any GL state changes."""
    slats, gloss = parameters.get("slats"), parameters.get("gloss")
    if isinstance(slats, bool) or not isinstance(slats, int) or not 6 <= slats <= 48:
        raise ValueError("Blinds 3D Slats needs a resolved slat count between 6 and 48")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Blinds 3D Slats needs a resolved gloss between 0 and 1")
    return slats, float(gloss)


def _slats_style(parameters: Mapping[str, object]) -> bool:
    return parameters.get("style", "flat") == "slats"


_SLATS_PROGRAM = None


def _slats_program():
    """The 3D Slats shader module, loaded the first time the style is used (Flat never loads it).

    Bound once on that first use, so a running Slats frame never re-enters the import machinery."""
    global _SLATS_PROGRAM
    if _SLATS_PROGRAM is None:
        from rendering.gl_programs import blinds_slats_program
        _SLATS_PROGRAM = blinds_slats_program
    return _SLATS_PROGRAM


def _slat_passes() -> tuple[NativeScenePass, ...]:
    """3D Slats' two passes (N5.2c), from its shader module (loaded at the first ask, as the Python style does)."""
    shaders = _slats_program()
    return (
        item_quad_pass("backdrop", shaders.BLINDS_BACKDROP_VERTEX_SOURCE, shaders.BLINDS_BACKDROP_FRAGMENT_SOURCE,
                       (("uNewTex", "new"),)),
        NativeScenePass("slats", native_clip_depth(shaders.BLINDS_SLATS_VERTEX_SOURCE), shaders.BLINDS_SLATS_FRAGMENT_SOURCE, mesh="slat",
                        samplers=(("uOldTex", "old"), ("uNewTex", "new"), ("uEnvironment", "environment")), depth=True),
    )


class QuickBlindsRenderer(NativeScenePasses):
    transition_id = "blinds"

    # ------------------------------------------------------------------------------- N5.2c: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return (_FLAT_PASS, *_slat_passes())

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        if not _slats_style(parameters):
            _blinds_feather(parameters)
            return NativeScene((_FLAT_PASS,))
        count, _gloss = _slats_parameters(parameters)
        if _blinds_direction_mode(run.request.direction) == 2:
            raise ValueError("Blinds 3D Slats turn about horizontal or vertical axes only")
        backdrop, slats = _slat_passes()
        slats = NativeScenePass(slats.name, slats.vertex_source, slats.fragment_source, mesh=slats.mesh,
                                instances=count, samplers=slats.samplers, depth=True)
        shaders = _slats_program()
        slat = NativeSceneMesh("slat", pack_floats(shaders.BLINDS_SLAT_BOX_VERTICES), _BOX_INPUTS)
        return NativeScene((backdrop, slats), (slat,), scene3d_request_samples(parameters), True)

    def scene_show(self, run, sample) -> int:
        if not _slats_style(run.request.parameter_dict()):
            return SHOW_EFFECT                  # the flat style draws its shader at every progress
        return eased_show(max(0.0, min(1.0, float(sample.eased_progress))))

    def scene_values(self, run, sample, logical_size: tuple[float, float]) -> dict[str, object]:
        """The frame's values of either style (the matrix and the item size are the core's)."""
        parameters = run.request.parameter_dict()
        mode = _blinds_direction_mode(run.request.direction)
        if not _slats_style(parameters):
            cols, rows = _blinds_grid(logical_size)
            return {"u_progress": float(sample.eased_progress), "u_grid": (float(cols), float(rows)),
                    "u_feather": _blinds_feather(parameters), "u_direction": mode}
        count, gloss = _slats_parameters(parameters)
        # Direction "Horizontal" keeps the flat style's vertical stripes: columns.
        return {"uProgress": max(0.0, min(1.0, float(sample.eased_progress))), "uCount": count,
                "uVertical": 1 if mode == 0 else 0, "uGloss": gloss}

    # The photographs each 3D Slats program reads (bind_frame binds them); every other value is in its pass block.
    _SLAT_SAMPLERS = ("uOldTex", "uNewTex")
    _BACKDROP_SAMPLERS = ("uNewTex",)


def create_transition_renderer() -> QuickBlindsRenderer:
    return QuickBlindsRenderer()
