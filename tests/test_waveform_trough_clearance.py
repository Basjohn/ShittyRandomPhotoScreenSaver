"""Troughs never meet the floor and the shape never changes (operator, 5 Nov: "we collide with the floor a lot";
then per-knot trough limits made boxy flat-bottomed troughs "instead of FLOWING"). The floor rule only lifts a
ribbon as a whole. Test-owned controls only; structure, never authored values."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed

LOUD = {'bands': (.95, .9, .85), 'intensity': 1., 'presence': 1.}


def deep_model():
    c = replace(controls(), rotation_enabled=False, pulse=PulseControls(width=6., speed=18., fade=2.))
    # Loud, preset-range height and a strong swell, at a preset-range lift.
    c = replace(c, ranges={**c.ranges, 'height': (1.5, 2.4), 'bend': (2., 2.8), 'lift': (.8, 1.)})
    return primed(c)


def heights(snapshot):
    data = np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)
    out = []
    for path in data:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        if count < 8 or path[2, 3] <= .02:
            continue
        knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start+np.arange(count)) % capacity]
        y = knots[:, 0, 1]+snapshot.packet.world_origin[1]
        hang = np.abs(knots[:, 0, 3]*np.cos(knots[:, 1, 1]))
        out.append((y, y-hang))
    return out


def run(model, seconds=6.):
    lowest, rises, frames = [], [], []
    for index in range(round(seconds*90)):
        frame = model.advance(1/90, hit=1. if index % 30 == 0 else 0., **LOUD)
        rises.append(model._trough_lift.copy())
        frames.append(heights(frame))
        lowest.append(min(edge.min() for _, edge in frames[-1]))
    return np.asarray(lowest[90:]), np.asarray(rises), frames


def test_the_floor_rule_only_lifts_each_ribbon_as_a_whole_and_keeps_it_off_the_floor(monkeypatch):
    lowest, rises, bounded = run(deep_model())
    with monkeypatch.context() as off:
        off.setattr(dyn, 'TROUGH_LIFT_MAX', 0.)
        unbounded_lowest, _, unbounded = run(deep_model())
    # Shape preserved exactly: every ribbon is the unbounded ribbon plus one vertical offset (its rise).
    for tick in range(90, len(bounded), 37):
        for (y, _), (y0, _) in zip(bounded[tick], unbounded[tick]):
            offset = y-y0
            assert np.ptp(offset) < 1e-4
    # It actually lifts the sheet's lower edge: far higher than without it, at every percentile. (In this deliberately
    # extreme case the bounded rise cannot clear every swell-deepened trough; the optional floor deformation does.)
    for q in (10, 50, 90):
        assert np.percentile(lowest, q) > np.percentile(unbounded_lowest, q)+.5
    # The rise eases (attack/release on the logical clock), never in one jump: no tick carries more than a fortieth
    # of the largest rise (a jump would carry all of it).
    assert np.abs(np.diff(rises[:, :, 0], axis=0)).max() < .025*rises.max()
