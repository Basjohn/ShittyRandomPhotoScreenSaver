import math

import numpy as np
import pytest

from core.ribbon_frames import (FrameDiscontinuity, MAX_STRIP_STATIONS, WidthFrame,
                                strip_path, strip_station, width_frame)
from core.ribbon_geometry import PathSample


def check(frame):
    axes = np.array((frame.tangent, frame.side, frame.normal))
    np.testing.assert_allclose(axes @ axes.T, np.eye(3), atol=1e-12)
    assert np.isfinite(axes).all()
    assert np.linalg.det(axes) == pytest.approx(1.)


def helix(n=40):
    q = np.linspace(0, 3, n)
    samples = [PathSample(float(t), (float(t), math.sin(t), math.cos(t)), .2, t*2) for t in q]
    tangents = [(1., math.cos(t), -math.sin(t)) for t in q]
    return samples, tangents


def test_transport_twist_and_edges_are_orthonormal_without_cumulative_twist():
    samples, tangents = helix()
    stations = strip_path(samples, tangents)
    for sample, station in zip(samples, stations):
        check(station.frame)
        assert math.dist(station.left, station.right) == pytest.approx(.4)
        np.testing.assert_allclose(np.mean([station.left, station.right], axis=0), sample.position)
        assert station.left_uv == (sample.coordinate, 0.)
        assert station.right_uv == (sample.coordinate, 1.)
    previous = None
    for _ in range(10):
        previous = width_frame((1, 0, 0), previous=previous, twist=math.pi/2)
        np.testing.assert_allclose(previous.side, (0, 0, 1), atol=1e-15)


def test_batch_and_eviction_anchor_keep_identical_roll():
    samples, tangents = helix()
    whole = strip_path(samples, tangents)
    first = strip_path(samples[:13], tangents[:13])
    rest = strip_path(samples[13:], tangents[13:], initial_frame=first[-1].frame)
    assert first+rest == whole
    retained = strip_path(samples[20:], tangents[20:], initial_frame=whole[19].frame)
    assert retained == whole[20:]
    reseeded = strip_path(samples[20:], tangents[20:])
    assert not np.allclose(reseeded[-1].frame.side, whole[-1].frame.side)


def test_orthographic_parallel_sight_ignores_eye_and_depth_but_perspective_does_not():
    tangent = (1., 1., 0.)
    a = width_frame(tangent, mode='camera_facing', position=(0, 0, -5), eye=(2, 3, 10))
    b = width_frame(tangent, mode='camera_facing', position=(5, 3, -50), eye=(9, -6, 2))
    assert a == b
    p = width_frame(tangent, mode='camera_facing', projection='perspective', position=(5, 3, -5))
    assert not np.allclose(a.side, p.side)
    np.testing.assert_allclose(np.dot(p.side, (5, 3, -15)), 0, atol=1e-12)
    check(a)
    check(p)


def test_parallel_camera_sight_is_explicit_and_finite_through_pole():
    previous = None
    sides = []
    for x in np.linspace(-.1, .1, 101):
        frame = width_frame((x, 0, -1), previous=previous, seed_side=(0, 1, 0), mode='camera_facing')
        check(frame)
        sides.append(frame.side)
        previous = frame
        if abs(x) < .04:
            assert frame.camera_parallel
    assert min(np.dot(a, b) for a, b in zip(sides, sides[1:])) > .99


def test_stationary_is_a_gap_and_true_reversal_requires_explicit_break():
    samples = [PathSample(i, (i, 0, 0)) for i in range(3)]
    stations = strip_path(samples, [(1, 0, 0), (0, 0, 0), (1, 0, 0)])
    assert stations[1] is None
    assert width_frame((0, 0, 0)) is None
    assert stations[0].frame == stations[2].frame
    with pytest.raises(FrameDiscontinuity, match='reversal'):
        width_frame((-1, 0, 0), previous=stations[0].frame)
    with pytest.raises(FrameDiscontinuity, match='Seed'):
        width_frame((0, 1, 0))


def test_bad_inputs_and_capacity_fail_without_mutating_anchor():
    previous = width_frame((1, 0, 0))
    with pytest.raises(ValueError):
        strip_path([PathSample(0, (0, 0, 0))], [], initial_frame=previous)
    with pytest.raises(ValueError, match='capacity'):
        strip_path((PathSample(i, (i, 0, 0)) for i in range(MAX_STRIP_STATIONS+1)),
                   ((1, 0, 0) for _ in range(MAX_STRIP_STATIONS+1)))
    with pytest.raises(ValueError, match='unit'):
        width_frame((1, 0, 0), previous=WidthFrame((2, 0, 0), (0, 1, 0), (0, 1, 0), (0, 0, 1)))
    with pytest.raises(ValueError):
        width_frame((math.nan, 0, 0))
    with pytest.raises(ValueError):
        width_frame((1, 0, 0), mode='camera_facing', view_direction=(0, 0, 0))
    assert previous == width_frame((1, 0, 0))


def test_two_sided_normal_and_unwrapped_twist_are_explicit_geometry():
    a = strip_station(PathSample(0, (0, 0, 0), .3, 4*math.pi), (1, 0, 0))
    b = strip_station(PathSample(1, (0, 0, 0), .3, 5*math.pi), (1, 0, 0))
    np.testing.assert_allclose(a.frame.normal, -np.array(b.frame.normal), atol=1e-14)
    np.testing.assert_allclose(a.left, b.right, atol=1e-14)


def test_camera_defined_initial_side_does_not_require_an_unrelated_seed():
    frame = width_frame((0, 1, 0), mode='camera_facing')
    check(frame)
    np.testing.assert_allclose(frame.side, (-1, 0, 0))
    with pytest.raises(ValueError, match='increase'):
        strip_path([PathSample(1, (0, 0, 0)), PathSample(0, (1, 0, 0))], [(1, 0, 0)]*2)


@pytest.mark.parametrize('scale', (1e-300, 1e-11, 1., 1e300))
def test_direction_magnitude_does_not_erase_slow_paths(scale):
    frame = width_frame((scale, scale, 0), mode='camera_facing', view_direction=(0, 0, -scale))
    check(frame)
    expected = width_frame((1, 1, 0), mode='camera_facing')
    np.testing.assert_allclose(frame.side, expected.side, atol=1e-14)


@pytest.mark.parametrize('epsilon', (-1e-10, 1e-10))
def test_camera_pole_azimuth_seam_never_silently_flips_roll(epsilon):
    anchor = width_frame((1, 0, 0))
    sight = (math.sqrt(1-.04**2), .04, epsilon)
    with pytest.raises(FrameDiscontinuity, match='roll-ambiguous'):
        width_frame((1, 0, 0), previous=anchor, mode='camera_facing', view_direction=sight)
    assert anchor == width_frame((1, 0, 0))


def test_unrepresentable_edges_fail_without_inventing_a_width_floor():
    with pytest.raises(FrameDiscontinuity, match='precision'):
        strip_station(PathSample(0, (1e6, 1e6, 1e6), 1e-20), (1, 0, 0))
