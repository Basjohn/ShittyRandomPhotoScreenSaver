"""Fixed response, break-proof Breathing and Kick Accent (operator, 6 Nov: "when it went suddenly quiet everything
became more reactive pointing to bad adaptive logic. Adaptive is a very problematic approach"; "many sustained kicks
ignored ... Something for a sense of them?"; "make whatever adaptive remains turn off able").

Test-owned controls and inputs with the production constants; structure only, never authored values. Negative
controls: a test-owned remembered-peak gain (the retired Adaptive Response, 7 Nov) re-scales what follows a break and
remembers a prelude; Kick Accent 0 adds nothing. The response is memoryless (tests/test_waveform_memoryless_response.py)."""
import math
from dataclasses import replace
import numpy as np
import core.waveform_ribbon_dynamics as dyn
from tests.test_waveform_ribbon_dynamics import controls, primed
from tests.test_waveform_no_twitch import accelerations

DT = 1/90
SILENT = dict(bands=(0., 0., 0.), intensity=0., presence=0.)


def remembered_peak(monkeypatch):
    """Negative control: a test-owned running-level normaliser (each drive divided by a 10 s mean of its own target, the
    shape of every learned level agents added). Proves the measurement sees a response that remembers the music."""
    import math as _math
    means = {}

    def adaptive(target, key):
        mean = means.get(key, target)
        mean = means[key] = target+(mean-target)*_math.exp(-(1/90)/10.)
        return min(1., .6*target/max(.2, mean))
    monkeypatch.setattr(dyn, 'fixed_response', adaptive)


def phrase(t, level=1., uneven=False):
    """Loud phrases (a 3 s swell), a kick every half second. ``uneven``: as real music, the song's peaks are rare (one
    phrase in four at full level, the rest at 70%), so a remembered peak is set by moments a break can fall between."""
    swell = 1. if t % 3. < 1. else 0.
    if uneven and t % 12. >= 3.:
        level *= .7
    return dict(bands=tuple(level*(.6+.4*swell)*share for share in (1., .85, .7)), intensity=level*(.7+.3*swell),
                presence=1., hit=.5*level if t % .5 < DT else 0.)


def run(c, seconds, break_at=None, break_for=0., prelude=None, level=1., uneven=False):
    """(time, height drive, bend drive) per tick; the phrase clock never stops, so the music after a break is the music
    the control hears at the same time."""
    model = primed(c)
    if prelude is not None:
        for index in range(round(20/DT)):
            model.advance(DT, **phrase(index*DT, prelude))
    rows = []
    for index in range(round(seconds/DT)):
        t = index*DT
        silent = break_at is not None and break_at <= t < break_at+break_for
        model.advance(DT, **(SILENT if silent else phrase(t, level, uneven)))
        rows.append((t, model.drive['height'], model.drive['bend']))
    return np.asarray(rows)


def after(rows, start, end):
    window = rows[(rows[:, 0] >= start) & (rows[:, 0] < end)]
    return window[:, 1:].mean(axis=0)


def break_change(c, length, signed=False):
    """Largest relative change of the mean height/bend drives 1.5-12 s after a break against the unbroken control
    (``signed``: the largest swell, negative when what follows is only smaller)."""
    control, broken = run(c, 48., uneven=True), run(c, 48., break_at=27., break_for=length, uneven=True)
    end = 27.+length
    change = after(broken, end+1.5, end+12.)/after(control, end+1.5, end+12.)-1.
    return float(change.max()) if signed else float(np.abs(change).max())


def test_a_two_to_five_second_break_does_not_rescale_what_follows(monkeypatch):
    c = replace(controls(), breathing=1.)
    for length in (2., 5.):
        # Memoryless: once the followers have taken the music back (1.5 s), what follows is what the unbroken song draws.
        assert break_change(c, length) < .01, length
    # Negative control: a remembered peak sizes what follows differently until the song's next peak.
    remembered_peak(monkeypatch)
    assert break_change(c, 5.) > .05


def louder_after_break_change(c, length=5.):
    """A break that falls where the song gets louder (level .55 before 27 s, 1 from then on): the largest relative
    change of the mean height/bend drives 1.5-12 s after the break against the unbroken control. The control's phrase
    mean followed the louder music through those seconds; the broken run's held the quieter level through the silence."""
    def go(broken):
        model, rows = primed(c), []
        for index in range(round(48./DT)):
            t = index*DT
            silent = broken and 27. <= t < 27.+length
            model.advance(DT, **(SILENT if silent else phrase(t, .55 if t < 27. else 1.)))
            rows.append((t, model.drive['height'], model.drive['bend']))
        return np.asarray(rows)
    end = 27.+length
    return float(np.abs(after(go(True), end+1.5, end+12.)/after(go(False), end+1.5, end+12.)-1.).max())


def test_a_break_where_the_song_gets_louder_does_not_swell_what_follows(monkeypatch):
    """Recorded music with spliced 2-5 s breaks: the former phrase widening of a returning passage against a mean held
    through the silence sized the following 10 s 7-17% up. Memoryless, the return is the unbroken song."""
    c = replace(controls(), breathing=0.)
    settled = louder_after_break_change(c)
    assert settled < .01, settled
    remembered_peak(monkeypatch)   # negative control
    assert louder_after_break_change(c) > settled+.03


def test_the_response_remembers_nothing(monkeypatch):
    """What came before (a loud or a quiet prelude) never changes the size of what follows. A remembered peak sizes the
    same passage differently for its 30 s memory (negative control)."""
    c = replace(controls(), breathing=0.)
    loud, quiet = run(c, 20., prelude=1., level=.6), run(c, 20., prelude=.3, level=.6)
    assert np.abs(after(loud, 16., 20.)-after(quiet, 16., 20.)).max() < 5e-3
    remembered_peak(monkeypatch)
    loud, quiet = run(c, 20., prelude=1., level=.6), run(c, 20., prelude=.3, level=.6)
    assert np.abs(after(loud, 16., 20.)-after(quiet, 16., 20.)).max() > .05


def roll_and_births(kick_accent, level=1.):
    """Roll speed above the plain roll after each kick of a sustained loud passage, and the spark births it banked."""
    model = primed(replace(controls(), kick_accent=kick_accent))
    rises, births, angle = [], 0., model.angle
    for index in range(round(12/DT)):
        t = index*DT
        before = model._pulse_births
        model.advance(DT, **phrase(t, level))
        speed = math.degrees(math.remainder(model.angle-angle, 2*math.pi))/DT
        angle = model.angle
        if t > 6.:
            rises.append(speed-model.angular_speed)
            births += max(0., model._pulse_births-before)
    return np.asarray(rises), births


def test_a_sustained_loud_kick_turns_the_roll_and_banks_sparks_without_twitching():
    rises, _ = roll_and_births(.7)
    assert rises.max() > 5., rises.max()                  # a felt, brief roll on each kick (degrees per second)
    off, _ = roll_and_births(0.)
    assert np.abs(off).max() < 1e-9                         # negative control: Kick Accent 0 adds nothing
    quiet, _ = roll_and_births(.7, level=.25)               # a passage with geometry headroom keeps it to the swell
    assert quiet.max() < .25*rises.max()
    base = accelerations(primed(controls()))
    kicked = accelerations(primed(replace(controls(), kick_accent=1.)))
    for axis in (0, 1):
        assert kicked[..., axis].max() <= 1.1*base[..., axis].max()+1e-3, axis


def test_kick_accent_banks_spark_births_only_with_sparks():
    from core.ribbon_bursts import RibbonAccentControls
    from types import MappingProxyType
    ranges = MappingProxyType({key: (1., 2.) for key in ('spark_count', 'spark_lifetime', 'spark_drift', 'spark_rise',
                                                        'spark_size', 'spark_light', 'spark_white', 'spark_glow')}
                              | {'spark_span': (10., 20.)})
    model = primed(replace(controls(), kick_accent=1., accents=RibbonAccentControls(ranges)))
    banked = 0.
    for index in range(round(8/DT)):
        before = model._pulse_births
        model.advance(DT, **phrase(index*DT))
        banked += max(0., model._pulse_births-before)
    assert banked > 1.
    _, none = roll_and_births(1.)                            # no sparks control: nothing is banked
    assert none == 0.
