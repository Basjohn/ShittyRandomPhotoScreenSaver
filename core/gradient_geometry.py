"""Qt-free geometry for a two-endpoint linear gradient, independent of palettes."""
from __future__ import annotations

import math

MIN_GRADIENT_SPAN = .05


def admit_gradient_endpoints(values) -> tuple[float, float, float, float]:
    """Dark XY then Light XY in normalized top-left coordinates.

    The minimum span is an explicit editor constraint; coincident endpoints
    have no gradient direction and must not produce an undefined shader input.
    """
    try:
        result = tuple(float(value) for value in values)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Gradient endpoints require four finite coordinates") from error
    if len(result) != 4 or not all(math.isfinite(value) for value in result):
        raise ValueError("Gradient endpoints require four finite coordinates")
    result = tuple(max(0., min(1., value)) for value in result)
    if math.hypot(result[2] - result[0], result[3] - result[1]) < MIN_GRADIENT_SPAN:
        raise ValueError("Gradient endpoints are closer than the minimum span")
    return result


def project_linear_gradient(values, aspect: float) -> tuple[float, float, float]:
    """Return vector XY and centre-relative bias for a physical endpoint line.

    ``clamp(dot(uv - .5, vector) + .5 + bias, 0, 1)`` is exactly zero at Dark
    and one at Light. The aspect metric keeps the blend normal aligned with
    the drawn line on a non-square content surface.
    """
    dark_x, dark_y, light_x, light_y = admit_gradient_endpoints(values)
    if not math.isfinite(aspect) or aspect <= 0:
        raise ValueError("Gradient content aspect must be positive and finite")
    dx, dy = light_x - dark_x, light_y - dark_y
    denominator = dx * dx * aspect * aspect + dy * dy
    gx, gy = dx * aspect * aspect / denominator, dy / denominator
    bias = (.5 - dark_x) * gx + (.5 - dark_y) * gy - .5
    return gx, gy, bias
