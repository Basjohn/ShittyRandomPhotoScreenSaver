"""Neon Lake's Water Lines: the water's face lines and its shoreline, with their glow, fade out and are skipped at 0.

At 0 nothing that belongs to a line can show: changing the lines' own colour alpha, Water Line Glow or Shore Glow
leaves every pixel as it was, while the water's body (shine, the Sun / Moon path) still draws. The mirrored surface
pass, which draws nothing but the water's lines, is not issued at 0. Values are test-owned, never preset values.
"""
from dataclasses import replace

import numpy as np

from core.settings.visualizer_mode_settings import Slider, require_mode_settings
from tests.test_neon_fidelity_controls import _lake_scene
from tests.test_neon_lake_renderer import target  # noqa: F401  (pytest fixture)
from tests.test_neon_water_layers import _difference

_KEY = "shockwave_grid_water_lines"
_WAVES = ((0.6, 0.0, -1.2, 1.4), (1.1, -0.3, -0.9, 1.2), (0.3, 0.3, -1.5, 1.2))


def _lake(amount, **parameters):
    """Half water, half land, lit lines and edge glow, crests on the water."""
    snapshot = _lake_scene(**{**dict(shockwave_grid_glow=0.8, shockwave_grid_water_detail=0.6,
                                     shockwave_grid_water_shine=0.7, shockwave_grid_shore_glow=1.5,
                                     shockwave_grid_water_line_glow=2.0, shockwave_grid_water_reaction=0.0,
                                     shockwave_grid_line_color=[90, 220, 255, 255],
                                     shockwave_grid_crest_color=[255, 80, 220, 255]),
                              **parameters, _KEY: amount})
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, events=_WAVES)))


def _changed(capture, host, a, b):
    return int((_difference(capture, host, a, b) > 24).sum())


def test_water_lines_is_one_spec_slider_in_the_water_bucket_beside_water_detail():
    spec = require_mode_settings("shockwave_grid")
    control = spec.control(_KEY)
    assert isinstance(control, Slider) and (control.low, control.high) == (0.0, 1.0)
    water = [entry.key for entry in spec.controls if entry.bucket == "waves"]
    assert water.index(_KEY) == water.index("shockwave_grid_water_detail") + 1


def test_at_zero_no_line_or_its_glow_can_show(target):
    capture, host = target
    variations = (
        dict(shockwave_grid_line_color=[90, 220, 255, 40]),            # the face lines' opacity
        dict(shockwave_grid_water_line_glow=0.0),                       # their glow
        dict(shockwave_grid_shore_glow=0.0),                            # the edge's glow
        dict(shockwave_grid_shore_glow_color=[0, 255, 0, 255]),         # its colour
    )
    for variation in variations:
        # Negative control: with the lines drawn, each of these changes the picture.
        assert _changed(capture, host, _lake(1.0), _lake(1.0, **variation)) > 100, variation
        assert _changed(capture, host, _lake(0.0), _lake(0.0, **variation)) == 0, variation


def test_at_zero_the_water_keeps_its_body(target):
    capture, host = target
    assert _changed(capture, host, _lake(1.0), _lake(0.0)) > 200, "the lines go"
    assert _changed(capture, host, _lake(0.0, shockwave_grid_water_shine=0.0),
                    _lake(0.0, shockwave_grid_water_shine=1.0)) > 500, "the water's shine still draws"


def test_the_lines_fade_between_one_and_zero(target):
    capture, host = target
    full = _difference(capture, host, _lake(0.0), _lake(1.0)).astype(float)
    half = _difference(capture, host, _lake(0.0), _lake(0.5)).astype(float)
    lit = full > 24
    share = half[lit].sum() / full[lit].sum()
    assert 0.2 < share < 0.8, f"half way is part way, never a switch ({share:.2f})"


def test_at_zero_water_reaction_keeps_only_a_flat_lift_with_no_pattern(target):
    capture, host = target
    loud = tuple((0.2 + k / 9.0, -0.4 + 0.2 * (k % 5), -1.0, 1.6) for k in range(36))   # a loud passage of waves

    def reaction(amount):
        """What Water Reaction adds to the frame (luma) at this Water Lines amount, driven by the passage."""
        def frame(react):
            # No bloom and no Sun / Moon path: the net is judged on its own pixels.
            snapshot = _lake(amount, shockwave_grid_water_reaction=react, shockwave_grid_water_detail=0.0,
                             shockwave_grid_shore_glow=0.0, shockwave_grid_glow=0.0, shockwave_grid_water_glint=0.0)
            snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
                snapshot.logical.mode_state, events=loud)))
            capture.render(host, snapshot)
            return capture.render(host, snapshot)[..., :3].astype(float).mean(axis=-1)
        return frame(1.0) - frame(0.0)

    drawn, hidden = reaction(1.0), reaction(0.0)
    # The lake: what the reaction lights with the lines drawn, on the water half of the basin (the land's ridges,
    # which breathe with the drive, stay out of it).
    lake = np.abs(drawn) > 6
    lake[:, int(0.45 * lake.shape[1]):] = False
    assert lake.mean() > 0.01, "the passage lights the lake"
    # The pattern is the addition minus its lake-wide mean: with the lines hidden next to none of it is left ...
    pattern = lambda image: np.abs(image[lake] - image[lake].mean()).mean()   # noqa: E731
    assert pattern(hidden) < 0.1 * pattern(drawn), (pattern(hidden), pattern(drawn))
    # ... while the lake as a whole is still lifted by the music.
    assert hidden[lake].mean() > 0.1 * drawn[lake].mean() > 0.0


def test_the_mirrored_line_pass_is_skipped_at_zero(target, monkeypatch):
    from OpenGL import GL as gl
    capture, host = target
    calls = []
    real = gl.glDrawArrays

    def counted(mode, first, count):
        calls.append(mode)
        return real(mode, first, count)

    def triangles(amount):
        snapshot = _lake(amount, shockwave_grid_water_reflection=1.0, shockwave_grid_tilt=0.2)
        capture.render(host, snapshot)
        calls.clear()
        monkeypatch.setattr(gl, "glDrawArrays", counted)
        try:
            capture.render(host, snapshot)
        finally:
            monkeypatch.setattr(gl, "glDrawArrays", real)
        return calls.count(gl.GL_TRIANGLES)

    assert triangles(0.0) == triangles(1.0) - 1
    assert triangles(0.5) == triangles(1.0)
