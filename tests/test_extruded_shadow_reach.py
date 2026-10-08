"""Target allocation and actual Edit footprint both contain admitted shadows."""
from __future__ import annotations

import dataclasses
import itertools

import numpy as np
import pytest

from rendering.gl_programs.extruded_spectrum_program import (
    EXTRUDED_CEILING, EXTRUDED_MAX_TILT, EXTRUDED_MAX_TURN,
    extruded_project, extruded_reach, extruded_shadow_project,
)
from rendering.quick.scene3d.shadows import directional_shadow_vector
from rendering.quick.visualizer.edit_content_envelope import resolve_edit_content_envelope
from tests.test_qtquick_extruded_spectrum import _snapshot, _with_shadow_style, target
from widgets.spotify_visualizer.render_state import freeze_render_fields
from OpenGL import GL as gl


def test_shadow_ceiling_sweep_contains_projected_corners_and_off_bounds_are_exact():
    field, centre, half_span, fit = (0.0, 0.0, 500.0, 200.0), 250.0, 1.2, (1.0, 0.0)
    escaped_old_bound = 0
    for tilt, turn, depth, reflection, offset in itertools.product(
        (0.0, 0.3, 0.7, 1.0), (-1.0, -0.75, -0.5, 0.0, 0.5, 0.75, 1.0),
        (0.01, 0.6), (0.0, 0.5),
        ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (-1, 1), (1, -1)),
    ):
        tilt, turn = tilt * EXTRUDED_MAX_TILT, turn * EXTRUDED_MAX_TURN
        vector = directional_shadow_vector(offset, 0.22)
        args = (field, centre, half_span, depth, tilt, turn, fit, reflection)
        old = extruded_reach(*args)
        assert extruded_reach(*args, shadow_vector=(0.0, 0.0)) == old
        expanded = extruded_reach(*args, shadow_vector=vector)
        for x, z, height in itertools.product((-half_span, half_span), (-depth, 0.0), (0.0, 0.3, EXTRUDED_CEILING)):
            sx, sy, _ = extruded_shadow_project((x, height, z), tilt, turn, vector)
            px, py = centre + sx * 200.0, 200.0 - sy * 200.0
            assert expanded[0] - 1e-9 <= px <= expanded[2] + 1e-9
            assert expanded[1] - 1e-9 <= py <= expanded[3] + 1e-9
            if not (old[0] <= px <= old[2] and old[1] <= py <= old[3]):
                escaped_old_bound += 1
    assert escaped_old_bound > 100             # restoring old bounds meaningfully fails containment


@pytest.mark.qt
def test_rejected_shadow_never_expands_edit_bounds_target_or_pixels(target):
    """Saved historical options cannot re-admit a rejected pass or offscreen allocation."""
    from core.settings.visualizer_mode_registry import EXTRUDED_CAST_SHADOW_AVAILABLE

    assert EXTRUDED_CAST_SHADOW_AVAILABLE is False
    capture, host = target
    snapshot = _with_shadow_style(_snapshot(
        extruded_spectrum_allow_overflow=True, extruded_spectrum_shadow_enabled=True,
        extruded_spectrum_shadow_strength=1.0, extruded_spectrum_reflection=0.0,
        extruded_spectrum_face_mirror=0.0, spectrum_ghosting_enabled=False,
    ), offset=(5.0, 5.0))
    parameters = dict(snapshot.logical.mode_state.parameters)
    parameters['bar_count'] = snapshot.logical.common.bar_count
    original = resolve_edit_content_envelope(
        'extruded_spectrum', snapshot.presentation, parameters, logical=snapshot.logical)
    with_shadow = capture.render(host, snapshot, (0.88, 0.73, 0.49, 1.0))
    parameters['extruded_spectrum_shadow_enabled'] = False
    off = dataclasses.replace(snapshot.logical.mode_state, parameters=freeze_render_fields(parameters))
    disabled = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=off))
    without_shadow = capture.render(host, disabled, (0.88, 0.73, 0.49, 1.0))
    assert np.array_equal(with_shadow, without_shadow)
    assert resolve_edit_content_envelope(
        'extruded_spectrum', snapshot.presentation, parameters, logical=disabled.logical) == original
