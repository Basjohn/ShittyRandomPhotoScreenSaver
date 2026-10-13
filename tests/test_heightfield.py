"""Strict authoring format, normalized sampling and GPU payload contract."""
import math
import struct

import pytest

from rendering.gl_programs.heightfield import (
    basin_profile,
    heightfield_bytes,
    heightfield_surface_bytes,
    normalize_heightfield,
    sample_heightfield,
    sample_heightfield_curve,
)


@pytest.mark.parametrize("value", [
    None, [], {}, {"version": 2, "size": 2, "heights": [0.0] * 4},
    {"version": True, "size": 2, "heights": [0.0] * 4},
    {"version": 1, "size": True, "heights": [0.0] * 4},
    {"version": 1, "size": 1, "heights": [0.0]},
    {"version": 1, "size": 66, "heights": [0.0] * (66 * 66)},
    {"version": 1, "size": 2.1, "heights": [0.0] * 4},
    {"version": 1, "size": 2, "heights": [0.0] * 3},
    *({"version": 1, "size": 2, "heights": [0.0, 0.0, 0.0, bad]}
      for bad in (True, None, "bad", -0.01, 1.01, float("nan"), float("inf"))),
])
def test_explicit_malformed_terrain_is_never_replaced(value):
    with pytest.raises(ValueError):
        normalize_heightfield(value)


def test_rows_sampling_exact_water_and_packing_share_one_normalized_domain():
    source = {"version": 1, "size": 2.0, "heights": [-0.0, 0.25, 0.5, 1.0]}
    terrain = normalize_heightfield(source)
    assert terrain == {"version": 1, "size": 2, "heights": [0.0, 0.25, 0.5, 1.0]}
    assert sample_heightfield(terrain, -1.0, -1.0) == 0.0
    assert sample_heightfield(terrain, 1.0, 0.0) == 0.25
    assert sample_heightfield(terrain, 0.0, 1.0) == 0.5
    assert sample_heightfield(terrain, 2.0, 2.0) == 1.0
    assert sample_heightfield(terrain, 0.5, 0.5) == 0.4375
    payload = heightfield_bytes(terrain)
    assert isinstance(payload, bytes)
    assert payload[:8] == b"\x00\x00\x00\x00\x00\x00\x80>"
    assert struct.unpack("<4f", payload) == tuple(terrain["heights"])
    source["heights"][1] = 0.99
    assert terrain["heights"][1] == 0.25
    with pytest.raises(ValueError):
        sample_heightfield(terrain, float("nan"), 0.0)
    # Water is defined solely by authored sample zero; positive interpolated shore is solid land.
    assert sample_heightfield(terrain, 0.0, 0.0) == 0.0
    assert sample_heightfield(terrain, 0.1, 0.0) > 0.0


def test_basin_seed_is_deterministic_and_keeps_a_real_flat_lake_with_ridges_and_islands():
    terrain = basin_profile()
    assert terrain == basin_profile()
    assert normalize_heightfield(terrain) == terrain
    water = sum(height == 0.0 for height in terrain["heights"])
    assert 0.20 < water / len(terrain["heights"]) < 0.80
    assert sample_heightfield(terrain, 0.5, 0.4) == 0.0
    assert max(terrain["heights"]) > 0.35
    assert sample_heightfield(terrain, 0.24, 0.57) > 0.0
    for size in (2, 65):
        assert normalize_heightfield(basin_profile(size))["size"] == size


def test_positive_cubic_curve_preserves_constant_and_control_point_range():
    constant = normalize_heightfield({
        "version": 1, "size": 4, "heights": [0.375] * 16,
    })
    for u in (-0.5, 0.0, 0.13, 0.5, 0.91, 1.0, 1.5):
        for v in (-0.25, 0.0, 0.37, 0.72, 1.0, 1.25):
            assert sample_heightfield_curve(constant, u, v) == pytest.approx(0.375, abs=1e-14)

    values = [0.0, 1.0, 0.1, 0.9, 0.8, 0.2, 1.0, 0.0, 0.3,
              0.7, 0.05, 0.95, 0.6, 0.4, 0.85, 0.15]
    terrain = normalize_heightfield({"version": 1, "size": 4, "heights": values})
    for y in range(25):
        for x in range(25):
            height = sample_heightfield_curve(terrain, x / 24.0, y / 24.0)
            assert min(values) <= height <= max(values)


def test_positive_cubic_curve_is_continuous_and_clamps_finite_uv_edges():
    terrain = normalize_heightfield({
        "version": 1,
        "size": 5,
        "heights": [
            0.0, 0.8, 0.1, 0.9, 0.3,
            0.7, 0.2, 1.0, 0.4, 0.6,
            0.1, 0.9, 0.3, 0.8, 0.0,
            1.0, 0.4, 0.7, 0.2, 0.5,
            0.3, 0.6, 0.0, 0.9, 0.1,
        ],
    })
    epsilon = 1e-6
    for seam in (0.25, 0.5, 0.75):
        for v in (0.0, 0.17, 0.53, 0.88, 1.0):
            left = sample_heightfield_curve(terrain, seam - epsilon, v)
            at = sample_heightfield_curve(terrain, seam, v)
            right = sample_heightfield_curve(terrain, seam + epsilon, v)
            assert max(abs(left - at), abs(right - at)) < 2e-5
        for u in (0.0, 0.21, 0.58, 0.91, 1.0):
            below = sample_heightfield_curve(terrain, u, seam - epsilon)
            at = sample_heightfield_curve(terrain, u, seam)
            above = sample_heightfield_curve(terrain, u, seam + epsilon)
            assert max(abs(below - at), abs(above - at)) < 2e-5

    for v in (0.0, 0.31, 0.67, 1.0):
        assert sample_heightfield_curve(terrain, -3.0, v) == sample_heightfield_curve(terrain, 0.0, v)
        assert sample_heightfield_curve(terrain, 4.0, v) == sample_heightfield_curve(terrain, 1.0, v)
    for u in (0.0, 0.27, 0.64, 1.0):
        assert sample_heightfield_curve(terrain, u, -2.0) == sample_heightfield_curve(terrain, u, 0.0)
        assert sample_heightfield_curve(terrain, u, 2.0) == sample_heightfield_curve(terrain, u, 1.0)
    for u, v in ((float("nan"), 0.0), (0.0, float("inf")), (float("-inf"), 0.5)):
        with pytest.raises(ValueError, match="coordinates must be finite"):
            sample_heightfield_curve(terrain, u, v)


def test_bilinear_authored_zero_owns_water_when_curve_rises_at_the_coast():
    terrain = normalize_heightfield({
        "version": 1,
        "size": 3,
        "heights": [0.0, 0.6, 0.0, 0.0, 0.8, 0.0, 0.0, 0.4, 0.0],
    })
    authored_height = sample_heightfield(terrain, 0.0, 0.0)
    curved_surface_height = sample_heightfield_curve(terrain, 0.0, 0.0)
    assert authored_height == 0.0
    assert curved_surface_height > 0.0
    assert authored_height == 0.0  # Water classification uses the authored bilinear field.


def test_surface_payload_interleaves_height_and_distance_from_bilinear_shore_support():
    size = 5
    heights = [0.0] * (size * size)
    heights[2 * size + 2] = 0.75
    terrain = normalize_heightfield({"version": 1, "size": size, "heights": heights})
    payload = heightfield_surface_bytes(terrain)
    pairs = struct.unpack(f"<{size * size * 2}f", payload)

    for y in range(size):
        for x in range(size):
            index = (y * size + x) * 2
            expected_distance = math.hypot(max(abs(x - 2) - 1, 0), max(abs(y - 2) - 1, 0)) / (size - 1)
            assert pairs[index] == heights[y * size + x]
            assert pairs[index + 1] == pytest.approx(expected_distance, abs=1e-7)
            assert math.isfinite(pairs[index + 1])

    # The one-texel Chebyshev expansion includes bilinear-positive zero samples.
    assert pairs[(1 * size + 1) * 2 + 1] == 0.0
    assert pairs[(0 * size + 2) * 2 + 1] == pytest.approx(0.25)
    assert pairs[(0 * size + 0) * 2 + 1] == pytest.approx(math.sqrt(2) / 4.0)


def test_surface_payload_is_finite_deterministic_at_boundaries_and_all_water_or_solid():
    size = 4
    water = normalize_heightfield({"version": 1, "size": size, "heights": [0.0] * (size * size)})
    water_payload = heightfield_surface_bytes(water)
    water_pairs = struct.unpack(f"<{size * size * 2}f", water_payload)
    assert water_payload == heightfield_surface_bytes(water)
    assert all(math.isfinite(value) for value in water_pairs)
    assert water_pairs[0::2] == (0.0,) * (size * size)
    assert water_pairs[1::2] == (1.0,) * (size * size)

    solid = normalize_heightfield({"version": 1, "size": size, "heights": [0.2] * (size * size)})
    solid_payload = heightfield_surface_bytes(solid)
    solid_pairs = struct.unpack(f"<{size * size * 2}f", solid_payload)
    assert all(math.isfinite(value) for value in solid_pairs)
    assert solid_pairs[0::2] == pytest.approx((0.2,) * (size * size))
    assert solid_pairs[1::2] == (0.0,) * (size * size)

    edge_heights = [0.0] * (size * size)
    edge_heights[0] = 1.0
    edge = normalize_heightfield({"version": 1, "size": size, "heights": edge_heights})
    edge_pairs = struct.unpack(f"<{size * size * 2}f", heightfield_surface_bytes(edge))
    distance = lambda x, y: edge_pairs[(y * size + x) * 2 + 1]
    assert distance(1, 1) == 0.0
    assert distance(2, 2) == pytest.approx(math.sqrt(2) / 3.0)
    assert distance(3, 3) == pytest.approx(math.sqrt(8) / 3.0)
    assert all(math.isfinite(value) for value in edge_pairs)


def test_heightfield_rejects_positive_float32_underflow_and_keeps_minimum_normal():
    minimum_normal = 2.0 ** -126
    terrain = normalize_heightfield({
        "version": 1,
        "size": 2,
        "heights": [minimum_normal, 0.25, 0.0, 0.0],
    })
    assert terrain["heights"] == [minimum_normal, 0.25, 0.0, 0.0]
    assert struct.unpack_from("<f", heightfield_bytes(terrain), 0)[0] == minimum_normal
    assert struct.unpack_from("<f", heightfield_surface_bytes(terrain), 0)[0] == minimum_normal

    for too_small in (1e-50, math.nextafter(minimum_normal, 0.0)):
        with pytest.raises(ValueError, match="normal float32"):
            normalize_heightfield({"version": 1, "size": 2,
                                   "heights": [too_small, 0.0, 0.0, 0.0]})

    zero = normalize_heightfield({"version": 1, "size": 2, "heights": [-0.0, 0.0, 0.0, 0.0]})
    assert zero["heights"] == [0.0, 0.0, 0.0, 0.0]
