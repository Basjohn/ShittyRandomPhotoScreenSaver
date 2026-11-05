"""No twitch (operator, 5 Nov, repeatedly): on beats the body's motion stays velocity-continuous. Per logical tick the
acceleration of the same cloth points is measured under strong beats with the PRODUCTION constants (swell born beyond
the view, eased drives, spread kicks, smooth flow-rule share, fixed surge taper). Test-owned controls; structure only."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed


def accelerations(model, seconds=6., beat_every=24, beat=(.9, .8, .7), rest=(.35, .3, .25), intensity=.8):
    frames = []
    for index in range(round(seconds*90)):
        bands = beat if index % beat_every < 3 else rest
        snapshot = model.advance(1/90, hit=1. if index % beat_every == 0 else 0., bands=bands, intensity=intensity, presence=1.)
        data = np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)
        frames.append(data[:3, 4::KNOT_ROWS, :2].copy())
    P = np.stack(frames[90:])
    acc = np.abs(P[2:]-2*P[1:-1]+P[:-2])  # per tick^2, same ring slot = same cloth point ...
    step = np.abs(np.diff(P[..., 0], axis=0))
    reused = (step[1:] > 1.) | (step[:-1] > 1.)  # ... unless the ring reused the slot for a new knot
    return np.where(reused[..., None], 0., acc)


def test_beats_never_snap_the_body():
    model = primed(replace(controls(), breathing=1., pulse=PulseControls(speed=12., fade=2.5)))
    acc = accelerations(model)
    vertical = acc[..., 1].max()
    sideways = acc[..., 0].max()
    # Before the 5 Nov fixes this case measured 0.155 (vertical) and 0.114 (sideways) per tick^2: 45 ms drive snaps,
    # instantaneous spring kicks, a swell born mid-view, whole-field share/compression jumps and a drift-sized taper.
    assert vertical < .02, vertical
    assert sideways < .01, sideways


def test_soft_beats_never_snap_the_body_while_the_passage_breathes():
    # Breathing widens a soft passage's swings and shortens its release (operator, 5 Nov); its beats keep the same
    # no-twitch bounds as loud ones (two cascaded followers, spread kicks, rate-limited bounds).
    model = primed(replace(controls(), breathing=1., pulse=PulseControls(speed=12., fade=2.5)))
    acc = accelerations(model, beat=(.45, .4, .35), rest=(.2, .15, .1), intensity=.3)
    assert acc[..., 1].max() < .02, acc[..., 1].max()
    assert acc[..., 0].max() < .01, acc[..., 0].max()
