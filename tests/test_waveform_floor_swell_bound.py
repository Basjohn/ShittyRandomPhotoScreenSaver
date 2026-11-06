"""The floor is never hit (operator, 5 Nov: "we collide with the floor a lot", then "the floor is never hit and the
shape never changes"). Since swells reach the view at strength (6 Nov), their troughs need more lift than the whole-ribbon
lift may give; the swell's gain is then bounded (one scalar over the field, so the flow rule holds and the ribbon keeps
its own shape) so every visible lower edge stays above the floor. Floor Give keeps its authored contact.

Test-owned controls and inputs, production constants. Negative control: the same run with the bound off (as on main)
puts visible troughs below the floor."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed
from tests.test_waveform_no_twitch import accelerations

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


def lowest_visible_edge(snapshot):
    """Lowest sheet edge (world y; the floor is 0) over the knots the camera shows."""
    data = np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)
    out = np.inf
    for path in data:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        if count < 8 or path[2, 3] <= .02:
            continue
        knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start+np.arange(count)) % capacity]
        x = knots[:, 0, 0]+snapshot.packet.world_origin[0]+snapshot.head_x-snapshot.travel
        inside = (x >= SPAN[0]) & (x <= SPAN[1])
        edge = snapshot.packet.world_origin[1]+knots[inside, 0, 1]-np.abs(knots[inside, 0, 3]*np.cos(knots[inside, 1, 1]))
        out = min(out, float(edge.min()))
    return out


def run(model, seconds=8.):
    lows = []
    for index in range(round(seconds*90)):
        lows.append(lowest_visible_edge(model.advance(1/90, hit=1. if index % 30 == 0 else 0., **LOUD)))
    return np.asarray(lows[180:])


def test_visible_troughs_stay_above_the_floor(monkeypatch):
    bounded = run(deep())
    assert bounded.min() > 0., bounded.min()
    with monkeypatch.context() as off:          # negative control: the swell unbounded, as on main
        off.setattr(dyn.WaveformDynamics, '_floor_share', lambda self, *args: 1.)
        unbounded = run(deep())
    assert (unbounded < 0.).mean() > .1, (unbounded < 0.).mean()


def test_the_bound_eases_without_adding_twitch(monkeypatch):
    """tests/test_waveform_no_twitch.py's per-tick acceleration probe on the same deep configuration, with and without
    the bound: scaling the swell through two eased stages adds no snap of its own."""
    model, shares = deep(), []
    original = dyn.WaveformDynamics._floor_share
    def spy(self, *args):
        shares.append(original(self, *args))
        return shares[-1]
    monkeypatch.setattr(dyn.WaveformDynamics, '_floor_share', spy)
    bounded = accelerations(model)
    assert min(shares) < .9                                   # it binds here
    monkeypatch.setattr(dyn.WaveformDynamics, '_floor_share', lambda self, *args: 1.)
    unbounded = accelerations(deep())
    for axis in (0, 1):
        assert bounded[..., axis].max() <= 1.1*unbounded[..., axis].max()+1e-3, axis


def test_floor_give_keeps_its_authored_contact():
    model = deep(give=1.)
    run(model, seconds=3.)
    assert model._floor_bound[1] == 1.
