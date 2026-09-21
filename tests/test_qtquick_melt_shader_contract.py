"""Stable architecture gates for Melt's cohesive screen-space liquid front."""

from rendering.gl_programs.melt_drip_program import MELT_FRAGMENT_SOURCE


def test_melt_has_one_connected_front_without_detached_primitive_bodies():
    source = MELT_FRAGMENT_SOURCE
    # The rejected implementations manufactured drops from capsules/bulbs or
    # ray-marched a pseudo-volume.  Melt's silhouette must remain one graph so
    # every rivulet stays attached to the same source film.
    assert "capsule(" not in source
    assert "vec3 bulb" not in source
    assert "float frontAt(" in source
    assert "signedDepth=front-flow" in source
    assert "for(int i=0;i<12;i++)" in source


def test_melt_keeps_optics_shallow_and_does_not_texture_shred():
    source = MELT_FRAGMENT_SOURCE
    assert "ray=" not in source
    assert "for(int step=" not in source
    assert "distance+=" not in source
    assert "materialUv=clamp(screen+refractOffset-gravity*pull" in source
    assert "float meniscus=" in source
    assert "float streak=" in source
    assert "uTime" not in source
