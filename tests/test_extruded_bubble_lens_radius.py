"""Near-camera defocus reads a bubble's steady radius: breathing never refocuses the lens (operator 2026-10-24)."""
import numpy as np
import pytest

from rendering.gl_programs.extruded_bubble_scene import SHELL_FLOATS, bubble_instances


def _record(displayed, nominal, ident=7):
    # x, y, z, displayed radius, alpha, swell (displayed / nominal - 1), identity, cluster (-1: none)
    return (0.0, 0.0, -4.0, displayed, 1.0, displayed / nominal - 1.0, float(ident), -1.0)


def test_a_breathing_bubble_keeps_one_lens_radius_while_its_drawn_radius_swings():
    nominal = 0.8
    breaths = [bubble_instances(_record(displayed, nominal)) for displayed in (0.4, 0.8, 1.6, 2.2)]
    assert all(row.shape == (1, SHELL_FLOATS) for row in breaths)
    drawn = [row[0, 3] for row in breaths]
    lens = [row[0, 7] for row in breaths]
    assert len(set(drawn)) == 4                          # the shell itself still breathes
    assert lens == pytest.approx([nominal] * 4, rel=1e-6)   # the lens does not
