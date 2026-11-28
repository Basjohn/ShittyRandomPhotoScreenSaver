"""Focused contracts for Slide's frozen bounded motion styles."""

from __future__ import annotations

import pytest

from core.settings.default_contract import require_canonical_default
from rendering.quick.transitions.implementations.slide import (
    _slide_elastic_arrival,
    _slide_partition_sample,
)
from rendering.quick.transitions.request_resolution import resolve_quick_transition_spec


class _Settings:
    def __init__(self, motion_style: object) -> None:
        self._transitions = {
            "type": "Slide",
            "random_always": False,
            "slide": {"direction": "Left to Right", "motion_style": motion_style},
        }

    def get(self, key, default=None):
        if key == "transitions":
            return self._transitions
        return default


@pytest.mark.parametrize("style", ("Linear", "Elastic", "Wobble", "Flex"))
@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_slide_motion_styles_have_exact_endpoints_and_one_owner(style, direction):
    horizontal = direction in {"left", "right"}
    for progress, expected_owner in ((0.0, "source"), (1.0, "destination")):
        for pixel in range(131):
            axis = (pixel + 0.5) / 131.0
            coordinate = (axis, 0.347) if horizontal else (0.347, axis)
            owner, uv = _slide_partition_sample(direction, progress, coordinate, style)
            assert owner == expected_owner
            assert uv == coordinate


@pytest.mark.parametrize("style", ("Linear", "Elastic", "Wobble", "Flex"))
@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_slide_motion_styles_keep_dense_cardinal_partition_covered(style, direction):
    horizontal = direction in {"left", "right"}
    for progress in (index / 113.0 for index in range(114)):
        for pixel in range(131):
            axis = (pixel + 0.5) / 131.0
            coordinate = (axis, 0.619) if horizontal else (0.619, axis)
            owner, uv = _slide_partition_sample(direction, progress, coordinate, style)
            assert owner in {"source", "destination"}
            assert all(0.0 <= component <= 1.0 for component in uv)


def test_elastic_is_an_analytic_arrival_with_rebound_and_exact_completion():
    assert _slide_elastic_arrival(0.0) == 0.0
    assert _slide_elastic_arrival(1.0) == 1.0
    samples = [_slide_elastic_arrival(index / 1000.0) for index in range(1, 1000)]
    assert max(samples) > 1.0
    assert max(samples) <= 1.025
    # There is a true rebound after overshoot, rather than a merely eased ramp.
    peak = samples.index(max(samples))
    assert min(samples[peak + 1 :]) < 1.0


def test_elastic_overshoot_samples_the_departing_edge_without_wrapping():
    progress = next(index / 1000.0 for index in range(1, 1000) if _slide_elastic_arrival(index / 1000.0) > 1.0)
    amount = _slide_elastic_arrival(progress)
    owner, uv = _slide_partition_sample("left", progress, (0.2, 0.5), "Elastic")
    assert owner == "destination"
    assert uv[0] == pytest.approx(0.2 + (amount - 1.0))
    # Distinct interior output pixels retain distinct destination texels rather
    # than collapsing to the clamped departing edge.
    _, second_uv = _slide_partition_sample("left", progress, (0.7, 0.5), "Elastic")
    assert second_uv[0] == pytest.approx(0.7 + (amount - 1.0))
    assert second_uv[0] != uv[0]


def test_elastic_travel_has_no_late_velocity_jump_and_smooth_turnarounds():
    # The rejected implementation has speed 1 immediately before .78 and 10
    # immediately after it. Check the complete path as well as each turn.
    step = 0.0001
    values = [_slide_elastic_arrival(index * step) for index in range(10001)]
    speeds = [(right - left) / step for left, right in zip(values, values[1:])]
    assert max(abs(speed) for speed in speeds) < 2.5
    for join in (0.78, 0.90):
        before = (_slide_elastic_arrival(join) - _slide_elastic_arrival(join-step)) / step
        after = (_slide_elastic_arrival(join+step) - _slide_elastic_arrival(join)) / step
        assert abs(before - after) < 0.001
        left_accel = (_slide_elastic_arrival(join) - 2*_slide_elastic_arrival(join-step)
                      + _slide_elastic_arrival(join-2*step)) / step**2
        right_accel = (_slide_elastic_arrival(join+2*step) - 2*_slide_elastic_arrival(join+step)
                       + _slide_elastic_arrival(join)) / step**2
        assert abs(left_accel - right_accel) < 0.1


@pytest.mark.parametrize("style", ("Wobble", "Flex"))
def test_slide_warp_settles_without_an_endpoint_velocity_step(style):
    # Subtract the existing Linear travel to isolate the optional warp. Its
    # residual at either endpoint must vanish quadratically, not linearly.
    coordinate = (0.42, 0.31)
    def residual(progress):
        _, warped = _slide_partition_sample("left", progress, coordinate, style)
        _, linear = _slide_partition_sample("left", progress, coordinate, "Linear")
        return max(abs(a-b) for a, b in zip(warped, linear))
    for start, sign in ((0.0, 1), (1.0, -1)):
        near = residual(start + sign * .001)
        farther = residual(start + sign * .002)
        assert near > 0.0
        assert farther == pytest.approx(4.0 * near, rel=.001)


@pytest.mark.parametrize("style", ("Linear", "Elastic", "Wobble", "Flex"))
def test_slide_resolution_freezes_the_single_style_choice(style):
    spec = resolve_quick_transition_spec(_Settings(style))
    assert spec is not None
    assert dict(spec.parameters) == {"motion_style": style}


@pytest.mark.parametrize("invalid", ("Perspective", "elastic", "", 3, None, []))
def test_slide_resolution_falls_back_to_canonical_motion_style(invalid):
    # An invalid or corrupt authored motion style is not fatal: resolution falls
    # back to the canonical Slide default rather than raising, so a bad stored
    # value can never break the transition subsystem. Only a corrupt *canonical*
    # default would raise.
    spec = resolve_quick_transition_spec(_Settings(invalid))
    assert spec is not None
    expected = str(require_canonical_default("transitions.slide.motion_style"))
    assert dict(spec.parameters) == {"motion_style": expected}


@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_perspective_push_keeps_the_existing_cardinal_coverage_owner(direction):
    """The 3D source mapping may distort UVs, never coverage ownership."""

    horizontal = direction in {"left", "right"}
    for progress in (index / 79.0 for index in range(80)):
        for pixel in range(97):
            axis = (pixel + 0.5) / 97.0
            coordinate = (axis, 0.41) if horizontal else (0.41, axis)
            owner, uv = _slide_partition_sample(
                direction, progress, coordinate, "Perspective Push"
            )
            assert owner in {"source", "destination"}
            assert all(0.0 <= value <= 1.0 for value in uv)


def test_perspective_push_shader_ray_intersects_a_tilted_card_under_the_partition():
    from rendering.quick.transitions.implementations.slide import _SLIDE_FRAGMENT_SOURCE

    assert "perspectivePushUv" in _SLIDE_FRAGMENT_SOURCE
    assert "rayOrigin" in _SLIDE_FRAGMENT_SOURCE
    assert "rayDirection" in _SLIDE_FRAGMENT_SOURCE
    assert "dot(cardCenter - rayOrigin, normal)" in _SLIDE_FRAGMENT_SOURCE
    assert "float destinationOwns" in _SLIDE_FRAGMENT_SOURCE
    assert "u_motionStyle == 4" in _SLIDE_FRAGMENT_SOURCE


@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_perspective_push_ray_plane_reference_is_identity_at_exact_endpoints(direction):
    from rendering.quick.transitions.implementations.slide import _slide_perspective_card_uv

    for uv in ((0.03, 0.17), (0.5, 0.5), (0.94, 0.81)):
        assert _slide_perspective_card_uv(uv, direction, 0.0, (1920.0, 1080.0)) == pytest.approx(uv)
        assert _slide_perspective_card_uv(uv, direction, 1.0, (1080.0, 1920.0)) == pytest.approx(uv)


@pytest.mark.parametrize("direction", ("left", "right", "up", "down"))
def test_perspective_push_ray_plane_reference_is_aspect_and_axis_sensitive(direction):
    from rendering.quick.transitions.implementations.slide import _slide_perspective_card_uv

    uv = (0.31, 0.73)
    landscape = _slide_perspective_card_uv(uv, direction, 0.53, (1920.0, 1080.0))
    portrait = _slide_perspective_card_uv(uv, direction, 0.53, (1080.0, 1920.0))
    assert landscape != pytest.approx(uv)
    assert portrait != pytest.approx(uv)
    if direction in {"left", "right"}:
        assert landscape != pytest.approx(portrait)


