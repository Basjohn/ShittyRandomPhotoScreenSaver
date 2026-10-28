import math

import numpy as np
import pytest

from core.ribbon_geometry import MAX_PATH_SAMPLES, PathSample, RibbonHistory, centripetal_point


def samples(count):
    return [PathSample(i/60, (float(i), math.sin(i), 0.), .1+i*.01, i*.2) for i in range(count)]


def test_capacity_ring_eviction_and_batch_partition_preserve_absolute_knots():
    values = samples(30)
    whole, divided = RibbonHistory(8), RibbonHistory(8)
    for i in range(0, 30, 6):
        whole.extend(values[i:i+6])
    for sample in values:
        divided.append(sample)
    assert len(whole) == 8 and whole.payload_bytes == 8*8*8
    np.testing.assert_array_equal(whole.records(), divided.records())
    np.testing.assert_array_equal(whole.records()[:, 0], [s.coordinate for s in values[-8:]])
    for q in np.linspace(values[-7].coordinate, values[-2].coordinate, 29):
        assert whole.evaluate(q) == divided.evaluate(q)
    with pytest.raises(ValueError, match='outside retained'):
        whole.evaluate(values[0].coordinate)


def test_marked_interior_coordinate_does_not_slide_on_insertion_or_eviction():
    history = RibbonHistory(6)
    values = samples(8)
    history.extend(values[:5])
    marked = history.evaluate(2.4/60)
    history.append(values[5])
    assert history.evaluate(2.4/60) == marked
    history.append(values[6])  # Four local supporting knots still retained.
    assert history.evaluate(2.4/60) == marked
    # A segment-share implementation relocates the same normalized mark.
    assert history.evaluate(history.records()[0, 0]+.48*(history.records()[-1, 0]-history.records()[0, 0])) != marked


def test_bad_batch_is_atomic_and_clear_reuses_storage():
    history = RibbonHistory(4)
    history.append(samples(1)[0])
    before = history.records()
    with pytest.raises(ValueError):
        history.extend([samples(2)[1], PathSample(2, (math.nan, 0, 0))])
    np.testing.assert_array_equal(history.records(), before)
    with pytest.raises(ValueError):
        history.extend(samples(6)[1:])
    np.testing.assert_array_equal(history.records(), before)
    storage = id(history._data)
    history.clear()
    assert len(history) == 0 and history.evaluate(0) is None
    assert id(history._data) == storage and not history.records().size and history.epoch == 1
    history.append(samples(1)[0])
    assert history.evaluate(0) == samples(1)[0]


@pytest.mark.parametrize('positions', [
    [(0., 0., 0.)]*4,
    [(0., 0., 0.), (1., 0., 0.), (1., 0., 0.), (2., 0., 0.)],
    [(0., 0., 0.), (1., 0., 0.), (0., 0., 0.), (-1., 0., 0.)],
    [(-100., 0., 0.), (0., 0., 0.), (.001, 0., 0.), (.002, 0., 0.)],
])
def test_stationary_repeated_reversing_and_unequal_spacing_remain_finite(positions):
    history = RibbonHistory(4)
    history.extend(PathSample(i, p, .01+i*.1, i*2*math.pi) for i, p in enumerate(positions))
    for q in np.linspace(0, 3, 121):
        point = history.evaluate(q)
        assert all(math.isfinite(v) for v in (*point.position, point.twist))
        assert point.half_width > 0
    for i, position in enumerate(positions):
        assert history.evaluate(i).position == position
    if positions[1] == positions[2]:
        assert history.evaluate(1.5).position == positions[1]


def test_centripetal_curve_resists_the_uniform_unequal_spacing_overshoot():
    points = ((-100., 0., 0.), (0., 0., 0.), (.001, 0., 0.), (.002, 0., 0.))
    result = centripetal_point(*points, .5)
    assert 0 <= result[0] <= .001
    # Uniform Catmull-Rom's neighbouring long segment pulls this far outside.
    uniform = .5*((2*0) + (.001+100)*.5 + (2*-100-5*0+4*.001-.002)*.25
                  + (100+3*0-3*.001+.002)*.125)
    assert uniform > .001


@pytest.mark.parametrize('sample', [PathSample(0, (0, 0)), PathSample(math.inf, (0, 0, 0)),
    PathSample(0, (0, 0, 0), 0), PathSample(0, (1e300, 0, 0)), PathSample(0, (0, 0, 0), twist=math.nan), PathSample(1e300, (0, 0, 0))])
def test_invalid_domain_fails_before_mutation(sample):
    history = RibbonHistory()
    with pytest.raises(ValueError):
        history.append(sample)
    assert len(history) == 0 and history.payload_bytes == MAX_PATH_SAMPLES*64


def test_two_point_line_and_unwrapped_twist_have_no_startup_extension():
    history = RibbonHistory(2)
    history.extend([PathSample(10, (0, 0, 0), .1, 0), PathSample(11, (2, 0, 0), .3, 4*math.pi)])
    assert history.evaluate(10.5).position == pytest.approx((1, 0, 0))
    assert history.evaluate(10.5).half_width == pytest.approx(.2)
    assert history.evaluate(10.5).twist == pytest.approx(2*math.pi)
    with pytest.raises(ValueError):
        history.append(PathSample(11, (4, 0, 0)))


def test_owned_records_and_large_absolute_coordinates():
    history = RibbonHistory(4)
    history.extend(PathSample(1e9+i/60, (float(i), 0., 0.)) for i in range(4))
    output = history.records()
    output[:] = 0.
    assert history.evaluate(1e9+1.5/60).position == pytest.approx((1.5, 0, 0), abs=1e-5)
    for capacity in (1, 257, True, 2.5):
        with pytest.raises(ValueError):
            RibbonHistory(capacity)


@pytest.mark.parametrize('widths', [(1e6, 1e-20), (1e-20, 1e6), (5e-324, 5e-324)])
def test_large_ratio_and_subnormal_widths_preserve_positive_authored_bounds(widths):
    history = RibbonHistory(2)
    a = PathSample(0, (0, 0, 0), widths[0], 1e6)
    b = PathSample(1, (1, 0, 0), widths[1], 1e-20)
    history.extend([a, b])
    assert history.evaluate(0) == a
    assert history.evaluate(1) == b
    for q in (1e-15, .25, .5, .75, 1-1e-15):
        value = history.evaluate(q)
        assert min(widths) <= value.half_width <= max(widths)
        assert value.half_width > 0
