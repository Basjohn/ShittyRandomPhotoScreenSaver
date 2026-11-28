"""Lazy Quick renderer for Chromatic Shear: slices shear apart into spectral layers and back."""

from __future__ import annotations

import math
from collections.abc import Mapping


from rendering.gl_programs.chromatic_shear_program import (
    CHROMATIC_SHEAR_FRAGMENT_SOURCE,
    SHEAR_AXES,
    SHEAR_SLICES_RANGE,
)
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame


def chromatic_shear_parameters(parameters: Mapping[str, object]) -> tuple[float, int, int]:
    """The resolved spread, slice count and seed, validated before any GL state changes."""
    spread, slices, seed = parameters.get("spread"), parameters.get("slices"), parameters.get("seed")
    if isinstance(spread, bool) or not isinstance(spread, (int, float)) or not 0.0 <= float(spread) <= 1.0:
        raise ValueError("Chromatic Shear needs a resolved spread between 0 and 1")
    low, high = SHEAR_SLICES_RANGE
    if isinstance(slices, bool) or not isinstance(slices, int) or not low <= slices <= high:
        raise ValueError(f"Chromatic Shear needs a resolved slice count between {low} and {high}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Chromatic Shear needs a resolved seed")
    return float(spread), slices, seed


def _shown(progress: float) -> int:
    """What the frame shows: the old picture before the run, the new one at its end, else the effect."""
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= 1.0:
        return SHOW_NEW
    return SHOW_EFFECT


class QuickChromaticShearRenderer(NativeFragmentPass):
    transition_id = "chromatic_shear"
    fragment_source = CHROMATIC_SHEAR_FRAGMENT_SOURCE

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in CHROMATIC_SHEAR_BLOCK

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (validated first; no GL): the one owner, packed by ``render``
        and filled by the native core (N5.2b)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        axis = SHEAR_AXES.get(str(frame.run.request.direction))
        if axis is None:
            raise ValueError(f"unknown resolved Chromatic Shear axis: {frame.run.request.direction!r}")
        spread, slices, seed = chromatic_shear_parameters(frame.run.request.parameter_dict())
        length = math.hypot(*axis)
        return {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size, "u_target_px": frame.item_pixels,
                "uShow": _shown(progress), "uProgress": progress, "uAxis": (axis[0] / length, axis[1] / length),
                "uSpread": spread, "uSlices": float(slices), "uSeed": float(seed % 997)}


def create_transition_renderer() -> QuickChromaticShearRenderer:
    return QuickChromaticShearRenderer()
