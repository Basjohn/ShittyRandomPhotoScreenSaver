"""Photo surfaces (shared primitive, proved on its own): contact occlusion matches its CPU mirror on
the GPU, darkens a hollow and leaves a peak and a flat field open; brightness is the copy's
luminance and the frost's taps are normalised (a flat copy frosts to itself)."""
from __future__ import annotations

import math
import random

import pytest

from rendering.gl_programs.photo_surface import (
    PHOTO_LUMA,
    PHOTO_SURFACE_GLSL,
    photo_occlusion,
    photo_occlusion_glsl,
)

_BUMP_GLSL = "float bump(vec2 uv) { vec2 d = uv - 0.5; return 0.1 * exp(-dot(d, d) * 40.0); }\n"


def _bump(uv: tuple[float, float]) -> float:
    dx, dy = uv[0] - 0.5, uv[1] - 0.5
    return 0.1 * math.exp(-(dx * dx + dy * dy) * 40.0)


def test_a_hollow_darkens_and_a_peak_or_a_flat_field_stays_open():
    reach = (0.03, 0.03)
    assert photo_occlusion(_bump, (0.5, 0.5), _bump((0.5, 0.5)), reach, 0.1) == 0.0      # the peak
    assert photo_occlusion(lambda uv: 0.05, (0.3, 0.3), 0.05, reach, 0.1) == 0.0         # flat
    pit = photo_occlusion(_bump, (0.5, 0.5), 0.0, reach, 0.1)                            # sunk under the bump
    assert pit == 1.0
    flank = photo_occlusion(_bump, (0.62, 0.5), _bump((0.62, 0.5)), reach, 0.1)
    assert 0.0 < flank < 1.0


@pytest.mark.qt
def test_occlusion_brightness_and_frost_match_on_the_gpu(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        rng = random.Random(5)
        cases = [((rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8)), rng.uniform(-0.02, 0.1),
                  (rng.uniform(0.005, 0.06), rng.uniform(0.005, 0.06))) for _ in range(96)]
        gpu = probe.run("vec4 a = arg(0); FragColor = vec4(photoOcclusion(a.xy, a.z, arg(1).xy, 0.1), 0.0, 0.0, 0.0);",
                        [[(*uv, here, 0.0), reach] for uv, here, reach in cases],
                        declarations=_BUMP_GLSL + photo_occlusion_glsl("bump"))
        _check(gpu, [photo_occlusion(_bump, uv, here, reach, 0.1) for uv, here, reach in cases])

        # The argument texture itself, one flat colour, stands in for a photo copy.
        colour = (0.8, 0.4, 0.1)
        gpu = probe.run("vec2 uv = vec2(0.5); FragColor = vec4(photoFrost(uArgs, uv, 0.0), photoBrightness(uArgs, uv, 0.0));",
                        [[colour] for _ in range(8)], declarations=PHOTO_SURFACE_GLSL)
        luma = sum(c * w for c, w in zip(colour, PHOTO_LUMA))
        _check(gpu, [(*colour, luma)] * 8)
    finally:
        probe.close()
