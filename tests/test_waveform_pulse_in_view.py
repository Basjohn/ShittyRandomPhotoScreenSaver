"""The travelling swell is born and travels where the framed camera looks (operator, 6 Nov: Presets 1-3, Head To Tail
Travelling Pulse, "barely show a swell in view" while Centre Out Preset 4 reads clearly). The capture supplies the
scene-axis span the camera shows (``view_span``); Travelling Pulse edge swells are born just beyond it and age only once
seen. Test-owned controls and inputs with the PRODUCTION constants; structure only, never authored values.

Negative control: without a supplied span (as on main, where the swell is born at the fixed PULSE_ORIGIN and fades on
its way in) the same beats leave the view almost flat."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed, data
from tests.test_waveform_no_twitch import accelerations

DT = 1/90
SPAN = (-16., 16.)   # a large CUSTOM card's view of the scene axis (core.waveform_ribbon_view.visible_span)
VIEW = (dyn.PULSE_GRID >= SPAN[0]) & (dyn.PULSE_GRID <= SPAN[1])


def model_for(direction='Head To Tail', mode='Travelling Pulse', span=SPAN):
    model = primed(replace(controls(), rotation_enabled=False,
                           pulse=PulseControls(direction=direction, speed=12., fade=2.5, width=2.5, mode=mode)))
    if span is not None:
        model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=span)
    return model


def beating(model, seconds=12., every=.5, sample=None):
    out = []
    for index in range(round(seconds/DT)):
        snapshot = model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1.,
                                 hit=.6 if index % round(every/DT) == 0 else 0.)
        if index*DT >= 4.:
            out.append(sample(model, snapshot) if sample else model._geom_share[0]*model._geom[VIEW].max())
    return np.asarray(out)


def test_a_head_to_tail_swell_is_visible_inside_the_framed_view():
    seen, unseen = np.median(beating(model_for())), np.median(beating(model_for(span=None)))
    assert seen >= .5, seen          # a beat's swell reaches the view at strength (Centre Out's in-view level ~1)
    assert unseen < .25*seen, unseen  # negative control: born at PULSE_ORIGIN it arrives faded


def test_the_swell_is_born_beyond_the_view_and_slides_in_formed():
    """No swell pops into existence inside the view: one beat's in-view swell grows over several ticks from ~0."""
    model = model_for()
    model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=1.)
    trace = [model._geom_share[0]*model._geom[VIEW].max()]
    for _ in range(round(2./DT)):
        model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1.)
        trace.append(model._geom_share[0]*model._geom[VIEW].max())
    trace = np.asarray(trace)
    assert trace[0] < .05*trace.max(), (trace[0], trace.max())
    assert np.abs(np.diff(trace)).max() < .1*trace.max(), np.abs(np.diff(trace)).max()


def test_tail_to_head_is_born_at_the_other_edge():
    model = model_for(direction='Tail To Head')
    model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1., hit=1.)
    for _ in range(round(.3/DT)):
        model.advance(DT, bands=(.6, .5, .4), intensity=.75, presence=1.)
    x = dyn.PULSE_GRID[np.argmax(model._fresh[1])]
    assert SPAN[0]-20. < x < SPAN[0], x


def test_centre_out_and_the_other_modes_ignore_the_span_byte_for_byte():
    for direction, mode in (('Centre Out', 'Travelling Pulse'), ('Head To Tail', 'Group Wave'),
                            ('Tail To Head', 'Frozen Past'), ('Head To Tail', 'Whole Swell')):
        payload = lambda m, s: s.packet.payload + s.pulse
        with_span = beating(model_for(direction, mode), seconds=6., sample=payload)
        without = beating(model_for(direction, mode, span=None), seconds=6., sample=payload)
        assert (with_span == without).all(), (direction, mode)


def test_in_view_swells_never_snap_the_body():
    """tests/test_waveform_no_twitch.py's probe with the swells actually reaching the cloth. Its .02/.01 bounds were
    met by Head To Tail swells that arrived faded; visible swells move the cloth more (6 Nov, same probe: Centre Out
    .016/.015, Group Wave .021/.014, Head To Tail in view .028/.012 at +-16 and .030/.016 at +-5), all far below the
    .155/.114 per tick^2 of the pre-5 Nov snaps."""
    for span in (SPAN, (-5.24, 5.24)):
        model = primed(replace(controls(), breathing=1., pulse=PulseControls(speed=12., fade=2.5)))
        model.advance(0., bands=(0., 0., 0.), intensity=0., presence=0., view_span=span)
        acc = accelerations(model)
        assert acc[..., 1].max() < .035, (span, acc[..., 1].max())
        assert acc[..., 0].max() < .02, (span, acc[..., 0].max())
