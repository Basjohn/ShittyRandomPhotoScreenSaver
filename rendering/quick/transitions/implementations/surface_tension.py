"""Lazy Quick renderer for Surface Tension Merge: pools of the next picture swell and merge."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.surface_tension_program import (
    SURFACE_TENSION_FRAGMENT_SOURCE,
    TENSION_MAX_POOLS,
    TENSION_POOLS_RANGE,
    TENSION_SETTLE,
    tension_pools,
)
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame


def surface_tension_parameters(parameters: Mapping[str, object]) -> tuple[int, float, int]:
    """The resolved pool count, gloss and seed, validated before any GL state changes."""
    pools, gloss, seed = parameters.get("pools"), parameters.get("gloss"), parameters.get("seed")
    low, high = TENSION_POOLS_RANGE
    if isinstance(pools, bool) or not isinstance(pools, int) or not low <= pools <= high:
        raise ValueError(f"Surface Tension Merge needs a resolved pool count between {low} and {high}")
    if isinstance(gloss, bool) or not isinstance(gloss, (int, float)) or not 0.0 <= float(gloss) <= 1.0:
        raise ValueError("Surface Tension Merge needs a resolved gloss between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Surface Tension Merge needs a resolved seed")
    return pools, float(gloss), seed


def _padded(items: list, width: int) -> tuple:
    """A ``TENSION_MAX_POOLS`` array: ``items`` first, then zeros (the fragment reads only ``uPoolCount`` of them)."""
    return tuple(items) + ((0.0,) * width,) * (TENSION_MAX_POOLS - len(items))


def _shown(progress: float) -> int:
    """What the frame shows: the old picture before the run; the new one once the flood has covered everything and the
    meniscus has settled; else the effect."""
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= TENSION_SETTLE[1]:
        return SHOW_NEW
    return SHOW_EFFECT


class QuickSurfaceTensionRenderer(NativeFragmentPass):
    transition_id = "surface_tension"
    fragment_source = SURFACE_TENSION_FRAGMENT_SOURCE

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in SURFACE_TENSION_BLOCK

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (validated first; no GL): the one owner, packed by ``render``
        and filled by the native core (N5.2b). The pools are arrays (the core packs them flat at their stride)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        count, gloss, seed = surface_tension_parameters(frame.run.request.parameter_dict())
        width, height = frame.logical_size
        pools = tension_pools(seed, count, width / max(1e-6, height))
        return {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size, "u_target_px": frame.item_pixels,
                "uShow": _shown(progress),
                "uPools": _padded([(x, y, radius, birth) for x, y, radius, birth, _dx, _dy in pools], 4),
                "uDrift": _padded([(dx, dy) for *_rest, dx, dy in pools], 2),
                "uPoolCount": count, "uProgress": progress, "uGloss": gloss}


def create_transition_renderer() -> QuickSurfaceTensionRenderer:
    return QuickSurfaceTensionRenderer()
