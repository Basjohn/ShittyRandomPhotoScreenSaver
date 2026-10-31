import math

import numpy as np
import pytest

from core.ribbon_frames import strip_path
from core.ribbon_geometry import PathSample
from core.ribbon_packet import RIBBON_BYTES
from core.ribbon_ring import HEADER_ROWS, RibbonRing


def knots(ribbons, count, *, step=.1, origin=1e9):
    """Curved, twisting, per-ribbon offset paths on one coordinate lattice.

    At the default step, 200 knots travel 80 world units, 20 s and 60 rad, so every local rebase fires.
    """
    for i in range(count):
        t = i*step
        positions = [(t*4 - 3, math.sin(t*2.3 + r) + r*.5, -10 + .4*math.cos(t*1.7 + r)) for r in range(ribbons)]
        yield origin + t, positions, [.1 + .05*r + .03*math.sin(t) for r in range(ribbons)], [1e3 + t*3 + r for r in range(ribbons)]


def chronological(packet, ribbon):
    """(header, knots[count, 4, 4]) in chronological order from a ring packet."""
    data = np.frombuffer(packet.payload, np.float32).reshape(-1, RIBBON_BYTES//16, 4)[ribbon]
    count, start, capacity = int(data[0, 0]), int(data[1, 1]), int(data[1, 2])
    rows = data[HEADER_ROWS:].reshape(-1, 4, 4)
    return data[:HEADER_ROWS], rows[(start + np.arange(count)) % capacity]


def oracle_frames(history):
    """Full-history stateless frames with the ring's chord tangents (forward chord for the first knot)."""
    positions = [np.asarray(p) for _, p, _, _ in history]
    tangents = [positions[1] - positions[0]] + [b - a for a, b in zip(positions, positions[1:])]
    samples = [PathSample(q, tuple(p), w, 0.) for (q, _, w, _), p in zip(history, positions)]
    return strip_path(samples, tangents)


def test_ring_matches_the_stateless_oracle_through_eviction_and_rebase():
    ring = RibbonRing(3, capacity=32, period=.7)
    history = list(knots(3, 200))
    for n, item in enumerate(history, 1):
        ring.append(*item)
        if n not in (2, 31, 32, 33, 97, 161, 162, 200):  # all three locals rebase at knot 162
            continue
        packet = ring.packet()
        retained = history[max(0, n - 32):n]
        assert packet.vertices == (len(retained) - 1)*8*6 and packet.instances == 3
        origin = np.asarray(packet.world_origin)
        for r in range(3):
            header, rows = chronological(packet, r)
            frames = oracle_frames([(q, p[r], w[r], tw[r]) for q, p, w, tw in history[:n]])[n - len(retained):]
            truth = np.array([p[r] for _, p, _, _ in retained])
            np.testing.assert_allclose(rows[:, 0, :3] + origin, truth, atol=1e-5)
            np.testing.assert_allclose(rows[:, 0, 3], [w[r] for _, _, w, _ in retained], rtol=1e-6)
            assert (rows[:, 1, 2] == 1).all()
            np.testing.assert_allclose(rows[:, 3, :3], [f.frame.base_side for f in frames], atol=2e-6)
            # Absolute strand phase and twist survive local rebasing.
            phase = (header[0, 2] + rows[:, 1, 0]/header[0, 3]) % 1
            np.testing.assert_allclose(np.cos(2*np.pi*phase), [math.cos(2*math.pi*((q % .7)/.7)) for q, *_ in retained], atol=2e-4)
            twist = header[1, 0] + rows[:, 1, 1]
            np.testing.assert_allclose(np.cos(twist), [math.cos(tw[r]) for *_, tw in retained], atol=2e-5)


def test_admitted_knots_are_never_rewritten_by_later_appends():
    ring = RibbonRing(1, capacity=64)
    history = list(knots(1, 400, step=.05))
    for item in history[:40]:
        ring.append(*item)
    first = ring.packet()
    mark = chronological(first, 0)[1][30].copy()
    for item in history[40:60]:  # 3 s, 12 world units: below every rebase threshold
        ring.append(*item)
    after = ring.packet()
    np.testing.assert_array_equal(chronological(after, 0)[1][30], mark)
    assert after.world_origin == first.world_origin
    for item in history[60:]:  # 20 s and 80 world units: rebases and evicts
        ring.append(*item)
    final = ring.packet()
    header, rows = chronological(final, 0)
    retained = history[-64:]
    np.testing.assert_allclose(rows[:, 0, :3] + np.asarray(final.world_origin), [p[0] for _, p, _, _ in retained], atol=1e-5)


def test_reversal_breaks_the_strip_and_reseeds_without_bridging():
    ring = RibbonRing(1, capacity=16)
    xs = [0., 1., 2., 1., 0., -1.]  # chord reverses at the fourth knot
    for i, x in enumerate(xs):
        ring.append(i, [(x, 0., -10.)], .2)
    _, rows = chronological(ring.packet(), 0)
    assert rows[:, 1, 2].tolist() == [1, 1, 1, 1, 1, 1]
    # The reversed knot waited, then started a new strip from the seed side. The interval
    # into it is not drawn and its guard knots do not reach across the break.
    assert rows[:, 1, 3].tolist() == [1, 0, 0, 1, 0, 0]
    np.testing.assert_allclose(rows[3, 3, :3], (0, 1, 0), atol=1e-12)
    ring.append(6, [(-1., 0., -10.)], .2)  # repeated point keeps its frame
    _, rows = chronological(ring.packet(), 0)
    assert rows[-1, 1, 2] == 1
    np.testing.assert_array_equal(rows[-1, 3], rows[-2, 3])


def test_reversal_interval_is_not_drawable_until_reseeded():
    ring = RibbonRing(1, capacity=8)
    for i, x in enumerate((0., 1., 2., 1.)):
        ring.append(i, [(x, 0., -10.)], .2)
    _, rows = chronological(ring.packet(), 0)
    assert rows[:, 1, 2].tolist() == [1, 1, 1, 0]


@pytest.mark.parametrize('bad', [
    dict(coordinate=0.5), dict(coordinate=1. + 1e-6), dict(coordinate=math.nan), dict(coordinate=70.),
    dict(positions=[(math.inf, 0, 0)]), dict(positions=[(500., 0, -10)]), dict(half_widths=0.),
    dict(half_widths=1e-6), dict(twists=1e4), dict(positions=[(0, 0, 0), (1, 0, 0)])])
def test_rejected_knots_leave_the_ring_untouched(bad):
    ring = RibbonRing(1, capacity=8)
    ring.append(0., [(0., 0., -10.)], .2)
    ring.append(1., [(1., 0., -10.)], .2)
    before = ring.packet()
    item = dict(coordinate=2., positions=[(2., 0., -10.)], half_widths=.2, twists=0.)
    item.update(bad)
    with pytest.raises(ValueError):
        ring.append(**item)
    assert ring.packet() is before and len(ring) == 2


def test_packet_is_cached_until_change_and_empty_without_a_drawable_interval():
    ring = RibbonRing(2, capacity=4)
    assert ring.packet().instances == 0
    ring.append(0., [(0, 0, -10), (0, 1, -10)], .2)
    assert ring.packet().instances == 0  # one knot: pending, nothing to draw
    ring.append(1., [(1, 0, -10), (1, 1, -10)], .2)
    packet = ring.packet()
    assert packet.instances == 2 and packet.vertices == 48 and len(packet.payload) == 2*RIBBON_BYTES
    assert ring.packet() is packet
    epoch = ring.epoch
    ring.clear()
    assert ring.epoch == epoch + 1 and len(ring) == 0 and ring.packet().instances == 0
    ring.append(.5, [(5, 0, -10), (5, 1, -10)], .2)  # cleared ring accepts a new lattice and origin
    assert ring.packet().instances == 0
