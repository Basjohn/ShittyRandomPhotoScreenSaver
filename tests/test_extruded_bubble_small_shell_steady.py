"""A small resting bubble keeps steady light as it drifts by fractions of a pixel (no shimmer; operator 2026-10-24)."""
import numpy as np
import pytest

from tests.test_extruded_bubble_world_gpu import sphere_pixels  # noqa: F401  (fixture)


def _shimmer(sphere_pixels, radius):
    width, height = sphere_pixels.frame_size
    pixel_world = 2 * 6.0 * np.tan(np.radians(22.5)) / height          # one pixel at the bubble's depth (FOV 45)
    totals = []
    for step in range(16):
        centre = (step / 16 * pixel_world, step / 16 * 0.37 * pixel_world, -6.0)
        pixels, _ = sphere_pixels('ordinary', centre=centre, radius=radius, diag=0,
                                  uSkyTint=(.3, .4, .5), uShaftColour=(.5, .6, .7), uSpeckGlow=.6,
                                  uLightDir=(0., .3, .95), uSpecColour=(60., 60., 60.), uSpecShape=(.05, .25, .012),
                                  uLightStrength=1.)
        totals.append(float(pixels[..., :3].sum()))
    totals = np.asarray(totals)
    return float(totals.std() / max(totals.mean(), 1e-9)), pixel_world


@pytest.mark.qt
@pytest.mark.parametrize('pixels_across', [3.0, 4.5])
def test_a_small_resting_bubble_does_not_shimmer_as_it_drifts(sphere_pixels, pixels_across):
    _cv, pixel_world = _shimmer(sphere_pixels, 0.01)
    variation, _ = _shimmer(sphere_pixels, 0.5 * pixels_across * pixel_world)
    print(f'{pixels_across} px: light varies {variation:.3%} across sub-pixel offsets')
    assert variation < 0.03
