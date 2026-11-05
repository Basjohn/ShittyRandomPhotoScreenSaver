"""Troughs stay round above the floor (operator, 5 Nov: "we collide with the floor a lot ... the flat collision looks
poor ... perhaps how far the bottom half can go down could be clamped"). Test-owned controls only; structure, never
authored values."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PULSE_GRID, PulseControls, TROUGH_HANG
from tests.test_waveform_ribbon_dynamics import controls, primed

LOUD = {'bands': (.95, .9, .85), 'intensity': 1., 'presence': 1.}


def deep_model():
    c = replace(controls(), rotation_enabled=False, pulse=PulseControls(width=6., speed=3.))
    # Loud, preset-range height and a strong swell (beyond ~4x the room a monotone scale cannot hold the edge:
    # there the floor contact map is the documented last resort).
    c = replace(c, ranges={**c.ranges, 'height': (1.5, 2.4), 'bend': (2., 2.8), 'lift': (.8, 1.)})
    return primed(c)


def lower_edges(snapshot, span=9.):
    data = np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)
    out = []
    for path in data:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        if count < 8 or path[2, 3] <= .02:
            continue
        knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start+np.arange(count)) % capacity]
        x = knots[:, 0, 0]+snapshot.packet.world_origin[0]+snapshot.head_x-snapshot.travel
        y = knots[:, 0, 1]+snapshot.packet.world_origin[1]
        hang = TROUGH_HANG*np.abs(knots[:, 0, 3]*np.cos(knots[:, 1, 1]))
        inside = np.abs(x) < span
        out.append((x[inside], y[inside], y[inside]-hang[inside]))
    return out


def run_loud(model, seconds=6.):
    lowest, scales, last = [], [], None
    for index in range(round(seconds*90)):
        last = model.advance(1/90, hit=1. if index % 30 == 0 else 0., **LOUD)
        scales.append(model._trough_scale.copy())
        lowest.append(min(edge.min() for _, _, edge in lower_edges(last)))
    return np.asarray(lowest[90:]), np.asarray(scales), last


def test_loud_deep_troughs_settle_far_above_where_they_met_the_floor_and_stay_round(monkeypatch):
    lowest, scales, snapshot = run_loud(deep_model())
    with monkeypatch.context() as off:
        off.setattr(dyn, 'TROUGH_SCALE_MIN', 1.)
        off.setattr(dyn, 'TROUGH_SAFETY_KNEE', 1e9)
        unbounded, _, _ = run_loud(deep_model())
    # A deliberately loud, strongly swelled stress case: without the law the lower edge sinks metres into the
    # floor (where the contact map flattened it into a line); with it the edge stays at the floor or above.
    assert np.median(unbounded) < -2.
    assert np.percentile(lowest, 5) > -.25 and np.median(lowest) > np.median(unbounded)+2.
    # Round, never a flat run: at each ribbon's deepest knot the curve still bends up clearly.
    for x, y, _ in lower_edges(snapshot):
        k = np.gradient(np.gradient(y, x), x)
        at = int(np.argmin(y[2:-2]))+2
        if y[at] < y.mean()-.5:
            assert k[at] > .05
    # The depth scale changes smoothly (attack/release on the logical clock), never in one jump.
    assert np.abs(np.diff(scales[:, :, 0], axis=0)).max() < .2


def test_a_swell_never_changes_the_trough_depth_scale():
    """The scale is sized on the waveform without the travelling swell (flow rule: a swell only deepens). Compared
    with the same logical state at the same time with every swell field cleared."""
    import copy
    model = deep_model()
    swelled = 0
    for index in range(round(2.*90)):
        model.advance(1/90, hit=1. if index % 40 == 0 else 0., **LOUD)
        twin = copy.deepcopy(model)
        twin._pulse[:] = 0.
        twin._fresh[:] = 0.
        twin._held[:] = 0.
        twin._whole = twin._whole_fresh = 0.
        for name in ('_drift', '_level', '_focus', '_geom'):
            setattr(twin, name, np.zeros(PULSE_GRID.size))
        twin._snapshot = None
        model.snapshot(), twin.snapshot()
        np.testing.assert_array_equal(model._trough_scale, twin._trough_scale)
        swelled += bool(np.abs(model._geom).max() > .05)
    assert swelled > 30  # swells were present for much of the run
