"""Stable architecture gates for Melt's analytic gravity melt."""

from rendering.gl_programs.melt_drip_program import MELT_FRAGMENT_SOURCE


def test_melt_keeps_the_rejected_forms_out():
    source = MELT_FRAGMENT_SOURCE
    # Binding negative controls: detached drop bodies (capsules/bulbs) and a
    # ray-marched pseudo-volume were both rejected as not reading as liquid.
    assert "capsule(" not in source
    assert "vec3 bulb" not in source
    assert "ray=" not in source
    assert "for(int step=" not in source
    assert "distance+=" not in source
    # Analytic in progress: no clock of its own.
    assert "uTime" not in source


def test_melt_is_steered_by_an_origin_with_gravity():
    source = MELT_FRAGMENT_SOURCE
    assert "uniform vec2 uItemSize,uOrigin;" in source
    assert "uOriginMode" in source
    assert "uDirection" not in source
    assert "float meltStart(" in source
    # Weight: melted paint sags with the square of its age.
    assert "float sagOf(float a,float drip){return a*a*" in source


def test_melt_noise_uses_an_exact_lattice_hash():
    # A chaotic float hash rounded the same lattice corner differently in
    # neighbouring cells and cut the photograph into hard-edged rectangles.
    source = MELT_FRAGMENT_SOURCE
    assert "uvec3 v=uvec3(" in source
    assert "fract(p*vec2(123.34,456.21)" not in source
