"""E8: cast-shadow receiver occupies visible floor-side pixels at every view."""
from __future__ import annotations

import itertools
import math
import pytest

from rendering.gl_programs.extruded_spectrum_program import (
    EXTRUDED_CEILING, EXTRUDED_MAX_TILT, EXTRUDED_MAX_TURN,
    EXTRUDED_SHADOW_CAST_REACH, extruded_project, extruded_shadow_project,
)


def test_receiver_is_screen_directional_and_far_enough_from_the_bases():
    for tilt, turn in itertools.product((0.0, 0.12, 0.35, 0.65, 1.0),
                                        (-1.0, -0.75, -0.25, 0.0, 0.25, 0.75, 1.0)):
        angle, yaw = tilt * EXTRUDED_MAX_TILT, turn * EXTRUDED_MAX_TURN
        foot = extruded_shadow_project((0.0, EXTRUDED_CEILING, -0.25), angle, yaw, (0.0, 0.0))
        cast = extruded_shadow_project((0.0, EXTRUDED_CEILING, -0.25), angle, yaw, (0.22, 0.22))
        assert cast[0] - foot[0] == pytest.approx(.22 * EXTRUDED_CEILING * EXTRUDED_SHADOW_CAST_REACH)
        assert foot[1] - cast[1] == pytest.approx(.22 * EXTRUDED_CEILING * EXTRUDED_SHADOW_CAST_REACH)
        # New physical-acceptance oracle: a tall bar's cast clears 30% of its own
        # authored world-unit height in BOTH screen directions, not a tiny corner.
        assert cast[0] - foot[0] > .3 and foot[1] - cast[1] > .3


def test_signed_cardinals_do_not_create_perpendicular_sweep():
    p=(0.0, .95, -.3)
    for t in (-math.pi,-1.0,0,1.0,math.pi):
        base=extruded_shadow_project(p,.3,t,(0,0))
        right=extruded_shadow_project(p,.3,t,(.22,0))
        down=extruded_shadow_project(p,.3,t,(0,.22))
        left=extruded_shadow_project(p,.3,t,(-.22,0))
        up=extruded_shadow_project(p,.3,t,(0,-.22))
        assert right[0]>base[0]>left[0]
        assert down[1]<base[1]<up[1]
        assert right[1]==pytest.approx(base[1])==left[1]
        assert down[0]==pytest.approx(base[0])==up[0]


def test_zero_height_has_no_cast_displacement():
    for x,z in ((.7,-.2),(-1.2,0)):
        for tilt,turn in ((0,0),(.4,1.2)):
            assert extruded_shadow_project((x,0,z),tilt,turn,(.22,.22)) == pytest.approx(
                extruded_project((x,0,z),tilt,turn))


def test_shadow_vertex_program_never_uses_reserved_cast_identifier():
    """Catch GLSL lexer failures before the first Windows real-GL frame.

    Python parsing can validate an embedded shader string without ever
    compiling it. The shadow receiver must use a legal GLSL variable name.
    """
    import re
    from rendering.gl_programs.extruded_spectrum_program import EXTRUDED_VERTEX_SOURCE

    assert "vec3 shadowPoint = extrudedShadowProject(" in EXTRUDED_VERTEX_SOURCE
    assert not re.search(r"\b(?:vec[234]|float|int)\s+cast\b", EXTRUDED_VERTEX_SOURCE)


def test_receiver_keeps_base_footprint_and_horizontal_top_reach():
    from rendering.quick.scene3d.shadows import extruded_shadow_length
    assert extruded_shadow_length('Nearby') < extruded_shadow_length('Distant')
    assert extruded_shadow_length('Distant') == pytest.approx(0.22)
    for tilt, turn in ((0.4, 0.8), (0.0, -0.3), (1.1, 2.0)):
        for z in (-0.5, 0.0):
            base = (0.3, 0.0, z)
            assert extruded_shadow_project(base, tilt, turn, (0.22, 0.22)) == pytest.approx(
                extruded_project(base, tilt, turn))
            top = (0.3, EXTRUDED_CEILING, z)
            far = extruded_shadow_project(top, tilt, turn, (0.0, 0.0))
            front = extruded_project((top[0], 0, 0), tilt, turn)
            assert far[1] == pytest.approx(front[1])
            near_cast = extruded_shadow_project(top, tilt, turn, (0.045, 0.045))
            far_cast = extruded_shadow_project(top, tilt, turn, (0.22, 0.22))
            assert abs(far_cast[0] - far[0]) > abs(near_cast[0] - far[0])
            assert abs(far_cast[1] - far[1]) > abs(near_cast[1] - far[1])
