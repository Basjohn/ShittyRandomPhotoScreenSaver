"""Gravity melt renderer for Melt / Drip: the image melts from a chosen origin."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math


from rendering.gl_programs.melt_drip_program import MELT_FRAGMENT_SOURCE
from ..fullscreen_pass import NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame

# Resolved melt origins: (screen origin with y down, mode 0 = spread from the
# point, 1 = melt from every edge toward the centre).
MELT_ORIGINS: dict[str, tuple[tuple[float, float], float]] = {
    "top_left": ((0.0, 0.0), 0.0),
    "top_center": ((0.5, 0.0), 0.0),
    "top_right": ((1.0, 0.0), 0.0),
    "center_out": ((0.5, 0.5), 0.0),
    "center_in": ((0.5, 0.5), 1.0),
}


@dataclass(frozen=True, slots=True)
class MeltDripParameters:
    seed: int
    detail: float
    depth: float
    gloss: float
    origin: tuple[float, float]
    origin_mode: float


def melt_drip_parameters(
    parameters: Mapping[str, object], direction: object
) -> MeltDripParameters:
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Melt / Drip seed must be an integer between 1 and 65535")
    values: dict[str, float] = {}
    for name, lower, upper in (
        ("detail", 0.5, 2.0),
        ("depth", 0.0, 1.0),
        ("gloss", 0.0, 1.0),
    ):
        value = parameters.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"Melt / Drip {name} must be finite and numeric")
        numeric = float(value)
        if not lower <= numeric <= upper:
            raise ValueError(
                f"Melt / Drip {name} must be between {lower:g} and {upper:g}"
            )
        values[name] = numeric
    origin = MELT_ORIGINS.get(str(direction).strip().lower())
    if origin is None:
        raise ValueError(
            "Melt / Drip requires a resolved origin: " + ", ".join(MELT_ORIGINS)
        )
    return MeltDripParameters(
        seed,
        values["detail"],
        values["depth"],
        values["gloss"],
        origin[0],
        origin[1],
    )


class QuickMeltDripRenderer(NativeFragmentPass):
    transition_id = "melt_drip"
    fragment_source = MELT_FRAGMENT_SOURCE

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (validated first; no GL): the one owner, packed by ``render``
        and filled by the native core (N5.2b). The fragment draws each picture exactly at the run's ends itself."""
        params = melt_drip_parameters(frame.run.request.parameter_dict(), frame.run.request.direction)
        values: dict[str, object] = {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size,
                                     "u_target_px": frame.item_pixels}
        for name, value in (
            ("uProgress", frame.sample.eased_progress),
            ("uSeed", params.seed),
            ("uDetail", params.detail),
            ("uDepth", params.depth),
            ("uGloss", params.gloss),
            ("uOriginMode", params.origin_mode),
        ):
            values[name] = float(value)
        values["uOrigin"] = params.origin
        return values


def create_transition_renderer() -> QuickMeltDripRenderer:
    return QuickMeltDripRenderer()
