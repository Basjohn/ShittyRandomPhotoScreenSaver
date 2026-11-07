"""Pulse Rim and the floor lift sized from what the card's camera shows (6 Nov follow-ups to the in-view pulse).

* Pulse Rim reads the published field against one reference level set where a swell carried half the injected
  energy. Every band now carries a full release (Centre Out's two as well, 7 Nov night), so every band in Travelling
  Pulse and Frozen Past publishes RIM_EDGE_SHARE of its light: edge and Centre Out bands light the rims alike, and
  Group Wave and Whole Swell publish their level itself.
* The floor lift considers only the knots the camera can show (the card's visible span plus a lookahead), not a fixed
  +-TROUGH_VIEW: an unseen trough no longer lifts the ribbon, a visible one still does.

Test-owned controls and inputs; structure only, never authored values. Negative controls: Group Wave publishes its
level unscaled, and the model without a supplied span (the fixed +-TROUGH_VIEW)."""
from dataclasses import replace

import pytest
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed

DT = 1/90
SPAN = (-16., 16.)
VIEW = (dyn.PULSE_GRID >= SPAN[0]) & (dyn.PULSE_GRID <= SPAN[1])


def model_for(direction, span=SPAN, mode='Travelling Pulse'):
    model = primed(replace(controls(), rotation_enabled=False,
                           pulse=PulseControls(direction=direction, speed=12., fade=2.5, width=2.5, mode=mode)))
    if span is not None:
        model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=span)
    return model


def in_view(direction):
    """Median over a beating passage of the in-view max of the published rim field and of the appearance level."""
    model, published, level = model_for(direction), [], []
    for index in range(round(12/DT)):
        snapshot = model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=.6 if index % 45 == 0 else 0.)
        if index*DT >= 4.:
            published.append(np.frombuffer(snapshot.pulse, np.float32)[VIEW].max())
            level.append(model._level[VIEW].max())
    return np.median(published), np.median(level)


def test_an_edge_swell_lights_the_rims_as_strongly_as_a_centre_out_swell_not_more():
    (edge, edge_level), (centre, centre_level) = in_view('Head To Tail'), in_view('Centre Out')
    assert .6 <= edge/centre <= 1.35, (edge, centre)
    assert abs(edge/edge_level-dyn.RIM_EDGE_SHARE) < 1e-6 and abs(centre/centre_level-dyn.RIM_EDGE_SHARE) < 1e-6


@pytest.mark.parametrize('direction', ('Head To Tail', 'Centre Out'))
def test_every_band_publishes_the_rim_share_and_the_set_modes_their_level(direction):
    for mode, share in (('Travelling Pulse', dyn.RIM_EDGE_SHARE), ('Frozen Past', dyn.RIM_EDGE_SHARE),
                        ('Group Wave', 1.)):
        model = model_for(direction, mode=mode)
        for index in range(round(3/DT)):
            snapshot = model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=.6 if index % 45 == 0 else 0.)
        assert model._level.max() > 0., mode
        expected = model._level if share == 1. else model._level*share
        assert snapshot.pulse == expected.astype(np.float32).tobytes(), mode


def lift_for(trough_x, span):
    """The whole-ribbon lift target the floor rule sets for a single deep trough at scene x ``trough_x``."""
    model = model_for('Centre Out', span=span)
    model.advance(DT, bands=(.3, .3, .3), intensity=.5, presence=1.)
    x = np.tile(np.linspace(-40., 40., 401), (dyn.RIBBON_CAPACITY, 1))
    height = np.zeros_like(x)
    hang = np.where(np.abs(x-trough_x) < .5, 3., .1)          # a sheet hanging 3 units below rest at one place only
    model._trough_time = None                                  # the first call takes the target at once
    return float(model._height_shift(height, hang, 1., x).max())


def test_only_troughs_the_camera_can_show_lift_the_ribbon():
    canonical = (-5.24, 5.24)
    assert lift_for(3., canonical) > 1.               # a visible trough lifts
    assert lift_for(20., canonical) == 0.             # one far beyond the view and its lookahead does not ...
    assert lift_for(20., None) > 1.                   # ... (negative control: the fixed +-TROUGH_VIEW lifted for it)
    assert lift_for(20., SPAN) > 1.                   # and a larger card that shows (near) it does


def test_the_lookahead_lifts_for_a_trough_just_before_it_enters_the_view():
    model = model_for('Centre Out', span=(-5.24, 5.24))
    _visible, _centre, half = model._trough_view(np.zeros(1))
    assert half > 5.24
    assert lift_for(5.24+.5*(half-5.24), (-5.24, 5.24)) > 1.
