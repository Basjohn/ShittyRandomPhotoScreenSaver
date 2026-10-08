"""Target allocation and actual Edit footprint both contain admitted shadows."""
from __future__ import annotations

import dataclasses
import itertools

import numpy as np
import pytest

from rendering.gl_programs.extruded_spectrum_program import (
    EXTRUDED_CEILING, EXTRUDED_MAX_TILT, EXTRUDED_MAX_TURN,
    extruded_project, extruded_reach,
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
            sx, sy, _ = extruded_project((x + vector[0] * height, 0.0, z + vector[1] * height), tilt, turn)
            px, py = centre + sx * 200.0, 200.0 - sy * 200.0
            assert expanded[0] - 1e-9 <= px <= expanded[2] + 1e-9
            assert expanded[1] - 1e-9 <= py <= expanded[3] + 1e-9
            if not (old[0] <= px <= old[2] and old[1] <= py <= old[3]):
                escaped_old_bound += 1
    assert escaped_old_bound > 100             # restoring old bounds meaningfully fails containment


@pytest.mark.qt
def test_renderer_target_and_actual_edit_footprint_admit_shadows_with_gl_clip_negative_control(target, monkeypatch):
    from rendering.quick.visualizer.implementations import extruded_spectrum as implementation

    capture, host = target
    snapshot = _with_shadow_style(_snapshot(
        extruded_spectrum_allow_overflow=True, extruded_spectrum_shadow_enabled=True,
        extruded_spectrum_shadow_strength=1.0, extruded_spectrum_tilt=1.0,
        extruded_spectrum_turn=0.0, extruded_spectrum_reflection=0.0,
        extruded_spectrum_face_mirror=0.0, spectrum_ghosting_enabled=False,
    ), offset=(5.0, 5.0))
    presentation = dataclasses.replace(
        snapshot.presentation, outer_rect=(200.0, 130.0, 250.0, 150.0),
        content_rect=(200.0, 130.0, 250.0, 150.0), viewport_extent=(250.0, 150.0),
        current_aspect_ratio=250.0 / 150.0,
    )
    common = dataclasses.replace(snapshot.logical.common, bars=(2.0,) * snapshot.logical.common.bar_count)
    snapshot = dataclasses.replace(snapshot, presentation=presentation, logical=dataclasses.replace(snapshot.logical, common=common))
    backdrop = (0.88, 0.73, 0.49, 1.0)

    def render(candidate):
        # Production's render item is the saved stage, translated into the
        # window. The broader module's helper uses a whole-window item, which
        # cannot falsify clipping at this smaller item's scene target boundary.
        from tests.test_qtquick_extruded_spectrum import W, H

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.capture.fbo)
        gl.glViewport(0, 0, W, H)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(*backdrop)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        matrix = (2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0,
                  2 * 200 / W - 1, 1 - 2 * 130 / H, 0, 1)
        assert host.render(snapshot=candidate, viewport=(0, 0, W, H), logical_size=(250.0, 150.0),
                           matrix_values=matrix) == "extruded_spectrum"
        pixels = gl.glReadPixels(0, 0, W, H, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.flipud(np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(H, W, 4)).astype(np.int16)

    expanded = render(snapshot)
    parameters = dict(snapshot.logical.mode_state.parameters)
    parameters["bar_count"] = snapshot.logical.common.bar_count
    envelope = resolve_edit_content_envelope("extruded_spectrum", presentation, parameters, logical=snapshot.logical)
    assert envelope is not None
    parameters["extruded_spectrum_shadow_enabled"] = False
    off_envelope = resolve_edit_content_envelope("extruded_spectrum", presentation, parameters, logical=snapshot.logical)
    assert envelope != off_envelope
    assert envelope["right"] > off_envelope["right"]

    reach = implementation.extruded_reach
    monkeypatch.setattr(implementation, "extruded_reach", lambda *args, **kwargs: reach(*args))
    clipped = render(snapshot)
    difference = np.abs(expanded[..., :3] - clipped[..., :3]).max(axis=2)
    assert (difference > 8).sum() > 15          # old target actually cropped visible shadow pixels
    assert np.abs(expanded - clipped).max() > 8

    disabled_state = dataclasses.replace(snapshot.logical.mode_state, parameters=freeze_render_fields(parameters))
    disabled = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=disabled_state))
    disabled_old_bound = render(disabled)
    monkeypatch.setattr(implementation, "extruded_reach", reach)
    disabled_new_bound = render(disabled)
    assert np.array_equal(disabled_old_bound, disabled_new_bound)
