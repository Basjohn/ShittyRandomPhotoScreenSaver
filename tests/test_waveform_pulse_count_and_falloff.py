"""Pulse Count and Pulse Falloff (operator, 7 Nov night: "Why are there two pulses at once in your image? ... If this
number is intentional it should be editable 1-3 or so at once? With adjustable falloff to the sides too.")

* Pulse Count: at most that many pulses are still to come or in the framed view at once (Travelling Pulse and Frozen
  Past); a Centre Out pair is one pulse; a pulse that has left the view frees its place for the next onset.
* Pulse Falloff: a band is full over its Pulse Width core and fades out over Pulse Falloff at each side; that window is
  its light and, in Frozen Past, where the cloth follows the music.

Test-owned controls and inputs with the production constants; structure only, never authored values."""
from dataclasses import replace

import numpy as np
import pytest

import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed

DT = 1/90
SPAN = (-16., 16.)


def model_for(count=2, falloff=1., direction='Head To Tail', mode='Travelling Pulse', width=2.5):
    model = primed(replace(controls(), rotation_enabled=False,
                           pulse=PulseControls(direction=direction, speed=12., fade=6., width=width, mode=mode,
                                               count=count, falloff=falloff)))
    model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=SPAN)
    return model


def pulses_in_view(model):
    """Distinct launches (a Centre Out pair shares one) whose window overlaps the view, among bands still present."""
    p = model.controls.pulse
    reach = .5*p.width+p.falloff
    return len({band[4] for band in model._bands if band[3] >= dyn.BAND_PRESENT
                and band[0]+reach >= SPAN[0] and band[0]-reach <= SPAN[1]})


def beating(model, seconds=8., every=.25):
    seen = []
    for index in range(round(seconds/DT)):
        model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=.8 if index % round(every/DT) == 0 else 0.)
        if index*DT > 3.:
            seen.append(pulses_in_view(model))
    return np.asarray(seen)


@pytest.mark.parametrize('direction', ('Head To Tail', 'Tail To Head', 'Centre Out'))
@pytest.mark.parametrize('count', (1, 2, 3))
def test_no_more_pulses_than_pulse_count_are_in_view(count, direction):
    seen = beating(model_for(count=count, direction=direction))
    assert seen.max() == count, (seen.max(), count)   # dense beats fill the count, never more


def test_a_centre_out_pair_is_one_pulse():
    model = model_for(count=1, direction='Centre Out')
    seen = beating(model, seconds=4.)
    assert seen.max() == 1
    p = model.controls.pulse
    reach = .5*p.width+p.falloff
    shown = [band for band in model._bands if band[3] >= dyn.BAND_PRESENT and abs(band[0])-reach <= SPAN[1]]
    assert len(shown) == 2 and shown[0][4] == shown[1][4] and shown[0][1] == -shown[1][1]   # one launch, one each way


def test_a_pulse_that_has_left_the_view_frees_its_place():
    model = model_for(count=1)
    model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=1.)
    first = len(model._bands)
    for _ in range(round(1./DT)):                      # onsets while the pulse crosses: no second launch
        model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=.8)
    assert len(model._bands) == first
    p = model.controls.pulse
    reach = .5*p.width+p.falloff
    (band,) = model._bands
    assert band[1] < 0.                                # Head To Tail: born beyond the +x edge, travelling toward -x
    for _ in range(round(6./DT)):                      # no onsets until the pulse has left through the -x edge
        if band[0]+reach < SPAN[0]:
            break
        model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1.)
    assert band[0]+reach < SPAN[0] and band[3] >= dyn.BAND_PRESENT   # gone from view, though not faded
    model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=1.)
    assert len(model._bands) > first                   # it has left: the next onset launches


@pytest.mark.parametrize('falloff', (.5, 2.))
def test_pulse_falloff_is_the_band_window_and_its_light(falloff):
    model = model_for(count=1, falloff=falloff, mode='Frozen Past')
    model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=1.)
    for _ in range(round(1.2/DT)):
        model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1.)
    (position, _sign, strength, _target, _age), = [band for band in model._bands]
    distance = np.abs(dyn.PULSE_GRID-position)
    half = .5*model.controls.pulse.width
    presence, light = model._band_presence, model._band_light
    assert (presence[distance <= half] == 1.).all()                 # the core is full
    assert (presence[distance >= half+falloff] == 0.).all()         # nothing beyond the falloff
    ramp = (distance > half) & (distance < half+falloff)
    assert ramp.sum() >= 2*int(falloff/dyn.PULSE_DX)-2 and (presence[ramp] > 0.).all() and (presence[ramp] < 1.).all()
    order = np.argsort(distance)
    assert (np.diff(presence[order]) <= 1e-12).all()                # it only falls away from the band
    peak = 1.-np.exp(-strength/dyn.APP_SCALE)
    np.testing.assert_allclose(light, peak*presence, rtol=0., atol=1e-12)   # the light is the same window


def test_pulse_count_and_falloff_are_validated():
    for bad in ({'count': 0}, {'count': 4}, {'falloff': .1}, {'falloff': 13.}):
        with pytest.raises(ValueError):
            PulseControls(**bad)


# Operator, 7 Nov night: "You can also twist, particle flair, strand and rotate when capped but if that is a problem the
# way it is now you could make the freeze SLOWLY deflate as an optional setting."

def kicked(count, kick_accent=1., level=.5, seconds=8., every=.75):
    """Kick Accent's eased share (its twist and strand channels read it) summed over a beating passage whose Pulse
    Strength drive stays BELOW the geometry knee, so only the pulses' case can engage it."""
    model = primed(replace(controls(), kick_accent=kick_accent,
                           pulse=PulseControls(speed=12., fade=6., width=2.5, count=count, falloff=1.)))
    model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=SPAN)
    total, bend = 0., []
    for index in range(round(seconds/DT)):
        model.advance(DT, bands=(level*.6, level*.5, level*.4), intensity=level, presence=1.,
                      hit=.8 if index % round(every/DT) == 0 else 0.)
        if index*DT > 3.:
            total += model._kick_stage*DT
            bend.append(model.drive['bend'])
    return total, max(bend)


def test_a_kick_the_pulses_cannot_show_goes_to_kick_accent():
    capped, bend = kicked(count=1)
    assert bend < dyn.KICK_SENSE_KNEE                 # the geometry still has headroom: only the pulses are full
    room, _ = kicked(count=3)
    # Kicks spaced wider than a launch needs: with places free each launches its own pulse; with one place, the kicks
    # while it crosses go to the accent.
    assert capped > 0. and capped > 1.5*room, (capped, room)
    off, _ = kicked(count=1, kick_accent=0.)
    assert off == 0.                                   # negative control: Kick Accent 0 adds nothing


def test_kick_accent_nudges_the_twist_in_its_own_direction_and_bounded():
    model = primed(replace(controls(), kick_accent=1., rotation_enabled=False,
                           pulse=PulseControls(speed=12., fade=6., width=2.5, count=1, falloff=1.)))
    model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=SPAN)
    low, high = model.controls.twist_speed
    extra, phase = [], model._twist_total
    for index in range(round(8/DT)):
        model.advance(DT, bands=(.3, .25, .2), intensity=.5, presence=1., hit=.8 if index % round(.25/DT) == 0 else 0.)
        plain = low+(high-low)*model.drive['twist']
        extra.append((model._twist_total-phase)/DT-plain)
        phase = model._twist_total
    extra = np.asarray(extra)
    assert extra.max() > 0. and extra.min() >= -1e-9                     # it only ever adds, in the twist's direction
    assert extra.max() <= dyn.KICK_ROLL_SHARE*high+1e-9                  # bounded by the twist's own speed
    assert np.abs(np.diff(extra)).max() < .25*extra.max()                # eased: never a step


@pytest.mark.parametrize('deflate', (0., 2.))
def test_freeze_deflate_eases_held_cloth_back_toward_the_current_body(deflate):
    model = primed(replace(controls(), pulse=PulseControls(direction='Tail To Head', speed=12., fade=4., width=3.,
                                                           mode='Frozen Past', count=2, falloff=1., deflate=deflate)))
    model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=SPAN)
    height = list(dyn.FROZEN_BODY).index('height')
    for index in range(round(4/DT)):                   # loud, with onsets: bands shape the cloth loud
        model.advance(DT, bands=(.9, .8, .7), intensity=.95, presence=1., hit=1. if index % 90 == 0 else 0.)
    for _ in range(round(4/DT)):                       # let the bands leave the view: no onsets, soft
        model.advance(DT, bands=(.15, .12, .1), intensity=.2, presence=1.)
    cells = np.flatnonzero(np.abs(model._frozen_cells()) <= 10.)
    before, rolled = model._frozen_state[height][cells].copy(), model._frozen_rolled
    for _ in range(round(3*max(deflate, 1.)/DT)):      # three deflate times more of the same soft music, no bands
        model.advance(DT, bands=(.15, .12, .1), intensity=.2, presence=1.)
    assert not model._band_presence.any()
    live = dyn.unit(model.drive['height'])
    same = cells-(model._frozen_rolled-rolled)       # the same cloth cells: the held grid rolled with the cloth
    before, after = before[same >= 0], model._frozen_state[height][same[same >= 0]]
    if deflate:
        assert np.abs(after-live).max() < .1*np.abs(before-live).max()+1e-3   # eased most of the way back
    else:
        assert np.abs(after-before).max() < 1e-9       # off: held exactly until a pulse arrives
