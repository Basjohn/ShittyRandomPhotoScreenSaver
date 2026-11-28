"""Lazy Quick renderer for Capillary Bloom: the next picture spreads through the old like dye."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.capillary_bloom_program import (
    CAPILLARY_COST_GLSL,
    CAPILLARY_SETTLE,
    CAPILLARY_SOURCES_RANGE,
    capillary_native_fragment,
    capillary_sources,
)
from rendering.gl_programs.capillary_field import CAPILLARY_COST
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFieldRequest, NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame

#: N5.2g: the item textures the native core makes the run's arrival field and its extent into (ABI 43).
NATIVE_ARRIVAL = "capillary_arrival"
NATIVE_EXTENT = "capillary_extent"


def _shown(progress: float) -> int:
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= CAPILLARY_SETTLE[1]:
        return SHOW_NEW
    return SHOW_EFFECT


def capillary_bloom_parameters(parameters: Mapping[str, object]) -> tuple[int, float, int]:
    """The resolved source count, fibres and seed, validated before any GL state changes."""
    sources, fibres, seed = parameters.get("sources"), parameters.get("fibres"), parameters.get("seed")
    low, high = CAPILLARY_SOURCES_RANGE
    if isinstance(sources, bool) or not isinstance(sources, int) or not low <= sources <= high:
        raise ValueError(f"Capillary Bloom needs a resolved source count between {low} and {high}")
    if isinstance(fibres, bool) or not isinstance(fibres, (int, float)) or not 0.0 <= float(fibres) <= 1.0:
        raise ValueError("Capillary Bloom needs a resolved fibres value between 0 and 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Capillary Bloom needs a resolved seed")
    return sources, float(fibres), seed


# The native seed pack's block, resolved once (``propagation_seed_layout``): the recipe builder composes no shader.
from rendering.quick.scene3d.native_fields import propagation_seed_layout as _propagation_seed_layout  # noqa: E402

_SEED_LAYOUT = _propagation_seed_layout(CAPILLARY_COST_GLSL)

class QuickCapillaryBloomRenderer(NativeFragmentPass):
    transition_id = "capillary_bloom"
    #: N5.2g: the native pack's text (the native define and the gradient's dFdy sign, capillary_native_fragment).
    fragment_source = capillary_native_fragment()
    native_samplers = (("uArrival", NATIVE_ARRIVAL, "linear"), ("uExtent", NATIVE_EXTENT, "nearest"))
    native_settled = CAPILLARY_SETTLE[1]      # the eased progress from which the frame is the new picture

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in CAPILLARY_BLOOM_BLOCK

    @classmethod
    def native_field_sources(cls) -> dict[str, str]:
        from rendering.quick.scene3d.native_fields import propagation_sources

        return propagation_sources("capillary", CAPILLARY_COST_GLSL)

    def native_fields(self, run, pixels: tuple[int, int]) -> tuple[NativeFieldRequest, ...]:
        """N5.2g: the run's arrival field and extent as one field recipe (``PropagationField``'s dispatches), sampling
        no picture."""
        from rendering.quick.scene3d.native_fields import propagation_recipe

        count, fibres, seed = capillary_bloom_parameters(run.request.parameter_dict())
        size = (int(pixels[0]), int(pixels[1]))
        _key, sources, bound, cost_values = self._field_inputs(count, fibres, seed, size)
        return (NativeFieldRequest(None, propagation_recipe("capillary", _SEED_LAYOUT, size, sources, bound,
                                                            cost_values, arrival=NATIVE_ARRIVAL,
                                                            extent=NATIVE_EXTENT)),)

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (no GL): the one owner, packed by ``_draw`` and filled by the
        native core (N5.2g)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        _count, _fibres, seed = capillary_bloom_parameters(frame.run.request.parameter_dict())
        return {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size, "uProgress": progress,
                "uSeed": float(seed % 65536), "uShow": _shown(progress)}

    @staticmethod
    def _field_inputs(count: int, fibres: float, seed: int, size: tuple[int, int]):
        aspect = size[0] / max(1, size[1])
        sources, grain = capillary_sources(seed, count, aspect)
        # The paper's cost values (the seed's pass block).
        cost_values = {"uGrain": grain, "uFibres": fibres, "uSeed": float(seed % 65536)}
        key = (seed, count, round(fibres, 6), round(aspect, 4))
        return key, sources, CAPILLARY_COST, cost_values


def create_transition_renderer() -> QuickCapillaryBloomRenderer:
    return QuickCapillaryBloomRenderer()
