"""Refraction through thin layers (shared primitive, proved on its own): a flat layer bends nothing,
a tilted one bends the view toward the downhill side by more as it thickens, dispersion spreads the
channels symmetrically around green, Fresnel runs from f0 facing to 1 grazing, and the GPU equals
the CPU mirrors."""
from __future__ import annotations

import random

import pytest

from rendering.gl_programs.refraction import (
    REFRACTION_GLSL,
    REFRACTION_IOR_WATER,
    dispersion_shifts,
    fresnel_schlick,
    layer_normal,
    refraction_offset,
)


def test_a_flat_layer_bends_nothing_and_a_tilted_one_bends_downhill():
    assert refraction_offset((0.0, 0.0, 1.0), 0.05, REFRACTION_IOR_WATER) == pytest.approx((0.0, 0.0))
    # The surface rises to the right (gradient +x): the normal leans left, the view bends right... into the
    # thicker water, which is what makes a dome magnify.
    thin = refraction_offset(layer_normal((0.8, 0.0)), 0.02, REFRACTION_IOR_WATER)
    thick = refraction_offset(layer_normal((0.8, 0.0)), 0.06, REFRACTION_IOR_WATER)
    assert thin[0] > 0.0 and thin[1] == pytest.approx(0.0)
    assert thick[0] == pytest.approx(3.0 * thin[0])


def test_dispersion_spreads_channels_around_green_and_fresnel_spans_f0_to_one():
    red, green, blue = dispersion_shifts((0.01, 0.02), 1.0, 16 / 9)
    assert green == pytest.approx((0.01 * 9 / 16, -0.02))
    assert (red[0] + blue[0]) / 2 == pytest.approx(green[0]) and abs(blue[0]) > abs(green[0]) > abs(red[0])
    assert dispersion_shifts((0.01, 0.02), 0.0, 1.0) == ((0.01, -0.02),) * 3
    assert fresnel_schlick(1.0, 0.02) == pytest.approx(0.02) and fresnel_schlick(0.0, 0.02) == pytest.approx(1.0)


@pytest.mark.qt
def test_the_helpers_match_their_mirrors_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(8)
        cases = [((rng.uniform(-2, 2), rng.uniform(-2, 2)), rng.uniform(0.0, 0.08)) for _ in range(96)]
        gpu = probe.run("vec3 n = layerNormal(arg(0).xy); FragColor = vec4(refractionOffset(n, arg(0).z, 1.333), "
                        "fresnelSchlick(n.z, 0.02), n.z);",
                        [[(*g, h)] for g, h in cases], declarations=REFRACTION_GLSL)
        expected = []
        for gradient, thickness in cases:
            n = layer_normal(gradient)
            expected.append((*refraction_offset(n, thickness, 1.333), fresnel_schlick(n[2], 0.02), n[2]))
        _check(gpu, expected)
    finally:
        probe.close()
