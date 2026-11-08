"""The framed physical camera's horizontal field-of-view cap (operator 2026-11-08).

Structure only: no authored preset value and no number for the cap itself is pinned here. Every expectation derives
from ``FRAMED_MAX_HORIZONTAL_FOV_DEG`` and the spec's own lens range.
"""
from __future__ import annotations

import math

import pytest

from core.settings import framed_camera as fc


def _hfov(tan_x: float) -> float:
    return math.degrees(2.0 * math.atan(tan_x))


def _uncapped(fov: float, aspect: float, aperture: float, fov_range) -> tuple[float, float]:
    tan_y = fc.tan_half_fov(fov, fov_range) * aperture
    return tan_y * aspect, tan_y


def _max_tan_x() -> float:
    return math.tan(math.radians(fc.FRAMED_MAX_HORIZONTAL_FOV_DEG) / 2.0)


def _below_cap_cases():
    low, high = fc.FOV_RANGE
    for fov in (low, (low + high) / 2.0, high):
        for aperture in (0.6, 1.0, 1.3):
            # Aspects from tall up to just under the cap for this lens.
            limit = _max_tan_x() / (fc.tan_half_fov(fov) * aperture)
            for aspect in (0.4, 1.0, limit * 0.999):
                yield fov, aspect, aperture


def _wide_cases():
    low, high = fc.FOV_RANGE
    for fov in (low, high):
        for aperture in (0.79, 1.0, 7.42):
            limit = _max_tan_x() / (fc.tan_half_fov(fov) * aperture)
            for aspect in (max(limit * 1.01, 1e-3), max(limit, 1.0) * 3.2):
                yield fov, aspect, aperture


@pytest.mark.parametrize(("fov", "aspect", "aperture"), list(_below_cap_cases()))
def test_below_the_cap_the_lens_is_bit_identical_to_the_uncapped_one(fov, aspect, aperture):
    assert fc.viewport_tangents(fov, aspect, aperture) == _uncapped(fov, aspect, aperture, fc.FOV_RANGE)
    assert fc.effective_aperture_scale(fov, aspect, aperture) == aperture


def _assert_capped(fov, aspect, aperture, fov_range=fc.FOV_RANGE):
    before = _uncapped(fov, aspect, aperture, fov_range)
    assert _hfov(before[0]) > fc.FRAMED_MAX_HORIZONTAL_FOV_DEG            # the card really is past the cap
    tan_x, tan_y = fc.viewport_tangents(fov, aspect, aperture, fov_range)
    assert _hfov(tan_x) == pytest.approx(fc.FRAMED_MAX_HORIZONTAL_FOV_DEG, abs=1e-9)
    # The vertical view solves the projection for the capped horizontal one: pixel aspect still holds exactly.
    assert tan_y == pytest.approx(tan_x / aspect, rel=1e-15)
    assert tan_y < before[1]
    # Pixel-scale consumers follow the very same lens.
    effective = fc.effective_aperture_scale(fov, aspect, aperture, fov_range)
    assert effective == pytest.approx(tan_y / fc.tan_half_fov(fov, fov_range), rel=1e-15)


@pytest.mark.parametrize(("fov", "aspect", "aperture"), list(_wide_cases()))
def test_a_wide_card_shows_exactly_the_capped_horizontal_view(fov, aspect, aperture):
    _assert_capped(fov, aspect, aperture)


def test_negative_control_without_the_cap_the_wide_card_test_fails(monkeypatch):
    fov, aspect, aperture = next(iter(_wide_cases()))
    monkeypatch.setattr(fc, "_MAX_TAN_X", math.inf)
    with pytest.raises(AssertionError):
        _assert_capped(fov, aspect, aperture)


def test_project_point_and_view_matrices_project_through_the_capped_lens():
    spec = fc.FRAMED_CAMERA_SPECS()[0]
    fov, aspect = spec.fov_range[1], 4.0
    assert _hfov(_uncapped(fov, aspect, 1.0, spec.fov_range)[0]) > fc.FRAMED_MAX_HORIZONTAL_FOV_DEG
    _v2w, _w2v, tan, projection = fc.view_matrices(spec, 0.0, 0.0, aspect, fov, 0.1, 100.0)
    assert tan == fc.viewport_tangents(fov, aspect, 1.0, spec.fov_range)
    assert projection[0] == pytest.approx(1.0 / tan[0])
    axes = fc.camera_axes(spec, 0.0, 0.0)
    eye = (0.0, 0.0, 0.0)
    right, back = axes[:3], axes[6:9]
    # A point on the capped frustum's right edge at depth 1 lands on NDC x = 1.
    point = tuple(tan[0] * r - b for r, b in zip(right, back))
    x, _y, depth = fc.project_point(spec, point, eye, 0.0, 0.0, aspect, fov, axes=axes)
    assert depth == pytest.approx(1.0)
    assert x == pytest.approx(1.0)


def _mode_parameters(mode: str):
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    return dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0}, mode=mode).resolved_config)


def _eb_tangents(parameters, aspect, aperture):
    from rendering.gl_programs.extruded_bubble_scene import physical_camera
    return tuple(physical_camera(0.0, 0.0, aspect, fov_y_degrees=float(parameters["extruded_bubble_camera_fov"]),
                                 aperture_scale=aperture)[3])


def _neon_tangents(parameters, aspect, aperture):
    from rendering.gl_programs.neon_lake_basin_program import basin_view
    return tuple(basin_view(parameters, (0.0, 0.0, 300.0 * aspect, 300.0), aperture_scale=aperture).tan)


def _waveform_tangents(parameters, aspect, aperture):
    from core.waveform_ribbon_view import physical_view
    return tuple(physical_view(parameters, aspect, aperture)[3])


# Each framed mode's production projection entry point (renderer, Studio and edit envelope all call these).
_PROJECTIONS = {
    "extruded_bubble_": _eb_tangents,
    "shockwave_grid_": _neon_tangents,
    "waveform_ribbon_": _waveform_tangents,
}


def test_every_framed_field_of_view_control_admits_exactly_its_lens_range():
    """Settings repair/admission, preset loading and the Studio wheel all read the Slider; the camera math reads the
    spec. One range, so a value the control admits is the lens the renderer draws (never clamped up behind it)."""
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    from core.settings.visualizer_mode_settings import require_mode_settings
    from ui.studio.framed import camera_navigation
    for descriptor in iter_all_visualizer_mode_descriptors():
        spec = fc.spec_for_mode(descriptor.mode_id)
        if spec is None:
            continue
        control = require_mode_settings(descriptor.mode_id).control(spec.key("camera_fov"))
        assert (float(control.low), float(control.high)) == spec.fov_range, descriptor.mode_id
        low, high = spec.fov_range
        assert float(control.admit(low, high)) == low
        assert float(control.admit(low - 1.0, high)) == low
        assert fc.tan_half_fov(low, spec.fov_range) == math.tan(math.radians(low) / 2.0)
        assert camera_navigation(descriptor.mode_id, spec.prefix).zoom.bounds == spec.fov_range


def test_the_long_lens_end_still_caps_on_a_wide_card():
    for spec in fc.FRAMED_CAMERA_SPECS():
        low = spec.fov_range[0]
        wide = 3.0 * _max_tan_x() / fc.tan_half_fov(low, spec.fov_range)
        _assert_capped(low, wide, 1.0, spec.fov_range)


def test_every_framed_mode_projects_through_the_one_capped_lens():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    framed = {d.mode_id: fc.spec_for_mode(d.mode_id) for d in iter_all_visualizer_mode_descriptors()
              if d.framed_camera}
    assert {spec.prefix for spec in framed.values()} == set(_PROJECTIONS)
    for mode, spec in framed.items():
        parameters = _mode_parameters(mode)
        fov = float(parameters[spec.key("camera_fov")])
        project = _PROJECTIONS[spec.prefix]
        # Below the cap: exactly the uncapped lens.
        assert project(parameters, 1.0, 1.0) == _uncapped(fov, 1.0, 1.0, spec.fov_range)
        # A card wide enough to pass the cap at this lens shows exactly the capped horizontal view.
        wide = 3.0 * _max_tan_x() / fc.tan_half_fov(fov, spec.fov_range)
        tan = project(parameters, wide, 1.0)
        assert tan == pytest.approx(fc.viewport_tangents(fov, wide, 1.0, spec.fov_range), rel=1e-12)
        assert _hfov(tan[0]) == pytest.approx(fc.FRAMED_MAX_HORIZONTAL_FOV_DEG, abs=1e-9), mode
