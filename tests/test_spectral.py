"""Spectral layers (shared primitive, proved on its own): the layers' weights add up to exactly one
in every channel (unshifted layers rebuild a picture), run from red through green to blue, and the
GPU table equals the CPU one."""
from __future__ import annotations

import pytest

from rendering.gl_programs.spectral import SPECTRAL_GLSL, SPECTRAL_LAYERS, spectral_position, spectral_weight


def test_weights_add_up_to_one_and_run_red_to_violet():
    for channel in range(3):
        assert sum(spectral_weight(i)[channel] for i in range(SPECTRAL_LAYERS)) == pytest.approx(1.0, abs=1e-12)
    first, middle, last = spectral_weight(0), spectral_weight(SPECTRAL_LAYERS // 2), spectral_weight(SPECTRAL_LAYERS - 1)
    assert first[0] > first[1] and first[0] > first[2]
    assert middle[1] > middle[0] and middle[1] > middle[2]
    assert last[2] > last[1]
    assert spectral_position(0) == 0.0 and spectral_position(SPECTRAL_LAYERS - 1) == 1.0


@pytest.mark.qt
def test_the_gpu_table_matches(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check

    probe = _GlslProbe()
    try:
        gpu = probe.run("int i = int(arg(0).x); FragColor = vec4(spectralWeight(i), spectralPosition(i));",
                        [[(float(i),)] for i in range(SPECTRAL_LAYERS)], declarations=SPECTRAL_GLSL)
        _check(gpu, [(*spectral_weight(i), spectral_position(i)) for i in range(SPECTRAL_LAYERS)], tolerance=1e-6)
    finally:
        probe.close()
