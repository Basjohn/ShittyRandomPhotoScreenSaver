"""Physical-size and light-footprint accuracy of Bubble's opt-in particle glow.

The useful metric is luminance *outside* the unchanged core in scene pixels,
not the peak opacity or RGB at the point centre. No Qt/OpenGL is needed here;
actual GPU appearance and FPS must still be accepted natively.
"""
from __future__ import annotations

import math
from pathlib import Path


def _smoothstep(lo: float, hi: float, value: float) -> float:
    t = min(1.0, max(0.0, (value - lo) / (hi - lo)))
    return t * t * (3.0 - 2.0 * t)


def _sprite_diameter(body_diameter: float, glow: float) -> float:
    multiplier = 2.2 if glow <= 0.001 else 8.0 + 4.0 * min(1.0, max(0.0, glow / 6.0))
    return min(128.0, max(1.0, body_diameter * multiplier))


def _core_coverage(distance_px: float, body_diameter: float, glow: float) -> float:
    sprite = _sprite_diameter(body_diameter, glow)
    d = distance_px / (sprite * .5)
    ratio = min(1.0, body_diameter / sprite)
    return 1.0 - _smoothstep(.50 * ratio, 1.05 * ratio, d)


def _radiance(distance_px: float, body_diameter: float, glow: float) -> float:
    sprite = _sprite_diameter(body_diameter, glow)
    d = distance_px / (sprite * .5)
    if d > 1.0:
        return 0.0
    core = _core_coverage(distance_px, body_diameter, glow)
    response = 1.0 - math.exp(-.36 * max(0.0, glow))
    inner = math.exp(-((d / .18) ** 2))
    outer = math.exp(-((d / .66) ** 2))
    falloff = (.38 * inner + .72 * outer) * (1.0 - _smoothstep(.84, 1.0, d))
    return response * falloff * (1.0 - .96 * core)


def test_glow_keeps_the_exact_physical_core_at_all_intensities_and_sizes():
    for size in (1.4, 2.4, 7.0, 14.0):
        baseline = [_core_coverage(x * size / 20, size, 0.0) for x in range(25)]
        for glow in (0.6, 2.0, 4.0, 6.0):
            result = [_core_coverage(x * size / 20, size, glow) for x in range(25)]
            assert all(abs(a - b) < 1e-9 for a, b in zip(baseline, result))


def test_maximum_glow_lights_water_beyond_core_instead_of_making_a_solid_disc():
    # Typical 2.4px particle, 100% opacity, lightest colour. These are
    # emissive values before the particle's own stable per-dot opacity and tint.
    assert _core_coverage(2.0, 2.4, 6.0) == 0.0
    assert _core_coverage(8.0, 2.4, 6.0) == 0.0
    assert _radiance(5.0, 2.4, 6.0) > 0.35
    assert _radiance(8.0, 2.4, 6.0) > 0.20
    assert _radiance(11.0, 2.4, 6.0) > 0.10
    assert _radiance(14.4, 2.4, 6.0) == 0.0
    assert _radiance(8.0, 2.4, 6.0) > 3 * _radiance(8.0, 2.4, 0.65)


def test_emission_is_bounded_and_fades_at_the_sprite_edge():
    for glow in (0.0, 0.65, 2.0, 4.0, 6.0):
        sprite = _sprite_diameter(2.4, glow)
        values = [_radiance(sprite * .5 * i / 100, 2.4, glow) for i in range(101)]
        assert max(values) < 1.0
        assert values[-1] == 0.0
    assert _radiance(4.0, 2.4, 6.0) > _radiance(8.0, 2.4, 6.0)
    assert _radiance(8.0, 2.4, 6.0) > _radiance(12.0, 2.4, 6.0)


def test_shader_light_and_coverage_are_independent_and_physical_core_ratio_is_used():
    ambient = Path('rendering/quick/visualizer/implementations/bubble_ambient_gl.py').read_text()
    main = Path('widgets/spotify_visualizer/shaders/bubble.frag').read_text()
    assert 'vCoreRatio = min(1.0, coreDiameterPx / gl_PointSize);' in ambient
    assert 'alpha = core * uParticleColor.a;' in ambient
    assert 'emission = uParticleColor.rgb * response * falloff * coreShield' in ambient
    assert 'a > 0.00001 || light > 0.00001' in main
    assert 'if (a > 0.00001) {' not in main
