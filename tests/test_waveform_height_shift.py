"""Floor Clearance options (operator, 5 Nov): Dynamic Height Shift (the eased whole-ribbon lift, default), Static Height
(every ribbon holds its own constant height, STATIC_HEIGHT_LIFT) and, with the dynamic shift, Tilt Shift (the side the
history travels toward moves first). Test-owned controls only; structure, never authored values."""
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from tests.test_waveform_trough_clearance import LOUD, deep_model, heights

QUIET = {'bands': (0., 0., 0.), 'intensity': 0., 'presence': 0.}


def configured(**options):
    model = deep_model()
    model.controls = replace(model.controls, **options)
    return model


def run(model, ticks, loud=True):
    frames = []
    for index in range(ticks):
        frames.append(heights(model.advance(1/90, hit=1. if loud and index % 30 == 0 else 0., **(LOUD if loud else QUIET))))
    return frames


def rest_heights(frames):
    return [[y for y, _ in frame] for frame in frames]


def test_static_height_holds_one_constant_lift():
    model = configured(height_mode='Static Height')
    run(model, 270)
    lifts = []
    for loud in (True, False, True):
        for _ in range(90):
            model.advance(1/90, **(LOUD if loud else QUIET))
            lifts.append(model._trough_lift.copy())
    lifts = np.asarray(lifts)[:, :, 0]
    # Constant through loud and quiet passages, the same for every ribbon, at Static Height's own constant (the dynamic
    # shift may now rise higher: its limit covers swell troughs, test_waveform_floor_lift_clears_swells).
    assert np.ptp(lifts) < 1e-6
    assert abs(lifts[0, 0]-dyn.STATIC_HEIGHT_LIFT) < 1e-6


def test_switching_floor_clearance_live_eases_instead_of_jumping():
    model = configured()
    run(model, 180, loud=False)
    model.controls = replace(model.controls, height_mode='Static Height')
    lifts = []
    for _ in range(180):
        model.advance(1/90, **QUIET)
        lifts.append(model._trough_lift.copy())
    lifts = np.asarray(lifts)[:, :, 0]
    assert np.abs(np.diff(lifts, axis=0)).max() < .05
    assert lifts[-1].min() > .9*lifts.max()


def test_tilt_shift_off_is_exactly_the_dynamic_shift():
    plain = rest_heights(run(configured(), 360))
    tilt_off = rest_heights(run(configured(tilt_shift=False), 360))
    for a, b in zip(plain, tilt_off):
        for ya, yb in zip(a, b):
            assert np.array_equal(ya, yb)


def lockstep(schedule):
    """A Tilt Shift model and a plain one on identical input: per tick, per ribbon, the tilted minus the plain heights
    (knots ordered by world x, so index 0 is the far -x end), and the plain model's lift."""
    tilted, flat = configured(tilt_shift=True), configured()
    out, lifts = [], []
    for index, loud in enumerate(schedule):
        hit = 1. if loud and index % 30 == 0 else 0.
        a = heights(tilted.advance(1/90, hit=hit, **(LOUD if loud else QUIET)))
        b = heights(flat.advance(1/90, hit=hit, **(LOUD if loud else QUIET)))
        out.append([ya-yb for (ya, _), (yb, _) in zip(a, b)])
        lifts.append(flat._trough_lift[:len(out[-1]), 0].copy())
    return out, np.asarray(lifts)


SCHEDULE = [(index // 160) % 2 == 0 for index in range(960)]


def test_tilt_shift_leads_on_the_travel_side_rising_and_settling():
    # History travels toward TILT_SIDE (-x): that side lifts first while the lift rises and dips first while it settles.
    frames, lifts = lockstep(SCHEDULE)
    travel = 0 if dyn.TILT_SIDE < 0 else -1
    lead = np.asarray([[offset[travel]-offset[-1-travel] for offset in frame] for frame in frames])
    velocity = np.gradient(lifts, axis=0)*90.
    moving = np.abs(velocity) > .2
    assert moving.sum() > 50 and (velocity[moving] > 0).any() and (velocity[moving] < 0).any()
    # Where the lift clearly moves, the travel side leads in the same direction (allowing for the lead's own easing).
    agree = np.sign(lead[moving]) == np.sign(velocity[moving])
    assert agree.mean() > .9
    for frame in frames:
        for offset in frame:
            assert np.abs(offset).max() <= dyn.TILT_MAX+1e-6
            # A straight tilt across the view: the ribbon's own shape is unchanged.
            # (The lead is clipped beyond the view, so up to one corner per side is the only bend.)
            assert (np.abs(np.diff(offset, 2)) > 1e-4).sum() <= 4


def test_tilt_shift_never_jumps_and_eases_away_when_switched_off():
    frames, _ = lockstep(SCHEDULE)
    ends = np.asarray([[offset[0] for offset in frame] for frame in frames])
    assert np.abs(ends).max() > .05
    assert np.abs(np.diff(ends, axis=0)).max() < .02
    model = configured(tilt_shift=True)
    run(model, 200)
    model.controls = replace(model.controls, tilt_shift=False)
    leads = []
    for _ in range(180):
        model.advance(1/90, **QUIET)
        leads.append(np.abs(model._tilt_lead).max())
    assert leads[0] > 0. and np.abs(np.diff(leads)).max() < .02 and leads[-1] < .02*max(leads[0], 1e-9)+1e-4
