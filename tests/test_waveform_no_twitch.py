"""No twitch (operator, 5 Nov, repeatedly): on beats the body's motion stays velocity-continuous. Per logical tick the
acceleration of the same cloth points is measured under strong beats with the PRODUCTION constants (swell born beyond
the view, eased drives, spread kicks, smooth flow-rule share, fixed surge taper). Test-owned controls; structure only."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_dynamics import PulseControls
from tests.test_waveform_ribbon_dynamics import controls, primed


def accelerations(model, seconds=6., beat_every=24):
    frames = []
    for index in range(round(seconds*90)):
        bands = (.9, .8, .7) if index % beat_every < 3 else (.35, .3, .25)
        snapshot = model.advance(1/90, hit=1. if index % beat_every == 0 else 0., bands=bands, intensity=.8, presence=1.)
        data = np.frombuffer(snapshot.packet.payload, np.float32).reshape(dyn.RIBBON_CAPACITY, -1, 4)
        frames.append(data[:3, 4::KNOT_ROWS, :2].copy())
    P = np.stack(frames[90:])
    acc = np.abs(P[2:]-2*P[1:-1]+P[:-2])  # per tick^2, same ring slot = same cloth point ...
    step = np.abs(np.diff(P[..., 0], axis=0))
    reused = (step[1:] > 1.) | (step[:-1] > 1.)  # ... unless the ring reused the slot for a new knot
    return np.where(reused[..., None], 0., acc)


def test_beats_never_snap_the_body():
    model = primed(replace(controls(), pulse=PulseControls(speed=12., fade=2.5)))
    acc = accelerations(model)
    vertical = acc[..., 1].max()
    sideways = acc[..., 0].max()
    # Before the 5 Nov fixes this case measured 0.155 (vertical) and 0.114 (sideways) per tick^2: 45 ms drive snaps,
    # instantaneous spring kicks, a swell born mid-view, whole-field share/compression jumps and a drift-sized taper.
    assert vertical < .02, vertical
    assert sideways < .01, sideways
