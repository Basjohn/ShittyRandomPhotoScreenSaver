"""Lazy Quick renderer for VHS Distortion: tracking is lost and the picture rolls to the next one."""

from __future__ import annotations

from collections.abc import Mapping


from rendering.gl_programs.vhs_program import VHS_FRAGMENT_SOURCE, VHS_PERIOD, vhs_envelope, vhs_roll
from ..fullscreen_pass import SHOW_EFFECT, SHOW_NEW, SHOW_OLD, NativeFragmentPass
from ..render_contract import QuickTransitionRenderFrame

_ROLL_SIGN = {"up": 1.0, "down": -1.0}


def vhs_parameters(parameters: Mapping[str, object]) -> tuple[float, float, float, int]:
    """The resolved tracking, colour bleed, noise and seed, validated before any GL state changes."""
    values = []
    for name in ("tracking", "bleed", "noise"):
        value = parameters.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"VHS Distortion needs a resolved {name} between 0 and 1")
        values.append(float(value))
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("VHS Distortion needs a resolved seed")
    return values[0], values[1], values[2], seed


def _shown(envelope: float, roll: float) -> int:
    """What the frame shows: a clean signal before the roll (the old picture) and after hold and tracking have settled
    (the new one); else the effect."""
    if envelope <= 0.0 and roll <= 0.0:
        return SHOW_OLD
    if envelope <= 0.0 and roll >= VHS_PERIOD:
        return SHOW_NEW
    return SHOW_EFFECT


class QuickVhsRenderer(NativeFragmentPass):
    transition_id = "vhs"
    fragment_source = VHS_FRAGMENT_SOURCE

    _SAMPLERS = ("uOldTex", "uNewTex")      # every other value is in VHS_BLOCK

    def block_values(self, frame: QuickTransitionRenderFrame) -> dict[str, object]:
        """Every value of the pass block for this frame (validated first; no GL): the one owner, packed by ``render``
        and filled by the native core (N5.2b)."""
        progress = max(0.0, min(1.0, float(frame.sample.eased_progress)))
        code = str(frame.run.request.direction)
        if code not in _ROLL_SIGN:
            raise ValueError(f"unknown resolved VHS Distortion direction: {code!r}")
        tracking, bleed, noise, seed = vhs_parameters(frame.run.request.parameter_dict())
        envelope, roll = vhs_envelope(progress), vhs_roll(progress)
        return {"uMatrix": frame.matrix_values, "uItemSize": frame.logical_size, "u_target_px": frame.item_pixels,
                "uShow": _shown(envelope, roll), "uEnvelope": envelope, "uRoll": roll, "uRollSign": _ROLL_SIGN[code],
                "uTime": progress * frame.run.request.duration_ms / 1000.0, "uSeed": float(seed),
                "uTracking": tracking, "uBleed": bleed, "uNoise": noise}


def create_transition_renderer() -> QuickVhsRenderer:
    return QuickVhsRenderer()
