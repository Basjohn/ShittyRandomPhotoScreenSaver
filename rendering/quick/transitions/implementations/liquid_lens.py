"""Lazy Quick renderer for Liquid Lens: a lens of water hops between pitstops, growing at each,
then floods the picture with the next one."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_STOPS_RANGE
from rendering.gl_programs.liquid_lens_program import LIQUID_LENS_FRAGMENT_SOURCE, lens_height, lens_plan, lens_state
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame


def liquid_lens_parameters(parameters: Mapping[str, object]) -> tuple[float, float, int, int]:
    """The resolved refraction, dispersion, stops and seed, validated before any GL state changes."""
    values = []
    for name in ("refraction", "dispersion"):
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"Liquid Lens needs a resolved {name} between 0 and 1")
        values.append(float(value))
    stops, seed = parameters.get("stops"), parameters.get("seed")
    if isinstance(stops, bool) or not isinstance(stops, int) or not LIQUID_LENS_STOPS_RANGE[0] <= stops <= LIQUID_LENS_STOPS_RANGE[1]:
        raise ValueError("Liquid Lens needs a resolved number of stops")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Liquid Lens needs a resolved seed")
    return values[0], values[1], stops, seed


def _shown(progress: float) -> int:
    """What the frame shows: the old picture before the run; the new one at its end, or once the water has flattened
    out over a lens covering everything; else the effect."""
    if progress <= 0.0:
        return SHOW_OLD
    if progress >= 1.0 or (progress > 0.9 and lens_height(progress) <= 0.0):
        return SHOW_NEW
    return SHOW_EFFECT


class QuickLiquidLensRenderer(NativeFragmentPass):
    transition_id = "liquid_lens"
    fragment_source = LIQUID_LENS_FRAGMENT_SOURCE

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in LIQUID_LENS_BLOCK

    def __init__(self) -> None:
        self._plan_key = None
        self._plan = None

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (validated first; no GL): the one owner, packed by ``render``
        and filled by the native core (N5.2b). The run's plan is a few numbers, kept for the run."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        refraction, dispersion, stops, seed = liquid_lens_parameters(frame.run.request.parameter_dict())
        values: dict[str, object] = {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size,
                                     "u_target_px": frame.item_pixels, "uShow": _shown(progress),
                                     "uSeed": float(seed % 9973), "uRefraction": refraction,
                                     "uDispersion": dispersion}
        width, height = frame.logical_size
        aspect = width / max(1e-6, height)
        key = (frame.run.run_id, stops, seed, round(aspect, 6))
        if key != self._plan_key:
            self._plan_key, self._plan = key, lens_plan(stops, seed, aspect)
        duration = frame.run.request.duration_ms / 1000.0
        state = lens_state(self._plan, progress, duration)
        values.update({"uTime": progress * duration, "uCentre": state.centre, "uRadius": state.radius,
                       "uThick": state.thickness, "uReference": state.reference, "uEnvelope": state.envelope,
                       "uRound": state.rounding, "uBulge": state.bulge, "uTwist": state.twist,
                       "uRipple": state.ripple})
        return values


def create_transition_renderer() -> QuickLiquidLensRenderer:
    return QuickLiquidLensRenderer()
