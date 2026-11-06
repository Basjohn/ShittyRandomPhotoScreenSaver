"""Visible troughs clear the floor through height, never by shrinking a reaction (operator, 6 Nov: "Better to have good
reactivity than excessively avoid the floor"). Since swells reach the view at strength their troughs need more than the
former 1.5 whole-ribbon lift; the lift's limit covers them, the ribbon rising as a whole while its shape, swells and
kicks stay exactly as without the lift. Floor Give keeps its authored contact (the former limit).

Test-owned controls and inputs, production constants. Negative control: the same run at the former limit (as on main)
puts visible troughs below the floor."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed

SPAN = (-16., 16.)
LOUD = {'bands': (.95, .9, .85), 'intensity': 1., 'presence': 1.}


def deep(give=0.):
    """Loud, tall, strong swells reaching the view (Head To Tail Travelling Pulse with the card's span)."""
    c = replace(controls(), rotation_enabled=False, pulse=PulseControls(width=3., speed=12., fade=2.5))
    c = replace(c, ranges={**c.ranges, 'height': (1.4, 2.2), 'bend': (2., 2.8), 'lift': (.6, .8)},
                scene=replace(c.scene, floor=replace(c.scene.floor, give=give)))
    model = primed(c)
    model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=SPAN)
    return model


def visible(snapshot):
    """Per ribbon the camera shows: (knot centre heights, lower sheet edges, everything else per knot) in world y."""
    data = np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)
    out = []
    for path in data:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        if count < 8 or path[2, 3] <= .02:
            continue
        knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start+np.arange(count)) % capacity]
        x = knots[:, 0, 0]+snapshot.packet.world_origin[0]+snapshot.head_x-snapshot.travel
        inside = (x >= SPAN[0]) & (x <= SPAN[1])
        y = snapshot.packet.world_origin[1]+knots[inside, 0, 1]
        rest = knots[inside].copy()
        rest[:, 0, 1] = 0.
        out.append((y, y-np.abs(knots[inside, 0, 3]*np.cos(knots[inside, 1, 1])), rest))
    return out


def run(model, seconds=8.):
    frames, lifts = [], []
    for index in range(round(seconds*90)):
        frames.append(visible(model.advance(1/90, hit=1. if index % 30 == 0 else 0., **LOUD)))
        lifts.append(float(model._trough_lift.max()))
    lows = np.asarray([min(edge.min() for _, edge, _ in frame) for frame in frames])
    return lows[180:], frames, np.asarray(lifts)


def test_visible_troughs_clear_the_floor_by_lift(monkeypatch):
    lows, _, lifts = run(deep())
    assert lows.min() > 0., lows.min()
    assert lifts.max() > dyn.FLOOR_GIVE_LIFT_MAX       # it took more height than the former limit
    with monkeypatch.context() as off:                  # negative control: the former limit, as on main
        off.setattr(dyn, 'TROUGH_LIFT_MAX', dyn.FLOOR_GIVE_LIFT_MAX)
        capped, _, _ = run(deep())
    assert (capped < 0.).mean() > .1, (capped < 0.).mean()


def test_the_lift_leaves_shape_and_swells_exactly_as_they_are(monkeypatch):
    """Every visible ribbon is the unlifted ribbon plus one vertical offset; every other published knot field is
    bit-identical, so the swells (and kicks) the floor rule sees are the ones published."""
    _, lifted, _ = run(deep())
    with monkeypatch.context() as off:
        off.setattr(dyn, 'TROUGH_LIFT_MAX', 0.)
        _, flat, _ = run(deep())
    moved = 0
    for tick in range(180, len(lifted), 23):
        for (y, _, rest), (y0, _, rest0) in zip(lifted[tick], flat[tick]):
            assert np.array_equal(rest, rest0)
            offset = y-y0
            assert np.ptp(offset) < 1e-4
            moved += offset.mean() > .5
    assert moved                                          # the run is one the lift acts on


def test_floor_give_keeps_its_authored_contact():
    lows, _, lifts = run(deep(give=1.))
    assert lifts.max() <= dyn.FLOOR_GIVE_LIFT_MAX+1e-9
    assert (lows < 0.).any()
