"""Spectral layers: a shared, import-safe helper (GLSL plus CPU mirrors, no GL) for splitting a
picture into a few coloured layers that add back up to it exactly (Chromatic Shear first; any
prism, dispersion or rainbow effect can reuse it rather than an ad-hoc red/green/blue split).

``SPECTRAL_LAYERS`` layers run from red (0) to violet (last). Each layer's weight is a smooth
three-lobe colour (a red lobe that returns faintly at violet, green, blue), normalised so the
layers' weights sum to exactly one in every channel: drawn with no offsets, the layers rebuild the
photograph exactly; offset by different amounts, they fan into a rainbow fringe.

* ``spectralWeight(i)``: layer ``i``'s normalised RGB weight;
* ``spectralPosition(i)``: where layer ``i`` sits in the spectrum, 0 red to 1 violet.
"""

from __future__ import annotations

import math

SPECTRAL_LAYERS = 7


def spectral_colour(x: float) -> tuple[float, float, float]:
    """The unnormalised colour at spectrum position ``x`` (0 red, 1 violet)."""
    def lobe(centre: float, width: float) -> float:
        return math.exp(-((x - centre) / width) ** 2)
    return lobe(0.0, 0.3) + 0.35 * lobe(1.0, 0.18), lobe(0.45, 0.25), lobe(0.88, 0.25)


def spectral_position(i: int) -> float:
    return i / (SPECTRAL_LAYERS - 1)


def _weights() -> tuple[tuple[float, float, float], ...]:
    raw = [spectral_colour(spectral_position(i)) for i in range(SPECTRAL_LAYERS)]
    totals = [sum(c[k] for c in raw) for k in range(3)]
    return tuple(tuple(c[k] / totals[k] for k in range(3)) for c in raw)


SPECTRAL_WEIGHTS = _weights()


def spectral_weight(i: int) -> tuple[float, float, float]:
    """CPU mirror of ``spectralWeight``."""
    return SPECTRAL_WEIGHTS[i]


SPECTRAL_GLSL = (
    f"const int SPECTRAL_LAYERS = {SPECTRAL_LAYERS};\n"
    f"const vec3 SPECTRAL_WEIGHTS[{SPECTRAL_LAYERS}] = vec3[](\n"
    + ",\n".join(f"    vec3({r:.9f}, {g:.9f}, {b:.9f})" for r, g, b in SPECTRAL_WEIGHTS)
    + "\n);\n"
    + """vec3 spectralWeight(int i) { return SPECTRAL_WEIGHTS[i]; }
float spectralPosition(int i) { return float(i) / float(SPECTRAL_LAYERS - 1); }
"""
)
