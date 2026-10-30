"""Canonical EB physical drift field, shared by actors and bounded material paths.

The same expressions admit math scalars or NumPy arrays; GPU code only samples
frozen integrated displacement and never owns a second drift implementation.
"""
from __future__ import annotations
import math
from core.constants.extruded_bubble_world import WORLD_UNIT

# "wander" is the original per-bubble meander; the others steer the field and keep some meander so it is
# never robotic. Swirls orbit the stream axis and widen slowly, so BEAM births spiral out from the source.
DRIFT_DIRECTIONS = ("wander", "left", "right", "diagonal", "swish_across", "swish_depth", "random",
                    "swirl_cw", "swirl_ccw")
_STEER_SPEED = 0.10        # x WORLD_UNIT per second at full drift (left/right/diagonal)
_RANDOM_SPEED = 0.08
_SWISH_SPEED = 0.14
_SWISH_RATE = 0.55         # radians of motion phase per second of the shared swish carrier
_SWIRL_SPEED = 0.30        # tangential
_SWIRL_WIDEN = 0.06        # outward, so the orbit becomes a widening spiral
_STEERED_WANDER = 0.4      # share of the original meander kept under a steered direction
def steer(kind: str, position, phase: float, t: float, direction, across, depth_axis, axis_origin,
                 amount: float, *, ops=math):
    """Extra drift velocity for a Drift Direction; ``amount`` is the musical drift in world units/s."""
    def combine(a: float, b: float) -> tuple[float, float, float]:
        return tuple(amount * (a * u + b * v) for u, v in zip(across, depth_axis))

    if kind == "left":
        return combine(-_STEER_SPEED, 0.0)
    if kind == "right":
        return combine(_STEER_SPEED, 0.0)
    if kind == "diagonal":
        return combine(_STEER_SPEED * ops.sqrt(.5), _STEER_SPEED * ops.sqrt(.5))
    if kind == "random":  # a fixed heading per bubble, from its stable phase
        return combine(_RANDOM_SPEED * ops.cos(phase), _RANDOM_SPEED * ops.sin(phase))
    if kind in ("swish_across", "swish_depth"):
        # One shared carrier moves the field together; a small per-bubble lag keeps it organic.
        sway = _SWISH_SPEED * ops.sin(t * _SWISH_RATE - 0.35 * ops.sin(phase))
        return combine(sway, 0.0) if kind == "swish_across" else combine(0.0, sway)
    if kind in ("swirl_cw", "swirl_ccw"):
        r = tuple(p - o for p, o in zip(position, axis_origin))
        along = sum(a * d for a, d in zip(r, direction))
        radial = tuple(a - along * d for a, d in zip(r, direction))
        distance = ops.sqrt(sum(a * a for a in radial))
        if ops is math:
            radial = (tuple(math.cos(phase) * u + math.sin(phase) * v for u, v in zip(across, depth_axis))
                      if distance < 1e-3 * WORLD_UNIT else tuple(a / distance for a in radial))
        else:
            # These arrays are identical for all three vector components.
            # Reuse them without changing elementwise arithmetic or history.
            near_axis = distance < 1e-3 * WORLD_UNIT
            if not near_axis.any():
                # Nothing sits on the axis: the where() below would take a / distance for every record
                # (distance is then above the 1e-12 guard), so skip the fallback's trig and selects.
                radial = tuple(a / distance for a in radial)
            else:
                safe_distance = ops.maximum(distance, 1e-12)
                cosine, sine = ops.cos(phase), ops.sin(phase)
                radial = tuple(ops.where(near_axis,
                                        cosine * u + sine * v,
                                        a / safe_distance)
                               for a, u, v in zip(radial, across, depth_axis))
        # Counter-clockwise seen from the stream's end looking back at its source (right-hand rule).
        tangent = (direction[1] * radial[2] - direction[2] * radial[1],
                   direction[2] * radial[0] - direction[0] * radial[2],
                   direction[0] * radial[1] - direction[1] * radial[0])
        sign = 1.0 if kind == "swirl_ccw" else -1.0
        return tuple(amount * (sign * _SWIRL_SPEED * g + _SWIRL_WIDEN * q) for g, q in zip(tangent, radial))
    return (0.0, 0.0, 0.0)


def velocity(kind, position, phase, t, direction, across, depth_axis, axis_origin, amount, *, ops=math):
    """Full calibrated ordinary drift, scalar or batched; never includes stream/Sway/push."""
    meander = 1.0 if kind == 'wander' else _STEERED_WANDER
    wander = meander * amount * .05 * (ops.sin(t * .37 + phase) + .6 * ops.sin(t * .83 + 2.1 * phase))
    deep = meander * amount * .015 * ops.sin(t * .29 + 1.7 * phase)
    directed = steer(kind, position, phase, t, direction, across, depth_axis, axis_origin, amount, ops=ops)
    return tuple(u * wander + v * deep + d for u, v, d in zip(across, depth_axis, directed))
